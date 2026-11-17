import json
import os
import uuid
from pathlib import Path
import pytest
from sqlalchemy import select

from services.paper_config_service import (
    PaperConfigService,
    paper_config_service,
    DEFAULT_A4_CONFIG,
    DEFAULT_A5_CONFIG,
    DEFAULT_THERMAL_CONFIG,
)
from db.traditional_database import traditional_db_manager
from db.traditional_models import Company, Branch, PaperConfiguration
from desktop.web_bridge import BackendBridge

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Ensure Traditional migrations are applied and create isolated test companies."""
    traditional_db_manager.run_traditional_migrations()
    traditional_db_manager.ensure_initialized()

@pytest.fixture
def test_company_a():
    """Fixture providing an isolated test company A."""
    cid = f"test-company-a-{uuid.uuid4().hex[:8]}"
    with traditional_db_manager.session_scope() as session:
        comp = Company(
            id=cid,
            code=f"CA_{uuid.uuid4().hex[:6]}",
            name="Alpha Corp Test",
            is_active=True,
        )
        session.add(comp)
        branch = Branch(
            id=f"branch-a-{uuid.uuid4().hex[:8]}",
            company_id=cid,
            code="BR01",
            name="Main Branch",
        )
        session.add(branch)
    yield cid
    # Clean up
    with traditional_db_manager.session_scope() as session:
        c = session.get(Company, cid)
        if c:
            session.delete(c)

@pytest.fixture
def test_company_b():
    """Fixture providing an isolated test company B."""
    cid = f"test-company-b-{uuid.uuid4().hex[:8]}"
    with traditional_db_manager.session_scope() as session:
        comp = Company(
            id=cid,
            code=f"CB_{uuid.uuid4().hex[:6]}",
            name="Beta Corp Test",
            is_active=True,
        )
        session.add(comp)
        branch = Branch(
            id=f"branch-b-{uuid.uuid4().hex[:8]}",
            company_id=cid,
            code="BR01",
            name="Secondary Branch",
        )
        session.add(branch)
    yield cid
    with traditional_db_manager.session_scope() as session:
        c = session.get(Company, cid)
        if c:
            session.delete(c)

# -------------------------------------------------------------------------
# Test Cases
# -------------------------------------------------------------------------

def test_1_a4_settings_save_and_reload(test_company_a):
    """1. A4 settings save and reload."""
    custom_a4 = {
        **DEFAULT_A4_CONFIG,
        "orientation": "landscape",
        "margin_top_mm": 15.0,
        "margin_bottom_mm": 15.0,
        "margin_left_mm": 20.0,
        "margin_right_mm": 20.0,
        "print_scaling": 95,
        "header_spacing_mm": 12.0,
        "footer_spacing_mm": 10.0,
        "page_numbering": True,
        "default_printer": "Test A4 Office Printer",
    }

    saved = paper_config_service.save_paper_config(test_company_a, "a4", custom_a4)
    assert saved["paper_format"] == "a4"
    assert saved["orientation"] == "landscape"
    assert saved["margin_left_mm"] == 20.0
    assert saved["default_printer"] == "Test A4 Office Printer"

    # Reload from DB
    reloaded = paper_config_service.get_paper_config(test_company_a, "a4")
    assert reloaded["paper_format"] == "a4"
    assert reloaded["orientation"] == "landscape"
    assert reloaded["margin_top_mm"] == 15.0
    assert reloaded["print_scaling"] == 95
    assert reloaded["default_printer"] == "Test A4 Office Printer"
    assert reloaded["page_numbering"] is True
    assert reloaded["is_default"] is False

def test_2_a5_settings_save_and_reload(test_company_a):
    """2. A5 settings save and reload & format independence."""
    custom_a5 = {
        **DEFAULT_A5_CONFIG,
        "orientation": "portrait",
        "margin_top_mm": 8.0,
        "margin_bottom_mm": 8.0,
        "margin_left_mm": 8.0,
        "margin_right_mm": 8.0,
        "print_scaling": 100,
        "header_spacing_mm": 6.0,
        "footer_spacing_mm": 6.0,
        "default_printer": "Test A5 Countertop Printer",
    }

    saved = paper_config_service.save_paper_config(test_company_a, "a5", custom_a5)
    assert saved["paper_format"] == "a5"

    reloaded = paper_config_service.get_paper_config(test_company_a, "a5")
    assert reloaded["paper_format"] == "a5"
    assert reloaded["width_mm"] == 148.0
    assert reloaded["height_mm"] == 210.0
    assert reloaded["margin_top_mm"] == 8.0
    assert reloaded["default_printer"] == "Test A5 Countertop Printer"

    # Verify A4 remains distinct and unperturbed
    a4_config = paper_config_service.get_paper_config(test_company_a, "a4")
    assert a4_config["width_mm"] == 210.0
    assert a4_config["height_mm"] == 297.0

def test_3_thermal_58mm_configuration(test_company_a):
    """3. Thermal 58 mm configuration."""
    t58_config = {
        **DEFAULT_THERMAL_CONFIG,
        "thermal_paper_width_type": "58mm",
        "width_mm": 58.0,
        "printable_width_mm": 48.0,
        "margin_left_mm": 2.0,
        "margin_right_mm": 2.0,
        "font_size": 9,
        "line_spacing": 1.1,
        "char_alignment": "left",
        "auto_cut": True,
        "default_printer": "POS-58 Receipt Printer",
    }

    saved = paper_config_service.save_paper_config(test_company_a, "thermal", t58_config)
    assert saved["paper_format"] == "thermal"
    assert saved["width_mm"] == 58.0
    assert saved["printable_width_mm"] == 48.0

    reloaded = paper_config_service.get_paper_config(test_company_a, "thermal")
    assert reloaded["thermal_paper_width_type"] == "58mm"
    assert reloaded["width_mm"] == 58.0
    assert reloaded["printable_width_mm"] == 48.0
    assert reloaded["auto_cut"] is True

def test_4_thermal_80mm_configuration(test_company_a):
    """4. Thermal 80 mm configuration."""
    t80_config = {
        **DEFAULT_THERMAL_CONFIG,
        "thermal_paper_width_type": "80mm",
        "width_mm": 80.0,
        "printable_width_mm": 72.0,
        "margin_left_mm": 3.0,
        "margin_right_mm": 3.0,
        "font_size": 11,
        "line_spacing": 1.2,
        "char_alignment": "center",
        "print_density": "Dark",
        "auto_cut": True,
        "default_printer": "Epson TM-T88VI",
    }

    saved = paper_config_service.save_paper_config(test_company_a, "thermal", t80_config)
    assert saved["paper_format"] == "thermal"

    reloaded = paper_config_service.get_paper_config(test_company_a, "thermal")
    assert reloaded["thermal_paper_width_type"] == "80mm"
    assert reloaded["width_mm"] == 80.0
    assert reloaded["printable_width_mm"] == 72.0
    assert reloaded["print_density"] == "Dark"

def test_5_custom_thermal_width_validation():
    """5. Custom thermal width validation."""
    # Under min bounds (min is 30mm)
    bad_narrow = {
        **DEFAULT_THERMAL_CONFIG,
        "thermal_paper_width_type": "custom",
        "width_mm": 25.0,
        "printable_width_mm": 20.0,
    }
    with pytest.raises(ValueError, match="between 30 mm and 120 mm"):
        paper_config_service.validate_paper_config("thermal", bad_narrow)

    # Over max bounds (max is 120mm)
    bad_wide = {
        **DEFAULT_THERMAL_CONFIG,
        "thermal_paper_width_type": "custom",
        "width_mm": 130.0,
        "printable_width_mm": 100.0,
    }
    with pytest.raises(ValueError, match="between 30 mm and 120 mm"):
        paper_config_service.validate_paper_config("thermal", bad_wide)

    # Printable width exceeds total width minus margins
    bad_printable = {
        **DEFAULT_THERMAL_CONFIG,
        "thermal_paper_width_type": "custom",
        "width_mm": 70.0,
        "margin_left_mm": 5.0,
        "margin_right_mm": 5.0,
        "printable_width_mm": 65.0,  # 65 > (70 - 10 = 60)
    }
    with pytest.raises(ValueError, match="cannot exceed available width"):
        paper_config_service.validate_paper_config("thermal", bad_printable)

    # Valid custom width
    valid_custom = {
        **DEFAULT_THERMAL_CONFIG,
        "thermal_paper_width_type": "custom",
        "width_mm": 76.0,
        "printable_width_mm": 68.0,
        "margin_left_mm": 3.0,
        "margin_right_mm": 3.0,
    }
    cleaned = paper_config_service.validate_paper_config("thermal", valid_custom)
    assert cleaned["width_mm"] == 76.0
    assert cleaned["printable_width_mm"] == 68.0

def test_6_orientation_switching():
    """6. Orientation switching."""
    cfg_portrait = {
        **DEFAULT_A4_CONFIG,
        "orientation": "portrait"
    }
    validated_portrait = paper_config_service.validate_paper_config("a4", cfg_portrait)
    assert validated_portrait["orientation"] == "portrait"

    cfg_landscape = {
        **DEFAULT_A4_CONFIG,
        "orientation": "landscape"
    }
    validated_landscape = paper_config_service.validate_paper_config("a4", cfg_landscape)
    assert validated_landscape["orientation"] == "landscape"

    cfg_invalid = {
        **DEFAULT_A4_CONFIG,
        "orientation": "diagonal"
    }
    with pytest.raises(ValueError, match="Orientation must be 'portrait' or 'landscape'"):
        paper_config_service.validate_paper_config("a4", cfg_invalid)

def test_7_margin_validation():
    """7. Margin validation."""
    # Negative margins
    neg_margin = {
        **DEFAULT_A4_CONFIG,
        "margin_top_mm": -5.0
    }
    with pytest.raises(ValueError, match="Margin values cannot be negative"):
        paper_config_service.validate_paper_config("a4", neg_margin)

    # Left + Right margins >= Width
    excessive_h_margins = {
        **DEFAULT_A4_CONFIG,
        "width_mm": 210.0,
        "margin_left_mm": 110.0,
        "margin_right_mm": 105.0  # sum = 215 >= 210
    }
    with pytest.raises(ValueError, match="must be less than paper width"):
        paper_config_service.validate_paper_config("a4", excessive_h_margins)

    # Top + Bottom margins >= Height
    excessive_v_margins = {
        **DEFAULT_A4_CONFIG,
        "height_mm": 297.0,
        "margin_top_mm": 150.0,
        "margin_bottom_mm": 150.0  # sum = 300 >= 297
    }
    with pytest.raises(ValueError, match="must be less than paper height"):
        paper_config_service.validate_paper_config("a4", excessive_v_margins)

def test_8_preview_and_test_print_generation():
    """8. Neutral test print generation."""
    # Test sheet PDF generation for A4 portrait
    res_a4 = paper_config_service.generate_test_print("a4", DEFAULT_A4_CONFIG)
    assert res_a4["success"] is True
    assert "file_path" in res_a4
    pdf_path = Path(res_a4["file_path"])
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 500

    # Test sheet PDF generation for A5 landscape
    a5_land = {**DEFAULT_A5_CONFIG, "orientation": "landscape"}
    res_a5 = paper_config_service.generate_test_print("a5", a5_land)
    assert res_a5["success"] is True
    assert Path(res_a5["file_path"]).exists()

    # Test thermal receipt text generation
    res_thermal = paper_config_service.generate_test_print("thermal", DEFAULT_THERMAL_CONFIG)
    assert res_thermal["success"] is True
    assert res_thermal["format"] == "thermal"
    thermal_raw = res_thermal["receipt_text"]
    assert "ANTI-MATRIX TEST RECEIPT" in thermal_raw
    assert "HARDWARE ALIGNMENT TEST" in thermal_raw
    assert "AUTOMATIC PAPER CUT SIGNAL" in thermal_raw

def test_9_printer_discovery():
    """9. Printer discovery."""
    bridge = BackendBridge()
    raw_res = bridge.getAvailablePrintersWithCapabilities()
    res = json.loads(raw_res)
    assert "success" in res
    assert res["success"] is True
    assert "data" in res
    assert isinstance(res["data"], list)
    assert len(res["data"]) >= 1
    p0 = res["data"][0]
    assert "name" in p0
    assert "is_default" in p0
    assert "supports_auto_cut" in p0
    assert "supports_density" in p0

def test_10_reset_to_default(test_company_a):
    """10. Reset to default."""
    # Save a modified A4 config
    modified_a4 = {
        **DEFAULT_A4_CONFIG,
        "margin_top_mm": 35.0,
        "orientation": "landscape"
    }
    paper_config_service.save_paper_config(test_company_a, "a4", modified_a4)

    # Verify saved
    loaded = paper_config_service.get_paper_config(test_company_a, "a4")
    assert loaded["margin_top_mm"] == 35.0
    assert loaded["orientation"] == "landscape"
    assert loaded["is_default"] is False

    # Perform reset
    reset_res = paper_config_service.reset_paper_config(test_company_a, "a4")
    assert reset_res["margin_top_mm"] == DEFAULT_A4_CONFIG["margin_top_mm"]
    assert reset_res["orientation"] == DEFAULT_A4_CONFIG["orientation"]
    assert reset_res["is_default"] is True

    # Fetch again from DB to verify persistence of reset
    reloaded = paper_config_service.get_paper_config(test_company_a, "a4")
    assert reloaded["margin_top_mm"] == DEFAULT_A4_CONFIG["margin_top_mm"]
    assert reloaded["orientation"] == DEFAULT_A4_CONFIG["orientation"]
    assert reloaded["is_default"] is True

def test_11_company_branch_isolation(test_company_a, test_company_b):
    """11. Company/branch isolation."""
    # Company A uses Landscape A4 with 25mm left margin
    cfg_a = {**DEFAULT_A4_CONFIG, "orientation": "landscape", "margin_left_mm": 25.0}
    paper_config_service.save_paper_config(test_company_a, "a4", cfg_a)

    # Company B uses Portrait A4 with 14mm left margin
    cfg_b = {**DEFAULT_A4_CONFIG, "orientation": "portrait", "margin_left_mm": 14.0}
    paper_config_service.save_paper_config(test_company_b, "a4", cfg_b)

    # Verify Company A's config
    fetched_a = paper_config_service.get_paper_config(test_company_a, "a4")
    assert fetched_a["orientation"] == "landscape"
    assert fetched_a["margin_left_mm"] == 25.0

    # Verify Company B's config
    fetched_b = paper_config_service.get_paper_config(test_company_b, "a4")
    assert fetched_b["orientation"] == "portrait"
    assert fetched_b["margin_left_mm"] == 14.0

    # Reset Company A only
    paper_config_service.reset_paper_config(test_company_a, "a4")
    assert paper_config_service.get_paper_config(test_company_a, "a4")["margin_left_mm"] == DEFAULT_A4_CONFIG["margin_left_mm"]

    # Company B must remain unchanged
    assert paper_config_service.get_paper_config(test_company_b, "a4")["margin_left_mm"] == 14.0

def test_12_traditional_fast_mode_isolation(test_company_a):
    """12. Traditional / Fast mode isolation."""
    fast_company_id = "fast_store_co"
    # Fast billing uses fast_paper_configurations.json
    fast_a4 = {**DEFAULT_A4_CONFIG, "print_scaling": 88, "header_spacing_mm": 22.0}
    paper_config_service.save_fast_paper_config(fast_company_id, "a4", fast_a4)

    # Traditional billing uses traditional_db_manager
    trad_a4 = {**DEFAULT_A4_CONFIG, "print_scaling": 105, "header_spacing_mm": 15.0}
    paper_config_service.save_paper_config(test_company_a, "a4", trad_a4)

    # Verify isolation
    loaded_fast = paper_config_service.get_fast_paper_config(fast_company_id, "a4")
    loaded_trad = paper_config_service.get_paper_config(test_company_a, "a4")

    assert loaded_fast["print_scaling"] == 88
    assert loaded_fast["header_spacing_mm"] == 22.0
    assert loaded_trad["print_scaling"] == 105
    assert loaded_trad["header_spacing_mm"] == 15.0
