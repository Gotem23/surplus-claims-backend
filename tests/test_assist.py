import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def new_claim(client, api_key_header):
    """Create a fresh claim in 'new' status; soft-delete on teardown."""
    payload = {
        "state": "TX",
        "county": f"Travis-{uuid.uuid4()}",
        "case_number": f"ASSIST-{uuid.uuid4()}",
        "property_address": "456 Assist Ave",
        "surplus_amount": 500.00,
        "status": "new",
        "notes": "pytest assist test",
    }
    r = client.post("/claims", json=payload, headers=api_key_header)
    assert r.status_code == 200, r.text
    claim = r.json()
    yield claim
    client.delete(f"/claims/{claim['id']}", headers=api_key_header)


class TestNextSteps:
    def test_new_claim_has_two_transitions(self, client, api_key_header, new_claim):
        r = client.get(
            f"/assist/claims/{new_claim['id']}/next-steps",
            headers=api_key_header,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["current_status"] == "new"
        assert body["can_advance"] is True
        assert body["natural_next"] == "researching"
        statuses = [t["status"] for t in body["valid_transitions"]]
        assert statuses == ["researching", "closed"]

    def test_404_for_nonexistent_claim(self, client, api_key_header):
        r = client.get(
            f"/assist/claims/{uuid.uuid4()}/next-steps",
            headers=api_key_header,
        )
        assert r.status_code == 404

    def test_410_for_deleted_claim(self, client, api_key_header, new_claim):
        claim_id = new_claim["id"]
        client.delete(f"/claims/{claim_id}", headers=api_key_header)
        r = client.get(
            f"/assist/claims/{claim_id}/next-steps",
            headers=api_key_header,
        )
        assert r.status_code == 410

    def test_admin_key_satisfies_read_only_set(self, client, api_key_header, new_claim):
        r = client.get(
            f"/assist/claims/{new_claim['id']}/next-steps",
            headers=api_key_header,
        )
        assert r.status_code == 200


class TestAdvanceClaim:
    def test_advance_new_to_researching(self, client, api_key_header, new_claim):
        r = client.post(
            f"/assist/claims/{new_claim['id']}/advance",
            headers=api_key_header,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "researching"

    def test_advance_creates_audit_log(self, client, api_key_header, new_claim):
        claim_id = new_claim["id"]
        client.post(f"/assist/claims/{claim_id}/advance", headers=api_key_header)
        r = client.get(f"/claims/{claim_id}/audit", headers=api_key_header)
        assert r.status_code == 200
        logs = r.json()
        status_logs = [
            x for x in logs
            if x["action"] == "update" and x["field"] == "status"
        ]
        assert len(status_logs) >= 1
        assert status_logs[0]["old_value"] == "new"
        assert status_logs[0]["new_value"] == "researching"

    def test_advance_through_full_lifecycle(self, client, api_key_header, new_claim):
        claim_id = new_claim["id"]
        expected = [
            "researching",
            "contacted",
            "paperwork_ready",
            "filed",
            "approved",
            "paid",
            "closed",
        ]
        for expected_status in expected:
            r = client.post(f"/assist/claims/{claim_id}/advance", headers=api_key_header)
            assert r.status_code == 200, f"Failed advancing to {expected_status}: {r.text}"
            assert r.json()["status"] == expected_status

    def test_409_when_already_closed(self, client, api_key_header, new_claim):
        claim_id = new_claim["id"]
        client.patch(
            f"/claims/{claim_id}",
            json={"status": "closed"},
            headers=api_key_header,
        )
        r = client.post(f"/assist/claims/{claim_id}/advance", headers=api_key_header)
        assert r.status_code == 409

    def test_404_for_nonexistent_claim(self, client, api_key_header):
        r = client.post(
            f"/assist/claims/{uuid.uuid4()}/advance",
            headers=api_key_header,
        )
        assert r.status_code == 404

    def test_410_for_deleted_claim(self, client, api_key_header, new_claim):
        claim_id = new_claim["id"]
        client.delete(f"/claims/{claim_id}", headers=api_key_header)
        r = client.post(f"/assist/claims/{claim_id}/advance", headers=api_key_header)
        assert r.status_code == 410
