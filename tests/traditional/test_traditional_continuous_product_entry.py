"""
Test Suite: Traditional Billing Continuous Product Entry Mode (Backend).

Verifies:
1. Sequential entry of multiple products into Traditional Billing database.
2. Saved products remain in database and are fully retrievable.
3. Each product receives its own distinct barcode / SKU without reuse.
4. Modify mode updates existing products in place without duplicating records.
5. Validation failures (e.g. selling price > MRP, missing name/SKU) are rejected cleanly.
6. Fast Billing database (data/anti_matrix_billing.db) remains 100% frozen and isolated.
"""

from pathlib import Path
from decimal import Decimal
import hashlib
import pytest
from sqlalchemy import select, and_
from alembic.config import Config
from alembic import command

from db.traditional_database import TraditionalDatabaseManager
from db.traditional_models import Item, ItemBarcode
from services.traditional_company_service import TraditionalCompanyService
from services.traditional_product_service import TraditionalProductService


FAST_BILLING_DB_PATH = Path("data/anti_matrix_billing.db")
FAST_BILLING_EXPECTED_SHA256 = "bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd"


@pytest.fixture
def product_env(tmp_path):
    """Isolated SQLite database with Alembic schema for continuous product entry tests."""
    db_file = tmp_path / "test_continuous_prod.db"
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
        "name": "Alpha Continuous Entry Ltd",
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


def test_sequential_product_entry_and_persistence(product_env):
    """
    Test 1 & 4: Sequential creation of multiple products simulates operator continuous entry.
    Verifies that all saved products persist in the database and remain accessible.
    """
    prod_service = product_env["product_service"]
    cid = product_env["company_id"]
    uid = product_env["user_id"]

    products_to_enter = [
        {
            "name": "Milk Bikis 100g",
            "alias": "AMMILK000001",
            "sellingPrice": "20.00",
            "cogsAmount": "15.00",
            "mrp": "22.00",
            "unit": "Pcs.",
            "taxCategory": "GST 18%",
        },
        {
            "name": "Good Day Butter 100g",
            "alias": "AMGDAY000001",
            "sellingPrice": "30.00",
            "cogsAmount": "22.00",
            "mrp": "35.00",
            "unit": "Pcs.",
            "taxCategory": "GST 18%",
        },
        {
            "name": "50-50 Maska Chaska 50g",
            "alias": "AM5050000001",
            "sellingPrice": "10.00",
            "cogsAmount": "7.50",
            "mrp": "10.00",
            "unit": "Pcs.",
            "taxCategory": "GST 18%",
        },
    ]

    saved_records = []
    for p_data in products_to_enter:
        res = prod_service.save_product(cid, uid, p_data)
        assert res["id"] is not None
        assert res["name"] == p_data["name"]
        saved_records.append(res)

    assert len(saved_records) == 3

    # Verify all 3 are stored in the database
    with product_env["trad_mgr"].session_scope() as session:
        items = session.scalars(
            select(Item).where(Item.company_id == cid).order_by(Item.name)
        ).all()
        assert len(items) == 3
        item_names = {i.name for i in items}
        assert item_names == {
            "Milk Bikis 100g",
            "Good Day Butter 100g",
            "50-50 Maska Chaska 50g",
        }

    # Verify catalogue listing retrievability
    catalog = prod_service.list_products(cid, active_only=True)
    assert len(catalog) == 3


def test_barcode_cleared_and_not_reused(product_env):
    """
    Test 3: Each entered product uses its own distinct barcode / SKU.
    Reusing an existing barcode for a different product must fail.
    """
    prod_service = product_env["product_service"]
    cid = product_env["company_id"]
    uid = product_env["user_id"]

    # Save Product 1 with barcode BC001
    prod1 = prod_service.save_product(cid, uid, {
        "name": "Product Alpha",
        "alias": "AM0000000001",
        "sellingPrice": "100.00",
    })
    assert prod1["id"] is not None

    # Save Product 2 with same barcode BC001 must raise duplicate SKU / barcode error
    with pytest.raises(ValueError, match="(already exists|already assigned)"):
        prod_service.save_product(cid, uid, {
            "name": "Product Beta",
            "alias": "AM0000000001",
            "sellingPrice": "150.00",
        })

    # Save Product 2 with distinct barcode succeeds
    prod2 = prod_service.save_product(cid, uid, {
        "name": "Product Beta",
        "alias": "AM0000000002",
        "sellingPrice": "150.00",
    })
    assert prod2["id"] is not None


def test_modify_mode_updates_in_place(product_env):
    """
    Test 8: Modify mode updates the existing product without creating duplicate items.
    """
    prod_service = product_env["product_service"]
    cid = product_env["company_id"]
    uid = product_env["user_id"]

    # Initial save
    saved = prod_service.save_product(cid, uid, {
        "name": "Korean noodles",
        "alias": "AMJVY2Y7DCEA",
        "sellingPrice": "120.00",
        "cogsAmount": "90.00",
        "mrp": "140.00",
    })
    item_id = saved["id"]

    # Modify the product (price updated to 130.00)
    updated = prod_service.save_product(cid, uid, {
        "id": item_id,
        "name": "Korean noodles",
        "alias": "AMJVY2Y7DCEA",
        "sellingPrice": "130.00",
        "cogsAmount": "90.00",
        "mrp": "140.00",
    })

    assert updated["id"] == item_id
    assert Decimal(updated["sellingPrice"]) == Decimal("130.00")

    # Confirm database count is still 1 (no duplicate created)
    with product_env["trad_mgr"].session_scope() as session:
        items = session.scalars(select(Item).where(Item.company_id == cid)).all()
        assert len(items) == 1
        assert items[0].id == item_id
        assert items[0].selling_price == Decimal("130.00")


def test_failed_save_leaves_database_intact(product_env):
    """
    Test 5: When validation fails, the database remains in a consistent state.
    """
    prod_service = product_env["product_service"]
    cid = product_env["company_id"]
    uid = product_env["user_id"]

    # Save a valid product first
    prod_service.save_product(cid, uid, {
        "name": "Valid Product",
        "alias": "AMVALID00001",
        "sellingPrice": "50.00",
    })

    # Attempt save with invalid pricing: Selling price > MRP
    with pytest.raises(ValueError, match="cannot exceed MRP"):
        prod_service.save_product(cid, uid, {
            "name": "Invalid Price Product",
            "alias": "AMINVAL00001",
            "sellingPrice": "200.00",
            "mrp": "150.00",
        })

    # Database only contains the 1 valid product
    catalog = prod_service.list_products(cid)
    assert len(catalog) == 1
    assert catalog[0]["name"] == "Valid Product"


def test_fast_billing_isolation():
    """
    Test 9: Verify that Fast Billing SQLite database is completely untouched.
    """
    assert FAST_BILLING_DB_PATH.exists(), "Fast Billing database file must exist"
    data = FAST_BILLING_DB_PATH.read_bytes()
    current_hash = hashlib.sha256(data).hexdigest()
    assert current_hash == FAST_BILLING_EXPECTED_SHA256, (
        f"CRITICAL: Fast Billing database hash mismatch! Expected {FAST_BILLING_EXPECTED_SHA256}, got {current_hash}"
    )
