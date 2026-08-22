from apps.finance.models import Category, Transaction
from apps.finance.services import TransactionInputError, record_transaction

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
    ]

    categories = _active_category_names()
    if categories:
        lines += ['', '📂 CATEGORIES', categories]

    lines += [
        '',
        '🆕 COMING SOON',
        'Transaction history, monthly summaries, and spending breakdowns.',
        '',
        '➕ OTHER',
        'Start over: /start',
    ]

    return '\n'.join(lines)


def _usage(transaction_type):
    lines = [
        f'Usage: /{transaction_type.lower()} <amount> <category> [description]',
        f'Example: {EXAMPLES[transaction_type]}',
    ]

    categories = _active_category_names()
    if categories:
        lines.append(f'Categories: {categories}')

    return '\n'.join(lines)


def handle_transaction_command(text, transaction_type, transaction_at):
    _, _, remainder = text.partition(' ')
    args = remainder.split()

    if len(args) < 2:
        return _usage(transaction_type)

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

    emoji, verb = PHRASING[transaction_type]
    reply = f'{emoji} ₹{transaction.amount:.2f} {verb} {transaction.category.name}'
    if transaction.description:
        reply += f' — {transaction.description}'

    return reply
