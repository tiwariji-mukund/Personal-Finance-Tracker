from decimal import Decimal, InvalidOperation

from django.utils import timezone

from .models import Account, Category, Transaction


class TransactionInputError(ValueError):
    """Raised when transaction input from an external channel (e.g. Telegram) is invalid."""


def parse_amount(raw):
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        raise TransactionInputError(f"'{raw}' is not a valid amount.")

    if amount <= 0:
        raise TransactionInputError('Amount must be greater than zero.')

    return amount


def resolve_category(name):
    category = Category.objects.filter(name__iexact=name, is_active=True).first()
    if not category:
        raise TransactionInputError(f"Unknown category '{name}'.")

    return category


def resolve_default_account():
    # ponytail: single hardcoded default account (first active, by id) since the
    # input format has no account field. Add an explicit default-account setting
    # once more than one account needs to be picked from regularly.
    account = Account.objects.filter(is_active=True).order_by('id').first()
    if not account:
        raise TransactionInputError('No active account is configured.')

    return account


def record_transaction(*, transaction_type, amount_raw, category_name, description='', transaction_at=None):
    amount = parse_amount(amount_raw)
    category = resolve_category(category_name)
    account = resolve_default_account()

    return Transaction.objects.create(
        transaction_type=transaction_type,
        amount=amount,
        category=category,
        account=account,
        description=description,
        transaction_at=transaction_at or timezone.now(),
    )
