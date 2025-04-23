"""manual migration for mem0_memory_id and is_stored_in_graphiti

Revision ID: manual_mem0_graphiti_fields
Revises: 653acd793b85
Create Date: 2025-04-22 18:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'manual_mem0_graphiti_fields'
down_revision: Union[str, None] = '653acd793b85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade migration to remove mem0_memory_id and add is_stored_in_graphiti."""
    # 1. Add the new column
    op.add_column('chat_message', sa.Column('is_stored_in_graphiti', sa.Boolean(), nullable=False, server_default='false'))
    
    # 2. Create index for the new column
    op.create_index(op.f('ix_chat_message_is_stored_in_graphiti'), 'chat_message', ['is_stored_in_graphiti'], unique=False)
    
    # 3. Drop the mem0_memory_id column
    op.drop_column('chat_message', 'mem0_memory_id')


def downgrade() -> None:
    """Downgrade migration to restore original state."""
    # 1. Add back the mem0_memory_id column
    op.add_column('chat_message', sa.Column('mem0_memory_id', sa.VARCHAR(length=255), autoincrement=False, nullable=True))
    
    # 2. Drop the index for is_stored_in_graphiti
    op.drop_index(op.f('ix_chat_message_is_stored_in_graphiti'), table_name='chat_message')
    
    # 3. Drop the is_stored_in_graphiti column
    op.drop_column('chat_message', 'is_stored_in_graphiti') 