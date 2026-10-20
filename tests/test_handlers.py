import re
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

    async def feedback(self, user_id, message):
        self.calls.append(("feedback", user_id, message))
        self._maybe_fail()
        return {"ok": True}


class Msg:
    def __init__(self, text):
        self.text = text
        self.sent = []
        self.parse_modes = []

    async def reply_text(self, text, reply_markup=None, parse_mode=None):
        self.sent.append((text, reply_markup))
        self.parse_modes.append(parse_mode)


class Query:
    def __init__(self, data, text="Saved ₹20. Which category for \"samosa\"?"):
        self.data = data
        self.message = SimpleNamespace(text=text)
        self.edits = []
        self.edit_modes = []
        self.answers = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))

    async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
        self.edits.append((text, reply_markup))
        self.edit_modes.append(parse_mode)


def user(uid=1, name="Jasjeev"):
    return SimpleNamespace(id=uid, first_name=name)


def msg_update(text, uid=1, name="Jasjeev"):
    return SimpleNamespace(message=Msg(text), effective_user=user(uid, name), callback_query=None)


def cb_update(data, uid=1, **kw):
    return SimpleNamespace(message=None, effective_user=user(uid), callback_query=Query(data, **kw))


def ctx():
    return SimpleNamespace(user_data={})


@pytest.fixture
def setup():
    client = FakeClient()
    handlers = make_handlers(client)
    by_type = {}
    for h in handlers:
        by_type.setdefault(type(h), []).append(h)
    text = by_type[MessageHandler][0].callback
    callback = by_type[CallbackQueryHandler][0].callback
    start = by_type[CommandHandler][0].callback
    return client, text, callback, start


# --- greeting -------------------------------------------------------------


async def test_start_greets_by_name_explains_and_shows_menu(setup):
    _, _, _, start = setup
    u = msg_update("/start", name="Jasjeev")
    await start(u, ctx())
    reply, markup = u.message.sent[0]
    assert "Jasjeev" in reply
    assert "metro 40" in reply
    assert "Today's Spending" in reply and "Overall Stats" in reply and "Feedback" in reply
    labels = [b.text for row in markup.keyboard for b in row]
    assert labels == ["Today's Spending", "Overall Stats", "Feedback"]


async def test_start_without_a_name_still_greets(setup):
    _, _, _, start = setup
    u = msg_update("/start", name=None)
    await start(u, ctx())
    assert u.message.sent[0][0].startswith("Hi there")


# --- logging --------------------------------------------------------------


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


@pytest.mark.parametrize("t", ["asdf", "ok", "lunch 0", "x" * 300, "what can you do?"])
async def test_unparseable_gets_friendly_help_with_examples(setup, t):
    client, text, _, _ = setup
    u = msg_update(t)
    await text(u, ctx())
    reply = u.message.sent[0][0]
    assert reply != "Send it like: metro 40"
    assert "metro 40" in reply and "lunch 250" in reply
    assert client.calls == []


@pytest.mark.parametrize("t", ["Hi", "hello!", "Hey there", "HELLO"])
async def test_greeting_gets_a_hello_back_by_name(setup, t):
    client, text, _, _ = setup
    u = msg_update(t, name="Jasjeev")
    await text(u, ctx())
    reply = u.message.sent[0][0]
    assert "Jasjeev" in reply and "metro 40" in reply
    assert client.calls == []


async def test_sticker_is_ignored(setup):
    client, text, _, _ = setup
    u = msg_update(None)
    await text(u, ctx())
    assert u.message.sent == [] and client.calls == []


# --- category buttons -----------------------------------------------------


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


# --- bills ----------------------------------------------------------------


async def test_today_button_sends_a_bill(setup):
    _, text, _, _ = setup
    u = msg_update("Today's Spending")
    await text(u, ctx())
    reply = u.message.sent[0][0]
    assert u.message.parse_modes[0] == "HTML"
    assert reply.startswith("<pre>") and "RUPEE TRACKER" in reply
    assert re.search(r"[A-Z][a-z]{2}, \d{2} [A-Z][a-z]{2} \d{4}", reply)  # e.g. Tue, 20 Oct 2026
    assert "metro" in reply and "TOTAL" in reply and "₹40" in reply


async def test_stats_button_and_period_switch(setup):
    client, text, callback, _ = setup
    u = msg_update("Overall Stats")
    await text(u, ctx())
    reply, markup = u.message.sent[0]
    assert u.message.parse_modes[0] == "HTML"
    assert reply.startswith("<pre>") and "This month" in reply and "Travel" in reply and "100%" in reply
    data = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert data == ["stats:month", "stats:last_month", "stats:year"]
    c = cb_update("stats:last_month")
    await callback(c, ctx())
    assert ("stats", 1, "last_month") in client.calls
    assert c.callback_query.edit_modes[0] == "HTML"
    assert "Last month" in c.callback_query.edits[0][0]


# --- feedback -------------------------------------------------------------


async def test_feedback_button_prompts_then_saves_next_message(setup):
    client, text, _, _ = setup
    context = ctx()
    u = msg_update("Feedback")
    await text(u, context)
    assert "feedback" in u.message.sent[0][0].lower()
    assert context.user_data["awaiting_feedback"] is True
    u2 = msg_update("great bot, add budgets")
    await text(u2, context)
    assert client.calls == [("feedback", 1, "great bot, add budgets")]  # not logged as an expense
    assert "Thank" in u2.message.sent[0][0]
    assert "awaiting_feedback" not in context.user_data


async def test_feedback_too_long_keeps_waiting(setup):
    client, text, _, _ = setup
    context = ctx()
    context.user_data["awaiting_feedback"] = True
    client.error = BackendError(422)
    u = msg_update("x" * 1500)
    await text(u, context)
    assert "1000" in u.message.sent[0][0]
    assert context.user_data["awaiting_feedback"] is True


async def test_feedback_cap_stops_waiting(setup):
    client, text, _, _ = setup
    context = ctx()
    context.user_data["awaiting_feedback"] = True
    client.error = BackendError(409)
    u = msg_update("more feedback")
    await text(u, context)
    assert "plenty" in u.message.sent[0][0]
    assert "awaiting_feedback" not in context.user_data


@pytest.mark.parametrize("label", ["Today's Spending", "Overall Stats"])
async def test_menu_buttons_cancel_pending_input(setup, label):
    client, text, _, _ = setup
    context = ctx()
    context.user_data["awaiting_feedback"] = True
    context.user_data["new_cat_for"] = 7
    await text(msg_update(label), context)
    assert context.user_data == {}
    assert not any(c[0] in ("create", "feedback") for c in client.calls)


async def test_feedback_button_cancels_pending_new_category(setup):
    _, text, _, _ = setup
    context = ctx()
    context.user_data["new_cat_for"] = 7
    await text(msg_update("Feedback"), context)
    assert "new_cat_for" not in context.user_data
    assert context.user_data["awaiting_feedback"] is True
