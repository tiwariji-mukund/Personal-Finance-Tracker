from django.http import HttpRequest, HttpResponse
from .context import generate_request_id, reset_request_id, set_request_id
from . import get_logger

logger = get_logger(__name__)

class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(
        self,
        request: HttpRequest,
    ) -> HttpResponse:
        request_id = request.headers.get("X-Request-ID")

        if not request_id:
            request_id = generate_request_id()

        request.request_id = request_id
        token = set_request_id(request_id)

        try:
            response = self.get_response(request)

            response["X-Request-ID"] = request_id

            return response

        except Exception:
            logger.error(
                "Unhandled exception while processing request",
                event="request_processing_failed",
                method=request.method,
                path=request.path,
                exc_info=True,
            )
            raise

        finally:
            reset_request_id(token)