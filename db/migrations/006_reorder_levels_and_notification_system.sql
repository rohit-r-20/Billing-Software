-- Migration 006: Reorder Levels and Automatic Low-Stock Notification System
-- Implements configurable minimum stock level, reorder level, preferred reorder quantity,
-- branch-level stock overrides, and enriched low-stock notification state.

-- 1. Enforce Item Master configuration columns
ALTER TABLE items ADD COLUMN reorder_level REAL DEFAULT NULL;
ALTER TABLE items ADD COLUMN reorder_qty REAL DEFAULT NULL;
ALTER TABLE items ADD COLUMN max_stock_level REAL DEFAULT NULL;

-- 2. Enforce Low Stock Alert enrichment columns
ALTER TABLE low_stock_alerts ADD COLUMN branch_id TEXT;
ALTER TABLE low_stock_alerts ADD COLUMN reorder_level REAL;
ALTER TABLE low_stock_alerts ADD COLUMN min_stock_level REAL;
ALTER TABLE low_stock_alerts ADD COLUMN suggested_reorder_qty REAL;
ALTER TABLE low_stock_alerts ADD COLUMN severity TEXT DEFAULT 'REORDER_REQUIRED';

-- 3. Branch / Warehouse Specific Stock Threshold Overrides
CREATE TABLE IF NOT EXISTS item_branch_stock_configs (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    branch_id TEXT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    min_stock_level REAL,
    reorder_level REAL,
    reorder_qty REAL,
    max_stock_level REAL,
    alert_enabled INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(branch_id, item_id)
);

CREATE INDEX IF NOT EXISTS idx_item_branch_stock_configs_lookup 
ON item_branch_stock_configs(company_id, branch_id, item_id);
