"""Pydantic-схемы communicator для событий и Telegram webhook."""

from datetime import datetime

from pydantic import BaseModel, Field


class NewLetterEvent(BaseModel):
    letter_id: int
    recipient_id: int
    subject: str = Field(min_length=1, max_length=120)


class NewLetterNotificationResult(BaseModel):
    delivered_to_console: bool
    delivered_to_telegram: bool
    detail: str


class MailCoreTelegramContact(BaseModel):
    user_id: int
    telegram_chat_id: str | None
    telegram_username: str | None
    telegram_verified_at: datetime | None


class MailCoreUser(BaseModel):
    id: int
    username: str
    telegram_username: str | None
    telegram_verified_at: datetime | None
    created_at: datetime


class TelegramChat(BaseModel):
    id: int | str


class TelegramFromUser(BaseModel):
    username: str | None = None


class TelegramMessage(BaseModel):
    text: str | None = None
    chat: TelegramChat
    from_user: TelegramFromUser | None = Field(default=None, alias="from")

    model_config = {"populate_by_name": True}


class TelegramUpdate(BaseModel):
    update_id: int | None = None
    message: TelegramMessage | None = None


class TelegramWebhookResult(BaseModel):
    status: str
    detail: str
