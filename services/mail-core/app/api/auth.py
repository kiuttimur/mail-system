"""Эндпоинты входа пользователя по логину и cookie-сессии."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import (
    clear_auth_cookie,
    create_user_session,
    delete_user_session,
    get_current_user,
    session_cookie,
    set_auth_cookie,
)
from app.core.db import get_db
from app.core.security import verify_password
from app.models.user import User
from app.schemas.user import UserLogin, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(
    payload: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
    existing_session_token: str | None = Depends(session_cookie),
):
    user = db.scalar(select(User).where(User.username == payload.username))
    # Не раскрываем, что именно неверно: логин или пароль.
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
        )

    # Повторный логин перевыпускает cookie и удаляет прежнюю серверную сессию,
    # если она пришла с этим запросом.
    delete_user_session(db, existing_session_token)
    raw_token = create_user_session(db, user)
    set_auth_cookie(response, raw_token)
    return user


@router.post("/logout", response_model=dict[str, str])
def logout(
    response: Response,
    db: Session = Depends(get_db),
    existing_session_token: str | None = Depends(session_cookie),
):
    delete_user_session(db, existing_session_token)
    clear_auth_cookie(response)
    return {"status": "logged out"}


@router.get("/me", response_model=UserOut)
def auth_me(current_user: User = Depends(get_current_user)):
    return current_user
