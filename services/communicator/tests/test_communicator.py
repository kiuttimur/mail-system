"""Тесты communicator: уведомления о письмах и Telegram webhook."""

from __future__ import annotations

import asyncio

from app.api.notifications import notify_new_letter
from app.api.telegram import telegram_webhook
from app.main import app, health
from app.schemas.communicator import (
    MailCoreTelegramContact,
    MailCoreUser,
    NewLetterEvent,
    TelegramUpdate,
)


def test_health_returns_ok() -> None:
    # Проверяем базовый smoke-check communicator.
    assert health() == {"status": "ok"}


def test_routes_are_registered() -> None:
    # Проверяем, что FastAPI зарегистрировал ключевые роуты.
    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/notify/new-letter" in paths
    assert "/telegram/webhook" in paths
    assert "/docs" in paths


def test_notify_new_letter_logs_without_telegram_link(monkeypatch) -> None:
    # Проверяем fallback-сценарий:
    # communicator должен принять событие и отдать понятный ответ,
    # даже если у получателя еще нет привязанного Telegram.
    async def fake_get_telegram_contact(user_id: int) -> MailCoreTelegramContact:
        return MailCoreTelegramContact(
            user_id=user_id,
            telegram_chat_id=None,
            telegram_username=None,
            telegram_verified_at=None,
        )

    monkeypatch.setattr("app.api.notifications.get_telegram_contact", fake_get_telegram_contact)

    result = asyncio.run(
        notify_new_letter(
            NewLetterEvent(letter_id=10, recipient_id=7, subject="Hello"),
        )
    )

    assert result.delivered_to_console is True
    assert result.delivered_to_telegram is False
    assert result.detail == "recipient has no linked telegram chat"


def test_notify_new_letter_sends_telegram_when_chat_linked(monkeypatch) -> None:
    # Проверяем happy path:
    # если mail-core отдал chat_id, communicator пытается отправить сообщение в Telegram.
    calls: list[tuple[str | int, str]] = []

    async def fake_get_telegram_contact(user_id: int) -> MailCoreTelegramContact:
        return MailCoreTelegramContact(
            user_id=user_id,
            telegram_chat_id="chat-42",
            telegram_username="alice_mail",
            telegram_verified_at=None,
        )

    async def fake_send_text_message(chat_id: str | int, text: str) -> bool:
        calls.append((chat_id, text))
        return True

    monkeypatch.setattr("app.api.notifications.get_telegram_contact", fake_get_telegram_contact)
    monkeypatch.setattr("app.api.notifications.send_text_message", fake_send_text_message)

    result = asyncio.run(
        notify_new_letter(
            NewLetterEvent(letter_id=11, recipient_id=7, subject="Status update"),
        )
    )

    assert result.delivered_to_console is True
    assert result.delivered_to_telegram is True
    assert result.detail == "telegram notification sent"
    assert calls == [("chat-42", "New letter #11\nSubject: Status update")]


def test_telegram_webhook_confirms_link_and_replies(monkeypatch) -> None:
    # Проверяем основной flow Telegram /start:
    # communicator должен подтвердить link token через mail-core и ответить в чат.
    replies: list[tuple[str | int, str]] = []

    async def fake_confirm_telegram_link(token: str, chat_id: str, telegram_username: str | None) -> MailCoreUser:
        assert token == "token-123"
        assert chat_id == "9001"
        assert telegram_username == "alice_mail"
        return MailCoreUser.model_validate(
            {
                "id": 1,
                "username": "alice",
                "telegram_username": "alice_mail",
                "telegram_verified_at": "2026-04-23T12:00:00Z",
                "created_at": "2026-04-23T11:00:00Z",
            }
        )

    async def fake_send_text_message(chat_id: str | int, text: str) -> bool:
        replies.append((chat_id, text))
        return True

    monkeypatch.setattr("app.api.telegram.confirm_telegram_link", fake_confirm_telegram_link)
    monkeypatch.setattr("app.api.telegram.send_text_message", fake_send_text_message)

    result = asyncio.run(
        telegram_webhook(
            TelegramUpdate.model_validate(
                {
                    "update_id": 1,
                    "message": {
                        "text": "/start token-123",
                        "chat": {"id": 9001},
                        "from": {"username": "alice_mail"},
                    },
                }
            )
        )
    )

    assert result.status == "linked"
    assert result.detail == "telegram linked to user alice"
    assert replies == [(9001, "Telegram linked to mail account alice.")]


def test_telegram_webhook_ignores_non_start_messages() -> None:
    # Проверяем, что communicator не пытается подтверждать привязку
    # по любому сообщению, кроме команды /start.
    result = asyncio.run(
        telegram_webhook(
            TelegramUpdate.model_validate(
                {
                    "update_id": 2,
                    "message": {
                        "text": "hello",
                        "chat": {"id": 9002},
                        "from": {"username": "bob_mail"},
                    },
                }
            )
        )
    )

    assert result.status == "ignored"
    assert result.detail == "update does not contain /start command"
