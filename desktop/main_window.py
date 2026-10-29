"""
Main Application Window for Anti Matrix Billing ERP.
Hosts Qt WebEngine with the custom ERP interface and secures the QWebChannel bridge.
"""
import sys
from pathlib import Path
from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel

from desktop.web_bridge import BackendBridge
from core.configuration import config
from core.logging_config import logger


class CustomWebPage(QWebEnginePage):
    """Custom page to intercept console logs for auditing."""
    def javaScriptConsoleMessage(self, level, message, line, source_id):
        # Forward frontend errors to python logger
        if level == QWebEnginePage.ErrorMessageLevel:
            logger.warning(f"[Frontend JS Error L{line}]: {message}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} — {config.APP_DISPLAY_NAME} v{config.VERSION}")
        self.setMinimumSize(1024, 720)
        self.resize(1280, 800)

        # Initialize WebEngine View and Custom Page
        self.web_view = QWebEngineView(self)
        self.web_page = CustomWebPage(self.web_view)
        self.web_view.setPage(self.web_page)
        self.setCentralWidget(self.web_view)

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

    def closeEvent(self, event):
        """Controlled application shutdown."""
        logger.info("Application shutting down cleanly.")
        event.accept()

