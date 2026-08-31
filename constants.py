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

DESCRIPTION_PROMPT = '📝 Add a description, or tap Skip.'

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
    ('shared', 'Split a shared expense'),
    ('settle', 'Record a repayment from someone'),
    ('owed', 'See who owes you money'),
]

# --- Test fixtures (tests/) -----------------------------------------------

TEST_CHAT_ID = 42
TEST_WEBHOOK_URL = '/telegram/webhook/'
