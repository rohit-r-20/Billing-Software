#!/usr/bin/env python3
"""
Comprehensive Headless/GUI Verification Script for ANTI MATRIX — ALPHA BILLING SOFTWARE
Complete Enterprise ERP Implementation (Purchase, Inventory, Suppliers, Accounting, OCR).

Captures UI verification screenshots across standard retail resolutions:
- 1366x768
- 1536x864
- 1920x1080
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

SCREENSHOT_DIR = Path("/Users/dhvira/.gemini/antigravity/brain/09ba5738-f0ba-4bec-b71a-8b9e46f5c762/enterprise_erp_ui")
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
    wait_ms(400)
    out_path = SCREENSHOT_DIR / file_name
    pix = window.grab()
    pix.save(str(out_path), "PNG")
    logger.info(f"Captured screenshot {out_path} ({width}x{height})")
    return out_path


def main():
    logger.info("Starting Enterprise ERP UI Verification...")
    app = QApplication.instance() or QApplication(sys.argv)

    window = MainWindow()
    window.show()

    # Wait for web page to finish loading
    load_loop = QEventLoop()
    window.web_view.loadFinished.connect(lambda ok: load_loop.quit())
    load_loop.exec_()
    wait_ms(800)

    web_page = window.web_page

    # Log in or ensure active company
    init_res = run_js(web_page, """
        (function() {
            if (typeof companies !== 'undefined' && companies.length > 0) {
                activeCompany = companies[0];
            }
            if (typeof showScreen === 'function') {
                showScreen('view-purchase-entry');
            }
            return {
                hasActiveCompany: !!activeCompany,
                companyName: activeCompany ? activeCompany.name : null,
                currentScreen: currentScreen
            };
        })();
    """)
    logger.info(f"Initial setup: {init_res}")
    wait_ms(500)

    # 1. Verify Purchase Entry Screen
    logger.info("--- Testing Purchase Entry View ---")
    pur_info = run_js(web_page, """
        (function() {
            const vchNo = document.getElementById('pur-vch-no')?.value;
            const supSelect = document.getElementById('pur-supplier-select');
            const supInvNo = document.getElementById('pur-supplier-inv-no');
            if (supInvNo) supInvNo.value = 'INV/2026/8942';

            // Add sample items if empty
            if (typeof purchaseItemsData !== 'undefined' && purchaseItemsData.length > 0) {
                purchaseItemsData[0].name = 'Odonil Room Spray – Lavender Mist';
                purchaseItemsData[0].barcode = '8901207033728';
                purchaseItemsData[0].qty = 50;
                purchaseItemsData[0].cost_rate = 95.00;
                purchaseItemsData[0].tax_rate = 18;
                
                purchaseItemsData.push({
                    item_id: '',
                    barcode: '8901030999999',
                    name: 'Hide & Seek Chocolate Biscuits 120g',
                    batch_no: 'B-998',
                    expiry_date: '2027-12-31',
                    qty: 40,
                    free_qty: 4,
                    unit: 'Pcs',
                    cost_rate: 25.00,
                    discount_pct: 5,
                    taxable_amount: 0,
                    tax_rate: 18,
                    cgst_amount: 0,
                    sgst_amount: 0,
                    igst_amount: 0,
                    line_total: 0
                });
                renderPurchaseGridRows();
                calcPurchaseTotals();
            }

            return {
                vchNo: vchNo,
                supplierOptions: supSelect ? supSelect.options.length : 0,
                rowCount: document.querySelectorAll('#pur-items-tbody tr').length,
                subtotal: document.getElementById('pur-subtotal-val')?.textContent,
                grandTotal: document.getElementById('pur-grand-total')?.textContent
            };
        })();
    """)
    logger.info(f"Purchase Entry Status: {pur_info}")
    wait_ms(400)

    # Capture Purchase Entry at 1366x768, 1536x864, 1920x1080
    capture_screenshot(window, "purchase_entry_1366x768.png", 1366, 768)
    capture_screenshot(window, "purchase_entry_1536x864.png", 1536, 864)
    capture_screenshot(window, "purchase_entry_1920x1080.png", 1920, 1080)

    # 2. Verify Document OCR Modal
    logger.info("--- Testing Document OCR Modal ---")
    ocr_info = run_js(web_page, """
        (function() {
            if (typeof openOcrModal === 'function') {
                openOcrModal();
                const rawText = document.getElementById('ocr-raw-text-input');
                if (rawText && typeof SAMPLE_GST_INVOICE_TEXT !== 'undefined') {
                    rawText.value = SAMPLE_GST_INVOICE_TEXT;
                }
                if (typeof runOcrExtraction === 'function') {
                    runOcrExtraction();
                }
            }
            return {
                modalDisplay: document.getElementById('modal-invoice-ocr')?.style.display,
                resPanelDisplay: document.getElementById('ocr-results-panel')?.style.display
            };
        })();
    """)
    logger.info(f"OCR Initial Trigger: {ocr_info}")
    wait_ms(800)

    capture_screenshot(window, "invoice_ocr_modal_1366x768.png", 1366, 768)

    # Close OCR modal
    run_js(web_page, """
        document.getElementById('modal-invoice-ocr').style.display = 'none';
    """)
    wait_ms(300)

    # 3. Verify Stock Summary Screen
    logger.info("--- Testing Stock Summary Screen ---")
    stock_info = run_js(web_page, """
        (function() {
            if (typeof showScreen === 'function') {
                showScreen('view-stock-summary');
                if (typeof renderStockSummary === 'function') {
                    renderStockSummary();
                }
            }
            return {
                currentScreen: currentScreen
            };
        })();
    """)
    wait_ms(800)

    stock_rendered = run_js(web_page, """
        (function() {
            return {
                rowCount: document.querySelectorAll('#stock-summary-tbody tr').length,
                totalSkus: document.getElementById('stock-summary-total-skus')?.textContent,
                totalValuation: document.getElementById('stock-summary-total-valuation')?.textContent
            };
        })();
    """)
    logger.info(f"Stock Summary Rendered: {stock_rendered}")

    capture_screenshot(window, "stock_summary_1366x768.png", 1366, 768)
    capture_screenshot(window, "stock_summary_1536x864.png", 1536, 864)
    capture_screenshot(window, "stock_summary_1920x1080.png", 1920, 1080)

    # 4. Verify Stock Item Ledger Modal
    logger.info("--- Testing Stock Item Ledger Modal ---")
    ledger_modal_info = run_js(web_page, """
        (function() {
            const firstLedgerBtn = document.querySelector('.stock-btn-ledger');
            if (firstLedgerBtn) {
                firstLedgerBtn.click();
            }
            return {
                modalDisplay: document.getElementById('modal-stock-item-ledger')?.style.display
            };
        })();
    """)
    wait_ms(600)
    capture_screenshot(window, "stock_item_ledger_modal_1366x768.png", 1366, 768)

    run_js(web_page, "document.getElementById('modal-stock-item-ledger').style.display = 'none';")
    wait_ms(200)

    # 5. Verify Supplier Master View
    logger.info("--- Testing Supplier Master View ---")
    run_js(web_page, """
        showScreen('view-supplier-master');
        if (typeof renderSupplierMaster === 'function') renderSupplierMaster();
    """)
    wait_ms(600)
    capture_screenshot(window, "supplier_master_1366x768.png", 1366, 768)

    # 6. Verify Financial Day Book & Trial Balance View
    logger.info("--- Testing Day Book & Trial Balance View ---")
    run_js(web_page, """
        showScreen('view-day-book');
        switchDayBookTab('trial-balance');
    """)
    wait_ms(700)
    tb_status = run_js(web_page, """
        (function() {
            return {
                statusBadge: document.getElementById('trial-balance-status-badge')?.textContent.trim(),
                debit: document.getElementById('tb-total-debit')?.textContent,
                credit: document.getElementById('tb-total-credit')?.textContent,
                diff: document.getElementById('tb-difference')?.textContent
            };
        })();
    """)
    logger.info(f"Trial Balance Status: {tb_status}")
    capture_screenshot(window, "trial_balance_1366x768.png", 1366, 768)

    # Switch back to Day Book Tab
    run_js(web_page, "switchDayBookTab('daybook');")
    wait_ms(400)
    capture_screenshot(window, "day_book_1366x768.png", 1366, 768)

    # 7. Verify Fast Billing Navigation Pill
    logger.info("--- Testing Fast Billing Navigation ---")
    run_js(web_page, "showScreen('view-fast-billing');")
    wait_ms(400)
    fast_billing_pills = run_js(web_page, """
        (function() {
            return {
                hasStockPill: !!document.getElementById('btn-pos-quick-stock'),
                hasPurPill: !!document.getElementById('btn-pos-quick-purchase')
            };
        })();
    """)
    logger.info(f"Fast Billing ERP Pills: {fast_billing_pills}")
    capture_screenshot(window, "fast_billing_with_erp_pills_1366x768.png", 1366, 768)

    window.close()
    logger.info("Enterprise ERP UI Verification completed successfully.")


if __name__ == "__main__":
    main()

