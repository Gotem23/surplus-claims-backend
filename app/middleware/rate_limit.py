import time
from collections import defaultdict, deque

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.errors import error_payload


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory sliding window rate limit.
    Good for single-instance / dev. For multi-instance, use Redis later.
    """

    def __init__(
        self,
        app,
        requests: int = 60,
        per_seconds: int = 60,
        path_prefixes: tuple[str, ...] = ("/claims",),
    ):
        super().__init__(app)
        self.requests = requests
        self.per_seconds = per_seconds
        self.path_prefixes = path_prefixes
        self.hits = defaultdict(deque)  # key -> deque[timestamps]

    def _client_key(self, request) -> str:
        # Prefer X-Forwarded-For if behind proxy, else client host.
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    async def dispatch(self, request, call_next):
        # Only apply to selected paths
        path = request.url.path
        if not any(path.startswith(p) for p in self.path_prefixes):
            return await call_next(request)

        now = time.time()
        window_start = now - self.per_seconds
        key = self._client_key(request)

        q = self.hits[key]
        # Drop old timestamps
        while q and q[0] < window_start:
            q.popleft()

        if len(q) >= self.requests:
            rid = getattr(request.state, "request_id", None)
            return JSONResponse(
                status_code=429,
                content=error_payload(
                    "rate_limited",
                    "Too many requests. Please slow down.",
                    details={"limit": self.requests, "window_seconds": self.per_seconds},
                    request_id=rid,
                ),
                headers={"Retry-After": str(self.per_seconds)},
            )

        q.append(now)
        return await call_next(request)
