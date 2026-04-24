"""Pydantic-схемы пользователей, включая flow привязки Telegram."""

from datetime import datetime
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class TelegramLinkStartRequest(BaseModel):
    # Пока в проекте нет cookie/JWT-сессий, поэтому чувствительное действие
    # дополнительно подтверждается паролем текущего аккаунта.
    password: str = Field(min_length=8, max_length=128)


class TelegramLinkStartOut(BaseModel):
    # link_token нужен communicator/боту, а deep-link удобен UI.
    link_token: str
    expires_at: datetime
    telegram_bot_username: str | None
    telegram_deep_link: str | None


class TelegramLinkConfirm(BaseModel):
    token: str = Field(min_length=8, max_length=64)
    chat_id: str = Field(min_length=1, max_length=64)
    telegram_username: str | None = Field(default=None, max_length=255)


class TelegramContactOut(BaseModel):
    # Внутренний ответ для communicator: достаточно chat_id и статуса привязки.
    user_id: int
    telegram_chat_id: str | None
    telegram_username: str | None
    telegram_verified_at: datetime | None


class UserOut(BaseModel):
    id: int
    username: str
    telegram_username: str | None
    telegram_verified_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
