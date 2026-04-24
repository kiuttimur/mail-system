"""add telegram link fields to users

Revision ID: 0003_user_telegram_link
Revises: 0002_user_password_hash
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_user_telegram_link"
down_revision = "0002_user_password_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поля, которые нужны для безопасной привязки Telegram через
    # одноразовый токен и подтверждённый chat_id.
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("telegram_chat_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("telegram_username", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("telegram_link_token", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("telegram_link_token_created_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("telegram_verified_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_users_telegram_chat_id", ["telegram_chat_id"], unique=True)
        batch_op.create_index("ix_users_telegram_link_token", ["telegram_link_token"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_telegram_link_token")
        batch_op.drop_index("ix_users_telegram_chat_id")
        batch_op.drop_column("telegram_verified_at")
        batch_op.drop_column("telegram_link_token_created_at")
        batch_op.drop_column("telegram_link_token")
        batch_op.drop_column("telegram_username")
        batch_op.drop_column("telegram_chat_id")
