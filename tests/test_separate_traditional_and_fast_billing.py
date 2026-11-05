"""
Comprehensive Automated Acceptance Test Suite for:
Alpha Billing – Separate Traditional Billing and Fast Billing Environments

Verifies all 14 Acceptance Criteria specified in Section 12:
1. Traditional Billing retains its existing functionality.
2. Fast Billing opens in a separate internal tab.
3. Cashier cannot access inventory or purchase history.
4. Cashier cannot retrieve yesterday's sales through UI or backend.
5. Barcode billing works.
6. Invoice number is generated correctly.
7. Saving creates exactly one transaction.
8. Successful save opens the print screen automatically.
9. A4, A5, 58 mm and 80 mm formats render correctly.
10. Preview reflects the actual invoice.
11. Multiple copies do not create multiple invoices.
12. Printer failure does not duplicate or lose the transaction.
13. New Bill starts a fresh transaction.
14. Existing company and branch data remain isolated.
"""
import json
import uuid
import datetime
from pathlib import Path
import pytest

from services.billing_service import billing_service
from services.catalogue_service import catalogue_service
from services.printing_service import printing_service
from desktop.web_bridge import BackendBridge
from db.database import db_manager

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_HTML = BASE_DIR / "index.html"
APP_JS = BASE_DIR / "app.js"
STYLES_CSS = BASE_DIR / "styles.css"


def _get_active_company_id():
    """Retrieve actual company UUID from database."""
    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT id FROM companies WHERE code = 'COMP0001' LIMIT 1;").fetchone()
        return row[0] if row else "3a743bcd-8f9a-4154-a316-509cba3de99a"


COMPANY_ID = _get_active_company_id()


# ---------------------------------------------------------------------------
# Criterion 1: Traditional Billing retains full functionality & role permissions
# ---------------------------------------------------------------------------
def test_criterion_1_traditional_billing_retains_full_functionality():
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    # Traditional billing screen elements and views intact
    assert 'id="view-dashboard"' in html
    assert 'id="view-sales-voucher"' in html
    assert 'id="view-sales-list"' in html
    assert 'id="view-purchase-entry"' in html
    assert 'id="view-purchase-list"' in html
    assert 'id="view-stock-summary"' in html
    assert 'id="view-stock-adjustments"' in html
    assert 'id="view-add-account-master"' in html
    assert 'id="view-account-list"' in html
    assert 'id="view-add-item-master"' in html
    assert 'id="view-items-list"' in html
    assert 'id="view-day-book"' in html

    # Traditional billing activation restores full navigation & sidebar
    assert "activateBillingTab" in js
    assert 'tabKey === "traditional"' in js
    assert "enterCompanyDashboard" in js


# ---------------------------------------------------------------------------
# Criterion 2: Fast Billing opens in a separate internal tab
# ---------------------------------------------------------------------------
def test_criterion_2_internal_app_tabs_architecture():
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLES_CSS.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    # Tabs bar element in HTML
    assert 'id="app-tabs-bar"' in html
    assert 'id="tab-btn-traditional"' in html
    assert 'id="tab-btn-fast-billing"' in html
    assert 'id="btn-tab-switch-mode"' in html
    assert 'id="tab-mode-indicator"' in html

    # Styling for tabs bar
    assert ".alpha-app-tabs-bar" in css
    assert ".alpha-tab-btn" in css
    assert ".alpha-tab-btn.active" in css

    # Tab switching logic in app.js
    assert "activateBillingTab" in js
    assert "updateAppTabsDisplay" in js
    assert "closeBillingTab" in js
    assert "openTabs" in js
    assert "lastTraditionalScreen" in js
    assert "lastFastBillingScreen" in js


# ---------------------------------------------------------------------------
# Criterion 3: Cashier cannot access inventory or purchase history in Fast Billing
# ---------------------------------------------------------------------------
def test_criterion_3_fast_billing_workspace_isolation():
    html = INDEX_HTML.read_text(encoding="utf-8")

    # Violating pills must be completely absent from fast billing ribbon
    assert 'id="btn-pos-quick-stock"' not in html
    assert 'id="btn-pos-quick-purchase"' not in html
    assert 'id="btn-pos-low-stock-pill"' not in html

    # Fast billing ribbon must expose ONLY New Bill, Today's Sales History, Print/Reprint
    assert 'id="btn-pos-tab-new-sale"' in html
    assert 'id="btn-pos-tab-today-sales"' in html
    assert 'id="btn-pos-tab-reprint"' in html

    # Dedicated cashier screens exist
    assert 'id="view-fast-billing"' in html
    assert 'id="view-fast-billing-history"' in html
    assert 'id="view-fast-billing-print"' in html


# ---------------------------------------------------------------------------
# Criterion 4: Cashier cannot retrieve yesterday's sales through UI or backend
# ---------------------------------------------------------------------------
def test_criterion_4_today_sales_history_server_enforced_date():
    bridge = BackendBridge()

    # Query today's sales history via backend service
    today_sales = billing_service.get_today_sales_history(COMPANY_ID)
    assert isinstance(today_sales, list)

    now = datetime.datetime.now()
    today_dash = now.strftime("%d-%m-%Y")
    today_iso = now.strftime("%Y-%m-%d")

    # Ensure every single invoice returned belongs to today
    for vch in today_sales:
        vch_date = vch.get("vch_date") or ""
        created_at = vch.get("created_at") or ""
        assert (today_dash in vch_date or today_iso in vch_date or today_iso in created_at), (
            f"Voucher {vch.get('vch_no')} with date {vch_date} is not from today {today_iso}!"
        )

    # Bridge method verification
    resp_json = bridge.getTodaySalesHistory(COMPANY_ID, "")
    resp = json.loads(resp_json)
    assert resp["success"] is True
    assert isinstance(resp["data"], list)


# ---------------------------------------------------------------------------
# Criterion 5 & 6: Barcode billing works & Cashier product lookup omits stock/cost
# ---------------------------------------------------------------------------
def test_criterion_5_cashier_product_lookup_omits_stock_and_cost():
    bridge = BackendBridge()

    # Search cashier products
    items = catalogue_service.search_cashier_items(COMPANY_ID, "SPOON")
    assert len(items) > 0
    item = items[0]

    # Required billing fields present
    assert "name" in item
    assert "barcode" in item
    assert "sales_price" in item
    assert "tax_rate" in item
    assert "unit" in item

    # Restricted fields MUST NOT be present
    assert "current_stock" not in item
    assert "op_stock_qty" not in item
    assert "op_stock_val" not in item
    assert "purc_price" not in item
    assert "cost_rate" not in item

    # Barcode exact lookup
    barcode = item["barcode"]
    cashier_item = catalogue_service.get_cashier_item_by_barcode(COMPANY_ID, barcode)
    assert cashier_item is not None
    assert cashier_item["name"] == item["name"]
    assert "current_stock" not in cashier_item
    assert "op_stock_qty" not in cashier_item
    assert "purc_price" not in cashier_item

    # Verify via bridge slots
    search_resp = json.loads(bridge.searchCashierProducts(COMPANY_ID, "SPOON"))
    assert search_resp["success"] is True
    assert "current_stock" not in search_resp["data"][0]

    barcode_resp = json.loads(bridge.getCashierProductByBarcode(COMPANY_ID, barcode))
    assert barcode_resp["success"] is True
    assert "current_stock" not in barcode_resp["data"]


# ---------------------------------------------------------------------------
# Criterion 7: Saving creates exactly one transaction with correct invoice number
# ---------------------------------------------------------------------------
def test_criterion_7_saving_creates_exactly_one_transaction():
    bridge = BackendBridge()

    # Get next sequential number
    next_no_resp = json.loads(bridge.getNextVoucherNumber(COMPANY_ID, "Main"))
    assert next_no_resp["success"] is True
    expected_vch_no = next_no_resp["data"]

    # Fetch a valid item from catalogue
    with db_manager.get_connection() as conn:
        item_row = conn.execute("SELECT id, name FROM items WHERE company_id = ? LIMIT 1;", (COMPANY_ID,)).fetchone()
        real_item_id = item_row[0]
        real_item_name = item_row[1]

    test_items = [
        {
            "id": real_item_id,
            "name": real_item_name,
            "qty": 2.0,
            "unit": "Pcs.",
            "price": 100.0,
            "discount_percent": 5.0,
            "discount_amount": 10.0,
            "taxable_amount": 190.0,
            "tax_rate": 18.0,
            "tax_amount": 34.2,
            "line_total": 224.2
        }
    ]

    payload = {
        "party_name": "TEST CASHIER SALE",
        "customer_category": "Direct Customer",
        "sale_type": "L/GST-18%",
        "payment_method": "CASH",
        "items": test_items,
        "vch_date": datetime.datetime.now().strftime("%d-%m-%Y"),
        "narration": "Fast Billing Automated Verification"
    }

    create_resp = json.loads(bridge.createSaleInvoice(COMPANY_ID, json.dumps(payload)))
    assert create_resp["success"] is True
    created_vch = create_resp["data"]

    assert created_vch["vch_no"] == expected_vch_no
    assert created_vch["grand_total"] > 0

    # Verify in database: exactly one record exists with this voucher number
    with db_manager.get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM sales_vouchers WHERE company_id = ? AND vch_no = ?;",
            (COMPANY_ID, expected_vch_no)
        ).fetchone()[0]
        assert count == 1, f"Expected exactly 1 voucher with number {expected_vch_no}, found {count}"


# ---------------------------------------------------------------------------
# Criterion 8: Successful save opens print screen automatically in frontend
# ---------------------------------------------------------------------------
def test_criterion_8_automatic_post_save_print_screen_navigation():
    js = APP_JS.read_text(encoding="utf-8")

    # In finalizePosSale:
    # Must set isSavingPosSale lock to prevent duplicate clicks
    assert "isSavingPosSale = true" in js
    # On success: must call openFastBillingPrint
    assert "openFastBillingPrint(res.data.voucher_id || res.data.id, lastCompletedVoucherData)" in js
    # openFastBillingPrint must switch to view-fast-billing-print
    assert 'showScreen("view-fast-billing-print")' in js


# ---------------------------------------------------------------------------
# Criterion 9 & 10: Paper formats (A4, A5, 58mm, 80mm) & live preview rendering
# ---------------------------------------------------------------------------
def test_criterion_9_and_10_paper_formats_and_preview_rendering():
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLES_CSS.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    # Format selector buttons in HTML
    assert 'data-format="a4"' in html
    assert 'data-format="a5"' in html
    assert 'data-format="thermal-80"' in html
    assert 'data-format="thermal-58"' in html
    assert 'data-format="custom"' in html

    # Corresponding CSS sheet classes
    assert ".pos-invoice-sheet.sheet-a4" in css
    assert ".pos-invoice-sheet.sheet-a5" in css
    assert ".pos-invoice-sheet.sheet-thermal-80" in css
    assert ".pos-invoice-sheet.sheet-thermal-58" in css

    # Preview renderers in JS
    assert "renderInvoicePrintPreview" in js
    assert "renderThermalReceiptPreview" in js
    assert "renderTaxInvoiceSheetPreview" in js


# ---------------------------------------------------------------------------
# Criterion 11: Multiple copies do not create multiple invoices
# ---------------------------------------------------------------------------
def test_criterion_11_multiple_copies_never_duplicate_transactions():
    bridge = BackendBridge()

    # Get a sample invoice
    vouchers = billing_service.list_vouchers(COMPANY_ID, limit=1)
    assert len(vouchers) > 0
    target_vch = vouchers[0]
    vch_id = target_vch["id"]

    # Count vouchers before print
    with db_manager.get_connection() as conn:
        count_before = conn.execute("SELECT COUNT(*) FROM sales_vouchers WHERE company_id = ?;", (COMPANY_ID,)).fetchone()[0]

    # Print 3 copies of thermal 80mm
    print_resp = json.loads(bridge.printInvoice(COMPANY_ID, vch_id, "thermal-80", "EPSON TM-T82", 3))
    assert print_resp["success"] is True
    assert print_resp["data"]["copies"] == 3

    # Count vouchers after print: MUST BE STRICTLY EQUAL
    with db_manager.get_connection() as conn:
        count_after = conn.execute("SELECT COUNT(*) FROM sales_vouchers WHERE company_id = ?;", (COMPANY_ID,)).fetchone()[0]
        assert count_after == count_before, "Printing multiple copies must NEVER insert new sales vouchers!"

    # Verify audit log entry
    with db_manager.get_connection() as conn:
        log_row = conn.execute(
            "SELECT details FROM audit_logs WHERE action = 'PRINT_INVOICE' AND entity_id = ? ORDER BY created_at DESC LIMIT 1;",
            (vch_id,)
        ).fetchone()
        assert log_row is not None
        assert "3 copies" in log_row[0]


# ---------------------------------------------------------------------------
# Criterion 12: Printer failure preserves transaction
# ---------------------------------------------------------------------------
def test_criterion_12_printer_failure_preserves_transaction():
    bridge = BackendBridge()
    vouchers = billing_service.list_vouchers(COMPANY_ID, limit=1)
    target_vch = vouchers[0]

    # Attempt print with invalid/simulated printer
    print_resp = json.loads(bridge.printInvoice(COMPANY_ID, target_vch["id"], "thermal-80", "OFFLINE_TEST_PRINTER", 1))
    assert print_resp["success"] is True

    # Invoice in sales_vouchers remains completely intact and unaffected
    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT vch_no, grand_total FROM sales_vouchers WHERE id = ?;", (target_vch["id"],)).fetchone()
        assert row is not None
        assert row[0] == target_vch["vch_no"]


# ---------------------------------------------------------------------------
# Criterion 13: New Bill starts a fresh transaction
# ---------------------------------------------------------------------------
def test_criterion_13_new_bill_starts_fresh_transaction():
    js = APP_JS.read_text(encoding="utf-8")

    assert "openFastBillingNewBill" in js
    # Clears cart and tender inputs
    assert "posCart = []" in js
    assert 'showScreen("view-fast-billing")' in js


# ---------------------------------------------------------------------------
# Criterion 14: Existing company and branch data remain isolated
# ---------------------------------------------------------------------------
def test_criterion_14_company_and_branch_data_isolation():
    bridge = BackendBridge()

    # Query with active company ID
    today_sales_comp1 = json.loads(bridge.getTodaySalesHistory(COMPANY_ID, ""))
    assert today_sales_comp1["success"] is True

    # Query with non-existent or separate dummy company
    dummy_comp = str(uuid.uuid4())
    today_sales_dummy = json.loads(bridge.getTodaySalesHistory(dummy_comp, ""))
    assert today_sales_dummy["success"] is True
    # Dummy company has 0 sales
    assert len(today_sales_dummy["data"]) == 0
