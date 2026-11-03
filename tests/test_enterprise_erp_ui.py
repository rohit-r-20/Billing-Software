import re
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent


def test_enterprise_erp_views_in_html():
    """Verify all 6 new enterprise ERP views exist in index.html with correct structure."""
    html = (BASE_DIR / "index.html").read_text(encoding="utf-8")
    
    expected_views = [
        "view-purchase-entry",
        "view-purchase-list",
        "view-supplier-master",
        "view-stock-summary",
        "view-stock-adjustments",
        "view-day-book"
    ]
    for view_id in expected_views:
        assert f'id="{view_id}"' in html, f"Missing view: {view_id}"


def test_enterprise_erp_modals_in_html():
    """Verify all 6 enterprise ERP modals exist in index.html."""
    html = (BASE_DIR / "index.html").read_text(encoding="utf-8")

    expected_modals = [
        "modal-supplier-form",
        "modal-supplier-ledger",
        "modal-stock-item-ledger",
        "modal-invoice-ocr",
        "modal-sales-return",
        "modal-purchase-return"
    ]
    for modal_id in expected_modals:
        assert f'id="{modal_id}"' in html, f"Missing modal: {modal_id}"


def test_enterprise_erp_menubar_and_pos_pills():
    """Verify menubar tree items and Fast Billing ERP pills are present."""
    html = (BASE_DIR / "index.html").read_text(encoding="utf-8")

    # Fast Billing Quick Pills
    assert 'id="btn-pos-quick-stock"' in html
    assert 'id="btn-pos-quick-purchase"' in html

    # Menubar items
    assert 'id="menu-purchase-add"' in html
    assert 'id="menu-purchase-list"' in html
    assert 'id="menu-add-supplier-master"' in html
    assert 'id="menu-list-supplier-master"' in html
    assert 'id="menu-display-stock"' in html
    assert 'id="menu-display-daybook"' in html
    assert 'id="menu-display-trial-balance"' in html
    assert 'id="menu-sales-return"' in html
    assert 'id="menu-purchase-return"' in html
    assert 'id="menu-stock-transfer"' in html
    assert 'id="menu-stock-adjustment"' in html


def test_enterprise_erp_styles():
    """Verify CSS has tab, badge, and table styles."""
    css = (BASE_DIR / "styles.css").read_text(encoding="utf-8")

    assert ".btn-pos-erp-pill" in css
    assert ".erp-tab-btn" in css
    assert ".stock-badge-optimal" in css
    assert ".stock-badge-low" in css
    assert ".stock-badge-out" in css
    assert ".purchase-items-table" in css


def test_app_js_router_and_handlers():
    """Verify app.js includes new view elements, routing, and functions."""
    js = (BASE_DIR / "app.js").read_text(encoding="utf-8")

    # Router references
    assert "viewPurchaseEntry" in js
    assert "viewPurchaseList" in js
    assert "viewSupplierMaster" in js
    assert "viewStockSummary" in js
    assert "viewStockAdjustments" in js
    assert "viewDayBook" in js

    # Function declarations
    assert "function initPurchaseEntryScreen" in js
    assert "function postPurchaseVoucher" in js
    assert "function renderPurchaseRegister" in js
    assert "function renderSupplierMaster" in js
    assert "function saveSupplierMaster" in js
    assert "function renderStockSummary" in js
    assert "function openStockItemLedgerModal" in js
    assert "function initStockAdjustmentsScreen" in js
    assert "function postStockAdjustment" in js
    assert "function postStockTransfer" in js
    assert "function renderDayBookScreen" in js
    assert "function renderTrialBalanceScreen" in js
    assert "function runOcrExtraction" in js
    assert "function populatePurchaseVoucherFromOcr" in js
    assert "function postSalesReturn" in js
    assert "function postPurchaseReturn" in js

