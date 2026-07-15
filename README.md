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
4. Set `MODERATION_TIMEOUT_SECONDS` to the group-wide timeout for posting in a restricted topic without a matching role (minimum 31 seconds, default 60).
5. Start services:

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

## Admin panel access

- `owner` and `admin` can use applications, participants, settings, logs, and staff access management.
- `moderator` can use only applications and participants, including application decisions and community role assignment.
- Users without an active `admin_users` record receive HTTP 403 from protected API routes.
- Full administrators can add, change, or revoke staff access under Settings > Access.
- Production deployments must set `APP_ENV=production`; the development ID header is accepted only in local mode.

## Backups and storage

- Telegram attachments are not copied to the server. PostgreSQL stores their Telegram `file_id` and metadata.
- The `backup` container creates a validated PostgreSQL custom-format dump in `backups/` immediately after startup and then once per day.
- Dumps older than `BACKUP_RETENTION_DAYS` are removed automatically (14 days by default).
- Docker JSON logs are rotated at 10 MB with three files retained per container.

Create an additional backup immediately:

```powershell
docker compose run --rm backup sh /opt/backup/backup.sh --once
```

Validate a dump without restoring it:

```powershell
docker compose exec backup pg_restore --list /backups/prodby_TIMESTAMP.dump
```

The local `backups/` directory is on the same machine as the application. For production, copy this directory to independent storage because a VPS disk failure would otherwise remove both the database and its backups.
