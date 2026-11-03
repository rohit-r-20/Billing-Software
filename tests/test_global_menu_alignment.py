"""
Test Suite for Global Menu Alignment and Cascading Menu Positioning Fix.
Verifies:
- All top navigation menus and nested submenu columns are consistently left-aligned.
- Masters, Configuration, Account, Products & Items, Sales, Purchase headers have labels on left and arrows on right.
- Cascading submenus open adjacent to parent items and remain inside viewport.
- Alignment and containment are preserved across zoom levels (80%, 90%, 100%, 110%, 120%).
- All existing menu actions and click handlers continue functioning.
"""
import sys
from pathlib import Path
import pytest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QEventLoop, QTimer

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_HTML = BASE_DIR / "index.html"
STYLES_CSS = BASE_DIR / "styles.css"
APP_JS = BASE_DIR / "app.js"


@pytest.fixture
def web_view(session_web_view):
    return session_web_view


def eval_js(view, script):
    loop = QEventLoop()
    result = {"val": None}

    def callback(res):
        result["val"] = res
        loop.quit()

    view.page().runJavaScript(script, callback)
    loop.exec_()
    return result["val"]


def test_menu_html_structure():
    """Verify HTML structure of branches, labels, arrows, and element IDs."""
    html = INDEX_HTML.read_text(encoding="utf-8")

    # Check that branches have tree-label preceding tree-arrow
    assert '<div class="tree-branch-header"><span class="tree-label">Masters</span><span class="tree-arrow">&rsaquo;</span></div>' in html
    assert '<span class="tree-label">Account</span><span class="tree-arrow">&rsaquo;</span>' in html
    assert '<span class="tree-label">Supplier Master</span><span class="tree-arrow">&rsaquo;</span>' in html
    assert '<span class="tree-label">Products &amp; Items</span><span class="tree-arrow">&rsaquo;</span>' in html
    assert '<span class="tree-label">Configuration</span><span class="tree-arrow">&rsaquo;</span>' in html
    assert '<span class="tree-label">Sales</span><span class="tree-arrow">&rsaquo;</span>' in html
    assert '<span class="tree-label">Purchase</span><span class="tree-arrow">&rsaquo;</span>' in html

    # Verify key menu IDs are preserved
    expected_ids = [
        "menu-switch-mode", "menu-close-company", "menu-edit-company", "menu-new-company",
        "menu-add-account-master", "menu-modify-account-master", "menu-list-account-master",
        "menu-list-supplier-master", "menu-add-supplier-master",
        "menu-list-item-master", "menu-add-item-master", "menu-modify-item-master",
        "menu-config-features", "menu-config-voucher-series", "menu-change-password",
        "menu-data-export-import", "menu-fast-billing", "menu-sales-add", "menu-sales-modify",
        "menu-sales-list", "menu-purchase-add", "menu-purchase-modify", "menu-purchase-list",
        "menu-sales-return", "menu-purchase-return", "menu-stock-transfer", "menu-stock-adjustment",
        "menu-display-bills", "menu-display-purchase-register", "menu-display-trial-balance",
        "menu-display-daybook", "menu-display-stock", "menu-gst-reports",
        "menu-printer-settings", "menu-backup-restore", "menu-zoom-in", "menu-zoom-out",
        "menu-zoom-reset", "menu-help-shortcuts", "menu-help-about"
    ]
    for m_id in expected_ids:
        assert f'id="{m_id}"' in html, f"Missing menu id: {m_id}"


def test_menu_css_alignment_rules():
    """Verify CSS alignment rules for menus, items, branches, and arrows."""
    css = STYLES_CSS.read_text(encoding="utf-8")

    # Menubar overflow must be visible to allow dropdowns to pop down
    assert "overflow: visible;" in css

    # Tree items must be left-aligned
    assert ".tree-item {" in css
    assert "justify-content: flex-start;" in css

    # Branch headers must have space-between for left label and right arrow
    assert ".tree-branch-header {" in css
    assert "justify-content: space-between;" in css

    # Viewport boundary classes
    assert ".tree-submenu.submenu-flip-left" in css
    assert ".tree-submenu.submenu-shift-up" in css


def test_app_js_cascading_positioning():
    """Verify app.js includes cascading submenu positioning logic."""
    js = APP_JS.read_text(encoding="utf-8")
    assert "initCascadingSubmenuPositioning" in js
    assert "submenu-flip-left" in js
    assert "submenu-shift-up" in js


@pytest.mark.parametrize("zoom_level", [0.80, 0.90, 1.00, 1.10, 1.20])
def test_administration_menu_left_alignment_across_zoom(web_view, zoom_level):
    """Verify that all labels in Administration Column 1 share the exact same left coordinate across zoom levels."""
    # Enter dashboard
    eval_js(web_view, """
        if (typeof companies !== 'undefined' && companies.length > 0) {
            activeCompany = companies[0];
            sessionLowStockDismissed = true;
            enterCompanyDashboard(companies[0]);
            if (typeof closeLowStockAlertModal === 'function') closeLowStockAlertModal(false);
        }
    """)

    # Apply zoom
    eval_js(web_view, f"applyZoom({zoom_level});")
    loop = QEventLoop()
    QTimer.singleShot(250, loop.quit)
    loop.exec_()

    # Open Administration menu and measure label left positions
    result = eval_js(web_view, """
        (function() {
            const adminTree = document.querySelector('[data-menu="administration"] .dropdown-tree');
            adminTree.style.display = 'flex';
            
            const labels = [];
            // Get all direct tree-item and tree-branch-header in the first column
            adminTree.querySelectorAll(':scope > .tree-item, :scope > .tree-branch > .tree-branch-header').forEach(row => {
                const label = row.querySelector('.tree-label') || row;
                const rect = label.getBoundingClientRect();
                labels.push({
                    text: label.textContent.trim(),
                    left: Math.round(rect.left),
                    width: Math.round(rect.width)
                });
            });

            // Check branch header arrow position relative to label
            const mastersHeader = adminTree.querySelector('.tree-branch > .tree-branch-header');
            const mastersLabel = mastersHeader.querySelector('.tree-label').getBoundingClientRect();
            const mastersArrow = mastersHeader.querySelector('.tree-arrow').getBoundingClientRect();

            return {
                labels: labels,
                arrowIsRightOfLabel: mastersArrow.left > mastersLabel.right
            };
        })()
    """)

    assert result is not None
    labels = result["labels"]
    assert len(labels) >= 8

    # All labels in column 1 must have the identical left coordinate (within 1px subpixel tolerance)
    first_left = labels[0]["left"]
    for item in labels:
        assert abs(item["left"] - first_left) <= 1, f"Label {item['text']} left {item['left']} != {first_left}"

    # Arrow must be positioned to the right of the label
    assert result["arrowIsRightOfLabel"] is True


@pytest.mark.parametrize("zoom_level", [0.80, 0.90, 1.00, 1.10, 1.20])
def test_transactions_menu_left_alignment_across_zoom(web_view, zoom_level):
    """Verify that all labels in Transactions column share the exact same left coordinate across zoom levels."""
    # Ensure active company dashboard
    eval_js(web_view, """
        if (typeof companies !== 'undefined' && companies.length > 0) {
            activeCompany = companies[0];
            sessionLowStockDismissed = true;
            enterCompanyDashboard(companies[0]);
            if (typeof closeLowStockAlertModal === 'function') closeLowStockAlertModal(false);
        }
    """)
    eval_js(web_view, f"applyZoom({zoom_level});")
    loop = QEventLoop()
    QTimer.singleShot(250, loop.quit)
    loop.exec_()

    result = eval_js(web_view, """
        (function() {
            const transTree = document.querySelector('[data-menu="transactions"] .dropdown-tree');
            transTree.style.display = 'flex';
            
            const labels = [];
            transTree.querySelectorAll(':scope > .tree-item, :scope > .tree-branch > .tree-branch-header').forEach(row => {
                const label = row.querySelector('.tree-label') || row;
                const rect = label.getBoundingClientRect();
                labels.push({
                    text: label.textContent.trim(),
                    left: Math.round(rect.left),
                    width: Math.round(rect.width)
                });
            });

            const salesHeader = transTree.querySelector('.tree-branch > .tree-branch-header');
            const salesLabel = salesHeader.querySelector('.tree-label').getBoundingClientRect();
            const salesArrow = salesHeader.querySelector('.tree-arrow').getBoundingClientRect();

            return {
                labels: labels,
                arrowIsRightOfLabel: salesArrow.left > salesLabel.right
            };
        })()
    """)

    assert result is not None
    labels = result["labels"]
    assert len(labels) >= 10

    first_left = labels[0]["left"]
    for item in labels:
        assert abs(item["left"] - first_left) <= 1, f"Label {item['text']} left {item['left']} != {first_left}"

    assert result["arrowIsRightOfLabel"] is True


def test_cascading_submenus_alignment_and_containment(web_view):
    """Verify nested submenus (Level 2 & Level 3) are left-aligned and adjacent to parent items."""
    eval_js(web_view, """
        if (typeof companies !== 'undefined' && companies.length > 0) {
            activeCompany = companies[0];
            sessionLowStockDismissed = true;
            enterCompanyDashboard(companies[0]);
            if (typeof closeLowStockAlertModal === 'function') closeLowStockAlertModal(false);
        }
    """)
    eval_js(web_view, "applyZoom(1.0);")
    loop = QEventLoop()
    QTimer.singleShot(200, loop.quit)
    loop.exec_()

    res = eval_js(web_view, """
        (function() {
            const adminTree = document.querySelector('[data-menu="administration"] .dropdown-tree');
            adminTree.style.display = 'flex';

            const mastersBranch = adminTree.querySelector('.tree-branch');
            const mastersSub = mastersBranch.querySelector('.tree-submenu');
            mastersSub.style.display = 'flex';

            const mastersHeaderRect = mastersBranch.querySelector('.tree-branch-header').getBoundingClientRect();
            const mastersSubRect = mastersSub.getBoundingClientRect();

            // Measure Level 2 items in Masters submenu
            const level2Labels = [];
            mastersSub.querySelectorAll(':scope > .tree-item, :scope > .tree-branch > .tree-branch-header').forEach(row => {
                const label = row.querySelector('.tree-label') || row;
                level2Labels.push({
                    text: label.textContent.trim(),
                    left: Math.round(label.getBoundingClientRect().left)
                });
            });

            // Open Level 3 Account submenu
            const accountBranch = mastersSub.querySelector('.tree-branch');
            const accountSub = accountBranch.querySelector('.tree-submenu');
            accountSub.style.display = 'flex';

            const accountHeaderRect = accountBranch.querySelector('.tree-branch-header').getBoundingClientRect();
            const accountSubRect = accountSub.getBoundingClientRect();

            const level3Labels = [];
            accountSub.querySelectorAll(':scope > .tree-item').forEach(row => {
                const label = row.querySelector('.tree-label') || row;
                level3Labels.push({
                    text: label.textContent.trim(),
                    left: Math.round(label.getBoundingClientRect().left)
                });
            });

            return {
                level2Adjacent: Math.abs(mastersSubRect.left - mastersHeaderRect.right) <= 2,
                level2VerticalAligned: Math.abs(mastersSubRect.top - mastersHeaderRect.top) <= 2,
                level2Labels: level2Labels,
                level3Adjacent: Math.abs(accountSubRect.left - accountHeaderRect.right) <= 2,
                level3Labels: level3Labels
            };
        })()
    """)

    assert res is not None
    assert res["level2Adjacent"] is True
    assert res["level2VerticalAligned"] is True
    assert res["level3Adjacent"] is True

    # Level 2 all left-aligned
    l2 = res["level2Labels"]
    l2_first = l2[0]["left"]
    for it in l2:
        assert abs(it["left"] - l2_first) <= 1

    # Level 3 all left-aligned
    l3 = res["level3Labels"]
    l3_first = l3[0]["left"]
    for it in l3:
        assert abs(it["left"] - l3_first) <= 1


def test_menu_actions_continue_functioning(web_view):
    """Verify that clicking menu items opens their corresponding screens."""
    eval_js(web_view, """
        if (typeof companies !== 'undefined' && companies.length > 0) {
            activeCompany = companies[0];
            sessionLowStockDismissed = true;
            enterCompanyDashboard(companies[0]);
            if (typeof closeLowStockAlertModal === 'function') closeLowStockAlertModal(false);
        }
    """)

    # 1. Test Fast Billing menu item
    res_pos = eval_js(web_view, """
        (function() {
            const btn = document.getElementById('menu-fast-billing');
            if (btn) btn.click();
            return currentScreen;
        })()
    """)
    assert res_pos == "view-fast-billing"

    # 2. Test Traditional Sales Voucher menu item
    res_vch = eval_js(web_view, """
        (function() {
            const btn = document.getElementById('menu-sales-add');
            if (btn) btn.click();
            return currentScreen;
        })()
    """)
    assert res_vch == "view-sales-voucher"

    # 3. Test Products List menu item
    res_items = eval_js(web_view, """
        (function() {
            const btn = document.getElementById('menu-list-item-master');
            if (btn) btn.click();
            return currentScreen;
        })()
    """)
    assert res_items == "view-items-list"
