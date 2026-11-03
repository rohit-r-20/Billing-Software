"""
Test Suite for Application-Wide UI/UX Standardization.
Validates:
1. Complete removal of emojis from index.html and app.js.
2. Design system tokens and component classes in styles.css.
3. Operational Dashboard Shell structure with Left Sidebar (8 sections) and Workspace.
4. 4 Metric Cards (Today's Sales, Today's Purchases, Low Stock Alerts, Held Bills).
5. Quick Actions and Recent Activity Tables.
6. Sidebar navigation interactions and active state highlighting.
7. Zoom scaling and viewport containment.
"""
import re
from pathlib import Path
import pytest
from PyQt5.QtCore import QEventLoop, QTimer

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


def test_zero_emojis_in_html_and_js():
    """Verify that all emojis have been eliminated from index.html and app.js."""
    emoji_pattern = re.compile(
        r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\u203c-\u2049]"
    )

    html = INDEX_HTML.read_text(encoding="utf-8")
    html_emojis = emoji_pattern.findall(html)
    assert len(html_emojis) == 0, f"Found emojis in index.html: {set(html_emojis)}"

    js = APP_JS.read_text(encoding="utf-8")
    js_emojis = emoji_pattern.findall(js)
    assert len(js_emojis) == 0, f"Found emojis in app.js: {set(js_emojis)}"


def test_design_system_tokens_in_css():
    """Verify Anti Matrix design system tokens and standardized classes in styles.css."""
    css = STYLES_CSS.read_text(encoding="utf-8")

    # Tokens
    assert "--bg-desktop: #f8fafc;" in css
    assert "--brand-navy: #1e3a8a;" in css
    assert "--brand-primary: #1e40af;" in css
    assert "--brand-accent: #2563eb;" in css
    assert "--status-success-bg: #ecfdf5;" in css
    assert "--status-warning-bg: #fffbeb;" in css
    assert "--status-danger-bg: #fef2f2;" in css

    # Core UI components
    assert ".dash-shell" in css
    assert ".dash-sidebar" in css
    assert ".dash-nav-section" in css
    assert ".dash-nav-header" in css
    assert ".dash-nav-item" in css
    assert ".dash-main" in css
    assert ".page-header-container" in css
    assert ".metric-strip" in css
    assert ".metric-card" in css
    assert ".dashboard-tables-grid" in css
    assert ".data-table" in css
    assert ".status-badge" in css


def test_operational_dashboard_dom_elements():
    """Verify presence of Operational Dashboard elements and Left Sidebar in index.html."""
    html = INDEX_HTML.read_text(encoding="utf-8")

    # Sidebar structure and 8 sections
    assert 'id="dash-sidebar"' in html
    assert "Overview" in html
    assert "Sales Operations" in html
    assert "Purchases &amp; Payables" in html or "Purchases & Payables" in html
    assert "Inventory &amp; Stock" in html or "Inventory & Stock" in html
    assert "Customers" in html
    assert "Products" in html
    assert "Reports &amp; Accounts" in html or "Reports & Accounts" in html
    assert "Settings &amp; Admin" in html or "Settings & Admin" in html

    # Sidebar Navigation IDs
    sidebar_ids = [
        "btn-nav-overview",
        "btn-nav-pos",
        "btn-nav-sales-add",
        "btn-nav-sales-list",
        "btn-nav-sales-return",
        "btn-nav-purchase-add",
        "btn-nav-purchase-list",
        "btn-nav-purchase-return",
        "btn-nav-suppliers",
        "btn-nav-stock",
        "btn-nav-transfer",
        "btn-nav-adjustments",
        "btn-nav-low-stock",
        "btn-nav-customers",
        "btn-nav-customer-categories",
        "btn-nav-add-product",
        "btn-nav-products",
        "btn-nav-daybook",
        "btn-nav-trial-balance",
        "btn-nav-gst",
        "btn-nav-config",
        "btn-nav-switch-mode",
        "btn-nav-backup",
        "btn-nav-printer",
    ]
    for btn_id in sidebar_ids:
        assert f'id="{btn_id}"' in html, f"Missing sidebar item id: {btn_id}"

    # Metric Cards
    assert 'id="dash-today-sales"' in html
    assert 'id="dash-today-purchases"' in html
    assert 'id="dash-low-stock"' in html
    assert 'id="dash-held-bills"' in html

    # Quick Action Buttons
    assert 'id="dash-btn-pos"' in html
    assert 'id="dash-btn-sales-add"' in html
    assert 'id="dash-btn-purchase-add"' in html
    assert 'id="dash-btn-product-add"' in html
    assert 'id="dash-btn-stock-view"' in html
    assert 'id="dash-btn-daybook"' in html

    # Live Recent Tables
    assert 'id="dash-recent-sales-tbody"' in html
    assert 'id="dash-recent-purchases-tbody"' in html

    # Preserved compatibility elements
    assert 'id="dashboard-center-watermark"' in html
    assert 'id="dashboard-breadcrumb"' in html


def test_sidebar_navigation_live_interaction(session_web_view):
    """Test switching screens via sidebar navigation buttons in QWebEngineView."""
    view = session_web_view

    # Navigate to dashboard
    eval_js(view, """
        if (typeof activeCompany === 'undefined' || !activeCompany) {
            activeCompany = { id: 'COMP0001', name: 'ANTI MATRIX', fin_year: '2026-27' };
        }
        showScreen('view-dashboard');
    """)

    is_dash_active = eval_js(view, "document.getElementById('view-dashboard').classList.contains('active')")
    assert is_dash_active is True

    is_overview_highlighted = eval_js(view, "document.getElementById('btn-nav-overview').classList.contains('active')")
    assert is_overview_highlighted is True

    # Click Fast Billing nav item
    eval_js(view, "document.getElementById('btn-nav-pos').click()")
    is_pos_active = eval_js(view, "document.getElementById('view-fast-billing').classList.contains('active')")
    assert is_pos_active is True
    is_pos_highlighted = eval_js(view, "document.getElementById('btn-nav-pos').classList.contains('active')")
    assert is_pos_highlighted is True

    # Click Sales List nav item
    eval_js(view, "document.getElementById('btn-nav-sales-list').click()")
    is_sales_list_active = eval_js(view, "document.getElementById('view-sales-list').classList.contains('active')")
    assert is_sales_list_active is True

    # Click Overview nav item to return to dashboard
    eval_js(view, "document.getElementById('btn-nav-overview').click()")
    is_dash_active_again = eval_js(view, "document.getElementById('view-dashboard').classList.contains('active')")
    assert is_dash_active_again is True


def test_operational_dashboard_metrics_calculation(session_web_view):
    """Test renderOperationalDashboard() updates live metric cards."""
    view = session_web_view

    eval_js(view, """
        activeCompany = { id: 'COMP0001', name: 'ANTI MATRIX', fin_year: '2026-27' };
        renderOperationalDashboard();
    """)

    sales_val = eval_js(view, "document.getElementById('dash-today-sales').textContent")
    assert "₹" in sales_val or "&#8377;" in sales_val or "0.00" in sales_val

    pur_val = eval_js(view, "document.getElementById('dash-today-purchases').textContent")
    assert "₹" in pur_val or "&#8377;" in pur_val or "0.00" in pur_val

    low_stock_val = eval_js(view, "document.getElementById('dash-low-stock').textContent")
    assert "item" in low_stock_val

    held_bills_val = eval_js(view, "document.getElementById('dash-held-bills').textContent")
    assert "bill" in held_bills_val


def test_viewport_containment_with_sidebar(session_web_view):
    """Verify layout containment at various zoom levels with the operational sidebar."""
    view = session_web_view

    for zoom in [0.8, 1.0, 1.2]:
        eval_js(view, f"applyZoom({zoom}); showScreen('view-dashboard');")
        scroll_w = eval_js(view, "document.body.scrollWidth")
        client_w = eval_js(view, "document.body.clientWidth")
        # Ensure horizontal containment (no accidental body horizontal overflow)
        assert scroll_w <= client_w + 2, f"Horizontal blowout at zoom {zoom}: scrollWidth={scroll_w}, clientWidth={client_w}"

    # Reset zoom to 1.0
    eval_js(view, "applyZoom(1.0);")

