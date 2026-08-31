from io import StringIO
from unittest.mock import AsyncMock, patch

from django.core.management import call_command
from django.test import SimpleTestCase

from constants import BOT_COMMANDS

from apps.telegram_bot.views import app


class SetBotCommandsTests(SimpleTestCase):
    def test_registers_bot_commands_with_telegram(self):
        with patch.object(type(app.bot), '__aenter__', new=AsyncMock(return_value=app.bot)), \
                patch.object(type(app.bot), '__aexit__', new=AsyncMock(return_value=False)), \
                patch.object(type(app.bot), 'set_my_commands', new=AsyncMock()) as mock_set_commands:
            call_command('set_bot_commands', stdout=StringIO())

        mock_set_commands.assert_called_once_with(BOT_COMMANDS)
