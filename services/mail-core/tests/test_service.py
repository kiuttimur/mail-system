"""Тесты mail-core: бизнес-логика писем, Telegram flow и cookie-auth."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.api.letters import get_letter, inbox, mark_read, send_letter, sent
from app.api.users import (
    confirm_telegram_link,
    create_user,
    get_user_by_username,
    get_user_telegram_contact,
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
    UserCreate,
)
from app.ui import web_app

TEST_PASSWORD = "password123"


def create_test_user(db_session, username: str):
    # Хелпер сокращает повторяющуюся регистрацию пользователя в тестах.
    return create_user(UserCreate(username=username, password=TEST_PASSWORD), db_session)


def login_via_http(client, username: str, password: str = TEST_PASSWORD):
    return client.post(
        "/auth/login",
        json={"username": username, "password": password},
    )


def test_health_returns_ok() -> None:
    # Проверяем самый простой smoke-check сервиса:
    # endpoint /health должен отвечать статусом "ok".
    assert health() == {"status": "ok"}


def test_web_form_route_is_registered() -> None:
    # Проверяем, что приложение зарегистрировало веб-форму и auth endpoints.
    paths = {route.path for route in app.routes}
    assert "/" in paths
    assert "/auth/login" in paths
    assert "/auth/logout" in paths
    assert "/auth/me" in paths
    assert "/docs" in paths


def test_web_form_returns_html() -> None:
    # Проверяем, что корневая страница действительно отдаёт HTML.
    response = web_app()

    assert response.media_type == "text/html"
    assert b"Mail Core Web" in response.body


def test_create_and_list_users(db_session) -> None:
    # Проверяем базовый happy path для пользователей.
    alice = create_test_user(db_session, "alice")
    bob = create_test_user(db_session, "bob")

    users = list_users(current_user=alice, db=db_session)

    assert [user.username for user in users] == ["alice", "bob"]
    assert users[0].id == alice.id
    assert users[1].id == bob.id


def test_create_user_stores_hashed_password(db_session) -> None:
    # Проверяем, что пароль не хранится в базе в открытом виде.
    created_user = create_test_user(db_session, "alice")
    stored_user = db_session.get(User, created_user.id)

    assert stored_user is not None
    assert stored_user.password_hash != TEST_PASSWORD
    assert verify_password(TEST_PASSWORD, stored_user.password_hash) is True


def test_get_user_by_username_returns_existing_user(db_session) -> None:
    # Проверяем lookup по логину для формы отправки письма.
    created_user = create_test_user(db_session, "alice")

    loaded_user = get_user_by_username(
        "alice",
        current_user=created_user,
        db=db_session,
    )

    assert loaded_user.id == created_user.id
    assert loaded_user.username == created_user.username


def test_create_user_raises_409_for_duplicate_username(db_session) -> None:
    # Проверяем бизнес-ограничение уникальности username.
    create_test_user(db_session, "alice")

    with pytest.raises(HTTPException) as exc_info:
        create_test_user(db_session, "alice")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "username already exists"


def test_auth_me_requires_cookie(client) -> None:
    # Без cookie-сессии protected endpoint не должен отдавать пользователя.
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "not authenticated"


def test_login_sets_cookie_and_auth_me_returns_user(client, db_session) -> None:
    # Успешный логин должен выдать cookie и открыть доступ к /auth/me.
    created_user = create_test_user(db_session, "alice")

    login_response = login_via_http(client, "alice")
    me_response = client.get("/auth/me")

    assert login_response.status_code == 200
    assert login_response.cookies.get(settings.auth_cookie_name)
    assert me_response.status_code == 200
    assert me_response.json()["id"] == created_user.id
    assert me_response.json()["username"] == created_user.username


def test_login_raises_401_for_invalid_password(client, db_session) -> None:
    # Неверный пароль не должен создавать сессию.
    create_test_user(db_session, "alice")

    response = login_via_http(client, "alice", "wrongpass123")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid username or password"


def test_logout_invalidates_session(client, db_session) -> None:
    # После logout cookie удаляется, а доступ к /auth/me пропадает.
    create_test_user(db_session, "alice")
    login_via_http(client, "alice")

    logout_response = client.post("/auth/logout")
    me_response = client.get("/auth/me")

    assert logout_response.status_code == 200
    assert logout_response.json()["status"] == "logged out"
    assert me_response.status_code == 401


def test_letter_routes_require_cookie(client, db_session) -> None:
    # Пользовательские маршруты писем не должны быть открыты без логина.
    alice = create_test_user(db_session, "alice")

    response = client.get(f"/letters/inbox/{alice.id}")

    assert response.status_code == 401
    assert response.json()["detail"] == "not authenticated"


def test_start_telegram_link_returns_token_and_deep_link(db_session, monkeypatch) -> None:
    # Активной сессии достаточно, чтобы выпустить одноразовый токен и deep-link.
    monkeypatch.setattr(settings, "telegram_bot_username", "mail_system_test_bot")
    user = create_test_user(db_session, "alice")

    result = start_telegram_link(
        user.id,
        current_user=user,
        db=db_session,
    )
    stored_user = db_session.get(User, user.id)

    assert stored_user is not None
    assert result.link_token
    assert stored_user.telegram_link_token == result.link_token
    assert stored_user.telegram_link_token_created_at is not None
    assert result.telegram_bot_username == "mail_system_test_bot"
    assert result.telegram_deep_link == f"https://t.me/mail_system_test_bot?start={result.link_token}"


def test_start_telegram_link_rejects_other_user(db_session) -> None:
    # Нельзя начать привязку Telegram для чужого user_id даже с валидной cookie-сессией.
    alice = create_test_user(db_session, "alice")
    bob = create_test_user(db_session, "bob")

    with pytest.raises(HTTPException) as exc_info:
        start_telegram_link(
            bob.id,
            current_user=alice,
            db=db_session,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "forbidden for another user"


def test_confirm_telegram_link_binds_chat_and_clears_token(db_session) -> None:
    # После подтверждения chat_id сохраняется, а токен очищается.
    user = create_test_user(db_session, "alice")
    start_result = start_telegram_link(
        user.id,
        current_user=user,
        db=db_session,
    )

    linked_user = confirm_telegram_link(
        TelegramLinkConfirm(
            token=start_result.link_token,
            chat_id="chat-1001",
            telegram_username="alice_mail",
        ),
        db=db_session,
    )
    stored_user = db_session.get(User, user.id)

    assert stored_user is not None
    assert linked_user.telegram_username == "alice_mail"
    assert linked_user.telegram_verified_at is not None
    assert stored_user.telegram_chat_id == "chat-1001"
    assert stored_user.telegram_link_token is None
    assert stored_user.telegram_link_token_created_at is None


def test_get_user_telegram_contact_returns_linked_chat_data(db_session) -> None:
    # Internal endpoint для communicator должен отдать chat_id и метаданные Telegram.
    user = create_test_user(db_session, "alice")
    start_result = start_telegram_link(
        user.id,
        current_user=user,
        db=db_session,
    )
    confirm_telegram_link(
        TelegramLinkConfirm(
            token=start_result.link_token,
            chat_id="chat-5555",
            telegram_username="alice_mail",
        ),
        db=db_session,
    )

    contact = get_user_telegram_contact(user.id, db_session)

    assert contact.user_id == user.id
    assert contact.telegram_chat_id == "chat-5555"
    assert contact.telegram_username == "alice_mail"
    assert contact.telegram_verified_at is not None


def test_confirm_telegram_link_rejects_expired_token(db_session, monkeypatch) -> None:
    # Просроченный Telegram token должен стать недействительным и очиститься.
    monkeypatch.setattr(settings, "telegram_link_token_ttl_minutes", 15)
    user = create_test_user(db_session, "alice")
    start_result = start_telegram_link(
        user.id,
        current_user=user,
        db=db_session,
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
            db=db_session,
        )

    expired_user = db_session.get(User, user.id)
    assert expired_user is not None
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "telegram link token expired"
    assert expired_user.telegram_link_token is None
    assert expired_user.telegram_link_token_created_at is None


def test_confirm_telegram_link_allows_same_chat_id_for_multiple_accounts(db_session) -> None:
    # Один и тот же Telegram chat_id можно использовать для нескольких аккаунтов.
    alice = create_test_user(db_session, "alice")
    bob = create_test_user(db_session, "bob")

    alice_link = start_telegram_link(
        alice.id,
        current_user=alice,
        db=db_session,
    )
    bob_link = start_telegram_link(
        bob.id,
        current_user=bob,
        db=db_session,
    )

    confirm_telegram_link(
        TelegramLinkConfirm(
            token=alice_link.link_token,
            chat_id="chat-3003",
            telegram_username="alice_mail",
        ),
        db=db_session,
    )

    linked_bob = confirm_telegram_link(
        TelegramLinkConfirm(
            token=bob_link.link_token,
            chat_id="chat-3003",
            telegram_username="bob_mail",
        ),
        db=db_session,
    )
    alice_user = db_session.get(User, alice.id)
    bob_user = db_session.get(User, bob.id)

    assert alice_user is not None
    assert bob_user is not None
    assert linked_bob.id == bob.id
    assert alice_user.telegram_chat_id == "chat-3003"
    assert bob_user.telegram_chat_id == "chat-3003"


def test_send_letter_and_read_mailboxes(db_session) -> None:
    # Письмо должно попасть во входящие получателя и в отправленные отправителя.
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
            current_user=alice,
            db=db_session,
        )
    )

    loaded_letter = get_letter(letter.id, current_user=alice, db=db_session)
    bob_inbox = inbox(bob.id, False, 50, 0, current_user=bob, db=db_session)
    alice_sent = sent(alice.id, 50, 0, current_user=alice, db=db_session)

    assert loaded_letter.id == letter.id
    assert loaded_letter.is_read is False
    assert [item.id for item in bob_inbox] == [letter.id]
    assert [item.id for item in alice_sent] == [letter.id]


def test_inbox_unread_only_filters_read_letters(db_session) -> None:
    # unread_only=True должен оставлять только непрочитанные письма.
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
            current_user=alice,
            db=db_session,
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
            current_user=alice,
            db=db_session,
        )
    )

    mark_read(
        first_letter.id,
        MarkReadRequest(user_id=bob.id),
        current_user=bob,
        db=db_session,
    )
    unread_letters = inbox(bob.id, True, 50, 0, current_user=bob, db=db_session)

    assert [letter.id for letter in unread_letters] == [second_letter.id]


def test_send_letter_rejects_same_sender_and_recipient(db_session) -> None:
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
                current_user=alice,
                db=db_session,
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "sender_id cannot equal recipient_id"


def test_send_letter_requires_existing_recipient(db_session) -> None:
    # recipient должен существовать в базе.
    alice = create_test_user(db_session, "alice")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            send_letter(
                LetterCreate(
                    sender_id=alice.id,
                    recipient_id=999,
                    subject="Missing recipient",
                    body="No such user",
                ),
                current_user=alice,
                db=db_session,
            )
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "recipient user not found"


def test_send_letter_rejects_spoofed_sender(db_session) -> None:
    # Cookie-сессия должна запрещать отправку письма от чужого sender_id.
    alice = create_test_user(db_session, "alice")
    bob = create_test_user(db_session, "bob")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            send_letter(
                LetterCreate(
                    sender_id=bob.id,
                    recipient_id=alice.id,
                    subject="Spoofed",
                    body="This should be forbidden",
                ),
                current_user=alice,
                db=db_session,
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "sender_id must match current user"


def test_mark_read_allows_only_recipient(db_session) -> None:
    # Отметить письмо прочитанным может только получатель.
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
            current_user=alice,
            db=db_session,
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        mark_read(
            letter.id,
            MarkReadRequest(user_id=alice.id),
            current_user=alice,
            db=db_session,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "only recipient can mark as read"


def test_mark_read_rejects_spoofed_user_id(db_session) -> None:
    # Даже получатель не может подставить в body чужой user_id.
    alice = create_test_user(db_session, "alice")
    bob = create_test_user(db_session, "bob")

    letter = asyncio.run(
        send_letter(
            LetterCreate(
                sender_id=alice.id,
                recipient_id=bob.id,
                subject="Body spoofing",
                body="Current user and user_id must match",
            ),
            current_user=alice,
            db=db_session,
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        mark_read(
            letter.id,
            MarkReadRequest(user_id=alice.id),
            current_user=bob,
            db=db_session,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "user_id must match current user"


def test_mark_read_sets_read_flags_for_recipient(db_session) -> None:
    # Успешный mark_read должен проставить is_read и read_at.
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
            current_user=alice,
            db=db_session,
        )
    )

    updated_letter = mark_read(
        letter.id,
        MarkReadRequest(user_id=bob.id),
        current_user=bob,
        db=db_session,
    )

    assert updated_letter.is_read is True
    assert updated_letter.read_at is not None
