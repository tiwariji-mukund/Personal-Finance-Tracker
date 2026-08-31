import asyncio
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from telegram import Update
from constants import (
    CALLBACK_PREFIX_ACCOUNT,
    CALLBACK_PREFIX_CATEGORY,
    CALLBACK_PREFIX_DESCRIPTION_SKIP,
    TRANSACTION_COMMANDS,
)
from core.logging import get_logger
from .bot import create_application
from .commands import (
    build_help_message,
    build_owed_message,
    build_transaction_history_message,
    build_welcome_message,
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

log = get_logger(__name__)
app = create_application()

CALLBACK_HANDLERS = {
    CALLBACK_PREFIX_CATEGORY: handle_category_selected,
    CALLBACK_PREFIX_ACCOUNT: handle_account_selected,
    CALLBACK_PREFIX_DESCRIPTION_SKIP: handle_description_skipped,
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
        _send_reply(message.chat_id, handle_edit_command(message.chat_id, message.text))
        return

    if command == '/delete':
        _send_reply(message.chat_id, handle_delete_command(message.chat_id, message.text))
        return

    if command == '/shared':
        _send_result(message.chat_id, handle_shared_command(message.text))
        return

    if command == '/settle':
        _send_result(message.chat_id, handle_settle_command(message.text))
        return

    if command == '/owed':
        _send_reply(message.chat_id, build_owed_message())
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
    result = handler(callback_query.data, callback_query.message.chat_id) if handler else '❓ This action is no longer valid.'

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
    except json.JSONDecodeError:
        log.warning(
            'Rejected Telegram webhook payload with invalid JSON',
            event='telegram_webhook_invalid_json',
        )
        return JsonResponse({'error': 'Bad Request'}, status=400)

    try:
        update = Update.de_json(data=data, bot=app.bot)
    except (TypeError, ValueError):
        log.warning(
            'Rejected Telegram webhook payload with invalid update structure',
            event='telegram_webhook_invalid_update',
        )
        return JsonResponse({'error': 'Invalid Telegram update'}, status=400)

    log.info(
        'Telegram update received',
        event='telegram_update_received',
        update_id=update.update_id,
    )

    try:
        if update.message and update.message.text:
            _dispatch_command(update.message)
        elif update.callback_query:
            _dispatch_callback_query(update.callback_query)
    except Exception:
        # A bug in our own dispatch logic is not "an invalid Telegram update" —
        # log it as the real error it is. Still acknowledge receipt (200) so
        # Telegram doesn't retry-storm a request that would fail the same way
        # every time.
        log.error(
            'Unhandled exception while processing Telegram update',
            event='telegram_dispatch_failed',
            update_id=update.update_id,
            exc_info=True,
        )

    return JsonResponse({'status': 'received'}, status=200)