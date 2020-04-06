"""
extend orders table.

Revision ID: d1e6672520b2
Revises:
Create Date: 2019-07-29 17:38:09.136485
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'd1e6672520b2'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('orders', sa.Column('virtual', sa.Boolean(create_constraint=False)))
    op.add_column('orders', sa.Column('custom', sa.String))


def downgrade():
    op.drop_column('orders', 'virtual')
    op.drop_column('orders', 'custom')
