import json
from unittest.mock import AsyncMock, patch

from django.test import RequestFactory, SimpleTestCase, TestCase
from telegram import Update

from apps.finance.models import Account, Category, Transaction
from apps.telegram_bot.commands import _PENDING_AMOUNT_PROMPTS
from apps.telegram_bot.views import _answer_callback, _send_reply, app, webhook


def telegram_update(text, update_id=1, chat_id=42):
    return {
        'update_id': update_id,
        'message': {
            'message_id': 1,
            'date': 1650000000,
            'chat': {'id': chat_id, 'type': 'private'},
            'text': text,
        },
    }


def telegram_callback_update(data, update_id=1, chat_id=42):
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
        _PENDING_AMOUNT_PROMPTS.clear()
        self.factory = RequestFactory()
        self.category = Category.objects.create(name='Food', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)

    def _post(self, payload):
        return self.factory.post('/telegram/webhook/', data=json.dumps(payload).encode(), content_type='application/json')

    @patch('apps.telegram_bot.views._send_reply')
    def test_expense_command_creates_transaction_and_replies_to_chat(self, mock_send_reply):
        response = webhook(self._post(telegram_update('/expense 250 food swiggy', chat_id=42)))

        self.assertEqual(response.status_code, 200)
        transaction = Transaction.objects.get()
        self.assertEqual(transaction.category, self.category)
        self.assertEqual(transaction.description, 'swiggy')

        mock_send_reply.assert_called_once()
        chat_id, reply_text = mock_send_reply.call_args[0]
        self.assertEqual(chat_id, 42)
        self.assertIn('spent on', reply_text)

    @patch('apps.telegram_bot.views._send_reply')
    def test_bare_expense_then_amount_reply_leads_to_category_picker(self, mock_send_reply):
        # The full "click /expense, then just answer the amount" flow.
        response = webhook(self._post(telegram_update('/expense', chat_id=42)))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        chat_id, prompt = mock_send_reply.call_args[0]
        self.assertEqual(chat_id, 42)
        self.assertEqual(prompt, '💸 How much did you spend?')

        mock_send_reply.reset_mock()
        response = webhook(self._post(telegram_update('250', chat_id=42)))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        mock_send_reply.assert_called_once()
        chat_id, picker_prompt = mock_send_reply.call_args[0]
        markup = mock_send_reply.call_args[1]['reply_markup']
        self.assertEqual(chat_id, 42)
        self.assertIn('250', picker_prompt)
        self.assertIsNotNone(markup)

    @patch('apps.telegram_bot.views._send_reply')
    def test_expense_amount_only_sends_a_category_picker(self, mock_send_reply):
        response = webhook(self._post(telegram_update('/expense 250', chat_id=42)))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        mock_send_reply.assert_called_once()
        chat_id, prompt = mock_send_reply.call_args[0]
        markup = mock_send_reply.call_args[1]['reply_markup']
        self.assertEqual(chat_id, 42)
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
        response = webhook(self._post(telegram_update('/EXPENSE 250 food', chat_id=42)))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Transaction.objects.exists())
        mock_send_reply.assert_called_once()

    @patch('apps.telegram_bot.views._send_reply')
    def test_help_command_sends_help_message(self, mock_send_reply):
        response = webhook(self._post(telegram_update('/help', chat_id=42)))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        mock_send_reply.assert_called_once()
        chat_id, reply_text = mock_send_reply.call_args[0]
        self.assertEqual(chat_id, 42)
        self.assertIn('/expense', reply_text)
        self.assertIn('Food', reply_text)

    @patch('apps.telegram_bot.views._send_reply')
    def test_start_command_sends_welcome_message(self, mock_send_reply):
        response = webhook(self._post(telegram_update('/start', chat_id=42)))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        mock_send_reply.assert_called_once()
        chat_id, reply_text = mock_send_reply.call_args[0]
        self.assertEqual(chat_id, 42)
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

        response = webhook(self._post(telegram_update('/transactions', chat_id=42)))

        self.assertEqual(response.status_code, 200)
        mock_send_reply.assert_called_once()
        chat_id, reply_text = mock_send_reply.call_args[0]
        self.assertEqual(chat_id, 42)
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

        response = webhook(self._post(telegram_update(f'/edit {transaction.pk} 300 food petrol', chat_id=42)))

        self.assertEqual(response.status_code, 200)
        transaction.refresh_from_db()
        self.assertEqual(str(transaction.amount), '300.00')
        self.assertEqual(transaction.description, 'petrol')

        mock_send_reply.assert_called_once()
        chat_id, reply_text = mock_send_reply.call_args[0]
        self.assertEqual(chat_id, 42)
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

        response = webhook(self._post(telegram_update(f'/delete {transaction.pk}', chat_id=42)))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.filter(pk=transaction.pk).exists())

        mock_send_reply.assert_called_once()
        chat_id, reply_text = mock_send_reply.call_args[0]
        self.assertEqual(chat_id, 42)
        self.assertIn('Deleted', reply_text)

    @patch('apps.telegram_bot.views._send_reply')
    def test_unrecognized_slash_command_replies_with_hint(self, mock_send_reply):
        response = webhook(self._post(telegram_update('/expenses 350', chat_id=42)))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        mock_send_reply.assert_called_once()
        chat_id, reply_text = mock_send_reply.call_args[0]
        self.assertEqual(chat_id, 42)
        self.assertIn('/expenses', reply_text)

    @patch('apps.telegram_bot.views._send_reply')
    def test_invalid_transaction_command_replies_with_error_and_creates_nothing(self, mock_send_reply):
        response = webhook(self._post(telegram_update('/expense abc food')))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())
        mock_send_reply.assert_called_once()
        _, reply_text = mock_send_reply.call_args[0]
        self.assertTrue(reply_text.startswith('❌'))


class WebhookCallbackQueryDispatchTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.category = Category.objects.create(name='Food', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)

    def _post(self, payload):
        return self.factory.post('/telegram/webhook/', data=json.dumps(payload).encode(), content_type='application/json')

    @patch('apps.telegram_bot.views._answer_callback')
    def test_category_selection_with_single_account_creates_transaction(self, mock_answer):
        response = webhook(self._post(telegram_callback_update(f'cat|EXPENSE|250|{self.category.pk}', chat_id=42)))

        self.assertEqual(response.status_code, 200)
        transaction = Transaction.objects.get()
        self.assertEqual(transaction.category, self.category)
        self.assertEqual(transaction.account, self.account)

        mock_answer.assert_called_once()
        callback_query, text = mock_answer.call_args[0]
        self.assertIn('spent on', text)

    @patch('apps.telegram_bot.views._answer_callback')
    def test_category_selection_with_multiple_accounts_sends_account_picker(self, mock_answer):
        Account.objects.create(name='UPI', is_active=True)

        response = webhook(self._post(telegram_callback_update(f'cat|EXPENSE|250|{self.category.pk}', chat_id=42)))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())

        mock_answer.assert_called_once()
        callback_query, text = mock_answer.call_args[0]
        markup = mock_answer.call_args[1]['reply_markup']
        self.assertIn('pick an account', text)
        self.assertIsNotNone(markup)

    @patch('apps.telegram_bot.views._answer_callback')
    def test_account_selection_creates_transaction(self, mock_answer):
        response = webhook(self._post(
            telegram_callback_update(f'acc|EXPENSE|250|{self.category.pk}|{self.account.pk}', chat_id=42)
        ))

        self.assertEqual(response.status_code, 200)
        transaction = Transaction.objects.get()
        self.assertEqual(transaction.category, self.category)
        self.assertEqual(transaction.account, self.account)
        mock_answer.assert_called_once()

    @patch('apps.telegram_bot.views._answer_callback')
    def test_unknown_callback_prefix_is_handled_gracefully(self, mock_answer):
        response = webhook(self._post(telegram_callback_update('unknown|whatever', chat_id=42)))

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
            _send_reply(42, 'hello')

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
                'data': 'cat|EXPENSE|250|1',
                'message': {
                    'message_id': 1,
                    'date': 1650000000,
                    'chat': {'id': 42, 'type': 'private'},
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
