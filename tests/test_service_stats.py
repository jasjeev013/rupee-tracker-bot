from datetime import datetime, timezone

import pytest

from app.backend import service
from app.backend.db import connect


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    c = connect(":memory:")
    service.ensure_user(c, 1)
    service.ensure_user(c, 2)
    yield c
    c.close()


# 2026-10-20 18:29 UTC == 23:59 IST (Oct 20); 18:31 UTC == 00:01 IST (Oct 21)
NOW = utc(2026, 10, 20, 18, 29)


def test_today_only_includes_ist_today(conn):
    service.add_expense(conn, 1, "metro", 4000, now_utc=utc(2026, 10, 20, 18, 29))
    service.add_expense(conn, 1, "bus", 1000, now_utc=utc(2026, 10, 20, 18, 31))
    r = service.today(conn, 1, now_utc=NOW)
    assert [i.description for i in r.items] == ["metro"]
    assert r.total_paise == 4000
    assert r.items[0].category == "Travel"
    nxt = service.today(conn, 1, now_utc=utc(2026, 10, 20, 18, 32))
    assert [i.description for i in nxt.items] == ["bus"]


def test_stats_month_groups_by_category(conn):
    service.add_expense(conn, 1, "metro", 4000, now_utc=NOW)
    service.add_expense(conn, 1, "bus", 2000, now_utc=NOW)
    service.add_expense(conn, 1, "lunch", 6000, now_utc=NOW)
    r = service.stats(conn, 1, "month", now_utc=NOW)
    assert r.total_paise == 12000
    assert [(x.category, x.total_paise, x.percent) for x in r.rows] == [
        ("Food", 6000, 50),
        ("Travel", 6000, 50),
    ] or [(x.category, x.total_paise, x.percent) for x in r.rows] == [
        ("Travel", 6000, 50),
        ("Food", 6000, 50),
    ]


def test_stats_sorted_descending(conn):
    service.add_expense(conn, 1, "metro", 1000, now_utc=NOW)
    service.add_expense(conn, 1, "lunch", 3000, now_utc=NOW)
    r = service.stats(conn, 1, "month", now_utc=NOW)
    assert [x.category for x in r.rows] == ["Food", "Travel"]


def test_stats_last_month_and_year(conn):
    service.add_expense(conn, 1, "metro", 1000, now_utc=utc(2026, 9, 15, 6))
    service.add_expense(conn, 1, "metro", 2000, now_utc=utc(2026, 1, 1, 6))
    service.add_expense(conn, 1, "metro", 4000, now_utc=utc(2025, 12, 31, 6))
    assert service.stats(conn, 1, "last_month", now_utc=NOW).total_paise == 1000
    assert service.stats(conn, 1, "year", now_utc=NOW).total_paise == 3000
    assert service.stats(conn, 1, "month", now_utc=NOW).total_paise == 0


def test_last_month_in_january_is_december(conn):
    service.add_expense(conn, 1, "metro", 500, now_utc=utc(2025, 12, 31, 6))
    r = service.stats(conn, 1, "last_month", now_utc=utc(2026, 1, 10, 6))
    assert r.total_paise == 500


def test_stats_uncategorized_label(conn):
    service.add_expense(conn, 1, "samosa", 2000, now_utc=NOW)
    r = service.stats(conn, 1, "month", now_utc=NOW)
    assert r.rows[0].category == "Uncategorized"


def test_stats_empty_period(conn):
    r = service.stats(conn, 1, "month", now_utc=NOW)
    assert r.rows == [] and r.total_paise == 0
    t = service.today(conn, 1, now_utc=NOW)
    assert t.items == [] and t.total_paise == 0


def test_stats_excludes_other_users(conn):
    service.add_expense(conn, 2, "metro", 9999, now_utc=NOW)
    assert service.stats(conn, 1, "month", now_utc=NOW).total_paise == 0
    assert service.today(conn, 1, now_utc=NOW).total_paise == 0
