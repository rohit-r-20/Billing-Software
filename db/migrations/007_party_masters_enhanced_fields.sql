-- Migration 007: Permanent Database-Backed Party Masters (Customers & Suppliers)
-- Enhances accounts table with comprehensive party fields, active status, and audit timestamps.
-- Idempotent and non-destructive.

ALTER TABLE accounts ADD COLUMN country TEXT DEFAULT 'India';
ALTER TABLE accounts ADD COLUMN whatsapp TEXT;
ALTER TABLE accounts ADD COLUMN pincode TEXT;
ALTER TABLE accounts ADD COLUMN payment_terms INTEGER DEFAULT 30;
ALTER TABLE accounts ADD COLUMN notes TEXT;
ALTER TABLE accounts ADD COLUMN is_active INTEGER DEFAULT 1;
ALTER TABLE accounts ADD COLUMN updated_at TIMESTAMP;

-- Indexes for fast party lookups by group, mobile, GSTIN, and active status
CREATE INDEX IF NOT EXISTS idx_accounts_group_active ON accounts(company_id, account_group, is_active);
CREATE INDEX IF NOT EXISTS idx_accounts_mobile ON accounts(company_id, mobile);
CREATE INDEX IF NOT EXISTS idx_accounts_gstin ON accounts(company_id, gstin);
