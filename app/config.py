import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    backend_secret: str
    backend_url: str
    db_path: str


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable {name}")
    return value


def load_settings(dotenv_path: str | None = ".env") -> Settings:
    if dotenv_path:
        load_dotenv(dotenv_path)
    return Settings(
        bot_token=_required("BOT_API_KEY"),
        backend_secret=_required("BACKEND_SECRET"),
        backend_url=os.environ.get("BACKEND_URL", "http://127.0.0.1:8000"),
        db_path=os.environ.get("DB_PATH", "rupee.db"),
    )
