import uuid

from fastapi.testclient import TestClient

from app.main import app


def test_create_soft_delete_hides_claim_and_writes_audit():
    client = TestClient(app)

    # Unique identity to avoid UNIQUE(state, county, case_number) collisions
    case_number = f"TEST-{uuid.uuid4()}"

    payload = {
        "state": "MI",
        "county": "Wayne",
        "case_number": case_number,
        "property_address": "123 Test St",
        "surplus_amount": 123.45,
        "status": "new",
        "notes": "pytest"
    }

    # 1) Create
    r = client.post("/claims", json=payload)
    assert r.status_code == 200, r.text
    claim = r.json()
    claim_id = claim["id"]
    assert claim["deleted_at"] is None

    # 2) Soft delete
    r = client.delete(f"/claims/{claim_id}")
    assert r.status_code == 200, r.text

    # 3) Fetch default (include_deleted=false) -> should be hidden (404)
    r = client.get(f"/claims/{claim_id}?include_deleted=false")
    assert r.status_code == 404, r.text

    # 4) Fetch include_deleted=true -> should exist and have deleted_at
    r = client.get(f"/claims/{claim_id}?include_deleted=true")
    assert r.status_code == 200, r.text
    deleted = r.json()
    assert deleted["deleted_at"] is not None

    # 5) Audit log should include delete of deleted_at
    r = client.get(f"/claims/{claim_id}/audit?limit=50&offset=0")
    assert r.status_code == 200, r.text
    logs = r.json()
    assert isinstance(logs, list)

    # Look for the delete audit record
    matches = [
        x for x in logs
        if x.get("action") == "delete" and x.get("field") == "deleted_at"
    ]
    assert len(matches) >= 1, f"Expected delete audit record, got: {logs}"
