import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_user_id INTEGER PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,
    name TEXT NOT NULL COLLATE NOCASE,
    UNIQUE (telegram_user_id, name)
);
CREATE TABLE IF NOT EXISTS word_map (
    telegram_user_id INTEGER NOT NULL,
    word TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    PRIMARY KEY (telegram_user_id, word)
);
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    amount_paise INTEGER NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    created_at_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    created_at_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_expenses_user_time
    ON expenses (telegram_user_id, created_at_utc);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn
