"""Общие фикстуры тестов: временная БД и отключение communicator."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

SERVICE_ROOT = Path(__file__).resolve().parents[1]

if str(SERVICE_ROOT) not in sys.path:
    sys.path.append(str(SERVICE_ROOT))

from app.models.base import Base


@pytest.fixture()
def db_session(tmp_path: Path) -> Session:
    # Каждый тест работает на своей SQLite-базе, чтобы сценарии не влияли друг на друга.
    db_path = tmp_path / "mail_core_test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as session:
        yield session

    engine.dispose()


@pytest.fixture(autouse=True)
def disable_communicator(monkeypatch: pytest.MonkeyPatch) -> None:
    # Во время тестов не ходим в сторонний сервис, чтобы не зависеть от сети и окружения.
    async def noop_notify_new_letter(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr("app.api.letters.notify_new_letter", noop_notify_new_letter)
