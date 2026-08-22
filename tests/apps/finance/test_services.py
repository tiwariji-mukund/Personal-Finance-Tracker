from decimal import Decimal

from django.test import TestCase

from apps.finance.models import Account, Category, Transaction
from apps.finance.services import TransactionInputError, record_transaction


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
