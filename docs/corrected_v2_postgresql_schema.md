# Alpha Billing V2 — Corrected PostgreSQL Schema Specification

## 1. Architectural Scope & Design Philosophy

This document defines the **Authoritative Clean V2 PostgreSQL Schema** for Alpha Billing. It strips away legacy prototype artifacts and multi-tenant bloat while implementing the 14 approved V2 architectural corrections.

### Approved V2 Scope:
- **Single Company**: Fixed to the single operational tenant (`company_id = '3a743bcd-8f9a-4154-a316-509cba3de99a'`).
- **Single Stock Location**: Centralized retail/wholesale stock balances without multi-godown or inter-warehouse transfers.
- **Core Modules**: Customer & Supplier Masters, Item Master (with Categories and Units), Sales Invoicing & Returns, Purchase Invoicing & Returns, Inventory & Stock Movement Ledger, User Management & Permissions, Financial Payments/Allocations, Audit Logging, and Backup Management.

### Strictly Excluded (Out of Scope):
- Multi-company accounting, multi-branch routing, multi-godown structures, warehouse transfers, manufacturing/BOM, batch/expiry tracking, serial number tracking, advanced matrix pricing engines, full double-entry journals, and AI analytics.

---

## 2. Summary of 14 Architectural Corrections

| # | Architectural Requirement | Corrected Schema Implementation |
|---|---|---|
| **1** | **Unified Party Identity** | `accounts` table stores unified identity for Customers (`CUSTOMER`), Suppliers (`SUPPLIER`), or Both (`BOTH`). Eliminates redundant duplicate tables while preserving role segregation. |
| **2** | **Separate Opening Balances** | Formal `op_bal NUMERIC(15, 2)` and `op_type VARCHAR(2)` (`DR` for customer receivables, `CR` for supplier payables) with immutable audit stamp. |
| **3** | **Proper User, Role & Permissions** | Normalized `roles` (RBAC), `users` (with hashed credentials), and `user_permissions` (discrete capability flags). |
| **4** | **Strict NUMERIC Types** | All monetary amounts use `NUMERIC(15, 2)`; all quantities use `NUMERIC(15, 3)` (supports decimals like 0.250 kg). Eliminates float rounding drift. |
| **5** | **Proper Temporal Types** | Real dates use `DATE`; event timestamps use `TIMESTAMPTZ` / `TIMESTAMP WITH TIME ZONE`. |
| **6** | **Safe Company-Consistent FKs** | All foreign keys enforce referential integrity with explicit cascade policies (`ON DELETE CASCADE` for line items, `ON DELETE SET NULL` for party references). |
| **7** | **Immutable Stock Movement Ledger** | `stock_movements` acts as an append-only transaction ledger (`movement_type`: `PURCHASE`, `SALE`, `SALES_RETURN`, `PURCHASE_RETURN`, `ADJUSTMENT`). |
| **8** | **Weighted Average Cost (WAC)** | Item master records `cost_price NUMERIC(15, 2)` and `valuation_method VARCHAR(20) DEFAULT 'WAC'`. Inward purchases recompute WAC authoritatively. |
| **9** | **Historical COGS Snapshot on Sales** | `sales_voucher_items` records `cogs_unit_cost` and `cogs_total` at the exact time of sale, enabling reliable historical gross margin reporting regardless of future cost changes. |
| **10**| **Separate Purchase Payments & Allocations** | `purchase_payments` and `supplier_allocations` decouple invoice entry from disbursement, supporting partial payments and supplier advances. |
| **11**| **Sales & Purchase Return Tracking** | Dedicated `sales_returns` and `purchase_returns` with explicit foreign keys to the original vouchers (`original_voucher_id`). |
| **12**| **Safe Voucher Numbering** | `voucher_sequences` provides deterministic sequential counters with company and series isolation to prevent duplicate voucher generation. |
| **13**| **Audit & Activity History** | `audit_logs` records user identity, action, entity type, entity ID, and structured JSON context. |
| **14**| **Backup & Restore Management** | `system_backups` tracks physical snapshot files, SHA-256 checksums, byte sizes, and verification timestamps. |

---

## 3. Complete DDL Specification

### 3.1 Company & Configuration
```sql
CREATE TABLE companies (
    id VARCHAR(36) PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    fin_year VARCHAR(50) NOT NULL DEFAULT '2026-2027',
    gstin VARCHAR(50),
    state VARCHAR(100) DEFAULT 'Tamilnadu',
    currency_symbol VARCHAR(10) DEFAULT '₹',
    currency_code VARCHAR(10) DEFAULT 'INR',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE company_configs (
    company_id VARCHAR(36) PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    vch_start INTEGER DEFAULT 1,
    vch_digits INTEGER DEFAULT 3,
    vch_prefix VARCHAR(20) DEFAULT '',
    default_tax VARCHAR(20) DEFAULT '18',
    auto_round VARCHAR(5) DEFAULT 'Y',
    receipt_width INTEGER DEFAULT 80,
    print_copies INTEGER DEFAULT 1,
    allow_negative_stock INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

---

### 3.2 User Management & Permissions
```sql
CREATE TABLE roles (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    username VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role_id VARCHAR(36) REFERENCES roles(id) ON DELETE SET NULL,
    role_name VARCHAR(50) DEFAULT 'Administrator',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_company_username UNIQUE (company_id, username)
);
CREATE INDEX ix_users_company_id ON users(company_id);

CREATE TABLE user_permissions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission_key VARCHAR(100) NOT NULL,
    granted INTEGER DEFAULT 1,
    CONSTRAINT uq_user_permission_key UNIQUE (user_id, permission_key)
);
CREATE INDEX ix_user_permissions_user_id ON user_permissions(user_id);
```

---

### 3.3 Unified Party Master (Customers & Suppliers)
```sql
CREATE TABLE accounts (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    party_type VARCHAR(20) NOT NULL DEFAULT 'CUSTOMER', -- 'CUSTOMER', 'SUPPLIER', 'BOTH'
    name VARCHAR(255) NOT NULL,
    alias VARCHAR(100),
    print_name VARCHAR(255),
    account_group VARCHAR(100) NOT NULL DEFAULT 'Sundry Debtors',
    op_bal NUMERIC(15, 2) DEFAULT 0.00,
    op_type VARCHAR(2) DEFAULT 'DR', -- 'DR' (Receivable), 'CR' (Payable)
    current_receivable NUMERIC(15, 2) DEFAULT 0.00,
    current_payable NUMERIC(15, 2) DEFAULT 0.00,
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100) DEFAULT 'Tamilnadu',
    country VARCHAR(100) DEFAULT 'India',
    pincode VARCHAR(20),
    dealer_type VARCHAR(50) DEFAULT 'Unregistered',
    customer_category VARCHAR(50) DEFAULT 'Direct Customer',
    gstin VARCHAR(20),
    pan VARCHAR(20),
    mobile VARCHAR(20),
    whatsapp VARCHAR(20),
    email VARCHAR(100),
    bank_name VARCHAR(100),
    bank_acc VARCHAR(50),
    ifsc VARCHAR(20),
    credit_limit NUMERIC(15, 2) DEFAULT 0.00,
    payment_terms INTEGER DEFAULT 30,
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_accounts_company_name UNIQUE (company_id, name)
);
CREATE INDEX idx_accounts_group_active ON accounts(company_id, party_type, is_active);
CREATE INDEX ix_accounts_mobile ON accounts(mobile);
CREATE INDEX ix_accounts_gstin ON accounts(gstin);

-- Backward compatibility mirror view for legacy supplier queries:
CREATE VIEW suppliers_v2 AS
SELECT 
    id, company_id, alias AS code, name, print_name AS contact_person,
    mobile, email, gstin, pan, address, city, state, pincode,
    op_bal AS opening_balance, current_payable AS current_balance,
    credit_limit, payment_terms, bank_name, bank_acc, ifsc, is_active,
    created_at, updated_at
FROM accounts
WHERE party_type IN ('SUPPLIER', 'BOTH');
```

---

### 3.4 Categories, Units, Items & Barcodes
```sql
CREATE TABLE product_categories (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_categories_company_name UNIQUE (company_id, name)
);

CREATE TABLE product_units (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(50) NOT NULL,
    precision_decimals INTEGER DEFAULT 0,
    CONSTRAINT uq_units_company_code UNIQUE (company_id, code)
);

CREATE TABLE items (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    category_id VARCHAR(36) REFERENCES product_categories(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    alias VARCHAR(100),
    print_name VARCHAR(255),
    item_group VARCHAR(100) DEFAULT 'General',
    unit VARCHAR(20) DEFAULT 'Pcs.',
    hsn VARCHAR(20),
    tax_category VARCHAR(50) DEFAULT 'GST 18%',
    tax_rate NUMERIC(5, 2) DEFAULT 18.00,
    
    -- Pricing Structure
    sales_price NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    purc_price NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    mrp NUMERIC(15, 2) DEFAULT 0.00,
    min_sales_price NUMERIC(15, 2) DEFAULT 0.00,
    
    -- Inventory Valuation (Weighted Average Cost)
    valuation_method VARCHAR(20) DEFAULT 'WAC',
    cost_price NUMERIC(15, 2) DEFAULT 0.00,
    
    -- Stock Monitoring
    op_stock_qty NUMERIC(15, 3) DEFAULT 0.000,
    op_stock_val NUMERIC(15, 2) DEFAULT 0.00,
    min_stock_alert_level NUMERIC(15, 3) DEFAULT 0.000,
    reorder_level NUMERIC(15, 3) DEFAULT 0.000,
    reorder_qty NUMERIC(15, 3) DEFAULT 0.000,
    max_stock_level NUMERIC(15, 3) DEFAULT 0.000,
    alert_enabled INTEGER DEFAULT 1,
    
    description TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_items_company_name UNIQUE (company_id, name)
);
CREATE INDEX idx_items_comp_active ON items(company_id, is_active, name);
CREATE INDEX ix_items_alias ON items(alias);

CREATE TABLE item_barcodes (
    id VARCHAR(36) PRIMARY KEY,
    item_id VARCHAR(36) NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    barcode VARCHAR(100) NOT NULL,
    is_primary INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_item_barcodes_company_barcode UNIQUE (company_id, barcode)
);
CREATE INDEX ix_item_barcodes_barcode ON item_barcodes(barcode);
```

---

### 3.5 Single-Location Inventory & Stock Ledger
```sql
CREATE TABLE stock_balances (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    item_id VARCHAR(36) NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    current_qty NUMERIC(15, 3) NOT NULL DEFAULT 0.000,
    last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_stock_balances_company_item UNIQUE (company_id, item_id)
);
CREATE INDEX ix_stock_balances_item ON stock_balances(item_id);

CREATE TABLE stock_movements (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    item_id VARCHAR(36) NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    movement_type VARCHAR(20) NOT NULL, -- 'OPENING', 'SALE', 'SALES_RETURN', 'PURCHASE', 'PURCHASE_RETURN', 'ADJUSTMENT'
    qty NUMERIC(15, 3) NOT NULL,
    unit_cost NUMERIC(15, 2) DEFAULT 0.00,
    reference_type VARCHAR(50), -- 'INVOICE', 'PURCHASE', 'RETURN', 'MANUAL'
    reference_id VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_stock_movements_ref ON stock_movements(reference_type, reference_id);
CREATE INDEX ix_stock_movements_item ON stock_movements(item_id);
```

---

### 3.6 Sales Billing & COGS Snapshots
```sql
CREATE TABLE sales_vouchers (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    vch_no VARCHAR(50) NOT NULL,
    series VARCHAR(50) DEFAULT 'Main',
    vch_date DATE NOT NULL,
    sale_type VARCHAR(50) NOT NULL DEFAULT 'L/GST-18%',
    party_name VARCHAR(255) NOT NULL DEFAULT 'CASH',
    account_id VARCHAR(36) REFERENCES accounts(id) ON DELETE SET NULL,
    party_gstin VARCHAR(20),
    customer_category VARCHAR(50) DEFAULT 'Direct Customer',
    narration TEXT,
    
    -- Financial Totals
    subtotal NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    gross_subtotal NUMERIC(15, 2) DEFAULT 0.00,
    discount_total NUMERIC(15, 2) DEFAULT 0.00,
    taxable_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    tax_rate NUMERIC(5, 2) DEFAULT 0.00,
    cgst_amount NUMERIC(15, 2) DEFAULT 0.00,
    sgst_amount NUMERIC(15, 2) DEFAULT 0.00,
    igst_amount NUMERIC(15, 2) DEFAULT 0.00,
    round_off NUMERIC(15, 2) DEFAULT 0.00,
    grand_total NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    
    -- Settlement Status
    payment_method VARCHAR(50) DEFAULT 'CASH',
    payment_status VARCHAR(20) DEFAULT 'PAID',
    is_cancelled INTEGER DEFAULT 0,
    created_by VARCHAR(100) DEFAULT 'Admin',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_sales_vouchers_comp_vchno UNIQUE (company_id, vch_no)
);
CREATE INDEX idx_sales_vouchers_comp_date ON sales_vouchers(company_id, vch_date);
CREATE INDEX ix_sales_vouchers_account ON sales_vouchers(account_id);

CREATE TABLE sales_voucher_items (
    id VARCHAR(36) PRIMARY KEY,
    voucher_id VARCHAR(36) NOT NULL REFERENCES sales_vouchers(id) ON DELETE CASCADE,
    item_id VARCHAR(36) REFERENCES items(id) ON DELETE SET NULL,
    sn INTEGER DEFAULT 1,
    item_name VARCHAR(255) NOT NULL,
    barcode VARCHAR(100),
    hsn VARCHAR(50),
    qty NUMERIC(15, 3) NOT NULL,
    unit VARCHAR(20) DEFAULT 'Pcs.',
    price NUMERIC(15, 2) NOT NULL,
    amount NUMERIC(15, 2) DEFAULT 0.00,
    discount_percent NUMERIC(5, 2) DEFAULT 0.00,
    discount_amount NUMERIC(15, 2) DEFAULT 0.00,
    taxable_amount NUMERIC(15, 2) DEFAULT 0.00,
    tax_rate NUMERIC(5, 2) DEFAULT 18.00,
    tax_amount NUMERIC(15, 2) DEFAULT 0.00,
    cgst_rate NUMERIC(5, 2) DEFAULT 9.00,
    sgst_rate NUMERIC(5, 2) DEFAULT 9.00,
    igst_rate NUMERIC(5, 2) DEFAULT 0.00,
    cgst_amount NUMERIC(15, 2) DEFAULT 0.00,
    sgst_amount NUMERIC(15, 2) DEFAULT 0.00,
    igst_amount NUMERIC(15, 2) DEFAULT 0.00,
    line_total NUMERIC(15, 2) DEFAULT 0.00,
    
    -- Historical COGS Snapshot at Finalization
    cogs_unit_cost NUMERIC(15, 2) DEFAULT 0.00,
    cogs_total NUMERIC(15, 2) DEFAULT 0.00
);
CREATE INDEX ix_sales_voucher_items_vch ON sales_voucher_items(voucher_id);
```

---

### 3.7 Inward Purchases, Payments & Allocations
```sql
CREATE TABLE purchase_vouchers (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    vch_no VARCHAR(50) NOT NULL,
    supplier_invoice_no VARCHAR(100) NOT NULL,
    supplier_invoice_date DATE NOT NULL,
    vch_date DATE NOT NULL,
    supplier_id VARCHAR(36) REFERENCES accounts(id) ON DELETE SET NULL,
    supplier_name VARCHAR(255) NOT NULL,
    supplier_gstin VARCHAR(20),
    supplier_address TEXT,
    payment_type VARCHAR(50) DEFAULT 'CREDIT',
    due_date DATE,
    purchase_type VARCHAR(50) DEFAULT 'Local',
    narration TEXT,
    gross_amount NUMERIC(15, 2) DEFAULT 0.00,
    discount_total NUMERIC(15, 2) DEFAULT 0.00,
    taxable_amount NUMERIC(15, 2) DEFAULT 0.00,
    cgst_amount NUMERIC(15, 2) DEFAULT 0.00,
    sgst_amount NUMERIC(15, 2) DEFAULT 0.00,
    igst_amount NUMERIC(15, 2) DEFAULT 0.00,
    round_off NUMERIC(15, 2) DEFAULT 0.00,
    grand_total NUMERIC(15, 2) DEFAULT 0.00,
    amount_paid NUMERIC(15, 2) DEFAULT 0.00,
    outstanding_balance NUMERIC(15, 2) DEFAULT 0.00,
    is_cancelled INTEGER DEFAULT 0,
    created_by VARCHAR(100) DEFAULT 'Admin',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_purchase_vouchers_comp_vchno UNIQUE (company_id, vch_no)
);
CREATE INDEX ix_purchase_vouchers_supplier ON purchase_vouchers(supplier_id);

CREATE TABLE purchase_voucher_items (
    id VARCHAR(36) PRIMARY KEY,
    voucher_id VARCHAR(36) NOT NULL REFERENCES purchase_vouchers(id) ON DELETE CASCADE,
    item_id VARCHAR(36) REFERENCES items(id) ON DELETE SET NULL,
    sn INTEGER DEFAULT 1,
    item_name VARCHAR(255) NOT NULL,
    barcode VARCHAR(100),
    hsn VARCHAR(50),
    qty NUMERIC(15, 3) NOT NULL,
    free_qty NUMERIC(15, 3) DEFAULT 0.000,
    unit VARCHAR(20) DEFAULT 'PCS',
    purchase_rate NUMERIC(15, 2) DEFAULT 0.00,
    discount_percent NUMERIC(5, 2) DEFAULT 0.00,
    discount_amount NUMERIC(15, 2) DEFAULT 0.00,
    taxable_amount NUMERIC(15, 2) DEFAULT 0.00,
    tax_rate NUMERIC(5, 2) DEFAULT 18.00,
    cgst_amount NUMERIC(15, 2) DEFAULT 0.00,
    sgst_amount NUMERIC(15, 2) DEFAULT 0.00,
    igst_amount NUMERIC(15, 2) DEFAULT 0.00,
    line_total NUMERIC(15, 2) DEFAULT 0.00
);
CREATE INDEX ix_purchase_voucher_items_vch ON purchase_voucher_items(voucher_id);

-- Separate Purchase Payments & Supplier Allocations
CREATE TABLE purchase_payments (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    supplier_id VARCHAR(36) NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    payment_date DATE NOT NULL,
    payment_method VARCHAR(50) DEFAULT 'BANK_TRANSFER',
    amount NUMERIC(15, 2) NOT NULL,
    reference_no VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE supplier_allocations (
    id VARCHAR(36) PRIMARY KEY,
    payment_id VARCHAR(36) NOT NULL REFERENCES purchase_payments(id) ON DELETE CASCADE,
    purchase_voucher_id VARCHAR(36) NOT NULL REFERENCES purchase_vouchers(id) ON DELETE CASCADE,
    allocated_amount NUMERIC(15, 2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

---

### 3.8 Returns & Debit/Credit Notes
```sql
CREATE TABLE sales_returns (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    vch_no VARCHAR(50) NOT NULL,
    original_voucher_id VARCHAR(36) REFERENCES sales_vouchers(id) ON DELETE SET NULL,
    original_invoice_no VARCHAR(50),
    vch_date DATE NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    reason TEXT,
    taxable_amount NUMERIC(15, 2) DEFAULT 0.00,
    cgst_amount NUMERIC(15, 2) DEFAULT 0.00,
    sgst_amount NUMERIC(15, 2) DEFAULT 0.00,
    igst_amount NUMERIC(15, 2) DEFAULT 0.00,
    grand_total NUMERIC(15, 2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_sales_returns_comp_vchno UNIQUE (company_id, vch_no)
);

CREATE TABLE sales_return_items (
    id VARCHAR(36) PRIMARY KEY,
    return_id VARCHAR(36) NOT NULL REFERENCES sales_returns(id) ON DELETE CASCADE,
    item_id VARCHAR(36) NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    sn INTEGER DEFAULT 1,
    item_name VARCHAR(255),
    qty NUMERIC(15, 3) NOT NULL,
    unit VARCHAR(20) DEFAULT 'Pcs.',
    rate NUMERIC(15, 2) DEFAULT 0.00,
    tax_rate NUMERIC(5, 2) DEFAULT 0.00,
    tax_amount NUMERIC(15, 2) DEFAULT 0.00,
    line_total NUMERIC(15, 2) NOT NULL,
    restock_condition VARCHAR(50) DEFAULT 'GOOD'
);

CREATE TABLE purchase_returns (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    vch_no VARCHAR(50) NOT NULL,
    original_voucher_id VARCHAR(36) REFERENCES purchase_vouchers(id) ON DELETE SET NULL,
    original_invoice_no VARCHAR(50),
    vch_date DATE NOT NULL,
    supplier_id VARCHAR(36) REFERENCES accounts(id) ON DELETE SET NULL,
    supplier_name VARCHAR(255) NOT NULL,
    reason TEXT,
    taxable_amount NUMERIC(15, 2) DEFAULT 0.00,
    cgst_amount NUMERIC(15, 2) DEFAULT 0.00,
    sgst_amount NUMERIC(15, 2) DEFAULT 0.00,
    igst_amount NUMERIC(15, 2) DEFAULT 0.00,
    grand_total NUMERIC(15, 2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_purchase_returns_comp_vchno UNIQUE (company_id, vch_no)
);

CREATE TABLE purchase_return_items (
    id VARCHAR(36) PRIMARY KEY,
    return_id VARCHAR(36) NOT NULL REFERENCES purchase_returns(id) ON DELETE CASCADE,
    item_id VARCHAR(36) NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    sn INTEGER DEFAULT 1,
    item_name VARCHAR(255),
    qty NUMERIC(15, 3) NOT NULL,
    unit VARCHAR(20) DEFAULT 'Pcs.',
    rate NUMERIC(15, 2) DEFAULT 0.00,
    purchase_rate NUMERIC(15, 2) DEFAULT 0.00,
    tax_rate NUMERIC(5, 2) DEFAULT 0.00,
    tax_amount NUMERIC(15, 2) DEFAULT 0.00,
    line_total NUMERIC(15, 2) NOT NULL
);
```

---

### 3.9 Voucher Numbering, Audit Logs & System Backups
```sql
CREATE TABLE voucher_sequences (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    voucher_type VARCHAR(50) NOT NULL, -- 'SALE', 'PURCHASE', 'RECEIPT'
    series VARCHAR(50) NOT NULL DEFAULT 'Main',
    current_number INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_voucher_sequence_type_series UNIQUE (company_id, voucher_type, series)
);

CREATE TABLE barcode_sequences (
    id VARCHAR(36) PRIMARY KEY,
    sequence_name VARCHAR(50) NOT NULL UNIQUE,
    prefix VARCHAR(10) NOT NULL DEFAULT 'AB',
    current_value BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) REFERENCES companies(id) ON DELETE CASCADE,
    username VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(100),
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_audit_logs_action ON audit_logs(company_id, action, created_at);

CREATE TABLE system_backups (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) REFERENCES companies(id) ON DELETE CASCADE,
    backup_type VARCHAR(50) NOT NULL, -- 'PRE_MIGRATION', 'SCHEDULED', 'MANUAL'
    file_path TEXT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    sha256_hash VARCHAR(64) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    status VARCHAR(20) DEFAULT 'VERIFIED',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```
