-- Migration 002: Add Discount Support to Sales Invoices & Daily Discount Configuration Table

-- 1. Add discount fields to sales_vouchers
ALTER TABLE sales_vouchers ADD COLUMN gross_subtotal REAL DEFAULT 0.0;
ALTER TABLE sales_vouchers ADD COLUMN discount_total REAL DEFAULT 0.0;

-- 2. Add discount fields to sales_voucher_items
ALTER TABLE sales_voucher_items ADD COLUMN discount_percent REAL DEFAULT 0.0;
ALTER TABLE sales_voucher_items ADD COLUMN discount_amount REAL DEFAULT 0.0;
ALTER TABLE sales_voucher_items ADD COLUMN taxable_amount REAL DEFAULT 0.0;

-- 3. Daily Discount Configuration Table
CREATE TABLE IF NOT EXISTS daily_discount_configs (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    branch_id TEXT REFERENCES branches(id) ON DELETE SET NULL,
    business_date TEXT NOT NULL,              -- 'YYYY-MM-DD'
    discount_percent REAL NOT NULL DEFAULT 0.0,
    is_active INTEGER NOT NULL DEFAULT 1,
    enabled_by TEXT NOT NULL DEFAULT 'Admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, branch_id, business_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_discount_lookup 
ON daily_discount_configs(company_id, branch_id, business_date, is_active);
