# Personal-Finance-Tracker

A Personal Finance Manager that gives a complete picture of my financial health.

## What's built so far

- **Finance domain models** (`apps/finance/`) — `Transaction` (income/expense/transfer/settlement, linked to a `Category` and `Account`), `Category` (name, icon, color, active flag), and `Account` (savings/credit card/cash/UPI). Categories and accounts in use can't be deleted (`on_delete=PROTECT`).
- **Django Admin** — customized list views, search, filters, and date hierarchy for all three models.
- **Seed data** — `python manage.py seed_data` populates default categories and accounts idempotently.
- **Telegram bot webhook** (`apps/telegram_bot/`) — receives and validates Telegram updates via webhook (not polling) at `/telegram/webhook/`. It currently parses and acknowledges updates only; it does not yet create transactions from messages.
- **Structured observability** (`core/logging/`) — JSON-formatted logs across the app, with a per-request `X-Request-ID` (generated or propagated from an incoming header) attached to every log line via middleware.
- **Tests** — under the root-level `tests/` package, mirroring the source tree (`tests/core/logging/`, `tests/apps/...`).

Not yet built: turning Telegram messages into transactions, a dashboard, loan/credit-card tracking, shared-expense/reimbursement tracking, and AI-based spending analysis.

## Requirements to build and run

- Python 3.11+
- A `.env` file in the project root with:

  | Variable | Required | Description |
  |---|---|---|
  | `SECRET_KEY` | Yes | Django secret key. |
  | `DEBUG` | No (defaults to `False`) | `True`/`False`. |
  | `TELEGRAM_BOT_TOKEN` | Yes | Bot token from [@BotFather](https://t.me/BotFather). |

  `SECRET_KEY` and `TELEGRAM_BOT_TOKEN` are required — the app raises an error at startup if either is missing.

## Setup

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_data
python manage.py createsuperuser
python manage.py runserver
```

The app serves at `http://127.0.0.1:8000/` — admin at `/admin/`, Telegram webhook at `/telegram/webhook/`.

## Running tests

```bash
python manage.py test
```
