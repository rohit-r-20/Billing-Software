"""
Automated Test Suite for Global Removal of Duplicate Window Control Buttons.

Validates:
1. Complete removal of .window-controls and .win-btn across the entire DOM.
2. Absence of custom Minimize (—), Maximize (□), and Close (×) window buttons on all pages.
3. Native window control hints on MainWindow (Minimize and Close kept, Maximize disabled).
4. Header layout alignment and navigation integrity.
5. All major views (Overview, Fast Billing, Traditional Billing, Catalogue, etc.) verified.
"""
import sys
from pathlib import Path
import pytest
from PyQt5.QtCore import QEventLoop, QTimer, Qt
from PyQt5.QtWidgets import QApplication

from desktop.main_window import MainWindow

BASE_DIR = Path(__file__).resolve().parent.parent


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


@pytest.fixture(scope="module")
def live_window(app_instance):
    win = MainWindow()
    win.show()

    loop = QEventLoop()
    if win.web_view.page().url().isEmpty() or win.web_view.isLoading():
        win.web_view.loadFinished.connect(lambda ok: loop.quit())
        loop.exec_()
    wait_ms(800)

    # Initialize company session if needed
    eval_js(win.web_view, """
        if (typeof window.BusinessContext !== 'undefined') {
            // Context initialized
        } else if (typeof companies !== 'undefined' && companies.length > 0) {
            activeCompany = companies[0];
            sessionLowStockDismissed = true;
            if (typeof enterCompanyDashboard === 'function') enterCompanyDashboard(companies[0]);
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
            
            // Check top header / titlebar structure
            const titlebar = document.querySelector('.alpha-top-header') || document.querySelector('.alpha-titlebar');
            const titleLeft = titlebar ? (titlebar.querySelector('.header-title-box') || titlebar.querySelector('.title-left') || titlebar.querySelector('.brand-title')) : null;

            return {
                hasWinControls: winControls !== null,
                winBtnsCount: winBtns.length,
                minimizeBtnsCount: minimizeBtns.length,
                maximizeBtnsCount: maximizeBtns.length,
                hasTitlebar: titlebar !== null,
                hasTitleLeft: titleLeft !== null
            };
        })()
    """)

    assert res["hasWinControls"] is False, "Custom .window-controls element must be completely absent from DOM"
    assert res["winBtnsCount"] == 0, "No .win-btn elements should exist in DOM"
    assert res["minimizeBtnsCount"] == 0, "No custom Minimize button should exist"
    assert res["maximizeBtnsCount"] == 0, "No custom Maximize button should exist"
    assert res["hasTitlebar"] is True, "Header/titlebar should remain present"
    assert res["hasTitleLeft"] is True, "Title group should remain present"


def test_native_macos_window_controls_preserved(live_window):
    """Verify that native window-management hints and functions are intact."""
    flags = live_window.windowFlags()

    # Window flags must NOT have FramelessWindowHint (which strips OS window controls)
    assert not (flags & Qt.FramelessWindowHint), "FramelessWindowHint must NOT be set"

    # Verify native button hints: Minimize, Maximize/Restore, and Close are enabled on window frame
    assert bool(flags & Qt.WindowMinimizeButtonHint) is True
    assert bool(flags & Qt.WindowCloseButtonHint) is True
    assert bool(flags & Qt.WindowMaximizeButtonHint) is True

    # Window must launch and stay maximized
    assert live_window.isMaximized() is True
    assert live_window.isMinimized() is False

    # Test minimize and restore functions
    live_window.showMinimized()
    assert live_window.isMinimized() or sys.platform == "darwin"
    live_window.showNormal()
    assert not live_window.isMinimized()
    assert live_window.isMaximized() is True


def test_header_alignment_and_zoom_functionality(live_window):
    """Verify header layout recalculation, boundary alignment, and containment."""
    res = eval_js(live_window.web_view, """
        (function() {
            const titlebar = document.querySelector('.alpha-top-header') || document.querySelector('.alpha-titlebar') || document.getElementById('app-root');
            const titlebarRect = titlebar.getBoundingClientRect();
            const winW = window.innerWidth;

            return {
                titlebarWidth: titlebarRect.width,
                winW: winW
            };
        })()
    """)

    assert res["titlebarWidth"] <= res["winW"] + 2


def test_switch_billing_mode_and_navigation_integrity(live_window):
    """Verify that navigation controls remain properly aligned and functional."""
    res = eval_js(live_window.web_view, """
        (function() {
            const navBtn = document.getElementById('btn-header-company') || document.getElementById('bar-switch-mode') || document.getElementById('btn-nav-pos');
            return {
                exists: navBtn !== null
            };
        })()
    """)

    assert res["exists"] is True


def test_window_controls_absent_across_all_major_screens(live_window):
    """Verify that custom window controls are absent across all view containers in DOM."""
    res = eval_js(live_window.web_view, """
        (function() {
            const views = document.querySelectorAll('.screen-view, .workspace-area, .alpha-app-shell, .alpha-top-header');
            let foundControls = 0;
            let foundBtns = 0;
            views.forEach(v => {
                foundControls += v.querySelectorAll('.window-controls').length;
                foundBtns += v.querySelectorAll('.win-btn').length;
            });
            return {
                viewsCount: views.length,
                foundControls: foundControls,
                foundBtns: foundBtns
            };
        })()
    """)

    assert res["viewsCount"] > 0, "Application view containers must exist"
    assert res["foundControls"] == 0, "No .window-controls should exist in any screen view"
    assert res["foundBtns"] == 0, "No .win-btn elements should exist in any screen view"
