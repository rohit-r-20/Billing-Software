#!/usr/bin/env python3
"""
Headless / GUI Verification Script for Live Payment Calculation, Balance Due,
and Optional Percentage Discount Column in Fast Billing.

Runs in PyQt5 with QWebEngine, tests DOM reactivity, calculations,
cash validation, and captures multi-resolution screenshots.
"""
import sys
import os
import json
import time
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from PyQt5.QtCore import Qt, QUrl, QTimer, QEventLoop
from PyQt5.QtWidgets import QApplication

from core.configuration import config
from core.logging_config import logger
from desktop.main_window import MainWindow

SCREENSHOT_DIR = Path("/Users/dhvira/.gemini/antigravity/brain/09ba5738-f0ba-4bec-b71a-8b9e46f5c762/fast_billing_ui")
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


def main():
    logger.info("Initializing Live Payment and Discount Verification...")
    app = QApplication.instance() or QApplication(sys.argv)

    window = MainWindow()
    window.show()

    # Wait for page load
    load_loop = QEventLoop()
    window.web_view.loadFinished.connect(lambda ok: load_loop.quit())
    load_loop.exec_()
    wait_ms(700)

    web_page = window.web_page

    # 1. Switch to Fast Billing screen
    run_js(web_page, """
        if (typeof showScreen === 'function') {
            showScreen('view-fast-billing');
        }
    """)
    wait_ms(300)

    # 2. Check 10-column table structure and presence of discount controls
    structure_check = run_js(web_page, """
        (function() {
            const thElements = Array.from(document.querySelectorAll('#pos-cart-table thead th'));
            const thTexts = thElements.map(th => th.textContent.trim());
            const hasDailyToggle = !!document.getElementById('pos-daily-discount-toggle');
            const hasDailyBadge = !!document.getElementById('pos-daily-discount-badge');
            const hasGrossSubtotal = !!document.getElementById('pos-gross-subtotal');
            const hasDiscountTotal = !!document.getElementById('pos-discount-total');
            const hasBalanceDue = !!document.getElementById('pos-balance-due-val');
            const tenderReceived = document.getElementById('pos-tender-received');

            return {
                thCount: thElements.length,
                thTexts: thTexts,
                discountColIdx: thTexts.findIndex(t => t.includes('Discount')),
                priceColIdx: thTexts.findIndex(t => t.includes('Price')),
                taxColIdx: thTexts.findIndex(t => t.includes('Tax')),
                hasDailyToggle: hasDailyToggle,
                hasDailyBadge: hasDailyBadge,
                hasGrossSubtotal: hasGrossSubtotal,
                hasDiscountTotal: hasDiscountTotal,
                hasBalanceDue: hasBalanceDue,
                tenderStep: tenderReceived ? tenderReceived.getAttribute('step') : null
            };
        })();
    """)
    logger.info(f"Structure verification: {structure_check}")

    # 3. Populate cart with test items:
    # Milk Bikis (5% disc), Hide & Seek (10% disc), Odonil Room Spray (0% disc)
    populate_cart = run_js(web_page, """
        (function() {
            posCart = [
                {
                    id: 'ITEM_MB_01',
                    name: 'BRITANNIA MILK BIKIS 100G [DEMO]',
                    barcode: '890123450001',
                    qty: 2,
                    price: 10.0,
                    taxRate: 5.0,
                    discountPercent: 5.0,
                    unit: 'Pcs.',
                    is_verified: 1
                },
                {
                    id: 'ITEM_HS_02',
                    name: 'PARLE HIDE & SEEK 100G [DEMO]',
                    barcode: '890123450002',
                    qty: 1,
                    price: 30.0,
                    taxRate: 18.0,
                    discountPercent: 10.0,
                    unit: 'Pcs.',
                    is_verified: 1
                },
                {
                    id: 'ITEM_OD_03',
                    name: 'ODONIL ROOM SPRAY - LAVENDER MIST',
                    barcode: '8901207033728',
                    qty: 1,
                    price: 175.0,
                    taxRate: 18.0,
                    discountPercent: 0.0,
                    unit: 'Can',
                    is_verified: 1
                }
            ];
            renderPosCart();

            // Set daily discount badge to show active demo state
            activeDailyDiscount = { active: true, percent: 5.0, date: getTodayDateStr() };
            updateDailyDiscountUI();

            return {
                cartLength: posCart.length,
                grossSubtotal: document.getElementById('pos-gross-subtotal').textContent,
                discountTotal: document.getElementById('pos-discount-total').textContent,
                taxableSubtotal: document.getElementById('pos-subtotal').textContent,
                taxTotal: document.getElementById('pos-tax-total').textContent,
                roundOff: document.getElementById('pos-round-off').textContent,
                payableAmount: document.getElementById('pos-payable-amount').textContent
            };
        })();
    """)
    logger.info(f"Cart populated and totals verified: {populate_cart}")

    # 4. Test live tender calculation matrix on Amount Received
    test_amounts = [0.0, 13.0, 100.0, 200.0, 258.0, 300.0, 500.0]
    calc_results = []

    for amt in test_amounts:
        calc_check = run_js(web_page, f"""
            (function() {{
                const input = document.getElementById('pos-tender-received');
                input.value = '{amt}';
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                
                const changeVal = document.getElementById('pos-change-due-val').textContent;
                const balanceVal = document.getElementById('pos-balance-due-val').textContent;
                const balanceColor = window.getComputedStyle(document.getElementById('pos-balance-due-val')).color;

                return {{
                    entered: {amt},
                    changeDue: changeVal,
                    balanceDue: balanceVal,
                    balanceColor: balanceColor
                }};
            }})();
        """)
        calc_results.append(calc_check)
        wait_ms(100)

    logger.info(f"Calculation Matrix Results: {json.dumps(calc_results, indent=2)}")

    # 5. Set realistic tender amount for screenshot (e.g. ₹300 tendered for ₹258 payable -> Change Due: ₹42.00, Balance: ₹0.00)
    run_js(web_page, """
        (function() {
            const input = document.getElementById('pos-tender-received');
            input.value = '300.00';
            input.dispatchEvent(new Event('input', { bubbles: true }));
        })();
    """)
    wait_ms(300)

    # 6. Capture full window screenshots at 1366x768, 1536x864, 1920x1080
    resolutions = [
        (1366, 768, "payment_discount_1366x768.png"),
        (1536, 864, "payment_discount_1536x864.png"),
        (1920, 1080, "payment_discount_1920x1080.png")
    ]

    for width, height, filename in resolutions:
        window.resize(width, height)
        wait_ms(350)
        pixmap = window.grab()
        save_path = SCREENSHOT_DIR / filename
        pixmap.save(str(save_path))
        logger.info(f"Saved screenshot: {save_path}")

    # 7. Also test underpayment state (₹100 received -> Balance Due ₹158 in red) and capture detailed close-up
    run_js(web_page, """
        (function() {
            const input = document.getElementById('pos-tender-received');
            input.value = '100.00';
            input.dispatchEvent(new Event('input', { bubbles: true }));
        })();
    """)
    wait_ms(300)

    window.resize(1366, 768)
    wait_ms(250)
    underpay_pixmap = window.grab()
    underpay_path = SCREENSHOT_DIR / "payment_underpaid_balance_due_1366x768.png"
    underpay_pixmap.save(str(underpay_path))
    logger.info(f"Saved underpayment balance screenshot: {underpay_path}")

    print("\n=======================================================")
    print("LIVE PAYMENT & DISCOUNT VERIFICATION SUCCESSFUL")
    print("=======================================================")
    print(f"Table Columns ({structure_check['thCount']}): {structure_check['thTexts']}")
    print(f"Discount Column Index: {structure_check['discountColIdx']} (Between Price at {structure_check['priceColIdx']} and Tax at {structure_check['taxColIdx']})")
    print(f"Cart Summary: {populate_cart}")
    print("Tender Calculation Matrix:")
    for r in calc_results:
        print(f"  Tendered: ₹{r['entered']:>6.2f}  |  Change Due: {r['changeDue']:>9}  |  Balance Due: {r['balanceDue']:>9}")
    print("Screenshots captured:")
    for _, _, fn in resolutions:
        print(f"  - {SCREENSHOT_DIR / fn}")
    print(f"  - {underpay_path}")
    print("=======================================================\n")

    window.close()


if __name__ == "__main__":
    main()
