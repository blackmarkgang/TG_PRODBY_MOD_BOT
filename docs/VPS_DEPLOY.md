# Развертывание на Ubuntu VPS

Инструкция рассчитана на Ubuntu 22.04/24.04, отдельный VPS и один поддомен, например `bot.example.com`.

## 1. Что подготовить

- VPS: рекомендуется 2 vCPU, 2 ГБ RAM, 25 ГБ SSD;
- публичный IPv4;
- SSH-пользователь с `sudo`;
- A-запись `bot.example.com` на IPv4 VPS;
- открытые входящие порты 80 и 443;
- токен бота, Telegram ID группы и администраторов.

Проверить DNS с компьютера:

```powershell
Resolve-DnsName bot.example.com
```

Ответ должен содержать IPv4 нового VPS.

## 2. Установка Docker на VPS

Подключитесь по SSH и выполните:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"
```

Переподключитесь по SSH и проверьте:

```bash
docker --version
docker compose version
```

## 3. Клонирование

```bash
git clone https://github.com/blackmarkgang/TG_PRODBY_MOD_BOT.git
cd TG_PRODBY_MOD_BOT
cp .env.production.example .env.production
chmod 600 .env.production
```

## 4. Production-переменные

Создайте URL-безопасный пароль:

```bash
openssl rand -hex 24
nano .env.production
```

Заполните:

```dotenv
APP_ENV=production
APP_DOMAIN=bot.example.com
PUBLIC_WEBAPP_URL=https://bot.example.com
API_BASE_URL=https://bot.example.com/api
CORS_ORIGINS=https://bot.example.com

BOT_TOKEN=токен_из_BotFather
TELEGRAM_GROUP_ID=-1001234567890
ADMIN_IDS=1692840322,7824886025

POSTGRES_PASSWORD=один_случайный_пароль
DATABASE_URL=postgresql+asyncpg://prodby:один_случайный_пароль@postgres:5432/prodby
SYNC_DATABASE_URL=postgresql+psycopg://prodby:один_случайный_пароль@postgres:5432/prodby
```

Пароль PostgreSQL во всех трех строках должен совпадать. Не добавляйте `DEV_ADMIN_ID` в production-файл.

## 5. Firewall

Сначала разрешите фактический SSH-порт, затем HTTP/HTTPS. Для стандартного SSH:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

Если SSH работает не на порту 22, разрешите этот порт до включения UFW. PostgreSQL наружу не публикуется.

## 6. Проверка и запуск

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

Caddy автоматически запросит HTTPS-сертификат после того, как DNS начнет указывать на VPS.

Проверка:

```bash
curl -fsS https://bot.example.com/api/health
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=100 caddy api bot
```

Health check должен вернуть JSON со статусом `ok`.

## 7. Telegram

1. Добавьте бота администратором Telegram-группы.
2. Выдайте права на удаление сообщений, ограничения участников и создание пригласительных ссылок.
3. В BotFather укажите `https://bot.example.com` как URL Mini App/Menu Button, если используется постоянная кнопка меню.
4. Откройте личный чат с ботом и отправьте `/admin`.
5. Проверьте заявки, вложения, назначение ролей и ограничения форумных тем.

## 8. Обновление

Сначала создайте ручной бэкап:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backup sh /opt/backup/backup.sh --once
git pull --ff-only
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

Миграции Alembic выполняются автоматически контейнером `migrate` до запуска API и бота.

## 9. Диагностика

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f api bot caddy
df -h
free -h
```

Логи Docker ограничены тремя файлами по 10 МБ на контейнер.
