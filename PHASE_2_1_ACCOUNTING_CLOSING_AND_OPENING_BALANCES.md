# PHASE 2.1 — TRADITIONAL BILLING ACCOUNTING OPENING BALANCES AND YEAR-END CLOSING

**Project:** Anti-Matrix Billing V2  
**Role:** Senior ERP Backend Architect & Core Engineering  
**Module:** Traditional Billing Accounting Foundation (Phase 2.1 Extension)  
**Status:** Complete & Verified  

---

## 1. Executive Summary & Architecture Overview

Phase 2.1 extends the Phase 2 Traditional Double-Entry Accounting Foundation in Anti-Matrix Billing V2 by delivering an enterprise-grade financial year lifecycle engine. It introduces:

1. **Controlled Opening Balance Workflow:** Secure, authorized entry of initial ledger balances for eligible permanent accounts (Assets, Liabilities, Equity), automatic balancing using `OPENING_BALANCE_EQUITY` (`GRP_RESERVES`), strict rejection of nominal accounts, and complete reversal capability.
2. **Authoritative Single-Source Accounting Treatment:** Elimination of balance double-counting between posted opening journal entries and `AccountGroupMapping` metadata across all financial reports (Trial Balance, General Ledger, Day Book, Balance Sheet).
3. **Automated Financial-Year Closing Service:** Calculation of exact operational Net Profit / Loss for the fiscal year, generation of balanced closing journal entries (`voucher_type = 'YEAR_END_CLOSING'`) zeroing nominal accounts (Income and Expense) to `0.00` and transferring Net Profit (Credit) or Net Loss (Debit) directly to `RETAINED_EARNINGS` (Equity).
4. **Controlled Reopening Engine:** Authorized reversal of year-end closing entries, rolling back subsequent carry-forwards, resetting closing status to `REOPENED`, and restoring operational ledger balances.
5. **Next-Year Opening Carry-Forward Engine:** Automated rollover of permanent account closing balances from a closed fiscal year into a balanced opening journal (`voucher_type = 'OPENING'`) for the consecutive financial year.
6. **Physical Database & Tenant Separation:** Full compliance with the dual-database architecture (`data/traditional_billing.db` vs `data/anti_matrix_billing.db`), tenant isolation, exact `Decimal` precision (`ROUND_HALF_UP`), and strict database immutability.

---

## 2. Controlled Opening Balance Workflow

### 2.1 Permanent Account Eligibility & Nominal Account Rejection
Opening balances establish the starting financial position of a company for a financial year. In accordance with standard accounting principles:
- **Eligible Accounts:** Only permanent balance sheet accounts (`ASSET`, `LIABILITY`, and `EQUITY`) are permitted to carry opening balances.
- **Strict Nominal Rejection:** Any submission containing `INCOME` (e.g. Sales, Service Income) or `EXPENSE` (e.g. Purchases, Rent, Electricity) accounts is immediately rejected with `TraditionalAccountingError`.

### 2.2 Directional Treatment and Automatic Balancing
- **Assets:** Default opening balance direction is `DR` (Debit). Positive balances are recorded as journal debits; abnormal credit balances are recorded as credits.
- **Liabilities & Equity:** Default opening balance direction is `CR` (Credit). Positive balances are recorded as journal credits; abnormal debit balances are recorded as debits.
- **Automated Balancing:** When the submitted total debits do not equal total credits:
  $$\text{Difference} = |\text{Total Debits} - \text{Total Credits}|$$
  The engine automatically generates an offsetting line using the dedicated standard equity account `OPENING_BALANCE_EQUITY` (`GRP_RESERVES`):
  - If $\text{Total Debits} > \text{Total Credits}$: `OPENING_BALANCE_EQUITY` is credited by the difference.
  - If $\text{Total Credits} > \text{Total Debits}$: `OPENING_BALANCE_EQUITY` is debited by the difference.
  - If $\text{Total Debits} == \text{Total Credits}$: No offset line is generated; the opening journal contains only the submitted accounts.

### 2.3 Security, Atomicity, and Deduplication Guards
- **Explicit Authorization Guard:** Posting opening balances is a sensitive operation. `authorization_confirmed=True` is strictly required. Any call with `authorization_confirmed=False` raises `UnauthorizedAccountingActionError` (subclassing both `TraditionalAccountingError` and Python's built-in `PermissionError`).
- **Closed Financial Year Guard:** Posting opening balances to an already closed financial year is strictly blocked (`FinancialYearClosedError`).
- **Duplicate Prevention:** A company can have only one active posted opening journal per financial year. Subsequent attempts raise `DuplicateJournalError`.
- **Zero/Empty Submission Rejection:** Submissions that are empty or contain only zero amounts are rejected (`TraditionalAccountingError`).
- **Accounting Period Validation:** The voucher date (defaulting to the first day of the fiscal year, e.g. `2026-04-01`) is checked against all closed accounting periods.

### 2.4 Opening Balance Reversal Workflow
Posted opening journals are strictly immutable and cannot be deleted (`ImmutableJournalError`). To correct erroneous opening entries:
1. `reverse_opening_balances(company_id, financial_year, reversal_reason, authorization_confirmed=True)` is called.
2. The active opening journal is marked `REVERSED`.
3. An inverse compensating reversal voucher (`REV-OP-{financial_year}`) is posted.
4. `AccountGroupMapping.opening_balance` metadata for the involved accounts is reset to `0.00`.
5. An audit log entry (`OPENING_JOURNAL_REVERSED`) is recorded with full user and reason details.

---

## 3. Financial-Year Closing Engine

### 3.1 Operational Net Profit / Loss Calculation
The closing service executes year-end settlement without mutating or destroying operational reporting:
- P&L calculation queries all operational income credits and expense debits within the financial year, strictly filtering out any `YEAR_END_CLOSING` vouchers (`JournalEntry.voucher_type != 'YEAR_END_CLOSING'`).
- Net Profit / Loss is computed as:
  $$\text{Net Profit} = \sum \text{Income Credits} - \sum \text{Income Debits} - \left( \sum \text{Expense Debits} - \sum \text{Expense Credits} \right)$$
- If $\text{Net Profit} \ge 0$, `is_profit = True`; otherwise `is_profit = False`.

### 3.2 Closing Journal Generation (`voucher_type = 'YEAR_END_CLOSING'`)
A balanced closing journal entry (`CLS-{financial_year}`) is generated on the fiscal year-end date (e.g. `2027-03-31`):
1. **Income Accounts:** For each Income account with a credit balance, a Debit line of equal amount is created.
2. **Expense Accounts:** For each Expense account with a debit balance, a Credit line of equal amount is created.
3. **Retained Earnings Transfer:**
   - If Net Profit $> 0$: `RETAINED_EARNINGS` is credited with the profit amount.
   - If Net Loss $> 0$: `RETAINED_EARNINGS` is debited with the loss amount.
4. **Double-Entry Equilibrium:** Total debits in the closing journal exactly equal total credits.
5. **Ledger Result:** Post-closing, all nominal accounts have an exact ending balance of `0.00`, while `RETAINED_EARNINGS` incorporates the net profit or loss.

### 3.3 Closing State Record & Double-Closing Rejection
A record is atomically created or updated in the `financial_year_closings` table:
- `company_id`, `branch_id`, `financial_year`, `closing_date`, `closing_journal_id`, `net_profit`, `status='CLOSED'`, `closed_by`.
- Subsequent attempts to close an already closed financial year are rejected with `FinancialYearClosedError`.

### 3.4 Controlled Financial-Year Reopening
When audits or corrections require reopening a closed fiscal year:
1. `reopen_financial_year(company_id, financial_year, reopen_reason, authorization_confirmed=True)` verifies the year is currently `CLOSED`.
2. If next year's carry-forward opening journal exists (`next_opening_journal_id`), it is automatically reversed first to preserve inter-year integrity.
3. The year-end closing journal entry is marked `REVERSED` and compensated with an inverse journal.
4. `FinancialYearClosing.status` is updated to `'REOPENED'`, `reopened_at` is set, and `reopen_reason` is stored.
5. Nominal account balances are restored to their operational states in the General Ledger and Trial Balance.
6. An audit log entry (`FINANCIAL_YEAR_REOPENED`) is recorded.

---

## 4. Next-Year Opening Carry-Forward Engine

Permanent accounts must roll forward into the subsequent financial year:
1. `carry_forward_to_next_financial_year(company_id, current_financial_year, next_financial_year=None, ...)` requires authorization and verifies `current_financial_year` is `CLOSED`.
2. Extracts permanent account ending balances (Asset, Liability, Equity with updated Retained Earnings) as of the closing date.
3. Nominal accounts (Income and Expense) are strictly zeroed out and are NOT carried forward.
4. Posts a balanced opening journal for the next financial year:
   - `voucher_type = 'OPENING'`
   - `voucher_number = f"OP-{next_financial_year}"`
   - `voucher_date = f"{next_financial_year_start}-04-01"`
5. Updates `FinancialYearClosing.next_opening_journal_id` to establish bidirectional traceability.
6. Updates `AccountGroupMapping` opening balance metadata for the accounts in the new year.
7. Total debits and total credits in the carried-forward journal are guaranteed equal ($\text{Assets} = \text{Liabilities} + \text{Equity}$).

---

## 5. Authoritative Double-Counting Elimination

To eliminate discrepancies between posted opening journals and account metadata:
1. **The Core Invariant:** A posted opening journal entry (`voucher_type = 'OPENING'`, `status = 'POSTED'`) is the **sole authoritative record** of opening balances in the ledger.
2. **Metadata Synchronization:** `AccountGroupMapping.opening_balance` stores metadata for display and setup views.
3. **Query Resolution:**
   - In `get_trial_balance`, `get_chart_of_accounts`, `get_general_ledger`, and `get_balance_sheet`, the engine inspects whether an account has a posted `OPENING` journal line.
   - If an account has an authoritative posted `OPENING` journal line, that line is already present in `JournalEntryLine` and aggregated into the ledger totals (`tot_deb`, `tot_cred`). The calculation sets `base_op = 0.00`, eliminating duplicate addition.
   - If an account has no posted `OPENING` journal line (e.g. pre-migration accounts or accounts created directly with opening balances), the calculation gracefully falls back to `m.opening_balance`, maintaining 100% backward compatibility with legacy tests.
4. **Balance Sheet Harmony:**
   - **Open Financial Year:** $\text{Assets} = \text{Liabilities} + \text{Equity} + \text{Net Profit (P&L)}$.
   - **Closed Financial Year:** Net profit was already moved into `RETAINED_EARNINGS` (Equity) by the closing voucher. In the Balance Sheet report, `net_profit_for_period` is set to `0.00`, preventing net profit from being added twice. Total Assets exactly equal Total Liabilities + Total Equity.

---

## 6. Schema Migrations and ORM Models

### 6.1 Alembic Migration 006
`traditional_migrations/versions/006_financial_year_closing_and_opening_balances.py`

```python
op.create_table(
    'financial_year_closings',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('company_id', sa.String(length=36), nullable=False),
    sa.Column('branch_id', sa.String(length=36), nullable=False),
    sa.Column('financial_year', sa.String(length=20), nullable=False),
    sa.Column('closing_date', sa.String(length=10), nullable=False),
    sa.Column('closing_journal_id', sa.String(length=36), nullable=True),
    sa.Column('next_financial_year', sa.String(length=20), nullable=True),
    sa.Column('next_opening_journal_id', sa.String(length=36), nullable=True),
    sa.Column('net_profit', sa.Numeric(precision=15, scale=2), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='CLOSED', nullable=False),
    sa.Column('closed_by', sa.String(length=36), nullable=True),
    sa.Column('reopened_by', sa.String(length=36), nullable=True),
    sa.Column('reopened_at', sa.DateTime(), nullable=True),
    sa.Column('reopen_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['closing_journal_id'], ['journal_entries.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['next_opening_journal_id'], ['journal_entries.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['closed_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['reopened_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('company_id', 'financial_year', name='uq_fy_closings_company_fy'),
    sa.CheckConstraint("status IN ('CLOSED', 'REOPENED')", name='chk_fy_closings_status')
)
```

### 6.2 ORM Model Mapping
`db/traditional_models.py`
- Added `FinancialYearClosing` mapped to `financial_year_closings`.
- Added bidirectional relationship `year_closings = relationship("FinancialYearClosing", back_populates="company", cascade="all, delete-orphan")` on `Company`.

---

## 7. Automated Test Verification

### 7.1 The 20 Required Phase 2.1 Scenarios
Authored in `tests/traditional/test_traditional_closing_and_opening.py`:

| # | Test Function Name | Tested Invariant & Behavior | Status |
|---|---|---|---|
| 1 | `test_asset_opening_balance_debits` | Asset opening balances debited; balanced by Opening Balance Equity credit. | **PASSED** |
| 2 | `test_liability_and_equity_opening_balance_credits` | Liability and equity credits posted; balanced by Opening Balance Equity debit. | **PASSED** |
| 3 | `test_balanced_opening_journal_without_equity_offset` | When debits == credits, no Opening Balance Equity line is generated. | **PASSED** |
| 4 | `test_unbalanced_opening_balance_automatic_obe_balancing` | Debits != credits automatically offsets into `OPENING_BALANCE_EQUITY`. | **PASSED** |
| 5 | `test_rejection_of_opening_balance_on_nominal_accounts` | Opening balances on Income or Expense accounts strictly rejected. | **PASSED** |
| 6 | `test_rejection_of_duplicate_opening_balance_submission` | Duplicate opening balance submission for same FY rejected. | **PASSED** |
| 7 | `test_authorization_rejection_when_unauthorized` | Calls without `authorization_confirmed=True` fail closed (`PermissionError`). | **PASSED** |
| 8 | `test_rejection_of_empty_or_all_zero_opening_balance_submission` | Empty submissions and all-zero amounts rejected. | **PASSED** |
| 9 | `test_opening_balance_reversal_and_reset_of_balances` | Opening journal reversed via compensating voucher; metadata reset to 0.00. | **PASSED** |
| 10 | `test_immutability_of_posted_opening_journal` | Direct deletion of posted opening journal raises `ImmutableJournalError`. | **PASSED** |
| 11 | `test_year_end_closing_with_net_profit_transferred_to_retained_earnings` | Net profit closed to Retained Earnings (Equity); closing record stored. | **PASSED** |
| 12 | `test_year_end_closing_with_net_loss_transferred_to_retained_earnings` | Net loss closed as debit to Retained Earnings; closing record stored. | **PASSED** |
| 13 | `test_nominal_accounts_zeroed_out_post_closing_in_trial_balance` | Income and Expense accounts zeroed out in post-closing Trial Balance. | **PASSED** |
| 14 | `test_permanent_account_balances_preserved_post_closing` | Asset and Liability balances unchanged before and after closing. | **PASSED** |
| 15 | `test_profit_and_loss_report_operational_figures_preserved_post_closing` | P&L statement filters out closing voucher, preserving operational results. | **PASSED** |
| 16 | `test_balance_sheet_equality_maintained_post_closing_without_double_counting` | Balance Sheet holds Assets = Liab + Equity before & after closing with 0 diff. | **PASSED** |
| 17 | `test_rejection_of_double_closing_already_closed_financial_year` | Re-closing an already closed financial year raises `FinancialYearClosedError`. | **PASSED** |
| 18 | `test_controlled_reopening_of_closed_financial_year` | Authorized reopening reverses closing journal and restores open state. | **PASSED** |
| 19 | `test_carry_forward_to_next_financial_year_creates_balanced_opening_journal` | Permanent accounts roll forward into next FY's balanced opening voucher. | **PASSED** |
| 20 | `test_general_ledger_and_day_book_traceability_of_closing_and_opening_journals` | Full audit trail traceability of opening and closing entries in GL & Day Book. | **PASSED** |

### 7.2 Full Traditional Regression Suite
Executed across all 152 test cases in `tests/traditional/`:
```bash
.venv/bin/pytest tests/traditional/ -v
# Result: 152 passed in 32.53s (100% PASS)
```

### 7.3 Frontend Integration Test Suites
Executed across all 8 frontend integration suites:
```bash
for f in tests/*.js; do node "$f"; done
# 1. test_mode_aware_company_loading.js: 8/8 passed
# 2. test_traditional_account_master_frontend.js: 3/3 passed
# 3. test_traditional_continuous_product_entry.js: 7/7 passed
# 4. test_traditional_dashboard_frontend.js: 5/5 passed
# 5. test_traditional_modify_product_navigation.js: 5/5 passed
# 6. test_traditional_recovery_frontend.js: 6/6 passed
# 7. test_traditional_sales_pricing_frontend.js: 10/10 passed
# 8. test_traditional_wide_autocomplete_frontend.js: 5/5 passed
# Total: 49/49 assertions PASSED (100% PASS)
```

### 7.4 Physical Database Integrity Checksums
Verified against the repository's baseline checksums:
```bash
shasum -a 256 data/*.db
```
- `data/anti_matrix_billing.db`: `bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd` (**100% UNCHANGED**)
- `data/traditional_billing.db`: `0c4e5078625f3f7eef2793e86a5124966800fe7427d456f348a47ad422a57a30` (**100% UNCHANGED**)
- `data/app.db`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (**100% UNCHANGED**)

All uncommitted Git changes have been preserved intact without any commit or push actions.
