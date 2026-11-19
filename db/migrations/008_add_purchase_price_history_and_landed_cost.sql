-- Migration 008: Add purchase_price_history table, freight_charges, handling_charges, and landed_cost
-- Non-destructive, additive, idempotent.

-- 1. Purchase Price History Table
CREATE TABLE IF NOT EXISTS purchase_price_history (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    branch_id TEXT REFERENCES branches(id) ON DELETE SET NULL,
    item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    supplier_id TEXT REFERENCES suppliers(id) ON DELETE SET NULL,
    voucher_id TEXT NOT NULL REFERENCES purchase_vouchers(id) ON DELETE CASCADE,
    voucher_number TEXT NOT NULL,
    supplier_invoice_no TEXT,
    purchase_date TEXT NOT NULL,
    purchase_rate REAL NOT NULL,
    qty REAL NOT NULL,
    discount_percent REAL DEFAULT 0.0,
    tax_rate REAL DEFAULT 0.0,
    landed_cost REAL DEFAULT 0.0,
    previous_rate REAL DEFAULT 0.0,
    is_revision INTEGER DEFAULT 0,
    revision_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pph_lookup ON purchase_price_history(company_id, item_id, supplier_id, purchase_date);
CREATE INDEX IF NOT EXISTS idx_pph_item_date ON purchase_price_history(company_id, item_id, purchase_date);
CREATE INDEX IF NOT EXISTS idx_pph_voucher ON purchase_price_history(voucher_id);
