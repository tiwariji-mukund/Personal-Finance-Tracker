from decimal import Decimal, InvalidOperation

from django.utils import timezone

from .models import Account, Category, Transaction


class TransactionInputError(ValueError):
    """Raised when transaction input from an external channel (e.g. Telegram) is invalid."""


def parse_amount(raw):
    try:
        amount = Decimal(raw.replace(',', ''))  # tolerate thousands separators, e.g. '1,200.50'
    except InvalidOperation:
        raise TransactionInputError(f"'{raw}' is not a valid amount.")

    if amount <= 0:
        raise TransactionInputError('Amount must be greater than zero.')

    return amount


def resolve_category(name):
    category = Category.objects.filter(name__iexact=name, is_active=True).first()
    if not category:
        message = f"Unknown category '{name}'."
        valid = ', '.join(Category.objects.filter(is_active=True).order_by('name').values_list('name', flat=True))
        if valid:
            message += f' Valid categories: {valid}'
        raise TransactionInputError(message)

    return category


def resolve_default_account():
    # ponytail: single hardcoded default account (first active, by id) since the
    # input format has no account field. Add an explicit default-account setting
    # once more than one account needs to be picked from regularly.
    account = Account.objects.filter(is_active=True).order_by('id').first()
    if not account:
        raise TransactionInputError('No active account is configured.')

    return account


def create_transaction(*, transaction_type, amount, category, account, description='', transaction_at=None):
    return Transaction.objects.create(
        transaction_type=transaction_type,
        amount=amount,
        category=category,
        account=account,
        description=description,
        transaction_at=transaction_at or timezone.now(),
    )


def record_transaction(*, transaction_type, amount_raw, category_name, description='', transaction_at=None):
    return create_transaction(
        transaction_type=transaction_type,
        amount=parse_amount(amount_raw),
        category=resolve_category(category_name),
        account=resolve_default_account(),
        description=description,
        transaction_at=transaction_at,
    )


def active_categories():
    return Category.objects.filter(is_active=True).order_by('name')


def active_accounts():
    return Account.objects.filter(is_active=True).order_by('id')


def resolve_transaction(raw_id):
    try:
        transaction_id = int(raw_id)
    except ValueError:
        raise TransactionInputError(f"'{raw_id}' is not a valid transaction id.")

    try:
        return Transaction.objects.select_related('category').get(pk=transaction_id)
    except Transaction.DoesNotExist:
        raise TransactionInputError(f'No transaction found with id {transaction_id}.')


def update_transaction(raw_id, *, amount_raw, category_name, description=''):
    # ponytail: amount/category/description only — changing expense vs income
    # isn't supported, delete and re-add if the type itself was wrong.
    transaction = resolve_transaction(raw_id)
    transaction.amount = parse_amount(amount_raw)
    transaction.category = resolve_category(category_name)
    transaction.description = description
    transaction.save()
    return transaction


def delete_transaction(transaction):
    transaction.delete()
