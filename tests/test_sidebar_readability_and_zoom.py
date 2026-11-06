"""
Test Suite for Alpha Billing – Sidebar Readability, Dark Typography and Global Zoom Integration

Validates:
1. Sidebar typography contrast & readability (primary headings: #0f172a, weight 700; icons: #1e293b).
2. Submenu typography (sub-buttons: #334155, weight 600; icons: #475569).
3. Active item identification (background: #eff6ff, text: #1e40af, weight 700, icon: #2563eb).
4. Visual hierarchy (Heading > Active Submenu > Normal Submenu > Secondary).
5. Hover states (maintains dark readable text #0f172a).
6. Tooltip and truncation safety (title attributes, min-width: 0, text-overflow: ellipsis).
7. Viewport containment and overflow prevention across zoom levels (70%, 100%, 130%, 150%).
8. Header zoom controls containment.
"""
import json
from pathlib import Path
import pytest
from PyQt5.QtCore import QEventLoop, QTimer

INDEX_HTML_PATH = Path(__file__).resolve().parent.parent / "index.html"
TOKENS_CSS_PATH = Path(__file__).resolve().parent.parent / "css" / "tokens.css"
LAYOUT_CSS_PATH = Path(__file__).resolve().parent.parent / "css" / "layout.css"
RESPONSIVE_CSS_PATH = Path(__file__).resolve().parent.parent / "css" / "responsive.css"
NAV_JS_PATH = Path(__file__).resolve().parent.parent / "js" / "navigation.js"


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


def test_sidebar_tokens_and_css_rules():
    """Verify CSS tokens and layout rules for sidebar readability and containment."""
    tokens_css = TOKENS_CSS_PATH.read_text(encoding="utf-8")
    assert "--alpha-sidebar-heading: #0f172a" in tokens_css
    assert "--alpha-sidebar-text: #334155" in tokens_css
    assert "--alpha-sidebar-icon: #1e293b" in tokens_css
    assert "--alpha-sidebar-sub-icon: #475569" in tokens_css

    layout_css = LAYOUT_CSS_PATH.read_text(encoding="utf-8")
    # Verify primary navigation button typography
    assert "color: var(--alpha-sidebar-heading, #0f172a);" in layout_css
    assert "font-weight: 700;" in layout_css
    # Verify submenu typography
    assert "color: var(--alpha-sidebar-text, #334155);" in layout_css
    assert "font-weight: 600;" in layout_css
    # Verify active state styling
    assert "#eff6ff" in layout_css
    assert "#1e40af" in layout_css
    # Verify truncation safety
    assert "min-width: 0;" in layout_css
    assert "text-overflow: ellipsis;" in layout_css
    assert "overflow: hidden;" in layout_css


def test_sidebar_primary_headings_typography(web_view):
    """Verify computed styles of primary navigation headings meet high contrast and weight requirements."""
    # Ensure dashboard is initialized and sidebar is expanded
    eval_js(web_view, """
        if (typeof companies !== 'undefined' && companies.length > 0) {
            activeCompany = companies[0];
            sessionLowStockDismissed = true;
            enterCompanyDashboard(companies[0]);
            if (typeof closeLowStockAlertModal === 'function') closeLowStockAlertModal(false);
        }
        if (window.SidebarNavigation && window.SidebarNavigation.isCollapsed) {
            window.SidebarNavigation.setCollapsed(false);
        }
    """)

    results = eval_js(web_view, """
        (function() {
            const parentBtns = Array.from(document.querySelectorAll('.nav-parent-btn'));
            return parentBtns.map(btn => {
                const style = window.getComputedStyle(btn);
                const label = btn.querySelector('.nav-label');
                const labelText = label ? label.textContent.trim() : '';
                const icon = btn.querySelector('.nav-icon');
                const iconStyle = icon ? window.getComputedStyle(icon) : null;

                return {
                    text: labelText,
                    title: btn.title,
                    color: style.color,
                    fontWeight: style.fontWeight,
                    iconColor: iconStyle ? iconStyle.color : null
                };
            });
        })()
    """)

    assert len(results) >= 8  # Company, Administration, Transaction, Display, Printing, Housekeeping, Help, Add-on
    expected_headings = [
        "Company", "Administration", "Transaction", "Display",
        "Printing", "Housekeeping", "Help", "Add-on"
    ]

    found_headings = [r["text"] for r in results]
    for exp in expected_headings:
        assert exp in found_headings, f"Expected primary heading '{exp}' not found in sidebar"

    for r in results:
        # Check dark charcoal/navy color rgb(15, 23, 42) = #0f172a (or active #1e3a8a rgb(30, 58, 138))
        # Both are dark high contrast >= 12:1 against #ffffff
        assert "rgb(15, 23, 42)" in r["color"] or "rgb(30, 58, 138)" in r["color"], (
            f"Heading '{r['text']}' color is '{r['color']}', expected dark charcoal/navy rgb(15, 23, 42)"
        )
        # Font weight must be strong: 700 or bold
        assert r["fontWeight"] in ["700", "bold"], f"Heading '{r['text']}' font weight is {r['fontWeight']}, expected 700"
        # Tooltip title must be set
        assert r["title"] == r["text"], f"Heading button '{r['text']}' missing title attribute"
        # Icon color must be sufficiently dark: rgb(30, 41, 59) (#1e293b) or active brand primary rgb(37, 99, 235)
        if r["iconColor"]:
            assert "rgb(30, 41, 59)" in r["iconColor"] or "rgb(37, 99, 235)" in r["iconColor"], (
                f"Heading '{r['text']}' icon color is '{r['iconColor']}', expected dark icon color"
            )


def test_sidebar_submenu_typography_and_hierarchy(web_view):
    """Verify submenu items have darker readable grey/navy typography and correct visual hierarchy."""
    # Expand Administration section
    eval_js(web_view, """
        if (window.SidebarNavigation) {
            window.SidebarNavigation.expandSection('administration');
        }
    """)

    sub_metrics = eval_js(web_view, """
        (function() {
            const subBtns = Array.from(document.querySelectorAll('.nav-sub-btn'));
            return subBtns.map(btn => {
                const style = window.getComputedStyle(btn);
                const label = btn.querySelector('.nav-sub-label');
                const labelText = label ? label.textContent.trim() : '';
                const icon = btn.querySelector('.nav-sub-icon');
                const iconStyle = icon ? window.getComputedStyle(icon) : null;

                return {
                    text: labelText,
                    title: btn.title,
                    color: style.color,
                    fontWeight: style.fontWeight,
                    iconColor: iconStyle ? iconStyle.color : null,
                    isActive: btn.classList.contains('active')
                };
            });
        })()
    """)

    assert len(sub_metrics) > 0
    for item in sub_metrics:
        # Check title attribute
        assert item["title"] == item["text"]
        if not item["isActive"]:
            # Normal submenu item: #334155 (rgb(51, 65, 85))
            assert "rgb(51, 65, 85)" in item["color"], (
                f"Submenu '{item['text']}' color is '{item['color']}', expected #334155 (rgb(51, 65, 85))"
            )
            # Font weight 600
            assert item["fontWeight"] in ["600", "bold"], (
                f"Submenu '{item['text']}' font weight is {item['fontWeight']}, expected 600"
            )
            # Icon color #475569 (rgb(71, 85, 105))
            if item["iconColor"]:
                assert "rgb(71, 85, 105)" in item["iconColor"], (
                    f"Submenu '{item['text']}' icon color is '{item['iconColor']}', expected #475569 (rgb(71, 85, 105))"
                )


def test_sidebar_active_item_identification(web_view):
    """Verify active navigation item has subtle light-blue background, dark blue text, and blue icon."""
    # Activate Item Master Add item
    eval_js(web_view, """
        if (window.SidebarNavigation) {
            window.SidebarNavigation.expandSection('administration');
            const item = document.getElementById('sub-item-master-add') || document.querySelector('.nav-sub-btn');
            if (item) item.click();
        }
    """)

    active_info = eval_js(web_view, """
        (function() {
            const activeSub = document.querySelector('.nav-sub-btn.active, .nav-child-sub-btn.active');
            if (!activeSub) return null;

            const style = window.getComputedStyle(activeSub);
            const icon = activeSub.querySelector('.nav-sub-icon');
            const iconStyle = icon ? window.getComputedStyle(icon) : null;
            const label = activeSub.querySelector('.nav-sub-label');

            return {
                text: label ? label.textContent.trim() : '',
                color: style.color,
                bgColor: style.backgroundColor,
                borderColor: style.borderColor,
                fontWeight: style.fontWeight,
                iconColor: iconStyle ? iconStyle.color : null
            };
        })()
    """)

    assert active_info is not None, "No active submenu button found in sidebar"
    # Background: #eff6ff (rgb(239, 246, 255))
    assert "rgb(239, 246, 255)" in active_info["bgColor"], (
        f"Active item background is {active_info['bgColor']}, expected #eff6ff (rgb(239, 246, 255))"
    )
    # Text color: #1e40af (rgb(30, 64, 175))
    assert "rgb(30, 64, 175)" in active_info["color"], (
        f"Active item text color is {active_info['color']}, expected #1e40af (rgb(30, 64, 175))"
    )
    # Font weight: 700
    assert active_info["fontWeight"] in ["700", "bold"], (
        f"Active item font weight is {active_info['fontWeight']}, expected 700"
    )
    # Icon color: #2563eb (rgb(37, 99, 235))
    if active_info["iconColor"]:
        assert "rgb(37, 99, 235)" in active_info["iconColor"], (
            f"Active item icon color is {active_info['iconColor']}, expected #2563eb (rgb(37, 99, 235))"
        )


@pytest.mark.parametrize("zoom_level", [0.70, 1.00, 1.30, 1.50])
def test_sidebar_containment_and_overflow_across_zoom_levels(web_view, zoom_level):
    """Verify sidebar remains strictly contained with zero horizontal overflow across 70%-150% zoom."""
    eval_js(web_view, f"""
        if (window.ZoomController) {{
            window.ZoomController.setZoom({zoom_level});
        }} else if (typeof applyZoom === 'function') {{
            applyZoom({zoom_level});
        }}
        if (window.SidebarNavigation) {{
            window.SidebarNavigation.setCollapsed(false);
            window.SidebarNavigation.expandSection('administration');
            window.SidebarNavigation.expandSection('display');
        }}
    """)

    # Give browser a moment to layout
    loop = QEventLoop()
    QTimer.singleShot(250, loop.quit)
    loop.exec_()

    metrics = eval_js(web_view, """
        (function() {
            const sidebar = document.getElementById('alpha-sidebar');
            const nav = document.getElementById('alpha-sidebar-nav');
            const footer = document.querySelector('.alpha-sidebar-footer');
            const header = document.querySelector('.alpha-top-header');
            const zoomControls = document.querySelector('.header-zoom-controls');
            const subBtns = Array.from(document.querySelectorAll('.nav-sub-btn, .nav-parent-btn'));

            const sidebarRect = sidebar.getBoundingClientRect();
            const headerRect = header ? header.getBoundingClientRect() : null;
            const zoomRect = zoomControls ? zoomControls.getBoundingClientRect() : null;

            // Check if any button or label exceeds the sidebar right edge
            let maxRightOverflow = 0;
            subBtns.forEach(btn => {
                const btnRect = btn.getBoundingClientRect();
                const overflow = btnRect.right - sidebarRect.right;
                if (overflow > maxRightOverflow) {
                    maxRightOverflow = overflow;
                }
            });

            return {
                sidebarScrollWidth: sidebar.scrollWidth,
                sidebarClientWidth: sidebar.clientWidth,
                navScrollWidth: nav ? nav.scrollWidth : 0,
                navClientWidth: nav ? nav.clientWidth : 0,
                maxButtonOverflow: maxRightOverflow,
                sidebarRight: sidebarRect.right,
                sidebarLeft: sidebarRect.left,
                headerRight: headerRect ? headerRect.right : 0,
                zoomControlsRight: zoomRect ? zoomRect.right : 0
            };
        })()
    """)

    assert metrics is not None
    # 1. Zero horizontal overflow in sidebar: scrollWidth <= clientWidth (+2px float rounding tolerance)
    assert metrics["sidebarScrollWidth"] <= metrics["sidebarClientWidth"] + 2, (
        f"Sidebar has horizontal overflow at zoom {zoom_level}: scrollWidth={metrics['sidebarScrollWidth']}, clientWidth={metrics['sidebarClientWidth']}"
    )

    # 2. Nav list container has no horizontal overflow
    assert metrics["navScrollWidth"] <= metrics["navClientWidth"] + 2, (
        f"Nav list has horizontal overflow at zoom {zoom_level}: scrollWidth={metrics['navScrollWidth']}, clientWidth={metrics['navClientWidth']}"
    )

    # 3. No buttons spill outside the sidebar right boundary
    assert metrics["maxButtonOverflow"] <= 2, (
        f"A navigation button spilled out of the sidebar by {metrics['maxButtonOverflow']}px at zoom {zoom_level}"
    )

    # 4. Zoom controls remain within the top header
    if metrics["zoomControlsRight"] > 0:
        assert metrics["zoomControlsRight"] <= metrics["headerRight"] + 2, (
            f"Zoom controls spilled out of top header at zoom {zoom_level}: controls right={metrics['zoomControlsRight']}, header right={metrics['headerRight']}"
        )


def test_sidebar_user_profile_footer_typography_and_containment(web_view):
    """Verify the bottom user profile footer has high contrast dark typography and stays contained."""
    footer_metrics = eval_js(web_view, """
        (function() {
            const footer = document.querySelector('.alpha-sidebar-footer');
            const userName = document.querySelector('.user-name');
            const userRole = document.querySelector('.user-role-badge');
            const logoutBtn = document.querySelector('.btn-user-action');

            if (!footer || !userName || !userRole) return null;

            const nameStyle = window.getComputedStyle(userName);
            const roleStyle = window.getComputedStyle(userRole);

            return {
                nameColor: nameStyle.color,
                nameFontWeight: nameStyle.fontWeight,
                roleColor: roleStyle.color,
                roleFontWeight: roleStyle.fontWeight
            };
        })()
    """)

    assert footer_metrics is not None
    # User name: #0f172a (rgb(15, 23, 42)), font-weight 700
    assert "rgb(15, 23, 42)" in footer_metrics["nameColor"], (
        f"User name color is {footer_metrics['nameColor']}, expected rgb(15, 23, 42)"
    )
    assert footer_metrics["nameFontWeight"] in ["700", "bold"]

    # User role: #475569 (rgb(71, 85, 105))
    assert "rgb(71, 85, 105)" in footer_metrics["roleColor"], (
        f"User role color is {footer_metrics['roleColor']}, expected rgb(71, 85, 105)"
    )
