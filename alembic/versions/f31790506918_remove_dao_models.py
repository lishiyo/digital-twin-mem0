"""remove dao models

Revision ID: f31790506918
Revises: 43c40d9dfe40
Create Date: 2025-04-21 22:49:35.714847

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlalchemy.ext.asyncio
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = 'f31790506918'
down_revision: Union[str, None] = '43c40d9dfe40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands to remove DAO models, checking existence first ###
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Check if vote table exists
    if 'vote' in inspector.get_table_names():
        # Drop vote table indexes if they exist
        indexes = [idx['name'] for idx in inspector.get_indexes('vote')]
        for idx_name in ['ix_vote_id', 'ix_vote_proposal_id', 'ix_vote_user_id', 'ix_vote_created_at']:
            if idx_name in indexes:
                op.drop_index(idx_name, table_name='vote')
        
        # Drop the vote table
        op.drop_table('vote')
    
    # Check if proposal table exists
    if 'proposal' in inspector.get_table_names():
        # Drop proposal table indexes if they exist
        indexes = [idx['name'] for idx in inspector.get_indexes('proposal')]
        for idx_name in ['ix_proposal_id', 'ix_proposal_title', 'ix_proposal_author_id', 'ix_proposal_created_at']:
            if idx_name in indexes:
                op.drop_index(idx_name, table_name='proposal')
        
        # Drop the proposal table
        op.drop_table('proposal')
    # ### end of commands ###


def downgrade() -> None:
    # ### commands to recreate DAO models ###
    # We don't need to check existence for recreating tables
    
    # First recreate the proposal table
    op.create_table('proposal',
    sa.Column('id', sa.VARCHAR(length=36), autoincrement=False, nullable=False),
    sa.Column('title', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('author_id', sa.VARCHAR(length=36), autoincrement=False, nullable=False),
    sa.Column('status', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('voting_starts_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('voting_ends_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('total_votes', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('quorum_reached', sa.BOOLEAN(), autoincrement=False, nullable=False),
    sa.Column('graphiti_entity_id', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['user.id'], name='proposal_author_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='proposal_pkey')
    )
    op.create_index('ix_proposal_created_at', 'proposal', ['created_at'], unique=False)
    op.create_index('ix_proposal_author_id', 'proposal', ['author_id'], unique=False)
    op.create_index('ix_proposal_title', 'proposal', ['title'], unique=False)
    op.create_index('ix_proposal_id', 'proposal', ['id'], unique=False)
    
    # Then recreate the vote table
    op.create_table('vote',
    sa.Column('id', sa.VARCHAR(length=36), autoincrement=False, nullable=False),
    sa.Column('proposal_id', sa.VARCHAR(length=36), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.VARCHAR(length=36), autoincrement=False, nullable=False),
    sa.Column('choice', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('confidence', sa.FLOAT(), autoincrement=False, nullable=False),
    sa.Column('is_delegate_vote', sa.BOOLEAN(), autoincrement=False, nullable=False),
    sa.Column('is_twin_vote', sa.BOOLEAN(), autoincrement=False, nullable=False),
    sa.Column('graphiti_entity_id', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['proposal_id'], ['proposal.id'], name='vote_proposal_id_fkey'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='vote_user_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='vote_pkey')
    )
    op.create_index('ix_vote_created_at', 'vote', ['created_at'], unique=False)
    op.create_index('ix_vote_user_id', 'vote', ['user_id'], unique=False)
    op.create_index('ix_vote_proposal_id', 'vote', ['proposal_id'], unique=False)
    op.create_index('ix_vote_id', 'vote', ['id'], unique=False)
    # ### end of commands ### 