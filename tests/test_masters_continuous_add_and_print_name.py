"""
Automated Test Suite for Alpha Billing - Masters Module:
Automatic Print Name and Continuous Add Workflow

Verifies all 10 requirements:
1. Entering a Name automatically populates Print Name.
2. Editing Name updates Print Name.
3. Print Name cannot be independently edited.
4. Alias remains independently editable and is not overwritten by Name changes.
5. Saved Name and Print Name are identical in database and backend responses.
6. Successful save keeps the user on the same Add Master screen (no redirect to Dashboard, List, or Modify).
7. Form resets after successful save while preserving defaults.
8. Focus returns to the Name field.
9. Failed save preserves entered information and displays error without clearing form.
10. Item Master remains completely unaffected.
"""
import json
import uuid
from pathlib import Path
import pytest
from PyQt5.QtCore import QEventLoop, QTimer

from services.account_service import account_service
from services.catalogue_service import catalogue_service
from db.database import db_manager
from desktop.web_bridge import BackendBridge

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_HTML = BASE_DIR / "index.html"
APP_JS = BASE_DIR / "app.js"
STYLES_CSS = BASE_DIR / "styles.css"


def _get_active_company_id():
    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT id FROM companies WHERE code = 'COMP0001' LIMIT 1;").fetchone()
        return row[0] if row else "3a743bcd-8f9a-4154-a316-509cba3de99a"


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


def test_html_and_css_print_name_readonly_specs():
    """Verify HTML and CSS enforce readonly and distinct visual styling for acc-print-name."""
    html_content = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="acc-print-name"' in html_content
    assert 'class="input-readonly"' in html_content
    assert 'readonly' in html_content

    css_content = STYLES_CSS.read_text(encoding="utf-8")
    assert "#acc-print-name" in css_content
    assert ".input-readonly" in css_content
    assert "cursor: not-allowed" in css_content


def test_req1_req2_name_synchronises_with_print_name(web_view):
    """Req 1 & 2: Entering and editing Name automatically updates Print Name."""
    eval_js(web_view, """
        if (typeof companies !== 'undefined' && companies.length > 0) {
            activeCompany = companies[0];
            sessionLowStockDismissed = true;
            enterCompanyDashboard(companies[0]);
            if (typeof closeLowStockAlertModal === 'function') closeLowStockAlertModal(false);
        }
        openAddAccountMaster();
    """)

    # 1. Entering Name
    vals1 = eval_js(web_view, """
        (function() {
            const nameEl = document.getElementById('acc-name');
            const printEl = document.getElementById('acc-print-name');
            nameEl.value = 'ABC Traders';
            nameEl.dispatchEvent(new Event('input', { bubbles: true }));
            return {
                name: nameEl.value,
                printName: printEl.value
            };
        })()
    """)
    assert vals1["name"] == "ABC Traders"
    assert vals1["printName"] == "ABC Traders"

    # 2. Editing Name updates Print Name in lockstep
    vals2 = eval_js(web_view, """
        (function() {
            const nameEl = document.getElementById('acc-name');
            const printEl = document.getElementById('acc-print-name');
            nameEl.value = 'ABC Enterprises Global';
            nameEl.dispatchEvent(new Event('input', { bubbles: true }));
            return {
                name: nameEl.value,
                printName: printEl.value
            };
        })()
    """)
    assert vals2["name"] == "ABC Enterprises Global"
    assert vals2["printName"] == "ABC Enterprises Global"


def test_req3_print_name_cannot_be_independently_edited(web_view):
    """Req 3: Print Name must not be independently editable by the user and is visually identifiable."""
    props = eval_js(web_view, """
        (function() {
            const printEl = document.getElementById('acc-print-name');
            const style = window.getComputedStyle(printEl);
            return {
                isReadOnly: printEl.readOnly,
                hasAttr: printEl.hasAttribute('readonly'),
                cursor: style.cursor,
                bgColor: style.backgroundColor
            };
        })()
    """)
    assert props["isReadOnly"] is True
    assert props["hasAttr"] is True
    assert props["cursor"] == "not-allowed"
    # Background should be distinct muted/slate (e.g. rgb(241, 245, 249))
    assert "rgb(241, 245, 249)" in props["bgColor"] or "rgba(241, 245, 249" in props["bgColor"]


def test_req4_alias_remains_independently_editable(web_view):
    """Req 4: Alias remains independently editable and is not overwritten when Name changes."""
    vals = eval_js(web_view, """
        (function() {
            openAddAccountMaster();
            const nameEl = document.getElementById('acc-name');
            const aliasEl = document.getElementById('acc-alias');
            const printEl = document.getElementById('acc-print-name');

            // Set Name
            nameEl.value = 'ABC Traders';
            nameEl.dispatchEvent(new Event('input', { bubbles: true }));

            // Set user-defined Alias
            aliasEl.value = 'ABC';
            aliasEl.dispatchEvent(new Event('input', { bubbles: true }));

            // Modify Name again
            nameEl.value = 'ABC Traders Private Limited';
            nameEl.dispatchEvent(new Event('input', { bubbles: true }));

            return {
                name: nameEl.value,
                printName: printEl.value,
                alias: aliasEl.value
            };
        })()
    """)

    assert vals["name"] == "ABC Traders Private Limited"
    assert vals["printName"] == "ABC Traders Private Limited"
    assert vals["alias"] == "ABC"  # Alias was NOT overwritten


def test_req5_saved_name_and_print_name_are_identical():
    """Req 5: Ensure the final saved Print Name matches the saved Name in DB."""
    uid = uuid.uuid4().hex[:6]
    test_name = f"SYNC TEST {uid}"
    user_alias = f"ALIAS-{uid}"

    res = account_service.save_account(COMPANY_ID, {
        "name": test_name,
        "alias": user_alias,
        "group": "Sundry Debtors",
        "customer_category": "Commercial"
    })

    assert res["name"] == test_name.upper()
    assert res["print_name"] == test_name.upper()
    assert res["alias"] == user_alias

    # Verify directly from canonical database table
    with db_manager.get_connection() as conn:
        row = conn.execute(
            "SELECT name, print_name, alias FROM accounts WHERE id = ?;",
            (res["id"],)
        ).fetchone()
        assert row is not None
        assert row[0] == test_name.upper()
        assert row[1] == test_name.upper()  # Saved Print Name matches saved Name
        assert row[2] == user_alias


def test_req6_req7_req8_continuous_add_workflow(web_view):
    """Req 6, 7 & 8: Consecutive master additions keep user on Add screen, reset fields, and focus Name."""
    uid1 = uuid.uuid4().hex[:4]
    uid2 = uuid.uuid4().hex[:4]
    name1 = f"CONT MASTER ONE {uid1}"
    name2 = f"CONT MASTER TWO {uid2}"

    # Step 1: Open Add Account Master
    eval_js(web_view, "openAddAccountMaster();")

    # Step 2: Enter Master 1 and Save
    step1_res = eval_js(web_view, f"""
        (function() {{
            const nameEl = document.getElementById('acc-name');
            const aliasEl = document.getElementById('acc-alias');
            const saveBtn = document.getElementById('btn-acc-save');

            nameEl.value = '{name1}';
            nameEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
            aliasEl.value = 'M1-{uid1}';

            saveBtn.click();

            const activeScreen = document.querySelector('.screen-view.active');
            return {{
                activeScreenId: activeScreen ? activeScreen.id : null,
                isAddScreen: activeScreen && activeScreen.id === 'view-add-account-master'
            }};
        }})()
    """)

    assert step1_res["activeScreenId"] == "view-add-account-master"
    assert step1_res["isAddScreen"] is True

    # Allow async DOM updates and focus
    loop = QEventLoop()
    QTimer.singleShot(200, loop.quit)
    loop.exec_()

    # Verify form was reset and Name field has focus
    form_state1 = eval_js(web_view, """
        (function() {
            const nameEl = document.getElementById('acc-name');
            const aliasEl = document.getElementById('acc-alias');
            const printEl = document.getElementById('acc-print-name');
            const countryEl = document.getElementById('acc-country');
            const stateEl = document.getElementById('acc-state');
            const groupEl = document.getElementById('acc-group');
            const activeElementId = document.activeElement ? document.activeElement.id : null;

            return {
                nameVal: nameEl.value,
                aliasVal: aliasEl.value,
                printNameVal: printEl.value,
                countryVal: countryEl ? countryEl.value : null,
                stateVal: stateEl ? stateEl.value : null,
                groupVal: groupEl ? groupEl.value : null,
                focusedId: activeElementId
            };
        })()
    """)

    assert form_state1["nameVal"] == ""
    assert form_state1["aliasVal"] == ""
    assert form_state1["printNameVal"] == ""
    # Defaults preserved
    assert form_state1["countryVal"] == "India"
    assert form_state1["stateVal"] == "Tamilnadu"
    assert form_state1["groupVal"] == "Sundry Debtors"
    # Name focused
    assert form_state1["focusedId"] == "acc-name"

    # Step 3: Enter Master 2 consecutively without leaving Add Master screen
    step2_res = eval_js(web_view, f"""
        (function() {{
            const nameEl = document.getElementById('acc-name');
            const aliasEl = document.getElementById('acc-alias');
            const saveBtn = document.getElementById('btn-acc-save');

            nameEl.value = '{name2}';
            nameEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
            aliasEl.value = 'M2-{uid2}';

            saveBtn.click();

            const activeScreen = document.querySelector('.screen-view.active');
            return {{
                activeScreenId: activeScreen ? activeScreen.id : null,
                isAddScreen: activeScreen && activeScreen.id === 'view-add-account-master'
            }};
        }})()
    """)

    assert step2_res["activeScreenId"] == "view-add-account-master"
    assert step2_res["isAddScreen"] is True

    # Allow async DOM updates
    loop = QEventLoop()
    QTimer.singleShot(200, loop.quit)
    loop.exec_()

    # Step 4: Verify both masters were successfully saved to database
    with db_manager.get_connection() as conn:
        r1 = conn.execute("SELECT name, print_name FROM accounts WHERE name = ?;", (name1.upper(),)).fetchone()
        r2 = conn.execute("SELECT name, print_name FROM accounts WHERE name = ?;", (name2.upper(),)).fetchone()
        assert r1 is not None, f"First master '{name1}' was not found in DB"
        assert r1[0] == r1[1] == name1.upper()
        assert r2 is not None, f"Second master '{name2}' was not found in DB"
        assert r2[0] == r2[1] == name2.upper()


def test_req9_failed_save_preserves_entered_information(web_view):
    """Req 9: If saving fails, entered information is preserved and form is not cleared."""
    eval_js(web_view, """
        openAddAccountMaster();
        const nameEl = document.getElementById('acc-name');
        const aliasEl = document.getElementById('acc-alias');
        nameEl.value = 'PRESERVED PARTY NAME';
        nameEl.dispatchEvent(new Event('input', { bubbles: true }));
        aliasEl.value = 'PRESERVED ALIAS';
    """)

    # Attempt save with invalid group / simulation
    res = eval_js(web_view, """
        (function() {
            // Temporarily clear group to simulate validation failure
            const groupEl = document.getElementById('acc-group');
            const originalVal = groupEl.value;
            groupEl.value = '';

            // Suppress alert dialog during test
            const origAlert = window.alert;
            let alertMsg = null;
            window.alert = function(msg) { alertMsg = msg; };

            handleSaveAccountMaster();

            window.alert = origAlert;
            groupEl.value = originalVal;

            const nameEl = document.getElementById('acc-name');
            const aliasEl = document.getElementById('acc-alias');
            const printEl = document.getElementById('acc-print-name');
            const activeScreen = document.querySelector('.screen-view.active');

            return {
                alertReceived: alertMsg,
                nameVal: nameEl.value,
                aliasVal: aliasEl.value,
                printNameVal: printEl.value,
                screenId: activeScreen ? activeScreen.id : null
            };
        })()
    """)

    assert res["alertReceived"] is not None
    assert "select an Account Group" in res["alertReceived"]
    # Form data was NOT cleared
    assert res["nameVal"] == "PRESERVED PARTY NAME"
    assert res["aliasVal"] == "PRESERVED ALIAS"
    assert res["printNameVal"] == "PRESERVED PARTY NAME"
    assert res["screenId"] == "view-add-account-master"


def test_req10_item_master_remains_completely_unaffected(web_view):
    """Req 10: Item Master Name, Print Name, and save workflow remain completely unaffected."""
    # 1. Inspect DOM of Item Master
    item_props = eval_js(web_view, """
        (function() {
            const itemNameEl = document.getElementById('item-name');
            const itemPrintEl = document.getElementById('item-print-name');

            return {
                printIsReadOnly: itemPrintEl.readOnly,
                printHasAttr: itemPrintEl.hasAttribute('readonly')
            };
        })()
    """)
    # Item print name must NOT be readonly
    assert item_props["printIsReadOnly"] is False
    assert item_props["printHasAttr"] is False

    # 2. Verify independent editability of Item Name and Item Print Name
    vals = eval_js(web_view, """
        (function() {
            if (typeof resetProductMasterForm === 'function') resetProductMasterForm();
            const itemNameEl = document.getElementById('item-name');
            const itemPrintEl = document.getElementById('item-print-name');

            itemNameEl.value = 'BRITANNIA MILK BIKIS 100G';
            itemNameEl.dispatchEvent(new Event('input', { bubbles: true }));

            // Item Print Name remains empty or can be set independently
            const printAfterName = itemPrintEl.value;

            itemPrintEl.value = 'MILK BIKIS';
            itemPrintEl.dispatchEvent(new Event('input', { bubbles: true }));

            return {
                printAfterName: printAfterName,
                finalPrintName: itemPrintEl.value,
                finalName: itemNameEl.value
            };
        })()
    """)

    # Item Master does NOT auto-populate Print Name
    assert vals["printAfterName"] == ""
    assert vals["finalPrintName"] == "MILK BIKIS"
    assert vals["finalName"] == "BRITANNIA MILK BIKIS 100G"

    # 3. Verify Item Master save workflow still functions via service
    uid = uuid.uuid4().hex[:6]
    item = catalogue_service.save_item(COMPANY_ID, {
        "name": f"UNAFFECTED PRODUCT {uid}",
        "alias": f"SKU-{uid}",
        "print_name": "DIFFERENT PRINT NAME",
        "sales_price": 45.0
    })
    assert item["name"] == f"UNAFFECTED PRODUCT {uid}".upper()

    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT name, print_name FROM items WHERE id = ?;", (item["id"],)).fetchone()
        assert row is not None
        assert row[0] == f"UNAFFECTED PRODUCT {uid}".upper()
        # Item print name preserved its own independent value
        assert row[1] == "DIFFERENT PRINT NAME"
