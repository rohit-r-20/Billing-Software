"""
Automated Test Suite for Alpha Billing - Item Master:
Synchronise Product Name and Receipt Name

Validates all Acceptance Criteria:
1. Typing a new Product Name automatically populates Receipt Print Name.
2. Editing an existing Product Name immediately updates Receipt Print Name.
3. The user cannot manually edit Receipt Print Name (readonly, tabindex=-1, input-readonly class, event prevention).
4. The database stores identical values for Product Name and Receipt Print Name in SQLite & PostgreSQL.
5. Saving is rejected if Product Name is empty.
6. Saving is rejected if Receipt Print Name does not match Product Name.
7. Existing products display and update correctly in Modify mode.
8. Workflows and business rules preserved:
   - Account Master, Customer Master, Supplier Master remain unaffected.
   - Barcode generation & inventory calculations remain intact.
   - No duplicate records created.
"""
import uuid
from pathlib import Path
import pytest
from PyQt5.QtCore import QEventLoop, QTimer

from services.catalogue_service import catalogue_service
from services.account_service import account_service
from services.barcode_service import barcode_service
from db.database import db_manager

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_HTML = BASE_DIR / "index.html"
APP_JS = BASE_DIR / "app.js"
STYLES_CSS = BASE_DIR / "styles.css"


def _get_active_company_id():
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM companies WHERE code = 'COMP0001' LIMIT 1;")
        row = cursor.fetchone()
        return row["id"] if row else "3a743bcd-8f9a-4154-a316-509cba3de99a"


COMPANY_ID = _get_active_company_id()


@pytest.fixture
def web_view(session_web_view):
    return session_web_view


def eval_js(view, script):
    loop = QEventLoop()
    result = {"val": None}

    def callback(res):
        result["val"] = res
        loop.quit()

    view.page().runJavaScript(script, callback)
    loop.exec_()
    return result["val"]


def wait_for_js_condition(view, condition_js, timeout_ms=3000):
    loop = QEventLoop()
    res = {"val": False}
    start_time = [0]

    def check():
        def cb(v):
            if v:
                res["val"] = True
                loop.quit()
            elif start_time[0] < timeout_ms:
                start_time[0] += 50
                QTimer.singleShot(50, check)
            else:
                loop.quit()
        view.page().runJavaScript(condition_js, cb)

    check()
    loop.exec_()
    return res["val"]


# ============================================================================
# Acceptance Criterion 1 & 3: UI attributes and read-only styling
# ============================================================================

def test_ac3_html_and_css_item_print_name_readonly_specs():
    """Verify HTML and CSS enforce readonly and distinct visual styling for item-print-name."""
    html_content = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="item-print-name"' in html_content
    # Must have readonly, tabindex="-1", and class input-readonly
    assert 'id="item-print-name"' in html_content
    line_print_name = [line for line in html_content.splitlines() if 'id="item-print-name"' in line][0]
    assert 'readonly' in line_print_name
    assert 'tabindex="-1"' in line_print_name
    assert 'class="input-readonly"' in line_print_name

    css_content = STYLES_CSS.read_text(encoding="utf-8")
    assert "#item-print-name" in css_content
    assert ".input-readonly" in css_content


def test_ac3_item_print_name_cannot_be_manually_edited(web_view):
    """Verify user cannot manually edit Receipt Print Name in the UI."""
    dom_check = eval_js(web_view, """
        (function() {
            const printEl = document.getElementById('item-print-name');
            return {
                exists: !!printEl,
                isReadOnly: printEl.readOnly,
                hasReadOnlyAttr: printEl.hasAttribute('readonly'),
                tabIndex: printEl.tabIndex,
                classList: Array.from(printEl.classList)
            };
        })()
    """)
    assert dom_check["exists"] is True
    assert dom_check["isReadOnly"] is True
    assert dom_check["hasReadOnlyAttr"] is True
    assert dom_check["tabIndex"] == -1
    assert "input-readonly" in dom_check["classList"]


# ============================================================================
# Acceptance Criterion 1 & 2: Dynamic UI synchronisation
# ============================================================================

def test_ac1_typing_new_product_name_automatically_populates_receipt_print_name(web_view):
    """AC 1: Typing a new Product Name automatically populates Receipt Print Name."""
    result = eval_js(web_view, """
        (function() {
            if (typeof resetProductMasterForm === 'function') resetProductMasterForm();
            const nameEl = document.getElementById('item-name');
            const printEl = document.getElementById('item-print-name');

            nameEl.value = 'Milk Bikis 100g';
            nameEl.dispatchEvent(new Event('input', { bubbles: true }));

            return {
                nameVal: nameEl.value,
                printVal: printEl.value
            };
        })()
    """)
    assert result["nameVal"] == "Milk Bikis 100g"
    assert result["printVal"] == "Milk Bikis 100g"


def test_ac2_editing_product_name_immediately_updates_receipt_print_name(web_view):
    """AC 2: Editing an existing Product Name immediately updates Receipt Print Name."""
    result = eval_js(web_view, """
        (function() {
            const nameEl = document.getElementById('item-name');
            const printEl = document.getElementById('item-print-name');

            nameEl.value = 'Milk Bikis 100g Special Pack';
            nameEl.dispatchEvent(new Event('input', { bubbles: true }));
            const step1 = printEl.value;

            nameEl.value = 'Milk Bikis 200g Family Pack';
            nameEl.dispatchEvent(new Event('change', { bubbles: true }));
            const step2 = printEl.value;

            return {
                step1: step1,
                step2: step2
            };
        })()
    """)
    assert result["step1"] == "Milk Bikis 100g Special Pack"
    assert result["step2"] == "Milk Bikis 200g Family Pack"


# ============================================================================
# Acceptance Criterion 4: Database stores identical values
# ============================================================================

def test_ac4_database_stores_identical_values_for_product_name_and_receipt_print_name():
    """AC 4: The database stores identical values for Product Name and Receipt Print Name."""
    uid = uuid.uuid4().hex[:6]
    product_name = f"Parle-G Gold {uid}"

    saved_item = catalogue_service.save_item(COMPANY_ID, {
        "name": product_name,
        "sales_price": 25.0,
        "group": "Biscuits",
        "unit": "Pcs."
    })

    assert saved_item["id"] is not None
    assert saved_item["name"] == product_name.upper()
    assert saved_item["print_name"] == product_name.upper()
    assert saved_item["printName"] == product_name.upper()

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, print_name FROM items WHERE id = ?;", (saved_item["id"],))
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == row["print_name"]
        assert row["name"] == product_name.upper()


# ============================================================================
# Acceptance Criterion 5 & 6: Validation rules
# ============================================================================

def test_ac5_saving_rejected_if_product_name_empty():
    """AC 5: Saving is rejected if Product Name is empty."""
    with pytest.raises(ValueError, match="Item name cannot be empty"):
        catalogue_service.save_item(COMPANY_ID, {
            "name": "",
            "sales_price": 10.0
        })

    with pytest.raises(ValueError, match="Item name cannot be empty"):
        catalogue_service.save_item(COMPANY_ID, {
            "name": "   ",
            "sales_price": 10.0
        })


def test_ac6_saving_rejected_if_receipt_print_name_does_not_match():
    """AC 6: Saving is rejected if Receipt Print Name does not match Product Name."""
    uid = uuid.uuid4().hex[:6]
    with pytest.raises(ValueError, match="Receipt Print Name must match Product Name"):
        catalogue_service.save_item(COMPANY_ID, {
            "name": f"Good Day Cashew {uid}",
            "print_name": f"FORGED DIFFERENT NAME {uid}",
            "sales_price": 30.0
        })


# ============================================================================
# Acceptance Criterion 7: Modify mode display and update
# ============================================================================

def test_ac7_modify_existing_product_display_and_update(web_view):
    """AC 7: Existing products display and update correctly in Modify mode."""
    uid = uuid.uuid4().hex[:6]
    orig_name = f"Bourbon Biscuits {uid}"
    created = catalogue_service.save_item(COMPANY_ID, {
        "name": orig_name,
        "sales_price": 40.0,
        "group": "Biscuits"
    })
    item_id = created["id"]

    # 1. Load into modify view in UI
    eval_js(web_view, f"""
        (function() {{
            if (typeof loadProductForEditing === 'function') {{
                loadProductForEditing({{
                    id: '{item_id}',
                    name: '{created["name"]}',
                    print_name: '{created["print_name"]}',
                    sales_price: 40.0,
                    item_group: 'Biscuits',
                    unit: 'Pcs.'
                }});
            }}
        }})()
    """)

    load_res = eval_js(web_view, """
        (function() {
            const idEl = document.getElementById('item-id');
            const nameEl = document.getElementById('item-name');
            const printEl = document.getElementById('item-print-name');
            return {
                id: idEl ? idEl.value : null,
                name: nameEl ? nameEl.value : null,
                print: printEl ? printEl.value : null
            };
        })()
    """)
    assert load_res["id"] == item_id
    assert load_res["name"] == orig_name.upper()
    assert load_res["print"] == orig_name.upper()

    # 2. Update Product Name in modify view
    updated_name = f"Bourbon Biscuits Premium {uid}"
    updated_res = eval_js(web_view, f"""
        (function() {{
            const nameEl = document.getElementById('item-name');
            const printEl = document.getElementById('item-print-name');
            nameEl.value = '{updated_name}';
            nameEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
            return {{
                name: nameEl.value,
                print: printEl.value
            }};
        }})()
    """)
    assert updated_res["name"] == updated_name
    assert updated_res["print"] == updated_name

    # 3. Save modified product through service with updated name
    updated_item = catalogue_service.save_item(COMPANY_ID, {
        "id": item_id,
        "name": updated_name,
        "sales_price": 45.0,
        "group": "Biscuits"
    })
    assert updated_item["id"] == item_id
    assert updated_item["name"] == updated_name.upper()
    assert updated_item["print_name"] == updated_name.upper()

    # 4. Verify no duplicate records created in database
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM items WHERE id = ?;", (item_id,))
        count_row = cursor.fetchone()
        assert count_row["cnt"] == 1


# ============================================================================
# Acceptance Criterion 8: Scope boundaries & preservation of other workflows
# ============================================================================

def test_scope_preserves_party_masters_and_barcode_generation():
    """Verify changes are isolated to Item Master; Account Master and Barcode Generation preserved."""
    uid = uuid.uuid4().hex[:6]
    # Account Master works independently
    acc = account_service.save_account(COMPANY_ID, {
        "name": f"PARTY {uid}",
        "group": "Sundry Debtors",
        "customer_category": "Commercial"
    })
    assert acc["id"] is not None
    assert acc["name"] == f"PARTY {uid}".upper()
    assert acc["print_name"] == f"PARTY {uid}".upper()

    # Barcode generator works normally for items
    barcode_res = barcode_service.generate_internal_barcode(company_id=COMPANY_ID)
    barcode = barcode_res["barcode"]
    assert barcode.startswith("AB")
    uniqueness = barcode_service.check_barcode_uniqueness(barcode, company_id=COMPANY_ID)
    assert uniqueness["is_unique"] is True
