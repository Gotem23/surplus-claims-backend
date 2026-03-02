import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("app.access")


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            rid = getattr(request.state, "request_id", None)

            # IMPORTANT: Do NOT log headers (avoids leaking secrets)
            # Log only minimal metadata
            status_code = getattr(response, "status_code", 500)
            logger.info(
                "access method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
                rid,
            )
