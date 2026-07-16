# Prod.by Bot

Telegram-бот закрытого музыкального сообщества с анкетами, вложениями, ролями, модерацией форумных тем и административной Mini App.

## Возможности

- заявки на вступление через личные сообщения бота;
- настраиваемые вопросы анкеты и вложения до 10 МБ;
- одобрение, отклонение и блокировка кандидатов;
- несколько ролей у участника;
- ограничения публикации в темах по ролям;
- уровни доступа `owner`, `admin` и `moderator`;
- журнал действий и просмотр медиа в панели;
- управление профилем Telegram-бота и текстами его сообщений;
- ежедневные резервные копии PostgreSQL и ротация Docker-логов.

## Стек

- Python 3.11, aiogram 3, FastAPI;
- PostgreSQL 16, SQLAlchemy 2, Alembic;
- React 19, Vite, TypeScript;
- Docker Compose, Nginx, Caddy.

## Документация

- [Локальный запуск](docs/LOCAL_SETUP.md)
- [Развертывание на Ubuntu VPS](docs/VPS_DEPLOY.md)
- [Резервные копии и восстановление](docs/BACKUP_RESTORE.md)

## Быстрый локальный запуск

```powershell
Copy-Item .env.example .env
# Заполните BOT_TOKEN, TELEGRAM_GROUP_ID и ADMIN_IDS в .env
docker compose up -d --build
```

- Панель: <http://localhost:5173>
- API health check: <http://localhost:8000/health>

Секреты не хранятся в Git. Файлы `.env` и `.env.production` игнорируются.

## Доступ к панели

- `owner` и `admin`: полный доступ;
- `moderator`: заявки и участники;
- остальные пользователи: HTTP 403.

В production обязательно используется `APP_ENV=production`. Локальный тестовый заголовок авторизации при этом отключен.

## Хранение вложений

Файлы заявок остаются в Telegram. В PostgreSQL сохраняются `file_id` и метаданные, поэтому вложения не занимают место на VPS. Бэкап PostgreSQL не содержит бинарные копии вложений.
