import json
from unittest.mock import AsyncMock, patch

from django.test import RequestFactory, SimpleTestCase, TestCase
from telegram import Update

from constants import CALLBACK_PREFIX_ACCOUNT, CALLBACK_PREFIX_CATEGORY, TEST_CHAT_ID, TEST_WEBHOOK_URL

from apps.finance.models import Account, Category, Transaction
from apps.telegram_bot.commands import _PENDING_PROMPTS
from apps.telegram_bot.views import _answer_callback, _send_reply, app, webhook


def telegram_update(text, update_id=1, chat_id=TEST_CHAT_ID):
    return {
        'update_id': update_id,
        'message': {
            'message_id': 1,
            'date': 1650000000,
            'chat': {'id': chat_id, 'type': 'private'},
            'text': text,
        },
    }


def telegram_callback_update(data, update_id=1, chat_id=TEST_CHAT_ID):
    return {
        'update_id': update_id,
        'callback_query': {
            'id': 'callback-1',
            'from': {'id': 1, 'is_bot': False, 'first_name': 'Test'},
            'chat_instance': 'chat-instance-1',
            'data': data,
            'message': {
                'message_id': 1,
                'date': 1650000000,
                'chat': {'id': chat_id, 'type': 'private'},
                'text': 'pick one',
            },
        },
    }


class WebhookTransactionDispatchTests(TestCase):
    def setUp(self):
        _PENDING_PROMPTS.clear()
        self.factory = RequestFactory()
        self.category = Category.objects.create(name='Food', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)

    def _post(self, payload):
        return self.factory.post(TEST_WEBHOOK_URL, data=json.dumps(payload).encode(), content_type='application/json')

    @patch('apps.telegram_bot.views._send_reply')
    def test_expense_command_creates_transaction_and_replies_to_chat(self, mock_send_reply):
        response = webhook(self._post(telegram_update('/expense 250 food swiggy')))

        self.assertEqual(response.status_code, 200)
        transaction = Transaction.objects.get()
        self.assertEqual(transaction.category, self.category)
        self.assertEqual(transaction.description, 'swiggy')

        mock_send_reply.assert_called_once()
        chat_id, reply_text = mock_send_reply.call_args[0]
        self.assertEqual(chat_id, TEST_CHAT_ID)
        self.assertIn('spent on', reply_text)

    @patch('apps.telegram_bot.views._send_reply')
    def test_bare_expense_then_amount_reply_leads_to_category_picker(self, mock_send_reply):
        # The full "click /expense, then just answer the amount" flow.
        response = webhook(self._post(telegram_update('/expense')))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        chat_id, prompt = mock_send_reply.call_args[0]
        self.assertEqual(chat_id, TEST_CHAT_ID)
        self.assertEqual(prompt, '💸 How much did you spend?')

        mock_send_reply.reset_mock()
        response = webhook(self._post(telegram_update('250')))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        mock_send_reply.assert_called_once()
        chat_id, picker_prompt = mock_send_reply.call_args[0]
        markup = mock_send_reply.call_args[1]['reply_markup']
        self.assertEqual(chat_id, TEST_CHAT_ID)
        self.assertIn('250', picker_prompt)
        self.assertIsNotNone(markup)

    @patch('apps.telegram_bot.views._send_reply')
    def test_expense_amount_only_sends_a_category_picker(self, mock_send_reply):
        response = webhook(self._post(telegram_update('/expense 250')))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        mock_send_reply.assert_called_once()
        chat_id, prompt = mock_send_reply.call_args[0]
        markup = mock_send_reply.call_args[1]['reply_markup']
        self.assertEqual(chat_id, TEST_CHAT_ID)
        self.assertIn('250', prompt)
        self.assertIsNotNone(markup)

    @patch('apps.telegram_bot.views._send_reply')
    def test_plain_message_does_not_create_transaction_or_reply(self, mock_send_reply):
        response = webhook(self._post(telegram_update('hello')))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        mock_send_reply.assert_not_called()

    @patch('apps.telegram_bot.views._send_reply')
    def test_command_matching_is_case_insensitive(self, mock_send_reply):
        response = webhook(self._post(telegram_update('/EXPENSE 250 food')))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Transaction.objects.exists())
        mock_send_reply.assert_called_once()

    @patch('apps.telegram_bot.views._send_reply')
    def test_bot_username_suffix_is_stripped_from_command(self, mock_send_reply):
        # Group chats address commands to a specific bot, e.g. '/expense@my_bot'.
        response = webhook(self._post(telegram_update('/expense@my_finance_bot 250 food')))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Transaction.objects.exists())
        mock_send_reply.assert_called_once()

    @patch('apps.telegram_bot.views._send_reply')
    def test_help_command_sends_help_message(self, mock_send_reply):
        response = webhook(self._post(telegram_update('/help')))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        mock_send_reply.assert_called_once()
        chat_id, reply_text = mock_send_reply.call_args[0]
        self.assertEqual(chat_id, TEST_CHAT_ID)
        self.assertIn('/expense', reply_text)
        self.assertIn('Food', reply_text)

    @patch('apps.telegram_bot.views._send_reply')
    def test_start_command_sends_welcome_message(self, mock_send_reply):
        response = webhook(self._post(telegram_update('/start')))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        mock_send_reply.assert_called_once()
        chat_id, reply_text = mock_send_reply.call_args[0]
        self.assertEqual(chat_id, TEST_CHAT_ID)
        self.assertIn('Welcome', reply_text)
        self.assertIn('/help', reply_text)

    @patch('apps.telegram_bot.views._send_reply')
    def test_transactions_command_sends_history(self, mock_send_reply):
        Transaction.objects.create(
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount='250',
            category=self.category,
            account=self.account,
            transaction_at='2026-08-22T12:00:00Z',
        )

        response = webhook(self._post(telegram_update('/transactions')))

        self.assertEqual(response.status_code, 200)
        mock_send_reply.assert_called_once()
        chat_id, reply_text = mock_send_reply.call_args[0]
        self.assertEqual(chat_id, TEST_CHAT_ID)
        self.assertIn('Recent transactions', reply_text)
        self.assertIn('250.00', reply_text)

    @patch('apps.telegram_bot.views._send_reply')
    def test_edit_command_updates_transaction_and_replies_to_chat(self, mock_send_reply):
        transaction = Transaction.objects.create(
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount='100',
            category=self.category,
            account=self.account,
            transaction_at='2026-08-22T12:00:00Z',
        )

        response = webhook(self._post(telegram_update(f'/edit {transaction.pk} 300 food petrol')))

        self.assertEqual(response.status_code, 200)
        transaction.refresh_from_db()
        self.assertEqual(str(transaction.amount), '300.00')
        self.assertEqual(transaction.description, 'petrol')

        mock_send_reply.assert_called_once()
        chat_id, reply_text = mock_send_reply.call_args[0]
        self.assertEqual(chat_id, TEST_CHAT_ID)
        self.assertIn('Updated', reply_text)

    @patch('apps.telegram_bot.views._send_reply')
    def test_delete_command_removes_transaction_and_replies_to_chat(self, mock_send_reply):
        transaction = Transaction.objects.create(
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount='100',
            category=self.category,
            account=self.account,
            transaction_at='2026-08-22T12:00:00Z',
        )

        response = webhook(self._post(telegram_update(f'/delete {transaction.pk}')))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.filter(pk=transaction.pk).exists())

        mock_send_reply.assert_called_once()
        chat_id, reply_text = mock_send_reply.call_args[0]
        self.assertEqual(chat_id, TEST_CHAT_ID)
        self.assertIn('Deleted', reply_text)

    @patch('apps.telegram_bot.views._send_reply')
    def test_unrecognized_slash_command_replies_with_hint(self, mock_send_reply):
        response = webhook(self._post(telegram_update('/expenses 350')))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        mock_send_reply.assert_called_once()
        chat_id, reply_text = mock_send_reply.call_args[0]
        self.assertEqual(chat_id, TEST_CHAT_ID)
        self.assertIn('/expenses', reply_text)

    @patch('apps.telegram_bot.views._send_reply')
    def test_invalid_transaction_command_replies_with_error_and_creates_nothing(self, mock_send_reply):
        response = webhook(self._post(telegram_update('/expense abc food')))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        mock_send_reply.assert_called_once()
        _, reply_text = mock_send_reply.call_args[0]
        self.assertTrue(reply_text.startswith('❌'))

    @patch('apps.telegram_bot.views._dispatch_command')
    def test_unexpected_dispatch_error_is_acknowledged_not_crashed(self, mock_dispatch):
        # A bug in our own processing must not surface as a Telegram-facing
        # 400/500 — it's not "an invalid update", it's our fault, and Telegram
        # would otherwise retry-storm a request that fails the same way
        # every time. See views.webhook's dispatch try/except.
        mock_dispatch.side_effect = RuntimeError('boom')

        response = webhook(self._post(telegram_update('/expense 250 food')))

        self.assertEqual(response.status_code, 200)


class WebhookCallbackQueryDispatchTests(TestCase):
    def setUp(self):
        _PENDING_PROMPTS.clear()
        self.factory = RequestFactory()
        self.category = Category.objects.create(name='Food', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)

    def _post(self, payload):
        return self.factory.post(TEST_WEBHOOK_URL, data=json.dumps(payload).encode(), content_type='application/json')

    @patch('apps.telegram_bot.views._answer_callback')
    def test_category_selection_with_single_account_prompts_for_a_description(self, mock_answer):
        response = webhook(self._post(telegram_callback_update(f'{CALLBACK_PREFIX_CATEGORY}|EXPENSE|250|{self.category.pk}')))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())

        mock_answer.assert_called_once()
        callback_query, text = mock_answer.call_args[0]
        markup = mock_answer.call_args[1]['reply_markup']
        self.assertIn('spent on', text)
        self.assertIn('Add a description', text)
        self.assertEqual(markup.inline_keyboard[0][0].text, '⏭ Skip')

    @patch('apps.telegram_bot.views._answer_callback')
    def test_category_selection_with_multiple_accounts_sends_account_picker(self, mock_answer):
        Account.objects.create(name='UPI', is_active=True)

        response = webhook(self._post(telegram_callback_update(f'{CALLBACK_PREFIX_CATEGORY}|EXPENSE|250|{self.category.pk}')))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())

        mock_answer.assert_called_once()
        callback_query, text = mock_answer.call_args[0]
        markup = mock_answer.call_args[1]['reply_markup']
        self.assertIn('pick an account', text)
        self.assertIsNotNone(markup)

    @patch('apps.telegram_bot.views._answer_callback')
    def test_account_selection_prompts_for_a_description(self, mock_answer):
        response = webhook(self._post(
            telegram_callback_update(f'{CALLBACK_PREFIX_ACCOUNT}|EXPENSE|250|{self.category.pk}|{self.account.pk}')
        ))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        mock_answer.assert_called_once()
        callback_query, text = mock_answer.call_args[0]
        self.assertIn('Add a description', text)

    @patch('apps.telegram_bot.views._answer_callback')
    def test_skip_button_after_account_selection_creates_transaction_with_no_description(self, mock_answer):
        webhook(self._post(
            telegram_callback_update(f'{CALLBACK_PREFIX_ACCOUNT}|EXPENSE|250|{self.category.pk}|{self.account.pk}')
        ))
        skip_callback_data = mock_answer.call_args[1]['reply_markup'].inline_keyboard[0][0].callback_data
        mock_answer.reset_mock()

        response = webhook(self._post(telegram_callback_update(skip_callback_data)))

        self.assertEqual(response.status_code, 200)
        transaction = Transaction.objects.get()
        self.assertEqual(transaction.category, self.category)
        self.assertEqual(transaction.account, self.account)
        self.assertEqual(transaction.description, '')
        mock_answer.assert_called_once()
        callback_query, text = mock_answer.call_args[0]
        self.assertIn('spent on', text)

    @patch('apps.telegram_bot.views._send_reply')
    @patch('apps.telegram_bot.views._answer_callback')
    def test_plain_text_reply_after_category_selection_creates_transaction_with_that_description(
        self, mock_answer, mock_send_reply
    ):
        webhook(self._post(telegram_callback_update(f'{CALLBACK_PREFIX_CATEGORY}|EXPENSE|250|{self.category.pk}')))

        response = webhook(self._post(telegram_update('swiggy dinner')))

        self.assertEqual(response.status_code, 200)
        transaction = Transaction.objects.get()
        self.assertEqual(transaction.description, 'swiggy dinner')
        mock_send_reply.assert_called_once()
        _, reply_text = mock_send_reply.call_args[0]
        self.assertIn('spent on', reply_text)

    @patch('apps.telegram_bot.views._answer_callback')
    def test_unknown_callback_prefix_is_handled_gracefully(self, mock_answer):
        response = webhook(self._post(telegram_callback_update('unknown|whatever')))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        mock_answer.assert_called_once()
        callback_query, text = mock_answer.call_args[0]
        self.assertIn('no longer valid', text)


class BotContextManagerUsageTests(SimpleTestCase):
    """Regression test: _send_reply and _answer_callback must call Bot API
    methods inside `async with app.bot:`. app.bot is a module-level singleton
    reused across webhook requests — skip that wrapping and it still works
    on a fresh process, but raises "This HTTPXRequest is not initialized!"
    on the next real request, after a prior properly-wrapped call has shut
    the client down. Every other test in this file mocks _send_reply /
    _answer_callback entirely, so none of them would catch this; this test
    spies on Bot.__aenter__/__aexit__ to confirm the wrapping is actually
    there, without needing to reproduce that exact multi-request timing.
    """

    def test_send_reply_uses_the_bot_context_manager(self):
        with patch.object(type(app.bot), '__aenter__', new=AsyncMock(return_value=app.bot)) as mock_enter, \
                patch.object(type(app.bot), '__aexit__', new=AsyncMock(return_value=False)) as mock_exit, \
                patch.object(type(app.bot), 'send_message', new=AsyncMock()) as mock_send:
            _send_reply(TEST_CHAT_ID, 'hello')

        mock_enter.assert_called_once()
        mock_exit.assert_called_once()
        mock_send.assert_called_once()

    def test_answer_callback_uses_the_bot_context_manager(self):
        payload = {
            'update_id': 1,
            'callback_query': {
                'id': 'callback-1',
                'from': {'id': 1, 'is_bot': False, 'first_name': 'Test'},
                'chat_instance': 'chat-instance-1',
                'data': f'{CALLBACK_PREFIX_CATEGORY}|EXPENSE|250|1',
                'message': {
                    'message_id': 1,
                    'date': 1650000000,
                    'chat': {'id': TEST_CHAT_ID, 'type': 'private'},
                    'text': 'pick one',
                },
            },
        }
        update = Update.de_json(data=payload, bot=app.bot)

        with patch.object(type(app.bot), '__aenter__', new=AsyncMock(return_value=app.bot)) as mock_enter, \
                patch.object(type(app.bot), '__aexit__', new=AsyncMock(return_value=False)) as mock_exit, \
                patch.object(type(update.callback_query), 'answer', new=AsyncMock()) as mock_answer, \
                patch.object(type(update.callback_query), 'edit_message_text', new=AsyncMock()) as mock_edit:
            _answer_callback(update.callback_query, 'done')

        mock_enter.assert_called_once()
        mock_exit.assert_called_once()
        mock_answer.assert_called_once()
        mock_edit.assert_called_once()


class EndToEndTransactionLifecycleTests(TestCase):
    """Task 5.10 — a single realistic session chained across many real
    webhook calls (not isolated unit calls), covering onboarding, both
    transaction-entry styles, history, editing, deletion, and error
    recovery, all against the same live chat/database state."""

    def setUp(self):
        _PENDING_PROMPTS.clear()
        self.factory = RequestFactory()
        self.food = Category.objects.create(name='Food', icon='🍔', is_active=True, category_type=Category.CategoryType.EXPENSE)
        self.travel = Category.objects.create(name='Travel', icon='🚕', is_active=True, category_type=Category.CategoryType.EXPENSE)
        self.salary = Category.objects.create(name='Salary', icon='💰', is_active=True, category_type=Category.CategoryType.INCOME)
        self.account = Account.objects.create(name='Cash', is_active=True)
        self.chat_id = 100

    def _post_message(self, text):
        payload = {
            'update_id': 1,
            'message': {
                'message_id': 1,
                'date': 1650000000,
                'chat': {'id': self.chat_id, 'type': 'private'},
                'text': text,
            },
        }
        return self.factory.post(TEST_WEBHOOK_URL, data=json.dumps(payload).encode(), content_type='application/json')

    def _post_callback(self, data):
        payload = {
            'update_id': 1,
            'callback_query': {
                'id': 'callback-1',
                'from': {'id': 1, 'is_bot': False, 'first_name': 'Test'},
                'chat_instance': 'chat-instance-1',
                'data': data,
                'message': {
                    'message_id': 1,
                    'date': 1650000000,
                    'chat': {'id': self.chat_id, 'type': 'private'},
                    'text': 'pick one',
                },
            },
        }
        return self.factory.post(TEST_WEBHOOK_URL, data=json.dumps(payload).encode(), content_type='application/json')

    @patch('apps.telegram_bot.views._answer_callback')
    @patch('apps.telegram_bot.views._send_reply')
    def test_full_session_onboarding_through_delete(self, mock_send_reply, mock_answer_callback):
        # 1. Onboarding
        self.assertEqual(webhook(self._post_message('/start')).status_code, 200)
        self.assertIn('Welcome', mock_send_reply.call_args[0][1])

        self.assertEqual(webhook(self._post_message('/help')).status_code, 200)
        self.assertIn('/expense', mock_send_reply.call_args[0][1])

        # 2. Full typed syntax
        self.assertEqual(webhook(self._post_message('/expense 250 food swiggy')).status_code, 200)
        first = Transaction.objects.get()
        self.assertEqual(first.category, self.food)
        reply = mock_send_reply.call_args[0][1]
        self.assertIn('spent on', reply)
        self.assertIn(f'#{first.pk}', reply)

        # 3. Conversational flow: bare command -> amount reply -> button tap
        self.assertEqual(webhook(self._post_message('/income')).status_code, 200)
        self.assertEqual(mock_send_reply.call_args[0][1], '💵 How much did you receive?')

        mock_send_reply.reset_mock()
        self.assertEqual(webhook(self._post_message('75000')).status_code, 200)
        prompt, markup = mock_send_reply.call_args[0][1], mock_send_reply.call_args[1]['reply_markup']
        self.assertIn('75000', prompt)
        salary_button = next(b for row in markup.inline_keyboard for b in row if 'Salary' in b.text)

        self.assertEqual(webhook(self._post_callback(salary_button.callback_data)).status_code, 200)
        callback_query, desc_prompt = mock_answer_callback.call_args[0]
        desc_markup = mock_answer_callback.call_args[1]['reply_markup']
        self.assertIn('Add a description', desc_prompt)
        skip_button = desc_markup.inline_keyboard[0][0]

        self.assertEqual(webhook(self._post_callback(skip_button.callback_data)).status_code, 200)
        second = Transaction.objects.exclude(pk=first.pk).get()
        self.assertEqual(second.transaction_type, Transaction.TransactionType.INCOME)
        self.assertEqual(second.category, self.salary)

        # 4. History shows both, most-recent-first
        self.assertEqual(webhook(self._post_message('/transactions')).status_code, 200)
        history = mock_send_reply.call_args[0][1]
        self.assertLess(history.index(f'#{second.pk}'), history.index(f'#{first.pk}'))

        # 5. Edit the first transaction
        response = webhook(self._post_message(f'/edit {first.pk} 300 travel dinner'))
        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        self.assertEqual(first.category, self.travel)
        self.assertEqual(first.description, 'dinner')
        self.assertIn('Updated', mock_send_reply.call_args[0][1])

        # 6. Delete the second transaction
        response = webhook(self._post_message(f'/delete {second.pk}'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.filter(pk=second.pk).exists())
        self.assertIn('Deleted', mock_send_reply.call_args[0][1])

        # 7. History now shows only the edited survivor
        self.assertEqual(webhook(self._post_message('/transactions')).status_code, 200)
        history = mock_send_reply.call_args[0][1]
        self.assertIn(f'#{first.pk}', history)
        self.assertNotIn(f'#{second.pk}', history)

        # 8. Error recovery: bad input doesn't break the session
        response = webhook(self._post_message('/expense abc food'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_send_reply.call_args[0][1].startswith('❌'))

        response = webhook(self._post_message(f'/delete {first.pk}'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())

        self.assertEqual(webhook(self._post_message('/transactions')).status_code, 200)
        self.assertIn('No transactions yet', mock_send_reply.call_args[0][1])
