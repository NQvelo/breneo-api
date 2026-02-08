"""
Log full traceback for any unhandled exception to the console.
Add to MIDDLEWARE (first in list) to see why a request returns 500.
"""
import logging
import traceback

logger = logging.getLogger(__name__)


class LogExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        logger.exception(
            "Unhandled exception: %s\n%s",
            exception,
            traceback.format_exc(),
        )
        return None  # let Django handle the response (500 or debug page)
