"""add_purchase_price_history_and_landed_cost

Revision ID: e4a78c1b9f20
Revises: 63b87d829649
Create Date: 2026-11-16 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection


# revision identifiers, used by Alembic.
revision: str = 'e4a78c1b9f20'
down_revision: Union[str, Sequence[str], None] = '63b87d829649'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = reflection.Inspector.from_engine(conn)
    existing_tables = insp.get_table_names()

    # 1. Create purchase_price_history table if not exists
    if 'purchase_price_history' not in existing_tables:
        op.create_table(
            'purchase_price_history',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('company_id', sa.String(length=36), nullable=False),
            sa.Column('branch_id', sa.String(length=36), nullable=True),
            sa.Column('item_id', sa.String(length=36), nullable=False),
            sa.Column('supplier_id', sa.String(length=36), nullable=True),
            sa.Column('voucher_id', sa.String(length=36), nullable=False),
            sa.Column('voucher_number', sa.String(length=50), nullable=False),
            sa.Column('supplier_invoice_no', sa.String(length=100), nullable=True),
            sa.Column('purchase_date', sa.String(length=20), nullable=False),
            sa.Column('purchase_rate', sa.Float(), nullable=False),
            sa.Column('qty', sa.Float(), nullable=False),
            sa.Column('discount_percent', sa.Float(), server_default='0.0', nullable=True),
            sa.Column('tax_rate', sa.Float(), server_default='0.0', nullable=True),
            sa.Column('landed_cost', sa.Float(), server_default='0.0', nullable=True),
            sa.Column('previous_rate', sa.Float(), server_default='0.0', nullable=True),
            sa.Column('is_revision', sa.Integer(), server_default='0', nullable=True),
            sa.Column('revision_notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=True),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['voucher_id'], ['purchase_vouchers.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('idx_pph_lookup', 'purchase_price_history', ['company_id', 'item_id', 'supplier_id', 'purchase_date'])
        op.create_index('idx_pph_item_date', 'purchase_price_history', ['company_id', 'item_id', 'purchase_date'])
        op.create_index('idx_pph_voucher', 'purchase_price_history', ['voucher_id'])

    # 2. Add additive columns to purchase_vouchers
    pv_cols = [c['name'] for c in insp.get_columns('purchase_vouchers')] if 'purchase_vouchers' in existing_tables else []
    if 'freight_charges' not in pv_cols:
        op.add_column('purchase_vouchers', sa.Column('freight_charges', sa.Float(), server_default='0.0', nullable=True))
    if 'handling_charges' not in pv_cols:
        op.add_column('purchase_vouchers', sa.Column('handling_charges', sa.Float(), server_default='0.0', nullable=True))

    # 3. Add landed_cost to purchase_voucher_items
    pvi_cols = [c['name'] for c in insp.get_columns('purchase_voucher_items')] if 'purchase_voucher_items' in existing_tables else []
    if 'landed_cost' not in pvi_cols:
        op.add_column('purchase_voucher_items', sa.Column('landed_cost', sa.Float(), server_default='0.0', nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    insp = reflection.Inspector.from_engine(conn)
    existing_tables = insp.get_table_names()

    if 'purchase_price_history' in existing_tables:
        op.drop_index('idx_pph_voucher', table_name='purchase_price_history')
        op.drop_index('idx_pph_item_date', table_name='purchase_price_history')
        op.drop_index('idx_pph_lookup', table_name='purchase_price_history')
        op.drop_table('purchase_price_history')

    pv_cols = [c['name'] for c in insp.get_columns('purchase_vouchers')] if 'purchase_vouchers' in existing_tables else []
    if 'handling_charges' in pv_cols:
        op.drop_column('purchase_vouchers', 'handling_charges')
    if 'freight_charges' in pv_cols:
        op.drop_column('purchase_vouchers', 'freight_charges')

    pvi_cols = [c['name'] for c in insp.get_columns('purchase_voucher_items')] if 'purchase_voucher_items' in existing_tables else []
    if 'landed_cost' in pvi_cols:
        op.drop_column('purchase_voucher_items', 'landed_cost')
