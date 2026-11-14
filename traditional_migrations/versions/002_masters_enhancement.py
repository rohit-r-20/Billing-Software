"""002_masters_enhancement

Revision ID: 002_masters_enhancement
Revises: 001_foundation_schema
Create Date: 2026-11-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_masters_enhancement'
down_revision: Union[str, None] = '001_foundation_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add additive columns to items table
    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('unit', sa.String(length=20), nullable=False, server_default='Pcs.'))
        batch_op.add_column(sa.Column('category', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('hsn', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('mrp', sa.Numeric(precision=12, scale=2), nullable=True))
        batch_op.add_column(sa.Column('min_sales_price', sa.Numeric(precision=12, scale=2), nullable=True))

    # 2. Add additive columns to accounts table (supporting Customer / Debtor attributes)
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('phone', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('email', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('address', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('gstin', sa.String(length=15), nullable=True))
        batch_op.add_column(sa.Column('state', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    # 3. Add single tenant branch unique constraint on branches table
    with op.batch_alter_table('branches', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_branches_single_tenant_branch', ['company_id'])

    # 4. Create barcode_reservations table
    op.create_table(
        'barcode_reservations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('barcode', sa.String(length=100), nullable=False),
        sa.Column('reserved_by', sa.String(length=36), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reserved_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'barcode', name='uq_barcode_reservations_company_barcode')
    )
    op.create_index('ix_barcode_reservations_company_expiry', 'barcode_reservations', ['company_id', 'expires_at'])


def downgrade() -> None:
    op.drop_index('ix_barcode_reservations_company_expiry', table_name='barcode_reservations')
    op.drop_table('barcode_reservations')

    with op.batch_alter_table('branches', schema=None) as batch_op:
        batch_op.drop_constraint('uq_branches_single_tenant_branch', type_='unique')

    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('state')
        batch_op.drop_column('gstin')
        batch_op.drop_column('address')
        batch_op.drop_column('email')
        batch_op.drop_column('phone')

    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.drop_column('min_sales_price')
        batch_op.drop_column('mrp')
        batch_op.drop_column('hsn')
        batch_op.drop_column('category')
        batch_op.drop_column('unit')
