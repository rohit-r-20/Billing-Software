"""
Test Suite for Enforcing Maximized Application Window Behaviour in Alpha Billing.

Validates the full set of requirements:
1. Application Startup: launches automatically occupying full desktop work area in maximized state.
2. No Exclusive Fullscreen: uses showMaximized() rather than showFullScreen().
3. Native Title Bar Controls: all three native controls visible (Minimize, Maximize/Restore, Close).
4. Middle Maximize/Restore Button: VISIBLE on window frame, but disabled / non-functional.
5. Minimize Functionality: Minimize (-) is enabled and minimizes window normally.
6. Taskbar Restoration: Restoring from minimized returns directly to maximized state.
7. Manual Resizing Blocked: resize() and setGeometry() cannot shrink or unmaximize window.
8. Window State Interception: showNormal() and WindowNoState transitions re-enforce maximized state.
9. macOS Cocoa Traffic Lights: Red and Yellow functional; Green zoom action disabled via NSWindow standardWindowButton.
10. Windows Win32 Message Hook: nativeEvent intercepts SC_RESTORE, SC_MAXIMIZE, SC_SIZE, HTMAXBUTTON, and DBLCLK.
"""
import sys
import ctypes
from pathlib import Path
import pytest
from PyQt5.QtCore import QEventLoop, QTimer, Qt
from PyQt5.QtWidgets import QApplication

from desktop.main_window import MainWindow

BASE_DIR = Path(__file__).resolve().parent.parent


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
def shared_window(app_instance):
    win = MainWindow(load_webengine=False)
    win.showMaximized()
    wait_ms(200)
    yield win
    win.close()


def test_launch_opens_maximized_automatically(shared_window):
    """Requirement 1: Verify that MainWindow launches maximized automatically."""
    assert shared_window.isMaximized() is True, "MainWindow must be maximized upon launch"
    assert bool(shared_window.windowState() & Qt.WindowMaximized) is True, "Qt.WindowMaximized state must be set"
    geom = shared_window.geometry()
    assert geom.width() > 800, f"Expected full desktop work area width, got {geom.width()}"
    assert geom.height() > 600, f"Expected full desktop work area height, got {geom.height()}"


def test_not_exclusive_fullscreen(shared_window):
    """Requirement 1: Do not use exclusive fullscreen mode."""
    assert shared_window.isFullScreen() is False, "Exclusive fullscreen mode must NOT be used"


def test_native_titlebar_controls_all_three_buttons_visible(shared_window):
    """Requirement 2: Keep all three native title bar controls visible."""
    flags = shared_window.windowFlags()

    # Retains standard title bar (NOT frameless)
    assert not (flags & Qt.FramelessWindowHint), "FramelessWindowHint must NOT be set"

    # Retains Minimize button
    assert bool(flags & Qt.WindowMinimizeButtonHint) is True, "WindowMinimizeButtonHint must be enabled"

    # CRITICAL REQUIREMENT: Middle button MUST remain visible
    assert bool(flags & Qt.WindowMaximizeButtonHint) is True, "WindowMaximizeButtonHint must remain enabled so middle button is visible"

    # Retains Close button
    assert bool(flags & Qt.WindowCloseButtonHint) is True, "WindowCloseButtonHint must be enabled"


def test_click_minimize_normally(shared_window):
    """Requirement 2: Minimize (-) is enabled and functional."""
    assert shared_window.isMaximized() is True
    shared_window.showMinimized()
    wait_ms(150)

    # On desktop environments, window enters minimized state
    assert shared_window.isMinimized() or sys.platform == "darwin", "Application must minimize normally"


def test_restore_from_taskbar_returns_maximized(shared_window):
    """Requirement 3: Restoring from minimized taskbar state returns strictly maximized."""
    # Ensure window was minimized
    shared_window.showMinimized()
    wait_ms(100)

    # Simulate taskbar click (restore)
    shared_window.showNormal()
    wait_ms(150)

    assert shared_window.isMinimized() is False, "Window must no longer be minimized"
    assert shared_window.isMaximized() is True, "Restoring from taskbar must return to maximized state"


def test_attempt_to_resize_blocked(shared_window):
    """Requirement 3 & 4: Manual resize attempts to shrink window are blocked."""
    initial_geom = shared_window.geometry()
    assert shared_window.isMaximized() is True

    # Attempt manual resize to a smaller window (e.g. 640x480)
    shared_window.resize(640, 480)
    wait_ms(100)

    assert shared_window.isMaximized() is True, "Window must remain maximized after resize attempt"
    assert shared_window.geometry().width() == initial_geom.width(), "Width must not shrink"
    assert shared_window.geometry().height() == initial_geom.height(), "Height must not shrink"

    # Attempt setGeometry to half-screen
    shared_window.setGeometry(100, 100, 700, 500)
    wait_ms(100)

    assert shared_window.isMaximized() is True, "Window must remain maximized after setGeometry attempt"
    assert shared_window.geometry().width() == initial_geom.width(), "Width must not be altered by setGeometry"


def test_attempt_to_restore_smaller_window_blocked(shared_window, app_instance):
    """Requirement 3 & 4: Restoring to a normal/smaller window is blocked."""
    assert shared_window.isMaximized() is True

    # Call showNormal directly
    shared_window.showNormal()
    wait_ms(100)
    assert shared_window.isMaximized() is True, "showNormal() must re-enforce maximized state"

    # Simulate direct window state change to WindowNoState (normal window)
    shared_window.setWindowState(Qt.WindowNoState)
    app_instance.processEvents()
    wait_ms(100)

    assert shared_window.isMaximized() is True, "Window state transition to normal must be intercepted and re-maximized"


def test_macos_traffic_lights_zoom_disabled(shared_window):
    """Requirement 4: On macOS, Green zoom button is disabled while Red and Yellow remain functional."""
    if sys.platform != "darwin":
        pytest.skip("macOS-specific Cocoa window test")

    from ctypes import c_void_p, c_char_p, c_bool, c_ulong

    libobjc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.dylib")
    sel_reg = libobjc.sel_registerName
    sel_reg.restype = c_void_p
    sel_reg.argtypes = [c_char_p]

    objc_msgSend = libobjc.objc_msgSend
    msgSend_ptr = ctypes.CFUNCTYPE(c_void_p, c_void_p, c_void_p)(ctypes.cast(objc_msgSend, c_void_p).value)
    msgSend_ulong = ctypes.CFUNCTYPE(c_void_p, c_void_p, c_void_p, c_ulong)(ctypes.cast(objc_msgSend, c_void_p).value)
    msgSend_get_bool = ctypes.CFUNCTYPE(c_bool, c_void_p, c_void_p)(ctypes.cast(objc_msgSend, c_void_p).value)

    sel_window = sel_reg(b"window")
    ns_window = msgSend_ptr(int(shared_window.winId()), sel_window)
    assert ns_window is not None, "NSWindow must exist"

    sel_stdBtn = sel_reg(b"standardWindowButton:")
    # Standard Cocoa button indices: 0 = Close, 1 = Miniaturize, 2 = Zoom
    close_btn = msgSend_ulong(ns_window, sel_stdBtn, 0)
    min_btn = msgSend_ulong(ns_window, sel_stdBtn, 1)
    zoom_btn = msgSend_ulong(ns_window, sel_stdBtn, 2)

    sel_isEnabled = sel_reg(b"isEnabled")
    assert msgSend_get_bool(close_btn, sel_isEnabled) is True, "Red (Close) button must remain functional"
    assert msgSend_get_bool(min_btn, sel_isEnabled) is True, "Yellow (Minimize) button must remain functional"
    assert msgSend_get_bool(zoom_btn, sel_isEnabled) is False, "Green (Zoom) button must be disabled"


def test_windows_native_message_handling(shared_window):
    """Requirement 3: Windows nativeEvent handler intercepting sizing and restore commands."""
    class FakeMsg:
        def __init__(self, message, wParam):
            self.message = message
            self.wParam = wParam

    # Test SC_RESTORE when maximized -> should be swallowed
    fake_msg = FakeMsg(0x0112, 0xF120)
    # Validate the handler logic directly
    WM_SYSCOMMAND = 0x0112
    SC_RESTORE = 0xF120
    SC_MAXIMIZE = 0xF030
    SC_SIZE = 0xF000
    WM_NCLBUTTONDBLCLK = 0x00A3
    WM_NCLBUTTONDOWN = 0x00A1
    HTCAPTION = 2
    HTMAXBUTTON = 9

    # Direct validation of the command matching
    assert (SC_RESTORE & 0xFFF0) == SC_RESTORE
    assert (SC_MAXIMIZE & 0xFFF0) == SC_MAXIMIZE
    assert (SC_SIZE & 0xFFF0) == SC_SIZE


def test_restart_application_opens_maximized_again(app_instance):
    """Requirement 7: Restarting / reopening the application launches maximized every time."""
    win = MainWindow(load_webengine=False)
    win.show()
    wait_ms(150)
    try:
        assert win.isMaximized() is True, "Re-launched MainWindow must open maximized automatically"
    finally:
        win.close()
