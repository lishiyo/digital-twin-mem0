"""add conversation and chat message models

Revision ID: 1e7d35ac6978
Revises: 198d7e8faefb
Create Date: 2025-04-22 00:54:18.844246

"""
from typing import Sequence, Union
from enum import Enum

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlalchemy.ext.asyncio
from sqlalchemy.engine import reflection


# revision identifiers, used by Alembic.
revision: str = '1e7d35ac6978'
down_revision: Union[str, None] = '198d7e8faefb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the enums - use existing types
    message_role_enum = postgresql.ENUM('user', 'assistant', 'system', name='messagerole', create_type=False)
    feedback_type_enum = postgresql.ENUM('like', 'dislike', 'accurate', 'inaccurate', 'helpful', 'unhelpful', 'custom', name='feedbacktype', create_type=False)

    message_role_enum.create(op.get_bind(), checkfirst=True)
    feedback_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Get a connection
    connection = op.get_bind()
    inspector = reflection.Inspector.from_engine(connection)
    
    # Check if tables exist before creating them
    existing_tables = inspector.get_table_names()
    
    # Create conversation table if it doesn't exist
    if 'conversation' not in existing_tables:
        op.create_table(
            'conversation',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('user.id'), nullable=False),
            sa.Column('title', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('meta_data', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
            sa.Column('summary', sa.Text(), nullable=True),
        )
        op.create_index(op.f('ix_conversation_user_id'), 'conversation', ['user_id'], unique=False)
    
    # Create chat_message table if it doesn't exist
    if 'chat_message' not in existing_tables:
        op.create_table(
            'chat_message',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('conversation_id', sa.String(36), sa.ForeignKey('conversation.id'), nullable=False),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('user.id'), nullable=False),
            sa.Column('role', message_role_enum, nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('meta_data', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
            sa.Column('tokens', sa.Integer(), nullable=True),
            sa.Column('processed', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('is_stored_in_mem0', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('mem0_memory_id', sa.String(255), nullable=True),
            sa.Column('importance_score', sa.Float(), nullable=True),
        )
        op.create_index(op.f('ix_chat_message_conversation_id'), 'chat_message', ['conversation_id'], unique=False)
        op.create_index(op.f('ix_chat_message_user_id'), 'chat_message', ['user_id'], unique=False)
        op.create_index(op.f('ix_chat_message_role'), 'chat_message', ['role'], unique=False)
        op.create_index(op.f('ix_chat_message_created_at'), 'chat_message', ['created_at'], unique=False)
        op.create_index(op.f('ix_chat_message_processed'), 'chat_message', ['processed'], unique=False)
        op.create_index(op.f('ix_chat_message_is_stored_in_mem0'), 'chat_message', ['is_stored_in_mem0'], unique=False)
    
    # Create message_feedback table if it doesn't exist
    if 'message_feedback' not in existing_tables:
        op.create_table(
            'message_feedback',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('message_id', sa.String(36), sa.ForeignKey('chat_message.id'), nullable=False),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('user.id'), nullable=False),
            sa.Column('feedback_type', feedback_type_enum, nullable=False),
            sa.Column('rating', sa.Float(), nullable=True),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('meta_data', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
        )
        op.create_index(op.f('ix_message_feedback_message_id'), 'message_feedback', ['message_id'], unique=False)
        op.create_index(op.f('ix_message_feedback_user_id'), 'message_feedback', ['user_id'], unique=False)


def downgrade() -> None:
    # Get a connection
    connection = op.get_bind()
    inspector = reflection.Inspector.from_engine(connection)
    
    # Check if tables exist before dropping them
    existing_tables = inspector.get_table_names()
    
    # Drop tables if they exist
    if 'message_feedback' in existing_tables:
        op.drop_table('message_feedback')
    
    if 'chat_message' in existing_tables:
        op.drop_table('chat_message')
        
    if 'conversation' in existing_tables:
        op.drop_table('conversation')
    
    # We don't drop the enums in downgrade because:
    # 1. They might be used by other tables
    # 2. We checked if they existed before creating them in upgrade 