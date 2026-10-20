import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

MAX_CATEGORIES = 30
MAX_MAPPINGS = 500
MAX_EXPENSES = 50_000
MAX_FEEDBACK = 20
MAX_FEEDBACK_LEN = 1000
MAX_NAME_LEN = 30

DEFAULT_CATEGORIES = ["Travel", "Food", "Groceries", "Other"]
DEFAULT_WORDS = {
    "metro": "Travel", "bus": "Travel", "auto": "Travel", "cab": "Travel",
    "lunch": "Food", "dinner": "Food", "breakfast": "Food", "chai": "Food",
    "vegetables": "Groceries", "milk": "Groceries",
}

_WORD = re.compile(r"\w+")


class NotFound(Exception):
    pass


class LimitExceeded(Exception):
    pass


@dataclass(frozen=True)
class Category:
    id: int
    name: str


@dataclass(frozen=True)
class AddResult:
    expense_id: int
    category: str | None
    word: str


def _utc_str(dt: datetime | None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def word_key(description: str) -> str:
    m = _WORD.search(description)
    return (m.group(0) if m else description.strip()[:MAX_NAME_LEN]).lower()


def ensure_user(conn: sqlite3.Connection, user_id: int) -> None:
    if conn.execute("SELECT 1 FROM users WHERE telegram_user_id=?", (user_id,)).fetchone():
        return
    with conn:
        conn.execute("INSERT OR IGNORE INTO users VALUES (?)", (user_id,))
        for name in DEFAULT_CATEGORIES:
            conn.execute(
                "INSERT OR IGNORE INTO categories (telegram_user_id, name) VALUES (?, ?)",
                (user_id, name),
            )
        ids = {c.name: c.id for c in list_categories(conn, user_id)}
        for word, cat in DEFAULT_WORDS.items():
            conn.execute(
                "INSERT OR IGNORE INTO word_map VALUES (?, ?, ?)", (user_id, word, ids[cat])
            )


def list_categories(conn: sqlite3.Connection, user_id: int) -> list[Category]:
    rows = conn.execute(
        "SELECT id, name FROM categories WHERE telegram_user_id=? ORDER BY id", (user_id,)
    ).fetchall()
    return [Category(r["id"], r["name"]) for r in rows]


def create_category(conn: sqlite3.Connection, user_id: int, name: str) -> Category:
    name = " ".join(name.split())
    if not name or len(name) > MAX_NAME_LEN:
        raise ValueError("Category name must be 1-30 characters")
    row = conn.execute(
        "SELECT id, name FROM categories WHERE telegram_user_id=? AND name=?", (user_id, name)
    ).fetchone()
    if row:
        return Category(row["id"], row["name"])
    count = conn.execute(
        "SELECT COUNT(*) n FROM categories WHERE telegram_user_id=?", (user_id,)
    ).fetchone()["n"]
    if count >= MAX_CATEGORIES:
        raise LimitExceeded("category limit reached")
    with conn:
        cur = conn.execute(
            "INSERT INTO categories (telegram_user_id, name) VALUES (?, ?)", (user_id, name)
        )
    return Category(cur.lastrowid, name)


def add_expense(
    conn: sqlite3.Connection,
    user_id: int,
    description: str,
    amount_paise: int,
    now_utc: datetime | None = None,
) -> AddResult:
    count = conn.execute(
        "SELECT COUNT(*) n FROM expenses WHERE telegram_user_id=?", (user_id,)
    ).fetchone()["n"]
    if count >= MAX_EXPENSES:
        raise LimitExceeded("expense limit reached")
    word = word_key(description)
    row = conn.execute(
        "SELECT c.id, c.name FROM word_map w JOIN categories c ON c.id = w.category_id "
        "WHERE w.telegram_user_id=? AND w.word=?",
        (user_id, word),
    ).fetchone()
    with conn:
        cur = conn.execute(
            "INSERT INTO expenses (telegram_user_id, description, amount_paise, category_id, "
            "created_at_utc) VALUES (?, ?, ?, ?, ?)",
            (user_id, description, amount_paise, row["id"] if row else None, _utc_str(now_utc)),
        )
    return AddResult(cur.lastrowid, row["name"] if row else None, word)


def assign_category(
    conn: sqlite3.Connection, user_id: int, expense_id: int, category_id: int
) -> str:
    exp = conn.execute(
        "SELECT description FROM expenses WHERE id=? AND telegram_user_id=?",
        (expense_id, user_id),
    ).fetchone()
    cat = conn.execute(
        "SELECT name FROM categories WHERE id=? AND telegram_user_id=?", (category_id, user_id)
    ).fetchone()
    if not exp or not cat:
        raise NotFound("expense or category not found")
    word = word_key(exp["description"])
    with conn:
        conn.execute(
            "UPDATE expenses SET category_id=? WHERE id=? AND telegram_user_id=?",
            (category_id, expense_id, user_id),
        )
        mappings = conn.execute(
            "SELECT COUNT(*) n FROM word_map WHERE telegram_user_id=?", (user_id,)
        ).fetchone()["n"]
        known = conn.execute(
            "SELECT 1 FROM word_map WHERE telegram_user_id=? AND word=?", (user_id, word)
        ).fetchone()
        if known or mappings < MAX_MAPPINGS:
            conn.execute(
                "INSERT OR REPLACE INTO word_map VALUES (?, ?, ?)", (user_id, word, category_id)
            )
    return cat["name"]


def add_feedback(conn: sqlite3.Connection, user_id: int, message: str) -> None:
    message = message.strip()
    if not message or len(message) > MAX_FEEDBACK_LEN:
        raise ValueError(f"Feedback must be 1-{MAX_FEEDBACK_LEN} characters")
    count = conn.execute(
        "SELECT COUNT(*) n FROM feedback WHERE telegram_user_id=?", (user_id,)
    ).fetchone()["n"]
    if count >= MAX_FEEDBACK:
        raise LimitExceeded("feedback limit reached")
    with conn:
        conn.execute(
            "INSERT INTO feedback (telegram_user_id, message, created_at_utc) VALUES (?, ?, ?)",
            (user_id, message, _utc_str(None)),
        )


IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class Item:
    description: str
    amount_paise: int
    category: str


@dataclass(frozen=True)
class TodayResult:
    items: list[Item]
    total_paise: int


@dataclass(frozen=True)
class StatRow:
    category: str
    total_paise: int
    percent: int


@dataclass(frozen=True)
class StatsResult:
    rows: list[StatRow]
    total_paise: int


def _period_bounds(period: str, now_utc: datetime | None) -> tuple[str, str]:
    now = (now_utc or datetime.now(timezone.utc)).astimezone(IST)
    if period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = (start + timedelta(days=32)).replace(day=1)
    elif period == "last_month":
        end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start = (end - timedelta(days=1)).replace(day=1)
    elif period == "year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(year=start.year + 1)
    elif period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    else:
        raise ValueError(f"unknown period {period!r}")
    return _utc_str(start), _utc_str(end)


def today(conn: sqlite3.Connection, user_id: int, now_utc: datetime | None = None) -> TodayResult:
    start, end = _period_bounds("today", now_utc)
    rows = conn.execute(
        "SELECT e.description, e.amount_paise, COALESCE(c.name, 'Uncategorized') AS category "
        "FROM expenses e LEFT JOIN categories c ON c.id = e.category_id "
        "WHERE e.telegram_user_id=? AND e.created_at_utc >= ? AND e.created_at_utc < ? "
        "ORDER BY e.created_at_utc, e.id",
        (user_id, start, end),
    ).fetchall()
    items = [Item(r["description"], r["amount_paise"], r["category"]) for r in rows]
    return TodayResult(items, sum(i.amount_paise for i in items))


def stats(
    conn: sqlite3.Connection, user_id: int, period: str, now_utc: datetime | None = None
) -> StatsResult:
    start, end = _period_bounds(period, now_utc)
    rows = conn.execute(
        "SELECT COALESCE(c.name, 'Uncategorized') AS category, SUM(e.amount_paise) AS total "
        "FROM expenses e LEFT JOIN categories c ON c.id = e.category_id "
        "WHERE e.telegram_user_id=? AND e.created_at_utc >= ? AND e.created_at_utc < ? "
        "GROUP BY category ORDER BY total DESC, category",
        (user_id, start, end),
    ).fetchall()
    grand = sum(r["total"] for r in rows)
    return StatsResult(
        [StatRow(r["category"], r["total"], round(r["total"] * 100 / grand)) for r in rows],
        grand,
    )
