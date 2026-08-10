import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from telegram import Update
from .bot import create_application

app = create_application()

# Create your views here.
@csrf_exempt
def webhook(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        update = Update.de_json(
            data = data,
            bot = app.bot,
        )

        return JsonResponse({
            'status': 'received',
        }, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Bad Request'}, status=400)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid Telegram update'}, status=400)