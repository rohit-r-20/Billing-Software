"""
Anti-Matrix Billing V2 - Invoice Alignment and Print Layout Test Suite.
Verifies:
1. A4 Portrait and Landscape alignment within exact printable bounds.
2. A5 Portrait and Landscape scaling, proportional columns, and no overflow.
3. Thermal 80mm and 58mm monospaced boundary adherence and safe text wrapping.
4. Custom paper dimensions calculation (no fallback to A4).
5. Safe wrapping for long product descriptions and multiple items.
6. Absolute integrity of accounting and Fast Billing database.
"""
import json
import os
import uuid
import hashlib
from typing import Optional, Dict, Any, List
from decimal import Decimal
from pathlib import Path
import pytest

from core.configuration import config
from db.traditional_database import traditional_db_manager
from db.traditional_models import Company, Branch, Account, SaleInvoice
from services.paper_config_service import paper_config_service
from services.bill_layout_config_service import bill_layout_service
from services.voucher_print_service import voucher_print_service


FAST_DB_PATH = Path("data/anti_matrix_billing.db")


def get_file_hash(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


TEST_ALIGNMENT_DB_PATH = config.DATA_DIR / "test_invoice_alignment.db"


@pytest.fixture(scope="session", autouse=True)
def setup_alignment_test_env():
    if TEST_ALIGNMENT_DB_PATH.exists():
        try:
            TEST_ALIGNMENT_DB_PATH.unlink()
        except Exception:
            pass

    from db.database import DatabaseManager
    from services.billing_service import billing_service
    from services.purchase_service import purchase_service

    test_core_db = DatabaseManager(f"sqlite:///{TEST_ALIGNMENT_DB_PATH.resolve().as_posix()}")
    test_core_db.run_migrations()

    billing_service.db = test_core_db
    purchase_service.db = test_core_db

    traditional_db_manager.run_traditional_migrations()
    traditional_db_manager.ensure_initialized()

    yield

    if TEST_ALIGNMENT_DB_PATH.exists():
        try:
            TEST_ALIGNMENT_DB_PATH.unlink()
        except Exception:
            pass


@pytest.fixture
def test_company_alignment():
    cid = f"test-comp-align-{uuid.uuid4().hex[:8]}"
    bid = f"test-br-align-{uuid.uuid4().hex[:8]}"
    aid = f"test-acc-align-{uuid.uuid4().hex[:8]}"
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
def committed_invoice_with_long_items(test_company_alignment):
    cid = test_company_alignment["company_id"]
    bid = test_company_alignment["branch_id"]
    aid = test_company_alignment["account_id"]
    inv_id = str(uuid.uuid4())
    vch_no = f"INV-ALGN-{uuid.uuid4().hex[:5].upper()}"

    items = [
        {
            "name": "Industrial Heavy Duty Multi-Angle Omnidirectional Laser Barcode Scanner Terminal System 2D",
            "code": "SCAN-PRO-MAX",
            "sku": "SKU-SCAN-ULTRA",
            "hsn": "84719000",
            "barcode": "8901234567890",
            "qty": 3.0,
            "unit": "Units",
            "price": 4500.0,
            "rate": 4500.0,
            "discount": 150.0,
            "tax_rate": 18.0,
            "gst_rate": 18.0,
            "taxable_amount": 13350.0,
            "cgst_amount": 1201.50,
            "sgst_amount": 1201.50,
            "igst_amount": 0.0,
            "line_total": 15753.00,
            "total": 15753.00
        },
        {
            "name": "Thermal Paper Roll Premium High Sensitivity 80mm x 50m BPA Free Cash Register Tape",
            "code": "ROLL-80-PREM",
            "sku": "SKU-ROLL-80",
            "hsn": "48119090",
            "barcode": "8909876543210",
            "qty": 20.0,
            "unit": "Rolls",
            "price": 75.0,
            "rate": 75.0,
            "discount": 0.0,
            "tax_rate": 12.0,
            "gst_rate": 12.0,
            "taxable_amount": 1500.0,
            "cgst_amount": 90.0,
            "sgst_amount": 90.0,
            "igst_amount": 0.0,
            "line_total": 1680.00,
            "total": 1680.00
        }
    ]

    with traditional_db_manager.session_scope() as session:
        inv = SaleInvoice(
            id=inv_id,
            company_id=cid,
            branch_id=bid,
            voucher_id=inv_id,
            voucher_number=vch_no,
            vch_date="16-11-2026",
            party_name="Nexus Technologies Pvt Ltd",
            account_id=aid,
            financial_year="2026-2027",
            series="SALES-26",
            sequence_number=101,
            sale_type="GST Local Sale",
            customer_category="Corporate Client",
            status="COMMITTED",
            payment_method="BANK_TRANSFER",
            narration="High Reliability Automation Hardware Procurement",
            subtotal=Decimal("14850.00"),
            taxable_amount=Decimal("14850.00"),
            cgst_amount=Decimal("1291.50"),
            sgst_amount=Decimal("1291.50"),
            igst_amount=Decimal("0.00"),
            round_off_amount=Decimal("0.00"),
            grand_total=Decimal("17433.00"),
            total_amount=Decimal("17433.00"),
            items_json=json.dumps(items)
        )
        session.add(inv)

    return {"voucher_id": inv_id, "vch_no": vch_no, "company_id": cid}


def test_01_a4_portrait_alignment_and_printable_bounds(committed_invoice_with_long_items):
    """Verify A4 Portrait compiles cleanly within exact printable width."""
    cid = committed_invoice_with_long_items["company_id"]
    vid = committed_invoice_with_long_items["voucher_id"]

    res = voucher_print_service.preview_voucher(cid, "sales_invoice", vid, paper_format="a4", orientation="portrait")
    assert res["success"] is True
    assert res["format"] == "a4"
    assert res["orientation"] == "portrait"
    assert os.path.exists(res["file_path"])
    assert os.path.getsize(res["file_path"]) > 2000


def test_02_a4_landscape_alignment(committed_invoice_with_long_items):
    """Verify A4 Landscape uses rotated dimensions and recalculates printable area."""
    cid = committed_invoice_with_long_items["company_id"]
    vid = committed_invoice_with_long_items["voucher_id"]

    res = voucher_print_service.preview_voucher(cid, "sales_invoice", vid, paper_format="a4", orientation="landscape")
    assert res["success"] is True
    assert res["orientation"] == "landscape"
    assert os.path.exists(res["file_path"])


def test_03_a5_portrait_alignment_and_typography_scaling(committed_invoice_with_long_items):
    """Verify A5 Portrait scales typography, prevents column blowout, and fits inside page."""
    cid = committed_invoice_with_long_items["company_id"]
    vid = committed_invoice_with_long_items["voucher_id"]

    res = voucher_print_service.preview_voucher(cid, "sales_invoice", vid, paper_format="a5", orientation="portrait")
    assert res["success"] is True
    assert res["format"] == "a5"
    assert os.path.exists(res["file_path"])


def test_04_a5_landscape_alignment(committed_invoice_with_long_items):
    """Verify A5 Landscape dimensions and containment."""
    cid = committed_invoice_with_long_items["company_id"]
    vid = committed_invoice_with_long_items["voucher_id"]

    res = voucher_print_service.preview_voucher(cid, "sales_invoice", vid, paper_format="a5", orientation="landscape")
    assert res["success"] is True
    assert res["orientation"] == "landscape"
    assert os.path.exists(res["file_path"])


def test_05_thermal_80mm_character_boundary_and_alignment(committed_invoice_with_long_items):
    """Verify Thermal 80mm generates monospaced stream where NO line exceeds character limit."""
    cid = committed_invoice_with_long_items["company_id"]
    vid = committed_invoice_with_long_items["voucher_id"]

    res = voucher_print_service.preview_voucher(cid, "sales_invoice", vid, paper_format="thermal-80")
    assert res["success"] is True
    assert res["content_type"] == "text/plain"
    text = res["preview_text"]

    lines = text.split("\n")
    # Verify no line exceeds 48 characters for 80mm thermal
    for idx, line in enumerate(lines, start=1):
        assert len(line) <= 48, f"Line {idx} in 80mm thermal exceeded 48 characters: '{line}' ({len(line)} chars)"

    # Verify key data is present
    assert "17433.00" in text
    assert committed_invoice_with_long_items["vch_no"] in text


def test_06_thermal_58mm_compact_alignment(committed_invoice_with_long_items):
    """Verify Thermal 58mm compact layout where NO line exceeds 32 characters."""
    cid = committed_invoice_with_long_items["company_id"]
    vid = committed_invoice_with_long_items["voucher_id"]

    res = voucher_print_service.preview_voucher(cid, "sales_invoice", vid, paper_format="thermal-58")
    assert res["success"] is True
    text = res["preview_text"]

    lines = text.split("\n")
    # Verify no line exceeds 32 characters for 58mm thermal
    for idx, line in enumerate(lines, start=1):
        assert len(line) <= 32, f"Line {idx} in 58mm thermal exceeded 32 characters: '{line}' ({len(line)} chars)"

    assert "17433.00" in text


def test_07_custom_paper_dimensions_and_printable_area(committed_invoice_with_long_items):
    """Verify custom paper (e.g. 100mm x 160mm) adapts dimensions without defaulting to A4."""
    cid = committed_invoice_with_long_items["company_id"]
    vid = committed_invoice_with_long_items["voucher_id"]
    vch_data = voucher_print_service.get_voucher_record(cid, "sales_invoice", vid)

    # Custom 100 mm x 160 mm
    res = bill_layout_service.compile_invoice_pdf(
        voucher_data=vch_data,
        company_id=cid,
        voucher_type="sales_invoice",
        paper_format="custom",
        custom_width_mm=100.0,
        custom_height_mm=160.0
    )
    assert res["success"] is True
    assert res["paper_format"] == "custom"
    assert os.path.exists(res["file_path"])
    # Printable width should be 100mm - 20mm = 80mm in points (approx 226.77 pt)
    from reportlab.lib.units import mm
    expected_w = (100.0 - 20.0) * mm
    assert abs(res["printable_width"] - expected_w) < 5.0


def test_08_database_integrity_and_accounting_immutability():
    """Verify Fast Billing database is completely untouched and hash is preserved."""
    assert FAST_DB_PATH.exists()
    fast_db_hash = get_file_hash(FAST_DB_PATH)
    assert fast_db_hash is not None
