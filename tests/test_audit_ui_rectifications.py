"""
Test Suite for Audit UI/UX Rectifications and Quality Assurance.
Validates:
1. DEF-01: Add/Edit Product (view-add-item-master) balanced 2-column layout and 7 sections.
2. DEF-02: Zero duplicate function declarations in app.js (setupSidebarAndDashboardNav, renderOperationalDashboard).
3. DEF-03: Purchase Inward (#btn-pur-search-item) wired and modal product search integration.
4. DEF-04: Stock Adjustments & Transfers (#btn-adj-reset, #btn-trn-reset) wired.
5. DEF-05: Standardized split-column label widths (.split-col .field-label) ensuring pixel-perfect alignment.
6. DEF-06: DOM presence and styling of #app-toast.
7. QWebEngine live interaction & multi-zoom containment (80%, 100%, 110%, 120%).
"""
import re
from pathlib import Path
import pytest
from PyQt5.QtCore import QEventLoop

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_HTML = BASE_DIR / "index.html"
STYLES_CSS = BASE_DIR / "styles.css"
APP_JS = BASE_DIR / "app.js"


def eval_js(view, script):
    loop = QEventLoop()
    result = {"val": None}

    def callback(res):
        result["val"] = res
        loop.quit()

    view.page().runJavaScript(script, callback)
    loop.exec_()
    return result["val"]


def test_def01_product_master_balanced_2col_and_7_sections():
    """Verify Add/Edit Product has balanced 2-column grid and all 7 Phase 5 sections."""
    html = INDEX_HTML.read_text(encoding="utf-8")

    # Balanced 2-column layout container
    assert 'class="master-layout-row product-master-grid"' in html

    # Section 1: Product Information
    assert 'id="item-name"' in html
    assert 'id="item-alias"' in html
    assert 'id="item-print-name"' in html
    assert 'id="item-group"' in html

    # Section 2: Unit & Stock Details
    assert "Unit &amp; Stock Details" in html or "Unit & Stock Details" in html
    assert 'id="item-unit"' in html
    assert 'id="item-op-qty"' in html
    assert 'id="item-op-val"' in html
    assert 'id="item-min-stock-level"' in html
    assert 'id="item-alert-enabled"' in html
    assert "Enable Low-Stock Alert" in html

    # Section 3: Tax Information
    assert "Tax &amp; Classification" in html or "Tax & Classification" in html
    assert 'id="item-tax-cat"' in html
    assert 'id="item-hsn"' in html

    # Section 4: Pricing Information
    assert "Pricing Information (₹)" in html
    assert 'id="item-sales-price"' in html
    assert 'id="item-purc-price"' in html
    assert 'id="item-mrp"' in html
    assert 'id="item-min-sales-price"' in html

    # Section 5: Discounts & Margin
    assert "Discounts &amp; Margin" in html or "Discounts & Margin" in html
    assert 'id="item-sale-disc"' in html
    assert 'id="item-purc-disc"' in html

    # Section 6: Product Description
    assert "Product Description" in html
    assert 'id="item-desc"' in html

    # Section 7: Barcode & Stock Notes
    assert "Barcode &amp; Stock Notes" in html or "Barcode & Stock Notes" in html
    assert 'id="item-extra-info"' in html

    # Header and Footer Action Buttons
    assert 'id="btn-item-back-list"' in html
    assert 'id="btn-item-open-list"' in html
    assert 'id="btn-item-close-top"' in html
    assert 'id="btn-item-new-clear"' in html
    assert 'id="btn-item-view-list-bottom"' in html
    assert 'id="btn-item-save"' in html
    assert 'id="btn-item-quit"' in html


def test_def02_zero_duplicate_functions_in_app_js():
    """Verify app.js does not contain duplicate function declarations."""
    js = APP_JS.read_text(encoding="utf-8")

    matches_nav = re.findall(r"function\s+setupSidebarAndDashboardNav\s*\(", js)
    assert len(matches_nav) == 1, f"Found {len(matches_nav)} definitions of setupSidebarAndDashboardNav"

    matches_dash = re.findall(r"function\s+renderOperationalDashboard\s*\(", js)
    assert len(matches_dash) == 1, f"Found {len(matches_dash)} definitions of renderOperationalDashboard"


def test_def03_purchase_search_product_button_wired():
    """Verify #btn-pur-search-item has click listener and PURCHASE target in app.js."""
    js = APP_JS.read_text(encoding="utf-8")
    assert 'btnPurSearchItem' in js
    assert 'openProductSearchModal("PURCHASE")' in js
    assert 'modalSearchTarget === "PURCHASE"' in js


def test_def04_stock_adjustment_and_transfer_resets_wired():
    """Verify #btn-adj-reset and #btn-trn-reset are wired to reset form state."""
    js = APP_JS.read_text(encoding="utf-8")
    assert 'btnAdjReset' in js
    assert 'btnTrnReset' in js
    assert 'adj-item-select' in js
    assert 'trn-item-select' in js


def test_def05_split_column_alignment_and_tokens_in_css():
    """Verify standardized .split-col .field-label width and balanced grid in styles.css."""
    css = STYLES_CSS.read_text(encoding="utf-8")
    assert ".product-master-grid .master-panel" in css
    assert "flex: 1 1 50%;" in css
    assert ".split-col .field-label" in css
    assert "width: 122px;" in css
    assert "min-width: 122px;" in css
    assert ".checkbox-inline-label" in css


def test_def06_app_toast_element_in_html_and_css():
    """Verify #app-toast element exists in index.html and has .app-toast rules in styles.css."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLES_CSS.read_text(encoding="utf-8")
    assert 'id="app-toast"' in html
    assert ".app-toast" in css
    assert "position: fixed;" in css


def test_live_product_master_form_interaction_and_alignment(session_web_view):
    """Test loading product in Add/Edit Product form and verify element alignment."""
    view = session_web_view

    # Navigate to Add/Edit Product
    eval_js(view, """
        activeCompany = { id: 'COMP0001', name: 'ANTI MATRIX', fin_year: '2026-27' };
        showScreen('view-add-item-master');
    """)

    is_active = eval_js(view, "document.getElementById('view-add-item-master').classList.contains('active')")
    assert is_active is True

    # Check horizontal alignment of Left Panel inputs
    # Product Name, Unit of Measure, Opening Stock, Min Stock Alert Level should all share aligned bounds
    alignments = eval_js(view, """
        (() => {
            const nameRect = document.getElementById('item-name').getBoundingClientRect();
            const unitRect = document.getElementById('item-unit').getBoundingClientRect();
            const opQtyRect = document.getElementById('item-op-qty').getBoundingClientRect();
            const minStockRect = document.getElementById('item-min-stock-level').getBoundingClientRect();
            const opValRect = document.getElementById('item-op-val').getBoundingClientRect();
            const alertCheckRect = document.getElementById('item-alert-enabled').getBoundingClientRect();

            return {
                nameLeft: Math.round(nameRect.left),
                unitLeft: Math.round(unitRect.left),
                opQtyLeft: Math.round(opQtyRect.left),
                minStockLeft: Math.round(minStockRect.left),
                opValLeft: Math.round(opValRect.left),
                alertCheckLeft: Math.round(alertCheckRect.left)
            };
        })()
    """)

    # opQty and minStock must be horizontally aligned on the same starting X coordinate
    assert alignments["opQtyLeft"] == alignments["minStockLeft"], (
        f"Opening Stock (left={alignments['opQtyLeft']}) and Min Stock Alert (left={alignments['minStockLeft']}) must align"
    )

    # opVal and alertCheck must start in the second column without overlapping
    assert alignments["alertCheckLeft"] >= alignments["opQtyLeft"], "Checkbox must not overlap opening stock"


def test_product_master_multi_zoom_containment(session_web_view):
    """Verify Add/Edit Product form containment at 80%, 100%, 110%, 120% zoom."""
    view = session_web_view

    for zoom in [0.8, 1.0, 1.1, 1.2]:
        eval_js(view, f"applyZoom({zoom}); showScreen('view-add-item-master');")
        scroll_w = eval_js(view, "document.body.scrollWidth")
        client_w = eval_js(view, "document.body.clientWidth")
        assert scroll_w <= client_w + 2, f"Horizontal blowout at zoom {zoom}: scrollWidth={scroll_w}, clientWidth={client_w}"

    # Reset zoom to 1.0
    eval_js(view, "applyZoom(1.0);")
