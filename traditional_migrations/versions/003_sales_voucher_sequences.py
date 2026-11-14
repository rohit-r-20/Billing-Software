"""003_sales_voucher_sequences

Revision ID: 003_sales_voucher_sequences
Revises: 002_masters_enhancement
Create Date: 2026-11-14 16:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_sales_voucher_sequences'
down_revision: Union[str, None] = '002_masters_enhancement'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create voucher_sequences table
    op.create_table(
        'voucher_sequences',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=False),
        sa.Column('financial_year', sa.String(length=20), nullable=False),
        sa.Column('series', sa.String(length=50), server_default='Main', nullable=False),
        sa.Column('current_number', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('prefix', sa.String(length=20), server_default='', nullable=True),
        sa.Column('padding', sa.Integer(), server_default='3', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'company_id', 'branch_id', 'financial_year', 'series',
            name='uq_voucher_sequences_scope'
        )
    )
    op.create_index('ix_voucher_sequences_scope', 'voucher_sequences', ['company_id', 'branch_id', 'financial_year', 'series'])

    # 2. Create sales_invoices table
    op.create_table(
        'sales_invoices',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('voucher_id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('financial_year', sa.String(length=20), nullable=False),
        sa.Column('series', sa.String(length=50), server_default='Main', nullable=False),
        sa.Column('sequence_number', sa.BigInteger(), nullable=False),
        sa.Column('voucher_number', sa.String(length=50), nullable=False),
        sa.Column('vch_date', sa.String(length=20), nullable=False),
        sa.Column('party_name', sa.String(length=255), nullable=False),
        sa.Column('account_id', sa.String(length=36), nullable=True),
        sa.Column('customer_category', sa.String(length=50), nullable=True),
        sa.Column('sale_type', sa.String(length=50), nullable=False),
        sa.Column('payment_method', sa.String(length=50), server_default='CASH', nullable=False),
        sa.Column('narration', sa.Text(), nullable=True),
        sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('taxable_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('cgst_amount', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('sgst_amount', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('igst_amount', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('round_off_amount', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('grand_total', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('payment_mode', sa.String(length=50), server_default='CASH', nullable=True),
        sa.Column('status', sa.String(length=20), server_default='PAID', nullable=True),
        sa.Column('items_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'company_id', 'branch_id', 'financial_year', 'series', 'voucher_number',
            name='uq_sales_invoices_scope_vch_no'
        ),
        sa.UniqueConstraint(
            'company_id', 'branch_id', 'financial_year', 'series', 'sequence_number',
            name='uq_sales_invoices_scope_seq_no'
        )
    )
    op.create_index('ix_sales_invoices_scope_date', 'sales_invoices', ['company_id', 'branch_id', 'vch_date'])


def downgrade() -> None:
    op.drop_table('sales_invoices')
    op.drop_table('voucher_sequences')
