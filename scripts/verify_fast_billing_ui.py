#!/usr/bin/env python3
"""
Verification Script for Fast Billing Product Table Dividers and Adjustable Text Size.
Loads the real application in PyQt5 / QWebEngine, tests the DOM, text sizes,
word wrapping, column alignments, responsive resolutions (1366x768, 1536x864, 1920x1080),
and captures visual screenshots.
"""
import sys
import os
import time
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from PyQt5.QtCore import Qt, QUrl, QTimer, QEventLoop
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView

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
    logger.info("Initializing Fast Billing UI Verification...")
    app = QApplication.instance() or QApplication(sys.argv)

    window = MainWindow()
    window.show()

    # Wait for page load
    load_loop = QEventLoop()
    window.web_view.loadFinished.connect(lambda ok: load_loop.quit())
    load_loop.exec_()
    wait_ms(600)

    web_page = window.web_page

    # 1. Switch directly to Fast Billing screen
    run_js(web_page, """
        if (typeof showScreen === 'function') {
            showScreen('view-fast-billing');
        }
    """)
    wait_ms(300)

    # 2. Add realistic cart items including demo products & Odonil Room Spray
    add_items_script = """
        posCart = [
            {
                item_id: 'ITEM_MB_01',
                name: 'MILK BIKIS [DEMO]',
                barcode: '890_TEST_001',
                qty: 2,
                price: 10.0,
                taxRate: 5.0,
                unit: 'Pcs.'
            },
            {
                item_id: 'ITEM_HS_02',
                name: 'HIDE & SEEK [DEMO]',
                barcode: '890_TEST_002',
                qty: 3,
                price: 20.0,
                taxRate: 18.0,
                unit: 'Pcs.'
            },
            {
                item_id: 'ITEM_OD_03',
                name: 'ODONIL ROOM SPRAY - LAVENDER MIST',
                barcode: '8901207033728',
                qty: 1,
                price: 175.0,
                taxRate: 18.0,
                unit: 'Can'
            },
            {
                item_id: 'ITEM_LS_04',
                name: 'LEVOSALBUTAMOL SULFATE [DEMO/UNVERIFIED]',
                barcode: '8909263004690',
                qty: 1,
                price: 0.0,
                taxRate: 12.0,
                unit: 'Bottle',
                is_verified: 0
            }
        ];
        renderPosCart();
        // Select row 3 (Odonil Room Spray)
        const rows = document.querySelectorAll('#pos-cart-tbody tr');
        if (rows.length >= 3) {
            rows[2].click();
        }
        "items_rendered"
    """
    res = run_js(web_page, add_items_script)
    wait_ms(300)

    # 3. DOM & CSS Inspection
    dom_check_script = """
        (function() {
            const table = document.getElementById('pos-cart-table');
            const wrapper = document.getElementById('pos-cart-table-wrapper');
            const toolbar = document.getElementById('pos-cart-toolbar');
            const countBadge = document.getElementById('pos-cart-table-count');
            const rows = document.querySelectorAll('#pos-cart-tbody tr');
            const firstTd = rows[0] ? rows[0].querySelector('td') : null;
            const firstTh = table.querySelector('thead th');
            const descTd = rows[2] ? rows[2].querySelector('.col-pos-desc') : null;

            const tdStyle = firstTd ? window.getComputedStyle(firstTd) : null;
            const thStyle = firstTh ? window.getComputedStyle(firstTh) : null;
            const descStyle = descTd ? window.getComputedStyle(descTd) : null;

            return {
                rowCount: rows.length,
                countBadgeText: countBadge ? countBadge.textContent : '',
                hasToolbar: !!toolbar,
                thBorderRight: thStyle ? thStyle.borderRight : '',
                tdBorderRight: tdStyle ? tdStyle.borderRight : '',
                descWrap: descStyle ? descStyle.whiteSpace : '',
                descWordBreak: descStyle ? descStyle.wordBreak : '',
                descClientHeight: descTd ? descTd.clientHeight : 0,
                wrapperScrollWidth: wrapper ? wrapper.scrollWidth : 0,
                wrapperClientWidth: wrapper ? wrapper.clientWidth : 0
            };
        })();
    """
    check_data = run_js(web_page, dom_check_script)
    logger.info(f"DOM Verification Results: {check_data}")

    # 4. Text Size Control Testing
    test_sizes_script = """
        (function() {
            const results = {};
            
            // Test Small
            document.getElementById('btn-pos-font-small').click();
            const container = document.getElementById('pos-cart-container');
            results.smallClass = container.className;
            results.smallStored = localStorage.getItem('alpha_pos_table_text_size');
            results.smallFontSize = window.getComputedStyle(document.querySelector('.pos-cart-table td')).fontSize;

            // Test Large
            document.getElementById('btn-pos-font-large').click();
            results.largeClass = container.className;
            results.largeStored = localStorage.getItem('alpha_pos_table_text_size');
            results.largeFontSize = window.getComputedStyle(document.querySelector('.pos-cart-table td')).fontSize;

            // Test Step Decrement (Large -> Normal)
            document.getElementById('btn-pos-font-dec').click();
            results.afterDecClass = container.className;
            results.afterDecStored = localStorage.getItem('alpha_pos_table_text_size');
            results.normalFontSize = window.getComputedStyle(document.querySelector('.pos-cart-table td')).fontSize;

            return results;
        })();
    """
    size_results = run_js(web_page, test_sizes_script)
    logger.info(f"Text Size Control Test Results: {size_results}")

    # 5. Capture Visual Snapshots at 3 standard resolutions:
    # 1366x768, 1536x864, 1920x1080
    resolutions = [
        (1366, 768, "resolution_1366x768.png"),
        (1536, 864, "resolution_1536x864.png"),
        (1920, 1080, "resolution_1920x1080.png")
    ]

    for width, height, filename in resolutions:
        window.resize(width, height)
        wait_ms(300)
        # Check horizontal overflow
        overflow_check = run_js(web_page, """
            (function() {
                const w = document.getElementById('pos-cart-table-wrapper');
                return {
                    scrollWidth: w ? w.scrollWidth : 0,
                    clientWidth: w ? w.clientWidth : 0,
                    hasOverflow: w ? w.scrollWidth > w.clientWidth : false
                };
            })();
        """)
        logger.info(f"Resolution {width}x{height} Overflow Check: {overflow_check}")
        
        pixmap = window.grab()
        save_path = SCREENSHOT_DIR / filename
        pixmap.save(str(save_path))
        logger.info(f"Saved screenshot: {save_path}")

    # Capture closeups of all 3 sizes at 1366x768
    window.resize(1366, 768)
    wait_ms(200)

    for sz in ["small", "normal", "large"]:
        run_js(web_page, f"document.getElementById('btn-pos-font-{sz}').click();")
        wait_ms(200)
        pix = window.grab()
        sz_path = SCREENSHOT_DIR / f"text_size_{sz}_1366x768.png"
        pix.save(str(sz_path))
        logger.info(f"Saved text size variation screenshot: {sz_path}")

    # Reset to normal
    run_js(web_page, "document.getElementById('btn-pos-font-normal').click();")
    wait_ms(200)

    print("\n--- FAST BILLING VERIFICATION REPORT ---")
    print(f"Row Count in DOM: {check_data.get('rowCount')}")
    print(f"Count Badge Text: {check_data.get('countBadgeText')}")
    print(f"Header Vertical Border Right: {check_data.get('thBorderRight')}")
    print(f"Cell Vertical Border Right: {check_data.get('tdBorderRight')}")
    print(f"Description Wrapping whiteSpace: {check_data.get('descWrap')}")
    print(f"Description Wrapping wordBreak: {check_data.get('descWordBreak')}")
    print(f"Description Cell Height (Expanded): {check_data.get('descClientHeight')}px")
    print(f"Small Font Size: {size_results.get('smallFontSize')} (stored: {size_results.get('smallStored')})")
    print(f"Normal Font Size: {size_results.get('normalFontSize')} (stored: {size_results.get('afterDecStored')})")
    print(f"Large Font Size: {size_results.get('largeFontSize')} (stored: {size_results.get('largeStored')})")
    print(f"Screenshots saved to: {SCREENSHOT_DIR}")
    print("----------------------------------------\n")

    window.close()


if __name__ == "__main__":
    main()
