"""
Acceptance Test Suite for:
Alpha Billing – Minimum Stock Level, Reorder Level and Automatic Low-Stock Notifications

Verifies all 8 testing criteria specified in Section 9:
1. Notifications trigger when stock reaches the reorder level.
2. Notifications trigger when stock falls below it.
3. Notifications are not duplicated continuously.
4. Resolved alerts are handled correctly.
5. Branch-specific stock thresholds work correctly.
6. Failed transactions do not trigger false notifications.
7. Fast Billing cashiers cannot access restricted inventory alerts.
8. Notifications remain available after application restart.
"""
import json
import uuid
import pytest
from datetime import datetime

from db.database import db_manager
from services.billing_service import billing_service
from services.purchase_service import purchase_service
from services.catalogue_service import catalogue_service
from services.inventory_service import inventory_service, InventoryService
from desktop.web_bridge import BackendBridge


def _get_or_create_test_company() -> str:
    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT id FROM companies WHERE code = 'COMP0001' LIMIT 1;").fetchone()
        if row:
            return row[0]
        row2 = conn.execute("SELECT id FROM companies ORDER BY id ASC LIMIT 1;").fetchone()
        return row2[0] if row2 else "3a743bcd-8f9a-4154-a316-509cba3de99a"


COMPANY_ID = _get_or_create_test_company()


def _get_default_branch(company_id: str) -> str:
    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT id FROM branches WHERE company_id = ? ORDER BY is_default DESC, id ASC LIMIT 1;", (company_id,)).fetchone()
        if row:
            return row[0]
        new_id = str(uuid.uuid4())
        conn.execute("INSERT INTO branches (id, company_id, code, name, is_default) VALUES (?, ?, 'MAIN', 'Main Branch', 1);", (new_id, company_id))
        conn.commit()
        return new_id


def _create_test_customer(
    company_id: str,
    customer_name: str,
    customer_category: str = "Direct Customer"
) -> tuple:
    """Create a customer master record in the accounts table for non-cash sales testing.
    Appends a unique suffix to the customer name to ensure test isolation.

    Returns tuple of (account_id, unique_customer_name) for proper test isolation.
    """
    account_id = str(uuid.uuid4())
    unique_suffix = uuid.uuid4().hex[:6].upper()
    unique_name = f"{customer_name}-{unique_suffix}"
    with db_manager.get_connection() as conn:
        conn.execute("""
            INSERT INTO accounts (
                id, company_id, name, alias, print_name, account_group,
                customer_category, is_active
            ) VALUES (?, ?, ?, ?, ?, 'Sundry Debtors', ?, 1);
        """, (account_id, company_id, unique_name, '', unique_name, customer_category))
        conn.commit()
    return account_id, unique_name


def _create_configured_item(
    company_id: str,
    branch_id: str,
    initial_qty: float,
    reorder_level: float = 15.0,
    min_stock_level: float = 10.0,
    reorder_qty: float = 25.0,
    max_stock_level: float = None,
    alert_enabled: int = 1,
) -> dict:
    """Create a configured item with specific stock thresholds for low-stock notification testing."""
    item_name = f"TEST-ITEM-{uuid.uuid4().hex[:8].upper()}"
    barcode = f"BARCODE-{uuid.uuid4().hex[:12].upper()}"

    item_data = {
        "company_id": company_id,
        "name": item_name,
        "alias": barcode,
        "branch_id": branch_id,
        "op_stock_qty": initial_qty,
        "min_stock_level": min_stock_level,
        "reorder_level": reorder_level,
        "reorder_qty": reorder_qty,
        "max_stock_level": max_stock_level,
        "alert_enabled": alert_enabled,
        "sales_price": 100.0,
        "purc_price": 65.0,
    }

    result = catalogue_service.save_item(company_id, item_data)

    actual_stock = inventory_service.get_stock(company_id, result["id"], branch_id)

    return {
        "id": result["id"],
        "name": item_name,
        "barcode": barcode,
        "branch_id": branch_id,
        "initial_qty": initial_qty,
        "reorder_level": reorder_level,
        "min_stock_level": min_stock_level,
        "reorder_qty": reorder_qty,
        "max_stock_level": max_stock_level,
        "alert_enabled": alert_enabled,
        "current_stock": actual_stock,
    }


# ---------------------------------------------------------------------------
# Criterion 1: Notifications trigger when stock reaches the reorder level
# ---------------------------------------------------------------------------
def test_criterion_1_notification_triggers_when_reaching_reorder_level():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_configured_item(
        company_id=COMPANY_ID,
        branch_id=branch_id,
        initial_qty=20.0,
        reorder_level=15.0,
        min_stock_level=10.0
    )

    # Initially at 20.0 (above reorder level 15.0) -> no alert
    alerts = inventory_service.evaluate_low_stock_alerts(COMPANY_ID, branch_id)
    assert not any(a["item_id"] == item["id"] for a in alerts)

    # Create customer master for non-cash sale
    _, customer_name = _create_test_customer(COMPANY_ID, "REACH THRESHOLD CUSTOMER")

    # Sale of exactly 5.0 -> stock becomes exactly 15.0 (Available Stock == Reorder Level)
    billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{"id": item["id"], "name": item["name"], "qty": 5.0, "price": 100.0, "tax_rate": 18.0}],
        branch_id=branch_id,
        party_name=customer_name,
        series="Main"
    )

    # Verify notification triggers
    active_alerts = inventory_service.get_active_low_stock_alerts(COMPANY_ID)
    matching = [a for a in active_alerts if a["item_id"] == item["id"]]
    assert len(matching) == 1, "Notification must trigger when available stock reaches reorder level exactly."
    alert = matching[0]
    assert alert["current_stock"] == 15.0
    assert alert["threshold"] == 15.0
    assert alert["severity"] == "REORDER_REQUIRED"
    assert alert["status"] == "ACTIVE"


# ---------------------------------------------------------------------------
# Criterion 2: Notifications trigger when stock falls below reorder level
# ---------------------------------------------------------------------------
def test_criterion_2_notification_triggers_when_falling_below_reorder_level():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_configured_item(
        company_id=COMPANY_ID,
        branch_id=branch_id,
        initial_qty=20.0,
        reorder_level=15.0,
        min_stock_level=10.0,
        max_stock_level=50.0
    )

    # Create customer master for non-cash sale
    _, customer_name = _create_test_customer(COMPANY_ID, "FALL BELOW CUSTOMER")

    # Sale of 12.0 -> stock becomes 8.0 (below reorder level 15.0 and below min stock 10.0)
    billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{"id": item["id"], "name": item["name"], "qty": 12.0, "price": 100.0, "tax_rate": 18.0}],
        branch_id=branch_id,
        party_name=customer_name,
        series="Main"
    )

    active_alerts = inventory_service.get_active_low_stock_alerts(COMPANY_ID)
    matching = [a for a in active_alerts if a["item_id"] == item["id"]]
    assert len(matching) == 1
    alert = matching[0]
    assert alert["current_stock"] == 8.0
    assert alert["shortfall"] == 7.0  # 15.0 - 8.0
    assert alert["severity"] == "CRITICAL", "Stock below min_stock_level must trigger CRITICAL severity."
    # Suggested reorder: target stock (50.0) - available stock (8.0) = 42.0 (matching prompt example!)
    assert alert["suggested_reorder_qty"] == 42.0


# ---------------------------------------------------------------------------
# Criterion 3: Notifications are not duplicated continuously
# ---------------------------------------------------------------------------
def test_criterion_3_notifications_not_duplicated_continuously():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_configured_item(
        company_id=COMPANY_ID,
        branch_id=branch_id,
        initial_qty=14.0,  # Below reorder level 15.0
        reorder_level=15.0,
        min_stock_level=10.0
    )

    # Initial evaluation creates 1 alert
    alerts1 = inventory_service.evaluate_low_stock_alerts(COMPANY_ID, branch_id)
    matching1 = [a for a in alerts1 if a["item_id"] == item["id"]]
    assert len(matching1) == 1
    first_alert_id = matching1[0]["alert_id"]

    # Create customer masters for non-cash sales
    _, customer_name1 = _create_test_customer(COMPANY_ID, "SUBSEQUENT SALE 1")
    _, customer_name2 = _create_test_customer(COMPANY_ID, "SUBSEQUENT SALE 2")

    # Subsequent sale 1: sell 2 units (stock 12.0)
    billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{"id": item["id"], "name": item["name"], "qty": 2.0, "price": 100.0, "tax_rate": 18.0}],
        branch_id=branch_id,
        party_name=customer_name1,
        series="Main"
    )

    # Subsequent sale 2: sell 3 units (stock 9.0)
    billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{"id": item["id"], "name": item["name"], "qty": 3.0, "price": 100.0, "tax_rate": 18.0}],
        branch_id=branch_id,
        party_name=customer_name2,
        series="Main"
    )

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, available_qty, status FROM low_stock_alerts WHERE company_id = ? AND item_id = ?;", (COMPANY_ID, item["id"]))
        rows = cursor.fetchall()
        # MUST remain exactly 1 row; not duplicated for each sale!
        assert len(rows) == 1, f"Expected exactly 1 alert row in database, got {len(rows)}"
        assert rows[0]["id"] == first_alert_id, "Alert ID must be preserved and updated."
        assert rows[0]["available_qty"] == 9.0, "Stock quantity must be updated to 9.0 on existing alert."


# ---------------------------------------------------------------------------
# Criterion 4: Resolved alerts are handled correctly & cycle properly
# ---------------------------------------------------------------------------
def test_criterion_4_resolved_alerts_handled_correctly():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_configured_item(
        company_id=COMPANY_ID,
        branch_id=branch_id,
        initial_qty=12.0,  # Below reorder level 15.0
        reorder_level=15.0,
        min_stock_level=10.0
    )

    inventory_service.evaluate_low_stock_alerts(COMPANY_ID, branch_id)
    active1 = inventory_service.get_active_low_stock_alerts(COMPANY_ID)
    assert any(a["item_id"] == item["id"] for a in active1)

    # Replenish stock via purchase of 20 units -> stock becomes 32.0 (> 15.0 threshold)
    purchase_service.create_purchase_voucher(
        company_id=COMPANY_ID,
        data={
            "supplier_name": "REPLENISHMENT SUPPLIER",
            "supplier_invoice_no": f"PUR-{uuid.uuid4().hex[:6]}",
            "bill_no": f"PUR-{uuid.uuid4().hex[:6]}",
            "bill_date": datetime.now().strftime("%Y-%m-%d"),
            "branch_id": branch_id,
            "items": [{"item_id": item["id"], "qty": 20.0, "unit_price": 65.0, "tax_category": "GST 18%"}]
        }
    )

    # Active alerts should NO LONGER contain this item
    active_now = inventory_service.get_active_low_stock_alerts(COMPANY_ID)
    assert not any(a["item_id"] == item["id"] for a in active_now), "Alert must be resolved when stock replenished above threshold."

    # But resolved notifications filter MUST contain it in historical log
    resolved = inventory_service.get_active_low_stock_alerts(COMPANY_ID, filter_type="resolved")
    matching_resolved = [r for r in resolved if r["item_id"] == item["id"]]
    assert len(matching_resolved) >= 1
    assert matching_resolved[0]["status"] == "RESOLVED"
    assert matching_resolved[0]["resolved_at"] != ""

    # Create customer master for non-cash sale
    _, customer_name = _create_test_customer(COMPANY_ID, "RE-BREACH CUSTOMER")

    # Now drop stock below threshold again (sale of 20 units -> stock becomes 12.0 <= 15.0)
    billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{"id": item["id"], "name": item["name"], "qty": 20.0, "price": 100.0, "tax_rate": 18.0}],
        branch_id=branch_id,
        party_name=customer_name,
        series="Main"
    )

    # A NEW notification event must be generated
    active_again = inventory_service.get_active_low_stock_alerts(COMPANY_ID)
    re_breached = [a for a in active_again if a["item_id"] == item["id"]]
    assert len(re_breached) == 1
    assert re_breached[0]["status"] == "ACTIVE"

    # In database, both the old resolved alert and new active alert exist (history preserved)
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM low_stock_alerts WHERE company_id = ? AND item_id = ?;", (COMPANY_ID, item["id"]))
        statuses = [r[0] for r in cursor.fetchall()]
        assert "RESOLVED" in statuses
        assert "ACTIVE" in statuses


# ---------------------------------------------------------------------------
# Criterion 5: Branch-specific stock thresholds work correctly
# ---------------------------------------------------------------------------
def test_criterion_5_branch_specific_stock_thresholds():
    # Create two isolated branches
    branch_a = str(uuid.uuid4())
    branch_b = str(uuid.uuid4())
    with db_manager.get_connection() as conn:
        conn.execute("INSERT INTO branches (id, company_id, code, name, is_default) VALUES (?, ?, ?, 'Branch A', 0);", (branch_a, COMPANY_ID, f"BRA-{uuid.uuid4().hex[:4]}"))
        conn.execute("INSERT INTO branches (id, company_id, code, name, is_default) VALUES (?, ?, ?, 'Branch B', 0);", (branch_b, COMPANY_ID, f"BRB-{uuid.uuid4().hex[:4]}"))
        conn.commit()

    # Create item with company default reorder level = 20.0, initial stock = 10.0 in both branches
    item = _create_configured_item(
        company_id=COMPANY_ID,
        branch_id=branch_a,
        initial_qty=10.0,
        reorder_level=20.0,
        min_stock_level=15.0
    )
    with db_manager.get_connection() as conn:
        conn.execute("""
            INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
            VALUES (?, ?, ?, ?, 10.0);
        """, (str(uuid.uuid4()), COMPANY_ID, branch_b, item["id"]))
        conn.commit()

    # Configure Branch B override: reorder_level = 5.0, min_stock_level = 2.0
    catalogue_service.set_item_branch_config(
        company_id=COMPANY_ID,
        branch_id=branch_b,
        item_id=item["id"],
        config_data={
            "reorder_level": 5.0,
            "min_stock_level": 2.0,
            "alert_enabled": 1
        }
    )

    alerts = inventory_service.evaluate_low_stock_alerts(COMPANY_ID)
    item_alerts_branch_a = [a for a in alerts if a["item_id"] == item["id"] and a["branch_id"] == branch_a]
    item_alerts_branch_b = [a for a in alerts if a["item_id"] == item["id"] and a["branch_id"] == branch_b]

    # Branch A: 10.0 <= default reorder level 20.0 -> TRIGGERS alert!
    assert len(item_alerts_branch_a) == 1
    assert item_alerts_branch_a[0]["threshold"] == 20.0

    # Branch B: 10.0 > branch override reorder level 5.0 -> DOES NOT TRIGGER alert!
    assert len(item_alerts_branch_b) == 0, "Branch B override threshold (5.0) must take precedence over default (20.0)."


# ---------------------------------------------------------------------------
# Criterion 6: Failed transactions do not trigger false notifications
# ---------------------------------------------------------------------------
def test_criterion_6_failed_transactions_do_not_trigger_false_notifications():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_configured_item(
        company_id=COMPANY_ID,
        branch_id=branch_id,
        initial_qty=30.0,
        reorder_level=15.0,
        min_stock_level=10.0
    )

    # Ensure negative stock is disabled so overselling triggers rollback
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM company_configs WHERE company_id = ?;", (COMPANY_ID,))
        if cursor.fetchone():
            cursor.execute("UPDATE company_configs SET allow_negative_stock = 0 WHERE company_id = ?;", (COMPANY_ID,))
        else:
            cursor.execute("INSERT INTO company_configs (company_id, allow_negative_stock) VALUES (?, 0);", (COMPANY_ID,))
        conn.commit()

    # Attempt a transaction that oversells (requesting 9999.0 when only 30.0 available)
    with pytest.raises(Exception):
        billing_service.create_sale_invoice(
            company_id=COMPANY_ID,
            items=[{"id": item["id"], "name": item["name"], "qty": 9999.0, "price": 100.0, "tax_rate": 18.0}],
            branch_id=branch_id,
            party_name="FAILED SALE",
            series="Main"
        )

    # Verify stock remained unchanged at 30.0
    current_stock = inventory_service.get_stock(COMPANY_ID, item["id"], branch_id)
    assert current_stock == 30.0

    # Verify no false notification was generated
    active_alerts = inventory_service.get_active_low_stock_alerts(COMPANY_ID)
    assert not any(a["item_id"] == item["id"] for a in active_alerts)


# ---------------------------------------------------------------------------
# Criterion 7: Fast Billing cashiers cannot access restricted inventory alerts
# ---------------------------------------------------------------------------
def test_criterion_7_fast_billing_cashiers_cannot_access_restricted_inventory_alerts():
    import tests.test_phase4_security_and_authorization as auth_tests

    # Test 1: Unauthenticated user gets authentication error
    bridge = BackendBridge()
    unauth_resp_raw = bridge.getLowStockNotifications(COMPANY_ID, "all", None)
    unauth_resp = json.loads(unauth_resp_raw)
    assert unauth_resp["success"] is False
    assert "Authentication" in unauth_resp["error"] or "authenticated" in unauth_resp["error"].lower(), \
        "Unauthenticated user must receive authentication error."

    # Test 2: Administrator (authenticated) gets full access to low stock notifications
    admin_bridge = auth_tests.create_authenticated_bridge("Administrator")
    admin_resp_raw = admin_bridge.getLowStockNotifications(COMPANY_ID, "all", None)
    admin_resp = json.loads(admin_resp_raw)
    assert admin_resp["success"] is True, f"Administrator should get access, got error: {admin_resp}"
    assert isinstance(admin_resp["data"], list)

    # Test 3: POS Cashier (authenticated) gets denied access
    pos_cashier_bridge = auth_tests.create_authenticated_bridge("POS_Cashier")
    pos_cashier_raw = pos_cashier_bridge.getLowStockNotifications(COMPANY_ID, "critical", None)
    pos_cashier_resp = json.loads(pos_cashier_raw)
    assert pos_cashier_resp["success"] is False
    assert "Access Denied" in pos_cashier_resp["error"], \
        "POS Cashier must be denied access to stock notifications."

    # Test 4: Fast Billing Cashier (authenticated) gets denied access
    fb_cashier_bridge = auth_tests.create_authenticated_bridge("Fast_Billing_Cashier")
    fb_cashier_raw = fb_cashier_bridge.getLowStockNotifications(COMPANY_ID, "all", None)
    fb_cashier_resp = json.loads(fb_cashier_raw)
    assert fb_cashier_resp["success"] is False
    assert "Access Denied" in fb_cashier_resp["error"], \
        "Fast Billing Cashier must be denied access to stock notifications."

    # Test 5: Cashier barcode search strictly hides valuation and stock metrics
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_configured_item(COMPANY_ID, branch_id, initial_qty=50.0)
    cashier_item = catalogue_service.get_cashier_item_by_barcode(COMPANY_ID, item["barcode"])
    assert cashier_item is not None
    assert "sales_price" in cashier_item
    assert "purc_price" not in cashier_item, "Purchase price / cost must be hidden from cashier."
    assert "current_stock" not in cashier_item, "Stock quantity must be hidden from cashier."
    assert "stock_value" not in cashier_item, "Stock valuation must be hidden from cashier."


# ---------------------------------------------------------------------------
# Criterion 8: Notifications remain available after application restart
# ---------------------------------------------------------------------------
def test_criterion_8_notifications_persist_across_application_restart():
    branch_id = _get_default_branch(COMPANY_ID)
    item = _create_configured_item(
        company_id=COMPANY_ID,
        branch_id=branch_id,
        initial_qty=7.0,  # Below reorder 15 and min 10
        reorder_level=15.0,
        min_stock_level=10.0,
        reorder_qty=40.0,
        max_stock_level=None
    )

    # Generate alert
    initial_alerts = inventory_service.evaluate_low_stock_alerts(COMPANY_ID, branch_id)
    matching = [a for a in initial_alerts if a["item_id"] == item["id"]]
    assert len(matching) == 1
    alert_id = matching[0]["alert_id"]

    # Simulate fresh application restart: instantiate a brand new InventoryService instance
    restarted_service = InventoryService()
    persisted_alerts = restarted_service.get_active_low_stock_alerts(COMPANY_ID)
    persisted_matching = [a for a in persisted_alerts if a["item_id"] == item["id"]]

    assert len(persisted_matching) == 1, "Alert must persist in SQLite database across application restarts."
    persisted = persisted_matching[0]
    assert persisted["alert_id"] == alert_id
    assert persisted["current_stock"] == 7.0
    assert persisted["threshold"] == 15.0
    assert persisted["severity"] == "CRITICAL"
    assert persisted["suggested_reorder_qty"] == 40.0
    assert persisted["status"] == "ACTIVE"
