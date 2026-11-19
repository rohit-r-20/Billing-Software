"""005_bill_layout_configuration

Revision ID: 005_bill_layout_configuration
Revises: 004_paper_configuration
Create Date: 2026-11-16 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_bill_layout_configuration'
down_revision: Union[str, None] = '004_paper_configuration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'bill_layout_configurations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=True),
        sa.Column('voucher_type', sa.String(length=50), nullable=False),  # sales_invoice, sales_return, purchase_invoice, purchase_return
        sa.Column('layout_name', sa.String(length=100), server_default='Standard Layout', nullable=False),
        sa.Column('header_config', sa.Text(), nullable=False),  # JSON serialized
        sa.Column('invoice_info_config', sa.Text(), nullable=False),  # JSON serialized
        sa.Column('columns_config', sa.Text(), nullable=False),  # JSON serialized
        sa.Column('totals_config', sa.Text(), nullable=False),  # JSON serialized
        sa.Column('footer_config', sa.Text(), nullable=False),  # JSON serialized
        sa.Column('style_config', sa.Text(), nullable=False),  # JSON serialized
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'voucher_type', name='uq_bill_layout_scope')
    )


def downgrade() -> None:
    op.drop_table('bill_layout_configurations')
