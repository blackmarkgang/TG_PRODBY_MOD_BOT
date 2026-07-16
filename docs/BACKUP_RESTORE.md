# Резервные копии и восстановление

## Что сохраняется

Бэкап содержит PostgreSQL: пользователей, заявки, ответы, роли, настройки, журнал и Telegram `file_id` вложений. Сами медиафайлы остаются в Telegram и в дамп не входят.

## Автоматические копии

Контейнер `backup`:

- создает проверенный custom-format дамп сразу после запуска;
- повторяет бэкап раз в сутки;
- удаляет локальные копии старше 14 дней.

Файлы находятся в `backups/` и исключены из Git.

## Ручной бэкап

Локально:

```powershell
docker compose run --rm backup sh /opt/backup/backup.sh --once
Get-ChildItem backups -Filter *.dump
```

На VPS:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backup sh /opt/backup/backup.sh --once
ls -lh backups/
```

## Проверка дампа без изменения рабочей базы

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec backup pg_restore --list /backups/prodby_TIMESTAMP.dump >/dev/null
echo $?
```

Код `0` означает, что структура дампа читается.

## Восстановление в тестовую базу

Сначала замените имя файла:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec postgres sh -c 'createdb -U "$POSTGRES_USER" prodby_restore_test'
docker compose --env-file .env.production -f docker-compose.prod.yml exec backup sh -c 'pg_restore -U "$PGUSER" -h postgres -d prodby_restore_test /backups/prodby_TIMESTAMP.dump'
docker compose --env-file .env.production -f docker-compose.prod.yml exec postgres sh -c 'psql -U "$POSTGRES_USER" -d prodby_restore_test -c "SELECT count(*) FROM applications;"'
docker compose --env-file .env.production -f docker-compose.prod.yml exec postgres sh -c 'dropdb -U "$POSTGRES_USER" prodby_restore_test'
```

Это не затрагивает рабочую базу из `POSTGRES_DB`.

## Внешняя копия

Папка `backups/` находится на том же VPS. Она не защищает от потери диска или удаления сервера. В production настройте копирование дампов в S3-совместимое хранилище либо резервные снимки у провайдера. Не публикуйте дампы и не добавляйте их в Git.
