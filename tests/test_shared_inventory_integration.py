"""
Acceptance Test Suite for:
Alpha Billing – Integrate Traditional Billing, Fast Billing and Shared Inventory

Tests all 9 specific requirements specified in Section 7:
1. Sale through Traditional Billing reduces stock.
2. Sale through Fast Billing reduces the same stock.
3. Traditional Billing reflects Fast Billing deductions.
4. Fast Billing reflects Traditional Billing deductions.
5. Sales returns correctly restore stock when goods are received.
6. Failed invoices do not change stock.
7. Simultaneous sales cannot oversell stock accidentally (negative stock policy & concurrency).
8. Multiple companies and branches remain isolated.
9. Existing product and transaction records remain intact & 9-metric breakdown is verified.
"""
import json
import uuid
import threading
from datetime import datetime
from pathlib import Path
import pytest

from db.database import db_manager
from services.billing_service import billing_service
from services.catalogue_service import catalogue_service
from services.inventory_service import inventory_service
from services.company_service import company_service
from desktop.web_bridge import BackendBridge


def _get_or_create_test_company():
    """Retrieve primary test company."""
    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT id FROM companies WHERE code = 'COMP0001' LIMIT 1;").fetchone()
        if row:
            return row[0]
        row2 = conn.execute("SELECT id FROM companies ORDER BY id ASC LIMIT 1;").fetchone()
        return row2[0] if row2 else "3a743bcd-8f9a-4154-a316-509cba3de99a"


COMPANY_ID = _get_or_create_test_company()

# Ensure customer masters exist for deterministic test runs
with db_manager.get_connection() as _conn:
    for _cname in ("TRADITIONAL CUSTOMER", "ENTERPRISE CLIENT", "RETURN TEST PARTY"):
        _conn.execute("""
            INSERT INTO accounts (id, company_id, name, account_group, is_active)
            VALUES (?, ?, ?, 'Sundry Debtors', 1)
            ON CONFLICT(company_id, name) DO NOTHING;
        """, (str(uuid.uuid4()), COMPANY_ID, _cname))
    _conn.commit()


def _get_default_branch(company_id: str) -> str:
    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT id FROM branches WHERE company_id = ? ORDER BY is_default DESC, id ASC LIMIT 1;", (company_id,)).fetchone()
        if row:
            return row[0]
        new_id = str(uuid.uuid4())
        conn.execute("INSERT INTO branches (id, company_id, code, name, is_default) VALUES (?, ?, 'MAIN', 'Main Branch', 1);", (new_id, company_id))
        conn.commit()
        return new_id


def _create_isolated_test_product(company_id: str, branch_id: str, initial_qty: float = 100.0) -> dict:
    """Creates a dedicated product for deterministic stock testing."""
    item_id = str(uuid.uuid4())
    unique_code = f"TEST-{uuid.uuid4().hex[:8].upper()}"
    barcode = f"890{uuid.uuid4().hex[:10].upper()}"

    with db_manager.get_connection() as conn:
        conn.execute("""
            INSERT INTO items (
                id, company_id, name, alias, print_name, item_group, unit,
                op_stock_qty, op_stock_val, tax_category, hsn, sales_price,
                purc_price, mrp, min_sales_price, is_active
            ) VALUES (?, ?, ?, ?, ?, 'Test Group', 'Pcs.', ?, ?, 'GST 18%', '9999', 100.0, 60.0, 120.0, 90.0, 1);
        """, (item_id, company_id, unique_code, barcode, unique_code, initial_qty, initial_qty * 60.0))

        conn.execute("""
            INSERT INTO item_barcodes (id, item_id, company_id, barcode, is_primary)
            VALUES (?, ?, ?, ?, 1);
        """, (str(uuid.uuid4()), item_id, company_id, barcode))

        conn.execute("""
            INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(branch_id, item_id) DO UPDATE SET current_qty = excluded.current_qty;
        """, (str(uuid.uuid4()), company_id, branch_id, item_id, initial_qty))
        conn.commit()

    return {
        "id": item_id,
        "name": unique_code,
        "barcode": barcode,
        "branch_id": branch_id,
        "initial_qty": initial_qty
    }


# ---------------------------------------------------------------------------
# Test 1: Sale through Traditional Billing reduces stock
# ---------------------------------------------------------------------------
def test_criterion_1_traditional_billing_sale_reduces_stock():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_isolated_test_product(COMPANY_ID, branch_id, 50.0)
    initial_stock = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)
    assert initial_stock == 50.0

    # Execute Traditional Billing sale of 5 units
    items = [{
        "id": item["id"],
        "name": item["name"],
        "qty": 5.0,
        "price": 100.0,
        "tax_rate": 18.0
    }]

    vch = billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=items,
        branch_id=branch_id,
        party_name="TRADITIONAL CUSTOMER",
        series="Main"
    )

    assert vch["voucher_id"] is not None
    vch_no = vch["vch_no"]

    # Verify stock balance reduced by exactly 5
    new_stock = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)
    assert new_stock == 45.0, f"Expected 45.0, got {new_stock}"

    # Verify stock movement recorded with linkage to sales voucher
    with db_manager.get_connection() as conn:
        mov = conn.execute("""
            SELECT movement_type, qty, reference_id, reference_type
            FROM stock_movements
            WHERE company_id = ? AND branch_id = ? AND item_id = ? AND reference_id = ?;
        """, (COMPANY_ID, branch_id, item["id"], vch_no)).fetchone()

        assert mov is not None
        assert mov["movement_type"] == "SALE"
        assert float(mov["qty"]) == -5.0
        assert mov["reference_type"] == "INVOICE"


# ---------------------------------------------------------------------------
# Test 2: Sale through Fast Billing reduces the same stock
# ---------------------------------------------------------------------------
def test_criterion_2_fast_billing_sale_reduces_same_stock():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_isolated_test_product(COMPANY_ID, branch_id, 40.0)
    bridge = BackendBridge()

    # Fast Billing payload structure
    fast_billing_payload = {
        "party_name": "CASH",
        "customer_category": "Direct Customer",
        "sale_type": "L/GST-18%",
        "payment_method": "CASH",
        "items": [{
            "id": item["id"],
            "name": item["name"],
            "qty": 8.0,
            "unit": "Pcs.",
            "price": 100.0,
            "discount_percent": 0.0,
            "discount_amount": 0.0,
            "taxable_amount": 800.0,
            "tax_rate": 18.0,
            "tax_amount": 144.0,
            "line_total": 944.0
        }],
        "vch_date": datetime.now().strftime("%d-%m-%Y"),
        "narration": "Fast Billing Checkout"
    }

    resp = json.loads(bridge.createSaleInvoice(COMPANY_ID, json.dumps(fast_billing_payload)))
    assert resp["success"] is True
    vch_no = resp["data"]["vch_no"]

    # Shared stock must now be 40 - 8 = 32
    shared_stock = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)
    assert shared_stock == 32.0, f"Expected 32.0, got {shared_stock}"

    # Movement must be recorded
    with db_manager.get_connection() as conn:
        mov = conn.execute("""
            SELECT movement_type, qty FROM stock_movements
            WHERE company_id = ? AND branch_id = ? AND item_id = ? AND reference_id = ?;
        """, (COMPANY_ID, branch_id, item["id"], vch_no)).fetchone()
        assert mov is not None
        assert float(mov["qty"]) == -8.0


# ---------------------------------------------------------------------------
# Test 3: Traditional Billing reflects Fast Billing deductions
# ---------------------------------------------------------------------------
def test_criterion_3_traditional_billing_reflects_fast_billing_deductions():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_isolated_test_product(COMPANY_ID, branch_id, 60.0)
    bridge = BackendBridge()

    # 1. Check stock in Traditional Billing summary view before
    summary_before = inventory_service.get_stock_summary(COMPANY_ID, branch_id, item["name"])
    assert len(summary_before) == 1
    assert summary_before[0]["closing_stock"] == 60.0

    # 2. Fast Billing checkout of 12 units
    payload = {
        "party_name": "WALK-IN",
        "payment_method": "UPI",
        "items": [{
            "id": item["id"],
            "name": item["name"],
            "qty": 12.0,
            "unit": "Pcs.",
            "price": 100.0,
            "tax_rate": 18.0
        }]
    }
    resp = json.loads(bridge.createSaleInvoice(COMPANY_ID, json.dumps(payload)))
    assert resp["success"] is True

    # 3. Traditional Billing stock summary must immediately show 48.0
    summary_after = inventory_service.get_stock_summary(COMPANY_ID, branch_id, item["name"])
    assert len(summary_after) == 1
    assert summary_after[0]["closing_stock"] == 48.0


# ---------------------------------------------------------------------------
# Test 4: Fast Billing reflects Traditional Billing deductions
# ---------------------------------------------------------------------------
def test_criterion_4_fast_billing_reflects_traditional_billing_deductions():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_isolated_test_product(COMPANY_ID, branch_id, 75.0)
    bridge = BackendBridge()

    # 1. Fast Billing initial lookup
    stock_before_resp = json.loads(bridge.getAuthoritativeStock(COMPANY_ID, item["id"], branch_id))
    assert stock_before_resp["success"] is True
    assert stock_before_resp["data"] == 75.0

    # 2. Traditional Billing sale of 25 units
    billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{"id": item["id"], "name": item["name"], "qty": 25.0, "price": 100.0, "tax_rate": 18.0}],
        branch_id=branch_id,
        party_name="ENTERPRISE CLIENT"
    )

    # 3. Fast Billing immediately sees 50.0 available stock
    stock_after_resp = json.loads(bridge.getAuthoritativeStock(COMPANY_ID, item["id"], branch_id))
    assert stock_after_resp["success"] is True
    assert stock_after_resp["data"] == 50.0

    # Barcode search in Fast Billing also reflects updated stock
    barcode_item = catalogue_service.find_by_barcode(COMPANY_ID, item["barcode"])
    assert barcode_item is not None
    assert barcode_item["current_stock"] == 50.0


# ---------------------------------------------------------------------------
# Test 5: Sales returns correctly restore stock when goods are received
# ---------------------------------------------------------------------------
def test_criterion_5_sales_returns_restore_stock():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_isolated_test_product(COMPANY_ID, branch_id, 30.0)

    # Make sale of 10 units -> stock becomes 20
    sale = billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{"id": item["id"], "name": item["name"], "qty": 10.0, "price": 100.0, "tax_rate": 18.0}],
        branch_id=branch_id,
        party_name="RETURN TEST PARTY"
    )
    assert inventory_service.get_stock(COMPANY_ID, item["id"], branch_id) == 20.0

    # Return 4 units as SALEABLE condition -> stock must become 24
    ret_res = billing_service.create_sales_return(
        company_id=COMPANY_ID,
        data={
            "branch_id": branch_id,
            "customer_name": "RETURN TEST PARTY",
            "items": [{
                "item_id": item["id"],
                "name": item["name"],
                "qty": 4.0,
                "rate": 100.0,
                "tax_rate": 18.0,
                "restock_condition": "SALEABLE"
            }],
            "original_voucher_id": sale["voucher_id"],
            "original_invoice_no": sale["vch_no"],
            "reason": "Customer overbought"
        }
    )
    assert ret_res["id"] is not None

    # Verify stock restored to 24
    restored_stock = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)
    assert restored_stock == 24.0, f"Expected 24.0, got {restored_stock}"

    # Verify return movement in ledger
    with db_manager.get_connection() as conn:
        ret_mov = conn.execute("""
            SELECT movement_type, qty, reference_id FROM stock_movements
            WHERE company_id = ? AND branch_id = ? AND item_id = ? AND movement_type = 'SALES_RETURN';
        """, (COMPANY_ID, branch_id, item["id"])).fetchone()
        assert ret_mov is not None
        assert float(ret_mov["qty"]) == 4.0


# ---------------------------------------------------------------------------
# Test 6: Failed invoices do not change stock (Atomic Rollback)
# ---------------------------------------------------------------------------
def test_criterion_6_failed_invoices_do_not_change_stock():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_isolated_test_product(COMPANY_ID, branch_id, 50.0)
    stock_before = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)

    # Count invoices and movements before
    with db_manager.get_connection() as conn:
        inv_count_before = conn.execute("SELECT COUNT(*) FROM sales_vouchers WHERE company_id = ?;", (COMPANY_ID,)).fetchone()[0]
        mov_count_before = conn.execute("SELECT COUNT(*) FROM stock_movements WHERE company_id = ? AND item_id = ?;", (COMPANY_ID, item["id"])).fetchone()[0]

    # Deliberately attempt an invalid invoice (empty items list or invalid company)
    with pytest.raises(Exception):
        billing_service.create_sale_invoice(
            company_id=COMPANY_ID,
            items=[],  # Empty items triggers ValueError
            branch_id=branch_id
        )

    # Stock must remain strictly unaffected
    stock_after = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)
    assert stock_after == stock_before

    # Database records must have no dangling vouchers or movements
    with db_manager.get_connection() as conn:
        inv_count_after = conn.execute("SELECT COUNT(*) FROM sales_vouchers WHERE company_id = ?;", (COMPANY_ID,)).fetchone()[0]
        mov_count_after = conn.execute("SELECT COUNT(*) FROM stock_movements WHERE company_id = ? AND item_id = ?;", (COMPANY_ID, item["id"])).fetchone()[0]

        assert inv_count_after == inv_count_before
        assert mov_count_after == mov_count_before


# ---------------------------------------------------------------------------
# Test 7: Simultaneous sales cannot oversell stock accidentally
# ---------------------------------------------------------------------------
def test_criterion_7_simultaneous_sales_cannot_oversell_stock():
    branch_id = _get_default_branch(COMPANY_ID)
    # Configure company policy: Negative stock NOT allowed
    company_service.save_config(COMPANY_ID, {"allowNegativeStock": False})

    # Create product with strictly 5 units
    item = _create_isolated_test_product(COMPANY_ID, branch_id, 5.0)

    # Attempt a single sale exceeding available stock (e.g. 10 units)
    with pytest.raises(ValueError) as excinfo:
        billing_service.create_sale_invoice(
            company_id=COMPANY_ID,
            items=[{"id": item["id"], "name": item["name"], "qty": 10.0, "price": 100.0, "tax_rate": 18.0}],
            branch_id=branch_id
        )
    assert "Insufficient stock" in str(excinfo.value)

    # Stock remains 5.0
    assert inventory_service.get_stock(COMPANY_ID, item["id"], branch_id) == 5.0

    # Simulate 5 concurrent threads attempting to buy 2 units each (Total 10 units requested, only 5 available)
    successes = []
    failures = []

    def worker():
        try:
            billing_service.create_sale_invoice(
                company_id=COMPANY_ID,
                items=[{"id": item["id"], "name": item["name"], "qty": 2.0, "price": 100.0, "tax_rate": 18.0}],
                branch_id=branch_id
            )
            successes.append(True)
        except Exception as e:
            failures.append(str(e))

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Maximum 2 sales could succeed (2 * 2 = 4 units <= 5; 3rd would require 6 > 5)
    assert len(successes) == 2, f"Expected exactly 2 successful sales, got {len(successes)}"
    assert len(failures) == 3, f"Expected 3 blocked sales, got {len(failures)}"

    # Final stock must be strictly >= 0 (5 - 4 = 1.0)
    final_stock = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)
    assert final_stock == 1.0, f"Expected 1.0 remaining stock, got {final_stock}"


# ---------------------------------------------------------------------------
# Test 8: Multiple companies and branches remain isolated
# ---------------------------------------------------------------------------
def test_criterion_8_multi_company_and_multi_branch_isolation():
    branch_1 = _get_default_branch(COMPANY_ID)

    # Create a second branch in the same company
    branch_2 = str(uuid.uuid4())
    unique_code = f"BR-{uuid.uuid4().hex[:6].upper()}"
    with db_manager.get_connection() as conn:
        conn.execute("""
            INSERT INTO branches (id, company_id, code, name, is_default)
            VALUES (?, ?, ?, 'Secondary Warehouse', 0);
        """, (branch_2, COMPANY_ID, unique_code))
        conn.commit()

    # Product exists in both branches with different quantities
    item_id = str(uuid.uuid4())
    item_name = f"MULTI-BRANCH-{uuid.uuid4().hex[:6].upper()}"
    with db_manager.get_connection() as conn:
        conn.execute("""
            INSERT INTO items (id, company_id, name, unit, is_active)
            VALUES (?, ?, ?, 'Pcs.', 1);
        """, (item_id, COMPANY_ID, item_name))
        # Branch 1 has 100 units
        conn.execute("INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty) VALUES (?, ?, ?, ?, 100.0);", (str(uuid.uuid4()), COMPANY_ID, branch_1, item_id))
        # Branch 2 has 50 units
        conn.execute("INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty) VALUES (?, ?, ?, ?, 50.0);", (str(uuid.uuid4()), COMPANY_ID, branch_2, item_id))
        conn.commit()

    # Sale of 20 units in Branch 1
    billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        branch_id=branch_1,
        items=[{"id": item_id, "name": item_name, "qty": 20.0, "price": 50.0, "tax_rate": 18.0}]
    )

    # Branch 1 stock must be 80.0
    assert inventory_service.get_stock(COMPANY_ID, item_id, branch_1) == 80.0

    # Branch 2 stock must remain completely untouched at 50.0
    assert inventory_service.get_stock(COMPANY_ID, item_id, branch_2) == 50.0


# ---------------------------------------------------------------------------
# Test 9: Existing records intact & 9-metric breakdown verified
# ---------------------------------------------------------------------------
def test_criterion_9_existing_records_intact_and_stock_breakdown_formula():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_isolated_test_product(COMPANY_ID, branch_id, 100.0)

    # 1. Purchase inward of 30 units
    inventory_service.adjust_stock(
        company_id=COMPANY_ID,
        branch_id=branch_id,
        item_id=item["id"],
        qty_delta=30.0,
        movement_type="PURCHASE",
        notes="Inward shipment"
    )

    # 2. Sale outward of 20 units
    billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        branch_id=branch_id,
        items=[{"id": item["id"], "name": item["name"], "qty": 20.0, "price": 100.0, "tax_rate": 18.0}]
    )

    # 3. Sales return inward of 5 units
    inventory_service.adjust_stock(
        company_id=COMPANY_ID,
        branch_id=branch_id,
        item_id=item["id"],
        qty_delta=5.0,
        movement_type="SALES_RETURN",
        notes="Customer return"
    )

    # 4. Purchase return outward of 10 units
    inventory_service.adjust_stock(
        company_id=COMPANY_ID,
        branch_id=branch_id,
        item_id=item["id"],
        qty_delta=-10.0,
        movement_type="PURCHASE_RETURN",
        notes="Supplier return"
    )

    # 5. Stock transfer out of 8 units
    inventory_service.adjust_stock(
        company_id=COMPANY_ID,
        branch_id=branch_id,
        item_id=item["id"],
        qty_delta=-8.0,
        movement_type="TRANSFER_OUT",
        notes="Outward transfer"
    )

    # 6. Physical count adjustment of -2 units
    inventory_service.adjust_stock(
        company_id=COMPANY_ID,
        branch_id=branch_id,
        item_id=item["id"],
        qty_delta=-2.0,
        movement_type="ADJUSTMENT",
        notes="Damage write-off"
    )

    # Calculate authoritative breakdown
    breakdown = inventory_service.calculate_stock_breakdown(COMPANY_ID, item["id"], branch_id)

    assert breakdown["opening_stock"] == 100.0
    assert breakdown["purchased_quantity"] == 30.0
    assert breakdown["sold_quantity"] == 20.0
    assert breakdown["sales_return_quantity"] == 5.0
    assert breakdown["purchase_return_quantity"] == 10.0
    assert breakdown["stock_transfer_in"] == 0.0
    assert breakdown["stock_transfer_out"] == 8.0
    assert breakdown["stock_adjustments"] == -2.0

    # Expected: 100 + 30 - 20 + 5 - 10 + 0 - 8 - 2 = 95.0
    expected_available = 100.0 + 30.0 - 20.0 + 5.0 - 10.0 + 0.0 - 8.0 - 2.0
    assert breakdown["available_stock"] == 95.0
    assert breakdown["available_stock"] == expected_available

    # Also verify bridge slot returns identical data
    bridge = BackendBridge()
    bridge_resp = json.loads(bridge.getStockBreakdown(COMPANY_ID, item["id"], branch_id))
    assert bridge_resp["success"] is True
    assert bridge_resp["data"]["available_stock"] == 95.0
