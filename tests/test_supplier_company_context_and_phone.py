"""
Tests for:
Anti-Matrix Billing — Supplier Company Context Resolution & Strict 10-Digit Phone Limit
Verifies:
1. Supplier creation resolves the active Traditional Billing company context without error.
2. The newly saved supplier is immediately retrievable via listSuppliers.
3. Phone number validation strictly enforces exactly 10 numeric digits:
   - Rejects < 10 digits
   - Rejects > 10 digits
   - Rejects non-numeric characters (letters, spaces, punctuation)
   - Accepts valid 10 digits
4. Company context mismatch or invalid company raises clear ValueError/PermissionError.
5. Fast Billing database remains completely untouched.
"""
import json
import pytest
from pathlib import Path
from db.database import db_manager, DatabaseManager
from db.traditional_database import traditional_db_manager
from services.supplier_service import supplier_service
from desktop.web_bridge import BackendBridge
from services.traditional_auth_service import session_registry
from core.configuration import config


TRAD_COMPANY_ID = "71b91c79-91d6-4712-938e-025176ccd13a"


@pytest.fixture
def auth_bridge():
    bridge = BackendBridge()
    token = session_registry.create_session(
        user_id="test-admin-uuid",
        company_id=TRAD_COMPANY_ID,
        branch_id="test-branch-uuid",
        role_name="Administrator",
        username="ADMIN",
        display_name="Test Administrator",
        company_code="CORP01",
    )
    bridge._traditional_session = session_registry.get_session(token)
    return bridge


def test_supplier_creation_with_valid_company_context(auth_bridge):
    """Verify supplier is saved into Traditional Billing company database without context error."""
    payload = {
        "name": "Coimbatore Textile Supplies",
        "phone": "9876543210",
        "gstin": "33ABCDE1234F1Z5",
        "address": "45 Trichy Road",
        "city": "Coimbatore",
        "state": "Tamilnadu",
        "credit_limit": 75000.0,
        "opening_balance": 25000.0
    }
    resp = json.loads(auth_bridge.saveSupplier(TRAD_COMPANY_ID, json.dumps(payload)))
    assert resp["success"] is True
    data = resp["data"]
    assert data["name"] == "COIMBATORE TEXTILE SUPPLIES"
    assert data["phone"] == "9876543210"
    assert data["code"].startswith("SUP-")

    # Verify immediate dropdown listing availability
    list_resp = json.loads(auth_bridge.listSuppliers(TRAD_COMPANY_ID, ""))
    assert list_resp["success"] is True
    supplier_ids = [s["id"] for s in list_resp["data"]]
    assert data["id"] in supplier_ids


def test_strict_10_digit_phone_validation(auth_bridge):
    """Verify strictly 10 numeric digits are enforced on supplier contact phone."""
    invalid_phones = [
        ("123456789", "fewer than 10 digits"),
        ("12345678901", "more than 10 digits"),
        ("98765abcd0", "letters"),
        ("98765-4321", "hyphenated"),
        ("98765 4321", "spaced"),
        ("+9198765432", "country code non-digit prefix"),
        ("abcdefghij", "pure letters"),
    ]

    for bad_phone, desc in invalid_phones:
        payload = {
            "name": f"Phone Test Supplier {bad_phone}",
            "phone": bad_phone
        }
        resp = json.loads(auth_bridge.saveSupplier(TRAD_COMPANY_ID, json.dumps(payload)))
        assert resp["success"] is False, f"Expected rejection for {desc}: {bad_phone}"
        assert "10 numeric digits" in resp["error"] or "10 digits" in resp["error"]


def test_valid_10_digit_phone_accepted(auth_bridge):
    """Verify exactly 10 numeric digits pass validation."""
    payload = {
        "name": "Valid Phone Yarn Agency",
        "phone": "9123456789",
        "city": "Salem"
    }
    resp = json.loads(auth_bridge.saveSupplier(TRAD_COMPANY_ID, json.dumps(payload)))
    assert resp["success"] is True
    assert resp["data"]["phone"] == "9123456789"


def test_invalid_company_context_rejection(auth_bridge):
    """Verify non-existent company UUID is rejected with clear error."""
    payload = {
        "name": "Ghost Company Supplier",
        "phone": "9876543210"
    }
    # 1. Direct service call with genuinely non-existent company
    with pytest.raises(ValueError) as exc_info:
        supplier_service.save_supplier("00000000-0000-0000-0000-000000000000", payload)
    assert "Invalid company context" in str(exc_info.value)
    assert "00000000-0000-0000-0000-000000000000" in str(exc_info.value)

    # 2. Bridge call with unauthorized company
    resp = json.loads(auth_bridge.saveSupplier("00000000-0000-0000-0000-000000000000", json.dumps(payload)))
    assert resp["success"] is False
    assert "Access denied" in resp["error"]


def test_fast_billing_isolation():
    """Verify Fast Billing database is untouched."""
    fast_db_path = Path("data/anti_matrix_billing.db")
    if fast_db_path.exists():
        # Fast DB must not contain traditional company or suppliers created in this test
        import sqlite3
        conn = sqlite3.connect(str(fast_db_path))
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "companies" in tables:
            rows = conn.execute("SELECT id FROM companies WHERE id = ?", (TRAD_COMPANY_ID,)).fetchall()
            assert len(rows) == 0
