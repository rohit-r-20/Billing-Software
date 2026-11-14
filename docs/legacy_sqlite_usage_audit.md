# Alpha Billing V2 — Legacy SQLite Usage Audit

## 1. Executive Summary

This document audits every database access point, SQLite reference, database connection, and query pattern across the entire Alpha Billing repository. Each occurrence is catalogued and categorized according to its functional role in the system.

### Classification Categories:
- **Category A**: Historical SQLite migration tooling (Preserved for safe data transition).
- **Category B**: Test-only SQLite usage (Isolated unit tests and mock fixtures).
- **Category C**: Active production / application database usage (Must target PostgreSQL).
- **Category D**: Unused legacy code (Obsolete scripts or dead code paths).
- **Category E**: Unknown — Requires further investigation.

---

## 2. Inventory and Classification of Database Access

### A. Direct `sqlite3.connect` Occurrences

| File Path | Line(s) | Category | Description & Purpose |
|---|---|---|---|
| `scripts/migrate_sqlite_to_supabase.py` | 75, 105 | **A** | **Historical SQLite Migration Tooling**: Reads historical data in read-only mode (`?mode=ro`) to extract vouchers, items, and accounts for PostgreSQL migration. |
| `services/database_migration_service.py` | 179, 184 | **A** | **Historical SQLite Migration Tooling**: Safe migration service orchestrating chunked batch reads from SQLite source tables. |
| `db/database.py` | 329, 439 | **C / A** | **Central Database Abstraction**: Line 329 initializes local SQLite connection *only* when `is_sqlite` is True. Line 439 executes online backup via SQLite native backup API when in SQLite mode. |
| `tests/test_database_abstraction_and_connection.py` | 161 | **B** | **Test-Only**: Verifies that the historical SQLite database file remained 100% untouched (`PRAGMA integrity_check`). |
| `tests/test_postgresql_and_supabase_config.py` | 635, 651 | **B** | **Test-Only**: Verifies data integrity check and read-only mode behavior on SQLite file. |

---

### B. `sqlite:///` URL References

| File Path | Line(s) | Category | Description & Purpose |
|---|---|---|---|
| `core/configuration.py` | 88, 115 | **C** | **Configuration Fallback**: Default SQLite URL returned only when no `DATABASE_URL` or `SUPABASE_DATABASE_URL` is defined in `.env`. Line 115 checks `is_sqlite()`. |
| `db/database.py` | 234 | **C** | **Database Manager**: Strips `sqlite:///` prefix to extract filesystem path when configured for SQLite. |
| `tests/test_postgresql_and_supabase_config.py` | 110, 667 | **B** | **Test-Only**: Tests default configuration resolution and SQLite URL formatting. |

---

### C. SQLAlchemy Engine & Sessionmaker Creation

| File Path | Line(s) | Category | Description & Purpose |
|---|---|---|---|
| `db/database.py` | 272, 281 | **C** | **Active Database Layer**: Central factory for SQLAlchemy 2.x `create_engine()` with connection pooling (`QueuePool`). |
| `db/database.py` | 282 | **C** | **Active Database Layer**: Central `sessionmaker(bind=self._engine, expire_on_commit=False)` factory. |
| `alembic/env.py` | 54 | **C** | **Database Migration Engine**: Alembic migration runner initializing offline/online engine. |

---

### D. Service Layer Database Access (`self.db.get_connection()`)

The application service layer does not call `sqlite3.connect` directly. Instead, domain services rely on `self.db.get_connection()`:

| Service File | Lines with DB Access | Category | Target Dialect & Active Routing |
|---|---|---|---|
| `services/account_service.py` | 19, 39, 95, 173, 335, 358 | **C** | When `is_postgres` is True, routes queries to PostgreSQL `accounts` table via `PostgresConnectionAdapter`. |
| `services/supplier_service.py` | 18, 33, 56, 68, 80, 128, 207, 228 | **C** | Routes queries to PostgreSQL `suppliers` table via `PostgresConnectionAdapter`. |
| `services/catalogue_service.py` | 19, 25, 62, 128, 183, 233, 275, 393, 611, 652, 668 | **C** | Routes queries to PostgreSQL `items` and `item_barcodes` tables. |
| `services/inventory_service.py` | 20, 32, 45, 85, 189, 236, 297, 389, 471, 629, 734, 957, 1015 | **C** | Routes queries to PostgreSQL `stock_balances` and `stock_movements`. Uses PostgreSQL `ON CONFLICT DO UPDATE`. |
| `services/billing_service.py` | 23, 29, 60, 141, 180, 559, 639, 1034, 1177, 1189, 1213, 1249, 1286, 1317, 1408, 1417 | **C** | Routes sales vouchers, invoice items, and payment receipts to PostgreSQL. |
| `services/purchase_service.py` | 29, 41, 54, 86, 158, 183, 221, 305, 502, 517, 555, 895, 937 | **C** | Routes inward purchase vouchers and supplier invoices to PostgreSQL. |
| `services/company_service.py` | 18, 31, 94, 133, 152, 182 | **C** | Routes company configs and branch details to PostgreSQL. |
| `services/barcode_service.py` | 34, 66, 301, 407 | **C** | Routes internal barcode generation and sequences. Has offline SQLite helper for standalone tests. |
| `services/accounting_service.py` | 18, 32, 75, 142 | **C** | Routes double-entry journal entries and general ledger lines. |
| `services/reporting_service.py` | 17, 35, 48, 77 | **C** | Queries financial and sales summaries across PostgreSQL tables. |

---

### E. Unused / Legacy Code & One-Off Scripts

| File Path | Category | Status & Action |
|---|---|---|
| `add_odonil_product.py` | **D** | One-off product insertion script created during earlier UI testing. Should be archived or moved to `scripts/scratch/`. |
| `core/export_import_cli.py` | **D** | Legacy CSV export/import utility from pre-V2 architecture. Retained for historical utility. |
| `services/demo_product_service.py` | **D** | Seeds demo retail products into the active database. Harmless development helper. |

---

## 3. Active Business Operations: Does Anything Still Write to SQLite?

A critical requirement of Phase 2 is to determine:
> **Whether any active customer, supplier, item, sales, or purchase functionality still writes to SQLite when configured for PostgreSQL.**

### Finding: NO Active Business Service Writes to SQLite in PostgreSQL Mode.

#### Verification Details:
1. When `DATABASE_URL` in `.env` targets PostgreSQL (Supabase or self-managed):
   - `AppConfig.is_postgres()` returns `True`.
   - `DatabaseManager.is_postgres` is initialized to `True`.
   - `db_manager.get_connection()` returns `PostgresConnectionAdapter` backed by `psycopg.connect()`.
   - All write operations (`INSERT INTO accounts`, `INSERT INTO sales_vouchers`, `INSERT INTO items`, `INSERT INTO stock_balances`) execute against the remote PostgreSQL database.
2. In `services/barcode_service.py`:
   - A helper method `_ensure_sequence_table_sqlite()` exists, but is guarded by `if self.db.is_sqlite:`. In PostgreSQL mode, this branch is entirely bypassed.
3. In `services/billing_service.py`:
   - `_ensure_sequence_table()` creates the `voucher_sequences` table if missing on both dialects.
4. **Conclusion**: When PostgreSQL is configured, SQLite writes are 100% disabled across all core business domains. SQLite is accessed only by the historical migration orchestrator in read-only mode (`?mode=ro`).
