from telegram.ext import Application
from telegram.request import HTTPXRequest
from django.conf import settings
from core.logging import get_logger

log = get_logger(__name__)

def _build_request() -> HTTPXRequest:
    # Behind a TLS-inspecting corporate proxy (e.g. Netskope), the proxy's CA
    # isn't in certifi's bundle, so httpx's default verification fails even
    # though the system CA bundle already trusts it. TELEGRAM_CA_BUNDLE lets
    # that system bundle be used explicitly; unset preserves normal secure
    # (certifi-based) verification.
    httpx_kwargs = {'verify': settings.TELEGRAM_CA_BUNDLE} if settings.TELEGRAM_CA_BUNDLE else {}
    return HTTPXRequest(httpx_kwargs=httpx_kwargs)

def create_application() -> Application:
    app = Application.builder().token(
        settings.TELEGRAM_BOT_TOKEN
    ).request(_build_request()).build()
    log.info(
        'Telegram bot application initialized.',
        event='telegram_bot_inititalized',
        ca_bundle_configured=bool(settings.TELEGRAM_CA_BUNDLE),
    )
    return app