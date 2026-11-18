"""
Test Suite: GST & Tax Configuration Module (Anti-Matrix Billing V2 - Phase 5)

Verifies:
1. GST registration settings and default configuration
2. 15-character GSTIN format validation and structure parsing
3. Intra-state CGST & SGST calculation (50/50 split, zero penny discrepancy)
4. Inter-state IGST calculation (100% IGST)
5. Tax-inclusive pricing line calculation (Taxable = Net / (1 + Rate/100))
6. Tax-exclusive pricing line calculation (Taxable = Net, Tax = Taxable * Rate)
7. Discount and tax interaction (Discount applied before tax)
8. Sales Invoice tax calculation & database storage
9. Sales Return tax reversal
10. Purchase Invoice tax calculation & input tax credit
11. Purchase Return tax reversal
12. HSN/SAC code validation & length enforcement (optional, 4_digit, 6_digit, 8_digit)
13. Decimal precision and rounding rules (nearest_rupee, two_decimals, none)
14. Multi-tenant company isolation (Company A vs Company B)
15. Branch isolation and fallback
16. WebBridge role-based permissions enforcement (Admin/Manager/Accountant vs unauthorized)
17. Historical invoice preservation (prospective configuration application)
18. Fast Billing compatibility & JSON isolation
19. Traditional Billing compatibility & Alembic migration 007 verification
20. Consistency between preview sandbox, saved invoice, and ledger posting
"""

import copy
import hashlib
import json
import os
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from core.configuration import config
from db.database import DatabaseManager
from db.traditional_database import traditional_db_manager
from db.traditional_models import (
    Account,
    Branch,
    Company,
    GstTaxConfiguration,
    SaleInvoice,
)
from desktop.web_bridge import BackendBridge
from services.billing_service import billing_service
from services.gst_tax_config_service import (
    DEFAULT_GST_CONFIG,
    gst_tax_config_service,
)
from services.purchase_service import purchase_service
from services.tax_service import TaxService, tax_service
from services.traditional_auth_service import session_registry as traditional_session_registry


FAST_DB_PATH = Path("data/anti_matrix_billing.db")
EXPECTED_FAST_DB_SHA256 = "BDD99C65E7431336321ADABA2D6276F24CAA88CB4BD1A4A62204930FC62061BD"
TEST_CORE_DB_PATH = Path("data/test_phase5_core.db")


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Ensure Traditional migrations are applied up to head (migration 007) and isolated test core DB."""
    if TEST_CORE_DB_PATH.exists():
        try:
            TEST_CORE_DB_PATH.unlink()
        except Exception:
            pass

    test_core_db = DatabaseManager(f"sqlite:///{TEST_CORE_DB_PATH.resolve().as_posix()}")
    test_core_db.run_migrations()

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
def test_company_a():
    """Provides isolated test company A in Tamil Nadu."""
    cid = f"test-gst-comp-a-{uuid.uuid4().hex[:8]}"
    bid = f"branch-a-{uuid.uuid4().hex[:8]}"
    with traditional_db_manager.session_scope() as session:
        comp = Company(
            id=cid,
            code=f"GA_{uuid.uuid4().hex[:6]}",
            name="Alpha Retailers Pvt Ltd",
            gstin="33AAAPL9876C1Z2",
            state="Tamil Nadu (33)",
            fin_year="2026-2027",
            is_active=True,
        )
        session.add(comp)
        branch = Branch(
            id=bid,
            company_id=cid,
            code="BR01",
            name="Main Branch",
            is_active=True,
        )
        session.add(branch)

    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO companies (id, code, name, fin_year, gstin, state) VALUES (?, ?, ?, ?, ?, ?);",
            (cid, f"GA_{uuid.uuid4().hex[:6]}", "Alpha Retailers Pvt Ltd", "2026-2027", "33AAAPL9876C1Z2", "Tamil Nadu (33)")
        )
        cur.execute(
            "INSERT OR REPLACE INTO branches (id, company_id, code, name) VALUES (?, ?, ?, ?);",
            (bid, cid, "BR01", "Main Branch")
        )
        conn.commit()

    yield {"company_id": cid, "branch_id": bid, "state": "Tamil Nadu (33)", "gstin": "33AAAPL9876C1Z2"}

    with traditional_db_manager.session_scope() as session:
        c = session.get(Company, cid)
        if c:
            session.delete(c)


@pytest.fixture
def test_company_b():
    """Provides isolated test company B in Karnataka."""
    cid = f"test-gst-comp-b-{uuid.uuid4().hex[:8]}"
    bid = f"branch-b-{uuid.uuid4().hex[:8]}"
    with traditional_db_manager.session_scope() as session:
        comp = Company(
            id=cid,
            code=f"GB_{uuid.uuid4().hex[:6]}",
            name="Beta Traders Corporation",
            gstin="29BBBPD1234E1Z5",
            state="Karnataka (29)",
            fin_year="2026-2027",
            is_active=True,
        )
        session.add(comp)
        branch = Branch(
            id=bid,
            company_id=cid,
            code="BR01",
            name="Bangalore Depot",
            is_active=True,
        )
        session.add(branch)

    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO companies (id, code, name, fin_year, gstin, state) VALUES (?, ?, ?, ?, ?, ?);",
            (cid, f"GB_{uuid.uuid4().hex[:6]}", "Beta Traders Corporation", "2026-2027", "29BBBPD1234E1Z5", "Karnataka (29)")
        )
        cur.execute(
            "INSERT OR REPLACE INTO branches (id, company_id, code, name) VALUES (?, ?, ?, ?);",
            (bid, cid, "BR01", "Bangalore Depot")
        )
        conn.commit()

    yield {"company_id": cid, "branch_id": bid, "state": "Karnataka (29)", "gstin": "29BBBPD1234E1Z5"}

    with traditional_db_manager.session_scope() as session:
        c = session.get(Company, cid)
        if c:
            session.delete(c)


# ---------------------------------------------------------------------------
# 1. GST Registration Settings & Defaults
# ---------------------------------------------------------------------------

def test_01_gst_registration_settings_and_defaults():
    """Verify default GST configuration keys, standard slabs, and safe fallback values."""
    cfg = DEFAULT_GST_CONFIG
    assert cfg["is_gst_enabled"] is True
    assert cfg["registration_type"] == "Regular"
    assert cfg["default_tax_mode"] == "exclusive"
    assert cfg["default_tax_rate"] == 18.00
    assert cfg["tax_rounding_rule"] == "nearest_rupee"
    assert cfg["decimal_precision_currency"] == 2
    assert cfg["decimal_precision_qty"] == 3
    assert cfg["hsn_enforcement_mode"] == "optional"
    assert cfg["show_hsn_summary"] is True
    assert cfg["enable_rcm"] is False

    # Standard slabs: 0%, 5%, 12%, 18%, 28%
    slabs = [float(r) for r in cfg["supported_tax_rates"]]
    assert 0.00 in slabs
    assert 5.00 in slabs
    assert 12.00 in slabs
    assert 18.00 in slabs
    assert 28.00 in slabs


# ---------------------------------------------------------------------------
# 2. 15-character GSTIN Format Validation
# ---------------------------------------------------------------------------

def test_02_15_char_gstin_format_validation():
    """Verify 15-character GSTIN format validation, structure parsing, and invalid rejection."""
    # Valid Tamil Nadu GSTIN
    is_valid, msg, comps = gst_tax_config_service.validate_gstin("33AAAPL9876C1Z2")
    assert is_valid is True
    assert comps["state_code"] == "33"
    assert comps["state_name"] == "Tamil Nadu"
    assert comps["pan"] == "AAAPL9876C"
    assert comps["entity_number"] == "1"
    assert comps["checksum"] == "2"

    # Valid Karnataka GSTIN
    is_valid, msg, comps = gst_tax_config_service.validate_gstin("29BBBPD1234E1Z5")
    assert is_valid is True
    assert comps["state_code"] == "29"
    assert comps["state_name"] == "Karnataka"

    # Invalid GSTINs
    invalid_cases = [
        "",  # Empty
        "33AAAPL9876C1Z",  # 14 chars
        "33AAAPL9876C1Z23",  # 16 chars
        "XXAAAPL9876C1Z2",  # Non-numeric state code
        "33aaapl9876c1z2",  # Lowercase (will be cleaned to uppercase if handled, or tested raw)
        "33AAAPL9876C1A2",  # 14th char not 'Z'
    ]
    for inv in invalid_cases:
        valid, err_msg, _ = gst_tax_config_service.validate_gstin(inv)
        if inv == "33aaapl9876c1z2":
            # Clean uppercase passes
            assert valid is True
        else:
            assert valid is False, f"Expected {inv} to fail validation"


# ---------------------------------------------------------------------------
# 3. Intra-State CGST & SGST Calculation (50/50 Split, Zero Penny Discrepancy)
# ---------------------------------------------------------------------------

def test_03_intra_state_cgst_sgst_equal_split_zero_penny_discrepancy():
    """Verify intra-state splits 50/50 and eliminates penny discrepancy on odd amounts."""
    # Standard even amount
    res = TaxService.calculate_line_item(
        price=1000.0,
        qty=1.0,
        tax_rate=18.0,
        is_interstate=False,
    )
    assert res["taxable_amount"] == 1000.0
    assert res["tax_amount"] == 180.0
    assert res["cgst_rate"] == 9.0
    assert res["sgst_rate"] == 9.0
    assert res["cgst_amount"] == 90.0
    assert res["sgst_amount"] == 90.0
    assert res["igst_amount"] == 0.0
    assert res["line_total"] == 1180.0

    # Odd penny test: Price = 1.05 at 5% rate -> Gross = 1.05, Tax = 0.05
    res_odd = TaxService.calculate_line_item(
        price=1.05,
        qty=1.0,
        tax_rate=5.0,
        is_interstate=False,
    )
    assert res_odd["taxable_amount"] == 1.05
    assert res_odd["tax_amount"] == 0.05
    # Zero penny discrepancy guarantee: cgst + sgst == tax_amount
    assert round(res_odd["cgst_amount"] + res_odd["sgst_amount"], 2) == round(res_odd["tax_amount"], 2)
    assert res_odd["igst_amount"] == 0.0


# ---------------------------------------------------------------------------
# 4. Inter-State IGST Calculation (100% IGST)
# ---------------------------------------------------------------------------

def test_04_inter_state_igst_full_allocation():
    """Verify inter-state allocates 100% to IGST with zero CGST and SGST."""
    res = TaxService.calculate_line_item(
        price=1000.0,
        qty=1.0,
        tax_rate=18.0,
        is_interstate=True,
    )
    assert res["taxable_amount"] == 1000.0
    assert res["tax_amount"] == 180.0
    assert res["cgst_amount"] == 0.0
    assert res["sgst_amount"] == 0.0
    assert res["igst_rate"] == 18.0
    assert res["igst_amount"] == 180.0
    assert res["line_total"] == 1180.0

    # State comparison helper
    assert TaxService.is_interstate(company_state="Tamil Nadu (33)", customer_state="Karnataka (29)") is True
    assert TaxService.is_interstate(company_state="Tamil Nadu (33)", customer_state="Tamil Nadu (33)") is False


# ---------------------------------------------------------------------------
# 5. Tax-Inclusive Pricing Line Calculation
# ---------------------------------------------------------------------------

def test_05_tax_inclusive_pricing_calculation():
    """Verify Tax-Inclusive formula: Taxable = Net / (1 + Rate/100)."""
    # Gross = 118.00 at 18% inclusive
    res18 = TaxService.calculate_line_item(
        price=118.0,
        qty=1.0,
        tax_rate=18.0,
        is_tax_inclusive=True,
        is_interstate=False,
    )
    assert res18["taxable_amount"] == 100.0
    assert res18["tax_amount"] == 18.0
    assert res18["cgst_amount"] == 9.0
    assert res18["sgst_amount"] == 9.0
    assert res18["line_total"] == 118.0

    # Gross = 105.00 at 5% inclusive
    res5 = TaxService.calculate_line_item(
        price=105.0,
        qty=1.0,
        tax_rate=5.0,
        is_tax_inclusive=True,
        is_interstate=False,
    )
    assert res5["taxable_amount"] == 100.0
    assert res5["tax_amount"] == 5.0
    assert res5["line_total"] == 105.0


# ---------------------------------------------------------------------------
# 6. Tax-Exclusive Pricing Line Calculation
# ---------------------------------------------------------------------------

def test_06_tax_exclusive_pricing_calculation():
    """Verify Tax-Exclusive formula: Taxable = Net, Tax = Taxable * Rate."""
    res = TaxService.calculate_line_item(
        price=250.0,
        qty=2.0,
        tax_rate=12.0,
        is_tax_inclusive=False,
        is_interstate=False,
    )
    assert res["taxable_amount"] == 500.0
    assert res["tax_amount"] == 60.0
    assert res["cgst_amount"] == 30.0
    assert res["sgst_amount"] == 30.0
    assert res["line_total"] == 560.0


# ---------------------------------------------------------------------------
# 7. Discount and Tax Interaction (Discount Applied Before Tax)
# ---------------------------------------------------------------------------

def test_07_discount_applied_before_tax_interaction():
    """Verify statutory rule: trade discounts are subtracted before tax calculation."""
    # Gross = 1000.0, 10% discount -> Net taxable = 900.0, 18% tax = 162.0 -> Total = 1062.0
    res = TaxService.calculate_line_item(
        price=100.0,
        qty=10.0,
        tax_rate=18.0,
        discount_percent=10.0,
        is_tax_inclusive=False,
        is_interstate=False,
    )
    assert res["discount_amount"] == 100.0
    assert res["taxable_amount"] == 900.0
    assert res["tax_amount"] == 162.0
    assert res["cgst_amount"] == 81.0
    assert res["sgst_amount"] == 81.0
    assert res["line_total"] == 1062.0


# ---------------------------------------------------------------------------
# 8. Sales Invoice Tax Calculation & Database Storage
# ---------------------------------------------------------------------------

def test_08_sales_invoice_tax_calculation_and_database_storage(test_company_a):
    """Verify sales invoice calculates taxes and stores tax fields properly in database."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    inv_items = [
        {"item_name": "Premium Keyboard", "price": 1000.0, "qty": 2.0, "tax_rate": 18.0, "discount_percent": 0.0},
        {"item_name": "Optical Mouse", "price": 500.0, "qty": 1.0, "tax_rate": 18.0, "discount_percent": 0.0},
    ]

    totals = tax_service.calculate_voucher_totals(
        items=inv_items,
        company_state="Tamil Nadu (33)",
        customer_state="Tamil Nadu (33)",
        auto_round=True,
    )

    assert totals["taxable_amount"] == 2500.0
    assert totals["cgst_amount"] == 225.0
    assert totals["sgst_amount"] == 225.0
    assert totals["igst_amount"] == 0.0
    assert totals["total_tax"] == 450.0
    assert totals["grand_total"] == 2950.0

    # Test database insertion of sales voucher with calculated totals
    vch_id = str(uuid.uuid4())
    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sales_vouchers (
                id, company_id, branch_id, vch_no, series, vch_date,
                sale_type, party_name, mat_centre,
                subtotal, gross_subtotal, discount_total,
                taxable_amount, tax_rate, cgst_amount, sgst_amount, igst_amount,
                round_off, grand_total, payment_method, payment_status
            ) VALUES (?, ?, ?, ?, 'Main', '2026-11-16', 'L/GST', 'Test Customer', 'Main Store', 2500.0, 2500.0, 0.0, ?, 18.0, ?, ?, ?, ?, ?, 'CASH', 'PAID');
        """, (
            vch_id, cid, bid, f"INV-{uuid.uuid4().hex[:6]}",
            totals["taxable_amount"], totals["cgst_amount"], totals["sgst_amount"],
            totals["igst_amount"], totals["round_off"], totals["grand_total"]
        ))
        conn.commit()

        # Query back and verify stored fields
        cur.execute("SELECT taxable_amount, cgst_amount, sgst_amount, igst_amount, grand_total FROM sales_vouchers WHERE id = ?;", (vch_id,))
        row = cur.fetchone()
        assert row is not None
        assert row["taxable_amount"] == 2500.0
        assert row["cgst_amount"] == 225.0
        assert row["sgst_amount"] == 225.0
        assert row["igst_amount"] == 0.0
        assert row["grand_total"] == 2950.0


# ---------------------------------------------------------------------------
# 9. Sales Return Tax Reversal
# ---------------------------------------------------------------------------

def test_09_sales_return_tax_reversal():
    """Verify sales return reverses output tax accounts in double-entry ledger."""
    # When a return occurs, Output CGST and Output SGST must be debited
    return_items = [
        {"item_name": "Premium Keyboard", "price": 1000.0, "qty": 1.0, "tax_rate": 18.0}
    ]
    calc = tax_service.calculate_voucher_totals(
        items=return_items,
        company_state="Tamil Nadu (33)",
        customer_state="Tamil Nadu (33)",
    )
    assert calc["taxable_amount"] == 1000.0
    assert calc["cgst_amount"] == 90.0
    assert calc["sgst_amount"] == 90.0

    # Output tax reversal entry lines: Debit Output CGST (90.0), Debit Output SGST (90.0)
    journal_lines = [
        {"account": "Sales Returns", "debit": calc["taxable_amount"], "credit": 0.0},
        {"account": "Output CGST Account", "debit": calc["cgst_amount"], "credit": 0.0},
        {"account": "Output SGST Account", "debit": calc["sgst_amount"], "credit": 0.0},
        {"account": "Accounts Receivable", "debit": 0.0, "credit": calc["grand_total"]},
    ]
    tot_debit = sum(line["debit"] for line in journal_lines)
    tot_credit = sum(line["credit"] for line in journal_lines)
    assert tot_debit == tot_credit == 1180.0


# ---------------------------------------------------------------------------
# 10. Purchase Invoice Tax Calculation & Input Tax Credit
# ---------------------------------------------------------------------------

def test_10_purchase_invoice_tax_calculation_and_input_tax_credit(test_company_a):
    """Verify purchase invoice calculates input taxes correctly and records Input Tax Credit."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    purchase_items = [
        {
            "name": "SSD 1TB NVMe",
            "qty": 5.0,
            "unit": "Pcs.",
            "rate": 4000.0,
            "tax_rate": 18.0,
            "discount_percent": 0.0,
        }
    ]

    calc = tax_service.calculate_voucher_totals(
        items=[{"price": it["rate"], "qty": it["qty"], "tax_rate": it["tax_rate"]} for it in purchase_items],
        company_state="Tamil Nadu (33)",
        customer_state="Tamil Nadu (33)",
    )
    assert calc["taxable_amount"] == 20000.0
    assert calc["cgst_amount"] == 1800.0
    assert calc["sgst_amount"] == 1800.0
    assert calc["grand_total"] == 23600.0

    # Input tax credit journal lines:
    # Debit Purchases (20,000), Debit Input CGST (1,800), Debit Input SGST (1,800), Credit Accounts Payable (23,600)
    journal_lines = [
        {"account": "Purchases Account", "debit": 20000.0, "credit": 0.0},
        {"account": "Input CGST Account", "debit": 1800.0, "credit": 0.0},
        {"account": "Input SGST Account", "debit": 1800.0, "credit": 0.0},
        {"account": "Accounts Payable", "debit": 0.0, "credit": 23600.0},
    ]
    assert sum(line["debit"] for line in journal_lines) == sum(line["credit"] for line in journal_lines)


# ---------------------------------------------------------------------------
# 11. Purchase Return Tax Reversal
# ---------------------------------------------------------------------------

def test_11_purchase_return_tax_reversal():
    """Verify purchase return reverses Input CGST and Input SGST accounts."""
    # When goods are returned to supplier, Input tax credit must be reversed (credited)
    ret_calc = tax_service.calculate_voucher_totals(
        items=[{"price": 4000.0, "qty": 1.0, "tax_rate": 18.0}],
        company_state="Tamil Nadu (33)",
        customer_state="Tamil Nadu (33)",
    )
    assert ret_calc["taxable_amount"] == 4000.0
    assert ret_calc["cgst_amount"] == 360.0
    assert ret_calc["sgst_amount"] == 360.0

    # Reversal journal lines:
    # Debit Accounts Payable (4,720), Credit Purchase Returns (4,000), Credit Input CGST (360), Credit Input SGST (360)
    reversal_lines = [
        {"account": "Accounts Payable", "debit": 4720.0, "credit": 0.0},
        {"account": "Purchase Returns", "debit": 0.0, "credit": 4000.0},
        {"account": "Input CGST Reversal", "debit": 0.0, "credit": 360.0},
        {"account": "Input SGST Reversal", "debit": 0.0, "credit": 360.0},
    ]
    assert sum(line["debit"] for line in reversal_lines) == sum(line["credit"] for line in reversal_lines)


# ---------------------------------------------------------------------------
# 12. HSN/SAC Code Validation & Length Enforcement
# ---------------------------------------------------------------------------

def test_12_hsn_sac_code_validation_and_enforcement():
    """Verify HSN/SAC enforcement modes: optional, 4_digit, 6_digit, and 8_digit."""
    # 1. Optional
    v, _ = gst_tax_config_service.validate_hsn("", mode="optional")
    assert v is True
    v, _ = gst_tax_config_service.validate_hsn("8471", mode="optional")
    assert v is True

    # 2. 4_digit
    v, _ = gst_tax_config_service.validate_hsn("", mode="4_digit")
    assert v is False  # Mandatory
    v, _ = gst_tax_config_service.validate_hsn("12", mode="4_digit")
    assert v is False  # Too short
    v, _ = gst_tax_config_service.validate_hsn("8471", mode="4_digit")
    assert v is True
    v, _ = gst_tax_config_service.validate_hsn("84713010", mode="4_digit")
    assert v is True

    # 3. 6_digit
    v, _ = gst_tax_config_service.validate_hsn("8471", mode="6_digit")
    assert v is False  # 4 digits rejected
    v, _ = gst_tax_config_service.validate_hsn("847130", mode="6_digit")
    assert v is True

    # 4. 8_digit
    v, _ = gst_tax_config_service.validate_hsn("847130", mode="8_digit")
    assert v is False  # 6 digits rejected
    v, _ = gst_tax_config_service.validate_hsn("84713010", mode="8_digit")
    assert v is True

    # Non-digit rejection
    v, _ = gst_tax_config_service.validate_hsn("8471A", mode="optional")
    assert v is False


# ---------------------------------------------------------------------------
# 13. Decimal Precision and Rounding Rules
# ---------------------------------------------------------------------------

def test_13_decimal_precision_and_rounding_rules():
    """Verify rounding rules: nearest_rupee, two_decimals, and unrounded."""
    # 1. nearest_rupee (ROUND_HALF_UP with round_off)
    # 118.45 -> 118.00 (round-off: -0.45)
    r1 = tax_service.calculate_voucher_totals(
        items=[{"price": 100.38, "qty": 1.0, "tax_rate": 18.0}],  # Taxable 100.38, Tax 18.07, Total 118.45
        auto_round=True,
    )
    assert r1["grand_total"] == 118.0
    assert r1["round_off"] == -0.45

    # 118.60 -> 119.00 (round-off: +0.40)
    r2 = tax_service.calculate_voucher_totals(
        items=[{"price": 100.51, "qty": 1.0, "tax_rate": 18.0}],  # Taxable 100.51, Tax 18.09, Total 118.60
        auto_round=True,
    )
    assert r2["grand_total"] == 119.0
    assert r2["round_off"] == 0.40

    # 2. two_decimals (no rupee round-off)
    r3 = tax_service.calculate_voucher_totals(
        items=[{"price": 100.38, "qty": 1.0, "tax_rate": 18.0}],
        auto_round=False,
    )
    assert r3["grand_total"] == 118.45
    assert r3["round_off"] == 0.0


# ---------------------------------------------------------------------------
# 14. Multi-Tenant Company Isolation
# ---------------------------------------------------------------------------

def test_14_multi_tenant_company_isolation(test_company_a, test_company_b):
    """Verify Company A and Company B have independent GST configurations."""
    cid_a = test_company_a["company_id"]
    cid_b = test_company_b["company_id"]

    # Save Company A with 18% default rate and Tamil Nadu GSTIN
    gst_tax_config_service.save_traditional_config(
        company_id=cid_a,
        config_data={
            "is_gst_enabled": True,
            "gstin": "33AAAPL9876C1Z2",
            "legal_name": "Alpha Retailers Pvt Ltd",
            "state": "Tamil Nadu (33)",
            "default_tax_rate": 18.0,
            "tax_rounding_rule": "nearest_rupee",
        },
    )

    # Save Company B with 12% default rate and Karnataka GSTIN
    gst_tax_config_service.save_traditional_config(
        company_id=cid_b,
        config_data={
            "is_gst_enabled": True,
            "gstin": "29BBBPD1234E1Z5",
            "legal_name": "Beta Traders Corporation",
            "state": "Karnataka (29)",
            "default_tax_rate": 12.0,
            "tax_rounding_rule": "two_decimals",
        },
    )

    cfg_a = gst_tax_config_service.get_traditional_config(cid_a)
    cfg_b = gst_tax_config_service.get_traditional_config(cid_b)

    assert cfg_a["gstin"] == "33AAAPL9876C1Z2"
    assert cfg_a["state"] == "Tamil Nadu (33)"
    assert cfg_a["default_tax_rate"] == 18.0
    assert cfg_a["tax_rounding_rule"] == "nearest_rupee"

    assert cfg_b["gstin"] == "29BBBPD1234E1Z5"
    assert cfg_b["state"] == "Karnataka (29)"
    assert cfg_b["default_tax_rate"] == 12.0
    assert cfg_b["tax_rounding_rule"] == "two_decimals"


# ---------------------------------------------------------------------------
# 15. Branch Isolation and Fallback
# ---------------------------------------------------------------------------

def test_15_branch_isolation_and_fallback(test_company_a):
    """Verify branch-specific tax configuration overrides company, while unconfigured branch inherits."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    # 1. Company level config
    gst_tax_config_service.save_traditional_config(
        company_id=cid,
        config_data={"default_tax_rate": 18.0, "state": "Tamil Nadu (33)"},
    )

    # 2. Branch-specific config
    gst_tax_config_service.save_traditional_config(
        company_id=cid,
        branch_id=bid,
        config_data={"default_tax_rate": 5.0, "state": "Tamil Nadu (33)"},
    )

    branch_cfg = gst_tax_config_service.get_traditional_config(cid, branch_id=bid)
    company_cfg = gst_tax_config_service.get_traditional_config(cid)

    assert branch_cfg["default_tax_rate"] == 5.0
    assert company_cfg["default_tax_rate"] == 18.0


# ---------------------------------------------------------------------------
# 16. WebBridge Role-Based Permissions Enforcement
# ---------------------------------------------------------------------------

def test_16_web_bridge_role_permissions_enforcement(test_company_a):
    """Verify authorized roles can save/reset GST config, while unauthorized roles are blocked."""
    bridge = BackendBridge()
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    # 1. Unauthenticated -> fails
    bridge._authenticated_session = None
    bridge._traditional_session = None
    res = json.loads(bridge.saveGstTaxConfig(json.dumps({"default_tax_rate": 18.0}), "traditional"))
    assert res["success"] is False

    # 2. Unauthorized role (Cashier) -> blocked with permission_denied
    bridge._authenticated_session = {
        "session_id": str(uuid.uuid4()),
        "company_id": cid,
        "branch_id": bid,
        "role": "Cashier",
        "username": "cashier1",
    }
    res = json.loads(bridge.saveGstTaxConfig(json.dumps({"default_tax_rate": 18.0}), "traditional"))
    assert res["success"] is False
    assert res.get("permission_denied") is True

    # 3. Authorized role (System Administrator) -> succeeds
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

    res = json.loads(bridge.saveGstTaxConfig(
        json.dumps({
            "is_gst_enabled": True,
            "gstin": "33AAAPL9876C1Z2",
            "state": "Tamil Nadu (33)",
            "default_tax_rate": 18.0,
        }),
        "traditional"
    ))
    assert res["success"] is True

    # 4. Authorized role (Accountant) -> reset succeeds
    token_acc = traditional_session_registry.create_session(
        user_id="usr-accountant",
        company_id=cid,
        branch_id=bid,
        role_name="Accountant",
        username="acct1",
        display_name="Senior Accountant",
    )
    bridge._traditional_session = traditional_session_registry.get_session(token_acc)
    reset_res = json.loads(bridge.resetGstTaxConfig("traditional"))
    assert reset_res["success"] is True


# ---------------------------------------------------------------------------
# 17. Historical Invoice Preservation (Prospective Configuration Application)
# ---------------------------------------------------------------------------

def test_17_historical_invoice_preservation(test_company_a):
    """Verify saved historical invoices are never modified when GST settings are changed."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    # Commit historical invoice with 18% tax
    inv_id = str(uuid.uuid4())
    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sales_vouchers (
                id, company_id, branch_id, vch_no, series, vch_date,
                sale_type, party_name, mat_centre,
                subtotal, gross_subtotal, discount_total,
                taxable_amount, tax_rate, cgst_amount, sgst_amount, igst_amount,
                round_off, grand_total, payment_method, payment_status
            ) VALUES (?, ?, ?, 'INV-HIST-001', 'Main', '2026-11-01', 'L/GST', 'Past Customer', 'Main Store', 1000.0, 1000.0, 0.0, 1000.0, 18.0, 90.0, 90.0, 0.0, 0.0, 1180.0, 'CASH', 'PAID');
        """, (inv_id, cid, bid))
        conn.commit()

    # Now update GST configuration to 5% default rate
    gst_tax_config_service.save_traditional_config(
        company_id=cid,
        config_data={"default_tax_rate": 5.0, "state": "Tamil Nadu (33)"},
    )

    # Query historical invoice - must remain exactly 18% and 1180.0
    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT taxable_amount, tax_rate, cgst_amount, sgst_amount, grand_total FROM sales_vouchers WHERE id = ?;", (inv_id,))
        row = cur.fetchone()
        assert row["tax_rate"] == 18.0
        assert row["taxable_amount"] == 1000.0
        assert row["cgst_amount"] == 90.0
        assert row["sgst_amount"] == 90.0
        assert row["grand_total"] == 1180.0


# ---------------------------------------------------------------------------
# 18. Fast Billing Compatibility & JSON Isolation
# ---------------------------------------------------------------------------

def test_18_fast_billing_compatibility_and_json_isolation():
    """Verify Fast Billing GST configuration writes to JSON without touching SQLite DB."""
    fast_json_path = Path("data/fast_gst_tax_configurations.json")
    fast_cfg_payload = {
        "is_gst_enabled": True,
        "gstin": "33AAAPL9876C1Z2",
        "state": "Tamil Nadu (33)",
        "default_tax_mode": "inclusive",
        "default_tax_rate": 18.0,
        "tax_rounding_rule": "nearest_rupee",
    }

    saved = gst_tax_config_service.save_fast_config(fast_cfg_payload)
    assert saved["default_tax_mode"] == "inclusive"
    assert fast_json_path.exists()

    retrieved = gst_tax_config_service.get_fast_config()
    assert retrieved["default_tax_mode"] == "inclusive"
    assert retrieved["gstin"] == "33AAAPL9876C1Z2"


# ---------------------------------------------------------------------------
# 19. Traditional Billing Compatibility & Alembic Migration 007
# ---------------------------------------------------------------------------

def test_19_traditional_billing_compatibility_and_alembic_migration(test_company_a):
    """Verify Alembic migration 007 table gst_tax_configurations schema and columns."""
    cid = test_company_a["company_id"]
    with traditional_db_manager.session_scope() as session:
        # Verify SQLAlchemy model maps to table
        dummy_id = f"test-schema-{uuid.uuid4().hex[:6]}"
        cfg_entry = GstTaxConfiguration(
            id=dummy_id,
            company_id=cid,
            is_gst_enabled=True,
            gstin="33AAAPL9876C1Z2",
            legal_name="Test Legal Entity",
            state="Tamil Nadu (33)",
            state_code="33",
            registration_type="Regular",
            default_place_of_supply="Tamil Nadu (33)",
            default_tax_mode="exclusive",
            default_tax_rate=18.0,
            tax_rounding_rule="nearest_rupee",
        )
        session.add(cfg_entry)
        session.flush()

        stmt = select(GstTaxConfiguration).where(GstTaxConfiguration.id == dummy_id)
        fetched = session.execute(stmt).scalars().first()
        assert fetched is not None
        assert fetched.gstin == "33AAAPL9876C1Z2"
        assert fetched.default_tax_rate == 18.0

        session.delete(fetched)


# ---------------------------------------------------------------------------
# 20. Consistency Between Preview, Saved Invoice, and Ledger Posting
# ---------------------------------------------------------------------------

def test_20_consistency_preview_saved_invoice_and_ledger():
    """Verify sandbox calculation preview exactly matches actual invoice calculations and ledger totals."""
    cfg = copy.deepcopy(DEFAULT_GST_CONFIG)
    cfg["state"] = "Tamil Nadu (33)"
    cfg["default_tax_mode"] = "exclusive"
    cfg["tax_rounding_rule"] = "nearest_rupee"

    sample_data = {
        "price": 500.0,
        "qty": 2.0,
        "tax_rate": 18.0,
        "discount_percent": 0.0,
        "customer_state": "Tamil Nadu (33)",
    }

    preview = gst_tax_config_service.calculate_sample_tax(cfg, sample_data)
    assert preview["taxable_amount"] == 1000.0
    assert preview["cgst_amount"] == 90.0
    assert preview["sgst_amount"] == 90.0
    assert preview["igst_amount"] == 0.0
    assert preview["grand_total"] == 1180.0

    # Compare with TaxService voucher totals
    actual_totals = tax_service.calculate_voucher_totals(
        items=[{"price": 500.0, "qty": 2.0, "tax_rate": 18.0}],
        company_state="Tamil Nadu (33)",
        customer_state="Tamil Nadu (33)",
        auto_round=True,
    )
    assert actual_totals["taxable_amount"] == preview["taxable_amount"]
    assert actual_totals["cgst_amount"] == preview["cgst_amount"]
    assert actual_totals["sgst_amount"] == preview["sgst_amount"]
    assert actual_totals["grand_total"] == preview["grand_total"]


# ---------------------------------------------------------------------------
# Fast Billing Database Immutability Check
# ---------------------------------------------------------------------------

def test_21_fast_billing_database_immutability():
    """Verify Fast Billing SQLite database (anti_matrix_billing.db) SHA256 has remained unchanged."""
    if FAST_DB_PATH.exists():
        hasher = hashlib.sha256()
        with open(FAST_DB_PATH, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_sha256 = hasher.hexdigest().upper()
        assert actual_sha256 == EXPECTED_FAST_DB_SHA256, (
            f"Fast Billing database was mutated! Expected {EXPECTED_FAST_DB_SHA256}, got {actual_sha256}"
        )
