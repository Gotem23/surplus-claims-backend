from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_missing_api_key_returns_401():
    r = client.get("/claims")
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "unauthorized"
    assert body["error"]["message"] == "Missing API key"


def test_invalid_api_key_returns_401():
    r = client.get("/claims", headers={"X-API-Key": "bad-key"})
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "unauthorized"
    assert body["error"]["message"] == "Invalid API key"
