from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from constants import (
    BOT_COMMANDS,
    CALLBACK_PREFIX_ACCOUNT,
    CALLBACK_PREFIX_CATEGORY,
    PENDING_ACTION_DELETE_ID,
    PENDING_ACTION_DESCRIPTION,
    PENDING_ACTION_EDIT_DETAILS,
    PENDING_ACTION_EDIT_ID,
    TEST_CHAT_ID,
    TRANSACTION_HISTORY_LIMIT,
)

from apps.finance.models import Account, Category, Person, Transaction
from apps.telegram_bot.commands import (
    _PENDING_PROMPTS,
    build_owed_message,
    build_transaction_history_message,
    handle_account_selected,
    handle_category_selected,
    handle_delete_command,
    handle_description_skipped,
    handle_edit_command,
    handle_plain_message,
    handle_settle_command,
    handle_shared_command,
    handle_transaction_command,
)

IMPLEMENTED_COMMANDS = {
    'start', 'help', 'expense', 'income', 'invest', 'transactions', 'edit', 'delete',
    'shared', 'settle', 'owed',
}
CHAT_ID = TEST_CHAT_ID


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
        _PENDING_PROMPTS.clear()
        self.category = Category.objects.create(name='Food', is_active=True, category_type=Category.CategoryType.EXPENSE)
        self.salary = Category.objects.create(name='Salary', is_active=True, category_type=Category.CategoryType.INCOME)
        self.mutual_fund = Category.objects.create(
            name='MutualFund', is_active=True, category_type=Category.CategoryType.TRANSFER
        )
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
        reply = handle_transaction_command(CHAT_ID, '/income 50000 salary', Transaction.TransactionType.INCOME, self.now)

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.transaction_type, Transaction.TransactionType.INCOME)
        self.assertEqual(transaction.description, '')
        self.assertIn('received as', reply)

    def test_valid_invest_creates_a_transfer_transaction_and_replies_with_confirmation(self):
        reply = handle_transaction_command(
            CHAT_ID, '/invest 5000 mutualfund sip', Transaction.TransactionType.TRANSFER, self.now
        )

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.transaction_type, Transaction.TransactionType.TRANSFER)
        self.assertEqual(transaction.amount, Decimal('5000'))
        self.assertIn('invested in', reply)

    def test_invest_category_picker_only_offers_investment_categories(self):
        result = handle_transaction_command(CHAT_ID, '/invest 5000', Transaction.TransactionType.TRANSFER, self.now)

        prompt, markup = result
        buttons = [button for row in markup.inline_keyboard for button in row]
        self.assertEqual(len(buttons), 1)
        self.assertIn('MutualFund', buttons[0].text)

    def test_expense_category_picker_does_not_offer_investment_categories(self):
        result = handle_transaction_command(CHAT_ID, '/expense 250', Transaction.TransactionType.EXPENSE, self.now)

        prompt, markup = result
        button_texts = [button.text for row in markup.inline_keyboard for button in row]
        self.assertTrue(all('MutualFund' not in text and 'Salary' not in text for text in button_texts))

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
        self.assertEqual(buttons[0].callback_data, f'{CALLBACK_PREFIX_CATEGORY}|EXPENSE|250|{self.category.pk}')

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
        _PENDING_PROMPTS.clear()
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
        self.assertEqual(buttons[0].callback_data, f'{CALLBACK_PREFIX_CATEGORY}|EXPENSE|250|{self.category.pk}')

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
        _PENDING_PROMPTS.clear()
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
        reply = handle_edit_command(CHAT_ID, f'/edit {self.transaction.pk} 300 travel petrol')

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.amount, Decimal('300'))
        self.assertEqual(self.transaction.category, self.travel)
        self.assertEqual(self.transaction.description, 'petrol')
        self.assertIn('Updated', reply)
        self.assertIn(f'#{self.transaction.pk}', reply)
        self.assertIn('petrol', reply)

    def test_missing_arguments_returns_usage_without_changing_anything(self):
        reply = handle_edit_command(CHAT_ID, f'/edit {self.transaction.pk} 300')

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.amount, Decimal('100'))
        self.assertIn('Usage', reply)

    def test_unknown_id_returns_error(self):
        reply = handle_edit_command(CHAT_ID, '/edit 99999 300 travel')

        self.assertTrue(reply.startswith('❌'))

    def test_invalid_amount_returns_error_without_changing_anything(self):
        reply = handle_edit_command(CHAT_ID, f'/edit {self.transaction.pk} abc travel')

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.amount, Decimal('100'))
        self.assertTrue(reply.startswith('❌'))

    def test_bare_edit_asks_which_transaction_instead_of_showing_usage(self):
        reply = handle_edit_command(CHAT_ID, '/edit')

        self.assertNotIn('Usage', reply)
        self.assertIn('id', reply)
        self.assertEqual(_PENDING_PROMPTS[CHAT_ID], PENDING_ACTION_EDIT_ID)

    def test_id_only_reply_shows_current_details_and_asks_for_new_ones(self):
        handle_edit_command(CHAT_ID, '/edit')

        reply = handle_plain_message(CHAT_ID, str(self.transaction.pk))

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.amount, Decimal('100'))  # unchanged so far
        self.assertIn(f'#{self.transaction.pk}', reply)
        self.assertIn('spent on', reply)
        self.assertEqual(_PENDING_PROMPTS[CHAT_ID], (PENDING_ACTION_EDIT_DETAILS, self.transaction.pk))

    def test_id_then_details_across_two_replies_updates_the_transaction(self):
        handle_edit_command(CHAT_ID, '/edit')
        handle_plain_message(CHAT_ID, str(self.transaction.pk))

        reply = handle_plain_message(CHAT_ID, '300 travel petrol')

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.amount, Decimal('300'))
        self.assertEqual(self.transaction.category, self.travel)
        self.assertEqual(self.transaction.description, 'petrol')
        self.assertIn('Updated', reply)

    def test_unknown_id_reply_returns_error_and_clears_the_pending_prompt(self):
        handle_edit_command(CHAT_ID, '/edit')

        reply = handle_plain_message(CHAT_ID, '99999')

        self.assertTrue(reply.startswith('❌'))
        self.assertNotIn(CHAT_ID, _PENDING_PROMPTS)


class HandleDeleteCommandTests(TestCase):
    def setUp(self):
        _PENDING_PROMPTS.clear()
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
        reply = handle_delete_command(CHAT_ID, f'/delete {self.transaction.pk}')

        self.assertFalse(Transaction.objects.filter(pk=self.transaction.pk).exists())
        self.assertIn('Deleted', reply)
        self.assertIn(f'#{self.transaction.pk}', reply)

    def test_bare_delete_asks_which_transaction_instead_of_showing_usage(self):
        reply = handle_delete_command(CHAT_ID, '/delete')

        self.assertTrue(Transaction.objects.filter(pk=self.transaction.pk).exists())
        self.assertNotIn('Usage', reply)
        self.assertIn('id', reply)
        self.assertEqual(_PENDING_PROMPTS[CHAT_ID], PENDING_ACTION_DELETE_ID)

    def test_id_reply_after_bare_delete_deletes_the_transaction(self):
        handle_delete_command(CHAT_ID, '/delete')

        reply = handle_plain_message(CHAT_ID, str(self.transaction.pk))

        self.assertFalse(Transaction.objects.filter(pk=self.transaction.pk).exists())
        self.assertIn('Deleted', reply)

    def test_unknown_id_returns_error_without_deleting_anything(self):
        reply = handle_delete_command(CHAT_ID, '/delete 99999')

        self.assertTrue(Transaction.objects.filter(pk=self.transaction.pk).exists())
        self.assertTrue(reply.startswith('❌'))


class HandleCategorySelectedTests(TestCase):
    def setUp(self):
        _PENDING_PROMPTS.clear()
        self.category = Category.objects.create(name='Travel', is_active=True)

    def test_single_active_account_prompts_for_a_description_instead_of_creating_immediately(self):
        account = Account.objects.create(name='Cash', is_active=True)

        result = handle_category_selected(f'{CALLBACK_PREFIX_CATEGORY}|EXPENSE|200|{self.category.pk}', CHAT_ID)

        self.assertFalse(Transaction.objects.exists())
        self.assertIsInstance(result, tuple)
        prompt, markup = result
        self.assertIn('Travel', prompt)
        self.assertIn('200', prompt)
        buttons = [button for row in markup.inline_keyboard for button in row]
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].text, '⏭ Skip')
        self.assertEqual(
            _PENDING_PROMPTS[CHAT_ID],
            (PENDING_ACTION_DESCRIPTION, 'EXPENSE', '200', self.category.pk, account.pk),
        )

    def test_multiple_active_accounts_returns_an_account_picker(self):
        cash = Account.objects.create(name='Cash', is_active=True)
        upi = Account.objects.create(name='UPI', is_active=True)

        result = handle_category_selected(f'{CALLBACK_PREFIX_CATEGORY}|EXPENSE|200|{self.category.pk}', CHAT_ID)

        self.assertFalse(Transaction.objects.exists())
        self.assertIsInstance(result, tuple)
        prompt, markup = result
        self.assertIn('Travel', prompt)
        buttons = [button for row in markup.inline_keyboard for button in row]
        self.assertEqual({b.text for b in buttons}, {'Cash', 'UPI'})
        self.assertEqual(
            {b.callback_data for b in buttons},
            {f'{CALLBACK_PREFIX_ACCOUNT}|EXPENSE|200|{self.category.pk}|{cash.pk}', f'{CALLBACK_PREFIX_ACCOUNT}|EXPENSE|200|{self.category.pk}|{upi.pk}'},
        )

    def test_no_active_accounts_returns_error(self):
        result = handle_category_selected(f'{CALLBACK_PREFIX_CATEGORY}|EXPENSE|200|{self.category.pk}', CHAT_ID)

        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(result.startswith('❌'))

    def test_unknown_category_returns_error(self):
        Account.objects.create(name='Cash', is_active=True)

        result = handle_category_selected(f'{CALLBACK_PREFIX_CATEGORY}|EXPENSE|200|99999', CHAT_ID)

        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(result.startswith('❌'))

    def test_invalid_amount_in_callback_data_returns_error_instead_of_raising(self):
        Account.objects.create(name='Cash', is_active=True)

        result = handle_category_selected(f'{CALLBACK_PREFIX_CATEGORY}|EXPENSE|not-a-number|{self.category.pk}', CHAT_ID)

        self.assertFalse(Transaction.objects.exists())
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith('❌'))


class HandleAccountSelectedTests(TestCase):
    def setUp(self):
        _PENDING_PROMPTS.clear()
        self.category = Category.objects.create(name='Travel', is_active=True)
        self.account = Account.objects.create(name='UPI', is_active=True)

    def test_valid_selection_prompts_for_a_description_instead_of_creating_immediately(self):
        result = handle_account_selected(
            f'{CALLBACK_PREFIX_ACCOUNT}|EXPENSE|200|{self.category.pk}|{self.account.pk}', CHAT_ID
        )

        self.assertFalse(Transaction.objects.exists())
        prompt, markup = result
        self.assertIn('Travel', prompt)
        self.assertIn('UPI', prompt)
        buttons = [button for row in markup.inline_keyboard for button in row]
        self.assertEqual(buttons[0].text, '⏭ Skip')
        self.assertEqual(
            _PENDING_PROMPTS[CHAT_ID],
            (PENDING_ACTION_DESCRIPTION, 'EXPENSE', '200', self.category.pk, self.account.pk),
        )

    def test_unknown_account_returns_error_without_creating_transaction(self):
        result = handle_account_selected(
            f'{CALLBACK_PREFIX_ACCOUNT}|EXPENSE|200|{self.category.pk}|99999', CHAT_ID
        )

        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(result.startswith('❌'))

    def test_invalid_amount_in_callback_data_returns_error_instead_of_raising(self):
        result = handle_account_selected(
            f'{CALLBACK_PREFIX_ACCOUNT}|EXPENSE|not-a-number|{self.category.pk}|{self.account.pk}', CHAT_ID
        )

        self.assertFalse(Transaction.objects.exists())
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith('❌'))


class DescriptionPromptTests(TestCase):
    """Covers the step after a category/account picker completes: an
    optional description, collected via a plain-text reply or skipped with
    a button tap."""

    def setUp(self):
        _PENDING_PROMPTS.clear()
        self.category = Category.objects.create(name='Travel', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)

    def test_replying_with_text_creates_the_transaction_with_that_description(self):
        handle_category_selected(f'{CALLBACK_PREFIX_CATEGORY}|EXPENSE|200|{self.category.pk}', CHAT_ID)

        reply = handle_plain_message(CHAT_ID, 'petrol for bike')

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.description, 'petrol for bike')
        self.assertIn('spent on', reply)
        self.assertNotIn(CHAT_ID, _PENDING_PROMPTS)

    def test_tapping_skip_creates_the_transaction_with_no_description(self):
        prompt, markup = handle_category_selected(
            f'{CALLBACK_PREFIX_CATEGORY}|EXPENSE|200|{self.category.pk}', CHAT_ID
        )
        skip_callback_data = markup.inline_keyboard[0][0].callback_data

        reply = handle_description_skipped(skip_callback_data, CHAT_ID)

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.description, '')
        self.assertIn('spent on', reply)
        self.assertNotIn(CHAT_ID, _PENDING_PROMPTS)

    def test_skip_button_is_scoped_per_chat_and_clears_only_that_chats_prompt(self):
        other_chat_id = CHAT_ID + 1
        prompt, markup = handle_category_selected(
            f'{CALLBACK_PREFIX_CATEGORY}|EXPENSE|200|{self.category.pk}', CHAT_ID
        )
        handle_account_selected(
            f'{CALLBACK_PREFIX_ACCOUNT}|EXPENSE|150|{self.category.pk}|{self.account.pk}', other_chat_id
        )
        skip_callback_data = markup.inline_keyboard[0][0].callback_data

        handle_description_skipped(skip_callback_data, CHAT_ID)

        self.assertNotIn(CHAT_ID, _PENDING_PROMPTS)
        self.assertIn(other_chat_id, _PENDING_PROMPTS)


class HandleSharedCommandTests(TestCase):
    def setUp(self):
        self.rent = Category.objects.create(name='Rent', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.alice = Person.objects.create(name='Alice', is_active=True)
        self.bob = Person.objects.create(name='Bob', is_active=True)

    def test_valid_split_creates_transaction_with_shares(self):
        reply = handle_shared_command('/shared 25000 rent alice:5000 bob:5000 monthly rent')

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.amount, Decimal('25000'))
        self.assertEqual(transaction.description, 'monthly rent')
        self.assertEqual(transaction.shares.count(), 2)
        self.assertIn('Split with', reply)
        self.assertIn('Alice', reply)
        self.assertIn('Bob', reply)

    def test_missing_shares_returns_usage_without_creating_transaction(self):
        reply = handle_shared_command('/shared 25000 rent')

        self.assertFalse(Transaction.objects.exists())
        self.assertIn('Usage', reply)

    def test_unknown_person_returns_error_without_creating_transaction(self):
        reply = handle_shared_command('/shared 25000 rent nobody:5000')

        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(reply.startswith('❌'))

    def test_shares_exceeding_total_returns_error_without_creating_transaction(self):
        reply = handle_shared_command('/shared 100 rent alice:60 bob:60')

        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(reply.startswith('❌'))


class HandleSettleCommandTests(TestCase):
    def setUp(self):
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.alice = Person.objects.create(name='Alice', is_active=True)

    def test_valid_settlement_creates_transaction_and_replies_with_confirmation(self):
        reply = handle_settle_command('/settle alice 5000 rent repayment')

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.transaction_type, Transaction.TransactionType.SETTLEMENT)
        self.assertEqual(transaction.amount, Decimal('5000'))
        self.assertEqual(transaction.person, self.alice)
        self.assertIn('5000', reply)
        self.assertIn('Alice', reply)

    def test_missing_amount_returns_usage_without_creating_transaction(self):
        reply = handle_settle_command('/settle alice')

        self.assertFalse(Transaction.objects.exists())
        self.assertIn('Usage', reply)

    def test_unknown_person_returns_error_without_creating_transaction(self):
        reply = handle_settle_command('/settle nobody 5000')

        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(reply.startswith('❌'))


class BuildOwedMessageTests(TestCase):
    def setUp(self):
        self.rent = Category.objects.create(name='Rent', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.alice = Person.objects.create(name='Alice', is_active=True)

    def test_no_outstanding_balances_returns_a_friendly_message(self):
        message = build_owed_message()

        self.assertIn('Nobody owes you', message)

    def test_lists_people_with_a_nonzero_balance(self):
        handle_shared_command('/shared 1000 rent alice:400')

        message = build_owed_message()

        self.assertIn('Alice', message)
        self.assertIn('400', message)
