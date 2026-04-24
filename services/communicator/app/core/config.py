"""Настройки communicator из .env и переменных окружения."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    mail_core_url: str = "http://127.0.0.1:8001"
    telegram_bot_token: str | None = None
    telegram_request_timeout_seconds: float = 5.0
    communicator_log_prefix: str = "[COMMUNICATOR]"


settings = Settings()
