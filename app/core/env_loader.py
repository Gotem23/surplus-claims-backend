import os

from dotenv import load_dotenv


def load_env() -> None:
    # What the process is requesting (PowerShell $env:ENV)
    requested = os.getenv("ENV", "dev").strip().lower()

    # Choose the correct env file
    filename = {
        "prod": ".env.prod",
        "production": ".env.prod",
        "test": ".env.test",
        "dev": ".env.dev",
        "development": ".env.dev",
    }.get(requested, ".env.dev")

    # Load the selected file first, then optional shared defaults
    # override=False means existing process env vars win (PowerShell can override)
    load_dotenv(filename, override=False)
    load_dotenv(".env", override=False)

    # Verify the loaded file matches the requested environment
    loaded = os.getenv("ENV", "").strip().lower()
    if not loaded:
        raise RuntimeError(f"{filename} must define ENV={requested}")

    if loaded != requested:
        raise RuntimeError(f"ENV mismatch: process ENV={requested} but {filename} has ENV={loaded}")

    # Production required variables (fail fast)
    if requested in ("prod", "production"):
        required = ("DATABASE_URL", "API_KEY_HASHES", "CORS_ORIGINS")
        missing = [k for k in required if not os.getenv(k, "").strip()]
        if missing:
            raise RuntimeError(
                "Missing required env var(s) in production: " + ", ".join(missing)
            )
