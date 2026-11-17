"""
Comprehensive Automated Test Suite: Traditional Financial Reconciliation & Engine Hardening.
Phase 3.5 — Anti-Matrix Billing V2 Core Backend Architecture.

Validates all 15 required financial reconciliation, hardening, and integrity scenarios:
1. Balanced customer AR reconciliation.
2. Deliberately mismatched customer AR (reporting without auto-modifying).
3. Balanced supplier AP reconciliation.
4. Supplier AP reconciliation with on-account advances.
5. Cash account reconciliation.
6. Bank account reconciliation.
7. Reversed receipt reconciliation (restores balances cleanly).
8. Reversed supplier payment reconciliation (restores balances cleanly).
9. Cross-company isolation.
10. Financial-year isolation.
11. Decimal precision and rounding (zero floating-point drift).
12. Duplicate journal reference detection.
13. Orphan journal and orphan voucher detection.
14. Atomic rollback verification (zero orphan rows on failure).
15. Strict read-only diagnostic verification (zero mutations).
"""

import uuid
import hashlib
from decimal import Decimal
from pathlib import Path
import pytest
from sqlalchemy import select, and_, func
from alembic.config import Config
from alembic import command

from db.traditional_database import TraditionalDatabaseManager
from db.traditional_models import (
    Company,
    Branch,
    Account,
    AccountGroup,
    AccountGroupMapping,
    SaleInvoice,
    CustomerReceipt,
    ReceiptAllocation,
    SupplierPayment,
    PaymentAllocation,
    JournalEntry,
    JournalEntryLine,
    AuditLog,
    utc_now,
)
from services.traditional_company_service import TraditionalCompanyService
from services.traditional_accounting_service import TraditionalAccountingService
from services.traditional_payment_service import TraditionalPaymentService
from services.traditional_financial_reconciliation_service import (
    TraditionalFinancialReconciliationService,
    FinancialReconciliationError,
    CompanyNotFoundError,
)

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
def recon_env(tmp_path):
    """Provides an isolated, fully migrated Traditional SQLite database for financial reconciliation tests."""
    db_file = tmp_path / "test_traditional_reconciliation.db"
    db_url = f"sqlite:///{db_file}"

    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    company_service = TraditionalCompanyService(db_manager=trad_mgr)
    accounting_service = TraditionalAccountingService(db_manager=trad_mgr)
    payment_service = TraditionalPaymentService(db_manager=trad_mgr, accounting_service=accounting_service)
    recon_service = TraditionalFinancialReconciliationService(
        db_manager=trad_mgr,
        accounting_service=accounting_service,
        payment_service=payment_service,
    )

    company_info = company_service.initial_setup({
        "name": "Zenith Financial Hardening Corp",
        "code": "CORP_ZENITH",
        "finYear": "2026-2027",
        "taxNo": "33CCCCC2222C1Z3",
        "state": "Tamilnadu",
        "adminUsername": "ADMIN",
        "adminPassword": "SecurePassword123!",
    })
    cid = company_info["companyId"]
    bid = company_info["branchId"]
    uid = company_info["adminUserId"]

    accounting_service.ensure_standard_accounts(cid)

    # Set up accounts and mappings
    with trad_mgr.session_scope() as sess:
        bank_grp = sess.scalar(
            select(AccountGroup).where(and_(AccountGroup.company_id == cid, AccountGroup.code == "GRP_BANK"))
        )
        hdfc_acc = Account(
            id=str(uuid.uuid4()),
            company_id=cid,
            code="BANK_HDFC",
            name="HDFC Current Account",
            account_type="Bank",
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        sess.add(hdfc_acc)
        sess.flush()
        sess.add(AccountGroupMapping(
            id=str(uuid.uuid4()),
            company_id=cid,
            account_id=hdfc_acc.id,
            group_id=bank_grp.id,
            account_nature="ASSET",
            created_at=utc_now(),
        ))

        # Customer Account: Sigma Trading (Debtor)
        cust = Account(
            id=str(uuid.uuid4()),
            company_id=cid,
            code="CUST_SIGMA",
            name="Sigma Trading",
            account_type="Debtor",
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        # Supplier Account: Vega Manufacturing (Creditor)
        supp = Account(
            id=str(uuid.uuid4()),
            company_id=cid,
            code="SUPP_VEGA",
            name="Vega Manufacturing",
            account_type="Creditor",
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        sess.add_all([cust, supp])
        sess.flush()

        cash_acc = sess.scalar(select(Account).where(and_(Account.company_id == cid, Account.code == "CASH")))
        cust_id = cust.id
        supp_id = supp.id
        cash_id = cash_acc.id
        bank_id = hdfc_acc.id

        # Invoice for Sigma Trading: 1180.00
        inv1 = SaleInvoice(
            id=str(uuid.uuid4()),
            voucher_id=str(uuid.uuid4()),
            company_id=cid,
            branch_id=bid,
            user_id=uid,
            financial_year="2026-2027",
            series="Main",
            sequence_number=1,
            voucher_number="INV-2026-001",
            vch_date="17-11-2026",
            party_name="Sigma Trading",
            account_id=cust_id,
            sale_type="L/GST-18%",
            payment_method="CREDIT",
            subtotal=Decimal("1000.00"),
            taxable_amount=Decimal("1000.00"),
            cgst_amount=Decimal("90.00"),
            sgst_amount=Decimal("90.00"),
            igst_amount=Decimal("0.00"),
            round_off_amount=Decimal("0.00"),
            grand_total=Decimal("1180.00"),
            total_amount=Decimal("1180.00"),
            items_json="[]",
            status="UNPAID",
            created_at=utc_now(),
        )
        sess.add(inv1)
        sess.flush()
        inv1_id = inv1.id

    # Record GL entry for the sale invoice
    accounting_service.record_sales_journal(
        company_id=cid,
        branch_id=bid,
        invoice_id=inv1_id,
        invoice_number="INV-2026-001",
        invoice_date="17-11-2026",
        customer_account_id=cust_id,
        sales_amount=Decimal("1000.00"),
        output_cgst=Decimal("90.00"),
        output_sgst=Decimal("90.00"),
        user_id=uid,
    )

    # Record GL entry for a purchase from Vega: 3000.00
    accounting_service.record_purchase_journal(
        company_id=cid,
        branch_id=bid,
        bill_id=str(uuid.uuid4()),
        bill_number="BILL-2026-001",
        bill_date="17-11-2026",
        supplier_account_id=supp_id,
        purchase_amount=Decimal("3000.00"),
        narration="Purchase from Vega",
        user_id=uid,
    )

    return {
        "db_file": db_file,
        "trad_mgr": trad_mgr,
        "company_service": company_service,
        "accounting_service": accounting_service,
        "payment_service": payment_service,
        "recon_service": recon_service,
        "company_id": cid,
        "branch_id": bid,
        "admin_user_id": uid,
        "cash_id": cash_id,
        "bank_id": bank_id,
        "cust_id": cust_id,
        "supp_id": supp_id,
        "inv1_id": inv1_id,
    }


# ==============================================================================
# 1. Balanced Customer AR Reconciliation
# ==============================================================================

def test_balanced_customer_ar_reconciliation(recon_env):
    """Scenario 1: Verifies GL AR exactly matches dynamic unpaid invoices and advances."""
    rs = recon_env["recon_service"]
    ps = recon_env["payment_service"]
    cid = recon_env["company_id"]
    cust_id = recon_env["cust_id"]
    cash_id = recon_env["cash_id"]
    inv1_id = recon_env["inv1_id"]

    # Initial state: 1180.00 invoice unpaid, GL has 1180.00 Dr
    rec_initial = rs.reconcile_customer_ar(cid, customer_account_id=cust_id)
    assert rec_initial["status"] == "BALANCED"
    assert rec_initial["total_difference"] == "0.00"
    assert rec_initial["total_gl_control_balance"] == "1180.00"
    assert rec_initial["total_subledger_balance"] == "1180.00"

    # Settle partial 500.00
    ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("500.00"),
        allocations=[{"invoice_id": inv1_id, "allocated_amount": Decimal("500.00")}],
    )

    # After partial receipt: 680.00 unpaid, GL has 680.00 Dr
    rec_partial = rs.reconcile_customer_ar(cid, customer_account_id=cust_id)
    assert rec_partial["status"] == "BALANCED"
    assert rec_partial["total_difference"] == "0.00"
    assert rec_partial["total_gl_control_balance"] == "680.00"
    assert rec_partial["total_subledger_balance"] == "680.00"


# ==============================================================================
# 2. Deliberately Mismatched Customer AR
# ==============================================================================

def test_deliberately_mismatched_customer_ar(recon_env):
    """Scenario 2: Detects and reports deliberate AR discrepancy without auto-repairing."""
    rs = recon_env["recon_service"]
    trad_mgr = recon_env["trad_mgr"]
    cid = recon_env["company_id"]
    cust_id = recon_env["cust_id"]

    # Deliberately post an out-of-band journal debiting customer 250.00 without an invoice
    acct = recon_env["accounting_service"]
    coa = {a["code"]: a["id"] for a in acct.get_chart_of_accounts(cid)}
    acct.post_journal_entry(
        company_id=cid,
        branch_id=recon_env["branch_id"],
        voucher_type="JOURNAL",
        voucher_date="17-11-2026",
        lines=[
            {"account_id": cust_id, "debit": Decimal("250.00"), "credit": Decimal("0.00")},
            {"account_id": coa["ROUND_OFF"], "debit": Decimal("0.00"), "credit": Decimal("250.00")},
        ],
        narration="Manual out-of-band debit",
    )

    rec = rs.reconcile_customer_ar(cid, customer_account_id=cust_id)
    assert rec["status"] == "MISMATCHED"
    assert rec["mismatched_count"] == 1
    # GL = 1180 + 250 = 1430. Subledger = 1180. Difference = 250.00
    assert rec["total_difference"] == "250.00"
    cust_report = rec["customers"][0]
    assert cust_report["status"] == "MISMATCHED"
    assert cust_report["difference"] == "250.00"
    assert "differs from Subledger" in cust_report["discrepancy_details"]


# ==============================================================================
# 3. Balanced Supplier AP Reconciliation
# ==============================================================================

def test_balanced_supplier_ap_reconciliation(recon_env):
    """Scenario 3: Verifies GL AP matches subledger bills and payments."""
    rs = recon_env["recon_service"]
    ps = recon_env["payment_service"]
    cid = recon_env["company_id"]
    supp_id = recon_env["supp_id"]
    cash_id = recon_env["cash_id"]

    # Initial state: 3000.00 purchase billed from fixture
    rec_initial = rs.reconcile_supplier_ap(cid, supplier_account_id=supp_id)
    assert rec_initial["status"] == "BALANCED"
    assert rec_initial["total_difference"] == "0.00"
    assert rec_initial["total_gl_control_balance"] == "3000.00"
    assert rec_initial["total_subledger_balance"] == "3000.00"

    # Full payment of 3000.00
    ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp_id,
        source_account_id=cash_id,
        total_amount=Decimal("3000.00"),
        allocations=[{"bill_number": "BILL-2026-001", "allocated_amount": Decimal("3000.00")}],
    )

    rec_paid = rs.reconcile_supplier_ap(cid, supplier_account_id=supp_id)
    assert rec_paid["status"] == "BALANCED"
    assert rec_paid["total_difference"] == "0.00"
    assert rec_paid["total_gl_control_balance"] == "0.00"
    assert rec_paid["total_subledger_balance"] == "0.00"


# ==============================================================================
# 4. Supplier Reconciliation with On-Account Advances
# ==============================================================================

def test_supplier_reconciliation_with_on_account_advances(recon_env):
    """Scenario 4: Reconciles AP and advances when on-account advance payments exist."""
    rs = recon_env["recon_service"]
    ps = recon_env["payment_service"]
    cid = recon_env["company_id"]
    supp_id = recon_env["supp_id"]
    bank_id = recon_env["bank_id"]

    # Advance payment of 1000.00 (unallocated)
    ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp_id,
        source_account_id=bank_id,
        total_amount=Decimal("1000.00"),
        payment_method="BANK",
    )

    # GL AP: 3000 Cr - 1000 Dr = 2000 Cr
    # Subledger: 3000 bills - 1000 advance = 2000
    rec_ap = rs.reconcile_supplier_ap(cid, supplier_account_id=supp_id)
    assert rec_ap["status"] == "BALANCED"
    assert rec_ap["total_difference"] == "0.00"
    assert rec_ap["total_gl_control_balance"] == "2000.00"
    assert rec_ap["total_subledger_balance"] == "2000.00"

    # Check advance reconciliation
    rec_adv = rs.reconcile_supplier_advances(cid, supplier_account_id=supp_id)
    assert rec_adv["status"] == "BALANCED"
    assert rec_adv["total_unallocated_advances"] == "1000.00"
    assert rec_adv["violations_count"] == 0


# ==============================================================================
# 5. Cash Account Reconciliation
# ==============================================================================

def test_cash_account_reconciliation(recon_env):
    """Scenario 5: Reconciles Cash-in-Hand against posted receipt and payment vouchers."""
    rs = recon_env["recon_service"]
    ps = recon_env["payment_service"]
    cid = recon_env["company_id"]
    cust_id = recon_env["cust_id"]
    supp_id = recon_env["supp_id"]
    cash_id = recon_env["cash_id"]

    # Cash receipt: +500.00
    ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("500.00"),
        payment_method="CASH",
    )
    # Cash payment: -200.00
    ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp_id,
        source_account_id=cash_id,
        total_amount=Decimal("200.00"),
        payment_method="CASH",
    )

    rec_cb = rs.reconcile_cash_and_bank(cid, account_id=cash_id)
    assert rec_cb["status"] == "BALANCED"
    assert rec_cb["mismatched_count"] == 0
    cash_info = rec_cb["accounts"][0]
    assert cash_info["total_receipts_posted"] == "500.00"
    assert cash_info["total_payments_posted"] == "200.00"
    assert len(cash_info["discrepancies"]) == 0


# ==============================================================================
# 6. Bank Account Reconciliation
# ==============================================================================

def test_bank_account_reconciliation(recon_env):
    """Scenario 6: Reconciles Bank ledger account against posted receipt and payment vouchers."""
    rs = recon_env["recon_service"]
    ps = recon_env["payment_service"]
    cid = recon_env["company_id"]
    cust_id = recon_env["cust_id"]
    supp_id = recon_env["supp_id"]
    bank_id = recon_env["bank_id"]

    # Bank receipt: +4000.00
    ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust_id,
        deposit_account_id=bank_id,
        total_amount=Decimal("4000.00"),
        payment_method="BANK",
    )
    # Bank payment: -1500.00
    ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp_id,
        source_account_id=bank_id,
        total_amount=Decimal("1500.00"),
        payment_method="BANK",
    )

    rec_cb = rs.reconcile_cash_and_bank(cid, account_id=bank_id)
    assert rec_cb["status"] == "BALANCED"
    bank_info = rec_cb["accounts"][0]
    assert bank_info["total_receipts_posted"] == "4000.00"
    assert bank_info["total_payments_posted"] == "1500.00"
    assert len(bank_info["discrepancies"]) == 0


# ==============================================================================
# 7. Reversed Receipt Reconciliation
# ==============================================================================

def test_reversed_receipt_reconciliation(recon_env):
    """Scenario 7: Reversal of receipt restores AR and cash balances without discrepancies."""
    rs = recon_env["recon_service"]
    ps = recon_env["payment_service"]
    cid = recon_env["company_id"]
    cust_id = recon_env["cust_id"]
    cash_id = recon_env["cash_id"]
    inv1_id = recon_env["inv1_id"]

    # Post receipt 1180.00 (settles invoice fully)
    rc = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("1180.00"),
        allocations=[{"invoice_id": inv1_id, "allocated_amount": Decimal("1180.00")}],
    )

    # Reverse receipt
    ps.reverse_customer_receipt(
        company_id=cid,
        receipt_id=rc["id"],
        reversal_reason="Cheque dishonoured",
    )

    # AR must reconcile back to 1180.00
    rec_ar = rs.reconcile_customer_ar(cid, customer_account_id=cust_id)
    assert rec_ar["status"] == "BALANCED"
    assert rec_ar["total_gl_control_balance"] == "1180.00"
    assert rec_ar["total_subledger_balance"] == "1180.00"

    # Cash book must show reversed receipt without discrepancies
    rec_cb = rs.reconcile_cash_and_bank(cid, account_id=cash_id)
    assert rec_cb["status"] == "BALANCED"
    cash_info = rec_cb["accounts"][0]
    assert cash_info["total_receipts_reversed"] == "1180.00"


# ==============================================================================
# 8. Reversed Supplier Payment Reconciliation
# ==============================================================================

def test_reversed_supplier_payment_reconciliation(recon_env):
    """Scenario 8: Reversal of supplier payment restores AP and cash balances cleanly."""
    rs = recon_env["recon_service"]
    ps = recon_env["payment_service"]
    cid = recon_env["company_id"]
    supp_id = recon_env["supp_id"]
    cash_id = recon_env["cash_id"]

    # Post payment of 1000.00
    p = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp_id,
        source_account_id=cash_id,
        total_amount=Decimal("1000.00"),
        allocations=[{"bill_number": "BILL-2026-001", "allocated_amount": Decimal("1000.00")}],
    )

    # Reverse payment
    ps.reverse_supplier_payment(
        company_id=cid,
        payment_id=p["id"],
        reversal_reason="Payment cancelled",
    )

    # AP must reconcile back to 3000.00
    rec_ap = rs.reconcile_supplier_ap(cid, supplier_account_id=supp_id)
    assert rec_ap["status"] == "BALANCED"
    assert rec_ap["total_gl_control_balance"] == "3000.00"
    assert rec_ap["total_subledger_balance"] == "3000.00"

    rec_cb = rs.reconcile_cash_and_bank(cid, account_id=cash_id)
    assert rec_cb["status"] == "BALANCED"
    cash_info = rec_cb["accounts"][0]
    assert cash_info["total_payments_reversed"] == "1000.00"


# ==============================================================================
# 9. Cross-Company Isolation
# ==============================================================================

def test_cross_company_isolation(recon_env):
    """Scenario 9: Diagnostics strictly isolate company data and reject foreign company IDs."""
    rs = recon_env["recon_service"]
    fake_cid = str(uuid.uuid4())

    with pytest.raises(CompanyNotFoundError):
        rs.reconcile_customer_ar(fake_cid)

    with pytest.raises(CompanyNotFoundError):
        rs.reconcile_supplier_ap(fake_cid)

    with pytest.raises(CompanyNotFoundError):
        rs.get_financial_reconciliation_summary(fake_cid)


# ==============================================================================
# 10. Financial-Year Isolation
# ==============================================================================

def test_financial_year_isolation(recon_env):
    """Scenario 10: Reconciling as of a date respects historical transaction horizon."""
    rs = recon_env["recon_service"]
    cid = recon_env["company_id"]
    cust_id = recon_env["cust_id"]

    # As of a date before the sale (e.g. 01-11-2026):
    rec_past = rs.reconcile_customer_ar(cid, customer_account_id=cust_id, as_of_date="01-11-2026")
    assert rec_past["status"] == "BALANCED"
    assert rec_past["total_gl_control_balance"] == "0.00"


# ==============================================================================
# 11. Decimal Precision and Rounding
# ==============================================================================

def test_decimal_precision_and_rounding(recon_env):
    """Scenario 11: Exact precision without float arithmetic drift on fractions."""
    rs = recon_env["recon_service"]
    ps = recon_env["payment_service"]
    cid = recon_env["company_id"]
    cust_id = recon_env["cust_id"]
    cash_id = recon_env["cash_id"]

    # Payment with 33 paise
    ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("123.33"),
        payment_method="CASH",
    )

    rec_ar = rs.reconcile_customer_ar(cid, customer_account_id=cust_id)
    assert rec_ar["status"] == "BALANCED"
    assert rec_ar["total_difference"] == "0.00"


# ==============================================================================
# 12. Duplicate Journal Reference Detection
# ==============================================================================

def test_duplicate_journal_detection(recon_env):
    """Scenario 12: Detects if two distinct receipt vouchers point to the same journal ID."""
    rs = recon_env["recon_service"]
    ps = recon_env["payment_service"]
    trad_mgr = recon_env["trad_mgr"]
    cid = recon_env["company_id"]
    cust_id = recon_env["cust_id"]
    cash_id = recon_env["cash_id"]

    r1 = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("100.00"),
    )
    r2 = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("200.00"),
    )

    # Deliberately point r2's journal_id to r1's journal_id in test DB
    with trad_mgr.session_scope() as sess:
        r2_db = sess.scalar(select(CustomerReceipt).where(CustomerReceipt.id == r2["id"]))
        r2_db.journal_id = r1["journal_id"]
        sess.flush()

    audit = rs.detect_orphan_or_duplicate_journals(cid)
    assert audit["status"] == "DISCREPANCIES_FOUND"
    assert audit["duplicate_receipt_journal_refs_count"] >= 1


# ==============================================================================
# 13. Orphan Journal and Orphan Voucher Detection
# ==============================================================================

def test_orphan_journal_detection(recon_env):
    """Scenario 13: Detects orphan journals and vouchers with missing journal references."""
    rs = recon_env["recon_service"]
    trad_mgr = recon_env["trad_mgr"]
    cid = recon_env["company_id"]
    bid = recon_env["branch_id"]

    # Create orphan journal entry tagged CUSTOMER_RECEIPT
    with trad_mgr.session_scope() as sess:
        orph_jrn = JournalEntry(
            id=str(uuid.uuid4()),
            company_id=cid,
            branch_id=bid,
            financial_year="2026-2027",
            voucher_number="JRN-ORPHAN-01",
            voucher_type="RECEIPT",
            voucher_date="17-11-2026",
            reference_type="CUSTOMER_RECEIPT",
            total_debit=Decimal("500.00"),
            total_credit=Decimal("500.00"),
            status="POSTED",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        sess.add(orph_jrn)
        sess.flush()

    audit = rs.detect_orphan_or_duplicate_journals(cid)
    assert audit["status"] == "DISCREPANCIES_FOUND"
    assert audit["orphan_journals_count"] >= 1


# ==============================================================================
# 14. Atomic Rollback Verification
# ==============================================================================

def test_atomic_rollback_verification(recon_env):
    """Scenario 14: Verifies partial transaction failures leave zero orphan rows in any table."""
    rs = recon_env["recon_service"]
    ps = recon_env["payment_service"]
    trad_mgr = recon_env["trad_mgr"]
    cid = recon_env["company_id"]
    cust_id = recon_env["cust_id"]
    cash_id = recon_env["cash_id"]

    with trad_mgr.read_session_scope() as sess:
        initial_rc_count = sess.scalar(
            select(func.count(CustomerReceipt.id)).where(CustomerReceipt.company_id == cid)
        )

    # Intentionally trigger failure via negative allocation amount
    with pytest.raises(ValueError):
        ps.create_customer_receipt(
            company_id=cid,
            customer_account_id=cust_id,
            deposit_account_id=cash_id,
            total_amount=Decimal("500.00"),
            allocations=[{"invoice_id": recon_env["inv1_id"], "allocated_amount": Decimal("-100.00")}],
        )

    # Verify no receipt was added
    with trad_mgr.read_session_scope() as sess:
        final_rc_count = sess.scalar(
            select(func.count(CustomerReceipt.id)).where(CustomerReceipt.company_id == cid)
        )
    assert final_rc_count == initial_rc_count

    # Audit check confirms completely clean state
    audit = rs.detect_orphan_or_duplicate_journals(cid)
    assert audit["status"] == "CLEAN"


# ==============================================================================
# 15. Strict Read-Only Diagnostic Verification
# ==============================================================================

def test_readonly_diagnostic_verification(recon_env):
    """Scenario 15: Proves diagnostic methods never mutate database rows or states."""
    rs = recon_env["recon_service"]
    cid = recon_env["company_id"]
    db_file = recon_env["db_file"]

    # Compute SHA-256 before running diagnostic
    hash_before = compute_sha256(db_file)

    # Execute comprehensive summary
    summary = rs.get_financial_reconciliation_summary(cid)
    assert summary["overall_verdict"] == "HEALTHY"

    # Compute SHA-256 after running diagnostic
    hash_after = compute_sha256(db_file)
    assert hash_after == hash_before, "Database was mutated by read-only diagnostic!"
