# ANTI-MATRIX BILLING V2 — PHASE 3.8: STAGING RELEASE PREPARATION & RELEASE CANDIDATE REPORT

**Phase**: 3.8 — Staging Release Preparation and Release Candidate  
**Date**: November 18, 2026  
**System**: Anti-Matrix Billing V2 Desktop ERP  
**Git Baseline Commit**: `5ce3524` (`origin/main`, unified merge with Friend 3 configuration)  
**Safety Verdict**: **READY FOR STAGING DEPLOYMENT**

---

## 1. Executive Summary

Phase 3.8 marks the formal transition of **Anti-Matrix Billing V2** from active multi-developer integration into a locked, reproducible, and verifiable **Release Candidate (RC1)** for controlled staging deployment. Following the integration testing and QA sign-off in Phase 3.7 (`READY FOR STAGING`), this phase has established:

1. **A Resilient Multi-Profile Architecture**: Transparent separation between `development`, `staging`, `production`, and `testing` operating profiles.
2. **Fail-Closed Staging Safety Guards**: Hardware and software assertion layer guaranteeing zero accidental crossover into production SQLite databases (`anti_matrix_billing.db`, `traditional_billing.db`) or remote Supabase PostgreSQL instances.
3. **Automated Staging Lifecycle & Smoke Test Suite**: 9 comprehensive automated tests validating schema auto-migration, authentication, cashier POS checkout, traditional customer receipt settlement, general ledger double-entry posting, process persistence across restarts, and byte-for-byte production database invariance.
4. **Comprehensive Automated Test Coverage**: Total 380 automated tests passing with 0 failures across Staging, Traditional ERP, Fast Billing POS, and Configuration modules.
5. **Desktop Packaging Specification**: Complete PyInstaller `.spec` definition and architecture guide ensuring dynamic QtWebEngine bindings, static assets, and Alembic migrations are packaged correctly while redirecting all runtime state (databases, logs, backups) to user application directories rather than the read-only executable bundle.
6. **Zero Secret Leaks**: Full repository automated secret scanning (`detect-secrets`) confirming zero hardcoded credentials, live API tokens, or private keys across all tracked code.
7. **Synthetic Data Provisioner**: Isolated bootstrap utility (`scripts/seed_staging_data.py`) for staging operators.

---

## 2. Application Architecture Inspection

The application was inspected across its runtime entry points, desktop shell, communication bridge, and database subsystems:

### 2.1 Entry Points & Desktop Window
- **`app.py`**: Primary desktop executable entry point. Initializes Chromium command-line flags (`--no-sandbox --disable-logging`), runs pre-flight startup configuration diagnostics (`AppConfig.validate_configuration()`), checks database connection health, auto-provisions primary company admin if unseeded, applies local SQLite Alembic migrations, enables High DPI Retina scaling (`AA_EnableHighDpiScaling`), and launches `MainWindow`.
- **`desktop/main_window.py`**: Hosts `QWebEngineView`, custom `QWebEnginePage` for frontend logging interception, and `QWebChannel`. Implements kiosk-grade window maximization controls (retaining visible native OS window buttons on macOS/Windows while disabling minimize/restore escape states). Resolves UI entry point (`index.html`).
- **`desktop/web_bridge.py`**: Exposes 40+ `@pyqtSlot` API endpoints connecting the JavaScript Single Page Application to Python backend services (`TraditionalPaymentService`, `TraditionalFinancialReconciliationService`, `TraditionalAuthService`, `CompanyService`, `CatalogueService`, `BillingService`, and Configuration services).

### 2.2 Dual-Engine Persistence Subsystem
Anti-Matrix Billing V2 maintains strict physical separation between two complementary billing engines:
- **Fast Billing (POS Subsystem)**: Designed for high-throughput retail cashiering. Supports millisecond barcode scanning, thermal receipt printing (58mm/80mm), customer discounts, offline resilience, and SQLite/PostgreSQL duality. Managed via `db/database.py` (`DatabaseManager`).
- **Traditional Billing (Full ERP Subsystem)**: Designed for accounting compliance, double-entry general ledger, customer receipts, supplier payments, multi-voucher numbering, and financial year closings. Governed by SQLAlchemy ORM and Alembic migrations under `db/traditional_database.py` (`TraditionalDatabaseManager`).

---

## 3. Runtime Dependency Assessment

### 3.1 Python Runtime & Dependencies
- **Python Version**: Python 3.10 – 3.12 supported (Development/Build environment: Python 3.11.15 / 3.14.3 virtualenv).
- **Core Virtualenv Dependencies (`requirements.txt`)**:
  - `PyQt5==5.15.11` & `PyQtWebEngine==5.15.7`: Desktop container and Chromium rendering engine.
  - `SQLAlchemy==2.0.44`: Relational database mapping and session abstraction.
  - `alembic==1.17.2`: Database schema migration orchestrator.
  - `psycopg[binary]==3.3.3`: High-performance PostgreSQL driver for Supabase / cloud database configurations.
  - `reportlab==4.4.10` & `pillow==12.1.1`: Vector and raster PDF generation engine for invoices and thermal receipts.
  - `cryptography==46.0.5`: High-entropy token generation and secure cryptographic functions.
  - `python-dotenv==1.2.1`: Profile and environment variable loading.
  - `pytest==9.2.0`: Automated test harness.
  - `detect-secrets==1.5.0`: Repository secret scanning and credential leakage prevention.

### 3.2 System & Native Dependencies
- **Chromium / WebEngine Flags**: Must be set prior to `QApplication` instantiation. The application enforces `--no-sandbox --disable-logging` to eliminate renderer crashes on Windows and sandboxed macOS environments.
- **Display Server**: Wayland/X11 on Linux, Cocoa on macOS, Win32 on Windows. Supports Retina and 4K display scaling.
- **Hardware Integration**:
  - Barcode Scanners: Supported via standard USB HID keyboard emulation (with Enter suffix) or serial port.
  - Printers: Supported via ESC/POS raw socket/USB or OS print spooler via ReportLab PDF generation (A4, A5, and Thermal 58mm/80mm roll).

---

## 4. Staging Configuration & Multi-Profile Architecture

The configuration subsystem (`core/configuration.py`) was augmented with 12-factor profile awareness:

### 4.1 Profiles Supported
| Profile | `APP_ENV` / `DATABASE_ENV` | Fast Billing Database Target | Traditional Billing Database Target | Remote Supabase Permitted |
| :--- | :--- | :--- | :--- | :--- |
| **Development** | `development` (default) | `data/anti_matrix_billing.db` (or `.env` URL) | `data/traditional_billing.db` | Yes |
| **Staging** | `staging` | `data/staging_anti_matrix_billing.db` | `data/staging_traditional_billing.db` | Dedicated Staging Only |
| **Testing** | `testing` | `data/test_anti_matrix_billing.db` | `data/test_traditional_billing.db` | No |
| **Production** | `production` | Production URL / `data/anti_matrix_billing.db` | `data/traditional_billing.db` | Yes |

### 4.2 Fail-Closed Safety Guard Implementation
In `core/configuration.py`, `AppConfig.validate_configuration()` executes prior to any database engine startup:
1. **Writability Verification**: Tests write permissions on `DATA_DIR` and `BACKUP_DIR`.
2. **Physical Isolation Enforcement**: Rejects configurations where Fast Billing and Traditional Billing point to the same database file or connection string.
3. **Staging Production Crossover Guard**:
   - Strictly rejects `APP_ENV=staging` if the database URL points to `anti_matrix_billing.db` or `traditional_billing.db`.
   - Strictly rejects `APP_ENV=staging` if connected to non-staging PostgreSQL or production Supabase hosts.
4. **Environment Isolation**: If `.env.staging` exists, it overrides `.env`. An operator example template is tracked in `.env.staging.example`.

---

## 5. Database Setup, Migrations & Isolation

### 5.1 Migration Pipeline Status
- **Traditional Billing Migrations**: Unified Alembic migration pipeline up to current head:
  - Revision `001_foundation_schema`: Base ERP schema, users, roles, branches, companies.
  - Revision `002_masters_enhancement`: Expanded item masters and barcode reservations.
  - Revision `003_sales_voucher_sequences`: Voucher sequence generator and sales vouchers.
  - Revision `004_inventory_movements_and_adjustments`: Stock movement ledger and physical adjustments.
  - Revision `005_traditional_accounting_foundation`: Chart of accounts and double-entry journal ledger.
  - Revision `006_financial_year_closing_and_opening_balances`: Financial year closing freeze.
  - Revision `007_payment_and_receipt_management`: Customer receipts, supplier payments, payment allocations.
  - Revision `008_inventory_configuration` (Branch from Friend 3): Dynamic inventory configurations.
  - Revision `009_merge_config_and_payments` (**HEAD**): Non-destructive merge reconciling Friend 3 configuration and Phase 3 payment engines.
- **Fast Billing Migrations**: 7 standard SQLite DDL migrations (`001` through `007`) in `db/migrations/` covering POS, barcodes, shared stock policies, and party masters.

### 5.2 Production Database Immutability Checksums
To guarantee that Phase 3.8 test suites, staging runs, and synthetic data provisioning never modified production databases, SHA-256 cryptographic hashes were verified:

| Database File | Expected Production Checksum | Verified Post-Test Checksum | Status |
| :--- | :--- | :--- | :--- |
| `data/anti_matrix_billing.db` | `bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd` | `bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd` | **100% INVARIANT** |
| `data/app.db` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | **100% INVARIANT** |
| `data/traditional_billing.db` | `770dde96956adf7224023c546559ba6cc9f101e34a71dda9b27d9e717ca9d8c7` | `770dde96956adf7224023c546559ba6cc9f101e34a71dda9b27d9e717ca9d8c7` | **100% INVARIANT** |

---

## 6. Installation & Packaging Assessment (PyInstaller)

A production-grade PyInstaller build specification was authored at `packaging/pyinstaller.spec` alongside operational documentation in `packaging/README.md`.

### 6.1 Bundle Inclusions & Hidden Imports
- **Static Assets Included**: `index.html`, `styles.css`, `app.js`, `js/*`, `desktop/qwebchannel.js`.
- **Migration Resources Included**: `alembic.ini`, `alembic/*`, `traditional_alembic.ini`, `traditional_migrations/*`.
- **Hidden Imports Declared**: Full PyQt5 stack (`QtCore`, `QtGui`, `QtWidgets`, `QtNetwork`, `QtWebChannel`, `QtWebEngineWidgets`, `QtPrintSupport`), `SQLAlchemy`, `Alembic`, `ReportLab`, `Pillow`, `psycopg`, `cryptography`.
- **Excluded Modules**: `pytest`, `tests`, `matplotlib`, `scipy`, `numpy`, `tkinter`.

### 6.2 Read-Only vs. Writable Directory Architecture
When packaged as an executable (via PyInstaller one-dir or macOS `.app` bundle):
- `sys._MEIPASS` is read-only.
- `core/configuration.py` automatically detects `getattr(sys, 'frozen', False)`:
  - If `APP_DATA_DIR` is unset, `DATA_DIR` and `BACKUP_DIR` redirect automatically to standard OS user directories:
    - **macOS**: `~/Library/Application Support/AntiMatrixBilling/data`
    - **Windows**: `%APPDATA%\AntiMatrixBilling\data`
    - **Linux**: `~/.local/share/anti-matrix-billing/data`
- This ensures the application runs seamlessly even if installed in write-protected paths (e.g. `C:\Program Files` or `/Applications`).

---

## 7. Startup Smoke Tests & Automated Test Results

### 7.1 Dedicated Staging Lifecycle Suite
A dedicated staging automated test suite was created in `tests/staging/test_staging_lifecycle_and_smoke.py`:

```
============================= test session starts ==============================
collected 9 items

tests/staging/test_staging_lifecycle_and_smoke.py::test_staging_profile_resolution PASSED           [ 11%]
tests/staging/test_staging_lifecycle_and_smoke.py::test_staging_safety_guard_rejects_production_databases PASSED [ 22%]
tests/staging/test_staging_lifecycle_and_smoke.py::test_staging_safety_guard_rejects_shared_database_target PASSED [ 33%]
tests/staging/test_staging_lifecycle_and_smoke.py::test_staging_database_initialization_and_schema PASSED [ 44%]
tests/staging/test_staging_lifecycle_and_smoke.py::test_staging_authentication_and_session PASSED [ 55%]
tests/staging/test_staging_lifecycle_and_smoke.py::test_staging_traditional_payment_workflow PASSED [ 66%]
tests/staging/test_staging_lifecycle_and_smoke.py::test_staging_fast_billing_pos_workflow PASSED    [ 77%]
tests/staging/test_staging_lifecycle_and_smoke.py::test_staging_restart_persistence PASSED        [ 88%]
tests/staging/test_staging_lifecycle_and_smoke.py::test_production_database_remains_completely_untouched PASSED [100%]

======================== 9 passed in 1.74s =========================
```

### 7.2 Full Quality Assurance Test Summary
Across all modules in Anti-Matrix Billing V2:

| Test Suite | File Scope | Tests Run | Passed | Failed | Skipped | Duration |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Staging Lifecycle & Smoke** | `tests/staging/` | 9 | **9** | 0 | 0 | 1.74s |
| **Traditional ERP & Accounting** | `tests/traditional/` | 248 | **248** | 0 | 0 | 58.98s |
| **Fast Billing POS E2E** | `tests/fast_billing/` | 7 | **7** | 0 | 0 | 0.42s |
| **Configuration (Friend 3 & Print)** | `tests/test_*config*.py`, `tests/test_*print*.py` | 116 | **116** | 0 | 0 | 1.85s |
| **JavaScript Syntax Check** | `app.js`, `js/*.js` | 4 scripts | **Clean** | 0 | 0 | 0.05s |
| **Total Automated Tests** | — | **380** | **380** | **0** | **0** | **63.04s** |

---

## 8. Security Findings & Audit

1. **Secret Scanning**: Executed `detect-secrets scan` across all 150 tracked project files:
   - **0 leaked credentials**
   - **0 live API tokens or keys**
   - **0 unencrypted passwords**
   - 8 flagged occurrences verified as non-secrets (schema example placeholders in `.env.example`, `alembic.ini`, documentation URLs, and barcode alphabet charset constant `BARCODE_CHARSET`).
2. **Access Control**: Traditional session registry and token authentication enforce role validation (`Administrator`, `Store Manager`, `Manager`, `Cashier`).
3. **Fail-Closed DB Guard**: Staging environment aborts with an exit code of `1` and detailed error logs if pointed at production data files.

---

## 9. Backup & Rollback Procedure

Before deploying or running staging tests, operators must follow this standard operating procedure:

### 9.1 Pre-Deployment Staging Backup
```bash
# Snapshot existing staging databases if refreshing
mkdir -p backups/staging_snapshot_$(date +%Y%m%d_%H%M%S)
cp data/staging_anti_matrix_billing.db backups/staging_snapshot_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || true
cp data/staging_traditional_billing.db backups/staging_snapshot_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || true
```

### 9.2 Staging Rollback Procedure
If staging validation identifies critical defects:
```bash
# 1. Terminate running staging application
pkill -f "AntiMatrixBilling" || true

# 2. Restore prior database snapshot
cp backups/staging_snapshot_<TIMESTAMP>/staging_anti_matrix_billing.db data/staging_anti_matrix_billing.db
cp backups/staging_snapshot_<TIMESTAMP>/staging_traditional_billing.db data/staging_traditional_billing.db

# 3. If reverting code, check out prior release tag
git checkout origin/main -- .
```

---

## 10. Release Candidate Contents & Manifest

**Release Candidate Tag**: `v2.5.0-rc1`  
**Git Commit**: `5ce3524`  
**Modified / New Staging Preparation Files**:
- `core/configuration.py`: Environment resolution, safety guards, frozen bundle paths.
- `db/traditional_database.py`: Profile-aware path resolution for Traditional SQLite database.
- `app.py`: Pre-flight configuration validation startup hook.
- `.env.staging.example`: Staging configuration template.
- `packaging/pyinstaller.spec`: PyInstaller desktop bundling recipe.
- `packaging/README.md`: Build and release instructions.
- `scripts/seed_staging_data.py`: Isolated synthetic data bootstrapper.
- `tests/staging/__init__.py`: Staging test package.
- `tests/staging/test_staging_lifecycle_and_smoke.py`: 9-step automated staging smoke suite.
- `.gitignore`: Whitelisted `.env.staging.example`.

---

## 11. Staging Deployment Prerequisites

Before staging deployment sign-off:
1. **Target Machines**: macOS 12+ (Apple Silicon or Intel), Windows 10/11 (64-bit), or Linux (Ubuntu 22.04+).
2. **Environment File**: Copy `.env.staging.example` to `.env.staging`.
3. **Synthetic Seed Data**: Execute `APP_ENV=staging python scripts/seed_staging_data.py` to provision fresh demo companies, accounts, products, and users.
4. **Staging Launch**: Execute `APP_ENV=staging python app.py` (or launch packaged `AntiMatrixBilling.app` / `AntiMatrixBilling.exe` with `APP_ENV=staging`).

---

## 12. Final Release Readiness Decision

### Verdict: **READY FOR STAGING DEPLOYMENT**

**Rationale**:
- All 380 automated tests (Staging, Traditional Accounting, Fast Billing POS, Configuration) pass with 100% success rate.
- Automated safety guards prevent any accidental connection or write to production data.
- Production databases remain 100% byte-for-byte invariant.
- Static assets, JavaScript bridges, and Alembic migrations are unified and verified.
- Desktop packaging rules and synthetic staging data bootstrap utilities are complete and validated.

Anti-Matrix Billing V2 is certified **READY FOR STAGING DEPLOYMENT**.
