"""
Unit tests for Odonil Room Spray – Lavender Mist (Barcode: 8901207033728).
Validates catalogue insertion, idempotency, search by name/brand/barcode,
barcode lookup across scanning workflows, and unconfigured price checkout protection.
"""
import pytest
from db.database import DatabaseManager
from services.catalogue_service import CatalogueService
from add_odonil_product import add_or_update_odonil_product, ODONIL_PRODUCT


@pytest.fixture
def odonil_test_env(tmp_path):
    db_file = tmp_path / "odonil_test.db"
    manager = DatabaseManager(db_file)
    manager.run_migrations()

    with manager.get_connection() as conn:
        conn.execute("""
            INSERT INTO companies (id, code, name, fin_year, gstin, state)
            VALUES ('C_ODONIL', 'COMP0001', 'ANTI MATRIX TEST STORE', '2026-27', '33AAAPL1234F1Z1', 'Tamilnadu');
        """)
        conn.execute("""
            INSERT INTO branches (id, company_id, code, name, is_default)
            VALUES ('B_ODONIL', 'C_ODONIL', 'BR01', 'Main Branch', 1);
        """)
        conn.commit()

    return manager


def test_odonil_catalogue_addition_and_idempotency(odonil_test_env):
    cat_svc = CatalogueService(odonil_test_env)

    # 1. Initial Addition
    res1 = add_or_update_odonil_product(company_id="C_ODONIL", db=odonil_test_env)
    assert res1["success"] is True
    assert res1["action"] == "new_item_created"
    prod_id = res1["product_id"]
    assert prod_id is not None
    assert res1["barcode"] == "8901207033728"
    assert res1["barcode_format"] == "EAN-13"

    # 2. Verify stored catalogue fields
    item = cat_svc.get_item_by_id("C_ODONIL", prod_id)
    assert item is not None
    assert item["name"] == "ODONIL ROOM SPRAY - LAVENDER MIST"
    assert item["print_name"] == "Odonil Room Spray – Lavender Mist"
    assert item["item_group"] == "Home Care / Air Freshener"
    assert item["unit"] == "Can"
    assert item["sales_price"] == 0.0  # Unconfigured per requirement 7
    assert item["purc_price"] == 0.0
    assert item["mrp"] == 0.0
    assert item["current_stock"] == 0.0
    assert item["is_verified"] == 0   # Blocked from checkout until configured
    assert "8901207033728" in item["barcodes"]

    # 3. Idempotency Check: Running addition a second time must NOT create duplicate records
    res2 = add_or_update_odonil_product(company_id="C_ODONIL", db=odonil_test_env)
    assert res2["success"] is True
    assert res2["action"] == "existing_barcode_found"
    assert res2["product_id"] == prod_id

    # Verify database still has exactly 1 product with this name and barcode
    with odonil_test_env.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM items WHERE company_id = 'C_ODONIL' AND name = ?;", (ODONIL_PRODUCT["name"],))
        assert cursor.fetchone()["count"] == 1

        cursor.execute("SELECT COUNT(*) as count FROM item_barcodes WHERE company_id = 'C_ODONIL' AND barcode = ?;", ("8901207033728",))
        assert cursor.fetchone()["count"] == 1


def test_odonil_search_by_name_brand_barcode(odonil_test_env):
    add_or_update_odonil_product(company_id="C_ODONIL", db=odonil_test_env)
    cat_svc = CatalogueService(odonil_test_env)

    # Search by full product name
    res_name = cat_svc.search_items("C_ODONIL", "Odonil Room Spray")
    assert len(res_name) >= 1
    assert any(it["name"] == "ODONIL ROOM SPRAY - LAVENDER MIST" for it in res_name)

    # Search by brand ("Odonil")
    res_brand = cat_svc.search_items("C_ODONIL", "Odonil")
    assert len(res_brand) >= 1
    assert any(it["name"] == "ODONIL ROOM SPRAY - LAVENDER MIST" for it in res_brand)

    # Search by fragrance ("Lavender")
    res_frag = cat_svc.search_items("C_ODONIL", "Lavender")
    assert len(res_frag) >= 1
    assert any(it["name"] == "ODONIL ROOM SPRAY - LAVENDER MIST" for it in res_frag)

    # Search by Category ("Air Freshener")
    res_cat = cat_svc.search_items("C_ODONIL", "Air Freshener")
    assert len(res_cat) >= 1
    assert any(it["name"] == "ODONIL ROOM SPRAY - LAVENDER MIST" for it in res_cat)

    # Search by Barcode ("8901207033728")
    res_barcode = cat_svc.search_items("C_ODONIL", "8901207033728")
    assert len(res_barcode) >= 1
    assert any(it["name"] == "ODONIL ROOM SPRAY - LAVENDER MIST" for it in res_barcode)


def test_odonil_barcode_lookup_and_cart_checkout_protection(odonil_test_env):
    add_or_update_odonil_product(company_id="C_ODONIL", db=odonil_test_env)
    cat_svc = CatalogueService(odonil_test_env)

    # Barcode lookup simulation (as performed by USB scanner, mobile scanner, and manual entry)
    found_item = cat_svc.find_by_barcode("C_ODONIL", "8901207033728")
    assert found_item is not None
    assert found_item["name"] == "ODONIL ROOM SPRAY - LAVENDER MIST"
    assert found_item["unit"] == "Can"
    assert found_item["matched_barcode"] == "8901207033728"
    assert found_item["sales_price"] == 0.0
    assert found_item["is_verified"] == 0

    # Fast Billing Cart simulation:
    cart = [
        {
            "id": found_item["id"],
            "name": found_item["name"],
            "barcode": found_item["matched_barcode"],
            "unit": found_item["unit"],
            "price": found_item["sales_price"],
            "is_verified": found_item["is_verified"],
            "qty": 1.0
        }
    ]

    # Verify checkout blocking rule:
    # Any item with price <= 0 or is_verified == 0 must be rejected
    unverified = [it for it in cart if it["price"] <= 0 or it["is_verified"] == 0]
    assert len(unverified) == 1
    assert unverified[0]["name"] == "ODONIL ROOM SPRAY - LAVENDER MIST"
    assert unverified[0]["unit"] == "Can"

