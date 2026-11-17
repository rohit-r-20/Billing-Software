"""005_traditional_accounting_foundation

Revision ID: 005_traditional_accounting_foundation
Revises: 004_inventory_movements_and_adjustments
Create Date: 2026-11-16 16:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_traditional_accounting_foundation'
down_revision: Union[str, None] = '004_inventory_movements_and_adjustments'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create account_groups table
    op.create_table(
        'account_groups',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('nature', sa.String(length=20), nullable=False),
        sa.Column('parent_group_id', sa.String(length=36), nullable=True),
        sa.Column('is_system', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_group_id'], ['account_groups.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'code', name='uq_account_groups_company_code'),
        sa.CheckConstraint("nature IN ('ASSET', 'LIABILITY', 'EQUITY', 'INCOME', 'EXPENSE')", name='chk_account_groups_nature')
    )
    op.create_index('ix_account_groups_company', 'account_groups', ['company_id'])

    # 2. Create account_group_mappings table (enhances accounts without mutating accounts table)
    op.create_table(
        'account_group_mappings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('account_id', sa.String(length=36), nullable=False),
        sa.Column('group_id', sa.String(length=36), nullable=False),
        sa.Column('account_nature', sa.String(length=20), nullable=False),
        sa.Column('opening_balance', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=False),
        sa.Column('opening_balance_type', sa.String(length=2), server_default='DR', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['account_groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'account_id', name='uq_account_group_mappings_account'),
        sa.CheckConstraint("account_nature IN ('ASSET', 'LIABILITY', 'EQUITY', 'INCOME', 'EXPENSE')", name='chk_agm_nature'),
        sa.CheckConstraint("opening_balance_type IN ('DR', 'CR')", name='chk_agm_op_type')
    )
    op.create_index('ix_agm_company_group', 'account_group_mappings', ['company_id', 'group_id'])

    # 3. Create accounting_periods table
    op.create_table(
        'accounting_periods',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('financial_year', sa.String(length=20), nullable=False),
        sa.Column('period_name', sa.String(length=50), nullable=False),
        sa.Column('start_date', sa.String(length=10), nullable=False),
        sa.Column('end_date', sa.String(length=10), nullable=False),
        sa.Column('is_closed', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('closed_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['closed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'financial_year', 'period_name', name='uq_accounting_periods_company_fy_name'),
        sa.CheckConstraint('start_date <= end_date', name='chk_accounting_periods_dates')
    )
    op.create_index('ix_accounting_periods_company_dates', 'accounting_periods', ['company_id', 'start_date', 'end_date'])

    # 4. Create journal_entries table
    op.create_table(
        'journal_entries',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=False),
        sa.Column('financial_year', sa.String(length=20), nullable=False),
        sa.Column('voucher_number', sa.String(length=50), nullable=False),
        sa.Column('voucher_type', sa.String(length=30), nullable=False),
        sa.Column('voucher_date', sa.String(length=10), nullable=False),
        sa.Column('narration', sa.Text(), nullable=True),
        sa.Column('total_debit', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('total_credit', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='POSTED', nullable=False),
        sa.Column('reference_type', sa.String(length=50), nullable=True),
        sa.Column('reference_id', sa.String(length=100), nullable=True),
        sa.Column('reversal_of_id', sa.String(length=36), nullable=True),
        sa.Column('reversed_by_id', sa.String(length=36), nullable=True),
        sa.Column('reversal_reason', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=128), nullable=True),
        sa.Column('posted_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['posted_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reversal_of_id'], ['journal_entries.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reversed_by_id'], ['journal_entries.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'branch_id', 'financial_year', 'voucher_type', 'voucher_number', name='uq_journal_entries_scope_vch'),
        sa.UniqueConstraint('company_id', 'idempotency_key', name='uq_journal_entries_idempotency'),
        sa.CheckConstraint('total_debit = total_credit', name='chk_journal_entries_total_balanced'),
        sa.CheckConstraint('total_debit > 0', name='chk_journal_entries_total_positive'),
        sa.CheckConstraint("status IN ('DRAFT', 'POSTED', 'REVERSED')", name='chk_journal_entries_status')
    )
    op.create_index('ix_journal_entries_company_date', 'journal_entries', ['company_id', 'voucher_date'])
    op.create_index('ix_journal_entries_ref', 'journal_entries', ['company_id', 'reference_type', 'reference_id'])

    # 5. Create journal_entry_lines table
    op.create_table(
        'journal_entry_lines',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('journal_id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.String(length=36), nullable=False),
        sa.Column('debit', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=False),
        sa.Column('credit', sa.Numeric(precision=15, scale=2), server_default='0.00', nullable=False),
        sa.Column('narration', sa.Text(), nullable=True),
        sa.Column('party_type', sa.String(length=30), nullable=True),
        sa.Column('party_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['journal_id'], ['journal_entries.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('journal_id', 'line_number', name='uq_journal_entry_lines_journal_line'),
        sa.CheckConstraint('debit >= 0', name='chk_jlines_debit_non_neg'),
        sa.CheckConstraint('credit >= 0', name='chk_jlines_credit_non_neg'),
        sa.CheckConstraint('((debit > 0 AND credit == 0) OR (credit > 0 AND debit == 0))', name='chk_jlines_one_side_nonzero')
    )
    op.create_index('ix_jlines_company_account', 'journal_entry_lines', ['company_id', 'account_id', 'created_at'])


def downgrade() -> None:
    op.drop_table('journal_entry_lines')
    op.drop_table('journal_entries')
    op.drop_table('accounting_periods')
    op.drop_table('account_group_mappings')
    op.drop_table('account_groups')
