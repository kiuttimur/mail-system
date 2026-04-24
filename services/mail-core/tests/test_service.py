"""Набор unit/smoke-тестов для основной логики mail-core."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.api.auth import login
from app.api.letters import get_letter, inbox, mark_read, send_letter, sent
from app.api.users import (
    confirm_telegram_link,
    create_user,
    get_user,
    get_user_telegram_contact,
    get_user_by_username,
    list_users,
    start_telegram_link,
)
from app.core.config import settings
from app.core.security import verify_password
from app.main import app, health
from app.models.user import User
from app.schemas.letter import LetterCreate, MarkReadRequest
from app.schemas.user import (
    TelegramLinkConfirm,
    TelegramLinkStartRequest,
    UserCreate,
    UserLogin,
)
from app.ui import web_app

TEST_PASSWORD = "password123"


def create_test_user(db_session, username: str):
    # Хелпер сокращает повторяющуюся регистрацию пользователя в тестах.
    return create_user(UserCreate(username=username, password=TEST_PASSWORD), db_session)


def test_health_returns_ok() -> None:
    # Проверяем самый простой smoke-check сервиса:
    # endpoint /health должен отвечать статусом "ok".
    assert health() == {"status": "ok"}


def test_web_form_route_is_registered() -> None:
    # Проверяем, что приложение зарегистрировало веб-форму на "/"
    # и Swagger на "/docs", а также endpoint логина.
    paths = {route.path for route in app.routes}
    assert "/" in paths
    assert "/auth/login" in paths
    assert "/docs" in paths


def test_web_form_returns_html() -> None:
    # Проверяем, что корневая страница действительно отдаёт HTML,
    # а не пустой ответ или JSON.
    response = web_app()

    assert response.media_type == "text/html"
    assert b"Mail Core Web" in response.body


def test_create_and_list_users(db_session) -> None:
    # Проверяем базовый happy path для пользователей:
    # можно создать нескольких пользователей и потом получить их списком.
    alice = create_test_user(db_session, "alice")
    bob = create_test_user(db_session, "bob")

    users = list_users(db_session)

    assert [user.username for user in users] == ["alice", "bob"]
    assert users[0].id == alice.id
    assert users[1].id == bob.id


def test_create_user_stores_hashed_password(db_session) -> None:
    # Проверяем, что пароль не хранится в базе в открытом виде:
    # в users сохраняется password_hash, который можно верифицировать.
    created_user = create_test_user(db_session, "alice")
    stored_user = db_session.get(User, created_user.id)

    assert stored_user is not None
    assert stored_user.password_hash != TEST_PASSWORD
    assert verify_password(TEST_PASSWORD, stored_user.password_hash) is True


def test_get_user_by_username_returns_existing_user(db_session) -> None:
    # Проверяем lookup по логину:
    # он нужен форме отправки письма, где получатель указывается по username.
    created_user = create_test_user(db_session, "alice")

    loaded_user = get_user_by_username("alice", db_session)

    assert loaded_user.id == created_user.id
    assert loaded_user.username == created_user.username


def test_create_user_raises_409_for_duplicate_username(db_session) -> None:
    # Проверяем бизнес-ограничение уникальности username:
    # второй пользователь с тем же именем должен давать 409.
    create_test_user(db_session, "alice")

    with pytest.raises(HTTPException) as exc_info:
        create_test_user(db_session, "alice")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "username already exists"


def test_get_user_raises_404_when_user_missing(db_session) -> None:
    # Проверяем сценарий "пользователь не найден":
    # сервис должен вернуть 404, а не пустой объект.
    with pytest.raises(HTTPException) as exc_info:
        get_user(999, db_session)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "user not found"


def test_get_user_by_username_raises_404_when_user_missing(db_session) -> None:
    # Проверяем, что при отправке письма на несуществующий логин
    # сервер корректно возвращает 404.
    with pytest.raises(HTTPException) as exc_info:
        get_user_by_username("missing_user", db_session)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "user not found"


def test_login_returns_user_for_valid_credentials(db_session) -> None:
    # Проверяем успешный вход:
    # если username и пароль верные, сервис возвращает пользователя.
    created_user = create_test_user(db_session, "alice")

    logged_in_user = login(
        UserLogin(username="alice", password=TEST_PASSWORD),
        db_session,
    )

    assert logged_in_user.id == created_user.id
    assert logged_in_user.username == created_user.username


def test_login_raises_401_for_invalid_password(db_session) -> None:
    # Проверяем ошибку входа:
    # неверный пароль должен приводить к 401.
    create_test_user(db_session, "alice")

    with pytest.raises(HTTPException) as exc_info:
        login(UserLogin(username="alice", password="wrongpass123"), db_session)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "invalid username or password"


def test_start_telegram_link_returns_token_and_deep_link(db_session, monkeypatch) -> None:
    # Проверяем старт привязки Telegram:
    # при правильном пароле сервис должен выдать одноразовый токен
    # и deep-link для будущего Telegram-бота.
    monkeypatch.setattr(settings, "telegram_bot_username", "mail_system_test_bot")
    user = create_test_user(db_session, "alice")

    result = start_telegram_link(
        user.id,
        TelegramLinkStartRequest(password=TEST_PASSWORD),
        db_session,
    )
    stored_user = db_session.get(User, user.id)

    assert stored_user is not None
    assert result.link_token
    assert stored_user.telegram_link_token == result.link_token
    assert stored_user.telegram_link_token_created_at is not None
    assert result.telegram_bot_username == "mail_system_test_bot"
    assert result.telegram_deep_link == f"https://t.me/mail_system_test_bot?start={result.link_token}"


def test_start_telegram_link_rejects_invalid_password(db_session) -> None:
    # Проверяем защиту старта привязки:
    # без подтверждения паролем нельзя выпустить токен для Telegram.
    user = create_test_user(db_session, "alice")

    with pytest.raises(HTTPException) as exc_info:
        start_telegram_link(
            user.id,
            TelegramLinkStartRequest(password="wrongpass123"),
            db_session,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "invalid password"


def test_confirm_telegram_link_binds_chat_and_clears_token(db_session) -> None:
    # Проверяем успешное подтверждение Telegram:
    # подтверждённый chat_id и username сохраняются в профиле,
    # а одноразовый токен после использования очищается.
    user = create_test_user(db_session, "alice")
    start_result = start_telegram_link(
        user.id,
        TelegramLinkStartRequest(password=TEST_PASSWORD),
        db_session,
    )

    linked_user = confirm_telegram_link(
        TelegramLinkConfirm(
            token=start_result.link_token,
            chat_id="chat-1001",
            telegram_username="alice_mail",
        ),
        db_session,
    )
    stored_user = db_session.get(User, user.id)

    assert stored_user is not None
    assert linked_user.telegram_username == "alice_mail"
    assert linked_user.telegram_verified_at is not None
    assert stored_user.telegram_chat_id == "chat-1001"
    assert stored_user.telegram_link_token is None
    assert stored_user.telegram_link_token_created_at is None


def test_get_user_telegram_contact_returns_linked_chat_data(db_session) -> None:
    # Проверяем внутренний endpoint для communicator:
    # после подтверждения привязки сервис должен отдать chat_id и метаданные Telegram.
    user = create_test_user(db_session, "alice")
    start_result = start_telegram_link(
        user.id,
        TelegramLinkStartRequest(password=TEST_PASSWORD),
        db_session,
    )
    confirm_telegram_link(
        TelegramLinkConfirm(
            token=start_result.link_token,
            chat_id="chat-5555",
            telegram_username="alice_mail",
        ),
        db_session,
    )

    contact = get_user_telegram_contact(user.id, db_session)

    assert contact.user_id == user.id
    assert contact.telegram_chat_id == "chat-5555"
    assert contact.telegram_username == "alice_mail"
    assert contact.telegram_verified_at is not None


def test_confirm_telegram_link_rejects_expired_token(db_session, monkeypatch) -> None:
    # Проверяем срок жизни токена:
    # если Telegram подтвердил ссылку слишком поздно, токен должен
    # стать недействительным и больше не оставаться в профиле.
    monkeypatch.setattr(settings, "telegram_link_token_ttl_minutes", 15)
    user = create_test_user(db_session, "alice")
    start_result = start_telegram_link(
        user.id,
        TelegramLinkStartRequest(password=TEST_PASSWORD),
        db_session,
    )

    stored_user = db_session.get(User, user.id)
    assert stored_user is not None
    stored_user.telegram_link_token_created_at = datetime.now(timezone.utc) - timedelta(
        minutes=settings.telegram_link_token_ttl_minutes + 1
    )
    db_session.add(stored_user)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        confirm_telegram_link(
            TelegramLinkConfirm(
                token=start_result.link_token,
                chat_id="chat-2002",
                telegram_username="alice_mail",
            ),
            db_session,
        )

    expired_user = db_session.get(User, user.id)
    assert expired_user is not None
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "telegram link token expired"
    assert expired_user.telegram_link_token is None
    assert expired_user.telegram_link_token_created_at is None


def test_confirm_telegram_link_allows_same_chat_id_for_multiple_accounts(db_session) -> None:
    # Проверяем новое правило привязки:
    # один и тот же Telegram chat_id можно использовать для нескольких аккаунтов
    # одного и того же пользователя.
    alice = create_test_user(db_session, "alice")
    bob = create_test_user(db_session, "bob")

    alice_link = start_telegram_link(
        alice.id,
        TelegramLinkStartRequest(password=TEST_PASSWORD),
        db_session,
    )
    bob_link = start_telegram_link(
        bob.id,
        TelegramLinkStartRequest(password=TEST_PASSWORD),
        db_session,
    )

    confirm_telegram_link(
        TelegramLinkConfirm(
            token=alice_link.link_token,
            chat_id="chat-3003",
            telegram_username="alice_mail",
        ),
        db_session,
    )

    linked_bob = confirm_telegram_link(
        TelegramLinkConfirm(
            token=bob_link.link_token,
            chat_id="chat-3003",
            telegram_username="bob_mail",
        ),
        db_session,
    )
    alice_user = db_session.get(User, alice.id)
    bob_user = db_session.get(User, bob.id)

    assert alice_user is not None
    assert bob_user is not None
    assert linked_bob.id == bob.id
    assert alice_user.telegram_chat_id == "chat-3003"
    assert bob_user.telegram_chat_id == "chat-3003"


def test_send_letter_and_read_mailboxes(db_session) -> None:
    # Проверяем основной сценарий писем:
    # письмо создаётся, находится по id, попадает во входящие получателя
    # и в отправленные отправителя.
    alice = create_test_user(db_session, "alice")
    bob = create_test_user(db_session, "bob")

    letter = asyncio.run(
        send_letter(
            LetterCreate(
                sender_id=alice.id,
                recipient_id=bob.id,
                subject="Hello",
                body="How are you?",
            ),
            db_session,
        )
    )

    loaded_letter = get_letter(letter.id, db_session)
    bob_inbox = inbox(bob.id, False, 50, 0, db_session)
    alice_sent = sent(alice.id, 50, 0, db_session)

    assert loaded_letter.id == letter.id
    assert loaded_letter.is_read is False
    assert [item.id for item in bob_inbox] == [letter.id]
    assert [item.id for item in alice_sent] == [letter.id]


def test_inbox_unread_only_filters_read_letters(db_session) -> None:
    # Проверяем фильтр unread_only:
    # после отметки одного письма как прочитанного
    # во входящих с unread_only=True должно остаться только непрочитанное.
    alice = create_test_user(db_session, "alice")
    bob = create_test_user(db_session, "bob")

    first_letter = asyncio.run(
        send_letter(
            LetterCreate(
                sender_id=alice.id,
                recipient_id=bob.id,
                subject="First",
                body="First body",
            ),
            db_session,
        )
    )
    second_letter = asyncio.run(
        send_letter(
            LetterCreate(
                sender_id=alice.id,
                recipient_id=bob.id,
                subject="Second",
                body="Second body",
            ),
            db_session,
        )
    )

    mark_read(first_letter.id, MarkReadRequest(user_id=bob.id), db_session)
    unread_letters = inbox(bob.id, True, 50, 0, db_session)

    assert [letter.id for letter in unread_letters] == [second_letter.id]


def test_send_letter_rejects_same_sender_and_recipient(db_session) -> None:
    # Проверяем защиту от отправки письма самому себе:
    # sender_id и recipient_id не должны совпадать.
    alice = create_test_user(db_session, "alice")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            send_letter(
                LetterCreate(
                    sender_id=alice.id,
                    recipient_id=alice.id,
                    subject="Oops",
                    body="This should fail",
                ),
                db_session,
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "sender_id cannot equal recipient_id"


def test_send_letter_requires_existing_users(db_session) -> None:
    # Проверяем, что письмо нельзя создать с несуществующими пользователями:
    # сервис должен явно вернуть 404 по sender/recipient.
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            send_letter(
                LetterCreate(
                    sender_id=1,
                    recipient_id=2,
                    subject="Missing users",
                    body="No users in database",
                ),
                db_session,
            )
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "sender user not found"


def test_mark_read_allows_only_recipient(db_session) -> None:
    # Проверяем правило доступа:
    # отметить письмо прочитанным может только получатель, не отправитель.
    alice = create_test_user(db_session, "alice")
    bob = create_test_user(db_session, "bob")

    letter = asyncio.run(
        send_letter(
            LetterCreate(
                sender_id=alice.id,
                recipient_id=bob.id,
                subject="Private",
                body="Recipient should mark this read",
            ),
            db_session,
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        mark_read(letter.id, MarkReadRequest(user_id=alice.id), db_session)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "only recipient can mark as read"


def test_mark_read_sets_read_flags_for_recipient(db_session) -> None:
    # Проверяем успешный сценарий mark_read:
    # письмо становится прочитанным и получает timestamp в read_at.
    alice = create_test_user(db_session, "alice")
    bob = create_test_user(db_session, "bob")

    letter = asyncio.run(
        send_letter(
            LetterCreate(
                sender_id=alice.id,
                recipient_id=bob.id,
                subject="Status update",
                body="Please read this letter",
            ),
            db_session,
        )
    )

    updated_letter = mark_read(letter.id, MarkReadRequest(user_id=bob.id), db_session)

    assert updated_letter.is_read is True
    assert updated_letter.read_at is not None
