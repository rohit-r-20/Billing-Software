"""
Comprehensive Unit & Integration Test Suite for Enterprise ERP Integration:
Centralized Inventory, Purchase Management, Supplier Master, Returns, Adjustments,
Transfers, Valuation, Double-Entry Accounting, and Document OCR.
"""
import pytest
from datetime import datetime
from db.database import DatabaseManager
from services.supplier_service import SupplierService
from services.catalogue_service import CatalogueService
from services.inventory_service import InventoryService
from services.purchase_service import PurchaseService
from services.billing_service import BillingService
from services.accounting_service import AccountingService
from services.ocr_service import OCRService


@pytest.fixture
def erp_db(tmp_path):
    db_file = tmp_path / "enterprise_erp_test.db"
    manager = DatabaseManager(db_file)
    manager.run_migrations()

    with manager.get_connection() as conn:
        conn.execute("""
            INSERT INTO companies (id, code, name, fin_year, gstin, state)
            VALUES ('C1', 'COMP0001', 'ANTI MATRIX RETAIL', '2026-27', '33AAAPL1234F1Z1', 'Tamilnadu');
        """)
        conn.execute("""
            INSERT INTO branches (id, company_id, code, name, is_default)
            VALUES ('B1', 'C1', 'BR01', 'Main Branch', 1);
        """)
        conn.execute("""
            INSERT INTO branches (id, company_id, code, name, is_default)
            VALUES ('B2', 'C1', 'BR02', 'Warehouse Godown B', 0);
        """)
        conn.execute("""
            INSERT INTO company_configs (company_id, vch_start, vch_digits, vch_prefix)
            VALUES ('C1', 1, 3, 'INV-');
        """)
        conn.commit()

    return manager


def test_supplier_master_crud_and_balance(erp_db):
    supp_svc = SupplierService(erp_db)

    # 1. Create Supplier
    supp = supp_svc.save_supplier("C1", {
        "name": "ABC DISTRIBUTORS",
        "gstin": "33ABCDE1234F1Z5",
        "state": "Tamilnadu",
        "mobile": "9876543210",
        "opening_balance": 500.0
    })
    assert supp["name"] == "ABC DISTRIBUTORS"
    assert supp["code"].startswith("SUP-")

    # 2. Query Supplier
    fetched = supp_svc.get_supplier_by_id("C1", supp["id"])
    assert fetched is not None
    assert fetched["gstin"] == "33ABCDE1234F1Z5"
    assert fetched["current_balance"] == 500.0

    # 3. Adjust balance
    new_bal = supp_svc.update_supplier_balance("C1", supp["id"], 250.0)
    assert new_bal == 750.0

    # 4. Check list
    supp_list = supp_svc.list_suppliers("C1", "ABC")
    assert len(supp_list) == 1
    assert supp_list[0]["name"] == "ABC DISTRIBUTORS"


def test_end_to_end_purchase_sales_returns_inventory_lifecycle(erp_db):
    """
    Executes the exact end-to-end acceptance scenario:
    1. Purchase Milk Bikis 100 packets @ ₹8.00 from ABC Distributors (Credit).
    2. Fast Billing sells 5 packets -> Stock 95.
    3. Traditional Billing sells 3 packets -> Stock 92.
    4. Stock Summary verifies closing stock = 92 packets.
    5. Purchase Return 10 packets -> Stock 82.
    6. Sales Return 2 packets -> Stock 84.
    7. Stock Adjustment (Damage) 4 packets -> Stock 80.
    8. Stock Transfer 10 packets to Branch B2 -> B1 becomes 70, B2 becomes 10, Company-wide = 80.
    """
    cat_svc = CatalogueService(erp_db)
    inv_svc = InventoryService(erp_db)
    purc_svc = PurchaseService(erp_db)
    bill_svc = BillingService(erp_db)
    acc_svc = AccountingService(erp_db)

    # 0. Register Milk Bikis in Catalogue
    item = cat_svc.save_item("C1", {
        "name": "MILK BIKIS",
        "alias": "890_TEST_001",
        "sales_price": 10.0,
        "purc_price": 8.0,
        "op_stock_qty": 0.0,
        "tax_category": "GST 5%"
    })
    item_id = item["id"]
    assert inv_svc.get_stock("C1", item_id, "B1") == 0.0

    # =========================================================================
    # STEP 1: TEST A — Purchase Entry
    # =========================================================================
    purc_res = purc_svc.create_purchase_voucher("C1", {
        "supplier_name": "ABC DISTRIBUTORS",
        "supplier_gstin": "33ABCDE1234F1Z5",
        "supplier_invoice_no": "ABC/2026/001",
        "supplier_invoice_date": "2026-11-01",
        "vch_date": "2026-11-01",
        "payment_type": "CREDIT",
        "branch_id": "B1",
        "items": [
            {
                "item_id": item_id,
                "name": "MILK BIKIS",
                "barcode": "890_TEST_001",
                "qty": 100.0,
                "unit": "Packets",
                "purchase_rate": 8.0,
                "tax_rate": 5.0
            }
        ]
    })

    # Expected:
    # Internal voucher: PUR-000001
    # Supplier bill: ABC/2026/001 preserved
    # Gross: 100 * 8 = 800 + 5% tax (40) = 840.0
    assert purc_res["supplier_invoice_no"] == "ABC/2026/001"
    assert purc_res["vch_no"] == "PUR-000001"
    assert purc_res["grand_total"] == 840.0
    assert purc_res["outstanding_balance"] == 840.0

    # Stock must increase from 0 to 100
    assert inv_svc.get_stock("C1", item_id, "B1") == 100.0

    # Duplicate supplier bill protection check
    with pytest.raises(ValueError, match="Duplicate Supplier Invoice detected"):
        purc_svc.create_purchase_voucher("C1", {
            "supplier_name": "ABC DISTRIBUTORS",
            "supplier_invoice_no": "ABC/2026/001",
            "supplier_invoice_date": "2026-11-01",
            "items": [{"item_id": item_id, "qty": 10.0, "purchase_rate": 8.0}]
        })

    # =========================================================================
    # STEP 2: TEST B — Fast Billing Sale (Sell 5 packets)
    # =========================================================================
    fast_sale = bill_svc.create_sale_invoice(
        company_id="C1",
        branch_id="B1",
        items=[
            {
                "id": item_id,
                "name": "MILK BIKIS",
                "price": 10.0,
                "qty": 5.0,
                "tax_rate": 5.0
            }
        ],
        payment_method="CASH",
        narration="Fast Billing POS Sale"
    )
    # Stock must reduce from 100 to 95
    assert inv_svc.get_stock("C1", item_id, "B1") == 95.0

    # =========================================================================
    # STEP 3: TEST C — Traditional Billing Sale (Sell 3 packets)
    # Traditional billing passes only name without explicit id; service resolves it!
    # =========================================================================
    trad_sale = bill_svc.create_sale_invoice(
        company_id="C1",
        branch_id="B1",
        party_name="LOCAL CUSTOMER",
        items=[
            {
                "name": "MILK BIKIS",
                "price": 10.0,
                "qty": 3.0,
                "tax_rate": 5.0
            }
        ],
        payment_method="UPI",
        narration="Traditional Sales Voucher"
    )
    # Stock must reduce from 95 to 92
    assert inv_svc.get_stock("C1", item_id, "B1") == 92.0

    # =========================================================================
    # STEP 4: TEST D — Cross-Mode Stock Summary Reconciliation
    # =========================================================================
    summary = inv_svc.get_stock_summary("C1", "B1")
    mb_summary = next(s for s in summary if s["product_name"] == "MILK BIKIS")
    assert mb_summary["closing_stock"] == 92.0
    assert mb_summary["purchase_inward"] == 100.0
    assert mb_summary["sales_outward"] == 8.0  # 5 + 3
    assert mb_summary["valuation_rate"] == 8.0 # Purchased @ 8.0
    assert mb_summary["stock_value"] == round(92.0 * 8.0, 2)

    # =========================================================================
    # STEP 5: TEST E — Purchase Return (Return 10 packets)
    # =========================================================================
    pret_res = purc_svc.create_purchase_return("C1", {
        "original_voucher_id": purc_res["voucher_id"],
        "supplier_name": "ABC DISTRIBUTORS",
        "branch_id": "B1",
        "reason": "10 damaged packets returned to supplier",
        "items": [
            {
                "item_id": item_id,
                "name": "MILK BIKIS",
                "qty": 10.0,
                "rate": 8.0,
                "tax_rate": 5.0
            }
        ]
    })
    # Stock must reduce from 92 to 82
    assert inv_svc.get_stock("C1", item_id, "B1") == 82.0

    # =========================================================================
    # STEP 6: TEST F — Sales Return (Return 2 packets from customer)
    # =========================================================================
    sret_res = bill_svc.create_sales_return("C1", {
        "original_voucher_id": trad_sale["voucher_id"],
        "customer_name": "LOCAL CUSTOMER",
        "branch_id": "B1",
        "reason": "Customer overbought 2 packets",
        "items": [
            {
                "item_id": item_id,
                "name": "MILK BIKIS",
                "qty": 2.0,
                "rate": 10.0,
                "tax_rate": 5.0,
                "restock_condition": "SALEABLE"
            }
        ]
    })
    # Stock must increase from 82 to 84
    assert inv_svc.get_stock("C1", item_id, "B1") == 84.0

    # =========================================================================
    # STEP 7: TEST G — Stock Adjustment (Damage 4 packets)
    # =========================================================================
    adj_res = inv_svc.record_stock_adjustment("C1", {
        "branch_id": "B1",
        "adj_type": "DAMAGE",
        "reason": "Water damage in carton",
        "items": [
            {
                "item_id": item_id,
                "system_qty": 84.0,
                "physical_qty": 80.0,
                "diff_qty": -4.0,
                "unit_cost": 8.0
            }
        ]
    })
    # Stock must reduce from 84 to 80
    assert inv_svc.get_stock("C1", item_id, "B1") == 80.0

    # =========================================================================
    # STEP 8: TEST H — Stock Transfer (10 packets B1 -> B2)
    # =========================================================================
    trf_res = inv_svc.record_stock_transfer("C1", {
        "source_branch_id": "B1",
        "dest_branch_id": "B2",
        "reason": "Restock warehouse B2",
        "items": [
            {
                "item_id": item_id,
                "qty": 10.0,
                "unit_cost": 8.0
            }
        ]
    })
    # B1 decreases from 80 to 70
    assert inv_svc.get_stock("C1", item_id, "B1") == 70.0
    # B2 increases from 0 to 10
    assert inv_svc.get_stock("C1", item_id, "B2") == 10.0
    # Company-wide total stock remains 80.0
    assert inv_svc.get_stock("C1", item_id) == 80.0

    # =========================================================================
    # STEP 9: TEST I & J — Chronological Stock Item Ledger & Day Book
    # =========================================================================
    ledger_res = inv_svc.get_stock_item_ledger("C1", item_id, "B1")
    assert ledger_res["closing_balance"] == 70.0
    tx_types = [entry["transaction_type"] for entry in ledger_res["ledger"]]
    assert "PURCHASE" in tx_types
    assert "SALE" in tx_types
    assert "PURCHASE_RETURN" in tx_types
    assert "SALES_RETURN" in tx_types
    assert "DAMAGE" in tx_types
    assert "TRANSFER_OUT" in tx_types

    # Day Book Verification
    day_book = acc_svc.get_day_book("C1")
    assert len(day_book) >= 4

    # Trial Balance Verification
    tb = acc_svc.get_trial_balance("C1")
    assert tb["is_balanced"] is True
    assert tb["total_debit"] > 0
    assert tb["total_credit"] > 0


def test_ocr_document_extraction_to_draft(erp_db):
    cat_svc = CatalogueService(erp_db)
    ocr_svc = OCRService(erp_db)

    # Create catalog item
    cat_svc.save_item("C1", {
        "name": "PARLE HIDE & SEEK",
        "alias": "890_TEST_002",
        "sales_price": 20.0,
        "purc_price": 16.0,
        "tax_category": "GST 18%"
    })

    sample_invoice_text = """
    TAX INVOICE
    SUPPLIER: METRO CASH & CARRY INDIA PVT LTD
    GSTIN: 33AABCM1234D1Z2
    Invoice No: MCC/2026/8942
    Date: 01/11/2026

    Item Description          Qty    Rate    Taxable   GST%   Total
    PARLE HIDE & SEEK 100G    50     16.00   800.00    18%    944.00
    Total Amount: 944.00
    """

    res = ocr_svc.process_invoice_document("C1", sample_invoice_text, "metro_bill.txt")
    assert res["supplier_invoice_no"] == "MCC/2026/8942"
    assert res["supplier_gstin"] == "33AABCM1234D1Z2"
    assert len(res["items"]) >= 1
    assert "PARLE HIDE & SEEK" in res["items"][0]["name"]
    assert res["draft_id"] is not None

