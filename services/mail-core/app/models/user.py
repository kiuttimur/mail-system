"""SQLAlchemy-модель пользователя почтовой системы."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    # Храним только результат хеширования, а не исходный пароль.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Подтверждённая привязка Telegram-чата, в который можно отправлять уведомления.
    # Один и тот же chat_id может быть привязан к нескольким аккаунтам одного пользователя.
    telegram_chat_id: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
        nullable=True,
    )
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Одноразовый токен для безопасной привязки через Telegram bot /start.
    telegram_link_token: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=True,
    )
    telegram_link_token_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    telegram_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
