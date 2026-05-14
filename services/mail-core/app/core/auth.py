"""Cookie-based auth: создание серверных сессий и получение current user."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from fastapi import Depends, HTTPException, Response, status
from fastapi.security import APIKeyCookie
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models.user import User
from app.models.user_session import UserSession

session_cookie = APIKeyCookie(name=settings.auth_cookie_name, auto_error=False)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_user_session(db: Session, user: User) -> str:
    raw_token = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(minutes=settings.auth_session_ttl_minutes)

    session = UserSession(
        user_id=user.id,
        session_token_hash=_hash_session_token(raw_token),
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    return raw_token


def delete_user_session(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return

    session = db.scalar(
        select(UserSession).where(
            UserSession.session_token_hash == _hash_session_token(raw_token)
        )
    )
    if session:
        db.delete(session)
        db.commit()


def set_auth_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=raw_token,
        max_age=settings.auth_session_ttl_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )


def get_current_user(
    raw_token: str | None = Depends(session_cookie),
    db: Session = Depends(get_db),
) -> User:
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )

    session = db.scalar(
        select(UserSession).where(
            UserSession.session_token_hash == _hash_session_token(raw_token)
        )
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
        )

    if _normalize_datetime(session.expires_at) <= _now():
        db.delete(session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="session expired",
        )

    user = db.get(User, session.user_id)
    if not user:
        db.delete(session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user for session not found",
        )

    return user
