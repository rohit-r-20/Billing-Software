# Alpha Billing V2 — Alembic Migration Review & Pre-Flight Assessment

## 1. Overview & Single Versioning Mechanism

Alpha Billing V2 establishes **Alembic** as the sole, authoritative database schema versioning tool. Schema management is completely decoupled from application startup:
- Migrations are version-controlled in the repository under `alembic/versions/`.
- Schema upgrades are applied through deterministic CLI commands (`alembic upgrade head`).
- Desktop application launch (`app.py`) never issues destructive DDL or schema upgrades automatically.

---

## 2. Current Migration Repository Audit

The repository contains 4 linear, version-controlled revisions:

| Revision ID | Down Revision | Description | Schema Impact |
|---|---|---|---|
| **`c2e29c4427bb`** | *None (Base)* | `initial_complete_schema` | Core tables (`companies`, `branches`, `accounts`, `items`, `sales_vouchers`, `stock_balances`, etc.). |
| **`20d0e084fa62`** | `c2e29c4427bb` | `add_ocr_invoice_drafts` | Added `ocr_invoice_drafts` staging table for purchase OCR. |
| **`bec935e29b50`** | `20d0e084fa62` | `align_all_columns_with_erp_schema` | Aligned missing columns (`gross_subtotal`, `discount_total`, `customer_category`, `reference_no`). |
| **`63b87d829649`** | `bec935e29b50` | `add_barcode_sequences_table` | Added atomic sequence table for unique internal Code 128 barcode generation. |

- Current Alembic Head: **`63b87d829649`**
- Migration Branching: **Zero branches (100% linear history)**

---

## 3. Target Supabase Database Pre-Flight Inspection

Before proposing or generating any schema changes, a read-only inspection of the active Supabase PostgreSQL database was conducted:

### Inspection Findings:
1. **Database Objects Status**:
   - The Supabase database is **NOT empty**.
   - It contains **40 tables** in the `public` schema.
   - The `alembic_version` table is present and stamped at **`63b87d829649`**.
2. **Existing Data Rows in Supabase**:
   - `accounts`: 385 rows
   - `items`: 813 rows
   - `item_barcodes`: 452 rows
   - `sales_vouchers`: 578 rows
   - `purchase_vouchers`: 136 rows
   - `stock_balances`: 842 rows
   - `stock_movements`: 825 rows
   - `audit_logs`: 897 rows
3. **Implication**:
   - The Supabase database contains active development and testing records from earlier integration cycles.
   - **Destructive operations (`DROP TABLE`, `TRUNCATE`, database resets) must NOT be executed.**
   - Any new migration to align with the Corrected V2 Schema must be applied as an incremental, non-destructive upgrade.

---

## 4. Schema Delta: Existing Alembic Schema vs Approved V2 Scope

| Feature / Table | Current Alembic Schema (`63b87d829649`) | Approved V2 Schema Specification | Migration Action |
|---|---|---|---|
| **Party Masters** | Separate `accounts` and `suppliers` tables | Unified `accounts` table with `party_type` (`CUSTOMER`, `SUPPLIER`, `BOTH`) | Provide `suppliers_v2` compatibility view; add `party_type` column. |
| **COGS Snapshot** | Not captured at line level | `sales_voucher_items.cogs_unit_cost` & `cogs_total` | Add nullable columns to `sales_voucher_items`. |
| **WAC Valuation** | Item cost tracked simply as `purc_price` | `items.valuation_method` & `items.cost_price` | Add `valuation_method VARCHAR(20) DEFAULT 'WAC'`. |
| **Purchase Allocations** | Payments stored in legacy `payments` table | Separate `purchase_payments` and `supplier_allocations` | Introduce dedicated tables without dropping existing records. |
| **Backup Registry** | Manual backup files | `system_backups` metadata table | Introduce `system_backups` table. |
| **Multi-Branch Tables** | `godowns`, `stock_transfers` present | Out of strict V2 Scope | Leave tables dormant; do not drop to avoid breaking existing references. |

---

## 5. Migration Execution Policy

1. **No Startup DDL**: Migrations are completely absent from `app.py`.
2. **Confirmation Gate**: In accordance with Phase Five rules, no DDL modifications have been applied to Supabase in this turn.
3. **Zero SQLite Migration**: No historical SQLite records will be copied into Supabase during this connection and architecture configuration phase.
