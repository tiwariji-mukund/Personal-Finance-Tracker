from django.utils import timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from apps.finance.models import Account, Category, Transaction
from apps.finance.services import (
    TransactionInputError,
    active_accounts,
    active_categories,
    create_transaction,
    delete_transaction,
    parse_amount,
    record_transaction,
    resolve_transaction,
    update_transaction,
)

# ponytail: fixed cap, no pagination — add a /transactions <n> argument or
# paging if a flat recent-N list stops being enough.
TRANSACTION_HISTORY_LIMIT = 10

BUTTONS_PER_ROW = 2

# Category/account picker state travels in the callback_data itself
# ('cat|TYPE|amount|category_id', 'acc|TYPE|amount|category_id|account_id')
# rather than a server-side pending-transaction table — there's nothing to
# expire or clean up, and a button still works correctly no matter how long
# it sits unanswered.
# ponytail: the picker flow doesn't collect a description — type the full
# "/expense <amount> <category> <description>" form for that.

# ponytail: in-memory only (module-level dict), keyed by chat id — tracks a
# chat that just sent a bare /expense or /income and is expected to reply
# with the amount next. Lost on process restart and not shared across
# multiple worker processes; move to a DB-backed table if either becomes a
# real problem for this single-process personal bot.
_PENDING_AMOUNT_PROMPTS = {}

AMOUNT_PROMPTS = {
    Transaction.TransactionType.EXPENSE: '💸 How much did you spend?',
    Transaction.TransactionType.INCOME: '💵 How much did you receive?',
}

EXAMPLES = {
    Transaction.TransactionType.EXPENSE: '/expense 250 food swiggy dinner',
    Transaction.TransactionType.INCOME: '/income 50000 salary august payout',
}

# (emoji, verb) used to phrase the confirmation as a natural sentence, e.g.
# "💸 ₹200.00 spent on Travel — petrol".
PHRASING = {
    Transaction.TransactionType.EXPENSE: ('💸', 'spent on'),
    Transaction.TransactionType.INCOME: ('💵', 'received as'),
}

# Registered with Telegram via the set_bot_commands management command so they
# show up as tap-to-fill suggestions instead of needing to be typed by hand.
# Keep descriptions short and syntax-free — detailed usage belongs in /help.
BOT_COMMANDS = [
    ('start', 'Start the finance tracker'),
    ('help', 'Show available commands'),
    ('expense', 'Add an expense'),
    ('income', 'Add income'),
    ('transactions', 'View recent transactions'),
    ('edit', 'Edit a transaction'),
    ('delete', 'Delete a transaction'),
]


def _active_category_names():
    return ', '.join(Category.objects.filter(is_active=True).order_by('name').values_list('name', flat=True))


def build_welcome_message():
    return (
        '👋 Hey! Welcome to your Personal Finance Tracker.\n\n'
        '💰 Your money, your rules — right here in this chat.\n\n'
        "I'll help you keep track of:\n"
        '• 💸 Expenses\n'
        '• 💵 Income\n'
        '• 📜 Your transaction history\n'
        '• 🎯 Where your money is actually going\n\n'
        "No spreadsheets, no forms — just send me a quick command and I'll log it.\n\n"
        'For example:\n'
        '👉 /expense 450 food\n'
        '👉 /income 75000 salary\n\n'
        "📈 Over time you'll be able to look back and see exactly where it all went.\n\n"
        'Type /help to see everything I can do.'
    )


def build_help_message():
    lines = [
        '📖 How can I help?',
        '',
        '💸 TRANSACTIONS',
        '',
        'Add an expense:',
        f'👉 {EXAMPLES[Transaction.TransactionType.EXPENSE]}',
        '',
        'Add income:',
        f'👉 {EXAMPLES[Transaction.TransactionType.INCOME]}',
        '',
        "Not sure of the category? Just tap /expense or /income — I'll ask",
        "for the amount, then show buttons to pick from.",
        '',
        'View recent transactions:',
        '👉 /transactions',
        '',
        '✏️ MANAGE',
        '',
        'Edit a transaction (get the id from /transactions):',
        '👉 /edit 12 300 travel petrol',
        '',
        'Delete a transaction:',
        '👉 /delete 12',
    ]

    categories = _active_category_names()
    if categories:
        lines += ['', '📂 CATEGORIES', categories]

    lines += [
        '',
        '🆕 COMING SOON',
        'Monthly summaries and spending breakdowns.',
        '',
        '➕ OTHER',
        'Start over: /start',
    ]

    return '\n'.join(lines)


def _format_transaction(transaction, *, with_date=False):
    emoji, verb = PHRASING[transaction.transaction_type]
    line = f'#{transaction.pk} {emoji} ₹{transaction.amount:.2f} {verb} {transaction.category.name}'
    if transaction.description:
        line += f' — {transaction.description}'
    if with_date:
        line += f' ({timezone.localtime(transaction.transaction_at):%d %b})'
    return line


def build_transaction_history_message():
    transactions = Transaction.objects.select_related('category')[:TRANSACTION_HISTORY_LIMIT]
    if not transactions:
        return '📭 No transactions yet. Try /expense or /income to add one.'

    lines = ['📜 Recent transactions', '']
    lines += [_format_transaction(transaction, with_date=True) for transaction in transactions]
    return '\n'.join(lines)


def _buttons_in_rows(buttons):
    return [buttons[i:i + BUTTONS_PER_ROW] for i in range(0, len(buttons), BUTTONS_PER_ROW)]


def build_category_picker(transaction_type, amount_raw):
    try:
        amount = parse_amount(amount_raw)
    except TransactionInputError as exc:
        return f'❌ {exc}'

    categories = list(active_categories())
    if not categories:
        return '❌ No active categories configured.'

    buttons = [
        InlineKeyboardButton(
            f'{category.icon} {category.name}'.strip(),
            callback_data=f'cat|{transaction_type}|{amount}|{category.pk}',
        )
        for category in categories
    ]

    emoji, _ = PHRASING[transaction_type]
    prompt = f'{emoji} ₹{amount:.2f} — pick a category:'
    return prompt, InlineKeyboardMarkup(_buttons_in_rows(buttons))


def handle_category_selected(callback_data):
    _, transaction_type, amount_raw, category_id = callback_data.split('|')

    category = Category.objects.filter(pk=category_id, is_active=True).first()
    if not category:
        return '❌ That category is no longer available.'

    accounts = list(active_accounts())
    if not accounts:
        return '❌ No active account is configured.'

    if len(accounts) == 1:
        transaction = create_transaction(
            transaction_type=transaction_type,
            amount=parse_amount(amount_raw),
            category=category,
            account=accounts[0],
        )
        return _format_transaction(transaction)

    buttons = [
        InlineKeyboardButton(
            account.name,
            callback_data=f'acc|{transaction_type}|{amount_raw}|{category_id}|{account.pk}',
        )
        for account in accounts
    ]
    prompt = f'{category.icon} {category.name} — pick an account:'
    return prompt, InlineKeyboardMarkup(_buttons_in_rows(buttons))


def handle_account_selected(callback_data):
    _, transaction_type, amount_raw, category_id, account_id = callback_data.split('|')

    category = Category.objects.filter(pk=category_id, is_active=True).first()
    account = Account.objects.filter(pk=account_id, is_active=True).first()
    if not category or not account:
        return '❌ That option is no longer available.'

    transaction = create_transaction(
        transaction_type=transaction_type,
        amount=parse_amount(amount_raw),
        category=category,
        account=account,
    )
    return _format_transaction(transaction)


def _resolve_transaction_args(chat_id, transaction_type, args, transaction_at):
    if not args:
        _PENDING_AMOUNT_PROMPTS[chat_id] = transaction_type
        return AMOUNT_PROMPTS[transaction_type]

    if len(args) == 1:
        return build_category_picker(transaction_type, args[0])

    amount_raw, category_name, *description_words = args
    description = ' '.join(description_words)

    try:
        transaction = record_transaction(
            transaction_type=transaction_type,
            amount_raw=amount_raw,
            category_name=category_name,
            description=description,
            transaction_at=transaction_at,
        )
    except TransactionInputError as exc:
        return f'❌ {exc}'

    return _format_transaction(transaction)


def handle_transaction_command(chat_id, text, transaction_type, transaction_at):
    _, _, remainder = text.partition(' ')
    return _resolve_transaction_args(chat_id, transaction_type, remainder.split(), transaction_at)


def handle_plain_message(chat_id, text):
    """Continues a pending /expense or /income amount prompt for this chat,
    if there is one. Returns None (caller should ignore the message) when
    nothing is pending."""
    transaction_type = _PENDING_AMOUNT_PROMPTS.pop(chat_id, None)
    if transaction_type is None:
        return None

    return _resolve_transaction_args(chat_id, transaction_type, text.split(), transaction_at=None)


def handle_edit_command(text):
    _, _, remainder = text.partition(' ')
    args = remainder.split()

    if len(args) < 3:
        return 'Usage: /edit <id> <amount> <category> [description]\nExample: /edit 12 300 travel petrol'

    raw_id, amount_raw, category_name, *description_words = args
    description = ' '.join(description_words)

    try:
        transaction = update_transaction(
            raw_id,
            amount_raw=amount_raw,
            category_name=category_name,
            description=description,
        )
    except TransactionInputError as exc:
        return f'❌ {exc}'

    return f'✏️ Updated: {_format_transaction(transaction)}'


def handle_delete_command(text):
    _, _, remainder = text.partition(' ')
    args = remainder.split()

    if len(args) < 1:
        return 'Usage: /delete <id>\nExample: /delete 12'

    try:
        transaction = resolve_transaction(args[0])
    except TransactionInputError as exc:
        return f'❌ {exc}'

    summary = _format_transaction(transaction)
    delete_transaction(transaction)
    return f'🗑️ Deleted: {summary}'
