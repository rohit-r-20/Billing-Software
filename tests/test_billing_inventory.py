"""Unit tests for Billing and Inventory transactions."""
import pytest
from db.database import DatabaseManager
from services.billing_service import BillingService
from services.catalogue_service import CatalogueService
from services.account_service import AccountService


@pytest.fixture
def initialized_db(tmp_path):
    db_file = tmp_path / "billing_test.db"
    manager = DatabaseManager(db_file)
    manager.run_migrations()
    
    # Create test company and default branch
    with manager.get_connection() as conn:
        conn.execute("""
            INSERT INTO companies (id, code, name, fin_year, gstin, state)
            VALUES ('C1', 'COMP0001', 'ANTI MATRIX', '2026-27', '33AAAPL1234F1Z1', 'Tamilnadu');
        """)
        conn.execute("""
            INSERT INTO branches (id, company_id, code, name, is_default)
            VALUES ('B1', 'C1', 'BR01', 'Main Branch', 1);
        """)
        conn.execute("""
            INSERT INTO company_configs (company_id, vch_start, vch_digits, vch_prefix)
            VALUES ('C1', 1, 3, 'INV-');
        """)
        conn.commit()
    return manager


def test_atomic_sales_invoice_creation(initialized_db):
    cat_service = CatalogueService(initialized_db)
    bill_service = BillingService(initialized_db)
    acc_service = AccountService(initialized_db)

    # 0. Register customer master
    cust = acc_service.save_account('C1', {
        "name": "KAVIN RETAILS",
        "account_group": "Sundry Debtors",
        "state": "Tamilnadu"
    })
    
    # 1. Create a product with 100 units opening stock
    item_res = cat_service.save_item('C1', {
        "name": "COLGATE TOOTHPASTE 100G",
        "alias": "890123450001",
        "sales_price": 50.0,
        "op_stock_qty": 100.0,
        "tax_category": "GST 18%"
    })
    item_id = item_res["id"]
    
    # Verify opening stock balance is 100
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT current_qty FROM stock_balances WHERE branch_id = 'B1' AND item_id = ?;", (item_id,))
        assert cursor.fetchone()[0] == 100.0
        
    # 2. Checkout a sale for 4 units
    cart_items = [
        {
            "id": item_id,
            "name": "COLGATE TOOTHPASTE 100G",
            "price": 50.0,
            "qty": 4.0,
            "tax_rate": 18.0
        }
    ]
    
    sale_res = bill_service.create_sale_invoice(
        company_id='C1',
        items=cart_items,
        party_name="KAVIN RETAILS",
        sale_type="L/GST-18%",
        payment_method="UPI"
    )
    
    assert sale_res["vch_no"] == "INV-001"
    # 4 * 50 = 200 + 18% tax (36) = 236
    assert sale_res["grand_total"] == 236.0
    
    # 3. Verify stock balance was deducted: 100 - 4 = 96
    with initialized_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT current_qty FROM stock_balances WHERE branch_id = 'B1' AND item_id = ?;", (item_id,))
        assert cursor.fetchone()[0] == 96.0
        
        # Verify stock movement ledger
        cursor.execute("SELECT movement_type, qty, reference_id FROM stock_movements WHERE item_id = ?;", (item_id,))
        movements = cursor.fetchall()
        assert len(movements) == 1
        assert movements[0][0] == "SALE"
        assert movements[0][1] == -4.0
        assert movements[0][2] == "INV-001"
        
        # Verify payment ledger
        cursor.execute("SELECT method, amount FROM payments WHERE voucher_id = ?;", (sale_res["voucher_id"],))
        pay = cursor.fetchone()
        assert pay[0] == "UPI"
        assert pay[1] == 236.0
        
    # 4. Next invoice sequence must be INV-002
    next_no = bill_service.get_next_voucher_number('C1')
    assert next_no == "INV-002"


def test_empty_invoice_raises_error(initialized_db):
    bill_service = BillingService(initialized_db)
    with pytest.raises(ValueError):
        bill_service.create_sale_invoice(
            company_id='C1',
            items=[],
            party_name="CASH"
        )

