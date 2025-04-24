"""rename_chat_message_fields

Revision ID: 111d3837be93
Revises: f3dff1ae54b9
Create Date: 2025-04-23 17:38:05.768230

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '111d3837be93'
down_revision: Union[str, None] = 'f3dff1ae54b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename processed to processed_in_mem0
    op.alter_column('chat_message', 'processed', new_column_name='processed_in_mem0')
    
    # Rename ingested to processed_in_summary 
    op.alter_column('chat_message', 'ingested', new_column_name='processed_in_summary')
    
    # Add new field processed_in_graphiti
    op.add_column('chat_message', sa.Column('processed_in_graphiti', sa.Boolean(), nullable=False, server_default='false'))
    
    # Create indices for the new/renamed fields
    op.create_index('ix_chat_message_processed_in_graphiti', 'chat_message', ['processed_in_graphiti'], unique=False)
    op.create_index('ix_chat_message_processed_in_mem0', 'chat_message', ['processed_in_mem0'], unique=False)
    op.create_index('ix_chat_message_processed_in_summary', 'chat_message', ['processed_in_summary'], unique=False)
    
    # Drop old indices that may have been created for the old field names
    op.drop_index('ix_chat_message_processed', table_name='chat_message', if_exists=True)
    op.drop_index('ix_chat_message_ingested', table_name='chat_message', if_exists=True)


def downgrade() -> None:
    # Drop indices for the new/renamed fields
    op.drop_index('ix_chat_message_processed_in_graphiti', table_name='chat_message')
    op.drop_index('ix_chat_message_processed_in_mem0', table_name='chat_message')
    op.drop_index('ix_chat_message_processed_in_summary', table_name='chat_message')
    
    # Drop the new field
    op.drop_column('chat_message', 'processed_in_graphiti')
    
    # Rename fields back to original names
    op.alter_column('chat_message', 'processed_in_summary', new_column_name='ingested')
    op.alter_column('chat_message', 'processed_in_mem0', new_column_name='processed')
    
    # Recreate original indices
    op.create_index('ix_chat_message_processed', 'chat_message', ['processed'], unique=False)
    op.create_index('ix_chat_message_ingested', 'chat_message', ['ingested'], unique=False) 