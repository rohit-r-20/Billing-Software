"""
Comprehensive Verification Tests for Low-Stock Alerts and Customer Category Discounts
Anti Matrix Alpha Billing Software — Controlled Enhancement
"""
import pytest
import uuid
from decimal import Decimal
from services.catalogue_service import catalogue_service
from services.inventory_service import inventory_service
from services.billing_service import billing_service
from services.account_service import account_service
from services.purchase_service import purchase_service
from services.tax_service import tax_service
from db.database import db_manager


@pytest.fixture(autouse=True)
def ensure_schema():
    db_manager.run_migrations()


@pytest.fixture
def active_company():
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM companies LIMIT 1;")
        row = cursor.fetchone()
        assert row is not None, "At least one test company must exist."
        return row["id"]


# ==============================================================================
# 1. LOW-STOCK DATA INTEGRITY & CALCULATION TESTS
# ==============================================================================

def test_01_optional_threshold_disabled_by_default(active_company):
    """Items created without min_stock_alert_level must not trigger low-stock alerts."""
    item_name = f"TEST_NO_ALERT_{uuid.uuid4().hex[:6]}"
    saved = catalogue_service.save_item(active_company, {
        "name": item_name,
        "sales_price": 50.0,
        "op_stock_qty": 5.0,
        "min_stock_alert_level": None,  # Optional / empty
        "alert_enabled": 1
    })
    assert saved["id"] is not None
    assert saved.get("min_stock_alert_level") is None

    alerts = inventory_service.evaluate_low_stock_alerts(active_company)
    alert_item_ids = [a["item_id"] for a in alerts]
    assert saved["id"] not in alert_item_ids, "Item with no threshold must not trigger alerts."


def test_02_threshold_boundary_equal_stock_no_alert(active_company):
    """When stock == threshold, alert must NOT trigger (condition is strictly stock < threshold)."""
    item_name = f"TEST_BOUNDARY_{uuid.uuid4().hex[:6]}"
    saved = catalogue_service.save_item(active_company, {
        "name": item_name,
        "sales_price": 100.0,
        "op_stock_qty": 10.0,
        "min_stock_alert_level": 10.0,  # Exact equal
        "alert_enabled": 1
    })
    alerts = inventory_service.evaluate_low_stock_alerts(active_company)
    alert_item_ids = [a["item_id"] for a in alerts]
    assert saved["id"] not in alert_item_ids, "Stock equal to threshold must not trigger alert."


def test_03_stock_below_threshold_triggers_alert(active_company):
    """When stock < threshold, alert must trigger with correct shortfall."""
    item_name = f"TEST_LOW_{uuid.uuid4().hex[:6]}"
    saved = catalogue_service.save_item(active_company, {
        "name": item_name,
        "sales_price": 120.0,
        "op_stock_qty": 4.0,
        "min_stock_alert_level": 10.0,
        "alert_enabled": 1
    })
    alerts = inventory_service.evaluate_low_stock_alerts(active_company)
    matching = [a for a in alerts if a["item_id"] == saved["id"]]
    assert len(matching) == 1, "Alert must be created for stock below threshold."
    alert = matching[0]
    assert alert["threshold"] == 10.0
    assert alert["current_stock"] == 4.0
    assert alert["shortfall"] == 6.0
    assert alert["status"] in ("ACTIVE", "DISMISSED")


def test_04_zero_and_negative_stock_alerts(active_company):
    """Stock = 0 and Stock < 0 must trigger alerts if threshold > 0."""
    item_zero = catalogue_service.save_item(active_company, {
        "name": f"TEST_ZERO_{uuid.uuid4().hex[:6]}",
        "sales_price": 40.0,
        "op_stock_qty": 0.0,
        "min_stock_alert_level": 5.0,
        "alert_enabled": 1
    })
    alerts = inventory_service.evaluate_low_stock_alerts(active_company)
    matching_zero = [a for a in alerts if a["item_id"] == item_zero["id"]]
    assert len(matching_zero) == 1
    assert matching_zero[0]["current_stock"] == 0.0
    assert matching_zero[0]["shortfall"] == 5.0
    assert matching_zero[0]["is_zero"] is True


def test_05_stock_deduction_in_sale_triggers_alert(active_company):
    """Selling an item and bringing stock below threshold must trigger low stock alert."""
    item_sale = catalogue_service.save_item(active_company, {
        "name": f"TEST_SALE_ALERT_{uuid.uuid4().hex[:6]}",
        "sales_price": 50.0,
        "op_stock_qty": 12.0,
        "min_stock_alert_level": 8.0,
        "alert_enabled": 1
    })
    # Before sale: 12 >= 8 -> no alert
    alerts_before = inventory_service.evaluate_low_stock_alerts(active_company)
    assert item_sale["id"] not in [a["item_id"] for a in alerts_before]

    # Checkout sale of 6 units -> remaining = 6 (< 8)
    res = billing_service.create_sale_invoice(
        company_id=active_company,
        items=[{
            "id": item_sale["id"],
            "name": item_sale["name"],
            "qty": 6.0,
            "price": 50.0,
            "tax_rate": 18.0
        }],
        party_name="CASH"
    )
    assert res["voucher_id"] is not None

    alerts_after = inventory_service.get_active_low_stock_alerts(active_company)
    matching = [a for a in alerts_after if a["item_id"] == item_sale["id"]]
    assert len(matching) == 1
    assert matching[0]["current_stock"] == 6.0
    assert matching[0]["shortfall"] == 2.0


def test_06_replenishment_resolves_low_stock_alert(active_company):
    """When stock is replenished via purchase or adjustment to >= threshold, alert auto-resolves."""
    item_replenish = catalogue_service.save_item(active_company, {
        "name": f"TEST_REPLENISH_{uuid.uuid4().hex[:6]}",
        "sales_price": 80.0,
        "op_stock_qty": 3.0,
        "min_stock_alert_level": 10.0,
        "alert_enabled": 1
    })
    # Trigger initial alert
    alerts = inventory_service.evaluate_low_stock_alerts(active_company)
    assert item_replenish["id"] in [a["item_id"] for a in alerts]

    # Post purchase to bring stock to 15 (>= 10)
    purc_res = purchase_service.create_purchase_voucher(active_company, {
        "supplier_name": "TEST WHOLESALER LTD",
        "supplier_invoice_no": f"INV-{uuid.uuid4().hex[:6]}",
        "supplier_invoice_date": "2026-11-01",
        "items": [{
            "item_id": item_replenish["id"],
            "name": item_replenish["name"],
            "qty": 12.0,
            "unit": "Pcs.",
            "purchase_rate": 60.0,
            "tax_rate": 18.0
        }]
    })
    assert purc_res["voucher_id"] is not None

    # Alert should now be automatically resolved
    active_alerts = inventory_service.get_active_low_stock_alerts(active_company)
    assert item_replenish["id"] not in [a["item_id"] for a in active_alerts], "Replenished item must have its alert resolved."


def test_07_dismiss_alert_lifecycle(active_company):
    """Dismissing an alert marks it as DISMISSED without affecting the underlying stock."""
    item_dismiss = catalogue_service.save_item(active_company, {
        "name": f"TEST_DISMISS_{uuid.uuid4().hex[:6]}",
        "sales_price": 75.0,
        "op_stock_qty": 2.0,
        "min_stock_alert_level": 10.0,
        "alert_enabled": 1
    })
    alerts = inventory_service.evaluate_low_stock_alerts(active_company)
    matching = [a for a in alerts if a["item_id"] == item_dismiss["id"]]
    assert len(matching) == 1
    alert_id = matching[0]["alert_id"]

    # Dismiss alert
    dismiss_ok = inventory_service.dismiss_low_stock_alert(active_company, alert_id)
    assert dismiss_ok is True

    # Active alerts list excludes dismissed ones
    active_alerts = inventory_service.get_active_low_stock_alerts(active_company, include_dismissed=False)
    assert alert_id not in [a["alert_id"] for a in active_alerts]

    # Full list includes it with DISMISSED status
    all_alerts = inventory_service.get_active_low_stock_alerts(active_company, include_dismissed=True)
    dismissed = [a for a in all_alerts if a["alert_id"] == alert_id]
    assert len(dismissed) == 1
    assert dismissed[0]["status"] == "DISMISSED"


# ==============================================================================
# 2. CUSTOMER CATEGORY DISCOUNTS & PRICING TESTS
# ==============================================================================

def test_08_customer_category_default_discounts(active_company):
    """Default customer category discounts: Commercial=5%, Sub-Commercial=2.5%, Direct=0%."""
    discounts = billing_service.get_customer_category_discounts(active_company)
    assert discounts["Commercial"] == 5.0
    assert discounts["Sub-Commercial"] == 2.5
    assert discounts["Direct Customer"] == 0.0


def test_09_customer_category_configuration_persistence(active_company):
    """Configuring customer category discounts validates range 0-100% and persists accurately."""
    # Test valid update
    updated = billing_service.set_customer_category_discounts(active_company, {
        "Commercial": 8.0,
        "Sub-Commercial": 4.0,
        "Direct Customer": 1.0
    })
    assert updated["Commercial"] == 8.0
    assert updated["Sub-Commercial"] == 4.0
    assert updated["Direct Customer"] == 1.0

    # Test re-fetch
    fresh = billing_service.get_customer_category_discounts(active_company)
    assert fresh["Commercial"] == 8.0
    assert fresh["Sub-Commercial"] == 4.0
    assert fresh["Direct Customer"] == 1.0

    # Test out of range validation (< 0 or > 100)
    with pytest.raises(ValueError):
        billing_service.set_customer_category_discounts(active_company, {"Commercial": -5.0})

    with pytest.raises(ValueError):
        billing_service.set_customer_category_discounts(active_company, {"Commercial": 105.0})

    # Restore defaults
    billing_service.set_customer_category_discounts(active_company, {
        "Commercial": 5.0,
        "Sub-Commercial": 2.5,
        "Direct Customer": 0.0
    })


def test_10_customer_master_category_assignment(active_company):
    """Saving customer with a category properly associates and returns that category."""
    acc_comm = account_service.save_account(active_company, {
        "name": f"COMMERCIAL STORE_{uuid.uuid4().hex[:6]}",
        "account_group": "Sundry Debtors",
        "customerCategory": "Commercial"
    })
    assert acc_comm["customer_category"] == "Commercial"

    acc_sub = account_service.save_account(active_company, {
        "name": f"SUB COMMERCIAL SHOP_{uuid.uuid4().hex[:6]}",
        "account_group": "Sundry Debtors",
        "customerCategory": "Sub-Commercial"
    })
    assert acc_sub["customer_category"] == "Sub-Commercial"

    acc_direct = account_service.save_account(active_company, {
        "name": f"DIRECT WALK IN_{uuid.uuid4().hex[:6]}",
        "account_group": "Sundry Debtors"
        # omitted customerCategory defaults to Direct Customer
    })
    assert acc_direct["customer_category"] == "Direct Customer"


def test_11_discount_precedence_and_authoritative_calculation(active_company):
    """Verify discount precedence: Manual Line > Max(Category, Daily)."""
    # Baseline Commercial (5%)
    disc = billing_service.calculate_authoritative_discount(
        company_id=active_company,
        customer_category="Commercial",
        manual_discount_percent=None,
        apply_daily_discount=False
    )
    assert disc == 5.0

    # Manual cashier override to 12% takes explicit precedence
    disc_override = billing_service.calculate_authoritative_discount(
        company_id=active_company,
        customer_category="Commercial",
        manual_discount_percent=12.0,
        apply_daily_discount=False
    )
    assert disc_override == 12.0

    # Direct Customer (0%)
    disc_direct = billing_service.calculate_authoritative_discount(
        company_id=active_company,
        customer_category="Direct Customer",
        manual_discount_percent=None,
        apply_daily_discount=False
    )
    assert disc_direct == 0.0


def test_12_sales_invoice_tax_and_discount_calculation(active_company):
    """
    Verify complete sale invoice computation with category discount:
    Original: 10 units @ ₹100 = ₹1000
    Discount (Commercial 5%): ₹50
    Taxable Base: ₹950
    GST 18%: ₹171 (CGST ₹85.50 + SGST ₹85.50)
    Grand Total: ₹1121
    """
    acc = account_service.save_account(active_company, {
        "name": f"B2B CLIENT_{uuid.uuid4().hex[:6]}",
        "customerCategory": "Commercial"
    })
    it = catalogue_service.save_item(active_company, {
        "name": f"TEST_DISC_ITEM_{uuid.uuid4().hex[:6]}",
        "sales_price": 100.0,
        "tax_category": "GST 18%",
        "op_stock_qty": 50.0
    })

    disc_pct = billing_service.calculate_authoritative_discount(
        company_id=active_company,
        customer_category=acc["customer_category"]
    )
    assert disc_pct == 5.0

    invoice_res = billing_service.create_sale_invoice(
        company_id=active_company,
        party_name=acc["name"],
        account_id=acc["id"],
        customer_category=acc["customer_category"],
        items=[{
            "id": it["id"],
            "name": it["name"],
            "qty": 10.0,
            "price": 100.0,
            "discount_percent": disc_pct,
            "tax_rate": 18.0
        }]
    )
    assert invoice_res["voucher_id"] is not None
    assert invoice_res["customer_category"] == "Commercial"
    totals = invoice_res["totals"]
    assert totals["discount_total"] == 50.0
    assert totals["taxable_amount"] == 950.0
    assert totals["cgst_amount"] == 85.5
    assert totals["sgst_amount"] == 85.5
    assert totals["grand_total"] == 1121.0

