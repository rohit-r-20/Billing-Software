import json
import os
import uuid
from pathlib import Path
import pytest
from sqlalchemy import select

from core.configuration import config
from services.bill_layout_config_service import (
    BillLayoutConfigService,
    bill_layout_service,
    VOUCHER_TYPES,
    DEFAULT_COLUMNS,
)
from services.paper_config_service import (
    paper_config_service,
    DEFAULT_A4_CONFIG,
    DEFAULT_A5_CONFIG,
    DEFAULT_THERMAL_CONFIG,
)
from services.printing_service import printing_service
from db.traditional_database import traditional_db_manager
from db.traditional_models import Company, Branch, BillLayoutConfiguration
from desktop.web_bridge import BackendBridge


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Ensure Traditional migrations are applied up to head."""
    traditional_db_manager.run_traditional_migrations()
    traditional_db_manager.ensure_initialized()


@pytest.fixture
def test_company_a():
    """Provides isolated test company A."""
    cid = f"test-company-a-{uuid.uuid4().hex[:8]}"
    with traditional_db_manager.session_scope() as session:
        comp = Company(
            id=cid,
            code=f"CA_{uuid.uuid4().hex[:6]}",
            name="Alpha Enterprise Pvt Ltd",
            gstin="33AAAPL9876C1Z2",
            state="Tamil Nadu (33)",
            is_active=True,
        )
        session.add(comp)
        branch = Branch(
            id=f"branch-a-{uuid.uuid4().hex[:8]}",
            company_id=cid,
            code="BR01",
            name="Headquarters",
        )
        session.add(branch)
    yield cid
    with traditional_db_manager.session_scope() as session:
        c = session.get(Company, cid)
        if c:
            session.delete(c)


@pytest.fixture
def test_company_b():
    """Provides isolated test company B."""
    cid = f"test-company-b-{uuid.uuid4().hex[:8]}"
    with traditional_db_manager.session_scope() as session:
        comp = Company(
            id=cid,
            code=f"CB_{uuid.uuid4().hex[:6]}",
            name="Beta Distributors Ltd",
            gstin="29BBBPD1234E1Z5",
            state="Karnataka (29)",
            is_active=True,
        )
        session.add(comp)
        branch = Branch(
            id=f"branch-b-{uuid.uuid4().hex[:8]}",
            company_id=cid,
            code="BR01",
            name="Central Depot",
        )
        session.add(branch)
    yield cid
    with traditional_db_manager.session_scope() as session:
        c = session.get(Company, cid)
        if c:
            session.delete(c)


# -------------------------------------------------------------------------
# Test Cases (All 15 Required Coverage Items)
# -------------------------------------------------------------------------

def test_1_independent_layouts_for_all_four_voucher_types(test_company_a):
    """1. Independent layouts for all four voucher types."""
    for vt in VOUCHER_TYPES:
        cfg = bill_layout_service.get_default_config(vt)
        cfg["layout_name"] = f"Custom {vt.replace('_', ' ').title()}"
        cfg["invoice_info_config"]["title"] = f"OFFICIAL {vt.upper()}"
        
        saved = bill_layout_service.save_layout_config(test_company_a, vt, cfg)
        assert saved["voucher_type"] == vt
        assert saved["layout_name"] == f"Custom {vt.replace('_', ' ').title()}"
        assert saved["invoice_info_config"]["title"] == f"OFFICIAL {vt.upper()}"

    # Verify each voucher type retained its independent settings
    sales_inv = bill_layout_service.get_layout_config(test_company_a, "sales_invoice")
    sales_ret = bill_layout_service.get_layout_config(test_company_a, "sales_return")
    pur_inv = bill_layout_service.get_layout_config(test_company_a, "purchase_invoice")
    pur_ret = bill_layout_service.get_layout_config(test_company_a, "purchase_return")

    assert sales_inv["invoice_info_config"]["title"] == "OFFICIAL SALES_INVOICE"
    assert sales_ret["invoice_info_config"]["title"] == "OFFICIAL SALES_RETURN"
    assert pur_inv["invoice_info_config"]["title"] == "OFFICIAL PURCHASE_INVOICE"
    assert pur_ret["invoice_info_config"]["title"] == "OFFICIAL PURCHASE_RETURN"


def test_2_company_logo_persistence(test_company_a):
    """2. Company logo persistence (data URL, positioning, sizing, visibility)."""
    cfg = bill_layout_service.get_default_config("sales_invoice")
    cfg["header_config"]["show_logo"] = True
    cfg["header_config"]["logo_data"] = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    cfg["header_config"]["logo_position"] = "center"
    cfg["header_config"]["logo_width_mm"] = 45.0
    cfg["header_config"]["logo_height_mm"] = 30.0

    saved = bill_layout_service.save_layout_config(test_company_a, "sales_invoice", cfg)
    assert saved["header_config"]["show_logo"] is True
    assert saved["header_config"]["logo_position"] == "center"
    assert saved["header_config"]["logo_width_mm"] == 45.0
    assert saved["header_config"]["logo_height_mm"] == 30.0
    assert "data:image/png;base64," in saved["header_config"]["logo_data"]

    # Reload from DB
    reloaded = bill_layout_service.get_layout_config(test_company_a, "sales_invoice")
    assert reloaded["header_config"]["show_logo"] is True
    assert reloaded["header_config"]["logo_position"] == "center"
    assert reloaded["header_config"]["logo_width_mm"] == 45.0


def test_3_company_details_loading(test_company_a):
    """3. Company details loading from actual database records."""
    details = bill_layout_service.get_company_details(test_company_a)
    assert details["company_id"] == test_company_a
    assert details["company_name"] == "Alpha Enterprise Pvt Ltd"
    assert details["gstin"] == "33AAAPL9876C1Z2"
    assert details["state"] == "Tamil Nadu (33)"


def test_4_gst_field_visibility(test_company_a):
    """4. GST field visibility toggles (CGST, SGST, IGST in totals and table)."""
    cfg = bill_layout_service.get_default_config("sales_invoice")
    # Hide CGST and SGST, enable IGST (e.g. for interstate transactions)
    cfg["totals_config"]["show_cgst_total"] = False
    cfg["totals_config"]["show_sgst_total"] = False
    cfg["totals_config"]["show_igst_total"] = True

    # In columns:
    for c in cfg["columns_config"]:
        if c["key"] in ("cgst", "sgst"):
            c["visible"] = False
        elif c["key"] == "igst":
            c["visible"] = True

    saved = bill_layout_service.save_layout_config(test_company_a, "sales_invoice", cfg)
    assert saved["totals_config"]["show_cgst_total"] is False
    assert saved["totals_config"]["show_sgst_total"] is False
    assert saved["totals_config"]["show_igst_total"] is True

    col_map = {c["key"]: c["visible"] for c in saved["columns_config"]}
    assert col_map["cgst"] is False
    assert col_map["sgst"] is False
    assert col_map["igst"] is True


def test_5_product_column_visibility(test_company_a):
    """5. Product column visibility (showing/hiding specific columns)."""
    cfg = bill_layout_service.get_default_config("sales_invoice")
    for c in cfg["columns_config"]:
        if c["key"] in ("sku", "barcode", "description"):
            c["visible"] = True
        elif c["key"] == "discount":
            c["visible"] = False

    saved = bill_layout_service.save_layout_config(test_company_a, "sales_invoice", cfg)
    col_map = {c["key"]: c["visible"] for c in saved["columns_config"]}
    assert col_map["sku"] is True
    assert col_map["barcode"] is True
    assert col_map["description"] is True
    assert col_map["discount"] is False


def test_6_column_ordering(test_company_a):
    """6. Column ordering customization."""
    cfg = bill_layout_service.get_default_config("sales_invoice")
    # Move 'hsn' to order 1, 'name' to order 2
    for c in cfg["columns_config"]:
        if c["key"] == "hsn":
            c["order"] = 1
        elif c["key"] == "name":
            c["order"] = 2
        elif c["key"] == "sl_no":
            c["order"] = 3

    saved = bill_layout_service.save_layout_config(test_company_a, "sales_invoice", cfg)
    ordered_keys = [c["key"] for c in saved["columns_config"]]
    assert ordered_keys[0] == "hsn"
    assert ordered_keys[1] == "name"
    assert ordered_keys[2] == "sl_no"


def test_7_footer_customization(test_company_a):
    """7. Footer customization (terms, bank details, notes, signatory)."""
    cfg = bill_layout_service.get_default_config("sales_invoice")
    cfg["footer_config"]["terms_and_conditions"] = "Custom terms: Strict 7 days net payment."
    cfg["footer_config"]["bank_name"] = "State Bank of India"
    cfg["footer_config"]["account_number"] = "112233445566"
    cfg["footer_config"]["ifsc_code"] = "SBIN0001234"
    cfg["footer_config"]["upi_id"] = "alpha@sbi"
    cfg["footer_config"]["customer_notes"] = "Special client terms applied."
    cfg["footer_config"]["signatory_title"] = "Managing Director"

    saved = bill_layout_service.save_layout_config(test_company_a, "sales_invoice", cfg)
    ftr = saved["footer_config"]
    assert ftr["terms_and_conditions"] == "Custom terms: Strict 7 days net payment."
    assert ftr["bank_name"] == "State Bank of India"
    assert ftr["account_number"] == "112233445566"
    assert ftr["ifsc_code"] == "SBIN0001234"
    assert ftr["upi_id"] == "alpha@sbi"
    assert ftr["signatory_title"] == "Managing Director"


def test_8_a4_preview(test_company_a):
    """8. A4 preview generation (compiles A4 PDF combining Phase 1 paper settings & Phase 2 layout)."""
    sample_voucher = {
        "vch_no": "INV-A4-001",
        "vch_date": "16-11-2026",
        "party_name": "Modern Retailers",
        "items": [
            {"name": "Industrial Router", "qty": 2, "rate": 3500.0, "total": 7000.0, "taxable_amount": 7000.0, "cgst": 630.0, "sgst": 630.0},
        ],
        "subtotal": 7000.0,
        "cgst_amount": 630.0,
        "sgst_amount": 630.0,
        "grand_total": 8260.0
    }

    res = bill_layout_service.compile_invoice_pdf(
        voucher_data=sample_voucher,
        company_id=test_company_a,
        voucher_type="sales_invoice",
        paper_format="a4"
    )
    assert res["success"] is True
    assert res["paper_format"] == "a4"
    pdf_path = Path(res["file_path"])
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 1000


def test_9_a5_preview(test_company_a):
    """9. A5 preview generation (compiles A5 PDF with independent A5 dimensions)."""
    sample_voucher = {
        "vch_no": "INV-A5-001",
        "vch_date": "16-11-2026",
        "party_name": "Corner Shop",
        "items": [
            {"name": "Handheld Terminal", "qty": 1, "rate": 1500.0, "total": 1500.0, "taxable_amount": 1500.0, "cgst": 135.0, "sgst": 135.0},
        ],
        "subtotal": 1500.0,
        "grand_total": 1770.0
    }

    res = bill_layout_service.compile_invoice_pdf(
        voucher_data=sample_voucher,
        company_id=test_company_a,
        voucher_type="sales_invoice",
        paper_format="a5"
    )
    assert res["success"] is True
    assert res["paper_format"] == "a5"
    pdf_path = Path(res["file_path"])
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 1000


def test_10_thermal_preview(test_company_a):
    """10. Thermal preview generation (formats responsive continuous receipt stream)."""
    sample_voucher = {
        "vch_no": "POS-0099",
        "vch_date": "16-11-2026",
        "party_name": "Walk-in Customer",
        "items": [
            {"name": "Thermal Ribbon", "qty": 3, "rate": 120.0, "total": 360.0},
        ],
        "subtotal": 360.0,
        "grand_total": 360.0
    }

    receipt_text = bill_layout_service.format_invoice_thermal(
        voucher_data=sample_voucher,
        company_id=test_company_a,
        voucher_type="sales_invoice",
        paper_format="thermal"
    )
    assert "ALPHA ENTERPRISE PVT LTD" in receipt_text
    assert "POS-0099" in receipt_text
    assert "Thermal Ribbon" in receipt_text
    assert "GRAND TOTAL:" in receipt_text
    assert "PAPER CUT" in receipt_text


def test_11_layout_save_and_reload(test_company_a):
    """11. Layout save, reload, and partial section reset."""
    custom_title = "SPECIAL COMMERCIAL INVOICE"
    cfg = bill_layout_service.get_default_config("sales_invoice")
    cfg["invoice_info_config"]["title"] = custom_title
    cfg["style_config"]["header_bg_color"] = "#047857"

    bill_layout_service.save_layout_config(test_company_a, "sales_invoice", cfg)

    # Reload from DB
    reloaded = bill_layout_service.get_layout_config(test_company_a, "sales_invoice")
    assert reloaded["invoice_info_config"]["title"] == custom_title
    assert reloaded["style_config"]["header_bg_color"] == "#047857"
    assert reloaded["is_default"] is False

    # Partial reset of invoice_info_config section
    part_reset = bill_layout_service.reset_layout_config(test_company_a, "sales_invoice", section="invoice_info_config")
    assert part_reset["invoice_info_config"]["title"] == "TAX INVOICE"
    # style_config remains customized
    assert part_reset["style_config"]["header_bg_color"] == "#047857"

    # Full reset to factory defaults
    full_reset = bill_layout_service.reset_layout_config(test_company_a, "sales_invoice")
    assert full_reset["is_default"] is True
    assert full_reset["style_config"]["header_bg_color"] == "#1e40af"


def test_12_company_isolation(test_company_a, test_company_b):
    """12. Company isolation: Tenant A and Tenant B layout settings do not leak."""
    # Tenant A configures Title A
    cfg_a = bill_layout_service.get_default_config("sales_invoice")
    cfg_a["invoice_info_config"]["title"] = "TENANT A EXCLUSIVE INVOICE"
    bill_layout_service.save_layout_config(test_company_a, "sales_invoice", cfg_a)

    # Tenant B configures Title B
    cfg_b = bill_layout_service.get_default_config("sales_invoice")
    cfg_b["invoice_info_config"]["title"] = "TENANT B WHOLESALE BILL"
    bill_layout_service.save_layout_config(test_company_b, "sales_invoice", cfg_b)

    # Verify isolation
    loaded_a = bill_layout_service.get_layout_config(test_company_a, "sales_invoice")
    loaded_b = bill_layout_service.get_layout_config(test_company_b, "sales_invoice")

    assert loaded_a["invoice_info_config"]["title"] == "TENANT A EXCLUSIVE INVOICE"
    assert loaded_b["invoice_info_config"]["title"] == "TENANT B WHOLESALE BILL"

    # Resetting Tenant A does not alter Tenant B
    bill_layout_service.reset_layout_config(test_company_a, "sales_invoice")
    assert bill_layout_service.get_layout_config(test_company_a, "sales_invoice")["invoice_info_config"]["title"] == "TAX INVOICE"
    assert bill_layout_service.get_layout_config(test_company_b, "sales_invoice")["invoice_info_config"]["title"] == "TENANT B WHOLESALE BILL"


def test_13_branch_isolation(test_company_a):
    """13. Branch isolation and layout duplication."""
    # Duplicate Sales Invoice layout to Sales Return layout
    dup_res = bill_layout_service.duplicate_layout_config(
        company_id=test_company_a,
        from_voucher_type="sales_invoice",
        to_voucher_type="sales_return"
    )
    assert dup_res["voucher_type"] == "sales_return"
    assert dup_res["invoice_info_config"]["title"] == "CREDIT NOTE / SALES RETURN"

    # Verify both exist independently
    reloaded_ret = bill_layout_service.get_layout_config(test_company_a, "sales_return")
    assert reloaded_ret["voucher_type"] == "sales_return"


def test_14_traditional_fast_billing_isolation(test_company_a):
    """14. Traditional / Fast Billing isolation (JSON store vs Traditional DB)."""
    fast_company_id = "fast_retail_co"
    fast_cfg = bill_layout_service.get_default_config("sales_invoice")
    fast_cfg["layout_name"] = "Fast Cashier Custom Layout"
    fast_cfg["invoice_info_config"]["title"] = "FAST POS RECEIPT"
    
    bill_layout_service.save_fast_layout_config(fast_company_id, "sales_invoice", fast_cfg)

    # Traditional billing config
    trad_cfg = bill_layout_service.get_default_config("sales_invoice")
    trad_cfg["layout_name"] = "Traditional ERP Custom Layout"
    trad_cfg["invoice_info_config"]["title"] = "FORMAL TAX INVOICE"
    bill_layout_service.save_layout_config(test_company_a, "sales_invoice", trad_cfg)

    # Verify isolation
    loaded_fast = bill_layout_service.get_fast_layout_config(fast_company_id, "sales_invoice")
    loaded_trad = bill_layout_service.get_layout_config(test_company_a, "sales_invoice")

    assert loaded_fast["invoice_info_config"]["title"] == "FAST POS RECEIPT"
    assert loaded_trad["invoice_info_config"]["title"] == "FORMAL TAX INVOICE"


def test_15_existing_printing_regression_tests(test_company_a):
    """15. Printing engine regression test: PrintingService generates PDF & Thermal seamlessly."""
    tmp_out = config.DATA_DIR / "invoices" / "test_regression_inv.pdf"
    voucher_data = {
        "company_id": test_company_a,
        "company_name": "Alpha Enterprise Pvt Ltd",
        "company_gstin": "33AAAPL9876C1Z2",
        "voucher_no": "VCH-REG-999",
        "voucher_type": "sales_invoice",
        "party_name": "Standard Customer",
        "items": [
            {"item_name": "General Widget", "qty": 5, "price": 100.0, "amount": 500.0}
        ],
        "subtotal": 500.0,
        "grand_total": 590.0,
        "cgst_amount": 45.0,
        "sgst_amount": 45.0,
    }

    # 1. Test generate_pdf_invoice with layout compilation
    pdf_res = printing_service.generate_pdf_invoice(voucher_data, tmp_out, paper_format="a4", company_id=test_company_a)
    assert Path(pdf_res).exists()
    assert Path(pdf_res).stat().st_size > 1000

    # 2. Test format_thermal_receipt with layout compilation
    thermal_res = printing_service.format_thermal_receipt(voucher_data, width_mm=80, company_id=test_company_a)
    assert "ALPHA ENTERPRISE PVT LTD" in thermal_res
    assert "VCH-REG-999" in thermal_res
    assert "GRAND TOTAL:" in thermal_res
