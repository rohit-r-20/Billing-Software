"""009_merge_config_and_payments

Revision ID: 009_merge_config_and_payments
Revises: 007_payment_and_receipt_management, 008_inventory_configuration
Create Date: 2026-11-17 21:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_merge_config_and_payments'
down_revision: Union[str, Sequence[str], None] = ('007_payment_and_receipt_management', '008_inventory_configuration')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
