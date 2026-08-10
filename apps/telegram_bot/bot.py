from telegram.ext import Application
from django.conf import settings
from core.logging import get_logger

log = get_logger(__name__)
def create_application() -> Application:
    app = Application.builder().token(
        settings.TELEGRAM_BOT_TOKEN
    ).build()
    log.info('Telegram bot application initialized.', event='telegram_bot_inititalized')
    return app