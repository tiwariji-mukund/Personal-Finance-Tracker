from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.finance.models import Account, Category, Transaction
from apps.telegram_bot.commands import handle_transaction_command


class HandleTransactionCommandTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Food', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.now = timezone.now()

    def test_valid_expense_creates_transaction_and_replies_with_confirmation(self):
        reply = handle_transaction_command('/expense 250 food swiggy', Transaction.TransactionType.EXPENSE, self.now)

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.transaction_type, Transaction.TransactionType.EXPENSE)
        self.assertEqual(transaction.amount, Decimal('250'))
        self.assertEqual(transaction.category, self.category)
        self.assertEqual(transaction.description, 'swiggy')
        self.assertIn('Expense', reply)
        self.assertIn('250', reply)
        self.assertIn('swiggy', reply)

    def test_valid_income_without_description(self):
        reply = handle_transaction_command('/income 50000 food', Transaction.TransactionType.INCOME, self.now)

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.transaction_type, Transaction.TransactionType.INCOME)
        self.assertEqual(transaction.description, '')
        self.assertIn('Income', reply)

    def test_missing_arguments_returns_usage_without_creating_transaction(self):
        reply = handle_transaction_command('/expense 250', Transaction.TransactionType.EXPENSE, self.now)

        self.assertFalse(Transaction.objects.exists())
        self.assertIn('Usage', reply)

    def test_invalid_amount_returns_error_without_creating_transaction(self):
        reply = handle_transaction_command('/expense abc food', Transaction.TransactionType.EXPENSE, self.now)

        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(reply.startswith('❌'))

    def test_unknown_category_returns_error_without_creating_transaction(self):
        reply = handle_transaction_command('/expense 250 unknown', Transaction.TransactionType.EXPENSE, self.now)

        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(reply.startswith('❌'))
