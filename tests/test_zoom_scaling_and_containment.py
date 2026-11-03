"""
Test Suite for Zoom Scaling and Viewport Containment Fix
Verifies:
- Zoom levels: 80%, 90%, 100%, 110%, 120%, 130%
- Viewport containment of Header, Switch Billing Mode, Main Workspace, and Footer
- Window resizing with active zoom
- Layout preservation without clipping
"""
import sys
from pathlib import Path
import pytest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QEventLoop, QTimer

INDEX_HTML_PATH = Path(__file__).resolve().parent.parent / "index.html"
STYLES_CSS_PATH = Path(__file__).resolve().parent.parent / "styles.css"
APP_JS_PATH = Path(__file__).resolve().parent.parent / "app.js"


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


def test_css_zoom_containment_rules():
    """Verify CSS rules for desktop container containment and modal sizing."""
    css_content = STYLES_CSS_PATH.read_text(encoding="utf-8")
    assert "calc(100vw / var(--ui-scale))" in css_content
    assert "calc(100vh / var(--ui-scale))" in css_content
    assert ".modal-overlay {" in css_content
    assert "width: 100%;" in css_content or "calc(100vw" in css_content


def test_app_js_zoom_engine():
    """Verify app.js calculates dynamic width and height on zoom and window resize."""
  
    js_content = APP_JS_PATH.read_text(encoding="utf-8")
    assert "function applyZoom" in js_content
    assert "calc(100vw /" in js_content
    assert "calc(100vh /" in js_content
    assert "window.addEventListener(\"resize\"" in js_content


@pytest.mark.parametrize("zoom_level", [0.80, 0.90, 1.00, 1.10, 1.20, 1.30])
def test_dashboard_viewport_containment_across_zoom_levels(web_view, zoom_level):
    """Verify that all major layout regions remain fully contained inside the window at various zoom levels."""
    # Ensure company dashboard is active
    eval_js(web_view, """
        if (typeof companies !== 'undefined' && companies.length > 0) {
            activeCompany = companies[0];
            sessionLowStockDismissed = true;
            enterCompanyDashboard(companies[0]);
            if (typeof closeLowStockAlertModal === 'function') closeLowStockAlertModal(false);
        }
    """)

    # Apply tested zoom
    eval_js(web_view, f"applyZoom({zoom_level});")
    loop = QEventLoop()
    QTimer.singleShot(300, loop.quit)
    loop.exec_()

    measurements = eval_js(web_view, """
        (function() {
            const root = document.getElementById('app-root');
            const switchBtn = document.getElementById('bar-switch-mode');
            const statusbar = document.getElementById('erp-statusbar');
            const winControls = document.querySelector('.window-controls');
            const zoomLabel = document.getElementById('quick-zoom-label');

            const winW = window.innerWidth;
            const winH = window.innerHeight;

            // Rendered pixel bounds accounting for zoom
            const scale = typeof uiZoom !== 'undefined' ? uiZoom : 1.0;
            const rootRect = root.getBoundingClientRect();
            const switchRect = switchBtn ? switchBtn.getBoundingClientRect() : null;
            const statusRect = statusbar ? statusbar.getBoundingClientRect() : null;
            const winControlsRect = winControls ? winControls.getBoundingClientRect() : null;

            return {
                winW: winW,
                winH: winH,
                scale: scale,
                zoomLabelText: zoomLabel ? zoomLabel.textContent.trim() : '',
                rootRenderedWidth: Math.round(rootRect.width * scale),
                rootRenderedHeight: Math.round(rootRect.height * scale),
                switchRightRendered: switchRect ? Math.round(switchRect.right * scale) : 0,
                statusBottomRendered: statusRect ? Math.round(statusRect.bottom * scale) : 0,
                statusTopRendered: statusRect ? Math.round(statusRect.top * scale) : 0,
                winControlsRightRendered: winControlsRect ? Math.round(winControlsRect.right * scale) : 0
            };
        })()
    """)

    assert measurements is not None
    win_w = measurements["winW"]
    win_h = measurements["winH"]

    # 1. Desktop container rendered size matches window viewport within 2px tolerance
    assert abs(measurements["rootRenderedWidth"] - win_w) <= 2
    assert abs(measurements["rootRenderedHeight"] - win_h) <= 2

    # 2. Switch Billing Mode button must be within the application's right boundary
    assert measurements["switchRightRendered"] <= win_w + 1

    # 3. Window controls must remain within the right boundary
    if measurements["winControlsRightRendered"] > 0:
        assert measurements["winControlsRightRendered"] <= win_w + 1

    # 4. Status bar footer must not be pushed below the application window
    assert measurements["statusBottomRendered"] <= win_h + 2
    assert measurements["statusTopRendered"] < win_h

    # 5. Zoom label matches expected percentage
    expected_pct = f"{int(round(zoom_level * 100))}%"
    assert measurements["zoomLabelText"] == expected_pct


def test_window_resizing_with_active_zoom(web_view):
    """Verify that resizing the native application window maintains full containment when zoomed."""
    eval_js(web_view, """
        if (typeof companies !== 'undefined' && companies.length > 0) {
            activeCompany = companies[0];
            sessionLowStockDismissed = true;
            enterCompanyDashboard(companies[0]);
        }
        applyZoom(1.20);
    """)

    for width, height in [(1024, 720), (1366, 768), (1536, 864), (1920, 1080)]:
        web_view.resize(width, height)
        loop = QEventLoop()
        QTimer.singleShot(300, loop.quit)
        loop.exec_()

        res = eval_js(web_view, """
            (function() {
                const root = document.getElementById('app-root');
                const switchBtn = document.getElementById('bar-switch-mode');
                const statusbar = document.getElementById('erp-statusbar');
                const scale = typeof uiZoom !== 'undefined' ? uiZoom : 1.2;
                return {
                    winW: window.innerWidth,
                    winH: window.innerHeight,
                    rootWidth: Math.round(root.getBoundingClientRect().width * scale),
                    rootHeight: Math.round(root.getBoundingClientRect().height * scale),
                    switchRight: switchBtn ? Math.round(switchBtn.getBoundingClientRect().right * scale) : 0,
                    statusBottom: statusbar ? Math.round(statusbar.getBoundingClientRect().bottom * scale) : 0
                };
            })()
        """)

        assert res["switchRight"] <= res["winW"] + 1
        assert res["statusBottom"] <= res["winH"] + 2
        assert abs(res["rootWidth"] - res["winW"]) <= 2
        assert abs(res["rootHeight"] - res["winH"]) <= 2


def test_fast_billing_and_traditional_billing_containment(web_view):
    """Verify that Fast Billing POS and Traditional Billing remain fully contained at 120% zoom."""
    eval_js(web_view, """
        if (typeof companies !== 'undefined' && companies.length > 0) {
            activeCompany = companies[0];
            sessionLowStockDismissed = true;
            enterCompanyDashboard(companies[0]);
        }
        applyZoom(1.20);
    """)

    # Fast Billing POS
    eval_js(web_view, "openFastBillingPos();")
    loop = QEventLoop()
    QTimer.singleShot(300, loop.quit)
    loop.exec_()

    pos_check = eval_js(web_view, """
        (function() {
            const posRibbon = document.querySelector('.pos-ribbon');
            const posFooter = document.querySelector('.pos-hotkeys-bar');
            const scale = typeof uiZoom !== 'undefined' ? uiZoom : 1.2;
            const winW = window.innerWidth;
            const winH = window.innerHeight;
            return {
                ribbonRight: posRibbon ? Math.round(posRibbon.getBoundingClientRect().right * scale) : 0,
                footerBottom: posFooter ? Math.round(posFooter.getBoundingClientRect().bottom * scale) : 0,
                winW: winW,
                winH: winH
            };
        })()
    """)
    assert pos_check["ribbonRight"] <= pos_check["winW"] + 2
    assert pos_check["footerBottom"] <= pos_check["winH"] + 2

    # Traditional Billing
    eval_js(web_view, "showScreen('view-sales-voucher');")
    loop = QEventLoop()
    QTimer.singleShot(300, loop.quit)
    loop.exec_()

    trad_check = eval_js(web_view, """
        (function() {
            const ribbon = document.querySelector('.form-screen-ribbon');
            const footer = document.querySelector('.vch-bottom-hotkeys');
            const scale = typeof uiZoom !== 'undefined' ? uiZoom : 1.2;
            const winW = window.innerWidth;
            const winH = window.innerHeight;
            return {
                ribbonRight: ribbon ? Math.round(ribbon.getBoundingClientRect().right * scale) : 0,
                footerBottom: footer ? Math.round(footer.getBoundingClientRect().bottom * scale) : 0,
                winW: winW,
                winH: winH
            };
        })()
    """)
    assert trad_check["ribbonRight"] <= trad_check["winW"] + 2
    assert trad_check["footerBottom"] <= trad_check["winH"] + 2
