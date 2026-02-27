"""add_api_keys_and_preferred_model_to_user_settings

Revision ID: 16e2c7853fdb
Revises: 003
Create Date: 2026-02-27 06:36:26.054005+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '16e2c7853fdb'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_settings', sa.Column('openai_api_key', sa.String(length=500), nullable=True))
    op.add_column('user_settings', sa.Column('anthropic_api_key', sa.String(length=500), nullable=True))
    op.add_column('user_settings', sa.Column('preferred_model', sa.String(length=100), server_default='gpt-4.1', nullable=False))


def downgrade() -> None:
    op.drop_column('user_settings', 'preferred_model')
    op.drop_column('user_settings', 'anthropic_api_key')
    op.drop_column('user_settings', 'openai_api_key')
