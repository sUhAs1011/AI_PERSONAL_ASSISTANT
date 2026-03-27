from fastapi.testclient import TestClient

from app.main import app


def test_put_then_get_preferences():
    client = TestClient(app)
    put_resp = client.put("/preferences/u1", json={"no_meetings_before_hour": 10})
    get_resp = client.get("/preferences/u1")
    assert put_resp.status_code == 200
    assert get_resp.json()["no_meetings_before_hour"] == 10

