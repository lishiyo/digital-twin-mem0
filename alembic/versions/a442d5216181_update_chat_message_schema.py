"""update_chat_message_schema

Revision ID: a442d5216181
Revises: 1e7d35ac6978
Create Date: 2025-04-22 01:38:07.583773

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a442d5216181'
down_revision: Union[str, None] = '1e7d35ac6978'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type if it doesn't exist
    message_role_enum = postgresql.ENUM('user', 'assistant', 'system', name='messagerole', create_type=False)
    message_role_enum.create(op.get_bind(), checkfirst=True)
    
    # Add new columns
    op.add_column('chat_message', sa.Column('conversation_id', sa.String(36), nullable=True))
    op.add_column('chat_message', sa.Column('role', sa.Enum('user', 'assistant', 'system', name='messagerole'), nullable=True))
    op.add_column('chat_message', sa.Column('meta_data', postgresql.JSON(astext_type=sa.Text()), server_default='{}', nullable=False))
    op.add_column('chat_message', sa.Column('tokens', sa.Integer(), nullable=True))
    op.add_column('chat_message', sa.Column('processed', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('chat_message', sa.Column('mem0_message_id', sa.String(255), nullable=True))
    op.add_column('chat_message', sa.Column('mem0_metadata', postgresql.JSON(astext_type=sa.Text()), server_default='{}', nullable=False))
    op.add_column('chat_message', sa.Column('embedding_id', sa.String(255), nullable=True))
    op.add_column('chat_message', sa.Column('ingested', sa.Boolean(), server_default='false', nullable=False))
    
    # Migrate data from old columns to new columns
    op.execute("""
    UPDATE chat_message 
    SET 
        conversation_id = session_id,
        role = CASE 
            WHEN sender = 'user' THEN 'user'::messagerole
            WHEN sender = 'assistant' THEN 'assistant'::messagerole
            ELSE 'system'::messagerole
        END
    """)
    
    # Create index on conversation_id
    op.create_index(op.f('ix_chat_message_conversation_id'), 'chat_message', ['conversation_id'], unique=False)
    
    # Add foreign key constraint to conversation
    op.create_foreign_key('fk_chat_message_conversation_id', 'chat_message', 'conversation', ['conversation_id'], ['id'])
    
    # Create index on new columns
    op.create_index(op.f('ix_chat_message_processed'), 'chat_message', ['processed'], unique=False)
    op.create_index(op.f('ix_chat_message_role'), 'chat_message', ['role'], unique=False)
    op.create_index(op.f('ix_chat_message_ingested'), 'chat_message', ['ingested'], unique=False)
    
    # Now, make the new columns not nullable after data migration
    op.alter_column('chat_message', 'conversation_id', nullable=False)
    op.alter_column('chat_message', 'role', nullable=False)
    
    # Drop old columns
    op.drop_column('chat_message', 'session_id')
    op.drop_column('chat_message', 'sender')


def downgrade() -> None:
    # Add back old columns
    op.add_column('chat_message', sa.Column('session_id', sa.VARCHAR(length=255), nullable=True))
    op.add_column('chat_message', sa.Column('sender', sa.VARCHAR(length=50), nullable=True))
    
    # Migrate data back to old columns
    op.execute("""
    UPDATE chat_message 
    SET 
        session_id = conversation_id,
        sender = CASE 
            WHEN role = 'user' THEN 'user'
            WHEN role = 'assistant' THEN 'assistant'
            ELSE 'system'
        END
    """)
    
    # Make old columns not nullable
    op.alter_column('chat_message', 'session_id', nullable=False)
    op.alter_column('chat_message', 'sender', nullable=False)
    
    # Drop foreign key constraint
    op.drop_constraint('fk_chat_message_conversation_id', 'chat_message', type_='foreignkey')
    
    # Drop indexes
    op.drop_index(op.f('ix_chat_message_ingested'), table_name='chat_message')
    op.drop_index(op.f('ix_chat_message_role'), table_name='chat_message')
    op.drop_index(op.f('ix_chat_message_processed'), table_name='chat_message')
    op.drop_index(op.f('ix_chat_message_conversation_id'), table_name='chat_message')
    
    # Drop new columns
    op.drop_column('chat_message', 'ingested')
    op.drop_column('chat_message', 'embedding_id')
    op.drop_column('chat_message', 'mem0_metadata')
    op.drop_column('chat_message', 'mem0_message_id')
    op.drop_column('chat_message', 'processed')
    op.drop_column('chat_message', 'tokens')
    op.drop_column('chat_message', 'meta_data')
    op.drop_column('chat_message', 'role')
    op.drop_column('chat_message', 'conversation_id') 