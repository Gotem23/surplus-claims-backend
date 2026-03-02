"""add api_keys table

Revision ID: e1a2b3c4d5f6
Revises: 3de2ccae4dd7
Create Date: 2026-03-02 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e1a2b3c4d5f6'
down_revision: str | Sequence[str] | None = '3de2ccae4dd7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create api_keys table if it doesn't exist (safe to run on production)."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name                    VARCHAR(120),
            key_hash                VARCHAR(255) NOT NULL,
            role                    VARCHAR(30)  NOT NULL,
            is_active               BOOLEAN      NOT NULL DEFAULT TRUE,
            created_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),
            revoked_at              TIMESTAMPTZ,
            tenant_id               UUID         NOT NULL,
            status                  TEXT         NOT NULL,
            expires_at              TIMESTAMPTZ,
            revoked_reason          TEXT,
            created_by_actor_type   TEXT,
            created_by_actor_id     TEXT,
            revoked_by_actor_type   TEXT,
            revoked_by_actor_id     TEXT,
            rotated_from_key_id     UUID REFERENCES api_keys(id) ON DELETE SET NULL,
            rotated_to_key_id       UUID REFERENCES api_keys(id) ON DELETE SET NULL,
            rotation_grace_ends_at  TIMESTAMPTZ,
            last_used_at            TIMESTAMPTZ,
            last_used_ip            INET,
            CONSTRAINT api_keys_status_check
                CHECK (status IN ('active', 'expiring', 'revoked', 'expired'))
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_api_keys_role
            ON api_keys (role)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_api_keys_is_active
            ON api_keys (is_active)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_api_keys_tenant_id
            ON api_keys (tenant_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_api_keys_expires_at
            ON api_keys (expires_at)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_api_keys_rotated_from_key_id
            ON api_keys (rotated_from_key_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_api_keys_rotated_to_key_id
            ON api_keys (rotated_to_key_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_api_keys_tenant_status
            ON api_keys (tenant_id, status)
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_api_keys_tenant_name_active
            ON api_keys (tenant_id, name)
            WHERE is_active = TRUE
    """)


def downgrade() -> None:
    """Drop api_keys table."""
    op.execute("DROP TABLE IF EXISTS api_keys")
