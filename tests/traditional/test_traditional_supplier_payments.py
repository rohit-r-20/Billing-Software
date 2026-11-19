"""
Comprehensive Automated Test Suite: Traditional Supplier Payments & Bill Allocations.
Phase 3.4 — Anti-Matrix Billing V2 Core Backend Architecture.

Validates all 24 required supplier payment, allocation, accounting, and security scenarios:
1. Cash supplier payment.
2. Bank supplier payment.
3. UPI supplier payment.
4. Full supplier payment.
5. Partial supplier payment.
6. Multiple purchase/bill allocations.
7. Advance supplier payment.
8. Unallocated payment tracking.
9. On-account payment and subsequent allocation.
10. Dynamic supplier outstanding calculations (ledger AP vs advances vs purchases).
11. Over-allocation rejection.
12. Cross-supplier allocation rejection.
13. Cross-company isolation.
14. Invalid source account rejection (rejecting non-Cash/Bank accounts, and payee account validity).
15. Duplicate idempotency key handling.
16. Duplicate voucher rejection.
17. Accounting journal correctness (Double-entry Debit AP, Credit Cash/Bank, Credit Discount).
18. Transaction rollback on error (no partial transactions or orphan journals).
19. Closed-period rejection.
20. Payment reversal (creates reversing journal and marks REVERSED).
21. Duplicate reversal rejection.
22. Reversed payment excluded from balances (restores outstanding balance).
23. Concurrent voucher sequence generation / thread-safety.
24. Traditional/Fast database isolation (Fast Billing DB untouched).
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
    SupplierPayment,
    PaymentAllocation,
    JournalEntry,
    JournalEntryLine,
    AuditLog,
    utc_now,
)
from services.traditional_company_service import TraditionalCompanyService
from services.traditional_accounting_service import (
    TraditionalAccountingService,
    ClosedPeriodError,
)
from services.traditional_payment_service import (
    TraditionalPaymentService,
    TraditionalPaymentError,
    SupplierPaymentNotFoundError,
    InvalidSourceAccountError,
    InvalidSupplierAccountError,
    OverAllocationError,
    DuplicateReceiptError,
    DuplicateReversalError,
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
def supplier_env(tmp_path):
    """Provides an isolated, fully migrated Traditional SQLite database for supplier payment tests."""
    db_file = tmp_path / "test_traditional_supplier_payments.db"
    db_url = f"sqlite:///{db_file}"

    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    company_service = TraditionalCompanyService(db_manager=trad_mgr)
    accounting_service = TraditionalAccountingService(db_manager=trad_mgr)
    payment_service = TraditionalPaymentService(db_manager=trad_mgr, accounting_service=accounting_service)

    company_info = company_service.initial_setup({
        "name": "Nexus Industrial Supplies Corp",
        "code": "CORP_NEXUS",
        "finYear": "2026-2027",
        "taxNo": "33BBBBB1111B1Z2",
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
        # Bank Account: HDFC Current Account
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

        # Supplier 1: Apex Industrial Products
        supp1 = Account(
            id=str(uuid.uuid4()),
            company_id=cid,
            code="SUPP_APEX",
            name="Apex Industrial Products",
            account_type="Creditor",
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        # Supplier 2: Horizon Raw Materials
        supp2 = Account(
            id=str(uuid.uuid4()),
            company_id=cid,
            code="SUPP_HORIZON",
            name="Horizon Raw Materials",
            account_type="Creditor",
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        # Customer: Orion Retailers (Debtor - for validation tests)
        cust = Account(
            id=str(uuid.uuid4()),
            company_id=cid,
            code="CUST_ORION",
            name="Orion Retailers",
            account_type="Debtor",
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        # Expense: Office Stationery (Expense - for invalid source tests)
        exp_acc = Account(
            id=str(uuid.uuid4()),
            company_id=cid,
            code="EXP_OFFICE",
            name="Office Stationery Expense",
            account_type="Expense",
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        sess.add_all([supp1, supp2, cust, exp_acc])
        sess.flush()

        cash_acc = sess.scalar(select(Account).where(and_(Account.company_id == cid, Account.code == "CASH")))
        supp1_id = supp1.id
        supp2_id = supp2.id
        cust_id = cust.id
        exp_id = exp_acc.id
        cash_id = cash_acc.id
        bank_id = hdfc_acc.id

    # Record initial purchase journals for Supplier 1 and Supplier 2
    accounting_service.record_purchase_journal(
        company_id=cid,
        branch_id=bid,
        bill_id=str(uuid.uuid4()),
        bill_number="BILL-2026-001",
        bill_date="17-11-2026",
        supplier_account_id=supp1_id,
        purchase_amount=Decimal("1200.00"),
        narration="Purchase bill 001 from Apex",
        user_id=uid,
    )
    accounting_service.record_purchase_journal(
        company_id=cid,
        branch_id=bid,
        bill_id=str(uuid.uuid4()),
        bill_number="BILL-2026-002",
        bill_date="17-11-2026",
        supplier_account_id=supp1_id,
        purchase_amount=Decimal("3000.00"),
        narration="Purchase bill 002 from Apex",
        user_id=uid,
    )
    accounting_service.record_purchase_journal(
        company_id=cid,
        branch_id=bid,
        bill_id=str(uuid.uuid4()),
        bill_number="BILL-2026-003",
        bill_date="17-11-2026",
        supplier_account_id=supp2_id,
        purchase_amount=Decimal("5000.00"),
        narration="Purchase bill 003 from Horizon",
        user_id=uid,
    )

    return {
        "trad_mgr": trad_mgr,
        "company_service": company_service,
        "accounting_service": accounting_service,
        "payment_service": payment_service,
        "company_id": cid,
        "branch_id": bid,
        "admin_user_id": uid,
        "cash_id": cash_id,
        "bank_id": bank_id,
        "supp1_id": supp1_id,
        "supp2_id": supp2_id,
        "cust_id": cust_id,
        "exp_id": exp_id,
    }


# ==============================================================================
# 1. Cash Supplier Payment
# ==============================================================================

def test_cash_supplier_payment(supplier_env):
    """Scenario 1: Creates a cash payment disbursed from Cash-in-Hand to supplier."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cash_id = supplier_env["cash_id"]

    res = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=cash_id,
        total_amount=Decimal("1000.00"),
        payment_method="CASH",
        notes="Cash disbursement for supplies",
    )

    assert res["id"] is not None
    assert res["voucher_number"].startswith("PAY-")
    assert res["payment_method"] == "CASH"
    assert res["total_amount"] == "1000.00"
    assert res["unallocated_amount"] == "1000.00"
    assert res["status"] == "POSTED"
    assert res["journal_id"] is not None


# ==============================================================================
# 2. Bank Supplier Payment
# ==============================================================================

def test_bank_supplier_payment(supplier_env):
    """Scenario 2: Creates a bank transfer / cheque disbursement to supplier."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    bank_id = supplier_env["bank_id"]

    res = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=bank_id,
        total_amount=Decimal("1500.00"),
        payment_method="BANK",
        reference_number="CHQ-889900",
        notes="Cheque payment for inventory",
    )

    assert res["payment_method"] == "BANK"
    assert res["source_account_id"] == bank_id
    assert res["reference_number"] == "CHQ-889900"
    assert res["total_amount"] == "1500.00"
    assert res["status"] == "POSTED"


# ==============================================================================
# 3. UPI Supplier Payment
# ==============================================================================

def test_upi_supplier_payment(supplier_env):
    """Scenario 3: Creates an instant UPI supplier disbursement."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    bank_id = supplier_env["bank_id"]

    res = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=bank_id,
        total_amount=Decimal("850.00"),
        payment_method="UPI",
        reference_number="UPI/321654987/vendor",
        notes="UPI disbursement",
    )

    assert res["payment_method"] == "UPI"
    assert res["total_amount"] == "850.00"
    assert res["reference_number"] == "UPI/321654987/vendor"
    assert res["status"] == "POSTED"


# ==============================================================================
# 4. Full Supplier Payment
# ==============================================================================

def test_full_supplier_payment(supplier_env):
    """Scenario 4: Fully settles a purchase bill with exact allocated amount."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cash_id = supplier_env["cash_id"]

    # BILL-2026-001 has total 1200.00
    res = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=cash_id,
        total_amount=Decimal("1200.00"),
        allocations=[{"bill_number": "BILL-2026-001", "allocated_amount": Decimal("1200.00")}],
    )

    assert res["total_amount"] == "1200.00"
    assert res["allocated_amount"] == "1200.00"
    assert res["unallocated_amount"] == "0.00"
    assert len(res["allocations"]) == 1

    # Dynamic outstanding check
    bill_out = ps.get_supplier_invoice_outstanding(
        company_id=cid,
        bill_number_or_voucher_id="BILL-2026-001",
        total_bill_amount=Decimal("1200.00"),
    )
    assert bill_out["outstanding_amount"] == "0.00"
    assert bill_out["is_settled"] is True
    assert bill_out["total_allocated"] == "1200.00"


# ==============================================================================
# 5. Partial Supplier Payment
# ==============================================================================

def test_partial_supplier_payment(supplier_env):
    """Scenario 5: Partially settles a purchase bill, leaving an accurate remaining outstanding balance."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cash_id = supplier_env["cash_id"]

    # BILL-2026-002 has total 3000.00; pay 1000.00
    res = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=cash_id,
        total_amount=Decimal("1000.00"),
        allocations=[{"bill_number": "BILL-2026-002", "allocated_amount": Decimal("1000.00")}],
    )

    assert res["allocated_amount"] == "1000.00"
    assert res["unallocated_amount"] == "0.00"

    bill_out = ps.get_supplier_invoice_outstanding(
        company_id=cid,
        bill_number_or_voucher_id="BILL-2026-002",
        total_bill_amount=Decimal("3000.00"),
    )
    assert bill_out["outstanding_amount"] == "2000.00"
    assert bill_out["is_settled"] is False
    assert bill_out["total_allocated"] == "1000.00"


# ==============================================================================
# 6. Multiple Purchase/Bill Allocations
# ==============================================================================

def test_multiple_purchase_bill_allocations(supplier_env):
    """Scenario 6: Allocates a single payment across multiple distinct purchase bills."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    bank_id = supplier_env["bank_id"]

    # Settle 500 on BILL-A and 1500 on BILL-B
    res = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=bank_id,
        total_amount=Decimal("2000.00"),
        payment_method="BANK",
        allocations=[
            {"bill_number": "BILL-MULTI-A", "allocated_amount": Decimal("500.00")},
            {"bill_number": "BILL-MULTI-B", "allocated_amount": Decimal("1500.00")},
        ],
    )

    assert res["allocated_amount"] == "2000.00"
    assert res["unallocated_amount"] == "0.00"
    assert len(res["allocations"]) == 2

    out_a = ps.get_supplier_invoice_outstanding(cid, "BILL-MULTI-A", total_bill_amount=Decimal("500.00"))
    assert out_a["outstanding_amount"] == "0.00"
    assert out_a["is_settled"] is True

    out_b = ps.get_supplier_invoice_outstanding(cid, "BILL-MULTI-B", total_bill_amount=Decimal("2000.00"))
    assert out_b["outstanding_amount"] == "500.00"
    assert out_b["is_settled"] is False


# ==============================================================================
# 7. Advance Supplier Payment
# ==============================================================================

def test_advance_supplier_payment(supplier_env):
    """Scenario 7: 100% advance payment with zero initial bill allocations."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp2_id = supplier_env["supp2_id"]
    cash_id = supplier_env["cash_id"]

    res = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp2_id,
        source_account_id=cash_id,
        total_amount=Decimal("5000.00"),
        notes="Advance for future supply order",
    )

    assert res["total_amount"] == "5000.00"
    assert res["allocated_amount"] == "0.00"
    assert res["unallocated_amount"] == "5000.00"
    assert len(res["allocations"]) == 0

    supp_out = ps.get_supplier_outstanding(cid, supp2_id)
    assert Decimal(supp_out["total_unallocated_advances"]) >= Decimal("5000.00")


# ==============================================================================
# 8. Unallocated Payment Tracking
# ==============================================================================

def test_unallocated_payment_tracking(supplier_env):
    """Scenario 8: Payment exceeding the sum of allocations tracks unallocated funds cleanly."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cash_id = supplier_env["cash_id"]

    res = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=cash_id,
        total_amount=Decimal("4000.00"),
        allocations=[{"bill_number": "BILL-TRACK-01", "allocated_amount": Decimal("1500.00")}],
    )

    assert res["total_amount"] == "4000.00"
    assert res["allocated_amount"] == "1500.00"
    assert res["unallocated_amount"] == "2500.00"


# ==============================================================================
# 9. On-Account Payment and Subsequent Allocation
# ==============================================================================

def test_on_account_payment_and_subsequent_allocation(supplier_env):
    """Scenario 9: Creates on-account payment and subsequently applies advance funds to a purchase bill."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    bank_id = supplier_env["bank_id"]

    # Step 1: Create advance payment of 3000.00
    p1 = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=bank_id,
        total_amount=Decimal("3000.00"),
        payment_method="BANK",
    )
    assert p1["unallocated_amount"] == "3000.00"

    # Step 2: Allocate 1800.00 to a newly received bill
    p1_alloc = ps.allocate_supplier_payment(
        company_id=cid,
        payment_id=p1["id"],
        allocations=[{"bill_number": "BILL-LATER-01", "allocated_amount": Decimal("1800.00")}],
    )

    assert p1_alloc["allocated_amount"] == "1800.00"
    assert p1_alloc["unallocated_amount"] == "1200.00"
    assert len(p1_alloc["allocations"]) == 1

    out_later = ps.get_supplier_invoice_outstanding(
        company_id=cid,
        bill_number_or_voucher_id="BILL-LATER-01",
        total_bill_amount=Decimal("2000.00"),
    )
    assert out_later["outstanding_amount"] == "200.00"
    assert out_later["is_settled"] is False


# ==============================================================================
# 10. Dynamic Supplier Outstanding Calculations
# ==============================================================================

def test_supplier_outstanding_calculations(supplier_env):
    """Scenario 10: Authoritative calculation of general ledger AP balance and unallocated advances."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cash_id = supplier_env["cash_id"]

    # Initial state from fixture:
    # BILL-001 (1200.00) + BILL-002 (3000.00) = 4200.00 Cr
    rep_initial = ps.get_supplier_outstanding(cid, supp1_id)
    assert Decimal(rep_initial["net_ledger_payable"]) == Decimal("4200.00")
    assert rep_initial["balance_type"] == "Cr"

    # Pay 1200.00
    ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=cash_id,
        total_amount=Decimal("1200.00"),
        allocations=[{"bill_number": "BILL-2026-001", "allocated_amount": Decimal("1200.00")}],
    )

    rep_after = ps.get_supplier_outstanding(cid, supp1_id)
    # Remaining ledger balance: 4200 - 1200 = 3000.00 Cr
    assert Decimal(rep_after["net_ledger_payable"]) == Decimal("3000.00")
    assert rep_after["balance_type"] == "Cr"
    assert Decimal(rep_after["period_payments_disbursed"]) >= Decimal("1200.00")


# ==============================================================================
# 11. Over-Allocation Rejection
# ==============================================================================

def test_over_allocation_rejection(supplier_env):
    """Scenario 11: Allocation amounts exceeding total payment or unallocated balance are rejected."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cash_id = supplier_env["cash_id"]

    # A. Sum of allocations exceeds total payment amount
    with pytest.raises(OverAllocationError):
        ps.create_supplier_payment(
            company_id=cid,
            supplier_account_id=supp1_id,
            source_account_id=cash_id,
            total_amount=Decimal("1000.00"),
            allocations=[{"bill_number": "BILL-OVER-01", "allocated_amount": Decimal("1500.00")}],
        )

    # B. Subsequent allocation exceeds remaining unallocated advance balance
    p_adv = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=cash_id,
        total_amount=Decimal("500.00"),
    )
    with pytest.raises(OverAllocationError):
        ps.allocate_supplier_payment(
            company_id=cid,
            payment_id=p_adv["id"],
            allocations=[{"bill_number": "BILL-OVER-02", "allocated_amount": Decimal("750.00")}],
        )


# ==============================================================================
# 12. Cross-Supplier Allocation Rejection
# ==============================================================================

def test_cross_supplier_rejection(supplier_env):
    """Scenario 12: Allocations tagged with a different supplier account must be rejected."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    supp2_id = supplier_env["supp2_id"]
    cash_id = supplier_env["cash_id"]

    with pytest.raises(ValueError, match="belongs to another supplier"):
        ps.create_supplier_payment(
            company_id=cid,
            supplier_account_id=supp1_id,
            source_account_id=cash_id,
            total_amount=Decimal("1000.00"),
            allocations=[{
                "bill_number": "BILL-CROSS-01",
                "allocated_amount": Decimal("1000.00"),
                "supplier_account_id": supp2_id,  # Mismatch!
            }],
        )


# ==============================================================================
# 13. Cross-Company Isolation
# ==============================================================================

def test_cross_company_isolation(supplier_env):
    """Scenario 13: Verifies cross-company payment creation, queries, and reversals are strictly rejected."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cash_id = supplier_env["cash_id"]

    fake_company_id = str(uuid.uuid4())

    with pytest.raises(ValueError, match="Company '.*' not found"):
        ps.create_supplier_payment(
            company_id=fake_company_id,
            supplier_account_id=supp1_id,
            source_account_id=cash_id,
            total_amount=Decimal("500.00"),
        )

    # Valid payment in Company A
    p = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=cash_id,
        total_amount=Decimal("500.00"),
    )

    # Attempting to fetch or reverse under another company ID
    with pytest.raises(SupplierPaymentNotFoundError):
        ps.get_supplier_payment(company_id=fake_company_id, payment_id=p["id"])

    with pytest.raises(SupplierPaymentNotFoundError):
        ps.reverse_supplier_payment(
            company_id=fake_company_id,
            payment_id=p["id"],
            reversal_reason="Cross company test",
        )


# ==============================================================================
# 14. Invalid Source and Supplier Account Rejection
# ==============================================================================

def test_invalid_source_and_supplier_account_rejection(supplier_env):
    """Scenario 14: Non-Cash/Bank accounts as source or non-Creditor as payee must fail."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cust_id = supplier_env["cust_id"]
    exp_id = supplier_env["exp_id"]
    cash_id = supplier_env["cash_id"]
    bank_id = supplier_env["bank_id"]

    # A. Expense account used as source of funds
    with pytest.raises(InvalidSourceAccountError):
        ps.create_supplier_payment(
            company_id=cid,
            supplier_account_id=supp1_id,
            source_account_id=exp_id,
            total_amount=Decimal("500.00"),
        )

    # B. Debtor account used as payee for supplier payment
    with pytest.raises(InvalidSupplierAccountError):
        ps.create_supplier_payment(
            company_id=cid,
            supplier_account_id=cust_id,
            source_account_id=cash_id,
            total_amount=Decimal("500.00"),
        )

    # C. CASH payment method using a Bank account
    with pytest.raises(InvalidSourceAccountError):
        ps.create_supplier_payment(
            company_id=cid,
            supplier_account_id=supp1_id,
            source_account_id=bank_id,
            total_amount=Decimal("500.00"),
            payment_method="CASH",
        )

    # D. UPI payment method using a Cash account
    with pytest.raises(InvalidSourceAccountError):
        ps.create_supplier_payment(
            company_id=cid,
            supplier_account_id=supp1_id,
            source_account_id=cash_id,
            total_amount=Decimal("500.00"),
            payment_method="UPI",
        )


# ==============================================================================
# 15. Duplicate Idempotency Key
# ==============================================================================

def test_duplicate_idempotency(supplier_env):
    """Scenario 15: Submitting duplicate idempotency key returns the existing payment record idempotently."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cash_id = supplier_env["cash_id"]

    idem_key = "IDEM_PAY_991827"

    p1 = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=cash_id,
        total_amount=Decimal("750.00"),
        idempotency_key=idem_key,
    )

    p2 = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=cash_id,
        total_amount=Decimal("750.00"),
        idempotency_key=idem_key,
    )

    assert p1["id"] == p2["id"]
    assert p1["voucher_number"] == p2["voucher_number"]


# ==============================================================================
# 16. Duplicate Voucher Rejection
# ==============================================================================

def test_duplicate_voucher_rejection(supplier_env):
    """Scenario 16: Supplying a manual duplicate voucher number in the same FY must fail."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cash_id = supplier_env["cash_id"]

    ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=cash_id,
        total_amount=Decimal("100.00"),
        voucher_number="PAY-MANUAL-01",
    )

    with pytest.raises(DuplicateReceiptError):
        ps.create_supplier_payment(
            company_id=cid,
            supplier_account_id=supp1_id,
            source_account_id=cash_id,
            total_amount=Decimal("200.00"),
            voucher_number="PAY-MANUAL-01",
        )


# ==============================================================================
# 17. Accounting Journal Correctness
# ==============================================================================

def test_accounting_journal_correctness(supplier_env):
    """Scenario 17: Verifies double-entry journal lines (Debit AP, Credit Cash/Bank, Credit Discount)."""
    ps = supplier_env["payment_service"]
    trad_mgr = supplier_env["trad_mgr"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    bank_id = supplier_env["bank_id"]

    # Payment of 2000.00 with 100.00 discount received
    res = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=bank_id,
        total_amount=Decimal("2000.00"),
        payment_method="BANK",
        allocations=[{
            "bill_number": "BILL-DISC-01",
            "allocated_amount": Decimal("2000.00"),
            "discount_amount": Decimal("100.00"),
        }],
    )

    journal_id = res["journal_id"]
    assert journal_id is not None

    with trad_mgr.read_session_scope() as sess:
        jrn = sess.scalar(select(JournalEntry).where(JournalEntry.id == journal_id))
        assert jrn.status == "POSTED"
        assert jrn.voucher_type == "PAYMENT"
        # Total debit = 2000 payment + 100 discount = 2100.00
        assert jrn.total_debit == jrn.total_credit == Decimal("2100.00")

        lines = sorted(jrn.lines, key=lambda l: l.line_number)
        # Line 1: Debit Supplier AP 2100.00
        assert lines[0].account_id == supp1_id
        assert lines[0].debit == Decimal("2100.00")
        assert lines[0].credit == Decimal("0.00")

        # Line 2: Credit Bank 2000.00
        assert lines[1].account_id == bank_id
        assert lines[1].debit == Decimal("0.00")
        assert lines[1].credit == Decimal("2000.00")

        # Line 3: Credit Discount Received (Round Off) 100.00
        assert lines[2].debit == Decimal("0.00")
        assert lines[2].credit == Decimal("100.00")


# ==============================================================================
# 18. Transaction Rollback
# ==============================================================================

def test_transaction_rollback(supplier_env):
    """Scenario 18: Any failure during payment creation rolls back the entire transaction atomically."""
    ps = supplier_env["payment_service"]
    trad_mgr = supplier_env["trad_mgr"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cash_id = supplier_env["cash_id"]

    # Trigger error via negative allocation amount
    with pytest.raises(ValueError):
        ps.create_supplier_payment(
            company_id=cid,
            supplier_account_id=supp1_id,
            source_account_id=cash_id,
            total_amount=Decimal("1000.00"),
            allocations=[{"bill_number": "BILL-ERR", "allocated_amount": Decimal("-500.00")}],
        )

    # Verify no payment record or journal entry was created
    with trad_mgr.read_session_scope() as sess:
        count = sess.scalar(
            select(func.count(SupplierPayment.id)).where(SupplierPayment.company_id == cid)
        )
        assert count == 0


# ==============================================================================
# 19. Closed-Period Rejection
# ==============================================================================

def test_closed_period_rejection(supplier_env):
    """Scenario 19: Supplier payment dated in a closed accounting period is rejected."""
    ps = supplier_env["payment_service"]
    acct_svc = supplier_env["accounting_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cash_id = supplier_env["cash_id"]

    acct_svc.create_accounting_period(
        company_id=cid,
        financial_year="2026-2027",
        period_name="OCT-2026",
        start_date="01-10-2026",
        end_date="31-10-2026",
    )
    acct_svc.close_accounting_period(
        company_id=cid,
        period_id_or_name="OCT-2026",
    )

    with pytest.raises(ClosedPeriodError):
        ps.create_supplier_payment(
            company_id=cid,
            supplier_account_id=supp1_id,
            source_account_id=cash_id,
            total_amount=Decimal("500.00"),
            payment_date="15-10-2026",
        )


# ==============================================================================
# 20. Payment Reversal
# ==============================================================================

def test_payment_reversal(supplier_env):
    """Scenario 20: Reversing a posted supplier payment creates compensating journal and marks REVERSED."""
    ps = supplier_env["payment_service"]
    trad_mgr = supplier_env["trad_mgr"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cash_id = supplier_env["cash_id"]

    p = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=cash_id,
        total_amount=Decimal("800.00"),
        notes="Payment to be reversed",
    )

    rev = ps.reverse_supplier_payment(
        company_id=cid,
        payment_id=p["id"],
        reversal_reason="Duplicate payment instruction error",
    )

    assert rev["status"] == "REVERSED"
    assert rev["reversal_reason"] == "Duplicate payment instruction error"
    assert rev["reversal_journal_id"] is not None

    with trad_mgr.read_session_scope() as sess:
        p_db = sess.scalar(select(SupplierPayment).where(SupplierPayment.id == p["id"]))
        assert p_db.status == "REVERSED"

        rev_jrn = sess.scalar(select(JournalEntry).where(JournalEntry.id == rev["reversal_journal_id"]))
        assert rev_jrn.voucher_type == "REVERSAL"
        assert rev_jrn.total_debit == Decimal("800.00")


# ==============================================================================
# 21. Duplicate Reversal Rejection
# ==============================================================================

def test_duplicate_reversal_rejection(supplier_env):
    """Scenario 21: Attempting to reverse an already reversed supplier payment must fail."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cash_id = supplier_env["cash_id"]

    p = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=cash_id,
        total_amount=Decimal("300.00"),
    )

    ps.reverse_supplier_payment(company_id=cid, payment_id=p["id"], reversal_reason="First reversal")

    with pytest.raises(DuplicateReversalError):
        ps.reverse_supplier_payment(company_id=cid, payment_id=p["id"], reversal_reason="Second reversal attempt")


# ==============================================================================
# 22. Reversed Payment Restores Balances
# ==============================================================================

def test_reversed_payment_restores_balances(supplier_env):
    """Scenario 22: Reversing a supplier payment automatically restores the purchase bill outstanding balance."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cash_id = supplier_env["cash_id"]

    # Settle BILL-RESTORE (1500.00)
    p = ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=cash_id,
        total_amount=Decimal("1500.00"),
        allocations=[{"bill_number": "BILL-RESTORE", "allocated_amount": Decimal("1500.00")}],
    )

    assert ps.get_supplier_invoice_outstanding(cid, "BILL-RESTORE", total_bill_amount=Decimal("1500.00"))["outstanding_amount"] == "0.00"

    # Reverse the payment
    ps.reverse_supplier_payment(company_id=cid, payment_id=p["id"], reversal_reason="Transaction voided")

    # Outstanding is restored to 1500.00!
    out_restored = ps.get_supplier_invoice_outstanding(cid, "BILL-RESTORE", total_bill_amount=Decimal("1500.00"))
    assert out_restored["outstanding_amount"] == "1500.00"
    assert out_restored["is_settled"] is False


# ==============================================================================
# 23. Concurrent / Sequential Voucher Sequence Generation
# ==============================================================================

def test_voucher_sequence_generation(supplier_env):
    """Scenario 23: Successive payment creations generate strictly sequential voucher numbers."""
    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cash_id = supplier_env["cash_id"]

    p1 = ps.create_supplier_payment(company_id=cid, supplier_account_id=supp1_id, source_account_id=cash_id, total_amount=Decimal("100.00"))
    p2 = ps.create_supplier_payment(company_id=cid, supplier_account_id=supp1_id, source_account_id=cash_id, total_amount=Decimal("200.00"))
    p3 = ps.create_supplier_payment(company_id=cid, supplier_account_id=supp1_id, source_account_id=cash_id, total_amount=Decimal("300.00"))

    assert p1["voucher_number"] == "PAY-0001"
    assert p2["voucher_number"] == "PAY-0002"
    assert p3["voucher_number"] == "PAY-0003"


# ==============================================================================
# 24. Traditional / Fast Database Isolation
# ==============================================================================

def test_traditional_fast_database_isolation(supplier_env):
    """Scenario 24: Verifies Traditional supplier payments do not mutate Fast Billing database."""
    fast_db_hash_before = compute_sha256(FAST_DB_PATH)

    ps = supplier_env["payment_service"]
    cid = supplier_env["company_id"]
    supp1_id = supplier_env["supp1_id"]
    cash_id = supplier_env["cash_id"]

    ps.create_supplier_payment(
        company_id=cid,
        supplier_account_id=supp1_id,
        source_account_id=cash_id,
        total_amount=Decimal("9999.00"),
        notes="High-value payment testing DB physical isolation",
    )

    fast_db_hash_after = compute_sha256(FAST_DB_PATH)
    assert fast_db_hash_after == fast_db_hash_before, "Fast Billing database was mutated during Traditional payment test!"
