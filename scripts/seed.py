import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

ENV = os.getenv("ENV", "dev").strip().lower()
DB_URL = os.getenv("DATABASE_URL", "").strip()

if not DB_URL:
    raise RuntimeError("DATABASE_URL not set")

if ENV in ("prod", "production"):
    raise RuntimeError("Seeding is disabled in production")

if ENV not in ("dev", "test"):
    raise RuntimeError("Seeding is only allowed in dev or test")

if os.getenv("ALLOW_SEED", "0") != "1":
    raise RuntimeError("Seeding blocked. Set ALLOW_SEED=1 to run seeds.")



engine = create_engine(DB_URL, future=True)


def _get_allowed_status(conn) -> str:
    # Read the CHECK constraint definition and extract quoted literals
    row = conn.execute(
        text(
            """
            SELECT pg_get_constraintdef(c.oid) AS def
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            WHERE t.relname = 'surplus_claims'
              AND c.conname = 'ck_claim_status_valid'
              AND c.contype = 'c'
            """
        )
    ).mappings().first()

    if not row or not row.get("def"):
        # Fallback: safest possible default if constraint name changes
        return "new"

    definition = row["def"]  # e.g., CHECK ((status = ANY (ARRAY['NEW'::text,'PAID'::text])))
    # Extract single-quoted literals
    allowed = []
    in_quote = False
    buf = []
    for ch in definition:
        if ch == "'":
            if in_quote:
                allowed.append("".join(buf))
                buf = []
                in_quote = False
            else:
                in_quote = True
        elif in_quote:
            buf.append(ch)

    # Pick the first allowed literal if we found any
    if allowed:
        return allowed[0]

    return "new"


def seed() -> None:
    now = datetime.now(timezone.utc)

    with engine.begin() as conn:
        cols = conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'surplus_claims'
                ORDER BY ordinal_position
                """
            )
        ).scalars().all()

        if not cols:
            print("No public.surplus_claims table found. Nothing to seed.")
            return

        values: dict[str, object] = {}

        if "id" in cols:
            values["id"] = str(uuid.uuid4())
        if "created_at" in cols:
            values["created_at"] = now
        if "updated_at" in cols:
            values["updated_at"] = now

        # Determine a valid status from DB constraint
        valid_status = _get_allowed_status(conn)

        for c in cols:
            if c in ("id", "created_at", "updated_at", "deleted_at"):
                continue

            if c in ("surplus_amount", "amount", "claim_amount"):
                values[c] = 1234.56
                continue

            if c == "status":
                values[c] = valid_status
                continue

            if c == "state":
                values[c] = "MI"
                continue

            if c == "county":
                values[c] = "Oakland"
                continue

            if c == "case_number":
                values[c] = "CASE-0001"
                continue

            if c == "property_address":
                values[c] = "123 Main St"
                continue

            if c == "notes":
                values[c] = "seed"
                continue

            if c.endswith("_id"):
                continue

            values[c] = "x"

        col_list = ", ".join(values.keys())
        param_list = ", ".join(f":{k}" for k in values.keys())

        conn.execute(
            text(
                f"""
                INSERT INTO surplus_claims ({col_list})
                VALUES ({param_list})
                ON CONFLICT DO NOTHING
                """
            ),
            values,
        )



        print("Seeding complete.")
        print("Used status:", valid_status)
        print("Seeded columns:", list(values.keys()))


if __name__ == "__main__":
    seed()
