import pytest

from app.config import load_settings


def test_load_settings_reads_env(monkeypatch):
    monkeypatch.setenv("BOT_API_KEY", "tok")
    monkeypatch.setenv("BACKEND_SECRET", "sec")
    monkeypatch.delenv("BACKEND_URL", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    s = load_settings(dotenv_path=None)
    assert s.bot_token == "tok"
    assert s.backend_secret == "sec"
    assert s.backend_url == "http://127.0.0.1:8000"
    assert s.db_path == "rupee.db"


def test_missing_secret_raises(monkeypatch):
    monkeypatch.setenv("BOT_API_KEY", "tok")
    monkeypatch.delenv("BACKEND_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="BACKEND_SECRET"):
        load_settings(dotenv_path=None)
