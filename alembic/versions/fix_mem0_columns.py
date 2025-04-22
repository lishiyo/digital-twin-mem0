"""add missing mem0 columns

Revision ID: fix_mem0_columns
Revises: a442d5216181
Create Date: 2025-04-22 14:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'fix_mem0_columns'
down_revision: Union[str, None] = 'a442d5216181'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the missing mem0 columns to chat_message
    op.add_column('chat_message', sa.Column('mem0_message_id', sa.String(255), nullable=True))
    op.add_column('chat_message', sa.Column('mem0_metadata', postgresql.JSON(astext_type=sa.Text()), server_default='{}', nullable=False))
    op.add_column('chat_message', sa.Column('embedding_id', sa.String(255), nullable=True))
    op.add_column('chat_message', sa.Column('ingested', sa.Boolean(), server_default='false', nullable=False))
    
    # Create index on ingested column
    op.create_index(op.f('ix_chat_message_ingested'), 'chat_message', ['ingested'], unique=False)


def downgrade() -> None:
    # Drop index
    op.drop_index(op.f('ix_chat_message_ingested'), table_name='chat_message')
    
    # Drop columns
    op.drop_column('chat_message', 'ingested')
    op.drop_column('chat_message', 'embedding_id')
    op.drop_column('chat_message', 'mem0_metadata')
    op.drop_column('chat_message', 'mem0_message_id') 