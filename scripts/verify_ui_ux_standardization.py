#!/usr/bin/env python3
"""
Comprehensive Visual Verification Script for ANTI MATRIX — ALPHA BILLING SOFTWARE
UI/UX Standardization:
- Global emoji removal
- Anti Matrix design system styling
- Operational Dashboard with Left Sidebar (8 sections)
- 4 Live Metric Cards, Quick Actions, and Recent Tables
- Standardized screens for all views and modals
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

SCREENSHOT_DIR = Path("/Users/dhvira/.gemini/antigravity/brain/09ba5738-f0ba-4bec-b71a-8b9e46f5c762/ui_ux_standardization")
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


def capture_screenshot(window, file_name, width=1280, height=800):
    window.resize(width, height)
    wait_ms(400)
    out_path = SCREENSHOT_DIR / file_name
    pix = window.grab()
    pix.save(str(out_path), "PNG")
    logger.info(f"Captured screenshot {out_path} ({width}x{height})")
    return out_path


def main():
    logger.info("Starting UI/UX Standardization Visual Capture...")
    app = QApplication.instance() or QApplication(sys.argv)

    window = MainWindow()
    window.show()

    load_loop = QEventLoop()
    window.web_view.loadFinished.connect(lambda ok: load_loop.quit())
    load_loop.exec_()
    wait_ms(1000)

    page = window.web_view.page()

    # Setup active company and session
    run_js(page, """
        activeCompany = { id: 'COMP0001', name: 'ANTI MATRIX', fin_year: '2026-27' };
        if (typeof companies !== 'undefined' && companies.length > 0) {
            activeCompany = companies[0];
        }
    """)

    # 1. Operational Dashboard Overview (100% zoom)
    run_js(page, "applyZoom(1.0); showScreen('view-dashboard'); renderOperationalDashboard();")
    wait_ms(400)
    capture_screenshot(window, "01_dashboard_operational_overview.png")

    # 2. Fast Billing POS
    run_js(page, "showScreen('view-fast-billing');")
    wait_ms(400)
    capture_screenshot(window, "02_fast_billing_pos.png")

    # 3. Traditional Sales Voucher
    run_js(page, "showScreen('view-sales-voucher');")
    wait_ms(400)
    capture_screenshot(window, "03_sales_voucher_traditional.png")

    # 4. Sales Register (Invoices List)
    run_js(page, "showScreen('view-sales-list'); renderSalesRegister();")
    wait_ms(400)
    capture_screenshot(window, "04_sales_register_invoices.png")

    # 5. Products Catalogue
    run_js(page, "showScreen('view-items-list'); renderProductsList();")
    wait_ms(400)
    capture_screenshot(window, "05_products_catalogue.png")

    # 6. Purchase Inward Entry
    run_js(page, "showScreen('view-purchase-entry');")
    wait_ms(400)
    capture_screenshot(window, "06_purchase_inward_entry.png")

    # 7. Purchase Register
    run_js(page, "showScreen('view-purchase-list'); renderPurchaseRegister();")
    wait_ms(400)
    capture_screenshot(window, "07_purchase_register.png")

    # 8. Supplier Master & Payables
    run_js(page, "showScreen('view-supplier-master'); renderSupplierMaster();")
    wait_ms(400)
    capture_screenshot(window, "08_supplier_master_payable.png")

    # 9. Stock Summary & Valuation
    run_js(page, "showScreen('view-stock-summary'); renderStockSummary();")
    wait_ms(400)
    capture_screenshot(window, "09_stock_summary_valuation.png")

    # 10. Stock Adjustments & Transfers
    run_js(page, "showScreen('view-stock-adjustments');")
    wait_ms(400)
    capture_screenshot(window, "10_stock_adjustments_transfers.png")

    # 11. Day Book & Trial Balance
    run_js(page, "showScreen('view-day-book'); renderDayBookScreen();")
    wait_ms(400)
    capture_screenshot(window, "11_day_book_trial_balance.png")

    # 12. Add Item Master
    run_js(page, "showScreen('view-add-item-master');")
    wait_ms(400)
    capture_screenshot(window, "12_add_item_master.png")

    # 13. Add Account Master
    run_js(page, "showScreen('view-add-account-master');")
    wait_ms(400)
    capture_screenshot(window, "13_add_account_master.png")

    # 14. Company Selection
    run_js(page, "showScreen('view-companies');")
    wait_ms(400)
    capture_screenshot(window, "14_company_selection.png")

    # 15. Login Screen
    run_js(page, "showScreen('view-login');")
    wait_ms(400)
    capture_screenshot(window, "15_login_screen.png")

    # 16. Low Stock Alert Modal
    run_js(page, """(() => {
        showScreen('view-dashboard');
        const modal = document.getElementById('modal-low-stock-alert');
        if (modal) modal.classList.add('active');
    })();""")
    wait_ms(400)
    capture_screenshot(window, "16_low_stock_alert_modal.png")
    run_js(page, "(() => { const modal = document.getElementById('modal-low-stock-alert'); if (modal) modal.classList.remove('active'); })();")

    # 17. Mobile Scanner Pairing Modal
    run_js(page, """(() => {
        const modal = document.getElementById('modal-mobile-scanner');
        if (modal) modal.classList.add('active');
    })();""")
    wait_ms(400)
    capture_screenshot(window, "17_mobile_scanner_modal.png")
    run_js(page, "(() => { const modal = document.getElementById('modal-mobile-scanner'); if (modal) modal.classList.remove('active'); })();")

    # 18. Dashboard at 120% Zoom
    run_js(page, "applyZoom(1.2); showScreen('view-dashboard');")
    wait_ms(400)
    capture_screenshot(window, "18_dashboard_zoom_120.png")

    # 19. Dashboard at 80% Zoom
    run_js(page, "applyZoom(0.8); showScreen('view-dashboard');")
    wait_ms(400)
    capture_screenshot(window, "19_dashboard_zoom_80.png")

    # Reset zoom to 1.0
    run_js(page, "applyZoom(1.0);")

    logger.info("All UI/UX Standardization screenshots captured successfully.")
    window.close()


if __name__ == "__main__":
    main()

