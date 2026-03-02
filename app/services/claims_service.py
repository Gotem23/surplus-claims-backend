# app/services/claims_service.py

from typing import Any

# For now this is just a skeleton.
# Next steps will wire this into your existing crud functions.


class ClaimsService:
    def __init__(self, crud_module):
        self.crud = crud_module

    def list_claims(
        self,
        db,
        limit: int,
        offset: int,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Returns (items, total)
        """
        filters = filters or {}
        items = self.crud.list_claims(db, limit=limit, offset=offset, **filters)
        total = self.crud.count_claims(db, **filters)
        return items, total
