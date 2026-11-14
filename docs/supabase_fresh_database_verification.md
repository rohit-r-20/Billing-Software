# Supabase PostgreSQL Database & Configuration Verification Report

**Date & Time:** 2026-11-09T16:15:00+05:30  
**Phase:** Phase 2A — Supabase Fresh Database Verification  
**Environment:** macOS (Apple Silicon aarch64), Python 3.11 (.venv), PostgreSQL 17.11  
**Project ID / Reference:** `nxetowrecgjbpijdjpqd`  
**Security Standard:** Strict credential redacting enforced (zero passwords, keys, or raw secrets exposed).

---

## 1. Executive Summary

A comprehensive read-only audit of the Alpha Billing database configuration and the live Supabase project was conducted without modifying `.env`, applying schema changes, running migrations, or executing database write operations.

Key discoveries:
1. **Active Configuration Points to Localhost, Not Supabase:** The active `.env` file defines `DATABASE_URL` pointing to a local PostgreSQL 17.11 instance (`localhost:5432/alpha_billing_dev`). The Supabase connection string is present on line 10 but is **commented out** (`# SUPABASE_DATABASE_URL=...`).
2. **Supabase Direct Host Has No IPv4 Routing:** Direct connection to `db.nxetowrecgjbpijdjpqd.supabase.co:5432` fails with `[Errno 8] nodename nor servname provided, or not known`. This occurs because Supabase direct endpoints only publish IPv6 `AAAA` DNS records (`2406:da14:18fe:3100::2c0c`), which cannot be resolved on client networks without active IPv6 DNS/routing.
3. **Live Supabase Database Verified via Pooler:** The Supabase project is hosted in AWS region **`ap-northeast-1` (Tokyo)**. Successful read-only connection was established via the Supabase Session Pooler (`aws-0-ap-northeast-1.pooler.supabase.com:5432`) using `sslmode=require`.
4. **Supabase Is NOT an Empty Database:** In contrast to the initial assumption of an unmigrated database, the live Supabase `public` schema already contains **40 application tables** stamped at Alembic revision **`63b87d829649`**, with existing business records in companies, branches, items, accounts, barcodes, vouchers, and journal entries.
5. **Authentication Gap Identified:** Although the `public.users` table exists in Supabase with the required schema, it currently contains **0 rows**. Multi-user login (`Admin`, `Manager`, `Cashier`) will fail until user records are created or seeded.

---

## 2. Configuration Inspection

Five configuration and startup files were inspected:

### A. `.env`
- **Active Variable:** `DATABASE_URL` is set to `postgresql+psycopg://dhvira@localhost:5432/alpha_billing_dev`.
- **Target:** Points to a **local** PostgreSQL database on `localhost:5432`. It does **not** point to Supabase.
- **Commented Supabase Variable:** Line 10 contains `# SUPABASE_DATABASE_URL=postgresql+psycopg://postgres:***@db.nxetowrecgjbpijdjpqd.supabase.co:5432/postgres`.
- **Real vs Placeholder:** Both strings are real, valid connection strings (no placeholder tokens like `<password>` or `your-project`).
- **Driver:** Uses `postgresql+psycopg` (SQLAlchemy 2.x dialect for Psycopg 3).
- **SSL Parameter:** Neither `.env` URL includes `?sslmode=require` in its query parameters.
- **Other Settings:** `APP_ENV=development`, `APP_LOG_LEVEL=INFO`.

### B. `.env.example`
- Documents Option A (Supabase Session Pooler and Direct), Option B (Self-Managed Production), Option C (Local PostgreSQL), and Option D (SQLite fallback).
- Explicitly provides pooler format: `postgresql+psycopg://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres?sslmode=require`.
- Correctly recommends conservative pooling parameters: `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=10`, `DB_POOL_TIMEOUT=30`, `DB_POOL_RECYCLE=300`.

### C. `core/configuration.py`
- Resolution order in `AppConfig.get_database_url()`:
  1. `DATABASE_URL` (highest priority)
  2. `SUPABASE_DATABASE_URL`
  3. `ANTI_MATRIX_DATABASE_URL` (legacy)
  4. Local SQLite file fallback: `sqlite:///data/anti_matrix_billing.db`
- **Impact:** Because `DATABASE_URL` is currently defined and uncommented, the application binds exclusively to `localhost:5432` and completely ignores `SUPABASE_DATABASE_URL`.
- Provides `mask_database_url()` which strips credentials for safe logging and diagnostics.

### D. `db/database.py`
- Initialises SQLAlchemy 2.x engine via `create_engine()` with connection pooling.
- Dialect translation: `translate_placeholders_to_percent_s()` converts SQLite `?` to PostgreSQL `%s`, handles `GROUP_CONCAT` -> `STRING_AGG`, and escapes `%` literals.
- Connection adapters: `PostgresConnectionAdapter` and `PostgresCursorAdapter` wrap native Psycopg 3 connections with `PostgresRow` dictionary row emulation.
- **Diagnostic Finding:** In `DatabaseManager.check_health()`, unpacking `db_name, schema_name = cursor.fetchone()` on `SELECT current_database(), current_schema()` unpacks the dictionary keys `('current_database', 'current_schema')` instead of dictionary values because `PostgresRow` inherits from `dict`. This is a non-breaking diagnostic cosmetic display issue.

### E. `app.py`
- Startup sequence executes `db_manager.check_health()` on line 46 before opening `MainWindow`.
- Does not run automatic DDL migrations on startup (migrations are safely decoupled).

---

## 3. Database Connectivity & Inspection Results

### 3.1 Local PostgreSQL Database (`localhost:5432/alpha_billing_dev`)
- **Connection:** Successful (via UNIX domain socket / loopback).
- **Version:** `PostgreSQL 17.11 (Homebrew) on aarch64-apple-darwin25.6.0`
- **Latency:** ~10.6 ms
- **Public Tables:** 40 tables present, stamped at Alembic revision `63b87d829649`.

### 3.2 Supabase Direct Endpoint (`db.nxetowrecgjbpijdjpqd.supabase.co:5432`)
- **Connection:** **Failed**
- **Error Category:** `psycopg.OperationalError`
- **Error Message:** `failed to resolve host 'db.nxetowrecgjbpijdjpqd.supabase.co': [Errno 8] nodename nor servname provided, or not known`
- **Root Cause Analysis:**
  - Standard `dig @8.8.8.8 db.nxetowrecgjbpijdjpqd.supabase.co A` returns `0` answers (`NOERROR`, empty answer).
  - `dig @8.8.8.8 db.nxetowrecgjbpijdjpqd.supabase.co AAAA` returns IPv6 address `2406:da14:18fe:3100::2c0c`.
  - Supabase has deprecated direct IPv4 routing for managed databases. Clients without dual-stack IPv6 network routing cannot connect to the direct hostname.

### 3.3 Supabase Session Pooler (`aws-0-ap-northeast-1.pooler.supabase.com:5432`)
- **Connection:** **SUCCESSFUL**
- **Pooler Host:** `aws-0-ap-northeast-1.pooler.supabase.com` (Port 5432)
- **Resolved IPv4 Addresses:** `52.68.3.1`, `54.64.190.72` (Tokyo, Japan)
- **Authentication User:** `postgres.nxetowrecgjbpijdjpqd`
- **SSL Required:** `sslmode=require` (Connection rejected if SSL is omitted)
- **Version:** `PostgreSQL 17.11 on aarch64-unknown-linux-gnu, compiled by gcc (GCC) 15.2.0, 64-bit`
- **Current Database:** `postgres`
- **Current Schema:** `public`
- **Network Round-Trip Latency:** ~142 ms

---

## 4. Live Supabase PostgreSQL Schema & Table Inventory

The live Supabase database contains **12 schemas** and **84 non-system tables**:

### Schemas Present
`auth`, `extensions`, `graphql`, `graphql_public`, `information_schema`, `pg_catalog`, `pg_toast`, `pgbouncer`, `public`, `realtime`, `storage`, `vault`.

### Tables in `public` Schema & Row Counts (40 Total)

| Table Name | Row Count | Category | Notes |
|:---|:---:|:---|:---|
| `accounts` | 385 | Financial Master | Chart of accounts |
| `alembic_version` | 1 | Migrations | Stamped at `63b87d829649` |
| `audit_logs` | 897 | System Audit | Historical audit trail |
| `barcode_sequences` | 1 | Barcode System | Internal sequence tracking |
| `branches` | 47 | Master Data | Operational branches and stores |
| `companies` | 2 | Master Data | `COMP0001` (ANTI MATRIX), `COMP_ISO_2` |
| `company_configs` | 1 | System Config | Company-level operational parameters |
| `customer_category_discounts` | 6 | Pricing Master | Customer pricing tiers |
| `daily_discount_configs` | 0 | Pricing Master | Empty |
| `godowns` | 0 | Inventory Master | Secondary godowns |
| `item_barcodes` | 452 | Master Data | EAN/UPC and internal barcodes |
| `item_branch_stock_configs` | 15 | Inventory Master | Branch-specific stock policies |
| `items` | 813 | Master Data | Product catalog |
| `journal_entries` | 747 | Financial Ledger | Double-entry journals |
| `journal_entry_lines` | 3,040 | Financial Ledger | Journal distribution lines |
| `low_stock_alerts` | 1,905 | Alerts System | Reorder alerts |
| `ocr_invoice_drafts` | 2 | Procurement | Purchase invoice OCR scans |
| `payments` | 578 | Financial Transactions | Vouchers and receipts |
| `purchase_return_items` | 0 | Procurement | Empty |
| `purchase_returns` | 0 | Procurement | Empty |
| `purchase_voucher_items` | 136 | Procurement | Line items |
| `purchase_vouchers` | 136 | Procurement | Vendor bills |
| `registers` | 1 | POS Hardware | POS billing register |
| `roles` | 0 | Access Control | **Empty** |
| `sales_return_items` | 36 | Retail Sales | Credit notes items |
| `sales_returns` | 36 | Retail Sales | Credit notes |
| `sales_voucher_items` | 579 | Retail Sales | Line items |
| `sales_vouchers` | 578 | Retail Sales | Tax invoices |
| `stock_adjustment_items` | 0 | Inventory Movements | Empty |
| `stock_adjustments` | 0 | Inventory Movements | Empty |
| `stock_balances` | 842 | Inventory Balances | Real-time on-hand quantities |
| `stock_batches` | 0 | Inventory Batches | Batch tracking |
| `stock_movements` | 825 | Inventory Movements | Stock movement audit ledger |
| `stock_transfer_items` | 0 | Inventory Transfers | Empty |
| `stock_transfers` | 0 | Inventory Transfers | Empty |
| `suppliers` | 91 | Master Data | Vendor parties |
| `unit_conversions` | 0 | Master Data | UOM conversions |
| `user_permissions` | 0 | Access Control | **Empty** |
| `users` | 0 | Access Control | **Empty (Critical Authentication Finding)** |
| `voucher_sequences` | 0 | Numbering Engine | Invoice numbering sequences |

---

## 5. Review of Modified Application Files

The seven files modified during the paused Phase 3 workstream were verified:

1. **[`services/company_service.py`](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/services/company_service.py):**
   - Implements two-stage authentication:
     - Stage 1: Looks up the user in `users` table:
       `SELECT ... FROM users u WHERE u.company_id = ? AND UPPER(u.username) = ? AND (u.is_active = 1 OR u.is_active IS NULL);`
     - Stage 2: Fallback to `companies` table if the username matches `companies.username` or if authenticating against company admin credentials.
   - **Schema Compatibility:** The `users` table in Supabase contains columns:
     `id`, `company_id`, `username`, `email`, `password_hash`, `full_name`, `role_id`, `role_name`, `is_active`, `created_at`, `updated_at`.
     All columns queried by `company_service.py` **exist** in the Supabase schema.
   - **Dependency Status:** No missing tables or missing columns. However, because `users` has 0 rows, Stage 1 will return no rows; login will fall back to Stage 2 (`companies` table).
   - In `companies`, `COMP0001` has `username = 'A'` and an existing `password_hash`. `COMP_ISO_2` has `password_hash = NULL`.

2. **[`js/business_context.js`](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/js/business_context.js):**
   - Correctly initializes with `isAuthenticated = false`, `currentUser = null`, `activeCompanyId = null`, `activeBranchId = null`.
   - Disabled automatic company auto-selection on startup.
   - Dispatches `"auth-changed"` event to notify header and navigation managers.

3. **[`index.html`](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/index.html):**
   - `#alpha-top-header` and `#alpha-sidebar` initial styles set to `display: none;`.
   - Hardcoded company, branch, user initials, and admin titles removed from initial HTML markup.

4. **[`core/configuration.py`](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/core/configuration.py):**
   - Supports portable database environment detection (`DATABASE_ENV`), connection pooling options, and URL credential masking.

5. **[`db/database.py`](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/db/database.py):**
   - Supports centralized engine and session factory with query placeholder translation and transactional scope handling.
   - Added backward-compatible aliases `run_migrations()` and `restore_database()`.

6. **[`app.py`](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/app.py):**
   - Decoupled from startup DDL migrations; executes non-destructive `check_health()` on launch.

7. **[`.env.example`](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/.env.example):**
   - Cleanly documents pooler and direct connection strings.

---

## 6. Gaps & Missing Requirements

| Area | Current State | Requirement | Impact |
|:---|:---|:---|:---|
| **Active Target** | `DATABASE_URL` targets `localhost:5432/alpha_billing_dev` | Must target Supabase Session Pooler | App currently communicates with local Mac PostgreSQL, not Supabase |
| **Network Protocol** | `.env` commented URL uses direct host `db.nxetowrecgjbpijdjpqd.supabase.co` | Must use Pooler `aws-0-ap-northeast-1.pooler.supabase.com` | Direct host fails DNS resolution on IPv4 networks |
| **SSL Flag** | No SSL query parameter in `.env` | Must include `?sslmode=require` | Supabase connection refused without SSL |
| **User Records** | `public.users` has 0 rows | At least 1 active user record per company in `users` | Specific user login (`Admin`, `Manager`, `Cashier`) will fail until a user is seeded |
| **UI Lifecycle** | Startup redirect in `app.js` line 10297 calls `showScreen("view-dashboard")` | Must call `showScreen("view-login")` and guard views | Frontend will open dashboard if not intercepted |

---

## 7. Recommended Next Steps (When Authorized)

1. **Update `.env` (When permitted by user):**
   Replace the local `DATABASE_URL` with the verified Supabase Session Pooler connection string:
   ```env
   DATABASE_URL=postgresql+psycopg://postgres.nxetowrecgjbpijdjpqd:[PASSWORD]@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres?sslmode=require
   ```
2. **Seed Initial Admin User (Non-destructive):**
   Insert an initial active administrator record into `public.users` for company `COMP0001` (`id: 3a743bcd-8f9a-4154-a316-509cba3de99a`) with a securely hashed password (Argon2id / PBKDF2-SHA256) so that multi-user authentication is testable against PostgreSQL.
3. **Complete Workstream A Frontend Controls:**
   - In `app.js`: Change startup screen from `view-dashboard` to `view-login`, add route protection in `showScreen()`, and bind `logoutUser()` to `BusinessContext.clearAuthenticatedSession()`.
   - In `js/header.js`: Toggle `#alpha-top-header` visibility based on `"auth-changed"` event and render authenticated user profile dynamically.
   - In `js/navigation.js`: Wire sidebar logout button and action route guards.
4. **Execute Verification Test Suite:**
   Run the 20 PostgreSQL integration tests against isolated test records in Supabase.
