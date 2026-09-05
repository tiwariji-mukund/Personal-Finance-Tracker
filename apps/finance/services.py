from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from constants import DASHBOARD_TREND_MONTHS, MAX_TRANSACTION_AMOUNT, TRANSACTION_HISTORY_LIMIT

from .models import Account, Category, Person, Transaction, TransactionShare


class TransactionInputError(ValueError):
    """Raised when transaction input from an external channel (e.g. Telegram) is invalid."""


def parse_amount(raw):
    try:
        amount = Decimal(raw.replace(',', ''))  # tolerate thousands separators, e.g. '1,200.50'
    except InvalidOperation:
        raise TransactionInputError(f"'{raw}' is not a valid amount.")

    if amount <= 0:
        raise TransactionInputError('Amount must be greater than zero.')

    if amount.as_tuple().exponent < -2:
        raise TransactionInputError(f"'{raw}' has too many decimal places (max 2).")

    if amount > MAX_TRANSACTION_AMOUNT:
        raise TransactionInputError(f'Amount must be at most ₹{MAX_TRANSACTION_AMOUNT:,.2f}.')

    return amount


def resolve_category(name, transaction_type):
    category = Category.objects.filter(name__iexact=name, is_active=True, category_type=transaction_type).first()
    if not category:
        message = f"Unknown category '{name}'."
        valid = ', '.join(active_categories(transaction_type).values_list('name', flat=True))
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


def create_transaction(*, transaction_type, amount, account, category=None, person=None, description='', transaction_at=None):
    return Transaction.objects.create(
        transaction_type=transaction_type,
        amount=amount,
        category=category,
        account=account,
        person=person,
        description=description,
        transaction_at=transaction_at or timezone.now(),
    )


def record_transaction(*, transaction_type, amount_raw, category_name, description='', transaction_at=None):
    return create_transaction(
        transaction_type=transaction_type,
        amount=parse_amount(amount_raw),
        category=resolve_category(category_name, transaction_type),
        account=resolve_default_account(),
        description=description,
        transaction_at=transaction_at,
    )


def active_categories(transaction_type):
    return Category.objects.filter(is_active=True, category_type=transaction_type).order_by('name')


def active_accounts():
    return Account.objects.filter(is_active=True).order_by('id')


def active_people():
    return Person.objects.filter(is_active=True).order_by('name')


def resolve_person(name):
    person = Person.objects.filter(name__iexact=name, is_active=True).first()
    if not person:
        message = f"Unknown person '{name}'."
        valid = ', '.join(active_people().values_list('name', flat=True))
        if valid:
            message += f' Valid people: {valid}'
        raise TransactionInputError(message)

    return person


def record_shared_expense(*, amount_raw, category_name, shares_raw, description='', transaction_at=None):
    """Records an EXPENSE the user paid in full, with one or more people each
    owing back a share of it (e.g. splitting a rent payment)."""
    amount = parse_amount(amount_raw)
    shares = [(resolve_person(name), parse_amount(share_amount_raw)) for name, share_amount_raw in shares_raw]

    total_shares = sum((share_amount for _, share_amount in shares), Decimal('0'))
    if total_shares > amount:
        raise TransactionInputError(
            f'Shares (₹{total_shares:,.2f}) cannot exceed the total amount (₹{amount:,.2f}).'
        )

    transaction = create_transaction(
        transaction_type=Transaction.TransactionType.EXPENSE,
        amount=amount,
        category=resolve_category(category_name, Transaction.TransactionType.EXPENSE),
        account=resolve_default_account(),
        description=description,
        transaction_at=transaction_at,
    )
    TransactionShare.objects.bulk_create(
        TransactionShare(transaction=transaction, person=person, amount=share_amount)
        for person, share_amount in shares
    )
    return transaction


def record_settlement(*, person_name, amount_raw, description='', transaction_at=None):
    """Records money a person paid back to the user."""
    return create_transaction(
        transaction_type=Transaction.TransactionType.SETTLEMENT,
        amount=parse_amount(amount_raw),
        account=resolve_default_account(),
        person=resolve_person(person_name),
        description=description,
        transaction_at=transaction_at,
    )


def outstanding_for_person(person):
    owed = TransactionShare.objects.filter(person=person).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    settled = Transaction.objects.filter(
        transaction_type=Transaction.TransactionType.SETTLEMENT, person=person
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    return owed - settled


def outstanding_balances():
    return [
        {'person': person, 'outstanding': outstanding_for_person(person)}
        for person in active_people()
    ]


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
    amount = parse_amount(amount_raw)

    total_shares = transaction.shares.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    if total_shares > amount:
        raise TransactionInputError(
            f'Amount (₹{amount:,.2f}) cannot be less than the shares already split (₹{total_shares:,.2f}).'
        )

    transaction.amount = amount
    transaction.category = resolve_category(category_name, transaction.transaction_type)
    transaction.description = description
    transaction.save()
    return transaction


def delete_transaction(transaction):
    transaction.delete()


def shift_month(year, month, delta):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def _month_bounds(year, month):
    start = timezone.make_aware(datetime(year, month, 1))
    end = timezone.make_aware(datetime(*shift_month(year, month, 1), 1))
    return start, end


def dashboard_summary(year, month):
    start, end = _month_bounds(year, month)
    transactions = Transaction.objects.filter(transaction_at__gte=start, transaction_at__lt=end)

    totals_by_type = {
        row['transaction_type']: row['total']
        for row in transactions.values('transaction_type').annotate(total=Sum('amount'))
    }
    income = totals_by_type.get(Transaction.TransactionType.INCOME, Decimal('0'))
    expenses = totals_by_type.get(Transaction.TransactionType.EXPENSE, Decimal('0'))
    invested = totals_by_type.get(Transaction.TransactionType.TRANSFER, Decimal('0'))
    settled = totals_by_type.get(Transaction.TransactionType.SETTLEMENT, Decimal('0'))

    # 'expenses' above is gross cash paid out (correct for cash-flow), but part
    # of it may belong to other people (a shared expense) rather than being
    # the user's own spend — see TransactionShare.
    reimbursable = TransactionShare.objects.filter(
        transaction__in=transactions.filter(transaction_type=Transaction.TransactionType.EXPENSE)
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    personal_expenses = expenses - reimbursable

    category_rows = (
        transactions.filter(transaction_type=Transaction.TransactionType.EXPENSE)
        .values('category__name', 'category__icon', 'category__color')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    category_breakdown = [
        {
            'name': row['category__name'] or 'Uncategorized',
            'icon': row['category__icon'] or '',
            'color': row['category__color'] or '#6B7280',
            'total': row['total'],
            'percentage': (row['total'] / expenses * 100) if expenses else Decimal('0'),
        }
        for row in category_rows
    ]

    return {
        'income': income,
        'expenses': expenses,
        'reimbursable': reimbursable,
        'personal_expenses': personal_expenses,
        'net': income - expenses,
        'invested': invested,
        'settled': settled,
        'category_breakdown': category_breakdown,
        'transactions': transactions.select_related('category', 'account').order_by('-transaction_at')[
            :TRANSACTION_HISTORY_LIMIT
        ],
    }


def monthly_trend(months=DASHBOARD_TREND_MONTHS):
    today = timezone.localtime(timezone.now()).date()
    start_year, start_month = shift_month(today.year, today.month, -(months - 1))
    start, _ = _month_bounds(start_year, start_month)

    rows = (
        Transaction.objects.filter(transaction_at__gte=start)
        .annotate(month=TruncMonth('transaction_at'))
        .values('month', 'transaction_type')
        .annotate(total=Sum('amount'))
    )
    totals_by_month = {}
    for row in rows:
        key = (row['month'].year, row['month'].month)
        totals_by_month.setdefault(key, {})[row['transaction_type']] = row['total']

    trend = []
    year, month = start_year, start_month
    for _ in range(months):
        totals = totals_by_month.get((year, month), {})
        trend.append({
            'year': year,
            'month': month,
            'label': date(year, month, 1).strftime('%b %Y'),
            'income': totals.get(Transaction.TransactionType.INCOME, Decimal('0')),
            'expense': totals.get(Transaction.TransactionType.EXPENSE, Decimal('0')),
            'invested': totals.get(Transaction.TransactionType.TRANSFER, Decimal('0')),
        })
        year, month = shift_month(year, month, 1)
    return trend
