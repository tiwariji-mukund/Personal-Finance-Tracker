import asyncio
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from telegram import Update
from apps.finance.models import Transaction
from core.logging import get_logger
from .bot import create_application
from .commands import (
    build_help_message,
    build_transaction_history_message,
    build_welcome_message,
    handle_account_selected,
    handle_category_selected,
    handle_delete_command,
    handle_edit_command,
    handle_plain_message,
    handle_transaction_command,
)

log = get_logger(__name__)
app = create_application()

TRANSACTION_COMMANDS = {
    '/expense': Transaction.TransactionType.EXPENSE,
    '/income': Transaction.TransactionType.INCOME,
}

CALLBACK_HANDLERS = {
    'cat': handle_category_selected,
    'acc': handle_account_selected,
}


def _send_reply(chat_id, text, reply_markup=None):
    async def _send():
        async with app.bot:
            await app.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    asyncio.run(_send())


def _send_result(chat_id, result):
    # Command handlers return either a plain string, or an (text, InlineKeyboardMarkup)
    # tuple when the next step is picking from buttons.
    if isinstance(result, tuple):
        text, markup = result
    else:
        text, markup = result, None

    _send_reply(chat_id, text, reply_markup=markup)


def _dispatch_command(message):
    first_word = message.text.split(maxsplit=1)[0]
    if not first_word.startswith('/'):
        result = handle_plain_message(message.chat_id, message.text)
        if result is not None:
            _send_result(message.chat_id, result)
        return

    command = first_word.split('@', 1)[0].lower()

    if command == '/start':
        _send_reply(message.chat_id, build_welcome_message())
        return

    if command == '/help':
        _send_reply(message.chat_id, build_help_message())
        return

    if command == '/transactions':
        _send_reply(message.chat_id, build_transaction_history_message())
        return

    if command == '/edit':
        _send_reply(message.chat_id, handle_edit_command(message.text))
        return

    if command == '/delete':
        _send_reply(message.chat_id, handle_delete_command(message.text))
        return

    transaction_type = TRANSACTION_COMMANDS.get(command)
    if not transaction_type:
        _send_reply(message.chat_id, f"❓ Unknown command '{command}'. Try /expense, /income, or /help.")
        return

    result = handle_transaction_command(message.chat_id, message.text, transaction_type, message.date)
    log.info(
        'Telegram transaction command processed',
        event='telegram_transaction_command_processed',
        command=command,
    )
    _send_result(message.chat_id, result)


def _answer_callback(callback_query, text, reply_markup=None):
    async def _respond():
        async with app.bot:
            await callback_query.answer()
            await callback_query.edit_message_text(text, reply_markup=reply_markup)

    asyncio.run(_respond())


def _dispatch_callback_query(callback_query):
    prefix, _, _ = callback_query.data.partition('|')
    handler = CALLBACK_HANDLERS.get(prefix)
    result = handler(callback_query.data) if handler else '❓ This action is no longer valid.'

    if isinstance(result, tuple):
        text, markup = result
    else:
        text, markup = result, None

    _answer_callback(callback_query, text, reply_markup=markup)

    log.info(
        'Telegram callback query processed',
        event='telegram_callback_query_processed',
        callback_type=prefix,
    )


# Create your views here.
@csrf_exempt
def webhook(request):
    if request.method != 'POST':
        log.warning(
            'Rejected non-POST request to Telegram webhook',
            event='telegram_webhook_method_not_allowed',
            method=request.method,
        )
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        update = Update.de_json(
            data = data,
            bot = app.bot,
        )

        log.info(
            'Telegram update received',
            event='telegram_update_received',
            update_id=update.update_id,
        )

        if update.message and update.message.text:
            _dispatch_command(update.message)
        elif update.callback_query:
            _dispatch_callback_query(update.callback_query)

        return JsonResponse({
            'status': 'received',
        }, status=200)
    except json.JSONDecodeError:
        log.warning(
            'Rejected Telegram webhook payload with invalid JSON',
            event='telegram_webhook_invalid_json',
        )
        return JsonResponse({'error': 'Bad Request'}, status=400)
    except (TypeError, ValueError):
        log.warning(
            'Rejected Telegram webhook payload with invalid update structure',
            event='telegram_webhook_invalid_update',
        )
        return JsonResponse({'error': 'Invalid Telegram update'}, status=400)