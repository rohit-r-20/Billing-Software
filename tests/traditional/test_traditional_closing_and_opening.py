"""
Comprehensive Automated Test Suite: Traditional Billing Opening Balances and Year-End Closing.
Phase 2.1 — Anti-Matrix Billing V2 Core Backend Architecture.

Validates all 20 required opening balance, closing, carry-forward, reporting, and security scenarios:
1. Asset opening balance debits.
2. Liability and equity opening balance credits.
3. Balanced opening journal without equity offset.
4. Unbalanced opening balance with automatic Opening Balance Equity balancing line.
5. Rejection of opening balance on nominal (Income/Expense) accounts.
6. Rejection of duplicate opening balance submission for the same FY.
7. Authorization rejection when unauthorized (post, close, reopen, carry-forward).
8. Rejection of empty or all-zero opening balance submission.
9. Opening balance reversal and reset of balances.
10. Immutability of posted opening journal (cannot edit or delete directly).
11. Year-end closing with net profit transferred to Retained Earnings.
12. Year-end closing with net loss transferred to Retained Earnings.
13. Nominal accounts zeroed out post-closing in Trial Balance.
14. Permanent account balances preserved post-closing.
15. P&L report operational figures preserved post-closing (filters out closing voucher).
16. Balance Sheet equality maintained post-closing without double-counting net profit.
17. Rejection of double-closing an already closed financial year.
18. Controlled reopening of a closed financial year.
19. Carry-forward to next financial year creates balanced opening journal for next FY.
20. General Ledger & Day Book traceability of closing and opening journals.
"""

from decimal import Decimal
from pathlib import Path
import pytest
from sqlalchemy import select, and_
from alembic.config import Config
from alembic import command

from db.traditional_database import TraditionalDatabaseManager
from db.traditional_models import (
    Account,
    AccountGroupMapping,
    JournalEntry,
    JournalEntryLine,
    FinancialYearClosing,
    AuditLog,
)
from services.traditional_company_service import TraditionalCompanyService
from services.traditional_accounting_service import (
    TraditionalAccountingService,
    TraditionalAccountingError,
    DuplicateJournalError,
    ImmutableJournalError,
    FinancialYearClosedError,
    UnauthorizedAccountingActionError,
)


@pytest.fixture
def acct_env(tmp_path):
    """Provides an isolated, fully migrated Traditional SQLite database for closing and opening tests."""
    db_file = tmp_path / "test_traditional_closing_opening.db"
    db_url = f"sqlite:///{db_file}"

    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    company_service = TraditionalCompanyService(db_manager=trad_mgr)
    accounting_service = TraditionalAccountingService(db_manager=trad_mgr)

    company_info = company_service.initial_setup({
        "name": "Arasu Closing & Opening Corp",
        "code": "CORP_CLS",
        "finYear": "2026-2027",
        "taxNo": "33AAACA9999A1Z9",
        "state": "Tamilnadu",
        "adminUsername": "ADMIN",
        "adminPassword": "SecurePassword123!",
    })

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


def _get_accounts_by_code(acct_svc, company_id):
    """Helper to return a dict of code -> account dict."""
    return {a["code"]: a for a in acct_svc.get_chart_of_accounts(company_id)}


# ==============================================================================
# 1. Asset Opening Balance Debits
# ==============================================================================

def test_asset_opening_balance_debits(acct_env):
    """Scenario 1: Asset opening balance debits balanced by Opening Balance Equity credit."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]
    uid = acct_env["user_id"]
    accs = _get_accounts_by_code(acct_svc, cid)

    # Asset accounts: Cash and Stock in Hand
    cash_id = accs["CASH"]["id"]
    stock_id = accs["STOCK_IN_HAND"]["id"]

    res = acct_svc.post_opening_balances(
        company_id=cid,
        financial_year="2026-2027",
        opening_balances=[
            {"account_id": cash_id, "amount": Decimal("50000.00"), "balance_type": "DR"},
            {"account_id": stock_id, "amount": Decimal("75000.00"), "balance_type": "DR"},
        ],
        voucher_date="2026-04-01",
        branch_id=bid,
        authorization_confirmed=True,
        posted_by=uid,
    )

    assert res["voucher_type"] == "OPENING"
    assert res["voucher_number"] == "OP-2026-2027"
    assert res["total_debit"] == "125000.00"
    assert res["total_credit"] == "125000.00"

    # Verify Trial Balance debits and balanced state
    tb = acct_svc.get_trial_balance(cid, financial_year="2026-2027")
    assert tb["is_balanced"] is True
    assert tb["difference"] == "0.00"
    assert tb["total_debit"] == "125000.00"
    assert tb["total_credit"] == "125000.00"

    tb_lines = {item["account_code"]: item for item in tb["accounts"]}
    assert tb_lines["CASH"]["debit"] == "50000.00"
    assert tb_lines["STOCK_IN_HAND"]["debit"] == "75000.00"
    assert tb_lines["OPENING_BALANCE_EQUITY"]["credit"] == "125000.00"


# ==============================================================================
# 2. Liability and Equity Opening Balance Credits
# ==============================================================================

def test_liability_and_equity_opening_balance_credits(acct_env):
    """Scenario 2: Liability and equity opening balance credits balanced by Opening Balance Equity debit."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]
    uid = acct_env["user_id"]

    # Create supplier account (Liability) and Capital account (Equity)
    sup = acct_svc.create_account(cid, "SUPPLIER_A", "Supplier A", "GRP_SUNDRY_CREDITORS", account_type="Creditor")
    cap = acct_svc.create_account(cid, "OWNER_CAPITAL", "Owner Capital", "GRP_CAPITAL", account_type="Capital")

    res = acct_svc.post_opening_balances(
        company_id=cid,
        financial_year="2026-2027",
        opening_balances=[
            {"account_id": sup["id"], "amount": Decimal("30000.00"), "balance_type": "CR"},
            {"account_id": cap["id"], "amount": Decimal("70000.00"), "balance_type": "CR"},
        ],
        voucher_date="2026-04-01",
        branch_id=bid,
        authorization_confirmed=True,
        posted_by=uid,
    )

    assert res["voucher_type"] == "OPENING"
    assert res["total_debit"] == "100000.00"
    assert res["total_credit"] == "100000.00"

    tb = acct_svc.get_trial_balance(cid, financial_year="2026-2027")
    assert tb["is_balanced"] is True
    tb_lines = {item["account_code"]: item for item in tb["accounts"]}
    assert tb_lines["SUPPLIER_A"]["credit"] == "30000.00"
    assert tb_lines["OWNER_CAPITAL"]["credit"] == "70000.00"
    assert tb_lines["OPENING_BALANCE_EQUITY"]["debit"] == "100000.00"


# ==============================================================================
# 3. Balanced Opening Journal Without Equity Offset
# ==============================================================================

def test_balanced_opening_journal_without_equity_offset(acct_env):
    """Scenario 3: When submitted opening debits == credits, no Opening Balance Equity line is generated."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]
    accs = _get_accounts_by_code(acct_svc, cid)

    cash_id = accs["CASH"]["id"]
    sup = acct_svc.create_account(cid, "SUP_BAL", "Supplier Balanced", "GRP_SUNDRY_CREDITORS", account_type="Creditor")
    cap = acct_svc.create_account(cid, "CAP_BAL", "Capital Balanced", "GRP_CAPITAL", account_type="Capital")

    res = acct_svc.post_opening_balances(
        company_id=cid,
        financial_year="2026-2027",
        opening_balances=[
            {"account_id": cash_id, "amount": Decimal("100000.00"), "balance_type": "DR"},
            {"account_id": sup["id"], "amount": Decimal("40000.00"), "balance_type": "CR"},
            {"account_id": cap["id"], "amount": Decimal("60000.00"), "balance_type": "CR"},
        ],
        authorization_confirmed=True,
    )

    # Exactly 3 lines (Cash Dr, Sup Cr, Cap Cr) — no OBE plug
    assert len(res["lines"]) == 3
    line_acc_codes = {l["account_code"] for l in res["lines"]}
    assert "OPENING_BALANCE_EQUITY" not in line_acc_codes
    assert res["total_debit"] == "100000.00"
    assert res["total_credit"] == "100000.00"

    tb = acct_svc.get_trial_balance(cid, financial_year="2026-2027")
    assert tb["is_balanced"] is True
    assert "OPENING_BALANCE_EQUITY" not in {item["account_code"] for item in tb["accounts"]}


# ==============================================================================
# 4. Unbalanced Opening Balance Automatic OBE Balancing
# ==============================================================================

def test_unbalanced_opening_balance_automatic_obe_balancing(acct_env):
    """Scenario 4: When debits != credits, OPENING_BALANCE_EQUITY line automatically balances the entry."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    accs = _get_accounts_by_code(acct_svc, cid)

    cash_id = accs["CASH"]["id"]
    cap = acct_svc.create_account(cid, "CAP_UNBAL", "Capital Unbalanced", "GRP_CAPITAL", account_type="Capital")

    res = acct_svc.post_opening_balances(
        company_id=cid,
        financial_year="2026-2027",
        opening_balances=[
            {"account_id": cash_id, "amount": Decimal("120000.00"), "balance_type": "DR"},
            {"account_id": cap["id"], "amount": Decimal("50000.00"), "balance_type": "CR"},
        ],
        authorization_confirmed=True,
    )

    assert len(res["lines"]) == 3
    obe_line = next(l for l in res["lines"] if l["account_code"] == "OPENING_BALANCE_EQUITY")
    assert obe_line["credit"] == "70000.00"
    assert obe_line["debit"] == "0.00"

    bs = acct_svc.get_balance_sheet(cid, financial_year="2026-2027")
    assert bs["is_balanced"] is True
    assert bs["total_assets"] == "120000.00"
    assert bs["total_liabilities_and_equity"] == "120000.00"


# ==============================================================================
# 5. Rejection of Opening Balance on Nominal Accounts
# ==============================================================================

def test_rejection_of_opening_balance_on_nominal_accounts(acct_env):
    """Scenario 5: Opening balances on Income or Expense accounts are strictly rejected."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    accs = _get_accounts_by_code(acct_svc, cid)

    sales_id = accs["SALES"]["id"]
    purchase_id = accs["PURCHASE"]["id"]

    # Attempt on Income
    with pytest.raises(TraditionalAccountingError) as exc_inc:
        acct_svc.post_opening_balances(
            company_id=cid,
            financial_year="2026-2027",
            opening_balances=[{"account_id": sales_id, "amount": Decimal("1000.00")}],
            authorization_confirmed=True,
        )
    assert "nominal account (INCOME)" in str(exc_inc.value)

    # Attempt on Expense
    with pytest.raises(TraditionalAccountingError) as exc_exp:
        acct_svc.post_opening_balances(
            company_id=cid,
            financial_year="2026-2027",
            opening_balances=[{"account_id": purchase_id, "amount": Decimal("500.00")}],
            authorization_confirmed=True,
        )
    assert "nominal account (EXPENSE)" in str(exc_exp.value)


# ==============================================================================
# 6. Rejection of Duplicate Opening Balance Submission
# ==============================================================================

def test_rejection_of_duplicate_opening_balance_submission(acct_env):
    """Scenario 6: Second attempt to post opening balances for the same financial year is rejected."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    accs = _get_accounts_by_code(acct_svc, cid)
    cash_id = accs["CASH"]["id"]

    acct_svc.post_opening_balances(
        company_id=cid,
        financial_year="2026-2027",
        opening_balances=[{"account_id": cash_id, "amount": Decimal("25000.00")}],
        authorization_confirmed=True,
    )

    with pytest.raises(DuplicateJournalError) as exc_dup:
        acct_svc.post_opening_balances(
            company_id=cid,
            financial_year="2026-2027",
            opening_balances=[{"account_id": cash_id, "amount": Decimal("30000.00")}],
            authorization_confirmed=True,
        )
    assert "already been posted" in str(exc_dup.value)


# ==============================================================================
# 7. Authorization Rejection When Unauthorized
# ==============================================================================

def test_authorization_rejection_when_unauthorized(acct_env):
    """Scenario 7: Calling sensitive workflows without authorization_confirmed=True fails closed."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    accs = _get_accounts_by_code(acct_svc, cid)
    cash_id = accs["CASH"]["id"]

    # post_opening_balances unauthorized
    with pytest.raises((UnauthorizedAccountingActionError, PermissionError)):
        acct_svc.post_opening_balances(
            company_id=cid,
            financial_year="2026-2027",
            opening_balances=[{"account_id": cash_id, "amount": Decimal("10000.00")}],
            authorization_confirmed=False,
        )

    # reverse_opening_balances unauthorized
    with pytest.raises((UnauthorizedAccountingActionError, PermissionError)):
        acct_svc.reverse_opening_balances(
            company_id=cid,
            financial_year="2026-2027",
            reversal_reason="Mistake",
            authorization_confirmed=False,
        )

    # close_financial_year unauthorized
    with pytest.raises((UnauthorizedAccountingActionError, PermissionError)):
        acct_svc.close_financial_year(
            company_id=cid,
            financial_year="2026-2027",
            authorization_confirmed=False,
        )

    # reopen_financial_year unauthorized
    with pytest.raises((UnauthorizedAccountingActionError, PermissionError)):
        acct_svc.reopen_financial_year(
            company_id=cid,
            financial_year="2026-2027",
            reopen_reason="Audit adjustment",
            authorization_confirmed=False,
        )

    # carry_forward_to_next_financial_year unauthorized
    with pytest.raises((UnauthorizedAccountingActionError, PermissionError)):
        acct_svc.carry_forward_to_next_financial_year(
            company_id=cid,
            current_financial_year="2026-2027",
            authorization_confirmed=False,
        )


# ==============================================================================
# 8. Rejection of Empty or All-Zero Opening Balance Submission
# ==============================================================================

def test_rejection_of_empty_or_all_zero_opening_balance_submission(acct_env):
    """Scenario 8: Submissions with empty list or only zero balances are rejected."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    accs = _get_accounts_by_code(acct_svc, cid)
    cash_id = accs["CASH"]["id"]

    # Empty list
    with pytest.raises(TraditionalAccountingError) as exc_empty:
        acct_svc.post_opening_balances(
            company_id=cid,
            financial_year="2026-2027",
            opening_balances=[],
            authorization_confirmed=True,
        )
    assert "cannot be empty" in str(exc_empty.value)

    # All zeros
    with pytest.raises(TraditionalAccountingError) as exc_zero:
        acct_svc.post_opening_balances(
            company_id=cid,
            financial_year="2026-2027",
            opening_balances=[
                {"account_id": cash_id, "amount": Decimal("0.00")},
            ],
            authorization_confirmed=True,
        )
    assert "at least one account with a non-zero balance" in str(exc_zero.value)


# ==============================================================================
# 9. Opening Balance Reversal and Reset of Balances
# ==============================================================================

def test_opening_balance_reversal_and_reset_of_balances(acct_env):
    """Scenario 9: Reversing opening balances posts compensating voucher and resets metadata."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    accs = _get_accounts_by_code(acct_svc, cid)
    cash_id = accs["CASH"]["id"]

    acct_svc.post_opening_balances(
        company_id=cid,
        financial_year="2026-2027",
        opening_balances=[{"account_id": cash_id, "amount": Decimal("45000.00")}],
        authorization_confirmed=True,
    )

    # Verify AccountGroupMapping was updated
    coa = _get_accounts_by_code(acct_svc, cid)
    assert coa["CASH"]["opening_balance"] == "45000.00"

    # Reverse
    rev = acct_svc.reverse_opening_balances(
        company_id=cid,
        financial_year="2026-2027",
        reversal_reason="Wrong bank figures entered",
        authorization_confirmed=True,
    )
    assert rev["voucher_type"] == "REVERSAL"
    assert rev["voucher_number"] == "REV-OP-2026-2027"

    # Metadata reset to 0.00
    coa_after = _get_accounts_by_code(acct_svc, cid)
    assert coa_after["CASH"]["opening_balance"] == "0.00"
    assert coa_after["CASH"]["current_balance"] == "0.00"

    # Audit log check
    with acct_env["trad_mgr"].read_session_scope() as sess:
        audit = sess.scalar(
            select(AuditLog).where(
                and_(AuditLog.company_id == cid, AuditLog.event_type == "OPENING_JOURNAL_REVERSED")
            )
        )
        assert audit is not None


# ==============================================================================
# 10. Immutability of Posted Opening Journal
# ==============================================================================

def test_immutability_of_posted_opening_journal(acct_env):
    """Scenario 10: Posted opening journals cannot be deleted or directly modified."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    accs = _get_accounts_by_code(acct_svc, cid)
    cash_id = accs["CASH"]["id"]

    op_journal = acct_svc.post_opening_balances(
        company_id=cid,
        financial_year="2026-2027",
        opening_balances=[{"account_id": cash_id, "amount": Decimal("15000.00")}],
        authorization_confirmed=True,
    )

    with pytest.raises(ImmutableJournalError):
        acct_svc.delete_journal_entry(cid, op_journal["id"])


# ==============================================================================
# 11. Year-End Closing with Net Profit Transferred to Retained Earnings
# ==============================================================================

def test_year_end_closing_with_net_profit_transferred_to_retained_earnings(acct_env):
    """Scenario 11: Net Profit is transferred to Retained Earnings (Equity) upon FY closing."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]
    uid = acct_env["user_id"]
    accs = _get_accounts_by_code(acct_svc, cid)

    cash_id = accs["CASH"]["id"]
    sales_id = accs["SALES"]["id"]
    purch_id = accs["PURCHASE"]["id"]
    ret_id = accs["RETAINED_EARNINGS"]["id"]

    # 1. Post operational sales (100,000) and purchases (60,000) -> Net Profit = 40,000
    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-06-15",
        lines=[
            {"account_id": cash_id, "debit": Decimal("100000.00"), "credit": Decimal("0.00")},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("100000.00")},
        ],
        financial_year="2026-2027",
    )
    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="PURCHASE",
        voucher_date="2026-07-20",
        lines=[
            {"account_id": purch_id, "debit": Decimal("60000.00"), "credit": Decimal("0.00")},
            {"account_id": cash_id, "debit": Decimal("0.00"), "credit": Decimal("60000.00")},
        ],
        financial_year="2026-2027",
    )

    # 2. Close financial year
    close_res = acct_svc.close_financial_year(
        company_id=cid,
        financial_year="2026-2027",
        closing_date="2027-03-31",
        user_id=uid,
        notes="FY 2026-2027 audited closing",
        authorization_confirmed=True,
    )

    assert close_res["status"] == "CLOSED"
    assert close_res["net_profit_or_loss"] == "40000.00"
    assert close_res["is_profit"] is True

    # 3. Verify closing journal lines
    cls_j = close_res["closing_journal"]
    assert cls_j["voucher_type"] == "YEAR_END_CLOSING"
    assert cls_j["voucher_number"] == "CLS-2026-2027"

    cls_lines = {l["account_code"]: l for l in cls_j["lines"]}
    # Sales debited 100,000 to close credit balance
    assert cls_lines["SALES"]["debit"] == "100000.00"
    # Purchase credited 60,000 to close debit balance
    assert cls_lines["PURCHASE"]["credit"] == "60000.00"
    # Retained Earnings credited 40,000 with Net Profit
    assert cls_lines["RETAINED_EARNINGS"]["credit"] == "40000.00"


# ==============================================================================
# 12. Year-End Closing with Net Loss Transferred to Retained Earnings
# ==============================================================================

def test_year_end_closing_with_net_loss_transferred_to_retained_earnings(acct_env):
    """Scenario 12: Net Loss is debited to Retained Earnings (Equity) upon FY closing."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]
    accs = _get_accounts_by_code(acct_svc, cid)

    cash_id = accs["CASH"]["id"]
    sales_id = accs["SALES"]["id"]
    purch_id = accs["PURCHASE"]["id"]

    # Sales 30,000, Purchases 50,000 -> Net Loss = -20,000
    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-08-01",
        lines=[
            {"account_id": cash_id, "debit": Decimal("30000.00"), "credit": Decimal("0.00")},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("30000.00")},
        ],
        financial_year="2026-2027",
    )
    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="PURCHASE",
        voucher_date="2026-08-10",
        lines=[
            {"account_id": purch_id, "debit": Decimal("50000.00"), "credit": Decimal("0.00")},
            {"account_id": cash_id, "debit": Decimal("0.00"), "credit": Decimal("50000.00")},
        ],
        financial_year="2026-2027",
    )

    close_res = acct_svc.close_financial_year(
        company_id=cid,
        financial_year="2026-2027",
        authorization_confirmed=True,
    )

    assert close_res["status"] == "CLOSED"
    assert close_res["net_profit_or_loss"] == "-20000.00"
    assert close_res["is_profit"] is False

    cls_lines = {l["account_code"]: l for l in close_res["closing_journal"]["lines"]}
    # Retained Earnings debited 20,000 for Net Loss
    assert cls_lines["RETAINED_EARNINGS"]["debit"] == "20000.00"


# ==============================================================================
# 13. Nominal Accounts Zeroed Out Post-Closing in Trial Balance
# ==============================================================================

def test_nominal_accounts_zeroed_out_post_closing_in_trial_balance(acct_env):
    """Scenario 13: Trial Balance shows 0.00 for nominal accounts post-closing, retaining balance."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]
    accs = _get_accounts_by_code(acct_svc, cid)

    cash_id = accs["CASH"]["id"]
    sales_id = accs["SALES"]["id"]

    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-09-01",
        lines=[
            {"account_id": cash_id, "debit": Decimal("80000.00"), "credit": Decimal("0.00")},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("80000.00")},
        ],
        financial_year="2026-2027",
    )

    acct_svc.close_financial_year(company_id=cid, financial_year="2026-2027", authorization_confirmed=True)

    tb = acct_svc.get_trial_balance(cid, financial_year="2026-2027")
    assert tb["is_balanced"] is True
    tb_lines = {item["account_code"]: item for item in tb["accounts"]}

    # Sales is closed to zero (omitted or 0.00)
    if "SALES" in tb_lines:
        assert tb_lines["SALES"]["net_balance"] == "0.00"
    assert tb_lines["CASH"]["debit"] == "80000.00"
    assert tb_lines["RETAINED_EARNINGS"]["credit"] == "80000.00"


# ==============================================================================
# 14. Permanent Account Balances Preserved Post-Closing
# ==============================================================================

def test_permanent_account_balances_preserved_post_closing(acct_env):
    """Scenario 14: Asset and liability balances remain identical before and after closing."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]
    accs = _get_accounts_by_code(acct_svc, cid)

    cash_id = accs["CASH"]["id"]
    sup = acct_svc.create_account(cid, "SUP_PERM", "Supplier Permanent", "GRP_SUNDRY_CREDITORS", account_type="Creditor")

    # Capital injection: 150,000 Cash, 50,000 Creditor
    acct_svc.post_opening_balances(
        company_id=cid,
        financial_year="2026-2027",
        opening_balances=[
            {"account_id": cash_id, "amount": Decimal("150000.00"), "balance_type": "DR"},
            {"account_id": sup["id"], "amount": Decimal("50000.00"), "balance_type": "CR"},
        ],
        authorization_confirmed=True,
    )

    # Pre-closing balances
    pre_coa = _get_accounts_by_code(acct_svc, cid)
    cash_pre = pre_coa["CASH"]["current_balance"]
    sup_pre = pre_coa["SUP_PERM"]["current_balance"]

    acct_svc.close_financial_year(company_id=cid, financial_year="2026-2027", authorization_confirmed=True)

    # Post-closing balances
    post_coa = _get_accounts_by_code(acct_svc, cid)
    assert post_coa["CASH"]["current_balance"] == cash_pre
    assert post_coa["SUP_PERM"]["current_balance"] == sup_pre


# ==============================================================================
# 15. P&L Report Operational Figures Preserved Post-Closing
# ==============================================================================

def test_profit_and_loss_report_operational_figures_preserved_post_closing(acct_env):
    """Scenario 15: P&L statement filters out YEAR_END_CLOSING vouchers and preserves operational figures."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]
    accs = _get_accounts_by_code(acct_svc, cid)

    cash_id = accs["CASH"]["id"]
    sales_id = accs["SALES"]["id"]
    purch_id = accs["PURCHASE"]["id"]

    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-10-01",
        lines=[
            {"account_id": cash_id, "debit": Decimal("90000.00"), "credit": Decimal("0.00")},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("90000.00")},
        ],
        financial_year="2026-2027",
    )
    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="PURCHASE",
        voucher_date="2026-10-05",
        lines=[
            {"account_id": purch_id, "debit": Decimal("40000.00"), "credit": Decimal("0.00")},
            {"account_id": cash_id, "debit": Decimal("0.00"), "credit": Decimal("40000.00")},
        ],
        financial_year="2026-2027",
    )

    pnl_pre = acct_svc.get_profit_and_loss(cid, financial_year="2026-2027")
    assert pnl_pre["total_income"] == "90000.00"
    assert pnl_pre["total_expense"] == "40000.00"
    assert pnl_pre["net_profit"] == "50000.00"

    # Close FY
    acct_svc.close_financial_year(company_id=cid, financial_year="2026-2027", authorization_confirmed=True)

    # P&L after closing must still show the exact operational performance!
    pnl_post = acct_svc.get_profit_and_loss(cid, financial_year="2026-2027")
    assert pnl_post["total_income"] == "90000.00"
    assert pnl_post["total_expense"] == "40000.00"
    assert pnl_post["net_profit"] == "50000.00"


# ==============================================================================
# 16. Balance Sheet Equality Maintained Post-Closing Without Double-Counting
# ==============================================================================

def test_balance_sheet_equality_maintained_post_closing_without_double_counting(acct_env):
    """Scenario 16: Balance Sheet Assets == Liab + Equity holds before and after closing with 0 difference."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]
    accs = _get_accounts_by_code(acct_svc, cid)

    cash_id = accs["CASH"]["id"]
    sales_id = accs["SALES"]["id"]
    cap = acct_svc.create_account(cid, "CAP_EQ", "Capital Equity", "GRP_CAPITAL", account_type="Capital")

    # Initial opening balance
    acct_svc.post_opening_balances(
        company_id=cid,
        financial_year="2026-2027",
        opening_balances=[
            {"account_id": cash_id, "amount": Decimal("100000.00"), "balance_type": "DR"},
            {"account_id": cap["id"], "amount": Decimal("100000.00"), "balance_type": "CR"},
        ],
        authorization_confirmed=True,
    )

    # Make 50,000 cash sales
    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-11-01",
        lines=[
            {"account_id": cash_id, "debit": Decimal("50000.00"), "credit": Decimal("0.00")},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("50000.00")},
        ],
        financial_year="2026-2027",
    )

    # 1. Before closing: Assets = 150,000, Capital = 100,000, Net Profit = 50,000 -> Balanced!
    bs_open = acct_svc.get_balance_sheet(cid, financial_year="2026-2027")
    assert bs_open["is_balanced"] is True
    assert bs_open["is_financial_year_closed"] is False
    assert bs_open["total_assets"] == "150000.00"
    assert bs_open["total_equity"] == "100000.00"
    assert bs_open["net_profit_for_period"] == "50000.00"
    assert bs_open["total_liabilities_and_equity"] == "150000.00"
    assert bs_open["difference"] == "0.00"

    # 2. Close FY
    acct_svc.close_financial_year(company_id=cid, financial_year="2026-2027", authorization_confirmed=True)

    # 3. After closing: Assets = 150,000, Equity = 150,000 (Capital 100k + Retained Earnings 50k).
    # net_profit_for_period added in BS is 0.00 to avoid double counting!
    bs_closed = acct_svc.get_balance_sheet(cid, financial_year="2026-2027")
    assert bs_closed["is_balanced"] is True
    assert bs_closed["is_financial_year_closed"] is True
    assert bs_closed["total_assets"] == "150000.00"
    assert bs_closed["total_equity"] == "150000.00"
    assert bs_closed["total_liabilities_and_equity"] == "150000.00"
    assert bs_closed["difference"] == "0.00"


# ==============================================================================
# 17. Rejection of Double-Closing Already Closed Financial Year
# ==============================================================================

def test_rejection_of_double_closing_already_closed_financial_year(acct_env):
    """Scenario 17: Attempting to close an already closed financial year raises FinancialYearClosedError."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]

    acct_svc.close_financial_year(company_id=cid, financial_year="2026-2027", authorization_confirmed=True)

    with pytest.raises(FinancialYearClosedError):
        acct_svc.close_financial_year(company_id=cid, financial_year="2026-2027", authorization_confirmed=True)


# ==============================================================================
# 18. Controlled Reopening of Closed Financial Year
# ==============================================================================

def test_controlled_reopening_of_closed_financial_year(acct_env):
    """Scenario 18: Authorized reopening reverses closing journal, updates status to REOPENED."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]
    accs = _get_accounts_by_code(acct_svc, cid)

    cash_id = accs["CASH"]["id"]
    sales_id = accs["SALES"]["id"]

    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-11-15",
        lines=[
            {"account_id": cash_id, "debit": Decimal("35000.00"), "credit": Decimal("0.00")},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("35000.00")},
        ],
        financial_year="2026-2027",
    )

    close_res = acct_svc.close_financial_year(company_id=cid, financial_year="2026-2027", authorization_confirmed=True)
    assert close_res["status"] == "CLOSED"

    # Reopen
    reopen_res = acct_svc.reopen_financial_year(
        company_id=cid,
        financial_year="2026-2027",
        reopen_reason="Auditor found missed expense invoice",
        authorization_confirmed=True,
    )

    assert reopen_res["status"] == "REOPENED"
    rec = acct_svc.get_financial_year_closing(cid, "2026-2027")
    assert rec["status"] == "REOPENED"

    # Operational status restored: Sales account balance is back in Trial Balance
    tb = acct_svc.get_trial_balance(cid, financial_year="2026-2027")
    tb_lines = {item["account_code"]: item for item in tb["accounts"]}
    assert tb_lines["SALES"]["credit"] == "35000.00"
    assert tb["is_balanced"] is True


# ==============================================================================
# 19. Carry-Forward to Next Financial Year Creates Balanced Opening Journal
# ==============================================================================

def test_carry_forward_to_next_financial_year_creates_balanced_opening_journal(acct_env):
    """Scenario 19: Permanent accounts carry forward into next FY's balanced opening journal."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]
    accs = _get_accounts_by_code(acct_svc, cid)

    cash_id = accs["CASH"]["id"]
    sales_id = accs["SALES"]["id"]
    purch_id = accs["PURCHASE"]["id"]
    cap = acct_svc.create_account(cid, "CAP_CF", "Capital CarryForward", "GRP_CAPITAL", account_type="Capital")

    # Initial opening
    acct_svc.post_opening_balances(
        company_id=cid,
        financial_year="2026-2027",
        opening_balances=[
            {"account_id": cash_id, "amount": Decimal("200000.00"), "balance_type": "DR"},
            {"account_id": cap["id"], "amount": Decimal("200000.00"), "balance_type": "CR"},
        ],
        authorization_confirmed=True,
    )

    # Activity: Sales 100,000, Purchases 40,000 -> Net Profit = 60,000. Ending Cash = 260,000.
    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-12-01",
        lines=[
            {"account_id": cash_id, "debit": Decimal("100000.00"), "credit": Decimal("0.00")},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("100000.00")},
        ],
        financial_year="2026-2027",
    )
    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="PURCHASE",
        voucher_date="2026-12-05",
        lines=[
            {"account_id": purch_id, "debit": Decimal("40000.00"), "credit": Decimal("0.00")},
            {"account_id": cash_id, "debit": Decimal("0.00"), "credit": Decimal("40000.00")},
        ],
        financial_year="2026-2027",
    )

    # Close 2026-2027
    acct_svc.close_financial_year(company_id=cid, financial_year="2026-2027", authorization_confirmed=True)

    # Carry forward to 2027-2028
    cf_res = acct_svc.carry_forward_to_next_financial_year(
        company_id=cid,
        current_financial_year="2026-2027",
        authorization_confirmed=True,
    )

    assert cf_res["source_financial_year"] == "2026-2027"
    assert cf_res["next_financial_year"] == "2027-2028"
    assert cf_res["total_carried_forward"] == "260000.00"

    next_j = cf_res["opening_journal"]
    assert next_j["voucher_number"] == "OP-2027-2028"
    assert next_j["financial_year"] == "2027-2028"

    # Verify no nominal accounts in next opening journal
    line_codes = {l["account_code"] for l in next_j["lines"]}
    assert "SALES" not in line_codes
    assert "PURCHASE" not in line_codes

    # Cash 260,000 Dr, Capital 200,000 Cr, Retained Earnings 60,000 Cr
    lines_by_code = {l["account_code"]: l for l in next_j["lines"]}
    assert lines_by_code["CASH"]["debit"] == "260000.00"
    assert lines_by_code["CAP_CF"]["credit"] == "200000.00"
    assert lines_by_code["RETAINED_EARNINGS"]["credit"] == "60000.00"

    # Verify Trial Balance in next year is balanced
    tb_next = acct_svc.get_trial_balance(cid, financial_year="2027-2028")
    assert tb_next["is_balanced"] is True
    assert tb_next["total_debit"] == "260000.00"
    assert tb_next["total_credit"] == "260000.00"


# ==============================================================================
# 20. General Ledger & Day Book Traceability
# ==============================================================================

def test_general_ledger_and_day_book_traceability_of_closing_and_opening_journals(acct_env):
    """Scenario 20: Full audit trail traceability of opening and closing entries in GL and Day Book."""
    acct_svc = acct_env["accounting_service"]
    cid = acct_env["company_id"]
    bid = acct_env["branch_id"]
    accs = _get_accounts_by_code(acct_svc, cid)

    cash_id = accs["CASH"]["id"]
    sales_id = accs["SALES"]["id"]
    ret_id = accs["RETAINED_EARNINGS"]["id"]

    # 1. Post opening balances
    acct_svc.post_opening_balances(
        company_id=cid,
        financial_year="2026-2027",
        opening_balances=[{"account_id": cash_id, "amount": Decimal("50000.00")}],
        voucher_date="2026-04-01",
        authorization_confirmed=True,
    )

    # 2. Post sales
    acct_svc.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="2026-05-10",
        lines=[
            {"account_id": cash_id, "debit": Decimal("25000.00"), "credit": Decimal("0.00")},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("25000.00")},
        ],
        financial_year="2026-2027",
    )

    # 3. Close FY
    acct_svc.close_financial_year(
        company_id=cid,
        financial_year="2026-2027",
        closing_date="2027-03-31",
        authorization_confirmed=True,
    )

    # 4. Verify Day Book lists all 3 vouchers in chronological sequence
    day_book = acct_svc.get_day_book(cid, start_date="2026-04-01", end_date="2027-03-31")
    vch_types = [j["voucher_type"] for j in day_book]
    assert vch_types == ["OPENING", "SALES", "YEAR_END_CLOSING"]

    # 5. Verify General Ledger of Retained Earnings contains the closing entry
    gl_ret = acct_svc.get_general_ledger(cid, account_id=ret_id, financial_year="2026-2027")
    assert gl_ret["period_credit"] == "25000.00"
    assert gl_ret["closing_balance"] == "25000.00"
    assert gl_ret["closing_balance_type"] == "Cr"
    assert len(gl_ret["entries"]) == 1
    assert gl_ret["entries"][0]["voucher_type"] == "YEAR_END_CLOSING"
    assert gl_ret["entries"][0]["voucher_number"] == "CLS-2026-2027"
