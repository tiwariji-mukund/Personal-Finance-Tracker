from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from constants import (
    BOT_COMMANDS,
    CALLBACK_PREFIX_ACCOUNT,
    CALLBACK_PREFIX_CATEGORY,
    CALLBACK_PREFIX_OWED_ALL,
    CALLBACK_PREFIX_SHARED_CANCEL,
    CALLBACK_PREFIX_SHARED_CONFIRM,
    CALLBACK_PREFIX_SHARED_DESC_SKIP,
    PENDING_ACTION_DELETE_ID,
    PENDING_ACTION_DESCRIPTION,
    PENDING_ACTION_EDIT_DETAILS,
    PENDING_ACTION_EDIT_ID,
    TEST_CHAT_ID,
    TRANSACTION_HISTORY_LIMIT,
)

from apps.finance.models import Account, Category, Person, Transaction
from apps.finance.services import outstanding_for_person
from apps.telegram_bot.commands import (
    _PENDING_PROMPTS,
    build_borrowers_message,
    build_owed_message,
    build_transaction_history_message,
    handle_account_selected,
    handle_add_borrower_command,
    handle_category_selected,
    handle_delete_command,
    handle_description_skipped,
    handle_edit_command,
    handle_owed_all_selected,
    handle_owed_command,
    handle_owed_person_selected,
    handle_plain_message,
    handle_remove_borrower_cancelled,
    handle_remove_borrower_command,
    handle_remove_borrower_confirmed,
    handle_remove_borrower_picked,
    handle_settle_cancelled,
    handle_settle_command,
    handle_settle_confirmed,
    handle_settle_person_selected,
    handle_shared_borrower_toggled,
    handle_shared_borrowers_done,
    handle_shared_cancelled,
    handle_shared_category_selected,
    handle_shared_command,
    handle_shared_confirmed,
    handle_shared_description_skipped,
    handle_transaction_command,
)

IMPLEMENTED_COMMANDS = {
    'start', 'help', 'expense', 'income', 'invest', 'transactions', 'edit', 'delete',
    'shared', 'settle', 'owed', 'borrowers', 'addborrower', 'removeborrower',
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

    def test_duplicate_person_returns_error_without_creating_transaction(self):
        reply = handle_shared_command('/shared 100 rent alice:30 alice:20')

        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(reply.startswith('❌'))

    def test_single_person_share_leaves_the_rest_as_the_users_own_expense(self):
        reply = handle_shared_command('/shared 25000 rent alice:5000')

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.amount, Decimal('25000'))
        share = transaction.shares.get()
        self.assertEqual(share.person, self.alice)
        self.assertEqual(share.amount, Decimal('5000'))
        self.assertIn('Alice', reply)

    def test_malformed_tokens_are_rejected_instead_of_silently_becoming_the_description(self):
        reply = handle_shared_command('/shared 1200 rent alice')

        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(reply.startswith('❌'))

    def test_description_words_are_not_mistaken_for_person_shares(self):
        reply = handle_shared_command('/shared 1200 rent alice:400 bob:300 lunch with the team')

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.description, 'lunch with the team')
        self.assertEqual(transaction.shares.count(), 2)

    def test_reusing_an_existing_person_does_not_create_a_duplicate(self):
        handle_shared_command('/shared 1000 rent alice:400')
        handle_shared_command('/shared 2000 rent alice:500')

        self.assertEqual(Person.objects.filter(name='Alice').count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)

    def test_bare_command_launches_the_borrower_picker_instead_of_usage_text(self):
        result = handle_shared_command('/shared')

        self.assertIsInstance(result, tuple)
        prompt, markup = result
        self.assertNotIn('Usage', prompt)
        button_texts = {b.text for row in markup.inline_keyboard for b in row}
        self.assertEqual(button_texts, {'Alice', 'Bob', '✅ Done', '❌ Cancel'})

    def test_bare_command_with_no_borrowers_suggests_addborrower(self):
        Person.objects.all().delete()

        result = handle_shared_command('/shared')

        self.assertIsInstance(result, str)
        self.assertIn('/addborrower', result)


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


def _select_borrowers(chat_id, people):
    """Simulates tapping each of `people`'s buttons on the /shared borrower
    picker in turn, then Done — mirroring how the real toggle buttons
    accumulate the selected-id list in their callback_data."""
    selected = set()
    for person in people:
        csv = ','.join(str(i) for i in sorted(selected))
        handle_shared_borrower_toggled(f'shb|{csv}|{person.pk}', chat_id)
        selected.add(person.pk)
    csv = ','.join(str(i) for i in sorted(selected))
    return handle_shared_borrowers_done(f'shdone|{csv}', chat_id)


class BorrowerManagementCommandTests(TestCase):
    def setUp(self):
        _PENDING_PROMPTS.clear()
        self.rent = Category.objects.create(name='Rent', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)

    def test_adding_a_new_borrower(self):
        reply = handle_add_borrower_command(CHAT_ID, '/addborrower Alice')

        self.assertEqual(Person.objects.filter(name='Alice', is_active=True).count(), 1)
        self.assertIn('Alice', reply)
        self.assertTrue(reply.startswith('✅'))

    def test_adding_a_duplicate_borrower_does_not_create_a_second_row(self):
        Person.objects.create(name='Alice', is_active=True)

        reply = handle_add_borrower_command(CHAT_ID, '/addborrower Alice')

        self.assertEqual(Person.objects.filter(name__iexact='alice').count(), 1)
        self.assertIn('already exists', reply)
        self.assertTrue(reply.startswith('⚠️'))

    def test_bare_addborrower_prompts_then_the_next_reply_adds_the_name(self):
        reply = handle_add_borrower_command(CHAT_ID, '/addborrower')

        self.assertFalse(Person.objects.exists())
        self.assertIn('name', reply.lower())

        reply = handle_plain_message(CHAT_ID, 'Alice')

        self.assertEqual(Person.objects.filter(name='Alice').count(), 1)
        self.assertTrue(reply.startswith('✅'))

    def test_build_borrowers_message_lists_active_borrowers_with_balances(self):
        Person.objects.create(name='Alice', is_active=True)
        handle_add_borrower_command(CHAT_ID, '/addborrower Bob')
        handle_shared_command('/shared 1000 rent alice:400')

        message = build_borrowers_message()

        self.assertIn('Alice', message)
        self.assertIn('400', message)
        self.assertIn('Bob', message)

    def test_build_borrowers_message_with_no_borrowers_suggests_addborrower(self):
        message = build_borrowers_message()

        self.assertIn('/addborrower', message)

    def test_remove_borrower_deactivates_and_preserves_history(self):
        alice = Person.objects.create(name='Alice', is_active=True)
        handle_shared_command('/shared 1000 rent alice:400')

        pick_result = handle_remove_borrower_command('/removeborrower')
        _, markup = pick_result
        pick_btn = next(b for row in markup.inline_keyboard for b in row if b.text == 'Alice')

        confirm_result = handle_remove_borrower_picked(pick_btn.callback_data, CHAT_ID)
        message, markup = confirm_result
        self.assertIn('1 historical shared expense', message)
        confirm_btn = next(b for row in markup.inline_keyboard for b in row if b.text == 'Remove')

        reply = handle_remove_borrower_confirmed(confirm_btn.callback_data, CHAT_ID)

        alice.refresh_from_db()
        self.assertFalse(alice.is_active)
        self.assertTrue(reply.startswith('✅'))
        # historical shared expense is untouched
        self.assertEqual(alice.shares.count(), 1)

    def test_remove_borrower_cancel_leaves_the_borrower_active(self):
        alice = Person.objects.create(name='Alice', is_active=True)

        reply = handle_remove_borrower_cancelled(f'rmbrwno', CHAT_ID)

        alice.refresh_from_db()
        self.assertTrue(alice.is_active)
        self.assertIn('Cancelled', reply)

    def test_removed_borrower_does_not_appear_in_the_shared_picker(self):
        Person.objects.create(name='Alice', is_active=False)
        Person.objects.create(name='Bob', is_active=True)

        _, markup = handle_shared_command('/shared')

        button_texts = {b.text for row in markup.inline_keyboard for b in row}
        self.assertNotIn('Alice', button_texts)
        self.assertIn('Bob', button_texts)

    def test_remove_borrower_with_no_active_borrowers(self):
        reply = handle_remove_borrower_command('/removeborrower')

        self.assertIsInstance(reply, str)
        self.assertIn("don't have any borrowers", reply)


class SharedInteractiveFlowTests(TestCase):
    def setUp(self):
        _PENDING_PROMPTS.clear()
        self.rent = Category.objects.create(name='Rent', is_active=True, category_type=Category.CategoryType.EXPENSE)
        self.mutual_fund = Category.objects.create(
            name='MutualFund', is_active=True, category_type=Category.CategoryType.TRANSFER
        )
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.alice = Person.objects.create(name='Alice', is_active=True)
        self.bob = Person.objects.create(name='Bob', is_active=True)

    def _pick_category(self, chat_id, category):
        pending = _PENDING_PROMPTS[chat_id]
        self.assertEqual(pending[0], 'SHARED_CATEGORY')
        return handle_shared_category_selected(f'shcat|{category.pk}', chat_id)

    def test_toggling_a_borrower_twice_deselects_them(self):
        _, markup = handle_shared_borrower_toggled('shb||1', CHAT_ID)
        alice_btn = next(b for row in markup.inline_keyboard for b in row if 'Alice' in b.text)
        self.assertTrue(alice_btn.text.startswith('✓'))

        _, markup = handle_shared_borrower_toggled(alice_btn.callback_data, CHAT_ID)
        alice_btn = next(b for row in markup.inline_keyboard for b in row if b.text == 'Alice')
        self.assertFalse(alice_btn.text.startswith('✓'))

    def test_done_with_no_selection_returns_error_and_keeps_the_picker_open(self):
        reply, markup = handle_shared_borrowers_done('shdone|', CHAT_ID)

        self.assertTrue(reply.startswith('❌'))
        self.assertIsInstance(markup, type(markup))
        self.assertNotIn(CHAT_ID, _PENDING_PROMPTS)

    def test_done_with_selection_prompts_for_the_amount(self):
        reply = _select_borrowers(CHAT_ID, [self.alice, self.bob])

        self.assertEqual(reply, '💰 How much did you pay in total?')
        self.assertEqual(_PENDING_PROMPTS[CHAT_ID][0], 'SHARED_AMOUNT')
        self.assertEqual(set(_PENDING_PROMPTS[CHAT_ID][1]), {self.alice.pk, self.bob.pk})

    def test_invalid_amount_keeps_the_flow_alive_for_a_retry(self):
        _select_borrowers(CHAT_ID, [self.alice])

        reply = handle_plain_message(CHAT_ID, 'not-a-number')

        self.assertTrue(reply.startswith('❌'))
        self.assertEqual(_PENDING_PROMPTS[CHAT_ID][0], 'SHARED_AMOUNT')

        # the chat can now retry with a valid amount
        reply = handle_plain_message(CHAT_ID, '25000')
        self.assertIn('category', reply[0].lower())

    def test_amount_leads_to_a_category_picker_restricted_to_expense_categories(self):
        _select_borrowers(CHAT_ID, [self.alice])

        _, markup = handle_plain_message(CHAT_ID, '25000')

        button_texts = {b.text for row in markup.inline_keyboard for b in row}
        self.assertIn('Rent', button_texts)
        self.assertNotIn('MutualFund', button_texts)

    def test_stale_category_callback_is_rejected(self):
        reply = handle_shared_category_selected(f'shcat|{self.rent.pk}', CHAT_ID)

        self.assertIn('no longer valid', reply)
        self.assertFalse(Transaction.objects.exists())

    def test_category_selection_prompts_for_the_first_borrowers_share(self):
        _select_borrowers(CHAT_ID, [self.alice, self.bob])
        handle_plain_message(CHAT_ID, '25000')

        reply = self._pick_category(CHAT_ID, self.rent)

        self.assertIn("Alice", reply)
        self.assertEqual(_PENDING_PROMPTS[CHAT_ID][0], 'SHARED_SHARE')

    def test_invalid_share_keeps_prompting_for_the_same_borrower(self):
        _select_borrowers(CHAT_ID, [self.alice])
        handle_plain_message(CHAT_ID, '25000')
        self._pick_category(CHAT_ID, self.rent)

        reply = handle_plain_message(CHAT_ID, 'not-a-number')

        self.assertTrue(reply.startswith('❌'))
        self.assertIn('Alice', reply)
        self.assertEqual(_PENDING_PROMPTS[CHAT_ID][0], 'SHARED_SHARE')

    def test_shares_move_to_the_next_borrower_in_turn(self):
        _select_borrowers(CHAT_ID, [self.alice, self.bob])
        handle_plain_message(CHAT_ID, '25000')
        self._pick_category(CHAT_ID, self.rent)

        reply = handle_plain_message(CHAT_ID, '5000')

        self.assertIn('Bob', reply)

    def test_shares_exceeding_the_total_restart_share_entry(self):
        _select_borrowers(CHAT_ID, [self.alice, self.bob])
        handle_plain_message(CHAT_ID, '100')
        self._pick_category(CHAT_ID, self.rent)
        handle_plain_message(CHAT_ID, '60')

        reply = handle_plain_message(CHAT_ID, '60')

        self.assertTrue(reply.startswith('❌'))
        self.assertIn('Please enter the shares again', reply)
        self.assertIn('Alice', reply)
        pending = _PENDING_PROMPTS[CHAT_ID]
        self.assertEqual(pending[0], 'SHARED_SHARE')
        self.assertEqual(pending[4], ())  # collected shares were reset

        # can now re-enter valid shares
        handle_plain_message(CHAT_ID, '30')
        reply = handle_plain_message(CHAT_ID, '30')
        self.assertIn('description', reply[0].lower())

    def test_shares_exactly_equal_to_the_total_leave_no_personal_share(self):
        _select_borrowers(CHAT_ID, [self.alice, self.bob])
        handle_plain_message(CHAT_ID, '100')
        self._pick_category(CHAT_ID, self.rent)
        handle_plain_message(CHAT_ID, '50')
        handle_plain_message(CHAT_ID, '50')

        skip_result = handle_shared_description_skipped(CALLBACK_PREFIX_SHARED_DESC_SKIP, CHAT_ID)
        message, markup = skip_result
        self.assertIn('Your share: ₹0.00', message)

        confirm_btn = next(b for row in markup.inline_keyboard for b in row if 'Confirm' in b.text)
        handle_shared_confirmed(confirm_btn.callback_data, CHAT_ID)

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.amount - sum(s.amount for s in transaction.shares.all()), Decimal('0'))

    def test_description_via_text_reply_reaches_the_confirmation_screen(self):
        _select_borrowers(CHAT_ID, [self.alice])
        handle_plain_message(CHAT_ID, '25000')
        self._pick_category(CHAT_ID, self.rent)
        handle_plain_message(CHAT_ID, '5000')

        reply = handle_plain_message(CHAT_ID, 'monthly rent')

        message, markup = reply
        self.assertIn('monthly rent', message)
        self.assertIn('Your share: ₹20,000.00', message)
        self.assertEqual(_PENDING_PROMPTS[CHAT_ID][0], 'SHARED_CONFIRM')

    def test_confirm_creates_the_transaction_with_the_correct_split(self):
        _select_borrowers(CHAT_ID, [self.alice, self.bob])
        handle_plain_message(CHAT_ID, '25000')
        self._pick_category(CHAT_ID, self.rent)
        handle_plain_message(CHAT_ID, '5000')
        handle_plain_message(CHAT_ID, '5000')
        _, markup = handle_plain_message(CHAT_ID, 'monthly rent')
        confirm_btn = next(b for row in markup.inline_keyboard for b in row if 'Confirm' in b.text)

        reply = handle_shared_confirmed(confirm_btn.callback_data, CHAT_ID)

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.amount, Decimal('25000'))
        self.assertEqual(transaction.category, self.rent)
        self.assertEqual(transaction.description, 'monthly rent')
        shares = {share.person: share.amount for share in transaction.shares.all()}
        self.assertEqual(shares, {self.alice: Decimal('5000'), self.bob: Decimal('5000')})
        self.assertIn('Your expense: ₹15,000.00', reply)
        self.assertIn('Amount owed to you: ₹10,000.00', reply)
        self.assertNotIn(CHAT_ID, _PENDING_PROMPTS)

    def test_cancel_at_the_borrower_stage_creates_nothing(self):
        _select_borrowers(CHAT_ID, [self.alice])

        reply = handle_shared_cancelled(CALLBACK_PREFIX_SHARED_CANCEL, CHAT_ID)

        self.assertEqual(reply, '❌ Shared expense cancelled.')
        self.assertFalse(Transaction.objects.exists())
        self.assertNotIn(CHAT_ID, _PENDING_PROMPTS)

    def test_cancel_at_the_confirmation_stage_creates_nothing(self):
        _select_borrowers(CHAT_ID, [self.alice])
        handle_plain_message(CHAT_ID, '25000')
        self._pick_category(CHAT_ID, self.rent)
        handle_plain_message(CHAT_ID, '5000')
        handle_shared_description_skipped(CALLBACK_PREFIX_SHARED_DESC_SKIP, CHAT_ID)

        reply = handle_shared_cancelled(CALLBACK_PREFIX_SHARED_CANCEL, CHAT_ID)

        self.assertEqual(reply, '❌ Shared expense cancelled.')
        self.assertFalse(Transaction.objects.exists())
        self.assertNotIn(CHAT_ID, _PENDING_PROMPTS)

    def test_stale_confirm_callback_after_cancel_is_rejected(self):
        reply = handle_shared_confirmed(CALLBACK_PREFIX_SHARED_CONFIRM, CHAT_ID)

        self.assertIn('no longer valid', reply)
        self.assertFalse(Transaction.objects.exists())

    def test_borrower_removed_mid_flow_aborts_before_confirmation(self):
        _select_borrowers(CHAT_ID, [self.alice])
        handle_plain_message(CHAT_ID, '25000')
        self.alice.is_active = False
        self.alice.save(update_fields=['is_active'])

        reply = self._pick_category(CHAT_ID, self.rent)

        self.assertIn('no longer available', reply)
        self.assertFalse(Transaction.objects.exists())
        self.assertNotIn(CHAT_ID, _PENDING_PROMPTS)

    def test_a_stray_text_reply_during_a_button_only_stage_does_not_crash(self):
        _select_borrowers(CHAT_ID, [self.alice])
        handle_plain_message(CHAT_ID, '25000')  # now awaiting a category button tap

        reply = handle_plain_message(CHAT_ID, 'some random text')

        self.assertIn('buttons', reply.lower())
        # the category picker is still usable afterwards
        self.assertEqual(_PENDING_PROMPTS[CHAT_ID][0], 'SHARED_CATEGORY')


class SettleInteractiveFlowTests(TestCase):
    def setUp(self):
        _PENDING_PROMPTS.clear()
        self.rent = Category.objects.create(name='Rent', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.alice = Person.objects.create(name='Alice', is_active=True)
        handle_shared_command('/shared 1000 rent alice:400')

    def test_bare_settle_with_no_borrowers_suggests_addborrower(self):
        Person.objects.update(is_active=False)  # Alice has a protected share, so deactivate rather than delete

        reply = handle_settle_command('/settle')

        self.assertIsInstance(reply, str)
        self.assertIn('/addborrower', reply)

    def test_bare_settle_shows_a_borrower_picker(self):
        _, markup = handle_settle_command('/settle')

        button_texts = {b.text for row in markup.inline_keyboard for b in row}
        self.assertIn('Alice', button_texts)

    def test_selecting_a_borrower_shows_their_outstanding_balance_and_asks_for_the_amount(self):
        _, markup = handle_settle_command('/settle')
        btn = next(b for row in markup.inline_keyboard for b in row if b.text == 'Alice')

        reply = handle_settle_person_selected(btn.callback_data, CHAT_ID)

        self.assertIn('400', reply)
        self.assertEqual(_PENDING_PROMPTS[CHAT_ID], ('SETTLE_AMOUNT', self.alice.pk))

    def test_amount_reply_shows_a_confirmation_with_the_remaining_balance(self):
        handle_settle_person_selected(f'stlp|{self.alice.pk}', CHAT_ID)

        message, markup = handle_plain_message(CHAT_ID, '150')

        self.assertIn('Remaining: ₹250.00', message)
        confirm_btn = next(b for row in markup.inline_keyboard for b in row if 'Confirm' in b.text)
        self.assertEqual(confirm_btn.callback_data, f'stlconfirm|{self.alice.pk}|150')

    def test_confirm_creates_the_settlement_transaction(self):
        handle_settle_person_selected(f'stlp|{self.alice.pk}', CHAT_ID)
        handle_plain_message(CHAT_ID, '150')

        reply = handle_settle_confirmed(f'stlconfirm|{self.alice.pk}|150', CHAT_ID)

        transaction = Transaction.objects.get(transaction_type=Transaction.TransactionType.SETTLEMENT)
        self.assertEqual(transaction.amount, Decimal('150'))
        self.assertEqual(transaction.person, self.alice)
        self.assertEqual(outstanding_for_person(self.alice), Decimal('250'))
        self.assertIn('150', reply)

    def test_full_repayment_zeroes_the_outstanding_balance(self):
        handle_settle_person_selected(f'stlp|{self.alice.pk}', CHAT_ID)
        handle_plain_message(CHAT_ID, '400')

        handle_settle_confirmed(f'stlconfirm|{self.alice.pk}|400', CHAT_ID)

        self.assertEqual(outstanding_for_person(self.alice), Decimal('0'))

    def test_cancel_creates_no_settlement(self):
        handle_settle_person_selected(f'stlp|{self.alice.pk}', CHAT_ID)
        handle_plain_message(CHAT_ID, '150')

        reply = handle_settle_cancelled(CALLBACK_PREFIX_SHARED_CANCEL, CHAT_ID)

        self.assertFalse(Transaction.objects.filter(transaction_type=Transaction.TransactionType.SETTLEMENT).exists())
        self.assertIn('cancelled', reply.lower())
        self.assertNotIn(CHAT_ID, _PENDING_PROMPTS)


class OwedInteractiveFlowTests(TestCase):
    def setUp(self):
        _PENDING_PROMPTS.clear()
        self.rent = Category.objects.create(name='Rent', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.alice = Person.objects.create(name='Alice', is_active=True)
        self.bob = Person.objects.create(name='Bob', is_active=True)

    def test_no_borrowers_suggests_addborrower(self):
        Person.objects.all().delete()

        reply = handle_owed_command('/owed')

        self.assertIsInstance(reply, str)
        self.assertIn('/addborrower', reply)

    def test_shows_a_picker_with_an_all_option(self):
        _, markup = handle_owed_command('/owed')

        button_texts = {b.text for row in markup.inline_keyboard for b in row}
        self.assertEqual(button_texts, {'Alice', 'Bob', 'All'})

    def test_selecting_a_borrower_shows_their_balance(self):
        handle_shared_command('/shared 1000 rent alice:400')

        reply = handle_owed_person_selected(f'owedp|{self.alice.pk}', CHAT_ID)

        self.assertIn('Alice', reply)
        self.assertIn('400', reply)

    def test_selecting_a_borrower_with_no_outstanding_balance(self):
        reply = handle_owed_person_selected(f'owedp|{self.bob.pk}', CHAT_ID)

        self.assertIn('₹0.00', reply)

    def test_all_selection_matches_the_non_interactive_summary(self):
        handle_shared_command('/shared 1000 rent alice:400')

        reply = handle_owed_all_selected(CALLBACK_PREFIX_OWED_ALL, CHAT_ID)

        self.assertEqual(reply, build_owed_message())
        self.assertIn('Alice', reply)
