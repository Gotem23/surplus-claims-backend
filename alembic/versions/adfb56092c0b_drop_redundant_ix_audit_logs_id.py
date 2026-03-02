"""drop redundant ix_audit_logs_id

Revision ID: adfb56092c0b
Revises: 3de2ccae4dd7
Create Date: 2026-01-07 07:29:17.743000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'adfb56092c0b'
down_revision: str | Sequence[str] | None = '3de2ccae4dd7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade():
    op.drop_index("ix_audit_logs_id", table_name="audit_logs")


def downgrade():
    op.create_index(
        "ix_audit_logs_id",
        "audit_logs",
        ["id"],
        unique=False,
    )