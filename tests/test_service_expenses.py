import pytest

from app.backend import service
from app.backend.db import connect
from app.backend.service import LimitExceeded, NotFound


@pytest.fixture
def conn():
    c = connect(":memory:")
    service.ensure_user(c, 1)
    service.ensure_user(c, 2)
    yield c
    c.close()


def cat_id(conn, user, name):
    return next(c.id for c in service.list_categories(conn, user) if c.name == name)


def test_known_word_is_categorized(conn):
    assert service.add_expense(conn, 1, "metro", 4000).category == "Travel"


def test_unknown_word_returns_none_and_saves(conn):
    r = service.add_expense(conn, 1, "samosa", 2000)
    assert r.category is None and r.word == "samosa"
    row = conn.execute("SELECT category_id FROM expenses WHERE id=?", (r.expense_id,)).fetchone()
    assert row["category_id"] is None


def test_assign_category_learns_word(conn):
    r = service.add_expense(conn, 1, "samosa", 2000)
    assert service.assign_category(conn, 1, r.expense_id, cat_id(conn, 1, "Food")) == "Food"
    assert service.add_expense(conn, 1, "samosa", 3000).category == "Food"


def test_first_word_key(conn):
    assert service.add_expense(conn, 1, "Lunch with team", 25000).category == "Food"
    assert service.add_expense(conn, 1, "lunch, again", 100).category == "Food"


def test_mapping_is_per_user(conn):
    r = service.add_expense(conn, 1, "samosa", 2000)
    service.assign_category(conn, 1, r.expense_id, cat_id(conn, 1, "Food"))
    assert service.add_expense(conn, 2, "samosa", 2000).category is None


def test_assign_other_users_expense_raises_notfound(conn):
    r = service.add_expense(conn, 1, "samosa", 2000)
    with pytest.raises(NotFound):
        service.assign_category(conn, 2, r.expense_id, cat_id(conn, 2, "Food"))
    with pytest.raises(NotFound):
        service.assign_category(conn, 1, r.expense_id, cat_id(conn, 2, "Food"))


def test_assign_twice_is_idempotent(conn):
    r = service.add_expense(conn, 1, "samosa", 2000)
    c = cat_id(conn, 1, "Food")
    service.assign_category(conn, 1, r.expense_id, c)
    service.assign_category(conn, 1, r.expense_id, c)
    n = conn.execute("SELECT COUNT(*) n FROM word_map WHERE telegram_user_id=1 AND word='samosa'").fetchone()["n"]
    assert n == 1


def test_create_category_duplicate_returns_existing(conn):
    existing = cat_id(conn, 1, "Food")
    assert service.create_category(conn, 1, "  food ").id == existing


def test_category_cap(conn):
    for i in range(26):
        service.create_category(conn, 1, f"c{i}")
    with pytest.raises(LimitExceeded):
        service.create_category(conn, 1, "one too many")


def test_expense_cap(conn, monkeypatch):
    monkeypatch.setattr(service, "MAX_EXPENSES", 2)
    service.add_expense(conn, 1, "metro", 100)
    service.add_expense(conn, 1, "metro", 100)
    with pytest.raises(LimitExceeded):
        service.add_expense(conn, 1, "metro", 100)
