import json
import logging
import sys
import uuid
from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from core.logging.context import reset_request_id, set_request_id
from core.logging.logger import JsonFormatter, PROJECT_ROOT


def make_record(lineno, msg='test message', context=None, exc_info=None, pathname=None):
    pathname = pathname or str(PROJECT_ROOT / 'apps' / 'finance' / 'models.py')
    record = logging.LogRecord(
        name='test',
        level=logging.INFO,
        pathname=pathname,
        lineno=lineno,
        msg=msg,
        args=(),
        exc_info=exc_info,
    )
    record.context = context or {}
    return record


class JsonFormatterTests(SimpleTestCase):
    def setUp(self):
        self.formatter = JsonFormatter()

    def test_mandatory_fields_are_present(self):
        token = set_request_id('req-123')
        try:
            data = json.loads(self.formatter.format(make_record(42, msg='hello world')))
        finally:
            reset_request_id(token)

        self.assertEqual(data['level'], 'INFO')
        self.assertEqual(data['message'], 'hello world')
        self.assertEqual(data['request_id'], 'req-123')
        self.assertEqual(data['file'], 'apps/finance/models.py:42')
        self.assertIn('timestamp', data)

    def test_site_packages_paths_are_trimmed_to_the_package_name(self):
        pathname = str(PROJECT_ROOT / 'env' / 'lib' / 'python3.11' / 'site-packages' / 'django' / 'core' / 'servers' / 'basehttp.py')
        data = json.loads(self.formatter.format(make_record(213, pathname=pathname)))

        self.assertEqual(data['file'], 'django/core/servers/basehttp.py:213')

    def test_request_id_defaults_to_a_generated_uuid4_when_unset(self):
        data = json.loads(self.formatter.format(make_record(1)))
        self.assertEqual(uuid.UUID(data['request_id']).version, 4)

    def test_timestamp_is_in_ist_with_millisecond_precision(self):
        record = make_record(1)
        record.created = 1700000000.123456

        data = json.loads(self.formatter.format(record))

        parsed = datetime.strptime(data['timestamp'], '%Y-%m-%dT%H:%M:%S.%f')
        expected = datetime.fromtimestamp(record.created, tz=timezone.utc).replace(tzinfo=None) + timedelta(hours=5, minutes=30)
        expected = expected.replace(microsecond=(expected.microsecond // 1000) * 1000)  # isoformat truncates to milliseconds
        self.assertEqual(parsed, expected)

    def test_context_fields_are_flattened_into_top_level_json(self):
        data = json.loads(self.formatter.format(make_record(1, context={'event': 'x', 'foo': 'bar'})))

        self.assertEqual(data['event'], 'x')
        self.assertEqual(data['foo'], 'bar')

    def test_exception_is_included_when_exc_info_present(self):
        try:
            raise ValueError('boom')
        except ValueError:
            record = make_record(1, exc_info=sys.exc_info())

        data = json.loads(self.formatter.format(record))
        self.assertIn('boom', data['exception'])
