import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from telegram import Update
from core.logging import get_logger
from .bot import create_application

log = get_logger(__name__)
app = create_application()

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