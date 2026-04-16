"""initial users + letters

Revision ID: 0001_initial
Revises: 
Create Date: 2026-03-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Базовая схема первого релиза: пользователи и письма между ними.
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "letters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], name="fk_letters_sender_id_users"),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], name="fk_letters_recipient_id_users"),
    )

    op.create_index("ix_letters_sender_id", "letters", ["sender_id"])
    op.create_index("ix_letters_recipient_id", "letters", ["recipient_id"])
    op.create_index("ix_letters_created_at", "letters", ["created_at"])


def downgrade() -> None:
    # Откат идёт в обратном порядке, чтобы сначала снять зависимости писем.
    op.drop_index("ix_letters_created_at", table_name="letters")
    op.drop_index("ix_letters_recipient_id", table_name="letters")
    op.drop_index("ix_letters_sender_id", table_name="letters")
    op.drop_table("letters")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
