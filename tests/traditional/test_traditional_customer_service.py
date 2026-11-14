"""
Test Suite: Traditional Billing Customer Master & Account Code Generation.

Requirements covered:
1. Creating a customer without manually entering a code generates CUS-000001.
2. Sequential customer creation generates CUS-000002, CUS-000003, etc.
3. Concurrent customer creation generates collision-free unique codes.
4. Editing an existing customer retains its original code.
5. Attempting to supply a duplicate code fails safely.
6. Company isolation: Customer codes in Company A do not collide with or affect Company B's sequence.
7. Supplier and other account master workflows remain functional (SUP-000001, BNK-000001, etc.).
8. Fast Billing database remains frozen and untouched.
"""

import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytest
from sqlalchemy import select
from alembic.config import Config
from alembic import command

from db.traditional_database import TraditionalDatabaseManager
from db.traditional_models import Company, Account
from services.traditional_company_service import TraditionalCompanyService
from services.traditional_customer_service import TraditionalCustomerService


@pytest.fixture
def customer_env(tmp_path):
    """Isolated SQLite database with Alembic migrations applied for customer tests."""
    db_file = tmp_path / "test_traditional_cust.db"
    db_url = f"sqlite:///{db_file}"

    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    company_service = TraditionalCompanyService(db_manager=trad_mgr)
    customer_service = TraditionalCustomerService(db_manager=trad_mgr)

    # Initialize primary company
    setup_data = {
        "code": "COMP01",
        "name": "Alpha Traders Co",
        "finYear": "2026-2027",
        "taxNo": "33AAAPL1234F1Z1",
        "state": "Tamilnadu",
        "adminUsername": "ADMIN01",
        "adminPassword": "AdminPassword@2026",
    }
    company_info = company_service.initial_setup(setup_data)

    yield {
        "trad_mgr": trad_mgr,
        "company_service": company_service,
        "customer_service": customer_service,
        "company_id": company_info["companyId"],
        "user_id": company_info["adminUserId"],
        "db_file": db_file,
    }

    trad_mgr.close()


def test_create_customer_without_code_generates_cus_000001(customer_env):
    """
    Requirement 1: Creating a customer without entering a code generates 'CUS-000001'.
    Matches the exact form scenario: Arasu Traders, alias Arasu, Sundry Debtors (Customers).
    """
    svc = customer_env["customer_service"]
    cid = customer_env["company_id"]

    data = {
        "name": "Arasu Traders",
        "alias": "Arasu",
        "group": "Sundry Debtors (Customers)",
        "opBal": 0.00,
        "state": "Tamilnadu",
        "phone": "9876543210",
        "address": "12, Bazaar Street, Salem",
    }

    cust = svc.save_customer(cid, data)

    assert cust is not None
    assert cust["code"] == "CUS-000001"
    assert cust["customer_code"] == "CUS-000001"
    assert cust["name"] == "Arasu Traders"
    assert cust["account_type"] == "Debtor"
    assert cust["group"] == "Sundry Debtors"
    assert cust["phone"] == "9876543210"
    assert cust["state"] == "Tamilnadu"
    assert cust["isActive"] is True

    # Verify retrieval
    retrieved = svc.get_customer(cid, cust["id"])
    assert retrieved is not None
    assert retrieved["code"] == "CUS-000001"
    assert retrieved["name"] == "Arasu Traders"


def test_sequential_customer_creation_generates_incrementing_codes(customer_env):
    """
    Requirement 2: Sequential customer creation generates CUS-000001, CUS-000002, CUS-000003, etc.
    """
    svc = customer_env["customer_service"]
    cid = customer_env["company_id"]

    names = ["Customer Alpha", "Customer Beta", "Customer Gamma", "Customer Delta"]
    codes = []

    for name in names:
        c = svc.save_customer(cid, {"name": name, "group": "Sundry Debtors"})
        codes.append(c["code"])

    assert codes == ["CUS-000001", "CUS-000002", "CUS-000003", "CUS-000004"]


def test_concurrent_customer_creation_generates_collision_free_unique_codes(customer_env):
    """
    Requirement 3: Concurrent customer creation generates collision-free unique codes.
    Uses multi-threaded worker pool to simulate simultaneous customer creations.
    """
    svc = customer_env["customer_service"]
    cid = customer_env["company_id"]

    num_customers = 20

    def create_cust(idx: int):
        return svc.save_customer(
            cid,
            {
                "name": f"Concurrent Customer {idx:02d}",
                "group": "Sundry Debtors",
                "phone": f"98765432{idx:02d}",
            },
        )

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(create_cust, i) for i in range(num_customers)]
        for f in as_completed(futures):
            results.append(f.result())

    assert len(results) == num_customers

    # All codes must be unique
    generated_codes = [r["code"] for r in results]
    assert len(set(generated_codes)) == num_customers

    # Codes must span CUS-000001 through CUS-000020
    expected_codes = {f"CUS-{i:06d}" for i in range(1, num_customers + 1)}
    assert set(generated_codes) == expected_codes


def test_editing_existing_customer_retains_original_code(customer_env):
    """
    Requirement 4: Editing an existing customer retains its original code.
    No new code is generated during updates.
    """
    svc = customer_env["customer_service"]
    cid = customer_env["company_id"]

    # 1. Create first customer
    c1 = svc.save_customer(cid, {"name": "Original Name", "group": "Sundry Debtors"})
    orig_id = c1["id"]
    orig_code = c1["code"]
    assert orig_code == "CUS-000001"

    # 2. Update without passing code in payload
    updated_1 = svc.save_customer(
        cid,
        {
            "id": orig_id,
            "name": "Updated Name V1",
            "phone": "9123456789",
        },
    )
    assert updated_1["id"] == orig_id
    assert updated_1["code"] == "CUS-000001"
    assert updated_1["name"] == "Updated Name V1"
    assert updated_1["phone"] == "9123456789"

    # 3. Update with existing code explicitly passed
    updated_2 = svc.save_customer(
        cid,
        {
            "id": orig_id,
            "name": "Updated Name V2",
            "code": "CUS-000001",
        },
    )
    assert updated_2["code"] == "CUS-000001"
    assert updated_2["name"] == "Updated Name V2"

    # 4. Create second customer to ensure sequence continues from 2, not resetting or jumping
    c2 = svc.save_customer(cid, {"name": "Second Customer", "group": "Sundry Debtors"})
    assert c2["code"] == "CUS-000002"


def test_attempting_to_supply_duplicate_code_fails_safely(customer_env):
    """
    Requirement 5: Attempting to supply a duplicate code fails safely with a clear ValueError.
    """
    svc = customer_env["customer_service"]
    cid = customer_env["company_id"]

    # 1. Create customer with explicit code
    svc.save_customer(cid, {"name": "Cust 1", "code": "CUS-MANUAL01", "group": "Sundry Debtors"})

    # 2. Duplicate on new customer creation
    with pytest.raises(ValueError, match="already exists"):
        svc.save_customer(cid, {"name": "Cust 2", "code": "CUS-MANUAL01", "group": "Sundry Debtors"})

    # 3. Duplicate on updating another customer
    c2 = svc.save_customer(cid, {"name": "Cust 2 Valid", "code": "CUS-MANUAL02", "group": "Sundry Debtors"})
    with pytest.raises(ValueError, match="already assigned"):
        svc.save_customer(
            cid,
            {
                "id": c2["id"],
                "name": "Cust 2 Renamed",
                "code": "CUS-MANUAL01",
            },
        )


def test_company_isolation_tenant_sequences(customer_env):
    """
    Requirement 6: Company isolation. Customer codes in Company A do not collide with
    or affect Company B's sequence.
    """
    svc = customer_env["customer_service"]
    trad_mgr = customer_env["trad_mgr"]
    cid_a = customer_env["company_id"]

    # Company A creates two customers
    ca1 = svc.save_customer(cid_a, {"name": "Company A Customer 1", "group": "Sundry Debtors"})
    ca2 = svc.save_customer(cid_a, {"name": "Company A Customer 2", "group": "Sundry Debtors"})
    assert ca1["code"] == "CUS-000001"
    assert ca2["code"] == "CUS-000002"

    # Create Company B
    cid_b = "comp-b-uuid"
    comp_b = Company(
        id=cid_b,
        code="COMP02",
        name="Beta Enterprises",
        fin_year="2026-2027",
        gstin="33BBBPB5678F1Z2",
        state="Tamilnadu",
        is_active=True,
    )
    with trad_mgr.session_scope() as session:
        session.add(comp_b)

    # Company B creates customers: should start at CUS-000001 independently
    cb1 = svc.save_customer(cid_b, {"name": "Company B Customer 1", "group": "Sundry Debtors"})
    cb2 = svc.save_customer(cid_b, {"name": "Company B Customer 2", "group": "Sundry Debtors"})
    assert cb1["code"] == "CUS-000001"
    assert cb2["code"] == "CUS-000002"

    # Company A creates another customer: sequence should advance to CUS-000003
    ca3 = svc.save_customer(cid_a, {"name": "Company A Customer 3", "group": "Sundry Debtors"})
    assert ca3["code"] == "CUS-000003"


def test_supplier_and_other_account_master_workflows(customer_env):
    """
    Requirement 7: Supplier and other account master workflows remain functional.
    Suppliers receive SUP- prefix, banks BNK-, cash CSH-, and neither interferes
    with customer CUS- sequences.
    """
    svc = customer_env["customer_service"]
    cid = customer_env["company_id"]

    # 1. Create supplier
    sup1 = svc.save_customer(cid, {"name": "Salem Textile Mills", "group": "Sundry Creditors (Suppliers)"})
    assert sup1["code"] == "SUP-000001"
    assert sup1["account_type"] == "Creditor"
    assert sup1["group"] == "Sundry Creditors"

    sup2 = svc.save_customer(cid, {"name": "Erode Dyeing Works", "group": "Sundry Creditors"})
    assert sup2["code"] == "SUP-000002"
    assert sup2["account_type"] == "Creditor"

    # 2. Create bank account
    bank = svc.save_customer(cid, {"name": "HDFC Bank Ltd", "group": "Bank Accounts"})
    assert bank["code"] == "BNK-000001"
    assert bank["account_type"] == "Bank"

    # 3. Create cash account
    petty_cash = svc.save_customer(cid, {"name": "Petty Cash Account", "group": "Cash-in-hand"})
    assert petty_cash["code"] == "CSH-000001"
    assert petty_cash["account_type"] == "Cash"

    # 4. Create customer: customer sequence starts at CUS-000001, completely unaffected
    cust1 = svc.save_customer(cid, {"name": "Arasu Traders", "group": "Sundry Debtors (Customers)"})
    assert cust1["code"] == "CUS-000001"
    assert cust1["account_type"] == "Debtor"

    # 5. Editing supplier retains SUP-000001
    sup1_updated = svc.save_customer(
        cid,
        {
            "id": sup1["id"],
            "name": "Salem Textile Mills Ltd",
            "group": "Sundry Creditors",
        },
    )
    assert sup1_updated["code"] == "SUP-000001"
    assert sup1_updated["name"] == "Salem Textile Mills Ltd"

    # 6. list_accounts includes all types
    all_accs = svc.list_accounts(cid)
    types_found = {a["account_type"] for a in all_accs}
    assert "Creditor" in types_found
    assert "Bank" in types_found
    assert "Cash" in types_found
    assert "Debtor" in types_found


def test_traditional_customer_operations_do_not_touch_fast_billing(customer_env):
    """
    Requirement 8: Traditional customer operations do not touch or modify the Fast Billing database.
    """
    fast_db = Path("data/anti_matrix_billing.db")
    assert fast_db.exists(), "Fast Billing database file must exist"

    initial_hash = hashlib.sha256(fast_db.read_bytes()).hexdigest()

    svc = customer_env["customer_service"]
    cid = customer_env["company_id"]

    # Perform multiple customer and supplier operations
    c = svc.save_customer(cid, {"name": "Isolation Customer", "group": "Sundry Debtors"})
    svc.save_customer(cid, {"id": c["id"], "name": "Isolation Customer Renamed"})
    svc.list_customers(cid)
    svc.list_accounts(cid)
    svc.get_customer(cid, c["id"])
    svc.set_customer_active(cid, c["id"], False)

    final_hash = hashlib.sha256(fast_db.read_bytes()).hexdigest()
    assert initial_hash == final_hash, "Fast Billing database must remain 100% untouched"


def test_web_bridge_customer_rpc_lifecycle(customer_env):
    """
    Requirement 9: End-to-end WebBridge RPC validation for traditional customer and account operations.
    Covers unauthenticated protection, auto-code generation via RPC, and listing accounts.
    """
    import json
    from desktop.web_bridge import BackendBridge
    from services.traditional_auth_service import session_registry as trad_session_registry

    bridge = BackendBridge()
    bridge._traditional_customer_service = customer_env["customer_service"]

    # 1. Unauthenticated call fails closed
    unauth_resp = json.loads(bridge.traditional_saveCustomer(json.dumps({"name": "Should Fail"})))
    assert unauth_resp["success"] is False
    assert "Authentication required" in unauth_resp["error"]

    # 2. Authenticate session as Administrator
    token = trad_session_registry.create_session(
        user_id=customer_env["user_id"],
        company_id=customer_env["company_id"],
        branch_id="br-01",
        role_name="Administrator",
        username="ADMIN01",
        display_name="System Administrator",
    )
    bridge._traditional_session = trad_session_registry.get_session(token)

    # 3. Save customer without code via RPC
    payload = {
        "name": "Arasu Traders",
        "alias": "Arasu",
        "group": "Sundry Debtors (Customers)",
        "opBal": 0.00,
        "phone": "9876543210",
        "address": "Bazaar Street",
    }
    resp = json.loads(bridge.traditional_saveCustomer(json.dumps(payload)))
    assert resp["success"] is True
    assert resp["data"]["code"] == "CUS-000001"
    assert resp["data"]["name"] == "Arasu Traders"
    cust_id = resp["data"]["id"]

    # 4. Get customer via RPC
    get_resp = json.loads(bridge.traditional_getCustomer(cust_id))
    assert get_resp["success"] is True
    assert get_resp["data"]["code"] == "CUS-000001"

    # 5. List customers via RPC
    list_resp = json.loads(bridge.traditional_listCustomers("", True))
    assert list_resp["success"] is True
    assert len(list_resp["data"]) == 1
    assert list_resp["data"][0]["code"] == "CUS-000001"

    # 6. List accounts via RPC
    list_acc_resp = json.loads(bridge.traditional_listAccounts("", False))
    assert list_acc_resp["success"] is True
    # Should contain CASH, SALES from initial setup + the newly added customer
    codes = [a["code"] for a in list_acc_resp["data"]]
    assert "CUS-000001" in codes
    assert "CASH" in codes
    assert "SALES" in codes
