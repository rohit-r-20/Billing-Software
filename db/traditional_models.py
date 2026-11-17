"""
Traditional Billing Database Models (SQLAlchemy Declarative).
Defines the foundation and master tables for Traditional Billing:
1. companies
2. branches (single BR01 per company)
3. roles
4. users
5. accounts (General Ledger & Debtors/Customers)
6. items
7. item_barcodes
8. barcode_reservations
9. stock_balances (current_qty_scaled >= 0)
10. audit_logs
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Numeric,
    BigInteger,
    Integer,
    Text,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.types import TypeDecorator

TraditionalBase = declarative_base()


def generate_uuid() -> str:
    """Generates a UUID4 string for primary keys."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Returns current UTC timestamp (timezone-aware)."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Normalizes any datetime to a timezone-aware UTC datetime:
    - If dt is None: returns None.
    - If dt is naive (tzinfo is None, e.g. loaded from SQLite): assumes it represents UTC
      and attaches timezone.utc (replace(tzinfo=timezone.utc)), NEVER converting from local time.
    - If dt is aware (tzinfo is not None): converts it to UTC (.astimezone(timezone.utc)).
    """
    if dt is None:
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class UTCDateTime(TypeDecorator):
    """
    SQLAlchemy TypeDecorator for timezone-aware UTC datetimes.
    - On write / bind: converts aware datetime to UTC and stores naive UTC for SQLite (or aware for Postgres).
    - On read / result: normalizes naive UTC timestamp from SQLite to timezone-aware UTC (replace tzinfo=utc).
    """
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                if dialect is None or dialect.name == "sqlite":
                    return value.astimezone(timezone.utc).replace(tzinfo=None)
                return value.astimezone(timezone.utc)
            return value
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value


class Company(TraditionalBase):
    __tablename__ = "companies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    fin_year = Column(String(20), nullable=True)
    gstin = Column(String(15), nullable=True)
    state = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    branches = relationship("Branch", back_populates="company", cascade="all, delete-orphan")
    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    accounts = relationship("Account", back_populates="company", cascade="all, delete-orphan")
    account_groups = relationship("AccountGroup", back_populates="company", cascade="all, delete-orphan")
    accounting_periods = relationship("AccountingPeriod", back_populates="company", cascade="all, delete-orphan")
    journal_entries = relationship("JournalEntry", back_populates="company", cascade="all, delete-orphan")
    year_closings = relationship("FinancialYearClosing", back_populates="company", cascade="all, delete-orphan")
    items = relationship("Item", back_populates="company", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="company", cascade="all, delete-orphan")
    stock_movements = relationship("StockMovement", back_populates="company", cascade="all, delete-orphan")
    stock_adjustments = relationship("StockAdjustment", back_populates="company", cascade="all, delete-orphan")
    stock_transfers = relationship("StockTransfer", back_populates="company", cascade="all, delete-orphan")


class Branch(TraditionalBase):
    __tablename__ = "branches"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)

    company = relationship("Company", back_populates="branches")

    __table_args__ = (
        CheckConstraint("code = 'BR01'", name="chk_branches_single_branch_br01"),
        UniqueConstraint("company_id", "code", name="uq_branches_company_code"),
        UniqueConstraint("company_id", name="uq_branches_single_tenant_branch"),
    )


class Role(TraditionalBase):
    __tablename__ = "roles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)


class User(TraditionalBase):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String(50), nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    role_name = Column(String(50), ForeignKey("roles.name"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    company = relationship("Company", back_populates="users")

    __table_args__ = (
        UniqueConstraint("company_id", "username", name="uq_users_company_username"),
    )


class AccountGroup(TraditionalBase):
    __tablename__ = "account_groups"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    nature = Column(String(20), nullable=False)  # ASSET, LIABILITY, EQUITY, INCOME, EXPENSE
    parent_group_id = Column(String(36), ForeignKey("account_groups.id", ondelete="SET NULL"), nullable=True)
    is_system = Column(Boolean, default=False, nullable=False)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)

    company = relationship("Company", back_populates="account_groups")
    parent_group = relationship("AccountGroup", remote_side=[id], backref="subgroups")
    mappings = relationship("AccountGroupMapping", back_populates="group", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_account_groups_company_code"),
        CheckConstraint("nature IN ('ASSET', 'LIABILITY', 'EQUITY', 'INCOME', 'EXPENSE')", name="chk_account_groups_nature"),
    )


class Account(TraditionalBase):
    __tablename__ = "accounts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    account_type = Column(String(30), nullable=False)  # 'Debtor', 'Creditor', 'Cash', 'Bank', 'Sales', etc.
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    gstin = Column(String(15), nullable=True)
    state = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=True)

    company = relationship("Company", back_populates="accounts")
    group_mapping = relationship("AccountGroupMapping", uselist=False, back_populates="account", cascade="all, delete-orphan")
    journal_lines = relationship("JournalEntryLine", back_populates="account")

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_accounts_company_code"),
    )

    @property
    def group_id(self):
        return self.group_mapping.group_id if self.group_mapping else None

    @property
    def account_nature(self):
        return self.group_mapping.account_nature if self.group_mapping else None

    @property
    def opening_balance(self):
        return self.group_mapping.opening_balance if self.group_mapping else Decimal("0.00")

    @property
    def opening_balance_type(self):
        return self.group_mapping.opening_balance_type if self.group_mapping else "DR"


class AccountGroupMapping(TraditionalBase):
    __tablename__ = "account_group_mappings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id = Column(String(36), ForeignKey("account_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    account_nature = Column(String(20), nullable=False)
    opening_balance = Column(Numeric(15, 2), server_default="0.00", default=0.00, nullable=False)
    opening_balance_type = Column(String(2), server_default="DR", default="DR", nullable=False)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    company = relationship("Company")
    account = relationship("Account", back_populates="group_mapping")
    group = relationship("AccountGroup", back_populates="mappings")

    __table_args__ = (
        UniqueConstraint("company_id", "account_id", name="uq_account_group_mappings_account"),
        Index("ix_agm_company_group", "company_id", "group_id"),
        CheckConstraint("account_nature IN ('ASSET', 'LIABILITY', 'EQUITY', 'INCOME', 'EXPENSE')", name="chk_agm_nature"),
        CheckConstraint("opening_balance_type IN ('DR', 'CR')", name="chk_agm_op_type"),
    )


class Item(TraditionalBase):
    __tablename__ = "items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    print_name = Column(String(255), nullable=True)
    unit = Column(String(20), default="Pcs.", nullable=False)
    category = Column(String(100), nullable=True)
    hsn = Column(String(20), nullable=True)
    tax_category = Column(String(50), nullable=True)
    tax_rate_percent = Column(Numeric(5, 2), default=0.00, nullable=False)
    selling_price = Column(Numeric(12, 2), nullable=False)
    cogs_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    mrp = Column(Numeric(12, 2), nullable=True)
    min_sales_price = Column(Numeric(12, 2), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    company = relationship("Company", back_populates="items")
    barcodes = relationship("ItemBarcode", back_populates="item", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("company_id", "sku", name="uq_items_company_sku"),
        CheckConstraint("selling_price >= 0", name="chk_items_selling_price_non_neg"),
        CheckConstraint("cogs_amount >= 0", name="chk_items_cogs_non_neg"),
    )


class ItemBarcode(TraditionalBase):
    __tablename__ = "item_barcodes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    barcode = Column(String(100), nullable=False)

    item = relationship("Item", back_populates="barcodes")

    __table_args__ = (
        UniqueConstraint("company_id", "barcode", name="uq_item_barcodes_company_barcode"),
    )


class BarcodeReservation(TraditionalBase):
    __tablename__ = "barcode_reservations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    barcode = Column(String(100), nullable=False)
    reserved_by = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(UTCDateTime, nullable=False)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "barcode", name="uq_barcode_reservations_company_barcode"),
        Index("ix_barcode_reservations_company_expiry", "company_id", "expires_at"),
    )


class StockBalance(TraditionalBase):
    __tablename__ = "stock_balances"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    current_qty_scaled = Column(BigInteger, default=0, nullable=False)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "branch_id", "item_id", name="uq_stock_balances_company_branch_item"),
        CheckConstraint("current_qty_scaled >= 0", name="chk_stock_balances_qty_non_neg"),
    )


class AuditLog(TraditionalBase):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=True)
    event_type = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(36), nullable=True)
    payload_json = Column(Text, nullable=True)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)

    company = relationship("Company", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_company_created", "company_id", "created_at"),
    )


class VoucherSequence(TraditionalBase):
    __tablename__ = "voucher_sequences"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year = Column(String(20), nullable=False)
    series = Column(String(50), server_default="Main", default="Main", nullable=False)
    current_number = Column(BigInteger, server_default="0", default=0, nullable=False)
    prefix = Column(String(20), server_default="", default="", nullable=True)
    padding = Column(Integer, server_default="3", default=3, nullable=False)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    company = relationship("Company")
    branch = relationship("Branch")

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "branch_id",
            "financial_year",
            "series",
            name="uq_voucher_sequences_scope",
        ),
        Index("ix_voucher_sequences_scope", "company_id", "branch_id", "financial_year", "series"),
    )


class SaleInvoice(TraditionalBase):
    __tablename__ = "sales_invoices"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    voucher_id = Column(String(36), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    financial_year = Column(String(20), nullable=False)
    series = Column(String(50), server_default="Main", default="Main", nullable=False)
    sequence_number = Column(BigInteger, nullable=False)
    voucher_number = Column(String(50), nullable=False)
    vch_date = Column(String(20), nullable=False)
    party_name = Column(String(255), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    customer_category = Column(String(50), nullable=True)
    sale_type = Column(String(50), nullable=False)
    payment_method = Column(String(50), server_default="CASH", default="CASH", nullable=False)
    narration = Column(Text, nullable=True)
    subtotal = Column(Numeric(12, 2), nullable=False)
    taxable_amount = Column(Numeric(12, 2), nullable=False)
    cgst_amount = Column(Numeric(12, 2), server_default="0.00", default=0.0, nullable=False)
    sgst_amount = Column(Numeric(12, 2), server_default="0.00", default=0.0, nullable=False)
    igst_amount = Column(Numeric(12, 2), server_default="0.00", default=0.0, nullable=False)
    round_off_amount = Column(Numeric(12, 2), server_default="0.00", default=0.0, nullable=False)
    grand_total = Column(Numeric(12, 2), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=True)
    payment_mode = Column(String(50), server_default="CASH", default="CASH", nullable=True)
    status = Column(String(20), server_default="PAID", default="PAID", nullable=True)
    items_json = Column(Text, nullable=False)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)

    company = relationship("Company")
    branch = relationship("Branch")
    account = relationship("Account")

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "branch_id",
            "financial_year",
            "series",
            "voucher_number",
            name="uq_sales_invoices_scope_vch_no",
        ),
        UniqueConstraint(
            "company_id",
            "branch_id",
            "financial_year",
            "series",
            "sequence_number",
            name="uq_sales_invoices_scope_seq_no",
        ),
        Index("ix_sales_invoices_scope_date", "company_id", "branch_id", "vch_date"),
    )


class StockMovement(TraditionalBase):
    __tablename__ = "stock_movements"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    movement_type = Column(String(30), nullable=False)  # OPENING, PURCHASE, SALE, ADJUSTMENT, TRANSFER_IN, TRANSFER_OUT, SALES_RETURN, PURCHASE_RETURN, REVERSAL
    qty_scaled = Column(BigInteger, nullable=False)  # Scaled by 1000 (positive = inward, negative = outward)
    unit_cost = Column(Numeric(12, 2), server_default="0.00", default=0.00, nullable=False)
    reference_type = Column(String(50), nullable=True)  # OPENING, PURCHASE_VOUCHER, SALES_INVOICE, STOCK_ADJUSTMENT, STOCK_TRANSFER, SALES_RETURN, PURCHASE_RETURN
    reference_id = Column(String(100), nullable=True)
    idempotency_key = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)

    company = relationship("Company", back_populates="stock_movements")
    branch = relationship("Branch")
    item = relationship("Item")
    user = relationship("User")

    __table_args__ = (
        Index("ix_stock_movements_company_item", "company_id", "item_id"),
        Index("ix_stock_movements_company_branch_date", "company_id", "branch_id", "created_at"),
        Index("ix_stock_movements_reference", "company_id", "reference_type", "reference_id"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_stock_movements_company_idempotency"),
    )


class StockAdjustment(TraditionalBase):
    __tablename__ = "stock_adjustments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    item_name = Column(String(255), nullable=False)
    adjustment_type = Column(String(50), nullable=False)  # DAMAGE, PHYSICAL_COUNT, EXPIRED, OPENING, CORRECTION
    quantity_scaled = Column(BigInteger, nullable=False)  # Scaled by 1000
    quantity = Column(Numeric(12, 3), nullable=False)
    unit_cost = Column(Numeric(12, 2), server_default="0.00", default=0.00, nullable=False)
    reason = Column(Text, nullable=True)
    authorized_by = Column(String(100), nullable=True)
    idempotency_key = Column(String(100), nullable=True)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)

    company = relationship("Company", back_populates="stock_adjustments")
    branch = relationship("Branch")
    item = relationship("Item")

    __table_args__ = (
        Index("ix_stock_adjustments_company_created", "company_id", "created_at"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_stock_adjustments_company_idempotency"),
    )


class StockTransfer(TraditionalBase):
    __tablename__ = "stock_transfers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    source_branch_id = Column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    dest_branch_id = Column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    item_name = Column(String(255), nullable=False)
    quantity_scaled = Column(BigInteger, nullable=False)  # Scaled by 1000
    quantity = Column(Numeric(12, 3), nullable=False)
    transfer_number = Column(String(50), nullable=False)
    reason = Column(Text, nullable=True)
    authorized_by = Column(String(100), nullable=True)
    idempotency_key = Column(String(100), nullable=True)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)

    company = relationship("Company", back_populates="stock_transfers")
    source_branch = relationship("Branch", foreign_keys=[source_branch_id])
    dest_branch = relationship("Branch", foreign_keys=[dest_branch_id])
    item = relationship("Item")

    __table_args__ = (
        Index("ix_stock_transfers_company_created", "company_id", "created_at"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_stock_transfers_company_idempotency"),
    )


class AccountingPeriod(TraditionalBase):
    __tablename__ = "accounting_periods"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year = Column(String(20), nullable=False)
    period_name = Column(String(50), nullable=False)
    start_date = Column(String(10), nullable=False)
    end_date = Column(String(10), nullable=False)
    is_closed = Column(Boolean, default=False, nullable=False)
    closed_at = Column(UTCDateTime, nullable=True)
    closed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    company = relationship("Company", back_populates="accounting_periods")
    closed_by_user = relationship("User")

    __table_args__ = (
        UniqueConstraint("company_id", "financial_year", "period_name", name="uq_accounting_periods_company_fy_name"),
        Index("ix_accounting_periods_company_dates", "company_id", "start_date", "end_date"),
        CheckConstraint("start_date <= end_date", name="chk_accounting_periods_dates"),
    )


class JournalEntry(TraditionalBase):
    __tablename__ = "journal_entries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year = Column(String(20), nullable=False, index=True)
    voucher_number = Column(String(50), nullable=False)
    voucher_type = Column(String(30), nullable=False, index=True)  # JOURNAL, SALES, PURCHASE, PAYMENT, RECEIPT, CONTRA, SALES_RETURN, PURCHASE_RETURN, REVERSAL, OPENING
    voucher_date = Column(String(10), nullable=False, index=True)
    narration = Column(Text, nullable=True)
    total_debit = Column(Numeric(15, 2), nullable=False)
    total_credit = Column(Numeric(15, 2), nullable=False)
    status = Column(String(20), server_default="POSTED", default="POSTED", nullable=False)  # DRAFT, POSTED, REVERSED
    reference_type = Column(String(50), nullable=True)
    reference_id = Column(String(100), nullable=True)
    reversal_of_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    reversed_by_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    reversal_reason = Column(Text, nullable=True)
    idempotency_key = Column(String(128), nullable=True)
    posted_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    company = relationship("Company", back_populates="journal_entries")
    branch = relationship("Branch")
    posted_by_user = relationship("User")
    lines = relationship("JournalEntryLine", back_populates="journal", cascade="all, delete-orphan", order_by="JournalEntryLine.line_number")
    reversal_of = relationship("JournalEntry", remote_side=[id], foreign_keys=[reversal_of_id])

    __table_args__ = (
        UniqueConstraint("company_id", "branch_id", "financial_year", "voucher_type", "voucher_number", name="uq_journal_entries_scope_vch"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_journal_entries_idempotency"),
        Index("ix_journal_entries_company_date", "company_id", "voucher_date"),
        Index("ix_journal_entries_ref", "company_id", "reference_type", "reference_id"),
        CheckConstraint("total_debit = total_credit", name="chk_journal_entries_total_balanced"),
        CheckConstraint("total_debit > 0", name="chk_journal_entries_total_positive"),
        CheckConstraint("status IN ('DRAFT', 'POSTED', 'REVERSED')", name="chk_journal_entries_status"),
    )


class JournalEntryLine(TraditionalBase):
    __tablename__ = "journal_entry_lines"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    journal_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number = Column(Integer, nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    debit = Column(Numeric(15, 2), server_default="0.00", default=0.00, nullable=False)
    credit = Column(Numeric(15, 2), server_default="0.00", default=0.00, nullable=False)
    narration = Column(Text, nullable=True)
    party_type = Column(String(30), nullable=True)
    party_id = Column(String(36), nullable=True)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)

    journal = relationship("JournalEntry", back_populates="lines")
    account = relationship("Account", back_populates="journal_lines")

    __table_args__ = (
        UniqueConstraint("journal_id", "line_number", name="uq_journal_entry_lines_journal_line"),
        Index("ix_jlines_company_account", "company_id", "account_id", "created_at"),
        CheckConstraint("debit >= 0", name="chk_jlines_debit_non_neg"),
        CheckConstraint("credit >= 0", name="chk_jlines_credit_non_neg"),
        CheckConstraint("((debit > 0 AND credit == 0) OR (credit > 0 AND debit == 0))", name="chk_jlines_one_side_nonzero"),
    )


class FinancialYearClosing(TraditionalBase):
    __tablename__ = "financial_year_closings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year = Column(String(20), nullable=False)
    closing_date = Column(String(10), nullable=False)
    closing_journal_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    next_financial_year = Column(String(20), nullable=True)
    next_opening_journal_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    net_profit = Column(Numeric(15, 2), nullable=False)
    status = Column(String(20), server_default="CLOSED", default="CLOSED", nullable=False)  # CLOSED, REOPENED
    closed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reopened_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reopened_at = Column(UTCDateTime, nullable=True)
    reopen_reason = Column(Text, nullable=True)
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    company = relationship("Company", back_populates="year_closings")
    branch = relationship("Branch")
    closing_journal = relationship("JournalEntry", foreign_keys=[closing_journal_id])
    next_opening_journal = relationship("JournalEntry", foreign_keys=[next_opening_journal_id])
    closed_by_user = relationship("User", foreign_keys=[closed_by])
    reopened_by_user = relationship("User", foreign_keys=[reopened_by])

    __table_args__ = (
        UniqueConstraint("company_id", "financial_year", name="uq_fy_closings_company_fy"),
        CheckConstraint("status IN ('CLOSED', 'REOPENED')", name="chk_fy_closings_status"),
        Index("ix_fy_closings_company_date", "company_id", "closing_date"),
    )


class PaperConfiguration(TraditionalBase):
    __tablename__ = "paper_configurations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True)
    paper_format = Column(String(20), nullable=False)  # 'a4', 'a5', 'thermal'

    # Dimensions (mm)
    width_mm = Column(Numeric(10, 2), nullable=False)
    height_mm = Column(Numeric(10, 2), nullable=True)  # None for continuous roll
    orientation = Column(String(20), nullable=False, default="portrait")  # 'portrait', 'landscape'

    # Margins (mm)
    margin_top_mm = Column(Numeric(10, 2), nullable=False, default=10.0)
    margin_bottom_mm = Column(Numeric(10, 2), nullable=False, default=10.0)
    margin_left_mm = Column(Numeric(10, 2), nullable=False, default=10.0)
    margin_right_mm = Column(Numeric(10, 2), nullable=False, default=10.0)

    # General / Output Settings
    default_printer = Column(String(255), nullable=True, default="")
    print_scaling = Column(Integer, nullable=False, default=100)  # Percentage 25-300
    header_spacing_mm = Column(Numeric(10, 2), nullable=False, default=5.0)
    footer_spacing_mm = Column(Numeric(10, 2), nullable=False, default=5.0)
    page_numbering = Column(Boolean, nullable=False, default=True)

    # Thermal-specific
    thermal_paper_width_type = Column(String(20), nullable=True, default="80mm")  # '58mm', '80mm', 'custom'
    printable_width_mm = Column(Numeric(10, 2), nullable=True, default=72.0)
    print_density = Column(String(50), nullable=True, default="Normal")  # 'Light', 'Normal', 'Dark'
    font_size = Column(Integer, nullable=True, default=10)
    line_spacing = Column(Numeric(5, 2), nullable=True, default=1.2)
    char_alignment = Column(String(20), nullable=True, default="left")  # 'left', 'center', 'right'
    auto_cut = Column(Boolean, nullable=True, default=True)

    created_at = Column(UTCDateTime, default=utc_now, nullable=False)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    company = relationship("Company")
    branch = relationship("Branch")

    __table_args__ = (
        UniqueConstraint("company_id", "paper_format", name="uq_paper_configurations_scope"),
        Index("ix_paper_configurations_scope", "company_id", "paper_format"),
    )


class BillLayoutConfiguration(TraditionalBase):
    """
    Phase 2: Bill Layout Configuration.
    Stores invoice layout design, header visibility, company logo,
    table column ordering/visibility, totals & tax visibility, and footer options.
    Scoped per (company_id, voucher_type).
    """
    __tablename__ = "bill_layout_configurations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True)
    voucher_type = Column(String(50), nullable=False)  # 'sales_invoice', 'sales_return', 'purchase_invoice', 'purchase_return'
    layout_name = Column(String(100), nullable=False, default="Standard Layout")

    # Serialized JSON configuration sections
    header_config = Column(Text, nullable=False)
    invoice_info_config = Column(Text, nullable=False)
    columns_config = Column(Text, nullable=False)
    totals_config = Column(Text, nullable=False)
    footer_config = Column(Text, nullable=False)
    style_config = Column(Text, nullable=False)

    created_at = Column(UTCDateTime, default=utc_now, nullable=False)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    company = relationship("Company")
    branch = relationship("Branch")

    __table_args__ = (
        UniqueConstraint("company_id", "voucher_type", name="uq_bill_layout_scope"),
        Index("ix_bill_layout_scope", "company_id", "voucher_type"),
    )


class VoucherNumberingConfiguration(TraditionalBase):
    """
    Phase 4: Voucher Numbering Configuration.
    Stores prefix, starting sequence, padding, suffix, financial year inclusion,
    branch code inclusion, and series reset rules per voucher type, company, and branch.
    Scoped per (company_id, branch_id, voucher_type, series).
    """
    __tablename__ = "voucher_numbering_configurations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True)
    voucher_type = Column(String(50), nullable=False)  # 'sales_invoice', 'sales_return', 'purchase_invoice', 'purchase_return'
    series = Column(String(50), server_default="Main", default="Main", nullable=False)
    is_custom_enabled = Column(Boolean, server_default="0", default=False, nullable=False)
    prefix = Column(String(50), server_default="", default="", nullable=False)
    start_number = Column(BigInteger, server_default="1", default=1, nullable=False)
    padding = Column(Integer, server_default="4", default=4, nullable=False)
    suffix = Column(String(50), server_default="", default="", nullable=False)
    include_financial_year = Column(Boolean, server_default="0", default=False, nullable=False)
    fy_format = Column(String(20), server_default="YYYY-YY", default="YYYY-YY", nullable=False)
    fy_separator = Column(String(10), server_default="/", default="/", nullable=False)
    include_branch_code = Column(Boolean, server_default="0", default=False, nullable=False)
    branch_position = Column(String(20), server_default="prefix", default="prefix", nullable=False)
    reset_frequency = Column(String(20), server_default="yearly", default="yearly", nullable=False)

    created_at = Column(UTCDateTime, default=utc_now, nullable=False)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    company = relationship("Company")
    branch = relationship("Branch")

    __table_args__ = (
        UniqueConstraint("company_id", "branch_id", "voucher_type", "series", name="uq_vch_numbering_cfg_scope"),
        Index("ix_vch_numbering_cfg_lookup", "company_id", "voucher_type", "series"),
    )


class GstTaxConfiguration(TraditionalBase):
    """
    Phase 5: GST & Tax Configuration.
    Stores company-aware and branch-aware GST registration, tax rates, calculation rules,
    HSN summary rules, and transaction defaults.
    Scoped per (company_id, branch_id).
    """
    __tablename__ = "gst_tax_configurations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True)
    is_gst_enabled = Column(Boolean, server_default="1", default=True, nullable=False)
    gstin = Column(String(15), nullable=True)
    legal_name = Column(String(255), nullable=True)
    trade_name = Column(String(255), nullable=True)
    state = Column(String(100), nullable=True)
    state_code = Column(String(10), nullable=True)
    registration_type = Column(String(50), server_default="Regular", default="Regular", nullable=False)
    default_place_of_supply = Column(String(100), nullable=True)
    default_tax_mode = Column(String(20), server_default="exclusive", default="exclusive", nullable=False)
    default_tax_rate = Column(Numeric(5, 2), server_default="18.00", default=18.00, nullable=False)
    supported_tax_rates_json = Column(Text, server_default='["0.00", "5.00", "12.00", "18.00", "28.00"]', default='["0.00", "5.00", "12.00", "18.00", "28.00"]', nullable=False)
    enable_cess = Column(Boolean, server_default="0", default=False, nullable=False)
    default_cess_rate = Column(Numeric(5, 2), server_default="0.00", default=0.00, nullable=False)
    tax_rounding_rule = Column(String(30), server_default="nearest_rupee", default="nearest_rupee", nullable=False)
    decimal_precision_currency = Column(Integer, server_default="2", default=2, nullable=False)
    decimal_precision_qty = Column(Integer, server_default="3", default=3, nullable=False)
    hsn_enforcement_mode = Column(String(30), server_default="optional", default="optional", nullable=False)
    show_hsn_summary = Column(Boolean, server_default="1", default=True, nullable=False)
    enable_rcm = Column(Boolean, server_default="0", default=False, nullable=False)
    transaction_defaults_json = Column(Text, server_default="{}", default="{}", nullable=False)
    effective_from = Column(String(20), server_default="", default="", nullable=False)

    created_at = Column(UTCDateTime, default=utc_now, nullable=False)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    company = relationship("Company")
    branch = relationship("Branch")

    __table_args__ = (
        UniqueConstraint("company_id", "branch_id", name="uq_gst_tax_cfg_scope"),
        Index("ix_gst_tax_cfg_lookup", "company_id"),
    )


class InventoryConfiguration(TraditionalBase):
    """
    Phase 6: Inventory Configuration.
    Stores company-aware and branch-aware inventory tracking rules,
    UOM defaults, decimal precisions, negative stock policy, stock alert thresholds,
    valuation method (Weighted Average Cost), warehouse material centres, and product tracking toggles.
    Scoped per (company_id, branch_id).
    """
    __tablename__ = "inventory_configurations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True)

    enable_inventory_tracking = Column(Boolean, server_default="1", default=True, nullable=False)
    default_uom = Column(String(30), server_default="Pcs.", default="Pcs.", nullable=False)
    qty_decimal_precision = Column(Integer, server_default="3", default=3, nullable=False)
    allow_fractional_qty = Column(Boolean, server_default="1", default=True, nullable=False)
    default_product_type = Column(String(50), server_default="Stockable", default="Stockable", nullable=False)
    auto_generate_sku = Column(Boolean, server_default="1", default=True, nullable=False)
    barcode_symbology = Column(String(30), server_default="EAN-13", default="EAN-13", nullable=False)

    allow_negative_stock = Column(Boolean, server_default="0", default=False, nullable=False)
    validate_stock_on_sale = Column(Boolean, server_default="1", default=True, nullable=False)
    stock_warning_behavior = Column(String(30), server_default="warn_and_allow", default="warn_and_allow", nullable=False)
    low_stock_alert_enabled = Column(Boolean, server_default="1", default=True, nullable=False)
    default_min_stock_level = Column(Numeric(12, 3), server_default="10.000", default=10.0, nullable=False)
    default_reorder_level = Column(Numeric(12, 3), server_default="15.000", default=15.0, nullable=False)
    default_reorder_qty = Column(Numeric(12, 3), server_default="50.000", default=50.0, nullable=False)
    default_max_stock_level = Column(Numeric(12, 3), server_default="500.000", default=500.0, nullable=False)

    valuation_method = Column(String(30), server_default="weighted_average", default="weighted_average", nullable=False)
    default_material_centre = Column(String(100), server_default="Main Store", default="Main Store", nullable=False)
    track_branch_stock = Column(Boolean, server_default="1", default=True, nullable=False)
    allow_inter_branch_transfer = Column(Boolean, server_default="1", default=True, nullable=False)

    enable_batch_tracking = Column(Boolean, server_default="0", default=False, nullable=False)
    enable_expiry_tracking = Column(Boolean, server_default="0", default=False, nullable=False)
    enable_barcode_tracking = Column(Boolean, server_default="1", default=True, nullable=False)
    link_hsn_sac = Column(Boolean, server_default="1", default=True, nullable=False)

    warn_on_low_stock = Column(Boolean, server_default="1", default=True, nullable=False)
    warn_on_negative_stock = Column(Boolean, server_default="1", default=True, nullable=False)
    warn_on_expiry = Column(Boolean, server_default="0", default=False, nullable=False)
    expiry_warning_days = Column(Integer, server_default="30", default=30, nullable=False)

    created_at = Column(UTCDateTime, default=utc_now, nullable=False)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    company = relationship("Company")
    branch = relationship("Branch")

    __table_args__ = (
        UniqueConstraint("company_id", "branch_id", name="uq_inventory_cfg_scope"),
        Index("ix_inventory_cfg_lookup", "company_id"),
    )

