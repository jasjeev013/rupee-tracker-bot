# Rupee Tracker Bot

A Telegram bot for logging daily cash spending. Send `metro 40`; it saves the expense under a personal category and shows today's spending and monthly/yearly category stats.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` (see `.env.example`):

- `BOT_API_KEY` — the token from BotFather
- `BACKEND_SECRET` — any long random string shared by the bot and backend
- optional: `BACKEND_URL` (default `http://127.0.0.1:8000`), `DB_PATH` (default `rupee.db`)

## Run

Two processes, in two terminals:

```bash
python -m app.backend    # API on 127.0.0.1:8000
python -m app.bot.main   # Telegram bot (long polling)
```

## Run with Docker (dev)

```bash
docker compose -f docker-compose.dev.yml up --build
```

Starts `backend` and `bot` from `Dockerfile.dev`. The source is bind-mounted, so after a code change run `docker compose -f docker-compose.dev.yml restart`. The database is `data/rupee.db` in the repo folder (git-ignored). The backend is published on `127.0.0.1:8000` only. A production Dockerfile/compose will be added separately.

## Test

```bash
pytest
```
