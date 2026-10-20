import logging

from telegram.ext import Application

from app.bot.client import BackendClient
from app.bot.handlers import make_handlers
from app.config import load_settings


def build_application() -> Application:
    settings = load_settings()
    client = BackendClient(settings.backend_url, settings.backend_secret)
    app = Application.builder().token(settings.bot_token).build()
    app.add_handlers(make_handlers(client))
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # httpx logs full request URLs, which include the bot token
    logging.getLogger("httpx").setLevel(logging.WARNING)
    build_application().run_polling()
