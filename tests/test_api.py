import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.config import Settings

H = {"X-Bot-Secret": "s3cret"}


@pytest.fixture
def client(tmp_path):
    settings = Settings("tok", "s3cret", "http://x", str(tmp_path / "t.db"))
    return TestClient(create_app(settings))


def post_expense(client, user=1, desc="metro", paise=4000):
    return client.post(
        "/expenses", json={"user_id": user, "description": desc, "amount_paise": paise}, headers=H
    )


def test_requires_secret(client):
    assert client.get("/today", params={"user_id": 1}).status_code == 401
    assert client.get("/today", params={"user_id": 1}, headers={"X-Bot-Secret": "no"}).status_code == 401


def test_post_expense_roundtrip(client):
    r = post_expense(client)
    assert r.status_code == 200
    body = r.json()
    assert body["category"] == "Travel" and body["word"] == "metro"
    t = client.get("/today", params={"user_id": 1}, headers=H).json()
    assert t["total_paise"] == 4000 and t["items"][0]["description"] == "metro"


def test_unknown_word_then_assign(client):
    body = post_expense(client, desc="samosa", paise=2000).json()
    assert body["category"] is None
    cats = client.get("/categories", params={"user_id": 1}, headers=H).json()
    food = next(c["id"] for c in cats if c["name"] == "Food")
    r = client.post(
        f"/expenses/{body['expense_id']}/category",
        json={"user_id": 1, "category_id": food},
        headers=H,
    )
    assert r.json() == {"category": "Food"}
    assert post_expense(client, desc="samosa", paise=3000).json()["category"] == "Food"


def test_assign_category_other_user_404(client):
    eid = post_expense(client, user=1, desc="samosa").json()["expense_id"]
    cats2 = client.get("/categories", params={"user_id": 2}, headers=H).json()
    r = client.post(
        f"/expenses/{eid}/category",
        json={"user_id": 2, "category_id": cats2[0]["id"]},
        headers=H,
    )
    assert r.status_code == 404


def test_create_category(client):
    r = client.post("/categories", json={"user_id": 1, "name": "Gym"}, headers=H)
    assert r.status_code == 200 and r.json()["name"] == "Gym"
    bad = client.post("/categories", json={"user_id": 1, "name": "  "}, headers=H)
    assert bad.status_code == 422


def test_validation(client):
    assert post_expense(client, paise=0).status_code == 422
    assert post_expense(client, desc="x" * 201).status_code == 422
    assert post_expense(client, desc="").status_code == 422


def test_stats_endpoint_shape(client):
    post_expense(client)
    r = client.get("/stats", params={"user_id": 1, "period": "month"}, headers=H).json()
    assert r["total_paise"] == 4000
    assert r["rows"] == [{"category": "Travel", "total_paise": 4000, "percent": 100}]
    bad = client.get("/stats", params={"user_id": 1, "period": "decade"}, headers=H)
    assert bad.status_code == 422


def test_rate_limit_returns_429(tmp_path):
    settings = Settings("tok", "s3cret", "http://x", str(tmp_path / "t.db"))
    c = TestClient(create_app(settings, rate_limit=(2, 60)))
    assert post_expense(c).status_code == 200
    assert post_expense(c).status_code == 200
    assert post_expense(c).status_code == 429
    assert post_expense(c, user=2).status_code == 200
