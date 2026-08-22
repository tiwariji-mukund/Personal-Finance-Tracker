# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Django-based personal finance tracker. Transactions are ingested via a Telegram bot webhook; a Django admin site is the primary interface for viewing/managing data. No frontend templates or REST API exist yet — `apps/finance/views.py` and `apps/finance/urls.py` are empty stubs.

## Setup & commands

Requires a `.env` file in the repo root (not checked in) with at least:
```
SECRET_KEY=...
DEBUG=True
TELEGRAM_BOT_TOKEN=...
```
`config/env.py` raises `ValueError` at import time if `SECRET_KEY` or `TELEGRAM_BOT_TOKEN` is missing — the app will not boot without them.

```bash
pip install -r requirements.txt

python manage.py migrate              # sqlite db.sqlite3, created in repo root
python manage.py seed_data            # seeds default Categories and Accounts (idempotent, uses get_or_create)
python manage.py createsuperuser
python manage.py runserver
```

All tests live under the root-level `tests/` package, mirroring the source tree (`tests/apps/finance/`, `tests/apps/telegram_bot/`, `tests/core/logging/`) rather than a `tests.py` per app/module. Run the whole suite with `python manage.py test`, or scope it with `python manage.py test tests.core.logging`.

## Architecture

- **`apps/finance/`** — the domain app: `Category`, `Account`, `Transaction` models (all extend `BaseModel` in `models.py`, which just adds `created_at`/`updated_at`). `Transaction.account`/`category` use `on_delete=PROTECT`, so accounts/categories in use cannot be deleted. Default seed data lives in `apps/finance/constants/` and is loaded by the `seed_data` management command — add new default categories/accounts there rather than via the admin or a migration.
- **`apps/telegram_bot/`** — integrates `python-telegram-bot`. `bot.py` builds a module-level `telegram.ext.Application` singleton (`create_application()`), which `views.py` instantiates once at import time and reuses across requests. `views.webhook` (POST-only, CSRF-exempt) is Telegram's webhook target at `/telegram/webhook/`; it currently only parses and acknowledges updates — it does not yet dispatch them to handlers or create `Transaction` rows. Bot handlers/parsing logic for turning Telegram messages into transactions belongs here.
- **`core/logging/`** — structured JSON logging used in place of Django's default logging, imported as `from core.logging import get_logger`. `get_logger(__name__)` returns an `ApplicationLogger` with `.info/.warning/.error/.critical(message, **context)` methods; context kwargs become extra fields in the JSON log line. `RequestIDMiddleware` (registered first in `MIDDLEWARE`) generates/propagates an `X-Request-ID` header per request via a contextvar (`core/logging/context.py`) so every log line within a request can be correlated. `config/settings.py`'s `LOGGING` dict wires `core.logging.logger.JsonFormatter` to a console handler at root level (and for the `django` logger, with `propagate: False` to avoid double logging), so all logging — Django's own and app code — prints as JSON.
- **`config/`** — standard Django project package. `config/env.py` is the only settings access point for environment variables (`get_env`, `get_bool`); don't call `os.getenv` directly elsewhere. `TIME_ZONE` is `Asia/Kolkata` and `core/logging/logger.py` formats timestamps in IST explicitly, independent of `USE_TZ`.
