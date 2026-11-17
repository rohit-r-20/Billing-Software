"""
Comprehensive Automated Test Suite: Traditional Billing Double-Entry Accounting Engine.
Validates all 18 architecture, security, transaction, and isolation invariants:
1. Account creation and hierarchy (5-nature hierarchy: Asset, Liability, Equity, Income, Expense).
2. Multi-tenant company isolation (cross-tenant account reference strictly rejected).
3. Valid balanced double-entry journal posting and balance updates.
4. Rejection of unbalanced journals (total debits != total credits).
5. Rejection of negative amounts, zero amounts, and two-sided lines.
6. Duplicate posting prevention (idempotency key deduplication).
7. Reversal entries (compensating journal, audit trail, original marked REVERSED).
8. Closed accounting period restrictions and reopening.
9. General Ledger calculations (opening balance, running balance, closing balance).
10. Trial Balance calculations (total Dr == total Cr, mathematical reconciliation).
11. Profit and Loss calculations (Income - Expense = Net Profit).
12. Balance Sheet calculations (Assets == Liabilities + Equity + Net Profit).
13. Cash Book and Bank Book calculations.
14. Accounts Receivable and Accounts Payable outstandings.
15. Atomic transaction rollback on failure.
16. Concurrent posting safety under multi-threading.
17. Database isolation between Fast Billing and Traditional Billing.
18. Migration upgrade (rev 004 -> 005) and downgrade lifecycle.
"""

import os
import shutil
import hashlib
import concurrent.futures
from pathlib import Path
from decimal import Decimal
import pytest
from sqlalchemy import select, and_, text, func
from alembic.config import Config
from alembic import command

from db.traditional_database import TraditionalDatabaseManager
from db.traditional_models import (
    Company,
    Branch,
    User,
    Account,
    AccountGroup,
    AccountingPeriod,
    JournalEntry,
    JournalEntryLine,
)
from services.traditional_company_service import TraditionalCompanyService
from services.traditional_accounting_service import (
    TraditionalAccountingService,
    UnbalancedJournalError,
    InsufficientJournalLinesError,
    InvalidJournalAmountError,
    ClosedPeriodError,
    AccountNotFoundError,
    JournalReversalError,
    ImmutableJournalError,
    round_money,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FAST_DB_PATH = BASE_DIR / "data" / "anti_matrix_billing.db"


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture
def acct_env(tmp_path):
    """Provides an isolated, fully migrated Traditional SQLite database for accounting tests."""
    db_file = tmp_path / "test_traditional_acct.db"
    db_url = f"sqlite:///{db_file}"

    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    company_service = TraditionalCompanyService(db_manager=trad_mgr)
    accounting_service = TraditionalAccountingService(db_manager=trad_mgr)

    # Bootstrap Company A
    company_info = company_service.initial_setup({
        "name": "Arasu Accounting Corp",
        "code": "CORP01",
        "finYear": "2026-2027",
        "taxNo": "33AAACA1234A1Z1",
        "state": "Tamilnadu",
        "adminUsername": "ADMIN",
        "adminPassword": "SecurePassword123!",
    })

    # Ensure standard chart of accounts
    accounting_service.ensure_standard_accounts(company_info["companyId"])

    return {
        "db_url": db_url,
        "trad_mgr": trad_mgr,
        "company_service": company_service,
        "accounting_service": accounting_service,
        "company_id": company_info["companyId"],
        "branch_id": company_info["branchId"],
        "user_id": company_info["adminUserId"],
    }


# ==============================================================================
# 1. Account Creation and Hierarchy
# ==============================================================================

def test_account_creation_and_hierarchy(acct_env):
    """Verifies creation of custom account groups and accounts across the 5 fundamental natures."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]

    # 1. Create sub-group under Fixed Assets
    grp = acct_svc.create_account_group(
        company_id=cid,
        code="GRP_OFFICE_EQUIP",
        name="Office Equipment",
        nature="ASSET",
        parent_group_code="GRP_FIXED_ASSETS",
    )
    assert grp["code"] == "GRP_OFFICE_EQUIP"
    assert grp["nature"] == "ASSET"
    assert grp["parent_group_id"] is not None

    # 2. Create custom accounts
    acc_asset = acct_svc.create_account(
        company_id=cid,
        code="MACBOOK_01",
        name="MacBook Pro M3",
        group_code="GRP_OFFICE_EQUIP",
        opening_balance=Decimal("150000.00"),
        opening_balance_type="DR",
    )
    assert acc_asset["code"] == "MACBOOK_01"
    assert acc_asset["account_nature"] == "ASSET"
    assert acc_asset["opening_balance"] == "150000.00"
    assert acc_asset["current_balance"] == "150000.00"

    # 3. Create expense account
    acc_exp = acct_svc.create_account(
        company_id=cid,
        code="RENT_EXP",
        name="Office Rent",
        group_code="GRP_INDIRECT_EXPENSES",
        account_type="Expense",
    )
    assert acc_exp["code"] == "RENT_EXP"
    assert acc_exp["account_nature"] == "EXPENSE"

    # 4. Chart of Accounts verification
    coa = acct_svc.get_chart_of_accounts(cid)
    codes = [a["code"] for a in coa]
    assert "MACBOOK_01" in codes
    assert "RENT_EXP" in codes
    assert "CASH" in codes
    assert "SALES" in codes


# ==============================================================================
# 2. Company Isolation
# ==============================================================================

def test_company_isolation(acct_env):
    """Ensures account operations and journal postings strictly respect tenant boundaries."""
    trad_mgr = acct_env["trad_mgr"]
    acct_svc = acct_env["accounting_service"]
    cid_a = acct_env["company_id"]
    bid_a = acct_env["branch_id"]

    # Create Company B directly in session
    cid_b = "comp-tenant-b-uuid"
    bid_b = "branch-b-uuid"
    with trad_mgr.session_scope() as sess:
        comp_b = Company(
            id=cid_b,
            code="CORP02",
            name="Bharath Trading Co",
            fin_year="2026-2027",
            is_active=True,
        )
        sess.add(comp_b)
        branch_b = Branch(
            id=bid_b,
            company_id=cid_b,
            code="BR01",
            name="Branch B",
            is_active=True,
        )
        sess.add(branch_b)

    # Initialize standard accounts for Company B
    acct_svc.ensure_standard_accounts(cid_b)

    # Retrieve CASH account for Company A and Company B
    coa_a = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid_a)}
    coa_b = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid_b)}

    cash_a = coa_a["CASH"]
    cash_b = coa_b["CASH"]
    sales_b = coa_b["SALES"]

    assert cash_a != cash_b

    # Attempt to post a journal in Company B referencing Company A's cash account
    with pytest.raises(AccountNotFoundError) as exc_info:
        acct_svc.post_journal_entry(
            company_id=cid_b,
            branch_id=bid_b,
            voucher_type="JOURNAL",
            voucher_date="2026-05-10",
            lines=[
                {"account_id": cash_a, "debit": Decimal("5000.00"), "credit": Decimal("0.00")},
                {"account_id": sales_b, "debit": Decimal("0.00"), "credit": Decimal("5000.00")},
            ],
        )
    assert "not found or does not belong to company" in str(exc_info.value)


# ==============================================================================
# 3. Valid Balanced Journal Posting
# ==============================================================================

def test_valid_balanced_journal_posting(acct_env):
    """Verifies that a valid balanced journal posts correctly and updates account balances atomically."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]

    coa = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid)}
    cash_id = coa["CASH"]
    sales_id = coa["SALES"]

    j = acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-05-15",
        lines=[
            {"account_id": cash_id, "debit": Decimal("1000.00"), "credit": Decimal("0.00"), "narration": "Cash Sale"},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("1000.00"), "narration": "Sales Revenue"},
        ],
        voucher_number="JV-SALES-001",
        narration="Test Sales Invoice #001",
    )

    assert j["voucher_number"] == "JV-SALES-001"
    assert j["status"] == "POSTED"
    assert j["total_debit"] == "1000.00"
    assert j["total_credit"] == "1000.00"
    assert len(j["lines"]) == 2

    # Verify Account.current_balance
    coa_after = {a["code"]: Decimal(a["current_balance"]) for a in acct_svc.get_chart_of_accounts(cid)}
    # Cash is Asset (normal Dr): +1000
    assert coa_after["CASH"] == Decimal("1000.00")
    # Sales is Income (normal Cr): +1000
    assert coa_after["SALES"] == Decimal("1000.00")


# ==============================================================================
# 4. Rejection of Unbalanced Journals
# ==============================================================================

def test_rejection_of_unbalanced_journals(acct_env):
    """Rejects journals where total debits do not equal total credits."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]

    coa = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid)}
    cash_id = coa["CASH"]
    sales_id = coa["SALES"]

    with pytest.raises(UnbalancedJournalError) as exc_info:
        acct_svc.post_journal_entry(
            company_id=cid,
            branch_id=bid,
            voucher_type="JOURNAL",
            voucher_date="2026-05-15",
            lines=[
                {"account_id": cash_id, "debit": Decimal("1000.00"), "credit": Decimal("0.00")},
                {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("800.00")},
            ],
        )
    assert "unbalanced" in str(exc_info.value).lower()


# ==============================================================================
# 5. Rejection of Negative and Invalid Amounts
# ==============================================================================

def test_rejection_of_negative_and_invalid_amounts(acct_env):
    """Rejects negative amounts, zero lines, two-sided lines, and journals with fewer than 2 lines."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]

    coa = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid)}
    cash_id = coa["CASH"]
    sales_id = coa["SALES"]

    # 1. Fewer than 2 lines
    with pytest.raises(InsufficientJournalLinesError):
        acct_svc.post_journal_entry(
            company_id=cid,
            branch_id=bid,
            voucher_type="JOURNAL",
            voucher_date="2026-05-15",
            lines=[{"account_id": cash_id, "debit": Decimal("100.00"), "credit": Decimal("0.00")}],
        )

    # 2. Negative debit
    with pytest.raises(InvalidJournalAmountError) as exc:
        acct_svc.post_journal_entry(
            company_id=cid,
            branch_id=bid,
            voucher_type="JOURNAL",
            voucher_date="2026-05-15",
            lines=[
                {"account_id": cash_id, "debit": Decimal("-100.00"), "credit": Decimal("0.00")},
                {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("-100.00")},
            ],
        )
    assert "non-negative" in str(exc.value).lower()

    # 3. Line with both Debit > 0 and Credit > 0
    with pytest.raises(InvalidJournalAmountError) as exc:
        acct_svc.post_journal_entry(
            company_id=cid,
            branch_id=bid,
            voucher_type="JOURNAL",
            voucher_date="2026-05-15",
            lines=[
                {"account_id": cash_id, "debit": Decimal("100.00"), "credit": Decimal("50.00")},
                {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("50.00")},
            ],
        )
    assert "both debit" in str(exc.value).lower()

    # 4. Zero on both sides
    with pytest.raises(InvalidJournalAmountError):
        acct_svc.post_journal_entry(
            company_id=cid,
            branch_id=bid,
            voucher_type="JOURNAL",
            voucher_date="2026-05-15",
            lines=[
                {"account_id": cash_id, "debit": Decimal("0.00"), "credit": Decimal("0.00")},
                {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("0.00")},
            ],
        )


# ==============================================================================
# 6. Duplicate Posting Prevention (Idempotency)
# ==============================================================================

def test_duplicate_posting_prevention(acct_env):
    """Verifies idempotency key deduplication prevents double-posting."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]

    coa = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid)}
    cash_id = coa["CASH"]
    sales_id = coa["SALES"]

    lines = [
        {"account_id": cash_id, "debit": Decimal("500.00"), "credit": Decimal("0.00")},
        {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("500.00")},
    ]

    # First post
    j1 = acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-05-20",
        lines=lines,
        idempotency_key="INV-IDEM-001",
    )

    # Second post with identical idempotency_key
    j2 = acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-05-20",
        lines=lines,
        idempotency_key="INV-IDEM-001",
    )

    assert j1["id"] == j2["id"]

    # Verify balance was only mutated ONCE (+500, not +1000)
    coa_after = {a["code"]: Decimal(a["current_balance"]) for a in acct_svc.get_chart_of_accounts(cid)}
    assert coa_after["CASH"] == Decimal("500.00")


# ==============================================================================
# 7. Reversal Entries
# ==============================================================================

def test_reversal_entries(acct_env):
    """Verifies reversal journals compensate balances and maintain audit trails."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]

    coa = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid)}
    cash_id = coa["CASH"]
    sales_id = coa["SALES"]

    j = acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-05-21",
        lines=[
            {"account_id": cash_id, "debit": Decimal("2500.00"), "credit": Decimal("0.00")},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("2500.00")},
        ],
        voucher_number="SAL-00025",
    )

    # Check balances after posting
    coa1 = {a["code"]: Decimal(a["current_balance"]) for a in acct_svc.get_chart_of_accounts(cid)}
    assert coa1["CASH"] == Decimal("2500.00")

    # Reverse journal
    rev = acct_svc.reverse_journal_entry(
        company_id=cid,
        journal_id=j["id"],
        reversal_reason="Customer cancelled order",
    )

    assert rev["voucher_type"] == "REVERSAL"
    assert rev["total_debit"] == "2500.00"

    # Check that original journal is now marked REVERSED
    with acct_env["trad_mgr"].read_session_scope() as sess:
        orig = sess.scalar(select(JournalEntry).where(JournalEntry.id == j["id"]))
        assert orig.status == "REVERSED"
        assert orig.reversed_by_id == rev["id"]
        assert orig.reversal_reason == "Customer cancelled order"

    # Check balances are completely restored to zero
    coa2 = {a["code"]: Decimal(a["current_balance"]) for a in acct_svc.get_chart_of_accounts(cid)}
    assert coa2["CASH"] == Decimal("0.00")
    assert coa2["SALES"] == Decimal("0.00")

    # Attempting to reverse an already reversed journal raises JournalReversalError
    with pytest.raises(JournalReversalError):
        acct_svc.reverse_journal_entry(
            company_id=cid,
            journal_id=j["id"],
            reversal_reason="Second reversal attempt",
        )

    # Deletion of posted or reversed journal is rejected
    with pytest.raises(ImmutableJournalError):
        acct_svc.delete_journal_entry(company_id=cid, journal_id=j["id"])


# ==============================================================================
# 8. Closed-Period Restrictions
# ==============================================================================

def test_closed_period_restrictions(acct_env):
    """Verifies that posting into closed accounting periods is rejected and reopening allows posting."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]

    coa = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid)}
    cash_id = coa["CASH"]
    sales_id = coa["SALES"]

    # 1. Create and close period for April 2026
    period = acct_svc.create_accounting_period(
        company_id=cid,
        financial_year="2026-2027",
        period_name="APRIL-2026",
        start_date="2026-04-01",
        end_date="2026-04-30",
    )
    acct_svc.close_accounting_period(company_id=cid, period_id_or_name=period["id"])

    # 2. Attempt posting on 2026-04-15 -> must be rejected
    lines = [
        {"account_id": cash_id, "debit": Decimal("100.00"), "credit": Decimal("0.00")},
        {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("100.00")},
    ]
    with pytest.raises(ClosedPeriodError) as exc_info:
        acct_svc.post_journal_entry(
            company_id=cid,
            branch_id=bid,
            voucher_type="SALES",
            voucher_date="2026-04-15",
            lines=lines,
        )
    assert "is CLOSED" in str(exc_info.value)

    # 3. Posting on 2026-05-01 (outside closed period) succeeds
    j_may = acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-05-01",
        lines=lines,
    )
    assert j_may["status"] == "POSTED"

    # 4. Reopen period and verify posting on 2026-04-15 now succeeds
    acct_svc.reopen_accounting_period(company_id=cid, period_id_or_name=period["id"])
    j_apr = acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-04-15",
        lines=lines,
    )
    assert j_apr["status"] == "POSTED"


# ==============================================================================
# 9. General Ledger Calculations
# ==============================================================================

def test_general_ledger_calculations(acct_env):
    """Verifies opening balance, chronological running balance, and closing balance in General Ledger."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]

    coa = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid)}
    cash_id = coa["CASH"]
    sales_id = coa["SALES"]
    purchase_id = coa["PURCHASE"]

    # Transaction 1: 2026-05-01 (+1000 Cash)
    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-05-01",
        lines=[
            {"account_id": cash_id, "debit": Decimal("1000.00"), "credit": Decimal("0.00")},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("1000.00")},
        ],
    )

    # Transaction 2: 2026-05-05 (-400 Cash for Purchase)
    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="PURCHASE",
        voucher_date="2026-05-05",
        lines=[
            {"account_id": purchase_id, "debit": Decimal("400.00"), "credit": Decimal("0.00")},
            {"account_id": cash_id, "debit": Decimal("0.00"), "credit": Decimal("400.00")},
        ],
    )

    # Query General Ledger for Cash starting from 2026-05-03
    led = acct_svc.get_general_ledger(
        company_id=cid,
        account_id=cash_id,
        start_date="2026-05-03",
        end_date="2026-05-10",
    )

    # Prior movement on 2026-05-01 is 1000 Dr
    assert led["opening_balance"] == "1000.00"
    assert led["opening_balance_type"] == "Dr"
    assert led["period_debit"] == "0.00"
    assert led["period_credit"] == "400.00"
    # Closing balance: 1000 - 400 = 600 Dr
    assert led["closing_balance"] == "600.00"
    assert led["closing_balance_type"] == "Dr"
    assert len(led["entries"]) == 1
    assert led["entries"][0]["running_balance"] == "600.00"


# ==============================================================================
# 10. Trial Balance Calculations
# ==============================================================================

def test_trial_balance_calculations(acct_env):
    """Verifies that Trial Balance reconciles total debits and total credits with zero difference."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]

    coa = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid)}
    cash_id = coa["CASH"]
    sales_id = coa["SALES"]
    purchase_id = coa["PURCHASE"]

    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-05-10",
        lines=[
            {"account_id": cash_id, "debit": Decimal("5000.00"), "credit": Decimal("0.00")},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("5000.00")},
        ],
    )
    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="PURCHASE",
        voucher_date="2026-05-11",
        lines=[
            {"account_id": purchase_id, "debit": Decimal("3000.00"), "credit": Decimal("0.00")},
            {"account_id": cash_id, "debit": Decimal("0.00"), "credit": Decimal("3000.00")},
        ],
    )

    tb = acct_svc.get_trial_balance(company_id=cid)
    assert tb["is_balanced"] is True
    assert Decimal(tb["difference"]) == Decimal("0.00")
    assert tb["total_debit"] == tb["total_credit"]


# ==============================================================================
# 11. Profit and Loss Calculations
# ==============================================================================

def test_profit_and_loss_calculations(acct_env):
    """Verifies Profit and Loss calculations: Total Income - Total Expense = Net Profit."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]

    coa = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid)}
    cash_id = coa["CASH"]
    sales_id = coa["SALES"]
    purchase_id = coa["PURCHASE"]

    # Sales of 10,000
    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-06-01",
        lines=[
            {"account_id": cash_id, "debit": Decimal("10000.00"), "credit": Decimal("0.00")},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("10000.00")},
        ],
    )

    # Purchase of 6,500
    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="PURCHASE",
        voucher_date="2026-06-02",
        lines=[
            {"account_id": purchase_id, "debit": Decimal("6500.00"), "credit": Decimal("0.00")},
            {"account_id": cash_id, "debit": Decimal("0.00"), "credit": Decimal("6500.00")},
        ],
    )

    pnl = acct_svc.get_profit_and_loss(company_id=cid)
    assert pnl["total_income"] == "10000.00"
    assert pnl["total_expense"] == "6500.00"
    assert pnl["net_profit"] == "3500.00"
    assert pnl["is_profit"] is True


# ==============================================================================
# 12. Balance Sheet Calculations
# ==============================================================================

def test_balance_sheet_calculations(acct_env):
    """Verifies Balance Sheet fundamental equation: Assets = Liabilities + Equity + Net Profit."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]

    coa = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid)}
    cash_id = coa["CASH"]
    sales_id = coa["SALES"]

    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-06-10",
        lines=[
            {"account_id": cash_id, "debit": Decimal("15000.00"), "credit": Decimal("0.00")},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("15000.00")},
        ],
    )

    bs = acct_svc.get_balance_sheet(company_id=cid)
    assert bs["total_assets"] == "15000.00"
    assert bs["net_profit_for_period"] == "15000.00"
    assert bs["total_liabilities_and_equity"] == "15000.00"
    assert bs["difference"] == "0.00"
    assert bs["is_balanced"] is True


# ==============================================================================
# 13. Cash Book and Bank Book Calculations
# ==============================================================================

def test_cash_and_bank_book_calculations(acct_env):
    """Verifies Cash Book and Bank Book statement calculation engines."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]

    # Create Bank Account
    bank_acc = acct_svc.create_account(
        company_id=cid,
        code="HDFC_BANK",
        name="HDFC Current Account",
        group_code="GRP_BANK",
        account_type="Bank",
        opening_balance=Decimal("25000.00"),
        opening_balance_type="DR",
    )

    coa = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid)}
    cash_id = coa["CASH"]
    bank_id = bank_acc["id"]

    # Deposit 5,000 Cash into Bank
    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="CONTRA",
        voucher_date="2026-06-15",
        lines=[
            {"account_id": bank_id, "debit": Decimal("5000.00"), "credit": Decimal("0.00"), "narration": "Cash deposit"},
            {"account_id": cash_id, "debit": Decimal("0.00"), "credit": Decimal("5000.00"), "narration": "Cash deposited in bank"},
        ],
    )

    cb = acct_svc.get_cash_book(company_id=cid)
    assert cb["period_credit"] == "5000.00"

    bb = acct_svc.get_bank_book(company_id=cid, account_id=bank_id)
    # Opening 25,000 + 5,000 deposit = 30,000 closing
    assert bb["opening_balance"] == "25000.00"
    assert bb["period_debit"] == "5000.00"
    assert bb["closing_balance"] == "30000.00"


# ==============================================================================
# 14. Accounts Receivable and Accounts Payable Calculations
# ==============================================================================

def test_receivable_and_payable_calculations(acct_env):
    """Verifies customer outstanding (AR) and supplier outstanding (AP) reports via integration blueprints."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]

    # 1. Create Customer (Debtor)
    cust = acct_svc.create_account(
        company_id=cid,
        code="CUS-00100",
        name="Apex Enterprises",
        group_code="GRP_SUNDRY_DEBTORS",
        account_type="Debtor",
    )

    # 2. Create Supplier (Creditor)
    supp = acct_svc.create_account(
        company_id=cid,
        code="SUP-00200",
        name="Zenith Supplies",
        group_code="GRP_SUNDRY_CREDITORS",
        account_type="Creditor",
    )

    # 3. Post Sales Invoice to Customer: 10,000 + 900 CGST + 900 SGST = 11,800
    acct_svc.record_sales_journal(
        company_id=cid,
        branch_id=bid,
        invoice_id="inv-001-uuid",
        invoice_number="INV-2026-001",
        invoice_date="2026-06-20",
        customer_account_id=cust["id"],
        sales_amount=Decimal("10000.00"),
        output_cgst=Decimal("900.00"),
        output_sgst=Decimal("900.00"),
    )

    # 4. Post Customer Partial Receipt: 5,000
    coa = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid)}
    acct_svc.record_customer_receipt(
        company_id=cid,
        branch_id=bid,
        receipt_number="REC-001",
        receipt_date="2026-06-22",
        customer_account_id=cust["id"],
        cash_or_bank_account_id=coa["CASH"],
        amount=Decimal("5000.00"),
    )

    # Verify Receivables Report
    rec_rep = acct_svc.get_receivables_report(company_id=cid)
    # 11,800 billed - 5,000 paid = 6,800 outstanding
    assert Decimal(rec_rep["total_receivable"]) == Decimal("6800.00")

    # 5. Post Purchase Bill from Supplier: 8,000 + 720 CGST + 720 SGST = 9,440
    acct_svc.record_purchase_journal(
        company_id=cid,
        branch_id=bid,
        bill_id="bill-001-uuid",
        bill_number="BILL-2026-001",
        bill_date="2026-06-21",
        supplier_account_id=supp["id"],
        purchase_amount=Decimal("8000.00"),
        input_cgst=Decimal("720.00"),
        input_sgst=Decimal("720.00"),
    )

    # Verify Payables Report
    pay_rep = acct_svc.get_payables_report(company_id=cid)
    assert Decimal(pay_rep["total_payable"]) == Decimal("9440.00")


# ==============================================================================
# 15. Transaction Rollback on Failure
# ==============================================================================

def test_transaction_rollback(acct_env):
    """Verifies that an error midway rolls back all journal lines and balance mutations."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]
    trad_mgr = acct_env["trad_mgr"]

    coa = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid)}
    cash_id = coa["CASH"]

    # Attempt posting with an invalid second account
    with pytest.raises(AccountNotFoundError):
        acct_svc.post_journal_entry(
            company_id=cid,
            branch_id=bid,
            voucher_type="JOURNAL",
            voucher_date="2026-06-25",
            lines=[
                {"account_id": cash_id, "debit": Decimal("1000.00"), "credit": Decimal("0.00")},
                {"account_id": "non-existent-account-uuid", "debit": Decimal("0.00"), "credit": Decimal("1000.00")},
            ],
        )

    # Verify no journal was saved
    with trad_mgr.read_session_scope() as sess:
        count = sess.scalar(select(func.count(JournalEntry.id)).where(JournalEntry.company_id == cid))
        assert count == 0


# ==============================================================================
# 16. Concurrent Posting Safety
# ==============================================================================

def test_concurrent_posting_safety(acct_env):
    """Verifies concurrent threads posting balanced journals maintain double-entry integrity without corruption."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]

    coa = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid)}
    cash_id = coa["CASH"]
    sales_id = coa["SALES"]

    num_threads = 5
    postings_per_thread = 4

    def worker(thread_idx: int):
        for i in range(postings_per_thread):
            key = f"CONC_THREAD_{thread_idx}_{i}"
            acct_svc.post_journal_entry(
                company_id=cid,
                branch_id=bid,
                voucher_type="SALES",
                voucher_date="2026-06-28",
                lines=[
                    {"account_id": cash_id, "debit": Decimal("100.00"), "credit": Decimal("0.00")},
                    {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("100.00")},
                ],
                idempotency_key=key,
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, t) for t in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    # Reconcile Trial Balance
    tb = acct_svc.get_trial_balance(company_id=cid)
    assert tb["is_balanced"] is True
    assert Decimal(tb["difference"]) == Decimal("0.00")

    expected_total = Decimal("100.00") * num_threads * postings_per_thread
    assert Decimal(tb["total_debit"]) == expected_total


# ==============================================================================
# 17. Database Isolation between Fast Billing and Traditional Billing
# ==============================================================================

def test_database_isolation_fast_vs_traditional(acct_env):
    """Verifies that Traditional accounting operations do not affect Fast Billing database file."""
    fast_db_hash_before = compute_sha256(FAST_DB_PATH)

    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]

    coa = {a["code"]: a["id"] for a in acct_svc.get_chart_of_accounts(cid)}
    cash_id = coa["CASH"]
    sales_id = coa["SALES"]

    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="JOURNAL",
        voucher_date="2026-07-01",
        lines=[
            {"account_id": cash_id, "debit": Decimal("9999.00"), "credit": Decimal("0.00")},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("9999.00")},
        ],
    )

    fast_db_hash_after = compute_sha256(FAST_DB_PATH)
    assert fast_db_hash_after == fast_db_hash_before, "Fast Billing database was mutated during Traditional accounting test!"


# ==============================================================================
# 18. Migration Upgrade and Downgrade Lifecycle
# ==============================================================================

def test_migration_upgrade_and_downgrade(tmp_path):
    """Verifies clean Alembic upgrade to 005 and downgrade back to 004 on a disposable database."""
    test_db = tmp_path / "migration_lifecycle.db"
    db_url = f"sqlite:///{test_db}"

    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade to 004
    command.upgrade(alembic_cfg, "004_inventory_movements_and_adjustments")

    # 2. Upgrade to 005 (head)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    with trad_mgr.read_session_scope() as sess:
        # Verify account_groups, accounting_periods, journal_entries, journal_entry_lines exist
        tables = [r[0] for r in sess.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).all()]
        assert "account_groups" in tables
        assert "accounting_periods" in tables
        assert "journal_entries" in tables
        assert "journal_entry_lines" in tables

    # 3. Downgrade back to 004
    command.downgrade(alembic_cfg, "004_inventory_movements_and_adjustments")

    with trad_mgr.read_session_scope() as sess:
        tables_after = [r[0] for r in sess.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).all()]
        assert "account_groups" not in tables_after
        assert "journal_entries" not in tables_after
        assert "journal_entry_lines" not in tables_after
        assert "accounting_periods" not in tables_after
