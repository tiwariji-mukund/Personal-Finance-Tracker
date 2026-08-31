from datetime import datetime
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from constants import MAX_TRANSACTION_AMOUNT, TRANSACTION_HISTORY_LIMIT

from apps.finance.models import Account, Category, Person, Transaction, TransactionShare
from apps.finance.services import (
    TransactionInputError,
    dashboard_summary,
    delete_transaction,
    monthly_trend,
    outstanding_balances,
    outstanding_for_person,
    parse_amount,
    record_settlement,
    record_shared_expense,
    record_transaction,
    resolve_transaction,
    shift_month,
    update_transaction,
)


class ParseAmountTests(SimpleTestCase):
    def test_rejects_amount_above_the_maximum(self):
        with self.assertRaises(TransactionInputError):
            parse_amount(str(MAX_TRANSACTION_AMOUNT + 1))

    def test_accepts_the_maximum_amount(self):
        self.assertEqual(parse_amount(str(MAX_TRANSACTION_AMOUNT)), MAX_TRANSACTION_AMOUNT)

    def test_rejects_more_than_two_decimal_places(self):
        with self.assertRaises(TransactionInputError):
            parse_amount('250.999')

    def test_accepts_exactly_two_decimal_places(self):
        self.assertEqual(parse_amount('250.99'), Decimal('250.99'))

    def test_accepts_whole_numbers(self):
        self.assertEqual(parse_amount('250'), Decimal('250'))


class RecordTransactionTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Food', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)

    def test_rejects_a_category_that_belongs_to_a_different_transaction_type(self):
        Category.objects.create(name='MutualFund', is_active=True, category_type=Category.CategoryType.TRANSFER)

        with self.assertRaises(TransactionInputError):
            record_transaction(
                transaction_type=Transaction.TransactionType.EXPENSE,
                amount_raw='100',
                category_name='mutualfund',
            )

    def test_creates_transaction_with_resolved_category_and_account(self):
        transaction = record_transaction(
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount_raw='250.50',
            category_name='food',  # case-insensitive match
            description='swiggy',
        )

        self.assertEqual(transaction.amount, Decimal('250.50'))
        self.assertEqual(transaction.category, self.category)
        self.assertEqual(transaction.account, self.account)
        self.assertEqual(transaction.description, 'swiggy')
        self.assertEqual(transaction.transaction_type, Transaction.TransactionType.EXPENSE)

    def test_accepts_comma_separated_amount(self):
        transaction = record_transaction(
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount_raw='1,200.50',
            category_name='food',
        )

        self.assertEqual(transaction.amount, Decimal('1200.50'))

    def test_rejects_non_numeric_amount(self):
        with self.assertRaises(TransactionInputError):
            record_transaction(
                transaction_type=Transaction.TransactionType.EXPENSE,
                amount_raw='abc',
                category_name='food',
            )

    def test_rejects_non_positive_amount(self):
        with self.assertRaises(TransactionInputError):
            record_transaction(
                transaction_type=Transaction.TransactionType.EXPENSE,
                amount_raw='0',
                category_name='food',
            )

    def test_rejects_unknown_category(self):
        with self.assertRaises(TransactionInputError):
            record_transaction(
                transaction_type=Transaction.TransactionType.EXPENSE,
                amount_raw='100',
                category_name='does-not-exist',
            )

    def test_rejects_inactive_category(self):
        self.category.is_active = False
        self.category.save()

        with self.assertRaises(TransactionInputError):
            record_transaction(
                transaction_type=Transaction.TransactionType.EXPENSE,
                amount_raw='100',
                category_name='food',
            )

    def test_requires_an_active_account_to_exist(self):
        self.account.is_active = False
        self.account.save()

        with self.assertRaises(TransactionInputError):
            record_transaction(
                transaction_type=Transaction.TransactionType.EXPENSE,
                amount_raw='100',
                category_name='food',
            )


class ResolveTransactionTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Food', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.transaction = Transaction.objects.create(
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount=Decimal('100'),
            category=self.category,
            account=self.account,
            transaction_at=timezone.now(),
        )

    def test_resolves_an_existing_transaction_by_id(self):
        found = resolve_transaction(str(self.transaction.pk))
        self.assertEqual(found, self.transaction)

    def test_rejects_a_non_numeric_id(self):
        with self.assertRaises(TransactionInputError):
            resolve_transaction('abc')

    def test_rejects_a_missing_id(self):
        with self.assertRaises(TransactionInputError):
            resolve_transaction(str(self.transaction.pk + 1000))


class UpdateTransactionTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Food', is_active=True)
        self.travel = Category.objects.create(name='Travel', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.transaction = Transaction.objects.create(
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount=Decimal('100'),
            category=self.category,
            account=self.account,
            description='old',
            transaction_at=timezone.now(),
        )

    def test_updates_amount_category_and_description(self):
        updated = update_transaction(
            str(self.transaction.pk),
            amount_raw='300',
            category_name='travel',
            description='petrol',
        )

        self.transaction.refresh_from_db()
        self.assertEqual(updated.pk, self.transaction.pk)
        self.assertEqual(self.transaction.amount, Decimal('300'))
        self.assertEqual(self.transaction.category, self.travel)
        self.assertEqual(self.transaction.description, 'petrol')

    def test_rejects_unknown_id_without_changing_anything(self):
        with self.assertRaises(TransactionInputError):
            update_transaction('99999', amount_raw='300', category_name='travel')

    def test_rejects_invalid_amount_without_changing_anything(self):
        with self.assertRaises(TransactionInputError):
            update_transaction(str(self.transaction.pk), amount_raw='abc', category_name='travel')

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.amount, Decimal('100'))


class DeleteTransactionTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Food', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.transaction = Transaction.objects.create(
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount=Decimal('100'),
            category=self.category,
            account=self.account,
            transaction_at=timezone.now(),
        )

    def test_deletes_the_transaction(self):
        delete_transaction(self.transaction)
        self.assertFalse(Transaction.objects.filter(pk=self.transaction.pk).exists())


class ShiftMonthTests(SimpleTestCase):
    def test_rolls_forward_into_the_next_year(self):
        self.assertEqual(shift_month(2026, 12, 1), (2027, 1))

    def test_rolls_backward_into_the_previous_year(self):
        self.assertEqual(shift_month(2026, 1, -1), (2025, 12))

    def test_plain_shift_within_the_same_year(self):
        self.assertEqual(shift_month(2026, 3, 2), (2026, 5))


class DashboardSummaryTests(TestCase):
    def setUp(self):
        self.food = Category.objects.create(name='Food', is_active=True)
        self.travel = Category.objects.create(name='Travel', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)

    def _create(self, transaction_type, amount, category, when):
        return Transaction.objects.create(
            transaction_type=transaction_type,
            amount=Decimal(amount),
            category=category,
            account=self.account,
            transaction_at=timezone.make_aware(datetime(*when)),
        )

    def test_computes_income_expenses_and_net_for_the_given_month(self):
        self._create(Transaction.TransactionType.INCOME, '50000', self.food, (2026, 3, 5))
        self._create(Transaction.TransactionType.EXPENSE, '300', self.food, (2026, 3, 10))
        self._create(Transaction.TransactionType.EXPENSE, '700', self.travel, (2026, 3, 15))
        self._create(Transaction.TransactionType.EXPENSE, '999', self.food, (2026, 2, 20))  # different month

        summary = dashboard_summary(2026, 3)

        self.assertEqual(summary['income'], Decimal('50000'))
        self.assertEqual(summary['expenses'], Decimal('1000'))
        self.assertEqual(summary['net'], Decimal('49000'))

    def test_category_breakdown_only_includes_expenses_with_percentages(self):
        self._create(Transaction.TransactionType.EXPENSE, '300', self.food, (2026, 3, 10))
        self._create(Transaction.TransactionType.EXPENSE, '700', self.travel, (2026, 3, 15))
        self._create(Transaction.TransactionType.INCOME, '50000', self.food, (2026, 3, 5))

        breakdown = dashboard_summary(2026, 3)['category_breakdown']

        self.assertEqual(len(breakdown), 2)
        travel_row = next(row for row in breakdown if row['name'] == 'Travel')
        food_row = next(row for row in breakdown if row['name'] == 'Food')
        self.assertEqual(travel_row['total'], Decimal('700'))
        self.assertEqual(travel_row['percentage'], Decimal('70'))
        self.assertEqual(food_row['percentage'], Decimal('30'))

    def test_empty_month_returns_a_zeroed_summary(self):
        summary = dashboard_summary(2026, 3)

        self.assertEqual(summary['income'], Decimal('0'))
        self.assertEqual(summary['expenses'], Decimal('0'))
        self.assertEqual(summary['invested'], Decimal('0'))
        self.assertEqual(summary['category_breakdown'], [])
        self.assertEqual(list(summary['transactions']), [])

    def test_transfers_are_tracked_as_invested_and_excluded_from_expenses(self):
        self._create(Transaction.TransactionType.TRANSFER, '5000', self.food, (2026, 3, 5))
        self._create(Transaction.TransactionType.EXPENSE, '300', self.food, (2026, 3, 10))

        summary = dashboard_summary(2026, 3)

        self.assertEqual(summary['invested'], Decimal('5000'))
        self.assertEqual(summary['expenses'], Decimal('300'))
        self.assertEqual(summary['net'], Decimal('-300'))
        self.assertEqual(len(summary['category_breakdown']), 1)
        self.assertEqual(summary['category_breakdown'][0]['total'], Decimal('300'))

    def test_recent_transactions_are_capped_at_the_history_limit(self):
        for day in range(1, TRANSACTION_HISTORY_LIMIT + 4):
            self._create(Transaction.TransactionType.EXPENSE, '10', self.food, (2026, 3, day))

        summary = dashboard_summary(2026, 3)

        self.assertEqual(len(summary['transactions']), TRANSACTION_HISTORY_LIMIT)


class RecordSharedExpenseTests(TestCase):
    def setUp(self):
        self.rent = Category.objects.create(name='Rent', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.alice = Person.objects.create(name='Alice', is_active=True)
        self.bob = Person.objects.create(name='Bob', is_active=True)

    def test_creates_expense_with_shares_for_each_person(self):
        transaction = record_shared_expense(
            amount_raw='25000',
            category_name='rent',
            shares_raw=[('alice', '5000'), ('bob', '5000')],
            description='monthly rent',
        )

        self.assertEqual(transaction.amount, Decimal('25000'))
        self.assertEqual(transaction.transaction_type, Transaction.TransactionType.EXPENSE)
        shares = {share.person.name: share.amount for share in transaction.shares.all()}
        self.assertEqual(shares, {'Alice': Decimal('5000'), 'Bob': Decimal('5000')})

    def test_rejects_shares_exceeding_the_total_amount(self):
        with self.assertRaises(TransactionInputError):
            record_shared_expense(
                amount_raw='100',
                category_name='rent',
                shares_raw=[('alice', '60'), ('bob', '60')],
            )

    def test_rejects_an_unknown_person(self):
        with self.assertRaises(TransactionInputError):
            record_shared_expense(
                amount_raw='100',
                category_name='rent',
                shares_raw=[('nobody', '50')],
            )

    def test_no_shares_are_created_if_a_share_is_invalid(self):
        with self.assertRaises(TransactionInputError):
            record_shared_expense(
                amount_raw='100',
                category_name='rent',
                shares_raw=[('alice', '50'), ('nobody', '50')],
            )

        self.assertFalse(Transaction.objects.exists())


class RecordSettlementTests(TestCase):
    def setUp(self):
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.alice = Person.objects.create(name='Alice', is_active=True)

    def test_creates_a_settlement_transaction_for_the_person(self):
        transaction = record_settlement(person_name='alice', amount_raw='5000', description='rent repayment')

        self.assertEqual(transaction.transaction_type, Transaction.TransactionType.SETTLEMENT)
        self.assertEqual(transaction.amount, Decimal('5000'))
        self.assertEqual(transaction.person, self.alice)
        self.assertIsNone(transaction.category)

    def test_rejects_an_unknown_person(self):
        with self.assertRaises(TransactionInputError):
            record_settlement(person_name='nobody', amount_raw='100')


class OutstandingBalanceTests(TestCase):
    def setUp(self):
        self.rent = Category.objects.create(name='Rent', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.alice = Person.objects.create(name='Alice', is_active=True)
        self.bob = Person.objects.create(name='Bob', is_active=True)

    def test_outstanding_is_shares_owed_minus_settlements_received(self):
        record_shared_expense(amount_raw='1000', category_name='rent', shares_raw=[('alice', '400')])
        record_settlement(person_name='alice', amount_raw='150')

        self.assertEqual(outstanding_for_person(self.alice), Decimal('250'))

    def test_outstanding_is_zero_for_a_person_with_no_shares(self):
        self.assertEqual(outstanding_for_person(self.bob), Decimal('0'))

    def test_outstanding_balances_lists_all_active_people(self):
        record_shared_expense(amount_raw='1000', category_name='rent', shares_raw=[('alice', '400')])

        balances = {row['person']: row['outstanding'] for row in outstanding_balances()}

        self.assertEqual(balances[self.alice], Decimal('400'))
        self.assertEqual(balances[self.bob], Decimal('0'))


class DashboardSummaryReimbursementTests(TestCase):
    def setUp(self):
        self.rent = Category.objects.create(name='Rent', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.alice = Person.objects.create(name='Alice', is_active=True)

    def test_personal_expenses_excludes_shares_owed_by_others(self):
        record_shared_expense(
            amount_raw='25000',
            category_name='rent',
            shares_raw=[('alice', '5000')],
            transaction_at=timezone.make_aware(datetime(2026, 3, 10)),
        )

        summary = dashboard_summary(2026, 3)

        self.assertEqual(summary['expenses'], Decimal('25000'))
        self.assertEqual(summary['reimbursable'], Decimal('5000'))
        self.assertEqual(summary['personal_expenses'], Decimal('20000'))

    def test_settlements_are_tracked_separately_and_excluded_from_income(self):
        record_settlement(
            person_name='alice',
            amount_raw='5000',
            transaction_at=timezone.make_aware(datetime(2026, 3, 10)),
        )

        summary = dashboard_summary(2026, 3)

        self.assertEqual(summary['settled'], Decimal('5000'))
        self.assertEqual(summary['income'], Decimal('0'))


class MonthlyTrendTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Food', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)

    def test_returns_one_row_per_requested_month_oldest_first(self):
        trend = monthly_trend(months=3)

        self.assertEqual(len(trend), 3)
        expected_months = [
            shift_month(trend[-1]['year'], trend[-1]['month'], delta)
            for delta in (-2, -1, 0)
        ]
        actual_months = [(row['year'], row['month']) for row in trend]
        self.assertEqual(actual_months, expected_months)

    def test_aggregates_income_and_expense_for_the_current_month(self):
        now = timezone.localtime(timezone.now())
        Transaction.objects.create(
            transaction_type=Transaction.TransactionType.INCOME,
            amount=Decimal('1000'),
            category=self.category,
            account=self.account,
            transaction_at=timezone.make_aware(datetime(now.year, now.month, 1)),
        )

        trend = monthly_trend(months=1)

        self.assertEqual(trend[0]['income'], Decimal('1000'))
        self.assertEqual(trend[0]['expense'], Decimal('0'))
        self.assertEqual(trend[0]['invested'], Decimal('0'))

    def test_aggregates_invested_amounts_separately_from_income_and_expense(self):
        now = timezone.localtime(timezone.now())
        Transaction.objects.create(
            transaction_type=Transaction.TransactionType.TRANSFER,
            amount=Decimal('2000'),
            category=self.category,
            account=self.account,
            transaction_at=timezone.make_aware(datetime(now.year, now.month, 1)),
        )

        trend = monthly_trend(months=1)

        self.assertEqual(trend[0]['invested'], Decimal('2000'))
        self.assertEqual(trend[0]['income'], Decimal('0'))
        self.assertEqual(trend[0]['expense'], Decimal('0'))
