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

## Conventions

- **All constants live in the root-level `constants.py`.** Anything that would otherwise be a hardcoded/magic value shared across the app (limits, thresholds, header names, default seed data, bot command tables, test fixture values like a dummy chat id) belongs there, imported by both application code and test files — never redefine or re-hardcode the same value locally. `constants.py` deliberately has **no Django/app imports**, since it's imported by `config/settings.py` before Django's app registry exists; where a constant conceptually belongs to a model (e.g. transaction type identifiers), it's expressed as a plain string literal there rather than importing the model, matching the value Django's own migrations already freeze independently.

## Architecture

- **`apps/finance/`** — the domain app: `Category`, `Account`, `Transaction` models (all extend `BaseModel` in `models.py`, which just adds `created_at`/`updated_at`). `Transaction.account`/`category` use `on_delete=PROTECT`, so accounts/categories in use cannot be deleted. `services.py` is the business-logic layer (validation, category/account resolution, transaction CRUD) used by both the admin and the Telegram bot — Telegram-specific code should call into `services.py` rather than touching models directly. Default seed data (`DEFAULT_CATEGORIES`, `DEFAULT_ACCOUNTS`) lives in the root `constants.py` and is loaded by the `seed_data` management command.
- **`apps/telegram_bot/`** — integrates `python-telegram-bot`. `bot.py` builds a module-level `telegram.ext.Application` singleton (`create_application()`), which `views.py` instantiates once at import time and reuses across requests. `views.webhook` (POST-only, CSRF-exempt) is Telegram's webhook target at `/telegram/webhook/`, handling both `message` and `callback_query` (inline button tap) updates. `commands.py` holds the actual command logic: `/expense`, `/income` (typed, amount-only-with-category-picker, or bare-with-conversational-amount-prompt), `/transactions`, `/edit`, `/delete`, `/help`, `/start`. Any Bot API call must be wrapped in `async with app.bot:` (see `_send_reply`/`_answer_callback` in `views.py`) — skipping it works on a fresh process but raises `RuntimeError: This HTTPXRequest is not initialized!` on the next call once another properly-wrapped call has already shut the client down.
- **`core/logging/`** — structured JSON logging used in place of Django's default logging, imported as `from core.logging import get_logger`. `get_logger(__name__)` returns an `ApplicationLogger` with `.info/.warning/.error/.critical(message, **context)` methods; context kwargs become extra fields in the JSON log line. `RequestIDMiddleware` (registered first in `MIDDLEWARE`) generates/propagates an `X-Request-ID` header per request via a contextvar (`core/logging/context.py`) so every log line within a request can be correlated. `config/settings.py`'s `LOGGING` dict wires `core.logging.logger.JsonFormatter` to a console handler at root level (and for the `django` logger, with `propagate: False` to avoid double logging; `httpx`'s own logger is silenced to `WARNING` since it logs the Telegram bot token embedded in request URLs at `INFO`), so all logging — Django's own and app code — prints as JSON.
- **`config/`** — standard Django project package. `config/env.py` is the only settings access point for environment variables (`get_env`, `get_bool`); don't call `os.getenv` directly elsewhere. `TIME_ZONE` is `constants.IST_TIMEZONE_NAME` (`Asia/Kolkata`) and `core/logging/logger.py` formats timestamps in that same zone explicitly, independent of `USE_TZ`.
