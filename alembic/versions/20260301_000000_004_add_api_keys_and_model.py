"""Add encrypted API key fields and preferred model to user_settings.

Revision ID: 004
Revises: 003
Create Date: 2026-03-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("encrypted_openai_api_key", sa.Text(), nullable=True),
    )
    op.add_column(
        "user_settings",
        sa.Column("encrypted_anthropic_api_key", sa.Text(), nullable=True),
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "preferred_model",
            sa.String(100),
            nullable=False,
            server_default="gpt-5.2",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "preferred_model")
    op.drop_column("user_settings", "encrypted_anthropic_api_key")
    op.drop_column("user_settings", "encrypted_openai_api_key")
