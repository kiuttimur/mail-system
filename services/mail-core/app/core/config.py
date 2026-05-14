"""Чтение настроек приложения из .env и переменных окружения."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env используется только как локальный источник конфигурации;
    # реальные значения можно переопределять переменными окружения.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///./mail_core.db"

    communicator_url: str | None = None
    communicator_timeout_seconds: float = 2.0
    telegram_bot_username: str | None = None
    telegram_link_token_ttl_minutes: int = 15
    auth_cookie_name: str = "mail_core_session"
    auth_session_ttl_minutes: int = 60 * 24 * 7
    auth_cookie_secure: bool = False
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "lax"


settings = Settings()
