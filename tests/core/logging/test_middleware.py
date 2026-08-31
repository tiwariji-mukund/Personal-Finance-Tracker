import uuid

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from constants import REQUEST_ID_HEADER

from core.logging.context import get_request_id
from core.logging.middleware import RequestIDMiddleware


class RequestIDMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _middleware(self, seen):
        def get_response(request):
            seen.append(get_request_id())
            return HttpResponse()
        return RequestIDMiddleware(get_response)

    def test_incoming_request_id_is_reused(self):
        seen = []
        request = self.factory.get('/', HTTP_X_REQUEST_ID='incoming-id')

        response = self._middleware(seen)(request)

        self.assertEqual(response[REQUEST_ID_HEADER], 'incoming-id')
        self.assertEqual(seen, ['incoming-id'])

    def test_missing_request_id_generates_uuid4(self):
        seen = []
        request = self.factory.get('/')

        response = self._middleware(seen)(request)

        generated = response[REQUEST_ID_HEADER]
        self.assertEqual(uuid.UUID(generated).version, 4)
        self.assertEqual(seen, [generated])

    def test_context_is_reset_after_request(self):
        request = self.factory.get('/', HTTP_X_REQUEST_ID='scoped-id')

        self._middleware([])(request)

        self.assertNotEqual(get_request_id(), 'scoped-id')
