-- 001_initial_schema.sql
-- Initial relational schema for Anti Matrix Billing ERP

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 1. Companies / Tenants
CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    fin_year TEXT NOT NULL,
    gstin TEXT,
    state TEXT DEFAULT 'Tamilnadu',
    username TEXT DEFAULT 'A',
    password_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Branches
CREATE TABLE IF NOT EXISTS branches (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    address TEXT,
    phone TEXT,
    is_default INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, code)
);

-- 3. Cashier Registers
CREATE TABLE IF NOT EXISTS registers (
    id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(branch_id, code)
);

-- 4. Company Configurations
CREATE TABLE IF NOT EXISTS company_configs (
    company_id TEXT PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    vch_start INTEGER DEFAULT 1,
    vch_digits INTEGER DEFAULT 3,
    vch_prefix TEXT DEFAULT '',
    default_tax TEXT DEFAULT '18',
    auto_round TEXT DEFAULT 'Y',
    receipt_width INTEGER DEFAULT 80,
    print_copies INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Account Masters (Customers, Suppliers, Banks, Cash)
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    alias TEXT,
    print_name TEXT,
    account_group TEXT NOT NULL, -- 'Sundry Debtors', 'Sundry Creditors', etc.
    op_bal REAL DEFAULT 0.0,
    op_type TEXT DEFAULT 'Dr',
    address TEXT,
    state TEXT DEFAULT 'Tamilnadu',
    dealer_type TEXT DEFAULT 'Unregistered',
    gstin TEXT,
    mobile TEXT,
    bank_name TEXT,
    bank_acc TEXT,
    ifsc TEXT,
    current_balance REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, name)
);

-- 6. Item Masters (Products & Goods)
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    alias TEXT,
    print_name TEXT,
    item_group TEXT DEFAULT 'General',
    unit TEXT DEFAULT 'Pcs.',
    op_stock_qty REAL DEFAULT 0.0,
    op_stock_val REAL DEFAULT 0.0,
    tax_category TEXT DEFAULT 'GST 18%',
    hsn TEXT,
    sales_price REAL DEFAULT 0.0,
    purc_price REAL DEFAULT 0.0,
    mrp REAL DEFAULT 0.0,
    min_sales_price REAL DEFAULT 0.0,
    description TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, name)
);

-- 7. Item Barcodes (Supports multiple barcodes per item)
CREATE TABLE IF NOT EXISTS item_barcodes (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    barcode TEXT NOT NULL,
    is_primary INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, barcode)
);

-- 8. Branch Stock Balances
CREATE TABLE IF NOT EXISTS stock_balances (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    branch_id TEXT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    current_qty REAL DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(branch_id, item_id)
);

-- 9. Stock Movements (Ledger of all stock ins and outs)
CREATE TABLE IF NOT EXISTS stock_movements (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    branch_id TEXT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    movement_type TEXT NOT NULL, -- 'OPENING', 'SALE', 'RETURN', 'PURCHASE', 'ADJUSTMENT'
    qty REAL NOT NULL,           -- Positive for addition, negative for deduction
    unit_cost REAL DEFAULT 0.0,
    reference_type TEXT,         -- 'INVOICE', 'MANUAL', 'PURCHASE'
    reference_id TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10. Sales Vouchers / Invoices
CREATE TABLE IF NOT EXISTS sales_vouchers (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    branch_id TEXT REFERENCES branches(id) ON DELETE SET NULL,
    vch_no TEXT NOT NULL,
    series TEXT DEFAULT 'Main',
    vch_date TEXT NOT NULL,
    sale_type TEXT NOT NULL,     -- 'L/GST-18%', 'I/GST-18%', etc.
    party_name TEXT NOT NULL,
    account_id TEXT REFERENCES accounts(id) ON DELETE SET NULL,
    party_gstin TEXT,
    mat_centre TEXT DEFAULT 'Main Store',
    narration TEXT,
    subtotal REAL NOT NULL DEFAULT 0.0,
    taxable_amount REAL NOT NULL DEFAULT 0.0,
    tax_rate REAL DEFAULT 0.0,
    cgst_amount REAL DEFAULT 0.0,
    sgst_amount REAL DEFAULT 0.0,
    igst_amount REAL DEFAULT 0.0,
    round_off REAL DEFAULT 0.0,
    grand_total REAL NOT NULL DEFAULT 0.0,
    payment_method TEXT DEFAULT 'CASH',
    payment_status TEXT DEFAULT 'PAID',
    is_cancelled INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, vch_no)
);

-- 11. Sales Voucher Line Items
CREATE TABLE IF NOT EXISTS sales_voucher_items (
    id TEXT PRIMARY KEY,
    voucher_id TEXT NOT NULL REFERENCES sales_vouchers(id) ON DELETE CASCADE,
    item_id TEXT REFERENCES items(id) ON DELETE SET NULL,
    sn INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    hsn TEXT,
    qty REAL NOT NULL,
    unit TEXT DEFAULT 'Pcs.',
    price REAL NOT NULL,
    amount REAL NOT NULL,
    tax_rate REAL DEFAULT 0.0,
    tax_amount REAL DEFAULT 0.0
);

-- 12. Payments Ledger
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    voucher_id TEXT REFERENCES sales_vouchers(id) ON DELETE CASCADE,
    method TEXT NOT NULL,       -- 'CASH', 'UPI', 'CARD', 'CREDIT'
    amount REAL NOT NULL,
    ref_number TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 13. Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    company_id TEXT REFERENCES companies(id) ON DELETE SET NULL,
    username TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_items_company ON items(company_id);
CREATE INDEX IF NOT EXISTS idx_barcodes_lookup ON item_barcodes(company_id, barcode);
CREATE INDEX IF NOT EXISTS idx_stock_branch_item ON stock_balances(branch_id, item_id);
CREATE INDEX IF NOT EXISTS idx_vouchers_comp_date ON sales_vouchers(company_id, vch_date);
CREATE INDEX IF NOT EXISTS idx_voucher_items_vch ON sales_voucher_items(voucher_id);

