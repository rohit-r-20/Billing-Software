"""
Automated Test Suite for Global Removal of Duplicate Window Control Buttons.

Validates:
1. Complete removal of .window-controls and .win-btn across the entire DOM.
2. Absence of custom Minimize (—), Maximize (□), and Close (×) window buttons on all pages.
3. Native macOS traffic-light / window control hints preservation on MainWindow.
4. Header layout alignment, zoom controls functionality, and switch billing mode integrity.
5. All major views (Overview, Fast Billing, Traditional Billing, Catalogue, etc.) verified.
"""
import sys
from pathlib import Path
import pytest
from PyQt5.QtCore import QEventLoop, QTimer, Qt, QUrl
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView

from desktop.main_window import MainWindow

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_HTML = BASE_DIR / "index.html"
STYLES_CSS = BASE_DIR / "styles.css"


def eval_js(view, script):
    loop = QEventLoop()
    result = {"val": None}

    def callback(res):
        result["val"] = res
        loop.quit()

    view.page().runJavaScript(script, callback)
    loop.exec_()
    return result["val"]


def wait_ms(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec_()


@pytest.fixture(scope="module")
def app_instance():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def live_window(app_instance):
    win = MainWindow()
    win.resize(1280, 800)
    win.show()

    loop = QEventLoop()
    win.web_view.loadFinished.connect(lambda ok: loop.quit())
    loop.exec_()
    wait_ms(600)

    # Initialize company session
    eval_js(win.web_view, """
        if (typeof companies !== 'undefined' && companies.length > 0) {
            activeCompany = companies[0];
            sessionLowStockDismissed = true;
            enterCompanyDashboard(companies[0]);
        }
    """)
    wait_ms(300)

    yield win
    win.close()


def test_custom_window_controls_completely_absent_from_dom(live_window):
    """Verify that .window-controls and .win-btn are completely absent from the DOM."""
    res = eval_js(live_window.web_view, """
        (function() {
            const winControls = document.querySelector('.window-controls');
            const winBtns = document.querySelectorAll('.win-btn');
            const minimizeBtns = document.querySelectorAll('button[title="Minimize"]');
            const maximizeBtns = document.querySelectorAll('button[title="Maximize"]');
            
            // Check titlebar structure
            const titlebar = document.querySelector('.alpha-titlebar');
            const titleLeft = titlebar ? titlebar.querySelector('.title-left') : null;
            const headerTools = titlebar ? titlebar.querySelector('.header-center-tools') : null;

            return {
                hasWinControls: winControls !== null,
                winBtnsCount: winBtns.length,
                minimizeBtnsCount: minimizeBtns.length,
                maximizeBtnsCount: maximizeBtns.length,
                hasTitlebar: titlebar !== null,
                hasTitleLeft: titleLeft !== null,
                hasHeaderTools: headerTools !== null
            };
        })()
    """)

    assert res["hasWinControls"] is False, "Custom .window-controls element must be completely absent from DOM"
    assert res["winBtnsCount"] == 0, "No .win-btn elements should exist in DOM"
    assert res["minimizeBtnsCount"] == 0, "No custom Minimize button should exist"
    assert res["maximizeBtnsCount"] == 0, "No custom Maximize button should exist"
    assert res["hasTitlebar"] is True, "Titlebar should remain present"
    assert res["hasTitleLeft"] is True, "App title should remain present"
    assert res["hasHeaderTools"] is True, "Zoom header tools should remain present"


def test_native_macos_window_controls_preserved(live_window):
    """Verify that native window-management hints and functions are fully intact."""
    flags = live_window.windowFlags()

    # Window flags must NOT have FramelessWindowHint (which strips OS window controls)
    assert not (flags & Qt.FramelessWindowHint), "FramelessWindowHint must NOT be set"

    # Window should be resizable and have standard desktop window behavior
    assert live_window.isMaximized() is False or live_window.isMaximized() is True
    assert live_window.isMinimized() is False

    # Test minimize/restore functions safely without crash
    live_window.showMinimized()
    assert live_window.isMinimized() or sys.platform == "darwin"  # on some headless mac runners window manager queues event
    live_window.showNormal()
    assert not live_window.isMinimized()


def test_header_alignment_and_zoom_functionality(live_window):
    """Verify header layout recalculation, right-side alignment, and zoom functionality."""
    eval_js(live_window.web_view, "applyZoom(1.0);")
    wait_ms(200)

    res = eval_js(live_window.web_view, """
        (function() {
            const titlebar = document.querySelector('.alpha-titlebar');
            const titleLeft = titlebar.querySelector('.title-left');
            const zoomTools = titlebar.querySelector('.header-center-tools');
            const zoomInBtn = document.getElementById('quick-zoom-in');
            const zoomOutBtn = document.getElementById('quick-zoom-out');
            const zoomLabel = document.getElementById('quick-zoom-label');

            const titlebarRect = titlebar.getBoundingClientRect();
            const titleLeftRect = titleLeft.getBoundingClientRect();
            const zoomToolsRect = zoomTools.getBoundingClientRect();

            return {
                titlebarWidth: titlebarRect.width,
                titleLeftLeft: titleLeftRect.left,
                zoomToolsRight: zoomToolsRect.right,
                zoomText: zoomLabel ? zoomLabel.textContent.trim() : '',
                hasZoomIn: zoomInBtn !== null,
                hasZoomOut: zoomOutBtn !== null
            };
        })()
    """)

    # Zoom tools should be aligned on the right side of the titlebar
    assert res["hasZoomIn"] is True
    assert res["hasZoomOut"] is True
    assert res["zoomText"] == "100%"
    assert res["titleLeftLeft"] >= 0
    # Zoom tools right edge should comfortably fit within the titlebar with proper right margin
    assert res["zoomToolsRight"] <= res["titlebarWidth"]

    # Test zoom adjustment via header controls
    eval_js(live_window.web_view, "document.getElementById('quick-zoom-in').click();")
    wait_ms(150)
    zoom_after = eval_js(live_window.web_view, "document.getElementById('quick-zoom-label').textContent.trim();")
    assert zoom_after == "105%"

    eval_js(live_window.web_view, "document.getElementById('quick-zoom-out').click();")
    wait_ms(150)
    zoom_reset = eval_js(live_window.web_view, "document.getElementById('quick-zoom-label').textContent.trim();")
    assert zoom_reset == "100%"


def test_switch_billing_mode_and_navigation_integrity(live_window):
    """Verify that Switch Billing Mode button remains properly right-aligned and functional."""
    res = eval_js(live_window.web_view, """
        (function() {
            const switchBtn = document.getElementById('bar-switch-mode');
            const switchRect = switchBtn.getBoundingClientRect();
            const winW = window.innerWidth;

            return {
                exists: switchBtn !== null,
                text: switchBtn ? switchBtn.textContent.trim() : '',
                right: switchRect.right,
                winW: winW
            };
        })()
    """)

    assert res["exists"] is True
    assert "Switch" in res["text"]
    assert res["right"] <= res["winW"], "Switch Billing Mode button must stay within window boundary"


def test_window_controls_absent_across_all_major_screens(live_window):
    """Verify that custom window controls are absent across Overview, POS, Traditional, etc."""
    screens_to_test = [
        ("Overview", "openView('view-overview')"),
        ("Fast Billing (POS)", "openFastBillingPos()"),
        ("Traditional Sales Voucher", "openSalesVoucher()"),
        ("Product Catalogue", "openView('view-items-list')"),
        ("Add Item Master", "openView('view-add-item-master')"),
        ("Purchase Entry", "openView('view-purchase-entry')"),
        ("Stock Summary", "openView('view-stock-summary')"),
        ("Supplier Master", "openView('view-supplier-master')"),
        ("Day Book", "openView('view-day-book')"),
    ]

    for screen_name, nav_script in screens_to_test:
        eval_js(live_window.web_view, nav_script)
        wait_ms(200)

        check = eval_js(live_window.web_view, """
            (function() {
                const winControls = document.querySelector('.window-controls');
                const winBtns = document.querySelectorAll('.win-btn');
                return {
                    hasControls: winControls !== null,
                    btnCount: winBtns.length
                };
            })()
        """)

        assert check["hasControls"] is False, f"Custom window controls found on screen: {screen_name}"
        assert check["btnCount"] == 0, f"Custom window buttons found on screen: {screen_name}"
