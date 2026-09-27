from decimal import Decimal

from django.utils import timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from constants import (
    ADD_BORROWER_PROMPT,
    AMOUNT_PROMPTS,
    BOT_COMMANDS,
    BUTTONS_PER_ROW,
    CALLBACK_ONLY_PENDING_ACTIONS,
    CALLBACK_PREFIX_ACCOUNT,
    CALLBACK_PREFIX_CATEGORY,
    CALLBACK_PREFIX_DESCRIPTION_SKIP,
    CALLBACK_PREFIX_OWED_ALL,
    CALLBACK_PREFIX_OWED_PERSON,
    CALLBACK_PREFIX_REMOVE_BORROWER_CANCEL,
    CALLBACK_PREFIX_REMOVE_BORROWER_CONFIRM,
    CALLBACK_PREFIX_REMOVE_BORROWER_PICK,
    CALLBACK_PREFIX_SETTLE_CANCEL,
    CALLBACK_PREFIX_SETTLE_CONFIRM,
    CALLBACK_PREFIX_SETTLE_PERSON,
    CALLBACK_PREFIX_SHARED_BORROWER,
    CALLBACK_PREFIX_SHARED_CANCEL,
    CALLBACK_PREFIX_SHARED_CATEGORY,
    CALLBACK_PREFIX_SHARED_CONFIRM,
    CALLBACK_PREFIX_SHARED_DESC_SKIP,
    CALLBACK_PREFIX_SHARED_DONE,
    DELETE_ID_PROMPT,
    DESCRIPTION_PROMPT,
    EDIT_ID_PROMPT,
    EXAMPLES,
    NOT_A_BUTTON_REPLY_MESSAGE,
    OWED_NO_BORROWERS_MESSAGE,
    PENDING_ACTION_ADD_BORROWER_NAME,
    PENDING_ACTION_DELETE_ID,
    PENDING_ACTION_DESCRIPTION,
    PENDING_ACTION_EDIT_DETAILS,
    PENDING_ACTION_EDIT_ID,
    PENDING_ACTION_SETTLE_AMOUNT,
    PENDING_ACTION_SHARED_AMOUNT,
    PENDING_ACTION_SHARED_CATEGORY,
    PENDING_ACTION_SHARED_CONFIRM,
    PENDING_ACTION_SHARED_DESCRIPTION,
    PENDING_ACTION_SHARED_SHARE,
    PHRASING,
    SETTLE_CANCELLED_MESSAGE,
    SETTLE_NO_BORROWERS_MESSAGE,
    SHARED_AMOUNT_PROMPT,
    SHARED_BORROWER_PROMPT,
    SHARED_CANCELLED_MESSAGE,
    SHARED_DESCRIPTION_PROMPT,
    SHARED_NO_BORROWERS_MESSAGE,
    TRANSACTION_HISTORY_LIMIT,
)

from apps.finance.models import Account, Category, Person, Transaction, TransactionShare
from apps.finance.services import (
    TransactionInputError,
    active_accounts,
    active_categories,
    active_people,
    add_borrower,
    borrower_share_count,
    create_transaction,
    delete_transaction,
    deactivate_borrower,
    outstanding_balances,
    outstanding_for_person,
    parse_amount,
    record_settlement,
    record_shared_expense,
    record_shared_expense_for_people,
    record_transaction,
    resolve_active_person,
    resolve_transaction,
    update_transaction,
)
from core.logging import get_logger

log = get_logger(__name__)

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
# amount/category for an /edit whose id is already known),
# (PENDING_ACTION_DESCRIPTION, transaction_type, amount_raw, category_id,
# account_id) (awaiting an optional description after a category/account
# picker completes), a /shared draft (see the PENDING_ACTION_SHARED_*
# constants in constants.py), (PENDING_ACTION_SETTLE_AMOUNT, person_id)
# (awaiting a repayment amount after /settle's borrower picker), or
# PENDING_ACTION_ADD_BORROWER_NAME (awaiting a name after a bare
# /addborrower). Lost on process restart and not shared across multiple
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
        'Paid for others? Just tap /shared — no need to type names:',
        '1. Select the people you paid for',
        '2. Enter the total amount',
        '3. Select the category',
        '4. Enter each person\'s share',
        '5. Add an optional description',
        '6. Confirm',
        '',
        'Example: you pay ₹25,000 rent for yourself, Alice, and Bob —',
        "Alice's share ₹5,000, Bob's share ₹5,000. The bot records your",
        'expense as ₹15,000, and that Alice and Bob each owe you ₹5,000.',
        '',
        '👥 BORROWERS',
        '',
        'View people you can select for a shared expense:',
        '👉 /borrowers',
        'Add someone:',
        '👉 /addborrower',
        'Remove someone (hides them from new expenses, keeps history):',
        '👉 /removeborrower',
        '',
        '💰 REPAYMENTS',
        '',
        'See who owes you, and pick someone for details:',
        '👉 /owed',
        'Someone paid you back — tap /settle and pick who:',
        '👉 /settle',
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

    if pending == PENDING_ACTION_ADD_BORROWER_NAME:
        return _resolve_add_borrower_args(chat_id, text.split())

    if isinstance(pending, tuple) and pending[0] == PENDING_ACTION_SHARED_AMOUNT:
        return _continue_shared_amount(chat_id, pending[1], text)

    if isinstance(pending, tuple) and pending[0] == PENDING_ACTION_SHARED_SHARE:
        return _continue_shared_share(chat_id, pending, text)

    if isinstance(pending, tuple) and pending[0] == PENDING_ACTION_SHARED_DESCRIPTION:
        _, amount_raw, category_id, done_pairs = pending
        return _prompt_shared_confirm(chat_id, amount_raw, category_id, done_pairs, text.strip())

    if isinstance(pending, tuple) and pending[0] == PENDING_ACTION_SETTLE_AMOUNT:
        return _continue_settle_amount(chat_id, pending[1], text)

    if isinstance(pending, tuple) and pending[0] in CALLBACK_ONLY_PENDING_ACTIONS:
        _PENDING_PROMPTS[chat_id] = pending  # this step needs a button tap, not text — keep it alive
        return NOT_A_BUTTON_REPLY_MESSAGE

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
    """Splits leading 'name:amount' tokens (shares) from the rest (description).
    Kept for the free-text /shared syntax (backward compatible, undocumented in
    /help); bare /shared now launches the borrower-picker flow below instead."""
    shares_raw = []
    for index, token in enumerate(args):
        name, sep, amount_raw = token.partition(':')
        if not sep or not name or not amount_raw:
            return shares_raw, args[index:]
        shares_raw.append((name, amount_raw))
    return shares_raw, []


# ---------------------------------------------------------------------------
# Borrower registry: /borrowers, /addborrower, /removeborrower.
#
# Person (apps/finance/models.py) already has everything a borrower needs
# (name, is_active, created_at/updated_at) and is already the app's single
# person/reimbursement-participant model, so it doubles as the borrower
# registry rather than introducing a separate model. It's used identically
# by /shared, /owed, and /settle below — all three resolve borrowers through
# apps.finance.services (active_people/resolve_active_person/add_borrower/
# deactivate_borrower), never re-implementing lookup themselves.
#
# ponytail: no per-user ownership on Person — this is a single-owner personal
# tracker (one Telegram bot token, no User/login model anywhere in the repo),
# so a global borrower list is correct as-is. Add a `user` FK here (and to
# Account/Category/Transaction, plus a Telegram chat_id -> User mapping) only
# if the app actually grows multiple owners.
# ---------------------------------------------------------------------------


def build_borrowers_message():
    people = list(active_people())
    if not people:
        return SHARED_NO_BORROWERS_MESSAGE

    lines = ['👥 Your borrowers', '']
    for person in people:
        outstanding = outstanding_for_person(person)
        suffix = f' — ₹{outstanding:,.2f} owed' if outstanding else ''
        lines.append(f'• {person.name}{suffix}')
    return '\n'.join(lines)


def _resolve_add_borrower_args(chat_id, args):
    if not args:
        _PENDING_PROMPTS[chat_id] = PENDING_ACTION_ADD_BORROWER_NAME
        return ADD_BORROWER_PROMPT

    name = ' '.join(args)
    try:
        person, created = add_borrower(name)
    except TransactionInputError as exc:
        return f'❌ {exc}'

    if not created:
        return f'⚠️ {person.name} already exists.'

    log.info('Borrower added', event='borrower_created', person_id=person.pk)
    return f'✅ Added {person.name} as a borrower.'


def handle_add_borrower_command(chat_id, text):
    _, _, remainder = text.partition(' ')
    return _resolve_add_borrower_args(chat_id, remainder.split())


def _borrower_buttons(people, callback_prefix):
    return [InlineKeyboardButton(person.name, callback_data=f'{callback_prefix}|{person.pk}') for person in people]


def handle_remove_borrower_command(text):
    people = list(active_people())
    if not people:
        return "🤝 You don't have any borrowers to remove."

    return '🗑️ Who do you want to remove?', InlineKeyboardMarkup(
        _buttons_in_rows(_borrower_buttons(people, CALLBACK_PREFIX_REMOVE_BORROWER_PICK))
    )


def handle_remove_borrower_picked(callback_data, chat_id):
    _, raw_id = callback_data.split('|')
    try:
        person = resolve_active_person(raw_id)
    except TransactionInputError as exc:
        return f'❌ {exc}'

    count = borrower_share_count(person)
    history_note = f'{person.name} has {count} historical shared expense{"s" if count != 1 else ""}.\n\n' if count else ''
    message = (
        f'⚠️ Remove {person.name}?\n\n'
        f'{history_note}'
        'Removing them will hide them from new shared expenses but preserve existing records.'
    )
    buttons = [[
        InlineKeyboardButton('Remove', callback_data=f'{CALLBACK_PREFIX_REMOVE_BORROWER_CONFIRM}|{person.pk}'),
        InlineKeyboardButton('Cancel', callback_data=CALLBACK_PREFIX_REMOVE_BORROWER_CANCEL),
    ]]
    return message, InlineKeyboardMarkup(buttons)


def handle_remove_borrower_confirmed(callback_data, chat_id):
    _, raw_id = callback_data.split('|')
    try:
        person = resolve_active_person(raw_id)
    except TransactionInputError as exc:
        return f'❌ {exc}'

    deactivate_borrower(person)
    log.info('Borrower removed', event='borrower_removed', person_id=person.pk)
    return f'✅ {person.name} removed. Historical records are preserved.'


def handle_remove_borrower_cancelled(callback_data, chat_id):
    return '❌ Cancelled — no changes made.'


# ---------------------------------------------------------------------------
# /shared — interactive flow: pick borrowers, enter the total, pick a
# category, enter each borrower's share, add an optional description, then
# confirm. Borrower selection (below) bakes its state into callback_data, the
# same way the plain category/account picker above does, since it's pure
# button-tapping with no text reply in between. From the amount prompt
# onward every step needs (or might need) a plain-text reply, so the draft
# moves into _PENDING_PROMPTS instead — seeAmount PENDING_ACTION_SHARED_*
# in constants.py for the exact shape carried at each stage.
# ---------------------------------------------------------------------------


def _parse_ids_csv(csv):
    return tuple(int(part) for part in csv.split(',') if part)


def _shared_borrower_keyboard(people, selected_ids):
    selected_csv = ','.join(str(i) for i in sorted(selected_ids))
    buttons = [
        InlineKeyboardButton(
            f'✓ {person.name}' if person.pk in selected_ids else person.name,
            callback_data=f'{CALLBACK_PREFIX_SHARED_BORROWER}|{selected_csv}|{person.pk}',
        )
        for person in people
    ]
    rows = _buttons_in_rows(buttons)
    rows.append([
        InlineKeyboardButton('✅ Done', callback_data=f'{CALLBACK_PREFIX_SHARED_DONE}|{selected_csv}'),
        InlineKeyboardButton('❌ Cancel', callback_data=CALLBACK_PREFIX_SHARED_CANCEL),
    ])
    return InlineKeyboardMarkup(rows)


def _shared_borrower_picker(selected_ids=frozenset()):
    people = list(active_people())
    if not people:
        return SHARED_NO_BORROWERS_MESSAGE
    return SHARED_BORROWER_PROMPT, _shared_borrower_keyboard(people, selected_ids)


def handle_shared_command(text):
    _, _, remainder = text.partition(' ')
    args = remainder.split()
    if not args:
        return _shared_borrower_picker()

    if len(args) < 3:
        return (
            'Usage: /shared <amount> <category> <person:share> [person:share ...] [description]\n'
            'Example: /shared 25000 rent alice:5000 bob:5000 monthly rent\n'
            'Tip: send /shared with no arguments to pick people from a list instead.'
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


def handle_shared_borrower_toggled(callback_data, chat_id):
    _, selected_csv, toggle_id_raw = callback_data.split('|')
    selected = set(_parse_ids_csv(selected_csv))
    selected.symmetric_difference_update({int(toggle_id_raw)})
    return _shared_borrower_picker(selected)


def handle_shared_borrowers_done(callback_data, chat_id):
    _, selected_csv = callback_data.split('|')
    selected = _parse_ids_csv(selected_csv)
    if not selected:
        return f'❌ Select at least one person.\n{SHARED_BORROWER_PROMPT}', _shared_borrower_keyboard(
            list(active_people()), set()
        )

    valid_ids = tuple(active_people().filter(pk__in=selected).values_list('pk', flat=True))
    if len(valid_ids) != len(selected):
        return f'❌ One of the selected people is no longer available.\n{SHARED_BORROWER_PROMPT}', _shared_borrower_keyboard(
            list(active_people()), set()
        )

    _PENDING_PROMPTS[chat_id] = (PENDING_ACTION_SHARED_AMOUNT, valid_ids)
    log.info('Shared expense started', event='shared_expense_started', borrower_ids=list(valid_ids))
    return SHARED_AMOUNT_PROMPT


def handle_shared_cancelled(callback_data, chat_id):
    _PENDING_PROMPTS.pop(chat_id, None)
    log.info('Shared expense cancelled', event='shared_expense_cancelled')
    return SHARED_CANCELLED_MESSAGE


def _continue_shared_amount(chat_id, borrower_ids, amount_raw):
    try:
        parse_amount(amount_raw)
    except TransactionInputError as exc:
        _PENDING_PROMPTS[chat_id] = (PENDING_ACTION_SHARED_AMOUNT, borrower_ids)
        return f'❌ {exc}\n{SHARED_AMOUNT_PROMPT}'

    categories = list(active_categories(Transaction.TransactionType.EXPENSE))
    if not categories:
        return '❌ No active expense categories configured.'

    _PENDING_PROMPTS[chat_id] = (PENDING_ACTION_SHARED_CATEGORY, borrower_ids, amount_raw)
    buttons = [
        InlineKeyboardButton(
            f'{category.icon} {category.name}'.strip(),
            callback_data=f'{CALLBACK_PREFIX_SHARED_CATEGORY}|{category.pk}',
        )
        for category in categories
    ]
    return '🏷 Select a category:', InlineKeyboardMarkup(_buttons_in_rows(buttons))


def _prompt_for_share(person):
    return f"💸 How much was {person.name}'s share?"


def handle_shared_category_selected(callback_data, chat_id):
    _, category_id = callback_data.split('|')
    pending = _PENDING_PROMPTS.get(chat_id)
    if not (isinstance(pending, tuple) and pending[0] == PENDING_ACTION_SHARED_CATEGORY):
        return '❓ This action is no longer valid. Start again with /shared.'
    _, borrower_ids, amount_raw = pending

    category = Category.objects.filter(
        pk=category_id, is_active=True, category_type=Transaction.TransactionType.EXPENSE
    ).first()
    if not category:
        _PENDING_PROMPTS.pop(chat_id, None)
        return '❌ That category is no longer available. Start again with /shared.'

    people = list(active_people().filter(pk__in=borrower_ids))
    if len(people) != len(borrower_ids):
        _PENDING_PROMPTS.pop(chat_id, None)
        return '❌ One of the selected people is no longer available. Start again with /shared.'

    _PENDING_PROMPTS[chat_id] = (PENDING_ACTION_SHARED_SHARE, amount_raw, category.pk, borrower_ids, ())
    return _prompt_for_share(Person.objects.get(pk=borrower_ids[0]))


def _continue_shared_share(chat_id, pending, share_raw):
    _, amount_raw, category_id, remaining_ids, done_pairs = pending
    current_id = remaining_ids[0]

    try:
        parse_amount(share_raw)
    except TransactionInputError as exc:
        _PENDING_PROMPTS[chat_id] = pending
        return f'❌ {exc}\n{_prompt_for_share(Person.objects.get(pk=current_id))}'

    done_pairs = done_pairs + ((current_id, share_raw),)
    remaining_ids = remaining_ids[1:]

    if remaining_ids:
        _PENDING_PROMPTS[chat_id] = (PENDING_ACTION_SHARED_SHARE, amount_raw, category_id, remaining_ids, done_pairs)
        return _prompt_for_share(Person.objects.get(pk=remaining_ids[0]))

    total_amount = parse_amount(amount_raw)
    total_shares = sum((parse_amount(raw) for _, raw in done_pairs), Decimal('0'))
    if total_shares > total_amount:
        original_ids = tuple(pid for pid, _ in done_pairs)
        _PENDING_PROMPTS[chat_id] = (PENDING_ACTION_SHARED_SHARE, amount_raw, category_id, original_ids, ())
        return (
            f'❌ Borrower shares total ₹{total_shares:,.2f}, which is greater than '
            f'the total amount of ₹{total_amount:,.2f}.\n'
            f'Please enter the shares again.\n{_prompt_for_share(Person.objects.get(pk=original_ids[0]))}'
        )

    _PENDING_PROMPTS[chat_id] = (PENDING_ACTION_SHARED_DESCRIPTION, amount_raw, category_id, done_pairs)
    skip_button = InlineKeyboardButton('⏭ Skip', callback_data=CALLBACK_PREFIX_SHARED_DESC_SKIP)
    return SHARED_DESCRIPTION_PROMPT, InlineKeyboardMarkup([[skip_button]])


def _build_shared_confirm_message(amount_raw, category_id, done_pairs, description):
    amount = parse_amount(amount_raw)
    category = Category.objects.get(pk=category_id)
    total_shares = sum((parse_amount(raw) for _, raw in done_pairs), Decimal('0'))
    people_by_id = {person.pk: person for person in Person.objects.filter(pk__in=[pid for pid, _ in done_pairs])}

    lines = [
        '📋 Please confirm',
        '',
        f'Total paid: ₹{amount:,.2f}',
        f'Category: {category.name}',
        '',
        f'Your share: ₹{amount - total_shares:,.2f}',
        '',
    ]
    lines += [f'{people_by_id[pid].name} owes you: ₹{parse_amount(raw):,.2f}' for pid, raw in done_pairs]
    if description:
        lines += ['', description]
    return '\n'.join(lines)


def _prompt_shared_confirm(chat_id, amount_raw, category_id, done_pairs, description):
    _PENDING_PROMPTS[chat_id] = (PENDING_ACTION_SHARED_CONFIRM, amount_raw, category_id, done_pairs, description)
    message = _build_shared_confirm_message(amount_raw, category_id, done_pairs, description)
    buttons = [[
        InlineKeyboardButton('✅ Confirm', callback_data=CALLBACK_PREFIX_SHARED_CONFIRM),
        InlineKeyboardButton('❌ Cancel', callback_data=CALLBACK_PREFIX_SHARED_CANCEL),
    ]]
    return message, InlineKeyboardMarkup(buttons)


def handle_shared_description_skipped(callback_data, chat_id):
    pending = _PENDING_PROMPTS.get(chat_id)
    if not (isinstance(pending, tuple) and pending[0] == PENDING_ACTION_SHARED_DESCRIPTION):
        return '❓ This action is no longer valid. Start again with /shared.'
    _, amount_raw, category_id, done_pairs = pending
    return _prompt_shared_confirm(chat_id, amount_raw, category_id, done_pairs, description='')


def handle_shared_confirmed(callback_data, chat_id):
    pending = _PENDING_PROMPTS.pop(chat_id, None)
    if not (isinstance(pending, tuple) and pending[0] == PENDING_ACTION_SHARED_CONFIRM):
        return '❓ This action is no longer valid. Start again with /shared.'
    _, amount_raw, category_id, done_pairs, description = pending

    category = Category.objects.filter(
        pk=category_id, is_active=True, category_type=Transaction.TransactionType.EXPENSE
    ).first()
    if not category:
        return '❌ That category is no longer available.'

    people_by_id = {person.pk: person for person in active_people().filter(pk__in=[pid for pid, _ in done_pairs])}
    if len(people_by_id) != len(done_pairs):
        return '❌ One of the selected people is no longer available.'

    try:
        transaction = record_shared_expense_for_people(
            amount_raw=amount_raw,
            category=category,
            people_shares=[(people_by_id[pid], raw) for pid, raw in done_pairs],
            description=description,
        )
    except TransactionInputError as exc:
        return f'❌ {exc}'

    log.info(
        'Shared expense recorded',
        event='shared_expense_completed',
        transaction_id=transaction.pk,
        borrower_count=len(done_pairs),
    )

    shares = list(transaction.shares.select_related('person'))
    owed_total = sum((share.amount for share in shares), Decimal('0'))
    lines = [
        '✅ Shared expense recorded.',
        '',
        f'Your expense: ₹{transaction.amount - owed_total:,.2f}',
        f'Amount owed to you: ₹{owed_total:,.2f}',
        '',
    ]
    lines += [f'{share.person.name}: ₹{share.amount:,.2f}' for share in shares]
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# /settle — pick who paid you back from the same borrower registry, enter
# how much, then confirm.
# ---------------------------------------------------------------------------


def _settle_borrower_picker():
    people = list(active_people())
    if not people:
        return SETTLE_NO_BORROWERS_MESSAGE
    return '💰 Who is paying you back?', InlineKeyboardMarkup(
        _buttons_in_rows(_borrower_buttons(people, CALLBACK_PREFIX_SETTLE_PERSON))
    )


def handle_settle_command(text):
    _, _, remainder = text.partition(' ')
    args = remainder.split()
    if not args:
        return _settle_borrower_picker()

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


def handle_settle_person_selected(callback_data, chat_id):
    _, raw_id = callback_data.split('|')
    try:
        person = resolve_active_person(raw_id)
    except TransactionInputError as exc:
        return f'❌ {exc}'

    _PENDING_PROMPTS[chat_id] = (PENDING_ACTION_SETTLE_AMOUNT, person.pk)
    log.info('Settlement started', event='settlement_started', person_id=person.pk)
    outstanding = outstanding_for_person(person)
    return f'{person.name} currently owes you ₹{outstanding:,.2f}.\nHow much did {person.name} pay back?'


def _continue_settle_amount(chat_id, person_id, amount_raw):
    try:
        person = resolve_active_person(person_id)
        parse_amount(amount_raw)
    except TransactionInputError as exc:
        _PENDING_PROMPTS[chat_id] = (PENDING_ACTION_SETTLE_AMOUNT, person_id)
        return f'❌ {exc}'

    outstanding = outstanding_for_person(person)
    amount = parse_amount(amount_raw)
    buttons = [[
        InlineKeyboardButton('✅ Confirm', callback_data=f'{CALLBACK_PREFIX_SETTLE_CONFIRM}|{person.pk}|{amount_raw}'),
        InlineKeyboardButton('❌ Cancel', callback_data=CALLBACK_PREFIX_SETTLE_CANCEL),
    ]]
    message = (
        f'📋 Settlement\n\n{person.name}\n\n'
        f'Previously owed: ₹{outstanding:,.2f}\n'
        f'Paid back: ₹{amount:,.2f}\n'
        f'Remaining: ₹{outstanding - amount:,.2f}'
    )
    return message, InlineKeyboardMarkup(buttons)


def handle_settle_confirmed(callback_data, chat_id):
    _, raw_id, amount_raw = callback_data.split('|')
    try:
        person = resolve_active_person(raw_id)
        transaction = record_settlement(person_name=person.name, amount_raw=amount_raw)
    except TransactionInputError as exc:
        return f'❌ {exc}'

    log.info(
        'Settlement recorded',
        event='settlement_completed',
        transaction_id=transaction.pk,
        person_id=transaction.person_id,
    )
    return f'✅ ₹{transaction.amount:,.2f} received from {transaction.person.name}.'


def handle_settle_cancelled(callback_data, chat_id):
    _PENDING_PROMPTS.pop(chat_id, None)
    return SETTLE_CANCELLED_MESSAGE


# ---------------------------------------------------------------------------
# /owed — pick a borrower from the same registry to see their balance, or
# view everyone at once (the previous, non-interactive behaviour).
# ---------------------------------------------------------------------------


def handle_owed_command(text):
    people = list(active_people())
    if not people:
        return OWED_NO_BORROWERS_MESSAGE

    rows = _buttons_in_rows(_borrower_buttons(people, CALLBACK_PREFIX_OWED_PERSON))
    rows.append([InlineKeyboardButton('All', callback_data=CALLBACK_PREFIX_OWED_ALL)])
    return '🤝 Who do you want to check?', InlineKeyboardMarkup(rows)


def handle_owed_person_selected(callback_data, chat_id):
    _, raw_id = callback_data.split('|')
    try:
        person = resolve_active_person(raw_id)
    except TransactionInputError as exc:
        return f'❌ {exc}'

    log.info('Owed balance viewed', event='owed_viewed', person_id=person.pk)
    lines = [f'🤝 {person.name} owes you ₹{outstanding_for_person(person):,.2f}.']

    recent = (
        TransactionShare.objects.filter(person=person)
        .select_related('transaction__category')
        .order_by('-transaction__transaction_at')[:3]
    )
    if recent:
        lines += ['', 'Recent shared expenses:']
        lines += [
            f'• {share.transaction.category.name if share.transaction.category else "Uncategorized"} — '
            f'₹{share.amount:,.2f} ({timezone.localtime(share.transaction.transaction_at):%d %b %Y})'
            for share in recent
        ]
    return '\n'.join(lines)


def handle_owed_all_selected(callback_data, chat_id):
    return build_owed_message()


def build_owed_message():
    balances = [row for row in outstanding_balances() if row['outstanding'] != 0]
    if not balances:
        return '🤝 Nobody owes you anything right now.'

    lines = ['🤝 Owed to you', '']
    lines += [f"{row['person'].name}: ₹{row['outstanding']:.2f}" for row in balances]
    return '\n'.join(lines)
