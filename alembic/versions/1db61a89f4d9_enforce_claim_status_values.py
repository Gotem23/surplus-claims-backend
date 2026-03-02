"""enforce claim status values

Revision ID: 1db61a89f4d9
Revises: 09fbfe4384ed
Create Date: 2026-01-04 23:21:10.554981
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1db61a89f4d9"
down_revision: str | Sequence[str] | None = "09fbfe4384ed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_claim_status_valid",
        "surplus_claims",
        "status IN ('new','researching','contacted','paperwork_ready','filed','approved','paid','closed')",
    )


def downgrade() -> None:
    op.execute("ALTER TABLE surplus_claims DROP CONSTRAINT IF EXISTS ck_claim_status_valid;")
