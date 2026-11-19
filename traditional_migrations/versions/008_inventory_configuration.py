"""008_inventory_configuration

Revision ID: 008_inventory_configuration
Revises: 007_gst_tax_configuration
Create Date: 2026-11-17 11:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008_inventory_configuration'
down_revision: Union[str, None] = '007_gst_tax_configuration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'inventory_configurations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=True),
        sa.Column('enable_inventory_tracking', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('default_uom', sa.String(length=30), server_default='Pcs.', nullable=False),
        sa.Column('qty_decimal_precision', sa.Integer(), server_default='3', nullable=False),
        sa.Column('allow_fractional_qty', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('default_product_type', sa.String(length=50), server_default='Stockable', nullable=False),
        sa.Column('auto_generate_sku', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('barcode_symbology', sa.String(length=30), server_default='EAN-13', nullable=False),
        sa.Column('allow_negative_stock', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('validate_stock_on_sale', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('stock_warning_behavior', sa.String(length=30), server_default='warn_and_allow', nullable=False),
        sa.Column('low_stock_alert_enabled', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('default_min_stock_level', sa.Numeric(precision=12, scale=3), server_default='10.000', nullable=False),
        sa.Column('default_reorder_level', sa.Numeric(precision=12, scale=3), server_default='15.000', nullable=False),
        sa.Column('default_reorder_qty', sa.Numeric(precision=12, scale=3), server_default='50.000', nullable=False),
        sa.Column('default_max_stock_level', sa.Numeric(precision=12, scale=3), server_default='500.000', nullable=False),
        sa.Column('valuation_method', sa.String(length=30), server_default='weighted_average', nullable=False),
        sa.Column('default_material_centre', sa.String(length=100), server_default='Main Store', nullable=False),
        sa.Column('track_branch_stock', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('allow_inter_branch_transfer', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('enable_batch_tracking', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('enable_expiry_tracking', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('enable_barcode_tracking', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('link_hsn_sac', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('warn_on_low_stock', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('warn_on_negative_stock', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('warn_on_expiry', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('expiry_warning_days', sa.Integer(), server_default='30', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'branch_id', name='uq_inventory_cfg_scope')
    )
    op.create_index(
        'ix_inventory_cfg_lookup',
        'inventory_configurations',
        ['company_id']
    )


def downgrade() -> None:
    op.drop_index('ix_inventory_cfg_lookup', table_name='inventory_configurations')
    op.drop_table('inventory_configurations')
