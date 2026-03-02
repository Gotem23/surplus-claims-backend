import os

os.environ["DISABLE_RATE_LIMIT"] = "1"

import bcrypt
import pytest
from sqlalchemy import create_engine, text

TEST_API_KEY = "test-api-key-123"
# Fixed UUID so ON CONFLICT DO NOTHING is idempotent across reruns
TEST_KEY_ID = "00000000-0000-0000-0000-000000000001"


def _get_test_db_url() -> str:
    # Prefer DATABASE_URL from environment (set by CI); fall back to .env.dev for local runs
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return url
    from dotenv import dotenv_values
    env = dotenv_values(".env.dev")
    return env.get("DATABASE_URL", "")


@pytest.fixture(scope="session", autouse=True)
def _test_db_api_key():
    """Insert a test admin API key at session start; remove on teardown."""
    db_url = _get_test_db_url()
    if not db_url:
        pytest.skip("DATABASE_URL not found in .env.dev")

    engine = create_engine(db_url, pool_pre_ping=True)

    key_hash = bcrypt.hashpw(TEST_API_KEY.encode(), bcrypt.gensalt()).decode()

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO api_keys (id, name, key_hash, role, is_active, status, tenant_id, created_at)
                VALUES (:id, :name, :hash, 'admin', true, 'active',
                        '00000000-0000-0000-0000-000000000001'::uuid, NOW())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": TEST_KEY_ID, "name": "pytest-test-key", "hash": key_hash},
        )

    os.environ["API_KEY_HEADER"] = "X-API-Key"

    yield

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM api_keys WHERE id = :id"), {"id": TEST_KEY_ID})

    engine.dispose()


@pytest.fixture()
def api_key_header():
    return {"X-API-Key": TEST_API_KEY}
