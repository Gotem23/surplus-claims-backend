from starlette.middleware.base import BaseHTTPMiddleware


class RemoveServerHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        # Uvicorn/ASGI servers may add this header; remove it for hardening.
        if "server" in response.headers:
            del response.headers["server"]
        if "Server" in response.headers:
            del response.headers["Server"]
        return response
