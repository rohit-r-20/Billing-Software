# Alpha Billing V2 — Schema Implementation Gap Report

## 1. Executive Summary

This report performs a comprehensive structural delta analysis between the approved **Alpha Billing V2 Architecture** (documented in `docs/corrected_v2_postgresql_schema.md`) and the current state of both the **SQLAlchemy models** (`db/models.py`) and the **live Supabase database**.

The approved V2 architecture consolidates the enterprise data model into **26 focused tables** strictly tailored to single-company, single-location retail and wholesale billing, eliminating unnecessary multi-branch overhead while introducing essential accounting features (WAC inventory costing, historical COGS snapshots, and separate supplier payment tracking).

---

## 2. Table Count & Scope Comparison Matrix

| System Component | Table Count | Scope Focus |
|---|---|---|
| **Corrected V2 Specification** | **26 Tables** | Strictly single-company, single-location, unified parties, WAC inventory, exact decimals. |
| **Current `db/models.py`** | **39 Tables** | Legacy multi-branch, multi-godown, separated suppliers, double-entry journals, float types. |
| **Current Live Supabase DB** | **40 Tables** | Legacy schema (matches `models.py` + `alembic_version` tracking table). |

---

## 3. Structural Gap Analysis by Business Domain

### 1. Company & Branch Scope
- **V2 Specification**: Exactly **One Company** (`companies`) and **One Stock Location** (`stock_balances` referencing a single canonical store). Tables `branches`, `godowns`, `registers`, `stock_transfers`, and `stock_transfer_items` are removed from the V2 core.
- **Current Models & Supabase**: Contains `branches` (with 47 legacy rows in Supabase), `godowns`, `registers`, and inter-branch transfer tables.
- **Gap Status**: **Legacy Overkill**. 5 multi-location tables must be deprecated or simplified into a single-location model.

---

### 2. Unified Parties (Customers & Suppliers)
- **V2 Specification**: All business parties reside in a single unified `accounts` table with a `party_type` discriminator (`'CUSTOMER'`, `'SUPPLIER'`, `'BOTH'`), unified tax IDs (`gstin`, `pan`), and consolidated ledger balances.
- **Current Models & Supabase**: Two separate tables exist: `accounts` (385 rows) for customers, and `suppliers` (91 rows) for vendors.
- **Gap Status**: **Architectural Separation**. Needs forward-only unification to eliminate redundant duplicate master records.

---

### 3. Category & Unit Masters
- **V2 Specification**: Dedicated relational tables `product_categories` and `product_units` with foreign keys from `items` to prevent typos, ensure standardized UOMs, and facilitate reporting.
- **Current Models & Supabase**: Categories and units are stored as free-form strings (`category = VARCHAR(100)`, `unit = VARCHAR(50)`) inside the `items` table.
- **Gap Status**: **Missing V2 Tables**. `product_categories` and `product_units` are not yet created in `db/models.py` or Supabase.

---

### 4. Sales Invoices & Historical COGS Tracking
- **V2 Specification**: `sales_voucher_items` includes `cost_price_at_sale` (`NUMERIC(15, 4)`). When an item is sold, the exact Weighted Average Cost (WAC) at that instant is snapshotted, enabling 100% accurate historical gross margin and Cost of Goods Sold (COGS) reporting even if purchase prices change later.
- **Current Models & Supabase**: `sales_voucher_items` only records `price`, `qty`, `tax_rate`, and `tax_amount`. It does not store purchase cost at the time of sale.
- **Gap Status**: **Missing Critical Accounting Metric**. Column `cost_price_at_sale` is absent.

---

### 5. Purchase Invoices & Separate Supplier Payments
- **V2 Specification**:
  - Purchase invoices (`purchase_vouchers`) record incoming stock and vendor tax liability.
  - Supplier payments are tracked in a dedicated `purchase_payments` table and allocated across invoices via `supplier_allocations`.
- **Current Models & Supabase**:
  - Only a single `payments` table exists, which holds customer receipt records for sales vouchers (`voucher_id` foreign key referencing `sales_vouchers.id`).
  - There is no dedicated table for recording partial or batched vendor payments against purchase vouchers.
- **Gap Status**: **Missing V2 Tables**. `purchase_payments` and `supplier_allocations` do not exist.

---

### 6. Inventory Valuation & Stock Ledger (WAC)
- **V2 Specification**: `stock_movements` table records:
  - `historical_cost` (`NUMERIC(15, 4)`): Exact unit acquisition cost.
  - `running_qty` (`NUMERIC(15, 3)`): Cumulative stock balance after movement.
  - `running_valuation` (`NUMERIC(15, 2)`): Total inventory asset value after movement.
- **Current Models & Supabase**: `stock_movements` records only `quantity`, `unit_price`, and `movement_type` without running balance or running valuation columns.
- **Gap Status**: **Missing Valuation Columns**. WAC tracking requires adding running balance and valuation columns.

---

### 7. Backup & Restore System Tracking
- **V2 Specification**: `system_backups` table tracks backup timestamp, file size, checksum, and target location.
- **Current Models & Supabase**: Backup operations create filesystem files without a persistent database audit registry table.
- **Gap Status**: **Missing V2 Table**. `system_backups` is absent.

---

### 8. Data Types & Precision Discrepancies

| Field Category | Current Implementation (`models.py` & Supabase) | Corrected V2 Specification | Impact / Risk |
|---|---|---|---|
| Monetary / Financial | `Float` (`double precision`) | `NUMERIC(15, 2)` | Floating-point rounding errors in retail invoices. |
| Quantities | `Float` (`double precision`) | `NUMERIC(15, 3)` | Precision issues in weighed commodities (e.g. 0.250 kg). |
| Dates | `String(20)` (`VARCHAR(20)`) | `DATE` | Inability to use SQL date functions and chronological index sorting. |
| Timestamps | `DateTime` (No TZ) | `TIMESTAMPTZ` | Timestamp ambiguity across daylight saving / timezone changes. |
| Booleans | `Integer` (`0` or `1`) | `BOOLEAN` (`true` or `false`) | Non-standard boolean SQL queries and type cast errors. |

---

## 4. Comprehensive Inventory of Missing and Extraneous Tables

### Tables in Corrected V2 Specification but MISSING from Models and Supabase (5 Tables):
1. `purchase_payments` (Vendor outgoing payments tracking)
2. `supplier_allocations` (Invoice-to-payment allocation junction)
3. `product_categories` (Master category hierarchy)
4. `product_units` (Master unit of measurement catalog)
5. `system_backups` (Backup audit and verification log)

### Tables in Current Models and Supabase that are EXTRANEOUS to V2 Scope (18 Tables):
1. `branches` (47 rows - multi-branch distribution)
2. `godowns` (0 rows - multi-warehouse tracking)
3. `registers` (1 row - cash register hardware mapping)
4. `stock_transfers` & `stock_transfer_items` (Inter-branch logistics)
5. `stock_adjustments` & `stock_adjustment_items` (Merged into direct stock audit in V2)
6. `stock_batches` (Lot/batch expiry tracking - deferred to V3)
7. `item_branch_stock_configs` (Multi-branch reorder settings)
8. `suppliers` (Merged into unified `accounts` in V2)
9. `journal_entries` & `journal_entry_lines` (General double-entry accounting - deferred to V3)
10. `payments` (Replaced by clean sales payment receipts and separate `purchase_payments`)
11. `low_stock_alerts` (Handled via view/query on `stock_balances` in V2)
12. `customer_category_discounts` & `daily_discount_configs` (Simplified into pricing rules)
13. `ocr_invoice_drafts` (Staging table)
14. `unit_conversions` (Deferred to V3)

---

## 5. Implementation Roadmap Recommendation

To transition safely to the Corrected V2 Architecture:
1. **Preserve Current Supabase Test Snapshot**: Do not run destructive `DROP TABLE` or `RESET` commands.
2. **Update `db/models.py`**: Align ORM class definitions with the 26-table V2 specification (migrating `Float` to `Numeric`, `String(20)` to `Date`, and adding missing tables).
3. **Generate Forward-Only Alembic Migration**: Create a dedicated Alembic revision (e.g. `reconcile_to_v2_clean_architecture`) that creates the 5 missing tables and adds missing accounting columns (`cost_price_at_sale`, `historical_cost`, `running_valuation`).
4. **Update Service Layer Queries**: Adjust queries that currently reference `suppliers` or `WHERE is_active = 1` to target the unified `accounts` table and native boolean syntax.
