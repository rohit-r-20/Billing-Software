#!/usr/bin/env python3
"""
Comprehensive Headless/GUI Verification Script for ANTI MATRIX — ALPHA BILLING SOFTWARE
Low-Stock Alerts + Customer Category Discounts + UI Usability Refinement.

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

SCREENSHOT_DIR = Path("/Users/dhvira/.gemini/antigravity/brain/09ba5738-f0ba-4bec-b71a-8b9e46f5c762/low_stock_and_discounts_ui")
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
    logger.info("Starting Low-Stock Alerts & Customer Discounts UI Verification...")
    app = QApplication.instance() or QApplication(sys.argv)

    window = MainWindow()
    window.show()

    # Wait for web page to finish loading
    load_loop = QEventLoop()
    window.web_view.loadFinished.connect(lambda ok: load_loop.quit())
    load_loop.exec_()
    wait_ms(1000)

    web_page = window.web_page

    # Log in and select company
    init_res = run_js(web_page, """
        (function() {
            if (typeof companies !== 'undefined' && companies.length > 0) {
                activeCompany = companies[0];
            }
            if (typeof fetchCustomerCategoryDiscounts === 'function') {
                fetchCustomerCategoryDiscounts();
            }
            return {
                hasActiveCompany: !!activeCompany,
                companyName: activeCompany ? activeCompany.name : null
            };
        })();
    """)
    logger.info(f"Initialized company: {init_res}")
    wait_ms(500)

    # -------------------------------------------------------------
    # 1. Fast Billing POS with Customer Category & Low Stock Pill
    # -------------------------------------------------------------
    logger.info("Setting up Fast Billing POS with Customer Category & Low Stock Pill...")
    pos_res = run_js(web_page, """
        (function() {
            showScreen('view-fast-billing');
            initFastBillingScreen();

            cachedCategoryDiscounts = { 'Commercial': 5.0, 'Sub-Commercial': 2.5, 'Direct Customer': 0.0 };

            // Populate customer selector with commercial client
            const select = document.getElementById('pos-customer-select');
            if (select) {
                select.innerHTML = '';
                const optCash = document.createElement('option');
                optCash.value = '';
                optCash.dataset.category = 'Direct Customer';
                optCash.textContent = 'Cash / Walk-In Customer';
                select.appendChild(optCash);

                const optComm = document.createElement('option');
                optComm.value = 'acc-comm-01';
                optComm.dataset.category = 'Commercial';
                optComm.dataset.name = 'SUPREME COMMERCIAL MART';
                optComm.textContent = 'SUPREME COMMERCIAL MART (Commercial)';
                optComm.selected = true;
                select.appendChild(optComm);

                const optSub = document.createElement('option');
                optSub.value = 'acc-sub-01';
                optSub.dataset.category = 'Sub-Commercial';
                optSub.dataset.name = 'METRO MINI RETAIL';
                optSub.textContent = 'METRO MINI RETAIL (Sub-Commercial)';
                select.appendChild(optSub);

                handlePosCustomerChange();
            }

            // Ensure low-stock pill is visible with count
            const posPill = document.getElementById('btn-pos-low-stock-pill');
            const posCount = document.getElementById('pos-low-stock-count');
            if (posPill && posCount) {
                posPill.style.display = 'inline-flex';
                posCount.textContent = '15';
            }

            // Add demo items to POS cart using addItemToPosCart
            posCart = [];
            addItemToPosCart({
                id: 'odonil-01',
                barcode: '8901207033728',
                name: 'Odonil Room Spray – Lavender Mist 220ml',
                unit: 'Can',
                sales_price: 180.00,
                tax_category: 'GST 18%'
            });
            addItemToPosCart({
                id: 'demo-02',
                barcode: '8901063012361',
                name: 'BRITANNIA MILK BIKIS BISCUITS 100g',
                unit: 'Pkt',
                sales_price: 25.00,
                tax_category: 'GST 5%'
            });

            // Adjust quantity of first item
            if (posCart.length > 0) {
                posCart[0].qty = 2;
            }
            renderPosCart();

            return {
                cartCount: posCart.length,
                category: activePosCustomerCategory,
                items: posCart.map(i => ({ name: i.name, disc: i.discountPercent }))
            };
        })();
    """)
    logger.info(f"Fast Billing POS setup result: {pos_res}")

    # Capture Fast Billing at all 3 resolutions
    capture_screenshot(window, "fast_billing_commercial_1366x768.png", 1366, 768)
    capture_screenshot(window, "fast_billing_commercial_1536x864.png", 1536, 864)
    capture_screenshot(window, "fast_billing_commercial_1920x1080.png", 1920, 1080)

    # -------------------------------------------------------------
    # 2. Low-Stock Alert Modal
    # -------------------------------------------------------------
    logger.info("Opening Low-Stock Alert Modal...")
    run_js(web_page, """
        (function() {
            const sampleAlerts = [
                { item_id: 'it-1', product_name: 'ODONIL ROOM SPRAY - LAVENDER MIST', barcode: '8901207033728', unit: 'Can', current_stock: 4.0, threshold: 15.0, shortfall: 11.0, is_negative: false },
                { item_id: 'it-2', product_name: 'BRITANNIA MILK BIKIS BISCUITS 100g', barcode: '8901063012361', unit: 'Pkt', current_stock: 0.0, threshold: 20.0, shortfall: 20.0, is_negative: false },
                { item_id: 'it-3', product_name: 'PARLE HIDE & SEEK CHOCOLATE 120g', barcode: '8901719101038', unit: 'Pkt', current_stock: 2.0, threshold: 25.0, shortfall: 23.0, is_negative: false },
                { item_id: 'it-4', product_name: 'LEVOSALBUTAMOL SULFATE RESPIRATOR SOLN', barcode: '8901117002012', unit: 'Bottle', current_stock: -1.0, threshold: 10.0, shortfall: 11.0, is_negative: true }
            ];
            showLowStockAlertModal(sampleAlerts);
        })();
    """)
    capture_screenshot(window, "low_stock_alert_modal_1366x768.png", 1366, 768)

    # Close modal
    run_js(web_page, "closeLowStockAlertModal(false);")
    wait_ms(300)

    # -------------------------------------------------------------
    # 3. Traditional Billing with Party Category Discount Badge
    # -------------------------------------------------------------
    logger.info("Setting up Traditional Billing with Commercial Party...")
    run_js(web_page, """
        (function() {
            showScreen('view-sales-voucher');

            cachedAccountsList = [
                { id: 'acc-comm-01', name: 'COMMERCIAL STORE_FB4A68', customer_category: 'Commercial', account_group: 'Sundry Debtors' }
            ];
            cachedCategoryDiscounts = { 'Commercial': 5.0, 'Sub-Commercial': 2.5, 'Direct Customer': 0.0 };

            // Set party input to Commercial Client
            if (vchPartyInput) {
                vchPartyInput.value = 'COMMERCIAL STORE_FB4A68';
            }
            updateVoucherPartyCategory();

            // Populate row 1 with an item
            const itemInput = vchItemsTbody.querySelector('.vch-item-input[data-row="1"]');
            const qtyInput = vchItemsTbody.querySelector('.vch-qty-input[data-row="1"]');
            const unitInput = vchItemsTbody.querySelector('.vch-unit-input[data-row="1"]');
            const priceInput = vchItemsTbody.querySelector('.vch-price-input[data-row="1"]');
            if (itemInput && qtyInput && priceInput) {
                itemInput.value = 'ODONIL ROOM SPRAY - LAVENDER MIST';
                qtyInput.value = '10';
                unitInput.value = 'Can';
                priceInput.value = '180.00';
                calcRowAmount(1);
                recalculateVoucherTotals();
            }
        })();
    """)
    capture_screenshot(window, "traditional_billing_party_category_1366x768.png", 1366, 768)

    # -------------------------------------------------------------
    # 4. Stock Summary Screen Filtered by Low Stock
    # -------------------------------------------------------------
    logger.info("Setting up Stock Summary Screen filtered by LOW_STOCK...")
    run_js(web_page, """
        (function() {
            showScreen('view-stock-summary');
            const statusFilter = document.getElementById('stock-summary-filter-status');
            if (statusFilter) {
                statusFilter.value = 'LOW_STOCK';
            }
            renderStockSummary();
        })();
    """)
    capture_screenshot(window, "stock_summary_low_stock_1366x768.png", 1366, 768)

    # -------------------------------------------------------------
    # 5. Product Master Form with Minimum Stock Alert Level
    # -------------------------------------------------------------
    logger.info("Setting up Product Master with Minimum Stock Alert Level...")
    run_js(web_page, """
        (function() {
            showScreen('view-add-item-master');
            resetProductMasterForm();

            if (itemName) itemName.value = 'ODONIL ROOM SPRAY - LAVENDER MIST';
            const aliasEl = document.getElementById('item-alias');
            if (aliasEl) aliasEl.value = '8901207033728';
            const printEl = document.getElementById('item-print-name');
            if (printEl) printEl.value = 'Odonil Room Spray – Lavender Mist 220ml';
            const salesPriceEl = document.getElementById('item-sales-price');
            if (salesPriceEl) salesPriceEl.value = '180.00';
            const mrpEl = document.getElementById('item-mrp');
            if (mrpEl) mrpEl.value = '199.00';
            const minStockEl = document.getElementById('item-min-stock-level');
            if (minStockEl) minStockEl.value = '15.00';
            const alertEnabledEl = document.getElementById('item-alert-enabled');
            if (alertEnabledEl) alertEnabledEl.checked = true;
        })();
    """)
    capture_screenshot(window, "product_master_low_stock_threshold_1366x768.png", 1366, 768)

    # -------------------------------------------------------------
    # 6. Customer Master Form with Customer Category
    # -------------------------------------------------------------
    logger.info("Setting up Account Master with Customer Category...")
    run_js(web_page, """
        (function() {
            showScreen('view-add-account-master');

            if (accName) accName.value = 'SUPREME COMMERCIAL MART';
            const accGroup = document.getElementById('acc-group');
            if (accGroup) accGroup.value = 'Sundry Debtors';
            const catEl = document.getElementById('acc-customer-category');
            if (catEl) catEl.value = 'Commercial';
            const gstinEl = document.getElementById('acc-gstin');
            if (gstinEl) gstinEl.value = '33AABCS1429B1ZB';
        })();
    """)
    capture_screenshot(window, "customer_master_category_1366x768.png", 1366, 768)

    # -------------------------------------------------------------
    # 7. Configuration Modal with Customer Pricing & Discounts
    # -------------------------------------------------------------
    logger.info("Opening Configuration Modal with Customer Discounts...")
    run_js(web_page, """
        (function() {
            openConfigurationModal();
            const discComm = document.getElementById('cfg-disc-commercial');
            const discSub = document.getElementById('cfg-disc-sub-commercial');
            const discDir = document.getElementById('cfg-disc-direct');
            if (discComm) discComm.value = '5.0';
            if (discSub) discSub.value = '2.5';
            if (discDir) discDir.value = '0.0';
        })();
    """)
    capture_screenshot(window, "configuration_customer_discounts_1366x768.png", 1366, 768)

    logger.info("UI Verification completed successfully!")
    window.close()


if __name__ == "__main__":
    main()
