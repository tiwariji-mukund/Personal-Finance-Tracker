"""
Project-wide constants.

This module has no Django/app dependencies on purpose, so it can be
imported safely from anywhere — including config/settings.py, which loads
before Django's app registry is ready. The 'EXPENSE'/'INCOME' string
literals below mirror apps.finance.models.Transaction.TransactionType's
values rather than importing that enum, for exactly that reason (the same
way a migration file freezes its own copy of a model's choices).
"""

from decimal import Decimal

# --- Timezone ----------------------------------------------------------

IST_TIMEZONE_NAME = 'Asia/Kolkata'

# --- Structured logging (core/logging/) ---------------------------------

REQUEST_ID_HEADER = 'X-Request-ID'

RESERVED_FIELDS = {
    'timestamp',
    'level',
    'file',
    'request_id',
    'message',
}

# --- Finance domain (apps/finance/) --------------------------------------

# Must match Transaction.amount's DecimalField(max_digits=10, decimal_places=2).
MAX_TRANSACTION_AMOUNT = Decimal('99999999.99')

# category_type mirrors Transaction.TransactionType's values ('EXPENSE' /
# 'INCOME' / 'TRANSFER') so /expense, /income, and /invest each only ever
# offer categories that make sense for that command.
DEFAULT_CATEGORIES = [
    {'name': 'Food', 'icon': '🍔', 'color': '#EF4444', 'category_type': 'EXPENSE'},
    {'name': 'Shopping', 'icon': '🛍️', 'color': '#8B5CF6', 'category_type': 'EXPENSE'},
    {'name': 'Travel', 'icon': '🚕', 'color': '#3B82F6', 'category_type': 'EXPENSE'},
    {'name': 'Rent', 'icon': '🏠', 'color': '#F97316', 'category_type': 'EXPENSE'},
    {'name': 'Electricity', 'icon': '⚡', 'color': '#EAB308', 'category_type': 'EXPENSE'},
    {'name': 'Internet', 'icon': '🌐', 'color': '#06B6D4', 'category_type': 'EXPENSE'},
    {'name': 'Healthcare', 'icon': '🏥', 'color': '#10B981', 'category_type': 'EXPENSE'},
    {'name': 'Entertainment', 'icon': '🎬', 'color': '#EC4899', 'category_type': 'EXPENSE'},
    {'name': 'Miscellaneous', 'icon': '📦', 'color': '#6B7280', 'category_type': 'EXPENSE'},
    {'name': 'Salary', 'icon': '💰', 'color': '#16A34A', 'category_type': 'INCOME'},
    {'name': 'MutualFund', 'icon': '📊', 'color': '#6366F1', 'category_type': 'TRANSFER'},
    {'name': 'Stocks', 'icon': '📈', 'color': '#22C55E', 'category_type': 'TRANSFER'},
    {'name': 'FD', 'icon': '🏦', 'color': '#F59E0B', 'category_type': 'TRANSFER'},
    {'name': 'Gold', 'icon': '🥇', 'color': '#FACC15', 'category_type': 'TRANSFER'},
    {'name': 'PPF', 'icon': '🛡️', 'color': '#0EA5E9', 'category_type': 'TRANSFER'},
    {'name': 'OtherInvestment', 'icon': '📦', 'color': '#94A3B8', 'category_type': 'TRANSFER'},
]

DEFAULT_ACCOUNTS = [
    {'name': 'Salary Account', 'account_type': 'SAVINGS'},
    {'name': 'Expense Account', 'account_type': 'SAVINGS'},
    {'name': 'Cash', 'account_type': 'CASH'},
    {'name': 'Credit Card', 'account_type': 'CREDIT_CARD'},
    {'name': 'UPI', 'account_type': 'UPI'},
]

# --- Dashboard (apps/finance/views.py) ------------------------------------

DASHBOARD_TREND_MONTHS = 6

# --- Telegram bot (apps/telegram_bot/) -----------------------------------

TRANSACTION_TYPE_EXPENSE = 'EXPENSE'
TRANSACTION_TYPE_INCOME = 'INCOME'
# Money moved into an asset (e.g. investments) rather than spent — excluded
# from the dashboard's expense totals/category breakdown, tracked separately.
TRANSACTION_TYPE_TRANSFER = 'TRANSFER'
# A person paying back their share of a shared expense — cash inflow, but not
# INCOME, so it's excluded from the dashboard's income/expense totals.
TRANSACTION_TYPE_SETTLEMENT = 'SETTLEMENT'

# Inline-keyboard callback_data prefixes: 'cat|TYPE|amount|category_id',
# 'acc|TYPE|amount|category_id|account_id',
# 'skip|TYPE|amount|category_id|account_id'.
CALLBACK_PREFIX_CATEGORY = 'cat'
CALLBACK_PREFIX_ACCOUNT = 'acc'
CALLBACK_PREFIX_DESCRIPTION_SKIP = 'skip'

# /shared borrower-picker callback_data prefixes. Borrower selection
# (shb/shdone) bakes the whole selected-id list into callback_data — like
# the category/account picker above, it stays valid no matter how long the
# buttons sit unanswered. ponytail: assumes few enough borrowers that the
# csv list fits Telegram's 64-byte callback_data limit (fine for a personal
# tracker); move selection state server-side (like the steps below it) if
# that ever becomes a real constraint.
# 'shb|<selected_csv>|<toggle_id>', 'shdone|<selected_csv>', 'shcancel'.
# Category onward needs a plain-text reply in between (amount, each share),
# so from there the draft lives in _PENDING_PROMPTS instead: 'shcat|<category_id>'
# picks a category, 'shskip' skips the optional description, 'shconfirm' saves.
CALLBACK_PREFIX_SHARED_BORROWER = 'shb'
CALLBACK_PREFIX_SHARED_DONE = 'shdone'
CALLBACK_PREFIX_SHARED_CANCEL = 'shcancel'
CALLBACK_PREFIX_SHARED_CATEGORY = 'shcat'
CALLBACK_PREFIX_SHARED_DESC_SKIP = 'shskip'
CALLBACK_PREFIX_SHARED_CONFIRM = 'shconfirm'

# /owed borrower-picker: 'owedp|<person_id>' shows one borrower's balance,
# 'owedall' shows everyone (the old /owed behaviour).
CALLBACK_PREFIX_OWED_PERSON = 'owedp'
CALLBACK_PREFIX_OWED_ALL = 'owedall'

# /settle borrower-picker: 'stlp|<person_id>' picks who paid, then (after a
# plain-text amount reply) 'stlconfirm|<person_id>|<amount>' / 'stlcancel'.
CALLBACK_PREFIX_SETTLE_PERSON = 'stlp'
CALLBACK_PREFIX_SETTLE_CONFIRM = 'stlconfirm'
CALLBACK_PREFIX_SETTLE_CANCEL = 'stlcancel'

# /removeborrower: pick a borrower, confirm (shows their shared-expense
# history count first), or cancel.
CALLBACK_PREFIX_REMOVE_BORROWER_PICK = 'rmbrwpick'
CALLBACK_PREFIX_REMOVE_BORROWER_CONFIRM = 'rmbrwok'
CALLBACK_PREFIX_REMOVE_BORROWER_CANCEL = 'rmbrwno'

DESCRIPTION_PROMPT = '📝 Add a description, or tap Skip.'
SHARED_BORROWER_PROMPT = '👥 Who did you pay for? Tap to select, then Done.'
SHARED_NO_BORROWERS_MESSAGE = (
    "🤝 You haven't added any borrowers yet.\n"
    'Add one with /addborrower, then try /shared again.'
)
SHARED_AMOUNT_PROMPT = '💰 How much did you pay in total?'
SHARED_DESCRIPTION_PROMPT = '📝 Add a description, or tap Skip.'
SHARED_CANCELLED_MESSAGE = '❌ Shared expense cancelled.'
SETTLE_NO_BORROWERS_MESSAGE = (
    "🤝 You haven't added any borrowers yet.\n"
    'Add one with /addborrower, then try /settle again.'
)
SETTLE_CANCELLED_MESSAGE = '❌ Settlement cancelled.'
OWED_NO_BORROWERS_MESSAGE = "🤝 You haven't added any borrowers yet.\nAdd one with /addborrower."
ADD_BORROWER_PROMPT = "👤 What's the borrower's name?"
NOT_A_BUTTON_REPLY_MESSAGE = '👆 Please use the buttons above.'

# ponytail: fixed cap, no pagination — add a /transactions <n> argument or
# paging if a flat recent-N list stops being enough.
TRANSACTION_HISTORY_LIMIT = 10

BUTTONS_PER_ROW = 2

TRANSACTION_COMMANDS = {
    '/expense': TRANSACTION_TYPE_EXPENSE,
    '/income': TRANSACTION_TYPE_INCOME,
    '/invest': TRANSACTION_TYPE_TRANSFER,
}

EXAMPLES = {
    TRANSACTION_TYPE_EXPENSE: '/expense 250 food swiggy dinner',
    TRANSACTION_TYPE_INCOME: '/income 50000 salary august payout',
    TRANSACTION_TYPE_TRANSFER: '/invest 5000 investment sip mutual fund',
}

# (emoji, verb) used to phrase the confirmation as a natural sentence, e.g.
# "💸 ₹200.00 spent on Travel — petrol".
PHRASING = {
    TRANSACTION_TYPE_EXPENSE: ('💸', 'spent on'),
    TRANSACTION_TYPE_INCOME: ('💵', 'received as'),
    TRANSACTION_TYPE_TRANSFER: ('📈', 'invested in'),
    TRANSACTION_TYPE_SETTLEMENT: ('🤝', 'received from'),
}

AMOUNT_PROMPTS = {
    TRANSACTION_TYPE_EXPENSE: '💸 How much did you spend?',
    TRANSACTION_TYPE_INCOME: '💵 How much did you receive?',
    TRANSACTION_TYPE_TRANSFER: '📈 How much are you investing?',
}

# Pending-conversation markers stored in commands._PENDING_PROMPTS. Distinct
# from TRANSACTION_TYPE_* ('EXPENSE'/'INCOME'/'TRANSFER'), which are also
# stored there when a bare /expense, /income, or /invest is awaiting its
# amount reply.
PENDING_ACTION_EDIT_ID = 'EDIT_ID'
PENDING_ACTION_EDIT_DETAILS = 'EDIT_DETAILS'
PENDING_ACTION_DELETE_ID = 'DELETE_ID'
# Stored as (PENDING_ACTION_DESCRIPTION, transaction_type, amount_raw,
# category_id, account_id) once category+account are both picked via
# buttons, awaiting an optional description reply (or a Skip tap).
PENDING_ACTION_DESCRIPTION = 'DESCRIPTION'

# /shared interactive-flow markers, once borrower selection (handled entirely
# via callback_data, see CALLBACK_PREFIX_SHARED_BORROWER above) hands off to
# a step that needs a plain-text reply:
# (PENDING_ACTION_SHARED_AMOUNT, borrower_ids) — awaiting the total amount.
# (PENDING_ACTION_SHARED_CATEGORY, borrower_ids, amount_raw) — awaiting a
#   category button tap (no text expected).
# (PENDING_ACTION_SHARED_SHARE, amount_raw, category_id, remaining_ids,
#   done_pairs) — awaiting the next borrower's share; done_pairs is a tuple
#   of (person_id, share_raw) already collected.
# (PENDING_ACTION_SHARED_DESCRIPTION, amount_raw, category_id, done_pairs) —
#   awaiting an optional description reply (or a Skip tap).
# (PENDING_ACTION_SHARED_CONFIRM, amount_raw, category_id, done_pairs,
#   description) — awaiting a Confirm/Cancel tap (no text expected).
PENDING_ACTION_SHARED_AMOUNT = 'SHARED_AMOUNT'
PENDING_ACTION_SHARED_CATEGORY = 'SHARED_CATEGORY'
PENDING_ACTION_SHARED_SHARE = 'SHARED_SHARE'
PENDING_ACTION_SHARED_DESCRIPTION = 'SHARED_DESCRIPTION'
PENDING_ACTION_SHARED_CONFIRM = 'SHARED_CONFIRM'

# (PENDING_ACTION_SETTLE_AMOUNT, person_id) — awaiting the repayment amount
# after a borrower is picked for /settle.
PENDING_ACTION_SETTLE_AMOUNT = 'SETTLE_AMOUNT'

# Awaiting a name reply after a bare /addborrower.
PENDING_ACTION_ADD_BORROWER_NAME = 'ADD_BORROWER_NAME'

# Pending markers above that are satisfied by a button tap, not free text —
# a stray text reply during one of these should be reminded to use the
# buttons instead of being misread as the next step's input.
CALLBACK_ONLY_PENDING_ACTIONS = {PENDING_ACTION_SHARED_CATEGORY, PENDING_ACTION_SHARED_CONFIRM}

EDIT_ID_PROMPT = '✏️ Which transaction do you want to edit? Reply with its id (see /transactions).'
DELETE_ID_PROMPT = '🗑️ Which transaction do you want to delete? Reply with its id (see /transactions).'

# Registered with Telegram via the set_bot_commands management command so they
# show up as tap-to-fill suggestions instead of needing to be typed by hand.
# Keep descriptions short and syntax-free — detailed usage belongs in /help.
BOT_COMMANDS = [
    ('start', 'Start the finance tracker'),
    ('help', 'Show available commands'),
    ('expense', 'Add an expense'),
    ('income', 'Add income'),
    ('invest', 'Record an investment'),
    ('transactions', 'View recent transactions'),
    ('edit', 'Edit a transaction'),
    ('delete', 'Delete a transaction'),
    ('shared', 'Record a shared expense'),
    ('settle', 'Record a repayment'),
    ('owed', 'View money owed to you'),
    ('borrowers', 'View your borrowers'),
    ('addborrower', 'Add a borrower'),
    ('removeborrower', 'Remove a borrower'),
]

# --- Test fixtures (tests/) -----------------------------------------------

TEST_CHAT_ID = 42
TEST_WEBHOOK_URL = '/telegram/webhook/'
