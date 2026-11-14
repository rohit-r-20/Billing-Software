"""001_foundation_schema

Revision ID: 001_foundation_schema
Revises: 
Create Date: 2026-11-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_foundation_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. companies
    op.create_table(
        'companies',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('fin_year', sa.String(length=20), nullable=True),
        sa.Column('gstin', sa.String(length=15), nullable=True),
        sa.Column('state', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_companies_code')
    )
    op.create_index('ix_companies_code', 'companies', ['code'])

    # 2. branches
    op.create_table(
        'branches',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("code = 'BR01'", name='chk_branches_single_branch_br01'),
        sa.UniqueConstraint('company_id', 'code', name='uq_branches_company_code')
    )
    op.create_index('ix_branches_company_id', 'branches', ['company_id'])

    # 3. roles
    op.create_table(
        'roles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_roles_name')
    )
    op.create_index('ix_roles_name', 'roles', ['name'])

    # 4. users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=True),
        sa.Column('role_name', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_name'], ['roles.name']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'username', name='uq_users_company_username')
    )
    op.create_index('ix_users_company_id', 'users', ['company_id'])

    # 5. accounts
    op.create_table(
        'accounts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('account_type', sa.String(length=30), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'code', name='uq_accounts_company_code')
    )
    op.create_index('ix_accounts_company_id', 'accounts', ['company_id'])

    # 6. items
    op.create_table(
        'items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('sku', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('print_name', sa.String(length=255), nullable=True),
        sa.Column('tax_category', sa.String(length=50), nullable=True),
        sa.Column('tax_rate_percent', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0.00'),
        sa.Column('selling_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('cogs_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('selling_price >= 0', name='chk_items_selling_price_non_neg'),
        sa.CheckConstraint('cogs_amount >= 0', name='chk_items_cogs_non_neg'),
        sa.UniqueConstraint('company_id', 'sku', name='uq_items_company_sku')
    )
    op.create_index('ix_items_company_id', 'items', ['company_id'])

    # 7. item_barcodes
    op.create_table(
        'item_barcodes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('item_id', sa.String(length=36), nullable=False),
        sa.Column('barcode', sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'barcode', name='uq_item_barcodes_company_barcode')
    )
    op.create_index('ix_item_barcodes_company_id', 'item_barcodes', ['company_id'])
    op.create_index('ix_item_barcodes_item_id', 'item_barcodes', ['item_id'])

    # 8. stock_balances
    op.create_table(
        'stock_balances',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('branch_id', sa.String(length=36), nullable=False),
        sa.Column('item_id', sa.String(length=36), nullable=False),
        sa.Column('current_qty_scaled', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('current_qty_scaled >= 0', name='chk_stock_balances_qty_non_neg'),
        sa.UniqueConstraint('company_id', 'branch_id', 'item_id', name='uq_stock_balances_company_branch_item')
    )
    op.create_index('ix_stock_balances_company_id', 'stock_balances', ['company_id'])

    # 9. audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=True),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_company_created', 'audit_logs', ['company_id', 'created_at'])

    # Seed Standard System Roles
    roles_table = sa.table(
        'roles',
        sa.column('id', sa.String),
        sa.column('name', sa.String),
        sa.column('description', sa.Text),
    )
    op.bulk_insert(
        roles_table,
        [
            {'id': 'role_admin', 'name': 'Administrator', 'description': 'Full system administrator'},
            {'id': 'role_store_manager', 'name': 'Store Manager', 'description': 'Store operations manager'},
            {'id': 'role_manager', 'name': 'Manager', 'description': 'General business manager'},
            {'id': 'role_cashier', 'name': 'Cashier', 'description': 'Front desk point-of-sale cashier'},
        ]
    )


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('stock_balances')
    op.drop_table('item_barcodes')
    op.drop_table('items')
    op.drop_table('accounts')
    op.drop_table('users')
    op.drop_table('roles')
    op.drop_table('branches')
    op.drop_table('companies')
