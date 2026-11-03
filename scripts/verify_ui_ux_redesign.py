#!/usr/bin/env python3
"""
Comprehensive UI Verification Script for ANTI MATRIX — ALPHA BILLING SOFTWARE
UI/UX Identity Redesign:
- Removal of duplicate window controls
- Modern brand topbar
- 8-Section Primary Navigation Sidebar
- Operations Home Workspace with live metrics, quick actions, recent sales & purchases
"""
import sys
import os
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from PyQt5.QtCore import Qt, QUrl, QTimer, QEventLoop
from PyQt5.QtWidgets import QApplication

from core.configuration import config
from core.logging_config import logger
from desktop.main_window import MainWindow

SCREENSHOT_DIR = Path("/Users/dhvira/.gemini/antigravity/brain/09ba5738-f0ba-4bec-b71a-8b9e46f5c762/ui_ux_redesign")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def run_js(web_page, script):
    """Synchronously evaluate javascript and return the result."""
    loop = QEventLoop()
    res = {"val": None}

    def callback(val):
        res["val"] = val
        loop.quit()
    web_page.runJavaScript(script, callback)
    loop.exec_()
    return res["val"]


def wait_ms(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec_()


def capture_screenshot(window, file_name, width, height):
    window.resize(width, height)
    wait_ms(500)
    out_path = SCREENSHOT_DIR / file_name
    pix = window.grab()
    pix.save(str(out_path), "PNG")
    logger.info(f"Captured screenshot {out_path} ({width}x{height})")
    return out_path


def main():
    logger.info("Starting UI/UX Identity Redesign Verification...")
    app = QApplication.instance() or QApplication(sys.argv)

    window = MainWindow()
    window.show()

    # Wait for web page to finish loading
    load_loop = QEventLoop()
    window.web_view.loadFinished.connect(lambda ok: load_loop.quit())
    load_loop.exec_()
    wait_ms(1200)

    web_page = window.web_page

    # Log in and select company to initialize activeCompany
    init_res = run_js(web_page, """
        (function() {
            sessionLowStockDismissed = true;
            if (typeof companies !== 'undefined' && companies.length > 0) {
                activeCompany = companies[0];
            }
            if (typeof enterCompanyDashboard === 'function' && activeCompany) {
                enterCompanyDashboard(activeCompany);
            }
            if (typeof closeLowStockAlertModal === 'function') {
                closeLowStockAlertModal(false);
            }
            return {
                hasActiveCompany: !!activeCompany,
                companyName: activeCompany ? activeCompany.name : null,
                currentScreen: typeof currentScreen !== 'undefined' ? currentScreen : null
            };
        })();
    """)
    logger.info(f"Initialized company dashboard: {init_res}")
    wait_ms(800)

    # -------------------------------------------------------------
    # 1. Capture Dashboard Workspace Across Resolutions
    # -------------------------------------------------------------
    logger.info("Capturing Home Workspace at 1366x768...")
    capture_screenshot(window, "home_workspace_1366x768.png", 1366, 768)

    logger.info("Capturing Home Workspace at 1536x864...")
    capture_screenshot(window, "home_workspace_1536x864.png", 1536, 864)

    logger.info("Capturing Home Workspace at 1920x1080...")
    capture_screenshot(window, "home_workspace_1920x1080.png", 1920, 1080)

    # -------------------------------------------------------------
    # 2. Fast Billing POS
    # -------------------------------------------------------------
    logger.info("Switching to Fast Billing POS...")
    run_js(web_page, """
        (function() {
            if (typeof openFastBillingPos === 'function') {
                openFastBillingPos();
            } else {
                showScreen('view-fast-billing');
            }
        })();
    """)
    wait_ms(600)
    logger.info("Capturing Fast Billing POS at 1366x768...")
    capture_screenshot(window, "fast_billing_pos_1366x768.png", 1366, 768)

    # -------------------------------------------------------------
    # 3. Traditional Sales Voucher
    # -------------------------------------------------------------
    logger.info("Switching to Traditional Sales Voucher...")
    run_js(web_page, """
        (function() {
            showScreen('view-sales-voucher');
            if (typeof initSalesVoucherScreen === 'function') {
                initSalesVoucherScreen();
            }
        })();
    """)
    wait_ms(600)
    logger.info("Capturing Traditional Sales Voucher at 1366x768...")
    capture_screenshot(window, "traditional_sales_1366x768.png", 1366, 768)

    # -------------------------------------------------------------
    # 4. Stock Summary
    # -------------------------------------------------------------
    logger.info("Switching to Stock Summary...")
    run_js(web_page, """
        (function() {
            showScreen('view-stock-summary');
            if (typeof renderStockSummary === 'function') {
                renderStockSummary();
            }
        })();
    """)
    wait_ms(600)
    logger.info("Capturing Stock Summary at 1366x768...")
    capture_screenshot(window, "stock_summary_1366x768.png", 1366, 768)

    logger.info("UI Verification completed successfully!")
    window.close()


if __name__ == "__main__":
    main()
