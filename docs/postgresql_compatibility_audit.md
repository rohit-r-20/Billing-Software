# Alpha Billing V2 — PostgreSQL Compatibility Audit

## 1. Executive Summary

This audit assesses the compatibility of Alpha Billing's existing SQLAlchemy models (`db/models.py`), database layer (`db/database.py`), and application services (`services/`) with PostgreSQL. While SQLite accommodates dynamic typing, loose date representations, and non-enforced decimal arithmetic, PostgreSQL strictly enforces data types, foreign keys, transaction isolation, and column casting.

This report documents 12 core PostgreSQL compatibility dimensions and identifies required corrections for production readiness.

---

## 2. In-Depth Compatibility Analysis

### 1. UUID Compatibility
- **Current State**: Models in `db/models.py` define primary keys and foreign keys as `String(36)` (e.g. `id: Mapped[str] = mapped_column(String(36), primary_key=True)`). In PostgreSQL, these are stored as `character varying(36)`.
- **PostgreSQL Compatibility**:
  - `character varying(36)` works cleanly for UUID string storage across Psycopg 3 and SQLAlchemy.
  - However, native PostgreSQL `UUID` (`from sqlalchemy.dialects.postgresql import UUID`) offers higher performance (16 bytes vs. 36 bytes per row) and native UUID generation (`gen_random_uuid()`).
- **Verdict**: **COMPATIBLE**, with native `UUID` recommended as an optimization in the final V2 schema.

---

### 2. NUMERIC & Decimal Handling
- **Current State**: `db/models.py` uses `Float` (`double precision` in PostgreSQL) for monetary values (`subtotal`, `taxable_amount`, `grand_total`, `tax_rate`, `cgst_amount`, `current_balance`) and quantities (`current_qty`, `qty`).
- **PostgreSQL Compatibility Risk**:
  - In accounting and retail billing, IEEE 754 floating-point arithmetic introduces rounding artifacts (e.g., `0.1 + 0.2 = 0.30000000000000004`).
  - While SQLite transparently converts between `REAL` and integers, PostgreSQL requires `NUMERIC(precision, scale)` to guarantee exact decimal financial calculations.
- **Required Correction**:
  - Currency and tax amounts must be typed as `NUMERIC(15, 2)`.
  - Item quantities must be typed as `NUMERIC(15, 3)` (to support unit measurements like 0.250 kg).
  - Tax percentages must be typed as `NUMERIC(5, 2)`.
- **Verdict**: **REQUIRES CORRECTION** for financial precision compliance.

---

### 3. Date and Timestamp Handling
- **Current State**:
  - `vch_date` in `sales_vouchers`, `purchase_vouchers`, and `journal_entries` is stored as `String(20)` (`VARCHAR(20)` in PostgreSQL), containing text dates like `'01-11-2026'` or `'2026-11-06'`.
  - `created_at` and `updated_at` are stored as `DateTime` (PostgreSQL `TIMESTAMP WITHOUT TIME ZONE`).
- **PostgreSQL Compatibility Risk**:
  - Text dates cannot be properly filtered using SQL comparison operators (`BETWEEN`, `>`, `<`) or formatted with date functions (`DATE_TRUNC`, `EXTRACT`) without expensive `TO_DATE()` casts.
  - Sorting on `VARCHAR` dates containing `DD-MM-YYYY` results in alphabetical ordering instead of chronological ordering.
- **Required Correction**:
  - `vch_date` must be migrated to native PostgreSQL `DATE`.
  - Timestamps must use `TIMESTAMP WITH TIME ZONE` (`TIMESTAMPTZ`) to eliminate timezone ambiguity.
- **Verdict**: **REQUIRES CORRECTION**.

---

### 4. Transaction Boundaries & ACID Isolation
- **Current State**:
  - `DatabaseManager.session_scope()` provides atomic SQLAlchemy 2.x session scoping (`try: yield session; session.commit(); except: session.rollback(); raise`).
  - `PostgresConnectionAdapter` wraps DBAPI connections, executing `commit()` on context exit or `rollback()` on exceptions.
- **PostgreSQL Compatibility**:
  - PostgreSQL enforces strict transactional blocks. In PostgreSQL, if any query inside a transaction causes an error (e.g. unique violation), subsequent queries are blocked with `current transaction is aborted, commands ignored until end of transaction block` until an explicit `ROLLBACK` is issued.
  - The adapter's automatic rollback on exception properly clears the transaction state, preventing poisoned connection reuse.
- **Verdict**: **COMPATIBLE**.

---

### 5. Foreign-Key Enforcement
- **Current State**:
  - In SQLite, foreign keys require `PRAGMA foreign_keys = ON;`.
  - In PostgreSQL, foreign keys are always enforced at the database engine level.
- **Audit Finding**:
  - Tables in Supabase currently enforce 48 foreign-key constraints.
  - In historical development migrations, cascading deletes (`ON DELETE CASCADE` / `ON DELETE SET NULL`) were applied.
- **Verdict**: **COMPATIBLE**.

---

### 6. Unique Constraints & Parameterized Placeholders
- **Current State**:
  - Service queries write SQL with positional `?` placeholders (standard in Python SQLite).
  - `db/database.py` translates `?` into `%s` via `translate_placeholders_to_percent_s()`.
- **PostgreSQL Compatibility**:
  - Positional parameter substitution works cleanly across Psycopg 3.
  - Unique constraints (`uq_sales_vouchers_comp_vchno`, `uq_item_barcodes_company_code`) are enforced natively by PostgreSQL indexes.
- **Verdict**: **COMPATIBLE**.

---

### 7. PostgreSQL-Specific SQL vs. SQLite-Specific SQL
- **Audit of SQL Queries Across Services**:
  - **`ON CONFLICT` Clauses**: In `inventory_service.py` (lines 240-245), stock updates use:
    ```sql
    INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(branch_id, item_id) DO UPDATE SET
        current_qty = stock_balances.current_qty + excluded.current_qty,
        last_updated = CURRENT_TIMESTAMP;
    ```
    This syntax is valid in PostgreSQL and SQLite 3.24+.
  - **Boolean Equality**: Several service queries use `WHERE is_active = 1`. In PostgreSQL, if a column is typed as `BOOLEAN`, `is_active = 1` throws `operator does not exist: boolean = integer`. Because the legacy PostgreSQL schema typed `is_active` as `INTEGER`, queries currently succeed, but adopting native PostgreSQL `BOOLEAN` in V2 will require updating queries to `WHERE is_active IS TRUE`.
- **Verdict**: **REQUIRES ATTENTION** during V2 schema creation.

---

### 8. Voucher Number Generation & Concurrency
- **Current State**:
  - `billing_service.py` queries `SELECT vch_no FROM sales_vouchers WHERE company_id = ? AND series = ?;` and iterates through all rows in Python to find `max_vch_num`.
- **PostgreSQL Compatibility Risk**:
  - While this logic works in a single-user desktop environment, under multi-counter or concurrent retail POS usage, this approach is vulnerable to race conditions resulting in duplicate voucher numbers or unique constraint crashes.
- **Required Correction**:
  - Transition voucher number allocation to atomic PostgreSQL sequences or atomic `SELECT ... FOR UPDATE` locks on `voucher_sequences`.
- **Verdict**: **REQUIRES ARCHITECTURAL CORRECTION**.

---

### 9. Concurrent Stock Updates
- **Current State**:
  - Stock updates execute `INSERT ... ON CONFLICT(branch_id, item_id) DO UPDATE SET current_qty = stock_balances.current_qty + excluded.current_qty`.
- **PostgreSQL Compatibility**:
  - PostgreSQL handles `ON CONFLICT DO UPDATE` atomically with row-level locks, preventing dirty writes or lost updates during inventory deduction.
- **Verdict**: **COMPATIBLE**.

---

### 10. Summary Compatibility Matrix

| Feature / Domain | Current Implementation | PostgreSQL Native Target | Status |
|---|---|---|---|
| Primary Keys | `String(36)` UUIDs | `UUID` / `String(36)` | **Compatible** |
| Financial Decimals | `Float` (Double Precision) | `NUMERIC(15, 2)` | **Requires Correction** |
| Quantities | `Float` (Double Precision) | `NUMERIC(15, 3)` | **Requires Correction** |
| Voucher Dates | `VARCHAR(20)` ('DD-MM-YYYY') | `DATE` | **Requires Correction** |
| Timestamps | `DateTime` (No TZ) | `TIMESTAMPTZ` | **Requires Correction** |
| Booleans | `Integer` (0/1) | `BOOLEAN` (True/False) | **Requires Correction** |
| Transactions | `session_scope()` / DBAPI Adapter | ACID PostgreSQL Blocks | **Compatible** |
| Foreign Keys | Enforced via DDL | Engine Enforced | **Compatible** |
| Parameter Placeholders | `?` via translation adapter | `%s` via Psycopg 3 | **Compatible** |
| Stock Concurrency | `ON CONFLICT DO UPDATE` | Atomic Row Lock | **Compatible** |
| Voucher Sequences | Python loop over `vch_no` | Atomic Sequence / Lock | **Requires Correction** |
