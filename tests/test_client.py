import httpx
import pytest

from app.bot.client import BackendClient, BackendError


def make(handler):
    return BackendClient("http://b", "sec", transport=httpx.MockTransport(handler))


async def test_sends_secret_and_returns_json():
    seen = {}

    def handler(request: httpx.Request):
        seen["secret"] = request.headers["x-bot-secret"]
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"total_paise": 0, "items": []})

    out = await make(handler).today(7)
    assert seen["secret"] == "sec" and "user_id=7" in seen["url"]
    assert out == {"total_paise": 0, "items": []}


async def test_error_raises_backend_error():
    c = make(lambda r: httpx.Response(429, json={"detail": "rate limited"}))
    with pytest.raises(BackendError) as e:
        await c.add_expense(1, "metro", 4000)
    assert e.value.status == 429


async def test_post_bodies():
    bodies = []

    def handler(request: httpx.Request):
        bodies.append((request.url.path, request.content))
        return httpx.Response(200, json={})

    c = make(handler)
    await c.assign_category(1, 9, 3)
    assert bodies[0][0] == "/expenses/9/category"
    assert b'"category_id":3' in bodies[0][1].replace(b" ", b"")


async def test_feedback_posts_message():
    seen = []

    def handler(request: httpx.Request):
        seen.append((request.url.path, request.content))
        return httpx.Response(200, json={"ok": True})

    await make(handler).feedback(3, "great")
    assert seen[0][0] == "/feedback"
    assert b'"message":"great"' in seen[0][1].replace(b" ", b"")
