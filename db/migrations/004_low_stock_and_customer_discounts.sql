-- Migration 004: Product-Level Low-Stock Thresholds & Configurable Customer Category Discounts
-- Anti Matrix Alpha Billing Software — Controlled Enhancement

-- 1. Product Master additions for low-stock threshold & notifications
ALTER TABLE items ADD COLUMN min_stock_alert_level REAL DEFAULT NULL;
ALTER TABLE items ADD COLUMN alert_enabled INTEGER DEFAULT 1;

-- 2. Customer Master additions for customer category
ALTER TABLE accounts ADD COLUMN customer_category TEXT DEFAULT 'Direct Customer';

-- 3. Sales Vouchers customer category snapshot
ALTER TABLE sales_vouchers ADD COLUMN customer_category TEXT DEFAULT 'Direct Customer';

-- 4. Customer Category Discounts Configuration Table
CREATE TABLE IF NOT EXISTS customer_category_discounts (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    category TEXT NOT NULL,                         -- 'Commercial', 'Sub-Commercial', 'Direct Customer'
    discount_percent REAL NOT NULL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, category)
);

CREATE INDEX IF NOT EXISTS idx_customer_category_discounts 
ON customer_category_discounts(company_id, category);

-- 5. Seed default discounts for existing companies (Commercial: 5.0%, Sub-Commercial: 2.5%, Direct: 0.0%)
INSERT OR IGNORE INTO customer_category_discounts (id, company_id, category, discount_percent, updated_at)
SELECT lower(hex(randomblob(16))), id, 'Commercial', 5.0, CURRENT_TIMESTAMP FROM companies;

INSERT OR IGNORE INTO customer_category_discounts (id, company_id, category, discount_percent, updated_at)
SELECT lower(hex(randomblob(16))), id, 'Sub-Commercial', 2.5, CURRENT_TIMESTAMP FROM companies;

INSERT OR IGNORE INTO customer_category_discounts (id, company_id, category, discount_percent, updated_at)
SELECT lower(hex(randomblob(16))), id, 'Direct Customer', 0.0, CURRENT_TIMESTAMP FROM companies;

-- 6. Persistent Low-Stock Alert State & Lifecycle Tracking Table
CREATE TABLE IF NOT EXISTS low_stock_alerts (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    threshold REAL NOT NULL,
    available_qty REAL NOT NULL,
    status TEXT DEFAULT 'ACTIVE',                   -- 'ACTIVE', 'RESOLVED', 'DISMISSED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    dismissed_at TIMESTAMP,
    last_evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_low_stock_alerts_lookup 
ON low_stock_alerts(company_id, status);

