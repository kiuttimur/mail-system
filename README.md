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
├── docker-compose.yml
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
2. `mail-core` просит повторно ввести пароль и создаёт одноразовый token.
3. UI показывает deep-link вида `https://t.me/<bot>?start=<token>`.
4. Пользователь открывает бота и нажимает `Start`.
5. Telegram отправляет webhook в `communicator`.
6. `communicator` извлекает token и вызывает `POST /users/telegram/confirm` в `mail-core`.
7. `mail-core` сохраняет `telegram_chat_id`, `telegram_username` и время подтверждения.

Важно:
- пользователь не вводит чужой `@username` вручную;
- один и тот же Telegram чат можно привязать к нескольким аккаунтам;
- token одноразовый и живёт ограниченное время.

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

