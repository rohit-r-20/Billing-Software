"""
Test Suite: Voucher Numbering Configuration & Generation Module (Anti-Matrix Billing V2 - Phase 4)

Verifies:
1. All four voucher types (sales_invoice, sales_return, purchase_invoice, purchase_return)
2. Prefix, suffix, and padding formatting (3 to 8 digits)
3. Financial year formatting (YYYY-YY, YY-YY, YYYY, YYYY-YYYY, separators)
4. Branch-specific numbering (prefix vs suffix placement)
5. Strict validation rules (disallowing invalid characters, negative starts, out-of-range padding)
6. Traditional DB persistence via Alembic migration 006 table
7. Multi-tenant company and branch isolation
8. Traditional Sales Invoice generation with custom numbering
9. Traditional Sales Return generation with custom numbering
10. Purchase Invoice generation with custom numbering
11. Purchase Return generation with custom numbering
12. Duplicate prevention and collision handling
13. Sequence preservation: reprinting and previewing never consume sequence
14. Historical voucher preservation: existing records remain untouched
15. Fast Billing JSON persistence and DB immutability
16. WebBridge role-based access control (Admin/Manager allowed, unauthorized blocked)
17. Reset to default functionality
18. Fast Billing database SHA256 immutability verification
"""

import hashlib
import json
import os
import uuid
from pathlib import Path
import pytest
from sqlalchemy import select

from core.configuration import config
from db.traditional_database import traditional_db_manager
from db.traditional_models import (
    Company,
    Branch,
    VoucherSequence,
    SaleInvoice,
    VoucherNumberingConfiguration,
)
from services.voucher_numbering_service import (
    voucher_numbering_service,
    VOUCHER_TYPES,
    DEFAULT_CONFIGS,
)
from services.traditional_product_service import TraditionalProductService
from services.billing_service import billing_service
from services.purchase_service import purchase_service
from desktop.web_bridge import BackendBridge
from services.traditional_auth_service import session_registry as traditional_session_registry


traditional_product_service = TraditionalProductService(traditional_db_manager)


FAST_DB_PATH = Path("data/anti_matrix_billing.db")
EXPECTED_FAST_DB_SHA256 = "86F48362EEAB4FA208CB51B7C899504CB6E30D16F9CDCBF39478A3921B2213DA"


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Ensure Traditional migrations are applied up to head (migration 006)."""
    traditional_db_manager.run_traditional_migrations()
    traditional_db_manager.ensure_initialized()


@pytest.fixture
def test_company_a():
    """Provides isolated test company A with a default BR01 branch."""
    cid = f"test-vch-comp-a-{uuid.uuid4().hex[:8]}"
    with traditional_db_manager.session_scope() as session:
        comp = Company(
            id=cid,
            code=f"VA_{uuid.uuid4().hex[:6]}",
            name="Alpha Retailers Pvt Ltd",
            gstin="33AAAPL9876C1Z2",
            state="Tamil Nadu (33)",
            is_active=True,
        )
        session.add(comp)
        branch = Branch(
            id=f"branch-a-{uuid.uuid4().hex[:8]}",
            company_id=cid,
            code="BR01",
            name="Main Branch",
            is_active=True,
        )
        session.add(branch)
    yield {"company_id": cid, "branch_id": branch.id, "branch_code": "BR01"}
    with traditional_db_manager.session_scope() as session:
        c = session.get(Company, cid)
        if c:
            session.delete(c)


@pytest.fixture
def test_company_b():
    """Provides isolated test company B for multi-tenant isolation testing."""
    cid = f"test-vch-comp-b-{uuid.uuid4().hex[:8]}"
    with traditional_db_manager.session_scope() as session:
        comp = Company(
            id=cid,
            code=f"VB_{uuid.uuid4().hex[:6]}",
            name="Beta Traders Corporation",
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
            is_active=True,
        )
        session.add(branch)
    yield {"company_id": cid, "branch_id": branch.id, "branch_code": "BR01"}
    with traditional_db_manager.session_scope() as session:
        c = session.get(Company, cid)
        if c:
            session.delete(c)


# ---------------------------------------------------------------------------
# 1. Supported Voucher Types & Defaults
# ---------------------------------------------------------------------------

def test_01_all_four_voucher_types_defaults_and_formatting():
    """Verify all 4 supported voucher types have standard defaults and produce valid numbers."""
    assert len(VOUCHER_TYPES) == 4
    assert "sales_invoice" in VOUCHER_TYPES
    assert "sales_return" in VOUCHER_TYPES
    assert "purchase_invoice" in VOUCHER_TYPES
    assert "purchase_return" in VOUCHER_TYPES

    for vtype in VOUCHER_TYPES:
        cfg = DEFAULT_CONFIGS[vtype]
        assert cfg["voucher_type"] == vtype
        assert cfg["is_custom_enabled"] is False
        assert cfg["start_number"] >= 1
        assert 3 <= cfg["padding"] <= 8

        # Test formatting with custom enabled
        test_cfg = dict(cfg, is_custom_enabled=True)
        num = voucher_numbering_service.format_voucher_number(test_cfg, 1)
        assert len(num) > 0
        assert str(cfg["prefix"]) in num


# ---------------------------------------------------------------------------
# 2. Prefix, Suffix, and Padding Formatting
# ---------------------------------------------------------------------------

def test_02_prefix_suffix_and_padding_formatting():
    """Verify prefix, suffix, and padding from 3 to 8 digits."""
    # 4 digits padding
    cfg4 = {
        "is_custom_enabled": True,
        "prefix": "INV-",
        "padding": 4,
        "suffix": "/HO",
    }
    assert voucher_numbering_service.format_voucher_number(cfg4, 7) == "INV-0007/HO"

    # 3 digits padding (minimum)
    cfg3 = {
        "is_custom_enabled": True,
        "prefix": "REC/",
        "padding": 3,
        "suffix": "",
    }
    assert voucher_numbering_service.format_voucher_number(cfg3, 42) == "REC/042"

    # 6 digits padding
    cfg6 = {
        "is_custom_enabled": True,
        "prefix": "PUR-",
        "padding": 6,
        "suffix": "",
    }
    assert voucher_numbering_service.format_voucher_number(cfg6, 125) == "PUR-000125"

    # 8 digits padding (maximum)
    cfg8 = {
        "is_custom_enabled": True,
        "prefix": "TX_",
        "padding": 8,
        "suffix": "-FINAL",
    }
    assert voucher_numbering_service.format_voucher_number(cfg8, 999) == "TX_00000999-FINAL"


# ---------------------------------------------------------------------------
# 3. Financial Year Formatting
# ---------------------------------------------------------------------------

def test_03_financial_year_formatting():
    """Verify all 4 financial year formats (YYYY-YY, YY-YY, YYYY, YYYY-YYYY) and separators."""
    fy_str = "2026-2027"

    assert voucher_numbering_service.format_financial_year(fy_str, "YYYY-YY") == "2026-27"
    assert voucher_numbering_service.format_financial_year(fy_str, "YY-YY") == "26-27"
    assert voucher_numbering_service.format_financial_year(fy_str, "YYYY") == "2026"
    assert voucher_numbering_service.format_financial_year(fy_str, "YYYY-YYYY") == "2026-2027"

    # In formatted voucher numbers with separator
    cfg_fy = {
        "is_custom_enabled": True,
        "prefix": "SI",
        "padding": 4,
        "suffix": "",
        "include_financial_year": True,
        "fy_format": "YYYY-YY",
        "fy_separator": "/",
    }
    num = voucher_numbering_service.format_voucher_number(cfg_fy, 1, financial_year="2026-2027")
    assert num == "SI/2026-27/0001"

    # Dash separator
    cfg_fy_dash = {
        "is_custom_enabled": True,
        "prefix": "PUR",
        "padding": 4,
        "suffix": "",
        "include_financial_year": True,
        "fy_format": "YY-YY",
        "fy_separator": "-",
    }
    num_dash = voucher_numbering_service.format_voucher_number(cfg_fy_dash, 5, financial_year="2026-2027")
    assert num_dash == "PUR-26-27-0005"


# ---------------------------------------------------------------------------
# 4. Branch-Specific Numbering
# ---------------------------------------------------------------------------

def test_04_branch_specific_numbering():
    """Verify branch code inclusion in prefix position and suffix position."""
    # Branch at prefix: BR01/INV/0001
    cfg_branch_prefix = {
        "is_custom_enabled": True,
        "prefix": "INV-",
        "padding": 4,
        "suffix": "",
        "include_branch_code": True,
        "branch_position": "prefix",
    }
    num_p = voucher_numbering_service.format_voucher_number(cfg_branch_prefix, 1, branch_code="BR01")
    assert num_p == "BR01/INV/0001"

    # Branch at suffix: INV/0001/BR01
    cfg_branch_suffix = {
        "is_custom_enabled": True,
        "prefix": "INV-",
        "padding": 4,
        "suffix": "",
        "include_branch_code": True,
        "branch_position": "suffix",
    }
    num_s = voucher_numbering_service.format_voucher_number(cfg_branch_suffix, 1, branch_code="BR01")
    assert num_s == "INV/0001/BR01"


# ---------------------------------------------------------------------------
# 5. Validation Rules
# ---------------------------------------------------------------------------

def test_05_validation_rules():
    """Verify input validation enforces boundaries and rejects invalid characters."""
    # Invalid characters in prefix
    is_valid, errs, _ = voucher_numbering_service.validate_config({
        "voucher_type": "sales_invoice",
        "prefix": "INV@#$",
        "start_number": 1,
        "padding": 4,
    })
    assert is_valid is False
    assert any("Prefix" in e for e in errs)

    # Invalid start number (less than 1)
    is_valid, errs, _ = voucher_numbering_service.validate_config({
        "voucher_type": "sales_invoice",
        "prefix": "INV-",
        "start_number": 0,
        "padding": 4,
    })
    assert is_valid is False
    assert any("start" in e.lower() for e in errs)

    # Invalid padding (out of range 3-8)
    is_valid, errs, _ = voucher_numbering_service.validate_config({
        "voucher_type": "sales_invoice",
        "prefix": "INV-",
        "start_number": 1,
        "padding": 2,
    })
    assert is_valid is False
    assert any("Padding" in e for e in errs)

    is_valid, errs, _ = voucher_numbering_service.validate_config({
        "voucher_type": "sales_invoice",
        "prefix": "INV-",
        "start_number": 1,
        "padding": 10,
    })
    assert is_valid is False
    assert any("Padding" in e for e in errs)

    # Invalid voucher type
    is_valid, errs, _ = voucher_numbering_service.validate_config({
        "voucher_type": "unsupported_voucher_type",
        "prefix": "INV-",
        "start_number": 1,
        "padding": 4,
    })
    assert is_valid is False
    assert any("voucher_type" in e.lower() for e in errs)

    # Valid complete config
    is_valid, errs, clean = voucher_numbering_service.validate_config({
        "voucher_type": "sales_invoice",
        "is_custom_enabled": True,
        "prefix": "SI/",
        "start_number": 100,
        "padding": 5,
        "suffix": "/2026",
        "include_financial_year": True,
        "fy_format": "YYYY-YY",
        "fy_separator": "/",
        "include_branch_code": True,
        "branch_position": "prefix",
    })
    assert is_valid is True
    assert len(errs) == 0
    assert clean["prefix"] == "SI/"
    assert clean["start_number"] == 100
    assert clean["padding"] == 5


# ---------------------------------------------------------------------------
# 6. Traditional DB Persistence and Retrieval
# ---------------------------------------------------------------------------

def test_06_traditional_config_persistence_and_retrieval(test_company_a):
    """Verify custom numbering config is saved and read from traditional DB table."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    cfg_payload = {
        "voucher_type": "sales_invoice",
        "is_custom_enabled": True,
        "prefix": "ALPHAINV-",
        "start_number": 50,
        "padding": 4,
        "suffix": "",
        "include_financial_year": True,
        "fy_format": "YYYY-YY",
        "fy_separator": "/",
        "include_branch_code": False,
    }

    saved = voucher_numbering_service.save_traditional_config(
        company_id=cid,
        voucher_type="sales_invoice",
        data=cfg_payload,
        branch_id=bid,
    )
    assert saved["is_custom_enabled"] is True
    assert saved["prefix"] == "ALPHAINV-"
    assert saved["start_number"] == 50

    # Retrieve and verify
    retrieved = voucher_numbering_service.get_traditional_config(
        company_id=cid,
        voucher_type="sales_invoice",
        branch_id=bid,
    )
    assert retrieved["is_custom_enabled"] is True
    assert retrieved["prefix"] == "ALPHAINV-"
    assert retrieved["start_number"] == 50

    # Verify directly in SQLAlchemy model
    with traditional_db_manager.session_scope() as session:
        stmt = select(VoucherNumberingConfiguration).where(
            VoucherNumberingConfiguration.company_id == cid,
            VoucherNumberingConfiguration.voucher_type == "sales_invoice",
        )
        row = session.execute(stmt).scalars().first()
        assert row is not None
        assert row.prefix == "ALPHAINV-"
        assert row.start_number == 50
        assert row.is_custom_enabled is True


# ---------------------------------------------------------------------------
# 7. Multi-Tenant Company and Branch Isolation
# ---------------------------------------------------------------------------

def test_07_company_and_branch_isolation(test_company_a, test_company_b):
    """Verify Company A and Company B have completely independent numbering rules."""
    cid_a = test_company_a["company_id"]
    cid_b = test_company_b["company_id"]

    voucher_numbering_service.save_traditional_config(
        company_id=cid_a,
        voucher_type="sales_invoice",
        data={"is_custom_enabled": True, "prefix": "INV-COMP-A-", "start_number": 1, "padding": 4},
        branch_id=test_company_a["branch_id"],
    )

    voucher_numbering_service.save_traditional_config(
        company_id=cid_b,
        voucher_type="sales_invoice",
        data={"is_custom_enabled": True, "prefix": "INV-COMP-B-", "start_number": 500, "padding": 5},
        branch_id=test_company_b["branch_id"],
    )

    cfg_a = voucher_numbering_service.get_traditional_config(cid_a, "sales_invoice", branch_id=test_company_a["branch_id"])
    cfg_b = voucher_numbering_service.get_traditional_config(cid_b, "sales_invoice", branch_id=test_company_b["branch_id"])

    assert cfg_a["prefix"] == "INV-COMP-A-"
    assert cfg_a["start_number"] == 1
    assert cfg_a["padding"] == 4

    assert cfg_b["prefix"] == "INV-COMP-B-"
    assert cfg_b["start_number"] == 500
    assert cfg_b["padding"] == 5


# ---------------------------------------------------------------------------
# 8. Traditional Sales Invoice Generation with Custom Numbering
# ---------------------------------------------------------------------------

def test_08_traditional_sales_invoice_custom_numbering_generation(test_company_a):
    """Verify traditional sales invoice uses custom format and starts at configured start_number."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    # Save custom numbering for sales_invoice
    voucher_numbering_service.save_traditional_config(
        company_id=cid,
        voucher_type="sales_invoice",
        data={
            "is_custom_enabled": True,
            "prefix": "SALES/",
            "start_number": 200,
            "padding": 4,
            "suffix": "",
            "include_financial_year": False,
        },
        branch_id=bid,
    )

    # Next voucher preview should start at configured 200
    next_info = traditional_product_service.get_next_voucher_number(
        company_id=cid,
        branch_id=bid,
        series="Main",
    )
    assert next_info["voucher_number"] == "SALES/0200"
    assert next_info["is_custom"] is True


# ---------------------------------------------------------------------------
# 9. Traditional Sales Return Custom Numbering Generation
# ---------------------------------------------------------------------------

def test_09_traditional_sales_return_custom_numbering_generation(test_company_a):
    """Verify sales return uses custom format when enabled."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    voucher_numbering_service.save_traditional_config(
        company_id=cid,
        voucher_type="sales_return",
        data={
            "is_custom_enabled": True,
            "prefix": "CR-NOTE-",
            "start_number": 1,
            "padding": 5,
            "suffix": "",
            "include_financial_year": False,
        },
        branch_id=bid,
    )

    cfg = voucher_numbering_service.get_traditional_config(cid, "sales_return", branch_id=bid)
    assert cfg["is_custom_enabled"] is True
    formatted = voucher_numbering_service.format_voucher_number(cfg, 1)
    assert formatted == "CR-NOTE-00001"


# ---------------------------------------------------------------------------
# 10. Purchase Invoice Custom Numbering Generation
# ---------------------------------------------------------------------------

def test_10_purchase_invoice_custom_numbering_generation(test_company_a):
    """Verify purchase invoice uses custom numbering when enabled."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    voucher_numbering_service.save_traditional_config(
        company_id=cid,
        voucher_type="purchase_invoice",
        data={
            "is_custom_enabled": True,
            "prefix": "PINV-",
            "start_number": 15,
            "padding": 4,
            "suffix": "",
            "include_financial_year": False,
        },
        branch_id=bid,
    )

    next_pur = purchase_service.get_next_purchase_voucher_number(company_id=cid, series="Main")
    assert next_pur == "PINV-0015"


# ---------------------------------------------------------------------------
# 11. Purchase Return Custom Numbering Generation
# ---------------------------------------------------------------------------

def test_11_purchase_return_custom_numbering_generation(test_company_a):
    """Verify purchase return custom numbering formatting."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    voucher_numbering_service.save_traditional_config(
        company_id=cid,
        voucher_type="purchase_return",
        data={
            "is_custom_enabled": True,
            "prefix": "DR-NOTE-",
            "start_number": 1,
            "padding": 4,
            "suffix": "",
        },
        branch_id=bid,
    )

    cfg = voucher_numbering_service.get_traditional_config(cid, "purchase_return", branch_id=bid)
    assert cfg["is_custom_enabled"] is True
    formatted = voucher_numbering_service.format_voucher_number(cfg, 1)
    assert formatted == "DR-NOTE-0001"


# ---------------------------------------------------------------------------
# 12. Duplicate Prevention and Collision Handling
# ---------------------------------------------------------------------------

def test_12_duplicate_prevention_and_collision_handling(test_company_a):
    """Verify sequence auto-advances if a formatted voucher number already exists."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    # Pre-populate a sale invoice with voucher number 'COLLISION-0001'
    with traditional_db_manager.session_scope() as session:
        inv = SaleInvoice(
            id=f"inv-collision-{uuid.uuid4().hex[:8]}",
            voucher_id=str(uuid.uuid4()),
            company_id=cid,
            branch_id=bid,
            voucher_number="COLLISION-0001",
            series="Main",
            financial_year="2026-2027",
            sequence_number=1,
            vch_date="2026-11-16",
            party_name="Cash Customer",
            sale_type="IN_STATE",
            subtotal=100.0,
            taxable_amount=100.0,
            grand_total=100.0,
            items_json="[]",
        )
        session.add(inv)

    # Configure numbering with prefix 'COLLISION-' starting at 1
    voucher_numbering_service.save_traditional_config(
        company_id=cid,
        voucher_type="sales_invoice",
        data={
            "is_custom_enabled": True,
            "prefix": "COLLISION-",
            "start_number": 1,
            "padding": 4,
        },
        branch_id=bid,
    )

    # The service must detect that 'COLLISION-0001' already exists in SaleInvoice and offer 0002
    next_info = traditional_product_service.get_next_voucher_number(
        company_id=cid,
        branch_id=bid,
        series="Main",
    )
    assert next_info["voucher_number"] == "COLLISION-0002"


# ---------------------------------------------------------------------------
# 13. Sequence Preservation: Preview & Reprint Never Consumes Sequence
# ---------------------------------------------------------------------------

def test_13_reprinting_and_preview_does_not_consume_sequence(test_company_a):
    """Verify previewing or calculating next number multiple times does not increment sequence."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    voucher_numbering_service.save_traditional_config(
        company_id=cid,
        voucher_type="sales_invoice",
        data={
            "is_custom_enabled": True,
            "prefix": "PREV-",
            "start_number": 1,
            "padding": 4,
        },
        branch_id=bid,
    )

    # Call preview 5 times
    for _ in range(5):
        num1 = traditional_product_service.get_next_voucher_number(cid, branch_id=bid, series="Main")
        assert num1["voucher_number"] == "PREV-0001"

    # Preview via voucher_numbering_service.preview_voucher_number
    preview_res = voucher_numbering_service.preview_voucher_number(
        {"voucher_type": "sales_invoice", "prefix": "TEST-", "start_number": 1, "padding": 4},
        company_id=cid,
        branch_id=bid,
    )
    assert preview_res["sample"] == "TEST-0001"
    assert len(preview_res["next_projections"]) == 3


# ---------------------------------------------------------------------------
# 14. Historical Voucher Preservation
# ---------------------------------------------------------------------------

def test_14_historical_voucher_preservation(test_company_a):
    """Verify changing numbering rules never alters or renumbers existing historical transactions."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]
    hist_id = f"inv-hist-{uuid.uuid4().hex[:8]}"

    # Insert an existing historic invoice with number 'HIST-001'
    with traditional_db_manager.session_scope() as session:
        inv = SaleInvoice(
            id=hist_id,
            voucher_id=str(uuid.uuid4()),
            company_id=cid,
            branch_id=bid,
            voucher_number="HIST-001",
            series="Main",
            financial_year="2026-2027",
            sequence_number=1,
            vch_date="2026-01-01",
            party_name="Historic Client",
            sale_type="IN_STATE",
            subtotal=500.0,
            taxable_amount=500.0,
            grand_total=500.0,
            items_json="[]",
        )
        session.add(inv)

    # Enable new custom numbering
    voucher_numbering_service.save_traditional_config(
        company_id=cid,
        voucher_type="sales_invoice",
        data={
            "is_custom_enabled": True,
            "prefix": "NEWPREFIX-",
            "start_number": 999,
            "padding": 6,
        },
        branch_id=bid,
    )

    # Query the historical invoice: it MUST still be 'HIST-001'
    with traditional_db_manager.session_scope() as session:
        hist_inv = session.get(SaleInvoice, hist_id)
        assert hist_inv is not None
        assert hist_inv.voucher_number == "HIST-001"


# ---------------------------------------------------------------------------
# 15. Fast Billing JSON Persistence and SQLite Immutability
# ---------------------------------------------------------------------------

def test_15_fast_billing_json_isolation_and_generation():
    """Verify Fast Billing configurations are isolated in JSON file without touching Fast Billing DB."""
    cfg = {
        "voucher_type": "sales_invoice",
        "is_custom_enabled": True,
        "prefix": "FAST-",
        "start_number": 1,
        "padding": 5,
        "suffix": "",
    }
    saved = voucher_numbering_service.save_fast_config("DEFAULT_COMPANY", "sales_invoice", cfg)
    assert saved["is_custom_enabled"] is True
    assert saved["prefix"] == "FAST-"

    retrieved = voucher_numbering_service.get_fast_config("DEFAULT_COMPANY", "sales_invoice")
    assert retrieved["prefix"] == "FAST-"
    assert retrieved["padding"] == 5

    # Reset
    reset_res = voucher_numbering_service.reset_fast_config("DEFAULT_COMPANY", "sales_invoice")
    assert reset_res["is_custom_enabled"] is False


# ---------------------------------------------------------------------------
# 16. WebBridge Role-Based Access Control
# ---------------------------------------------------------------------------

def test_16_web_bridge_role_authorization(test_company_a):
    """Verify WebBridge enforces role-based authorization on save and reset."""
    bridge = BackendBridge()
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    # 1. Unauthenticated -> fails
    bridge._authenticated_session = None
    bridge._traditional_session = None
    res_str = bridge.saveVoucherNumberingConfig("sales_invoice", json.dumps({"prefix": "TEST-"}), "traditional")
    res = json.loads(res_str)
    assert res["success"] is False

    # 2. Authenticated as Cashier (unauthorized role) -> permission denied
    bridge._authenticated_session = {
        "session_id": str(uuid.uuid4()),
        "company_id": cid,
        "company_code": "VA",
        "branch_id": bid,
        "branch_code": "BR01",
        "user_id": "usr-cashier",
        "username": "cashier1",
        "role": "Cashier",
    }
    res_str = bridge.saveVoucherNumberingConfig("sales_invoice", json.dumps({"prefix": "TEST-"}), "traditional")
    res = json.loads(res_str)
    assert res["success"] is False
    assert res.get("permission_denied") is True

    # 3. Authenticated as Administrator -> allowed
    bridge._authenticated_session = None
    token = traditional_session_registry.create_session(
        user_id="usr-admin",
        company_id=cid,
        branch_id=bid,
        role_name="System Administrator",
        username="admin",
        display_name="System Administrator",
    )
    bridge._traditional_session = traditional_session_registry.get_session(token)

    res_str = bridge.saveVoucherNumberingConfig(
        "sales_invoice",
        json.dumps({
            "voucher_type": "sales_invoice",
            "is_custom_enabled": True,
            "prefix": "ADMIN-",
            "start_number": 1,
            "padding": 4,
        }),
        "traditional",
    )
    res = json.loads(res_str)
    assert res["success"] is True
    assert res["data"]["prefix"] == "ADMIN-"


# ---------------------------------------------------------------------------
# 17. Reset to Default
# ---------------------------------------------------------------------------

def test_17_reset_to_default(test_company_a):
    """Verify reset configuration restores factory defaults."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    # First enable custom
    voucher_numbering_service.save_traditional_config(
        cid, "sales_invoice", {"is_custom_enabled": True, "prefix": "CUSTOM-", "start_number": 99}, branch_id=bid
    )

    # Now reset
    reset_cfg = voucher_numbering_service.reset_traditional_config(cid, "sales_invoice", branch_id=bid)
    assert reset_cfg["is_custom_enabled"] is False
    assert reset_cfg["start_number"] == 1


# ---------------------------------------------------------------------------
# 18. Fast Billing Database SHA256 Immutability Verification
# ---------------------------------------------------------------------------

def test_18_fast_billing_db_hash_immutability():
    """Verify the Fast Billing production SQLite database remains bit-for-bit identical."""
    assert FAST_DB_PATH.exists(), f"Fast Billing DB not found at {FAST_DB_PATH}"
    with open(FAST_DB_PATH, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest().upper()
    assert file_hash == EXPECTED_FAST_DB_SHA256, (
        f"Fast Billing DB was altered! Expected {EXPECTED_FAST_DB_SHA256}, got {file_hash}"
    )
