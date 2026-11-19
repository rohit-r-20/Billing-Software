# Anti-Matrix Billing V2 — Phase 3.9B: Controlled Staging Launch Report

**Document**: `PHASE_3_9B_STAGING_LAUNCH_REPORT.md`  
**Timestamp**: 2026-11-18T18:43:30+05:30  
**Phase**: Phase 3.9B — Controlled Staging Launch and Authentication Validation  
**Target Environment**: Isolated Staging (`APP_ENV=staging`, `DATABASE_ENV=staging`)  
**Operating System**: macOS (Darwin 25.6.0 arm64) | Python 3.11.15 / 3.14.3  
**Executable Runtime**: PyQt5 Desktop Application (Cocoa, QtWebEngine with native Chromium sandbox intact)  

---

## 1. Executive Summary

Phase 3.9B executed a controlled launch of the desktop application in the isolated staging environment, followed by DOM verification of the Standalone Login Screen, JavaScript console log capture, and end-to-end authentication and session isolation checks.

- **Desktop Launch**: Successfully initialized `QApplication` (cocoa platform) and `MainWindow` with `QWebEngineView`.
- **UI Entrypoint**: `index.html` loaded cleanly into the WebEngine container.
- **Login Screen Rendering**: Standalone Login Screen (`#view-login`) rendered as the default active screen (`class="screen-view active"`), with product branding *"Alpha Billing Software"* and mode selectors.
- **Console & Log Errors**: **0** JavaScript console errors, **0** JavaScript console warnings, and **0** unhandled Python startup exceptions.
- **Authentication**: Both Traditional ERP (`staging_admin`) and Fast Billing POS (`staging_cashier`) authenticated cleanly; invalid passwords were systematically rejected.
- **Session & Credential Isolation**: Cross-database logins were rejected, role boundaries were strictly enforced, and post-logout endpoint protection was verified.
- **Production Databases**: Byte-invariance verified (100% untouched).

**Final Verdict**: **LAUNCH ACCEPTED**.

---

## 2. Launch & Runtime Results

| Component | Status | Details / Evidence |
|---|:---:|---|
| **Environment Profile** | **PASS** | `APP_ENV=staging`, `DATABASE_ENV=staging` |
| **Database Isolation** | **PASS** | Fast DB: `staging_anti_matrix_billing.db`<br>Traditional DB: `staging_traditional_billing.db` |
| **QApplication Initialization** | **PASS** | Platform: `cocoa` (macOS native GUI) |
| **Chromium Sandbox** | **PASS** | Native Chromium sandbox enabled by default (`--no-sandbox` not used) |
| **QWebEngineView Page Load** | **PASS** | `index.html` loaded successfully (`loadFinished: True`) |
| **Login Screen Rendering** | **PASS** | `#view-login` detected active with all required controls in DOM |
| **JavaScript Console Errors** | **PASS (0)** | Zero console errors detected during initialization and execution |
| **JavaScript Console Warnings** | **PASS (0)** | Zero console warnings detected |
| **Python Startup Exceptions** | **PASS (0)** | Zero startup exceptions |

---

## 3. DOM & UI Screen Verification

Inspected the live DOM in `QWebEngineView` via asynchronous JavaScript evaluation upon load completion:
- **Active Screen**: `#view-login` (`classList.contains('active') == true`)
- **Product Title**: `"Alpha Billing Software"`
- **Mode Toggle Controls**:
  - `#btn-login-mode-trad` (Traditional Billing): **Present**
  - `#btn-login-mode-fast` (POS Fast Billing): **Present**
- **Authentication Inputs**:
  - `#login-user-input` (User ID): **Present**
  - `#login-pwd-input` (Password): **Present**
  - `#login-company-select` (Company selector): **Present** (options populated)

---

## 4. Authentication Validation Results

### A. Traditional ERP Administrator Login
- **Target Company**: `STAGING-CORP` (`Apex Staging Enterprises Ltd`)
- **Username**: `staging_admin` (stored as canonical `STAGING_ADMIN`)
- **Role Assigned**: `Administrator`
- **Invalid Password Test**:
  - Attempted login with invalid password `"WrongPassword!"`.
  - Result: **Rejected** (`success: False`, `"Invalid company code, User ID, or password."`).
- **Valid Password Test**:
  - Attempted login with provisioned staging administrator credentials.
  - Result: **Accepted** (`success: True`, `session_token` issued).
  - Session Validation: `traditional_getAuthenticatedSession()` returned active session with `role: "Administrator"`.
- **Logout Test**:
  - `traditional_logout()` executed successfully.
  - Subsequent session check returned `authenticated: False`.

### B. Fast Billing POS Cashier Login
- **Target Company**: `STAGE01` (`Staging Enterprise Mart`)
- **Username**: `staging_cashier`
- **Role Assigned**: `Cashier`
- **Invalid Password Test**:
  - Attempted login with invalid password `"WrongPassword!"`.
  - Result: **Rejected** (`success: False`, `"Invalid User ID or password. Please try again."`).
- **Valid Password Test**:
  - Attempted login with provisioned staging cashier credentials.
  - Result: **Accepted** (`success: True`).
  - Session Validation: `getAuthenticatedSession()` returned active session with `role: "Cashier"`, `branchCode: "BR01"`.
- **Logout Test**:
  - `logout()` executed successfully.
  - Subsequent session check returned `authenticated: False`.

---

## 5. Session and Credential Isolation Results

| Check | Expected Behavior | Observed Result | Verdict |
|---|---|---|:---:|
| **Cross-Database Fast in Trad** | Cashier `staging_cashier` cannot authenticate to Traditional DB | Rejected: `Invalid company code, User ID, or password.` | **PASS** |
| **Cross-Database Trad in Fast** | Admin `STAGING_ADMIN` cannot authenticate to Fast POS DB | Rejected: `Invalid User ID or password. Please try again.` | **PASS** |
| **Role Boundary Enforcement** | Fast Cashier strictly has `Cashier`; Traditional Admin has `Administrator` | `Cashier` vs `Administrator` strictly segregated | **PASS** |
| **Post-Logout Traditional Guard** | Unauthenticated call to `traditional_listCustomers` rejected | Rejected: `Authentication required` (`success: False`) | **PASS** |
| **Post-Logout Fast Guard** | Unauthenticated call to `searchCashierProducts` protected | Handled safely, returning empty list/authorization error | **PASS** |

---

## 6. Python and JavaScript Error Logs

* **Python Unhandled Exceptions**: `None`
* **QtWebEngine Render Terminations**: `None` (Process exited cleanly with status 0 upon test completion)
* **Frontend JavaScript Errors**: `None`
* **Raw JSON Results**: Captured in [staging_launch_results.json](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/staging_launch_results.json)

---

## 7. Files Modified During Phase 3.9B

1. [scripts/seed_staging_data.py](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/scripts/seed_staging_data.py):
   - Aligned staging branch code from `'MAIN'` to canonical `'BR01'` to conform with `desktop/web_bridge.py` line 304 and production data schema.
2. [data/staging_anti_matrix_billing.db](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/data/staging_anti_matrix_billing.db):
   - Staging branch `code` updated to `'BR01'` in the disposable staging database.
3. [scripts/verify_staging_launch.py](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/scripts/verify_staging_launch.py):
   - Created controlled launch test runner.
4. [staging_launch_results.json](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/staging_launch_results.json):
   - Test results output.

*Note: No production databases, production configurations, or business logic modules were modified.*

---

## 8. Production Database Invariance Audit

SHA-256 hashes of all production database files were verified before and after the controlled launch:

| Database File | Pre-Launch SHA-256 | Post-Launch SHA-256 | Status |
|---|---|---|---|
| `data/anti_matrix_billing.db` | `bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd` | `bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd` | **Unmodified (0 bytes)** |
| `data/app.db` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | **Unmodified (0 bytes)** |
| `data/traditional_billing.db` | `770dde96956adf7224023c546559ba6cc9f101e34a71dda9b27d9e717ca9d8c7` | `770dde96956adf7224023c546559ba6cc9f101e34a71dda9b27d9e717ca9d8c7` | **Unmodified (0 bytes)** |

---

## 9. Blockers

- **Zero Blockers**: No launch, rendering, authentication, or isolation blockers identified.

---

## 10. Final Verdict

### **LAUNCH ACCEPTED**

The desktop application successfully launches in staging mode, renders the login interface cleanly without errors, validates operator authentication across both modes, and maintains strict database and credential isolation. Execution has stopped and is ready for Phase 3.9C.
