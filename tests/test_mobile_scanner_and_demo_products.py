"""
Unit tests for Demo Products Seeding and Mobile Wi-Fi Barcode Scanner Service.
"""
import json
import time
import urllib.request
import urllib.error
import pytest

from db.database import DatabaseManager
from services.catalogue_service import CatalogueService
from services.demo_product_service import DemoProductService, DEMO_PRODUCTS
from services.mobile_scanner_service import MobileScannerService


@pytest.fixture
def scanner_test_env(tmp_path):
    db_file = tmp_path / "scanner_test.db"
    manager = DatabaseManager(db_file)
    manager.run_migrations()

    with manager.get_connection() as conn:
        conn.execute("""
            INSERT INTO companies (id, code, name, fin_year, gstin, state)
            VALUES ('C_DEMO', 'COMP0001', 'ANTI MATRIX TEST STORE', '2026-27', '33AAAPL1234F1Z1', 'Tamilnadu');
        """)
        conn.execute("""
            INSERT INTO branches (id, company_id, code, name, is_default)
            VALUES ('B_DEMO', 'C_DEMO', 'BR01', 'Main Branch', 1);
        """)
        conn.execute("""
            INSERT INTO company_configs (company_id, vch_start, vch_digits, vch_prefix)
            VALUES ('C_DEMO', 1, 4, 'POS-');
        """)
        conn.commit()

    return manager


def test_seed_demo_products_idempotency_and_lookup(scanner_test_env):
    demo_svc = DemoProductService(scanner_test_env)
    cat_svc = CatalogueService(scanner_test_env)

    # 1. First Seed Run
    res1 = demo_svc.seed_demo_products(company_id="C_DEMO")
    assert len(res1["seeded"]) == 3
    assert len(res1["skipped_already_present"]) == 0

    # 2. Verify Milk Bikis
    bikis = cat_svc.find_by_barcode("C_DEMO", "890_TEST_001")
    assert bikis is not None
    assert "MILK BIKIS" in bikis["name"].upper()
    assert bikis["item_group"] == "Biscuits"
    assert bikis["sales_price"] == 10.0
    assert bikis["is_verified"] == 1

    # 3. Verify Hide & Seek
    hns = cat_svc.find_by_barcode("C_DEMO", "890_TEST_002")
    assert hns is not None
    assert "HIDE & SEEK" in hns["name"].upper()
    assert hns["item_group"] == "Biscuits"
    assert hns["sales_price"] == 20.0
    assert hns["is_verified"] == 1

    # 4. Verify Levosalbutamol sulfate (Medical Unconfigured)
    med = cat_svc.find_by_barcode("C_DEMO", "8909263004690")
    assert med is not None
    assert "LEVOSALBUTAMOL" in med["name"].upper()
    assert med["item_group"] == "Medical"
    assert med["sales_price"] == 0.0
    assert med["is_verified"] == 0

    # 5. Verify Company Code Lookup (COMP0001) works identically to UUID (C_DEMO)
    bikis_by_code = cat_svc.find_by_barcode("COMP0001", "890_TEST_001")
    assert bikis_by_code is not None
    assert "MILK BIKIS" in bikis_by_code["name"].upper()

    # 6. Idempotency: Second Seed Run must not duplicate records
    res2 = demo_svc.seed_demo_products(company_id="C_DEMO")
    assert len(res2["seeded"]) == 0
    assert len(res2["skipped_already_present"]) == 3

    # Status inspection
    status = demo_svc.get_status()
    assert len(status) == 3
    verified = [it for it in status if it["sales_price"] > 0]
    unverified = [it for it in status if it["sales_price"] <= 0]
    assert len(verified) == 2
    assert len(unverified) == 1


def test_cleanup_demo_products_safety(scanner_test_env):
    demo_svc = DemoProductService(scanner_test_env)
    cat_svc = CatalogueService(scanner_test_env)

    # Seed products
    demo_svc.seed_demo_products(company_id="C_DEMO")
    assert cat_svc.find_by_barcode("C_DEMO", "890_TEST_001") is not None

    # Simulate a sales voucher referencing Milk Bikis
    bikis = cat_svc.find_by_barcode("C_DEMO", "890_TEST_001")
    with scanner_test_env.get_connection() as conn:
        conn.execute("""
            INSERT INTO sales_vouchers (id, company_id, branch_id, vch_no, vch_date, sale_type, party_name, grand_total)
            VALUES ('VCH_TEST_001', 'C_DEMO', 'B_DEMO', 'POS-0001', '2026-10-29', 'L/GST-18%', 'CASH', 10.0);
        """)
        conn.execute("""
            INSERT INTO sales_voucher_items (id, voucher_id, item_id, sn, item_name, qty, unit, price, amount)
            VALUES ('VITEM_001', 'VCH_TEST_001', ?, 1, 'MILK BIKIS [DEMO]', 1.0, 'Pcs.', 10.0, 10.0);
        """, (bikis["id"],))
        conn.commit()

    # Cleanup demo products
    res_clean = demo_svc.cleanup_demo_products(company_id="C_DEMO")
    # Milk Bikis must be retained because it is referenced in sales_voucher_items!
    retained_names = [item["name"].upper() for item in res_clean["retained_due_to_transactions"]]
    assert any("MILK BIKIS" in name for name in retained_names)
    # Hide & Seek and Levosalbutamol sulfate can be safely deleted
    removed_names = [item["name"].upper() for item in res_clean["removed"]]
    assert any("HIDE & SEEK" in name for name in removed_names)
    assert any("LEVOSALBUTAMOL" in name for name in removed_names)

    # Verify Milk Bikis is preserved
    assert cat_svc.find_by_barcode("C_DEMO", "890_TEST_001") is not None
    # Verify Hide & Seek is removed
    assert cat_svc.find_by_barcode("C_DEMO", "890_TEST_002") is None


def test_mobile_scanner_server_endpoints_and_security(scanner_test_env):
    received_scans = []
    received_statuses = []

    def on_scan(barcode, device):
        received_scans.append((barcode, device))

    def on_status(status, details):
        received_statuses.append((status, details))

    scanner_svc = MobileScannerService(
        scan_callback=on_scan,
        status_callback=on_status
    )

    info = scanner_svc.start_server(company_id="C_DEMO", port=9123)
    assert info["is_running"] is True
    actual_port = info["port"]
    token = info["token"]
    assert token is not None and len(token) >= 8

    base_url = f"http://127.0.0.1:{actual_port}"

    try:
        # 1. Status endpoint
        req = urllib.request.Request(f"{base_url}/api/status?token={token}")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["active"] is True
            assert data["token_valid"] is True

        # 2. Scanner HTML endpoint with invalid token -> 401 Unauthorized
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"{base_url}/scanner?token=INVALID_TOKEN")
        assert exc_info.value.code == 401

        # 3. Scanner HTML endpoint with valid token -> 200 OK
        with urllib.request.urlopen(f"{base_url}/scanner?token={token}") as resp:
            assert resp.code == 200
            html = resp.read().decode("utf-8")
            assert "Anti Matrix" in html
            assert "Mobile Barcode Scanner" in html

        # 4. Pair device handshake
        pair_req = urllib.request.Request(
            f"{base_url}/api/pair",
            data=json.dumps({"token": token, "device": "iPhone 15 Pro", "user_agent": "Mozilla"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(pair_req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True

        assert scanner_svc.connected_device == "iPhone 15 Pro"

        # 5. Scan submission with valid token
        scan_req = urllib.request.Request(
            f"{base_url}/api/scan",
            data=json.dumps({"token": token, "barcode": "890_TEST_001", "device": "iPhone 15 Pro"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(scan_req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["barcode"] == "890_TEST_001"

        # Verify callback received scan
        assert len(received_scans) == 1
        assert received_scans[0] == ("890_TEST_001", "iPhone 15 Pro")

        # 6. Debounce test: rapid identical scan within 800ms is ignored
        scan_dup = urllib.request.Request(
            f"{base_url}/api/scan",
            data=json.dumps({"token": token, "barcode": "890_TEST_001", "device": "iPhone 15 Pro"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(scan_dup) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data.get("debounced") is True

        assert len(received_scans) == 1  # Still 1 because duplicate was debounced

        # 7. Scan submission with invalid token -> 401
        bad_scan_req = urllib.request.Request(
            f"{base_url}/api/scan",
            data=json.dumps({"token": "WRONG_TOKEN", "barcode": "890_TEST_002"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(bad_scan_req)
        assert exc_info.value.code == 401

        # 8. Token Revocation
        new_info = scanner_svc.revoke_token()
        assert new_info["token"] != token
        # Old token is now invalid
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"{base_url}/scanner?token={token}")
        assert exc_info.value.code == 401

    finally:
        scanner_svc.stop_server()
        assert scanner_svc.is_running is False
