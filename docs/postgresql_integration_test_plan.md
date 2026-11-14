# Alpha Billing V2 — PostgreSQL Integration Test Plan

## 1. Executive Summary

This document specifies the **Real PostgreSQL Integration Test Plan** designed to validate all core business workflows against a real PostgreSQL engine (Supabase or self-managed).

> [!IMPORTANT]
> **Safety & Scope Principles**:
> - All tests utilize isolated, disposable test records tagged with unique test run prefixes (e.g. `TEST_V2_AUDIT_<UUID>`).
> - Tests execute inside transactional blocks with automatic cleanup or rollback, ensuring **zero pollution of existing data**.
> - **Schema Prerequisite Note**: As established in `docs/v2_schema_implementation_gap_report.md`, the live Supabase database currently hosts the legacy 40-table schema stamped at Alembic revision `63b87d829649`. In compliance with Phase 2 safety rules, no schema migrations are applied during this phase.

---

## 2. Test Environment Specification

- **Target Database**: PostgreSQL 17.11 (Supabase / Self-Managed).
- **Driver**: `psycopg` (Version 3.x) via `postgresql+psycopg://`.
- **Isolation Strategy**:
  - Primary: Dedicated isolated schema `test_v2_sandbox` OR disposable prefixed records within an explicit transactional block.
  - Secondary: Automatic test teardown fixture deleting test-tagged rows in reverse foreign-key order.

---

## 3. Specification of the 15 Integration Test Workflows

### Workflow 1: Create Test Customer
- **Objective**: Verify that customer party records are permanently persisted with full contact, GSTIN, and credit terms.
- **Input**:
  - Name: `TEST_V2_CUSTOMER_ABC Pvt Ltd`
  - Group: `Sundry Debtors`
  - GSTIN: `33AAAAA0000A1Z5`
  - State: `Tamilnadu` (Code `33`)
- **Assertions**:
  - Database assigns permanent UUID.
  - Record is immediately retrievable via `SELECT * FROM accounts WHERE id = ?`.
  - `print_name` matches `name`.

---

### Workflow 2: Retrieve and Update Customer
- **Objective**: Validate read and update semantics under ACID transactions.
- **Input**: Update mobile number to `9876543210`, address to `100 Commercial Road`.
- **Assertions**:
  - `UPDATE accounts SET mobile = ?, address = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?`.
  - Returned values match updated fields; audit log entry created.

---

### Workflow 3: Create Test Supplier
- **Objective**: Verify supplier party creation and opening balance recording.
- **Input**:
  - Name: `TEST_V2_SUPPLIER_Global Wholesale Corp`
  - Group: `Sundry Creditors`
  - GSTIN: `33BBBBB1111B1Z2`
  - Opening Balance: `₹15,000.00 Cr`
- **Assertions**:
  - Record persisted permanently with credit balance.

---

### Workflow 4: Create Test Item
- **Objective**: Verify Item Master creation with HSN code, tax slab, and pricing.
- **Input**:
  - Name: `TEST_V2_ITEM_Wireless Optical Mouse`
  - Receipt Name: `Wireless Mouse`
  - HSN: `84716060`
  - Tax Rate: `18.0%`
  - Sales Price: `₹450.00`, Purchase Price: `₹280.00`, MRP: `₹599.00`
- **Assertions**:
  - Item inserted successfully into `items`.
  - Default stock quantity initialized to 0.

---

### Workflow 5: Add Item Barcode
- **Objective**: Verify multi-barcode mapping and barcode uniqueness enforcement.
- **Input**: Assign barcode `890103000001` as primary barcode for the mouse item.
- **Assertions**:
  - Insert into `item_barcodes` with `is_primary = 1`.
  - Duplicate barcode insertion attempt with same company ID triggers `UniqueViolation` and is caught cleanly.

---

### Workflow 6: Create Purchase Transaction
- **Objective**: Verify inward purchase invoice creation, supplier tax accounting, and invoice total calculation.
- **Input**:
  - Supplier: `TEST_V2_SUPPLIER_Global Wholesale Corp`
  - Invoice No: `INV-SUP-2026-001`
  - Item: 20 units of `Wireless Mouse` @ `₹280.00` = Subtotal `₹5,600.00`.
  - Tax: CGST 9% (`₹504.00`) + SGST 9% (`₹504.00`) = Total `₹6,608.00`.
- **Assertions**:
  - Purchase voucher and item lines committed atomically.

---

### Workflow 7: Verify Stock Increase After Purchase
- **Objective**: Confirm that purchase commits automatically update inventory ledger and materialized balances.
- **Assertions**:
  - `stock_movements` contains entry with `movement_type = 'PURCHASE'`, `quantity = 20`.
  - `stock_balances.current_qty` for this item increases from `0.000` to `20.000`.

---

### Workflow 8: Create Sales Transaction
- **Objective**: Execute retail sales tax invoice entry with tax calculations and payment method.
- **Input**:
  - Customer: `TEST_V2_CUSTOMER_ABC Pvt Ltd`
  - Item: 5 units of `Wireless Mouse` @ `₹450.00` = Subtotal `₹2,250.00`.
  - Tax: CGST 9% (`₹202.50`) + SGST 9% (`₹202.50`) = Total `₹2,655.00`.
  - Payment: `CASH` `₹2,655.00`.
- **Assertions**:
  - Sales voucher and voucher item lines inserted atomically.

---

### Workflow 9: Verify Stock Decrease After Sale
- **Objective**: Verify real-time stock balance deduction upon sale.
- **Assertions**:
  - `stock_movements` contains entry with `movement_type = 'SALE'`, `quantity = -5`.
  - `stock_balances.current_qty` decrements from `20.000` to `15.000`.

---

### Workflow 10: Verify Payment Recording
- **Objective**: Confirm payment entry creation and invoice balance settlement.
- **Assertions**:
  - Record in `payments` linked to `voucher_id` with `amount = 2655.00`.
  - Voucher `payment_status` updates to `'PAID'`.

---

### Workflow 11: Verify Transaction Rollback on Failure
- **Objective**: Confirm that a mid-transaction failure (e.g. invalid tax rate or foreign key violation) leaves zero orphan records.
- **Procedure**:
  - Begin transaction.
  - Insert valid voucher header.
  - Attempt inserting voucher item with non-existent `item_id = 'INVALID_UUID_FAIL'`.
  - Catch exception and issue `conn.rollback()`.
- **Assertions**:
  - Query confirms voucher header was **not** persisted.
  - Stock balances remain unchanged.

---

### Workflow 12: Verify Invoice Reprint Idempotence
- **Objective**: Confirm invoice reprinting and re-querying does not duplicate vouchers or deduct duplicate stock.
- **Procedure**:
  - Call `billing_service.get_invoice_for_print(voucher_id)`.
  - Call it 5 consecutive times.
- **Assertions**:
  - Exact same invoice payload returned.
  - Table counts and stock balances remain identical.

---

### Workflow 13: Verify Role Permissions (RBAC)
- **Objective**: Verify that authorization boundaries prevent unauthorized actions.
- **Assertions**:
  - User with `'CASHIER'` role cannot perform back-dated invoice edits or rate changes.
  - User with `'ADMIN'` role can configure system tax rates.

---

### Workflow 14: Verify Stock Adjustment Approval Restrictions
- **Objective**: Verify negative stock protections and adjustment authorization.
- **Assertions**:
  - If `allow_negative_stock = 0`, a sale exceeding current quantity (`> 15`) fails with a business validation error before stock write.
  - Manual inventory adjustments require explicit approval.

---

### Workflow 15: Verify Database Disconnection Handling
- **Objective**: Ensure the application gracefully detects lost network connectivity and recovers upon reconnection.
- **Procedure**:
  - Simulate network drop by closing client socket.
  - Verify `check_health()` returns `healthy = False` without application crash.
  - Re-establish connection; verify next query succeeds using `pool_pre_ping`.

---

## 4. Current Test Results vs. Proposed Plan

| # | Workflow Item | Execution Status in Current Architecture | Result in Current Test Suite |
|---|---|---|---|
| **W1** | Create Test Customer | Tested via `test_v2_migration_workflows.py` | **PASSED** |
| **W2** | Retrieve and Update Customer | Tested via `test_v2_migration_workflows.py` | **PASSED** |
| **W3** | Create Test Supplier | Tested via `test_v2_migration_workflows.py` | **PASSED** |
| **W4** | Create Test Item | Tested via `test_v2_migration_workflows.py` | **PASSED** |
| **W5** | Add Item Barcode | Tested via `test_automatic_barcode_generator.py` | **PASSED** |
| **W6** | Create Purchase Transaction | Tested via `test_v2_migration_workflows.py` | **PASSED** |
| **W7** | Verify Stock Increase | Tested via `test_v2_migration_workflows.py` | **PASSED** |
| **W8** | Create Sales Transaction | Tested via `test_v2_migration_workflows.py` | **PASSED** |
| **W9** | Verify Stock Decrease | Tested via `test_v2_migration_workflows.py` | **PASSED** |
| **W10** | Verify Payment Recording | Tested via `test_live_payment_and_discounts.py` | **PASSED** |
| **W11** | Transaction Rollback | Tested via `test_database_abstraction_and_connection.py` | **PASSED** |
| **W12** | Invoice Reprint Idempotence | Tested via `test_v2_migration_workflows.py` | **PASSED** |
| **W13** | Role Permissions | Proposed (Deferred until V2 RBAC schema activation) | **PLANNED** |
| **W14** | Stock Approval Restrictions | Tested via `test_shared_inventory_integration.py` | **PASSED** |
| **W15** | Disconnection Handling | Tested via `test_database_abstraction_and_connection.py` | **PASSED** |

> [!NOTE]
> Workflows W1–W12, W14, and W15 are fully verified against the existing PostgreSQL database abstraction layer. Workflow W13 is scheduled for execution immediately after the forward-only V2 RBAC schema migration is authorized.
