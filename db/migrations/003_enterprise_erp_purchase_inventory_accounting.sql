-- Migration 003: Enterprise ERP Integration — Purchase, Suppliers, Returns, Adjustments, Transfers, Valuation & Accounting
-- Compatible with SQLite, safe, idempotent, and non-destructive.

-- 1. Suppliers Master Table
CREATE TABLE IF NOT EXISTS suppliers (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    contact_person TEXT,
    mobile TEXT,
    email TEXT,
    gstin TEXT,
    pan TEXT,
    address TEXT,
    city TEXT,
    state TEXT DEFAULT 'Tamilnadu',
    pincode TEXT,
    opening_balance REAL DEFAULT 0.0,
    credit_limit REAL DEFAULT 0.0,
    payment_terms INTEGER DEFAULT 30,
    bank_name TEXT,
    bank_acc TEXT,
    ifsc TEXT,
    current_balance REAL DEFAULT 0.0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, name),
    UNIQUE(company_id, code)
);

CREATE INDEX IF NOT EXISTS idx_suppliers_company ON suppliers(company_id);
CREATE INDEX IF NOT EXISTS idx_suppliers_lookup ON suppliers(company_id, name);

-- 2. Godowns / Warehouses
CREATE TABLE IF NOT EXISTS godowns (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    branch_id TEXT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    address TEXT,
    is_default INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(branch_id, code)
);

CREATE INDEX IF NOT EXISTS idx_godowns_branch ON godowns(branch_id);

-- 3. Purchase Vouchers (Item Invoices)
CREATE TABLE IF NOT EXISTS purchase_vouchers (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    branch_id TEXT REFERENCES branches(id) ON DELETE SET NULL,
    godown_id TEXT REFERENCES godowns(id) ON DELETE SET NULL,
    vch_no TEXT NOT NULL,                     -- Internal e.g. PUR-000001
    supplier_invoice_no TEXT NOT NULL,        -- Supplier's physical bill e.g. ABC/2026/001
    supplier_invoice_date TEXT NOT NULL,      -- Supplier's bill date
    vch_date TEXT NOT NULL,                   -- Entry date
    supplier_id TEXT REFERENCES suppliers(id) ON DELETE SET NULL,
    supplier_name TEXT NOT NULL,
    supplier_gstin TEXT,
    supplier_address TEXT,
    supplier_state TEXT DEFAULT 'Tamilnadu',
    place_of_supply TEXT DEFAULT 'Tamilnadu',
    payment_type TEXT DEFAULT 'CREDIT',       -- 'CASH', 'BANK', 'CREDIT'
    due_date TEXT,
    purchase_type TEXT DEFAULT 'GST Purchase',-- 'GST Purchase', 'Non-GST Purchase'
    narration TEXT,
    gross_amount REAL DEFAULT 0.0,
    discount_total REAL DEFAULT 0.0,
    additional_expenses REAL DEFAULT 0.0,
    taxable_amount REAL DEFAULT 0.0,
    cgst_amount REAL DEFAULT 0.0,
    sgst_amount REAL DEFAULT 0.0,
    igst_amount REAL DEFAULT 0.0,
    cess_amount REAL DEFAULT 0.0,
    round_off REAL DEFAULT 0.0,
    grand_total REAL NOT NULL DEFAULT 0.0,
    amount_paid REAL DEFAULT 0.0,
    outstanding_balance REAL DEFAULT 0.0,
    is_draft INTEGER DEFAULT 0,
    is_cancelled INTEGER DEFAULT 0,
    created_by TEXT DEFAULT 'Admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, vch_no),
    UNIQUE(company_id, supplier_name, supplier_invoice_no, supplier_invoice_date)
);

CREATE INDEX IF NOT EXISTS idx_purchase_comp_date ON purchase_vouchers(company_id, vch_date);
CREATE INDEX IF NOT EXISTS idx_purchase_supplier ON purchase_vouchers(supplier_id);
CREATE INDEX IF NOT EXISTS idx_purchase_supp_inv ON purchase_vouchers(company_id, supplier_invoice_no);

-- 4. Purchase Voucher Line Items
CREATE TABLE IF NOT EXISTS purchase_voucher_items (
    id TEXT PRIMARY KEY,
    voucher_id TEXT NOT NULL REFERENCES purchase_vouchers(id) ON DELETE CASCADE,
    item_id TEXT REFERENCES items(id) ON DELETE SET NULL,
    sn INTEGER NOT NULL,
    barcode TEXT,
    item_name TEXT NOT NULL,
    hsn TEXT,
    qty REAL NOT NULL,
    free_qty REAL DEFAULT 0.0,
    unit TEXT DEFAULT 'Pcs.',
    purchase_rate REAL NOT NULL,
    discount_percent REAL DEFAULT 0.0,
    discount_amount REAL DEFAULT 0.0,
    taxable_amount REAL NOT NULL,
    tax_rate REAL DEFAULT 0.0,
    cgst_amount REAL DEFAULT 0.0,
    sgst_amount REAL DEFAULT 0.0,
    igst_amount REAL DEFAULT 0.0,
    cess_amount REAL DEFAULT 0.0,
    line_total REAL NOT NULL,
    batch_no TEXT,
    expiry_date TEXT
);

CREATE INDEX IF NOT EXISTS idx_purchase_items_vch ON purchase_voucher_items(voucher_id);
CREATE INDEX IF NOT EXISTS idx_purchase_items_item ON purchase_voucher_items(item_id);

-- 5. Purchase Returns (Debit Notes)
CREATE TABLE IF NOT EXISTS purchase_returns (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    branch_id TEXT REFERENCES branches(id) ON DELETE SET NULL,
    vch_no TEXT NOT NULL,
    original_voucher_id TEXT REFERENCES purchase_vouchers(id) ON DELETE SET NULL,
    original_supplier_inv_no TEXT,
    vch_date TEXT NOT NULL,
    supplier_id TEXT REFERENCES suppliers(id) ON DELETE SET NULL,
    supplier_name TEXT NOT NULL,
    reason TEXT,
    taxable_amount REAL DEFAULT 0.0,
    cgst_amount REAL DEFAULT 0.0,
    sgst_amount REAL DEFAULT 0.0,
    igst_amount REAL DEFAULT 0.0,
    grand_total REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, vch_no)
);

CREATE TABLE IF NOT EXISTS purchase_return_items (
    id TEXT PRIMARY KEY,
    return_id TEXT NOT NULL REFERENCES purchase_returns(id) ON DELETE CASCADE,
    item_id TEXT REFERENCES items(id) ON DELETE SET NULL,
    sn INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    qty REAL NOT NULL,
    unit TEXT DEFAULT 'Pcs.',
    rate REAL NOT NULL,
    tax_rate REAL DEFAULT 0.0,
    tax_amount REAL DEFAULT 0.0,
    line_total REAL NOT NULL
);

-- 6. Sales Returns (Credit Notes)
CREATE TABLE IF NOT EXISTS sales_returns (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    branch_id TEXT REFERENCES branches(id) ON DELETE SET NULL,
    vch_no TEXT NOT NULL,
    original_voucher_id TEXT REFERENCES sales_vouchers(id) ON DELETE SET NULL,
    original_invoice_no TEXT,
    vch_date TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    reason TEXT,
    taxable_amount REAL DEFAULT 0.0,
    cgst_amount REAL DEFAULT 0.0,
    sgst_amount REAL DEFAULT 0.0,
    igst_amount REAL DEFAULT 0.0,
    grand_total REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, vch_no)
);

CREATE TABLE IF NOT EXISTS sales_return_items (
    id TEXT PRIMARY KEY,
    return_id TEXT NOT NULL REFERENCES sales_returns(id) ON DELETE CASCADE,
    item_id TEXT REFERENCES items(id) ON DELETE SET NULL,
    sn INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    qty REAL NOT NULL,
    unit TEXT DEFAULT 'Pcs.',
    rate REAL NOT NULL,
    tax_rate REAL DEFAULT 0.0,
    tax_amount REAL DEFAULT 0.0,
    line_total REAL NOT NULL,
    restock_condition TEXT DEFAULT 'SALEABLE' -- 'SALEABLE', 'DAMAGED'
);

-- 7. Stock Adjustments
CREATE TABLE IF NOT EXISTS stock_adjustments (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    branch_id TEXT REFERENCES branches(id) ON DELETE SET NULL,
    godown_id TEXT REFERENCES godowns(id) ON DELETE SET NULL,
    vch_no TEXT NOT NULL,
    adj_date TEXT NOT NULL,
    adj_type TEXT NOT NULL, -- 'INCREASE', 'DECREASE', 'DAMAGE', 'EXPIRED', 'PHYSICAL_AUDIT'
    reason TEXT NOT NULL,
    authorized_by TEXT DEFAULT 'Admin',
    notes TEXT,
    total_items INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, vch_no)
);

CREATE TABLE IF NOT EXISTS stock_adjustment_items (
    id TEXT PRIMARY KEY,
    adjustment_id TEXT NOT NULL REFERENCES stock_adjustments(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    system_qty REAL NOT NULL,
    physical_qty REAL,
    diff_qty REAL NOT NULL,
    unit_cost REAL DEFAULT 0.0,
    notes TEXT
);

-- 8. Stock Transfers (Inter-godown / Inter-branch)
CREATE TABLE IF NOT EXISTS stock_transfers (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    transfer_no TEXT NOT NULL,
    transfer_date TEXT NOT NULL,
    source_branch_id TEXT REFERENCES branches(id) ON DELETE SET NULL,
    source_godown_id TEXT REFERENCES godowns(id) ON DELETE SET NULL,
    dest_branch_id TEXT REFERENCES branches(id) ON DELETE SET NULL,
    dest_godown_id TEXT REFERENCES godowns(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'COMPLETED', -- 'DISPATCHED', 'COMPLETED', 'CANCELLED'
    reason TEXT,
    created_by TEXT DEFAULT 'Admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, transfer_no)
);

CREATE TABLE IF NOT EXISTS stock_transfer_items (
    id TEXT PRIMARY KEY,
    transfer_id TEXT NOT NULL REFERENCES stock_transfers(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    qty REAL NOT NULL,
    unit TEXT DEFAULT 'Pcs.',
    unit_cost REAL DEFAULT 0.0
);

-- 9. Stock Batches
CREATE TABLE IF NOT EXISTS stock_batches (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    batch_no TEXT NOT NULL,
    mfg_date TEXT,
    expiry_date TEXT,
    purchase_rate REAL DEFAULT 0.0,
    qty_received REAL NOT NULL DEFAULT 0.0,
    qty_sold REAL NOT NULL DEFAULT 0.0,
    qty_available REAL NOT NULL DEFAULT 0.0,
    supplier_id TEXT REFERENCES suppliers(id) ON DELETE SET NULL,
    purchase_voucher_id TEXT REFERENCES purchase_vouchers(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, item_id, batch_no)
);

CREATE INDEX IF NOT EXISTS idx_batches_expiry ON stock_batches(company_id, expiry_date);

-- 10. Multi-Unit Conversions
CREATE TABLE IF NOT EXISTS unit_conversions (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    item_id TEXT REFERENCES items(id) ON DELETE CASCADE,
    from_unit TEXT NOT NULL,
    to_unit TEXT NOT NULL,
    multiplier REAL NOT NULL, -- e.g. 1 Box = 24 Pcs -> multiplier = 24.0
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, item_id, from_unit, to_unit)
);

-- 11. Double-Entry Accounting Journal
CREATE TABLE IF NOT EXISTS journal_entries (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    vch_no TEXT NOT NULL,
    vch_date TEXT NOT NULL,
    vch_type TEXT NOT NULL, -- 'PURCHASE', 'SALE', 'PURCHASE_RETURN', 'SALES_RETURN', 'PAYMENT', 'RECEIPT'
    reference_id TEXT,
    narration TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS journal_entry_lines (
    id TEXT PRIMARY KEY,
    journal_id TEXT NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
    account_name TEXT NOT NULL,
    debit REAL DEFAULT 0.0,
    credit REAL DEFAULT 0.0,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_journal_comp_date ON journal_entries(company_id, vch_date);
CREATE INDEX IF NOT EXISTS idx_journal_lines_acc ON journal_entry_lines(account_name);

-- 12. Supplier Invoice OCR & Document Staging
CREATE TABLE IF NOT EXISTS ocr_invoice_drafts (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    file_path TEXT,
    file_name TEXT,
    extracted_data TEXT, -- JSON
    status TEXT DEFAULT 'DRAFT', -- 'DRAFT', 'POSTED', 'DISCARDED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

