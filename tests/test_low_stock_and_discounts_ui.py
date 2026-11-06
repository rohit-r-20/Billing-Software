import re
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent


def test_product_master_low_stock_fields_in_html():
    """Verify Minimum Stock Alert Level and Enable Alerts checkbox in Product Master."""
    html = (BASE_DIR / "index.html").read_text(encoding="utf-8")
    assert 'id="item-min-stock-level"' in html
    assert 'id="item-alert-enabled"' in html
    assert "Min. Stock Alert Level" in html
    assert "Alerts if stock &lt; threshold" in html or "Alerts if stock < threshold" in html


def test_customer_master_category_field_in_html():
    """Verify Customer Category dropdown exists in Account Master form."""
    html = (BASE_DIR / "index.html").read_text(encoding="utf-8")
    assert 'id="acc-customer-category"' in html
    assert '<option value="Direct Customer"' in html
    assert '<option value="Commercial"' in html
    assert '<option value="Sub-Commercial"' in html


def test_configuration_modal_customer_discounts_in_html():
    """Verify Configuration Modal includes Customer Pricing & Category Discounts inputs."""
    html = (BASE_DIR / "index.html").read_text(encoding="utf-8")
    assert "Customer Pricing &amp; Category Discounts" in html or "Customer Pricing & Category Discounts" in html
    assert 'id="cfg-disc-commercial"' in html
    assert 'id="cfg-disc-sub-commercial"' in html
    assert 'id="cfg-disc-direct"' in html


def test_low_stock_modal_and_indicators_in_html():
    """Verify Low Stock Alert Modal, menubar pill, and POS ribbon pill."""
    html = (BASE_DIR / "index.html").read_text(encoding="utf-8")
    assert 'id="modal-low-stock-alert"' in html
    assert 'id="low-stock-modal-table"' in html
    assert 'id="low-stock-modal-tbody"' in html
    assert 'id="btn-close-low-stock-modal"' in html
    assert 'id="btn-low-stock-dismiss"' in html
    assert 'id="btn-low-stock-view-inventory"' in html
    assert 'id="btn-low-stock-view-product"' in html
    assert 'id="bar-low-stock-alert"' in html
    assert 'id="bar-low-stock-count"' in html
    assert 'id="btn-header-notifications"' in html
    assert 'id="header-notif-badge"' in html


def test_pos_and_voucher_customer_category_elements_in_html():
    """Verify Fast Billing POS customer selector and Traditional Billing party category badge."""
    html = (BASE_DIR / "index.html").read_text(encoding="utf-8")
    assert 'id="pos-customer-select"' in html
    assert 'id="pos-customer-category-badge"' in html
    assert 'id="vch-party-category-badge"' in html


def test_low_stock_and_discounts_css_classes():
    """Verify styling for badges, pills, and customer categories in styles.css."""
    css = (BASE_DIR / "styles.css").read_text(encoding="utf-8")
    assert ".stock-badge-low" in css
    assert ".stock-badge-out" in css
    assert ".pos-customer-category-badge" in css or ".pos-category-badge" in css
    assert ".vch-party-category-badge" in css
    assert ".commercial" in css
    assert ".sub-commercial" in css
    assert ".direct" in css


def test_app_js_low_stock_and_discounts_integration():
    """Verify app.js includes core low-stock alert and customer discount logic."""
    js = (BASE_DIR / "app.js").read_text(encoding="utf-8")

    # State variables
    assert "cachedCategoryDiscounts" in js
    assert "sessionLowStockDismissed" in js
    assert "activePosCustomerCategory" in js
    assert "activeVoucherCustomerCategory" in js

    # Key functions
    assert "function fetchCustomerCategoryDiscounts" in js
    assert "function checkLowStockAlerts" in js
    assert "function showLowStockAlertModal" in js
    assert "function closeLowStockAlertModal" in js
    assert "function initPosCustomerSelector" in js
    assert "function handlePosCustomerChange" in js
    assert "function updateVoucherPartyCategory" in js

    # Event listeners
    assert "barLowStockAlert" in js
    assert "btnPosLowStockPill" in js
    assert "btnCloseLowStockModal" in js
    assert "btnLowStockDismiss" in js
    assert "btnLowStockViewInventory" in js
    assert "btnLowStockViewProduct" in js
