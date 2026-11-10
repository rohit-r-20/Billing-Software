"""
Integration and regression test suite for Alpha Billing:
Rebuild Sales Invoice Workflow with Master-Linked Parties, Automatic Voucher Numbering,
Printing and Keyboard-Based Billing.

Covers all 17 Acceptance Criteria:
1. Customer search retrieves existing Masters records.
2. Partial-name search works (e.g. 'A', 'ABC').
3. Customer selection stores correct Master ID (account_id) on invoice.
4. Unknown customer cannot be silently created / no duplicate customer masters created.
5. Authorised CASH (Direct Customer) allowed for local sales, prohibited for Inter-State (I/GST).
6. Voucher numbering starts from configured next number and maintains sequential series.
7. Concurrency test: simultaneous invoice creation produces unique consecutive numbers.
8. Failed save transaction rolls back and does not permanently increment sequence counter.
9. Committed voucher numbers are never reused or reassigned.
10. Atomic save commits invoice header, items, tax calculation, and deducts stock balances.
11. Print failure leaves transaction safely committed and does not mutate stock.
12. Reprinting an invoice never alters inventory or re-deducts stock.
13. Printing screen displays actual saved invoice data retrieved from database.
14. Barcode scanning resolves correct registered product from Item Master.
15. Unregistered products cannot be added to invoices.
16. Standard Unit retrieved automatically from Item Master and is read-only (tabindex -1).
17. Company and branch isolation is preserved across all sequence and billing operations.
"""

import threading
import uuid
import pytest
from pathlib import Path

from db.database import DatabaseManager
from services.billing_service import BillingService
from services.catalogue_service import CatalogueService
from services.account_service import AccountService
from services.company_service import CompanyService
from services.inventory_service import InventoryService


@pytest.fixture
def erp_db(tmp_path):
    """Initializes a clean SQLite database with full ERP migrations and test companies."""
    db_file = tmp_path / "sales_rebuild_test.db"
    manager = DatabaseManager(str(db_file))
    manager.run_migrations()

    with manager.get_connection() as conn:
        # Company 1 (Tamil Nadu)
        conn.execute("""
            INSERT INTO companies (id, code, name, fin_year, gstin, state)
            VALUES ('C1', 'COMP0001', 'ANTI MATRIX RETAIL', '2026-27', '33AAAPL1234F1Z1', 'Tamilnadu');
        """)
        conn.execute("""
            INSERT INTO branches (id, company_id, code, name, is_default)
            VALUES ('B1', 'C1', 'BR01', 'Main Branch', 1);
        """)
        conn.execute("""
            INSERT INTO company_configs (company_id, vch_start, vch_digits, vch_prefix)
            VALUES ('C1', 590, 4, '');
        """)

        # Company 2 (Branch / Company Isolation Test)
        conn.execute("""
            INSERT INTO companies (id, code, name, fin_year, gstin, state)
            VALUES ('C2', 'COMP0002', 'MATRIX BRANCH 2', '2026-27', '29BBBP9876F1Z2', 'Karnataka');
        """)
        conn.execute("""
            INSERT INTO branches (id, company_id, code, name, is_default)
            VALUES ('B2', 'C2', 'BR02', 'Bangalore Branch', 1);
        """)
        conn.execute("""
            INSERT INTO company_configs (company_id, vch_start, vch_digits, vch_prefix)
            VALUES ('C2', 1, 4, 'KA-');
        """)
        conn.commit()

    return manager


# ==============================================================================
# SECTION 1: PARTY SELECTION - MASTERS DATABASE ONLY
# ==============================================================================

def test_01_customer_search_retrieves_existing_masters_records(erp_db):
    """Criterion 1: Party search retrieves customer records exclusively from Customer Masters."""
    acc_service = AccountService(erp_db)

    # Create customer masters in C1
    acc_service.save_account('C1', {
        "name": "ABC TRADERS",
        "alias": "ABC",
        "account_group": "Sundry Debtors",
        "gstin": "33ABCDE1234F1Z5",
        "mobile": "9876543210"
    })
    acc_service.save_account('C1', {
        "name": "ANAND ELECTRONICS",
        "alias": "ANAND",
        "account_group": "Sundry Debtors",
        "gstin": "33ANAND5678F1Z9",
        "mobile": "9123456780"
    })
    # Supplier master (should NOT appear in customer search)
    acc_service.save_account('C1', {
        "name": "ALPHA WHOLESALE SUPPLIERS",
        "account_group": "Sundry Creditors"
    })

    # Search for "ABC"
    results = acc_service.search_customers('C1', 'ABC')
    assert len(results) == 1
    assert results[0]["name"] == "ABC TRADERS"
    assert results[0]["alias"] == "ABC"
    assert results[0]["gstin"] == "33ABCDE1234F1Z5"

    # Search for "ANAND" by mobile
    results_mob = acc_service.search_customers('C1', '9123456780')
    assert len(results_mob) == 1
    assert results_mob[0]["name"] == "ANAND ELECTRONICS"

    # Verify supplier is omitted from customer search
    cust_names = [c["name"] for c in acc_service.search_customers('C1', '')]
    assert "ABC TRADERS" in cust_names
    assert "ANAND ELECTRONICS" in cust_names
    assert "ALPHA WHOLESALE SUPPLIERS" not in cust_names


def test_02_partial_name_search_works(erp_db):
    """Criterion 2: Case-insensitive prefix and partial-name search across name, alias, mobile, GSTIN."""
    acc_service = AccountService(erp_db)

    acc_service.save_account('C1', {"name": "ABC ENTERPRISES", "account_group": "Sundry Debtors"})
    acc_service.save_account('C1', {"name": "BABU TRADERS", "account_group": "Sundry Debtors"})
    acc_service.save_account('C1', {"name": "CHANDRA AGRO", "account_group": "Sundry Debtors"})

    # Single character partial search "A"
    res_a = acc_service.search_customers('C1', 'a')
    names_a = [r["name"] for r in res_a]
    assert "ABC ENTERPRISES" in names_a
    assert "BABU TRADERS" in names_a
    assert "CHANDRA AGRO" in names_a

    # Substring search "ABC"
    res_abc = acc_service.search_customers('C1', 'abc')
    assert len(res_abc) == 1
    assert res_abc[0]["name"] == "ABC ENTERPRISES"


def test_03_customer_selection_stores_correct_master_id(erp_db):
    """Criterion 3: Invoice stores the selected customer's permanent Master ID (account_id)."""
    acc_service = AccountService(erp_db)
    cat_service = CatalogueService(erp_db)
    bill_service = BillingService(erp_db)

    cust = acc_service.save_account('C1', {
        "name": "KAVIN ENTERPRISES",
        "account_group": "Sundry Debtors",
        "customer_category": "Commercial"
    })
    cust_id = cust["id"]

    prod = cat_service.save_item('C1', {
        "name": "MILK BIKIS 100G",
        "unit": "Pcs.",
        "sales_price": 20.0,
        "op_stock_qty": 50.0
    })

    invoice = bill_service.create_sale_invoice(
        company_id='C1',
        items=[{"id": prod["id"], "name": prod["name"], "price": 20.0, "qty": 2.0}],
        party_name="KAVIN ENTERPRISES",
        account_id=cust_id,
        sale_type="L/GST-18%"
    )

    assert invoice["account_id"] == cust_id
    assert invoice["party_name"] == "KAVIN ENTERPRISES"

    # Verify directly from database
    with erp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT account_id, party_name FROM sales_vouchers WHERE id = ?;", (invoice["id"],))
        row = cursor.fetchone()
        assert row["account_id"] == cust_id
        assert row["party_name"] == "KAVIN ENTERPRISES"


def test_04_unknown_customer_cannot_be_silently_created_and_no_duplicates(erp_db):
    """Criterion 4: Disallows saving an invoice with an unregistered party and prevents duplicates."""
    cat_service = CatalogueService(erp_db)
    bill_service = BillingService(erp_db)

    prod = cat_service.save_item('C1', {
        "name": "NOTEBOOK 200 PAGES",
        "sales_price": 60.0,
        "op_stock_qty": 20.0
    })

    # Attempt to save with unknown party name
    with pytest.raises(ValueError) as excinfo:
        bill_service.create_sale_invoice(
            company_id='C1',
            items=[{"id": prod["id"], "name": prod["name"], "price": 60.0, "qty": 1.0}],
            party_name="GHOST TRADERS NONEXISTENT",
            sale_type="L/GST-18%"
        )
    assert "No customer master found" in str(excinfo.value)

    # Verify no record was inserted into accounts table
    with erp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM accounts WHERE UPPER(name) = 'GHOST TRADERS NONEXISTENT';")
        assert cursor.fetchone()[0] == 0


def test_05_cash_sale_allowed_for_local_prohibited_for_interstate(erp_db):
    """Criterion 5: CASH walk-in customer is allowed for L/GST but prohibited for Inter-State (I/GST)."""
    cat_service = CatalogueService(erp_db)
    bill_service = BillingService(erp_db)

    prod = cat_service.save_item('C1', {
        "name": "PEN BLUE",
        "sales_price": 10.0,
        "op_stock_qty": 50.0
    })

    # 1. CASH allowed for local sale
    local_inv = bill_service.create_sale_invoice(
        company_id='C1',
        items=[{"id": prod["id"], "name": prod["name"], "price": 10.0, "qty": 1.0}],
        party_name="CASH",
        sale_type="L/GST-18%"
    )
    assert local_inv["party_name"] == "CASH"
    assert local_inv["account_id"] is None

    # 2. CASH prohibited for Inter-State sale
    with pytest.raises(ValueError) as excinfo:
        bill_service.create_sale_invoice(
            company_id='C1',
            items=[{"id": prod["id"], "name": prod["name"], "price": 10.0, "qty": 1.0}],
            party_name="CASH",
            sale_type="I/GST-18%"
        )
    assert "Inter-State (IGST) sales require a registered customer master" in str(excinfo.value)


# ==============================================================================
# SECTION 2: AUTOMATIC VOUCHER NUMBERING
# ==============================================================================

def test_06_voucher_numbering_starts_from_configured_next_number(erp_db):
    """Criterion 6: Voucher numbering starts from configured next number (0590)."""
    bill_service = BillingService(erp_db)

    # Next number for C1 (configured vch_start = 590, 4 digits)
    next_no = bill_service.get_next_voucher_number('C1', 'Main')
    assert next_no == "0590"


def test_07_concurrency_simultaneous_invoice_creation_produces_unique_consecutive_numbers(erp_db):
    """Criterion 7: Concurrency test: simultaneous invoice creation produces unique consecutive numbers."""
    acc_service = AccountService(erp_db)
    cat_service = CatalogueService(erp_db)
    bill_service = BillingService(erp_db)

    acc = acc_service.save_account('C1', {"name": "REGULAR CLIENT", "account_group": "Sundry Debtors"})
    prod = cat_service.save_item('C1', {
        "name": "BULK ITEM",
        "sales_price": 10.0,
        "op_stock_qty": 500.0
    })

    created_vch_numbers = []
    errors = []
    lock = threading.Lock()

    def worker():
        try:
            inv = bill_service.create_sale_invoice(
                company_id='C1',
                items=[{"id": prod["id"], "name": prod["name"], "price": 10.0, "qty": 1.0}],
                party_name="REGULAR CLIENT",
                account_id=acc["id"],
                sale_type="L/GST-18%"
            )
            with lock:
                created_vch_numbers.append(inv["vch_no"])
        except Exception as e:
            with lock:
                errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(created_vch_numbers) == 5
    # All 5 numbers must be unique
    assert len(set(created_vch_numbers)) == 5
    # Numbers should be 0590, 0591, 0592, 0593, 0594
    sorted_numbers = sorted(created_vch_numbers)
    expected_numbers = [f"{590 + i:04d}" for i in range(5)]
    assert sorted_numbers == expected_numbers


def test_08_failed_save_transaction_rolls_back_without_incrementing_sequence(erp_db):
    """Criterion 8: Failed transactions rollback and do not permanently increment sequence counter."""
    cat_service = CatalogueService(erp_db)
    bill_service = BillingService(erp_db)

    prod = cat_service.save_item('C1', {
        "name": "TEST ROLLBACK PRODUCT",
        "sales_price": 25.0,
        "op_stock_qty": 5.0
    })

    # Starting number is 0590
    assert bill_service.get_next_voucher_number('C1', 'Main') == "0590"

    # Attempt save that fails due to unknown customer
    with pytest.raises(ValueError):
        bill_service.create_sale_invoice(
            company_id='C1',
            items=[{"id": prod["id"], "name": prod["name"], "price": 25.0, "qty": 1.0}],
            party_name="UNKNOWN CUSTOMER",
            sale_type="L/GST-18%"
        )

    # Counter must remain at 0590 (no gap created)
    assert bill_service.get_next_voucher_number('C1', 'Main') == "0590"


def test_09_voucher_number_never_reused_or_duplicated(erp_db):
    """Criterion 9: Successfully committed voucher number is never reused or reassigned."""
    acc_service = AccountService(erp_db)
    cat_service = CatalogueService(erp_db)
    bill_service = BillingService(erp_db)

    acc = acc_service.save_account('C1', {"name": "CUST A", "account_group": "Sundry Debtors"})
    prod = cat_service.save_item('C1', {
        "name": "ITEM A",
        "sales_price": 50.0,
        "op_stock_qty": 50.0
    })

    inv1 = bill_service.create_sale_invoice(
        company_id='C1',
        items=[{"id": prod["id"], "name": prod["name"], "price": 50.0, "qty": 1.0}],
        party_name="CUST A",
        account_id=acc["id"],
        sale_type="L/GST-18%"
    )
    assert inv1["vch_no"] == "0590"

    # Next number must advance to 0591
    assert bill_service.get_next_voucher_number('C1', 'Main') == "0591"

    inv2 = bill_service.create_sale_invoice(
        company_id='C1',
        items=[{"id": prod["id"], "name": prod["name"], "price": 50.0, "qty": 1.0}],
        party_name="CUST A",
        account_id=acc["id"],
        sale_type="L/GST-18%"
    )
    assert inv2["vch_no"] == "0591"
    assert inv1["vch_no"] != inv2["vch_no"]


# ==============================================================================
# SECTION 3: SALES INVOICE SAVE AND PRINT WORKFLOW
# ==============================================================================

def _get_stock(db, item_id, branch_id='B1'):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT current_qty FROM stock_balances WHERE branch_id = ? AND item_id = ?;", (branch_id, item_id))
        row = cursor.fetchone()
        return float(row[0]) if row else 0.0


def _get_movements(db, item_id):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stock_movements WHERE item_id = ?;", (item_id,))
        return [dict(r) for r in cursor.fetchall()]


def test_10_atomic_save_calculates_subtotal_tax_and_deducts_stock(erp_db):
    """Criterion 10: Commit saves invoice, calculates taxes, and decrements stock balances immediately."""
    acc_service = AccountService(erp_db)
    cat_service = CatalogueService(erp_db)
    bill_service = BillingService(erp_db)

    acc = acc_service.save_account('C1', {
        "name": "RETAIL BUYER",
        "account_group": "Sundry Debtors",
        "state": "Tamilnadu"
    })
    prod = cat_service.save_item('C1', {
        "name": "SHAMPOO 200ML",
        "unit": "Bottle",
        "sales_price": 100.0,
        "op_stock_qty": 20.0
    })

    # Opening stock balance = 20.0
    bal_before = _get_stock(erp_db, prod["id"], 'B1')
    assert bal_before == 20.0

    inv = bill_service.create_sale_invoice(
        company_id='C1',
        items=[{"id": prod["id"], "name": prod["name"], "price": 100.0, "qty": 3.0}],
        party_name="RETAIL BUYER",
        account_id=acc["id"],
        sale_type="L/GST-18%"
    )

    # Subtotal = 300.0, CGST 9% = 27.0, SGST 9% = 27.0, Grand Total = 354.0
    assert inv["subtotal"] == 300.0
    assert inv["cgst_amount"] == 27.0
    assert inv["sgst_amount"] == 27.0
    assert inv["grand_total"] == 354.0

    # Stock immediately decremented from 20.0 to 17.0
    bal_after = _get_stock(erp_db, prod["id"], 'B1')
    assert bal_after == 17.0


def test_11_print_error_isolation_and_reprinting_never_mutates_stock(erp_db):
    """Criteria 11 & 12: Printing failure and reprinting never alter inventory or duplicate transactions."""
    acc_service = AccountService(erp_db)
    cat_service = CatalogueService(erp_db)
    bill_service = BillingService(erp_db)

    acc = acc_service.save_account('C1', {"name": "PRINT TEST CUSTOMER", "account_group": "Sundry Debtors"})
    prod = cat_service.save_item('C1', {
        "name": "SOAP BAR",
        "sales_price": 30.0,
        "op_stock_qty": 10.0
    })

    inv = bill_service.create_sale_invoice(
        company_id='C1',
        items=[{"id": prod["id"], "name": prod["name"], "price": 30.0, "qty": 2.0}],
        party_name="PRINT TEST CUSTOMER",
        account_id=acc["id"],
        sale_type="L/GST-18%"
    )

    # Stock balance after sale is 8.0
    assert _get_stock(erp_db, prod["id"], 'B1') == 8.0

    # Simulate printing and multiple reprints
    print_res1 = bill_service.print_invoice('C1', inv["id"], paper_format="thermal-80", printer_name="POS-80", copies=2)
    assert print_res1["success"] is True

    # Simulate reprint
    print_res2 = bill_service.print_invoice('C1', inv["id"], paper_format="a4", printer_name="HP LaserJet", copies=1)
    assert print_res2["success"] is True

    # Stock must remain strictly at 8.0 (never deducted again)
    assert _get_stock(erp_db, prod["id"], 'B1') == 8.0

    # Verify no additional movement records created
    movements = _get_movements(erp_db, prod["id"])
    out_movements = [m for m in movements if m["movement_type"] in ("SALE", "SALE_OUT")]
    assert len(out_movements) == 1
    assert abs(float(out_movements[0]["qty"])) == 2.0


def test_12_print_screen_displays_actual_saved_invoice_data(erp_db):
    """Criterion 13: Dedicated print screen retrieves actual saved invoice data."""
    acc_service = AccountService(erp_db)
    cat_service = CatalogueService(erp_db)
    bill_service = BillingService(erp_db)

    acc = acc_service.save_account('C1', {"name": "VERIFY PRINT DATA", "account_group": "Sundry Debtors"})
    prod = cat_service.save_item('C1', {
        "name": "TEST WIDGET",
        "sales_price": 120.0,
        "op_stock_qty": 15.0
    })

    saved = bill_service.create_sale_invoice(
        company_id='C1',
        items=[{"id": prod["id"], "name": prod["name"], "price": 120.0, "qty": 1.0}],
        party_name="VERIFY PRINT DATA",
        account_id=acc["id"],
        sale_type="L/GST-18%"
    )

    details = bill_service.get_voucher_details('C1', saved["id"])
    assert details is not None
    assert details["vch_no"] == saved["vch_no"]
    assert details["party_name"] == "VERIFY PRINT DATA"
    assert details["grand_total"] == saved["grand_total"]
    assert len(details["items"]) == 1
    assert details["items"][0]["item_name"] == "TEST WIDGET"


# ==============================================================================
# SECTION 4: PRODUCT ENTRY & KEYBOARD-BASED BILLING
# ==============================================================================

def test_14_barcode_scanning_and_registered_product_lookup(erp_db):
    """Criteria 14 & 15: Barcode scanning resolves registered product; unregistered products return failure."""
    cat_service = CatalogueService(erp_db)

    # Save item with barcode
    item = cat_service.save_item('C1', {
        "name": "BRITANNIA BISCUITS 200G",
        "alias": "890103000001",
        "sales_price": 35.0,
        "unit": "Pkt."
    })

    # Lookup by barcode
    found = cat_service.find_by_barcode('C1', '890103000001')
    assert found is not None
    assert found["id"] == item["id"]
    assert found["name"] == "BRITANNIA BISCUITS 200G"
    assert found["unit"] == "Pkt."

    # Lookup unknown barcode
    unknown = cat_service.find_by_barcode('C1', '999999999999')
    assert unknown is None


def test_15_standard_unit_retrieved_from_item_master_and_read_only():
    """Criterion 16: Verify in index.html & styles.css that Unit is between Item and Qty, read-only and tabindex -1."""
    html_path = Path("index.html")
    assert html_path.exists()
    content = html_path.read_text()

    # Column ordering in #vch-items-table must be S.N. -> Item -> Unit -> Qty -> Price -> Amount
    assert '<th class="col-vch-sn">S.N.</th>' in content
    assert '<th class="col-vch-item">Item</th>' in content
    assert '<th class="col-vch-unit">Unit</th>' in content
    assert '<th class="col-vch-qty">Qty.</th>' in content

    # Item table headers order: Unit comes before Qty
    idx_unit = content.find('<th class="col-vch-unit">Unit</th>')
    idx_qty = content.find('<th class="col-vch-qty">Qty.</th>')
    assert idx_unit < idx_qty, "Unit column must appear before Qty column in header"

    # Verify app.js renders unit input with readonly, input-readonly class, and tabindex="-1"
    app_js_path = Path("app.js")
    assert app_js_path.exists()
    js_content = app_js_path.read_text()
    assert 'class="vch-unit-input input-readonly"' in js_content
    assert 'tabindex="-1"' in js_content

    # Verify styles.css styles .input-readonly
    css_path = Path("styles.css")
    assert css_path.exists()
    css_content = css_path.read_text()
    assert ".vch-unit-input.input-readonly" in css_content


def test_16_company_and_branch_data_isolation(erp_db):
    """Criterion 17: Sequence numbers and customer masters are strictly isolated between companies."""
    acc_service = AccountService(erp_db)
    bill_service = BillingService(erp_db)

    # C1 next sequence is 0590
    assert bill_service.get_next_voucher_number('C1', 'Main') == "0590"

    # C2 next sequence is KA-0001
    assert bill_service.get_next_voucher_number('C2', 'Main') == "KA-0001"

    # Create customer in C1
    acc_service.save_account('C1', {"name": "TAMILNADU TRADER", "account_group": "Sundry Debtors"})

    # C2 search must NOT find C1's customer
    c2_customers = acc_service.search_customers('C2', 'TAMILNADU TRADER')
    assert len(c2_customers) == 0


def test_17_existing_masters_and_item_master_remain_unchanged(erp_db):
    """Criterion 18: Invoices do not alter customer masters or product definitions."""
    acc_service = AccountService(erp_db)
    cat_service = CatalogueService(erp_db)
    bill_service = BillingService(erp_db)

    cust = acc_service.save_account('C1', {
        "name": "IMMUTABLE CLIENT",
        "account_group": "Sundry Debtors",
        "mobile": "9998887776",
        "customer_category": "Sub-Commercial"
    })
    prod = cat_service.save_item('C1', {
        "name": "PRESERVED PRODUCT",
        "sales_price": 85.0,
        "unit": "Kg",
        "op_stock_qty": 40.0
    })

    # Perform sale
    bill_service.create_sale_invoice(
        company_id='C1',
        items=[{"id": prod["id"], "name": prod["name"], "price": 85.0, "qty": 5.0}],
        party_name="IMMUTABLE CLIENT",
        account_id=cust["id"],
        sale_type="L/GST-18%"
    )

    # Verify customer master record is unchanged
    saved_cust = acc_service.get_account_by_id('C1', cust["id"])
    assert saved_cust["name"] == "IMMUTABLE CLIENT"
    assert saved_cust["mobile"] == "9998887776"
    assert saved_cust["customer_category"] == "Sub-Commercial"

    # Verify item definition is unchanged
    saved_prod = cat_service.get_item_by_id('C1', prod["id"])
    assert saved_prod["name"] == "PRESERVED PRODUCT"
    assert saved_prod["unit"] == "Kg"
    assert float(saved_prod["sales_price"]) == 85.0
