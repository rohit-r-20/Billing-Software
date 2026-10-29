"""
Unit and integration tests for Product Selection, Catalogue Service,
and Desktop WebBridge item management in Anti Matrix Alpha Billing Software.
"""
import json
import pytest
from PyQt5.QtCore import QCoreApplication
from services.catalogue_service import catalogue_service
from desktop.web_bridge import BackendBridge


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance()
    if not app:
        app = QCoreApplication([])
    return app


def test_catalogue_search_items_by_company_code_and_uuid():
    """Verify search_items resolves company code (COMP0001) properly and matches by name, barcode, and group."""
    # 1. Search by product name using company code
    results_code = catalogue_service.search_items("COMP0001", "Milk")
    assert len(results_code) >= 1
    item = results_code[0]
    assert "MILK BIKIS" in item["name"].upper()
    assert item["sales_price"] == 10.0
    assert "890_TEST_001" in (item["barcodes"] or "")

    # 2. Search by exact barcode using company code
    results_barcode = catalogue_service.search_items("COMP0001", "890_TEST_002")
    assert len(results_barcode) >= 1
    assert "HIDE & SEEK" in results_barcode[0]["name"].upper()

    # 3. Search using actual company UUID
    comp_uuid = item["company_id"]
    results_uuid = catalogue_service.search_items(comp_uuid, "Milk")
    assert len(results_uuid) >= 1
    assert results_uuid[0]["id"] == item["id"]


def test_catalogue_get_item_by_id():
    """Verify get_item_by_id retrieves full product details including barcodes and stock."""
    # Search for an item first
    items = catalogue_service.search_items("COMP0001", "Milk")
    assert len(items) > 0
    target_id = items[0]["id"]

    # Retrieve by ID using company code
    item = catalogue_service.get_item_by_id("COMP0001", target_id)
    assert item is not None
    assert item["id"] == target_id
    assert "MILK BIKIS" in item["name"].upper()
    assert item["current_stock"] is not None
    assert item["sales_price"] == 10.0


def test_save_item_update_and_parameter_mapping():
    """Verify save_item handles updates by existing ID and maps camelCase parameters cleanly."""
    # Create or retrieve a test product
    items = catalogue_service.search_items("COMP0001", "TEST_PRODUCT_SEL")
    if items:
        item_id = items[0]["id"]
    else:
        created = catalogue_service.save_item("COMP0001", {
            "name": "TEST_PRODUCT_SEL",
            "alias": "SEL_CODE_001",
            "salesPrice": 45.0,
            "purcPrice": 30.0,
            "group": "Snacks",
            "unit": "Pcs.",
            "opStockQty": 50.0
        })
        item_id = created["id"]

    assert item_id is not None

    # Update item price and category using ID
    updated = catalogue_service.save_item("COMP0001", {
        "id": item_id,
        "name": "TEST_PRODUCT_SEL_UPDATED",
        "alias": "SEL_CODE_001_UPD",
        "salesPrice": 55.50,
        "purcPrice": 38.00,
        "group": "Snacks & Sweets",
        "unit": "Pcs.",
        "opStockQty": 60.0
    })

    assert updated["id"] == item_id
    assert updated["name"] == "TEST_PRODUCT_SEL_UPDATED"
    assert updated["sales_price"] == 55.50

    # Verify retrieval reflects the updated values
    fetched = catalogue_service.get_item_by_id("COMP0001", item_id)
    assert fetched is not None
    assert fetched["name"] == "TEST_PRODUCT_SEL_UPDATED"
    assert fetched["sales_price"] == 55.50
    assert fetched["item_group"] == "Snacks & Sweets"


def test_web_bridge_item_slots(qapp):
    """Verify WebBridge searchItems, getItemById, and saveItem slots return valid JSON."""
    bridge = BackendBridge()

    # 1. Test searchItems slot
    resp_search = bridge.searchItems("COMP0001", "Hide")
    data_search = json.loads(resp_search)
    assert data_search["success"] is True
    assert len(data_search["data"]) >= 1
    assert "HIDE & SEEK" in data_search["data"][0]["name"].upper()

    item_id = data_search["data"][0]["id"]

    # 2. Test getItemById slot
    resp_get = bridge.getItemById("COMP0001", item_id)
    data_get = json.loads(resp_get)
    assert data_get["success"] is True
    assert data_get["data"]["id"] == item_id
    assert data_get["data"]["sales_price"] == 20.0

    # 3. Test findByBarcode slot
    resp_barcode = bridge.findByBarcode("COMP0001", "890_TEST_001")
    data_barcode = json.loads(resp_barcode)
    assert data_barcode["success"] is True
    assert data_barcode["data"]["name"] == "MILK BIKIS [DEMO]"
