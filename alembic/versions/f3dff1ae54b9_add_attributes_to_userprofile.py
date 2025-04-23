"""Add attributes to UserProfile

Revision ID: f3dff1ae54b9
Revises: manual_mem0_graphiti_fields
Create Date: 2025-04-22 20:28:30.875355

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f3dff1ae54b9'
down_revision: Union[str, None] = 'manual_mem0_graphiti_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add attributes column to userprofile table
    op.add_column('userprofile', sa.Column('attributes', sa.JSON(), server_default='[]', nullable=False))


def downgrade() -> None:
    # Remove attributes column from userprofile table
    op.drop_column('userprofile', 'attributes') 