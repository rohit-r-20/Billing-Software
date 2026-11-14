"""
Test Suite: Traditional Billing Sales Pricing & Invoice Product Lookup.

Verifies:
1. Selecting a product (such as Milk) fetches the saved selling price from the database.
2. Product lookup by SKU works.
3. Product lookup by primary barcode works.
4. Product lookup by alternate barcode works.
5. Product unit of measurement, tax category, tax rate, and HSN are populated correctly.
6. Line amount calculation: quantity * unit_selling_price.
7. GST treatment: intra-state (CGST + SGST split) and inter-state (IGST).
8. Inactive or unknown products are rejected.
9. Tenant isolation: cross-company product access is rejected.
10. Backend invoice save validates prices against the database, rejecting manipulated prices.
11. Fast Billing database integrity: anti_matrix_billing.db is untouched.
"""

from pathlib import Path
from decimal import Decimal
import hashlib
import json
import uuid
import pytest
from sqlalchemy import select, and_
from alembic.config import Config
from alembic import command

from db.traditional_database import TraditionalDatabaseManager
from db.traditional_models import Company, Branch, Item, ItemBarcode
from services.traditional_company_service import TraditionalCompanyService
from services.traditional_product_service import TraditionalProductService
from desktop.web_bridge import BackendBridge


@pytest.fixture
def sales_pricing_env(tmp_path):
    """Isolated SQLite database with Alembic schema for sales pricing tests."""
    db_file = tmp_path / "test_sales_pricing.db"
    db_url = f"sqlite:///{db_file}"

    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    company_service = TraditionalCompanyService(db_manager=trad_mgr)
    product_service = TraditionalProductService(db_manager=trad_mgr)

    # 1. Bootstrap Company A
    comp_a = company_service.initial_setup({
        "code": "COMP_A",
        "name": "Company Alpha Retail",
        "finYear": "2026-2027",
        "taxNo": "33AAAPL1234F1Z1",
        "state": "Tamilnadu",
        "adminUsername": "ADMIN_A",
        "adminPassword": "SuperPassword@2026",
    })

    # 2. Add Company B directly to DB for tenant isolation testing
    comp_b_id = str(uuid.uuid4())
    with trad_mgr.session_scope() as session:
        session.add(
            Company(
                id=comp_b_id,
                code="COMP_B",
                name="Company Beta Wholesale",
                fin_year="2026-2027",
                state="Karnataka",
                is_active=True,
            )
        )

    yield {
        "trad_mgr": trad_mgr,
        "company_service": company_service,
        "product_service": product_service,
        "company_a_id": comp_a["companyId"],
        "user_a_id": comp_a["adminUserId"],
        "company_b_id": comp_b_id,
        "user_b_id": comp_a["adminUserId"],
        "db_file": db_file,
    }

    trad_mgr.close()


def test_select_product_retrieves_saved_selling_price(sales_pricing_env):
    """
    Requirement 1: Product selection by name (Milk) retrieves saved selling price (e.g. 35.00).
    Price must come directly from database selling_price, never default to 0.00 or COGS.
    """
    prod_service = sales_pricing_env["product_service"]
    cid = sales_pricing_env["company_a_id"]
    uid = sales_pricing_env["user_a_id"]

    # Save Milk with selling price 35.00 and COGS 28.00
    milk_data = {
        "sku": "AMMILK001",
        "name": "Aavin Full Cream Milk 500ml",
        "unit": "Pkt",
        "selling_price": "35.00",
        "cogs_amount": "28.00",
        "tax_category": "GST 5%",
        "tax_rate_percent": "5.00",
        "hsn": "0401",
    }
    saved_milk = prod_service.save_product(cid, uid, milk_data)
    assert saved_milk["sellingPrice"] == "35.00"

    # Lookup by name
    res = prod_service.lookup_product(cid, "Aavin Full Cream Milk 500ml")
    assert res is not None
    assert res["name"] == "Aavin Full Cream Milk 500ml"
    assert res["sellingPrice"] == "35.00"
    assert res["selling_price"] == "35.00"
    assert res["sales_price"] == "35.00"
    assert res["cogsAmount"] == "28.00"
    assert res["selling_price"] != res["cogs_amount"]  # Never fallback to COGS!


def test_product_lookup_by_sku_and_barcodes(sales_pricing_env):
    """
    Requirements 2, 3, 4:
    Product selection works by:
    - SKU
    - Primary barcode
    - Alternate barcode
    """
    prod_service = sales_pricing_env["product_service"]
    cid = sales_pricing_env["company_a_id"]
    uid = sales_pricing_env["user_a_id"]

    # Save a product with primary barcode
    prod_data = {
        "sku": "SKU-TEA-100G",
        "name": "Premium Tea 100g",
        "unit": "Pcs.",
        "selling_price": "85.50",
        "cogs_amount": "60.00",
        "barcode": "AMTEA0000001",
        "tax_category": "GST 5%",
        "tax_rate_percent": "5.00",
        "hsn": "0902",
    }
    saved = prod_service.save_product(cid, uid, prod_data)
    item_id = saved["id"]

    # Add alternate barcode
    alt_barcode = "ALTTEA888999"
    prod_service.add_barcode(cid, item_id, alt_barcode)

    # 1. Lookup by SKU
    by_sku = prod_service.lookup_product(cid, "SKU-TEA-100G")
    assert by_sku is not None
    assert by_sku["id"] == item_id
    assert by_sku["sellingPrice"] == "85.50"

    # 2. Lookup by Primary Barcode
    by_pri = prod_service.lookup_product(cid, "AMTEA0000001")
    assert by_pri is not None
    assert by_pri["id"] == item_id
    assert by_pri["sellingPrice"] == "85.50"

    # 3. Lookup by Alternate Barcode
    by_alt = prod_service.lookup_product(cid, "ALTTEA888999")
    assert by_alt is not None
    assert by_alt["id"] == item_id
    assert by_alt["sellingPrice"] == "85.50"


def test_product_metadata_population(sales_pricing_env):
    """
    Requirement 5: Unit of measurement, GST category, tax rate, and HSN populated correctly.
    """
    prod_service = sales_pricing_env["product_service"]
    cid = sales_pricing_env["company_a_id"]
    uid = sales_pricing_env["user_a_id"]

    prod_data = {
        "sku": "SKU-SHAMPOO-01",
        "name": "Herbal Shampoo 200ml",
        "unit": "Bottle",
        "selling_price": "199.00",
        "cogs_amount": "130.00",
        "tax_category": "GST 18%",
        "tax_rate_percent": "18.00",
        "hsn": "3305",
    }
    saved = prod_service.save_product(cid, uid, prod_data)

    lookup = prod_service.lookup_product(cid, "SKU-SHAMPOO-01")
    assert lookup["unit"] == "Bottle"
    assert lookup["taxCategory"] == "GST 18%"
    assert lookup["taxRatePercent"] == "18.00"
    assert lookup["hsn"] == "3305"


def test_line_amount_and_quantity_calculation(sales_pricing_env):
    """
    Requirement 6: Quantity changes recalculate line amount:
    line_amount = quantity * unit_selling_price (less discount).
    """
    prod_service = sales_pricing_env["product_service"]
    cid = sales_pricing_env["company_a_id"]
    uid = sales_pricing_env["user_a_id"]

    prod_data = {
        "sku": "SKU-OIL-1L",
        "name": "Refined Sunflower Oil 1L",
        "unit": "Pouch",
        "selling_price": "145.00",
        "cogs_amount": "120.00",
    }
    saved = prod_service.save_product(cid, uid, prod_data)

    # Validate items with quantity = 3
    items_to_validate = [
        {
            "item_id": saved["id"],
            "qty": 3,
            "selling_price": "145.00",
        }
    ]
    val_items = prod_service.validate_invoice_items(cid, items_to_validate)
    assert len(val_items) == 1
    # 3 * 145.00 = 435.00
    assert val_items[0]["qty"] == "3"
    assert val_items[0]["selling_price"] == "145.00"
    assert val_items[0]["gross_amount"] == "435.00"
    assert val_items[0]["amount"] == "435.00"


def test_gst_calculations_intra_state_and_inter_state(sales_pricing_env):
    """
    Requirement 7: GST calculations for intra-state and inter-state vouchers.
    - Intra-state (L/GST-18%): Subtotal * 9% CGST + Subtotal * 9% SGST.
    - Inter-state (I/GST-18%): Subtotal * 18% IGST.
    - Exact Decimal arithmetic, round-off, and grand total.
    """
    prod_service = sales_pricing_env["product_service"]
    cid = sales_pricing_env["company_a_id"]
    uid = sales_pricing_env["user_a_id"]

    prod1 = prod_service.save_product(cid, uid, {
        "sku": "ITEM-GST-1",
        "name": "Electronics Item 1",
        "selling_price": "1000.00",
    })

    items = prod_service.validate_invoice_items(cid, [
        {"item_id": prod1["id"], "qty": 1, "selling_price": "1000.00"}
    ])

    # 1. Intra-State (L/GST-18%)
    intra_totals = prod_service.calculate_invoice_totals(items, sale_type="L/GST-18%")
    assert intra_totals["subtotal"] == "1000.00"
    assert intra_totals["cgst_amount"] == "90.00"
    assert intra_totals["sgst_amount"] == "90.00"
    assert intra_totals["igst_amount"] == "0.00"
    assert intra_totals["total_tax_amount"] == "180.00"
    assert intra_totals["grand_total"] == "1180"

    # 2. Inter-State (I/GST-18%)
    inter_totals = prod_service.calculate_invoice_totals(items, sale_type="I/GST-18%")
    assert inter_totals["subtotal"] == "1000.00"
    assert inter_totals["cgst_amount"] == "0.00"
    assert inter_totals["sgst_amount"] == "0.00"
    assert inter_totals["igst_amount"] == "180.00"
    assert inter_totals["total_tax_amount"] == "180.00"
    assert inter_totals["grand_total"] == "1180"

    # 3. Round-off precision test with fractional total
    prod2 = prod_service.save_product(cid, uid, {
        "sku": "ITEM-GST-2",
        "name": "Fractional Item",
        "selling_price": "33.33",
    })
    fractional_items = prod_service.validate_invoice_items(cid, [
        {"item_id": prod2["id"], "qty": 1, "selling_price": "33.33"}
    ])
    frac_totals = prod_service.calculate_invoice_totals(fractional_items, sale_type="L/GST-18%")
    # 33.33 * 9% = 2.9997 -> rounded to 3.00 CGST, 3.00 SGST
    # Total raw: 33.33 + 3.00 + 3.00 = 39.33 -> grand_total = 39, round_off = -0.33
    assert frac_totals["subtotal"] == "33.33"
    assert frac_totals["cgst_amount"] == "3.00"
    assert frac_totals["sgst_amount"] == "3.00"
    assert frac_totals["grand_total"] == "39"
    assert frac_totals["round_off_amount"] == "-0.33"


def test_inactive_and_unknown_products_rejected(sales_pricing_env):
    """
    Requirement 8: Inactive or unknown products are rejected and never produce valid zero-priced lines.
    """
    prod_service = sales_pricing_env["product_service"]
    cid = sales_pricing_env["company_a_id"]
    uid = sales_pricing_env["user_a_id"]

    # 1. Unknown product lookup
    res_none = prod_service.lookup_product(cid, "NON_EXISTENT_PRODUCT_12345")
    assert res_none is None

    # 2. Inactive product
    prod_data = {
        "sku": "SKU-DISCONTINUED",
        "name": "Discontinued Biscuit",
        "selling_price": "50.00",
    }
    saved = prod_service.save_product(cid, uid, prod_data)

    # Deactivate the product directly in DB
    with sales_pricing_env["trad_mgr"].session_scope() as session:
        item = session.scalar(select(Item).where(Item.id == saved["id"]))
        item.is_active = False

    # Lookup must reject inactive product
    with pytest.raises(ValueError, match="inactive"):
        prod_service.lookup_product(cid, "SKU-DISCONTINUED")

    # Invoice validation must reject inactive product
    with pytest.raises(ValueError, match="inactive"):
        prod_service.validate_invoice_items(cid, [{"item_id": saved["id"], "qty": 1, "price": "50.00"}])


def test_tenant_isolation_rejects_cross_company_access(sales_pricing_env):
    """
    Requirement 9: Tenant isolation: products belonging to Company A cannot be retrieved or billed by Company B.
    """
    prod_service = sales_pricing_env["product_service"]
    cid_a = sales_pricing_env["company_a_id"]
    uid_a = sales_pricing_env["user_a_id"]
    cid_b = sales_pricing_env["company_b_id"]

    # Create product in Company A
    prod_a = prod_service.save_product(cid_a, uid_a, {
        "sku": "SKU-TENANT-A",
        "name": "Alpha Secret Product",
        "selling_price": "999.00",
    })

    # Company B lookup for Company A product returns None
    lookup_b = prod_service.lookup_product(cid_b, "SKU-TENANT-A")
    assert lookup_b is None

    # Company B cannot validate or bill Company A product
    with pytest.raises(ValueError, match="does not exist"):
        prod_service.validate_invoice_items(cid_b, [{"item_id": prod_a["id"], "qty": 1, "price": "999.00"}])


def test_backend_invoice_save_rejects_manipulated_prices(sales_pricing_env):
    """
    Requirement 10: Backend invoice save strictly validates product price against database,
    detecting and rejecting manipulated frontend prices.
    """
    prod_service = sales_pricing_env["product_service"]
    cid = sales_pricing_env["company_a_id"]
    uid = sales_pricing_env["user_a_id"]

    # Product with real price 500.00
    prod = prod_service.save_product(cid, uid, {
        "sku": "SKU-SAFE-PRICE",
        "name": "Luxury Perfume",
        "selling_price": "500.00",
    })

    # 1. Frontend submits tampered price (1.00 instead of 500.00)
    hacked_invoice = {
        "party_name": "Suspicious Buyer",
        "sale_type": "L/GST-18%",
        "items": [
            {
                "item_id": prod["id"],
                "name": "Luxury Perfume",
                "qty": 2,
                "price": "1.00",  # Manipulated!
                "amount": "2.00",
            }
        ]
    }

    with pytest.raises(ValueError, match="Manipulated price detected"):
        prod_service.save_sale_invoice(cid, uid, hacked_invoice)

    # 2. Honest invoice with correct price passes
    legit_invoice = {
        "party_name": "Honest Customer",
        "sale_type": "L/GST-18%",
        "items": [
            {
                "item_id": prod["id"],
                "name": "Luxury Perfume",
                "qty": 2,
                "price": "500.00",
                "amount": "1000.00",
            }
        ]
    }

    saved_invoice = prod_service.save_sale_invoice(cid, uid, legit_invoice)
    assert saved_invoice["subtotal"] == "1000.00"
    assert saved_invoice["grand_total"] == "1180"
    assert len(saved_invoice["items"]) == 1
    assert saved_invoice["items"][0]["selling_price"] == "500.00"


def test_fast_billing_database_remains_untouched():
    """
    Requirement 11: Fast Billing SQLite database (anti_matrix_billing.db)
    must remain completely unchanged with exact SHA-256 integrity.
    """
    expected_hash = "bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd"
    fast_db = Path("data/anti_matrix_billing.db")
    assert fast_db.exists(), "Fast Billing database file must exist"

    hasher = hashlib.sha256()
    with open(fast_db, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)

    actual_hash = hasher.hexdigest()
    assert actual_hash == expected_hash, f"Fast Billing DB was modified! Expected {expected_hash}, got {actual_hash}"
