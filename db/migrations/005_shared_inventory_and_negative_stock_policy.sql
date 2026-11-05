-- Migration 005: Shared Inventory Integration and Negative Stock Policy
-- Ensures unified stock ledger across Traditional Billing and Fast Billing
-- Adds company configuration for negative stock control and performance indexes

-- 1. Add allow_negative_stock column to company_configs if absent
-- SQLite supports ADD COLUMN safely
ALTER TABLE company_configs ADD COLUMN allow_negative_stock INTEGER DEFAULT 0;

-- 2. Performance and isolation indexes for multi-company & multi-branch stock
CREATE INDEX IF NOT EXISTS idx_stock_balances_comp_branch_item ON stock_balances (company_id, branch_id, item_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_comp_branch_item ON stock_movements (company_id, branch_id, item_id, movement_type);
CREATE INDEX IF NOT EXISTS idx_stock_movements_ref ON stock_movements (reference_id, reference_type);
