"""
Unit and Integration Tests for Live Payment Calculation, Balance Due,
Line-Item Percentage Discounts, and Daily Discount Configurations.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from db.database import DatabaseManager
from services.billing_service import BillingService
from services.catalogue_service import CatalogueService
from services.tax_service import TaxService, round_money
from services.printing_service import PrintingService
from desktop.web_bridge import BackendBridge


@pytest.fixture
def initialized_db(tmp_path):
    db_file = tmp_path / "payment_discount_test.db"
    manager = DatabaseManager(db_file)
    manager.run_migrations()

    with manager.get_connection() as conn:
        conn.execute("""
            INSERT INTO companies (id, code, name, fin_year, gstin, state)
            VALUES ('C1', 'COMP0001', 'ANTI MATRIX RETAIL', '2026-27', '33AAAPL1234F1Z1', 'Tamilnadu');
        """)
        conn.execute("""
            INSERT INTO companies (id, code, name, fin_year, gstin, state)
            VALUES ('C2', 'COMP0002', 'OTHER RETAIL', '2026-27', '33BBBPL5678F1Z2', 'Tamilnadu');
        """)
        conn.execute("""
            INSERT INTO branches (id, company_id, code, name, is_default)
            VALUES ('B1', 'C1', 'BR01', 'Main Branch', 1);
        """)
        conn.execute("""
            INSERT INTO branches (id, company_id, code, name, is_default)
            VALUES ('B2', 'C1', 'BR02', 'Secondary Branch', 0);
        """)
        conn.execute("""
            INSERT INTO company_configs (company_id, vch_start, vch_digits, vch_prefix)
            VALUES ('C1', 1, 3, 'INV-');
        """)
        conn.commit()

    return manager


# ==============================================================================
# 1. PAYMENT CALCULATION & BALANCE DUE SPECIFICATION TESTS
# ==============================================================================
class PaymentCalculator:
    """Python reference mirroring the app.js updatePosTenderCalc implementation."""
    @staticmethod
    def calculate(payable: float, tendered: float):
        d_payable = round(payable * 100)
        d_tendered = round(tendered * 100)
        if d_tendered > d_payable:
            change = (d_tendered - d_payable) / 100.0
            balance = 0.0
        elif d_tendered == d_payable:
            change = 0.0
            balance = 0.0
        else:
            change = 0.0
            balance = (d_payable - d_tendered) / 100.0
        return {"payable": payable, "tendered": tendered, "change": change, "balance": balance}


@pytest.mark.parametrize("received,expected_change,expected_balance", [
    (0.0, 0.0, 350.0),
    (13.0, 0.0, 337.0),
    (100.0, 0.0, 250.0),
    (300.0, 0.0, 50.0),
    (350.0, 0.0, 0.0),
    (400.0, 50.0, 0.0),
    (500.0, 150.0, 0.0),
])
def test_payment_calculation_table_with_payable_350(received, expected_change, expected_balance):
    """
    Validates exact arithmetic against the test specification matrix for Payable Amount = ₹350.00.
    """
    res = PaymentCalculator.calculate(payable=350.0, tendered=received)
    assert res["change"] == expected_change
    assert res["balance"] == expected_balance


def test_payment_calculation_decimal_precision():
    """Validates fractional currency amounts (paise precision) without float drift."""
    res1 = PaymentCalculator.calculate(payable=350.50, tendered=400.25)
    assert res1["change"] == 49.75
    assert res1["balance"] == 0.0

    res2 = PaymentCalculator.calculate(payable=120.75, tendered=100.00)
    assert res2["change"] == 0.0
    assert res2["balance"] == 20.75


# ==============================================================================
# 2. LINE-ITEM PERCENTAGE DISCOUNT ENGINE TESTS
# ==============================================================================
def test_line_item_discount_milk_bikis_5_percent():
    """
    Milk Bikis:
    Price: 10.00, Qty: 2
    Gross: 20.00
    Discount (5%): 1.00
    Taxable: 19.00
    Tax (5%): 0.95
    Line Total: 19.95
    """
    res = TaxService.calculate_line_item(
        price=10.0,
        qty=2.0,
        tax_rate=5.0,
        discount_percent=5.0,
        is_tax_inclusive=False,
        is_interstate=False
    )
    assert res["price"] == 10.0
    assert res["qty"] == 2.0
    assert res["discount_amount"] == 1.0
    assert res["taxable_amount"] == 19.0
    assert res["tax_rate"] == 5.0
    assert res["tax_amount"] == 0.95
    assert res["cgst_amount"] == 0.48
    assert res["sgst_amount"] == 0.47
    assert res["line_total"] == 19.95


def test_line_item_discount_hide_and_seek_10_percent():
    """
    Hide & Seek:
    Price: 30.00, Qty: 1
    Gross: 30.00
    Discount (10%): 3.00
    Taxable: 27.00
    Tax (18%): 4.86
    Line Total: 31.86
    """
    res = TaxService.calculate_line_item(
        price=30.0,
        qty=1.0,
        tax_rate=18.0,
        discount_percent=10.0,
        is_tax_inclusive=False,
        is_interstate=False
    )
    assert res["price"] == 30.0
    assert res["qty"] == 1.0
    assert res["discount_amount"] == 3.0
    assert res["taxable_amount"] == 27.0
    assert res["tax_rate"] == 18.0
    assert res["tax_amount"] == 4.86
    assert res["line_total"] == 31.86


def test_voucher_totals_with_multiple_discounts():
    """
    Calculates combined cart totals with Milk Bikis (5%) and Hide & Seek (10%).
    """
    items = [
        {"name": "MILK BIKIS", "price": 10.0, "qty": 2.0, "tax_rate": 5.0, "discount_percent": 5.0},
        {"name": "HIDE & SEEK", "price": 30.0, "qty": 1.0, "tax_rate": 18.0, "discount_percent": 10.0}
    ]
    totals = TaxService.calculate_voucher_totals(items, auto_round=True)

    # Gross Subtotal = (10 * 2) + (30 * 1) = 50.00
    assert totals["subtotal"] == 50.00
    # Total Discount = 1.00 + 3.00 = 4.00
    assert totals["discount_total"] == 4.00
    # Taxable Subtotal = 19.00 + 27.00 = 46.00
    assert totals["taxable_amount"] == 46.00
    # Total Tax = 0.95 + 4.86 = 5.81
    assert totals["total_tax"] == 5.81
    # Raw total = 46.00 + 5.81 = 51.81
    # Grand total with round-off to nearest rupee = 52.00
    assert totals["grand_total"] == 52.00
    assert totals["round_off"] == 0.19


# ==============================================================================
# 3. DAILY DISCOUNT PERSISTENCE & EXPIRY SPECIFICATION TESTS
# ==============================================================================
def test_daily_discount_set_and_get(initialized_db):
    billing_svc = BillingService(initialized_db)
    today = datetime.now().strftime("%Y-%m-%d")

    # Set daily discount for today at 5%
    saved = billing_svc.set_daily_discount(
        company_id="C1",
        branch_id="B1",
        business_date=today,
        discount_percent=5.0,
        is_active=True,
        enabled_by="Cashier1"
    )
    assert saved["discount_percent"] == 5.0
    assert saved["is_active"] is True

    # Retrieve setting for today
    cfg = billing_svc.get_daily_discount(company_id="C1", branch_id="B1", business_date=today)
    assert cfg is not None
    assert cfg["discount_percent"] == 5.0
    assert cfg["is_active"] == 1
    assert cfg["business_date"] == today


def test_daily_discount_automatic_expiration_on_new_date(initialized_db):
    billing_svc = BillingService(initialized_db)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    # Save a discount configured yesterday
    billing_svc.set_daily_discount(
        company_id="C1",
        branch_id="B1",
        business_date=yesterday,
        discount_percent=7.5,
        is_active=True
    )

    # Looking up today should return None because yesterday's discount automatically expired
    cfg_today = billing_svc.get_daily_discount(company_id="C1", branch_id="B1", business_date=today)
    assert cfg_today is None

    # Looking up yesterday directly retrieves the historical record
    cfg_yesterday = billing_svc.get_daily_discount(company_id="C1", branch_id="B1", business_date=yesterday)
    assert cfg_yesterday is not None
    assert cfg_yesterday["discount_percent"] == 7.5


def test_daily_discount_company_and_branch_isolation(initialized_db):
    billing_svc = BillingService(initialized_db)
    today = datetime.now().strftime("%Y-%m-%d")

    # Set discount for Company C1, Branch B1
    billing_svc.set_daily_discount("C1", "B1", today, 8.0, True)

    # Company C2 should have NO discount
    assert billing_svc.get_daily_discount("C2", "B1", today) is None

    # Company C1, Branch B2 should have NO discount
    assert billing_svc.get_daily_discount("C1", "B2", today) is None

    # Company C1, Branch B1 should have 8.0%
    cfg = billing_svc.get_daily_discount("C1", "B1", today)
    assert cfg is not None
    assert cfg["discount_percent"] == 8.0


# ==============================================================================
# 4. SALES VOUCHER ATOMIC CREATION WITH DISCOUNT FIELDS
# ==============================================================================
def test_create_sale_invoice_stores_discount_fields(initialized_db):
    cat_svc = CatalogueService(initialized_db)
    bill_svc = BillingService(initialized_db)

    # Create test product
    item = cat_svc.save_item("C1", {
        "name": "ODONIL ROOM SPRAY - LAVENDER MIST",
        "sales_price": 175.0,
        "op_stock_qty": 50.0,
        "tax_category": "GST 18%"
    })

    cart_items = [
        {
            "id": item["id"],
            "name": item["name"],
            "price": 175.0,
            "qty": 2.0,
            "unit": "Can",
            "tax_rate": 18.0,
            "discount_percent": 10.0,
            "discount_amount": 35.0,
            "taxable_amount": 315.0,
            "tax_amount": 56.70,
            "line_total": 371.70
        }
    ]

    res = bill_svc.create_sale_invoice(
        company_id="C1",
        branch_id="B1",
        account_id=None,
        items=cart_items,
        payment_method="CASH",
        narration="Fast Billing Test with 10% Discount"
    )

    vch_id = res["voucher_id"]
    assert res["totals"]["discount_total"] == 35.0

    # Query DB directly to verify schema fields were populated
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT gross_subtotal, discount_total, taxable_amount, grand_total FROM sales_vouchers WHERE id = ?;", (vch_id,))
        vch_row = cursor.fetchone()
        assert vch_row is not None
        assert vch_row[0] == 350.0  # Gross = 175 * 2
        assert vch_row[1] == 35.0   # Discount total
        assert vch_row[2] == 315.0  # Taxable amount
        assert vch_row[3] == 372.0  # Grand total (315 + 56.70 = 371.70 rounded to 372.0)

        cursor.execute("""
            SELECT discount_percent, discount_amount, taxable_amount, tax_rate, tax_amount
            FROM sales_voucher_items WHERE voucher_id = ?;
        """, (vch_id,))
        item_row = cursor.fetchone()
        assert item_row is not None
        assert item_row[0] == 10.0   # discount_percent
        assert item_row[1] == 35.0   # discount_amount
        assert item_row[2] == 315.0  # taxable_amount
        assert item_row[3] == 18.0   # tax_rate
        assert item_row[4] == 56.70  # tax_amount


# ==============================================================================
# 5. THERMAL RECEIPT RENDERING WITH DISCOUNT
# ==============================================================================
def test_thermal_receipt_includes_discount_and_gross(initialized_db):
    cat_svc = CatalogueService(initialized_db)
    bill_svc = BillingService(initialized_db)

    item = cat_svc.save_item("C1", {
        "name": "TEST SNACK",
        "sales_price": 50.0,
        "op_stock_qty": 20.0,
        "tax_category": "GST 5%"
    })

    cart_items = [
        {
            "id": item["id"],
            "name": item["name"],
            "price": 50.0,
            "qty": 2.0,
            "tax_rate": 5.0,
            "discount_percent": 10.0
        }
    ]

    res = bill_svc.create_sale_invoice(
        company_id="C1",
        branch_id="B1",
        account_id=None,
        items=cart_items,
        payment_method="CASH"
    )

    voucher_data = {
        "company_name": "ANTI MATRIX RETAIL",
        "vch_no": res["vch_no"],
        "items": cart_items,
        "gross_subtotal": 100.0,
        "discount_total": 10.0,
        "subtotal": 90.0,
        "cgst_amount": 2.25,
        "sgst_amount": 2.25,
        "grand_total": 95.0,
        "payment_method": "CASH"
    }

    receipt_text = PrintingService.format_thermal_receipt(voucher_data, width_mm=80)
    assert "Gross Total:" in receipt_text
    assert "Discount:" in receipt_text
    assert "-    10.00" in receipt_text or "-10.00" in receipt_text
    assert "Taxable Subtotal:" in receipt_text
