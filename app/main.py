import logging
import os
import sys

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.env_loader import load_env

# Load the correct .env.* file BEFORE reading any env vars
load_env()

from app.core.config import settings  # noqa: E402
from app.errors import error_payload  # noqa: E402
from app.logging_filters import RedactApiKeyFilter  # noqa: E402
from app.middleware.access_log import AccessLogMiddleware  # noqa: E402
from app.middleware.body_size_limit import BodySizeLimitMiddleware  # noqa: E402
from app.middleware.rate_limit import RateLimitMiddleware  # noqa: E402
from app.middleware.remove_server_header import RemoveServerHeaderMiddleware  # noqa: E402
from app.middleware.request_id import RequestIdMiddleware  # noqa: E402
from app.routers.claims import router as claims_router  # noqa: E402
from app.routers.public import router as public_router  # noqa: E402

logger = logging.getLogger(__name__)

# -----------------------
# Environment + safety
# -----------------------
APP_ENV = os.getenv("ENV", "dev").strip().lower()
IS_PROD = APP_ENV in ("prod", "production")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DISABLE_RATE_LIMIT = os.getenv("DISABLE_RATE_LIMIT", "0") == "1"

# Block --reload in prod (reliable)
if IS_PROD and any(a == "--reload" or a.startswith("--reload") for a in sys.argv):
    raise RuntimeError("Auto-reload must not be enabled in production")

# DB environment safety
if IS_PROD and any(s in DATABASE_URL for s in ("_dev", "_test")):
    raise RuntimeError("Unsafe DATABASE_URL: production cannot use dev/test database")

if APP_ENV == "test" and "_test" not in DATABASE_URL:
    raise RuntimeError("Unsafe DATABASE_URL: test environment must use a *_test database")

# -----------------------
# Logging
# -----------------------
logger = logging.getLogger("uvicorn.error")

logging.getLogger("uvicorn").addFilter(RedactApiKeyFilter())
logging.getLogger("uvicorn.error").addFilter(RedactApiKeyFilter())
logging.getLogger("uvicorn.access").addFilter(RedactApiKeyFilter())

# -----------------------
# CORS
# -----------------------
cors_env = os.getenv("CORS_ORIGINS", "").strip()

if IS_PROD and not cors_env:
    raise RuntimeError("CORS_ORIGINS must be set in production (comma-separated origins)")

if not cors_env:
    CORS_ORIGINS = ["http://localhost:3000"] if not IS_PROD else []
else:
    CORS_ORIGINS = [o.strip() for o in cors_env.split(",") if o.strip()]

API_KEY_HDR = settings.API_KEY_HEADER

TRUSTED_PROXY_HOSTS = [
    h.strip()
    for h in os.getenv("TRUSTED_PROXY_HOSTS", "127.0.0.1").split(",")
    if h.strip()
]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        if IS_PROD:
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self' https: data: blob:; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; "
                "style-src 'self' 'unsafe-inline' https:; "
                "img-src 'self' data: https:; "
                "font-src 'self' data: https:; "
                "connect-src 'self' https:; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )

        # HSTS only when HTTPS (direct or via proxy header)
        if IS_PROD:
            forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
            is_https = (request.url.scheme == "https") or (forwarded_proto == "https")
            if is_https:
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


class CorsPreflightMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Only handle browser CORS preflight requests
        if request.method != "OPTIONS":
            return await call_next(request)

        origin = request.headers.get("origin")
        rid = getattr(request.state, "request_id", None)

        # Not a browser preflight
        if not origin:
            return PlainTextResponse("OK", status_code=200)

        # Enforce allowlist
        if origin not in CORS_ORIGINS:
            return JSONResponse(
                status_code=400,
                content=error_payload(
                    code="cors_error",
                    message="Disallowed CORS origin",
                    request_id=rid,
                    details={"origin": origin},
                ),
            )

        # Allowed preflight
        resp = PlainTextResponse("OK", status_code=200)
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = f"Content-Type, {API_KEY_HDR}"
        resp.headers["Access-Control-Max-Age"] = "600"
        return resp


app = FastAPI(
    title="Surplus Claims API",
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc",
    openapi_url=None if IS_PROD else "/openapi.json",
)



@app.get("/version")
def version():
    return {"service": "surplus-api"}


# -----------------------
# Middleware stack
# -----------------------
if IS_PROD:
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=TRUSTED_PROXY_HOSTS)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RemoveServerHeaderMiddleware)
app.add_middleware(BodySizeLimitMiddleware, max_bytes=1024 * 1024)
app.add_middleware(RequestIdMiddleware)

# IMPORTANT: handle OPTIONS preflight without creating a catch-all route
app.add_middleware(CorsPreflightMiddleware)

if not DISABLE_RATE_LIMIT:
    app.add_middleware(
        RateLimitMiddleware,
        requests=3,
        per_seconds=10,
        path_prefixes=("/claims",),
    )

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", API_KEY_HDR],
    )

app.add_middleware(AccessLogMiddleware)

# -----------------------
# Exception handlers
# -----------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    rid = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_payload(
            code="validation_error",
            message="Validation failed",
            details=exc.errors(),
            request_id=rid,
        ),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    rid = getattr(request.state, "request_id", None)

    if IS_PROD and exc.status_code >= 500:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code="internal_error", message="Internal Server Error", request_id=rid),
        )

    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", "http_error")
        message = exc.detail.get("message", "Request failed")
        details = exc.detail.get("details")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code, message, details, request_id=rid),
        )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload("http_error", str(exc.detail), request_id=rid),
    )


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    rid = getattr(request.state, "request_id", None)

    if IS_PROD and exc.status_code >= 500:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code="internal_error", message="Internal Server Error", request_id=rid),
        )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(code="http_error", message=str(exc.detail), request_id=rid),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", None)
    logger.exception("Unhandled error request_id=%s path=%s", rid, request.url.path)
    return JSONResponse(
        status_code=500,
        content=error_payload(code="internal_error", message="Internal Server Error", request_id=rid),
    )


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version="1.0.0",
        description="Surplus Claims API",
        routes=app.routes,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})
    schema["components"]["securitySchemes"]["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": API_KEY_HDR,
    }

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.on_event("startup")
async def on_startup():
    logger.info("Surplus Claims API starting up")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Surplus Claims API shutting down")


app.include_router(public_router)
app.include_router(claims_router)
 