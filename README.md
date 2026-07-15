# Prod.by Bot

MVP for Telegram community applications, admin Mini App, roles, protected forum topics, and per-topic whitelists.

## Stack

- Python 3.11+
- aiogram 3
- FastAPI
- PostgreSQL
- SQLAlchemy 2 + Alembic
- React + Vite + TypeScript
- Docker Compose

## Local setup

1. Copy `.env.example` to `.env`.
2. Put the BotFather token into `BOT_TOKEN`.
3. Keep `ADMIN_IDS` as the initial owner/admin Telegram IDs.
4. Start services:

```powershell
docker compose up --build
```

API:

```text
http://localhost:8000
```

Admin web:

```text
http://localhost:5173
```

For Telegram Mini App testing, expose the admin/API URL through an HTTPS tunnel such as ngrok or Cloudflare Tunnel, then put that URL into BotFather / menu button settings.

## Development

Backend runs as two processes:

- `api`: FastAPI HTTP API for the admin panel.
- `bot`: aiogram long-polling worker for Telegram.

The project stores no secrets in Git. Use `.env`.

