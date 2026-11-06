"""
Acceptance Test Suite for:
Alpha Billing – Cross-Module Stock Synchronisation and Notification Validation

Tests all 10 requirements and the complete acceptance scenario:
1. Both billing modes update the same inventory records.
2. Stock changes reflected immediately after successful transaction commits.
3. Low-stock notifications generated regardless of which billing mode caused reduction.
4. Authorised owners and inventory managers see consolidated notifications.
5. Notifications identify correct company, branch and warehouse.
6. Cashiers do not gain inventory management access through notifications.
7. Stock not deducted twice when invoices are saved, printed or reprinted.
8. Printing failures never reverse or duplicate successful stock movements.
9. Invoice modifications reconcile stock movements correctly.
10. Sales returns update inventory according to actual goods received and return rules.
11. Complete Acceptance Scenario:
    Opening 100 -> TB 40 -> FB 30 -> TB 10 (triggers reorder at 20) -> FB 5 (updates alert to 15, no duplicates) -> Purc 50 (resolves alert at 65).
"""
import json
import uuid
from datetime import datetime
import pytest

from db.database import db_manager
from services.billing_service import billing_service
from services.purchase_service import purchase_service
from services.catalogue_service import catalogue_service
from services.inventory_service import inventory_service
from desktop.web_bridge import BackendBridge


def _get_or_create_test_company() -> str:
    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT id FROM companies WHERE code = 'COMP0001' LIMIT 1;").fetchone()
        if row:
            return row[0]
        row2 = conn.execute("SELECT id FROM companies ORDER BY id ASC LIMIT 1;").fetchone()
        return row2[0] if row2 else "3a743bcd-8f9a-4154-a316-509cba3de99a"


COMPANY_ID = _get_or_create_test_company()

# Ensure customer masters exist for cross-module synchronisation tests
with db_manager.get_connection() as _conn:
    for _cname in ("TRADITIONAL PARTY", "TB CUSTOMER", "PRINT TEST CUSTOMER", "MODIFY PARTY", "RETURN TEST PARTY", "TB CUSTOMER 1", "TB CUSTOMER 2"):
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


def _create_item(company_id: str, branch_id: str, op_qty: float = 100.0, reorder_lvl: float = 20.0, min_lvl: float = 10.0) -> dict:
    item_id = str(uuid.uuid4())
    unique_name = f"SYNC-{uuid.uuid4().hex[:8].upper()}"
    barcode = f"890{uuid.uuid4().hex[:10].upper()}"

    catalogue_service.save_item(company_id, {
        "id": item_id,
        "name": unique_name,
        "alias": barcode,
        "branch_id": branch_id,
        "op_stock_qty": op_qty,
        "reorder_level": reorder_lvl,
        "min_stock_alert_level": min_lvl,
        "sales_price": 60.0,
        "purc_price": 35.0,
        "alert_enabled": 1
    })

    return {
        "id": item_id,
        "name": unique_name,
        "barcode": barcode,
        "branch_id": branch_id,
        "initial_qty": op_qty,
        "reorder_level": reorder_lvl,
        "min_stock_level": min_lvl
    }


# ---------------------------------------------------------------------------
# Requirement 1 & 2: Shared inventory records & immediate reflection
# ---------------------------------------------------------------------------
def test_req1_and_req2_both_billing_modes_update_same_inventory_records():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_item(COMPANY_ID, branch_id, op_qty=100.0)

    # 1. Traditional Billing sale of 25 units
    billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{"id": item["id"], "name": item["name"], "qty": 25.0, "price": 60.0, "tax_rate": 18.0}],
        branch_id=branch_id,
        party_name="TRADITIONAL PARTY",
        series="Main"
    )

    # Immediate reflection check
    stock_after_tb = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)
    assert stock_after_tb == 75.0, "Traditional Billing must deduct stock immediately."

    # 2. Fast Billing sale of 15 units on the same product
    bridge = BackendBridge()
    fast_payload = {
        "party_name": "CASH",
        "sale_type": "L/GST-18%",
        "payment_method": "CASH",
        "items": [{"id": item["id"], "name": item["name"], "qty": 15.0, "unit": "Pcs.", "price": 60.0, "tax_rate": 18.0}],
        "narration": "Fast Billing Checkout"
    }
    bridge_resp = json.loads(bridge.createSaleInvoice(COMPANY_ID, json.dumps(fast_payload)))
    assert bridge_resp["success"] is True

    # Immediate reflection check for Fast Billing
    stock_after_fb = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)
    assert stock_after_fb == 60.0, "Fast Billing must deduct from the same shared stock balance immediately."

    # Verify both movements exist in the shared movement ledger
    with db_manager.get_connection() as conn:
        movs = conn.execute("SELECT qty, movement_type FROM stock_movements WHERE item_id = ? ORDER BY created_at ASC;", (item["id"],)).fetchall()
        assert len(movs) == 2
        assert movs[0][0] == -25.0
        assert movs[1][0] == -15.0


# ---------------------------------------------------------------------------
# Requirement 3: Notifications generated regardless of billing mode
# ---------------------------------------------------------------------------
def test_req3_low_stock_notifications_generated_regardless_of_mode():
    branch_id = _get_default_branch(COMPANY_ID)

    # Case A: Reached via Traditional Billing
    item_tb = _create_item(COMPANY_ID, branch_id, op_qty=25.0, reorder_lvl=20.0, min_lvl=10.0)
    billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{"id": item_tb["id"], "name": item_tb["name"], "qty": 6.0, "price": 60.0, "tax_rate": 18.0}],
        branch_id=branch_id,
        party_name="TB CUSTOMER"
    )
    alerts_tb = [a for a in inventory_service.get_active_low_stock_alerts(COMPANY_ID) if a["item_id"] == item_tb["id"]]
    assert len(alerts_tb) == 1
    assert alerts_tb[0]["current_stock"] == 19.0
    assert alerts_tb[0]["status"] == "ACTIVE"

    # Case B: Reached via Fast Billing
    item_fb = _create_item(COMPANY_ID, branch_id, op_qty=25.0, reorder_lvl=20.0, min_lvl=10.0)
    bridge = BackendBridge()
    fast_payload = {
        "party_name": "CASH",
        "sale_type": "L/GST-18%",
        "payment_method": "CASH",
        "items": [{"id": item_fb["id"], "name": item_fb["name"], "qty": 7.0, "unit": "Pcs.", "price": 60.0, "tax_rate": 18.0}]
    }
    bridge.createSaleInvoice(COMPANY_ID, json.dumps(fast_payload))
    alerts_fb = [a for a in inventory_service.get_active_low_stock_alerts(COMPANY_ID) if a["item_id"] == item_fb["id"]]
    assert len(alerts_fb) == 1
    assert alerts_fb[0]["current_stock"] == 18.0
    assert alerts_fb[0]["status"] == "ACTIVE"


# ---------------------------------------------------------------------------
# Requirement 4 & 5: Consolidated notifications & correct branch identification
# ---------------------------------------------------------------------------
def test_req4_and_req5_authorised_roles_see_consolidated_notifications_with_branch():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_item(COMPANY_ID, branch_id, op_qty=15.0, reorder_lvl=20.0, min_lvl=10.0)

    # Authorised roles
    bridge = BackendBridge()
    for role in ["Business Owner", "Administrator", "Inventory Manager", "Store Manager"]:
        resp_raw = bridge.getLowStockNotifications(COMPANY_ID, "all", role)
        resp = json.loads(resp_raw)
        assert resp["success"] is True, f"Role {role} must be granted access."
        matching = [a for a in resp["data"] if a["item_id"] == item["id"]]
        assert len(matching) == 1
        notif = matching[0]
        # Verify requirement 5: Branch and product identification
        assert notif["product_name"] == item["name"]
        assert notif["branch_id"] == branch_id
        assert notif["branch_name"] != ""


# ---------------------------------------------------------------------------
# Requirement 6: Cashiers must not gain inventory management access
# ---------------------------------------------------------------------------
def test_req6_cashiers_cannot_gain_inventory_management_access():
    bridge = BackendBridge()
    for cashier_role in ["cashier", "pos_cashier", "fast_billing_cashier"]:
        resp_raw = bridge.getLowStockNotifications(COMPANY_ID, "all", cashier_role)
        resp = json.loads(resp_raw)
        assert resp["success"] is False, f"Role {cashier_role} must be denied access."
        assert "Access Denied" in resp["error"]


# ---------------------------------------------------------------------------
# Requirement 7 & 8: No duplicate deduction on printing; print failures do not reverse stock
# ---------------------------------------------------------------------------
def test_req7_and_req8_printing_and_reprinting_never_mutate_stock():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_item(COMPANY_ID, branch_id, op_qty=50.0)
    bridge = BackendBridge()

    # 1. Create sale
    vch = billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{"id": item["id"], "name": item["name"], "qty": 10.0, "price": 60.0, "tax_rate": 18.0}],
        branch_id=branch_id,
        party_name="PRINT TEST CUSTOMER"
    )
    vch_id = vch["voucher_id"]
    stock_after_sale = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)
    assert stock_after_sale == 40.0

    # 2. Print initial invoice (3 copies)
    print_resp_1 = json.loads(bridge.printInvoice(COMPANY_ID, vch_id, "thermal-80", "EPSON-TM-T82", 3))
    assert print_resp_1["success"] is True
    assert inventory_service.get_stock(COMPANY_ID, item["id"], branch_id) == 40.0, "Printing 3 copies must not deduct stock again."

    # 3. Reprint invoice (2 copies)
    print_resp_2 = json.loads(bridge.printInvoice(COMPANY_ID, vch_id, "a4", "HP LaserJet Pro", 2))
    assert print_resp_2["success"] is True
    assert inventory_service.get_stock(COMPANY_ID, item["id"], branch_id) == 40.0, "Reprinting invoice must not deduct stock again."

    # 4. Print failure test (non-existent printer or invalid voucher)
    failed_print = json.loads(bridge.printInvoice(COMPANY_ID, "non-existent-voucher-id", "thermal-80", "", 1))
    assert failed_print["success"] is False
    assert inventory_service.get_stock(COMPANY_ID, item["id"], branch_id) == 40.0, "Print failure must never alter existing stock."

    # Confirm movement ledger contains exactly 1 stock movement for this sale
    with db_manager.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM stock_movements WHERE item_id = ?;", (item["id"],)).fetchone()[0]
        assert count == 1, "Only 1 stock movement must exist; printing must not create movements."


# ---------------------------------------------------------------------------
# Requirement 9: Invoice modifications reconcile stock movements correctly
# ---------------------------------------------------------------------------
def test_req9_invoice_modifications_reconcile_stock_movements_correctly():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_item(COMPANY_ID, branch_id, op_qty=80.0)

    # 1. Initial sale of 10 units -> stock 70.0
    vch = billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{"id": item["id"], "name": item["name"], "qty": 10.0, "price": 60.0, "tax_rate": 18.0}],
        branch_id=branch_id,
        party_name="MODIFY PARTY"
    )
    vch_id = vch["voucher_id"]
    assert inventory_service.get_stock(COMPANY_ID, item["id"], branch_id) == 70.0

    # 2. Modify invoice upward to 15 units -> stock decreases by 5 additional units (becomes 65.0)
    billing_service.modify_sale_invoice(
        company_id=COMPANY_ID,
        vch_id=vch_id,
        items=[{"id": item["id"], "name": item["name"], "qty": 15.0, "price": 60.0, "tax_rate": 18.0}],
        branch_id=branch_id,
        party_name="MODIFY PARTY"
    )
    assert inventory_service.get_stock(COMPANY_ID, item["id"], branch_id) == 65.0, "Modifying invoice to 15 units must leave stock at 65.0."

    # 3. Modify invoice downward to 8 units -> stock increases by 7 units (becomes 72.0)
    billing_service.modify_sale_invoice(
        company_id=COMPANY_ID,
        vch_id=vch_id,
        items=[{"id": item["id"], "name": item["name"], "qty": 8.0, "price": 60.0, "tax_rate": 18.0}],
        branch_id=branch_id,
        party_name="MODIFY PARTY"
    )
    assert inventory_service.get_stock(COMPANY_ID, item["id"], branch_id) == 72.0, "Modifying invoice to 8 units must restore stock to 72.0."

    # Authoritative ledger check: Opening 80 - Sale 8 = 72
    summary = inventory_service.get_stock_summary(COMPANY_ID, branch_id)
    item_row = [s for s in summary if s["item_id"] == item["id"]][0]
    assert item_row["closing_stock"] == 72.0


# ---------------------------------------------------------------------------
# Requirement 10: Sales returns update inventory according to return rules
# ---------------------------------------------------------------------------
def test_req10_sales_returns_update_inventory_according_to_return_rules():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_item(COMPANY_ID, branch_id, op_qty=50.0)

    # Sell 20 units -> stock 30.0
    vch = billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{"id": item["id"], "name": item["name"], "qty": 20.0, "price": 60.0, "tax_rate": 18.0}],
        branch_id=branch_id,
        party_name="RETURN TEST PARTY"
    )
    vch_id = vch["voucher_id"]
    assert inventory_service.get_stock(COMPANY_ID, item["id"], branch_id) == 30.0

    # 1. Return 5 units in SALEABLE condition -> stock restored to 35.0
    billing_service.create_sales_return(
        company_id=COMPANY_ID,
        data={
            "original_voucher_id": vch_id,
            "branch_id": branch_id,
            "items": [{"item_id": item["id"], "name": item["name"], "qty": 5.0, "rate": 60.0, "tax_rate": 18.0, "restock_condition": "SALEABLE"}]
        }
    )
    assert inventory_service.get_stock(COMPANY_ID, item["id"], branch_id) == 35.0, "Saleable goods return must restore stock."

    # 2. Return 3 units in DAMAGED condition -> stock is NOT restored to saleable inventory
    billing_service.create_sales_return(
        company_id=COMPANY_ID,
        data={
            "original_voucher_id": vch_id,
            "branch_id": branch_id,
            "items": [{"item_id": item["id"], "name": item["name"], "qty": 3.0, "rate": 60.0, "tax_rate": 18.0, "restock_condition": "DAMAGED"}]
        }
    )
    assert inventory_service.get_stock(COMPANY_ID, item["id"], branch_id) == 35.0, "Damaged goods must not increase saleable inventory."


# ---------------------------------------------------------------------------
# Complete Acceptance Scenario Specified in User Prompt
# ---------------------------------------------------------------------------
def test_acceptance_scenario_complete_cross_module_workflow():
    """
    Executes the full user acceptance scenario:
    - Item created with Opening Stock: 100, Reorder Level: 20, Minimum Stock Level: 10
    - Traditional Billing sells 40 units (stock -> 60)
    - Fast Billing sells 30 units (stock -> 30)
    - Traditional Billing sells 10 units (stock -> 20) -> reorder notification triggered!
    - Fast Billing sells 5 units (stock -> 15) -> existing notification updated, no duplicates!
    - Record a valid purchase of 50 units (stock -> 65) -> notification resolved!
    - Confirm database quantities and inventory movement records.
    """
    branch_id = _get_default_branch(COMPANY_ID)
    bridge = BackendBridge()

    # Step 1: Create Item (Opening 100, Reorder 20, Min 10)
    item = _create_item(COMPANY_ID, branch_id, op_qty=100.0, reorder_lvl=20.0, min_lvl=10.0)
    initial_stock = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)
    assert initial_stock == 100.0, "Initial stock must be exactly 100 units."

    # Step 2: Traditional Billing sells 40 units
    billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{"id": item["id"], "name": item["name"], "qty": 40.0, "price": 60.0, "tax_rate": 18.0}],
        branch_id=branch_id,
        party_name="TB CUSTOMER 1"
    )
    stock_step2 = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)
    assert stock_step2 == 60.0, f"Expected stock 60 units after TB sells 40, got {stock_step2}"
    alerts_step2 = [a for a in inventory_service.get_active_low_stock_alerts(COMPANY_ID) if a["item_id"] == item["id"]]
    assert len(alerts_step2) == 0, "No notification should trigger at stock 60 (above reorder 20)."

    # Step 3: Fast Billing sells 30 units
    fb_payload_1 = {
        "party_name": "CASH",
        "sale_type": "L/GST-18%",
        "payment_method": "CASH",
        "items": [{"id": item["id"], "name": item["name"], "qty": 30.0, "unit": "Pcs.", "price": 60.0, "tax_rate": 18.0}],
        "narration": "Fast Billing Sale 30"
    }
    fb_resp_1 = json.loads(bridge.createSaleInvoice(COMPANY_ID, json.dumps(fb_payload_1)))
    assert fb_resp_1["success"] is True
    stock_step3 = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)
    assert stock_step3 == 30.0, f"Expected stock 30 units after FB sells 30, got {stock_step3}"
    alerts_step3 = [a for a in inventory_service.get_active_low_stock_alerts(COMPANY_ID) if a["item_id"] == item["id"]]
    assert len(alerts_step3) == 0, "No notification should trigger at stock 30 (above reorder 20)."

    # Step 4: Traditional Billing sells 10 units -> Expected stock: 100 - 40 - 30 - 10 = 20 units
    billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{"id": item["id"], "name": item["name"], "qty": 10.0, "price": 60.0, "tax_rate": 18.0}],
        branch_id=branch_id,
        party_name="TB CUSTOMER 2"
    )
    stock_step4 = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)
    assert stock_step4 == 20.0, f"Expected stock 20 units, got {stock_step4}"

    # Notification must trigger when stock reaches 20
    alerts_step4 = [a for a in inventory_service.get_active_low_stock_alerts(COMPANY_ID) if a["item_id"] == item["id"]]
    assert len(alerts_step4) == 1, "The system should trigger the reorder notification when stock reaches 20."
    first_alert = alerts_step4[0]
    assert first_alert["current_stock"] == 20.0
    assert first_alert["threshold"] == 20.0
    assert first_alert["status"] == "ACTIVE"
    first_alert_id = first_alert["alert_id"]

    # Step 5: Fast Billing sells another 5 units -> Expected stock: 15 units
    fb_payload_2 = {
        "party_name": "CASH",
        "sale_type": "L/GST-18%",
        "payment_method": "CASH",
        "items": [{"id": item["id"], "name": item["name"], "qty": 5.0, "unit": "Pcs.", "price": 60.0, "tax_rate": 18.0}],
        "narration": "Fast Billing Sale 5"
    }
    fb_resp_2 = json.loads(bridge.createSaleInvoice(COMPANY_ID, json.dumps(fb_payload_2)))
    assert fb_resp_2["success"] is True
    stock_step5 = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)
    assert stock_step5 == 15.0, f"Expected stock 15 units after FB sells 5, got {stock_step5}"

    # Existing notification must be updated without creating a duplicate
    with db_manager.get_connection() as conn:
        db_alert_rows = conn.execute("SELECT id, available_qty, status FROM low_stock_alerts WHERE company_id = ? AND item_id = ?;", (COMPANY_ID, item["id"])).fetchall()
        assert len(db_alert_rows) == 1, f"Expected exactly 1 alert row in database (no duplicates), got {len(db_alert_rows)}"
        assert db_alert_rows[0][0] == first_alert_id, "Existing alert ID must be preserved."
        assert db_alert_rows[0][1] == 15.0, "Existing alert available_qty must be updated to 15."

    alerts_step5 = [a for a in inventory_service.get_active_low_stock_alerts(COMPANY_ID) if a["item_id"] == item["id"]]
    assert len(alerts_step5) == 1
    assert alerts_step5[0]["current_stock"] == 15.0

    # Step 6: Record a valid purchase of 50 units -> Expected stock: 65 units
    purch_data = {
        "supplier_name": "ACCEPTANCE SUPPLIER",
        "supplier_invoice_no": f"PINV-{uuid.uuid4().hex[:6]}",
        "bill_no": f"BILL-{uuid.uuid4().hex[:6]}",
        "bill_date": datetime.now().strftime("%Y-%m-%d"),
        "branch_id": branch_id,
        "items": [{"item_id": item["id"], "qty": 50.0, "unit_price": 35.0, "tax_category": "GST 18%"}]
    }
    purch_resp = purchase_service.create_purchase_voucher(COMPANY_ID, purch_data)
    assert purch_resp.get("vch_no") is not None

    stock_step6 = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)
    assert stock_step6 == 65.0, f"Expected stock 65 units after purchase of 50, got {stock_step6}"

    # Low-stock alert should become resolved
    active_alerts_after_purc = [a for a in inventory_service.get_active_low_stock_alerts(COMPANY_ID) if a["item_id"] == item["id"]]
    assert len(active_alerts_after_purc) == 0, "Low-stock alert must be resolved after replenishing to 65 units."

    resolved_history = [a for a in inventory_service.get_active_low_stock_alerts(COMPANY_ID, filter_type="resolved") if a["item_id"] == item["id"]]
    assert len(resolved_history) >= 1
    assert resolved_history[0]["status"] == "RESOLVED"
    assert resolved_history[0]["resolved_at"] != ""

    # Step 7: Confirm actual database quantities and movement records
    with db_manager.get_connection() as conn:
        # Confirm stock_balances table
        cur_qty = conn.execute("SELECT current_qty FROM stock_balances WHERE branch_id = ? AND item_id = ?;", (branch_id, item["id"])).fetchone()[0]
        assert cur_qty == 65.0, f"Direct database stock_balances.current_qty must be 65.0, got {cur_qty}"

        # Confirm stock_movements ledger
        mov_rows = conn.execute("SELECT qty, movement_type, reference_type FROM stock_movements WHERE item_id = ? ORDER BY created_at ASC;", (item["id"],)).fetchall()
        assert len(mov_rows) == 5, f"Expected exactly 5 stock movements, got {len(mov_rows)}"

        # 40 TB, 30 FB, 10 TB, 5 FB, 50 Purchase
        assert mov_rows[0][0] == -40.0
        assert mov_rows[1][0] == -30.0
        assert mov_rows[2][0] == -10.0
        assert mov_rows[3][0] == -5.0
        assert mov_rows[4][0] == 50.0

        net_movement = sum(m[0] for m in mov_rows)
        assert net_movement == -35.0, f"Expected net movement -35.0, got {net_movement}"
        assert 100.0 + net_movement == 65.0, "Authoritative reconciliation: Opening 100 + Net -35 = 65.0"
