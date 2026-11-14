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
# On Windows, --no-sandbox is required to prevent QtWebEngineProcess renderer crash.
existing_flags = os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '')
if '--no-sandbox' not in existing_flags:
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = f'{existing_flags} --no-sandbox --disable-logging'.strip()

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMessageBox

from core.configuration import config
from core.logging_config import logger
from db.database import db_manager
from desktop.main_window import MainWindow


def main():
    logger.info(f"Starting {config.APP_DISPLAY_NAME} v{config.VERSION} [{config.get_database_env()}]...")

    # Enable High DPI display scaling for modern 4K/Retina screens
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationName(config.VENDOR_NAME)

    # 1. Connection Health Check (Decoupled from DDL migrations)
    health = db_manager.check_health()
    if health.get("healthy"):
        logger.info(
            f"Database connected: {health.get('dialect')} ({health.get('database')}.{health.get('schema')}) "
            f"latency: {health.get('latency_ms')}ms [{health.get('url_masked')}]"
        )
        try:
            from services.company_service import company_service
            admin_info = company_service.provision_initial_administrator()
            if admin_info.get("created"):
                logger.info("Provisioned initial administrator account for primary company.")
        except Exception as e:
            logger.debug(f"Initial administrator provisioning note: {e}")
    else:
        logger.error(f"Database connection error: {health.get('error')}")
        # Note: Do not abort ungracefully; allow UI to present diagnostic connection screen if offline

    # 2. Traditional Billing Database Initialization (Local SQLite only)
    try:
        from db.traditional_database import traditional_db_manager
        if traditional_db_manager.is_sqlite:
            logger.info("Initializing Traditional Billing SQLite database schema via Alembic...")
            traditional_db_manager.run_traditional_migrations()
            logger.info("Traditional Billing SQLite schema up to date.")
        else:
            logger.info("Traditional Billing target is PostgreSQL; automatic migrations deferred.")
    except Exception as e:
        logger.error(f"Traditional Billing initialization error: {e}")

    # 3. Launch Main Desktop Window in Maximized State
    try:
        window = MainWindow()
        window.showMaximized()
        sys.exit(app.exec_())
    except Exception as e:
        logger.critical(f"Unhandled desktop error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
