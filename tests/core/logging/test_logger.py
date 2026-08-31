from django.test import SimpleTestCase

from constants import RESERVED_FIELDS

from core.logging import get_logger


class ReservedFieldTests(SimpleTestCase):
    def setUp(self):
        self.logger = get_logger('core.logging.tests')

    def test_reserved_fields_raise(self):
        # 'message' collides with info()'s own positional argument, so Python
        # itself blocks that override before it reaches our check.
        for field in RESERVED_FIELDS - {'message'}:
            with self.assertRaises(ValueError):
                self.logger.info('message', **{field: 'value'})

    def test_non_reserved_fields_do_not_raise(self):
        self.logger.info('message', event='ok', foo='bar')
