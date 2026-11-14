# Alpha Billing V2 — Phase 3: Supabase Connection and Multi-User Readiness Audit Report

**Date:** 2026-11-10  
**Phase:** Phase 3 — Supabase Connection & Multi-User Readiness Audit  
**Mode:** Read-Only Audit & Non-Destructive Transaction/Concurrency Verification  
**Target Database:** Supabase PostgreSQL 17.11 (`nxetowrecgjbpijdjpqd`, Tokyo Region via Session Pooler)  
**Baseline Database:** Local SQLite (`data/anti_matrix_billing.db`)  
**Development Database:** Local PostgreSQL (`alpha_billing_dev`)  

---

## 1. Executive Summary

This audit evaluates the live Supabase PostgreSQL connection, data integrity across the 40 tables, multi-company and branch data isolation, concurrent transaction handling, and authentication/RBAC readiness.

### Key Audit Results:
1. **Supabase Connectivity Verified (Read-Only):** Direct connection through the Supabase Tokyo Session Pooler (`aws-0-ap-northeast-1.pooler.supabase.com:5432`) is operational (round-trip latency: ~795 ms). The `DatabaseManager` in `db/database.py` successfully connects, queries, executes transactions with auto-rollback, and cleanly disposes pooled connections without leaks.
2. **Data Integrity (100% Referential Integrity):** All 74 foreign key relationships across 11,920 records were checked: **0 orphaned records**. All 35 unique constraints have zero duplicates. All 747 journal entries balance perfectly (Total Debit = Total Credit = ₹746,485.48). Formula verification for sales vouchers (`Taxable + CGST + SGST + IGST + RoundOff == GrandTotal`) passed with zero variance across all 578 vouchers.
3. **Multi-Company & Branch Isolation:** Data-level partitioning is strictly enforced across all 27 tenant tables with `WHERE company_id = ?`. However, an architectural authorization gap exists at the RPC bridge layer (`desktop/web_bridge.py`): the backend does not validate that the `company_id` passed by the client matches an authenticated session token.
4. **Transaction & Concurrency Safety:** Database-level duplicate prevention (`uq_sales_vouchers_comp_vchno`) and transaction rollbacks are working properly. When saving invoices, sequence allocation is serialized via row-level locks on `voucher_sequences`. However, the read-only preview method `get_next_voucher_number()` exhibits a concurrency race condition, returning identical draft numbers to concurrent users until saved.
5. **Authentication & RBAC Readiness:** The existing test credentials (`Company: COMP0001`, `User: A`, `Password: a`) succeed via the company fallback in `company_service.py`. The `public.users` table is ready in schema but has 0 rows. Services do not currently enforce server-side role or permission checks.

---

## 2. Supabase Connection & Infrastructure Verification

### 2.1 Connection Parameters & Environment Audit

| Parameter | Configuration / Actual State | Status / Verification |
|---|---|---|
| **Active `.env` Target** | `postgresql+psycopg://dhvira@localhost:5432/alpha_billing_dev` | Local PostgreSQL active. Supabase commented out on line 10. |
| **Supabase Pooler Host** | `aws-0-ap-northeast-1.pooler.supabase.com:5432` | Accessible via IPv4. Latency: ~795 ms from macOS client. |
| **Direct Host** | `db.nxetowrecgjbpijdjpqd.supabase.co:5432` | IPv6-only (`AAAA`). Inaccessible on standard IPv4 networks. |
| **PostgreSQL Version** | `PostgreSQL 17.11 on aarch64-unknown-linux-gnu` | Verified on live Supabase instance. |
| **SSL Requirement** | `sslmode=require` | Strictly required. Non-SSL connections are rejected. |
| **Max Connections** | 60 (managed pooler limit) | Verified via `SHOW max_connections`. |
| **Active Connections** | 1 active, 6 idle, 8 pooler reserved | Monitored in `pg_stat_activity`. |
| **Idle In Transaction** | **0** | No connection leaks or hung transactions detected. |
| **Default Isolation** | `READ COMMITTED` | Standard PostgreSQL ACID transaction isolation. |
| **Timezone** | `UTC` | Standard UTC server timezone. |

### 2.2 Connection Pooling & Transaction Management (`db/database.py`)
- **SQLAlchemy 2.x Engine:** Configured with conservative pool parameters (`pool_size=5`, `max_overflow=10`, `pool_timeout=30`, `pool_recycle=300`, `pool_pre_ping=True`). This fits comfortably within Supabase's 60-connection pooler limit.
- **Connection Adapter:** `PostgresConnectionAdapter` wraps native Psycopg 3 connections. In context-manager usage (`with db.get_connection() as conn:`), it commits on clean exit, automatically rolls back on exceptions, and ensures connection closure.
- **Engine Disposal:** Verified clean disposal via `supa_mgr.dispose()`.

---

## 3. Existing Data Integrity Audit (Read-Only)

All checks were executed in read-only mode against the live Supabase database:

```
================================================================================
SUPABASE DATA INTEGRITY VERIFICATION AUDIT RESULTS
================================================================================

1. Referential Integrity (74 Foreign Keys Audited):
   [PASS] 100% Referential Integrity: ZERO orphan records across all 74 foreign key relationships.

2. Unique Constraints & Key Duplicates:
   [PASS] companies.code: Unique (0 duplicates)
   [PASS] branches.code per company: Unique (0 duplicates)
   [PASS] item_barcodes.barcode: Unique (0 duplicates)
   [PASS] items.name per company: Unique (0 duplicates)
   [PASS] sales_vouchers.vch_no per company: Unique (0 duplicates)
   [PASS] purchase_vouchers.vch_no per company: Unique (0 duplicates)

3. Financial & Tax Integrity on Sales Vouchers (578 vouchers):
   Total vouchers: 578
   Sum Subtotal: ₹525,526.00
   Sum Taxable:  ₹523,186.00
   Sum CGST:     ₹47,086.74
   Sum SGST:     ₹47,086.74
   Sum RoundOff: ₹-2.48
   Sum GrandTot: ₹617,357.00
   Formula Check (Taxable + CGST + SGST + IGST + RoundOff == GrandTotal): Variance = ₹0.00 -> [PASS]

4. Accounting Integrity (Journal Entries & Lines):
   Total Balanced Entries: 747 | Total Debit: ₹746,485.48 | Total Credit: ₹746,485.48
   Unbalanced Journal Entries (Debit != Credit): 0 -> [PASS]

5. Inventory Consistency:
   Main Branch Items Audited: 794
   Formula Match (op_stock_qty + movements == current_qty): 777 items (97.9%)
   Discrepancies: 17 items (caused by early physical adjustments / test fixtures)
   Negative Stock Balances: 3 items (minimum balance: -6.0 Pcs)

6. Audit Trail (audit_logs table):
   Total Audit Logs: 897 records
   Historical Audit Logs: 887 records (100% non-null action, entity_type, created_at)
   Test Audit Logs: 10 records with created_at = NULL (from automated test sales #571-#578)
```

---

## 4. Multi-Company and Multi-Branch Isolation Audit

### 4.1 Data-Level Tenant Partitioning (Verified: Solid)
- Every business table (27 tables total) contains a `company_id` column indexed with foreign-key constraints to `public.companies(id)`.
- Every service query in `services/account_service.py`, `services/catalogue_service.py`, `services/billing_service.py`, `services/inventory_service.py`, `services/purchase_service.py`, and `services/reporting_service.py` explicitly includes `WHERE company_id = ?`.
- Verified via query simulation: When Company 1 (`3a743bcd...`) executes queries, it is impossible for Company 2 (`cd064e32...`) records to appear in the result set.

### 4.2 Request-Level Authorization Gap (Verified: Missing Check)
- **Vulnerability:** `BackendBridge` in `desktop/web_bridge.py` exposes methods directly to JavaScript (e.g. `listAccounts(company_id)`, `getInventoryDashboard(company_id)`, `getReport(company_id, report_type)`).
- **Evidence:** `BackendBridge` methods accept `company_id` as an unverified string argument passed from the client:
  ```python
  @pyqtSlot(str, result=str)
  def listAccounts(self, company_id: str) -> str:
      accs = account_service.list_accounts(company_id)
      return json.dumps({"success": True, "data": accs}, default=str)
  ```
  If a malicious script or compromised frontend component passes `company_id="cd064e32..."` (Company 2), the Python backend executes the query for Company 2 without checking whether the active session user has permission to access that company.
- **Fallback Behavior Risk:** In `account_service.py` and `inventory_service.py`, `_resolve_company_id()` contains:
  ```python
  cursor.execute("SELECT id FROM companies ORDER BY id ASC LIMIT 1;")
  c_default = cursor.fetchone()
  return c_default["id"]
  ```
  If `company_id` is passed as empty or invalid, the backend silently falls back to Company 1 (`ANTI MATRIX`) rather than rejecting the unauthorized request.

### 4.3 Branch-Level Authorization Findings
- In the database schema, `public.users` has **no `branch_id` column**.
- Users belong to a company, but there is no database constraint restricting a user to a specific branch.
- Any authenticated user of Company 1 can access inventory, sales, and purchases across all branches of Company 1.
- In V2 scope, this is acceptable because V2 strictly supports **one company and single-location inventory** (`Main Branch` / `BR01`). However, if multi-branch restrictions are required in future phases, `branch_id` must be added to `users` and enforced in queries.

---

## 5. Concurrency & Transaction Testing Results

All concurrency tests were conducted safely using synthetic identifiers and automatic rollbacks:

### 5.1 Transaction Rollback Integrity
* **Test:** Inserted synthetic item `SYNTHETIC_ROLLBACK_TEST_ITEM` and raised an unhandled exception inside `with supa_mgr.get_connection() as conn:`.
* **Result:** **PASSED**. Exception triggered `conn.rollback()` in `__exit__`. Re-querying the database confirmed 0 matching records.

### 5.2 Duplicate Transaction Prevention
* **Test:** Attempted to insert two sales vouchers with the same `company_id` and voucher number `SYNTH-DUP-...` in the same transaction.
* **Result:** **PASSED**. PostgreSQL immediately raised `psycopg.errors.UniqueViolation` on constraint `uq_sales_vouchers_comp_vchno`. The second insert was blocked.

### 5.3 Concurrent Voucher Numbering
* **Test:** Spawned 5 concurrent threads executing `get_next_voucher_number("3a743bcd...", "Main")` simultaneously against Supabase.
* **Result:** **Race Condition Observed**. All 5 threads returned the same candidate number `'579'`.
* **Analysis:**
  - `get_next_voucher_number()` is a read-only preview method; it does not lock rows.
  - However, in `save_sale_voucher()`, lines 311-329 execute:
    ```sql
    UPDATE voucher_sequences
    SET current_number = current_number + 1, updated_at = CURRENT_TIMESTAMP
    WHERE company_id = ? AND voucher_type = 'SALE' AND series = ?;
    ```
    This acquires an exclusive row-level lock on `voucher_sequences`. The first committing transaction succeeds, and concurrent saving transactions serialize cleanly.
  - If a draft screen holds an outdated candidate number, the database constraint `uq_sales_vouchers_comp_vchno` prevents duplication, but the user would see a save error unless the save flow dynamically retries.

### 5.4 Database Connection Cleanup
* **Test:** Monitored `pg_stat_activity` after multi-threaded bursts and engine disposal.
* **Result:** **PASSED**. Exactly 0 connections remained in `idle in transaction`. All connections returned to idle or were closed.

---

## 6. Authentication and RBAC Readiness

### 6.1 Current Authentication Architecture
The current authentication flow in `company_service.py` operates via a two-tier mechanism:

```mermaid
flowchart TD
    START["User submits: Company Code, Username, Password"] --> STEP_A{"Step A: Check public.users table?"}
    STEP_A -- "Match found" --> VERIFY_A{"verify_password(users.password_hash)?"}
    VERIFY_A -- "True" --> AUTH_USER["Authenticated as User (Role from users.role_name)"]
    VERIFY_A -- "False" --> FAIL["Authentication Failed"]
    STEP_A -- "No match (0 rows in users)" --> STEP_B{"Step B: Check companies table fallback?"}
    STEP_B -- "Match found" --> VERIFY_B{"verify_password(companies.password_hash)?"}
    VERIFY_B -- "True" --> AUTH_COMP["Authenticated as Company Admin (COMP0001, Role: Administrator)"]
    VERIFY_B -- "False" --> FAIL
```

### 6.2 Testing Credential Verification
* **Company:** `COMP0001`
* **Username:** `A`
* **Password:** `a`
* **Audit Result:** **VERIFIED WORKING**.
  - `COMP0001` exists in Supabase.
  - `companies.username` is `'A'`.
  - `companies.password_hash` matches password `'a'` via PBKDF2/SHA256 (`verify_password()` returns `True`).
  - Login succeeds via Step B fallback.

### 6.3 Multi-User & RBAC Gaps
1. **Empty `users` Table:** `public.users` has **0 rows**. User logins (e.g. `cashier_1`) fail until user records are created.
2. **Dormant `user_permissions` Table:** `user_permissions` table exists in PostgreSQL, but **zero Python services query it**.
3. **Client-Side-Only Role Enforcement:** `role_name` (`Administrator`, `Cashier`) is checked in JavaScript (`app.js`), but Python backend services (`billing_service`, `inventory_service`, `account_service`) do not check user roles before executing mutations.

### 6.4 Readiness for Future Administrator Provisioning
- The method `company_service.create_user(company_id, username, password, full_name, role_name)` is fully implemented and tested.
- It hashes passwords securely using `core.security.hash_password()`.
- Provisioning an initial administrator user can be executed safely via CLI or first-run prompt without altering the database schema.

---

## 7. Remaining Risks & Action Plan

| Risk / Gap | Severity | Impact | Recommended Action |
|---|---|---|---|
| **Direct Host IPv6 Inaccessibility** | Medium | Direct connection to `db.nxetowrecgjbpijdjpqd.supabase.co` fails on IPv4 networks. | Retain Supabase Tokyo Session Pooler (`aws-0-ap-northeast-1.pooler.supabase.com:5432`) as the standard connection endpoint. |
| **Missing Request Authorization in Bridge** | High | Unauthenticated JavaScript RPC calls could query arbitrary `company_id` if frontend is modified. | Store authenticated `session_token` / `active_company_id` on `BackendBridge` in Python and validate against all incoming RPC calls. |
| **Unseeded `users` Table** | Medium | Multi-user roles cannot be used until records are seeded in `public.users`. | Retain existing company fallback (`COMP0001 / A / a`) for testing; provide an administrative user provisioning script before release. |
| **Voucher Preview Race Condition** | Low | Multiple concurrent users opening a new bill screen simultaneously see the same draft voucher number. | Document that preview is indicative; sequence is finalized and locked upon invoice checkout. |
| **10 Historical Test Audit Logs with NULL Timestamps** | Low | 10 test entries from automated test sales #571-#578 have `created_at = NULL`. | Non-breaking; add `DEFAULT CURRENT_TIMESTAMP` to `audit_logs.created_at`. |

---

## 8. Exact Files Modified

During this read-only audit phase:
- **Project codebase files modified:** **0 files** (No application code, `.env`, or configuration files were modified).
- **Database changes executed:** **0 changes** (No tables created, altered, deleted, or truncated; all test operations used transactions that were explicitly rolled back).
- **Temporary diagnostic scripts created in scratch directory:**
  - `scratch/audit_supabase_connection.py`
  - `scratch/test_db_manager_supabase.py`
  - `scratch/audit_data_integrity.py`
  - `scratch/inspect_data_discrepancies.py`
  - `scratch/test_concurrency_and_transactions.py`
- **Documentation created:**
  - `docs/phase_3_supabase_connection_and_multi_user_audit.md`

---

### Audit Sign-Off
- **Status:** PHASE 3 READ-ONLY AUDIT COMPLETE
- **Supabase Connectivity:** VERIFIED OPERATIONAL
- **Data Integrity:** VERIFIED (100% REFERENTIAL INTEGRITY, 0 ORPHANS)
- **Fallback Login (`COMP0001 / A / a`):** VERIFIED WORKING
- **Next Step:** Awaiting user approval before applying any configuration or database updates.
