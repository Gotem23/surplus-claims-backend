from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200


def test_claims_requires_api_key():
    r = client.get("/claims")
    assert r.status_code == 401
    body = r.json()
    assert "error" in body
