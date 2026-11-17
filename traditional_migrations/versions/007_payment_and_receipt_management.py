"""007_payment_and_receipt_management

Revision ID: 007_payment_and_receipt_management
Revises: 006_financial_year_closing_and_opening_balances
Create Date: 2026-11-17 12:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_payment_and_receipt_management'
down_revision: Union[str, None] = '006_financial_year_closing_and_opening_balances'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create customer_receipts table
    op.create_table(
        'customer_receipts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=False),
        sa.Column('financial_year', sa.String(length=20), nullable=False),
        sa.Column('voucher_number', sa.String(length=50), nullable=False),
        sa.Column('receipt_date', sa.String(length=20), nullable=False),
        sa.Column('customer_account_id', sa.String(length=36), nullable=False),
        sa.Column('deposit_account_id', sa.String(length=36), nullable=False),
        sa.Column('payment_method', sa.String(length=50), server_default='CASH', nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('allocated_amount', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=False),
        sa.Column('unallocated_amount', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=False),
        sa.Column('discount_amount', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=False),
        sa.Column('reference_number', sa.String(length=100), nullable=True),
        sa.Column('reference_date', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('journal_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='POSTED', nullable=False),
        sa.Column('reversal_of_id', sa.String(length=36), nullable=True),
        sa.Column('reversal_reason', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_account_id'], ['accounts.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['deposit_account_id'], ['accounts.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['journal_id'], ['journal_entries.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reversal_of_id'], ['customer_receipts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'financial_year', 'voucher_number', name='uq_cust_receipts_company_fy_vch'),
        sa.UniqueConstraint('company_id', 'idempotency_key', name='uq_cust_receipts_idempotency'),
        sa.CheckConstraint('total_amount > 0', name='chk_cust_receipt_total_positive'),
        sa.CheckConstraint('allocated_amount >= 0', name='chk_cust_receipt_allocated_non_neg'),
        sa.CheckConstraint('unallocated_amount >= 0', name='chk_cust_receipt_unallocated_non_neg'),
        sa.CheckConstraint('discount_amount >= 0', name='chk_cust_receipt_discount_non_neg'),
        sa.CheckConstraint("status IN ('POSTED', 'REVERSED', 'CANCELLED')", name='chk_cust_receipt_status')
    )
    op.create_index('ix_cust_receipts_company_date', 'customer_receipts', ['company_id', 'receipt_date'])
    op.create_index('ix_cust_receipts_customer', 'customer_receipts', ['company_id', 'customer_account_id'])
    op.create_index('ix_cust_receipts_deposit', 'customer_receipts', ['company_id', 'deposit_account_id'])

    # 2. Create receipt_allocations table
    op.create_table(
        'receipt_allocations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('receipt_id', sa.String(length=36), nullable=False),
        sa.Column('invoice_id', sa.String(length=36), nullable=False),
        sa.Column('allocated_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('discount_amount', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['receipt_id'], ['customer_receipts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invoice_id'], ['sales_invoices.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('receipt_id', 'invoice_id', name='uq_ralloc_receipt_invoice'),
        sa.CheckConstraint('allocated_amount > 0', name='chk_ralloc_allocated_positive'),
        sa.CheckConstraint('discount_amount >= 0', name='chk_ralloc_discount_non_neg')
    )
    op.create_index('ix_ralloc_receipt', 'receipt_allocations', ['receipt_id'])
    op.create_index('ix_ralloc_invoice', 'receipt_allocations', ['invoice_id'])

    # 3. Create supplier_payments table
    op.create_table(
        'supplier_payments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=False),
        sa.Column('financial_year', sa.String(length=20), nullable=False),
        sa.Column('voucher_number', sa.String(length=50), nullable=False),
        sa.Column('payment_date', sa.String(length=20), nullable=False),
        sa.Column('supplier_account_id', sa.String(length=36), nullable=False),
        sa.Column('source_account_id', sa.String(length=36), nullable=False),
        sa.Column('payment_method', sa.String(length=50), server_default='CASH', nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('allocated_amount', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=False),
        sa.Column('unallocated_amount', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=False),
        sa.Column('discount_amount', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=False),
        sa.Column('reference_number', sa.String(length=100), nullable=True),
        sa.Column('reference_date', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('journal_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='POSTED', nullable=False),
        sa.Column('reversal_of_id', sa.String(length=36), nullable=True),
        sa.Column('reversal_reason', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['supplier_account_id'], ['accounts.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['source_account_id'], ['accounts.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['journal_id'], ['journal_entries.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reversal_of_id'], ['supplier_payments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'financial_year', 'voucher_number', name='uq_supp_payments_company_fy_vch'),
        sa.UniqueConstraint('company_id', 'idempotency_key', name='uq_supp_payments_idempotency'),
        sa.CheckConstraint('total_amount > 0', name='chk_supp_payment_total_positive'),
        sa.CheckConstraint('allocated_amount >= 0', name='chk_supp_payment_allocated_non_neg'),
        sa.CheckConstraint('unallocated_amount >= 0', name='chk_supp_payment_unallocated_non_neg'),
        sa.CheckConstraint('discount_amount >= 0', name='chk_supp_payment_discount_non_neg'),
        sa.CheckConstraint("status IN ('POSTED', 'REVERSED', 'CANCELLED')", name='chk_supp_payment_status')
    )
    op.create_index('ix_supp_payments_company_date', 'supplier_payments', ['company_id', 'payment_date'])
    op.create_index('ix_supp_payments_supplier', 'supplier_payments', ['company_id', 'supplier_account_id'])
    op.create_index('ix_supp_payments_source', 'supplier_payments', ['company_id', 'source_account_id'])

    # 4. Create payment_allocations table
    op.create_table(
        'payment_allocations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('payment_id', sa.String(length=36), nullable=False),
        sa.Column('purchase_voucher_id', sa.String(length=36), nullable=True),
        sa.Column('bill_number', sa.String(length=100), nullable=True),
        sa.Column('allocated_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('discount_amount', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=False),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['payment_id'], ['supplier_payments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('allocated_amount > 0', name='chk_palloc_allocated_positive'),
        sa.CheckConstraint('discount_amount >= 0', name='chk_palloc_discount_non_neg')
    )
    op.create_index('ix_palloc_payment', 'payment_allocations', ['payment_id'])
    op.create_index('ix_palloc_bill_no', 'payment_allocations', ['bill_number'])
    op.create_index('ix_palloc_purchase_vch', 'payment_allocations', ['purchase_voucher_id'])


def downgrade() -> None:
    op.drop_table('payment_allocations')
    op.drop_table('supplier_payments')
    op.drop_table('receipt_allocations')
    op.drop_table('customer_receipts')
