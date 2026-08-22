import asyncio
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from telegram import Update
from apps.finance.models import Transaction
from core.logging import get_logger
from .bot import create_application
from .commands import build_help_message, build_welcome_message, handle_transaction_command

log = get_logger(__name__)
app = create_application()

TRANSACTION_COMMANDS = {
    '/expense': Transaction.TransactionType.EXPENSE,
    '/income': Transaction.TransactionType.INCOME,
}


def _send_reply(chat_id, text):
    async def _send():
        async with app.bot:
            await app.bot.send_message(chat_id=chat_id, text=text)

    asyncio.run(_send())


def _dispatch_command(message):
    first_word = message.text.split(maxsplit=1)[0]
    if not first_word.startswith('/'):
        return

    command = first_word.split('@', 1)[0].lower()

    if command == '/start':
        _send_reply(message.chat_id, build_welcome_message())
        return

    if command == '/help':
        _send_reply(message.chat_id, build_help_message())
        return

    transaction_type = TRANSACTION_COMMANDS.get(command)
    if not transaction_type:
        _send_reply(message.chat_id, f"❓ Unknown command '{command}'. Try /expense, /income, or /help.")
        return

    reply = handle_transaction_command(message.text, transaction_type, message.date)
    log.info(
        'Telegram transaction command processed',
        event='telegram_transaction_command_processed',
        command=command,
    )
    _send_reply(message.chat_id, reply)


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