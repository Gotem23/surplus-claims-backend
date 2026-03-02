from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.errors import error_payload


class CORSErrorEnvelopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # CORSMiddleware returns plain-text 400s like:
        # "Disallowed CORS origin", "Disallowed CORS method"
        if response.status_code == 400 and getattr(response, "media_type", "") == "text/plain":
            try:
                body = response.body.decode("utf-8").strip()
            except Exception:
                body = ""

            if body.lower().startswith("disallowed cors"):
                rid = getattr(request.state, "request_id", None)
                return JSONResponse(
                    status_code=400,
                    content=error_payload(
                        code="cors_error",
                        message=body,
                        request_id=rid,
                    ),
                    headers=dict(response.headers),
                )

        return response
