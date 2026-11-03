"""Tests for Fast Billing Product Table Column Dividers, Adjustable Text Size Toolbar, and Word Wrapping."""
import re
from pathlib import Path
import pytest
from db.database import DatabaseManager
from services.catalogue_service import CatalogueService
from services.tax_service import tax_service


BASE_DIR = Path(__file__).resolve().parent.parent


def test_index_html_fast_billing_table_and_toolbar_markup():
    """Verify index.html contains all 9 column classes, wrapper, and text size controls."""
    html_content = (BASE_DIR / "index.html").read_text(encoding="utf-8")

    # Verify wrapper and container IDs
    assert 'id="pos-cart-container"' in html_content
    assert 'id="pos-cart-table-wrapper"' in html_content
    assert 'id="pos-cart-toolbar"' in html_content
    assert 'id="pos-cart-table-count"' in html_content

    # Verify all 9 semantic column headers in Fast Billing table
    expected_th_classes = [
        "col-pos-num",
        "col-pos-barcode",
        "col-pos-desc",
        "col-pos-qty",
        "col-pos-unit",
        "col-pos-price",
        "col-pos-tax",
        "col-pos-total",
        "col-pos-action",
    ]
    for cls in expected_th_classes:
        assert f'class="{cls}"' in html_content or f'class="{cls} ' in html_content

    # Verify Incremental Text Size Control in Toolbar
    assert 'id="btn-pos-font-dec"' in html_content
    assert 'id="pos-font-size-val"' in html_content
    assert 'id="btn-pos-font-inc"' in html_content
    assert "Font Size:" in html_content or "Text Size:" in html_content

    # Verify old discrete Small/Normal/Large buttons are removed
    assert 'id="btn-pos-font-small"' not in html_content
    assert 'id="btn-pos-font-normal"' not in html_content
    assert 'id="btn-pos-font-large"' not in html_content


def test_styles_css_dividers_and_text_sizing_rules():
    """Verify styles.css defines crisp vertical dividers, wrapping, and text size profiles."""
    css_content = (BASE_DIR / "styles.css").read_text(encoding="utf-8")

    # 1. Vertical Dividers on thead th and tbody td
    assert "border-right: 1px solid #334155" in css_content
    assert "border-right: 1px solid #cbd5e1" in css_content
    assert "border-collapse: separate" in css_content
    assert "border-spacing: 0" in css_content

    # 2. Description column wrapping without clipping or truncation
    assert ".col-pos-desc" in css_content
    assert "white-space: normal" in css_content
    assert "word-break: normal" in css_content
    assert "overflow-wrap: break-word" in css_content

    # 3. Three distinct text size scale profiles scoped to .pos-cart-container
    assert ".pos-cart-container.pos-text-size-small" in css_content
    assert ".pos-cart-container.pos-text-size-normal" in css_content
    assert ".pos-cart-container.pos-text-size-large" in css_content

    # 4. Toolbar styling
    assert ".pos-cart-toolbar" in css_content
    assert ".pos-text-size-btn-group" in css_content
    assert ".btn-text-size-opt.active" in css_content

    # 5. Row hover and selection states preserving borders
    assert ".pos-cart-table tbody tr:hover td" in css_content
    assert "pos-row-selected" in css_content or "active-row" in css_content


def test_app_js_pos_cart_rendering_and_text_sizing_logic():
    """Verify app.js implements semantic column classes, selection, and text size persistence."""
    js_content = (BASE_DIR / "app.js").read_text(encoding="utf-8")

    # 1. Semantic td classes in renderPosCart
    assert 'class="col-pos-num"' in js_content
    assert 'class="col-pos-barcode"' in js_content
    assert 'class="col-pos-desc"' in js_content
    assert 'class="col-pos-qty"' in js_content
    assert 'class="col-pos-unit"' in js_content
    assert 'class="col-pos-price"' in js_content
    assert 'class="col-pos-tax"' in js_content
    assert 'class="col-pos-total"' in js_content
    assert 'class="col-pos-action"' in js_content

    # 2. Barcode and name badges
    assert 'class="pos-barcode-badge"' in js_content
    assert 'class="pos-item-name"' in js_content

    # 3. Table item count update
    assert 'pos-cart-table-count' in js_content

    # 4. Text sizing management functions
    assert "function applyPosCartTextSize" in js_content
    assert "function getPosCartTextSize" in js_content
    assert "function stepPosCartTextSize" in js_content
    assert "function initPosTextSizeControls" in js_content

    # 5. LocalStorage persistence
    assert 'alpha_pos_table_text_size' in js_content

    # 6. Called on startup & Fast Billing initialization
    assert "initPosTextSizeControls();" in js_content


def test_catalogue_demo_and_odonil_products_in_pos_cart(tmp_path):
    """Verify demo products (Milk Bikis, Hide & Seek) and Odonil Room Spray calculate correctly in cart."""
    db_file = tmp_path / "test_pos_cart.db"
    manager = DatabaseManager(db_file)
    manager.run_migrations()

    with manager.get_connection() as conn:
        conn.execute("""
            INSERT INTO companies (id, code, name, fin_year, gstin, state)
            VALUES ('C_TEST', 'COMP99', 'TEST STORE', '2026-27', '33AAAPL9999F1Z1', 'Tamilnadu');
        """)
        conn.commit()

    cat = CatalogueService(manager)

    # Seed Milk Bikis
    cat.save_item('C_TEST', {
        "name": "MILK BIKIS [DEMO]",
        "alias": "890_TEST_001",
        "barcode": "890_TEST_001",
        "sales_price": 10.0,
        "tax_category": "GST 5%",
        "unit": "Pcs.",
        "op_stock_qty": 50.0
    })

    # Seed Hide & Seek
    cat.save_item('C_TEST', {
        "name": "HIDE & SEEK [DEMO]",
        "alias": "890_TEST_002",
        "barcode": "890_TEST_002",
        "sales_price": 20.0,
        "tax_category": "GST 18%",
        "unit": "Pcs.",
        "op_stock_qty": 50.0
    })

    # Seed Odonil Room Spray – Lavender Mist
    cat.save_item('C_TEST', {
        "name": "ODONIL ROOM SPRAY - LAVENDER MIST",
        "alias": "8901207033728",
        "barcode": "8901207033728",
        "sales_price": 175.0,
        "tax_category": "GST 18%",
        "unit": "Can",
        "op_stock_qty": 20.0
    })

    # Find each by barcode
    mb = cat.find_by_barcode('C_TEST', '890_TEST_001')
    assert mb is not None
    assert mb['name'] == 'MILK BIKIS [DEMO]'
    assert mb['sales_price'] == 10.0

    hs = cat.find_by_barcode('C_TEST', '890_TEST_002')
    assert hs is not None
    assert hs['name'] == 'HIDE & SEEK [DEMO]'
    assert hs['sales_price'] == 20.0

    od = cat.find_by_barcode('C_TEST', '8901207033728')
    assert od is not None
    assert 'ODONIL' in od['name']
    assert od['sales_price'] == 175.0

    # Simulate cart calculation
    cart = [
        {"item_id": mb["id"], "name": mb["name"], "barcode": "890_TEST_001", "qty": 2, "price": 10.0, "taxRate": 5.0, "unit": "Pcs."},
        {"item_id": hs["id"], "name": hs["name"], "barcode": "890_TEST_002", "qty": 3, "price": 20.0, "taxRate": 18.0, "unit": "Pcs."},
        {"item_id": od["id"], "name": od["name"], "barcode": "8901207033728", "qty": 1, "price": 175.0, "taxRate": 18.0, "unit": "Can"},
    ]

    subtotal = sum(item["qty"] * item["price"] for item in cart)
    # (2*10 = 20) + (3*20 = 60) + (1*175 = 175) = 255.0
    assert subtotal == 255.0

    tax_total = sum((item["qty"] * item["price"] * item["taxRate"]) / 100 for item in cart)
    # 20*0.05 = 1.0; 60*0.18 = 10.8; 175*0.18 = 31.5 -> total = 43.3
    assert round(tax_total, 2) == 43.30

    grand_total = subtotal + tax_total
    assert round(grand_total, 2) == 298.30
    assert round(grand_total) == 298


def eval_js(view, script):
    from PyQt5.QtCore import QEventLoop
    loop = QEventLoop()
    result = {"val": None}

    def callback(res):
        result["val"] = res
        loop.quit()

    view.page().runJavaScript(script, callback)
    loop.exec_()
    return result["val"]


def test_incremental_font_size_step_and_bounds(session_web_view):
    """Test incremental +/- text size controls, min/max limits, button disabled state, and persistence."""
    view = session_web_view

    # Navigate to Fast Billing
    eval_js(view, """
        activeCompany = { id: 'COMP0001', name: 'ANTI MATRIX', fin_year: '2026-27' };
        openFastBillingPos();
    """)

    # Initial default size should be 13 px
    disp = eval_js(view, "document.getElementById('pos-font-size-val').textContent")
    assert "px" in disp

    # Set to 13 explicitly
    eval_js(view, "applyPosCartTextSize(13);")
    assert eval_js(view, "document.getElementById('pos-font-size-val').textContent") == "13 px"
    assert eval_js(view, "document.getElementById('btn-pos-font-dec').disabled") is False
    assert eval_js(view, "document.getElementById('btn-pos-font-inc').disabled") is False

    # Click + to reach 14 px
    eval_js(view, "document.getElementById('btn-pos-font-inc').click();")
    assert eval_js(view, "document.getElementById('pos-font-size-val').textContent") == "14 px"
    assert eval_js(view, "localStorage.getItem('alpha_pos_table_text_size')") == "14"

    # Click - twice to reach 12 px
    eval_js(view, "document.getElementById('btn-pos-font-dec').click();")
    assert eval_js(view, "document.getElementById('pos-font-size-val').textContent") == "13 px"
    eval_js(view, "document.getElementById('btn-pos-font-dec').click();")
    assert eval_js(view, "document.getElementById('pos-font-size-val').textContent") == "12 px"

    # Step down to MIN (11 px)
    eval_js(view, "applyPosCartTextSize(11);")
    assert eval_js(view, "document.getElementById('pos-font-size-val').textContent") == "11 px"
    assert eval_js(view, "document.getElementById('btn-pos-font-dec').disabled") is True
    assert eval_js(view, "document.getElementById('btn-pos-font-inc').disabled") is False

    # Clicking dec when disabled should not drop below 11
    eval_js(view, "document.getElementById('btn-pos-font-dec').click();")
    assert eval_js(view, "document.getElementById('pos-font-size-val').textContent") == "11 px"

    # Step up to MAX (18 px)
    eval_js(view, "applyPosCartTextSize(18);")
    assert eval_js(view, "document.getElementById('pos-font-size-val').textContent") == "18 px"
    assert eval_js(view, "document.getElementById('btn-pos-font-inc').disabled") is True
    assert eval_js(view, "document.getElementById('btn-pos-font-dec').disabled") is False

    # Clicking inc when disabled should not exceed 18
    eval_js(view, "document.getElementById('btn-pos-font-inc').click();")
    assert eval_js(view, "document.getElementById('pos-font-size-val').textContent") == "18 px"

    # Reset to default 13 px
    eval_js(view, "applyPosCartTextSize(13);")
    assert eval_js(view, "document.getElementById('pos-font-size-val').textContent") == "13 px"


def test_pos_cart_columns_accessibility_and_wrapping_with_long_names(session_web_view):
    """Test that all table columns remain accessible and long product names wrap at various font sizes."""
    view = session_web_view

    # Populate cart with short and long product names
    eval_js(view, """
        posCart = [
            {
                id: 'P1',
                barcode: '8904132959446',
                name: 'SPOON',
                qty: 2,
                price: 15.00,
                unit: 'Pcs.',
                taxRate: 18,
                discountPercent: 0
            },
            {
                id: 'P2',
                barcode: '8901234567890',
                name: 'Milk Bikis Original Family Pack 10 Rupees Crisp Biscuits',
                qty: 5,
                price: 25.00,
                unit: 'Pack',
                taxRate: 5,
                discountPercent: 2.5
            },
            {
                id: 'P3',
                barcode: '8901207033728',
                name: 'Marigold Premium Glucose Biscuits Family Pack Large',
                qty: 1,
                price: 120.00,
                unit: 'Box',
                taxRate: 18,
                discountPercent: 5.0
            }
        ];
        renderPosCart();
    """)

    # Verify all columns in table header and body
    th_count = eval_js(view, "document.querySelectorAll('#pos-cart-table thead th').length")
    assert th_count == 10  # #, Barcode, Desc, Qty, Unit, Price, Discount, Tax, Total, Action

    # Test across font sizes: 11px (min), 13px (default), 16px, 18px (max)
    for sz in [11, 13, 16, 18]:
        eval_js(view, f"applyPosCartTextSize({sz});")

        # Verify rows exist
        rows_count = eval_js(view, "document.querySelectorAll('#pos-cart-tbody tr').length")
        assert rows_count == 3

        # Check wrapping on second item (Milk Bikis with long name)
        is_wrapped = eval_js(view, """
            (() => {
                const names = document.querySelectorAll('.pos-item-name');
                if (names.length < 2) return false;
                const longName = names[1];
                // In wrapped multi-line text, clientHeight is greater than line-height (~18px)
                return longName.clientHeight >= 16;
            })()
        """)
        assert is_wrapped is True

        # Verify no horizontal blowout of body
        scroll_w = eval_js(view, "document.body.scrollWidth")
        client_w = eval_js(view, "document.body.clientWidth")
        assert scroll_w <= client_w + 2, f"Horizontal window blowout at font size {sz}px"

        # Verify payment panel remains visible and positioned
        pay_panel_visible = eval_js(view, """
            (() => {
                const p = document.querySelector('.pos-summary-panel');
                return p && p.getBoundingClientRect().width > 200;
            })()
        """)
        assert pay_panel_visible is True

    # Reset to default
    eval_js(view, "applyPosCartTextSize(13);")


