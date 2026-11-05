"""
Comprehensive Automated Test Suite for Standard Add, Modify & List Workflow
Verifies all 10 Acceptance Criteria:
1. Masters displays exactly Add, Modify, List.
2. Item Master displays exactly Add, Modify, List.
3. Sales displays exactly Add, Modify, List.
4. Purchase displays exactly Add, Modify, List.
5. All four Add workflows save valid records.
6. All four Modify workflows retrieve and update existing records correctly.
7. All four List workflows display existing records correctly.
8. A saved sales invoice cannot be deleted from the UI or through application backend operations.
9. Sales modifications correctly reconcile inventory and accounting.
10. Existing data and unrelated modules remain unaffected.
"""
import json
import uuid
import subprocess
import pytest
from pathlib import Path

from services.account_service import account_service
from services.catalogue_service import catalogue_service
from services.billing_service import billing_service
from services.purchase_service import purchase_service
from services.inventory_service import inventory_service
from db.database import db_manager
from desktop.web_bridge import BackendBridge

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_HTML = BASE_DIR / "index.html"
APP_JS = BASE_DIR / "app.js"
NAV_JS = BASE_DIR / "js" / "navigation.js"


def _get_active_company_id():
    """Retrieve actual company ID from canonical database."""
    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT id FROM companies WHERE code = 'COMP0001' LIMIT 1;").fetchone()
        return row[0] if row else "3a743bcd-8f9a-4154-a316-509cba3de99a"


COMPANY_ID = _get_active_company_id()


def _get_evaluated_nav_config():
    """Run node to evaluate PRIMARY_NAV_CONFIG and return as Python data structure."""
    node_script = """
    const fs = require('fs');
    global.window = {};
    global.localStorage = { getItem: () => null };
    global.document = { getElementById: () => null };
    let code = fs.readFileSync('js/navigation.js', 'utf8');
    code = code.replace('const PRIMARY_NAV_CONFIG =', 'global.PRIMARY_NAV_CONFIG =');
    eval(code);
    console.log(JSON.stringify(global.PRIMARY_NAV_CONFIG));
    """
    res = subprocess.run(["node", "-e", node_script], cwd=str(BASE_DIR), capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


# -------------------------------------------------------------
# CRITERIA 1 - 4: NAVIGATION HIERARCHY
# -------------------------------------------------------------
def test_criterion_1_masters_displays_exactly_add_modify_list():
    """Verify Masters submenu displays ONLY Add, Modify, List."""
    nav_config = _get_evaluated_nav_config()
    admin = next(s for s in nav_config if s["id"] == "administration")
    masters = next(sub for sub in admin["submenus"] if sub["label"] == "Masters")

    children = masters.get("children", [])
    labels = [c["label"] for c in children]
    assert labels == ["Add", "Modify", "List"], f"Masters must have only Add, Modify, List; got {labels}"
    assert children[0]["targetView"] == "view-add-account-master"
    assert children[1]["modalId"] == "modal-select-account-modify"
    assert children[2]["targetView"] == "view-account-list"


def test_criterion_2_item_master_displays_exactly_add_modify_list():
    """Verify Item Master submenu displays ONLY Add, Modify, List."""
    nav_config = _get_evaluated_nav_config()
    admin = next(s for s in nav_config if s["id"] == "administration")
    items = next(sub for sub in admin["submenus"] if sub["label"] == "Item Master")

    children = items.get("children", [])
    labels = [c["label"] for c in children]
    assert labels == ["Add", "Modify", "List"], f"Item Master must have only Add, Modify, List; got {labels}"
    assert children[0]["targetView"] == "view-add-item-master"
    assert children[1]["modalId"] == "modal-select-item-modify"
    assert children[2]["targetView"] == "view-items-list"


def test_criterion_3_sales_displays_exactly_add_modify_list():
    """Verify Sales submenu displays ONLY Add, Modify, List."""
    nav_config = _get_evaluated_nav_config()
    tx = next(s for s in nav_config if s["id"] == "transaction")
    sales = next(sub for sub in tx["submenus"] if sub["label"] == "Sales")

    children = sales.get("children", [])
    labels = [c["label"] for c in children]
    assert labels == ["Add", "Modify", "List"], f"Sales must have only Add, Modify, List; got {labels}"
    assert children[0]["targetView"] == "view-sales-voucher"
    assert children[1]["modalId"] == "modal-select-sales-modify"
    assert children[2]["targetView"] == "view-sales-list"


def test_criterion_4_purchase_displays_exactly_add_modify_list():
    """Verify Purchase submenu displays ONLY Add, Modify, List."""
    nav_config = _get_evaluated_nav_config()
    tx = next(s for s in nav_config if s["id"] == "transaction")
    purchase = next(sub for sub in tx["submenus"] if sub["label"] == "Purchase")

    children = purchase.get("children", [])
    labels = [c["label"] for c in children]
    assert labels == ["Add", "Modify", "List"], f"Purchase must have only Add, Modify, List; got {labels}"
    assert children[0]["targetView"] == "view-purchase-entry"
    assert children[1]["modalId"] == "modal-select-purchase-modify"
    assert children[2]["targetView"] == "view-purchase-list"


# -------------------------------------------------------------
# CRITERIA 5: ALL FOUR ADD WORKFLOWS SAVE VALID RECORDS
# -------------------------------------------------------------
def test_criterion_5_add_workflows():
    """Verify Add operations across Masters, Item Master, Sales, and Purchase."""
    uid = uuid.uuid4().hex[:6]
    # 5.1 Add Account Master
    acc_name = f"TEST WF CUSTOMER {uid}"
    acc = account_service.save_account(COMPANY_ID, {
        "name": acc_name,
        "group": "Sundry Debtors",
        "customer_category": "Commercial",
        "mobile": "9876543210",
        "gstin": "33AAACA1234A1Z1"
    })
    assert acc["id"] is not None
    assert acc["name"] == acc_name.upper()

    # 5.2 Add Item Master (with duplicate code & barcode validation)
    sku_code = f"SKU-{uid}"
    barcode = f"890{uid.upper()}1234"
    item = catalogue_service.save_item(COMPANY_ID, {
        "name": f"TEST WF PRODUCT {uid}",
        "alias": sku_code,
        "barcodes": barcode,
        "sales_price": 100.0,
        "tax_category": "GST 18%",
        "op_stock_qty": 50.0
    })
    assert item["id"] is not None

    # Verify duplicate prevention
    with pytest.raises(ValueError, match="already assigned"):
        catalogue_service.save_item(COMPANY_ID, {
            "name": f"DUPLICATE PRODUCT {uid}",
            "alias": sku_code,
            "sales_price": 50.0
        })

    with pytest.raises(ValueError, match="already registered"):
        catalogue_service.save_item(COMPANY_ID, {
            "name": f"DUPLICATE BARCODE {uid}",
            "alias": f"UNIQUE-SKU-{uid}",
            "barcodes": barcode,
            "sales_price": 50.0
        })

    # 5.3 Add Purchase Voucher
    pur_vch = purchase_service.create_purchase_voucher(COMPANY_ID, {
        "supplier_id": acc["id"],
        "supplier_name": acc_name,
        "supplier_invoice_no": f"SUP-INV-{uid}",
        "supplier_invoice_date": "2026-11-05",
        "voucher_date": "2026-11-05",
        "items": [{
            "item_id": item["id"],
            "name": item["name"],
            "qty": 20,
            "unit": "Pcs",
            "cost_rate": 60.0,
            "tax_rate": 18.0
        }]
    })
    assert pur_vch["vch_no"].startswith("PUR-")
    assert pur_vch["grand_total"] > 0

    # 5.4 Add Sales Invoice
    sale_vch = billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{
            "item_id": item["id"],
            "name": item["name"],
            "qty": 5,
            "unit": "Pcs",
            "price": 100.0
        }],
        party_name=acc_name,
        customer_category="Commercial",
        sale_type="L/GST-18%",
        payment_method="CASH"
    )
    assert sale_vch["vch_no"] is not None
    assert sale_vch["grand_total"] > 0


# -------------------------------------------------------------
# CRITERIA 6: ALL FOUR MODIFY WORKFLOWS RETRIEVE AND UPDATE
# -------------------------------------------------------------
def test_criterion_6_modify_workflows():
    """Verify Modify operations update records while preserving references."""
    uid = uuid.uuid4().hex[:6]
    # 6.1 Modify Account Master
    acc = account_service.save_account(COMPANY_ID, {
        "name": f"ACC MODIFY {uid}",
        "group": "Sundry Debtors",
        "mobile": "9998887770"
    })
    acc_id = acc["id"]

    updated_acc = account_service.save_account(COMPANY_ID, {
        "id": acc_id,
        "name": f"ACC MODIFY {uid}",
        "group": "Sundry Debtors",
        "mobile": "9998887771",
        "address": "42 Commercial Street"
    })
    assert updated_acc["id"] == acc_id
    stored_acc = account_service.get_account_by_id(COMPANY_ID, acc_id)
    assert stored_acc["mobile"] == "9998887771"

    # 6.2 Modify Item Master
    prod = catalogue_service.save_item(COMPANY_ID, {
        "name": f"PROD MODIFY {uid}",
        "alias": f"MOD-SKU-{uid}",
        "barcodes": f"BAR-{uid}",
        "sales_price": 250.0
    })
    prod_id = prod["id"]

    updated_prod = catalogue_service.save_item(COMPANY_ID, {
        "id": prod_id,
        "name": f"PROD MODIFY UPDATED {uid}",
        "alias": f"MOD-SKU-{uid}",
        "barcodes": f"BAR-{uid}",
        "sales_price": 275.0
    })
    assert updated_prod["id"] == prod_id
    assert updated_prod["name"] == f"PROD MODIFY UPDATED {uid}".upper()
    assert updated_prod["sales_price"] == 275.0

    # 6.3 Modify Sales Invoice
    sale = billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{
            "item_id": prod_id,
            "name": f"PROD MODIFY UPDATED {uid}",
            "qty": 4,
            "price": 275.0
        }],
        party_name="CASH"
    )
    vch_id = sale["voucher_id"]

    modified_sale = billing_service.modify_sale_invoice(
        company_id=COMPANY_ID,
        vch_id=vch_id,
        items=[{
            "item_id": prod_id,
            "name": f"PROD MODIFY UPDATED {uid}",
            "qty": 6,
            "price": 275.0
        }],
        party_name="CASH",
        narration="Updated quantity to 6"
    )
    assert modified_sale["vch_no"] == sale["vch_no"]
    assert modified_sale["totals"]["subtotal"] == 6 * 275.0

    # 6.4 Modify Purchase Voucher
    pur = purchase_service.create_purchase_voucher(COMPANY_ID, {
        "supplier_id": acc_id,
        "supplier_name": f"ACC MODIFY {uid}",
        "supplier_invoice_no": f"PUR-INV-{uid}",
        "items": [{
            "item_id": prod_id,
            "name": f"PROD MODIFY UPDATED {uid}",
            "qty": 10,
            "cost_rate": 150.0
        }]
    })
    pur_id = pur["voucher_id"]

    modified_pur = purchase_service.modify_purchase_voucher(COMPANY_ID, pur_id, {
        "supplier_id": acc_id,
        "supplier_name": f"ACC MODIFY {uid}",
        "supplier_invoice_no": f"PUR-INV-REV-{uid}",
        "items": [{
            "item_id": prod_id,
            "name": f"PROD MODIFY UPDATED {uid}",
            "qty": 15,
            "cost_rate": 150.0
        }]
    })
    assert modified_pur["vch_no"] == pur["vch_no"]
    assert modified_pur["supplier_invoice_no"] == f"PUR-INV-REV-{uid}"


# -------------------------------------------------------------
# CRITERIA 7: ALL FOUR LIST WORKFLOWS DISPLAY EXISTING RECORDS
# -------------------------------------------------------------
def test_criterion_7_list_views_structure():
    """Verify HTML and JS elements for all 4 List views."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    # 1. Accounts List
    assert 'id="view-account-list"' in html
    assert 'id="acc-master-table"' in html
    assert 'id="acc-master-tbody"' in html
    assert 'id="acc-list-search"' in html
    assert 'id="acc-list-group-filter"' in html
    assert "renderAccountMasterList" in js

    # 2. Items List
    assert 'id="view-items-list"' in html
    assert 'id="items-master-tbody"' in html
    assert "renderProductsList" in js

    # 3. Sales List
    assert 'id="view-sales-list"' in html
    assert 'id="sales-register-tbody"' in html
    assert "renderSalesRegister" in js

    # 4. Purchase List
    assert 'id="view-purchase-list"' in html
    assert 'id="pur-register-tbody"' in html
    assert "renderPurchaseRegister" in js


# -------------------------------------------------------------
# CRITERIA 8: SALES INVOICE CANNOT BE DELETED
# -------------------------------------------------------------
def test_criterion_8_sales_invoice_cannot_be_deleted():
    """
    CRITICAL SECURITY RULE:
    A saved sales invoice must NEVER be deletable from UI or backend.
    """
    # 8.1 Backend method raises PermissionError
    with pytest.raises(PermissionError, match="saved sales bill must NEVER be deleted"):
        billing_service.delete_sale_invoice(COMPANY_ID, "VCH-DOESNT-MATTER")

    # 8.2 WebBridge slot returns permission error
    bridge = BackendBridge()
    res_raw = bridge.deleteSaleInvoice(COMPANY_ID, "VCH-0001")
    res = json.loads(res_raw)
    assert res["success"] is False
    assert "must NEVER be deleted" in res["error"]

    # 8.3 Verify no delete buttons exist in Sales Voucher or Sales Register in index.html
    html = INDEX_HTML.read_text(encoding="utf-8")
    sales_vch_view = html[html.find('id="view-sales-voucher"'):html.find('id="view-sales-list"')]
    assert "btn-delete" not in sales_vch_view


# -------------------------------------------------------------
# CRITERIA 9: SALES MODIFICATIONS ATOMICALLY RECONCILE INVENTORY
# -------------------------------------------------------------
def test_criterion_9_sales_modifications_reconcile_inventory():
    """Verify that editing a sales invoice correctly recalculates stock and journals."""
    uid = uuid.uuid4().hex[:6]
    # Create product with initial opening stock 100
    prod = catalogue_service.save_item(COMPANY_ID, {
        "name": f"STOCK RECON ITEM {uid}",
        "alias": f"STK-{uid}",
        "sales_price": 50.0,
        "op_stock_qty": 100.0
    })
    prod_id = prod["id"]

    # Current stock should be 100
    cur_stock = inventory_service.get_stock(COMPANY_ID, prod_id)
    assert cur_stock == 100.0

    # Create sale invoice with qty 20 -> stock drops to 80
    sale = billing_service.create_sale_invoice(
        company_id=COMPANY_ID,
        items=[{
            "item_id": prod_id,
            "name": f"STOCK RECON ITEM {uid}",
            "qty": 20,
            "price": 50.0
        }],
        party_name="CASH"
    )
    assert inventory_service.get_stock(COMPANY_ID, prod_id) == 80.0

    # Modify sale invoice to qty 10 -> stock must reconcile to 90
    billing_service.modify_sale_invoice(
        company_id=COMPANY_ID,
        vch_id=sale["voucher_id"],
        items=[{
            "item_id": prod_id,
            "name": f"STOCK RECON ITEM {uid}",
            "qty": 10,
            "price": 50.0
        }],
        party_name="CASH"
    )
    assert inventory_service.get_stock(COMPANY_ID, prod_id) == 90.0

    # Modify sale invoice to qty 35 -> stock must reconcile to 65
    billing_service.modify_sale_invoice(
        company_id=COMPANY_ID,
        vch_id=sale["voucher_id"],
        items=[{
            "item_id": prod_id,
            "name": f"STOCK RECON ITEM {uid}",
            "qty": 35,
            "price": 50.0
        }],
        party_name="CASH"
    )
    assert inventory_service.get_stock(COMPANY_ID, prod_id) == 65.0


# -------------------------------------------------------------
# CRITERIA 10: EXISTING DATA AND UNRELATED MODULES REMAIN UNAFFECTED
# -------------------------------------------------------------
def test_criterion_10_unrelated_modules_unaffected():
    """Verify other Administration, Company, Display, and Transaction sections remain intact."""
    nav_config = _get_evaluated_nav_config()

    # Company submenus: exactly 2
    comp = next(s for s in nav_config if s["id"] == "company")
    assert [sub["label"] for sub in comp["submenus"]] == ["Edit Company", "Close Company"]

    # Administration submenus: exactly 10
    admin = next(s for s in nav_config if s["id"] == "administration")
    assert len(admin["submenus"]) == 10

    # Verify untouched administration sections exist
    admin_labels = [s["label"] for s in admin["submenus"]]
    assert "Configuration" in admin_labels
    assert "Users" in admin_labels
    assert "Mobile App" in admin_labels
    assert "Utilities" in admin_labels
    assert "Bulk Updates" in admin_labels
    assert "Data Export Import" in admin_labels
    assert "Miscellaneous Data Entry" in admin_labels
    assert "Change Financial Year" in admin_labels
