# PHASE 2 — TRADITIONAL DOUBLE-ENTRY ACCOUNTING ENGINE
**Anti-Matrix Billing V2 — Core Backend Architecture Deliverable**  
*Date: November 16, 2026*  
*Author: Senior ERP Accounting Architect & Python Backend Engineer*

---

## 1. Executive Summary

Phase 2 of the Traditional Billing engine implementation is complete. Anti-Matrix Billing V2 now features an enterprise-grade, double-entry general ledger and financial accounting engine built exclusively for Traditional Billing (`data/traditional_billing.db`).

The engine adheres strictly to established ERP accounting and auditing standards:
- **Physical & Logical Database Isolation:** Complete separation between Fast Billing (`data/anti_matrix_billing.db`) and Traditional Billing (`data/traditional_billing.db`). No shared sessions, transactions, ORM models, or accounting tables.
- **Fundamental 5-Nature Hierarchy:** Structured account hierarchy supporting Assets, Liabilities, Equity, Income, and Expenses with hierarchical account groups and account group mappings.
- **Mathematical Double-Entry Enforcement:** Invariants enforced at both the database schema level (CHECK constraints, unique keys, foreign keys) and the Python service layer ($\sum \text{Debit} = \sum \text{Credit}$, non-negative values, two-sided line prohibition).
- **Immutable Ledger & Reversal Accounting:** Posted accounting vouchers are immutable. Edits and silent deletions are rejected; corrections execute as compensating reversal entries referencing the original voucher.
- **Period & Year Controls:** Configurable accounting periods with fail-closed posting rejection for closed periods and automatic financial year derivation (April 1 to March 31).
- **Fixed-Point Monetary Precision:** Exact `Decimal` arithmetic rounded to 2 decimal places (`ROUND_HALF_UP`) with zero floating-point imprecision.
- **Audit-Grade Financial Reporting:** Accurate backend computation engines for General Ledger, Day Book, Trial Balance, Profit & Loss Statement, Balance Sheet, Cash Book, Bank Book, Accounts Receivable (AR), and Accounts Payable (AP).
- **Strict Team Boundaries:** Delivered entirely within core backend files without modifying code assigned to Friend 1 (Sales), Friend 2 (Purchase), or Friend 3 (Configuration).

---

## 2. Existing Architecture Discovered

Before designing the accounting foundation, an architectural audit of existing Traditional models and database structures was conducted.

### 2.1 Database & Service Landscape

| Dimension | Fast Billing (POS) | Traditional Billing |
| :--- | :--- | :--- |
| **Database File** | `data/anti_matrix_billing.db` | `data/traditional_billing.db` |
| **Connection Manager** | `db/database.py` (`DatabaseManager`) | `db/traditional_database.py` (`TraditionalDatabaseManager`) |
| **Declarative Base** | `db/models.py` (`Base`) | `db/traditional_models.py` (`TraditionalBase`) |
| **Migrations Head** | `001_initial_schema` | `005_traditional_accounting_foundation` |
| **Accounting Service**| `services/accounting_service.py` | `services/traditional_accounting_service.py` |
| **Customer/Account Service** | `services/account_service.py` | `services/traditional_customer_service.py` |
| **Inventory Service** | `services/inventory_service.py` | `services/traditional_inventory_service.py` |

### 2.2 Key Invariants & Schema Discoveries
1. **Existing `accounts` Table:**  
   The existing Traditional `accounts` table in `data/traditional_billing.db` holds `id`, `company_id`, `code`, `name`, `account_type`, `phone`, `email`, `address`, `gstin`, `state`, `is_active`, `created_at`, `updated_at`.
2. **Backward Compatibility & Non-Breaking Extension:**  
   Rather than performing destructive column mutations or table rewrites on `accounts` that would break legacy migration replays, we created a dedicated `account_group_mappings` table. This allows existing services (`TraditionalCustomerService`, `TraditionalCompanyService`) to insert into `accounts` without encountering missing columns, while equipping all accounts with rich group links, natures, opening balances, and balance tracking.
3. **Single Branch `BR01` Constraint:**  
   Traditional Billing's `branches` table enforces `chk_branches_single_branch_br01` (`code = 'BR01'`) and `uq_branches_single_tenant_branch`. All journal entries validate against the authenticated company and its branch.
4. **Indian Financial Year:**  
   Company configuration defines `fin_year` (e.g. `'2026-2027'`). The accounting service automatically parses voucher dates (`YYYY-MM-DD` or `DD-MM-YYYY`) into standard Indian Financial Years (April 1 to March 31) with fallback to `company.fin_year`.

---

## 3. Files Created and Modified

### 3.1 Files Created
- `traditional_migrations/versions/005_traditional_accounting_foundation.py`  
  Alembic migration creating `account_groups`, `account_group_mappings`, `accounting_periods`, `journal_entries`, and `journal_entry_lines` tables with indexes and check constraints.
- `services/traditional_accounting_service.py`  
  Core enterprise double-entry accounting engine providing journal posting, period controls, reversal management, report generation, and module integration helpers.
- `tests/traditional/test_traditional_accounting.py`  
  Automated test suite verifying all 18 required accounting, security, and transaction scenarios.
- `PHASE_2_TRADITIONAL_ACCOUNTING_IMPLEMENTATION.md`  
  This architectural deliverable.

### 3.2 Files Modified
- `db/traditional_models.py`  
  Added ORM models `AccountGroup`, `AccountGroupMapping`, `AccountingPeriod`, `JournalEntry`, and `JournalEntryLine` with relationships on `Company` and `Account`.

---

## 4. Database Schema & Migration Details

### 4.1 Migration: `005_traditional_accounting_foundation.py`
Revision: `005`  
Revises: `004_inventory_movements_and_adjustments`  
Target: Traditional Billing SQLite database (`traditional_migrations`)

```
001_traditional_initial (rev 001)
         │
         ▼
002_masters_enhancement (rev 002)
         │
         ▼
003_sales_voucher_sequences (rev 003)
         │
         ▼
004_inventory_movements_and_adjustments (rev 004)
         │
         ▼
005_traditional_accounting_foundation (rev 005) [NEW]
```

### 4.2 Data Models

#### 1. `AccountGroup` (`account_groups`)
Stores the hierarchical tree of account groups categorized under the 5 fundamental natures.

| Column | Type | Constraints / Description |
| :--- | :--- | :--- |
| `id` | `VARCHAR(36)` | Primary Key (UUIDv4) |
| `company_id` | `VARCHAR(36)` | FK -> `companies.id`, Indexed |
| `code` | `VARCHAR(50)` | Group code (e.g. `GRP_CURR_ASSETS`, `GRP_BANK`) |
| `name` | `VARCHAR(100)` | Group display name |
| `nature` | `VARCHAR(20)` | `ASSET`, `LIABILITY`, `EQUITY`, `INCOME`, `EXPENSE` |
| `parent_group_id` | `VARCHAR(36)` | FK -> `account_groups.id` (self-referencing parent) |
| `is_system` | `BOOLEAN` | True for predefined system groups |
| `created_at` | `DATETIME` | Timestamp UTC |

**Constraints & Indexes:**
- Check: `chk_account_groups_nature`: `nature IN ('ASSET', 'LIABILITY', 'EQUITY', 'INCOME', 'EXPENSE')`
- Unique: `uq_account_groups_company_code`: `(company_id, code)`
- Index: `ix_account_groups_company`: `(company_id)`

#### 2. `AccountGroupMapping` (`account_group_mappings`)
Links ledger accounts (`accounts`) to groups, natures, and opening balances without modifying the existing `accounts` table schema.

| Column | Type | Constraints / Description |
| :--- | :--- | :--- |
| `id` | `VARCHAR(36)` | Primary Key (UUIDv4) |
| `company_id` | `VARCHAR(36)` | FK -> `companies.id`, Indexed |
| `account_id` | `VARCHAR(36)` | FK -> `accounts.id` ON DELETE CASCADE |
| `group_id` | `VARCHAR(36)` | FK -> `account_groups.id` ON DELETE CASCADE |
| `account_nature` | `VARCHAR(20)` | `ASSET`, `LIABILITY`, `EQUITY`, `INCOME`, `EXPENSE` |
| `opening_balance`| `NUMERIC(15, 2)` | Initial base opening balance |
| `opening_balance_type` | `VARCHAR(2)` | `DR` or `CR` |
| `created_at` | `DATETIME` | Timestamp UTC |
| `updated_at` | `DATETIME` | Timestamp UTC |

**Constraints & Indexes:**
- Unique: `uq_account_group_mappings_account`: `(company_id, account_id)`
- Check: `chk_agm_nature`: `account_nature IN ('ASSET', 'LIABILITY', 'EQUITY', 'INCOME', 'EXPENSE')`
- Check: `chk_agm_op_type`: `opening_balance_type IN ('DR', 'CR')`
- Index: `ix_agm_company_group`: `(company_id, group_id)`

#### 3. `AccountingPeriod` (`accounting_periods`)
Controls posting permissions for specific calendar and fiscal windows.

| Column | Type | Constraints / Description |
| :--- | :--- | :--- |
| `id` | `VARCHAR(36)` | Primary Key (UUIDv4) |
| `company_id` | `VARCHAR(36)` | FK -> `companies.id`, Indexed |
| `financial_year` | `VARCHAR(20)` | E.g. `'2026-2027'` |
| `period_name` | `VARCHAR(50)` | E.g. `'APRIL-2026'`, `'Q1-2026'` |
| `start_date` | `VARCHAR(10)` | YYYY-MM-DD |
| `end_date` | `VARCHAR(10)` | YYYY-MM-DD |
| `is_closed` | `BOOLEAN` | If True, journal posting in date window is rejected |
| `closed_at` | `DATETIME` | Timestamp when period was closed |
| `closed_by` | `VARCHAR(36)` | FK -> `users.id` |
| `created_at` | `DATETIME` | Timestamp UTC |
| `updated_at` | `DATETIME` | Timestamp UTC |

**Constraints & Indexes:**
- Unique: `uq_accounting_periods_company_fy_name`: `(company_id, financial_year, period_name)`
- Check: `chk_accounting_periods_dates`: `start_date <= end_date`
- Index: `ix_accounting_periods_company_dates`: `(company_id, start_date, end_date)`

#### 4. `JournalEntry` (`journal_entries`)
Represents the header of an atomic double-entry accounting transaction.

| Column | Type | Constraints / Description |
| :--- | :--- | :--- |
| `id` | `VARCHAR(36)` | Primary Key (UUIDv4) |
| `company_id` | `VARCHAR(36)` | FK -> `companies.id`, Indexed |
| `branch_id` | `VARCHAR(36)` | FK -> `branches.id`, Indexed |
| `financial_year` | `VARCHAR(20)` | E.g. `'2026-2027'`, Indexed |
| `voucher_number` | `VARCHAR(50)` | Document number (e.g. `JV-SALES-001`) |
| `voucher_type` | `VARCHAR(30)` | `JOURNAL`, `SALES`, `PURCHASE`, `PAYMENT`, `RECEIPT`, `CONTRA`, `REVERSAL`, `OPENING` |
| `voucher_date` | `VARCHAR(10)` | YYYY-MM-DD, Indexed |
| `narration` | `TEXT` | Header remarks |
| `total_debit` | `NUMERIC(15, 2)` | Sum of debits (`> 0`) |
| `total_credit` | `NUMERIC(15, 2)` | Sum of credits (`== total_debit`) |
| `status` | `VARCHAR(20)` | `POSTED`, `REVERSED`, `DRAFT` |
| `reference_type` | `VARCHAR(50)` | E.g. `SALES_INVOICE`, `PURCHASE_BILL` |
| `reference_id` | `VARCHAR(100)` | ID of source business document |
| `reversal_of_id` | `VARCHAR(36)` | FK -> `journal_entries.id` (if this is a reversal) |
| `reversed_by_id` | `VARCHAR(36)` | FK -> `journal_entries.id` (reversal voucher pointer) |
| `reversal_reason`| `TEXT` | Mandatory explanation for reversal |
| `idempotency_key`| `VARCHAR(128)` | Unique key to prevent duplicate posting |
| `posted_by` | `VARCHAR(36)` | FK -> `users.id` |
| `created_at` | `DATETIME` | Timestamp UTC |
| `updated_at` | `DATETIME` | Timestamp UTC |

**Constraints & Indexes:**
- Check: `chk_journal_entries_total_balanced`: `total_debit = total_credit`
- Check: `chk_journal_entries_total_positive`: `total_debit > 0`
- Check: `chk_journal_entries_status`: `status IN ('DRAFT', 'POSTED', 'REVERSED')`
- Unique: `uq_journal_entries_scope_vch`: `(company_id, branch_id, financial_year, voucher_type, voucher_number)`
- Unique: `uq_journal_entries_idempotency`: `(company_id, idempotency_key)`
- Index: `ix_journal_entries_company_date`: `(company_id, voucher_date)`
- Index: `ix_journal_entries_ref`: `(company_id, reference_type, reference_id)`

#### 5. `JournalEntryLine` (`journal_entry_lines`)
Individual debit and credit postings comprising the journal.

| Column | Type | Constraints / Description |
| :--- | :--- | :--- |
| `id` | `VARCHAR(36)` | Primary Key (UUIDv4) |
| `journal_id` | `VARCHAR(36)` | FK -> `journal_entries.id` ON DELETE CASCADE, Indexed |
| `company_id` | `VARCHAR(36)` | FK -> `companies.id`, Indexed |
| `line_number` | `INTEGER` | 1-based sequential line index |
| `account_id` | `VARCHAR(36)` | FK -> `accounts.id` ON DELETE RESTRICT, Indexed |
| `debit` | `NUMERIC(15, 2)` | Debit amount (`>= 0`) |
| `credit` | `NUMERIC(15, 2)` | Credit amount (`>= 0`) |
| `narration` | `TEXT` | Line-level remarks |
| `party_type` | `VARCHAR(30)` | `CUSTOMER`, `SUPPLIER`, `EMPLOYEE`, `NONE` |
| `party_id` | `VARCHAR(36)` | Associated party identifier |
| `created_at` | `DATETIME` | Timestamp UTC |

**Constraints & Indexes:**
- Check: `chk_jlines_debit_non_neg`: `debit >= 0`
- Check: `chk_jlines_credit_non_neg`: `credit >= 0`
- Check: `chk_jlines_one_side_nonzero`: `((debit > 0 AND credit == 0) OR (credit > 0 AND debit == 0))`
- Unique: `uq_journal_entry_lines_journal_line`: `(journal_id, line_number)`
- Index: `ix_jlines_company_account`: `(company_id, account_id, created_at)`

---

## 5. Account Hierarchy & Chart of Accounts Design

### 5.1 The 5 Root Account Natures

```
ACCOUNT HIERARCHY
├── 1. ASSET (Normal Balance: DEBIT)
│   ├── GRP_CURR_ASSETS (Current Assets)
│   │   ├── GRP_CASH (Cash-in-Hand) ──> [CASH]
│   │   ├── GRP_BANK (Bank Accounts) ──> [HDFC, SBI]
│   │   ├── GRP_SUNDRY_DEBTORS (Receivables) ──> [Customers]
│   │   ├── GRP_STOCK (Stock-in-Hand) ──> [STOCK_IN_HAND]
│   │   ├── GRP_INPUT_GST (Input Duties & Taxes) ──> [INPUT_CGST, INPUT_SGST, INPUT_IGST]
│   │   └── GRP_LOANS_ADV (Loans & Advances)
│   └── GRP_FIXED_ASSETS (Fixed Assets)
│       └── [Equipment, Furniture, Vehicles]
│
├── 2. LIABILITY (Normal Balance: CREDIT)
│   ├── GRP_CURR_LIAB (Current Liabilities)
│   │   ├── GRP_SUNDRY_CREDITORS (Payables) ──> [Suppliers]
│   │   ├── GRP_OUTPUT_GST (Output Duties & Taxes) ──> [OUTPUT_CGST, OUTPUT_SGST, OUTPUT_IGST]
│   │   ├── GRP_DUTIES_TAXES (Taxes Payable)
│   │   └── GRP_PROVISIONS (Provisions)
│   └── GRP_LOANS_LIAB (Loans & Borrowings)
│       └── GRP_BANK_OD (Bank OD / CC Accounts)
│
├── 3. EQUITY (Normal Balance: CREDIT)
│   ├── GRP_CAPITAL (Capital Account)
│   └── GRP_RESERVES (Reserves & Surplus)
│       └── GRP_RETAINED_EARNINGS ──> [RETAINED_EARNINGS]
│
├── 4. INCOME (Normal Balance: CREDIT)
│   ├── GRP_SALES (Sales Accounts) ──> [SALES, Interstate Sales]
│   ├── GRP_DIRECT_INCOME (Direct Income)
│   └── GRP_INDIRECT_INCOME (Discounts Received, Interest)
│
└── 5. EXPENSE (Normal Balance: DEBIT)
    ├── GRP_PURCHASE (Purchase Accounts) ──> [PURCHASE]
    ├── GRP_DIRECT_EXPENSES (Freight, Cartage, Wages)
    └── GRP_INDIRECT_EXPENSES (Rent, Salaries, Electricity, ROUND_OFF)
```

---

## 6. Double-Entry Posting & Reversal Design

### 6.1 Posting Pipeline
When `post_journal_entry` is invoked:
1. **Idempotency Guard:** If an `idempotency_key` is supplied, checks for prior submission. If found, returns existing journal without side effects.
2. **Tenant Context Verification:** Verifies that `company_id` and `branch_id` exist and match the tenant boundary.
3. **Period Control Guard:** Evaluates `voucher_date` against `accounting_periods`. If any closed period matches `start_date <= voucher_date <= end_date`, raises `ClosedPeriodError`.
4. **Line Validation:**
   - Requires $\ge 2$ lines (raises `InsufficientJournalLinesError`).
   - Verifies each `account_id` belongs to `company_id` (raises `AccountNotFoundError`).
   - Verifies `debit >= 0` and `credit >= 0`.
   - Rejects lines with both `debit > 0` and `credit > 0`, or both `== 0` (raises `InvalidJournalAmountError`).
5. **Double-Entry Equilibrium Check:**
   $$\sum \text{Debit} = \sum \text{Credit}$$
   If $\sum \text{Debit} \neq \sum \text{Credit}$, rejects with `UnbalancedJournalError`. The service **never** invents balancing lines.
6. **Atomic Transaction Write:**
   Inserts `JournalEntry` and `JournalEntryLine` records, generates sequential voucher number if needed, logs an `AuditLog` event (`JOURNAL_POSTED`), and commits within `session_scope()`.

### 6.2 Reversal Pipeline
To enforce accounting auditability, journals cannot be deleted or silently modified:
1. Validates that target journal is in `POSTED` status (cannot reverse `DRAFT` or already `REVERSED` entries).
2. Generates an inverse compensating journal:
   - For every line in original entry: `new_debit = old_credit` and `new_credit = old_debit`.
   - `voucher_type = 'REVERSAL'`
   - `voucher_number = f"REV-{orig.voucher_number}"`
   - `reference_type = 'JOURNAL_ENTRY'` and `reference_id = orig.id`
3. Sets original journal status to `REVERSED`, sets `reversed_by_id = rev.id`, records `reversal_reason`.
4. Both original and reversal entries remain on the immutable double-entry ledger, exactly canceling out to zero net balance.

---

## 7. Accounting Service Methods & Signatures

Located in `services/traditional_accounting_service.py`, instantiated as singleton `traditional_accounting_service`.

```python
class TraditionalAccountingService:
    # --------------------------------------------------------------------------
    # Chart of Accounts & Groups
    # --------------------------------------------------------------------------
    def ensure_standard_account_groups(self, company_id: str, session: Optional[Session] = None) -> List[Dict[str, Any]]
    def ensure_standard_accounts(self, company_id: str, session: Optional[Session] = None) -> List[Dict[str, Any]]
    def create_account_group(self, company_id: str, code: str, name: str, nature: str, parent_group_code: Optional[str] = None, session: Optional[Session] = None) -> Dict[str, Any]
    def create_account(self, company_id: str, code: str, name: str, group_code: str, account_type: Optional[str] = None, opening_balance: Decimal = Decimal('0.00'), opening_balance_type: str = 'DR', ...) -> Dict[str, Any]
    def get_chart_of_accounts(self, company_id: str, session: Optional[Session] = None) -> List[Dict[str, Any]]

    # --------------------------------------------------------------------------
    # Period & Fiscal Year Controls
    # --------------------------------------------------------------------------
    def derive_financial_year(vch_date_str: Optional[str] = None, fallback_fy: Optional[str] = None) -> str
    def create_accounting_period(self, company_id: str, financial_year: str, period_name: str, start_date: str, end_date: str, session: Optional[Session] = None) -> Dict[str, Any]
    def close_accounting_period(self, company_id: str, period_id_or_name: str, user_id: Optional[str] = None, session: Optional[Session] = None) -> Dict[str, Any]
    def reopen_accounting_period(self, company_id: str, period_id_or_name: str, user_id: Optional[str] = None, session: Optional[Session] = None) -> Dict[str, Any]
    def validate_period_is_open(self, company_id: str, voucher_date: str, session: Session) -> None

    # --------------------------------------------------------------------------
    # Journal Operations
    # --------------------------------------------------------------------------
    def post_journal_entry(self, company_id: str, branch_id: str, voucher_type: str, voucher_date: str, lines: List[Dict[str, Any]], voucher_number: Optional[str] = None, narration: Optional[str] = None, reference_type: Optional[str] = None, reference_id: Optional[str] = None, idempotency_key: Optional[str] = None, financial_year: Optional[str] = None, posted_by: Optional[str] = None, session: Optional[Session] = None) -> Dict[str, Any]
    def reverse_journal_entry(self, company_id: str, journal_id: str, reversal_reason: str, reversal_date: Optional[str] = None, user_id: Optional[str] = None, session: Optional[Session] = None) -> Dict[str, Any]
    def delete_journal_entry(self, company_id: str, journal_id: str, session: Optional[Session] = None) -> bool

    # --------------------------------------------------------------------------
    # Financial Reports
    # --------------------------------------------------------------------------
    def get_general_ledger(self, company_id: str, account_id: str, branch_id: Optional[str] = None, financial_year: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, session: Optional[Session] = None) -> Dict[str, Any]
    def get_day_book(self, company_id: str, branch_id: Optional[str] = None, date: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, session: Optional[Session] = None) -> List[Dict[str, Any]]
    def get_trial_balance(self, company_id: str, branch_id: Optional[str] = None, financial_year: Optional[str] = None, as_of_date: Optional[str] = None, session: Optional[Session] = None) -> Dict[str, Any]
    def get_profit_and_loss(self, company_id: str, branch_id: Optional[str] = None, financial_year: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, session: Optional[Session] = None) -> Dict[str, Any]
    def get_balance_sheet(self, company_id: str, branch_id: Optional[str] = None, financial_year: Optional[str] = None, as_of_date: Optional[str] = None, session: Optional[Session] = None) -> Dict[str, Any]
    def get_cash_book(self, company_id: str, branch_id: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, session: Optional[Session] = None) -> Dict[str, Any]
    def get_bank_book(self, company_id: str, branch_id: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, account_id: Optional[str] = None, session: Optional[Session] = None) -> Dict[str, Any]
    def get_receivables_report(self, company_id: str, branch_id: Optional[str] = None, as_of_date: Optional[str] = None, session: Optional[Session] = None) -> Dict[str, Any]
    def get_payables_report(self, company_id: str, branch_id: Optional[str] = None, as_of_date: Optional[str] = None, session: Optional[Session] = None) -> Dict[str, Any]

    # --------------------------------------------------------------------------
    # Integration Blueprints
    # --------------------------------------------------------------------------
    def record_sales_journal(self, company_id: str, branch_id: str, invoice_id: str, invoice_number: str, invoice_date: str, customer_account_id: str, sales_amount: Decimal, output_cgst: Decimal = Decimal('0.00'), output_sgst: Decimal = Decimal('0.00'), output_igst: Decimal = Decimal('0.00'), round_off: Decimal = Decimal('0.00'), is_cash_sale: bool = False, ...) -> Dict[str, Any]
    def record_purchase_journal(self, company_id: str, branch_id: str, bill_id: str, bill_number: str, bill_date: str, supplier_account_id: str, purchase_amount: Decimal, input_cgst: Decimal = Decimal('0.00'), input_sgst: Decimal = Decimal('0.00'), input_igst: Decimal = Decimal('0.00'), round_off: Decimal = Decimal('0.00'), is_cash_purchase: bool = False, ...) -> Dict[str, Any]
    def record_customer_receipt(self, company_id: str, branch_id: str, receipt_number: str, receipt_date: str, customer_account_id: str, cash_or_bank_account_id: str, amount: Decimal, discount_amount: Decimal = Decimal('0.00'), ...) -> Dict[str, Any]
    def record_supplier_payment(self, company_id: str, branch_id: str, payment_number: str, payment_date: str, supplier_account_id: str, cash_or_bank_account_id: str, amount: Decimal, discount_amount: Decimal = Decimal('0.00'), ...) -> Dict[str, Any]
```

---

## 8. Report Calculation Methodology

1. **General Ledger:**
   - **Opening Balance:** Base opening balance plus net debits minus credits for all posted transactions dated $< \text{start\_date}$.
   - **Chronological Entries:** Filters transactions between $\text{start\_date}$ and $\text{end\_date}$, computing running balance line-by-line.
   - **Closing Balance:** Running balance at final entry with `Dr` or `Cr` designation.
2. **Trial Balance:**
   - Computes net balance for all active accounts up to `as_of_date`.
   - Populates two columns: `debit` (if net Dr $> 0$) and `credit` (if net Cr $> 0$).
   - Sums all debits and credits; asserts $\text{difference} == 0.00$ and `is_balanced == True`.
3. **Profit & Loss Statement:**
   - Restricts to accounts classified under `INCOME` and `EXPENSE`.
   - $\text{Total Income} = \sum (\text{Credits} - \text{Debits})$ across all `INCOME` accounts.
   - $\text{Total Expense} = \sum (\text{Debits} - \text{Credits})$ across all `EXPENSE` accounts.
   - $\text{Net Profit} = \text{Total Income} - \text{Total Expense}$.
4. **Balance Sheet:**
   - Aggregates `ASSET`, `LIABILITY`, and `EQUITY` accounts.
   - Adds $\text{Net Profit for Period}$ computed from P&L up to `as_of_date` to Equity.
   - Verifies the fundamental accounting balance:
     $$\text{Total Assets} = \text{Total Liabilities} + \text{Total Equity} + \text{Net Profit}$$
5. **Receivables & Payables Outstandings:**
   - Dynamically calculates ledger balances for all Sundry Debtors (Customers) and Sundry Creditors (Suppliers), reporting billed amounts, collected amounts, and current net outstanding.

---

## 9. Integration Blueprints for Assigned Team Members

Per team task ownership boundaries, no code in Friend 1 (Sales), Friend 2 (Purchase), or Friend 3 (Configuration) was edited. Below are the documented integration contracts.

### 9.1 Friend 1 — Sales Integration Blueprint

When finalizing a Traditional sales invoice:

```python
from decimal import Decimal
from services.traditional_accounting_service import traditional_accounting_service

def post_sales_invoice_to_accounts(session, company_id: str, branch_id: str, invoice_data: dict, user_id: str):
    """
    Called within the Sales invoice database transaction scope.
    Enlists the accounting journal in the active caller session.
    """
    journal = traditional_accounting_service.record_sales_journal(
        company_id=company_id,
        branch_id=branch_id,
        invoice_id=invoice_data["id"],
        invoice_number=invoice_data["voucher_number"],
        invoice_date=invoice_data["vch_date"],
        customer_account_id=invoice_data["account_id"],
        sales_amount=Decimal(str(invoice_data["taxable_amount"])),
        output_cgst=Decimal(str(invoice_data.get("cgst_amount", 0))),
        output_sgst=Decimal(str(invoice_data.get("sgst_amount", 0))),
        output_igst=Decimal(str(invoice_data.get("igst_amount", 0))),
        round_off=Decimal(str(invoice_data.get("round_off_amount", 0))),
        is_cash_sale=(invoice_data.get("payment_method") == "CASH"),
        user_id=user_id,
        session=session,  # Enlist in Sales transaction
    )
    return journal
```

When receiving payment from customer:

```python
def record_customer_payment_receipt(session, company_id: str, branch_id: str, receipt_data: dict, user_id: str):
    """Posts customer receipt crediting Accounts Receivable."""
    return traditional_accounting_service.record_customer_receipt(
        company_id=company_id,
        branch_id=branch_id,
        receipt_number=receipt_data["receipt_number"],
        receipt_date=receipt_data["date"],
        customer_account_id=receipt_data["customer_account_id"],
        cash_or_bank_account_id=receipt_data["bank_or_cash_account_id"],
        amount=Decimal(str(receipt_data["amount"])),
        discount_amount=Decimal(str(receipt_data.get("discount", 0))),
        idempotency_key=f"REC:{receipt_data['receipt_number']}",
        user_id=user_id,
        session=session,
    )
```

---

### 9.2 Friend 2 — Purchase Integration Blueprint

When finalizing a Traditional purchase bill:

```python
from decimal import Decimal
from services.traditional_accounting_service import traditional_accounting_service

def post_purchase_bill_to_accounts(session, company_id: str, branch_id: str, bill_data: dict, user_id: str):
    """
    Called within the Purchase bill database transaction scope.
    Enlists the accounting journal in the active caller session.
    """
    journal = traditional_accounting_service.record_purchase_journal(
        company_id=company_id,
        branch_id=branch_id,
        bill_id=bill_data["id"],
        bill_number=bill_data["voucher_number"],
        bill_date=bill_data["bill_date"],
        supplier_account_id=bill_data["supplier_account_id"],
        purchase_amount=Decimal(str(bill_data["taxable_amount"])),
        input_cgst=Decimal(str(bill_data.get("cgst_amount", 0))),
        input_sgst=Decimal(str(bill_data.get("sgst_amount", 0))),
        input_igst=Decimal(str(bill_data.get("igst_amount", 0))),
        round_off=Decimal(str(bill_data.get("round_off_amount", 0))),
        is_cash_purchase=(bill_data.get("payment_type") == "CASH"),
        user_id=user_id,
        session=session,  # Enlist in Purchase transaction
    )
    return journal
```

When disbursing payment to supplier:

```python
def record_supplier_payment_disbursement(session, company_id: str, branch_id: str, payment_data: dict, user_id: str):
    """Posts supplier payment debiting Accounts Payable."""
    return traditional_accounting_service.record_supplier_payment(
        company_id=company_id,
        branch_id=branch_id,
        payment_number=payment_data["payment_number"],
        payment_date=payment_data["date"],
        supplier_account_id=payment_data["supplier_account_id"],
        cash_or_bank_account_id=payment_data["bank_or_cash_account_id"],
        amount=Decimal(str(payment_data["amount"])),
        discount_amount=Decimal(str(payment_data.get("discount", 0))),
        idempotency_key=f"PAY:{payment_data['payment_number']}",
        user_id=user_id,
        session=session,
    )
```

---

## 10. Verification & Test Execution Results

All 18 targeted accounting engine tests, 114 traditional regression tests, and all 8 frontend test suites were executed with 100% pass rates.

### 10.1 Targeted Accounting Engine Tests (`tests/traditional/test_traditional_accounting.py`)
Ran: `.venv/bin/pytest tests/traditional/test_traditional_accounting.py -v`  
**Result: 18 passed in 4.01s (100% PASS)**

| Test Scenario | Status | Description |
| :--- | :---: | :--- |
| `test_account_creation_and_hierarchy` | PASSED | Group hierarchy under 5 root natures; custom accounts created and mapped. |
| `test_company_isolation` | PASSED | Cross-company account usage rejected (`AccountNotFoundError`). |
| `test_valid_balanced_journal_posting` | PASSED | Posts balanced entry, verifies line count, balances, and audit log. |
| `test_rejection_of_unbalanced_journals` | PASSED | Unbalanced entries rejected (`UnbalancedJournalError`), no partial commit. |
| `test_rejection_of_negative_and_invalid_amounts`| PASSED | Rejects negative debits/credits, two-sided lines, and $< 2$ lines. |
| `test_duplicate_posting_prevention` | PASSED | Identical idempotency key returns existing journal without double-posting. |
| `test_reversal_entries` | PASSED | Reversal generates inverse compensating journal; restores balances to 0. |
| `test_closed_period_restrictions` | PASSED | Posting in closed period blocked (`ClosedPeriodError`); reopening permits posting. |
| `test_general_ledger_calculations` | PASSED | Exact opening, chronological movements, and running balance calculation. |
| `test_trial_balance_calculations` | PASSED | Verifies total debit equals total credit ($\text{difference} == 0.00$). |
| `test_profit_and_loss_calculations` | PASSED | Verifies Income $-$ Expenses $=$ Net Profit. |
| `test_balance_sheet_calculations` | PASSED | Verifies $\text{Assets} = \text{Liabilities} + \text{Equity} + \text{Net Profit}$. |
| `test_cash_and_bank_book_calculations` | PASSED | Cash Book and Bank Book statements calculate opening, entries, and closing. |
| `test_receivable_and_payable_calculations` | PASSED | Calculates customer outstandings (AR) and supplier outstandings (AP). |
| `test_transaction_rollback` | PASSED | Error midway rolls back entire transaction, leaving database intact. |
| `test_concurrent_posting_safety` | PASSED | 5 threads $\times$ 4 postings = 20 entries concurrently; Trial Balance balanced. |
| `test_database_isolation_fast_vs_traditional` | PASSED | Traditional accounting operations leave Fast DB file completely untouched. |
| `test_migration_upgrade_and_downgrade` | PASSED | Full Alembic migration lifecycle from 004 to 005 and back to 004. |

### 10.2 Full Traditional Backend Suite (`tests/traditional/`)
Ran: `.venv/bin/pytest tests/traditional/ -v`  
**Result: 132 passed in 27.64s (100% PASS)**

### 10.3 Frontend Suites (`node tests/*.js`)
Ran all 8 JavaScript integration suites:
- `test_mode_aware_company_loading.js` (8/8 PASSED)
- `test_traditional_account_master_frontend.js` (3/3 PASSED)
- `test_traditional_continuous_product_entry.js` (7/7 PASSED)
- `test_traditional_dashboard_frontend.js` (5/5 PASSED)
- `test_traditional_modify_product_navigation.js` (5/5 PASSED)
- `test_traditional_recovery_frontend.js` (6/6 PASSED)
- `test_traditional_sales_pricing_frontend.js` (10/10 PASSED)
- `test_traditional_wide_autocomplete_frontend.js` (5/5 PASSED)  
**Total Frontend Assertions: 49/49 PASSED (100%)**

---

## 11. Production Database Integrity & Hash Verification

Both production database files were verified before and after test execution to guarantee zero data alteration:

```bash
$ shasum -a 256 data/anti_matrix_billing.db data/traditional_billing.db
bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd  data/anti_matrix_billing.db
0c4e5078625f3f7eef2793e86a5124966800fe7427d456f348a47ad422a57a30  data/traditional_billing.db
```

- `data/anti_matrix_billing.db`: **IDENTICAL** (`bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd`)
- `data/traditional_billing.db`: **IDENTICAL** (`0c4e5078625f3f7eef2793e86a5124966800fe7427d456f348a47ad422a57a30`)

---

## 12. Final Git Status

```bash
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
	modified:   .gitignore
	modified:   app.js
	modified:   db/traditional_models.py
	modified:   desktop/web_bridge.py
	modified:   index.html
	modified:   tests/conftest.py
	modified:   tests/test_enterprise_erp_backend.py
	modified:   tests/test_fast_billing_ui_enhancements.py
	modified:   tests/test_product_selection_and_management.py
	modified:   tests/test_separate_traditional_and_fast_billing.py

Untracked files:
	PHASE_1_TRADITIONAL_INVENTORY_IMPLEMENTATION.md
	PHASE_2_TRADITIONAL_ACCOUNTING_IMPLEMENTATION.md
	TEAM_DEVELOPMENT_OWNERSHIP_AND_INTEGRATION.md
	scripts/provision_traditional_recovery_token.py
	services/traditional_accounting_service.py
	services/traditional_inventory_service.py
	services/traditional_recovery_service.py
	services/traditional_recovery_token.py
	tests/test_traditional_recovery_frontend.js
	tests/traditional/test_traditional_accounting.py
	tests/traditional/test_traditional_inventory.py
	tests/traditional/test_traditional_recovery.py
	traditional_migrations/versions/004_inventory_movements_and_adjustments.py
	traditional_migrations/versions/005_traditional_accounting_foundation.py

no changes added to commit (use "git add" and/or "git commit -a")
```

---

## 13. Known Constraints & Outstanding Decisions

1. **Single-Branch Model:**  
   Like inventory, branch accounting currently maps to the single operational branch `BR01` enforced by `chk_branches_single_branch_br01`. The schema and service fully support multi-branch filtering whenever multi-branch support is unlocked.
2. **Opening Balance Equity Offsetting:**  
   Opening balances entered for individual accounts currently contribute to the Trial Balance as net debit or credit. For full financial closure, an explicit Opening Balance Journal or Opening Balance Equity account should offset net differences during first-time migration.
3. **Friend 1 & Friend 2 Integration:**  
   The integration helper methods (`record_sales_journal`, `record_purchase_journal`, etc.) are ready to be called by Friend 1 and Friend 2 by importing `traditional_accounting_service` from `services.traditional_accounting_service`.
