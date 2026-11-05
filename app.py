#!/usr/bin/env python3
"""
Anti Matrix Commercial Billing & POS System
Entry Point for Desktop ERP Application.
"""
import sys
import os
from pathlib import Path

# Auto-delegate to local project virtual environment if run via system python
_project_dir = Path(__file__).resolve().parent
_venv_python = _project_dir / ".venv" / "bin" / "python"
if _venv_python.exists() and sys.executable != str(_venv_python):
    try:
        import PyQt5
    except ImportError:
        os.execv(str(_venv_python), [str(_venv_python)] + sys.argv)

# Set Chromium command-line flags BEFORE PyQt5/QWebEngine initialization.
# On Windows, --no-sandbox is required to prevent QtWebEngineProcess renderer crash (STATUS_BREAKPOINT -2147483645).
existing_flags = os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '')
if '--no-sandbox' not in existing_flags:
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = f'{existing_flags} --no-sandbox --disable-logging'.strip()

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from core.configuration import config
from core.logging_config import logger
from db.database import db_manager
from services.migration_service import migration_service
from desktop.main_window import MainWindow


def main():
    logger.info(f"Starting {config.APP_DISPLAY_NAME} v{config.VERSION}...")

    # Enable High DPI display scaling for modern 4K/Retina screens
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationName(config.VENDOR_NAME)

    # 1. Initialize and run database migrations
    try:
        applied = db_manager.run_migrations()
        if applied:
            logger.info(f"Database migrations applied: {applied}")
        
        # Verify default company exists
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM companies;")
            count = cursor.fetchone()[0]
            if count == 0:
                logger.info("Initializing fresh database with default company...")
                migration_service.import_localstorage_payload({})
    except Exception as e:
        logger.error(f"Database initialization failure: {e}")
        sys.exit(1)

    # 2. Launch Main Desktop Window
    try:
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        logger.critical(f"Unhandled desktop error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

