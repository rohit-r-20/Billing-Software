"""Unit tests for Barcode Scanner and Fast Billing POS logic."""
import pytest
from db.database import DatabaseManager
from services.catalogue_service import CatalogueService
from services.tax_service import tax_service
from services.billing_service import BillingService


@pytest.fixture
def pos_test_env(tmp_path):
    db_file = tmp_path / "pos_test.db"
    manager = DatabaseManager(db_file)
    manager.run_migrations()

    with manager.get_connection() as conn:
        conn.execute("""
            INSERT INTO companies (id, code, name, fin_year, gstin, state)
            VALUES ('C_POS', 'COMP0001', 'SUPERMARKET MART', '2026-27', '33AAAPL1234F1Z1', 'Tamilnadu');
        """)
        conn.execute("""
            INSERT INTO branches (id, company_id, code, name, is_default)
            VALUES ('B_POS', 'C_POS', 'BR01', 'Main Store', 1);
        """)
        conn.execute("""
            INSERT INTO company_configs (company_id, vch_start, vch_digits, vch_prefix)
            VALUES ('C_POS', 1, 4, 'POS-');
        """)
        conn.commit()

    return manager


def test_barcode_lookup_and_repeated_scan_increment(pos_test_env):
    cat = CatalogueService(pos_test_env)
    
    # Register 2 products with barcodes
    item1 = cat.save_item('C_POS', {
        "name": "AMUL BUTTER 100G",
        "alias": "890126201005",
        "sales_price": 56.0,
        "tax_category": "GST 12%",
        "op_stock_qty": 50.0
    })
    
    item2 = cat.save_item('C_POS', {
        "name": "ORGANIC TOMATO",
        "alias": "VEG-TOMATO",
        "unit": "Kg",
        "sales_price": 40.0,
        "tax_category": "GST 0%",
        "op_stock_qty": 100.0
    })

    # 1. First Scan of AMUL BUTTER
    found = cat.find_by_barcode('C_POS', '890126201005')
    assert found is not None
    assert found["name"] == "AMUL BUTTER 100G"
    assert found["sales_price"] == 56.0

    # Simulate POS Cart
    cart = {}
    
    def add_or_increment_barcode(bcode, custom_qty=1.0):
        prod = cat.find_by_barcode('C_POS', bcode)
        if not prod:
            return False, "Unknown Barcode"
        pid = prod["id"]
        if pid in cart:
            cart[pid]["qty"] += custom_qty
        else:
            cart[pid] = {
                "id": pid,
                "name": prod["name"],
                "price": prod["sales_price"],
                "qty": custom_qty,
                "unit": prod["unit"],
                "tax_rate": 12.0 if "12%" in prod["tax_category"] else 0.0
            }
        return True, "Added"

    # Scan 1: 1 Butter
    ok, _ = add_or_increment_barcode('890126201005')
    assert ok is True
    assert cart[item1["id"]]["qty"] == 1.0

    # Scan 2: Repeated scan of Butter -> Qty becomes 2.0
    ok, _ = add_or_increment_barcode('890126201005')
    assert ok is True
    assert cart[item1["id"]]["qty"] == 2.0

    # Scan 3: Fractional Vegetable Scan (e.g. from weighing scale label: 1.750 kg)
    ok, _ = add_or_increment_barcode('VEG-TOMATO', custom_qty=1.750)
    assert ok is True
    assert cart[item2["id"]]["qty"] == 1.750

    # Scan 4: Unknown barcode
    ok, msg = add_or_increment_barcode('999999999999')
    assert ok is False
    assert msg == "Unknown Barcode"

    # Calculate Totals
    cart_list = list(cart.values())
    totals = tax_service.calculate_voucher_totals(cart_list, auto_round=True)
    
    # 2 Butters @ 56 = 112 (+12% tax = 13.44) -> 125.44
    # 1.75 Tomato @ 40 = 70.00 (0% tax) -> 70.00
    # Total before round = 195.44 -> Rounded = 195.00
    assert totals["grand_total"] == 195.0
    assert round(totals["round_off"], 2) == -0.44

