#!/usr/bin/env python3
"""
Anti Matrix Commercial Billing & POS System
Entry Point for Desktop ERP Application.
"""
import sys
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

