"""004_paper_configuration

Revision ID: 004_paper_configuration
Revises: 003_sales_voucher_sequences
Create Date: 2026-11-15 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_paper_configuration'
down_revision: Union[str, None] = '006_financial_year_closing_and_opening_balances'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'paper_configurations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=True),
        sa.Column('paper_format', sa.String(length=20), nullable=False),
        sa.Column('width_mm', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('height_mm', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('orientation', sa.String(length=20), server_default='portrait', nullable=False),
        sa.Column('margin_top_mm', sa.Numeric(precision=10, scale=2), server_default='10.0', nullable=False),
        sa.Column('margin_bottom_mm', sa.Numeric(precision=10, scale=2), server_default='10.0', nullable=False),
        sa.Column('margin_left_mm', sa.Numeric(precision=10, scale=2), server_default='10.0', nullable=False),
        sa.Column('margin_right_mm', sa.Numeric(precision=10, scale=2), server_default='10.0', nullable=False),
        sa.Column('default_printer', sa.String(length=255), server_default='', nullable=True),
        sa.Column('print_scaling', sa.Integer(), server_default='100', nullable=False),
        sa.Column('header_spacing_mm', sa.Numeric(precision=10, scale=2), server_default='5.0', nullable=False),
        sa.Column('footer_spacing_mm', sa.Numeric(precision=10, scale=2), server_default='5.0', nullable=False),
        sa.Column('page_numbering', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('thermal_paper_width_type', sa.String(length=20), server_default='80mm', nullable=True),
        sa.Column('printable_width_mm', sa.Numeric(precision=10, scale=2), server_default='72.0', nullable=True),
        sa.Column('print_density', sa.String(length=50), server_default='Normal', nullable=True),
        sa.Column('font_size', sa.Integer(), server_default='10', nullable=True),
        sa.Column('line_spacing', sa.Numeric(precision=5, scale=2), server_default='1.2', nullable=True),
        sa.Column('char_alignment', sa.String(length=20), server_default='left', nullable=True),
        sa.Column('auto_cut', sa.Boolean(), server_default=sa.true(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'paper_format', name='uq_paper_configurations_scope')
    )
    op.create_index(
        'ix_paper_configurations_scope',
        'paper_configurations',
        ['company_id', 'paper_format']
    )


def downgrade() -> None:
    op.drop_index('ix_paper_configurations_scope', table_name='paper_configurations')
    op.drop_table('paper_configurations')
