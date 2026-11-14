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
    items = relationship("Item", back_populates="company", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="company", cascade="all, delete-orphan")


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

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_accounts_company_code"),
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
