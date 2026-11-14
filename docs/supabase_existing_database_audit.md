# Alpha Billing V2 — Supabase Existing Database Audit

## 1. Executive Summary

This document provides a comprehensive, read-only architectural audit of the live **Supabase PostgreSQL** cloud instance connected to Alpha Billing. The audit was conducted using direct, read-only system catalog queries (`information_schema` and `pg_catalog`) via **Psycopg 3** with strict SSL enforcement (`sslmode=require`).

> [!IMPORTANT]
> **Safety Compliance**:
> All queries executed during this audit were strictly read-only (`SELECT`). No DDL, `DROP`, `TRUNCATE`, `ALTER`, or `DELETE` statements were executed. Existing data and schema definitions remain 100% intact.

---

## 2. Server & Endpoint Verification

- **Host**: `db.nxetowrecgjbpijdjpqd.supabase.co` (Direct IPv6: `2406:da14:18fe:3100::2c0c:5432`)
- **Engine / Version**: `PostgreSQL 17.11 on aarch64-unknown-linux-gnu, compiled by gcc (GCC) 15.2.0, 64-bit`
- **Database**: `postgres`
- **Active User**: `postgres`
- **SSL / TLS**: Active (`TLS_AES_256_GCM_SHA384`, Enforced `sslmode=require`)
- **Alembic Version**: `63b87d829649` (Migration Revision: `reconcile_all_master_ids_and_branches`)

---

## 3. Database Schemas Discovered

The PostgreSQL instance contains **8 schemas**:
1. `public`: Application tables, views, sequences, and Alembic version tracking.
2. `auth`: Supabase authentication and identity management system schema.
3. `extensions`: Installed PostgreSQL extensions (e.g. `uuid-ossp`, `pgcrypto`).
4. `graphql`: Supabase GraphQL engine schema.
5. `graphql_public`: Public entrypoint for GraphQL queries.
6. `realtime`: Supabase CDC / WebSocket replication schema.
7. `storage`: Supabase object storage metadata schema.
8. `vault`: Encrypted secrets and key management vault.

---

## 4. Public Schema Tables & Business Record Row Counts

The `public` schema contains **40 tables** holding a total of **12,152 rows**:

| # | Table Name | Type | Row Count | Primary Key | Foreign Keys | Status / Purpose |
|---|---|---|---|---|---|---|
| 1 | `accounts` | BASE TABLE | **385** | `id` | 1 | Customer/Party masters (legacy) |
| 2 | `alembic_version` | BASE TABLE | **1** | `version_num` | 0 | Revision tracking (`63b87d829649`) |
| 3 | `audit_logs` | BASE TABLE | **897** | `id` | 1 | System activity and change audit trail |
| 4 | `barcode_sequences` | BASE TABLE | **1** | `id` | 0 | Sequence tracking for internal barcodes |
| 5 | `branches` | BASE TABLE | **47** | `id` | 1 | Legacy multi-branch distribution entities |
| 6 | `companies` | BASE TABLE | **2** | `id` | 0 | Company entities ('ANTI MATRIX', 'Second Isolated Company') |
| 7 | `company_configs` | BASE TABLE | **1** | `company_id` | 1 | Voucher prefixes, default tax, rounding rules |
| 8 | `customer_category_discounts` | BASE TABLE | **6** | `id` | 1 | Customer pricing tier discounts |
| 9 | `daily_discount_configs` | BASE TABLE | **0** | `id` | 2 | Scheduled discount configurations |
| 10 | `godowns` | BASE TABLE | **0** | `id` | 2 | Legacy warehouse entities |
| 11 | `item_barcodes` | BASE TABLE | **452** | `id` | 2 | Barcode to item mappings |
| 12 | `item_branch_stock_configs` | BASE TABLE | **15** | `id` | 3 | Per-branch reorder thresholds |
| 13 | `items` | BASE TABLE | **813** | `id` | 1 | Item / Product master catalogue |
| 14 | `journal_entries` | BASE TABLE | **747** | `id` | 1 | Double-entry journal vouchers |
| 15 | `journal_entry_lines` | BASE TABLE | **3,040** | `id` | 2 | Double-entry accounting line items |
| 16 | `low_stock_alerts` | BASE TABLE | **1,905** | `id` | 3 | Reorder notification alert queue |
| 17 | `ocr_invoice_drafts` | BASE TABLE | **2** | `id` | 1 | Scanned invoice OCR drafts |
| 18 | `payments` | BASE TABLE | **578** | `id` | 2 | Customer sales invoice payment receipts |
| 19 | `purchase_return_items` | BASE TABLE | **0** | `id` | 2 | Purchase return line items |
| 20 | `purchase_returns` | BASE TABLE | **0** | `id` | 4 | Debit note vouchers |
| 21 | `purchase_voucher_items` | BASE TABLE | **136** | `id` | 2 | Purchase line items |
| 22 | `purchase_vouchers` | BASE TABLE | **136** | `id` | 4 | Inward purchase vouchers |
| 23 | `registers` | BASE TABLE | **1** | `id` | 1 | POS cash drawer / terminal register |
| 24 | `roles` | BASE TABLE | **0** | `id` | 0 | Role definitions (RBAC) |
| 25 | `sales_return_items` | BASE TABLE | **36** | `id` | 2 | Sales return line items |
| 26 | `sales_returns` | BASE TABLE | **36** | `id` | 4 | Credit note vouchers |
| 27 | `sales_voucher_items` | BASE TABLE | **579** | `id` | 2 | Retail billing line items |
| 28 | `sales_vouchers` | BASE TABLE | **578** | `id` | 3 | Sales tax invoice vouchers |
| 29 | `stock_adjustment_items` | BASE TABLE | **0** | `id` | 2 | Stock audit variance item lines |
| 30 | `stock_adjustments` | BASE TABLE | **0** | `id` | 2 | Physical inventory adjustment vouchers |
| 31 | `stock_balances` | BASE TABLE | **842** | `id` | 3 | Current stock quantities per branch/item |
| 32 | `stock_batches` | BASE TABLE | **0** | `id` | 4 | Expiry/batch tracking entities |
| 33 | `stock_movements` | BASE TABLE | **825** | `id` | 3 | Stock ledger movement transactions |
| 34 | `stock_transfer_items` | BASE TABLE | **0** | `id` | 2 | Inter-branch transfer line items |
| 35 | `stock_transfers` | BASE TABLE | **0** | `id` | 3 | Inter-branch inventory dispatch |
| 36 | `suppliers` | BASE TABLE | **91** | `id` | 1 | Vendor / Supplier master records |
| 37 | `unit_conversions` | BASE TABLE | **0** | `id` | 2 | Unit of measurement conversion rates |
| 38 | `user_permissions` | BASE TABLE | **0** | `id` | 1 | Granular access control permissions |
| 39 | `users` | BASE TABLE | **0** | `id` | 2 | System login accounts |
| 40 | `voucher_sequences` | BASE TABLE | **0** | `id` | 1 | Serial voucher numbering sequences |

---

## 5. Architectural Attribution: Previous Schema vs. Corrected V2

A central question in this audit is:
> **Do the 40 reported tables belong to the previous legacy schema or the corrected V2 architecture?**

### Finding: The 40 tables belong to the PREVIOUS (Legacy) Schema.

#### Technical Evidence:
1. **Separate Customer & Supplier Entities**:
   - Supabase currently has separate tables `accounts` (385 rows) and `suppliers` (91 rows).
   - In the approved **Corrected V2 Architecture**, all parties are unified into a single table with a `party_type` discriminator (`CUSTOMER`, `SUPPLIER`, `BOTH`).
2. **Multi-Branch & Warehouse Overkill**:
   - Supabase contains `branches` (47 rows), `godowns` (0 rows), `registers` (1 row), `stock_transfers`, and `stock_transfer_items`.
   - The strict **V2 Scope** permits only **One Company** and **One Stock Location** (`stock_locations`). Multi-branch distribution tables are explicitly out of scope for V2.
3. **Absence of Approved V2 Tables**:
   - The Corrected V2 specification defines `purchase_payments`, `supplier_allocations`, `product_categories`, `product_units`, and `system_backups`.
   - **None of these 5 tables exist in the current Supabase database**.
4. **Legacy Data Structures**:
   - Sales vouchers contain `vch_date` stored as `character varying(20)` strings (e.g. `'01-11-2026'`) rather than native PostgreSQL `DATE`.
   - Monetary and quantity fields are typed as `double precision` (`Float`) rather than exact `NUMERIC(15, 2)`.
   - Sales voucher items lack the `cost_price_at_sale` snapshot column required for historical COGS calculation.
   - Stock movements lack `historical_cost`, `running_qty`, and `running_valuation` columns required for WAC valuation.

---

## 6. Table Structure, Keys, and Constraints Detail

### A. Core Master Tables

#### `accounts` (Customer Masters - 385 Rows)
- **Primary Key**: `id` (`character varying(36)`)
- **Foreign Keys**: `company_id` -> `companies.id` (ON DELETE CASCADE)
- **Key Columns**: `name` (varchar), `print_name` (varchar), `account_group` (varchar), `gstin` (varchar), `mobile` (varchar), `opening_balance` (double precision), `current_balance` (double precision), `is_active` (integer).
- **Indexes**: `accounts_pkey` (unique), `ix_accounts_company_id`, `ix_accounts_name`, `ix_accounts_group`, `ix_accounts_gstin`, `ix_accounts_mobile`.

#### `suppliers` (Supplier Masters - 91 Rows)
- **Primary Key**: `id` (`character varying(36)`)
- **Foreign Keys**: `company_id` -> `companies.id` (ON DELETE CASCADE)
- **Key Columns**: `name` (varchar), `print_name` (varchar), `gstin` (varchar), `phone` (varchar), `opening_balance` (double precision), `current_balance` (double precision), `is_active` (integer).
- **Indexes**: `suppliers_pkey` (unique), `ix_suppliers_company_id`, `ix_suppliers_name`, `ix_suppliers_gstin`.

#### `items` (Item & Product Master - 813 Rows)
- **Primary Key**: `id` (`character varying(36)`)
- **Foreign Keys**: `company_id` -> `companies.id` (ON DELETE CASCADE)
- **Key Columns**: `name` (varchar), `receipt_name` (varchar), `category` (varchar), `unit` (varchar), `hsn_code` (varchar), `tax_rate` (double precision), `sales_price` (double precision), `purc_price` (double precision), `mrp` (double precision), `is_active` (integer).
- **Indexes**: `items_pkey` (unique), `ix_items_company_id`, `ix_items_name`, `ix_items_category`, `ix_items_hsn_code`.

#### `item_barcodes` (Barcode Master - 452 Rows)
- **Primary Key**: `id` (`character varying(36)`)
- **Foreign Keys**:
  - `company_id` -> `companies.id` (ON DELETE CASCADE)
  - `item_id` -> `items.id` (ON DELETE CASCADE)
- **Key Columns**: `barcode` (varchar), `is_primary` (integer).
- **Indexes**: `item_barcodes_pkey` (unique), `uq_item_barcodes_company_code` (unique on `company_id, barcode`), `ix_item_barcodes_item_id`.

---

### B. Transaction Tables

#### `sales_vouchers` (Sales Invoices - 578 Rows)
- **Primary Key**: `id` (`character varying(36)`)
- **Foreign Keys**:
  - `company_id` -> `companies.id` (ON DELETE CASCADE)
  - `branch_id` -> `branches.id` (ON DELETE SET NULL)
  - `account_id` -> `accounts.id` (ON DELETE SET NULL)
- **Key Columns**: `vch_no` (varchar), `series` (varchar), `vch_date` (varchar), `party_name` (varchar), `party_gstin` (varchar), `taxable_amount` (double precision), `cgst_amount` (double precision), `sgst_amount` (double precision), `round_off` (double precision), `grand_total` (double precision), `payment_method` (varchar).
- **Indexes**: `sales_vouchers_pkey` (unique), `uq_sales_vouchers_comp_vchno` (unique on `company_id, vch_no`), `idx_sales_vouchers_comp_date`, `ix_sales_vouchers_account_id`.

#### `purchase_vouchers` (Purchase Invoices - 136 Rows)
- **Primary Key**: `id` (`character varying(36)`)
- **Foreign Keys**:
  - `company_id` -> `companies.id` (ON DELETE CASCADE)
  - `branch_id` -> `branches.id` (ON DELETE SET NULL)
  - `godown_id` -> `godowns.id` (ON DELETE SET NULL)
  - `supplier_id` -> `suppliers.id` (ON DELETE SET NULL)
- **Key Columns**: `vch_no` (varchar), `supplier_invoice_no` (varchar), `vch_date` (varchar), `supplier_name` (varchar), `taxable_amount` (double precision), `grand_total` (double precision).
- **Indexes**: `purchase_vouchers_pkey` (unique), `uq_purchase_vouchers_comp_vchno` (unique on `company_id, vch_no`), `ix_purchase_vouchers_supplier_id`.

---

### C. Inventory Ledger & Balances

#### `stock_balances` (842 Rows)
- **Primary Key**: `id` (`character varying(36)`)
- **Foreign Keys**:
  - `company_id` -> `companies.id` (ON DELETE CASCADE)
  - `branch_id` -> `branches.id` (ON DELETE CASCADE)
  - `item_id` -> `items.id` (ON DELETE CASCADE)
- **Key Columns**: `current_qty` (double precision), `last_updated` (timestamp).
- **Unique Constraint**: `uq_stock_balances_branch_item` (unique on `branch_id, item_id`).

#### `stock_movements` (825 Rows)
- **Primary Key**: `id` (`character varying(36)`)
- **Foreign Keys**:
  - `company_id` -> `companies.id` (ON DELETE CASCADE)
  - `branch_id` -> `branches.id` (ON DELETE CASCADE)
  - `item_id` -> `items.id` (ON DELETE CASCADE)
- **Key Columns**: `movement_type` (varchar: 'IN', 'OUT', 'PURCHASE', 'SALE'), `quantity` (double precision), `unit_price` (double precision), `voucher_id` (varchar), `created_at` (timestamp).

---

## 7. Audit Conclusion

1. **Connectivity Confirmed**: Direct SSL connection to Supabase PostgreSQL 17.11 is verified and stable.
2. **Existing Data Verified**: The database is not blank; it contains 12,152 business rows from historical development testing.
3. **Schema Classification**: The current Supabase schema corresponds to the **pre-V2 development release** (Revision `63b87d829649`).
4. **Transition Requirement**: Before V2 production operation, a controlled, forward-only schema update must be applied to reconcile the legacy 40-table layout with the 26-table V2 architecture without destroying existing audit histories.
