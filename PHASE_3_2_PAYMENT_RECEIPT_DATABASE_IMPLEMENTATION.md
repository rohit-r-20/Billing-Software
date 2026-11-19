# Anti-Matrix Billing V2 — Phase 3.2: Payment & Receipt Database Implementation Report

**Document Version:** 1.0.0  
**Phase:** 3.2 (Payment & Receipt Database Foundation)  
**Author:** Senior Python ERP Database Architect  
**Status:** Completed & Fully Verified  
**Date:** 2026-11-17  

---

## Executive Summary

Phase 3.2 establishes the database foundation for Traditional Billing Payment and Receipt Management in Anti-Matrix Billing V2. All four required SQLAlchemy declarative ORM models (`CustomerReceipt`, `ReceiptAllocation`, `SupplierPayment`, `PaymentAllocation`), their accompanying constraints, indexes, and relationships have been implemented in [`db/traditional_models.py`](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/db/traditional_models.py).

A dedicated Alembic migration (`007_payment_and_receipt_management.py`) was created under [`traditional_migrations/versions/`](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/traditional_migrations/versions/007_payment_and_receipt_management.py) and thoroughly tested for complete forward upgrade and backward downgrade reversibility on disposable databases.

A dedicated automated test suite ([`tests/traditional/test_traditional_payment_models.py`](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/tests/traditional/test_traditional_payment_models.py)) was executed, passing all 14 test scenarios with 100% success. In addition, the full Traditional Billing test suite (166 tests across accounting, inventory, closing, voucher numbering, auth, and recovery) was executed and confirmed fully intact with zero regressions.

---

## 1. Models & Relationships Created

The four models were added to [`db/traditional_models.py`](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/db/traditional_models.py):

### 1.1 `CustomerReceipt` (`customer_receipts`)
Represents customer receipt vouchers deposited into Cash or Bank accounts.
- **Fields**:
  - `id`: `String(36)`, Primary Key (UUID4)
  - `company_id`: `String(36)`, FK -> `companies.id` (ON DELETE CASCADE, indexed)
  - `branch_id`: `String(36)`, FK -> `branches.id` (ON DELETE CASCADE, indexed)
  - `financial_year`: `String(20)`, Scoped financial year (e.g., `"2026-2027"`)
  - `voucher_number`: `String(50)`, Voucher sequence number
  - `receipt_date`: `String(20)`, Voucher date (`DD-MM-YYYY`)
  - `customer_account_id`: `String(36)`, FK -> `accounts.id` (Sundry Debtor, ON DELETE RESTRICT, indexed)
  - `deposit_account_id`: `String(36)`, FK -> `accounts.id` (Cash or Bank, ON DELETE RESTRICT, indexed)
  - `payment_method`: `String(50)`, default `"CASH"` (`"CASH"`, `"CHEQUE"`, `"NEFT_RTGS"`, `"UPI"`, `"CARD"`)
  - `total_amount`: `Numeric(15, 2)`, Non-negative monetary total received
  - `allocated_amount`: `Numeric(15, 2)`, Amount allocated to sales invoices (default `0.00`)
  - `unallocated_amount`: `Numeric(15, 2)`, Advance receipt balance (default `0.00`)
  - `discount_amount`: `Numeric(15, 2)`, Cash discount allowed (default `0.00`)
  - `reference_number`: `String(100)`, Cheque / UTR / Reference ID
  - `reference_date`: `String(20)`, Instrument date
  - `notes`: `Text`, Voucher remarks/narration
  - `journal_id`: `String(36)`, FK -> `journal_entries.id` (ON DELETE SET NULL, indexed)
  - `status`: `String(20)`, default `"POSTED"` (`"POSTED"`, `"REVERSED"`, `"CANCELLED"`)
  - `reversal_of_id`: `String(36)`, FK -> `customer_receipts.id` (ON DELETE SET NULL)
  - `reversal_reason`: `Text`, Reversal explanation
  - `idempotency_key`: `String(100)`, Scoped unique idempotency key
  - `created_by`: `String(36)`, FK -> `users.id` (ON DELETE SET NULL)
  - `created_at`: `UTCDateTime`, Timezone-aware UTC timestamp
  - `updated_at`: `UTCDateTime`, Timezone-aware UTC timestamp
- **Relationships**:
  - `company`: `relationship("Company", back_populates="receipts")`
  - `branch`: `relationship("Branch")`
  - `customer_account`: `relationship("Account", foreign_keys=[customer_account_id])`
  - `deposit_account`: `relationship("Account", foreign_keys=[deposit_account_id])`
  - `journal`: `relationship("JournalEntry", foreign_keys=[journal_id])`
  - `created_by_user`: `relationship("User", foreign_keys=[created_by])`
  - `reversal_of`: `relationship("CustomerReceipt", remote_side=[id], foreign_keys=[reversal_of_id])`
  - `allocations`: `relationship("ReceiptAllocation", back_populates="receipt", cascade="all, delete-orphan")`

### 1.2 `ReceiptAllocation` (`receipt_allocations`)
Represents line-item payment allocations from a customer receipt against sales invoices.
- **Fields**:
  - `id`: `String(36)`, Primary Key (UUID4)
  - `receipt_id`: `String(36)`, FK -> `customer_receipts.id` (ON DELETE CASCADE, indexed)
  - `invoice_id`: `String(36)`, FK -> `sales_invoices.id` (ON DELETE RESTRICT, indexed)
  - `allocated_amount`: `Numeric(15, 2)`, Portion of receipt applied to this invoice
  - `discount_amount`: `Numeric(15, 2)`, Cash discount allowed against this invoice (default `0.00`)
  - `created_by`: `String(36)`, FK -> `users.id` (ON DELETE SET NULL)
  - `created_at`: `UTCDateTime`, Allocation timestamp
- **Relationships**:
  - `receipt`: `relationship("CustomerReceipt", back_populates="allocations")`
  - `invoice`: `relationship("SaleInvoice", back_populates="receipt_allocations")`
  - `created_by_user`: `relationship("User", foreign_keys=[created_by])`

### 1.3 `SupplierPayment` (`supplier_payments`)
Represents supplier payment vouchers disbursed from Cash or Bank accounts.
- **Fields**:
  - `id`: `String(36)`, Primary Key (UUID4)
  - `company_id`: `String(36)`, FK -> `companies.id` (ON DELETE CASCADE, indexed)
  - `branch_id`: `String(36)`, FK -> `branches.id` (ON DELETE CASCADE, indexed)
  - `financial_year`: `String(20)`, Scoped financial year (e.g., `"2026-2027"`)
  - `voucher_number`: `String(50)`, Voucher sequence number
  - `payment_date`: `String(20)`, Voucher date (`DD-MM-YYYY`)
  - `supplier_account_id`: `String(36)`, FK -> `accounts.id` (Sundry Creditor, ON DELETE RESTRICT, indexed)
  - `source_account_id`: `String(36)`, FK -> `accounts.id` (Cash or Bank, ON DELETE RESTRICT, indexed)
  - `payment_method`: `String(50)`, default `"CASH"` (`"CASH"`, `"CHEQUE"`, `"NEFT_RTGS"`, `"UPI"`, `"CARD"`)
  - `total_amount`: `Numeric(15, 2)`, Non-negative monetary total disbursed
  - `allocated_amount`: `Numeric(15, 2)`, Amount allocated to bills (default `0.00`)
  - `unallocated_amount`: `Numeric(15, 2)`, Advance payment balance (default `0.00`)
  - `discount_amount`: `Numeric(15, 2)`, Cash discount received (default `0.00`)
  - `reference_number`: `String(100)`, Cheque / UTR / Reference ID
  - `reference_date`: `String(20)`, Instrument date
  - `notes`: `Text`, Voucher remarks/narration
  - `journal_id`: `String(36)`, FK -> `journal_entries.id` (ON DELETE SET NULL, indexed)
  - `status`: `String(20)`, default `"POSTED"` (`"POSTED"`, `"REVERSED"`, `"CANCELLED"`)
  - `reversal_of_id`: `String(36)`, FK -> `supplier_payments.id` (ON DELETE SET NULL)
  - `reversal_reason`: `Text`, Reversal explanation
  - `idempotency_key`: `String(100)`, Scoped unique idempotency key
  - `created_by`: `String(36)`, FK -> `users.id` (ON DELETE SET NULL)
  - `created_at`: `UTCDateTime`, Timezone-aware UTC timestamp
  - `updated_at`: `UTCDateTime`, Timezone-aware UTC timestamp
- **Relationships**:
  - `company`: `relationship("Company", back_populates="payments")`
  - `branch`: `relationship("Branch")`
  - `supplier_account`: `relationship("Account", foreign_keys=[supplier_account_id])`
  - `source_account`: `relationship("Account", foreign_keys=[source_account_id])`
  - `journal`: `relationship("JournalEntry", foreign_keys=[journal_id])`
  - `created_by_user`: `relationship("User", foreign_keys=[created_by])`
  - `reversal_of`: `relationship("SupplierPayment", remote_side=[id], foreign_keys=[reversal_of_id])`
  - `allocations`: `relationship("PaymentAllocation", back_populates="payment", cascade="all, delete-orphan")`

### 1.4 `PaymentAllocation` (`payment_allocations`)
Represents line-item payment allocations from a supplier payment against purchase bills.
- **Fields**:
  - `id`: `String(36)`, Primary Key (UUID4)
  - `payment_id`: `String(36)`, FK -> `supplier_payments.id` (ON DELETE CASCADE, indexed)
  - `purchase_voucher_id`: `String(36)`, Nullable reference for future Purchase module (indexed)
  - `bill_number`: `String(100)`, Supplier invoice / bill reference number
  - `allocated_amount`: `Numeric(15, 2)`, Amount applied to bill
  - `discount_amount`: `Numeric(15, 2)`, Discount received (default `0.00`)
  - `created_by`: `String(36)`, FK -> `users.id` (ON DELETE SET NULL)
  - `created_at`: `UTCDateTime`, Allocation timestamp
- **Relationships**:
  - `payment`: `relationship("SupplierPayment", back_populates="allocations")`
  - `created_by_user`: `relationship("User", foreign_keys=[created_by])`

---

## 2. Schema Constraints & Invariants

| Target Table | Constraint Name | Type | Definition / Guarantee |
| :--- | :--- | :--- | :--- |
| `customer_receipts` | `uq_cust_receipts_company_fy_vch` | UniqueConstraint | `(company_id, financial_year, voucher_number)` — Scoped gapless uniqueness |
| `customer_receipts` | `uq_cust_receipts_idempotency` | UniqueConstraint | `(company_id, idempotency_key)` — Prevents duplicate receipt postings |
| `customer_receipts` | `chk_cust_receipt_total_positive` | CheckConstraint | `total_amount > 0` — Rejects zero or negative payments |
| `customer_receipts` | `chk_cust_receipt_allocated_non_neg` | CheckConstraint | `allocated_amount >= 0` — Rejects negative allocations |
| `customer_receipts` | `chk_cust_receipt_unallocated_non_neg` | CheckConstraint | `unallocated_amount >= 0` — Rejects negative advance balances |
| `customer_receipts` | `chk_cust_receipt_discount_non_neg` | CheckConstraint | `discount_amount >= 0` — Rejects negative discounts |
| `customer_receipts` | `chk_cust_receipt_status` | CheckConstraint | `status IN ('POSTED', 'REVERSED', 'CANCELLED')` — Finite lifecycle |
| `receipt_allocations` | `uq_ralloc_receipt_invoice` | UniqueConstraint | `(receipt_id, invoice_id)` — One allocation per receipt-invoice pair |
| `receipt_allocations` | `chk_ralloc_allocated_positive` | CheckConstraint | `allocated_amount > 0` — Allocation amount must be strictly positive |
| `receipt_allocations` | `chk_ralloc_discount_non_neg` | CheckConstraint | `discount_amount >= 0` — Non-negative discounts |
| `supplier_payments` | `uq_supp_payments_company_fy_vch` | UniqueConstraint | `(company_id, financial_year, voucher_number)` — Scoped gapless uniqueness |
| `supplier_payments` | `uq_supp_payments_idempotency` | UniqueConstraint | `(company_id, idempotency_key)` — Prevents duplicate payment postings |
| `supplier_payments` | `chk_supp_payment_total_positive` | CheckConstraint | `total_amount > 0` — Disbursed amount must be strictly positive |
| `supplier_payments` | `chk_supp_payment_allocated_non_neg` | CheckConstraint | `allocated_amount >= 0` — Rejects negative allocations |
| `supplier_payments` | `chk_supp_payment_unallocated_non_neg` | CheckConstraint | `unallocated_amount >= 0` — Rejects negative advance balances |
| `supplier_payments` | `chk_supp_payment_discount_non_neg` | CheckConstraint | `discount_amount >= 0` — Rejects negative discounts |
| `supplier_payments` | `chk_supp_payment_status` | CheckConstraint | `status IN ('POSTED', 'REVERSED', 'CANCELLED')` — Finite lifecycle |
| `payment_allocations` | `chk_palloc_allocated_positive` | CheckConstraint | `allocated_amount > 0` — Allocation amount must be strictly positive |
| `payment_allocations` | `chk_palloc_discount_non_neg` | CheckConstraint | `discount_amount >= 0` — Non-negative discounts |

---

## 3. Migration Revision & Verification

- **Revision File**: [`traditional_migrations/versions/007_payment_and_receipt_management.py`](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/traditional_migrations/versions/007_payment_and_receipt_management.py)
- **Revision ID**: `007_payment_and_receipt_management`
- **Down Revision**: `006_financial_year_closing_and_opening_balances`

### Upgrade & Downgrade Execution Test Results (Disposable Database)

The migration lifecycle was executed on a temporary database (`tmpim3amer1.db`):

```text
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Running upgrade  -> 001_foundation_schema
INFO  [alembic.runtime.migration] Running upgrade 001_foundation_schema -> 002_masters_enhancement
INFO  [alembic.runtime.migration] Running upgrade 002_masters_enhancement -> 003_sales_voucher_sequences
INFO  [alembic.runtime.migration] Running upgrade 003_sales_voucher_sequences -> 004_inventory_movements_and_adjustments
INFO  [alembic.runtime.migration] Running upgrade 004_inventory_movements_and_adjustments -> 005_traditional_accounting_foundation
INFO  [alembic.runtime.migration] Running upgrade 005_traditional_accounting_foundation -> 006_financial_year_closing_and_opening_balances
INFO  [alembic.runtime.migration] Running upgrade 006_financial_year_closing_and_opening_balances -> 007_payment_and_receipt_management
Upgrade succeeded!
All 4 payment/receipt tables verified in schema!

Testing downgrade to 006_financial_year_closing_and_opening_balances...
INFO  [alembic.runtime.migration] Running downgrade 007_payment_and_receipt_management -> 006_financial_year_closing_and_opening_balances
Downgrade succeeded! Tables dropped cleanly.

Testing re-upgrade to head...
INFO  [alembic.runtime.migration] Running upgrade 006_financial_year_closing_and_opening_balances -> 007_payment_and_receipt_management
Re-upgrade succeeded!
```

---

## 4. Test Results

### 4.1 Payment Model Test Suite (`tests/traditional/test_traditional_payment_models.py`)

Ran 14 comprehensive tests covering all 15 specification requirements:

```text
tests/traditional/test_traditional_payment_models.py::test_create_all_four_models PASSED               [  7%]
tests/traditional/test_traditional_payment_models.py::test_foreign_keys_valid PASSED                   [ 14%]
tests/traditional/test_traditional_payment_models.py::test_receipt_allocation_relationship_and_cascade PASSED [ 21%]
tests/traditional/test_traditional_payment_models.py::test_payment_allocation_relationship_and_cascade PASSED [ 28%]
tests/traditional/test_traditional_payment_models.py::test_sales_invoice_allocation_reference PASSED   [ 35%]
tests/traditional/test_traditional_payment_models.py::test_nullable_future_purchase_voucher_reference PASSED [ 42%]
tests/traditional/test_traditional_payment_models.py::test_negative_amounts_rejected PASSED           [ 50%]
tests/traditional/test_traditional_payment_models.py::test_invalid_allocation_amounts_rejected PASSED  [ 57%]
tests/traditional/test_traditional_payment_models.py::test_voucher_uniqueness PASSED                  [ 64%]
tests/traditional/test_traditional_payment_models.py::test_idempotency_uniqueness PASSED              [ 71%]
tests/traditional/test_traditional_payment_models.py::test_company_and_branch_references_valid PASSED [ 78%]
tests/traditional/test_traditional_payment_models.py::test_journal_references PASSED                  [ 85%]
tests/traditional/test_traditional_payment_models.py::test_migration_upgrade_and_downgrade PASSED     [ 92%]
tests/traditional/test_traditional_payment_models.py::test_synonym_flexibility PASSED                 [100%]

============================== 14 passed in 3.20s ==============================
```

### 4.2 Full Traditional Billing Regression Suite

The entire Traditional Billing suite was executed with zero failures:
- **Total Tests Collected**: 166
- **Passed**: 166
- **Failed**: 0
- **Errors**: 0
- **Execution Time**: 37.10s

---

## 5. Purchase Integration Limitation & Forward Compatibility

1. **Current State**: Traditional Billing currently has no `PurchaseVoucher` model or `purchase_vouchers` table (owned by Friend 2).
2. **Design Strategy**:
   - In `PaymentAllocation`, `purchase_voucher_id` is defined as `Column(String(36), nullable=True, index=True)` without an active foreign key constraint.
   - `bill_number` (`String(100)`) stores vendor invoice identifiers (e.g., `"INV-VENDOR-9821"`).
   - This allows the system to record supplier payments and advance disbursements immediately.
3. **Future Introduction of Foreign Key**:
   When Friend 2 merges the `PurchaseVoucher` model and table, the foreign key constraint will be introduced via a dedicated follow-up Alembic migration:
   ```python
   # Future migration (e.g., 008_link_purchase_voucher_allocations.py)
   op.create_foreign_key(
       'fk_palloc_purchase_voucher',
       'payment_allocations', 'purchase_vouchers',
       ['purchase_voucher_id'], ['id'],
       ondelete='RESTRICT'
   )
   ```
   No existing tables, rows, or models will need to be restructured.

---

## 6. Files Modified & Git Status

### Files Modified
- [`db/traditional_models.py`](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/db/traditional_models.py): Added `synonym` import, `Company.receipts`, `Company.payments`, `SaleInvoice.receipt_allocations`, and the 4 new ORM models (`CustomerReceipt`, `ReceiptAllocation`, `SupplierPayment`, `PaymentAllocation`).
- [`traditional_migrations/versions/007_payment_and_receipt_management.py`](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/traditional_migrations/versions/007_payment_and_receipt_management.py): Created Alembic migration script for Phase 3.2.
- [`tests/traditional/test_traditional_payment_models.py`](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/tests/traditional/test_traditional_payment_models.py): Created comprehensive 14-test verification suite.
- [`PHASE_3_1_PAYMENT_RECEIPT_ARCHITECTURE.md`](file:///Users/dhvira/Documents/ANTI%20-%20MATRIX/Billing/PHASE_3_1_PAYMENT_RECEIPT_ARCHITECTURE.md): Architecture blueprint from Phase 3.1.

### Git Status Output
```text
 M db/traditional_models.py
?? PHASE_3_1_PAYMENT_RECEIPT_ARCHITECTURE.md
?? tests/traditional/test_traditional_payment_models.py
?? traditional_migrations/versions/007_payment_and_receipt_management.py
```

---

## 7. Production Database Integrity Confirmation

The SHA-256 hashes of all production database files were verified before and after test runs:

| Database File | Expected SHA-256 Hash | Actual SHA-256 Hash | Status |
| :--- | :--- | :--- | :--- |
| `data/anti_matrix_billing.db` | `bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd` | `bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd` | **Unchanged (Intact)** |
| `data/traditional_billing.db` | `0c4e5078625f3f7eef2793e86a5124966800fe7427d456f348a47ad422a57a30` | `0c4e5078625f3f7eef2793e86a5124966800fe7427d456f348a47ad422a57a30` | **Unchanged (Intact)** |
| `data/app.db` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | **Unchanged (Intact)** |

Zero writes or migrations occurred against production databases. No `.env` secrets were accessed. No commits or pushes were executed.

---

**End of Phase 3.2 Implementation Report.**
