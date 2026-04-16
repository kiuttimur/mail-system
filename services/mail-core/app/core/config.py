"""Чтение настроек приложения из .env и переменных окружения."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env используется только как локальный источник конфигурации;
    # реальные значения можно переопределять переменными окружения.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///./mail_core.db"

    communicator_url: str | None = None
    communicator_timeout_seconds: float = 2.0


settings = Settings()
