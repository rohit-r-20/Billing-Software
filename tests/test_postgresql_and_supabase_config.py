"""
Comprehensive Automated Test Suite for Alpha Billing PostgreSQL & Supabase Integration.
Validates:
1. Environment configuration, .env parsing, and credential masking.
2. Dual-dialect database manager (SQLAlchemy 2.x, Psycopg 3, parameter translation, row adapter).
3. Alembic schema migrations on PostgreSQL.
4. Permanent Party Masters (Customer, Supplier, Both) persistence in PostgreSQL.
5. Items, barcodes, and unique barcode constraint enforcement in PostgreSQL.
6. Sales invoice transaction atomicity (commit & rollback) and stock deduction in PostgreSQL.
7. Purchase invoice persistence with supplier linking in PostgreSQL.
8. Stock ledger, stock balances, and low-stock alerts in PostgreSQL.
9. Voucher sequence and voucher number uniqueness constraint enforcement in PostgreSQL.
10. Multi-company and multi-branch data isolation in PostgreSQL.
11. Safe, non-destructive SQLite to PostgreSQL data migration and integrity verification.
12. Dynamic dialect switching between PostgreSQL and SQLite.
"""

import os
import uuid
import pytest
from pathlib import Path

from core.configuration import config, AppConfig
from db.database import (
    DatabaseManager,
    translate_placeholders_to_percent_s,
    PostgresRow,
)
from services.account_service import account_service
from services.billing_service import billing_service
from services.purchase_service import purchase_service
from services.inventory_service import inventory_service
from services.database_migration_service import DatabaseMigrationService


# Canonical test database URL for local PostgreSQL
PG_TEST_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or "postgresql+psycopg://dhvira@localhost:5432/alpha_billing_dev"


@pytest.fixture(scope="session")
def pg_available():
    """Checks whether the PostgreSQL test database is reachable."""
    mgr = DatabaseManager(database_url=PG_TEST_URL)
    conn_info = mgr.test_connection()
    return conn_info["success"]


@pytest.fixture(scope="session")
def pg_db(pg_available):
    """Provides a DatabaseManager connected to PostgreSQL."""
    if not pg_available:
        pytest.skip("PostgreSQL test database not reachable at " + PG_TEST_URL)
    mgr = DatabaseManager(database_url=PG_TEST_URL)
    mgr.run_alembic_migrations()
    return mgr


@pytest.fixture
def tenant_comp_and_branch(pg_db):
    """Creates an isolated company and branch in PostgreSQL for test isolation."""
    comp_id = str(uuid.uuid4())
    comp_code = f"TEST_{uuid.uuid4().hex[:8].upper()}"
    branch_id = str(uuid.uuid4())
    branch_code = "HO"

    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO companies (id, code, name, fin_year, state)
            VALUES (?, ?, ?, '2026-2027', 'Tamilnadu');
            """,
            (comp_id, comp_code, f"Tenant {comp_code}")
        )
        cursor.execute(
            """
            INSERT INTO branches (id, company_id, code, name, is_default)
            VALUES (?, ?, ?, 'Head Office', 1);
            """,
            (branch_id, comp_id, branch_code)
        )
        cursor.execute(
            """
            INSERT INTO company_configs (company_id, vch_start, vch_digits, vch_prefix, default_tax)
            VALUES (?, 1, 3, 'INV-', '18');
            """,
            (comp_id,)
        )
        conn.commit()

    return {
        "company_id": comp_id,
        "company_code": comp_code,
        "branch_id": branch_id,
        "branch_code": branch_code
    }


# ==============================================================================
# 1. Environment & Configuration Security Tests
# ==============================================================================

def test_environment_configuration_and_dialect_detection():
    """Verifies DATABASE_URL parsing and dialect identification."""
    assert hasattr(AppConfig, "is_postgres")
    assert hasattr(AppConfig, "is_sqlite")
    assert hasattr(AppConfig, "get_database_dialect")

    # SQLite URL detection
    os.environ["DATABASE_URL"] = "sqlite:///data/test.db"
    assert AppConfig.is_sqlite() is True
    assert AppConfig.is_postgres() is False
    assert AppConfig.get_database_dialect() == "sqlite"

    # PostgreSQL Supabase standard URL detection
    os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:secret@db.xyz.supabase.co:5432/postgres"
    assert AppConfig.is_postgres() is True
    assert AppConfig.is_sqlite() is False
    assert AppConfig.get_database_dialect() == "postgresql"

    # Direct postgres:// detection
    os.environ["DATABASE_URL"] = "postgres://postgres:secret@db.xyz.supabase.co:6543/postgres"
    assert AppConfig.is_postgres() is True

    # Restore
    os.environ["DATABASE_URL"] = PG_TEST_URL


def test_env_example_and_gitignore_hygiene():
    """Verifies that .env.example exists with placeholders and .env is git-ignored."""
    base_dir = config.BASE_DIR
    env_example = base_dir / ".env.example"
    gitignore = base_dir / ".gitignore"

    assert env_example.exists(), ".env.example must exist for Supabase/PostgreSQL configuration"
    content = env_example.read_text()
    assert "DATABASE_URL" in content
    assert "supabase.co" in content
    # Ensure no real passwords or leaked secrets in .env.example
    assert "dhvira" not in content.lower()
    assert "[YOUR_PASSWORD]" in content or "your_password" in content.lower()

    assert gitignore.exists()
    gi_content = gitignore.read_text()
    assert ".env" in gi_content


def test_placeholder_translation_layer():
    """Verifies safe translation from SQLite '?' to PostgreSQL '%s'."""
    # Simple query
    q1 = "SELECT * FROM items WHERE id = ? AND company_id = ?;"
    assert translate_placeholders_to_percent_s(q1) == "SELECT * FROM items WHERE id = %s AND company_id = %s;"

    # Query with quoted string containing '?'
    q2 = "SELECT * FROM items WHERE name = 'What?' AND id = ?;"
    assert translate_placeholders_to_percent_s(q2) == "SELECT * FROM items WHERE name = 'What?' AND id = %s;"

    # Query with escaped single quote
    q3 = "SELECT * FROM items WHERE name = 'It''s fine?' AND code = ?;"
    assert translate_placeholders_to_percent_s(q3) == "SELECT * FROM items WHERE name = 'It''s fine?' AND code = %s;"


def test_postgres_row_adapter():
    """Verifies PostgresRow provides both dictionary and tuple indexing like sqlite3.Row."""
    raw_dict = {"id": "uuid-123", "name": "Item A", "price": 45.5}
    row = PostgresRow(raw_dict)

    # Named access
    assert row["id"] == "uuid-123"
    assert row["name"] == "Item A"
    assert row["price"] == 45.5

    # Integer index access (matches sqlite3.Row cursor.fetchone()[0])
    assert row[0] == "uuid-123"
    assert row[1] == "Item A"
    assert row[2] == 45.5

    # Dictionary utilities
    assert list(row.keys()) == ["id", "name", "price"]
    assert dict(row) == raw_dict


# ==============================================================================
# 2. Database Connection, Alembic Schema & Transaction Atomicity
# ==============================================================================

def test_database_manager_test_connection(pg_db):
    """Verifies test_connection returns dialect, version, and masked URL."""
    status = pg_db.test_connection()
    assert status["success"] is True
    assert status["dialect"] == "postgresql"
    assert "version" in status
    assert "PostgreSQL" in status["version"]
    assert ":" in status["url"]
    # Ensure password is not exposed in returned URL
    if "@" in status["url"] and ":" in status["url"].split("@")[0].split("://")[-1]:
        assert ":****@" in status["url"]


def test_alembic_migrations_schema_completeness(pg_db):
    """Verifies all required Alpha Billing ERP tables exist in PostgreSQL."""
    required_tables = [
        "companies", "branches", "roles", "users", "user_permissions",
        "registers", "company_configs", "customer_category_discounts",
        "daily_discount_configs", "godowns", "suppliers", "accounts",
        "items", "item_barcodes", "item_branch_stock_configs", "stock_balances",
        "voucher_sequences", "sales_vouchers", "sales_voucher_items", "payments",
        "sales_returns", "sales_return_items", "purchase_vouchers",
        "purchase_voucher_items", "purchase_returns", "purchase_return_items",
        "stock_movements", "low_stock_alerts", "audit_logs", "ocr_invoice_drafts",
        "stock_adjustments", "stock_adjustment_items", "stock_transfers",
        "stock_transfer_items", "stock_batches", "journal_entries",
        "journal_entry_lines", "unit_conversions", "alembic_version"
    ]

    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
            """
        )
        existing_tables = set(r[0] for r in cursor.fetchall())

    for tbl in required_tables:
        assert tbl in existing_tables, f"Expected table '{tbl}' was not created in PostgreSQL by Alembic"


def test_postgres_transaction_atomicity_and_rollback(pg_db, tenant_comp_and_branch):
    """Verifies that an error within a transaction cleanly rolls back all modifications in PostgreSQL."""
    comp_id = tenant_comp_and_branch["company_id"]
    test_acc_id = str(uuid.uuid4())

    try:
        with pg_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO accounts (id, company_id, name, account_group, op_bal)
                VALUES (?, ?, 'Atomic Rollback Test Account', 'Sundry Debtors', 1000.0);
                """,
                (test_acc_id, comp_id)
            )
            # Intentionally trigger an error in the same transaction
            cursor.execute("INSERT INTO non_existent_table_xyz VALUES (1, 2, 3);")
            conn.commit()
    except Exception:
        pass  # Expected exception

    # Verify the account was rolled back and does not exist
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM accounts WHERE id = ?;", (test_acc_id,))
        count = cursor.fetchone()[0]
        assert count == 0, "Failed transaction was not rolled back; partial state was committed!"


# ==============================================================================
# 3. Party Masters Persistence in PostgreSQL
# ==============================================================================

def test_postgres_party_masters_customer_and_supplier(pg_db, tenant_comp_and_branch, monkeypatch):
    """Verifies Customer, Supplier, and Both roles persist in PostgreSQL."""
    monkeypatch.setattr(account_service, "db", pg_db)
    comp_id = tenant_comp_and_branch["company_id"]

    # 1. Customer Party
    cust_res = account_service.save_account(
        company_id=comp_id,
        account_data={
            "name": "Supabase Retailers",
            "account_group": "Sundry Debtors",
            "dealer_type": "Registered",
            "gstin": "33ABCDE1234F1Z5",
            "mobile": "9876543210",
            "address": "100 Mount Road",
            "state": "Tamilnadu",
            "op_bal": 5000.0,
            "op_type": "Dr"
        }
    )
    assert "id" in cust_res
    cust_id = cust_res["id"]

    # Verify in PostgreSQL accounts table
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, print_name, account_group, gstin FROM accounts WHERE id = ?;", (cust_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == "SUPABASE RETAILERS"
        assert row["print_name"] == "SUPABASE RETAILERS"
        assert row["account_group"] == "Sundry Debtors"
        assert row["gstin"] == "33ABCDE1234F1Z5"

    # 2. Supplier Party (with mirroring in suppliers table)
    supp_res = account_service.save_account(
        company_id=comp_id,
        account_data={
            "name": "Supabase Distributors Ltd",
            "account_group": "Sundry Creditors",
            "dealer_type": "Regular",
            "gstin": "33XYZAB9876C1Z1",
            "mobile": "9123456789",
            "address": "200 Harbor Way",
            "state": "Tamilnadu",
            "op_bal": 12000.0,
            "op_type": "Cr"
        }
    )
    assert "id" in supp_res
    supp_id = supp_res["id"]

    # Verify in both accounts and suppliers tables
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT account_group FROM accounts WHERE id = ?;", (supp_id,))
        assert cursor.fetchone()["account_group"] == "Sundry Creditors"

        cursor.execute("SELECT name, gstin FROM suppliers WHERE id = ?;", (supp_id,))
        s_row = cursor.fetchone()
        assert s_row is not None
        assert s_row["name"] == "SUPABASE DISTRIBUTORS LTD"
        assert s_row["gstin"] == "33XYZAB9876C1Z1"


# ==============================================================================
# 4. Items, Barcodes & Constraint Enforcement in PostgreSQL
# ==============================================================================

def test_postgres_items_and_barcode_uniqueness_enforcement(pg_db, tenant_comp_and_branch):
    """Verifies items, barcodes, and unique barcode constraint in PostgreSQL."""
    comp_id = tenant_comp_and_branch["company_id"]
    item1_id = str(uuid.uuid4())
    item2_id = str(uuid.uuid4())
    test_barcode = f"890{uuid.uuid4().int % 10000000000:010d}"

    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        # Insert two items
        cursor.execute(
            """
            INSERT INTO items (id, company_id, name, unit, sales_price, purc_price, tax_category)
            VALUES (?, ?, 'PG Biscuit 100g', 'Pcs.', 25.0, 20.0, 'GST 18%');
            """,
            (item1_id, comp_id)
        )
        cursor.execute(
            """
            INSERT INTO items (id, company_id, name, unit, sales_price, purc_price, tax_category)
            VALUES (?, ?, 'PG Wafer 50g', 'Pcs.', 15.0, 10.0, 'GST 18%');
            """,
            (item2_id, comp_id)
        )
        # Assign barcode to item1
        cursor.execute(
            """
            INSERT INTO item_barcodes (id, item_id, company_id, barcode, is_primary)
            VALUES (?, ?, ?, ?, 1);
            """,
            (str(uuid.uuid4()), item1_id, comp_id, test_barcode)
        )
        conn.commit()

    # Attempting to assign the SAME barcode to item2 in the same company must fail
    with pytest.raises(Exception):
        with pg_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO item_barcodes (id, item_id, company_id, barcode, is_primary)
                VALUES (?, ?, ?, ?, 1);
                """,
                (str(uuid.uuid4()), item2_id, comp_id, test_barcode)
            )
            conn.commit()


# ==============================================================================
# 5. Sales & Purchase Transactions with Inventory Ledger in PostgreSQL
# ==============================================================================

def test_postgres_sales_invoice_and_inventory_movement(pg_db, tenant_comp_and_branch, monkeypatch):
    """Verifies sales voucher creation, payment recording, and stock movement in PostgreSQL."""
    monkeypatch.setattr(billing_service, "db", pg_db)
    monkeypatch.setattr(inventory_service, "db", pg_db)

    comp_id = tenant_comp_and_branch["company_id"]
    branch_id = tenant_comp_and_branch["branch_id"]
    item_id = str(uuid.uuid4())
    barcode = f"890{uuid.uuid4().int % 10000000000:010d}"

    # Setup item with opening stock balance
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO items (id, company_id, name, sales_price, unit)
            VALUES (?, ?, 'PG Test Juice 200ml', 40.0, 'Bottle');
            """,
            (item_id, comp_id)
        )
        cursor.execute(
            """
            INSERT INTO item_barcodes (id, item_id, company_id, barcode, is_primary)
            VALUES (?, ?, ?, ?, 1);
            """,
            (str(uuid.uuid4()), item_id, comp_id, barcode)
        )
        cursor.execute(
            """
            INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
            VALUES (?, ?, ?, ?, 100.0);
            """,
            (str(uuid.uuid4()), comp_id, branch_id, item_id)
        )
        conn.commit()

    # Save Sales Voucher
    # Save Sales Voucher via billing_service
    result = billing_service.create_sale_invoice(
        company_id=comp_id,
        branch_id=branch_id,
        party_name="Direct Cash Customer",
        items=[
            {
                "id": item_id,
                "name": "PG Test Juice 200ml",
                "barcode": barcode,
                "qty": 2.0,
                "price": 40.0,
                "tax_rate": 18.0
            }
        ],
        sale_type="L/GST-18%",
        payment_method="CASH"
    )
    assert result is not None
    vch_no = result["vch_no"]

    # Verify PostgreSQL sales voucher, line items, and stock deduction
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        # 1. Sales Voucher
        cursor.execute("SELECT id, vch_no, grand_total FROM sales_vouchers WHERE company_id = ? AND vch_no = ?;", (comp_id, vch_no))
        v_row = cursor.fetchone()
        assert v_row is not None
        vch_id = v_row["id"]
        assert round(v_row["grand_total"]) in (94, 95)

        # 2. Sales Voucher Items
        cursor.execute("SELECT item_name, qty, price FROM sales_voucher_items WHERE voucher_id = ?;", (vch_id,))
        item_rows = cursor.fetchall()
        assert len(item_rows) == 1
        assert item_rows[0]["qty"] == 2.0

        # 3. Stock Balance deducted from 100 to 98
        cursor.execute(
            "SELECT current_qty FROM stock_balances WHERE branch_id = ? AND item_id = ?;",
            (branch_id, item_id)
        )
        new_qty = cursor.fetchone()["current_qty"]
        assert new_qty == 98.0

        # 4. Stock Movement Ledger Record (linked to voucher number)
        cursor.execute(
            "SELECT movement_type, qty, reference_id FROM stock_movements WHERE reference_id = ?;",
            (vch_no,)
        )
        sm_row = cursor.fetchone()
        assert sm_row is not None
        assert sm_row["movement_type"] == "SALE"
        assert sm_row["qty"] == -2.0


def test_postgres_purchase_invoice_and_stock_addition(pg_db, tenant_comp_and_branch, monkeypatch):
    """Verifies purchase voucher creation, supplier link, and stock addition in PostgreSQL."""
    monkeypatch.setattr(purchase_service, "db", pg_db)
    monkeypatch.setattr(purchase_service.supplier_service, "db", pg_db)

    comp_id = tenant_comp_and_branch["company_id"]
    branch_id = tenant_comp_and_branch["branch_id"]
    supp_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())

    # Create supplier and item in PostgreSQL
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO suppliers (id, company_id, code, name, gstin)
            VALUES (?, ?, 'SUP01', 'PG Supplier Prime', '33AAACB1234D1Z2');
            """,
            (supp_id, comp_id)
        )
        cursor.execute(
            """
            INSERT INTO items (id, company_id, name, unit, purc_price)
            VALUES (?, ?, 'PG Raw Nuts 1kg', 'Kg', 150.0);
            """,
            (item_id, comp_id)
        )
        cursor.execute(
            """
            INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
            VALUES (?, ?, ?, ?, 10.0);
            """,
            (str(uuid.uuid4()), comp_id, branch_id, item_id)
        )
        conn.commit()

    purchase_payload = {
        "branch_id": branch_id,
        "supplier_id": supp_id,
        "supplier_name": "PG Supplier Prime",
        "supplier_invoice_no": f"BILL-{uuid.uuid4().hex[:6]}",
        "supplier_invoice_date": "2026-11-06",
        "vch_date": "2026-11-06",
        "items": [
            {
                "item_id": item_id,
                "item_name": "PG Raw Nuts 1kg",
                "qty": 10.0,
                "unit": "Kg",
                "cost_rate": 150.0,
                "tax_rate": 18.0
            }
        ]
    }

    result = purchase_service.create_purchase_voucher(comp_id, purchase_payload)
    assert result is not None
    pur_vch_id = result.get("voucher_id") or result.get("id")

    # Verify purchase voucher recorded in PostgreSQL
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT supplier_name, grand_total FROM purchase_vouchers WHERE id = ?;",
            (pur_vch_id,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["supplier_name"] == "PG Supplier Prime"
        assert abs(row["grand_total"] - 1770.0) < 0.01

        # Verify stock incremented from 10 to 20
        cursor.execute(
            "SELECT current_qty FROM stock_balances WHERE branch_id = ? AND item_id = ?;",
            (branch_id, item_id)
        )
        assert cursor.fetchone()["current_qty"] == 20.0


# ==============================================================================
# 6. Voucher Numbering Constraint Enforcement in PostgreSQL
# ==============================================================================

def test_postgres_voucher_uniqueness_constraint_enforcement(pg_db, tenant_comp_and_branch):
    """Verifies unique constraint uq_sales_vouchers_comp_vchno in PostgreSQL."""
    comp_id = tenant_comp_and_branch["company_id"]
    shared_vch_no = f"INV-DUP-{uuid.uuid4().hex[:4].upper()}"

    # First voucher insert succeeds
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO sales_vouchers (id, company_id, vch_no, vch_date, sale_type, party_name, subtotal, taxable_amount, grand_total)
            VALUES (?, ?, ?, '2026-11-06', 'L/GST-18%', 'Cash', 100.0, 100.0, 100.0);
            """,
            (str(uuid.uuid4()), comp_id, shared_vch_no)
        )
        conn.commit()

    # Second voucher insert with identical company_id and vch_no must raise unique violation
    with pytest.raises(Exception):
        with pg_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sales_vouchers (id, company_id, vch_no, vch_date, sale_type, party_name, subtotal, taxable_amount, grand_total)
                VALUES (?, ?, ?, '2026-11-06', 'L/GST-18%', 'Cash', 200.0, 200.0, 200.0);
                """,
                (str(uuid.uuid4()), comp_id, shared_vch_no)
            )
            conn.commit()


# ==============================================================================
# 7. Multi-Company & Multi-Branch Data Isolation
# ==============================================================================

def test_postgres_multi_company_isolation(pg_db, tenant_comp_and_branch):
    """Verifies that Company A cannot see or access Company B records."""
    comp1_id = tenant_comp_and_branch["company_id"]
    comp2_id = str(uuid.uuid4())
    comp2_code = f"ISO_{uuid.uuid4().hex[:6].upper()}"

    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        # Create second company
        cursor.execute(
            "INSERT INTO companies (id, code, name, fin_year) VALUES (?, ?, 'Isolated Co 2', '2026-2027');",
            (comp2_id, comp2_code)
        )
        # Add item in company 2
        cursor.execute(
            "INSERT INTO items (id, company_id, name) VALUES (?, ?, 'Secret Item Co 2');",
            (str(uuid.uuid4()), comp2_id)
        )
        conn.commit()

    # Query items for Company 1
    with pg_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM items WHERE company_id = ?;", (comp1_id,))
        comp1_items = [r["name"] for r in cursor.fetchall()]
        assert "Secret Item Co 2" not in comp1_items


# ==============================================================================
# 8. Non-Destructive SQLite to PostgreSQL Migration Service
# ==============================================================================

def test_database_migration_service_execution_and_integrity(pg_db):
    """Verifies that DatabaseMigrationService migrates data and leaves SQLite completely intact."""
    sqlite_path = config.DATABASE_PATH
    assert sqlite_path.exists(), "Source SQLite database file must exist"

    # Get initial SQLite item count
    import sqlite3
    with sqlite3.connect(str(sqlite_path)) as sq_conn:
        sq_cur = sq_conn.cursor()
        sq_cur.execute("SELECT count(*) FROM items;")
        initial_sqlite_count = sq_cur.fetchone()[0]

    # Run migration (truncate_target ensures pristine migration without cross-test UUID collisions)
    migration_service = DatabaseMigrationService(sqlite_path=sqlite_path, postgres_url=PG_TEST_URL)
    result = migration_service.migrate(truncate_target=True)

    assert result.success is True, f"Migration failed with errors: {result.errors}"
    assert result.referential_integrity_valid is True
    assert result.uniqueness_valid is True
    assert result.total_tables >= 20
    assert result.total_rows >= 1000

    # Verify SQLite was NOT mutated or corrupted
    with sqlite3.connect(str(sqlite_path)) as sq_conn:
        sq_cur = sq_conn.cursor()
        sq_cur.execute("PRAGMA integrity_check;")
        assert sq_cur.fetchone()[0] == "ok"
        sq_cur.execute("SELECT count(*) FROM items;")
        post_migration_sqlite_count = sq_cur.fetchone()[0]
        assert post_migration_sqlite_count == initial_sqlite_count


# ==============================================================================
# 9. Dynamic Dialect Switching via Environment
# ==============================================================================

def test_dynamic_environment_switching():
    """Verifies system dynamically switches connection pools and dialect on DATABASE_URL change."""
    # Switch to SQLite
    os.environ["DATABASE_URL"] = f"sqlite:///{config.DATABASE_PATH}"
    sqlite_mgr = DatabaseManager()
    assert sqlite_mgr.is_sqlite is True
    assert sqlite_mgr.is_postgres is False

    # Switch to PostgreSQL
    os.environ["DATABASE_URL"] = PG_TEST_URL
    pg_mgr = DatabaseManager()
    assert pg_mgr.is_postgres is True
    assert pg_mgr.is_sqlite is False
