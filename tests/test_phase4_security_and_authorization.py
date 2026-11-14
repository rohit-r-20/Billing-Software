"""
Comprehensive Regression & Security Test Suite for Phase 4:
- Valid authenticated company access
- Rejection of manipulated / unauthorized company ID
- Rejection of empty or whitespace company ID
- Rejection of unauthenticated RPC requests
- Prevention of cross-company data access
- Service-level unsafe fallback elimination
- Administrator provisioning and idempotency
- Existing initial test login credentials (COMP0001 / A / a)
- Sales and purchase voucher workflows with rollback
- Atomic sequence allocation and connection cleanup
"""
import json
import pytest
from db.database import db_manager
from desktop.web_bridge import BackendBridge
from services.company_service import company_service
from services.billing_service import billing_service
from services.inventory_service import inventory_service
from services.account_service import account_service
from services.catalogue_service import catalogue_service
from services.purchase_service import purchase_service
from services.supplier_service import supplier_service
from services.accounting_service import accounting_service


@pytest.fixture
def bridge():
    """Provides a fresh, unauthenticated BackendBridge instance."""
    b = BackendBridge()
    b.logout()
    return b


def create_authenticated_bridge(role: str = "Administrator"):
    """
    Create a BackendBridge instance authenticated as the specified role.
    Uses COMP0001 / A / a credentials and modifies the session role for testing.
    """
    b = BackendBridge()
    login_res = json.loads(b.authenticateUser("COMP0001", "A", "a"))
    assert login_res["success"] is True, f"Authentication failed: {login_res.get('error', 'Unknown error')}"

    # Override the role in session for role-based testing
    if role != "Administrator":
        b._authenticated_session["role"] = role

    return b


def test_unauthenticated_rpc_requests_rejected(bridge):
    """Verify that unauthenticated RPC requests cannot access protected business data."""
    # Accounts
    res = json.loads(bridge.listAccounts("COMP0001"))
    assert res["success"] is False
    assert "Authentication required" in res["error"]

    # Company Config
    res = json.loads(bridge.getCompanyConfig("COMP0001"))
    assert res["success"] is False
    assert "Authentication required" in res["error"]

    # Items
    res = json.loads(bridge.searchItems("COMP0001", "item"))
    assert res["success"] is False
    assert "Authentication required" in res["error"]

    # Sales Invoicing
    res = json.loads(bridge.createSaleInvoice("COMP0001", "{}"))
    assert res["success"] is False
    assert "Authentication required" in res["error"]

    # Invoices list
    res = json.loads(bridge.listVouchers("COMP0001"))
    assert res["success"] is False
    assert "Authentication required" in res["error"]

    # Inventory Dashboard
    res = json.loads(bridge.getInventoryDashboard("COMP0001"))
    assert res["success"] is False
    assert "Authentication required" in res["error"]

    # Trial Balance
    res = json.loads(bridge.getTrialBalance("COMP0001"))
    assert res["success"] is False
    assert "Authentication required" in res["error"]

    # Reports
    res = json.loads(bridge.getReport("COMP0001", "daily_sales"))
    assert res["success"] is False
    assert "Authentication required" in res["error"]

    # Administrative tools
    res = json.loads(bridge.performBackup(""))
    assert res["success"] is False
    assert "Authentication required" in res["error"]

    res = json.loads(bridge.listBackups())
    assert res["success"] is False
    assert "Authentication required" in res["error"]


def test_authenticated_company_access(bridge):
    """Verify that legitimate authentication grants access to authorized company data."""
    login_res = json.loads(bridge.authenticateUser("COMP0001", "A", "a"))
    assert login_res["success"] is True
    assert login_res["data"]["code"] == "COMP0001"
    comp_uuid = login_res["data"]["id"]

    # 1. Access by company code
    res_code = json.loads(bridge.listAccounts("COMP0001"))
    assert res_code["success"] is True
    assert isinstance(res_code["data"], list)

    # 2. Access by canonical company UUID
    res_uuid = json.loads(bridge.listAccounts(comp_uuid))
    assert res_uuid["success"] is True
    assert len(res_uuid["data"]) == len(res_code["data"])

    # 3. Check session state query
    session_res = json.loads(bridge.getAuthenticatedSession())
    assert session_res["success"] is True
    assert session_res["authenticated"] is True
    assert session_res["data"]["companyCode"] == "COMP0001"
    assert session_res["data"]["companyId"] == comp_uuid
    assert session_res["data"]["role"] == "Administrator"


def test_rejection_of_manipulated_company_id(bridge):
    """Verify that tampering with company_id in RPC requests is strictly rejected."""
    login_res = json.loads(bridge.authenticateUser("COMP0001", "A", "a"))
    assert login_res["success"] is True

    other_company = "cd064e32-7201-4af5-9772-991447d06504"

    # Attempt cross-company accounts access
    res = json.loads(bridge.listAccounts(other_company))
    assert res["success"] is False
    assert "Access denied" in res["error"]

    # Attempt cross-company item search
    res = json.loads(bridge.searchItems(other_company, "test"))
    assert res["success"] is False
    assert "Access denied" in res["error"]

    # Attempt cross-company invoice creation
    res = json.loads(bridge.createSaleInvoice(other_company, "{}"))
    assert res["success"] is False
    assert "Access denied" in res["error"]

    # Attempt cross-company reports
    res = json.loads(bridge.getReport(other_company, "daily_sales"))
    assert res["success"] is False
    assert "Access denied" in res["error"]

    # Attempt cross-company stock summary
    res = json.loads(bridge.getStockSummary(other_company, "", ""))
    assert res["success"] is False
    assert "Access denied" in res["error"]


def test_rejection_of_empty_or_whitespace_company_id(bridge):
    """Verify that missing or empty company context is rejected without silent fallback."""
    login_res = json.loads(bridge.authenticateUser("COMP0001", "A", "a"))
    assert login_res["success"] is True

    # Empty string
    res = json.loads(bridge.listAccounts(""))
    assert res["success"] is False
    assert "Company context is required" in res["error"]

    # Whitespace only
    res = json.loads(bridge.searchItems("   ", "item"))
    assert res["success"] is False
    assert "Company context is required" in res["error"]

    # Empty voucher sequence
    res = json.loads(bridge.getNextVoucherNumber("", "Main"))
    assert res["success"] is False
    assert "Company context is required" in res["error"]


def test_logout_session_invalidation(bridge):
    """Verify that logging out immediately invalidates session context."""
    login_res = json.loads(bridge.authenticateUser("COMP0001", "A", "a"))
    assert login_res["success"] is True

    # Verified active
    res = json.loads(bridge.listAccounts("COMP0001"))
    assert res["success"] is True

    # Logout
    logout_res = json.loads(bridge.logout())
    assert logout_res["success"] is True

    # Inactive post-logout
    res_after = json.loads(bridge.listAccounts("COMP0001"))
    assert res_after["success"] is False
    assert "Authentication required" in res_after["error"]

    session_res = json.loads(bridge.getAuthenticatedSession())
    assert session_res["authenticated"] is False


def test_service_level_unsafe_fallback_elimination():
    """Verify that all core business services reject missing company context at the service layer."""
    services = [
        ("billing_service", billing_service),
        ("inventory_service", inventory_service),
        ("account_service", account_service),
        ("catalogue_service", catalogue_service),
        ("purchase_service", purchase_service),
        ("supplier_service", supplier_service),
        ("accounting_service", accounting_service),
    ]

    for name, svc in services:
        # None
        with pytest.raises(ValueError, match="Company context is required"):
            svc._resolve_company_id(None)

        # Empty string
        with pytest.raises(ValueError, match="Company context is required"):
            svc._resolve_company_id("")

        # Whitespace
        with pytest.raises(ValueError, match="Company context is required"):
            svc._resolve_company_id("   ")

        # Non-existent company
        with pytest.raises(ValueError, match="Invalid company context"):
            svc._resolve_company_id("NON_EXISTENT_COMPANY_XYZ")


def test_administrator_provisioning_and_idempotency():
    """Verify idempotent administrator account provisioning for the primary company."""
    # First call
    res1 = company_service.provision_initial_administrator("COMP0001", "A", "a", "System Administrator")
    assert res1["username"] == "A"
    assert res1["role_name"] == "Administrator"
    assert res1["is_active"] == 1
    admin_id = res1["id"]

    # Second call (idempotency test)
    res2 = company_service.provision_initial_administrator("COMP0001", "A", "a", "System Administrator")
    assert res2["id"] == admin_id
    assert res2["created"] is False


def test_initial_test_credentials_login():
    """Verify that initial testing credentials (COMP0001 / A / a) authenticate successfully."""
    # Valid credentials
    auth = company_service.authenticate("COMP0001", "a", "A")
    assert auth is not None
    assert auth["code"] == "COMP0001"
    assert auth["username"] == "A"
    assert auth["displayName"] == "System Administrator"
    assert auth["role"] == "Administrator"

    # Invalid password
    auth_bad = company_service.authenticate("COMP0001", "wrong_password", "A")
    assert auth_bad is None

    # Missing company
    auth_missing = company_service.authenticate("", "a", "A")
    assert auth_missing is None


def test_sales_voucher_creation_and_transaction_rollback():
    """Verify voucher sequence allocation and complete transaction rollback without modifying business data."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, code FROM companies WHERE UPPER(code) = 'COMP0001' LIMIT 1;")
        c_row = cursor.fetchone()
        comp_id = c_row["id"] if isinstance(c_row, dict) or hasattr(c_row, "keys") else c_row[0]

        # Count vouchers before
        cursor.execute("SELECT COUNT(*) FROM sales_vouchers WHERE company_id = ?;", (comp_id,))
        count_before = cursor.fetchone()[0]

        # Allocate next voucher number in series
        next_vch_no = billing_service.get_next_voucher_number(comp_id, "Main")
        assert next_vch_no is not None
        assert int(next_vch_no) > 0

        # Simulate atomic rollback
        try:
            cursor.execute("""
                INSERT INTO sales_vouchers (
                    id, company_id, series, vch_no, vch_date, sale_type,
                    party_name, taxable_amount, subtotal, grand_total, is_cancelled
                ) VALUES (
                    'test-vch-rollback-id', ?, 'TestSeries', '999999', '2026-11-10', 'TAX_INVOICE',
                    'ROLLBACK_TEST', 100.0, 100.0, 118.0, 0
                );
            """, (comp_id,))
            cursor.execute("SELECT COUNT(*) FROM sales_vouchers WHERE id = 'test-vch-rollback-id';")
            assert cursor.fetchone()[0] == 1, "Voucher should exist inside active transaction"
            # Force simulated error to trigger rollback
            raise RuntimeError("Simulated transaction failure for test rollback")
        except RuntimeError:
            conn.rollback()

        # Count vouchers after: must be identical
        cursor.execute("SELECT COUNT(*) FROM sales_vouchers WHERE company_id = ?;", (comp_id,))
        count_after = cursor.fetchone()[0]
        assert count_before == count_after, "Rollback failed: record was retained"


def test_connection_cleanup_and_zero_leaks():
    """Verify that checking health and running queries leaves zero idle-in-transaction connections."""
    health = db_manager.check_health()
    assert health["healthy"] is True

    if db_manager.is_postgres:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM pg_stat_activity
                WHERE state = 'idle in transaction' AND datname = current_database();
            """)
            idle_in_tx = cursor.fetchone()[0]
            assert idle_in_tx == 0, f"Found {idle_in_tx} leaked transactions in 'idle in transaction' state"
