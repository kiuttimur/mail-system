"""Инициализация SQLAlchemy engine и зависимости сессии для FastAPI."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


connect_args = {}
if settings.database_url.startswith("sqlite"):
    # Для SQLite в dev-режиме нужен этот флаг, иначе один и тот же файл БД
    # нельзя безопасно использовать из FastAPI и тестов.
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    # Отдаём сессию на время запроса и гарантированно закрываем её после работы.
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
