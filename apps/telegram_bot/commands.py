from apps.finance.models import Transaction
from apps.finance.services import TransactionInputError, record_transaction

USAGE = {
    Transaction.TransactionType.EXPENSE: 'Usage: /expense <amount> <category> [description]',
    Transaction.TransactionType.INCOME: 'Usage: /income <amount> <category> [description]',
}

LABELS = {
    Transaction.TransactionType.EXPENSE: 'Expense',
    Transaction.TransactionType.INCOME: 'Income',
}


def handle_transaction_command(text, transaction_type, transaction_at):
    _, _, remainder = text.partition(' ')
    args = remainder.split()

    if len(args) < 2:
        return USAGE[transaction_type]

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
