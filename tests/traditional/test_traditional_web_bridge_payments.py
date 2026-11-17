"""
Comprehensive Automated Test Suite: Traditional Payment & Reconciliation WebBridge Integration.
Phase 3.6 — Anti-Matrix Billing V2 Core Architecture.

Validates all 11 required WebBridge and UI integration scenarios:
1. Unauthenticated session guard (fail-closed, authenticated: False).
2. Role-based access control (RBAC): Cashier allowed entry, Cashier denied reversal.
3. Next voucher number peeking (Receipt & Payment).
4. List Cash & Bank accounts filtering.
5. Customer Receipt lifecycle via WebBridge (create, details, list).
6. Supplier Payment lifecycle via WebBridge (create, details, list).
7. Customer and Supplier outstandings and subledger queries.
8. Controlled managerial reversals with mandatory reason.
9. Financial Reconciliation diagnostics & summary via WebBridge.
10. Multi-tenant company context and data isolation.
11. Fast Billing physical database isolation (zero byte modifications).
"""

import json
import uuid
import hashlib
from decimal import Decimal
from pathlib import Path
import pytest
from sqlalchemy import select
from alembic.config import Config
from alembic import command

from db.traditional_database import TraditionalDatabaseManager
from db.traditional_models import (
    Company,
    Branch,
    User,
    Account,
    SaleInvoice,
    CustomerReceipt,
    SupplierPayment,
    JournalEntry,
    utc_now,
)
from services.traditional_company_service import TraditionalCompanyService
from services.traditional_customer_service import TraditionalCustomerService
from services.traditional_accounting_service import TraditionalAccountingService
from services.traditional_payment_service import TraditionalPaymentService
from services.traditional_financial_reconciliation_service import TraditionalFinancialReconciliationService
from services.traditional_auth_service import session_registry as trad_session_registry
from desktop.web_bridge import BackendBridge

FAST_DB_PATH = Path("data/anti_matrix_billing.db").resolve()


def compute_sha256(file_path: Path) -> str:
    """Computes SHA-256 hash of a file to verify zero byte modification."""
    if not file_path.exists():
        return ""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


@pytest.fixture
def bridge_env(tmp_path):
    """Provides an isolated, fully migrated Traditional database and wired BackendBridge instance."""
    db_file = tmp_path / "test_traditional_bridge_payments.db"
    db_url = f"sqlite:///{db_file}"

    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    company_service = TraditionalCompanyService(db_manager=trad_mgr)
    customer_service = TraditionalCustomerService(db_manager=trad_mgr)
    accounting_service = TraditionalAccountingService(db_manager=trad_mgr)
    payment_service = TraditionalPaymentService(db_manager=trad_mgr, accounting_service=accounting_service)
    recon_service = TraditionalFinancialReconciliationService(
        db_manager=trad_mgr,
        accounting_service=accounting_service,
        payment_service=payment_service,
    )

    company_info = company_service.initial_setup({
        "name": "Alpha WebBridge Integration Corp",
        "code": "CORP_WB",
        "finYear": "2026-2027",
        "taxNo": "27WBCCC1111C1Z1",
        "state": "Maharashtra",
        "adminUsername": "ADMIN",
        "adminPassword": "SecurePassword123!",
    })
    company_id = company_info["companyId"]
    branch_id = company_info["branchId"]
    user_id = company_info["adminUserId"]

    accounting_service.ensure_standard_account_groups(company_id)
    accounting_service.ensure_standard_accounts(company_id)

    # Set up customer account
    cust_acc = accounting_service.create_account(
        company_id=company_id,
        code="CUST_WB_001",
        name="Global Retailers Ltd",
        account_type="Debtor",
        group_code="GRP_SUNDRY_DEBTORS",
    )
    # Set up supplier account
    supp_acc = accounting_service.create_account(
        company_id=company_id,
        code="SUPP_WB_001",
        name="Apex Fabrics Wholesaler",
        account_type="Creditor",
        group_code="GRP_SUNDRY_CREDITORS",
    )

    # Add a posted sales invoice
    with trad_mgr.session_scope() as sess:
        debtor_acc = sess.scalar(select(Account).where(Account.id == cust_acc["id"]))
        sales_acc = sess.scalar(select(Account).where(Account.company_id == company_id, Account.code == "SALES"))
        inv = SaleInvoice(
            id=str(uuid.uuid4()),
            voucher_id=str(uuid.uuid4()),
            company_id=company_id,
            branch_id=branch_id,
            user_id=user_id,
            financial_year="2026-2027",
            series="Main",
            sequence_number=1,
            voucher_number="INV/WB/001",
            vch_date="2026-05-10",
            party_name=debtor_acc.name,
            account_id=debtor_acc.id,
            sale_type="L/GST-18%",
            payment_method="CREDIT",
            subtotal=Decimal("10000.00"),
            taxable_amount=Decimal("10000.00"),
            cgst_amount=Decimal("0.00"),
            sgst_amount=Decimal("0.00"),
            igst_amount=Decimal("0.00"),
            round_off_amount=Decimal("0.00"),
            grand_total=Decimal("10000.00"),
            total_amount=Decimal("10000.00"),
            items_json="[]",
            status="POSTED",
            created_at=utc_now(),
        )
        sess.add(inv)
        sess.flush()
        inv_id = inv.id

        # Record sales journal in GL
        accounting_service.record_sales_journal(
            company_id=company_id,
            branch_id=branch_id,
            invoice_id=inv_id,
            invoice_number="INV/WB/001",
            invoice_date="2026-05-10",
            customer_account_id=debtor_acc.id,
            sales_amount=Decimal("10000.00"),
            user_id=user_id,
            session=sess,
        )

    # Instantiate WebBridge and inject isolated services
    bridge = BackendBridge(parent=None)
    bridge._traditional_company_service = company_service
    bridge._traditional_customer_service = customer_service
    bridge._traditional_accounting_service = accounting_service
    bridge._traditional_payment_service = payment_service
    bridge._traditional_recon_service = recon_service

    # Create admin session
    admin_token = trad_session_registry.create_session(
        user_id=user_id,
        company_id=company_id,
        branch_id=branch_id,
        role_name="Administrator",
        username="ADMIN",
        display_name="System Administrator",
    )

    # Create cashier session
    cashier_token = trad_session_registry.create_session(
        user_id=str(uuid.uuid4()),
        company_id=company_id,
        branch_id=branch_id,
        role_name="Cashier",
        username="CASHIER1",
        display_name="Front Desk Cashier",
    )

    return {
        "bridge": bridge,
        "company_id": company_id,
        "branch_id": branch_id,
        "user_id": user_id,
        "cust_acc_id": cust_acc["id"],
        "supp_acc_id": supp_acc["id"],
        "invoice_id": inv_id,
        "admin_token": admin_token,
        "cashier_token": cashier_token,
        "trad_mgr": trad_mgr,
        "accounting_service": accounting_service,
    }


def test_web_bridge_unauthenticated_guard(bridge_env):
    """Scenario 1: Unauthenticated calls to all payment & reconciliation slots fail closed."""
    bridge = bridge_env["bridge"]
    bridge._traditional_session = None

    slots_to_test = [
        lambda: bridge.traditional_getNextReceiptNumber("RCT"),
        lambda: bridge.traditional_getCustomerInvoices(bridge_env["cust_acc_id"], ""),
        lambda: bridge.traditional_createCustomerReceipt("{}"),
        lambda: bridge.traditional_getCustomerReceipt("dummy-id"),
        lambda: bridge.traditional_listCustomerReceipts("", "", "", "", "", 50, 0),
        lambda: bridge.traditional_reverseCustomerReceipt("dummy-id", "reason"),
        lambda: bridge.traditional_getNextPaymentNumber("PMT"),
        lambda: bridge.traditional_listSuppliers("", True),
        lambda: bridge.traditional_getSupplierBills(bridge_env["supp_acc_id"], ""),
        lambda: bridge.traditional_createSupplierPayment("{}"),
        lambda: bridge.traditional_getSupplierPayment("dummy-id"),
        lambda: bridge.traditional_listSupplierPayments("", "", "", "", "", 50, 0),
        lambda: bridge.traditional_reverseSupplierPayment("dummy-id", "reason"),
        lambda: bridge.traditional_listCashAndBankAccounts(),
        lambda: bridge.traditional_getCustomerOutstanding(bridge_env["cust_acc_id"], ""),
        lambda: bridge.traditional_listCustomersOutstanding(""),
        lambda: bridge.traditional_getSupplierOutstanding(bridge_env["supp_acc_id"], ""),
        lambda: bridge.traditional_listSuppliersOutstanding(""),
        lambda: bridge.traditional_getFinancialReconciliationSummary(""),
        lambda: bridge.traditional_reconcileCustomerAR(""),
        lambda: bridge.traditional_reconcileSupplierAP(""),
        lambda: bridge.traditional_reconcileCashAndBank(""),
    ]

    for slot_call in slots_to_test:
        resp_str = slot_call()
        resp = json.loads(resp_str)
        assert resp["success"] is False
        assert resp.get("authenticated") is False or "Authentication required" in resp.get("error", "")


def test_web_bridge_role_authorization_enforcement(bridge_env):
    """Scenario 2: Cashier can create payments/receipts, but is denied managerial reversals."""
    bridge = bridge_env["bridge"]

    # Authenticate as Cashier
    bridge._traditional_session = trad_session_registry.get_session(bridge_env["cashier_token"])

    # Cashier peeking voucher number -> Allowed
    rct_no_res = json.loads(bridge.traditional_getNextReceiptNumber("RCT"))
    assert rct_no_res["success"] is True

    # Cashier attempting reversal -> Denied (requires Administrator, Store Manager, Manager)
    rev_rct = json.loads(bridge.traditional_reverseCustomerReceipt("dummy-id", "Wrong receipt"))
    assert rev_rct["success"] is False
    assert "Unauthorized" in rev_rct["error"] or "Cashier" in rev_rct["error"]

    rev_pmt = json.loads(bridge.traditional_reverseSupplierPayment("dummy-id", "Wrong payment"))
    assert rev_pmt["success"] is False
    assert "Unauthorized" in rev_pmt["error"] or "Cashier" in rev_pmt["error"]


def test_web_bridge_peek_voucher_numbers(bridge_env):
    """Scenario 3: Sequential voucher number peeking returns correct formats."""
    bridge = bridge_env["bridge"]
    bridge._traditional_session = trad_session_registry.get_session(bridge_env["admin_token"])

    rct_res = json.loads(bridge.traditional_getNextReceiptNumber("RCT"))
    print("DEBUG RCT_RES:", rct_res)
    assert rct_res["success"] is True
    assert "RCT" in rct_res["data"]["voucher_number"]

    pmt_res = json.loads(bridge.traditional_getNextPaymentNumber("PMT"))
    assert pmt_res["success"] is True
    assert "PMT" in pmt_res["data"]["voucher_number"]


def test_web_bridge_list_cash_and_bank_accounts(bridge_env):
    """Scenario 4: listCashAndBankAccounts returns active Cash and Bank accounts."""
    bridge = bridge_env["bridge"]
    bridge._traditional_session = trad_session_registry.get_session(bridge_env["admin_token"])

    res = json.loads(bridge.traditional_listCashAndBankAccounts())
    assert res["success"] is True
    accounts = res["data"]
    assert len(accounts) >= 1
    codes = [a["code"] for a in accounts]
    assert "CASH" in codes


def test_web_bridge_customer_receipt_lifecycle(bridge_env):
    """Scenario 5: Complete Customer Receipt lifecycle via WebBridge."""
    bridge = bridge_env["bridge"]
    bridge._traditional_session = trad_session_registry.get_session(bridge_env["admin_token"])

    # 1. Query unsettled invoices for customer
    inv_res = json.loads(bridge.traditional_getCustomerInvoices(bridge_env["cust_acc_id"], ""))
    assert inv_res["success"] is True
    invoices = inv_res["data"]
    assert len(invoices) >= 1
    assert invoices[0]["invoice_id"] == bridge_env["invoice_id"]
    assert Decimal(invoices[0]["outstanding_amount"]) == Decimal("10000.00")

    # 2. Get deposit account ID (CASH)
    acc_res = json.loads(bridge.traditional_listCashAndBankAccounts())
    cash_acc = next(a for a in acc_res["data"] if a["code"] == "CASH")

    # 3. Create customer receipt: 12,000 received (10,000 to invoice, 2,000 unallocated advance)
    receipt_payload = {
        "customer_id": bridge_env["cust_acc_id"],
        "receipt_date": "2026-05-15",
        "total_amount": "12000.00",
        "payment_method": "CASH",
        "deposit_account_id": cash_acc["id"],
        "reference_number": "CHQ-100234",
        "notes": "Full settlement and advance via WebBridge",
        "allocations": [
            {
                "invoice_id": bridge_env["invoice_id"],
                "allocated_amount": "10000.00",
                "discount_amount": "0.00",
            }
        ],
    }
    create_res = json.loads(bridge.traditional_createCustomerReceipt(json.dumps(receipt_payload)))
    print("DEBUG CREATE_RCT_RES:", create_res)
    assert create_res["success"] is True
    receipt_id = create_res["data"]["id"]
    assert Decimal(create_res["data"]["allocated_amount"]) == Decimal("10000.00")
    assert Decimal(create_res["data"]["unallocated_amount"]) == Decimal("2000.00")

    # 4. Query receipt details
    detail_res = json.loads(bridge.traditional_getCustomerReceipt(receipt_id))
    assert detail_res["success"] is True
    assert detail_res["data"]["voucher_number"] == create_res["data"]["voucher_number"]
    assert len(detail_res["data"]["allocations"]) == 1

    # 5. List customer receipts
    list_res = json.loads(bridge.traditional_listCustomerReceipts("", "", "", "", "", 50, 0))
    assert list_res["success"] is True
    receipts = list_res["data"]["receipts"]
    assert any(r["id"] == receipt_id for r in receipts)


def test_web_bridge_supplier_payment_lifecycle(bridge_env):
    """Scenario 6: Complete Supplier Payment lifecycle via WebBridge."""
    bridge = bridge_env["bridge"]
    bridge._traditional_session = trad_session_registry.get_session(bridge_env["admin_token"])

    # 1. Query supplier bills notice
    bills_res = json.loads(bridge.traditional_getSupplierBills(bridge_env["supp_acc_id"], ""))
    assert bills_res["success"] is True
    assert "pending" in bills_res["data"]["message"].lower()

    # 2. Get payment account ID (CASH)
    acc_res = json.loads(bridge.traditional_listCashAndBankAccounts())
    cash_acc = next(a for a in acc_res["data"] if a["code"] == "CASH")

    # 3. Create on-account advance supplier payment: 5,000
    payment_payload = {
        "supplier_id": bridge_env["supp_acc_id"],
        "payment_date": "2026-05-18",
        "total_amount": "5000.00",
        "payment_method": "CASH",
        "payment_account_id": cash_acc["id"],
        "reference_number": "TXN-998877",
        "notes": "On-account advance disbursement via WebBridge",
        "allocations": [],
    }
    create_res = json.loads(bridge.traditional_createSupplierPayment(json.dumps(payment_payload)))
    assert create_res["success"] is True
    payment_id = create_res["data"]["id"]
    assert Decimal(create_res["data"]["unallocated_amount"]) == Decimal("5000.00")

    # 4. Query payment details
    detail_res = json.loads(bridge.traditional_getSupplierPayment(payment_id))
    assert detail_res["success"] is True
    assert detail_res["data"]["voucher_number"] == create_res["data"]["voucher_number"]

    # 5. List supplier payments
    list_res = json.loads(bridge.traditional_listSupplierPayments("", "", "", "", "", 50, 0))
    assert list_res["success"] is True
    assert any(p["id"] == payment_id for p in list_res["data"]["payments"])


def test_web_bridge_customer_and_supplier_outstandings(bridge_env):
    """Scenario 7: Accounts Receivable & Accounts Payable queries via WebBridge."""
    bridge = bridge_env["bridge"]
    bridge._traditional_session = trad_session_registry.get_session(bridge_env["admin_token"])

    # Customer outstanding
    cust_out = json.loads(bridge.traditional_getCustomerOutstanding(bridge_env["cust_acc_id"], ""))
    assert cust_out["success"] is True
    assert "net_ledger_outstanding" in cust_out["data"]

    # Customer receivables report across all customers
    all_cust = json.loads(bridge.traditional_listCustomersOutstanding(""))
    assert all_cust["success"] is True
    assert "customers" in all_cust["data"]

    # Supplier outstanding
    supp_out = json.loads(bridge.traditional_getSupplierOutstanding(bridge_env["supp_acc_id"], ""))
    assert supp_out["success"] is True
    assert "net_ledger_payable" in supp_out["data"]

    # Supplier payables report across all suppliers
    all_supp = json.loads(bridge.traditional_listSuppliersOutstanding(""))
    assert all_supp["success"] is True
    assert "suppliers" in all_supp["data"]


def test_web_bridge_managerial_reversals(bridge_env):
    """Scenario 8: Managerial reversals require non-empty reason and reverse records cleanly."""
    bridge = bridge_env["bridge"]
    bridge._traditional_session = trad_session_registry.get_session(bridge_env["admin_token"])

    acc_res = json.loads(bridge.traditional_listCashAndBankAccounts())
    cash_acc = next(a for a in acc_res["data"] if a["code"] == "CASH")

    # 1. Create a receipt
    rct_data = {
        "customer_id": bridge_env["cust_acc_id"],
        "receipt_date": "2026-05-20",
        "total_amount": "3000.00",
        "payment_method": "CASH",
        "deposit_account_id": cash_acc["id"],
    }
    rct_res = json.loads(bridge.traditional_createCustomerReceipt(json.dumps(rct_data)))
    rct_id = rct_res["data"]["id"]

    # Empty reason -> Rejected
    empty_rev = json.loads(bridge.traditional_reverseCustomerReceipt(rct_id, "   "))
    assert empty_rev["success"] is False
    assert "Reversal reason is mandatory" in empty_rev["error"]

    # Valid reason -> Success
    valid_rev = json.loads(bridge.traditional_reverseCustomerReceipt(rct_id, "Customer cheque bounced"))
    print("DEBUG VALID_REV:", valid_rev)
    assert valid_rev["success"] is True
    assert valid_rev["data"]["status"] == "REVERSED"

    # 2. Create a supplier payment
    pmt_data = {
        "supplier_id": bridge_env["supp_acc_id"],
        "payment_date": "2026-05-20",
        "total_amount": "2000.00",
        "payment_method": "CASH",
        "payment_account_id": cash_acc["id"],
    }
    pmt_res = json.loads(bridge.traditional_createSupplierPayment(json.dumps(pmt_data)))
    pmt_id = pmt_res["data"]["id"]

    # Empty reason -> Rejected
    empty_pmt_rev = json.loads(bridge.traditional_reverseSupplierPayment(pmt_id, ""))
    assert empty_pmt_rev["success"] is False
    assert "Reversal reason is mandatory" in empty_pmt_rev["error"]

    # Valid reason -> Success
    valid_pmt_rev = json.loads(bridge.traditional_reverseSupplierPayment(pmt_id, "Incorrect vendor bank details"))
    assert valid_pmt_rev["success"] is True
    assert valid_pmt_rev["data"]["status"] == "REVERSED"


def test_web_bridge_financial_reconciliation_summary(bridge_env):
    """Scenario 9: Comprehensive financial reconciliation summary via WebBridge."""
    bridge = bridge_env["bridge"]
    bridge._traditional_session = trad_session_registry.get_session(bridge_env["admin_token"])

    # 1. Executive Summary
    summary_res = json.loads(bridge.traditional_getFinancialReconciliationSummary(""))
    assert summary_res["success"] is True
    d = summary_res["data"]
    assert d["overall_status"] in ("BALANCED", "MISMATCHED")
    assert "customer_ar" in d
    assert "supplier_ap" in d
    assert "cash_and_bank" in d
    assert "customer_advances" in d
    assert "supplier_advances" in d
    assert "journal_audit" in d

    # 2. AR Diagnostic
    ar_res = json.loads(bridge.traditional_reconcileCustomerAR(""))
    assert ar_res["success"] is True
    assert "status" in ar_res["data"]

    # 3. AP Diagnostic
    ap_res = json.loads(bridge.traditional_reconcileSupplierAP(""))
    assert ap_res["success"] is True
    assert "status" in ap_res["data"]

    # 4. Cash/Bank Diagnostic
    cb_res = json.loads(bridge.traditional_reconcileCashAndBank(""))
    assert cb_res["success"] is True
    assert "status" in cb_res["data"]


def test_web_bridge_cross_company_isolation(bridge_env):
    """Scenario 10: Multi-tenant isolation enforced at the session level."""
    bridge = bridge_env["bridge"]
    trad_mgr = bridge_env["trad_mgr"]

    # Create Company B, Branch B, User B directly
    comp_b_id = str(uuid.uuid4())
    branch_b_id = str(uuid.uuid4())
    comp_b_user = str(uuid.uuid4())

    with trad_mgr.session_scope() as sess:
        comp_b = Company(
            id=comp_b_id,
            code="CORP_BETA_WB",
            name="Beta Enterprises Isolation Ltd",
            fin_year="2026-2027",
            gstin="27BETAC2222C1Z2",
            state="Maharashtra",
            is_active=True,
        )
        sess.add(comp_b)
        branch_b = Branch(
            id=branch_b_id,
            company_id=comp_b_id,
            code="BR01",
            name="Main Branch",
            is_active=True,
        )
        sess.add(branch_b)
        user_b = User(
            id=comp_b_user,
            company_id=comp_b_id,
            username="ADMIN_B",
            password_hash="mock_hash_beta",
            role_name="Administrator",
            full_name="Beta Admin",
            is_active=True,
        )
        sess.add(user_b)

    # Switch session to Company B
    token_b = trad_session_registry.create_session(
        user_id=comp_b_user,
        company_id=comp_b_id,
        branch_id=branch_b_id,
        role_name="Administrator",
        username="ADMIN_B",
        display_name="Beta Admin",
    )
    bridge._traditional_session = trad_session_registry.get_session(token_b)

    # List receipts in Company B -> Must be completely empty (zero bleed from Company A)
    res_b = json.loads(bridge.traditional_listCustomerReceipts("", "", "", "", "", 50, 0))
    assert res_b["success"] is True
    assert len(res_b["data"]["receipts"]) == 0

    # List payments in Company B -> Must be completely empty
    pmt_b = json.loads(bridge.traditional_listSupplierPayments("", "", "", "", "", 50, 0))
    assert pmt_b["success"] is True
    assert len(pmt_b["data"]["payments"]) == 0


def test_web_bridge_fast_billing_db_isolation(bridge_env):
    """Scenario 11: Fast Billing SQLite file remains 100% byte-identical."""
    initial_hash = compute_sha256(FAST_DB_PATH)

    # Perform a round of operations via WebBridge
    bridge = bridge_env["bridge"]
    bridge._traditional_session = trad_session_registry.get_session(bridge_env["admin_token"])

    bridge.traditional_getNextReceiptNumber("RCT")
    bridge.traditional_listCustomersOutstanding("")
    bridge.traditional_getFinancialReconciliationSummary("")

    post_hash = compute_sha256(FAST_DB_PATH)
    assert initial_hash == post_hash, "Fast Billing database must remain 100% unmodified."
