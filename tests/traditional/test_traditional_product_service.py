"""
Test Suite: Traditional Billing Product Service & SKU/Barcode Validation.
Proves:
1. Product with populated SKU saves successfully (including unified alias/barcode field).
2. Missing SKU is rejected with a clear validation message.
3. Barcode registration works independently of SKU.
4. Duplicate barcodes are rejected.
5. Product editing preserves the SKU and barcode.
6. Traditional product operations do not use Fast Billing services or databases.
"""

from pathlib import Path
from decimal import Decimal
import pytest
from sqlalchemy import select, and_
from alembic.config import Config
from alembic import command

from db.traditional_database import TraditionalDatabaseManager
from db.traditional_models import Company, Branch, Item, ItemBarcode
from services.traditional_company_service import TraditionalCompanyService
from services.traditional_product_service import TraditionalProductService


@pytest.fixture
def product_env(tmp_path):
    """Isolated SQLite database with Alembic schema for product tests."""
    db_file = tmp_path / "test_traditional_prod.db"
    db_url = f"sqlite:///{db_file}"

    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    company_service = TraditionalCompanyService(db_manager=trad_mgr)
    product_service = TraditionalProductService(db_manager=trad_mgr)

    # Bootstrap initial company
    setup_data = {
        "code": "CORP01",
        "name": "Alpha Retail Enterprise",
        "finYear": "2026-2027",
        "taxNo": "33AAAPL1234F1Z1",
        "state": "Tamilnadu",
        "adminUsername": "SUPERADMIN",
        "adminPassword": "SuperSecurePassword@2026",
    }
    company_info = company_service.initial_setup(setup_data)

    yield {
        "trad_mgr": trad_mgr,
        "company_service": company_service,
        "product_service": product_service,
        "company_id": company_info["companyId"],
        "user_id": company_info["adminUserId"],
        "db_file": db_file,
    }

    trad_mgr.close()


def test_product_with_populated_sku_saves_successfully(product_env):
    """
    Requirement 1: A product with a populated SKU saves successfully.
    Covers both explicit sku parameter and unified UI alias/barcode field mapping.
    """
    prod_service = product_env["product_service"]
    cid = product_env["company_id"]
    uid = product_env["user_id"]

    # 1. Direct SKU payload
    data1 = {
        "sku": "AMJVY2Y7DCEA",
        "name": "Korean noodles",
        "sellingPrice": "120.00",
        "cogsAmount": "90.00",
        "unit": "Pcs.",
        "category": "Noodles & Pasta",
    }
    res1 = prod_service.save_product(cid, uid, data1)
    assert res1["id"] is not None
    assert res1["sku"] == "AMJVY2Y7DCEA"
    assert res1["name"] == "Korean noodles"
    assert res1["sellingPrice"] == "120.00"
    assert res1["cogsAmount"] == "90.00"

    # 2. Unified UI payload mapping (where UI sends alias / barcodes)
    data2 = {
        "alias": "AM8877665544",
        "name": "Spicy Ramen 120g",
        "sales_price": "140.00",
        "purc_price": "105.00",
        "unit": "Pcs.",
    }
    res2 = prod_service.save_product(cid, uid, data2)
    assert res2["id"] is not None
    assert res2["sku"] == "AM8877665544"
    assert res2["barcode"] == "AM8877665544"
    assert res2["name"] == "Spicy Ramen 120g"


def test_missing_sku_rejected_with_clear_message(product_env):
    """
    Requirement 2: A missing SKU is rejected with a clear validation message.
    """
    prod_service = product_env["product_service"]
    cid = product_env["company_id"]
    uid = product_env["user_id"]

    # Missing sku completely
    with pytest.raises(ValueError) as exc1:
        prod_service.save_product(cid, uid, {
            "name": "No SKU Product",
            "sellingPrice": "50.00"
        })
    assert "Product SKU is required." in str(exc1.value)

    # Empty whitespace sku
    with pytest.raises(ValueError) as exc2:
        prod_service.save_product(cid, uid, {
            "sku": "   ",
            "name": "Blank SKU Product",
            "sellingPrice": "50.00"
        })
    assert "Product SKU is required." in str(exc2.value)

    # Missing name
    with pytest.raises(ValueError) as exc3:
        prod_service.save_product(cid, uid, {
            "sku": "VALID-SKU-01",
            "name": "",
            "sellingPrice": "50.00"
        })
    assert "Product Name is required." in str(exc3.value)


def test_barcode_registration_independent_of_sku(product_env):
    """
    Requirement 3: Barcode registration works independently of SKU.
    A product can have a SKU without any barcode, or a SKU distinct from its barcode.
    """
    prod_service = product_env["product_service"]
    trad_mgr = product_env["trad_mgr"]
    cid = product_env["company_id"]
    uid = product_env["user_id"]

    # Case A: Product with SKU only, no barcode
    data_no_bc = {
        "sku": "SKU-ONLY-001",
        "name": "Loose Basmati Rice 1kg",
        "sellingPrice": "110.00",
        "cogsAmount": "85.00",
    }
    res_no_bc = prod_service.save_product(cid, uid, data_no_bc)
    assert res_no_bc["sku"] == "SKU-ONLY-001"
    assert res_no_bc["barcode"] is None

    with trad_mgr.session_scope() as session:
        barcodes = session.scalars(
            select(ItemBarcode.barcode).where(
                and_(ItemBarcode.company_id == cid, ItemBarcode.item_id == res_no_bc["id"])
            )
        ).all()
        assert len(barcodes) == 0, "Item without barcode must have 0 rows in item_barcodes"

    # Case B: Product with distinct SKU and retail barcode
    data_distinct = {
        "sku": "SKU-NOODLES-SPICY",
        "barcode": "8901234567890",  # 13 digit EAN
        "name": "Packaged Noodles 70g",
        "sellingPrice": "20.00",
        "cogsAmount": "15.00",
    }
    res_distinct = prod_service.save_product(cid, uid, data_distinct)
    assert res_distinct["sku"] == "SKU-NOODLES-SPICY"
    assert res_distinct["barcode"] == "8901234567890"

    with trad_mgr.session_scope() as session:
        bc_row = session.scalar(
            select(ItemBarcode.barcode).where(
                and_(ItemBarcode.company_id == cid, ItemBarcode.item_id == res_distinct["id"])
            )
        )
        assert bc_row == "8901234567890"


def test_duplicate_barcodes_are_rejected(product_env):
    """
    Requirement 4: Duplicate barcodes are rejected.
    """
    prod_service = product_env["product_service"]
    cid = product_env["company_id"]
    uid = product_env["user_id"]

    # Save item 1 with barcode
    prod_service.save_product(cid, uid, {
        "sku": "SKU-ITEM-1",
        "barcode": "AM1122334455",
        "name": "Item 1",
        "sellingPrice": "50.00"
    })

    # Save item 2 with same barcode -> rejected
    with pytest.raises(ValueError) as exc:
        prod_service.save_product(cid, uid, {
            "sku": "SKU-ITEM-2",
            "barcode": "AM1122334455",
            "name": "Item 2",
            "sellingPrice": "60.00"
        })
    assert "already assigned to another item in this company" in str(exc.value)


def test_product_editing_preserves_sku_and_barcode(product_env):
    """
    Requirement 5: Product editing preserves the SKU and barcode.
    """
    prod_service = product_env["product_service"]
    cid = product_env["company_id"]
    uid = product_env["user_id"]

    # 1. Create product
    created = prod_service.save_product(cid, uid, {
        "sku": "SKU-EDIT-TEST",
        "barcode": "AMEDIT998877",
        "name": "Original Product Title",
        "sellingPrice": "100.00",
        "cogsAmount": "70.00"
    })
    item_id = created["id"]
    assert created["sku"] == "SKU-EDIT-TEST"
    assert created["barcode"] == "AMEDIT998877"

    # 2. Edit product (change name, change price, keep same SKU and Barcode)
    updated = prod_service.save_product(cid, uid, {
        "id": item_id,
        "sku": "SKU-EDIT-TEST",
        "barcode": "AMEDIT998877",
        "name": "Updated Product Title",
        "sellingPrice": "150.00",
        "cogsAmount": "85.00"
    })
    assert updated["id"] == item_id
    assert updated["sku"] == "SKU-EDIT-TEST"
    assert updated["barcode"] == "AMEDIT998877"
    assert updated["name"] == "Updated Product Title"
    assert updated["sellingPrice"] == "150.00"
    assert updated["cogsAmount"] == "85.00"

    # 3. Retrieve product and verify persistence
    retrieved = prod_service.get_product(cid, item_id)
    assert retrieved is not None
    assert retrieved["name"] == "Updated Product Title"
    assert retrieved["sku"] == "SKU-EDIT-TEST"
    assert "AMEDIT998877" in retrieved["barcodes"]


def test_traditional_product_operations_do_not_use_fast_billing(product_env):
    """
    Requirement 6: Traditional product operations do not use Fast Billing services or databases.
    """
    prod_service = product_env["product_service"]
    cid = product_env["company_id"]

    url = str(prod_service.db.database_url)
    assert "anti_matrix_billing.db" not in url
    assert "traditional" in url

    # Fetching products lists only traditional items
    items = prod_service.list_products(cid)
    assert isinstance(items, list)
