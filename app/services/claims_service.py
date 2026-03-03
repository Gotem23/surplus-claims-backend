from typing import Any

from fastapi import HTTPException

from app import schemas

# ---------------------------------------------------------------------------
# State machine definition
# ---------------------------------------------------------------------------
# Each key maps to an ordered list of (target_status, label, description).
# Index 0 is always the "natural" (advance) target.
# "closed" is absent as a key — it is the terminal state.

TRANSITIONS: dict[str, list[tuple[str, str, str]]] = {
    "new": [
        (
            "researching",
            "Begin Research",
            "Start actively investigating the claim — pull county records, verify "
            "surplus amount, and identify the rightful claimant.",
        ),
        (
            "closed",
            "Close Claim",
            "Mark this claim as closed without further action. Use only if the claim "
            "is invalid, a duplicate, or withdrawn.",
        ),
    ],
    "researching": [
        (
            "contacted",
            "Mark as Contacted",
            "Record that the claimant has been reached and initial contact was successful.",
        ),
        (
            "closed",
            "Close Claim",
            "Mark this claim as closed without further action.",
        ),
    ],
    "contacted": [
        (
            "paperwork_ready",
            "Paperwork Ready",
            "All required documents have been collected and the claim file is ready "
            "to submit to the county.",
        ),
        (
            "researching",
            "Return to Research",
            "Contact attempt failed or new information requires additional investigation.",
        ),
        (
            "closed",
            "Close Claim",
            "Mark this claim as closed without further action.",
        ),
    ],
    "paperwork_ready": [
        (
            "filed",
            "File Claim",
            "Submit the completed claim package to the appropriate county office or court.",
        ),
        (
            "contacted",
            "Return to Contacted",
            "Paperwork is incomplete or needs revision; return to the contacted stage.",
        ),
        (
            "closed",
            "Close Claim",
            "Mark this claim as closed without further action.",
        ),
    ],
    "filed": [
        (
            "approved",
            "Mark Approved",
            "The county has reviewed and approved the claim for disbursement.",
        ),
        (
            "researching",
            "Return to Research",
            "The filed claim was rejected or requires additional supporting documentation.",
        ),
        (
            "closed",
            "Close Claim",
            "Mark this claim as closed without further action.",
        ),
    ],
    "approved": [
        (
            "paid",
            "Mark as Paid",
            "Funds have been disbursed to the claimant. Claim is now fully resolved "
            "pending final closure.",
        ),
        (
            "closed",
            "Close Claim",
            "Mark this claim as closed without further action.",
        ),
    ],
    "paid": [
        (
            "closed",
            "Close Claim",
            "All funds disbursed and records reconciled. Archive this claim.",
        ),
    ],
    "closed": [],  # terminal — no valid transitions
}


class ClaimsService:
    def __init__(self, crud_module):
        self.crud = crud_module

    # ------------------------------------------------------------------
    # Existing method — unchanged
    # ------------------------------------------------------------------

    def list_claims(
        self,
        db,
        limit: int,
        offset: int,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Returns (items, total)."""
        filters = filters or {}
        items = self.crud.list_claims(db, limit=limit, offset=offset, **filters)
        total = self.crud.count_claims(db, **filters)
        return items, total

    # ------------------------------------------------------------------
    # State-machine helpers
    # ------------------------------------------------------------------

    def get_valid_transitions(self, status: str) -> list[tuple[str, str, str]]:
        """Return ordered (target_status, label, description) tuples for a status.

        Returns an empty list for 'closed' or any unrecognised status.
        Never raises — unknown statuses are treated as terminal.
        """
        return TRANSITIONS.get(status, [])

    def get_next_steps_response(self, db, claim_id: str) -> schemas.NextStepsResponse:
        """Load the claim and build a NextStepsResponse.

        Raises:
            HTTPException 404 — claim does not exist at all
            HTTPException 410 — claim is soft-deleted
        """
        claim = self.crud.get_claim_by_id(db, claim_id, include_deleted=True)
        if claim is None:
            raise HTTPException(status_code=404, detail="Claim not found")
        if claim.deleted_at is not None:
            raise HTTPException(status_code=410, detail="Claim has been deleted")

        current = str(claim.status)
        transitions = self.get_valid_transitions(current)

        options = [
            schemas.TransitionOption(
                status=schemas.ClaimStatus(target),
                label=label,
                description=desc,
            )
            for target, label, desc in transitions
        ]

        natural_next: schemas.ClaimStatus | None = None
        if transitions:
            natural_next = schemas.ClaimStatus(transitions[0][0])

        return schemas.NextStepsResponse(
            claim_id=claim.id,
            current_status=schemas.ClaimStatus(current),
            can_advance=len(transitions) > 0,
            natural_next=natural_next,
            valid_transitions=options,
        )

    def advance_claim(self, db, claim_id: str):
        """Advance the claim to the first (natural) next status.

        Flushes the status update and audit log but does NOT commit.
        The caller (router) owns commit() and refresh().

        Raises:
            HTTPException 404 — claim does not exist
            HTTPException 409 — claim is already at terminal state
            HTTPException 410 — claim is soft-deleted
        """
        claim = self.crud.get_claim_by_id(db, claim_id, include_deleted=True)
        if claim is None:
            raise HTTPException(status_code=404, detail="Claim not found")
        if claim.deleted_at is not None:
            raise HTTPException(status_code=410, detail="Claim has been deleted")

        current = str(claim.status)
        transitions = self.get_valid_transitions(current)

        if not transitions:
            raise HTTPException(
                status_code=409,
                detail=f"Claim is already at terminal state '{current}' and cannot be advanced",
            )

        new_status = transitions[0][0]

        updated = self.crud.update_claim(
            db, claim_id, schemas.SurplusClaimUpdate(status=schemas.ClaimStatus(new_status))
        )

        self.crud.create_audit_log(
            db=db,
            claim_id=claim_id,
            action="update",
            field="status",
            old_value=current,
            new_value=new_status,
        )

        return updated
