"""Initial structure

Revision ID: e918abdd84ef
Revises: d1e6672520b2
Create Date: 2019-08-20 14:29:04.043339

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e918abdd84ef'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'config',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('category', sa.String),
        sa.Column('key', sa.String),
        sa.Column('value', sa.String),
    )
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('worker', sa.String),
        sa.Column('order_id', sa.String),
        sa.Column('order', sa.String)
    )
    op.create_table(
        'balances',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('worker', sa.String),
        sa.Column('base_total', sa.Float),
        sa.Column('base_symbol', sa.String),
        sa.Column('quote_total', sa.Float),
        sa.Column('quote_symbol', sa.String),
        sa.Column('center_price', sa.Float),
        sa.Column('timestamp', sa.Integer)
    )


def downgrade():
    op.drop_table('config')
    op.drop_table('orders')
    op.drop_table('balances')
