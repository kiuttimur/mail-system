"""allow shared telegram chat ids

Revision ID: 0004_shared_telegram_chat
Revises: 0003_user_telegram_link
Create Date: 2026-04-23
"""

from alembic import op

revision = "0004_shared_telegram_chat"
down_revision = "0003_user_telegram_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Раньше один Telegram chat_id можно было привязать только к одному аккаунту.
    # Теперь разрешаем связывать один и тот же Telegram с несколькими аккаунтами.
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_telegram_chat_id")
        batch_op.create_index("ix_users_telegram_chat_id", ["telegram_chat_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_telegram_chat_id")
        batch_op.create_index("ix_users_telegram_chat_id", ["telegram_chat_id"], unique=True)
