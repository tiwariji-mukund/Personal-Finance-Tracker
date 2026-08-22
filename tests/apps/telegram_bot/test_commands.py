from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.finance.models import Account, Category, Transaction
from apps.telegram_bot.commands import (
    _PENDING_AMOUNT_PROMPTS,
    BOT_COMMANDS,
    TRANSACTION_HISTORY_LIMIT,
    build_transaction_history_message,
    handle_account_selected,
    handle_category_selected,
    handle_delete_command,
    handle_edit_command,
    handle_plain_message,
    handle_transaction_command,
)

IMPLEMENTED_COMMANDS = {'start', 'help', 'expense', 'income', 'transactions', 'edit', 'delete'}
CHAT_ID = 42


class BotCommandMenuTests(SimpleTestCase):
    def test_only_registers_implemented_commands(self):
        registered = {name for name, _ in BOT_COMMANDS}
        self.assertEqual(registered, IMPLEMENTED_COMMANDS)

    def test_no_duplicate_commands(self):
        names = [name for name, _ in BOT_COMMANDS]
        self.assertEqual(len(names), len(set(names)))

    def test_descriptions_are_short_and_syntax_free(self):
        for name, description in BOT_COMMANDS:
            self.assertLessEqual(len(description), 40, f'{name} description is too long for the menu')
            self.assertNotIn('<', description)
            self.assertNotIn('>', description)
            self.assertFalse(any(char.isdigit() for char in description), f'{name} description contains a syntax example')


class HandleTransactionCommandTests(TestCase):
    def setUp(self):
        _PENDING_AMOUNT_PROMPTS.clear()
        self.category = Category.objects.create(name='Food', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.now = timezone.now()

    def test_valid_expense_creates_transaction_and_replies_with_confirmation(self):
        reply = handle_transaction_command(CHAT_ID, '/expense 250 food swiggy', Transaction.TransactionType.EXPENSE, self.now)

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.transaction_type, Transaction.TransactionType.EXPENSE)
        self.assertEqual(transaction.amount, Decimal('250'))
        self.assertEqual(transaction.category, self.category)
        self.assertEqual(transaction.description, 'swiggy')
        self.assertIn('spent on', reply)
        self.assertIn('250', reply)
        self.assertIn('swiggy', reply)

    def test_valid_income_without_description(self):
        reply = handle_transaction_command(CHAT_ID, '/income 50000 food', Transaction.TransactionType.INCOME, self.now)

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.transaction_type, Transaction.TransactionType.INCOME)
        self.assertEqual(transaction.description, '')
        self.assertIn('received as', reply)

    def test_no_arguments_prompts_for_amount_without_creating_transaction(self):
        reply = handle_transaction_command(CHAT_ID, '/expense', Transaction.TransactionType.EXPENSE, self.now)

        self.assertFalse(Transaction.objects.exists())
        self.assertEqual(reply, '💸 How much did you spend?')

    def test_amount_only_returns_a_category_picker_without_creating_transaction(self):
        result = handle_transaction_command(CHAT_ID, '/expense 250', Transaction.TransactionType.EXPENSE, self.now)

        self.assertFalse(Transaction.objects.exists())
        self.assertIsInstance(result, tuple)
        prompt, markup = result
        self.assertIn('250', prompt)
        buttons = [button for row in markup.inline_keyboard for button in row]
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].callback_data, f'cat|EXPENSE|250|{self.category.pk}')

    def test_invalid_amount_returns_error_without_creating_transaction(self):
        reply = handle_transaction_command(CHAT_ID, '/expense abc food', Transaction.TransactionType.EXPENSE, self.now)

        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(reply.startswith('❌'))

    def test_unknown_category_returns_error_without_creating_transaction(self):
        reply = handle_transaction_command(CHAT_ID, '/expense 250 unknown', Transaction.TransactionType.EXPENSE, self.now)

        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(reply.startswith('❌'))


class HandlePlainMessageTests(TestCase):
    def setUp(self):
        _PENDING_AMOUNT_PROMPTS.clear()
        self.category = Category.objects.create(name='Food', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)

    def test_returns_none_when_nothing_is_pending(self):
        self.assertIsNone(handle_plain_message(CHAT_ID, '250'))
        self.assertFalse(Transaction.objects.exists())

    def test_amount_only_reply_continues_into_category_picker(self):
        handle_transaction_command(CHAT_ID, '/expense', Transaction.TransactionType.EXPENSE, None)

        result = handle_plain_message(CHAT_ID, '250')

        self.assertFalse(Transaction.objects.exists())
        self.assertIsInstance(result, tuple)
        prompt, markup = result
        self.assertIn('250', prompt)
        buttons = [button for row in markup.inline_keyboard for button in row]
        self.assertEqual(buttons[0].callback_data, f'cat|EXPENSE|250|{self.category.pk}')

    def test_full_reply_creates_transaction_directly(self):
        handle_transaction_command(CHAT_ID, '/expense', Transaction.TransactionType.EXPENSE, None)

        reply = handle_plain_message(CHAT_ID, '250 food swiggy')

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.category, self.category)
        self.assertEqual(transaction.description, 'swiggy')
        self.assertIn('spent on', reply)

    def test_pending_prompt_is_cleared_after_one_reply(self):
        handle_transaction_command(CHAT_ID, '/expense', Transaction.TransactionType.EXPENSE, None)
        handle_plain_message(CHAT_ID, '250')

        # nothing pending any more, so a second plain message is ignored
        self.assertIsNone(handle_plain_message(CHAT_ID, '300'))

    def test_invalid_amount_reply_returns_error(self):
        handle_transaction_command(CHAT_ID, '/expense', Transaction.TransactionType.EXPENSE, None)

        reply = handle_plain_message(CHAT_ID, 'abc')

        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(reply.startswith('❌'))

    def test_pending_prompts_are_scoped_per_chat(self):
        other_chat_id = CHAT_ID + 1
        handle_transaction_command(CHAT_ID, '/expense', Transaction.TransactionType.EXPENSE, None)

        self.assertIsNone(handle_plain_message(other_chat_id, '250'))


class BuildTransactionHistoryMessageTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Food', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)

    def test_empty_history_returns_a_friendly_message(self):
        message = build_transaction_history_message()

        self.assertFalse(Transaction.objects.exists())
        self.assertIn('No transactions yet', message)

    def test_lists_transactions_most_recent_first(self):
        older = Transaction.objects.create(
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount=Decimal('100'),
            category=self.category,
            account=self.account,
            transaction_at=timezone.now() - timezone.timedelta(days=1),
        )
        newer = Transaction.objects.create(
            transaction_type=Transaction.TransactionType.INCOME,
            amount=Decimal('5000'),
            category=self.category,
            account=self.account,
            description='bonus',
            transaction_at=timezone.now(),
        )

        message = build_transaction_history_message()
        lines = message.splitlines()

        newer_index = next(i for i, line in enumerate(lines) if 'bonus' in line)
        older_index = next(i for i, line in enumerate(lines) if '100.00' in line)
        self.assertLess(newer_index, older_index)
        self.assertIn('received as', lines[newer_index])
        self.assertIn('spent on', lines[older_index])

    def test_respects_the_history_limit(self):
        for i in range(TRANSACTION_HISTORY_LIMIT + 5):
            Transaction.objects.create(
                transaction_type=Transaction.TransactionType.EXPENSE,
                amount=Decimal('10'),
                category=self.category,
                account=self.account,
                transaction_at=timezone.now() - timezone.timedelta(minutes=i),
            )

        message = build_transaction_history_message()
        # Header + blank line + up to TRANSACTION_HISTORY_LIMIT entries.
        self.assertEqual(len(message.splitlines()), 2 + TRANSACTION_HISTORY_LIMIT)


class HandleEditCommandTests(TestCase):
    def setUp(self):
        self.food = Category.objects.create(name='Food', is_active=True)
        self.travel = Category.objects.create(name='Travel', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.transaction = Transaction.objects.create(
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount=Decimal('100'),
            category=self.food,
            account=self.account,
            transaction_at=timezone.now(),
        )

    def test_valid_edit_updates_transaction_and_replies_with_confirmation(self):
        reply = handle_edit_command(f'/edit {self.transaction.pk} 300 travel petrol')

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.amount, Decimal('300'))
        self.assertEqual(self.transaction.category, self.travel)
        self.assertEqual(self.transaction.description, 'petrol')
        self.assertIn('Updated', reply)
        self.assertIn(f'#{self.transaction.pk}', reply)
        self.assertIn('petrol', reply)

    def test_missing_arguments_returns_usage_without_changing_anything(self):
        reply = handle_edit_command(f'/edit {self.transaction.pk} 300')

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.amount, Decimal('100'))
        self.assertIn('Usage', reply)

    def test_unknown_id_returns_error(self):
        reply = handle_edit_command('/edit 99999 300 travel')

        self.assertTrue(reply.startswith('❌'))

    def test_invalid_amount_returns_error_without_changing_anything(self):
        reply = handle_edit_command(f'/edit {self.transaction.pk} abc travel')

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.amount, Decimal('100'))
        self.assertTrue(reply.startswith('❌'))


class HandleDeleteCommandTests(TestCase):
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

    def test_valid_delete_removes_transaction_and_replies_with_confirmation(self):
        reply = handle_delete_command(f'/delete {self.transaction.pk}')

        self.assertFalse(Transaction.objects.filter(pk=self.transaction.pk).exists())
        self.assertIn('Deleted', reply)
        self.assertIn(f'#{self.transaction.pk}', reply)

    def test_missing_id_returns_usage_without_deleting_anything(self):
        reply = handle_delete_command('/delete')

        self.assertTrue(Transaction.objects.filter(pk=self.transaction.pk).exists())
        self.assertIn('Usage', reply)

    def test_unknown_id_returns_error_without_deleting_anything(self):
        reply = handle_delete_command('/delete 99999')

        self.assertTrue(Transaction.objects.filter(pk=self.transaction.pk).exists())
        self.assertTrue(reply.startswith('❌'))


class HandleCategorySelectedTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Travel', is_active=True)

    def test_single_active_account_creates_transaction_immediately(self):
        account = Account.objects.create(name='Cash', is_active=True)

        result = handle_category_selected(f'cat|EXPENSE|200|{self.category.pk}')

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.category, self.category)
        self.assertEqual(transaction.account, account)
        self.assertEqual(transaction.amount, Decimal('200'))
        self.assertIsInstance(result, str)
        self.assertIn('spent on', result)

    def test_multiple_active_accounts_returns_an_account_picker(self):
        cash = Account.objects.create(name='Cash', is_active=True)
        upi = Account.objects.create(name='UPI', is_active=True)

        result = handle_category_selected(f'cat|EXPENSE|200|{self.category.pk}')

        self.assertFalse(Transaction.objects.exists())
        self.assertIsInstance(result, tuple)
        prompt, markup = result
        self.assertIn('Travel', prompt)
        buttons = [button for row in markup.inline_keyboard for button in row]
        self.assertEqual({b.text for b in buttons}, {'Cash', 'UPI'})
        self.assertEqual(
            {b.callback_data for b in buttons},
            {f'acc|EXPENSE|200|{self.category.pk}|{cash.pk}', f'acc|EXPENSE|200|{self.category.pk}|{upi.pk}'},
        )

    def test_no_active_accounts_returns_error(self):
        result = handle_category_selected(f'cat|EXPENSE|200|{self.category.pk}')

        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(result.startswith('❌'))

    def test_unknown_category_returns_error(self):
        Account.objects.create(name='Cash', is_active=True)

        result = handle_category_selected('cat|EXPENSE|200|99999')

        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(result.startswith('❌'))


class HandleAccountSelectedTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Travel', is_active=True)
        self.account = Account.objects.create(name='UPI', is_active=True)

    def test_valid_selection_creates_transaction(self):
        result = handle_account_selected(f'acc|EXPENSE|200|{self.category.pk}|{self.account.pk}')

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.category, self.category)
        self.assertEqual(transaction.account, self.account)
        self.assertEqual(transaction.amount, Decimal('200'))
        self.assertIn('spent on', result)

    def test_unknown_account_returns_error_without_creating_transaction(self):
        result = handle_account_selected(f'acc|EXPENSE|200|{self.category.pk}|99999')

        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(result.startswith('❌'))
