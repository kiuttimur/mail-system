"""Идемпотентное наполнение dev-базы тестовыми пользователями и письмами."""

from __future__ import annotations

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.letter import Letter
from app.models.user import User

SEED_USER_PASSWORD = "password123"
SEED_USERS = (
    "alice",
    "bob",
    *(f"user{i:03d}" for i in range(1, 99)),
)
SEED_LETTERS = (
    {
        "sender": "alice",
        "recipient": "bob",
        "subject": "Welcome to mail-core",
        "body": "Hi Bob! This is a seeded message from Alice.",
    },
    {
        "sender": "bob",
        "recipient": "alice",
        "subject": "Re: Welcome to mail-core",
        "body": "Hi Alice! Seed data is working.",
    },
)


def get_or_create_user(db, username: str) -> tuple[User, bool]:
    password_hash = hash_password(SEED_USER_PASSWORD)
    user = db.scalar(select(User).where(User.username == username))
    if user is not None:
        # Если пользователь уже был в старой БД без пароля, аккуратно дозаполняем хеш.
        if not user.password_hash:
            user.password_hash = password_hash
            db.add(user)
            db.flush()
        return user, False

    user = User(username=username, password_hash=password_hash)
    db.add(user)
    db.flush()
    return user, True


def get_or_create_letter(
    db,
    *,
    sender_id: int,
    recipient_id: int,
    subject: str,
    body: str,
) -> tuple[Letter, bool]:
    letter = db.scalar(
        select(Letter).where(
            Letter.sender_id == sender_id,
            Letter.recipient_id == recipient_id,
            Letter.subject == subject,
            Letter.body == body,
        )
    )
    if letter is not None:
        return letter, False

    letter = Letter(
        sender_id=sender_id,
        recipient_id=recipient_id,
        subject=subject,
        body=body,
    )
    db.add(letter)
    db.flush()
    return letter, True


def main() -> None:
    created_users = 0
    created_letters = 0

    with SessionLocal() as db:
        users_by_name: dict[str, User] = {}

        for username in SEED_USERS:
            user, created = get_or_create_user(db, username)
            users_by_name[username] = user
            created_users += int(created)

        # Письма тоже создаём идемпотентно, чтобы seed можно было запускать повторно.
        for item in SEED_LETTERS:
            _, created = get_or_create_letter(
                db,
                sender_id=users_by_name[item["sender"]].id,
                recipient_id=users_by_name[item["recipient"]].id,
                subject=item["subject"],
                body=item["body"],
            )
            created_letters += int(created)

        db.commit()

    print(
        "Seed complete: "
        f"created_users={created_users}, "
        f"created_letters={created_letters}, "
        f"default_password={SEED_USER_PASSWORD}"
    )


if __name__ == "__main__":
    main()
