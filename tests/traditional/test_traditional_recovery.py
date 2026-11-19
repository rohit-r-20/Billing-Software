"""
Test Suite: Traditional Billing Company & Administrator Recovery.
Covers:
1. Authorized company-name modification
2. Authorized username modification
3. Successful password reset
4. New password authentication
5. Incorrect recovery token rejection
6. Cancelled authorization rejection
7. Duplicate username rejection
8. Duplicate company-code rejection
9. Transaction rollback on failure
10. Audit log creation
11. Existing invoices & business records intact
12. Fast Billing isolation (SHA-256 integrity)
"""

import os
import json
import uuid
import hashlib
import pytest
from pathlib import Path
from alembic.config import Config
from alembic import command

from core.configuration import config
from db.traditional_database import TraditionalDatabaseManager
from db.traditional_models import (
    Company,
    Branch,
    User,
    Role,
    Account,
    Item,
    ItemBarcode,
    StockBalance,
    VoucherSequence,
    SaleInvoice,
    AuditLog,
    utc_now,
)
from services.traditional_auth_service import (
    TraditionalAuthService,
    TraditionalSessionRegistry,
    hash_password,
    verify_password,
)
from services.traditional_recovery_token import (
    get_canonical_recovery_token_path,
    provision_recovery_token,
    verify_recovery_token,
    consume_recovery_token,
)
from services.traditional_recovery_service import TraditionalRecoveryService
from desktop.web_bridge import BackendBridge


def _calculate_file_sha256(filepath: Path) -> str:
    """Calculates SHA256 checksum of a file if it exists."""
    if not filepath.exists():
        return ""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


@pytest.fixture
def recovery_env(tmp_path, monkeypatch):
    """
    Creates an isolated test environment with temporary Traditional DB
    and temporary recovery token path.
    """
    db_file = tmp_path / "test_recovery_traditional.db"
    db_url = f"sqlite:///{db_file}"

    # Apply Alembic migrations to temp DB
    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    session_reg = TraditionalSessionRegistry()
    auth_service = TraditionalAuthService(db_manager=trad_mgr, registry=session_reg)
    recovery_service = TraditionalRecoveryService(db_manager=trad_mgr)

    token_file = tmp_path / ".traditional_recovery_token"
    monkeypatch.setattr(
        "services.traditional_recovery_token.get_canonical_recovery_token_path",
        lambda: token_file,
    )
    monkeypatch.setattr(
        "desktop.web_bridge.get_canonical_recovery_token_path",
        lambda: token_file,
    )

    # Seed primary company, branch, and admin user
    comp_id = "comp_alpha_001"
    branch_id = "branch_alpha_001"
    admin_id = "user_admin_001"

    with trad_mgr.session_scope() as session:
        comp = Company(
            id=comp_id,
            code="CORP01",
            name="Alpha Retail Enterprise",
            fin_year="2026-2027",
            gstin="27ABCDE1234F1Z5",
            state="Maharashtra",
            is_active=True,
        )
        branch = Branch(
            id=branch_id,
            company_id=comp_id,
            code="BR01",
            name="Alpha Head Office",
            is_active=True,
        )
        admin = User(
            id=admin_id,
            company_id=comp_id,
            username="ADMIN",
            password_hash=hash_password("OriginalAdminPass@2026"),
            role_name="Administrator",
            is_active=True,
        )
        session.add(comp)
        session.add(branch)
        session.add(admin)

    yield {
        "trad_mgr": trad_mgr,
        "auth_service": auth_service,
        "recovery_service": recovery_service,
        "session_reg": session_reg,
        "token_file": token_file,
        "comp_id": comp_id,
        "branch_id": branch_id,
        "admin_id": admin_id,
    }

    trad_mgr.close()


# ---------------------------------------------------------------------------
# Test 1: Authorized company-name modification
# ---------------------------------------------------------------------------
def test_authorized_company_name_modification(recovery_env):
    env = recovery_env
    token_file = env["token_file"]

    # Provision recovery token
    ok, token, _ = provision_recovery_token(company_count=1, token_path=token_file)
    assert ok is True

    # Call recovery to update company name
    payload = {
        "company_id": env["comp_id"],
        "company_name": "Beta Retail Enterprise",
        "company_code": "CORP01",
        "admin_username": "ADMIN",
    }
    res = env["recovery_service"].recover_company_and_admin(payload)
    assert res["company_name"] == "Beta Retail Enterprise"
    assert res["company_code"] == "CORP01"
    assert res["company_id"] == env["comp_id"]

    # Verify in DB
    with env["trad_mgr"].read_session_scope() as session:
        from sqlalchemy import select
        comp = session.scalar(select(Company).where(Company.id == env["comp_id"]))
        assert comp.name == "Beta Retail Enterprise"
        assert comp.code == "CORP01"
        assert comp.id == env["comp_id"]


# ---------------------------------------------------------------------------
# Test 2: Authorized username modification
# ---------------------------------------------------------------------------
def test_authorized_username_modification(recovery_env):
    env = recovery_env
    token_file = env["token_file"]

    ok, token, _ = provision_recovery_token(company_count=1, token_path=token_file)
    assert ok is True

    payload = {
        "company_id": env["comp_id"],
        "company_name": "Alpha Retail Enterprise",
        "company_code": "CORP01",
        "admin_username": "SUPERADMIN",
    }
    res = env["recovery_service"].recover_company_and_admin(payload)
    assert res["admin_username"] == "SUPERADMIN"

    # Verify in DB
    with env["trad_mgr"].read_session_scope() as session:
        from sqlalchemy import select
        user = session.scalar(select(User).where(User.id == env["admin_id"]))
        assert user.username == "SUPERADMIN"
        assert user.role_name == "Administrator"


# ---------------------------------------------------------------------------
# Test 3: Successful password reset
# ---------------------------------------------------------------------------
def test_successful_password_reset(recovery_env):
    env = recovery_env
    token_file = env["token_file"]

    ok, token, _ = provision_recovery_token(company_count=1, token_path=token_file)
    assert ok is True

    payload = {
        "company_id": env["comp_id"],
        "company_name": "Alpha Retail Enterprise",
        "company_code": "CORP01",
        "admin_username": "ADMIN",
        "new_password": "NewSecretPassword@2026",
    }
    res = env["recovery_service"].recover_company_and_admin(payload)
    assert res["password_reset"] is True

    # Verify password verification
    with env["trad_mgr"].read_session_scope() as session:
        from sqlalchemy import select
        user = session.scalar(select(User).where(User.id == env["admin_id"]))
        assert verify_password(user.password_hash, "NewSecretPassword@2026") is True
        assert verify_password(user.password_hash, "OriginalAdminPass@2026") is False


# ---------------------------------------------------------------------------
# Test 4: New password authentication
# ---------------------------------------------------------------------------
def test_new_password_authentication(recovery_env):
    env = recovery_env
    auth = env["auth_service"]

    # 1. Update company code, username, and password in recovery
    payload = {
        "company_id": env["comp_id"],
        "company_name": "Omega Retail Solutions",
        "company_code": "OMEGA01",
        "admin_username": "OMEGAADMIN",
        "new_password": "OmegaSecurePassword@2026",
    }
    env["recovery_service"].recover_company_and_admin(payload)

    # 2. Old credentials fail
    old_auth = auth.authenticate("CORP01", "ADMIN", "OriginalAdminPass@2026")
    assert old_auth is None

    # Old password with new username fails
    wrong_pwd_auth = auth.authenticate("OMEGA01", "OMEGAADMIN", "OriginalAdminPass@2026")
    assert wrong_pwd_auth is None

    # 3. New credentials succeed
    new_auth = auth.authenticate("OMEGA01", "OMEGAADMIN", "OmegaSecurePassword@2026")
    assert new_auth is not None
    assert new_auth["company"]["id"] == env["comp_id"]
    assert new_auth["user"]["username"] == "OMEGAADMIN"
    assert new_auth["user"]["role"] == "Administrator"


# ---------------------------------------------------------------------------
# Test 5: Incorrect recovery token rejection
# ---------------------------------------------------------------------------
def test_incorrect_token_rejection(recovery_env):
    env = recovery_env
    token_file = env["token_file"]

    # Provision valid token
    ok, token, _ = provision_recovery_token(company_count=1, token_path=token_file)
    assert ok is True

    bridge = BackendBridge(parent=None)
    bridge._traditional_recovery_service = env["recovery_service"]
    bridge._override_recovery_token = "completely_wrong_token_hex_value_1234567890"

    payload = {
        "company_id": env["comp_id"],
        "company_name": "Tampered Name",
        "company_code": "TAMPER01",
        "admin_username": "HACKER",
    }
    raw_res = bridge.traditional_recoverCompanyAndAdmin(json.dumps(payload))
    res = json.loads(raw_res)

    assert res["success"] is False
    assert "Invalid recovery token" in res["error"]

    # Verify database was unchanged
    with env["trad_mgr"].read_session_scope() as session:
        from sqlalchemy import select
        comp = session.scalar(select(Company).where(Company.id == env["comp_id"]))
        user = session.scalar(select(User).where(User.id == env["admin_id"]))
        assert comp.name == "Alpha Retail Enterprise"
        assert comp.code == "CORP01"
        assert user.username == "ADMIN"


# ---------------------------------------------------------------------------
# Test 6: Cancelled authorization rejection
# ---------------------------------------------------------------------------
def test_cancelled_authorization_rejection(recovery_env):
    env = recovery_env
    token_file = env["token_file"]

    ok, token, _ = provision_recovery_token(company_count=1, token_path=token_file)
    assert ok is True

    bridge = BackendBridge(parent=None)
    bridge._traditional_recovery_service = env["recovery_service"]
    bridge._override_recovery_token = None  # Simulates operator clicking Cancel on Qt dialog

    payload = {
        "company_id": env["comp_id"],
        "company_name": "Cancelled Update",
        "company_code": "CORP01",
        "admin_username": "ADMIN",
    }
    raw_res = bridge.traditional_recoverCompanyAndAdmin(json.dumps(payload))
    res = json.loads(raw_res)

    assert res["success"] is False
    assert "cancelled" in res["error"].lower()

    # Verify database unchanged
    with env["trad_mgr"].read_session_scope() as session:
        from sqlalchemy import select
        comp = session.scalar(select(Company).where(Company.id == env["comp_id"]))
        assert comp.name == "Alpha Retail Enterprise"


# ---------------------------------------------------------------------------
# Test 7: Duplicate username rejection
# ---------------------------------------------------------------------------
def test_duplicate_username_rejection(recovery_env):
    env = recovery_env

    # Create a second user in the same company
    with env["trad_mgr"].session_scope() as session:
        cashier = User(
            id="user_cashier_002",
            company_id=env["comp_id"],
            username="CASHIER1",
            password_hash=hash_password("CashierPass123"),
            role_name="Cashier",
            is_active=True,
        )
        session.add(cashier)

    # Attempt to rename Administrator to CASHIER1
    payload = {
        "company_id": env["comp_id"],
        "company_name": "New Alpha Corp",
        "company_code": "CORP01",
        "admin_username": "CASHIER1",
    }
    with pytest.raises(ValueError) as excinfo:
        env["recovery_service"].recover_company_and_admin(payload)

    assert "already in use by another user" in str(excinfo.value)

    # Verify complete rollback
    with env["trad_mgr"].read_session_scope() as session:
        from sqlalchemy import select
        comp = session.scalar(select(Company).where(Company.id == env["comp_id"]))
        admin = session.scalar(select(User).where(User.id == env["admin_id"]))
        assert comp.name == "Alpha Retail Enterprise"
        assert admin.username == "ADMIN"


# ---------------------------------------------------------------------------
# Test 8: Duplicate company-code rejection
# ---------------------------------------------------------------------------
def test_duplicate_company_code_rejection(recovery_env):
    env = recovery_env

    # Create a second company with code CORP02
    with env["trad_mgr"].session_scope() as session:
        comp2 = Company(
            id="comp_beta_002",
            code="CORP02",
            name="Beta Corp",
            fin_year="2026-2027",
            is_active=True,
        )
        session.add(comp2)

    # Attempt to change company 1 code to CORP02
    payload = {
        "company_id": env["comp_id"],
        "company_name": "Attempted Rename",
        "company_code": "CORP02",
        "admin_username": "ADMIN",
    }
    with pytest.raises(ValueError) as excinfo:
        env["recovery_service"].recover_company_and_admin(payload)

    assert "already used by another company" in str(excinfo.value)

    # Verify rollback
    with env["trad_mgr"].read_session_scope() as session:
        from sqlalchemy import select
        comp = session.scalar(select(Company).where(Company.id == env["comp_id"]))
        assert comp.code == "CORP01"
        assert comp.name == "Alpha Retail Enterprise"


# ---------------------------------------------------------------------------
# Test 9: Transaction rollback on failure
# ---------------------------------------------------------------------------
def test_transaction_rollback_on_failure(recovery_env):
    env = recovery_env

    # Payload with valid company name but invalid password (< 4 chars)
    payload = {
        "company_id": env["comp_id"],
        "company_name": "Temporary Rollback Test Name",
        "company_code": "CORP99",
        "admin_username": "ADMIN",
        "new_password": "12",  # Invalid: less than 4 chars
    }

    with pytest.raises(ValueError) as excinfo:
        env["recovery_service"].recover_company_and_admin(payload)

    assert "at least 4 characters" in str(excinfo.value)

    # Verify database was NOT partially updated
    with env["trad_mgr"].read_session_scope() as session:
        from sqlalchemy import select
        comp = session.scalar(select(Company).where(Company.id == env["comp_id"]))
        assert comp.name == "Alpha Retail Enterprise"
        assert comp.code == "CORP01"


# ---------------------------------------------------------------------------
# Test 10: Audit log creation
# ---------------------------------------------------------------------------
def test_audit_log_creation(recovery_env):
    env = recovery_env

    payload = {
        "company_id": env["comp_id"],
        "company_name": "Alpha Prime Enterprise",
        "company_code": "ALPHA_PRIME",
        "admin_username": "PRIMEADMIN",
        "new_password": "PrimePassword@2026",
    }
    env["recovery_service"].recover_company_and_admin(payload)

    # Query AuditLog table
    with env["trad_mgr"].read_session_scope() as session:
        from sqlalchemy import select
        audit = session.scalar(
            select(AuditLog).where(
                AuditLog.company_id == env["comp_id"],
                AuditLog.event_type == "COMPANY_ADMIN_RECOVERED",
            )
        )
        assert audit is not None
        assert audit.entity_type == "COMPANY_RECOVERY"
        assert audit.entity_id == env["comp_id"]
        assert audit.user_id == env["admin_id"]

        data = json.loads(audit.payload_json)
        assert data["old_company_name"] == "Alpha Retail Enterprise"
        assert data["new_company_name"] == "Alpha Prime Enterprise"
        assert data["old_company_code"] == "CORP01"
        assert data["new_company_code"] == "ALPHA_PRIME"
        assert data["old_admin_username"] == "ADMIN"
        assert data["new_admin_username"] == "PRIMEADMIN"
        assert data["password_reset"] is True
        # Ensure password or hash is never recorded in audit log
        assert "password" not in data or data["password_reset"] is True
        assert "password_hash" not in data


# ---------------------------------------------------------------------------
# Test 11: Existing invoices and business records remain 100% intact
# ---------------------------------------------------------------------------
def test_existing_invoices_and_records_intact(recovery_env):
    env = recovery_env
    cid = env["comp_id"]
    bid = env["branch_id"]

    # 1. Seed complete business records
    party_id = "party_customer_001"
    item_id = "item_prod_001"
    inv_id = "invoice_sale_001"

    with env["trad_mgr"].session_scope() as session:
        # Party Account (Customer)
        party = Account(
            id=party_id,
            company_id=cid,
            code="CUS-000001",
            name="Sri Lakshmi Stores",
            account_type="Debtor",
            phone="9876543210",
            is_active=True,
        )
        # Item with Barcode and Stock Balance
        item = Item(
            id=item_id,
            company_id=cid,
            sku="SKU-NOODLE-001",
            name="Korean Noodles 120g",
            unit="Pcs.",
            selling_price=120.00,
            cogs_amount=90.00,
            tax_rate_percent=5.00,
            is_active=True,
        )
        barcode = ItemBarcode(
            id="barcode_001",
            company_id=cid,
            item_id=item_id,
            barcode="8901234567890",
        )
        stock = StockBalance(
            id="stock_001",
            company_id=cid,
            branch_id=bid,
            item_id=item_id,
            current_qty_scaled=50000,  # 50.000 Pcs
        )
        # Voucher Sequence
        vseq = VoucherSequence(
            id="seq_001",
            company_id=cid,
            branch_id=bid,
            financial_year="2026-2027",
            series="Main",
            current_number=1,
            prefix="INV-",
            padding=3,
        )
        # Sales Invoice
        inv = SaleInvoice(
            id=inv_id,
            voucher_id="vch_001",
            company_id=cid,
            branch_id=bid,
            user_id=env["admin_id"],
            financial_year="2026-2027",
            series="Main",
            sequence_number=1,
            voucher_number="INV-001",
            vch_date="2026-11-14",
            party_name="Sri Lakshmi Stores",
            account_id=party_id,
            sale_type="Tax Inclusive",
            payment_method="CASH",
            subtotal=114.29,
            taxable_amount=114.29,
            cgst_amount=2.86,
            sgst_amount=2.86,
            igst_amount=0.00,
            round_off_amount=-0.01,
            grand_total=120.00,
            total_amount=120.00,
            status="PAID",
            items_json=json.dumps([{"item_id": item_id, "name": "Korean Noodles 120g", "qty": 1, "rate": 120.00}]),
        )
        session.add_all([party, item, barcode, stock, vseq, inv])

    # 2. Perform Recovery: change company name, company code, admin username, and reset password
    payload = {
        "company_id": cid,
        "company_name": "Alpha Multi-Mart Pvt Ltd",
        "company_code": "AMMART01",
        "admin_username": "SYSADMIN",
        "new_password": "NewStorePassword@2026",
    }
    recovery_res = env["recovery_service"].recover_company_and_admin(payload)
    assert recovery_res["company_name"] == "Alpha Multi-Mart Pvt Ltd"
    assert recovery_res["company_code"] == "AMMART01"

    # 3. Verify ALL existing records remain 100% intact and linked
    with env["trad_mgr"].read_session_scope() as session:
        from sqlalchemy import select
        # Company ID strictly unchanged
        comp = session.scalar(select(Company).where(Company.id == cid))
        assert comp is not None
        assert comp.name == "Alpha Multi-Mart Pvt Ltd"
        assert comp.code == "AMMART01"

        # Customer account intact
        p = session.scalar(select(Account).where(Account.id == party_id))
        assert p is not None
        assert p.company_id == cid
        assert p.code == "CUS-000001"
        assert p.account_type == "Debtor"

        # Item and Barcode intact
        it = session.scalar(select(Item).where(Item.id == item_id))
        assert it is not None
        assert it.company_id == cid
        assert it.sku == "SKU-NOODLE-001"
        assert float(it.selling_price) == 120.00

        bc = session.scalar(select(ItemBarcode).where(ItemBarcode.id == "barcode_001"))
        assert bc is not None
        assert bc.barcode == "8901234567890"

        # Stock Balance intact
        stk = session.scalar(select(StockBalance).where(StockBalance.id == "stock_001"))
        assert stk is not None
        assert stk.company_id == cid
        assert stk.current_qty_scaled == 50000

        # Voucher Sequence intact
        seq = session.scalar(select(VoucherSequence).where(VoucherSequence.id == "seq_001"))
        assert seq is not None
        assert seq.company_id == cid
        assert seq.current_number == 1
        assert seq.prefix == "INV-"

        # Sales Invoice intact
        sale = session.scalar(select(SaleInvoice).where(SaleInvoice.id == inv_id))
        assert sale is not None
        assert sale.company_id == cid
        assert sale.account_id == party_id
        assert sale.voucher_number == "INV-001"
        assert float(sale.grand_total) == 120.00
        items_parsed = json.loads(sale.items_json)
        assert len(items_parsed) == 1
        assert items_parsed[0]["rate"] == 120.00


# ---------------------------------------------------------------------------
# Test 12: Fast Billing isolation (SHA-256 integrity)
# ---------------------------------------------------------------------------
def test_fast_billing_isolation(recovery_env):
    fast_db_path = Path("data/anti_matrix_billing.db").resolve()
    assert fast_db_path.exists(), "Fast Billing DB must exist"

    # Compute SHA-256 before recovery operation
    sha_before = _calculate_file_sha256(fast_db_path)

    # Perform full recovery cycle
    env = recovery_env
    token_file = env["token_file"]

    ok, token, _ = provision_recovery_token(company_count=1, token_path=token_file)
    assert ok is True

    bridge = BackendBridge(parent=None)
    bridge._traditional_recovery_service = env["recovery_service"]
    bridge._override_recovery_token = token

    payload = {
        "company_id": env["comp_id"],
        "company_name": "Isolated Corp",
        "company_code": "ISOCORP01",
        "admin_username": "ISOADMIN",
        "new_password": "IsoPassword@2026",
    }
    raw_res = bridge.traditional_recoverCompanyAndAdmin(json.dumps(payload))
    res = json.loads(raw_res)
    assert res["success"] is True

    # Compute SHA-256 after recovery operation
    sha_after = _calculate_file_sha256(fast_db_path)

    # Assert Fast Billing DB was completely untouched
    assert sha_after == sha_before
    assert sha_after == "bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd"


# ---------------------------------------------------------------------------
# Additional Token Lifecycle Tests
# ---------------------------------------------------------------------------
def test_cannot_provision_recovery_token_when_zero_companies(recovery_env):
    token_file = recovery_env["token_file"]
    ok, token, msg = provision_recovery_token(company_count=0, token_path=token_file)
    assert ok is False
    assert token == ""
    assert "No company exists" in msg
    assert not token_file.exists()


def test_token_consumed_after_successful_bridge_recovery(recovery_env):
    env = recovery_env
    token_file = env["token_file"]

    ok, token, _ = provision_recovery_token(company_count=1, token_path=token_file)
    assert ok is True
    assert token_file.exists()

    bridge = BackendBridge(parent=None)
    bridge._traditional_recovery_service = env["recovery_service"]
    bridge._override_recovery_token = token

    payload = {
        "company_id": env["comp_id"],
        "company_name": "New Alpha Entity",
        "company_code": "CORP01",
        "admin_username": "ADMIN",
    }
    raw_res = bridge.traditional_recoverCompanyAndAdmin(json.dumps(payload))
    res = json.loads(raw_res)
    assert res["success"] is True

    # Verify token was consumed/deleted post-commit
    assert not token_file.exists()


def test_direct_rpc_call_without_authorization_ui_fails_closed(recovery_env):
    env = recovery_env
    token_file = env["token_file"]

    ok, token, _ = provision_recovery_token(company_count=1, token_path=token_file)
    assert ok is True

    # Bridge instantiated with parent=None and NO _override_recovery_token
    bridge = BackendBridge(parent=None)
    bridge._traditional_recovery_service = env["recovery_service"]

    payload = {
        "company_id": env["comp_id"],
        "company_name": "Direct RPC Hack Attempt",
        "company_code": "HACK01",
        "admin_username": "HACKER",
    }
    raw_res = bridge.traditional_recoverCompanyAndAdmin(json.dumps(payload))
    res = json.loads(raw_res)

    assert res["success"] is False
    assert "Recovery authorization UI unavailable" in res["error"]

    # Verify database was unchanged
    with env["trad_mgr"].read_session_scope() as session:
        from sqlalchemy import select
        comp = session.scalar(select(Company).where(Company.id == env["comp_id"]))
        assert comp.name == "Alpha Retail Enterprise"


def test_failed_or_cancelled_recovery_does_not_consume_token(recovery_env):
    env = recovery_env
    token_file = env["token_file"]

    ok, token, _ = provision_recovery_token(company_count=1, token_path=token_file)
    assert ok is True
    assert token_file.exists()

    bridge = BackendBridge(parent=None)
    bridge._traditional_recovery_service = env["recovery_service"]

    # 1. Attempt with incorrect token
    bridge._override_recovery_token = "invalid_token_attempt"
    payload = {
        "company_id": env["comp_id"],
        "company_name": "Failed Attempt Corp",
        "company_code": "CORP01",
        "admin_username": "ADMIN",
    }
    raw_res = bridge.traditional_recoverCompanyAndAdmin(json.dumps(payload))
    res = json.loads(raw_res)
    assert res["success"] is False

    # Token file MUST still exist and retain original token
    assert token_file.exists()
    assert token_file.read_text(encoding="utf-8").strip() == token

    # 2. Attempt with cancelled prompt
    bridge._override_recovery_token = None
    raw_res2 = bridge.traditional_recoverCompanyAndAdmin(json.dumps(payload))
    res2 = json.loads(raw_res2)
    assert res2["success"] is False

    # Token file MUST STILL exist
    assert token_file.exists()
    assert token_file.read_text(encoding="utf-8").strip() == token

    # 3. Successful recovery with valid token
    bridge._override_recovery_token = token
    raw_res3 = bridge.traditional_recoverCompanyAndAdmin(json.dumps(payload))
    res3 = json.loads(raw_res3)
    assert res3["success"] is True

    # Post-commit: token is now consumed
    assert not token_file.exists()

    # 4. Attempt second recovery with consumed token -> rejected
    raw_res4 = bridge.traditional_recoverCompanyAndAdmin(json.dumps(payload))
    res4 = json.loads(raw_res4)
    assert res4["success"] is False
    assert "not found" in res4["error"]


def test_recovery_token_posix_permissions(recovery_env):
    token_file = recovery_env["token_file"]
    ok, token, _ = provision_recovery_token(company_count=1, token_path=token_file)
    assert ok is True
    assert token_file.exists()

    if os.name == "posix":
        mode = os.stat(token_file).st_mode & 0o777
        assert mode == 0o600, f"Expected 0o600 permissions, got {oct(mode)}"


def test_recovery_token_windows_acl_enforcement(recovery_env, monkeypatch):
    import subprocess
    token_file = recovery_env["token_file"]
    captured_calls = []

    def mock_subprocess_run(cmd, *args, **kwargs):
        captured_calls.append(cmd)
        class MockCompletedProcess:
            returncode = 0
            stdout = "processed file: ok"
            stderr = ""
        return MockCompletedProcess()

    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("USERNAME", "TestOperator")
    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    ok, token, _ = provision_recovery_token(company_count=1, token_path=token_file, force=True)
    assert ok is True
    assert len(captured_calls) == 1
    cmd = captured_calls[0]
    assert cmd[0] == "icacls"
    assert str(token_file) == cmd[1]
    assert "/inheritance:r" in cmd
    assert "/grant:r" in cmd
    assert "TestOperator:(R,W)" in cmd
    assert "*S-1-5-18:(R,W)" in cmd
    assert "*S-1-5-32-544:(R,W)" in cmd


def test_token_consumption_failure_reports_security_warning_and_remediation(recovery_env, monkeypatch):
    """
    Test security behavior when token consumption / file unlinking fails post-commit.
    Verifies that:
    1. Recovery transaction still commits successfully.
    2. File content is neutralized (zeroed out) so original token cannot be reused.
    3. Explicit security warning with manual remediation procedure is returned in response.
    """
    env = recovery_env
    token_file = env["token_file"]

    ok, token, _ = provision_recovery_token(company_count=1, token_path=token_file)
    assert ok is True
    assert token_file.exists()

    bridge = BackendBridge(parent=None)
    bridge._traditional_recovery_service = env["recovery_service"]
    bridge._override_recovery_token = token

    # Simulate unlink failure (e.g. file lock or read-only filesystem)
    orig_unlink = Path.unlink

    def mock_unlink(self, *args, **kwargs):
        if self.resolve() == token_file.resolve():
            raise PermissionError("Simulated file lock: unable to unlink")
        return orig_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", mock_unlink)

    payload = {
        "company_id": env["comp_id"],
        "company_name": "Resilient Corp",
        "company_code": "CORP01",
        "admin_username": "ADMIN",
    }
    raw_res = bridge.traditional_recoverCompanyAndAdmin(json.dumps(payload))
    res = json.loads(raw_res)

    assert res["success"] is True
    assert "warning" in res["data"]
    assert "SECURITY ALERT" in res["data"]["warning"]
    assert "could not be automatically deleted" in res["data"]["warning"]
    assert "Remediation: To ensure this authorization token cannot be reused, please manually delete" in res["data"]["warning"]

    # Critical security verify: token content was zeroed out, neutralizing reuse
    assert token_file.exists()
    assert token_file.read_text(encoding="utf-8").strip() == "0" * 48
    # Verifies original token CANNOT be used again
    assert not verify_recovery_token(token, token_file)
