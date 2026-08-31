import json, logging
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from .context import get_request_id
from typing import Any

from constants import IST_TIMEZONE_NAME, RESERVED_FIELDS

IST = ZoneInfo(IST_TIMEZONE_NAME)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

def _clean_file_path(pathname):
    path = Path(pathname)
    try:
        relative_path = path.relative_to(PROJECT_ROOT)
    except ValueError:
        return path.as_posix()

    # Site-packages code (e.g. Django's own logging) resolves to a noisy,
    # venv-specific path like 'env/lib/python3.11/site-packages/django/...'.
    # Trim everything up to and including 'site-packages' so it reads like
    # our own paths do: 'django/core/servers/basehttp.py' rather than that.
    parts = relative_path.parts
    if 'site-packages' in parts:
        relative_path = Path(*parts[parts.index('site-packages') + 1:])

    return relative_path.as_posix()

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=IST).replace(tzinfo=None).isoformat(timespec='milliseconds')
        relative_path = _clean_file_path(record.pathname)

        log_data = {
            'timestamp': timestamp,
            'level': record.levelname,
            'file': f'{relative_path}:{record.lineno}',
            'request_id': get_request_id(),
            'message': record.getMessage(),
        }

        context = getattr(record, 'context', {})
        log_data.update(context)

        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str, ensure_ascii=False)

class ApplicationLogger:
    '''
        Application-wide logging interface.

        Developers provide only:
            - message
            - optional contextual fields

        The logging infrastructure provides:
            - timestamp
            - level
            - file
            - line
            - request_id
    '''
    def __init__(self, logger_name: str) -> None:
        self._logger = logging.getLogger(logger_name)

    def debug(self, message: str, **context: Any) -> None:
        self._log(
            logging.DEBUG,
            message,
            context=context,
        )

    def info(self, message: str, **context: Any) -> None:
        self._log(
            logging.INFO,
            message,
            context=context,
        )

    def warning(self, message: str, **context: Any) -> None:
        self._log(
            logging.WARNING,
            message,
            context=context,
        )

    def error(self, message: str, *, exc_info: bool = False, **context: Any) -> None:
        self._log(
            logging.ERROR,
            message,
            context=context,
            exc_info=exc_info,
        )

    def critical(self, message: str, *, exc_info: bool = False, **context: Any) -> None:
        self._log(
            logging.CRITICAL,
            message,
            context=context,
            exc_info=exc_info,
        )

    def _log(self, level: int, message: str, context: dict[str, Any], *, exc_info: bool = False) -> None:
        for key in context:
            if key in RESERVED_FIELDS:
                raise ValueError(f'{key} is reserved logging field.')

        self._logger.log(level, message, extra={'context': context}, exc_info=exc_info, stacklevel=3)