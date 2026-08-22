from apps.finance.models import Category, Transaction
from apps.finance.services import TransactionInputError, record_transaction

EXAMPLES = {
    Transaction.TransactionType.EXPENSE: '/expense 250 food swiggy dinner',
    Transaction.TransactionType.INCOME: '/income 50000 salary august payout',
}

LABELS = {
    Transaction.TransactionType.EXPENSE: 'Expense',
    Transaction.TransactionType.INCOME: 'Income',
}

# Registered with Telegram via the set_bot_commands management command so they
# show up as tap-to-fill suggestions instead of needing to be typed by hand.
BOT_COMMANDS = [
    ('expense', 'Record an expense — amount, category, optional description'),
    ('income', 'Record income — amount, category, optional description'),
]


def _usage(transaction_type):
    lines = [
        f'Usage: /{transaction_type.lower()} <amount> <category> [description]',
        f'Example: {EXAMPLES[transaction_type]}',
    ]

    categories = ', '.join(Category.objects.filter(is_active=True).order_by('name').values_list('name', flat=True))
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

    reply = f'✅ {LABELS[transaction_type]} ₹{transaction.amount:.2f} | {transaction.category.name}'
    if transaction.description:
        reply += f' | {transaction.description}'

    return reply
