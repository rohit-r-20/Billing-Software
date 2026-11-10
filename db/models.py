"""
SQLAlchemy 2.x Declarative Models for Alpha Billing ERP.
Compatible with Supabase PostgreSQL, Self-Managed PostgreSQL, and SQLite.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, Text, Float, Integer, BigInteger, DateTime, ForeignKey,
    UniqueConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all Alpha Billing database models."""
    pass


# ==============================================================================
# 1. Company, Branch & Register Hierarchy
# ==============================================================================

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    fin_year: Mapped[str] = mapped_column(String(50), default="2026-2027", server_default="2026-2027", nullable=False)
    gstin: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), default="Tamilnadu", nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), default="A", nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)

    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    # Relationships
    branches: Mapped[List["Branch"]] = relationship("Branch", back_populates="company", cascade="all, delete-orphan")


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_default: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)


    company: Mapped["Company"] = relationship("Company", back_populates="branches")

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_branches_company_code"),
    )


class Register(Base):
    __tablename__ = "registers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)


    __table_args__ = (
        UniqueConstraint("branch_id", "code", name="uq_registers_branch_code"),
    )


class CompanyConfig(Base):
    __tablename__ = "company_configs"

    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    vch_start: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    vch_digits: Mapped[Optional[int]] = mapped_column(Integer, default=3, nullable=True)
    vch_prefix: Mapped[Optional[str]] = mapped_column(String(20), default="", nullable=True)
    default_tax: Mapped[Optional[str]] = mapped_column(String(20), default="18", nullable=True)
    auto_round: Mapped[Optional[str]] = mapped_column(String(5), default="Y", nullable=True)
    receipt_width: Mapped[Optional[int]] = mapped_column(Integer, default=80, nullable=True)
    print_copies: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    allow_negative_stock: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)


# ==============================================================================
# 2. Authentication, Users & Roles
# ==============================================================================

class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)
    role_name: Mapped[str] = mapped_column(String(50), default="Administrator")
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)

    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "username", name="uq_users_company_username"),
    )


class UserPermission(Base):
    __tablename__ = "user_permissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_key: Mapped[str] = mapped_column(String(100), nullable=False)
    granted: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (
        UniqueConstraint("user_id", "permission_key", name="uq_user_permission_key"),
    )


# ==============================================================================
# 3. Party Masters (Accounts & Suppliers)
# ==============================================================================

class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    alias: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    print_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    account_group: Mapped[str] = mapped_column(String(100), default="Sundry Debtors", nullable=False)
    op_bal: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    op_type: Mapped[Optional[str]] = mapped_column(String(5), default="Dr", nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), default="India", nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), default="Tamilnadu", nullable=True)
    dealer_type: Mapped[Optional[str]] = mapped_column(String(50), default="Unregistered", nullable=True)
    customer_category: Mapped[Optional[str]] = mapped_column(String(50), default="Direct Customer", nullable=True)
    gstin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    whatsapp: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank_acc: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ifsc: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pincode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    payment_terms: Mapped[Optional[int]] = mapped_column(Integer, default=30, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_balance: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    is_active: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)

    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_accounts_company_name"),
        Index("idx_accounts_group_active", "company_id", "account_group", "is_active"),
    )


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_person: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    gstin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pan: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), default="Tamilnadu", nullable=True)
    pincode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    opening_balance: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    current_balance: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    credit_limit: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    payment_terms: Mapped[Optional[int]] = mapped_column(Integer, default=30, nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank_acc: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ifsc: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)

    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_suppliers_company_name"),
        UniqueConstraint("company_id", "code", name="uq_suppliers_company_code"),
    )


# ==============================================================================
# 4. Item Master, Barcodes & Catalogue
# ==============================================================================

class Item(Base):
    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    alias: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    print_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    item_group: Mapped[Optional[str]] = mapped_column(String(100), default="General", nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(20), default="Pcs.", nullable=True)
    op_stock_qty: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    op_stock_val: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    tax_category: Mapped[Optional[str]] = mapped_column(String(50), default="GST 18%", nullable=True)
    hsn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sales_price: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    purc_price: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    mrp: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    min_sales_price: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    min_stock_alert_level: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    reorder_level: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    reorder_qty: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    max_stock_level: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    alert_enabled: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    is_active: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)


    # Relationships
    barcodes: Mapped[List["ItemBarcode"]] = relationship("ItemBarcode", back_populates="item", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_items_company_name"),
        Index("idx_items_comp_active_name", "company_id", "is_active", "name"),
    )


class ItemBarcode(Base):
    __tablename__ = "item_barcodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    barcode: Mapped[str] = mapped_column(String(100), nullable=False)
    is_primary: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)


    item: Mapped["Item"] = relationship("Item", back_populates="barcodes")

    __table_args__ = (
        UniqueConstraint("company_id", "barcode", name="uq_item_barcodes_company_barcode"),
    )


class ItemBranchStockConfig(Base):
    __tablename__ = "item_branch_stock_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    min_stock_level: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reorder_level: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reorder_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_stock_level: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    alert_enabled: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    __table_args__ = (
        UniqueConstraint("branch_id", "item_id", name="uq_branch_item_stock_cfg"),
    )


# ==============================================================================
# 5. Shared Inventory & Stock Movements
# ==============================================================================

class StockBalance(Base):
    __tablename__ = "stock_balances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    current_qty: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    __table_args__ = (
        UniqueConstraint("branch_id", "item_id", name="uq_stock_balances_branch_item"),
        Index("idx_stock_balances_lookup", "company_id", "branch_id", "item_id"),
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'OPENING', 'SALE', 'RETURN', 'PURCHASE', 'ADJUSTMENT'
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    unit_cost: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'INVOICE', 'MANUAL', 'PURCHASE'
    reference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)


    __table_args__ = (
        Index("idx_stock_movements_ref", "reference_type", "reference_id"),
    )


# ==============================================================================
# 6. Voucher Numbering & Sequences
# ==============================================================================

class VoucherSequence(Base):
    __tablename__ = "voucher_sequences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    voucher_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'SALE', 'PURCHASE', 'RECEIPT'
    series: Mapped[str] = mapped_column(String(50), default="Main", nullable=False)
    current_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "voucher_type", "series", name="uq_voucher_sequence_type_series"),
    )


class BarcodeSequence(Base):
    __tablename__ = "barcode_sequences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sequence_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    prefix: Mapped[str] = mapped_column(String(10), default="AB", server_default="AB", nullable=False)
    current_value: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0", nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


# ==============================================================================
# 7. Sales Invoices & Traditional / Fast Billing
# ==============================================================================

class SalesVoucher(Base):
    __tablename__ = "sales_vouchers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    vch_no: Mapped[str] = mapped_column(String(50), nullable=False)
    series: Mapped[Optional[str]] = mapped_column(String(50), default="Main", nullable=True)
    vch_date: Mapped[str] = mapped_column(String(20), nullable=False)
    sale_type: Mapped[str] = mapped_column(String(50), default="L/GST-18%", nullable=False)
    party_name: Mapped[str] = mapped_column(String(255), default="CASH", nullable=False)
    account_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    party_gstin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    mat_centre: Mapped[Optional[str]] = mapped_column(String(100), default="Main Store", nullable=True)
    narration: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subtotal: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    taxable_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tax_rate: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    cgst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    sgst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    igst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    round_off: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    grand_total: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), default="CASH", nullable=True)
    payment_status: Mapped[Optional[str]] = mapped_column(String(20), default="PAID", nullable=True)
    is_cancelled: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)

    gross_subtotal: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    discount_total: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    customer_category: Mapped[Optional[str]] = mapped_column(String(50), default="Direct Customer", nullable=True)

    # Relationships
    items: Mapped[List["SalesVoucherItem"]] = relationship("SalesVoucherItem", back_populates="voucher", cascade="all, delete-orphan")
    payments: Mapped[List["Payment"]] = relationship("Payment", back_populates="voucher", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("company_id", "vch_no", name="uq_sales_vouchers_comp_vchno"),
        Index("idx_sales_vouchers_comp_date", "company_id", "vch_date"),
    )


class SalesVoucherItem(Base):
    __tablename__ = "sales_voucher_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    voucher_id: Mapped[str] = mapped_column(String(36), ForeignKey("sales_vouchers.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("items.id", ondelete="SET NULL"), nullable=True, index=True)
    sn: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    barcode: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    hsn: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(20), default="Pcs.", nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    discount_percent: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    discount_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    tax_rate: Mapped[Optional[float]] = mapped_column(Float, default=18.0, nullable=True)
    tax_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    cgst_rate: Mapped[Optional[float]] = mapped_column(Float, default=9.0, nullable=True)
    sgst_rate: Mapped[Optional[float]] = mapped_column(Float, default=9.0, nullable=True)
    igst_rate: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    taxable_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    cgst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    sgst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    igst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    line_total: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)

    voucher: Mapped["SalesVoucher"] = relationship("SalesVoucher", back_populates="items")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    voucher_id: Mapped[str] = mapped_column(String(36), ForeignKey("sales_vouchers.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    method: Mapped[Optional[str]] = mapped_column(String(50), default="CASH", nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    ref_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reference_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)

    voucher: Mapped["SalesVoucher"] = relationship("SalesVoucher", back_populates="payments")


# ==============================================================================
# 8. Purchase Invoices
# ==============================================================================

class PurchaseVoucher(Base):
    __tablename__ = "purchase_vouchers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    godown_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("godowns.id", ondelete="SET NULL"), nullable=True, index=True)
    vch_no: Mapped[str] = mapped_column(String(50), nullable=False)
    supplier_invoice_no: Mapped[str] = mapped_column(String(100), nullable=False)
    supplier_invoice_date: Mapped[str] = mapped_column(String(20), nullable=False)
    vch_date: Mapped[str] = mapped_column(String(20), nullable=False)
    supplier_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_gstin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    supplier_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supplier_state: Mapped[Optional[str]] = mapped_column(String(100), default="Tamilnadu", nullable=True)
    place_of_supply: Mapped[Optional[str]] = mapped_column(String(100), default="Tamilnadu", nullable=True)
    payment_type: Mapped[Optional[str]] = mapped_column(String(50), default="CREDIT", nullable=True)
    due_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    purchase_type: Mapped[Optional[str]] = mapped_column(String(50), default="Local", nullable=True)
    narration: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gross_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    discount_total: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    additional_expenses: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    taxable_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    cgst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    sgst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    igst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    cess_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    round_off: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    grand_total: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    amount_paid: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    outstanding_balance: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    is_draft: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    is_cancelled: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), default="Admin", nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)

    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    # Relationships
    items: Mapped[List["PurchaseVoucherItem"]] = relationship("PurchaseVoucherItem", back_populates="voucher", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("company_id", "vch_no", name="uq_purchase_vouchers_comp_vchno"),
        UniqueConstraint("company_id", "supplier_id", "supplier_invoice_no", name="uq_pur_vch_supp_inv"),
    )


class PurchaseVoucherItem(Base):
    __tablename__ = "purchase_voucher_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    voucher_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_vouchers.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("items.id", ondelete="SET NULL"), nullable=True, index=True)
    sn: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    item_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    barcode: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    hsn: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    free_qty: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(20), default="PCS", nullable=True)
    purchase_rate: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    discount_percent: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    discount_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    taxable_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    tax_rate: Mapped[Optional[float]] = mapped_column(Float, default=18.0, nullable=True)
    cgst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    sgst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    igst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    cess_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    line_total: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    batch_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    expiry_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    voucher: Mapped["PurchaseVoucher"] = relationship("PurchaseVoucher", back_populates="items")


# ==============================================================================
# 9. Low Stock Notifications, Discounts & Audit Logs
# ==============================================================================

class LowStockAlert(Base):
    __tablename__ = "low_stock_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    item_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    threshold: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    available_qty: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    current_stock: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    threshold_level: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    threshold_type: Mapped[Optional[str]] = mapped_column(String(20), default="REORDER", nullable=True)
    reorder_level: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_stock_level: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    suggested_reorder_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    preferred_reorder_qty: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(50), default="REORDER_REQUIRED", nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(20), default="ACTIVE", nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)

    __table_args__ = (
        Index("idx_low_stock_company_status", "company_id", "status"),
    )


class CustomerCategoryDiscount(Base):
    __tablename__ = "customer_category_discounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    discount_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "category", name="uq_cust_category_disc"),
    )


class DailyDiscountConfig(Base):
    __tablename__ = "daily_discount_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True)
    business_date: Mapped[str] = mapped_column(String(20), nullable=False)
    discount_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    enabled_by: Mapped[str] = mapped_column(String(100), default="Admin", nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)

    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)



# ==============================================================================
# 10. ERP Warehouses, Adjustments, Returns & Financial Journals
# ==============================================================================

class Godown(Base):
    __tablename__ = "godowns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)



class StockAdjustment(Base):
    __tablename__ = "stock_adjustments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True)
    godown_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    vch_no: Mapped[str] = mapped_column(String(50), nullable=False)
    adj_date: Mapped[str] = mapped_column(String(20), nullable=False)
    adj_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    authorized_by: Mapped[Optional[str]] = mapped_column(String(100), default="Admin", nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_items: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)



class StockAdjustmentItem(Base):
    __tablename__ = "stock_adjustment_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    adjustment_id: Mapped[str] = mapped_column(String(36), ForeignKey("stock_adjustments.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    system_qty: Mapped[float] = mapped_column(Float, nullable=False)
    physical_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    diff_qty: Mapped[float] = mapped_column(Float, nullable=False)
    unit_cost: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class StockTransfer(Base):
    __tablename__ = "stock_transfers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    transfer_no: Mapped[str] = mapped_column(String(50), nullable=False)
    transfer_date: Mapped[str] = mapped_column(String(20), nullable=False)
    source_branch_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True)
    source_godown_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    dest_branch_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True)
    dest_godown_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), default="COMPLETED", nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), default="Admin", nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)



class StockTransferItem(Base):
    __tablename__ = "stock_transfer_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    transfer_id: Mapped[str] = mapped_column(String(36), ForeignKey("stock_transfers.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(20), default="Pcs.", nullable=True)
    unit_cost: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)


class StockBatch(Base):
    __tablename__ = "stock_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    batch_no: Mapped[str] = mapped_column(String(100), nullable=False)
    mfg_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    expiry_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    purchase_rate: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    qty_received: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    qty_sold: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    qty_available: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    supplier_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    purchase_voucher_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("purchase_vouchers.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)



class SalesReturn(Base):
    __tablename__ = "sales_returns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    vch_no: Mapped[str] = mapped_column(String(50), nullable=False)
    original_voucher_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    original_sales_vch_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("sales_vouchers.id", ondelete="SET NULL"), nullable=True)
    original_invoice_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    vch_date: Mapped[str] = mapped_column(String(20), nullable=False)
    party_name: Mapped[Optional[str]] = mapped_column(String(255), default="CASH", nullable=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    account_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    taxable_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    cgst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    sgst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    igst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    grand_total: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    total_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)


class SalesReturnItem(Base):
    __tablename__ = "sales_return_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    return_id: Mapped[str] = mapped_column(String(36), ForeignKey("sales_returns.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    sn: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    item_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(20), default="Pcs.", nullable=True)
    rate: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    tax_rate: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    tax_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    taxable_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    line_total: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    restock_condition: Mapped[Optional[str]] = mapped_column(String(50), default="GOOD", nullable=True)


class PurchaseReturn(Base):
    __tablename__ = "purchase_returns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    vch_no: Mapped[str] = mapped_column(String(50), nullable=False)
    original_voucher_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    original_purchase_vch_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("purchase_vouchers.id", ondelete="SET NULL"), nullable=True)
    original_supplier_inv_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vch_date: Mapped[str] = mapped_column(String(20), nullable=False)
    supplier_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    taxable_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    cgst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    sgst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    igst_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    grand_total: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    total_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)


class PurchaseReturnItem(Base):
    __tablename__ = "purchase_return_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    return_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_returns.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    sn: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    item_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(20), default="Pcs.", nullable=True)
    rate: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    purchase_rate: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    tax_rate: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    tax_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    line_total: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    vch_no: Mapped[str] = mapped_column(String(50), nullable=False)
    vch_date: Mapped[str] = mapped_column(String(20), nullable=False)
    vch_type: Mapped[Optional[str]] = mapped_column(String(50), default="Journal", nullable=True)
    reference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    narration: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)

    # Relationships
    lines: Mapped[List["JournalEntryLine"]] = relationship("JournalEntryLine", back_populates="journal", cascade="all, delete-orphan")


class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    journal_id: Mapped[str] = mapped_column(String(36), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    account_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    debit: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    credit: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    debit_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    credit_amount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    narration: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    journal: Mapped["JournalEntry"] = relationship("JournalEntry", back_populates="lines")


class UnitConversion(Base):
    __tablename__ = "unit_conversions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=True)
    from_unit: Mapped[str] = mapped_column(String(50), nullable=False)
    to_unit: Mapped[str] = mapped_column(String(50), nullable=False)
    multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)


class OCRInvoiceDraft(Base):
    __tablename__ = "ocr_invoice_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    extracted_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), default="DRAFT", nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)


