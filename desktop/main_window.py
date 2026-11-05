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

from PyQt5.QtCore import QUrl, Qt
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} — {config.APP_DISPLAY_NAME} v{config.VERSION}")
        self.setMinimumSize(1024, 720)
        self.resize(1280, 800)

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

    def closeEvent(self, event):
        """Controlled application shutdown."""
        logger.info("Application shutting down cleanly.")
        try:
            from services.mobile_scanner_service import mobile_scanner_service
            mobile_scanner_service.stop_server()
        except Exception as e:
            logger.warning(f"Error shutting down mobile scanner service: {e}")
        event.accept()
