"""add password hash to users

Revision ID: 0002_user_password_hash
Revises: 0001_initial
Create Date: 2026-04-16
"""

from alembic import op
import sqlalchemy as sa

from app.core.security import hash_password

revision = "0002_user_password_hash"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

LEGACY_DEFAULT_PASSWORD = "password123"


def upgrade() -> None:
    # Для уже существующих пользователей добавляем временный пароль,
    # чтобы после миграции строки не остались с NULL в password_hash.
    default_password_hash = hash_password(LEGACY_DEFAULT_PASSWORD)

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE users "
            "SET password_hash = :password_hash "
            "WHERE password_hash IS NULL"
        ),
        {"password_hash": default_password_hash},
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=255),
            nullable=False,
        )


def downgrade() -> None:
    # При откате просто удаляем добавленную колонку.
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("password_hash")
