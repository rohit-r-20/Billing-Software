"""
Tests for Alpha Billing Dashboard, Navigation, and WebEngine Integration.
"""
import json
import subprocess
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_HTML = BASE_DIR / "index.html"
STYLES_CSS = BASE_DIR / "styles.css"
APP_PY = BASE_DIR / "app.py"
MAIN_WINDOW_PY = BASE_DIR / "desktop" / "main_window.py"
NAV_JS = BASE_DIR / "js" / "navigation.js"
HEADER_JS = BASE_DIR / "js" / "header.js"
DASH_JS = BASE_DIR / "js" / "dashboard.js"
CONTEXT_JS = BASE_DIR / "js" / "business_context.js"
ICONS_JS = BASE_DIR / "js" / "icons.js"


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


def test_webengine_chromium_flags_configured():
    """Verify Chromium --no-sandbox flag is configured in app.py and desktop/main_window.py."""
    app_text = APP_PY.read_text(encoding="utf-8")
    assert "QTWEBENGINE_CHROMIUM_FLAGS" in app_text
    assert "--no-sandbox" in app_text

    main_win_text = MAIN_WINDOW_PY.read_text(encoding="utf-8")
    assert "QTWEBENGINE_CHROMIUM_FLAGS" in main_win_text
    assert "--no-sandbox" in main_win_text
    assert "LocalContentCanAccessFileUrls" in main_win_text
    assert "renderProcessTerminated" in main_win_text


def test_index_html_alpha_shell_structure():
    """Verify index.html contains the Alpha Billing shell, sidebar, header, and dashboard."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="app-root"' in html
    assert 'id="alpha-sidebar"' in html
    assert 'class="alpha-top-header"' in html
    assert 'id="view-dashboard"' in html


def test_company_navigation_exactly_two_entries():
    """Verify Company contains exactly 2 submenus: Edit Company and Close Company."""
    nav_config = _get_evaluated_nav_config()
    comp = next(s for s in nav_config if s["id"] == "company")
    labels = [sub["label"] for sub in comp["submenus"]]

    assert len(labels) == 2
    assert labels == ["Edit Company", "Close Company"]

    # Verify obsolete entries are completely absent
    assert "Switch Company" not in labels
    assert "Branch Management" not in labels
    assert "Company Profile & Tax Info" not in labels


def test_administration_navigation_exactly_nine_entries():
    """Verify Administration contains exactly 9 submenus in exact order."""
    nav_config = _get_evaluated_nav_config()
    admin = next(s for s in nav_config if s["id"] == "administration")
    labels = [sub["label"] for sub in admin["submenus"]]

    expected_order = [
        "Masters",
        "Configuration",
        "Users",
        "Mobile App",
        "Utilities",
        "Bulk Updates",
        "Data Export Import",
        "Miscellaneous Data Entry",
        "Change Financial Year"
    ]
    assert len(labels) == 9
    assert labels == expected_order


def test_transaction_navigation_exactly_thirteen_entries():
    """Verify Transaction contains exactly 13 submenus in exact order."""
    nav_config = _get_evaluated_nav_config()
    tx = next(s for s in nav_config if s["id"] == "transaction")
    labels = [sub["label"] for sub in tx["submenus"]]

    expected_tx_order = [
        "Sales",
        "Purchase",
        "Sales Return (Cr. Note)",
        "Purchase Return (Dr. Note)",
        "Payment",
        "Receipt",
        "Journal",
        "Contra",
        "Dr. Note (w/o Items)",
        "Cr. Note (w/o Items)",
        "Stock Transfer",
        "Stock Journal",
        "GST Misc. Utilities"
    ]
    assert len(labels) == 13
    assert labels == expected_tx_order


def test_other_primary_sections_unchanged():
    """Verify Display, Printing, Housekeeping, Help, and Add-on sections remain intact."""
    nav_config = _get_evaluated_nav_config()
    section_ids = [s["id"] for s in nav_config]
    assert section_ids == [
        "company",
        "administration",
        "transaction",
        "display",
        "printing",
        "housekeeping",
        "help",
        "addon"
    ]


def test_company_and_placeholder_modals_exist_in_html():
    """Verify Edit Company, Close Company Confirm, and Feature Placeholder modals exist."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="modal-edit-company"' in html
    assert 'id="edit-comp-name"' in html
    assert 'id="btn-save-edit-company"' in html

    assert 'id="modal-close-company-confirm"' in html
    assert 'id="btn-confirm-close-company"' in html

    assert 'id="modal-feature-placeholder"' in html
    assert 'id="placeholder-modal-title"' in html
    assert 'id="btn-ok-placeholder-modal"' in html


def test_header_multi_business_selectors():
    """Verify header contains multi-company and multi-branch selectors and profile menu."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="btn-header-company"' in html
    assert 'id="btn-header-branch"' in html
    assert 'id="btn-trigger-global-search"' in html
    assert 'id="btn-header-notifications"' in html
    assert 'id="btn-header-user"' in html


def test_dashboard_six_kpi_cards():
    """Verify the 6 required KPI cards exist in dashboard markup."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    kpis = [
        "dash-today-sales",
        "dash-today-purchases",
        "dash-total-stock-value",
        "dash-receivables",
        "dash-payables",
        "dash-today-expenses"
    ]
    for kpi_id in kpis:
        assert f'id="{kpi_id}"' in html


def test_dashboard_analytics_charts_and_activities():
    """Verify analytics charts and activity tabs exist."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="chart-sales-trend-container"' in html
    assert 'id="chart-payment-summary-container"' in html
    assert 'id="dash-recent-sales-tbody"' in html
    assert 'id="dash-recent-purchases-tbody"' in html
    assert 'id="dash-recent-payments-tbody"' in html
    assert 'id="dash-recent-stock-adjustments-tbody"' in html
    assert 'id="dashboard-quick-actions-panel"' in html


def test_css_modular_imports_and_light_theme_tokens():
    """Verify styles.css imports tokens, layout, components, dashboard, and responsive css."""
    css = STYLES_CSS.read_text(encoding="utf-8")
    assert "tokens.css" in css
    assert "layout.css" in css
    assert "components.css" in css
    assert "dashboard.css" in css
    assert "responsive.css" in css
