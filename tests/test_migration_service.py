"""Unit tests for browser localStorage migration service."""
import pytest
from pathlib import Path
from db.database import DatabaseManager
from services.migration_service import MigrationService


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "migration_test.db"
    manager = DatabaseManager(db_file)
    manager.run_migrations()
    return manager


def test_migration_payload_import(test_db):
    service = MigrationService(test_db)
    
    payload = {
        "alpha_companies": [
            {
                "id": "COMP0001",
                "name": "ANTI MATRIX",
                "code": "COMP0001",
                "finYear": "2026-2027 (1 Yr)",
                "taxNo": "33AAAPL1234F1Z1",
                "state": "Tamilnadu",
                "username": "A",
                "password": "a"
            }
        ],
        "alpha_config_COMP0001": {
            "vchStart": 1,
            "vchDigits": 3,
            "vchPrefix": "INV-",
            "defaultTax": "18",
            "autoRound": "Y"
        },
        "alpha_accounts_COMP0001": [
            {
                "name": "KAVIN RETAILS",
                "group": "Sundry Debtors",
                "opBal": "1500.00",
                "gstin": "33ABCDE1234F1Z5",
                "state": "Tamilnadu"
            }
        ],
        "alpha_items_COMP0001": [
            {
                "name": "PREMIUM BASMATI RICE 1KG",
                "unit": "Kg",
                "salesPrice": "120.00",
                "purcPrice": "95.00",
                "opStockQty": "50",
                "taxCategory": "GST 5%",
                "alias": "8901234567890"
            }
        ],
        "alpha_vouchers_COMP0001": [
            {
                "vchNo": "INV-001",
                "date": "29-10-2026",
                "saleType": "L/GST-5%",
                "party": "KAVIN RETAILS",
                "subtotal": 240.0,
                "grandTotal": "₹ 252.00",
                "items": [
                    {
                        "sn": 1,
                        "name": "PREMIUM BASMATI RICE 1KG",
                        "qty": 2.0,
                        "unit": "Kg",
                        "price": 120.0,
                        "amount": 240.0
                    }
                ]
            }
        ]
    }
    
    # 1. Initial Import
    res = service.import_localstorage_payload(payload)
    assert res["companies_imported"] == 1
    assert res["configs_imported"] == 1
    assert res["accounts_imported"] == 1
    assert res["items_imported"] == 1
    assert res["vouchers_imported"] == 1
    assert res["stock_movements_created"] == 2  # 1 opening stock + 1 sale
    
    # Verify stock balance: 50 opening - 2 sold = 48
    with test_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT current_qty FROM stock_balances;")
        balance = cursor.fetchone()[0]
        assert balance == 48.0
        
        # Verify invoice line items
        cursor.execute("SELECT item_name, qty, amount FROM sales_voucher_items;")
        item_row = cursor.fetchone()
        assert item_row[0] == "PREMIUM BASMATI RICE 1KG"
        assert item_row[1] == 2.0
        assert item_row[2] == 240.0
        
        # Verify barcode registration
        cursor.execute("SELECT barcode FROM item_barcodes;")
        barcode_row = cursor.fetchone()
        assert barcode_row[0] == "8901234567890"
        
    # 2. Second Import (Idempotency Test)
    res_second = service.import_localstorage_payload(payload)
    assert res_second["companies_imported"] == 0
    assert res_second["companies_skipped"] == 1
    assert res_second["accounts_imported"] == 0
    assert res_second["accounts_skipped"] == 1
    assert res_second["items_imported"] == 0
    assert res_second["items_skipped"] == 1
    assert res_second["vouchers_imported"] == 0
    assert res_second["vouchers_skipped"] == 1
