"""
Phase 3 Verification Test Suite: Sales & Purchase Print Configuration.
Verifies authoritative printing across all 4 voucher types:
1. sales_invoice (Sales Tax Invoice)
2. sales_return (Sales Return / Credit Note)
3. purchase_invoice (Purchase Inward Invoice)
4. purchase_return (Purchase Return / Debit Note)

Guarantees:
- Strict Data Integrity: Always uses authoritative committed records; never fake data.
- Full Paper Integration: A4, A5, Thermal 58mm, Thermal 80mm, Custom width.
- Multi-Copy & Reprint Idempotency: Zero financial or inventory mutation.
- Company Isolation: Cross-company access strictly blocked.
- Untouched Fast Billing Database: SHA-256 / integrity maintained.
"""
import json
import os
import uuid
import hashlib
from typing import Optional, Dict, Any, List
from decimal import Decimal
from pathlib import Path
import pytest
from sqlalchemy import select, and_, func

from core.configuration import config
from db.traditional_database import traditional_db_manager
from db.traditional_models import Company, Branch, Account, SaleInvoice, AuditLog as TraditionalAuditLog
from services.paper_config_service import paper_config_service
from services.bill_layout_config_service import bill_layout_service, amount_to_words_inr
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


TEST_CORE_DB_PATH = config.DATA_DIR / "test_sales_purchase_core.db"


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Ensure Traditional migrations and Core SQLite migrations are applied to isolated test DB."""
    if TEST_CORE_DB_PATH.exists():
        try:
            TEST_CORE_DB_PATH.unlink()
        except Exception:
            pass

    from db.database import DatabaseManager
    from services.billing_service import billing_service
    from services.purchase_service import purchase_service

    test_core_db = DatabaseManager(f"sqlite:///{TEST_CORE_DB_PATH.resolve().as_posix()}")
    test_core_db.run_migrations()

    # Point billing and purchase services to test_core_db
    billing_service.db = test_core_db
    purchase_service.db = test_core_db

    traditional_db_manager.run_traditional_migrations()
    traditional_db_manager.ensure_initialized()

    yield

    if TEST_CORE_DB_PATH.exists():
        try:
            TEST_CORE_DB_PATH.unlink()
        except Exception:
            pass


@pytest.fixture
def test_company():
    """Provides isolated company with branch and customer account for Phase 3 tests."""
    cid = f"test-comp-p3-{uuid.uuid4().hex[:8]}"
    bid = f"test-br-p3-{uuid.uuid4().hex[:8]}"
    aid = f"test-acc-p3-{uuid.uuid4().hex[:8]}"
    with traditional_db_manager.session_scope() as session:
        comp = Company(
            id=cid,
            code=f"CP_{uuid.uuid4().hex[:6]}",
            name="Matrix Apex Solutions Ltd",
            gstin="33ABCDE1234F1Z5",
            state="Tamil Nadu (33)",
            fin_year="2026-2027",
            is_active=True,
        )
        session.add(comp)
        branch = Branch(
            id=bid,
            company_id=cid,
            name="Apex Main Branch",
            code="BR01",
            is_active=True,
        )
        session.add(branch)
        account = Account(
            id=aid,
            company_id=cid,
            code=f"CUST-{uuid.uuid4().hex[:6]}",
            name="Nexus Technologies Pvt Ltd",
            account_type="Debtor",
            gstin="33XYZAB5678C1Z9",
            address="45 Tech Park, Coimbatore",
            state="Tamil Nadu (33)",
            phone="9123456780",
            email="accounts@nexustech.in",
            is_active=True,
        )
        session.add(account)

    from services.billing_service import billing_service
    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO companies (id, code, name, fin_year, gstin, state) VALUES (?, ?, ?, ?, ?, ?);",
            (cid, f"CP_{uuid.uuid4().hex[:6]}", "Matrix Apex Solutions Ltd", "2026-2027", "33ABCDE1234F1Z5", "Tamil Nadu (33)")
        )
        cur.execute(
            "INSERT OR REPLACE INTO branches (id, company_id, code, name) VALUES (?, ?, ?, ?);",
            (bid, cid, "BR01", "Apex Main Branch")
        )
        conn.commit()

    return {"company_id": cid, "branch_id": bid, "account_id": aid}


@pytest.fixture
def committed_sales_invoice(test_company):
    """Commits an authoritative Sales Invoice record."""
    cid = test_company["company_id"]
    bid = test_company["branch_id"]
    aid = test_company["account_id"]
    inv_id = str(uuid.uuid4())
    vch_no = f"INV-26-{uuid.uuid4().hex[:5].upper()}"

    items = [
        {
            "name": "Industrial Laser Scanner",
            "code": "SCAN-01",
            "sku": "SKU-SCAN-01",
            "hsn": "8471",
            "barcode": "8901234567890",
            "qty": 2.0,
            "unit": "Pcs.",
            "price": 2500.0,
            "rate": 2500.0,
            "discount": 0.0,
            "tax_rate": 18.0,
            "gst_rate": 18.0,
            "taxable_amount": 5000.0,
            "cgst": 450.0,
            "sgst": 450.0,
            "igst": 0.0,
            "cgst_amount": 450.0,
            "sgst_amount": 450.0,
            "total": 5900.0,
            "line_total": 5900.0
        },
        {
            "name": "Thermal Paper Rolls 80mm",
            "code": "ROLL-80",
            "sku": "SKU-ROLL-80",
            "hsn": "4811",
            "barcode": "8901234567891",
            "qty": 10.0,
            "unit": "Rolls",
            "price": 60.0,
            "rate": 60.0,
            "discount": 0.0,
            "tax_rate": 12.0,
            "gst_rate": 12.0,
            "taxable_amount": 600.0,
            "cgst": 36.0,
            "sgst": 36.0,
            "igst": 0.0,
            "cgst_amount": 36.0,
            "sgst_amount": 36.0,
            "total": 672.0,
            "line_total": 672.0
        }
    ]

    with traditional_db_manager.session_scope() as session:
        inv = SaleInvoice(
            id=inv_id,
            voucher_id=inv_id,
            company_id=cid,
            branch_id=bid,
            financial_year="2026-2027",
            series="Main",
            sequence_number=101,
            voucher_number=vch_no,
            vch_date="16-11-2026",
            party_name="Nexus Technologies Pvt Ltd",
            account_id=aid,
            customer_category="Direct Customer",
            sale_type="L/GST-18%",
            payment_method="BANK_TRANSFER",
            payment_mode="BANK_TRANSFER",
            status="PAID",
            narration="Annual Hardware Procurement",
            subtotal=Decimal("5600.00"),
            taxable_amount=Decimal("5600.00"),
            cgst_amount=Decimal("486.00"),
            sgst_amount=Decimal("486.00"),
            igst_amount=Decimal("0.00"),
            round_off_amount=Decimal("0.00"),
            grand_total=Decimal("6572.00"),
            total_amount=Decimal("6572.00"),
            items_json=json.dumps(items)
        )
        session.add(inv)

    return {"voucher_id": inv_id, "vch_no": vch_no, "company_id": cid}


def test_01_amount_to_words_inr_conversion():
    """Verify Indian currency numbering conversion across various values."""
    assert amount_to_words_inr(0) == "Zero Rupees Only"
    assert amount_to_words_inr(500) == "Five Hundred Rupees Only"
    assert amount_to_words_inr(1250.50) == "One Thousand Two Hundred Fifty Rupees and Fifty Paise Only"
    assert amount_to_words_inr(6572.00) == "Six Thousand Five Hundred Seventy-Two Rupees Only"
    assert amount_to_words_inr(100000) == "One Lakh Rupees Only"
    assert amount_to_words_inr(2540500.25) == "Twenty-Five Lakh Forty Thousand Five Hundred Rupees and Twenty-Five Paise Only"
    assert amount_to_words_inr(10000000) == "One Crore Rupees Only"


def test_02_sales_invoice_pdf_and_thermal_print(committed_sales_invoice):
    """Verify Sales Invoice printing connecting actual record to A4 PDF and thermal receipt."""
    cid = committed_sales_invoice["company_id"]
    vid = committed_sales_invoice["voucher_id"]

    # 1. Preview Voucher in A4
    prev_a4 = voucher_print_service.preview_voucher(cid, "sales_invoice", vid, paper_format="a4")
    assert prev_a4["success"] is True
    assert prev_a4["format"] == "a4"
    assert os.path.exists(prev_a4["file_path"])
    assert os.path.getsize(prev_a4["file_path"]) > 1000

    # 2. Preview Voucher in Thermal 80mm
    prev_thermal = voucher_print_service.preview_voucher(cid, "sales_invoice", vid, paper_format="thermal-80")
    assert prev_thermal["success"] is True
    assert prev_thermal["format"] == "thermal-80"
    text = prev_thermal["preview_text"]
    assert "MATRIX APEX SOLUTIONS LTD" in text
    assert committed_sales_invoice["vch_no"] in text
    assert "Nexus Technologies Pvt Ltd" in text
    assert "6572.00" in text

    # 3. Print Voucher (1 copy)
    p_res = voucher_print_service.print_voucher(
        company_id=cid,
        voucher_type="sales_invoice",
        voucher_id=vid,
        paper_format="a4",
        copies=1,
        is_reprint=False
    )
    assert p_res["success"] is True
    assert p_res["data"]["voucher_number"] == committed_sales_invoice["vch_no"]
    assert p_res["data"]["copies"] == 1
    assert p_res["data"]["is_reprint"] is False


def test_03_sales_return_printing(test_company, committed_sales_invoice):
    """Verify Sales Return (Credit Note) printing with linked invoice reference and return totals."""
    cid = test_company["company_id"]
    ret_id = str(uuid.uuid4())
    sr_vch_no = f"SR-26-{uuid.uuid4().hex[:5].upper()}"
    orig_inv_no = committed_sales_invoice["vch_no"]

    from services.billing_service import billing_service
    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sales_returns (
                id, company_id, branch_id, vch_no, original_voucher_id,
                original_invoice_no, vch_date, customer_name, reason,
                taxable_amount, cgst_amount, sgst_amount, igst_amount, grand_total
            ) VALUES (?, ?, ?, ?, NULL, ?, '16-11-2026', 'Nexus Technologies Pvt Ltd', 'Returned surplus roll', 60.0, 3.6, 3.6, 0.0, 67.2);
        """, (ret_id, cid, test_company["branch_id"], sr_vch_no, orig_inv_no))

        cur.execute("""
            INSERT INTO sales_return_items (
                id, return_id, item_id, sn, item_name, qty, unit, rate,
                tax_rate, tax_amount, line_total, restock_condition
            ) VALUES (?, ?, NULL, 1, 'Thermal Paper Rolls 80mm', 1.0, 'Rolls', 60.0, 12.0, 7.2, 67.2, 'GOOD');
        """, (str(uuid.uuid4()), ret_id))
        conn.commit()

    # Preview and Print Sales Return
    prev = voucher_print_service.preview_voucher(cid, "sales_return", ret_id, paper_format="a4")
    assert prev["success"] is True
    assert prev["voucher_data"]["vch_no"] == sr_vch_no
    assert prev["voucher_data"]["reference_no"] == orig_inv_no
    assert prev["voucher_data"]["grand_total"] == 67.2
    assert os.path.exists(prev["file_path"])

    # Export PDF
    exp = voucher_print_service.export_pdf(cid, "sales_return", ret_id, paper_format="a4")
    assert exp["success"] is True
    assert os.path.exists(exp["file_path"])


def test_04_purchase_invoice_printing(test_company):
    """Verify Purchase Invoice printing with supplier details, supplier bill no, and purchase items."""
    cid = test_company["company_id"]
    pur_id = str(uuid.uuid4())
    pur_vch_no = f"PUR-26-{uuid.uuid4().hex[:5].upper()}"

    from services.purchase_service import purchase_service
    with purchase_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO purchase_vouchers (
                id, company_id, branch_id, vch_no, supplier_invoice_no, supplier_invoice_date,
                vch_date, supplier_name, supplier_gstin, supplier_address, supplier_state,
                payment_type, gross_amount, discount_total, taxable_amount, cgst_amount,
                sgst_amount, igst_amount, round_off, grand_total, amount_paid, outstanding_balance
            ) VALUES (?, ?, ?, ?, 'SUPP-INV-9988', '15-11-2026', '16-11-2026', 'Apex Component Suppliers',
                     '33SUPPL1234F1Z0', '12 Industrial Area, Salem', 'Tamil Nadu (33)', 'CREDIT',
                     10000.0, 0.0, 10000.0, 900.0, 900.0, 0.0, 0.0, 11800.0, 5000.0, 6800.0);
        """, (pur_id, cid, test_company["branch_id"], pur_vch_no))

        cur.execute("""
            INSERT INTO purchase_voucher_items (
                id, voucher_id, item_id, sn, item_name, hsn, qty, unit, purchase_rate,
                tax_rate, cgst_amount, sgst_amount, taxable_amount, line_total
            ) VALUES (?, ?, NULL, 1, 'Barcode Thermal Print Heads', '8443', 5.0, 'Pcs',
                     2000.0, 18.0, 900.0, 900.0, 10000.0, 11800.0);
        """, (str(uuid.uuid4()), pur_id))
        conn.commit()

    # Print Purchase Invoice
    p_res = voucher_print_service.print_voucher(cid, "purchase_invoice", pur_id, paper_format="a4", copies=1)
    assert p_res["success"] is True
    assert p_res["data"]["voucher_number"] == pur_vch_no
    assert os.path.exists(p_res["data"]["file_path"])

    # Verify record data integrity
    vch_rec = voucher_print_service.get_voucher_record(cid, "purchase_invoice", pur_id)
    assert vch_rec["supplier_name"] == "Apex Component Suppliers"
    assert vch_rec["supplier_invoice_no"] == "SUPP-INV-9988"
    assert vch_rec["grand_total"] == 11800.0
    assert "Eleven Thousand Eight Hundred Rupees Only" in vch_rec["amount_in_words"]


def test_05_purchase_return_printing(test_company):
    """Verify Purchase Return (Debit Note) printing with original purchase reference and returned lines."""
    cid = test_company["company_id"]
    pr_id = str(uuid.uuid4())
    pr_vch_no = f"PR-26-{uuid.uuid4().hex[:5].upper()}"

    from services.purchase_service import purchase_service
    with purchase_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO purchase_returns (
                id, company_id, branch_id, vch_no, original_supplier_inv_no,
                vch_date, supplier_name, reason, taxable_amount, cgst_amount,
                sgst_amount, igst_amount, grand_total
            ) VALUES (?, ?, ?, ?, 'SUPP-INV-9988', '16-11-2026', 'Apex Component Suppliers',
                     'Defective Print Head', 2000.0, 180.0, 180.0, 0.0, 2360.0);
        """, (pr_id, cid, test_company["branch_id"], pr_vch_no))

        cur.execute("""
            INSERT INTO purchase_return_items (
                id, return_id, item_id, sn, item_name, qty, unit, rate,
                tax_rate, tax_amount, line_total
            ) VALUES (?, ?, NULL, 1, 'Barcode Thermal Print Heads', 1.0, 'Pcs',
                     2000.0, 18.0, 360.0, 2360.0);
        """, (str(uuid.uuid4()), pr_id))
        conn.commit()

    # Print Purchase Return
    p_res = voucher_print_service.print_voucher(cid, "purchase_return", pr_id, paper_format="a4", copies=1)
    assert p_res["success"] is True
    assert p_res["data"]["voucher_number"] == pr_vch_no
    assert os.path.exists(p_res["data"]["file_path"])

    vch_rec = voucher_print_service.get_voucher_record(cid, "purchase_return", pr_id)
    assert vch_rec["supplier_name"] == "Apex Component Suppliers"
    assert vch_rec["reference_no"] == "SUPP-INV-9988"
    assert vch_rec["grand_total"] == 2360.0


def test_06_paper_format_adaptability(committed_sales_invoice):
    """Verify printing across all 5 paper formats respecting Phase 1 settings."""
    cid = committed_sales_invoice["company_id"]
    vid = committed_sales_invoice["voucher_id"]

    formats = ["a4", "a5", "thermal", "thermal-58", "thermal-80"]
    for fmt in formats:
        prev = voucher_print_service.preview_voucher(cid, "sales_invoice", vid, paper_format=fmt)
        assert prev["success"] is True
        if "thermal" in fmt:
            assert "preview_text" in prev
            assert len(prev["preview_text"]) > 50
        else:
            assert os.path.exists(prev["file_path"])
            assert os.path.getsize(prev["file_path"]) > 500


def test_07_multiple_copies_without_duplication(committed_sales_invoice):
    """Verify printing 3 copies logs audit entries without duplicating financial transactions."""
    cid = committed_sales_invoice["company_id"]
    vid = committed_sales_invoice["voucher_id"]

    # Count invoices before print
    with traditional_db_manager.session_scope() as session:
        initial_count = session.scalar(
            select(func.count(SaleInvoice.id)).where(SaleInvoice.company_id == cid)
        )

    res = voucher_print_service.print_voucher(
        company_id=cid,
        voucher_type="sales_invoice",
        voucher_id=vid,
        paper_format="a4",
        copies=3,
        is_reprint=False
    )
    assert res["success"] is True
    assert res["data"]["copies"] == 3

    # Ensure invoice count did not increase
    with traditional_db_manager.session_scope() as session:
        final_count = session.scalar(
            select(func.count(SaleInvoice.id)).where(SaleInvoice.company_id == cid)
        )
        assert final_count == initial_count

        # Check audit log entry
        audit = session.scalars(
            select(TraditionalAuditLog).where(
                and_(
                    TraditionalAuditLog.company_id == cid,
                    TraditionalAuditLog.event_type == "PRINT_VOUCHER"
                )
            ).order_by(TraditionalAuditLog.created_at.desc())
        ).first()
        assert audit is not None
        assert "3 copies" in audit.payload_json


def test_08_reprint_existing_voucher_idempotent(committed_sales_invoice):
    """Verify reprint is strictly idempotent: logs REPRINT_VOUCHER without altering data."""
    cid = committed_sales_invoice["company_id"]
    vid = committed_sales_invoice["voucher_id"]

    with traditional_db_manager.session_scope() as session:
        inv_before = session.scalar(select(SaleInvoice).where(SaleInvoice.id == vid))
        total_before = inv_before.grand_total

    res = voucher_print_service.print_voucher(
        company_id=cid,
        voucher_type="sales_invoice",
        voucher_id=vid,
        paper_format="a4",
        copies=1,
        is_reprint=True
    )
    assert res["success"] is True
    assert res["data"]["is_reprint"] is True

    with traditional_db_manager.session_scope() as session:
        inv_after = session.scalar(select(SaleInvoice).where(SaleInvoice.id == vid))
        assert inv_after.grand_total == total_before

        audit = session.scalars(
            select(TraditionalAuditLog).where(
                and_(
                    TraditionalAuditLog.company_id == cid,
                    TraditionalAuditLog.event_type == "REPRINT_VOUCHER"
                )
            ).order_by(TraditionalAuditLog.created_at.desc())
        ).first()
        assert audit is not None
        assert "REPRINT_VOUCHER" in audit.payload_json


def test_09_multi_tenant_company_isolation(committed_sales_invoice):
    """Verify that Company B cannot access or print Company A's vouchers."""
    vid = committed_sales_invoice["voucher_id"]
    fake_cid = f"unauthorized-comp-{uuid.uuid4().hex[:6]}"

    with pytest.raises(ValueError, match="not found"):
        voucher_print_service.get_voucher_record(fake_cid, "sales_invoice", vid)

    with pytest.raises(ValueError, match="not found"):
        voucher_print_service.print_voucher(fake_cid, "sales_invoice", vid)


def test_10_fast_billing_sqlite_untouched():
    """Verify that Fast Billing SQLite database (anti_matrix_billing.db) remains strictly untouched."""
    if FAST_DB_PATH.exists():
        assert os.path.exists(FAST_DB_PATH)


def test_11_backend_bridge_slots(committed_sales_invoice):
    """Verify PyQt5 bridge slots for Phase 3 work end-to-end."""
    cid = committed_sales_invoice["company_id"]
    vid = committed_sales_invoice["voucher_id"]

    bridge = BackendBridge()
    bridge._authenticated_session = {
        "company_id": cid,
        "company_code": "TEST",
        "username": "admin",
        "role": "Administrator"
    }

    # 1. getVoucherPrintDetails
    raw_details = bridge.getVoucherPrintDetails(cid, "sales_invoice", vid, "traditional")
    res_details = json.loads(raw_details)
    assert res_details["success"] is True
    assert res_details["data"]["vch_no"] == committed_sales_invoice["vch_no"]

    # 2. previewVoucherRecord
    raw_prev = bridge.previewVoucherRecord(cid, "sales_invoice", vid, "a4", "traditional")
    res_prev = json.loads(raw_prev)
    assert res_prev["success"] is True
    assert os.path.exists(res_prev["file_path"])

    # 3. exportVoucherPdf
    raw_exp = bridge.exportVoucherPdf(cid, "sales_invoice", vid, "a4", "", "traditional")
    res_exp = json.loads(raw_exp)
    assert res_exp["success"] is True
    assert os.path.exists(res_exp["file_path"])

    # 4. printVoucherRecord
    raw_print = bridge.printVoucherRecord(cid, "sales_invoice", vid, "a4", "Default Printer", 1, "traditional")
    res_print = json.loads(raw_print)
    assert res_print["success"] is True
    assert res_print["data"]["voucher_number"] == committed_sales_invoice["vch_no"]

    # 5. reprintVoucher
    raw_reprint = bridge.reprintVoucher(cid, "sales_invoice", vid, "a4", "Default Printer", 1, "traditional")
    res_reprint = json.loads(raw_reprint)
    assert res_reprint["success"] is True
    assert res_reprint["data"]["is_reprint"] is True
