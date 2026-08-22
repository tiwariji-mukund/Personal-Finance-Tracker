import asyncio

from django.core.management.base import BaseCommand

from apps.telegram_bot.bot import create_application
from apps.telegram_bot.commands import BOT_COMMANDS


class Command(BaseCommand):
    help = 'Registers the /expense and /income command menu with Telegram.'

    def handle(self, *args, **options):
        app = create_application()

        async def _set():
            async with app.bot:
                await app.bot.set_my_commands(BOT_COMMANDS)

        asyncio.run(_set())
        self.stdout.write(self.style.SUCCESS('Bot command menu registered with Telegram.'))
