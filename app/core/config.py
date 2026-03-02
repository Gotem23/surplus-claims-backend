import os
from dataclasses import dataclass

# Environment
APP_ENV = os.getenv("ENV", "dev").strip().lower()
IS_PROD = APP_ENV in ("prod", "production")


def require_env(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


# Enforce required secrets in production
if IS_PROD:
    require_env("DATABASE_URL")
    require_env("API_KEY_HASHES")
    require_env("API_KEY_HEADER")


@dataclass(frozen=True)
class Settings:
    APP_ENV: str
    DATABASE_URL: str | None
    API_KEY_HEADER: str
    API_KEY_HASHES: list[str]
    CORS_ORIGINS: str


def get_settings() -> Settings:
    header = os.getenv("API_KEY_HEADER", "X-API-Key")

    raw_hashes = os.getenv("API_KEY_HASHES", "")
    hashes: list[str] = []

    for part in raw_hashes.split(","):
        h = part.strip().strip('"').strip("'")
        if h:
            hashes.append(h)

    return Settings(
        APP_ENV=APP_ENV,
        DATABASE_URL=os.getenv("DATABASE_URL"),
        API_KEY_HEADER=header,
        API_KEY_HASHES=hashes,
        CORS_ORIGINS=os.getenv("CORS_ORIGINS", ""),
    )


settings = get_settings()
