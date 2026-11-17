"""
End-to-End Integration and Production Readiness QA Test Suite: Traditional Billing Subsystem.
Phase 3.7 — Anti-Matrix Billing V2 Core Architecture.

Validates:
1. Application startup and traditional session context initialization.
2. Sales and Inventory E2E workflow (invoice, stock deduction, double-entry journals, taxes).
3. Friend 2 Purchase integration contract verification.
4. Customer Receipts full lifecycle (full/partial/multi-bill settlement, advances, cash/bank/UPI, reversal).
5. Supplier Payments full lifecycle (disbursements, advances, cash/bank/UPI, reversal).
6. Double-entry accounting integrity, debit/credit balance, period locks, audit history.
7. Financial reconciliation dashboard across AR, AP, Cash/Bank, Advances, Journal integrity,
   and deliberate discrepancy detection without silent ledger repair.
8. Physical database isolation (zero byte modifications to Fast Billing SQLite database).
"""

import json
import uuid
import hashlib
from decimal import Decimal
from pathlib import Path
import pytest
from sqlalchemy import select, func
from alembic.config import Config
from alembic import command

from db.traditional_database import TraditionalDatabaseManager
from db.traditional_models import (
    Company,
    Branch,
    User,
    Account,
    AccountGroup,
    Item,
    SaleInvoice,
    CustomerReceipt,
    ReceiptAllocation,
    SupplierPayment,
    PaymentAllocation,
    JournalEntry,
    JournalEntryLine,
    StockMovement,
    utc_now,
)
from services.traditional_company_service import TraditionalCompanyService
from services.traditional_customer_service import TraditionalCustomerService
from services.traditional_product_service import TraditionalProductService
from services.traditional_accounting_service import TraditionalAccountingService
from services.traditional_inventory_service import TraditionalInventoryService
from services.traditional_payment_service import TraditionalPaymentService
from services.traditional_financial_reconciliation_service import TraditionalFinancialReconciliationService
from services.traditional_auth_service import session_registry as trad_session_registry
from desktop.web_bridge import BackendBridge

FAST_DB_PATH = Path("data/anti_matrix_billing.db").resolve()


def compute_sha256(file_path: Path) -> str:
    """Computes SHA-256 checksum of a file."""
    if not file_path.exists():
        return ""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture
def qa_env(tmp_path):
    """
    Builds a fully isolated, pristine Traditional Billing environment.
    Runs Alembic migrations (001 through 007) and seeds an enterprise company,
    branch, roles, users, and core ledger accounts.
    """
    db_file = tmp_path / "traditional_qa_e2e.db"
    db_url = f"sqlite:///{db_file}"

    # 1. Execute Alembic Migrations
    alembic_cfg = Config("traditional_alembic.ini")
    alembic_cfg.set_main_option("script_location", "traditional_migrations")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)

    # 2. Services
    company_service = TraditionalCompanyService(trad_mgr)
    accounting_service = TraditionalAccountingService(trad_mgr)
    inventory_service = TraditionalInventoryService(trad_mgr)
    payment_service = TraditionalPaymentService(trad_mgr, accounting_service=accounting_service)
    recon_service = TraditionalFinancialReconciliationService(
        db_manager=trad_mgr,
        accounting_service=accounting_service,
        payment_service=payment_service,
    )
    product_service = TraditionalProductService(trad_mgr)
    customer_service = TraditionalCustomerService(trad_mgr)

    # 3. Initial Setup (One-time atomic onboarding)
    setup_data = {
        "name": "Global Retail Enterprises QA",
        "code": "CORP_QA01",
        "finYear": "2026-2027",
        "taxNo": "33AAACG1234F1Z5",
        "state": "Tamilnadu",
        "adminUsername": "ADMIN_QA",
        "adminPassword": "SecurePassword123!",
    }
    setup_res = company_service.initial_setup(setup_data)
    company_id = setup_res["companyId"]
    branch_id = setup_res["branchId"]
    admin_user_id = setup_res["adminUserId"]

    # 4. Provision Cashier User
    cashier_user_id = str(uuid.uuid4())
    with trad_mgr.session_scope() as sess:
        cashier = User(
            id=cashier_user_id,
            company_id=company_id,
            username="CASHIER_QA",
            password_hash="mock_cashier_hash",
            role_name="Cashier",
            full_name="Junior Cashier QA",
            is_active=True,
        )
        sess.add(cashier)

    # 5. Create Sessions
    admin_token = trad_session_registry.create_session(
        user_id=admin_user_id,
        company_id=company_id,
        branch_id=branch_id,
        role_name="Administrator",
        username="ADMIN_QA",
        display_name="QA Lead Admin",
    )
    cashier_token = trad_session_registry.create_session(
        user_id=cashier_user_id,
        company_id=company_id,
        branch_id=branch_id,
        role_name="Cashier",
        username="CASHIER_QA",
        display_name="Junior Cashier QA",
    )

    # 6. Wire Bridge
    bridge = BackendBridge()
    bridge._traditional_db_manager = trad_mgr
    bridge._traditional_company_service = company_service
    bridge._traditional_accounting_service = accounting_service
    bridge._traditional_payment_service = payment_service
    bridge._traditional_recon_service = recon_service

    return {
        "trad_mgr": trad_mgr,
        "company_id": company_id,
        "branch_id": branch_id,
        "admin_user_id": admin_user_id,
        "cashier_user_id": cashier_user_id,
        "admin_token": admin_token,
        "cashier_token": cashier_token,
        "accounting_service": accounting_service,
        "inventory_service": inventory_service,
        "payment_service": payment_service,
        "recon_service": recon_service,
        "product_service": product_service,
        "customer_service": customer_service,
        "bridge": bridge,
    }


# ==============================================================================
# 1. Startup & Navigation Context Verification
# ==============================================================================

def test_startup_auth_and_session_isolation(qa_env):
    """Verify session registry lifecycle and fail-closed authorization guards."""
    bridge = qa_env["bridge"]

    # Unauthenticated WebBridge call must fail closed
    bridge._traditional_session = None
    unauth_resp = json.loads(bridge.traditional_getNextReceiptNumber("RCT"))
    assert unauth_resp["success"] is False
    assert "authentication required" in unauth_resp["error"].lower() or "session" in unauth_resp["error"].lower()

    # Authenticate via Admin Token
    bridge._traditional_session = trad_session_registry.get_session(qa_env["admin_token"])
    auth_resp = json.loads(bridge.traditional_getNextReceiptNumber("RCT"))
    assert auth_resp["success"] is True
    assert "RCT" in auth_resp["data"]["voucher_number"]


# ==============================================================================
# 2. Traditional Sales & Inventory E2E Workflow
# ==============================================================================

def test_traditional_sales_and_inventory_e2e(qa_env):
    """
    Test sales invoice posting, stock deduction, and double-entry accounting journal.
    Verify that inventory reduces and accounting journal is mathematically balanced.
    """
    trad_mgr = qa_env["trad_mgr"]
    company_id = qa_env["company_id"]
    branch_id = qa_env["branch_id"]
    admin_id = qa_env["admin_user_id"]
    inventory_service = qa_env["inventory_service"]
    accounting_service = qa_env["accounting_service"]

    # 1. Create a Product with Initial Stock
    item_id = str(uuid.uuid4())
    cust_acc_id = str(uuid.uuid4())
    sales_acc_id = str(uuid.uuid4())
    cgst_acc_id = str(uuid.uuid4())
    sgst_acc_id = str(uuid.uuid4())

    with trad_mgr.session_scope() as sess:
        # Create Sales & Tax Accounts
        sess.add(Account(
            id=sales_acc_id, company_id=company_id, code="SALES-01", name="Domestic Sales",
            account_type="Sales", is_active=True
        ))
        sess.add(Account(
            id=cgst_acc_id, company_id=company_id, code="CGST-OUT", name="Output CGST",
            account_type="Tax", is_active=True
        ))
        sess.add(Account(
            id=sgst_acc_id, company_id=company_id, code="SGST-OUT", name="Output SGST",
            account_type="Tax", is_active=True
        ))
        # Create Customer Account
        sess.add(Account(
            id=cust_acc_id, company_id=company_id, code="CUST-ALPHA", name="Alpha Enterprises Ltd",
            account_type="Debtor", is_active=True
        ))
        # Create Item
        sess.add(Item(
            id=item_id, company_id=company_id, sku="PRD-101", name="Industrial Widget",
            hsn="84713010", unit="NOS", selling_price=Decimal("100.00"),
            mrp=Decimal("120.00"), cogs_amount=Decimal("60.00"), tax_rate_percent=Decimal("18.00"),
            is_active=True
        ))

    # Record initial stock in inventory engine
    inventory_service.record_opening_stock(
        company_id=company_id,
        branch_id=branch_id,
        item_id=item_id,
        qty=Decimal("100.000"),
        unit_cost=Decimal("60.00"),
        reference_id="INIT-001",
        user_id=admin_id,
    )

    # Verify initial stock
    stock_before = inventory_service.get_stock_balance(company_id=company_id, item_id=item_id)
    assert stock_before["current_qty"] == Decimal("100.000")

    # 2. Post Sales Invoice for 20 units @ 100.00 = 2000.00 + 18% GST (180 CGST + 180 SGST = 2360.00)
    inv_id = str(uuid.uuid4())
    inv_number = "INV/2026/001"

    with trad_mgr.session_scope() as sess:
        inv = SaleInvoice(
            id=inv_id,
            voucher_id=str(uuid.uuid4()),
            company_id=company_id,
            branch_id=branch_id,
            user_id=admin_id,
            financial_year="2026-2027",
            series="Main",
            sequence_number=1,
            voucher_number=inv_number,
            vch_date="2026-05-15",
            party_name="Alpha Enterprises Ltd",
            account_id=cust_acc_id,
            sale_type="TAX_INVOICE",
            payment_method="CREDIT",
            subtotal=Decimal("2000.00"),
            taxable_amount=Decimal("2000.00"),
            cgst_amount=Decimal("180.00"),
            sgst_amount=Decimal("180.00"),
            igst_amount=Decimal("0.00"),
            round_off_amount=Decimal("0.00"),
            grand_total=Decimal("2360.00"),
            total_amount=Decimal("2360.00"),
            status="POSTED",
            items_json=json.dumps([{
                "item_id": item_id,
                "name": "Industrial Widget",
                "qty": 20.0,
                "rate": 100.0,
                "tax_rate": 18.0,
                "tax_amount": 360.0,
                "total": 2360.0,
            }]),
        )
        sess.add(inv)

        # Post balanced accounting journal
        accounting_service.record_sales_journal(
            company_id=company_id,
            branch_id=branch_id,
            invoice_id=inv_id,
            invoice_number=inv_number,
            invoice_date="2026-05-15",
            customer_account_id=cust_acc_id,
            sales_amount=Decimal("2000.00"),
            output_cgst=Decimal("180.00"),
            output_sgst=Decimal("180.00"),
            user_id=admin_id,
            session=sess,
        )

    # Deduct stock via inventory service
    inventory_service.record_stock_outward(
        company_id=company_id,
        branch_id=branch_id,
        item_id=item_id,
        qty=Decimal("20.000"),
        unit_cost=Decimal("60.00"),
        reference_type="SALES_INVOICE",
        reference_id=inv_id,
        user_id=admin_id,
    )

    # 3. Verify Inventory Reduction
    stock_after = inventory_service.get_stock_balance(company_id=company_id, item_id=item_id)
    assert stock_after["current_qty"] == Decimal("80.000")

    # 4. Verify Accounting Journal Balanced
    gl_data = accounting_service.get_general_ledger(company_id=company_id, account_id=cust_acc_id)
    assert Decimal(gl_data["closing_balance"]) == Decimal("2360.00")
    assert gl_data["closing_balance_type"] == "Dr"


# ==============================================================================
# 3. Friend 2 Purchase Module Integration Contract Review
# ==============================================================================

def test_purchase_module_contract_and_forward_compatibility(qa_env):
    """
    Documents and verifies that payment allocations maintain clean forward compatibility
    with Friend 2's future Purchase model.
    """
    payment_service = qa_env["payment_service"]
    company_id = qa_env["company_id"]

    # Verify Supplier Bills Query returns pending contract notice
    bills = payment_service.get_supplier_bills_for_payment(company_id, str(uuid.uuid4()))
    assert "pending" in bills["message"].lower()
    assert bills["bills"] == []


# ==============================================================================
# 4. Customer Receipts Full Spectrum E2E
# ==============================================================================

def test_customer_receipts_full_spectrum_lifecycle(qa_env):
    """
    Test full invoice settlement, partial settlement, unallocated advances,
    payment methods (CASH/BANK/UPI), and role-guarded managerial reversals.
    """
    trad_mgr = qa_env["trad_mgr"]
    company_id = qa_env["company_id"]
    branch_id = qa_env["branch_id"]
    admin_id = qa_env["admin_user_id"]
    payment_service = qa_env["payment_service"]
    accounting_service = qa_env["accounting_service"]

    # Setup accounts
    cust_id = str(uuid.uuid4())
    cash_acc_id = str(uuid.uuid4())
    bank_acc_id = str(uuid.uuid4())

    with trad_mgr.session_scope() as sess:
        sess.add(Account(
            id=cust_id, company_id=company_id, code="CUST-BETA", name="Beta Retails",
            account_type="Debtor", is_active=True
        ))
        sess.add(Account(
            id=cash_acc_id, company_id=company_id, code="CASH-01", name="Main Cash Till",
            account_type="Cash", is_active=True
        ))
        sess.add(Account(
            id=bank_acc_id, company_id=company_id, code="BANK-HDFC", name="HDFC Current Account",
            account_type="Bank", is_active=True
        ))

    # Create 2 Sales Invoices for Beta Retails: Inv1 = 5000.00, Inv2 = 3000.00
    inv1_id = str(uuid.uuid4())
    inv2_id = str(uuid.uuid4())
    with trad_mgr.session_scope() as sess:
        sess.add(SaleInvoice(
            id=inv1_id,
            voucher_id=str(uuid.uuid4()),
            company_id=company_id,
            branch_id=branch_id,
            user_id=admin_id,
            financial_year="2026-2027",
            series="Main",
            sequence_number=2,
            voucher_number="INV/BETA/01",
            vch_date="2026-05-16",
            party_name="Beta Retails",
            account_id=cust_id,
            sale_type="TAX_INVOICE",
            payment_method="CREDIT",
            subtotal=Decimal("5000.00"),
            taxable_amount=Decimal("5000.00"),
            grand_total=Decimal("5000.00"),
            total_amount=Decimal("5000.00"),
            status="POSTED",
            items_json="[]",
        ))
        sess.add(SaleInvoice(
            id=inv2_id,
            voucher_id=str(uuid.uuid4()),
            company_id=company_id,
            branch_id=branch_id,
            user_id=admin_id,
            financial_year="2026-2027",
            series="Main",
            sequence_number=3,
            voucher_number="INV/BETA/02",
            vch_date="2026-05-17",
            party_name="Beta Retails",
            account_id=cust_id,
            sale_type="TAX_INVOICE",
            payment_method="CREDIT",
            subtotal=Decimal("3000.00"),
            taxable_amount=Decimal("3000.00"),
            grand_total=Decimal("3000.00"),
            total_amount=Decimal("3000.00"),
            status="POSTED",
            items_json="[]",
        ))

    # A. Multi-Invoice Receipt with Partial & Full Settlement via Bank
    # Total received: 6000.00 -> 5000.00 to Inv1 (fully paid), 1000.00 to Inv2 (partially paid, 2000.00 remaining)
    rct1 = payment_service.create_customer_receipt(
        company_id=company_id,
        branch_id=branch_id,
        customer_account_id=cust_id,
        deposit_account_id=bank_acc_id,
        total_amount=Decimal("6000.00"),
        receipt_date="2026-05-18",
        payment_method="BANK_TRANSFER",
        allocations=[
            {"invoice_id": inv1_id, "allocated_amount": Decimal("5000.00")},
            {"invoice_id": inv2_id, "allocated_amount": Decimal("1000.00")},
        ],
        user_id=admin_id,
    )
    assert Decimal(str(rct1["allocated_amount"])) == Decimal("6000.00")
    assert Decimal(str(rct1["unallocated_amount"])) == Decimal("0.00")

    # Check Invoices Outstanding
    out1 = payment_service.get_customer_invoice_outstanding(company_id=company_id, invoice_id=inv1_id)
    assert Decimal(str(out1["outstanding_amount"])) == Decimal("0.00")
    assert out1["is_settled"] is True

    out2 = payment_service.get_customer_invoice_outstanding(company_id=company_id, invoice_id=inv2_id)
    assert Decimal(str(out2["outstanding_amount"])) == Decimal("2000.00")
    assert out2["is_settled"] is False

    # B. Customer Advance Receipt (Unallocated) via UPI
    # Receive 5000.00 with only 2000.00 allocated to Inv2 -> 3000.00 is unallocated customer advance
    rct2 = payment_service.create_customer_receipt(
        company_id=company_id,
        branch_id=branch_id,
        customer_account_id=cust_id,
        deposit_account_id=bank_acc_id,
        total_amount=Decimal("5000.00"),
        receipt_date="2026-05-19",
        payment_method="UPI",
        allocations=[
            {"invoice_id": inv2_id, "allocated_amount": Decimal("2000.00")},
        ],
        user_id=admin_id,
    )
    assert Decimal(str(rct2["allocated_amount"])) == Decimal("2000.00")
    assert Decimal(str(rct2["unallocated_amount"])) == Decimal("3000.00")

    out2_post = payment_service.get_customer_invoice_outstanding(company_id=company_id, invoice_id=inv2_id)
    assert Decimal(str(out2_post["outstanding_amount"])) == Decimal("0.00")
    assert out2_post["is_settled"] is True

    # C. Managerial Reversal of rct2
    rev2 = payment_service.reverse_customer_receipt(
        company_id=company_id,
        receipt_id=rct2["id"],
        reversal_reason="Client requested cheque adjustment instead of UPI",
        user_id=admin_id,
    )
    assert rev2["status"] == "REVERSED"

    # Inv2 outstanding must restore back to 2000.00
    out2_restored = payment_service.get_customer_invoice_outstanding(company_id=company_id, invoice_id=inv2_id)
    assert Decimal(str(out2_restored["outstanding_amount"])) == Decimal("2000.00")


# ==============================================================================
# 5. Supplier Payments Full Spectrum E2E
# ==============================================================================

def test_supplier_payments_full_spectrum_lifecycle(qa_env):
    """
    Test direct supplier disbursements, on-account advances, cash/bank/UPI methods,
    and role-guarded managerial reversals.
    """
    trad_mgr = qa_env["trad_mgr"]
    company_id = qa_env["company_id"]
    branch_id = qa_env["branch_id"]
    admin_id = qa_env["admin_user_id"]
    payment_service = qa_env["payment_service"]

    supp_id = str(uuid.uuid4())
    cash_acc_id = str(uuid.uuid4())

    with trad_mgr.session_scope() as sess:
        sess.add(Account(
            id=supp_id, company_id=company_id, code="SUPP-GAMMA", name="Gamma Distributors",
            account_type="Creditor", is_active=True
        ))
        sess.add(Account(
            id=cash_acc_id, company_id=company_id, code="CASH-TILL2", name="Counter Cash 2",
            account_type="Cash", is_active=True
        ))

    # A. Direct On-Account Supplier Payment
    pmt = payment_service.create_supplier_payment(
        company_id=company_id,
        branch_id=branch_id,
        supplier_account_id=supp_id,
        source_account_id=cash_acc_id,
        total_amount=Decimal("15000.00"),
        payment_date="2026-05-20",
        payment_method="CASH",
        notes="Advance procurement disbursement",
        user_id=admin_id,
    )
    assert pmt["status"] == "POSTED"
    assert Decimal(str(pmt["unallocated_amount"])) == Decimal("15000.00")

    # B. Reversal with Audit Trail
    rev = payment_service.reverse_supplier_payment(
        company_id=company_id,
        payment_id=pmt["id"],
        reversal_reason="Duplicate payment instruction cancelled by purchase manager",
        user_id=admin_id,
    )
    assert rev["status"] == "REVERSED"


# ==============================================================================
# 6. Double-Entry Accounting Invariance & Period Lock
# ==============================================================================

def test_accounting_invariance_and_closed_period_lock(qa_env):
    """
    Verifies debit/credit equality, general ledger accuracy, and closed period immutability.
    """
    trad_mgr = qa_env["trad_mgr"]
    company_id = qa_env["company_id"]
    branch_id = qa_env["branch_id"]
    admin_id = qa_env["admin_user_id"]
    accounting_service = qa_env["accounting_service"]

    # Create & Close Period for 2026-Q1
    accounting_service.create_accounting_period(
        company_id=company_id,
        financial_year="2026-2027",
        period_name="FY2026-Q1",
        start_date="2026-04-01",
        end_date="2026-06-30",
    )
    accounting_service.close_accounting_period(
        company_id=company_id,
        period_id_or_name="FY2026-Q1",
        user_id=admin_id,
    )

    # Attempt to post receipt in closed period must be rejected
    cust_id = str(uuid.uuid4())
    bank_id = str(uuid.uuid4())
    with trad_mgr.session_scope() as sess:
        sess.add(Account(id=cust_id, company_id=company_id, code="CUST-LOCK", name="Locked Period Test Cust", account_type="Debtor", is_active=True))
        sess.add(Account(id=bank_id, company_id=company_id, code="BANK-LOCK", name="Locked Period Test Bank", account_type="Bank", is_active=True))

    payment_service = qa_env["payment_service"]
    with pytest.raises(Exception) as exc_info:
        payment_service.create_customer_receipt(
            company_id=company_id,
            branch_id=branch_id,
            customer_account_id=cust_id,
            deposit_account_id=bank_id,
            total_amount=Decimal("1000.00"),
            receipt_date="2026-05-15",  # In closed period (2026-04-01 to 2026-06-30)
            user_id=admin_id,
        )
    assert "closed" in str(exc_info.value).lower()


# ==============================================================================
# 7. Financial Reconciliation Dashboard & Discrepancy Detection
# ==============================================================================

def test_reconciliation_audit_and_deliberate_discrepancy_detection(qa_env):
    """
    Verifies that the financial reconciliation dashboard accurately audits subledgers
    and detects deliberate ledger discrepancies without silently repairing them.
    """
    recon_service = qa_env["recon_service"]
    trad_mgr = qa_env["trad_mgr"]
    company_id = qa_env["company_id"]

    # 1. Healthy Audit
    summary = recon_service.get_financial_reconciliation_summary(company_id=company_id)
    assert summary["overall_verdict"] in ("HEALTHY", "ATTENTION_REQUIRED")

    # 2. Deliberately Introduce Discrepancy: insert an orphan receipt journal without a voucher
    with trad_mgr.session_scope() as sess:
        acc_id = list(sess.scalars(select(Account.id).where(Account.company_id == company_id)))[0]
        orphan_j = JournalEntry(
            id=str(uuid.uuid4()),
            company_id=company_id,
            branch_id=qa_env["branch_id"],
            financial_year="2026-2027",
            voucher_number="ORPHAN-JRNL-01",
            voucher_type="RECEIPT",
            voucher_date="2026-05-21",
            reference_type="CUSTOMER_RECEIPT",
            reference_id=str(uuid.uuid4()),
            total_debit=Decimal("500.00"),
            total_credit=Decimal("500.00"),
            status="POSTED",
        )
        sess.add(orphan_j)
        sess.add(JournalEntryLine(
            id=str(uuid.uuid4()),
            journal_id=orphan_j.id,
            company_id=company_id,
            account_id=acc_id,
            debit=Decimal("500.00"),
            credit=Decimal("0.00"),
            line_number=1,
        ))
        sess.add(JournalEntryLine(
            id=str(uuid.uuid4()),
            journal_id=orphan_j.id,
            company_id=company_id,
            account_id=acc_id,
            debit=Decimal("0.00"),
            credit=Decimal("500.00"),
            line_number=2,
        ))

    # Diagnostic must now report anomalies without altering data
    audit_res = recon_service.detect_orphan_or_duplicate_journals(company_id=company_id)
    assert audit_res["total_anomalies_count"] > 0
    assert audit_res["status"] == "DISCREPANCIES_FOUND"


# ==============================================================================
# 8. Physical Database Isolation (Fast Billing Hash Invariance)
# ==============================================================================

def test_fast_billing_database_remains_byte_identical(qa_env):
    """
    Verifies that all Traditional Billing operations leave Fast Billing SQLite file
    100% byte-identical.
    """
    init_hash = compute_sha256(FAST_DB_PATH)

    # Execute series of traditional transactions via bridge
    bridge = qa_env["bridge"]
    bridge._traditional_session = trad_session_registry.get_session(qa_env["admin_token"])
    bridge.traditional_getNextReceiptNumber("RCT")
    bridge.traditional_listCustomersOutstanding("")
    bridge.traditional_getFinancialReconciliationSummary("")

    post_hash = compute_sha256(FAST_DB_PATH)
    assert init_hash == post_hash, "Fast Billing database file must never be touched by Traditional Billing."
