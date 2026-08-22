# Personal Finance Tracker

A personal finance manager built with Django that gives a complete picture of your financial health — record income and expenses, organize them by category and account, and manage everything through the Django admin or a Telegram bot.

## Features

- **Transactions** — track income, expenses, transfers, and settlements, each linked to a category and an account.
- **Categories & Accounts** — organize spending by category (with icon and color) and by account (savings, credit card, cash, UPI).
- **Telegram bot** — a webhook-based Telegram integration for interacting with the tracker from chat.
- **Structured logging** — JSON-formatted application logs with request-ID tracing across every request.
- **Admin dashboard** — manage all data through a customized Django admin interface.

## Tech Stack

- **Backend:** Django (Python)
- **Database:** SQLite
- **Bot:** [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) (webhook mode)

## Prerequisites

- Python 3.11+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Installation

```bash
git clone https://github.com/tiwariji-mukund/Personal-Finance-Tracker.git
cd Personal-Finance-Tracker

python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root:

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Django secret key |
| `DEBUG` | No (default: `False`) | `True` / `False` |
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from BotFather |

## Usage

```bash
python manage.py migrate
python manage.py seed_data       # loads default categories and accounts
python manage.py createsuperuser
python manage.py runserver
```

The app runs at `http://127.0.0.1:8000/`:

- Admin panel: `/admin/`
- Telegram webhook: `/telegram/webhook/`

## Running Tests

```bash
python manage.py test
```
