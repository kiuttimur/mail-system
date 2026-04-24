"""Эндпоинты работы с пользователями: регистрация и чтение профилей."""

from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.core.db import get_db
from app.models.user import User
from app.schemas.user import (
    TelegramContactOut,
    TelegramLinkConfirm,
    TelegramLinkStartOut,
    TelegramLinkStartRequest,
    UserCreate,
    UserOut,
)

router = APIRouter(prefix="/users", tags=["users"])


def _get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def _get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def _get_user_by_link_token(db: Session, token: str) -> User | None:
    return db.scalar(select(User).where(User.telegram_link_token == token))


def _build_telegram_deep_link(token: str) -> str | None:
    if not settings.telegram_bot_username:
        return None
    return f"https://t.me/{settings.telegram_bot_username}?start={token}"


def _telegram_token_expired(user: User) -> bool:
    if not user.telegram_link_token_created_at:
        return True
    created_at = user.telegram_link_token_created_at
    # SQLite часто возвращает naive datetime, поэтому для сравнения
    # считаем такие значения временем UTC.
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    expires_at = created_at + timedelta(
        minutes=settings.telegram_link_token_ttl_minutes
    )
    return datetime.now(timezone.utc) > expires_at


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    # Проверяем уникальность логина до вставки, чтобы вернуть понятную 409.
    exists = _get_user_by_username(db, payload.username)
    if exists:
        raise HTTPException(status_code=409, detail="username already exists")

    user = User(
        username=payload.username,
        # В БД хранится только хеш, а не исходный пароль.
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.id.asc())).all()
    return list(users)


@router.post("/{user_id}/telegram/link", response_model=TelegramLinkStartOut)
def start_telegram_link(
    user_id: int,
    payload: TelegramLinkStartRequest,
    db: Session = Depends(get_db),
):
    user = _get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    # Так как в проекте пока нет серверных сессий, подтверждаем владение аккаунтом паролем.
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid password")

    link_token = secrets.token_urlsafe(24)
    created_at = datetime.now(timezone.utc)

    user.telegram_link_token = link_token
    user.telegram_link_token_created_at = created_at
    db.add(user)
    db.commit()

    # UI получает сразу всё, что нужно для следующего шага:
    # срок жизни токена и deep-link на бота.
    expires_at = created_at + timedelta(minutes=settings.telegram_link_token_ttl_minutes)
    return TelegramLinkStartOut(
        link_token=link_token,
        expires_at=expires_at,
        telegram_bot_username=settings.telegram_bot_username,
        telegram_deep_link=_build_telegram_deep_link(link_token),
    )


@router.post("/telegram/confirm", response_model=UserOut)
def confirm_telegram_link(payload: TelegramLinkConfirm, db: Session = Depends(get_db)):
    # Этот endpoint должен вызывать Telegram bot/communicator после /start по deep-link.
    user = _get_user_by_link_token(db, payload.token)
    if not user:
        raise HTTPException(status_code=404, detail="telegram link token not found")

    if _telegram_token_expired(user):
        user.telegram_link_token = None
        user.telegram_link_token_created_at = None
        db.add(user)
        db.commit()
        raise HTTPException(status_code=400, detail="telegram link token expired")

    # Один и тот же Telegram чат может использоваться для нескольких аккаунтов.
    user.telegram_chat_id = payload.chat_id
    user.telegram_username = payload.telegram_username
    user.telegram_verified_at = datetime.now(timezone.utc)
    user.telegram_link_token = None
    user.telegram_link_token_created_at = None
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}/telegram-contact", response_model=TelegramContactOut)
def get_user_telegram_contact(user_id: int, db: Session = Depends(get_db)):
    # Этот endpoint нужен communicator, чтобы понимать, есть ли у получателя
    # подтвержденный Telegram chat_id для уведомлений.
    user = _get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    return TelegramContactOut(
        user_id=user.id,
        telegram_chat_id=user.telegram_chat_id,
        telegram_username=user.telegram_username,
        telegram_verified_at=user.telegram_verified_at,
    )


@router.get("/by-username/{username}", response_model=UserOut)
def get_user_by_username(username: str, db: Session = Depends(get_db)):
    # Этот lookup нужен веб-форме, где письмо отправляется по логину получателя.
    user = _get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = _get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return user
