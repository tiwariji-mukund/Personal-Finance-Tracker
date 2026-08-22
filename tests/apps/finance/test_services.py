from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.finance.models import Account, Category, Transaction
from apps.finance.services import (
    TransactionInputError,
    delete_transaction,
    record_transaction,
    resolve_transaction,
    update_transaction,
)


class RecordTransactionTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Food', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)

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
