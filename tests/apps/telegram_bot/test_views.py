import json
from unittest.mock import patch

from django.test import RequestFactory, TestCase

from apps.finance.models import Account, Category, Transaction
from apps.telegram_bot.views import webhook


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


class WebhookTransactionDispatchTests(TestCase):
    def setUp(self):
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
