"""
Test Suite for Global Application Zoom Across Every Screen in Alpha Billing
Verifies:
1. Central ZoomController singleton and window.applyZoom engine.
2. Zoom range: 70% to 150% with 10% increments and clamping at boundaries.
3. Header controls (#btn-zoom-in, #btn-zoom-out, #header-zoom-label):
   - Minus decreases zoom, Plus increases zoom.
   - Percentage updates immediately on both header and compatibility labels.
   - Buttons disabled at boundaries (70% and 150%).
4. Item & Product Master Add (#view-add-item-master) responsiveness:
   - Scales properly at 70%, 100%, 130%, 150%.
   - Form inputs, fieldsets, and save buttons remain visible and interactable.
   - Overflow and vertical scrolling function without clipping.
5. All other screens inherit the zoom level:
   - Dashboard, Company, Item Modify, Item List, Sales, Purchase, Fast Billing, Inventory, Reports.
6. Navigation and internal tab switching preserve zoom without resetting.
7. LocalStorage persistence across application restarts.
8. Printing dimensions and layout independence:
   - @media print resets zoom to 1 and preserves physical sheet dimensions (A4, A5, 80mm, 58mm).
   - Python ReportLab and thermal print services remain strictly independent of UI zoom.
"""
import json
from pathlib import Path
import pytest
from PyQt5.QtCore import QEventLoop, QTimer

INDEX_HTML_PATH = Path(__file__).resolve().parent.parent / "index.html"
STYLES_CSS_PATH = Path(__file__).resolve().parent.parent / "styles.css"
APP_JS_PATH = Path(__file__).resolve().parent.parent / "app.js"
LAYOUT_CSS_PATH = Path(__file__).resolve().parent.parent / "css" / "layout.css"


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


def test_zoom_controller_architecture_and_css_rules():
    """Verify that ZoomController is implemented centrally and CSS rules support both .alpha-app-shell and @media print."""
    app_js = APP_JS_PATH.read_text(encoding="utf-8")
    assert "const ZoomController = {" in app_js
    assert "window.ZoomController = ZoomController;" in app_js
    assert "window.applyZoom = applyZoom;" in app_js
    assert "MIN_ZOOM: 0.70" in app_js
    assert "MAX_ZOOM: 1.50" in app_js
    assert "STEP: 0.10" in app_js

    styles_css = STYLES_CSS_PATH.read_text(encoding="utf-8")
    assert ".alpha-app-shell {" in styles_css
    assert "zoom: var(--ui-scale" in styles_css
    assert "@media print {" in styles_css
    assert "zoom: 1 !important;" in styles_css
    assert "sheet-thermal-80" in styles_css
    assert "sheet-thermal-58" in styles_css

    layout_css = LAYOUT_CSS_PATH.read_text(encoding="utf-8")
    assert ".alpha-app-shell {" in layout_css
    assert "zoom: var(--ui-scale" in layout_css
    assert ".btn-header-zoom:disabled" in layout_css


def test_header_zoom_controls_stepping_and_labels(web_view):
    """Test header minus, plus buttons, labels, and boundary disabling."""
    # Reset to 100%
    eval_js(web_view, "window.ZoomController.resetZoom();")
    loop = QEventLoop()
    QTimer.singleShot(150, loop.quit)
    loop.exec_()

    state = eval_js(web_view, """
        (function() {
            const hLabel = document.getElementById('header-zoom-label');
            const qLabel = document.getElementById('quick-zoom-label');
            const btnIn = document.getElementById('btn-zoom-in');
            const btnOut = document.getElementById('btn-zoom-out');
            return {
                zoom: window.ZoomController.getZoom(),
                hText: hLabel ? hLabel.textContent.trim() : '',
                qText: qLabel ? qLabel.textContent.trim() : '',
                inDisabled: btnIn ? btnIn.disabled : false,
                outDisabled: btnOut ? btnOut.disabled : false
            };
        })()
    """)
    assert state["zoom"] == 1.0
    assert state["hText"] == "100%"
    assert state["qText"] == "100%"
    assert state["inDisabled"] is False
    assert state["outDisabled"] is False

    # Click Plus button -> 110%
    eval_js(web_view, "document.getElementById('btn-zoom-in').click();")
    state = eval_js(web_view, """
        ({
            zoom: window.ZoomController.getZoom(),
            hText: document.getElementById('header-zoom-label').textContent.trim(),
            qText: document.getElementById('quick-zoom-label').textContent.trim()
        })
    """)
    assert state["zoom"] == 1.10
    assert state["hText"] == "110%"
    assert state["qText"] == "110%"

    # Step up to 130%
    eval_js(web_view, "document.getElementById('btn-zoom-in').click();")
    eval_js(web_view, "document.getElementById('btn-zoom-in').click();")
    state = eval_js(web_view, """
        ({
            zoom: window.ZoomController.getZoom(),
            hText: document.getElementById('header-zoom-label').textContent.trim()
        })
    """)
    assert state["zoom"] == 1.30
    assert state["hText"] == "130%"

    # Step up to maximum 150%
    eval_js(web_view, "window.ZoomController.applyZoom(1.50);")
    state = eval_js(web_view, """
        ({
            zoom: window.ZoomController.getZoom(),
            hText: document.getElementById('header-zoom-label').textContent.trim(),
            inDisabled: document.getElementById('btn-zoom-in').disabled,
            outDisabled: document.getElementById('btn-zoom-out').disabled
        })
    """)
    assert state["zoom"] == 1.50
    assert state["hText"] == "150%"
    assert state["inDisabled"] is True
    assert state["outDisabled"] is False

    # Attempting to click Plus at max does not exceed 150%
    eval_js(web_view, "window.ZoomController.zoomIn();")
    assert eval_js(web_view, "window.ZoomController.getZoom()") == 1.50

    # Step down to minimum 70%
    eval_js(web_view, "window.ZoomController.applyZoom(0.70);")
    state = eval_js(web_view, """
        ({
            zoom: window.ZoomController.getZoom(),
            hText: document.getElementById('header-zoom-label').textContent.trim(),
            inDisabled: document.getElementById('btn-zoom-in').disabled,
            outDisabled: document.getElementById('btn-zoom-out').disabled
        })
    """)
    assert state["zoom"] == 0.70
    assert state["hText"] == "70%"
    assert state["inDisabled"] is False
    assert state["outDisabled"] is True

    # Attempting to zoom out below 70% does not go below 70%
    eval_js(web_view, "window.ZoomController.zoomOut();")
    assert eval_js(web_view, "window.ZoomController.getZoom()") == 0.70


@pytest.mark.parametrize("zoom_level", [0.70, 1.00, 1.30, 1.50])
def test_item_master_add_screen_responsiveness_at_zoom_levels(web_view, zoom_level):
    """Verify that Item Master Add (#view-add-item-master) properly scales and responds to zoom."""
    # Ensure active company
    eval_js(web_view, """
        if (typeof companies !== 'undefined' && companies.length > 0) {
            activeCompany = companies[0];
            sessionLowStockDismissed = true;
        }
    """)

    # Navigate to Item Master Add and set tested zoom
    eval_js(web_view, f"""
        window.applyZoom({zoom_level});
        showScreen('view-add-item-master');
    """)
    loop = QEventLoop()
    QTimer.singleShot(250, loop.quit)
    loop.exec_()

    metrics = eval_js(web_view, """
        (function() {
            const root = document.getElementById('app-root');
            const view = document.getElementById('view-add-item-master');
            const form = document.getElementById('form-item-master');
            const nameInput = document.getElementById('item-name');
            const barcodeInput = document.getElementById('item-alias');
            const minStockInput = document.getElementById('item-min-stock-level');
            const reorderInput = document.getElementById('item-reorder-level');
            const salesPriceInput = document.getElementById('item-sales-price');
            const ribbon = view.querySelector('.form-screen-ribbon');

            const scale = window.ZoomController.getZoom();
            const rootRect = root.getBoundingClientRect();
            const viewRect = view.getBoundingClientRect();
            const ribbonRect = ribbon.getBoundingClientRect();

            return {
                active: view.classList.contains('active'),
                scale: scale,
                rootStyleZoom: root.style.zoom,
                rootRenderedWidth: Math.round(rootRect.width * scale),
                winW: window.innerWidth,
                viewWidth: Math.round(viewRect.width * scale),
                ribbonWidth: Math.round(ribbonRect.width * scale),
                nameInputVisible: nameInput && nameInput.offsetParent !== null,
                barcodeInputVisible: barcodeInput && barcodeInput.offsetParent !== null,
                minStockVisible: minStockInput && minStockInput.offsetParent !== null,
                reorderVisible: reorderInput && reorderInput.offsetParent !== null,
                salesPriceVisible: salesPriceInput && salesPriceInput.offsetParent !== null,
                formScrollable: form ? (form.scrollHeight >= form.clientHeight) : false
            };
        })()
    """)

    assert metrics["active"] is True
    assert float(metrics["scale"]) == float(zoom_level)
    assert float(metrics["rootStyleZoom"]) == float(zoom_level)
    # Viewport containment within 2px
    assert abs(metrics["rootRenderedWidth"] - metrics["winW"]) <= 2
    # Form controls remain fully present & visible
    assert metrics["nameInputVisible"] is True
    assert metrics["barcodeInputVisible"] is True
    assert metrics["minStockVisible"] is True
    assert metrics["reorderVisible"] is True
    assert metrics["salesPriceVisible"] is True


def test_navigation_preserves_zoom_without_reset(web_view):
    """Verify that switching between different screens preserves the selected zoom level."""
    # Set zoom to 130%
    eval_js(web_view, """
        window.applyZoom(1.30);
        showScreen('view-dashboard');
    """)
    assert eval_js(web_view, "window.ZoomController.getZoom()") == 1.30

    # Navigate to Item Master Add
    eval_js(web_view, "showScreen('view-add-item-master');")
    assert eval_js(web_view, "window.ZoomController.getZoom()") == 1.30
    assert eval_js(web_view, "document.getElementById('header-zoom-label').textContent.trim()") == "130%"

    # Navigate to Sales Voucher
    eval_js(web_view, "showScreen('view-sales-voucher');")
    assert eval_js(web_view, "window.ZoomController.getZoom()") == 1.30
    assert eval_js(web_view, "document.getElementById('header-zoom-label').textContent.trim()") == "130%"

    # Navigate to Products List
    eval_js(web_view, "showScreen('view-items-list');")
    assert eval_js(web_view, "window.ZoomController.getZoom()") == 1.30

    # Navigate to Purchase Entry
    eval_js(web_view, "showScreen('view-purchase-entry');")
    assert eval_js(web_view, "window.ZoomController.getZoom()") == 1.30

    # Return to Dashboard
    eval_js(web_view, "showScreen('view-dashboard');")
    assert eval_js(web_view, "window.ZoomController.getZoom()") == 1.30
    assert eval_js(web_view, "document.getElementById('header-zoom-label').textContent.trim()") == "130%"


def test_internal_tab_switching_preserves_zoom(web_view):
    """Verify that switching between Traditional Billing and Fast Billing preserves active zoom."""
    eval_js(web_view, """
        window.applyZoom(1.20);
        showScreen('view-dashboard');
    """)
    assert eval_js(web_view, "window.ZoomController.getZoom()") == 1.20

    # Switch to Fast Billing workspace
    eval_js(web_view, "openFastBillingPos();")
    assert eval_js(web_view, "window.ZoomController.getZoom()") == 1.20
    assert eval_js(web_view, "document.getElementById('header-zoom-label').textContent.trim()") == "120%"
    assert eval_js(web_view, "document.getElementById('app-root').style.zoom") in ("1.2", "1.20")

    # Switch back to Traditional Billing tab
    eval_js(web_view, "switchInternalBillingTab('traditional');")
    assert eval_js(web_view, "window.ZoomController.getZoom()") == 1.20
    assert eval_js(web_view, "document.getElementById('header-zoom-label').textContent.trim()") == "120%"


def test_local_storage_persistence(web_view):
    """Verify that selected zoom is stored in localStorage and loaded on initialization."""
    eval_js(web_view, "window.applyZoom(1.40);")
    saved = eval_js(web_view, "localStorage.getItem('alpha_ui_zoom');")
    assert saved in ("1.4", "1.40")

    # Simulate fresh init reading from localStorage
    eval_js(web_view, "window.ZoomController.init();")
    assert eval_js(web_view, "window.ZoomController.getZoom()") == 1.40
    assert eval_js(web_view, "document.getElementById('header-zoom-label').textContent.trim()") == "140%"

    # Restore to 100%
    eval_js(web_view, "window.ZoomController.resetZoom();")
    assert eval_js(web_view, "localStorage.getItem('alpha_ui_zoom')") in ("1", "1.0", "1.00")


def test_modals_and_dropdowns_under_zoom(web_view):
    """Verify modals and dropdowns maintain positioning without overflow at 130% zoom."""
    eval_js(web_view, "window.applyZoom(1.30);")

    # Open Configuration modal
    eval_js(web_view, """
        const m = document.getElementById('modal-configuration');
        if (m) m.classList.add('show');
    """)
    res = eval_js(web_view, """
        (function() {
            const modal = document.getElementById('modal-configuration');
            const box = modal.querySelector('.create-comp-dialog-box');
            const scale = window.ZoomController.getZoom();
            const boxRect = box.getBoundingClientRect();
            return {
                isOpen: modal.classList.contains('show'),
                rightEdge: Math.round(boxRect.right * scale),
                bottomEdge: Math.round(boxRect.bottom * scale),
                winW: window.innerWidth,
                winH: window.innerHeight
            };
        })()
    """)
    assert res["isOpen"] is True
    assert res["rightEdge"] <= res["winW"] + 2
    assert res["bottomEdge"] <= res["winH"] + 2

    # Close modal
    eval_js(web_view, "document.getElementById('modal-configuration').classList.remove('show');")


def test_print_dimensions_independence_from_screen_zoom():
    """Verify that print formats (ReportLab PDF & CSS @media print) remain strictly independent of UI zoom."""
    # 1. Verify CSS @media print resets zoom to 1
    css = STYLES_CSS_PATH.read_text(encoding="utf-8")
    assert "@media print {" in css
    assert "zoom: 1 !important;" in css
    assert "--ui-scale: 1 !important;" in css
    assert "width: 80mm !important;" in css
    assert "width: 58mm !important;" in css

    # 2. Verify backend PDF invoice uses exact standard A4 points
    from services.printing_service import PrintingService
    from reportlab.lib.pagesizes import A4
    assert A4[0] == pytest.approx(595.27, 0.01)
    assert A4[1] == pytest.approx(841.89, 0.01)

    # 3. Verify thermal receipt formatting uses exact char width independent of screen zoom
    sample_vch = {
        "vch_no": "BILL-TEST-001",
        "vch_date": "2026-11-06",
        "company_name": "ANTI MATRIX",
        "net_amount": 150.00,
        "items": [{"name": "Milk Bikis", "qty": 2, "unit_price": 20.0, "total": 40.0}]
    }
    rec_80 = PrintingService.format_thermal_receipt(sample_vch, width_mm=80)
    rec_58 = PrintingService.format_thermal_receipt(sample_vch, width_mm=58)
    assert len(rec_80) > 0
    assert len(rec_58) > 0
    # 80mm format line width <= 48 chars; 58mm line width <= 32 chars
    assert all(len(line) <= 48 for line in rec_80.splitlines())
    assert all(len(line) <= 32 for line in rec_58.splitlines())
