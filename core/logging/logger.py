import json, logging
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from .context import get_request_id
from typing import Any

IST = ZoneInfo('Asia/Kolkata')
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESERVED_FIELDS = {
    'timestamp',
    'level',
    'file',
    'request_id',
    'message',
}

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=IST).replace(tzinfo=None).isoformat(timespec='milliseconds')
        file_path = Path(record.pathname)
        try:
            relative_path = file_path.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            relative_path = file_path

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