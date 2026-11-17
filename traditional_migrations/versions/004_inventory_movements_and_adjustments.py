"""004_inventory_movements_and_adjustments

Revision ID: 004_inventory_movements_and_adjustments
Revises: 003_sales_voucher_sequences
Create Date: 2026-11-16 15:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_inventory_movements_and_adjustments'
down_revision: Union[str, None] = '003_sales_voucher_sequences'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create stock_movements table (immutable ledger)
    op.create_table(
        'stock_movements',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=False),
        sa.Column('item_id', sa.String(length=36), nullable=False),
        sa.Column('movement_type', sa.String(length=30), nullable=False),
        sa.Column('qty_scaled', sa.BigInteger(), nullable=False),
        sa.Column('unit_cost', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('reference_type', sa.String(length=50), nullable=True),
        sa.Column('reference_id', sa.String(length=100), nullable=True),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'idempotency_key', name='uq_stock_movements_company_idempotency')
    )
    op.create_index('ix_stock_movements_company_item', 'stock_movements', ['company_id', 'item_id'])
    op.create_index('ix_stock_movements_company_branch_date', 'stock_movements', ['company_id', 'branch_id', 'created_at'])
    op.create_index('ix_stock_movements_reference', 'stock_movements', ['company_id', 'reference_type', 'reference_id'])

    # 2. Create stock_adjustments table
    op.create_table(
        'stock_adjustments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=False),
        sa.Column('item_id', sa.String(length=36), nullable=False),
        sa.Column('item_name', sa.String(length=255), nullable=False),
        sa.Column('adjustment_type', sa.String(length=50), nullable=False),
        sa.Column('quantity_scaled', sa.BigInteger(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('unit_cost', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('authorized_by', sa.String(length=100), nullable=True),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'idempotency_key', name='uq_stock_adjustments_company_idempotency')
    )
    op.create_index('ix_stock_adjustments_company_created', 'stock_adjustments', ['company_id', 'created_at'])

    # 3. Create stock_transfers table
    op.create_table(
        'stock_transfers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('source_branch_id', sa.String(length=36), nullable=False),
        sa.Column('dest_branch_id', sa.String(length=36), nullable=False),
        sa.Column('item_id', sa.String(length=36), nullable=False),
        sa.Column('item_name', sa.String(length=255), nullable=False),
        sa.Column('quantity_scaled', sa.BigInteger(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('transfer_number', sa.String(length=50), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('authorized_by', sa.String(length=100), nullable=True),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dest_branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'idempotency_key', name='uq_stock_transfers_company_idempotency')
    )
    op.create_index('ix_stock_transfers_company_created', 'stock_transfers', ['company_id', 'created_at'])


def downgrade() -> None:
    op.drop_table('stock_transfers')
    op.drop_table('stock_adjustments')
    op.drop_table('stock_movements')
