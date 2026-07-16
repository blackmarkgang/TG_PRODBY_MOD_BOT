# Локальный запуск

## Требования

- Git;
- Docker Desktop с Docker Compose;
- Telegram-бот, созданный через BotFather;
- числовой Telegram ID группы и ID первоначальных администраторов.

## 1. Получение проекта

```powershell
git clone https://github.com/blackmarkgang/TG_PRODBY_MOD_BOT.git
Set-Location TG_PRODBY_MOD_BOT
```

Если проект уже находится на компьютере, выполняйте остальные команды из корневой папки репозитория.

## 2. Переменные окружения

```powershell
Copy-Item .env.example .env
notepad .env
```

Обязательно заполните:

```dotenv
APP_ENV=local
BOT_TOKEN=токен_из_BotFather
TELEGRAM_GROUP_ID=-1001234567890
ADMIN_IDS=1692840322,7824886025
DEV_ADMIN_ID=1692840322
```

`DEV_ADMIN_ID` работает только при `APP_ENV=local` и позволяет открыть панель в обычном браузере без Telegram Mini App.

Пароль в `POSTGRES_PASSWORD` должен совпадать с паролем в `DATABASE_URL` и `SYNC_DATABASE_URL`.

## 3. Запуск

```powershell
docker compose up -d --build
docker compose ps
```

Откройте:

- <http://localhost:5173> — административная панель;
- <http://localhost:8000/health> — проверка API.

Проверьте бота командой `/start` в Telegram.

## 4. Логи

```powershell
docker compose logs -f api bot
```

Остановить просмотр: `Ctrl+C`.

## 5. Остановка и обновление

Остановка без удаления базы:

```powershell
docker compose down
```

Повторный запуск:

```powershell
docker compose up -d
```

Обновление проекта:

```powershell
git pull
docker compose up -d --build
```

Не выполняйте `docker compose down -v`, если хотите сохранить PostgreSQL.

## Telegram Mini App при локальной разработке

Telegram требует публичный HTTPS URL. `localhost` подходит только для проверки панели в браузере. Для теста внутри Telegram используйте HTTPS-туннель или тестовый VPS и обновите `PUBLIC_WEBAPP_URL`, `CORS_ORIGINS` и адрес API панели.
