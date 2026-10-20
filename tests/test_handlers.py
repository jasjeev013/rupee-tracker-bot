from types import SimpleNamespace

import pytest
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler

from app.bot.client import BackendError
from app.bot.handlers import make_handlers


class FakeClient:
    def __init__(self):
        self.calls = []
        self.add_result = {"expense_id": 5, "category": "Travel", "word": "metro"}
        self.error = None

    def _maybe_fail(self):
        if self.error:
            raise self.error

    async def add_expense(self, user_id, description, amount_paise):
        self.calls.append(("add", user_id, description, amount_paise))
        self._maybe_fail()
        return self.add_result

    async def assign_category(self, user_id, expense_id, category_id):
        self.calls.append(("assign", user_id, expense_id, category_id))
        self._maybe_fail()
        return {"category": "Food"}

    async def categories(self, user_id):
        return [{"id": 1, "name": "Travel"}, {"id": 2, "name": "Food"}]

    async def create_category(self, user_id, name):
        self.calls.append(("create", user_id, name))
        self._maybe_fail()
        return {"id": 9, "name": name}

    async def today(self, user_id):
        return {"items": [{"description": "metro", "amount_paise": 4000, "category": "Travel"}], "total_paise": 4000}

    async def stats(self, user_id, period):
        self.calls.append(("stats", user_id, period))
        return {"rows": [{"category": "Travel", "total_paise": 4000, "percent": 100}], "total_paise": 4000}


class Msg:
    def __init__(self, text):
        self.text = text
        self.sent = []

    async def reply_text(self, text, reply_markup=None):
        self.sent.append((text, reply_markup))


class Query:
    def __init__(self, data, text="Saved ₹20. Which category for \"samosa\"?"):
        self.data = data
        self.message = SimpleNamespace(text=text)
        self.edits = []
        self.answers = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))

    async def edit_message_text(self, text, reply_markup=None):
        self.edits.append((text, reply_markup))


def msg_update(text, user=1):
    return SimpleNamespace(message=Msg(text), effective_user=SimpleNamespace(id=user), callback_query=None)


def cb_update(data, user=1, **kw):
    return SimpleNamespace(message=None, effective_user=SimpleNamespace(id=user), callback_query=Query(data, **kw))


def ctx():
    return SimpleNamespace(user_data={})


@pytest.fixture
def setup():
    client = FakeClient()
    handlers = make_handlers(client)
    by_type = {}
    for h in handlers:
        by_type.setdefault(type(h), []).append(h)
    text = next(h for h in by_type[MessageHandler]).callback
    callback = by_type[CallbackQueryHandler][0].callback
    start = by_type[CommandHandler][0].callback
    return client, text, callback, start


async def test_start_shows_menu(setup):
    _, _, _, start = setup
    u = msg_update("/start")
    await start(u, ctx())
    _, markup = u.message.sent[0]
    labels = [b.text for row in markup.keyboard for b in row]
    assert labels == ["Today's Spending", "Overall Stats"]


async def test_logs_known_word(setup):
    client, text, _, _ = setup
    u = msg_update("metro 40")
    await text(u, ctx())
    assert client.calls == [("add", 1, "metro", 4000)]
    assert u.message.sent[0][0] == "Saved ₹40 to Travel"


async def test_unknown_word_shows_buttons(setup):
    client, text, _, _ = setup
    client.add_result = {"expense_id": 7, "category": None, "word": "samosa"}
    u = msg_update("samosa 20")
    await text(u, ctx())
    reply, markup = u.message.sent[0]
    assert reply == 'Saved ₹20. Which category for "samosa"?'
    buttons = [b for row in markup.inline_keyboard for b in row]
    assert [b.text for b in buttons] == ["Travel", "Food", "+ New category"]
    assert buttons[1].callback_data == "cat:7:2"
    assert buttons[2].callback_data == "newcat:7"
    assert all(len(b.callback_data.encode()) <= 64 for b in buttons)


async def test_unparseable_replies_hint(setup):
    client, text, _, _ = setup
    for t in ["hello", "lunch 0", "x" * 300]:
        u = msg_update(t)
        await text(u, ctx())
        assert u.message.sent[0][0] == "Send it like: metro 40"
    assert client.calls == []


async def test_sticker_is_ignored(setup):
    client, text, _, _ = setup
    u = msg_update(None)
    await text(u, ctx())
    assert u.message.sent == [] and client.calls == []


async def test_callback_assigns_and_edits(setup):
    client, _, callback, _ = setup
    u = cb_update("cat:7:2")
    await callback(u, ctx())
    assert client.calls == [("assign", 1, 7, 2)]
    assert u.callback_query.edits[0][0] == "Saved ₹20 to Food"


async def test_callback_notfound_message(setup):
    client, _, callback, _ = setup
    client.error = BackendError(404)
    u = cb_update("cat:7:2")
    await callback(u, ctx())
    assert u.callback_query.edits == []
    text, alert = u.callback_query.answers[-1]
    assert "no longer exists" in text and alert


async def test_rate_limited_message(setup):
    client, text, _, _ = setup
    client.error = BackendError(429)
    u = msg_update("metro 40")
    await text(u, ctx())
    assert u.message.sent[0][0] == "Slow down a little."


async def test_backend_down_message(setup):
    client, text, _, _ = setup
    client.error = BackendError(0)
    u = msg_update("metro 40")
    await text(u, ctx())
    assert u.message.sent[0][0] == "Something went wrong, try again."


async def test_today_button(setup):
    _, text, _, _ = setup
    u = msg_update("Today's Spending")
    await text(u, ctx())
    assert "Total ₹40" in u.message.sent[0][0]


async def test_stats_button_and_period_switch(setup):
    client, text, callback, _ = setup
    u = msg_update("Overall Stats")
    await text(u, ctx())
    reply, markup = u.message.sent[0]
    assert reply.startswith("This month") and "Travel ₹40 (100%)" in reply
    data = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert data == ["stats:month", "stats:last_month", "stats:year"]
    c = cb_update("stats:last_month")
    await callback(c, ctx())
    assert ("stats", 1, "last_month") in client.calls
    assert c.callback_query.edits[0][0].startswith("Last month")


async def test_new_category_flow(setup):
    client, text, callback, _ = setup
    context = ctx()
    c = cb_update("newcat:7")
    await callback(c, context)
    assert context.user_data["new_cat_for"] == 7
    u = msg_update("Gym")
    await text(u, context)
    assert ("create", 1, "Gym") in client.calls
    assert ("assign", 1, 7, 9) in client.calls
    assert u.message.sent[0][0] == "Saved to Gym"
    assert "new_cat_for" not in context.user_data


async def test_menu_label_cancels_pending_new_category(setup):
    client, text, _, _ = setup
    context = ctx()
    context.user_data["new_cat_for"] = 7
    u = msg_update("Today's Spending")
    await text(u, context)
    assert "new_cat_for" not in context.user_data
    assert not any(c[0] == "create" for c in client.calls)
