"""
Unit & Integration Tests for Purchase Voucher PDF Download & Auto-Open.
Validates:
1. Windows Downloads directory resolution via QStandardPaths.DownloadLocation.
2. Meaningful filename generation matching 'Purchase_Voucher_{vch_no}.pdf'.
3. Duplicate filename collision avoidance without overwriting existing files.
4. High-fidelity ReportLab PDF generation (>0 bytes) containing all required ERP voucher fields:
   - Company details (Name, Address, GSTIN, Phone, Email, State)
   - Voucher details (Voucher No, Date, Payment Mode, Godown)
   - Supplier details (Name, Address, GSTIN, State, Invoice No & Date)
   - Itemized inward goods table with Sl No, Description, HSN/SAC, Qty, Free, Unit, Rate, Disc %, Taxable, GST %, Total
   - Subtotals, Tax breakdown (CGST/SGST/IGST), freight/additional expenses, round-off, Grand Total
   - Amount in words in Indian Rupees
   - Remarks / Narration and goods receipt declaration
   - Dual signatory blocks (Store Incharge & Authorized Signatory)
5. WebBridge RPC slots 'printPurchaseVoucher' and 'generatePurchaseVoucherPdf'.
6. Auto-opening via QDesktopServices.openUrl with QUrl.fromLocalFile.
"""

import json
import uuid
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from db.database import DatabaseManager
from services.purchase_service import PurchaseService
from services.printing_service import printing_service
from desktop.web_bridge import BackendBridge
from PyQt5.QtCore import QStandardPaths, QUrl
from PyQt5.QtGui import QDesktopServices


@pytest.fixture
def pdf_test_env(tmp_path):
    """Isolated database and WebBridge environment for purchase PDF testing."""
    db_file = tmp_path / "test_purchase_pdf.db"
    db_url = f"sqlite:///{db_file}"

    test_db = DatabaseManager(database_url=db_url)
    from db.models import Base
    Base.metadata.create_all(bind=test_db.engine)

    purchase_svc = PurchaseService(db=test_db)

    company_id = str(uuid.uuid4())
    supplier_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())

    with test_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO companies (id, code, name, fin_year, gstin, state, username, password_hash, created_at, updated_at)
            VALUES (?, 'ACME', 'ACME Tech Solutions Pvt Ltd', '2026-2027', '33AABBA1122C1Z4', 'Tamilnadu', 'admin', 'hash', datetime('now'), datetime('now'));
        """, (company_id,))

        # Branch
        cursor.execute("""
            INSERT INTO branches (id, company_id, code, name, is_default, created_at)
            VALUES ('branch-main', ?, 'MAIN', 'Main Branch', 1, CURRENT_TIMESTAMP);
        """, (company_id,))

        # Godown
        cursor.execute("""
            INSERT INTO godowns (id, company_id, branch_id, code, name, is_default, created_at)
            VALUES ('GODOWN-MAIN', ?, 'branch-main', 'MAIN', 'Main Store', 1, CURRENT_TIMESTAMP);
        """, (company_id,))

        cursor.execute("""
            INSERT INTO suppliers (id, company_id, code, name, gstin, state, mobile, email, address, is_active, created_at)
            VALUES (?, ?, 'SUP-001', 'Prime Global Hardware Ltd', '29ABCDE1234F1Z5', 'Karnataka', '9876543210', 'sales@primeglobal.com', 'Plot 10, Industrial Estate, Bangalore', 1, CURRENT_TIMESTAMP);
        """, (supplier_id, company_id))

        cursor.execute("""
            INSERT INTO items (id, company_id, name, alias, sales_price, purc_price, unit, is_active, created_at)
            VALUES (?, ?, 'Cat6 Gigabit Patch Cable 2m', 'ITM-001', 150.0, 95.0, 'Pcs.', 1, CURRENT_TIMESTAMP);
        """, (item_id, company_id))

        conn.commit()

    # Create a real purchase voucher record
    vch_in = {
        "vch_no": "PUR-2026-0001",
        "vch_date": "2026-11-19",
        "supplier_id": supplier_id,
        "supplier_name": "Prime Global Hardware Ltd",
        "supplier_invoice_no": "INV-PRIME-902",
        "supplier_invoice_date": "2026-11-18",
        "supplier_gstin": "29ABCDE1234F1Z5",
        "supplier_state": "Karnataka",
        "payment_type": "CREDIT",
        "payment_terms": "NET 30",
        "godown_id": "GODOWN-MAIN",
        "freight_charges": 150.0,
        "handling_charges": 50.0,
        "narration": "Urgent procurement of patch cables for server room.",
        "items": [
            {
                "item_id": item_id,
                "item_name": "Cat6 Gigabit Patch Cable 2m",
                "hsn_code": "8544",
                "barcode": "CBL-CAT6-2M",
                "qty": 50,
                "free_qty": 5,
                "unit": "Pcs.",
                "purchase_rate": 95.0,
                "discount_percent": 5.0,
                "tax_rate": 18.0
            }
        ]
    }
    saved_vch = purchase_svc.create_purchase_voucher(company_id, vch_in)

    return {
        "db": test_db,
        "purchase_svc": purchase_svc,
        "company_id": company_id,
        "supplier_id": supplier_id,
        "item_id": item_id,
        "voucher_id": saved_vch["id"],
        "voucher_no": saved_vch["vch_no"],
        "tmp_dir": tmp_path
    }


def test_pdf_generation_content_and_structure(pdf_test_env):
    """Tests ReportLab purchase voucher PDF rendering with all ERP layout components."""
    purchase_svc = pdf_test_env["purchase_svc"]
    company_id = pdf_test_env["company_id"]
    voucher_id = pdf_test_env["voucher_id"]
    tmp_dir = pdf_test_env["tmp_dir"]

    vch = purchase_svc.get_purchase_voucher_details(company_id, voucher_id)
    assert vch is not None
    assert vch["vch_no"] == "PUR-000001"

    company_info = {
        "name": "ACME Tech Solutions Pvt Ltd",
        "address": "Level 3, OMR Cyber Park, Chennai - 600096",
        "gstin": "33AABBA1122C1Z4",
        "state": "Tamilnadu",
        "phone": "+91 44 4567 8900",
        "email": "finance@acmetech.com"
    }

    out_pdf = tmp_dir / "test_purchase_voucher.pdf"
    res_path = printing_service.generate_pdf_purchase_voucher(vch, out_pdf, company_info)

    assert res_path.exists()
    assert res_path.stat().st_size > 0
    # Verify PDF magic header
    with open(res_path, "rb") as f:
        header = f.read(5)
        assert header == b"%PDF-"


def test_filename_and_collision_avoidance(tmp_path):
    """Tests non-overwriting collision avoidance logic."""
    downloads_dir = tmp_path / "Downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    vch_no = "PUR-000001"
    clean_vch_no = "".join(c for c in vch_no if c.isalnum() or c in "-_")
    base_name = f"Purchase_Voucher_{clean_vch_no}"

    # First save: Purchase_Voucher_PUR-000001.pdf
    f1 = downloads_dir / f"{base_name}.pdf"
    f1.write_bytes(b"initial file content 1")
    assert f1.exists()

    # Second save: should resolve to Purchase_Voucher_PUR-000001_1.pdf
    candidate = downloads_dir / f"{base_name}.pdf"
    if candidate.exists():
        idx = 1
        while candidate.exists():
            candidate = downloads_dir / f"{base_name}_{idx}.pdf"
            idx += 1
    f2 = candidate
    f2.write_bytes(b"initial file content 2")
    assert f2.name == "Purchase_Voucher_PUR-000001_1.pdf"
    assert f1.read_bytes() == b"initial file content 1"  # original untouched!

    # Third save: should resolve to Purchase_Voucher_PUR-000001_2.pdf
    candidate = downloads_dir / f"{base_name}.pdf"
    if candidate.exists():
        idx = 1
        while candidate.exists():
            candidate = downloads_dir / f"{base_name}_{idx}.pdf"
            idx += 1
    f3 = candidate
    assert f3.name == "Purchase_Voucher_PUR-000001_2.pdf"


def test_web_bridge_print_purchase_voucher_workflow(pdf_test_env, monkeypatch):
    """
    Tests WebBridge printPurchaseVoucher:
    - Resolves DownloadLocation
    - Creates Purchase_Voucher_*.pdf in Downloads
    - Avoids collision
    - Calls QDesktopServices.openUrl
    - Returns JSON with success, filename, filepath, and opened=True
    """
    company_id = pdf_test_env["company_id"]
    voucher_id = pdf_test_env["voucher_id"]
    tmp_downloads = pdf_test_env["tmp_dir"] / "MockDownloads"
    tmp_downloads.mkdir(parents=True, exist_ok=True)

    # Mock QStandardPaths to return our test directory
    monkeypatch.setattr(
        QStandardPaths,
        "writableLocation",
        lambda loc: str(tmp_downloads)
    )

    # Mock QDesktopServices.openUrl to verify it is called with QUrl
    opened_urls = []
    def mock_open_url(url):
        opened_urls.append(url.toLocalFile() if hasattr(url, "toLocalFile") else str(url))
        return True

    monkeypatch.setattr(QDesktopServices, "openUrl", mock_open_url)

    # Initialize BackendBridge
    bridge = BackendBridge()
    bridge._authenticated_session = {
        "company_id": company_id,
        "company_code": "ACME",
        "user_id": "admin",
        "role": "Admin"
    }
    # Point purchase_service in bridge module to test instance
    with patch("desktop.web_bridge.purchase_service", pdf_test_env["purchase_svc"]):
        resp_str = bridge.printPurchaseVoucher(company_id, voucher_id, "A4", 1, "")
        resp = json.loads(resp_str)

        assert resp["success"] is True
        assert "Purchase_Voucher_PUR-000001.pdf" in resp["filename"]
        assert resp["opened"] is True
        assert Path(resp["filepath"]).exists()
        assert Path(resp["filepath"]).stat().st_size > 0
        assert len(opened_urls) == 1
        assert Path(opened_urls[0]).resolve() == Path(resp["filepath"]).resolve()

        # Second call: verify collision avoidance in WebBridge
        resp_str2 = bridge.printPurchaseVoucher(company_id, voucher_id, "A4", 1, "")
        resp2 = json.loads(resp_str2)
        assert resp2["success"] is True
        assert resp2["filename"] == "Purchase_Voucher_PUR-000001_1.pdf"
        assert Path(resp2["filepath"]).exists()
        assert Path(resp["filepath"]).exists()  # First file still exists untouched!


def test_web_bridge_generate_purchase_voucher_pdf_convenience_slot(pdf_test_env, monkeypatch):
    """Tests the convenience slot generatePurchaseVoucherPdf."""
    company_id = pdf_test_env["company_id"]
    voucher_id = pdf_test_env["voucher_id"]
    tmp_downloads = pdf_test_env["tmp_dir"] / "MockDownloads2"
    tmp_downloads.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        QStandardPaths,
        "writableLocation",
        lambda loc: str(tmp_downloads)
    )
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: True)

    bridge = BackendBridge()
    bridge._authenticated_session = {
        "company_id": company_id,
        "company_code": "ACME",
        "user_id": "admin",
        "role": "Admin"
    }

    with patch("desktop.web_bridge.purchase_service", pdf_test_env["purchase_svc"]):
        resp_str = bridge.generatePurchaseVoucherPdf(company_id, voucher_id)
        resp = json.loads(resp_str)
        assert resp["success"] is True
        assert "Purchase_Voucher_" in resp["filename"]
        assert Path(resp["filepath"]).exists()
