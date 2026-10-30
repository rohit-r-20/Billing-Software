"""
Unit tests for Demo Products Seeding and Mobile Wi-Fi Barcode Scanner Service.
"""
import json
import time
import ssl
import urllib.request
import urllib.error
import pytest

from db.database import DatabaseManager
from services.catalogue_service import CatalogueService
from services.demo_product_service import DemoProductService, DEMO_PRODUCTS
from services.mobile_scanner_service import MobileScannerService
from services.cert_service import cert_service


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
    assert info["protocol"] == "https"
    assert info["url"].startswith("https://")
    actual_port = info["port"]
    http_port = info["http_port"]
    token = info["token"]
    assert token is not None and len(token) >= 8

    # TLS Client Context using Anti Matrix Root CA
    client_ctx = ssl.create_default_context(cafile=str(cert_service.ca_crt_path))
    https_base = f"https://127.0.0.1:{actual_port}"
    http_base = f"http://127.0.0.1:{http_port}"

    try:
        # 1. Status endpoint over TLS HTTPS
        req = urllib.request.Request(f"{https_base}/api/status?token={token}")
        with urllib.request.urlopen(req, context=client_ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["active"] is True
            assert data["token_valid"] is True
            assert data["is_https"] is True

        # 2. CA Certificate download over HTTPS
        req_ca = urllib.request.Request(f"{https_base}/ca.crt")
        with urllib.request.urlopen(req_ca, context=client_ctx) as resp:
            assert resp.code == 200
            assert "application/x-x509-ca-cert" in resp.headers.get("Content-Type", "")
            ca_pem = resp.read()
            assert b"BEGIN CERTIFICATE" in ca_pem

        # 3. CA Certificate download over plain HTTP companion server (for zero-TLS friction phone setup)
        req_http_ca = urllib.request.Request(f"{http_base}/ca.crt")
        with urllib.request.urlopen(req_http_ca) as resp:
            assert resp.code == 200
            assert b"BEGIN CERTIFICATE" in resp.read()

        # 4. Setup page
        req_setup = urllib.request.Request(f"{https_base}/setup?token={token}")
        with urllib.request.urlopen(req_setup, context=client_ctx) as resp:
            assert resp.code == 200
            setup_html = resp.read().decode("utf-8")
            assert "Enable Camera Scanner" in setup_html
            assert "Option 1" in setup_html

        # 5. Scanner HTML endpoint with invalid token -> 401 Unauthorized
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"{https_base}/scanner?token=INVALID_TOKEN", context=client_ctx)
        assert exc_info.value.code == 401

        # 6. Scanner HTML endpoint with valid token over TLS -> 200 OK
        with urllib.request.urlopen(f"{https_base}/scanner?token={token}", context=client_ctx) as resp:
            assert resp.code == 200
            html = resp.read().decode("utf-8")
            assert "Anti Matrix" in html
            assert "Mobile Barcode Scanner" in html
            assert "playsinline" in html
            assert "validateCameraPrerequisites" in html

        # 7. Companion HTTP redirect to HTTPS
        class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
            def http_error_302(self, req, fp, code, msg, headers):
                return fp

        opener = urllib.request.build_opener(NoRedirectHandler)
        resp_redirect = opener.open(f"{http_base}/scanner?token={token}")
        assert resp_redirect.code in (302, 200)

        # 8. Pair device handshake over TLS
        pair_req = urllib.request.Request(
            f"{https_base}/api/pair",
            data=json.dumps({"token": token, "device": "Android Chrome 120", "user_agent": "Mozilla"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(pair_req, context=client_ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True

        assert scanner_svc.connected_device == "Android Chrome 120"

        # 9. Scan submission with valid token
        scan_req = urllib.request.Request(
            f"{https_base}/api/scan",
            data=json.dumps({"token": token, "barcode": "890_TEST_001", "device": "Android Chrome 120"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(scan_req, context=client_ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["barcode"] == "890_TEST_001"

        # Verify callback received scan
        assert len(received_scans) == 1
        assert received_scans[0] == ("890_TEST_001", "Android Chrome 120")

        # 10. Debounce test: rapid identical scan within 800ms is ignored
        scan_dup = urllib.request.Request(
            f"{https_base}/api/scan",
            data=json.dumps({"token": token, "barcode": "890_TEST_001", "device": "Android Chrome 120"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(scan_dup, context=client_ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data.get("debounced") is True

        assert len(received_scans) == 1  # Still 1 because duplicate was debounced

        # 11. Oversized payload security rejection (>10KB) -> 413
        oversized_data = {"token": token, "barcode": "A" * 12000}
        oversized_req = urllib.request.Request(
            f"{https_base}/api/scan",
            data=json.dumps(oversized_data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(oversized_req, context=client_ctx)
        assert exc_info.value.code == 413

        # 12. Scan submission with invalid token -> 401
        bad_scan_req = urllib.request.Request(
            f"{https_base}/api/scan",
            data=json.dumps({"token": "WRONG_TOKEN", "barcode": "890_TEST_002"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(bad_scan_req, context=client_ctx)
        assert exc_info.value.code == 401

        # 13. Token Revocation
        new_info = scanner_svc.revoke_token()
        assert new_info["token"] != token
        # Old token is now invalid
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"{https_base}/scanner?token={token}", context=client_ctx)
        assert exc_info.value.code == 401

    finally:
        scanner_svc.stop_server()
        assert scanner_svc.is_running is False


def test_connection_state_machine_and_watchdog_timeout(scanner_test_env):
    """
    Tests the truthful connection state machine:
    1. Server starts with client_connected=False, status 'Service Running — Waiting for Phone'
    2. Simulated scan does not mark phone as connected
    3. Pair handshake marks client_connected=True, status 'Phone Connected'
    4. Heartbeats refresh timestamp
    5. Heartbeat timeout (>10s) triggers watchdog to mark phone disconnected
    6. Heartbeat resumes connection
    7. Clean disconnect endpoint works
    """
    statuses = []

    def on_status(status, details):
        statuses.append((status, details))

    scanner_svc = MobileScannerService(status_callback=on_status)
    scanner_svc.heartbeat_timeout_seconds = 1.0  # Fast timeout for test

    info = scanner_svc.start_server(company_id="C_DEMO", port=9124)
    client_ctx = ssl.create_default_context(cafile=str(cert_service.ca_crt_path))
    https_base = f"https://127.0.0.1:{info['port']}"
    token = info["token"]

    try:
        # 1. Truthful initial state
        assert scanner_svc.client_connected is False
        assert "Waiting for Phone" in scanner_svc.status
        info_check = scanner_svc.get_info()
        assert info_check["client_connected"] is False
        assert info_check["connected_device"] == ""

        # 2. Simulated scan does NOT alter connection state
        sim_res = scanner_svc.simulate_scan(company_id="C_DEMO", barcode="890_TEST_001")
        assert sim_res["success"] is True
        assert sim_res["device"] == "Simulated Scan"
        assert scanner_svc.client_connected is False
        assert "Waiting for Phone" in scanner_svc.status

        # 3. Pair device over TLS
        ua = "Mozilla/5.0 (Linux; Android 13; Pixel 7 Build/TQ3A.230901.001) AppleWebKit/537.36"
        pair_req = urllib.request.Request(
            f"{https_base}/api/pair",
            data=json.dumps({"token": token, "device": ua}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(pair_req, context=client_ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True

        assert scanner_svc.client_connected is True
        assert "Phone Connected" in scanner_svc.status
        assert "Pixel 7" in scanner_svc.connected_device
        # Verify get_info returns connected state
        info_conn = scanner_svc.get_info()
        assert info_conn["client_connected"] is True
        assert "Pixel 7" in info_conn["connected_device"]

        # 4. Heartbeat GET endpoint
        hb_req = urllib.request.Request(f"{https_base}/api/heartbeat?token={token}")
        with urllib.request.urlopen(hb_req, context=client_ctx) as resp:
            hb_data = json.loads(resp.read().decode("utf-8"))
            assert hb_data["success"] is True
            assert hb_data["client_connected"] is True

        # 5. Watchdog Timeout: Inactivity > heartbeat_timeout_seconds (1.0s)
        for _ in range(30):
            if not scanner_svc.client_connected:
                break
            time.sleep(0.1)
        # Watchdog must have detected timeout and transitioned to Waiting/Disconnected
        assert scanner_svc.client_connected is False
        assert "Waiting for Phone" in scanner_svc.status
        info_after_timeout = scanner_svc.get_info()
        assert info_after_timeout["client_connected"] is False
        assert info_after_timeout["connected_device"] == ""

        # Verify callback received HEARTBEAT_TIMEOUT
        timeout_events = [s for s in statuses if s[0] == "HEARTBEAT_TIMEOUT"]
        assert len(timeout_events) >= 1

        # 6. Reconnection via Heartbeat
        with urllib.request.urlopen(hb_req, context=client_ctx) as resp:
            hb_data2 = json.loads(resp.read().decode("utf-8"))
            assert hb_data2["success"] is True
            assert hb_data2["client_connected"] is True

        assert scanner_svc.client_connected is True
        assert "Phone Connected" in scanner_svc.status

        # 7. Clean disconnect endpoint (/api/disconnect)
        dc_req = urllib.request.Request(f"{https_base}/api/disconnect?token={token}")
        with urllib.request.urlopen(dc_req, context=client_ctx) as resp:
            dc_data = json.loads(resp.read().decode("utf-8"))
            assert dc_data["success"] is True

        assert scanner_svc.client_connected is False
        assert "Waiting for Phone" in scanner_svc.status

    finally:
        scanner_svc.stop_server()


def test_demo_products_pricing_and_checkout_rules(scanner_test_env):
    """
    Tests demo product catalog properties and checkout validation rules.
    """
    demo_svc = DemoProductService(scanner_test_env)
    cat_svc = CatalogueService(scanner_test_env)
    demo_svc.seed_demo_products("C_DEMO")

    # Milk Bikis
    bikis = cat_svc.find_by_barcode("C_DEMO", "890_TEST_001")
    assert bikis["sales_price"] == 10.0
    assert bikis["is_verified"] == 1

    # Hide & Seek
    hns = cat_svc.find_by_barcode("C_DEMO", "890_TEST_002")
    assert hns["sales_price"] == 20.0
    assert hns["is_verified"] == 1

    # Levosalbutamol sulfate
    med = cat_svc.find_by_barcode("C_DEMO", "8909263004690")
    assert med["sales_price"] == 0.0
    assert med["is_verified"] == 0

    # Test cart checkout rule simulation:
    # Rule: If cart has any item with price <= 0 or is_verified == 0, checkout is blocked.
    valid_cart = [
        {"name": bikis["name"], "price": bikis["sales_price"], "is_verified": bikis["is_verified"], "qty": 2},
        {"name": hns["name"], "price": hns["sales_price"], "is_verified": hns["is_verified"], "qty": 1}
    ]

    invalid_cart = valid_cart + [
        {"name": med["name"], "price": med["sales_price"], "is_verified": med["is_verified"], "qty": 1}
    ]

    def validate_cart_for_checkout(cart):
        blocked = [it for it in cart if it["price"] <= 0 or it["is_verified"] == 0]
        return len(blocked) == 0, blocked

    is_valid, blocked_items = validate_cart_for_checkout(valid_cart)
    assert is_valid is True
    assert len(blocked_items) == 0

    is_valid_bad, blocked_items_bad = validate_cart_for_checkout(invalid_cart)
    assert is_valid_bad is False
    assert len(blocked_items_bad) == 1
    assert blocked_items_bad[0]["name"] == med["name"]
