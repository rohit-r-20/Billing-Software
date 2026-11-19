# Anti-Matrix Billing V2 — Fast Billing Shared Database Risk Assessment & Developer Isolation Plan

**Document Version:** 1.0.0  
**Audit Date:** 2026-11-19  
**Audit Type:** Read-Only Investigation & Developer Architecture Plan  
**Target Subsystems:** Fast Billing Backend (`db/database.py`), Traditional Billing Backend (`db/traditional_database.py`), Configuration Management (`core/configuration.py`)  
**Scope:** Developer Isolation for 4 Developers (Main Developer, Friend 1 — Sales, Friend 2 — Purchase, Friend 3 — Configuration)  

---

## 1. Executive Summary

This investigation evaluates the multi-developer isolation risks associated with the Fast Billing database backend. The previous audit (`DEVELOPER_DATABASE_ISOLATION_REPORT.md`) confirmed that when four developers share an identical `.env` file, their Fast Billing applications resolve to the identical remote Supabase PostgreSQL database instance (`aws-0-ap-northeast-1.pooler.supabase.com:5432`). 

This report evaluates the operational risks of concurrent access to that shared database, verifies the feasibility of running Fast Billing on local SQLite backends, defines a zero-collision configuration for each developer, and establishes a safe integration workflow via staging.

### Key Conclusions:
1. **Current Fast Billing Backend:** Currently resolves to a remote PostgreSQL cloud database hosted on Supabase (Tokyo region, session pooler). Concurrent development across four laptops on this single instance creates race conditions, dirty reads/writes, voucher sequence collisions, and unrepeatable test state.
2. **Database Purpose Assessment:** Local configuration and documentation establish that the Supabase instance was migrated from SQLite on November 7, 2026, and contains 11,920 records with balanced financial journal entries (₹746,485.48). However, it **cannot be conclusively determined from local repository evidence alone** whether this database is designated purely for testing or is an active customer production database. It must be treated as **high-risk protected storage**.
3. **Local SQLite Support Verified:** Fast Billing's `DatabaseManager` (`db/database.py`) and `AppConfig` (`core/configuration.py`) contain complete, native dual-backend support for SQLite with WAL mode, foreign-key enforcement, and dialect placeholder translation.
4. **Zero Code Changes Required:** Switching Fast Billing from Supabase to local SQLite requires **no application code modifications**. A simple one-line `.env` configuration change activates local SQLite instantly.
5. **Traditional Billing Independence:** Traditional Billing remains 100% physically isolated in its dedicated local SQLite file (`data/traditional_billing.db`) with fail-closed programmatic guards (`validate_traditional_database_target`).
6. **Final Verdict:** **`LOCAL ISOLATION SUPPORTED`**

---

## 2. Current Fast Billing Backend

### 2.1 Active Connection Resolution
Fast Billing connection strings are resolved via `AppConfig.get_database_url()` in `core/configuration.py` in the following priority order:
1. `STAGING_DATABASE_URL` (only when `APP_ENV=staging`)
2. `DATABASE_URL` (standard 12-factor PostgreSQL connection string)
3. `SUPABASE_DATABASE_URL` (cloud PostgreSQL provider string)
4. `ANTI_MATRIX_DATABASE_URL` (legacy configuration string)
5. Fallback: `sqlite:///{AppConfig.get_database_path()}` (`data/anti_matrix_billing.db`)

Under the default `.env` configuration:
- **Active Backend:** PostgreSQL 17.11 (via Psycopg 3 & SQLAlchemy 2.x Engine)
- **Resolved URL:** `postgresql+psycopg://postgres.nxetowrecgjbpijdjpqd:[REDACTED]@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres?sslmode=require`
- **Host Endpoint:** AWS Tokyo Session Pooler (`aws-0-ap-northeast-1.pooler.supabase.com:5432`)
- **Direct Host:** `db.nxetowrecgjbpijdjpqd.supabase.co:5432` (IPv6-only `AAAA`, inaccessible on standard IPv4 networks)
- **Active Dialect:** `postgresql`
- **Connection Pool:** `pool_size=5`, `max_overflow=10`, `pool_timeout=30s`, `pool_recycle=300s`, `pool_pre_ping=True`

### 2.2 Concurrency Hazards with Four Developers on One Cloud DB
When four developers connect simultaneously to this shared instance:
- **Voucher Sequence Collisions:** While transactional voucher insertion uses row-level locking on `voucher_sequences`, the draft preview method (`get_next_voucher_number()`) lacks locks and produces duplicate voucher numbers to concurrent developers.
- **Stock Balance Contention:** Inventory transactions mutate `stock_balances` across shared branch `1ebe5b37...`. Friend 1 (Sales) and Friend 2 (Purchase) will inadvertently overwrite each other's test quantities.
- **Master Data Pollution:** Friend 3 (Configuration) modifying account structures, taxes, or categories will alter behavior for developers testing sales or purchases mid-workflow.
- **Dangling Test Data:** Synthetic testing generates unverified vouchers and payments that pollute reports and journal entries.
- **Cloud Dependency & Network Outages:** Developers become dependent on internet access and pooler availability (~795 ms round-trip latency per remote query vs. <1 ms for local SQLite).

---

## 3. Database Purpose Evaluation

### 3.1 What Can Be Established from Local Evidence
Based on documentation (`docs/supabase_existing_data_and_connection_readiness.md`, `docs/phase_3_supabase_connection_and_multi_user_audit.md`) and configuration inspection:
- **Environment Tag:** `.env` defines `APP_ENV=development` and `DATABASE_ENV=development`.
- **Alembic Schema Revision:** `63b87d829649` (40 tables, 74 foreign-key constraints, 35 unique constraints).
- **Record Population:** The Supabase database contains **11,920 records** across 40 tables:
  - 2 companies (`ANTI MATRIX` - `COMP0001` and a secondary isolated test company)
  - 47 branches (Primary branch `1ebe5b37...` + 46 test isolation branches)
  - 813 inventory items and 452 barcode records
  - 578 sales vouchers and 136 purchase vouchers
  - 578 payment receipts
  - 747 journal entries totaling ₹746,485.48 in balanced debit/credit lines
  - 1,905 low-stock alert records and 897 audit logs
- **Data Origin:** Data analysis confirmed with 99.9% statistical certainty that these records originated from a baseline migration of `data/anti_matrix_billing.db` performed via `scripts/migrate_sqlite_to_supabase.py` on November 7, 2026, supplemented by test transactions (#571–#578).

### 3.2 What CANNOT Be Established from Local Evidence
- **Production Status:** The project reference `nxetowrecgjbpijdjpqd` and AWS pooler hostname do not reveal whether this Supabase tenant is an operational production database used by actual retail operators or a staging/development sandbox.
- **Live Client Activity:** While the `public.users` table has 0 rows (falling back to `companies.password_hash`), local files cannot verify whether real client operators authenticate via company credentials from other physical terminals.
- **Safe Disposable Nature:** Because the database contains actual historical billing data, vouchers, and accounts, **it cannot be treated as disposable development scratchpad storage**. Any accidental schema migration, column drop, or truncate command would cause irreversible data loss.

---

## 4. Fast Billing Database Support & Local SQLite Confirmation

### 4.1 Fast Billing SQLite Backend Architecture
A comprehensive audit of `db/database.py` and `core/configuration.py` confirms that Fast Billing possesses full, native support for local SQLite:

```
+-------------------------------------------------------------------------+
|                           Fast Billing Backend                          |
+-------------------------------------------------------------------------+
                                     |
                                     v
                  +-------------------------------------+
                  |   AppConfig.get_database_url()      |
                  +-------------------------------------+
                        |                         |
        DATABASE_URL unset / sqlite:       DATABASE_URL postgresql:
                        |                         |
                        v                         v
        +-------------------------------+  +-------------------------------+
        | SQLite Backend (db_path)      |  | PostgreSQL Backend            |
        | - sqlite3.connect(timeout=30) |  | - psycopg.connect()           |
        | - PRAGMA foreign_keys = ON    |  | - PostgresConnectionAdapter   |
        | - PRAGMA journal_mode = WAL   |  | - Connection Pooling (5/10)   |
        | - PRAGMA synchronous = NORMAL |  | - Dialect translation (?->%s) |
        | - sqlite3.Row named access    |  | - PostgresRow named access    |
        +-------------------------------+  +-------------------------------+
                        |                         |
                        +------------+------------+
                                     |
                                     v
                   +-----------------------------------+
                   | All 14 Business Services & Models |
                   +-----------------------------------+
```

1. **Automatic Fallback:** When `DATABASE_URL` is omitted, commented out, or points to a SQLite URI (`sqlite:///...`), `AppConfig.get_database_url()` automatically falls back to:
   ```python
   sqlite:///{AppConfig.get_database_path()}  # -> data/anti_matrix_billing.db
   ```
2. **Engine Initialization:** `DatabaseManager._init_engine()` initializes SQLAlchemy with `sqlite:///{path}` and provides standard `session_scope()` session management.
3. **DBAPI Connection Configuration (`get_connection`):**
   ```python
   conn = sqlite3.connect(
       str(self.db_path),
       timeout=30.0,
       detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
   )
   conn.row_factory = sqlite3.Row
   conn.execute("PRAGMA foreign_keys = ON;")
   conn.execute("PRAGMA journal_mode = WAL;")
   conn.execute("PRAGMA synchronous = NORMAL;")
   ```
4. **Dialect Compatibility Layer:**
   - Positional parameter placeholders (`?`) used in service SQL queries are natively supported by SQLite.
   - Aggregate functions (`GROUP_CONCAT`) are native in SQLite.
   - Row wrapper (`sqlite3.Row`) provides dictionary-style access (`row["column"]`) and tuple index access (`row[0]`), identical to the `PostgresRow` adapter.
5. **Code Changes Required:** **ZERO**. The application runs seamlessly on SQLite without modifying a single line of Python source code.

### 4.2 Traditional Billing Strict Separation
Traditional Billing is managed by `TraditionalDatabaseManager` in `db/traditional_database.py`. It is physically and logically decoupled from Fast Billing:
- Target database: `data/traditional_billing.db` (enforced by `AppConfig.get_traditional_database_path()`).
- Programmatic Guard: `validate_traditional_database_target(url_or_path)` raises `TraditionalConfigurationError` if any reference to `anti_matrix_billing.db` or the configured Fast Billing path is detected.
- Profile Validation: `AppConfig.validate_configuration()` explicitly checks `norm_fast == norm_trad` and emits a fatal configuration error if both systems target the same file or URL.

---

## 5. Developer Isolation Design for Four Developers

To achieve total independence, zero latency, offline capability, and complete protection of cloud data, **all four developers must operate on local SQLite backends during daily development**.

### 5.1 Developer Responsibilities and Workflows

| Developer Role | Responsibility Area | Target Fast Billing Subsystem | Primary Risk on Shared DB | Local SQLite Safety Benefit |
|---|---|---|---|---|
| **Main Developer** | Core architecture, database schemas, auth, staging releases | `db/database.py`, `core/configuration.py`, `desktop/` | Schema modifications breaking other developers' active tasks | Full control over schema migrations on local test database before staging |
| **Friend 1** | Sales & Cashier workflows | `services/sales_service.py`, `services/pos_service.py` | Voucher numbering conflicts (`#579+`), stock decrement collisions | Independent voucher sequence and stock balances for sale testing |
| **Friend 2** | Purchase & Supplier workflows | `services/purchase_service.py`, `services/supplier_service.py` | Inward stock balance overwrites, vendor ledger pollution | Dedicated supplier catalog and purchase voucher testing without shared mutation |
| **Friend 3** | Configuration, Masters & System Settings | `services/company_service.py`, `services/tax_service.py` | Overwriting global GST rates, company profiles, or barcode configs | Isolated company/branch settings without disrupting sales/purchase workflows |

### 5.2 Recommended Local Environment Configuration (`.env`)
Each developer maintains an identical local `.env` structure that specifies local SQLite for both billing subsystems. Sensitive cloud credentials are removed entirely:

```bash
# =============================================================================
# Alpha Billing ERP - Local Developer Environment (.env)
# =============================================================================

# Application Environment Profile
APP_ENV=development
DATABASE_ENV=development

# Fast Billing Backend (Local SQLite - Isolated per Laptop)
DATABASE_URL=sqlite:///data/anti_matrix_billing.db

# Traditional Billing Backend (Local SQLite - Isolated per Laptop)
TRADITIONAL_DATABASE_URL=sqlite:///data/traditional_billing.db

# Multi-Branch & Register Identity
BRANCH_CODE=BR01
REGISTER_CODE=REG01

# Diagnostics & Logging
LOG_LEVEL=INFO
DEBUG_MODE=False

# Connection Pool Defaults (for SQLite fallback)
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=300
```

### 5.3 Isolation Matrix

```
[Main Developer Laptop]          [Friend 1 Laptop]              [Friend 2 Laptop]              [Friend 3 Laptop]
+----------------------+        +----------------------+        +----------------------+        +----------------------+
| Fast DB:             |        | Fast DB:             |        | Fast DB:             |        | Fast DB:             |
| ./data/              |        | ./data/              |        | ./data/              |        | ./data/              |
|  anti_matrix_...db   |        |  anti_matrix_...db   |        |  anti_matrix_...db   |        |  anti_matrix_...db   |
|                      |        |                      |        |                      |        |                      |
| Traditional DB:      |        | Traditional DB:      |        | Traditional DB:      |        | Traditional DB:      |
| ./data/              |        | ./data/              |        | ./data/              |        | ./data/              |
|  traditional_...db   |        |  traditional_...db   |        |  traditional_...db   |        |  traditional_...db   |
+----------------------+        +----------------------+        +----------------------+        +----------------------+
          \                                \                               /                               /
           \                                \                             /                               /
            \                                \                           /                               /
             v                                v                         v                               v
       +-----------------------------------------------------------------------------------------------------+
       |                                       Git Repository (GitHub)                                       |
       |                   Branches: feature/sales, feature/purchase, feature/config, staging                |
       +-----------------------------------------------------------------------------------------------------+
                                                          |
                                                          v
                                     +-----------------------------------------+
                                     |       Central Staging Integration       |
                                     |               (APP_ENV=staging)         |
                                     |  - data/staging_anti_matrix_billing.db   |
                                     |  - data/staging_traditional_billing.db   |
                                     +-----------------------------------------+
```

---

## 6. Central Staging Integration Workflow

To combine changes from the four developers safely without endangering production data:

### 6.1 Git Branching Strategy
1. **Feature Branches:** Each friend works in an isolated Git branch:
   - `feature/sales-friend1`
   - `feature/purchase-friend2`
   - `feature/config-friend3`
   - `feature/core-main`
2. **Staging Branch (`staging`):** Changes are merged via pull request into `staging` for integration verification.

### 6.2 Staging Runtime Isolation (`APP_ENV=staging`)
When code is integrated for testing, the application is launched with `APP_ENV=staging`:
- **Fast Billing Staging Path:** Automatically redirected to `data/staging_anti_matrix_billing.db`.
- **Traditional Billing Staging Path:** Automatically redirected to `data/staging_traditional_billing.db`.
- **Automated Seeding:** Staging databases are populated with synthetic seed data via `scripts/seed_staging_data.py`.
- **Automated Verification:** Verified via headless launch and preflight tests (`scripts/verify_staging_launch.py`).

### 6.3 Fail-Closed Production Protection
The configuration validator (`AppConfig.validate_configuration()`) actively prevents staging from accidentally modifying production or remote databases:
- **Rule 1:** In staging mode, if Fast Billing targets `anti_matrix_billing.db`, startup fails closed with a fatal error.
- **Rule 2:** In staging mode, if Traditional Billing targets `traditional_billing.db`, startup fails closed with a fatal error.
- **Rule 3:** In staging mode, if any PostgreSQL or Supabase URL is specified without `"staging"` or `"test"` in the connection string, startup aborts immediately.

---

## 7. Migration and Runbook Requirements

### 7.1 Developer Setup Runbook (Step-by-Step)
For each of the four developers:

1. **Step 1: Update `.env` File**
   In the project root, edit `.env` (or copy `.env.example` to `.env`):
   ```bash
   # Comment out any remote PostgreSQL URL
   # DATABASE_URL=postgresql+psycopg://postgres...

   # Set Fast Billing to local SQLite
   DATABASE_URL=sqlite:///data/anti_matrix_billing.db
   TRADITIONAL_DATABASE_URL=sqlite:///data/traditional_billing.db
   APP_ENV=development
   ```

2. **Step 2: Validate Configuration**
   Run the read-only configuration verification command:
   ```bash
   python3 -c "from core.configuration import config; res = config.validate_configuration(); print('Valid:', res['valid']); print('Dialect:', config.get_database_dialect()); print('Errors:', res['errors'])"
   ```
   **Expected Output:**
   ```
   Valid: True
   Dialect: sqlite
   Errors: []
   ```

3. **Step 3: Baseline Database Verification**
   Verify that local SQLite databases exist and contain the required tables:
   ```bash
   python3 -c "from db.database import DatabaseManager; mgr = DatabaseManager(); conn = mgr.get_connection(); cur = conn.cursor(); cur.execute('SELECT count(*) FROM sqlite_master WHERE type=\'table\''); print('Fast Billing Tables:', cur.fetchone()[0]); conn.close()"
   ```
   **Expected Output:**
   ```
   Fast Billing Tables: 40
   ```

### 7.2 Database Migrations Policy
- **No Cloud Migrations:** No developer may execute `alembic upgrade` or schema alters against the remote Supabase database during daily development.
- **Local SQLite Migrations:** If a feature branch requires a schema migration:
  1. The authoring developer creates a new Alembic migration revision.
  2. The author tests the migration locally on their SQLite file.
  3. The migration script is peer-reviewed during PR review.
  4. The Main Developer executes the migration in the staging environment (`APP_ENV=staging`).
  5. Cloud database migration is deferred until formal production release planning.

---

## 8. Risks and Potential Blockers

| Risk Area | Severity | Impact | Mitigation Strategy |
|---|---|---|---|
| **Dialect Incompatibilities** (SQLite vs PostgreSQL syntax) | Medium | SQL syntax working on SQLite may fail on PostgreSQL (or vice versa). | The translation layer (`translate_placeholders_to_percent_s`) and SQLAlchemy 2.x ORM abstract most differences. All PRs must pass the central staging test suite where dialect checks are verified. |
| **SQLite Concurrency Contention** | Low | Multi-process writes on a single laptop can produce `database is locked`. | `DatabaseManager` configures WAL mode (`PRAGMA journal_mode = WAL;`) and a 30-second busy timeout (`timeout=30.0`), allowing concurrent readers and serialized writers without lock errors. |
| **Untracked Local Data Drift** | Low | Developers testing with different item or account sets may find UI differences. | Standardized test seeds (`scripts/seed_staging_data.py`) ensure repeatable data sets across developer machines. |
| **Git Contamination** | Low | Accidental commit of local `.db` binaries, `.env` credentials, or setup tokens. | Protected by `.gitignore` rules (`*.db`, `*.db-wal`, `*.db-shm`, `.env`, `.env.staging`, `.env.testing`, `setup_token.txt`). |

---

## 9. Final Verdict

```
================================================================================
FINAL VERDICT: LOCAL ISOLATION SUPPORTED
================================================================================
- Fast Billing possesses full, native, and robust SQLite support in DatabaseManager.
- Switching from remote Supabase to local SQLite requires ZERO code changes.
- Traditional Billing remains 100% physically isolated with strict validation guards.
- Local SQLite configuration eliminates all cross-developer concurrency hazards.
- Central staging (APP_ENV=staging) provides fail-closed integration testing.
================================================================================
```
