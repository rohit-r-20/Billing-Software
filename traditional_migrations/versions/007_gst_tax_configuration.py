"""007_gst_tax_configuration

Revision ID: 007_gst_tax_configuration
Revises: 006_voucher_numbering_configuration
Create Date: 2026-11-16 22:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_gst_tax_configuration'
down_revision: Union[str, None] = '006_voucher_numbering_configuration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'gst_tax_configurations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=True),
        sa.Column('is_gst_enabled', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('gstin', sa.String(length=15), nullable=True),
        sa.Column('legal_name', sa.String(length=255), nullable=True),
        sa.Column('trade_name', sa.String(length=255), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('state_code', sa.String(length=10), nullable=True),
        sa.Column('registration_type', sa.String(length=50), server_default='Regular', nullable=False),
        sa.Column('default_place_of_supply', sa.String(length=100), nullable=True),
        sa.Column('default_tax_mode', sa.String(length=20), server_default='exclusive', nullable=False),
        sa.Column('default_tax_rate', sa.Numeric(precision=5, scale=2), server_default='18.00', nullable=False),
        sa.Column('supported_tax_rates_json', sa.Text(), server_default='["0.00", "5.00", "12.00", "18.00", "28.00"]', nullable=False),
        sa.Column('enable_cess', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('default_cess_rate', sa.Numeric(precision=5, scale=2), server_default='0.00', nullable=False),
        sa.Column('tax_rounding_rule', sa.String(length=30), server_default='nearest_rupee', nullable=False),
        sa.Column('decimal_precision_currency', sa.Integer(), server_default='2', nullable=False),
        sa.Column('decimal_precision_qty', sa.Integer(), server_default='3', nullable=False),
        sa.Column('hsn_enforcement_mode', sa.String(length=30), server_default='optional', nullable=False),
        sa.Column('show_hsn_summary', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('enable_rcm', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('transaction_defaults_json', sa.Text(), server_default='{}', nullable=False),
        sa.Column('effective_from', sa.String(length=20), server_default='', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'branch_id', name='uq_gst_tax_cfg_scope')
    )
    op.create_index(
        'ix_gst_tax_cfg_lookup',
        'gst_tax_configurations',
        ['company_id']
    )


def downgrade() -> None:
    op.drop_index('ix_gst_tax_cfg_lookup', table_name='gst_tax_configurations')
    op.drop_table('gst_tax_configurations')
