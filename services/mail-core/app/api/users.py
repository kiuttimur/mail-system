"""Эндпоинты работы с пользователями: регистрация и чтение профилей."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.db import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    # Проверяем уникальность логина до вставки, чтобы вернуть понятную 409.
    exists = db.scalar(select(User).where(User.username == payload.username))
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


@router.get("/by-username/{username}", response_model=UserOut)
def get_user_by_username(username: str, db: Session = Depends(get_db)):
    # Этот lookup нужен веб-форме, где письмо отправляется по логину получателя.
    user = db.scalar(select(User).where(User.username == username))
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return user
