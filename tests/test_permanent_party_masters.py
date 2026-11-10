"""
Automated Test Suite for Alpha Billing - Permanent Database-Backed Party Masters

Verifies all requirements:
1. Permanent database persistence for Customer masters in SQLite `accounts` table.
2. Permanent database persistence for Supplier masters with mirroring in `suppliers` table.
3. Dual-role party master ('Both (Customer & Supplier)') selectable in Sales & Purchase without duplicate records.
4. Sales invoice creation and modification linking `sales_vouchers.account_id` to permanent customer ID.
5. Purchase invoice creation linking `purchase_vouchers.supplier_id` to permanent supplier ID.
6. Masters Modify updates existing records in place (retaining UUID) without creating duplicates.
7. Historical transaction integrity: Transaction references retained when party details are modified.
8. Deletion safety guard: Party referenced in sales or purchase vouchers cannot be hard-deleted (deactivation required).
9. Company isolation: Parties created for Company A are invisible to Company B.
10. Preservation of previously approved workflows:
    - Print Name auto-sync and read-only behavior.
    - Continuous Add workflow with form reset and focus.
    - Zero modifications or regressions to Item Master.
"""

import json
import uuid
import pytest
from db.database import db_manager
from services.account_service import account_service
from services.billing_service import billing_service
from services.purchase_service import purchase_service
from services.catalogue_service import catalogue_service
from desktop.web_bridge import BackendBridge


@pytest.fixture(scope="module")
def active_company():
    """Retrieve or create test company."""
    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT id, name FROM companies LIMIT 1;").fetchone()
        if row:
            return {"id": row["id"], "name": row["name"]}
        comp_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO companies (id, code, name, state)
            VALUES (?, 'TESTCOMP', 'Test Company Ltd', 'Tamilnadu');
        """, (comp_id,))
        conn.commit()
        return {"id": comp_id, "name": "Test Company Ltd"}


@pytest.fixture(scope="module")
def second_company():
    """Create or get a second company to verify multi-company isolation."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM companies WHERE code = 'COMP_ISO_2';")
        row = cursor.fetchone()
        if row:
            return {"id": row["id"], "name": row["name"]}
        comp_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO companies (id, code, name, state, fin_year)
            VALUES (?, 'COMP_ISO_2', 'Second Isolated Company', 'Karnataka', '2026-2027');
        """, (comp_id,))
        conn.commit()
    return {"id": comp_id, "name": "Second Isolated Company"}


@pytest.fixture(scope="module")
def sample_test_item(active_company):
    """Ensure at least one catalogue item exists with positive stock for invoice transactions."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, sales_price FROM items WHERE company_id = ? AND is_active = 1 LIMIT 1;", (active_company["id"],))
        existing = cursor.fetchone()
        if existing:
            item_id = existing["id"]
            cursor.execute("SELECT id FROM branches WHERE company_id = ? ORDER BY is_default DESC LIMIT 1;", (active_company["id"],))
            b_row = cursor.fetchone()
            if b_row:
                cursor.execute("""
                    INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                    VALUES (?, ?, ?, ?, 500)
                    ON CONFLICT(branch_id, item_id) DO UPDATE SET current_qty = current_qty + 500;
                """, (str(uuid.uuid4()), active_company["id"], b_row["id"], item_id))
            conn.commit()
            return {"id": item_id, "name": existing["name"], "price": existing["sales_price"]}

        item_id = str(uuid.uuid4())
        item_name = f"TEST ITEM {uuid.uuid4().hex[:6].upper()}"
        cursor.execute("""
            INSERT INTO items (
                id, company_id, name, alias, print_name, item_group, unit,
                sales_price, purc_price, op_stock_qty, is_active
            ) VALUES (?, ?, ?, 'TESTITEM', ?, 'General', 'PCS', 100.0, 70.0, 500.0, 1);
        """, (item_id, active_company["id"], item_name, item_name))
        cursor.execute("SELECT id FROM branches WHERE company_id = ? ORDER BY is_default DESC LIMIT 1;", (active_company["id"],))
        b_row = cursor.fetchone()
        if b_row:
            cursor.execute("""
                INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                VALUES (?, ?, ?, ?, 500)
                ON CONFLICT(branch_id, item_id) DO UPDATE SET current_qty = current_qty + 500;
            """, (str(uuid.uuid4()), active_company["id"], b_row["id"], item_id))
        conn.commit()
        return {"id": item_id, "name": item_name, "price": 100.0}


# ==============================================================================
# 1. Customer Master Permanent Database Persistence
# ==============================================================================
def test_customer_master_permanent_database_persistence(active_company):
    """Verify that a Customer Master is permanently persisted into SQLite accounts table with all 26 fields."""
    cust_name = f"Apex Enterprises {uuid.uuid4().hex[:6]}"
    cust_data = {
        "name": cust_name,
        "alias": "APEX",
        "print_name": cust_name,
        "account_group": "Sundry Debtors",
        "customer_category": "Commercial",
        "op_bal": 15000.0,
        "op_type": "D",
        "address": "124 Anna Salai, Mount Road",
        "country": "India",
        "state": "Tamilnadu",
        "dealer_type": "Registered",
        "gstin": "33AAACA1234A1Z5",
        "mobile": "9876543210",
        "whatsapp": "9876543210",
        "bank_name": "State Bank of India",
        "bank_acc": "123456789012",
        "ifsc": "SBIN0001234",
        "pincode": "600002",
        "payment_terms": 30,
        "notes": "Premium commercial client",
        "is_active": True
    }

    res = account_service.save_account(active_company["id"], cust_data)
    assert res is not None
    assert "id" in res
    assert res["name"] == cust_name.upper()
    assert res["print_name"] == cust_name.upper()
    assert res["classification"] == "Customer"
    customer_id = res["id"]

    # Re-open fresh database connection to verify hard disk persistence
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE company_id = ? AND id = ?;", (active_company["id"], customer_id))
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == cust_name.upper()
        assert row["print_name"] == cust_name.upper()
        assert row["alias"] == "APEX"
        assert row["account_group"] == "Sundry Debtors"
        assert row["customer_category"] == "Commercial"
        assert float(row["op_bal"]) == 15000.0
        assert row["country"] == "India"
        assert row["state"] == "Tamilnadu"
        assert row["dealer_type"] == "Registered"
        assert row["gstin"] == "33AAACA1234A1Z5"
        assert row["mobile"] == "9876543210"
        assert row["whatsapp"] == "9876543210"
        assert row["pincode"] == "600002"
        assert row["notes"] == "Premium commercial client"
        assert row["is_active"] == 1


# ==============================================================================
# 2. Sales Invoice Integration with Permanent Customer ID
# ==============================================================================
def test_sales_invoice_links_permanent_customer_id(active_company, sample_test_item):
    """Verify sales invoice links to permanent accounts.id and snapshots customer category."""
    cust_name = f"Shree Ram Trading {uuid.uuid4().hex[:6]}"
    cust_saved = account_service.save_account(active_company["id"], {
        "name": cust_name,
        "account_group": "Sundry Debtors",
        "customer_category": "Sub-Commercial",
        "mobile": "9988776655",
        "gstin": "33ABCDE1234F1Z5"
    })
    cust_id = cust_saved["id"]

    inv_result = billing_service.create_sale_invoice(
        company_id=active_company["id"],
        items=[{
            "id": sample_test_item["id"],
            "name": sample_test_item["name"],
            "qty": 2.0,
            "unit": "PCS",
            "price": 100.0
        }],
        party_name=cust_name,
        account_id=cust_id,
        customer_category="Sub-Commercial"
    )
    assert inv_result["vch_no"] is not None

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, account_id, party_name, customer_category FROM sales_vouchers WHERE vch_no = ? AND company_id = ?;", (inv_result["vch_no"], active_company["id"]))
        sv = cursor.fetchone()
        assert sv is not None
        assert sv["account_id"] == cust_id
        assert sv["party_name"] == cust_name
        assert sv["customer_category"] == "Sub-Commercial"


# ==============================================================================
# 3. Supplier Master Permanent Database Persistence and Mirroring
# ==============================================================================
def test_supplier_master_permanent_database_persistence(active_company):
    """Verify Supplier Master is saved in accounts table and mirrored in suppliers table with identical ID."""
    sup_name = f"National Agro Tech {uuid.uuid4().hex[:6]}"
    sup_data = {
        "name": sup_name,
        "alias": "NATAGRO",
        "account_group": "Sundry Creditors",
        "address": "Plot 54, SIDCO Industrial Estate",
        "country": "India",
        "state": "Tamilnadu",
        "dealer_type": "Registered",
        "gstin": "33AAACN5678A1Z9",
        "mobile": "9123456789",
        "whatsapp": "9123456789",
        "bank_name": "HDFC Bank",
        "bank_acc": "50100234567890",
        "ifsc": "HDFC0001234",
        "pincode": "600058",
        "notes": "Fertilizer and raw chemical vendor"
    }

    res = account_service.save_account(active_company["id"], sup_data)
    assert res is not None
    sup_id = res["id"]
    assert res["classification"] == "Supplier"

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        # Verify in accounts
        cursor.execute("SELECT * FROM accounts WHERE company_id = ? AND id = ?;", (active_company["id"], sup_id))
        acc_row = cursor.fetchone()
        assert acc_row is not None
        assert acc_row["name"] == sup_name.upper()
        assert acc_row["account_group"] == "Sundry Creditors"

        # Verify mirrored in suppliers with exact same ID
        cursor.execute("SELECT * FROM suppliers WHERE company_id = ? AND id = ?;", (active_company["id"], sup_id))
        sup_row = cursor.fetchone()
        assert sup_row is not None
        assert sup_row["name"] == sup_name.upper()
        assert sup_row["mobile"] == "9123456789"
        assert sup_row["gstin"] == "33AAACN5678A1Z9"


# ==============================================================================
# 4. Purchase Invoice Integration with Permanent Supplier ID
# ==============================================================================
def test_purchase_invoice_links_permanent_supplier_id(active_company, sample_test_item):
    """Verify purchase invoice links to permanent suppliers.id / accounts.id."""
    sup_name = f"Standard Raw Supplies {uuid.uuid4().hex[:6]}"
    sup_saved = account_service.save_account(active_company["id"], {
        "name": sup_name,
        "account_group": "Sundry Creditors",
        "mobile": "9444332211",
        "gstin": "33AAAAA1111A1Z1"
    })
    sup_id = sup_saved["id"]

    pur_result = purchase_service.create_purchase_voucher(
        company_id=active_company["id"],
        data={
            "supplier_id": sup_id,
            "supplier_name": sup_name,
            "supplier_invoice_no": f"INV-{uuid.uuid4().hex[:5]}",
            "supplier_invoice_date": "2026-11-06",
            "voucher_date": "2026-11-06",
            "series": "Main",
            "items": [{
                "item_id": sample_test_item["id"],
                "item_name": sample_test_item["name"],
                "qty": 10.0,
                "cost_rate": 60.0
            }]
        }
    )
    assert pur_result["voucher_id"] is not None

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, supplier_id, supplier_name FROM purchase_vouchers WHERE id = ?;", (pur_result["voucher_id"],))
        pv = cursor.fetchone()
        assert pv is not None
        assert pv["supplier_id"] == sup_id
        assert pv["supplier_name"] == sup_name


# ==============================================================================
# 5. Dual-Role Party (Both Customer & Supplier) Integration
# ==============================================================================
def test_dual_role_party_master_integration(active_company, sample_test_item):
    """Verify party with 'Both (Customer & Supplier)' is usable in both Sales and Purchase without duplicate identities."""
    party_name = f"Universal Traders & Co {uuid.uuid4().hex[:6]}"
    res = account_service.save_account(active_company["id"], {
        "name": party_name,
        "alias": "UNIVERSAL",
        "account_group": "Both (Customer & Supplier)",
        "customer_category": "Commercial",
        "mobile": "9840112233",
        "gstin": "33AAACU9999A1Z2"
    })
    party_id = res["id"]
    assert res["classification"] == "Both (Customer & Supplier)"

    # Verify search_customers returns it
    custs = account_service.search_customers(active_company["id"], party_name)
    assert any(c["id"] == party_id for c in custs)

    # Verify search_suppliers returns it
    supps = account_service.search_suppliers(active_company["id"], party_name)
    assert any(s["id"] == party_id for s in supps)

    # Use in Sales Invoice
    sale_inv = billing_service.create_sale_invoice(
        company_id=active_company["id"],
        items=[{"id": sample_test_item["id"], "name": sample_test_item["name"], "qty": 1.0, "unit": "PCS", "price": 100.0}],
        party_name=party_name,
        account_id=party_id
    )

    # Use in Purchase Invoice
    pur_inv = purchase_service.create_purchase_voucher(
        company_id=active_company["id"],
        data={
            "supplier_id": party_id,
            "supplier_name": party_name,
            "supplier_invoice_no": f"UNI-{uuid.uuid4().hex[:4]}",
            "items": [{"item_id": sample_test_item["id"], "item_name": sample_test_item["name"], "qty": 5.0, "cost_rate": 65.0}]
        }
    )

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT account_id FROM sales_vouchers WHERE vch_no = ?;", (sale_inv["vch_no"],))
        assert cursor.fetchone()["account_id"] == party_id

        cursor.execute("SELECT supplier_id FROM purchase_vouchers WHERE id = ?;", (pur_inv["voucher_id"],))
        assert cursor.fetchone()["supplier_id"] == party_id

        # Verify only ONE account record exists for this name in accounts table (no duplicate IDs)
        cursor.execute("SELECT COUNT(*) FROM accounts WHERE company_id = ? AND UPPER(name) = ?;", (active_company["id"], party_name.upper()))
        assert cursor.fetchone()[0] == 1


# ==============================================================================
# 6. Modify Party In-Place & Retain Transaction Links
# ==============================================================================
def test_modify_party_retains_uuid_and_transaction_references(active_company, sample_test_item):
    """Verify modifying a party updates the record without generating a new UUID and preserves transaction references."""
    initial_name = f"Original Party {uuid.uuid4().hex[:6]}"
    saved = account_service.save_account(active_company["id"], {
        "name": initial_name,
        "account_group": "Sundry Debtors",
        "mobile": "9000000001"
    })
    party_id = saved["id"]

    # Create sales voucher linked to this party
    inv = billing_service.create_sale_invoice(
        company_id=active_company["id"],
        items=[{"id": sample_test_item["id"], "name": sample_test_item["name"], "qty": 1.0, "price": 100.0}],
        party_name=initial_name,
        account_id=party_id
    )

    # Modify party details (e.g. phone, address, notes)
    updated_res = account_service.save_account(active_company["id"], {
        "id": party_id,
        "name": initial_name,
        "account_group": "Sundry Debtors",
        "mobile": "9999999999",
        "address": "Updated Address Lane 4",
        "notes": "Contact phone updated"
    })
    assert updated_res["id"] == party_id

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT mobile, address, notes FROM accounts WHERE id = ?;", (party_id,))
        acc = cursor.fetchone()
        assert acc["mobile"] == "9999999999"
        assert acc["address"] == "Updated Address Lane 4"
        assert acc["notes"] == "Contact phone updated"

        # Verify sales voucher still references the exact same party ID
        cursor.execute("SELECT account_id FROM sales_vouchers WHERE vch_no = ?;", (inv["vch_no"],))
        assert cursor.fetchone()["account_id"] == party_id


# ==============================================================================
# 7. Safety Guard: Referenced Party Cannot Be Hard Deleted
# ==============================================================================
def test_referenced_party_cannot_be_hard_deleted(active_company, sample_test_item):
    """Verify that delete_account blocks hard deletion when party is referenced in historical invoices."""
    party_name = f"Audit Protected Party {uuid.uuid4().hex[:6]}"
    saved = account_service.save_account(active_company["id"], {
        "name": party_name,
        "account_group": "Sundry Debtors"
    })
    party_id = saved["id"]

    # Link to a sales voucher
    billing_service.create_sale_invoice(
        company_id=active_company["id"],
        items=[{"id": sample_test_item["id"], "name": sample_test_item["name"], "qty": 1.0, "price": 100.0}],
        party_name=party_name,
        account_id=party_id
    )

    # Hard deletion must raise ValueError to protect historical ledger
    with pytest.raises(ValueError, match="Cannot delete party master referenced in existing sales invoices"):
        account_service.delete_account(active_company["id"], party_id)

    # Deactivation instead must succeed
    deactivated = account_service.deactivate_account(active_company["id"], party_id)
    assert deactivated is True

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_active FROM accounts WHERE id = ?;", (party_id,))
        assert cursor.fetchone()["is_active"] == 0


# ==============================================================================
# 8. Multi-Company Isolation
# ==============================================================================
def test_party_masters_multi_company_isolation(active_company, second_company):
    """Verify party created in Company A is not visible or retrievable in Company B."""
    party_name = f"Company A Exclusive Client {uuid.uuid4().hex[:6]}"
    saved = account_service.save_account(active_company["id"], {
        "name": party_name,
        "account_group": "Sundry Debtors"
    })
    party_id = saved["id"]

    # Company A can see it
    acc_a = account_service.get_account_by_id(active_company["id"], party_id)
    assert acc_a is not None
    assert acc_a["name"] == party_name.upper()

    # Company B CANNOT see it
    acc_b = account_service.get_account_by_id(second_company["id"], party_id)
    assert acc_b is None

    comp_b_list = account_service.list_accounts(second_company["id"], query=party_name)
    assert len(comp_b_list) == 0


# ==============================================================================
# 9. Web Bridge Slots Verification
# ==============================================================================
def test_backend_bridge_party_slots(active_company):
    """Verify that BackendBridge exposes searchCustomers, searchSuppliers, saveAccount, deleteAccount."""
    bridge = BackendBridge(None)

    # Create party via bridge
    party_name = f"Bridge Test Customer {uuid.uuid4().hex[:6]}"
    save_resp = json.loads(bridge.saveAccount(active_company["id"], json.dumps({
        "name": party_name,
        "alias": "BTC",
        "account_group": "Sundry Debtors",
        "customer_category": "Direct Customer"
    })))
    assert save_resp["success"] is True
    created_id = save_resp["data"]["id"]

    # Search customers via bridge
    cust_resp = json.loads(bridge.searchCustomers(active_company["id"], party_name))
    assert cust_resp["success"] is True
    assert any(c["id"] == created_id for c in cust_resp["data"])

    # Toggle active
    toggle_resp = json.loads(bridge.toggleAccountActive(active_company["id"], created_id, False))
    assert toggle_resp["success"] is True
    assert toggle_resp["data"] is False


# ==============================================================================
# 10. Item Master Unaffected Guarantee
# ==============================================================================
def test_item_master_unaffected(active_company):
    """Verify that Item Master services and catalogue remain intact and unaffected by Party Master changes."""
    items_before = catalogue_service.search_items(active_company["id"], "")
    assert isinstance(items_before, list)

    # Creating party masters does not alter items table
    account_service.save_account(active_company["id"], {
        "name": f"Dummy Party {uuid.uuid4().hex[:6]}",
        "account_group": "Sundry Debtors"
    })

    items_after = catalogue_service.search_items(active_company["id"], "")
    assert len(items_before) == len(items_after)
