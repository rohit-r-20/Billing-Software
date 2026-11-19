"""006_financial_year_closing_and_opening_balances

Revision ID: 006_financial_year_closing_and_opening_balances
Revises: 005_traditional_accounting_foundation
Create Date: 2026-11-16 17:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_financial_year_closing_and_opening_balances'
down_revision: Union[str, None] = '005_traditional_accounting_foundation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create financial_year_closings table
    op.create_table(
        'financial_year_closings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=False),
        sa.Column('financial_year', sa.String(length=20), nullable=False),
        sa.Column('closing_date', sa.String(length=10), nullable=False),
        sa.Column('closing_journal_id', sa.String(length=36), nullable=True),
        sa.Column('next_financial_year', sa.String(length=20), nullable=True),
        sa.Column('next_opening_journal_id', sa.String(length=36), nullable=True),
        sa.Column('net_profit', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='CLOSED', nullable=False),
        sa.Column('closed_by', sa.String(length=36), nullable=True),
        sa.Column('reopened_by', sa.String(length=36), nullable=True),
        sa.Column('reopened_at', sa.DateTime(), nullable=True),
        sa.Column('reopen_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['closing_journal_id'], ['journal_entries.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['next_opening_journal_id'], ['journal_entries.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['closed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reopened_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'financial_year', name='uq_fy_closings_company_fy'),
        sa.CheckConstraint("status IN ('CLOSED', 'REOPENED')", name='chk_fy_closings_status')
    )
    op.create_index('ix_fy_closings_company_date', 'financial_year_closings', ['company_id', 'closing_date'])


def downgrade() -> None:
    op.drop_table('financial_year_closings')
