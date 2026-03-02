from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.errors import error_payload


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int = 1024 * 1024):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request, call_next):
        rid = getattr(request.state, "request_id", None)

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content=error_payload(
                            code="payload_too_large",
                            message="Request body too large",
                            details={"max_bytes": self.max_bytes},
                            request_id=rid,
                        ),
                    )
            except ValueError:
                # If content-length is malformed, fall through and let FastAPI handle it
                pass

        return await call_next(request)
