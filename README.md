# mail-system

Учебная монорепа с двумя Python-микросервисами для "почтового" общения по REST API.
Это не realtime-мессенджер: здесь есть пользователи, письма с темой и текстом, входящие, отправленные и отметка "прочитано".

**Сервисы**
- `services/mail-core` — основной backend: пользователи, письма, веб-форма, REST API, миграции.
- `services/communicator` — сервис уведомлений: принимает событие о новом письме, логирует его и при настройке отправляет уведомление в Telegram.

## Что Уже Умеет Проект

- регистрация и вход по логину/паролю;
- хранение пароля только в виде `password_hash`;
- отправка и чтение писем;
- разделение входящих на прочитанные и непрочитанные;
- привязка Telegram через одноразовый token;
- уведомление о новом письме через `communicator`;
- Swagger UI у обоих сервисов;
- Alembic-миграции для `mail-core`;
- idempotent `seed.py` с тестовыми пользователями и письмами;
- тесты для `mail-core` и `communicator`.

## Структура Репозитория

```text
mail-system/
├── Caddyfile
├── docker-compose.yml
├── docker-compose.vps.yml
├── README.md
└── services/
    ├── communicator/
    │   ├── app/
    │   ├── Dockerfile
    │   ├── requirements.txt
    │   └── tests/
    └── mail-core/
        ├── alembic/
        ├── app/
        ├── Dockerfile
        ├── requirements.txt
        ├── seed.py
        └── tests/
```

## Как Устроены Сервисы

**mail-core**
- `app/main.py` — собирает FastAPI-приложение.
- `app/api/` — REST-роуты пользователей, писем и входа.
- `app/core/` — конфиг, БД, безопасность.
- `app/models/` — SQLAlchemy-модели `users` и `letters`.
- `app/schemas/` — Pydantic-схемы запросов и ответов.
- `app/services/communicator_client.py` — best-effort вызов второго сервиса.
- `app/templates/index.html` и `app/ui.py` — простая веб-форма поверх API.
- `alembic/` — миграции БД.

**communicator**
- `app/main.py` — FastAPI-приложение.
- `app/api/notifications.py` — принимает событие `new-letter` от `mail-core`.
- `app/api/telegram.py` — принимает Telegram webhook и завершает привязку.
- `app/services/mail_core_client.py` — ходит в `mail-core` за контактами и подтверждением привязки.
- `app/services/telegram_client.py` — отправляет сообщения через Telegram Bot API.

## Как Работает Сценарий С Письмом

1. Пользователь отправляет письмо в `mail-core`.
2. `mail-core` валидирует sender/recipient, сохраняет письмо в БД и возвращает ответ.
3. После сохранения `mail-core` best-effort вызывает `communicator` по `POST /notify/new-letter`.
4. `communicator` всегда пишет событие в консоль.
5. Если у получателя есть привязанный Telegram, `communicator` отправляет уведомление в Telegram Bot API.

## Как Работает Привязка Telegram

1. Пользователь входит в аккаунт и нажимает `Привязать Telegram`.
2. `mail-core` использует активную cookie-сессию и создаёт одноразовый token.
3. UI показывает deep-link вида `https://t.me/<bot>?start=<token>`.
4. Пользователь открывает бота и нажимает `Start`.
5. Telegram отправляет webhook в `communicator`.
6. `communicator` извлекает token и вызывает `POST /users/telegram/confirm` в `mail-core`.
7. `mail-core` сохраняет `telegram_chat_id`, `telegram_username` и время подтверждения.

Важно:
- пользователь не вводит чужой `@username` вручную;
- один и тот же Telegram чат можно привязать к нескольким аккаунтам;
- token одноразовый и живёт ограниченное время.

## Cloudflare Tunnel

`Cloudflare Tunnel` нужен для локальной разработки, когда `communicator` запущен у тебя на `localhost`, а Telegram должен прислать webhook извне.

Почему без него не работает webhook:
- Telegram не может обратиться к `http://127.0.0.1:8002`;
- `localhost` виден только на твоей машине;
- Telegram Bot API нужен публичный HTTPS URL.

Идея такая:
- `mail-core` остаётся локально на `http://127.0.0.1:8001`
- `communicator` остаётся локально на `http://127.0.0.1:8002`
- `cloudflared` открывает временный публичный адрес вида `https://something.trycloudflare.com`
- webhook Telegram указывает на `https://something.trycloudflare.com/telegram/webhook`



### Как поднять tunnel

1. Убедись, что запущен `communicator` на `8002`.

2. Установи `cloudflared`:

Через `curl`:

```bash
cd /tmp
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
mkdir -p ~/.local/bin
mv cloudflared ~/.local/bin/cloudflared
export PATH="$HOME/.local/bin:$PATH"
cloudflared --version
```

Или через `wget`:

```bash
cd /tmp
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O cloudflared
chmod +x cloudflared
mkdir -p ~/.local/bin
mv cloudflared ~/.local/bin/cloudflared
export PATH="$HOME/.local/bin:$PATH"
cloudflared --version
```

3. В отдельном терминале запусти tunnel:

```bash
export PATH="$HOME/.local/bin:$PATH"
cloudflared tunnel --url http://localhost:8002
```

4. `cloudflared` покажет временный публичный URL, например:

```text
https://random-name.trycloudflare.com
```

Этот терминал нельзя закрывать, пока нужен webhook.

### Как подключить Telegram webhook

Возьми bot token из `services/communicator/.env` и выполни:

```bash
export TOKEN="$(grep '^TELEGRAM_BOT_TOKEN=' /workspaces/mail-system/services/communicator/.env | cut -d= -f2-)"
export PUBLIC_URL="https://YOUR-TRYCLOUDFLARE-URL"

curl -X POST "https://api.telegram.org/bot$TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"$PUBLIC_URL/telegram/webhook\",\"drop_pending_updates\":true}"
```

После этого можно проверить:

```bash
curl "https://api.telegram.org/bot$TOKEN/getWebhookInfo"
```

Там должно быть:
- `url` с твоим `trycloudflare` адресом;
- без `last_error_message`, либо без ошибок;
- `pending_update_count` может быть больше нуля, это нормально.

### Как использовать в нашем проекте

Полный сценарий:

1. Запусти `mail-core`
2. Запусти `communicator`
3. Подними `cloudflared tunnel --url http://localhost:8002`
4. Поставь webhook через `setWebhook`
5. В `mail-core` нажми `Привязать Telegram`
6. Нажми ссылку на бота и в Telegram нажми `Start`
7. Telegram отправит webhook в `communicator`
8. `communicator` вызовет `mail-core` и завершит привязку
9. После отправки письма `communicator` сможет отправить уведомление в Telegram

### Типичные проблемы

- Если `getWebhookInfo` показывает `Wrong response from the webhook: 530 <none>`, значит старый tunnel уже умер или URL больше не существует.
- Если ты перезапустил `cloudflared`, URL почти наверняка изменился, и webhook надо поставить заново.
- Если закрыть терминал с `cloudflared`, Telegram перестанет видеть твой локальный `communicator`.
- Если всё работает локально, но бот не получает `Start`, проверь, что webhook указывает именно на новый `trycloudflare` URL.
- Если deep-link на бота открывает не чат, а просто сайт Telegram, можно вручную открыть бота и отправить `/start <token>`.

## Docker Compose

Можно поднять всё одной командой:

```bash
docker compose up --build
```

Что делает compose:
- собирает оба сервиса из `Dockerfile`;
- запускает `mail-core` и `communicator` в одной сети;
- автоматически прокидывает `mail-core -> communicator` и `communicator -> mail-core`;
- хранит SQLite в volume `mail_core_data`;
- при старте `mail-core` автоматически делает `alembic upgrade head`.

После запуска будут доступны:
- `mail-core`: `http://127.0.0.1:8001`
- `communicator`: `http://127.0.0.1:8002`
- `mail-core /docs`: `http://127.0.0.1:8001/docs`
- `communicator /docs`: `http://127.0.0.1:8002/docs`

Важно:
- в текущем `docker-compose.yml` порты сервисов привязаны к `127.0.0.1`;
- это безопаснее для VPS: наружу их не публикуем напрямую;
- для публичного HTTP/HTTPS поверх этих сервисов используй `Caddy`.

Остановка:

```bash
docker compose down
```

Удалить ещё и данные volume:

```bash
docker compose down -v
```

Запустить seed внутри контейнера:

```bash
docker compose exec mail-core python seed.py
```

## Caddy На VPS

Для хостинга на VPS проекту добавлен отдельный compose-слой `docker-compose.vps.yml`.
Он поднимает `Caddy`, который:
- слушает `80` и `443`;
- автоматически даёт HTTPS для домена;
- проксирует `https://<домен>/telegram/*` в `communicator`;
- проксирует всё остальное в `mail-core`.

### Что подготовить

1. У домена должна быть `A`-запись на IP VPS.

2. В корне проекта на VPS создай файл `.env` для docker compose:

```env
CADDY_HOST=your-domain.example
```

Пример:

```env
CADDY_HOST=mail.example.ru
```

### Как поднять

На VPS из корня проекта выполни:

```bash
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build
```

Проверить контейнеры:

```bash
docker compose -f docker-compose.yml -f docker-compose.vps.yml ps
```

Проверить логи `Caddy`:

```bash
docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f caddy
```

### Как работает маршрутизация

- `https://<домен>/` -> `mail-core`
- `https://<домен>/health` -> `mail-core`
- `https://<домен>/telegram/webhook` -> `communicator`

### Telegram Webhook Для VPS

Когда домен уже смотрит на VPS и `Caddy` поднялся, webhook ставится уже на боевой URL:

```bash
export TOKEN="$(grep '^TELEGRAM_BOT_TOKEN=' services/communicator/.env | cut -d= -f2-)"
export PUBLIC_URL="https://YOUR-DOMAIN"

curl -X POST "https://api.telegram.org/bot$TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"$PUBLIC_URL/telegram/webhook\",\"drop_pending_updates\":true,\"allowed_updates\":[\"message\"]}"
```

Проверка:

```bash
curl "https://api.telegram.org/bot$TOKEN/getWebhookInfo"
```

### Остановка

```bash
docker compose -f docker-compose.yml -f docker-compose.vps.yml down
```

## Тесты

`mail-core`

```bash
cd services/mail-core
source .venv/bin/activate
python -m pytest tests -q
```

`communicator`

```bash
cd services/communicator
source .venv/bin/activate
python -m pytest tests -q
```

## Замечание
- Если бот пишет `telegram link token not found`, значит token уже истёк, был заменён новым или уже использован.
