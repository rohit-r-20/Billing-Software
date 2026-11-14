"""
Comprehensive Automated Test Suite for Alpha Billing V2 Post-Migration Workflows.
Tests the exact 10 core business workflows against PostgreSQL:
1. Add a customer.
2. Add a supplier.
3. Add an item with barcode.
4. Record a purchase.
5. Verify stock increases.
6. Create a sales invoice.
7. Verify stock decreases.
8. Print an invoice.
9. Verify that reprinting does not create another invoice or stock movement.
10. Test database failure and rollback behaviour.
"""

import os
import uuid
import pytest
from decimal import Decimal

from core.configuration import config
from db.database import DatabaseManager, db_manager
from services.account_service import account_service
from services.purchase_service import purchase_service
from services.billing_service import billing_service
from services.inventory_service import inventory_service


PG_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or "postgresql+psycopg://dhvira@localhost:5432/alpha_billing_dev"
PRIMARY_COMPANY_ID = "3a743bcd-8f9a-4154-a316-509cba3de99a"
DEFAULT_BRANCH_ID = "1ebe5b37-4c99-4395-8783-6813eb02b521"


@pytest.fixture(scope="module")
def pg_db():
    mgr = DatabaseManager(database_url=PG_URL)
    conn_info = mgr.test_connection()
    if not conn_info["success"]:
        pytest.skip(f"PostgreSQL database not reachable at {PG_URL}")
    return mgr


@pytest.fixture(scope="module")
def setup_company(pg_db):
    """Ensures primary company and default branch exist in test database."""
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO companies (id, code, name, fin_year, gstin, state, username, password_hash)
            VALUES (?, 'COMP0001', 'ANTI MATRIX', '2026-2027', '33AAAPL1234F1Z1', 'Tamilnadu', 'A', 'hash')
            ON CONFLICT (id) DO NOTHING;
            """,
            (PRIMARY_COMPANY_ID,)
        )
        cursor.execute(
            """
            INSERT INTO branches (id, company_id, code, name, is_default)
            VALUES (?, ?, 'BR001', 'Main Branch', 1)
            ON CONFLICT (id) DO NOTHING;
            """,
            (DEFAULT_BRANCH_ID, PRIMARY_COMPANY_ID)
        )
        cursor.execute(
            """
            INSERT INTO company_configs (company_id, vch_start, vch_digits, vch_prefix)
            VALUES (?, 1, 3, '')
            ON CONFLICT (company_id) DO NOTHING;
            """,
            (PRIMARY_COMPANY_ID,)
        )
        conn.commit()
    return {"company_id": PRIMARY_COMPANY_ID, "branch_id": DEFAULT_BRANCH_ID}


def test_v2_workflow_1_add_customer(pg_db, setup_company):
    """Workflow 1: Add a permanent Customer Master."""
    comp_id = setup_company["company_id"]
    cust_name = f"V2 Test Customer {uuid.uuid4().hex[:6].upper()}"
    cust_data = {
        "name": cust_name,
        "alias": "V2CUST",
        "print_name": cust_name,
        "account_group": "Sundry Debtors",
        "state": "Tamilnadu",
        "dealer_type": "Unregistered",
        "customer_category": "Direct Customer",
        "mobile": "9876543210",
        "op_bal": 0.0,
        "op_type": "Dr"
    }

    res = account_service.save_account(comp_id, cust_data)
    assert res is not None
    assert "id" in res

    # Verify persisted in PostgreSQL (names normalized to uppercase)
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, account_group FROM accounts WHERE id = ?;", (res["id"],))
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == cust_name.upper()
        assert row["account_group"] == "Sundry Debtors"


def test_v2_workflow_2_add_supplier(pg_db, setup_company):
    """Workflow 2: Add a permanent Supplier Master."""
    comp_id = setup_company["company_id"]
    supp_name = f"V2 Test Supplier {uuid.uuid4().hex[:6].upper()}"
    supp_data = {
        "name": supp_name,
        "alias": "V2SUPP",
        "print_name": supp_name,
        "account_group": "Sundry Creditors",
        "state": "Tamilnadu",
        "dealer_type": "Registered",
        "gstin": "33ABCDE1234F1Z5",
        "mobile": "9876543211",
        "op_bal": 1000.0,
        "op_type": "Cr"
    }

    res = account_service.save_account(comp_id, supp_data)
    assert res is not None
    assert "id" in res

    # Verify persisted in both accounts and suppliers tables
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, account_group FROM accounts WHERE id = ?;", (res["id"],))
        acc_row = cursor.fetchone()
        assert acc_row is not None
        assert acc_row["name"] == supp_name.upper()

        cursor.execute("SELECT name, gstin FROM suppliers WHERE id = ?;", (res["id"],))
        supp_row = cursor.fetchone()
        assert supp_row is not None
        assert supp_row["name"] == supp_name.upper()
        assert supp_row["gstin"] == "33ABCDE1234F1Z5"


def test_v2_workflow_3_4_5_add_item_record_purchase_verify_stock(pg_db, setup_company):
    """
    Workflow 3: Add an Item with Barcode.
    Workflow 4: Record a Purchase Invoice.
    Workflow 5: Verify Stock Increases.
    """
    comp_id = setup_company["company_id"]
    item_id = str(uuid.uuid4())
    item_name = f"V2 Test Product {uuid.uuid4().hex[:6].upper()}"
    barcode_val = f"AB{uuid.uuid4().hex[:8].upper()}"

    # 1. Add Item and Barcode (Workflow 3)
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO items (id, company_id, name, print_name, unit, sales_price, purc_price, mrp, is_active)
            VALUES (?, ?, ?, ?, 'Pcs.', 120.0, 100.0, 130.0, 1);
            """,
            (item_id, comp_id, item_name, item_name)
        )
        cursor.execute(
            """
            INSERT INTO item_barcodes (id, item_id, company_id, barcode, is_primary)
            VALUES (?, ?, ?, ?, 1);
            """,
            (str(uuid.uuid4()), item_id, comp_id, barcode_val)
        )
        conn.commit()

    # Verify initial stock is 0
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT current_qty FROM stock_balances WHERE company_id = ? AND item_id = ?;", (comp_id, item_id))
        row = cursor.fetchone()
        initial_qty = row["current_qty"] if row else 0.0
        assert initial_qty == 0.0

    # 2. Record a Purchase (Workflow 4)
    purchase_data = {
        "supplier_name": "Test Wholesale Distributor",
        "supplier_invoice_no": f"PINV-{uuid.uuid4().hex[:6]}",
        "supplier_invoice_date": "2026-11-07",
        "items": [
            {
                "item_id": item_id,
                "item_name": item_name,
                "qty": 50.0,
                "unit": "Pcs.",
                "purchase_rate": 100.0,
                "tax_rate": 18.0
            }
        ]
    }
    purc_res = purchase_service.create_purchase_voucher(company_id=comp_id, data=purchase_data)
    assert purc_res is not None
    assert "voucher_id" in purc_res

    # 3. Verify Stock Increased to 50 (Workflow 5)
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT current_qty FROM stock_balances WHERE company_id = ? AND item_id = ?;", (comp_id, item_id))
        row = cursor.fetchone()
        assert row is not None
        assert row["current_qty"] == 50.0

        cursor.execute("SELECT movement_type, qty FROM stock_movements WHERE company_id = ? AND item_id = ?;", (comp_id, item_id))
        mov = cursor.fetchone()
        assert mov is not None
        assert mov["movement_type"] == "PURCHASE"
        assert mov["qty"] == 50.0


def test_v2_workflow_6_7_sales_invoice_and_stock_decrease(pg_db, setup_company):
    """
    Workflow 6: Create a Sales Invoice.
    Workflow 7: Verify Stock Decreases.
    """
    comp_id = setup_company["company_id"]
    item_id = str(uuid.uuid4())
    item_name = f"V2 Sales Item {uuid.uuid4().hex[:6].upper()}"

    # Initial stock: 100 units
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO items (id, company_id, name, unit, sales_price) VALUES (?, ?, ?, 'Pcs.', 200.0);",
            (item_id, comp_id, item_name)
        )
        cursor.execute(
            """
            INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
            VALUES (?, ?, ?, ?, 100.0)
            ON CONFLICT (branch_id, item_id) DO UPDATE SET current_qty = 100.0;
            """,
            (str(uuid.uuid4()), comp_id, DEFAULT_BRANCH_ID, item_id)
        )
        conn.commit()

    # Sell 20 units (Workflow 6)
    sale_items = [
        {
            "item_id": item_id,
            "item_name": item_name,
            "qty": 20.0,
            "price": 200.0,
            "unit": "Pcs.",
            "tax_rate": 18.0
        }
    ]
    sale_res = billing_service.create_sale_invoice(
        company_id=comp_id,
        items=sale_items,
        party_name="CASH"
    )
    assert sale_res is not None
    assert "id" in sale_res
    vch_no = sale_res["vch_no"]

    # Verify Stock Decreased from 100 to 80 (Workflow 7)
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT current_qty FROM stock_balances WHERE company_id = ? AND item_id = ?;", (comp_id, item_id))
        row = cursor.fetchone()
        assert row["current_qty"] == 80.0

        # Verify stock movement record (keyed by reference_id = vch_no)
        cursor.execute("SELECT movement_type, qty FROM stock_movements WHERE reference_id = ? AND item_id = ?;", (vch_no, item_id))
        mov = cursor.fetchone()
        assert mov is not None
        assert mov["movement_type"] == "SALE"
        assert mov["qty"] == -20.0


def test_v2_workflow_8_9_print_reprint_invoice_idempotence(pg_db, setup_company):
    """
    Workflow 8: Print an invoice.
    Workflow 9: Verify reprinting does not create another invoice or stock movement.
    """
    comp_id = setup_company["company_id"]
    item_id = str(uuid.uuid4())
    item_name = f"V2 Reprint Item {uuid.uuid4().hex[:6].upper()}"

    # Setup 10 units stock
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO items (id, company_id, name, unit, sales_price) VALUES (?, ?, ?, 'Pcs.', 50.0);",
            (item_id, comp_id, item_name)
        )
        cursor.execute(
            "INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty) VALUES (?, ?, ?, ?, 10.0);",
            (str(uuid.uuid4()), comp_id, DEFAULT_BRANCH_ID, item_id)
        )
        conn.commit()

    # Create Invoice
    sale_res = billing_service.create_sale_invoice(
        company_id=comp_id,
        items=[{"item_id": item_id, "item_name": item_name, "qty": 2.0, "price": 50.0}],
        party_name="CASH"
    )
    vch_id = sale_res["id"]

    # Count invoices and stock movements before print
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM sales_vouchers WHERE company_id = ?;", (comp_id,))
        vch_count_before = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM stock_movements WHERE company_id = ?;", (comp_id,))
        mov_count_before = cursor.fetchone()[0]
        cursor.execute("SELECT current_qty FROM stock_balances WHERE company_id = ? AND item_id = ?;", (comp_id, item_id))
        stock_before = cursor.fetchone()["current_qty"]
        assert stock_before == 8.0

    # Workflow 8: Print Invoice
    print_res1 = billing_service.print_invoice(company_id=comp_id, vch_id=vch_id, copies=1)
    assert print_res1["success"] is True

    # Workflow 9: Reprint Invoice (Multiple times)
    print_res2 = billing_service.print_invoice(company_id=comp_id, vch_id=vch_id, copies=2)
    assert print_res2["success"] is True
    print_res3 = billing_service.print_invoice(company_id=comp_id, vch_id=vch_id, copies=1)
    assert print_res3["success"] is True

    # Verify that counts and stock have NOT changed
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM sales_vouchers WHERE company_id = ?;", (comp_id,))
        vch_count_after = cursor.fetchone()[0]
        assert vch_count_after == vch_count_before, "Reprinting must NOT create new sales vouchers!"

        cursor.execute("SELECT count(*) FROM stock_movements WHERE company_id = ?;", (comp_id,))
        mov_count_after = cursor.fetchone()[0]
        assert mov_count_after == mov_count_before, "Reprinting must NOT create additional stock movements!"

        cursor.execute("SELECT current_qty FROM stock_balances WHERE company_id = ? AND item_id = ?;", (comp_id, item_id))
        stock_after = cursor.fetchone()["current_qty"]
        assert stock_after == stock_before, "Reprinting must NOT alter inventory balances!"


def test_v2_workflow_10_database_failure_and_rollback(pg_db, setup_company):
    """
    Workflow 10: Test database failure and transaction rollback behaviour.
    Simulates a failure during a multi-line invoice insertion:
    Asserts that the transaction rolls back cleanly, leaving invoice count and stock balances unchanged.
    """
    comp_id = setup_company["company_id"]
    item_id = str(uuid.uuid4())
    item_name = f"V2 Rollback Item {uuid.uuid4().hex[:6].upper()}"

    # Setup 50 units stock
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO items (id, company_id, name, unit, sales_price) VALUES (?, ?, ?, 'Pcs.', 100.0);",
            (item_id, comp_id, item_name)
        )
        cursor.execute(
            "INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty) VALUES (?, ?, ?, ?, 50.0);",
            (str(uuid.uuid4()), comp_id, DEFAULT_BRANCH_ID, item_id)
        )
        conn.commit()

    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM sales_vouchers WHERE company_id = ?;", (comp_id,))
        vch_count_initial = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM stock_movements WHERE company_id = ?;", (comp_id,))
        mov_count_initial = cursor.fetchone()[0]

    # Attempt a broken transaction (e.g. invalid non-existent foreign key or forced error)
    with pytest.raises(Exception):
        with pg_db.get_connection() as conn:
            cursor = conn.cursor()
            # 1. First insert voucher
            faulty_vch_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO sales_vouchers (id, company_id, vch_no, vch_date, sale_type, party_name, subtotal, taxable_amount, grand_total)
                VALUES (?, ?, 'FAIL_VCH_01', '2026-11-07', 'L/GST-18%', 'Cash', 100.0, 100.0, 100.0);
                """,
                (faulty_vch_id, comp_id)
            )
            # 2. Deduct stock
            cursor.execute(
                "UPDATE stock_balances SET current_qty = current_qty - 10 WHERE company_id = ? AND item_id = ?;",
                (comp_id, item_id)
            )
            # 3. Trigger intentional violation: insert line with non-existent foreign key company_id or unique violation
            cursor.execute(
                """
                INSERT INTO sales_vouchers (id, company_id, vch_no, vch_date, sale_type, party_name, subtotal, taxable_amount, grand_total)
                VALUES (?, 'NON_EXISTENT_COMPANY_ID_VIOLATING_FK', 'FAIL_VCH_02', '2026-11-07', 'L/GST-18%', 'Cash', 100.0, 100.0, 100.0);
                """,
                (str(uuid.uuid4()),)
            )
            conn.commit()

    # Verify rollback succeeded: stock and voucher counts are completely unchanged
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM sales_vouchers WHERE company_id = ?;", (comp_id,))
        assert cursor.fetchone()[0] == vch_count_initial, "Rolled back voucher must NOT exist!"

        cursor.execute("SELECT current_qty FROM stock_balances WHERE company_id = ? AND item_id = ?;", (comp_id, item_id))
        assert cursor.fetchone()["current_qty"] == 50.0, "Stock must remain unchanged after transaction rollback!"
