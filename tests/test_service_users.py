import pytest

from app.backend import service
from app.backend.db import connect


@pytest.fixture
def conn():
    c = connect(":memory:")
    yield c
    c.close()


def test_ensure_user_creates_defaults(conn):
    service.ensure_user(conn, 1)
    names = [c.name for c in service.list_categories(conn, 1)]
    assert names == ["Travel", "Food", "Groceries", "Other"]


def test_ensure_user_is_idempotent(conn):
    service.ensure_user(conn, 1)
    service.ensure_user(conn, 1)
    assert len(service.list_categories(conn, 1)) == 4


def test_users_are_isolated(conn):
    service.ensure_user(conn, 1)
    service.ensure_user(conn, 2)
    ids1 = {c.id for c in service.list_categories(conn, 1)}
    ids2 = {c.id for c in service.list_categories(conn, 2)}
    assert ids1.isdisjoint(ids2)
