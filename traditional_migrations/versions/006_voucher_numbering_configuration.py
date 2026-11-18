"""006_voucher_numbering_configuration

Revision ID: 006_voucher_numbering_configuration
Revises: 005_bill_layout_configuration
Create Date: 2026-11-16 21:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_voucher_numbering_configuration'
down_revision: Union[str, None] = '005_bill_layout_configuration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'voucher_numbering_configurations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=True),
        sa.Column('voucher_type', sa.String(length=50), nullable=False),  # sales_invoice, sales_return, purchase_invoice, purchase_return
        sa.Column('series', sa.String(length=50), server_default='Main', nullable=False),
        sa.Column('is_custom_enabled', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('prefix', sa.String(length=50), server_default='', nullable=False),
        sa.Column('start_number', sa.BigInteger(), server_default='1', nullable=False),
        sa.Column('padding', sa.Integer(), server_default='4', nullable=False),
        sa.Column('suffix', sa.String(length=50), server_default='', nullable=False),
        sa.Column('include_financial_year', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('fy_format', sa.String(length=20), server_default='YYYY-YY', nullable=False),
        sa.Column('fy_separator', sa.String(length=10), server_default='/', nullable=False),
        sa.Column('include_branch_code', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('branch_position', sa.String(length=20), server_default='prefix', nullable=False),
        sa.Column('reset_frequency', sa.String(length=20), server_default='yearly', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'branch_id', 'voucher_type', 'series', name='uq_vch_numbering_cfg_scope')
    )
    op.create_index(
        'ix_vch_numbering_cfg_lookup',
        'voucher_numbering_configurations',
        ['company_id', 'voucher_type', 'series']
    )


def downgrade() -> None:
    op.drop_index('ix_vch_numbering_cfg_lookup', table_name='voucher_numbering_configurations')
    op.drop_table('voucher_numbering_configurations')
