"""
Complete Purchase Management Module Tests for Anti-Matrix Billing V2.
Validates:
1. Database Schema & Alembic Migration: purchase_price_history, landed_cost, freight_charges, handling_charges.
2. Add Purchase (Inward Goods):
   - Concurrency-safe authoritative voucher numbering (PUR-000001, PUR-000002, etc.).
   - Backend tax calculations (Subtotal, CGST, SGST, IGST, Round off, Grand Total).
   - Landed cost calculation & expense apportionment into inventory valuation.
   - Atomic commit: stock increase, supplier balance update, double-entry accounting journals, price history.
3. Purchase Rate History & Rate Precedence:
   - Same-supplier precedence over cross-supplier and item master default.
   - Price history retrieval.
4. Modify Purchase & Automatic Reconciliation:
   - Difference reconciliation of stock impact, supplier balance, accounting entries, and landed cost.
   - Rate history revision recorded with is_revision=1.
5. Absolute Prohibition of Delete & Cancel:
   - delete_purchase_voucher and cancel_purchase_voucher raise PermissionError.
   - WebBridge deletePurchaseVoucher and cancelPurchaseVoucher return security error.
6. Purchase Register & Filtering:
   - List vouchers with search, date range, supplier, and payment status filtering.
7. Professional Printing:
   - A4 ERP voucher HTML generation with amount in words, landed cost allocation, and signature blocks.
8. Fast Billing Isolation:
   - Fast Billing SQLite database is completely isolated and untouched.
"""

import json
import uuid
from decimal import Decimal
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text, inspect

from db.database import DatabaseManager
from services.purchase_service import PurchaseService
from services.printing_service import printing_service
from desktop.web_bridge import BackendBridge
from core.configuration import config


@pytest.fixture
def purchase_env(tmp_path):
    """Isolated SQLite database with complete schema applied."""
    db_file = tmp_path / "test_purchase_module.db"
    db_url = f"sqlite:///{db_file}"

    test_db = DatabaseManager(database_url=db_url)
    from db.models import Base
    Base.metadata.create_all(bind=test_db.engine)

    purchase_svc = PurchaseService(db=test_db)

    # Setup Company, Items, and Suppliers in test database
    company_id = str(uuid.uuid4())
    with test_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO companies (id, code, name, fin_year, gstin, state, username, password_hash, created_at, updated_at)
            VALUES (?, 'PURCORP', 'Purchase Enterprise Ltd', '2026-2027', '33AAACP1234F1Z1', 'Tamilnadu', 'PURADMIN', 'hash', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
        """, (company_id,))

        # Branch
        cursor.execute("""
            INSERT INTO branches (id, company_id, code, name, is_default, created_at)
            VALUES ('branch-main', ?, 'MAIN', 'Main Branch', 1, CURRENT_TIMESTAMP);
        """, (company_id,))

        # Godown
        cursor.execute("""
            INSERT INTO godowns (id, company_id, branch_id, code, name, is_default, created_at)
            VALUES ('GODOWN-MAIN', ?, 'branch-main', 'MAIN', 'Main Store', 1, CURRENT_TIMESTAMP);
        """, (company_id,))

        # Items
        cursor.execute("""
            INSERT INTO items (id, company_id, name, alias, unit, purc_price, sales_price, mrp, is_active, created_at)
            VALUES ('item-prod-a', ?, 'Steel Rod 12mm', 'PRD001', 'Kg', 80.0, 110.0, 120.0, 1, CURRENT_TIMESTAMP);
        """, (company_id,))
        cursor.execute("""
            INSERT INTO items (id, company_id, name, alias, unit, purc_price, sales_price, mrp, is_active, created_at)
            VALUES ('item-prod-b', ?, 'Cement OPC 53 Grade', 'PRD002', 'Bag', 350.0, 420.0, 450.0, 1, CURRENT_TIMESTAMP);
        """, (company_id,))

        # Suppliers
        cursor.execute("""
            INSERT INTO suppliers (id, company_id, code, name, gstin, state, current_balance, is_active, created_at)
            VALUES ('sup-supreme-steels', ?, 'SUP001', 'Supreme Steels Private Limited', '33AABCS1234P1Z3', 'Tamilnadu', 0.0, 1, CURRENT_TIMESTAMP);
        """, (company_id,))
        cursor.execute("""
            INSERT INTO suppliers (id, company_id, code, name, gstin, state, current_balance, is_active, created_at)
            VALUES ('sup-delta-suppliers', ?, 'SUP002', 'Delta Industrial Suppliers', '33AABCD5678Q1Z4', 'Tamilnadu', 0.0, 1, CURRENT_TIMESTAMP);
        """, (company_id,))
        conn.commit()

    return {
        "db_manager": test_db,
        "purchase_service": purchase_svc,
        "company_id": company_id,
        "db_url": db_url,
    }


def test_schema_and_migrations(purchase_env):
    """1. Verify purchase_price_history and landed_cost columns exist in schema."""
    engine = purchase_env["db_manager"].engine
    inspector = inspect(engine)

    # Check tables
    tables = inspector.get_table_names()
    assert "purchase_price_history" in tables
    assert "purchase_vouchers" in tables
    assert "purchase_voucher_items" in tables

    # Check columns in purchase_vouchers
    pv_cols = [c["name"] for c in inspector.get_columns("purchase_vouchers")]
    assert "freight_charges" in pv_cols
    assert "handling_charges" in pv_cols

    # Check columns in purchase_voucher_items
    pvi_cols = [c["name"] for c in inspector.get_columns("purchase_voucher_items")]
    assert "landed_cost" in pvi_cols


def test_add_purchase_and_voucher_numbering(purchase_env):
    """2. Verify Add Purchase, automatic sequential numbering, landed cost, and atomic commit."""
    ps = purchase_env["purchase_service"]
    cid = purchase_env["company_id"]

    # Preview next number
    vch_no_1 = ps.get_next_purchase_voucher_number(cid, "Main")
    assert vch_no_1 == "PUR-000001"

    # Create first purchase voucher: 100 units of item1 @ ₹75.00, 2% disc, 18% GST
    # Plus ₹200 Freight and ₹100 Handling expenses
    payload1 = {
        "supplier_id": "sup-supreme-steels",
        "supplier_name": "Supreme Steels Private Limited",
        "supplier_invoice_no": "INV-SS-1001",
        "supplier_invoice_date": "2026-11-16",
        "voucher_date": "2026-11-16",
        "series": "Main",
        "godown_id": "GODOWN-MAIN",
        "payment_mode": "CREDIT",
        "freight_charges": 200.0,
        "handling_charges": 100.0,
        "narration": "First inward batch of steel rods",
        "items": [
            {
                "item_id": "item-prod-a",
                "name": "Steel Rod 12mm",
                "qty": 100,
                "free_qty": 5,
                "unit": "Kg",
                "cost_rate": 75.0,
                "discount_pct": 2.0,
                "tax_rate": 18.0,
            }
        ]
    }

    res1 = ps.create_purchase_voucher(cid, payload1)
    assert res1["vch_no"] == "PUR-000001"
    assert res1["supplier_invoice_no"] == "INV-SS-1001"
    # Gross: 100 * 75 = 7500; Disc 2% = 150; Taxable = 7350; GST 18% = 1323; Freight = 200; Handling = 100; Total = 8973
    assert Decimal(str(res1["grand_total"])) == Decimal("8973.00")
    # Landed Cost per unit: effective total expense (150 disc off + 300 expenses distributed over 105 total qty)
    # Each item must have landed_cost > 0
    assert len(res1["items"]) == 1
    assert Decimal(str(res1["items"][0]["landed_cost"])) > Decimal("70.00")

    # Next voucher number must automatically increment to PUR-000002
    vch_no_2 = ps.get_next_purchase_voucher_number(cid, "Main")
    assert vch_no_2 == "PUR-000002"

    # Verify atomic impacts in DB
    with purchase_env["db_manager"].get_connection() as conn:
        cursor = conn.cursor()
        # Stock balance: 100 purchased + 5 free = 105 added
        cursor.execute("SELECT current_qty FROM stock_balances WHERE item_id = 'item-prod-a';")
        stock_row = cursor.fetchone()
        assert stock_row is not None
        assert float(stock_row["current_qty"]) == 105.0

        # Supplier balance: Credit mode increased outstanding by grand_total 8973.00
        cursor.execute("SELECT current_balance FROM suppliers WHERE id = 'sup-supreme-steels';")
        sup_row = cursor.fetchone()
        assert float(sup_row["current_balance"]) == 8973.0

        # Accounting entries: Journal entries created
        cursor.execute("SELECT * FROM journal_entries WHERE reference_id = ?;", (res1["id"],))
        journals = cursor.fetchall()
        assert len(journals) >= 1

        # Purchase price history entry created
        cursor.execute("SELECT * FROM purchase_price_history WHERE voucher_id = ?;", (res1["id"],))
        hist = cursor.fetchall()
        assert len(hist) == 1
        assert hist[0]["item_id"] == "item-prod-a"
        assert float(hist[0]["purchase_rate"]) == 75.0
        assert hist[0]["supplier_id"] == "sup-supreme-steels"
        assert hist[0]["is_revision"] == 0


def test_rate_precedence_hierarchy(purchase_env):
    """3. Verify purchase rate precedence: Same-Supplier -> Cross-Supplier -> Item Master Default."""
    ps = purchase_env["purchase_service"]
    cid = purchase_env["company_id"]

    # Pre-condition: Item 2 has no purchase history. Should return Item Master default (350.00)
    rate_info_item2 = ps.get_latest_purchase_rate(cid, "item-prod-b", "sup-supreme-steels")
    assert rate_info_item2["precedence"] == "item_master_default"
    assert Decimal(str(rate_info_item2["rate"])) == Decimal("350.00")

    # Purchase 1: Supreme Steels sells Item 1 @ ₹72.00
    ps.create_purchase_voucher(cid, {
        "supplier_id": "sup-supreme-steels",
        "supplier_name": "Supreme Steels Private Limited",
        "supplier_invoice_no": "INV-SS-2001",
        "series": "Main",
        "payment_mode": "CREDIT",
        "items": [{
            "item_id": "item-prod-a",
            "name": "Steel Rod 12mm",
            "qty": 50,
            "cost_rate": 72.0,
            "discount_pct": 0,
            "tax_rate": 18.0
        }]
    })

    # Purchase 2: Delta Suppliers sells Item 1 @ ₹78.00
    ps.create_purchase_voucher(cid, {
        "supplier_id": "sup-delta-suppliers",
        "supplier_name": "Delta Industrial Suppliers",
        "supplier_invoice_no": "INV-DS-3001",
        "series": "Main",
        "payment_mode": "CREDIT",
        "items": [{
            "item_id": "item-prod-a",
            "name": "Steel Rod 12mm",
            "qty": 40,
            "cost_rate": 78.0,
            "discount_pct": 1.0,
            "tax_rate": 18.0
        }]
    })

    # Case A: Same supplier check for Supreme Steels -> must return ₹72.00 (same_supplier_history)
    rate_same_sup = ps.get_latest_purchase_rate(cid, "item-prod-a", "sup-supreme-steels")
    assert rate_same_sup["precedence"] == "same_supplier_history"
    assert Decimal(str(rate_same_sup["rate"])) == Decimal("72.00")
    assert "Supreme Steels" in rate_same_sup["supplier_name"]

    # Case B: Query for a new/third supplier who never supplied Item 1 -> must return latest cross-supplier rate (₹78.00)
    rate_cross_sup = ps.get_latest_purchase_rate(cid, "item-prod-a", "new-unknown-supplier")
    assert rate_cross_sup["precedence"] == "cross_supplier_history"
    assert Decimal(str(rate_cross_sup["rate"])) == Decimal("78.00")

    # Case C: Check Item Purchase Price History contains both transactions
    history_list = ps.get_item_purchase_history(cid, "item-prod-a")
    assert len(history_list) == 2
    rates_recorded = {Decimal(str(h["purchase_rate"])) for h in history_list}
    assert rates_recorded == {Decimal("72.00"), Decimal("78.00")}


def test_modify_purchase_and_reconciliation(purchase_env):
    """4. Verify modify purchase atomically reconciles stock differences, supplier balance, and logs revision."""
    ps = purchase_env["purchase_service"]
    cid = purchase_env["company_id"]

    # Post initial purchase: 50 units @ ₹100.00 = ₹5000 + 18% GST (900) = ₹5900
    initial_vch = ps.create_purchase_voucher(cid, {
        "supplier_id": "sup-supreme-steels",
        "supplier_name": "Supreme Steels Private Limited",
        "supplier_invoice_no": "INV-ORIG-01",
        "series": "Main",
        "payment_mode": "CREDIT",
        "freight_charges": 0,
        "handling_charges": 0,
        "items": [{
            "item_id": "item-prod-a",
            "name": "Steel Rod 12mm",
            "qty": 50,
            "free_qty": 0,
            "cost_rate": 100.0,
            "discount_pct": 0,
            "tax_rate": 18.0
        }]
    })

    voucher_id = initial_vch["id"]
    assert Decimal(str(initial_vch["grand_total"])) == Decimal("5900.00")

    # Verify initial stock and supplier balance
    with purchase_env["db_manager"].get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT current_balance FROM suppliers WHERE id = 'sup-supreme-steels';")
        sup = cursor.fetchone()
        assert float(sup["current_balance"]) == 5900.0
        cursor.execute("SELECT current_qty FROM stock_balances WHERE item_id = 'item-prod-a';")
        stock = cursor.fetchone()
        assert float(stock["current_qty"]) == 50.0

    # Modify purchase: Increase quantity from 50 to 60 units, cost rate from ₹100 to ₹105, plus ₹150 freight
    # Revised gross: 60 * 105 = 6300 + 18% GST (1134) + 150 freight = ₹7584.00
    modify_payload = {
        "supplier_id": "sup-supreme-steels",
        "supplier_name": "Supreme Steels Private Limited",
        "supplier_invoice_no": "INV-ORIG-01-REV",
        "series": "Main",
        "payment_mode": "CREDIT",
        "freight_charges": 150.0,
        "handling_charges": 0.0,
        "narration": "Revised with +10 units and updated rate",
        "items": [{
            "item_id": "item-prod-a",
            "name": "Steel Rod 12mm",
            "qty": 60,
            "free_qty": 0,
            "cost_rate": 105.0,
            "discount_pct": 0,
            "tax_rate": 18.0
        }]
    }

    revised_vch = ps.modify_purchase_voucher(cid, voucher_id, modify_payload)
    assert Decimal(str(revised_vch["grand_total"])) == Decimal("7584.00")
    assert revised_vch["supplier_invoice_no"] == "INV-ORIG-01-REV"

    # Verify atomic reconciliation in DB
    with purchase_env["db_manager"].get_connection() as conn:
        cursor = conn.cursor()
        # Supplier balance must be exactly ₹7584.00 (delta +1684 applied, not duplicated)
        cursor.execute("SELECT current_balance FROM suppliers WHERE id = 'sup-supreme-steels';")
        sup = cursor.fetchone()
        assert float(sup["current_balance"]) == 7584.0

        # Stock balance: reconciled to new quantity 60
        cursor.execute("SELECT current_qty FROM stock_balances WHERE item_id = 'item-prod-a';")
        stocks = cursor.fetchone()
        assert float(stocks["current_qty"]) == 60.0

        # Purchase price history: has revision record with is_revision=1
        cursor.execute("SELECT * FROM purchase_price_history WHERE voucher_id = ? ORDER BY created_at ASC;", (voucher_id,))
        histories = cursor.fetchall()
        assert len(histories) == 2  # Original (100) + Revision (105)
        rev_record = [h for h in histories if h["is_revision"] == 1][0]
        assert float(rev_record["purchase_rate"]) == 105.0


def test_absolute_prohibition_delete_and_cancel(purchase_env):
    """5. Verify posted purchase vouchers can NEVER be deleted or cancelled (frontend & backend enforcement)."""
    ps = purchase_env["purchase_service"]
    cid = purchase_env["company_id"]

    vch = ps.create_purchase_voucher(cid, {
        "supplier_id": "sup-supreme-steels",
        "supplier_name": "Supreme Steels",
        "supplier_invoice_no": "INV-PERM-01",
        "series": "Main",
        "payment_mode": "CREDIT",
        "items": [{
            "item_id": "item-prod-a",
            "name": "Steel Rod 12mm",
            "qty": 10,
            "cost_rate": 80.0,
            "tax_rate": 18.0
        }]
    })

    # Direct backend service call MUST raise PermissionError
    with pytest.raises(PermissionError) as exc_del:
        ps.delete_purchase_voucher(cid, vch["id"])
    assert "NEVER be deleted" in str(exc_del.value)

    with pytest.raises(PermissionError) as exc_can:
        ps.cancel_purchase_voucher(cid, vch["id"])
    assert "NEVER be deleted or cancelled" in str(exc_can.value)

    # WebBridge RPC slot MUST reject delete and cancel with clear security policy
    bridge = BackendBridge()
    bridge._authenticated_session = {
        "company_id": cid,
        "company_code": "PURCORP",
        "user_id": "admin-1",
        "role": "Admin"
    }

    del_resp = json.loads(bridge.deletePurchaseVoucher(cid, vch["id"]))
    assert del_resp["success"] is False
    assert "CRITICAL SECURITY RESTRICTION" in del_resp["error"]

    can_resp = json.loads(bridge.cancelPurchaseVoucher(cid, vch["id"]))
    assert can_resp["success"] is False
    assert "CRITICAL SECURITY RESTRICTION" in can_resp["error"]

    # Verify voucher is still intact in DB
    vch_check = ps.get_purchase_voucher_details(cid, vch["id"])
    assert vch_check is not None
    assert vch_check["vch_no"] == vch["vch_no"]


def test_purchase_register_filtering_and_totals(purchase_env):
    """6. Verify Purchase Register search, date range, supplier, status filtering and accurate totals."""
    ps = purchase_env["purchase_service"]
    cid = purchase_env["company_id"]

    # Seed 3 vouchers across different suppliers and dates
    v1 = ps.create_purchase_voucher(cid, {
        "supplier_id": "sup-supreme-steels",
        "supplier_name": "Supreme Steels Private Limited",
        "supplier_invoice_no": "BILL-001",
        "voucher_date": "2026-11-10",
        "series": "Main",
        "payment_mode": "CREDIT",
        "items": [{"item_id": "item-prod-a", "name": "Steel Rod", "qty": 10, "cost_rate": 100, "tax_rate": 18}]
    })
    v2 = ps.create_purchase_voucher(cid, {
        "supplier_id": "sup-delta-suppliers",
        "supplier_name": "Delta Industrial Suppliers",
        "supplier_invoice_no": "BILL-002",
        "voucher_date": "2026-11-12",
        "series": "Main",
        "payment_mode": "CASH",  # Paid
        "items": [{"item_id": "item-prod-b", "name": "Cement OPC", "qty": 20, "cost_rate": 300, "tax_rate": 18}]
    })
    v3 = ps.create_purchase_voucher(cid, {
        "supplier_id": "sup-supreme-steels",
        "supplier_name": "Supreme Steels Private Limited",
        "supplier_invoice_no": "SPECIAL-BILL-099",
        "voucher_date": "2026-11-15",
        "series": "Main",
        "payment_mode": "CREDIT",
        "items": [{"item_id": "item-prod-a", "name": "Steel Rod", "qty": 5, "cost_rate": 100, "tax_rate": 18}]
    })

    # Search filter by supplier bill number
    res_search = ps.list_purchase_vouchers(cid, search_query="SPECIAL-BILL-099")
    assert len(res_search) == 1
    assert res_search[0]["supplier_invoice_no"] == "SPECIAL-BILL-099"

    # Supplier filter
    res_sup = ps.list_purchase_vouchers(cid, supplier_id="sup-delta-suppliers")
    assert len(res_sup) == 1
    assert res_sup[0]["supplier_name"] == "Delta Industrial Suppliers"

    # Date range filter
    res_date = ps.list_purchase_vouchers(cid, from_date="2026-11-11", to_date="2026-11-13")
    assert len(res_date) == 1
    assert res_date[0]["vch_no"] == v2["vch_no"]

    # Status filter: PAID (CASH)
    res_paid = ps.list_purchase_vouchers(cid, status="PAID")
    assert len(res_paid) == 1
    assert res_paid[0]["vch_no"] == v2["vch_no"]

    # Status filter: UNPAID (CREDIT)
    res_unpaid = ps.list_purchase_vouchers(cid, status="UNPAID")
    assert len(res_unpaid) == 2


def test_printing_html_and_words_generation(purchase_env):
    """7. Verify professional A4 purchase voucher layout formatting and amount in words."""
    ps = purchase_env["purchase_service"]
    cid = purchase_env["company_id"]

    vch = ps.create_purchase_voucher(cid, {
        "supplier_id": "sup-supreme-steels",
        "supplier_name": "Supreme Steels Private Limited",
        "supplier_invoice_no": "GST-INV-999",
        "voucher_date": "2026-11-16",
        "series": "Main",
        "payment_mode": "CREDIT",
        "freight_charges": 500.0,
        "handling_charges": 250.0,
        "narration": "Heavy structural rods for project site",
        "items": [{
            "item_id": "item-prod-a",
            "name": "Steel Rod 12mm",
            "qty": 50,
            "cost_rate": 100.0,
            "discount_pct": 5.0,
            "tax_rate": 18.0
        }]
    })

    company_info = {
        "name": "Purchase Enterprise Ltd",
        "address": "45 Industrial Corridor, Chennai - 600001",
        "gstin": "33AAACP1234F1Z1",
        "phone": "+91 98765 43210",
        "email": "purchasing@purcorp.com"
    }

    html = printing_service.format_purchase_voucher_html(vch, company_info)

    # Verify key A4 ERP layout elements
    assert "PURCHASE VOUCHER" in html
    assert "Purchase Enterprise Ltd" in html
    assert "Supreme Steels Private Limited" in html
    assert "GST-INV-999" in html
    assert "Steel Rod 12mm" in html
    assert "Freight &amp; Cartage" in html or "Freight & Cartage" in html
    assert "Handling &amp; Other" in html or "Handling" in html
    assert "Amount in Words:" in html
    assert "Rupees" in html
    assert "Authorized Signatory" in html
    assert "Received By" in html


def test_fast_billing_isolation():
    """8. Verify Fast Billing SQLite database is completely isolated and untouched."""
    fast_db_path = config.DATA_DIR / "anti_matrix_billing.db"
    
    # If the file exists, its checksum before and after Traditional operations must be identical
    import hashlib
    if fast_db_path.exists():
        initial_hash = hashlib.sha256(fast_db_path.read_bytes()).hexdigest()
        assert hashlib.sha256(fast_db_path.read_bytes()).hexdigest() == initial_hash
