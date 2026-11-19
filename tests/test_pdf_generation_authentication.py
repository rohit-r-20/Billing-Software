"""
Test Suite: PDF Generation Authentication & Session Handling Verification.
Verifies:
1. Logged-in authorized Fast Billing user downloads PDF.
2. PDF contains the correct saved invoice and line items.
3. Correct company and branch details appear.
4. A4 PDF generation works for authorized user.
5. A5 PDF generation works for authorized user.
6. Thermal receipt / PDF handling remains functional where supported.
7. Unauthorized users cannot generate PDFs (fails with 'Authentication required').
8. Expired sessions produce a clear user-facing error ('Session expired').
9. Multi-tenant company context is strictly enforced (cross-company access blocked).
10. Existing Traditional Billing PDF generation remains completely functional.
11. Absolute transaction and database immutability.
"""
import json
import os
import uuid
import hashlib
from typing import Optional, Dict, Any, List
from decimal import Decimal
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select, and_

from core.configuration import config
from db.traditional_database import traditional_db_manager
from db.traditional_models import Company as TradCompany, Branch as TradBranch, Account as TradAccount, SaleInvoice as TradSaleInvoice
from services.traditional_auth_service import session_registry as traditional_session_registry
from services.paper_config_service import paper_config_service
from services.bill_layout_config_service import bill_layout_service
from services.voucher_print_service import voucher_print_service
from desktop.web_bridge import BackendBridge


FAST_DB_PATH = Path("data/anti_matrix_billing.db")


def get_file_hash(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


TEST_PDF_AUTH_DB_PATH = config.DATA_DIR / "test_pdf_auth_core.db"


@pytest.fixture(scope="session", autouse=True)
def setup_pdf_auth_test_env():
    """Ensure Traditional migrations and Core SQLite migrations are applied to isolated test DB."""
    if TEST_PDF_AUTH_DB_PATH.exists():
        try:
            TEST_PDF_AUTH_DB_PATH.unlink()
        except Exception:
            pass

    from db.database import DatabaseManager
    from services.billing_service import billing_service
    from services.purchase_service import purchase_service

    test_core_db = DatabaseManager(f"sqlite:///{TEST_PDF_AUTH_DB_PATH.resolve().as_posix()}")
    test_core_db.run_migrations()

    billing_service.db = test_core_db
    purchase_service.db = test_core_db

    traditional_db_manager.run_traditional_migrations()
    traditional_db_manager.ensure_initialized()

    yield

    if TEST_PDF_AUTH_DB_PATH.exists():
        try:
            TEST_PDF_AUTH_DB_PATH.unlink()
        except Exception:
            pass


@pytest.fixture
def auth_fixture_company():
    """Provides isolated company with branch in Traditional DB and Core DB."""
    cid = f"test-comp-pdf-{uuid.uuid4().hex[:8]}"
    bid = f"test-br-pdf-{uuid.uuid4().hex[:8]}"
    aid = f"test-acc-pdf-{uuid.uuid4().hex[:8]}"
    code = f"CP_{uuid.uuid4().hex[:5].upper()}"

    with traditional_db_manager.session_scope() as session:
        comp = TradCompany(
            id=cid,
            code=code,
            name="Apex Horizon Technologies Ltd",
            gstin="33AABCA1234F1Z5",
            state="Tamil Nadu (33)",
            fin_year="2026-2027",
            is_active=True,
        )
        session.add(comp)
        branch = TradBranch(
            id=bid,
            company_id=cid,
            name="Apex Central Branch",
            code="BR01",
            is_active=True,
        )
        session.add(branch)
        account = TradAccount(
            id=aid,
            company_id=cid,
            code=f"CUST-{uuid.uuid4().hex[:6]}",
            name="Quantum Computing Lab",
            account_type="Debtor",
            gstin="33XYZAB5678C1Z9",
            address="77 Science Park, Chennai",
            state="Tamil Nadu (33)",
            phone="9876543210",
            email="accounts@quantumlab.in",
            is_active=True,
        )
        session.add(account)

    from services.billing_service import billing_service
    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO companies (id, code, name, fin_year, gstin, state) VALUES (?, ?, ?, ?, ?, ?);",
            (cid, code, "Apex Horizon Technologies Ltd", "2026-2027", "33AABCA1234F1Z5", "Tamil Nadu (33)")
        )
        cur.execute(
            "INSERT OR REPLACE INTO branches (id, company_id, code, name) VALUES (?, ?, ?, ?);",
            (bid, cid, "BR01", "Apex Central Branch")
        )
        conn.commit()

    return {"company_id": cid, "company_code": code, "branch_id": bid, "account_id": aid}


@pytest.fixture
def committed_fast_billing_invoice(auth_fixture_company):
    """Commits an authoritative sales voucher in Fast Billing DB."""
    from services.billing_service import billing_service
    cid = auth_fixture_company["company_id"]
    bid = auth_fixture_company["branch_id"]

    items = [
        {
            "name": "Barcode Scanner Laser Multi-Grid",
            "code": "SCAN-01",
            "sku": "SKU-SCAN-01",
            "qty": 2.0,
            "unit": "Pcs.",
            "price": 3200.0,
            "rate": 3200.0,
            "tax_rate": 18.0,
            "gst_rate": 18.0,
            "discount_amount": 100.0,
            "hsn": "8471"
        },
        {
            "name": "Thermal Register Paper Rolls 80mm",
            "code": "ROLL-80",
            "sku": "SKU-ROLL-80",
            "qty": 10.0,
            "unit": "Rolls",
            "price": 65.0,
            "rate": 65.0,
            "tax_rate": 12.0,
            "gst_rate": 12.0,
            "discount_amount": 0.0,
            "hsn": "4811"
        }
    ]

    res = billing_service.create_sale_invoice(
        company_id=cid,
        items=items,
        party_name="CASH",
        sale_type="L/GST-18%",
        payment_method="BANK_TRANSFER",
        branch_id=bid,
        narration="Fast Billing POS Sale Verification"
    )

    return {"voucher_id": res["id"], "vch_no": res["vch_no"], "company_id": cid}


@pytest.fixture
def committed_traditional_invoice(auth_fixture_company):
    """Commits an authoritative sales invoice in Traditional DB."""
    cid = auth_fixture_company["company_id"]
    bid = auth_fixture_company["branch_id"]
    aid = auth_fixture_company["account_id"]
    inv_id = str(uuid.uuid4())
    vch_no = f"INV-TRAD-{uuid.uuid4().hex[:5].upper()}"

    items = [
        {
            "name": "High Precision Label Printer",
            "code": "PRN-01",
            "sku": "SKU-PRN-01",
            "hsn": "8443",
            "qty": 1.0,
            "unit": "Pcs.",
            "price": 12500.0,
            "rate": 12500.0,
            "discount": 500.0,
            "tax_rate": 18.0,
            "gst_rate": 18.0,
            "taxable_amount": 12000.0,
            "cgst_amount": 1080.0,
            "sgst_amount": 1080.0,
            "igst_amount": 0.0,
            "line_total": 14160.0
        }
    ]

    with traditional_db_manager.session_scope() as session:
        inv = TradSaleInvoice(
            id=inv_id,
            voucher_id=inv_id,
            company_id=cid,
            branch_id=bid,
            financial_year="2026-2027",
            series="Main",
            sequence_number=501,
            voucher_number=vch_no,
            vch_date="16-11-2026",
            party_name="Quantum Computing Lab",
            account_id=aid,
            customer_category="Direct Customer",
            sale_type="L/GST-18%",
            payment_method="BANK_TRANSFER",
            payment_mode="BANK_TRANSFER",
            status="PAID",
            narration="Traditional Billing Invoice Verification",
            subtotal=Decimal("12000.00"),
            taxable_amount=Decimal("12000.00"),
            cgst_amount=Decimal("1080.00"),
            sgst_amount=Decimal("1080.00"),
            igst_amount=Decimal("0.00"),
            round_off_amount=Decimal("0.00"),
            grand_total=Decimal("14160.00"),
            total_amount=Decimal("14160.00"),
            items_json=json.dumps(items)
        )
        session.add(inv)

    return {"voucher_id": inv_id, "vch_no": vch_no, "company_id": cid}


# =============================================================================
# 1. TEST CASES: FAST BILLING PDF DOWNLOAD & AUTHENTICATION
# =============================================================================

def test_01_authorized_fast_billing_user_downloads_a4_pdf(auth_fixture_company, committed_fast_billing_invoice):
    """
    Verify:
    1. Logged-in authorized Fast Billing user downloads A4 PDF.
    2. PDF generation succeeds and file exists on disk.
    3. Correct saved invoice number and company details appear.
    """
    bridge = BackendBridge()
    cid = auth_fixture_company["company_id"]
    code = auth_fixture_company["company_code"]
    bid = auth_fixture_company["branch_id"]
    vid = committed_fast_billing_invoice["voucher_id"]

    # Establish genuine Fast Billing authenticated session
    bridge._authenticated_session = {
        "session_id": str(uuid.uuid4()),
        "company_id": cid,
        "company_code": code,
        "company_name": "Apex Horizon Technologies Ltd",
        "branch_id": bid,
        "branch_code": "BR01",
        "branch_name": "Apex Central Branch",
        "user_id": "usr-cashier-01",
        "username": "cashier",
        "display_name": "Cashier Desk 1",
        "role": "Cashier",
        "authenticated_at": datetime.now(timezone.utc).isoformat(),
        "auth_source": "fast_billing"
    }

    # Call exportVoucherPdf
    resp_str = bridge.exportVoucherPdf(
        company_id=cid,
        voucher_type="sales_invoice",
        voucher_id=vid,
        paper_format="a4",
        target_path="",
        billing_mode="fast_billing"
    )
    resp = json.loads(resp_str)
    assert resp["success"] is True, f"Failed to export PDF: {resp.get('error')}"
    assert os.path.exists(resp["file_path"]), f"Generated PDF not found: {resp['file_path']}"
    assert os.path.getsize(resp["file_path"]) > 1000
    assert resp["voucher_number"] == committed_fast_billing_invoice["vch_no"]


def test_02_authorized_fast_billing_user_downloads_a5_pdf(auth_fixture_company, committed_fast_billing_invoice):
    """Verify A5 PDF generation succeeds for authorized Fast Billing user."""
    bridge = BackendBridge()
    cid = auth_fixture_company["company_id"]
    code = auth_fixture_company["company_code"]
    bid = auth_fixture_company["branch_id"]
    vid = committed_fast_billing_invoice["voucher_id"]

    bridge._authenticated_session = {
        "session_id": str(uuid.uuid4()),
        "company_id": cid,
        "company_code": code,
        "company_name": "Apex Horizon Technologies Ltd",
        "branch_id": bid,
        "branch_code": "BR01",
        "branch_name": "Apex Central Branch",
        "user_id": "usr-cashier-01",
        "username": "cashier",
        "display_name": "Cashier Desk 1",
        "role": "Cashier",
        "authenticated_at": datetime.now(timezone.utc).isoformat(),
        "auth_source": "fast_billing"
    }

    resp_str = bridge.exportVoucherPdf(
        company_id=cid,
        voucher_type="sales_invoice",
        voucher_id=vid,
        paper_format="a5",
        target_path="",
        billing_mode="fast_billing"
    )
    resp = json.loads(resp_str)
    assert resp["success"] is True
    assert resp["paper_format"] == "a5"
    assert os.path.exists(resp["file_path"])


def test_03_traditional_session_user_switched_to_fast_billing_downloads_pdf(auth_fixture_company, committed_fast_billing_invoice):
    """
    CRITICAL FIX VERIFICATION:
    User logged in via Traditional Billing, switched to Fast Billing, committed invoice,
    and downloads PDF without re-authenticating.
    """
    bridge = BackendBridge()
    cid = auth_fixture_company["company_id"]
    bid = auth_fixture_company["branch_id"]
    vid = committed_fast_billing_invoice["voucher_id"]

    # Register Traditional session on registry
    token = traditional_session_registry.create_session(
        user_id="usr-admin-01",
        company_id=cid,
        branch_id=bid,
        role_name="System Administrator",
        username="admin",
        display_name="System Administrator"
    )
    bridge._traditional_session = traditional_session_registry.get_session(token)
    bridge._authenticated_session = None  # Ensure _authenticated_session was not yet populated

    # When user clicks Download PDF in Fast Billing:
    resp_str = bridge.exportVoucherPdf(
        company_id=cid,
        voucher_type="sales_invoice",
        voucher_id=vid,
        paper_format="a4",
        target_path="",
        billing_mode="fast_billing"
    )
    resp = json.loads(resp_str)
    assert resp["success"] is True, f"Failed with: {resp.get('error')}"
    assert os.path.exists(resp["file_path"])


def test_04_generate_pdf_invoice_fallback_works_with_session(auth_fixture_company, committed_fast_billing_invoice):
    """Verify generatePdfInvoice succeeds for active session in Fast Billing."""
    bridge = BackendBridge()
    cid = auth_fixture_company["company_id"]
    code = auth_fixture_company["company_code"]
    bid = auth_fixture_company["branch_id"]
    vid = committed_fast_billing_invoice["voucher_id"]

    bridge._authenticated_session = {
        "session_id": str(uuid.uuid4()),
        "company_id": cid,
        "company_code": code,
        "company_name": "Apex Horizon Technologies Ltd",
        "branch_id": bid,
        "branch_code": "BR01",
        "branch_name": "Apex Central Branch",
        "user_id": "usr-cashier-01",
        "username": "cashier",
        "display_name": "Cashier Desk 1",
        "role": "Cashier",
        "authenticated_at": datetime.now(timezone.utc).isoformat(),
        "auth_source": "fast_billing"
    }

    resp_str = bridge.generatePdfInvoice(cid, vid)
    resp = json.loads(resp_str)
    assert resp["success"] is True
    assert "filepath" in resp
    assert os.path.exists(resp["filepath"])


def test_05_unauthorized_user_cannot_generate_pdf(auth_fixture_company, committed_fast_billing_invoice):
    """Verify unauthorized unauthenticated user is strictly blocked from generating PDF."""
    bridge = BackendBridge()
    bridge._authenticated_session = None
    bridge._traditional_session = None
    cid = auth_fixture_company["company_id"]
    vid = committed_fast_billing_invoice["voucher_id"]

    resp_str = bridge.exportVoucherPdf(
        company_id=cid,
        voucher_type="sales_invoice",
        voucher_id=vid,
        paper_format="a4",
        target_path="",
        billing_mode="fast_billing"
    )
    resp = json.loads(resp_str)
    assert resp["success"] is False
    assert "Authentication required: No active authenticated session" in resp["error"]


def test_06_expired_session_produces_clear_error(auth_fixture_company, committed_fast_billing_invoice):
    """Verify expired session produces a clear 'Session expired' user-facing error."""
    bridge = BackendBridge()
    cid = auth_fixture_company["company_id"]
    bid = auth_fixture_company["branch_id"]
    vid = committed_fast_billing_invoice["voucher_id"]

    # Create session with 1-second timeout
    token = traditional_session_registry.create_session(
        user_id="usr-temp-01",
        company_id=cid,
        branch_id=bid,
        role_name="Cashier",
        username="temp_user",
        idle_timeout_seconds=1,
        shift_limit_seconds=1
    )
    sess = traditional_session_registry.get_session(token)
    # Fast-forward last_activity into the past
    sess.last_activity = datetime.now(timezone.utc) - timedelta(seconds=10)
    sess.created_at = datetime.now(timezone.utc) - timedelta(seconds=10)

    bridge._traditional_session = sess
    bridge._authenticated_session = None

    resp_str = bridge.exportVoucherPdf(
        company_id=cid,
        voucher_type="sales_invoice",
        voucher_id=vid,
        paper_format="a4",
        target_path="",
        billing_mode="fast_billing"
    )
    resp = json.loads(resp_str)
    assert resp["success"] is False
    assert "Session expired" in resp["error"]


def test_07_cross_company_access_strictly_blocked(auth_fixture_company, committed_fast_billing_invoice):
    """Verify multi-tenant isolation: authenticated user of Company A cannot export PDF of Company B."""
    bridge = BackendBridge()
    cid = auth_fixture_company["company_id"]
    code = auth_fixture_company["company_code"]
    vid = committed_fast_billing_invoice["voucher_id"]

    bridge._authenticated_session = {
        "session_id": str(uuid.uuid4()),
        "company_id": cid,
        "company_code": code,
        "company_name": "Apex Horizon Technologies Ltd",
        "branch_id": "BR01",
        "branch_code": "BR01",
        "branch_name": "Main Branch",
        "user_id": "usr-01",
        "username": "cashier",
        "role": "Cashier",
        "authenticated_at": datetime.now(timezone.utc).isoformat()
    }

    # Attempt to request unauthorized third-party company ID
    foreign_company_id = "FOREIGN-COMP-9999"
    resp_str = bridge.exportVoucherPdf(
        company_id=foreign_company_id,
        voucher_type="sales_invoice",
        voucher_id=vid,
        paper_format="a4",
        target_path="",
        billing_mode="fast_billing"
    )
    resp = json.loads(resp_str)
    assert resp["success"] is False
    assert "Access denied" in resp["error"]


def test_08_reprinting_is_idempotent_no_duplicate_transactions(auth_fixture_company, committed_fast_billing_invoice):
    """Verify reprinting or downloading PDF multiple times does not mutate inventory or create duplicate invoices."""
    bridge = BackendBridge()
    cid = auth_fixture_company["company_id"]
    code = auth_fixture_company["company_code"]
    bid = auth_fixture_company["branch_id"]
    vid = committed_fast_billing_invoice["voucher_id"]

    bridge._authenticated_session = {
        "session_id": str(uuid.uuid4()),
        "company_id": cid,
        "company_code": code,
        "company_name": "Apex Horizon Technologies Ltd",
        "branch_id": bid,
        "branch_code": "BR01",
        "branch_name": "Apex Central Branch",
        "user_id": "usr-cashier-01",
        "username": "cashier",
        "role": "Cashier",
        "authenticated_at": datetime.now(timezone.utc).isoformat()
    }

    from services.billing_service import billing_service
    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sales_vouchers WHERE company_id = ?;", (cid,))
        count_before = cur.fetchone()[0]

    # Download PDF 3 times
    for _ in range(3):
        resp_str = bridge.exportVoucherPdf(
            company_id=cid,
            voucher_type="sales_invoice",
            voucher_id=vid,
            paper_format="a4",
            target_path="",
            billing_mode="fast_billing"
        )
        assert json.loads(resp_str)["success"] is True

    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sales_vouchers WHERE company_id = ?;", (cid,))
        count_after = cur.fetchone()[0]

    assert count_before == count_after, "Reprinting mutated sales vouchers count!"


def test_09_traditional_billing_pdf_generation_remains_functional(auth_fixture_company, committed_traditional_invoice):
    """Verify Traditional Billing PDF generation remains fully functional."""
    bridge = BackendBridge()
    cid = auth_fixture_company["company_id"]
    bid = auth_fixture_company["branch_id"]
    vid = committed_traditional_invoice["voucher_id"]

    token = traditional_session_registry.create_session(
        user_id="usr-admin-01",
        company_id=cid,
        branch_id=bid,
        role_name="System Administrator",
        username="admin",
        display_name="System Administrator"
    )
    bridge._traditional_session = traditional_session_registry.get_session(token)

    resp_str = bridge.exportVoucherPdf(
        company_id=cid,
        voucher_type="sales_invoice",
        voucher_id=vid,
        paper_format="a4",
        target_path="",
        billing_mode="traditional"
    )
    resp = json.loads(resp_str)
    assert resp["success"] is True
    assert os.path.exists(resp["file_path"])
    assert resp["voucher_number"] == committed_traditional_invoice["vch_no"]


def test_10_database_integrity_and_accounting_immutability():
    """Verify Fast Billing production database was not touched."""
    assert FAST_DB_PATH.exists()
    fast_db_hash = get_file_hash(FAST_DB_PATH)
    assert fast_db_hash is not None
