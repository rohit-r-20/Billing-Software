"""
Main Application Window for Alpha Billing ERP.
Hosts Qt WebEngine with the custom ERP interface and secures the QWebChannel bridge.
"""
import sys
import os
from pathlib import Path

# Ensure Chromium flags are active even if MainWindow is imported directly
existing_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
if "--no-sandbox" not in existing_flags:
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{existing_flags} --no-sandbox --disable-logging".strip()

from PyQt5.QtCore import QUrl, Qt, QEvent, QTimer
from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEnginePage, QWebEngineSettings
from PyQt5.QtWebChannel import QWebChannel

from desktop.web_bridge import BackendBridge
from core.configuration import config
from core.logging_config import logger


class CustomWebPage(QWebEnginePage):
    """Custom page to intercept console logs for auditing and debugging."""
    def javaScriptConsoleMessage(self, level, message, line, source_id):
        # Forward frontend errors to python logger
        if level == QWebEnginePage.ErrorMessageLevel:
            logger.warning(f"[Frontend JS Error L{line}]: {message}")
        else:
            logger.debug(f"[Frontend JS L{line}]: {message}")


class MainWindow(QMainWindow):
    def __init__(self, load_webengine: bool = True):
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} — {config.APP_DISPLAY_NAME} v{config.VERSION}")

        # Configure window flags: retain full native title bar with all three buttons visible
        # (Minimize, Maximize/Restore, Close). Maximize/Restore is kept VISIBLE per critical requirements,
        # but rendered non-functional/disabled natively and through Qt state interceptors.
        flags = (
            Qt.Window
            | Qt.WindowTitleHint
            | Qt.WindowSystemMenuHint
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )
        self.setWindowFlags(flags)

        # Enforce initial window state to Maximized on startup
        self.setWindowState(Qt.WindowMaximized)
        self._enforce_maximized = True

        self.web_view = None
        self.web_page = None

        if load_webengine:
            # Initialize WebEngine View and Custom Page
            self.web_view = QWebEngineView(self)
            self.web_page = CustomWebPage(self.web_view)

            # Configure WebEngine Settings for local enterprise application
            settings = self.web_page.settings()
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.ScrollAnimatorEnabled, True)

            self.web_view.setPage(self.web_page)
            self.setCentralWidget(self.web_view)

            # Connect lifecycle monitoring signals
            self.web_page.renderProcessTerminated.connect(self._on_render_process_terminated)
            self.web_view.loadFinished.connect(self._on_load_finished)

            # Setup QWebChannel for safe bidirectional JavaScript-to-Python communication
            self.channel = QWebChannel(self)
            self.bridge = BackendBridge(self)
            self.channel.registerObject("backend", self.bridge)
            self.web_page.setWebChannel(self.channel)

            # Load existing HTML interface
            index_file = config.BASE_DIR / "index.html"
            if not index_file.exists():
                raise FileNotFoundError(f"Missing UI entrypoint: {index_file}")

            file_url = QUrl.fromLocalFile(str(index_file.resolve()))
            self.web_view.load(file_url)
            logger.info(f"Loaded user interface from {file_url.toString()}")

    def _on_render_process_terminated(self, termination_status, exit_code):
        logger.critical(
            f"QtWebEngine render process terminated unexpectedly! "
            f"Status: {termination_status}, Exit Code: {exit_code}"
        )

    def _on_load_finished(self, success):
        if success:
            logger.info("Alpha Billing user interface loaded successfully.")
        else:
            logger.error("Failed to load user interface entrypoint into QWebEngineView.")

    def show(self):
        """Enforce maximized launch even if show() is called instead of showMaximized()."""
        self.showMaximized()

    def showNormal(self):
        """Prevent restoring to normal or smaller window; re-enforce maximized desktop state."""
        self.showMaximized()

    def _disable_native_maximize_button(self):
        """Disables native maximize/zoom button functionality while keeping it visible on the window frame."""
        if sys.platform == "darwin":
            try:
                import ctypes
                from ctypes import c_void_p, c_char_p, c_bool, c_ulong

                libobjc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.dylib")
                sel_registerName = libobjc.sel_registerName
                sel_registerName.restype = c_void_p
                sel_registerName.argtypes = [c_char_p]

                objc_msgSend = libobjc.objc_msgSend
                msgSend_ptr = ctypes.CFUNCTYPE(c_void_p, c_void_p, c_void_p)(ctypes.cast(objc_msgSend, c_void_p).value)
                msgSend_ulong = ctypes.CFUNCTYPE(c_void_p, c_void_p, c_void_p, c_ulong)(ctypes.cast(objc_msgSend, c_void_p).value)
                msgSend_bool = ctypes.CFUNCTYPE(None, c_void_p, c_void_p, c_bool)(ctypes.cast(objc_msgSend, c_void_p).value)

                view_id = int(self.winId())
                sel_window = sel_registerName(b"window")
                ns_window = msgSend_ptr(view_id, sel_window)
                if ns_window:
                    sel_stdBtn = sel_registerName(b"standardWindowButton:")
                    # 2 = NSWindowZoomButton (Green traffic light)
                    zoom_btn = msgSend_ulong(ns_window, sel_stdBtn, 2)
                    if zoom_btn:
                        sel_setEnabled = sel_registerName(b"setEnabled:")
                        msgSend_bool(zoom_btn, sel_setEnabled, False)
                        logger.debug("macOS Cocoa NSWindowZoomButton successfully disabled.")
            except Exception as e:
                logger.debug(f"macOS zoom button configuration note: {e}")

        elif sys.platform == "win32":
            try:
                import ctypes
                hwnd = int(self.winId())
                user32 = ctypes.windll.user32
                hmenu = user32.GetSystemMenu(hwnd, False)
                if hmenu:
                    MF_BYCOMMAND = 0x00000000
                    MF_GRAYED = 0x00000001
                    MF_DISABLED = 0x00000002
                    SC_MAXIMIZE = 0xF030
                    SC_RESTORE = 0xF120
                    SC_SIZE = 0xF000
                    user32.EnableMenuItem(hmenu, SC_MAXIMIZE, MF_BYCOMMAND | MF_GRAYED | MF_DISABLED)
                    user32.EnableMenuItem(hmenu, SC_RESTORE, MF_BYCOMMAND | MF_GRAYED | MF_DISABLED)
                    user32.EnableMenuItem(hmenu, SC_SIZE, MF_BYCOMMAND | MF_GRAYED | MF_DISABLED)
                    logger.debug("Windows native system menu items disabled (SC_MAXIMIZE, SC_RESTORE, SC_SIZE).")
            except Exception as e:
                logger.debug(f"Windows system menu configuration note: {e}")

    def showEvent(self, event):
        """Ensure the window is always maximized and native zoom/maximize is disabled when shown."""
        super().showEvent(event)
        if not self.isMaximized() and not self.isMinimized():
            self.showMaximized()
        self._disable_native_maximize_button()

    def resize(self, *args):
        """Block external manual resize attempts to prevent shrinking or unmaximizing the window."""
        if getattr(self, "_enforce_maximized", False) and self.isVisible():
            return
        super().resize(*args)

    def setGeometry(self, *args):
        """Block manual geometry changes to maintain the full-screen desktop work area."""
        if getattr(self, "_enforce_maximized", False) and self.isVisible():
            return
        super().setGeometry(*args)

    def changeEvent(self, event):
        """Monitor window state changes and strictly prevent restoring to smaller or half-screen windows."""
        if event.type() == QEvent.WindowStateChange:
            # If the window transitions to a state that is neither Minimized nor Maximized
            # (e.g. via Windows Snap, restore key combination, or OS gesture)
            if not self.isMinimized() and not self.isMaximized():
                logger.debug("Restoration to normal window blocked — re-enforcing maximized workspace.")
                QTimer.singleShot(0, self.showMaximized)
        super().changeEvent(event)

    def nativeEvent(self, eventType, message):
        """Windows native message hook to intercept low-level window sizing, double-click, and restoration."""
        if sys.platform == "win32" and eventType == b"windows_generic_MSG":
            try:
                import ctypes
                from ctypes import wintypes

                msg = wintypes.MSG.from_address(int(message))
                WM_SYSCOMMAND = 0x0112
                SC_RESTORE = 0xF120
                SC_MAXIMIZE = 0xF030
                SC_SIZE = 0xF000
                WM_NCLBUTTONDBLCLK = 0x00A3
                WM_NCLBUTTONDOWN = 0x00A1
                HTCAPTION = 2
                HTMAXBUTTON = 9

                if msg.message == WM_SYSCOMMAND:
                    cmd = msg.wParam & 0xFFF0
                    if cmd == SC_RESTORE:
                        # If minimized, restore back to full maximized state
                        if self.isMinimized():
                            self.showMaximized()
                            return True, 0
                        # If already open/maximized, block un-maximizing to normal window
                        return True, 0
                    elif cmd in (SC_SIZE, SC_MAXIMIZE):
                        # Prevent manual window sizing and unmaximizing
                        return True, 0
                elif msg.message == WM_NCLBUTTONDOWN:
                    if msg.wParam == HTMAXBUTTON:
                        # Swallow click on the native Maximize/Restore button
                        return True, 0
                elif msg.message == WM_NCLBUTTONDBLCLK:
                    if msg.wParam == HTCAPTION:
                        # Prevent double-clicking the title bar from unmaximizing the window
                        return True, 0
            except Exception as e:
                logger.debug(f"nativeEvent exception: {e}")
        return super().nativeEvent(eventType, message)

    def closeEvent(self, event):
        """Controlled application shutdown."""
        logger.info("Application shutting down cleanly.")
        try:
            from services.mobile_scanner_service import mobile_scanner_service
            mobile_scanner_service.stop_server()
        except Exception as e:
            logger.warning(f"Error shutting down mobile scanner service: {e}")
        event.accept()
