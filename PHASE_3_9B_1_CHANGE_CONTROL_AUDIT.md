# Phase 3.9B.1 — Staging Launch Change-Control Audit Report

**Document**: `PHASE_3_9B_1_CHANGE_CONTROL_AUDIT.md`  
**Timestamp**: 2026-11-18T23:38:30+05:30  
**Audit Type**: Read-Only Change-Control and Safety Audit  
**Scope**: All source, configuration, script, test, and document files modified or created during Phase 3.9B and preceding staging preparation  
**Target Environment**: Isolated Staging (`APP_ENV=staging`, `DATABASE_ENV=staging`)  
**Operating System**: macOS (Darwin 25.6.0 arm64) | Python 3.11.15 / 3.14.3  

---

## 1. Executive Summary

A comprehensive read-only change-control audit was performed across the complete working tree of Anti-Matrix Billing V2 following the successful completion of Phase 3.9B.

- **Production Databases**: 100% byte-invariant; SHA-256 checksums match authoritative baseline with zero mutations.
- **Production Configuration & Business Logic**: Zero production configuration (`.env`), zero Friend-owned modules (Sales, Purchase, Configuration), and zero financial/accounting/inventory business logic files were altered.
- **Staging Safety Guards**: Verified that `scripts/seed_staging_data.py` and `scripts/verify_staging_launch.py` strictly enforce `APP_ENV=staging`, validate database path naming, and cannot target production databases.
- **BR01 Branch Adjustment**: Verified that the alignment of the default branch code in staging from `'MAIN'` to `'BR01'` is strictly scoped to the disposable staging SQLite database (`data/staging_anti_matrix_billing.db`) and its seed script, bringing it into exact conformance with `desktop/web_bridge.py` line 304 and production database conventions.
- **Secrets & Credentials**: Zero plaintext passwords, secret keys, or authentication tokens are exposed in logs, reports, or tracked code.
- **Pre-existing Work**: All uncommitted changes from Phases 3.8 and 3.9 are 100% preserved.

---

## 2. Production Database Invariance Audit

The SHA-256 checksums of all three production database files were verified against the recorded baselines:

| Database File | Baseline SHA-256 | Current SHA-256 | Audit Status |
|---|---|---|:---:|
| `data/anti_matrix_billing.db` | `bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd` | `bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd` | **PASS (0 bytes changed)** |
| `data/app.db` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | **PASS (0 bytes changed)** |
| `data/traditional_billing.db` | `770dde96956adf7224023c546559ba6cc9f101e34a71dda9b27d9e717ca9d8c7` | `770dde96956adf7224023c546559ba6cc9f101e34a71dda9b27d9e717ca9d8c7` | **PASS (0 bytes changed)** |

---

## 3. Detailed Audit of Tracked Modified Files

### A. `.gitignore`
* **Git Status**: Modified (`Changes not staged for commit`)
* **Exact Purpose of Changes**:
  - Adds un-ignore rule for `.env.staging.example` so the reference staging template can be tracked.
  - Adds ignore rules for `build/`, `dist/`, and `*.spec.bak` to prevent tracking compiled PyInstaller binaries and build artifacts.
* **Exact Diff**:
```diff
diff --git a/.gitignore b/.gitignore
index 300dc5f..d2e88ea 100644
--- a/.gitignore
+++ b/.gitignore
@@ -40,6 +40,7 @@ scratch/
 # Environment secrets
 .env.*
 !.env.example
+!.env.staging.example
 
 # Python testing and tooling
 .pytest_cache/
@@ -48,4 +49,9 @@ scratch/
 
 # IDE
 .vscode/
-.idea/
\ No newline at end of file
+.idea/
+
+# Packaging builds
+build/
+dist/
+*.spec.bak
```
* **Necessity**: **Necessary**. Prevents multi-hundred-megabyte binary artifacts from polluting Git history and allows staging environment templates.
* **Risk Assessment**: **Low / Zero Risk**. Affects only Git tracking; does not alter runtime behavior.
* **Recommendation**: **KEEP**.

---

### B. `app.py`
* **Git Status**: Modified (`Changes not staged for commit`)
* **Exact Purpose of Changes**:
  - Restricts the Chromium sandbox bypass (`--no-sandbox`) so that standard desktop execution preserves the native Chromium sandbox. Bypass is only activated if `QTWEBENGINE_DISABLE_SANDBOX=1` is explicitly set in unprivileged container environments.
  - Adds Step 0 startup configuration validation (`cfg_diag = config.validate_configuration()`). If misconfigured or if pointing staging to production databases, logs errors and exits immediately with code 1 (`sys.exit(1)`).
* **Exact Diff**:
```diff
diff --git a/app.py b/app.py
index 37e2d08..43c2ea0 100755
--- a/app.py
+++ b/app.py
@@ -16,11 +16,16 @@ if _venv_python.exists() and sys.executable != str(_venv_python):
     except ImportError:
         os.execv(str(_venv_python), [str(_venv_python)] + sys.argv)
 
-# Set Chromium command-line flags BEFORE PyQt5/QWebEngine initialization.
-# On Windows, --no-sandbox is required to prevent QtWebEngineProcess renderer crash.
+# Configure Chromium command-line flags for QtWebEngine before Qt initialization.
+# Standard desktop execution preserves the native Chromium sandbox.
+# The sandbox bypass (--no-sandbox) is restricted to specialized environments
+# (such as containerized CI or unprivileged virtualization) and can be activated
+# by setting QTWEBENGINE_DISABLE_SANDBOX=1 or by passing --no-sandbox in QTWEBENGINE_CHROMIUM_FLAGS.
 existing_flags = os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '')
-if '--no-sandbox' not in existing_flags:
+if os.getenv('QTWEBENGINE_DISABLE_SANDBOX') == '1' and '--no-sandbox' not in existing_flags:
     os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = f'{existing_flags} --no-sandbox --disable-logging'.strip()
+elif '--disable-logging' not in existing_flags:
+    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = f'{existing_flags} --disable-logging'.strip()
 
 from PyQt5.QtCore import Qt
 from PyQt5.QtWidgets import QApplication, QMessageBox
@@ -34,6 +39,19 @@ from desktop.main_window import MainWindow
 def main():
     logger.info(f"Starting {config.APP_DISPLAY_NAME} v{config.VERSION} [{config.get_database_env()}]...")
 
+    # 0. Startup Configuration Validation
+    cfg_diag = config.validate_configuration()
+    if not cfg_diag["valid"]:
+        for err in cfg_diag["errors"]:
+            logger.critical(f"Startup configuration error: {err}")
+        print(f"\n[FATAL CONFIGURATION ERROR]:", file=sys.stderr)
+        for err in cfg_diag["errors"]:
+            print(f"  - {err}", file=sys.stderr)
+        sys.exit(1)
+    if cfg_diag["warnings"]:
+        for warn in cfg_diag["warnings"]:
+            logger.warning(f"Configuration warning: {warn}")
+
     # Enable High DPI display scaling for modern 4K/Retina screens
     QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
     QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
```
* **Necessity**: **Critical / Mandatory**. Fixes safety vulnerabilities identified in Phase 3.8 and Phase 3.8.1 by enforcing sandbox protection and fail-closed configuration validation.
* **Risk Assessment**: **Low Risk**. Enhances security posture; cleanly fails closed if misconfigured.
* **Recommendation**: **KEEP**.

---

### C. `core/configuration.py`
* **Git Status**: Modified (`Changes not staged for commit`)
* **Exact Purpose of Changes**:
  - Implements multi-environment profile detection (`APP_ENV=staging`, `testing`, `development`, `production`).
  - Supports 12-factor environment loading: in staging, loads `.env.staging` (if present) and strictly isolates from `.env`.
  - Dynamically resolves user data and backup directories for portable, local, and PyInstaller frozen modes.
  - Implements profile-aware database paths: in staging, defaults to `staging_anti_matrix_billing.db` and `staging_traditional_billing.db`.
  - Implements `validate_configuration()`: strictly blocks staging from connecting to production SQLite database files (`anti_matrix_billing.db`, `traditional_billing.db`) or shared database targets.
* **Summary of Diff**:
  - Replaces unconditional `.env` load with profile-aware loader.
  - Adds `TRADITIONAL_DATABASE_PATH = DATA_DIR / "traditional_billing.db"`.
  - Adds `get_environment()`, `is_staging()`, `is_production()`, `is_testing()`.
  - Adds `get_database_path()` and `get_traditional_database_path()`.
  - Adds `validate_configuration()`.
* **Necessity**: **Critical / Mandatory**. Core architectural foundation ensuring that staging execution never touches production databases.
* **Risk Assessment**: **Low Risk**. Fully backward-compatible; defaults to development/production behavior when `APP_ENV` is unset.
* **Recommendation**: **KEEP**.

---

### D. `db/traditional_database.py`
* **Git Status**: Modified (`Changes not staged for commit`)
* **Exact Purpose of Changes**:
  - Replaces hardcoded `config.DATABASE_PATH` with profile-aware `config.get_database_path()` in `validate_traditional_database_target`.
  - Replaces hardcoded `"data/traditional_billing.db"` with `config.get_traditional_database_path().resolve()`.
* **Exact Diff**:
```diff
diff --git a/db/traditional_database.py b/db/traditional_database.py
index 12b8fa8..795bfba 100644
--- a/db/traditional_database.py
+++ b/db/traditional_database.py
@@ -40,7 +40,7 @@ def validate_traditional_database_target(url_or_path: str) -> None:
         )
 
     # Reject if it exactly matches Fast Billing configured path
-    fast_configured_path = str(config.DATABASE_PATH).strip().lower()
+    fast_configured_path = str(config.get_database_path()).strip().lower()
     if normalized == fast_configured_path or normalized.endswith(fast_configured_path):
         raise TraditionalConfigurationError(
             "FATAL: Traditional Billing cannot use Fast Billing configured database path."
@@ -72,7 +72,7 @@ class TraditionalDatabaseManager:
             if env_url and env_url.strip():
                 target = env_url.strip()
             else:
-                default_sqlite_path = Path("data/traditional_billing.db").resolve()
+                default_sqlite_path = config.get_traditional_database_path().resolve()
                 target = f"sqlite:///{default_sqlite_path}"
 
         validate_traditional_database_target(target)
```
* **Necessity**: **Critical / Mandatory**. Ensures Traditional Database Manager resolves to `staging_traditional_billing.db` when `APP_ENV=staging`, preventing unintentional production target resolution.
* **Risk Assessment**: **Low / Zero Risk**. Eliminates hardcoded file paths while preserving strict validation against Fast Billing target collision.
* **Recommendation**: **KEEP**.

---

### E. `desktop/main_window.py`
* **Git Status**: Modified (`Changes not staged for commit`)
* **Exact Purpose of Changes**:
  - Restricts Chromium `--no-sandbox` flag to explicitly opted-in environments via `QTWEBENGINE_DISABLE_SANDBOX=1`.
  - Standard desktop execution leaves the native Chromium sandbox fully active.
* **Exact Diff**:
```diff
diff --git a/desktop/main_window.py b/desktop/main_window.py
index 05e105c..d02e7d1 100644
--- a/desktop/main_window.py
+++ b/desktop/main_window.py
@@ -6,10 +6,15 @@ import sys
 import os
 from pathlib import Path
 
-# Ensure Chromium flags are active even if MainWindow is imported directly
+# Configure Chromium command-line flags for QtWebEngine before Qt initialization.
+# Standard desktop execution preserves the native Chromium sandbox.
+# The sandbox bypass (--no-sandbox) is restricted to specialized environments
+# and can be activated by setting QTWEBENGINE_DISABLE_SANDBOX=1 or by passing --no-sandbox in QTWEBENGINE_CHROMIUM_FLAGS.
 existing_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
-if "--no-sandbox" not in existing_flags:
+if os.getenv("QTWEBENGINE_DISABLE_SANDBOX") == "1" and "--no-sandbox" not in existing_flags:
     os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{existing_flags} --no-sandbox --disable-logging".strip()
+elif "--disable-logging" not in existing_flags:
+    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{existing_flags} --disable-logging".strip()
 
 from PyQt5.QtCore import QUrl, Qt, QEvent, QTimer
 from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox
```
* **Necessity**: **Necessary**. Hardens application security in compliance with Phase 3.8.1 audit findings.
* **Risk Assessment**: **Low Risk**. Tested and verified working seamlessly on macOS Cocoa platform.
* **Recommendation**: **KEEP**.

---

## 4. Audit of Phase 3.9B Created & Modified Files

### A. `scripts/seed_staging_data.py`
* **Git Status**: Untracked (new staging utility script)
* **Exact Purpose**:
  - Automated, 100% idempotent provisioning tool for synthetic staging environments.
  - Provisions Fast Billing company `STAGE01` and branch `BR01`.
  - Provisions Traditional ERP company `STAGING-CORP`, branch `BR01`, and Chart of Accounts.
  - Provisions cashier (`staging_cashier`) and administrator (`staging_admin`) credentials using secure password hashing (PBKDF2-HMAC-SHA256 and bcrypt).
* **Can it EVER target production databases?**:
  - **NO**. The script contains 3 independent fail-closed guardrails:
    1. Lines 29-33: Forces `DATABASE_URL` and `TRADITIONAL_DATABASE_URL` to staging paths if `"staging"` is missing from the environment.
    2. Lines 66-68: Explicitly checks `config.is_production()` and aborts with `sys.exit(1)`.
    3. Lines 75-77: Explicitly checks `if "staging" not in fast_db.name or "staging" not in trad_db.name` and aborts with `sys.exit(1)`.
    4. Lines 80-85: Executes `config.validate_configuration()` and aborts with `sys.exit(1)` on any error.
* **Scope of the `BR01` Branch Code Adjustment**:
  - **Correctly Scoped**. In line 111, the branch insertion was updated from `'MAIN'` to `'BR01'`. This change affects solely the staging synthetic database (`staging_anti_matrix_billing.db`) when seeded. It brings the staging seed data into exact alignment with `desktop/web_bridge.py` line 304 (which requires `UPPER(code) == 'BR01'` as the primary branch) and the production branch schema convention.
* **Recommendation**: **KEEP**.

---

### B. `scripts/verify_staging_launch.py`
* **Git Status**: Untracked (new test automation script)
* **Exact Purpose**:
  - Headless/interactive test harness that launches `QApplication` and `MainWindow` with `QWebEngineView` under `APP_ENV=staging`.
  - Monitors `loadFinished`, probes DOM elements for the login view (`#view-login`), and records JavaScript console errors and warnings.
  - Exercises authentication for both Fast Billing Cashier and Traditional ERP Administrator, testing invalid password rejection, session verification, and session logout.
  - Tests cross-database login rejection and session isolation.
  - Verifies production database SHA-256 hashes before and after execution.
* **Does it use ONLY staging databases?**:
  - **YES**. Explicitly enforces `APP_ENV=staging` and `DATABASE_ENV=staging` on lines 25-26, asserts `"staging" in str(fast_db)` and `"staging" in str(trad_db)`, and validates that production database hashes are unaltered.
* **Are credentials or secrets exposed?**:
  - **NO**. Outputs only boolean status flags, user roles, and sanitized session metadata. No plaintext passwords or authentication tokens are logged or written to disk.
* **Recommendation**: **KEEP**.

---

### C. `PHASE_3_9B_STAGING_LAUNCH_REPORT.md`
* **Git Status**: Untracked (milestone deliverable report)
* **Exact Purpose**:
  - Authoritative Phase 3.9B release report documenting desktop launch, DOM inspection, JavaScript/Python error logs (0 errors), authentication validation, session isolation, and production database invariance.
* **Recommendation**: **KEEP**.

---

### D. `staging_launch_results.json`
* **Git Status**: Untracked (machine-readable test output)
* **Exact Purpose**:
  - Captures structured JSON results of the `verify_staging_launch.py` run (all flags `true`, 0 JS errors, 0 JS warnings, 0 Python exceptions).
* **Recommendation**: **KEEP**.

---

## 5. Audit of Untracked Supporting Staging & Packaging Artifacts

| File / Directory | Git Status | Purpose | Risk Assessment | Recommendation |
|---|---|---|---|:---:|
| `.env.staging.example` | Untracked | Staging environment template | Zero Risk | **KEEP** |
| `assets/` | Untracked | Generated platform icons (`.icns`, `.ico`, `.png`) | Zero Risk | **KEEP** |
| `packaging/pyinstaller.spec` | Untracked | PyInstaller specification for desktop bundle | Zero Risk | **KEEP** |
| `scripts/generate_app_icons.py` | Untracked | Reproducible platform icon generator script | Zero Risk | **KEEP** |
| `tests/staging/` | Untracked | Staging lifecycle, safety, and operator test suites | Zero Risk | **KEEP** |
| `PHASE_3_8_STAGING_RELEASE_PREPARATION.md` | Untracked | Phase 3.8 audit report | Zero Risk | **KEEP** |
| `PHASE_3_8_1_STAGING_SAFETY_AUDIT.md` | Untracked | Phase 3.8.1 audit report | Zero Risk | **KEEP** |
| `PHASE_3_9_PROGRESS.md` | Untracked | Phase 3.9 pause and progress documentation | Zero Risk | **KEEP** |
| `PHASE_3_9A_STAGING_PREFLIGHT.md` | Untracked | Phase 3.9A preflight report | Zero Risk | **KEEP** |

---

## 6. Verification of Scope and Safety Boundaries

1. **Friend-Owned Modules**:
   - Friend 1 (Sales/Billing): `services/billing_service.py` — **UNTOUCHED**.
   - Friend 2 (Purchase): `services/purchase_service.py` / Purchase endpoints — **UNTOUCHED**.
   - Friend 3 (Configuration): `services/paper_config_service.py`, `services/bill_layout_config_service.py`, `services/voucher_numbering_config_service.py`, `services/gst_tax_config_service.py`, `services/inventory_config_service.py` — **UNTOUCHED**.
2. **Business Logic & Accounting Models**:
   - `services/traditional_payment_service.py` — **UNTOUCHED**.
   - `services/traditional_accounting_service.py` — **UNTOUCHED**.
   - `services/traditional_financial_reconciliation_service.py` — **UNTOUCHED**.
   - `db/models.py` & `db/traditional_models.py` — **UNTOUCHED**.
3. **Database Schemas & Migrations**:
   - Alembic migration scripts in `traditional_migrations/` — **UNTOUCHED**.
   - Fast Billing migrations in `db/migrations/` — **UNTOUCHED**.
   - Zero migrations executed against production databases.
4. **Temporary Debugging Code**:
   - Verified that no temporary debug prints, bypasses, or mock overrides remain in any tracked source files.
5. **Preservation of Pre-existing Changes**:
   - All pre-existing modified files (`.gitignore`, `app.py`, `core/configuration.py`, `db/traditional_database.py`, `desktop/main_window.py`) and untracked assets from Phase 3.8 and Phase 3.9 remain intact and preserved.

---

## 7. Change-Control Recommendations Summary

| File | Status | Action | Notes |
|---|---|:---:|---|
| `.gitignore` | Modified | **KEEP** | Essential for packaging build hygiene |
| `app.py` | Modified | **KEEP** | Essential for fail-closed validation and sandbox security |
| `core/configuration.py` | Modified | **KEEP** | Essential for staging profile isolation |
| `db/traditional_database.py` | Modified | **KEEP** | Resolves dynamic staging database paths safely |
| `desktop/main_window.py` | Modified | **KEEP** | Preserves Chromium sandbox by default |
| `scripts/seed_staging_data.py` | Untracked | **KEEP** | Verified fail-closed; BR01 branch adjustment properly scoped |
| `scripts/verify_staging_launch.py` | Untracked | **KEEP** | Verified staging-only; zero secret disclosures |
| `staging_launch_results.json` | Untracked | **KEEP** | Valid test artifact |
| `PHASE_3_9B_STAGING_LAUNCH_REPORT.md` | Untracked | **KEEP** | Deliverable report |

---

## 8. Final Change-Control Verdict

### **APPROVED FOR PHASE 3.9C**

All changes are properly scoped, verified safe, and mathematically decoupled from production databases and business logic. The application is ready to proceed to Phase 3.9C (Operator Workflow Validation).
