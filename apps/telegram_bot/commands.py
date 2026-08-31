from django.utils import timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from constants import (
    AMOUNT_PROMPTS,
    BOT_COMMANDS,
    BUTTONS_PER_ROW,
    CALLBACK_PREFIX_ACCOUNT,
    CALLBACK_PREFIX_CATEGORY,
    CALLBACK_PREFIX_DESCRIPTION_SKIP,
    DELETE_ID_PROMPT,
    DESCRIPTION_PROMPT,
    EDIT_ID_PROMPT,
    EXAMPLES,
    PENDING_ACTION_DELETE_ID,
    PENDING_ACTION_DESCRIPTION,
    PENDING_ACTION_EDIT_DETAILS,
    PENDING_ACTION_EDIT_ID,
    PHRASING,
    TRANSACTION_HISTORY_LIMIT,
)

from apps.finance.models import Account, Category, Transaction
from apps.finance.services import (
    TransactionInputError,
    active_accounts,
    active_categories,
    create_transaction,
    delete_transaction,
    outstanding_balances,
    parse_amount,
    record_settlement,
    record_shared_expense,
    record_transaction,
    resolve_transaction,
    update_transaction,
)

# Category/account picker state travels in the callback_data itself
# ('cat|TYPE|amount|category_id', 'acc|TYPE|amount|category_id|account_id',
# 'skip|TYPE|amount|category_id|account_id') rather than a server-side
# pending-transaction table — there's nothing to expire or clean up, and a
# button still works correctly no matter how long it sits unanswered. Once
# category+account are both known, the description step (optional — reply
# with text, or tap Skip) is tracked in _PENDING_PROMPTS since it needs a
# plain-text reply, which callback_data alone can't collect.

# ponytail: in-memory only (module-level dict), keyed by chat id — tracks a
# chat that's mid-conversation and is expected to reply next. Value is
# either a TRANSACTION_TYPE_* (awaiting an amount for /expense, /income, or
# /invest), a PENDING_ACTION_* marker (awaiting a transaction id for /edit or
# /delete), (PENDING_ACTION_EDIT_DETAILS, transaction_id) (awaiting the new
# amount/category for an /edit whose id is already known), or
# (PENDING_ACTION_DESCRIPTION, transaction_type, amount_raw, category_id,
# account_id) (awaiting an optional description after a category/account
# picker completes). Lost on process restart and not shared across multiple
# worker processes; move to a DB-backed table if either becomes a real
# problem for this single-process personal bot.
_PENDING_PROMPTS = {}


def _active_category_names(transaction_type):
    return ', '.join(active_categories(transaction_type).values_list('name', flat=True))


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
        'Record an investment (kept separate from spending):',
        f'👉 {EXAMPLES[Transaction.TransactionType.TRANSFER]}',
        '',
        "Not sure of the category? Just tap /expense, /income, or /invest —",
        "I'll ask for the amount, then show buttons to pick from. You'll get",
        "a chance to add a description too, or tap Skip.",
        '',
        'View recent transactions:',
        '👉 /transactions',
        '',
        '✏️ MANAGE',
        '',
        'Edit a transaction (get the id from /transactions):',
        '👉 /edit 12 300 travel petrol',
        "Or just tap /edit — I'll ask for the id, then the new details.",
        '',
        'Delete a transaction:',
        '👉 /delete 12',
        "Or just tap /delete — I'll ask which id.",
        '',
        '🤝 SHARED EXPENSES',
        '',
        'Paid for others? Split it:',
        '👉 /shared 25000 rent alice:5000 bob:5000 monthly rent',
        '',
        'Someone paid you back:',
        '👉 /settle alice 5000',
        '',
        'See who owes you:',
        '👉 /owed',
    ]

    categories = _active_category_names(Transaction.TransactionType.EXPENSE)
    if categories:
        lines += ['', '📂 CATEGORIES', categories]

    investment_categories = _active_category_names(Transaction.TransactionType.TRANSFER)
    if investment_categories:
        lines += ['', '📈 INVESTMENT CATEGORIES', investment_categories]

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
    subject = transaction.category.name if transaction.category else transaction.person.name
    line = f'#{transaction.pk} {emoji} ₹{transaction.amount:.2f} {verb} {subject}'
    if transaction.description:
        line += f' — {transaction.description}'
    if with_date:
        line += f' ({timezone.localtime(transaction.transaction_at):%d %b})'
    return line


def build_transaction_history_message():
    transactions = Transaction.objects.select_related('category', 'person')[:TRANSACTION_HISTORY_LIMIT]
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

    categories = list(active_categories(transaction_type))
    if not categories:
        return '❌ No active categories configured.'

    buttons = [
        InlineKeyboardButton(
            f'{category.icon} {category.name}'.strip(),
            callback_data=f'{CALLBACK_PREFIX_CATEGORY}|{transaction_type}|{amount}|{category.pk}',
        )
        for category in categories
    ]

    emoji, _ = PHRASING[transaction_type]
    prompt = f'{emoji} ₹{amount:.2f} — pick a category:'
    return prompt, InlineKeyboardMarkup(_buttons_in_rows(buttons))


def _prompt_for_description(chat_id, transaction_type, amount_raw, category, account):
    _PENDING_PROMPTS[chat_id] = (PENDING_ACTION_DESCRIPTION, transaction_type, amount_raw, category.pk, account.pk)

    emoji, verb = PHRASING[transaction_type]
    amount = parse_amount(amount_raw)
    prompt = f'{emoji} ₹{amount:.2f} {verb} {category.icon} {category.name} via {account.name}\n{DESCRIPTION_PROMPT}'
    skip_button = InlineKeyboardButton(
        '⏭ Skip',
        callback_data=f'{CALLBACK_PREFIX_DESCRIPTION_SKIP}|{transaction_type}|{amount_raw}|{category.pk}|{account.pk}',
    )
    return prompt, InlineKeyboardMarkup([[skip_button]])


def _create_from_picker(transaction_type, amount_raw, category_id, account_id, description):
    try:
        amount = parse_amount(amount_raw)
    except TransactionInputError as exc:
        return f'❌ {exc}'

    category = Category.objects.filter(pk=category_id, is_active=True).first()
    account = Account.objects.filter(pk=account_id, is_active=True).first()
    if not category or not account:
        return '❌ That option is no longer available.'

    transaction = create_transaction(
        transaction_type=transaction_type,
        amount=amount,
        category=category,
        account=account,
        description=description,
    )
    return _format_transaction(transaction)


def handle_category_selected(callback_data, chat_id):
    _, transaction_type, amount_raw, category_id = callback_data.split('|')

    try:
        parse_amount(amount_raw)
    except TransactionInputError as exc:
        return f'❌ {exc}'

    category = Category.objects.filter(pk=category_id, is_active=True).first()
    if not category:
        return '❌ That category is no longer available.'

    accounts = list(active_accounts())
    if not accounts:
        return '❌ No active account is configured.'

    if len(accounts) == 1:
        return _prompt_for_description(chat_id, transaction_type, amount_raw, category, accounts[0])

    buttons = [
        InlineKeyboardButton(
            account.name,
            callback_data=f'{CALLBACK_PREFIX_ACCOUNT}|{transaction_type}|{amount_raw}|{category_id}|{account.pk}',
        )
        for account in accounts
    ]
    prompt = f'{category.icon} {category.name} — pick an account:'
    return prompt, InlineKeyboardMarkup(_buttons_in_rows(buttons))


def handle_account_selected(callback_data, chat_id):
    _, transaction_type, amount_raw, category_id, account_id = callback_data.split('|')

    try:
        parse_amount(amount_raw)
    except TransactionInputError as exc:
        return f'❌ {exc}'

    category = Category.objects.filter(pk=category_id, is_active=True).first()
    account = Account.objects.filter(pk=account_id, is_active=True).first()
    if not category or not account:
        return '❌ That option is no longer available.'

    return _prompt_for_description(chat_id, transaction_type, amount_raw, category, account)


def handle_description_skipped(callback_data, chat_id):
    _, transaction_type, amount_raw, category_id, account_id = callback_data.split('|')
    _PENDING_PROMPTS.pop(chat_id, None)
    return _create_from_picker(transaction_type, amount_raw, category_id, account_id, description='')


def _resolve_transaction_args(chat_id, transaction_type, args, transaction_at):
    if not args:
        _PENDING_PROMPTS[chat_id] = transaction_type
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
    """Continues whatever this chat is mid-conversation about — a bare
    /expense, /income, /invest, /edit, /delete, or an optional description
    after a category/account picker. Returns None (caller should ignore the
    message) when nothing is pending."""
    pending = _PENDING_PROMPTS.pop(chat_id, None)
    if pending is None:
        return None

    if pending == PENDING_ACTION_EDIT_ID:
        return _resolve_edit_args(chat_id, text.split())

    if isinstance(pending, tuple) and pending[0] == PENDING_ACTION_EDIT_DETAILS:
        return _continue_edit_details(pending[1], text.split())

    if pending == PENDING_ACTION_DELETE_ID:
        return _resolve_delete_args(chat_id, text.split())

    if isinstance(pending, tuple) and pending[0] == PENDING_ACTION_DESCRIPTION:
        _, transaction_type, amount_raw, category_id, account_id = pending
        return _create_from_picker(transaction_type, amount_raw, category_id, account_id, description=text.strip())

    return _resolve_transaction_args(chat_id, pending, text.split(), transaction_at=None)


def _continue_edit_details(transaction_id, args):
    if len(args) < 2:
        return 'Reply with: <amount> <category> [description]\nExample: 300 travel petrol'

    amount_raw, category_name, *description_words = args
    description = ' '.join(description_words)

    try:
        transaction = update_transaction(
            transaction_id,
            amount_raw=amount_raw,
            category_name=category_name,
            description=description,
        )
    except TransactionInputError as exc:
        return f'❌ {exc}'

    return f'✏️ Updated: {_format_transaction(transaction)}'


def _resolve_edit_args(chat_id, args):
    if not args:
        _PENDING_PROMPTS[chat_id] = PENDING_ACTION_EDIT_ID
        return EDIT_ID_PROMPT

    if len(args) == 1:
        try:
            transaction = resolve_transaction(args[0])
        except TransactionInputError as exc:
            return f'❌ {exc}'

        _PENDING_PROMPTS[chat_id] = (PENDING_ACTION_EDIT_DETAILS, transaction.pk)
        return f'✏️ Editing {_format_transaction(transaction)}\nReply with: <amount> <category> [description]'

    if len(args) < 3:
        return 'Usage: /edit <id> <amount> <category> [description]\nExample: /edit 12 300 travel petrol'

    raw_id, amount_raw, category_name, *description_words = args
    return _continue_edit_details(raw_id, [amount_raw, category_name, *description_words])


def handle_edit_command(chat_id, text):
    _, _, remainder = text.partition(' ')
    return _resolve_edit_args(chat_id, remainder.split())


def _resolve_delete_args(chat_id, args):
    if not args:
        _PENDING_PROMPTS[chat_id] = PENDING_ACTION_DELETE_ID
        return DELETE_ID_PROMPT

    try:
        transaction = resolve_transaction(args[0])
    except TransactionInputError as exc:
        return f'❌ {exc}'

    summary = _format_transaction(transaction)
    delete_transaction(transaction)
    return f'🗑️ Deleted: {summary}'


def handle_delete_command(chat_id, text):
    _, _, remainder = text.partition(' ')
    return _resolve_delete_args(chat_id, remainder.split())


def _parse_shares(args):
    """Splits leading 'name:amount' tokens (shares) from the rest (description)."""
    shares_raw = []
    for index, token in enumerate(args):
        name, sep, amount_raw = token.partition(':')
        if not sep or not name or not amount_raw:
            return shares_raw, args[index:]
        shares_raw.append((name, amount_raw))
    return shares_raw, []


def handle_shared_command(text):
    _, _, remainder = text.partition(' ')
    args = remainder.split()
    if len(args) < 3:
        return (
            'Usage: /shared <amount> <category> <person:share> [person:share ...] [description]\n'
            'Example: /shared 25000 rent alice:5000 bob:5000 monthly rent'
        )

    amount_raw, category_name, *rest = args
    shares_raw, description_words = _parse_shares(rest)
    if not shares_raw:
        return '❌ Add at least one person:share, e.g. alice:5000'

    try:
        transaction = record_shared_expense(
            amount_raw=amount_raw,
            category_name=category_name,
            shares_raw=shares_raw,
            description=' '.join(description_words),
        )
    except TransactionInputError as exc:
        return f'❌ {exc}'

    who = ', '.join(f'{share.person.name} ₹{share.amount:.2f}' for share in transaction.shares.select_related('person'))
    return f'{_format_transaction(transaction)}\n🤝 Split with: {who}'


def handle_settle_command(text):
    _, _, remainder = text.partition(' ')
    args = remainder.split()
    if len(args) < 2:
        return 'Usage: /settle <person> <amount> [description]\nExample: /settle alice 5000 rent repayment'

    person_name, amount_raw, *description_words = args
    try:
        transaction = record_settlement(
            person_name=person_name,
            amount_raw=amount_raw,
            description=' '.join(description_words),
        )
    except TransactionInputError as exc:
        return f'❌ {exc}'

    return f'🤝 ₹{transaction.amount:.2f} received from {transaction.person.name}'


def build_owed_message():
    balances = [row for row in outstanding_balances() if row['outstanding'] != 0]
    if not balances:
        return '🤝 Nobody owes you anything right now.'

    lines = ['🤝 Owed to you', '']
    lines += [f"{row['person'].name}: ₹{row['outstanding']:.2f}" for row in balances]
    return '\n'.join(lines)
