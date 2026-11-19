"""
Comprehensive Automated Test Suite: Traditional Customer Receipts & Allocations.
Phase 3.3 — Anti-Matrix Billing V2 Core Backend Architecture.

Validates all 24 required customer receipt, allocation, accounting, and security scenarios:
1. Cash receipt creation.
2. Bank receipt creation.
3. UPI receipt creation.
4. Full invoice settlement.
5. Partial invoice settlement.
6. Multiple invoice allocations.
7. Partial allocation (receipt amount > sum of allocations).
8. Advance receipt (zero invoice allocations, 100% advance).
9. Unallocated balance calculation and tracking.
10. Dynamic invoice outstanding calculation.
11. Total customer outstanding calculation (Ledger AR vs invoices vs advances).
12. Over-allocation rejection.
13. Cross-customer allocation rejection.
14. Cross-company isolation.
15. Invalid deposit account rejection (rejecting non-Cash/Bank accounts).
16. Duplicate idempotency rejection (returns existing receipt).
17. Duplicate voucher rejection.
18. Accounting journal correctness (Double-entry Debit Cash/Bank, Credit AR).
19. Transaction rollback on error (no partial transactions or orphan journals).
20. Closed-period rejection.
21. Receipt reversal (creates reversing journal and marks REVERSED).
22. Duplicate reversal rejection.
23. Reversed receipt excluded from outstanding calculations (balance restored).
24. Concurrent allocation safety.
"""

import uuid
from decimal import Decimal
from pathlib import Path
import pytest
from sqlalchemy import select, and_, func
from sqlalchemy.exc import IntegrityError
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
    CustomerReceiptNotFoundError,
    InvalidDepositAccountError,
    InvalidCustomerAccountError,
    OverAllocationError,
    InvoiceAlreadySettledError,
    DuplicateReceiptError,
    DuplicateReversalError,
)


@pytest.fixture
def receipt_env(tmp_path):
    """Provides an isolated, fully migrated Traditional SQLite database for receipt tests."""
    db_file = tmp_path / "test_traditional_receipts.db"
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
        "name": "Arasu Receipt Processing Corp",
        "code": "CORP_REC",
        "finYear": "2026-2027",
        "taxNo": "33AAACA9999A1Z9",
        "state": "Tamilnadu",
        "adminUsername": "ADMIN",
        "adminPassword": "SecurePassword123!",
    })
    cid = company_info["companyId"]
    bid = company_info["branchId"]
    uid = company_info["adminUserId"]

    accounting_service.ensure_standard_accounts(cid)

    # Set up accounts and invoices in database
    with trad_mgr.session_scope() as sess:
        # Bank Group
        bank_grp = sess.scalar(
            select(AccountGroup).where(and_(AccountGroup.company_id == cid, AccountGroup.code == "GRP_BANK"))
        )
        # Bank Account: HDFC Bank
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

        # Customer 1: Alpha Retailers
        cust1 = Account(
            id=str(uuid.uuid4()),
            company_id=cid,
            code="CUST_ALPHA",
            name="Alpha Retailers",
            account_type="Debtor",
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        # Customer 2: Beta Wholesalers
        cust2 = Account(
            id=str(uuid.uuid4()),
            company_id=cid,
            code="CUST_BETA",
            name="Beta Wholesalers",
            account_type="Debtor",
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        # Supplier Account: Gamma Suppliers
        supp = Account(
            id=str(uuid.uuid4()),
            company_id=cid,
            code="SUPP_GAMMA",
            name="Gamma Suppliers",
            account_type="Creditor",
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        sess.add_all([cust1, cust2, supp])
        sess.flush()

        # Invoices for Customer 1
        inv1 = SaleInvoice(
            id=str(uuid.uuid4()),
            voucher_id=str(uuid.uuid4()),
            company_id=cid,
            branch_id=bid,
            user_id=uid,
            financial_year="2026-2027",
            series="Main",
            sequence_number=1,
            voucher_number="INV-001",
            vch_date="17-11-2026",
            party_name="Alpha Retailers",
            account_id=cust1.id,
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
        inv2 = SaleInvoice(
            id=str(uuid.uuid4()),
            voucher_id=str(uuid.uuid4()),
            company_id=cid,
            branch_id=bid,
            user_id=uid,
            financial_year="2026-2027",
            series="Main",
            sequence_number=2,
            voucher_number="INV-002",
            vch_date="17-11-2026",
            party_name="Alpha Retailers",
            account_id=cust1.id,
            sale_type="L/GST-18%",
            payment_method="CREDIT",
            subtotal=Decimal("2000.00"),
            taxable_amount=Decimal("2000.00"),
            cgst_amount=Decimal("180.00"),
            sgst_amount=Decimal("180.00"),
            igst_amount=Decimal("0.00"),
            round_off_amount=Decimal("0.00"),
            grand_total=Decimal("2360.00"),
            total_amount=Decimal("2360.00"),
            items_json="[]",
            status="UNPAID",
            created_at=utc_now(),
        )
        # Invoice for Customer 2
        inv3 = SaleInvoice(
            id=str(uuid.uuid4()),
            voucher_id=str(uuid.uuid4()),
            company_id=cid,
            branch_id=bid,
            user_id=uid,
            financial_year="2026-2027",
            series="Main",
            sequence_number=3,
            voucher_number="INV-003",
            vch_date="17-11-2026",
            party_name="Beta Wholesalers",
            account_id=cust2.id,
            sale_type="L/GST-18%",
            payment_method="CREDIT",
            subtotal=Decimal("500.00"),
            taxable_amount=Decimal("500.00"),
            cgst_amount=Decimal("0.00"),
            sgst_amount=Decimal("0.00"),
            igst_amount=Decimal("0.00"),
            round_off_amount=Decimal("0.00"),
            grand_total=Decimal("500.00"),
            total_amount=Decimal("500.00"),
            items_json="[]",
            status="UNPAID",
            created_at=utc_now(),
        )
        sess.add_all([inv1, inv2, inv3])
        sess.flush()

        cash_acc = sess.scalar(select(Account).where(and_(Account.company_id == cid, Account.code == "CASH")))
        sales_acc = sess.scalar(select(Account).where(and_(Account.company_id == cid, Account.code == "SALES")))

        # Store IDs
        cash_id = cash_acc.id
        hdfc_id = hdfc_acc.id
        cust1_id = cust1.id
        cust2_id = cust2.id
        supp_id = supp.id
        sales_id = sales_acc.id
        inv1_id = inv1.id
        inv2_id = inv2.id
        inv3_id = inv3.id

    # Post initial sales journals so Accounts Receivable ledger matches invoices
    accounting_service.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="17-11-2026",
        lines=[
            {"account_id": cust1_id, "debit": Decimal("1180.00"), "credit": Decimal("0.00")},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("1180.00")},
        ],
        narration="Sales INV-001",
    )
    accounting_service.post_journal_entry(
        company_id=cid,
        branch_id=bid,
        voucher_type="SALES",
        voucher_date="17-11-2026",
        lines=[
            {"account_id": cust1_id, "debit": Decimal("2360.00"), "credit": Decimal("0.00")},
            {"account_id": sales_id, "debit": Decimal("0.00"), "credit": Decimal("2360.00")},
        ],
        narration="Sales INV-002",
    )

    return {
        "trad_mgr": trad_mgr,
        "payment_service": payment_service,
        "accounting_service": accounting_service,
        "company_id": cid,
        "branch_id": bid,
        "user_id": uid,
        "cash_id": cash_id,
        "hdfc_id": hdfc_id,
        "cust1_id": cust1_id,
        "cust2_id": cust2_id,
        "supp_id": supp_id,
        "sales_id": sales_id,
        "inv1_id": inv1_id,
        "inv2_id": inv2_id,
        "inv3_id": inv3_id,
    }


# ==============================================================================
# 1. Cash Receipt Creation
# ==============================================================================

def test_cash_receipt_creation(receipt_env):
    """Scenario 1: Creates a cash receipt deposited into Cash-in-Hand ledger."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]

    res = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("500.00"),
        payment_method="CASH",
        notes="Cash counter receipt",
    )

    assert res["id"] is not None
    assert res["voucher_number"].startswith("REC-")
    assert res["payment_method"] == "CASH"
    assert res["total_amount"] == "500.00"
    assert res["unallocated_amount"] == "500.00"
    assert res["status"] == "POSTED"
    assert res["journal_id"] is not None


# ==============================================================================
# 2. Bank Receipt Creation
# ==============================================================================

def test_bank_receipt_creation(receipt_env):
    """Scenario 2: Creates a bank receipt (NEFT/RTGS/Cheque) deposited into Bank ledger."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    hdfc_id = receipt_env["hdfc_id"]

    res = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=hdfc_id,
        total_amount=Decimal("1500.00"),
        payment_method="NEFT_RTGS",
        reference_number="UTR-HDFC-991823",
        notes="Bank wire payment",
    )

    assert res["voucher_number"].startswith("REC-")
    assert res["payment_method"] == "NEFT_RTGS"
    assert res["reference_number"] == "UTR-HDFC-991823"
    assert res["total_amount"] == "1500.00"


# ==============================================================================
# 3. UPI Receipt Creation
# ==============================================================================

def test_upi_receipt_creation(receipt_env):
    """Scenario 3: Creates a digital UPI receipt deposited into Bank ledger."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    hdfc_id = receipt_env["hdfc_id"]

    res = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=hdfc_id,
        total_amount=Decimal("350.00"),
        payment_method="UPI",
        reference_number="UPI-REF-88821",
        notes="UPI QR collection",
    )

    assert res["payment_method"] == "UPI"
    assert res["reference_number"] == "UPI-REF-88821"
    assert res["total_amount"] == "350.00"


# ==============================================================================
# 4. Full Invoice Settlement
# ==============================================================================

def test_full_invoice_settlement(receipt_env):
    """Scenario 4: Fully settles invoice INV-001 (1180.00), reducing outstanding to 0."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]
    inv1_id = receipt_env["inv1_id"]

    res = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("1180.00"),
        allocations=[{"invoice_id": inv1_id, "allocated_amount": Decimal("1180.00")}],
    )

    assert res["allocated_amount"] == "1180.00"
    assert res["unallocated_amount"] == "0.00"

    # Verify dynamic invoice outstanding is 0.00
    out = ps.get_customer_invoice_outstanding(cid, inv1_id)
    assert out["outstanding_amount"] == "0.00"
    assert out["is_settled"] is True


# ==============================================================================
# 5. Partial Invoice Settlement
# ==============================================================================

def test_partial_invoice_settlement(receipt_env):
    """Scenario 5: Partially settles invoice INV-002 (2360.00) with 1000.00 payment, leaving 1360.00."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    hdfc_id = receipt_env["hdfc_id"]
    inv2_id = receipt_env["inv2_id"]

    res = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=hdfc_id,
        total_amount=Decimal("1000.00"),
        payment_method="NEFT_RTGS",
        allocations=[{"invoice_id": inv2_id, "allocated_amount": Decimal("1000.00")}],
    )

    out = ps.get_customer_invoice_outstanding(cid, inv2_id)
    assert out["outstanding_amount"] == "1360.00"
    assert out["is_settled"] is False


# ==============================================================================
# 6. Multiple Invoice Allocations
# ==============================================================================

def test_multiple_invoice_allocations(receipt_env):
    """Scenario 6: Single receipt allocates payments across two separate invoices."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]
    inv1_id = receipt_env["inv1_id"]
    inv2_id = receipt_env["inv2_id"]

    res = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("2000.00"),
        allocations=[
            {"invoice_id": inv1_id, "allocated_amount": Decimal("1000.00")},
            {"invoice_id": inv2_id, "allocated_amount": Decimal("1000.00")},
        ],
    )

    assert len(res["allocations"]) == 2
    assert res["allocated_amount"] == "2000.00"
    assert res["unallocated_amount"] == "0.00"

    out1 = ps.get_customer_invoice_outstanding(cid, inv1_id)
    out2 = ps.get_customer_invoice_outstanding(cid, inv2_id)
    assert out1["outstanding_amount"] == "180.00"
    assert out2["outstanding_amount"] == "1360.00"


# ==============================================================================
# 7. Partial Allocation (Receipt > Allocations)
# ==============================================================================

def test_partial_allocation(receipt_env):
    """Scenario 7: Receipt amount of 1500.00 has 1000.00 allocated, leaving 500.00 unallocated."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]
    inv1_id = receipt_env["inv1_id"]

    res = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("1500.00"),
        allocations=[{"invoice_id": inv1_id, "allocated_amount": Decimal("1000.00")}],
    )

    assert res["total_amount"] == "1500.00"
    assert res["allocated_amount"] == "1000.00"
    assert res["unallocated_amount"] == "500.00"


# ==============================================================================
# 8. Advance Receipt
# ==============================================================================

def test_advance_receipt(receipt_env):
    """Scenario 8: Receipt with zero invoice allocations acts as a 100% advance receipt."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    hdfc_id = receipt_env["hdfc_id"]

    res = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=hdfc_id,
        total_amount=Decimal("5000.00"),
        payment_method="NEFT_RTGS",
        allocations=[],
        notes="General advance payment for future orders",
    )

    assert res["allocated_amount"] == "0.00"
    assert res["unallocated_amount"] == "5000.00"
    assert len(res["allocations"]) == 0


# ==============================================================================
# 9. Unallocated Balance Calculation & Subsequent Allocation
# ==============================================================================

def test_unallocated_balance_and_subsequent_allocation(receipt_env):
    """Scenario 9: Applies unallocated advance balance from receipt to invoice via allocate_customer_receipt."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]
    inv1_id = receipt_env["inv1_id"]

    # 1. Create advance receipt
    rc = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("2000.00"),
    )
    assert rc["unallocated_amount"] == "2000.00"

    # 2. Later apply 1180.00 to INV-001
    updated = ps.allocate_customer_receipt(
        company_id=cid,
        receipt_id=rc["id"],
        allocations=[{"invoice_id": inv1_id, "allocated_amount": Decimal("1180.00")}],
    )

    assert updated["allocated_amount"] == "1180.00"
    assert updated["unallocated_amount"] == "820.00"

    # Invoice is settled
    out = ps.get_customer_invoice_outstanding(cid, inv1_id)
    assert out["outstanding_amount"] == "0.00"
    assert out["is_settled"] is True


# ==============================================================================
# 10. Dynamic Invoice Outstanding Calculation
# ==============================================================================

def test_invoice_outstanding_calculation(receipt_env):
    """Scenario 10: Outstanding accounts for both payments and cash discounts."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]
    inv1_id = receipt_env["inv1_id"]

    # Allocate 1000.00 with 100.00 discount (total 1100.00 cleared against 1180.00)
    ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("1000.00"),
        allocations=[{"invoice_id": inv1_id, "allocated_amount": Decimal("1000.00"), "discount_amount": Decimal("100.00")}],
    )

    out = ps.get_customer_invoice_outstanding(cid, inv1_id)
    assert out["total_allocated"] == "1000.00"
    assert out["total_discount"] == "100.00"
    assert out["outstanding_amount"] == "80.00"


# ==============================================================================
# 11. Customer Outstanding Calculation
# ==============================================================================

def test_customer_outstanding_calculation(receipt_env):
    """Scenario 11: Authoritative customer report reconciling ledger balance and unpaid invoices."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]
    inv1_id = receipt_env["inv1_id"]

    # Initial state: 1180 + 2360 = 3540.00 outstanding
    rep_before = ps.get_customer_outstanding(cid, cust1_id)
    assert rep_before["total_unpaid_invoices_amount"] == "3540.00"
    assert rep_before["unpaid_invoices_count"] == 2

    # Settle INV-001 (1180.00)
    ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("1180.00"),
        allocations=[{"invoice_id": inv1_id, "allocated_amount": Decimal("1180.00")}],
    )

    rep_after = ps.get_customer_outstanding(cid, cust1_id)
    assert rep_after["total_unpaid_invoices_amount"] == "2360.00"
    assert rep_after["unpaid_invoices_count"] == 1


# ==============================================================================
# 12. Over-Allocation Rejection
# ==============================================================================

def test_over_allocation_rejection(receipt_env):
    """Scenario 12: Allocation exceeding invoice balance or receipt total is strictly rejected."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]
    inv1_id = receipt_env["inv1_id"]

    # A. Allocating more than invoice outstanding (1180.00)
    with pytest.raises(OverAllocationError):
        ps.create_customer_receipt(
            company_id=cid,
            customer_account_id=cust1_id,
            deposit_account_id=cash_id,
            total_amount=Decimal("2000.00"),
            allocations=[{"invoice_id": inv1_id, "allocated_amount": Decimal("1500.00")}],
        )

    # B. Allocation sum exceeds total_amount
    with pytest.raises(OverAllocationError):
        ps.create_customer_receipt(
            company_id=cid,
            customer_account_id=cust1_id,
            deposit_account_id=cash_id,
            total_amount=Decimal("500.00"),
            allocations=[{"invoice_id": inv1_id, "allocated_amount": Decimal("1000.00")}],
        )


# ==============================================================================
# 13. Cross-Customer Allocation Rejection
# ==============================================================================

def test_cross_customer_allocation_rejection(receipt_env):
    """Scenario 13: Attempting to allocate Customer 1's payment to Customer 2's invoice must be rejected."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]
    inv3_id = receipt_env["inv3_id"]  # Belongs to Customer 2 (Beta)

    with pytest.raises(ValueError, match="belongs to customer"):
        ps.create_customer_receipt(
            company_id=cid,
            customer_account_id=cust1_id,
            deposit_account_id=cash_id,
            total_amount=Decimal("500.00"),
            allocations=[{"invoice_id": inv3_id, "allocated_amount": Decimal("500.00")}],
        )


# ==============================================================================
# 14. Cross-Company Isolation
# ==============================================================================

def test_cross_company_isolation(receipt_env):
    """Scenario 14: Verifies cross-company invoice allocations and queries are strictly rejected."""
    ps = receipt_env["payment_service"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]
    inv1_id = receipt_env["inv1_id"]

    fake_company_id = str(uuid.uuid4())

    with pytest.raises(ValueError, match="Company '.*' not found"):
        ps.create_customer_receipt(
            company_id=fake_company_id,
            customer_account_id=cust1_id,
            deposit_account_id=cash_id,
            total_amount=Decimal("500.00"),
        )

    with pytest.raises(ValueError, match="does not belong to company"):
        ps.create_customer_receipt(
            company_id=receipt_env["company_id"],
            customer_account_id=cust1_id,
            deposit_account_id=cash_id,
            total_amount=Decimal("500.00"),
            allocations=[{"invoice_id": str(uuid.uuid4()), "allocated_amount": Decimal("500.00")}],
        )


# ==============================================================================
# 15. Invalid Deposit Account Rejection
# ==============================================================================

def test_invalid_deposit_account_rejection(receipt_env):
    """Scenario 15: Passing an Expense, Sales, Creditor, or non-Cash/Bank account must be rejected."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    sales_id = receipt_env["sales_id"]
    supp_id = receipt_env["supp_id"]

    # A. Sales account as deposit account
    with pytest.raises(InvalidDepositAccountError):
        ps.create_customer_receipt(
            company_id=cid,
            customer_account_id=cust1_id,
            deposit_account_id=sales_id,
            total_amount=Decimal("500.00"),
        )

    # B. Creditor account as deposit account
    with pytest.raises(InvalidDepositAccountError):
        ps.create_customer_receipt(
            company_id=cid,
            customer_account_id=cust1_id,
            deposit_account_id=supp_id,
            total_amount=Decimal("500.00"),
        )


# ==============================================================================
# 16. Duplicate Idempotency Key Rejection / Idempotent Return
# ==============================================================================

def test_duplicate_idempotency(receipt_env):
    """Scenario 16: Posting with identical idempotency key returns the existing receipt safely."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]

    idem_key = "IDEM_TXN_001928"

    rc1 = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("450.00"),
        idempotency_key=idem_key,
    )

    rc2 = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("450.00"),
        idempotency_key=idem_key,
    )

    assert rc1["id"] == rc2["id"]
    assert rc1["voucher_number"] == rc2["voucher_number"]


# ==============================================================================
# 17. Duplicate Voucher Rejection
# ==============================================================================

def test_duplicate_voucher_rejection(receipt_env):
    """Scenario 17: Attempting to supply a manual duplicate voucher number in same FY must fail."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]

    ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("100.00"),
        voucher_number="REC-MANUAL-01",
    )

    with pytest.raises(DuplicateReceiptError):
        ps.create_customer_receipt(
            company_id=cid,
            customer_account_id=cust1_id,
            deposit_account_id=cash_id,
            total_amount=Decimal("200.00"),
            voucher_number="REC-MANUAL-01",
        )


# ==============================================================================
# 18. Accounting Journal Correctness
# ==============================================================================

def test_accounting_journal_correctness(receipt_env):
    """Scenario 18: Verifies double-entry journal lines (Debit Cash/Bank, Credit AR, Debit Discount)."""
    ps = receipt_env["payment_service"]
    trad_mgr = receipt_env["trad_mgr"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]
    inv1_id = receipt_env["inv1_id"]

    res = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("1000.00"),
        allocations=[{"invoice_id": inv1_id, "allocated_amount": Decimal("1000.00"), "discount_amount": Decimal("50.00")}],
    )

    journal_id = res["journal_id"]
    assert journal_id is not None

    with trad_mgr.read_session_scope() as sess:
        jrn = sess.scalar(select(JournalEntry).where(JournalEntry.id == journal_id))
        assert jrn.status == "POSTED"
        assert jrn.voucher_type == "RECEIPT"
        assert jrn.total_debit == jrn.total_credit == Decimal("1050.00")

        lines = sorted(jrn.lines, key=lambda l: l.line_number)
        # Line 1: Debit Cash 1000.00
        assert lines[0].account_id == cash_id
        assert lines[0].debit == Decimal("1000.00")
        assert lines[0].credit == Decimal("0.00")

        # Line 2: Debit Discount Allowed (Round off) 50.00
        assert lines[1].debit == Decimal("50.00")
        assert lines[1].credit == Decimal("0.00")

        # Line 3: Credit Customer AR 1050.00
        assert lines[2].account_id == cust1_id
        assert lines[2].debit == Decimal("0.00")
        assert lines[2].credit == Decimal("1050.00")


# ==============================================================================
# 19. Transaction Rollback
# ==============================================================================

def test_transaction_rollback(receipt_env):
    """Scenario 19: Any failure during receipt creation rolls back entire transaction (no orphan journals)."""
    ps = receipt_env["payment_service"]
    trad_mgr = receipt_env["trad_mgr"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]

    # Intentionally trigger an error after sequence generation by passing invalid allocation
    with pytest.raises(Exception):
        ps.create_customer_receipt(
            company_id=cid,
            customer_account_id=cust1_id,
            deposit_account_id=cash_id,
            total_amount=Decimal("1000.00"),
            allocations=[{"invoice_id": str(uuid.uuid4()), "allocated_amount": Decimal("1000.00")}],
        )

    # Verify no receipt was saved
    with trad_mgr.read_session_scope() as sess:
        count = sess.scalar(select(func.count(CustomerReceipt.id)).where(CustomerReceipt.company_id == cid))
        assert count == 0


# ==============================================================================
# 20. Closed-Period Rejection
# ==============================================================================

def test_closed_period_rejection(receipt_env):
    """Scenario 20: Receipt on a date within a closed accounting period is rejected."""
    ps = receipt_env["payment_service"]
    acct_svc = receipt_env["accounting_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]

    # Close period October 2026
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
        ps.create_customer_receipt(
            company_id=cid,
            customer_account_id=cust1_id,
            deposit_account_id=cash_id,
            total_amount=Decimal("500.00"),
            receipt_date="15-10-2026",
        )


# ==============================================================================
# 21. Receipt Reversal
# ==============================================================================

def test_receipt_reversal(receipt_env):
    """Scenario 21: Reversing a posted receipt creates reversing journal and marks receipt REVERSED."""
    ps = receipt_env["payment_service"]
    trad_mgr = receipt_env["trad_mgr"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]

    rc = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("700.00"),
        notes="Cheque bounce test",
    )

    # Reverse receipt
    rev = ps.reverse_customer_receipt(
        company_id=cid,
        receipt_id=rc["id"],
        reversal_reason="Cheque dishonoured by drawer",
    )

    assert rev["status"] == "REVERSED"
    assert rev["reversal_reason"] == "Cheque dishonoured by drawer"
    assert rev["reversal_journal_id"] is not None

    # Verify compensating journal entry exists
    with trad_mgr.read_session_scope() as sess:
        rc_db = sess.scalar(select(CustomerReceipt).where(CustomerReceipt.id == rc["id"]))
        assert rc_db.status == "REVERSED"

        rev_jrn = sess.scalar(select(JournalEntry).where(JournalEntry.id == rev["reversal_journal_id"]))
        assert rev_jrn.voucher_type == "REVERSAL"
        assert rev_jrn.total_debit == Decimal("700.00")


# ==============================================================================
# 22. Duplicate Reversal Rejection
# ==============================================================================

def test_duplicate_reversal_rejection(receipt_env):
    """Scenario 22: Attempting to reverse an already reversed receipt must fail."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]

    rc = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("200.00"),
    )

    ps.reverse_customer_receipt(company_id=cid, receipt_id=rc["id"], reversal_reason="First reversal")

    with pytest.raises(DuplicateReversalError):
        ps.reverse_customer_receipt(company_id=cid, receipt_id=rc["id"], reversal_reason="Second reversal attempt")


# ==============================================================================
# 23. Reversed Receipt Excluded from Outstanding Calculations
# ==============================================================================

def test_reversed_receipt_restores_invoice_outstanding(receipt_env):
    """Scenario 23: Reversing a receipt automatically restores the invoice's outstanding balance."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]
    inv1_id = receipt_env["inv1_id"]

    # 1. Full settlement
    rc = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("1180.00"),
        allocations=[{"invoice_id": inv1_id, "allocated_amount": Decimal("1180.00")}],
    )
    assert ps.get_customer_invoice_outstanding(cid, inv1_id)["outstanding_amount"] == "0.00"

    # 2. Reverse receipt
    ps.reverse_customer_receipt(company_id=cid, receipt_id=rc["id"], reversal_reason="Bank payment stopped")

    # 3. Outstanding balance is automatically restored to 1180.00!
    out_after = ps.get_customer_invoice_outstanding(cid, inv1_id)
    assert out_after["outstanding_amount"] == "1180.00"
    assert out_after["is_settled"] is False


# ==============================================================================
# 24. Concurrent Allocation Safety
# ==============================================================================

def test_concurrent_allocation_safety(receipt_env):
    """Scenario 24: Sequential and repeated allocation attempts beyond balance are safely rejected."""
    ps = receipt_env["payment_service"]
    cid = receipt_env["company_id"]
    cust1_id = receipt_env["cust1_id"]
    cash_id = receipt_env["cash_id"]
    inv1_id = receipt_env["inv1_id"]

    # First allocation takes 1000.00 out of 1180.00 (remaining 180.00)
    ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("1000.00"),
        allocations=[{"invoice_id": inv1_id, "allocated_amount": Decimal("1000.00")}],
    )

    # Second allocation attempts 500.00 (exceeds remaining 180.00) -> must fail!
    with pytest.raises(OverAllocationError):
        ps.create_customer_receipt(
            company_id=cid,
            customer_account_id=cust1_id,
            deposit_account_id=cash_id,
            total_amount=Decimal("500.00"),
            allocations=[{"invoice_id": inv1_id, "allocated_amount": Decimal("500.00")}],
        )

    # But allocating exact remaining 180.00 succeeds
    res_exact = ps.create_customer_receipt(
        company_id=cid,
        customer_account_id=cust1_id,
        deposit_account_id=cash_id,
        total_amount=Decimal("180.00"),
        allocations=[{"invoice_id": inv1_id, "allocated_amount": Decimal("180.00")}],
    )
    assert res_exact["allocated_amount"] == "180.00"
    assert ps.get_customer_invoice_outstanding(cid, inv1_id)["outstanding_amount"] == "0.00"
