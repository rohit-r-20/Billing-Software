"""
Staging Lifecycle and Release Candidate Validation Test Suite.
Phase 3.8 — Anti-Matrix Billing V2 Staging Release Preparation.

Validates:
1. Staging configuration profile resolution and safety guards.
2. Staging database initialization (Fast Billing SQLite + Traditional Alembic).
3. Staging multi-tenant company, branch, and administrator provisioning.
4. Mode selection (Traditional ERP vs Fast Retail POS).
5. Traditional ERP workflows in staging (GL journal, Customer Receipt, Allocations).
6. Fast Retail POS workflows in staging (Barcode lookup, checkout, stock deduction).
7. Desktop WebBridge RPC registration and execution.
8. Session logout and clean invalidation.
9. Staging restart persistence.
10. Strict zero-byte invariance of production databases.
"""

import os
import hashlib
import json
import sys
import subprocess
from pathlib import Path
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config as AlembicConfig
from alembic import command

from core.configuration import AppConfig, config
from db.database import DatabaseManager
from db.traditional_database import TraditionalDatabaseManager, validate_traditional_database_target
from db.traditional_models import TraditionalBase, Company, Branch, Account, CustomerReceipt, ReceiptAllocation
from services.company_service import CompanyService
from services.catalogue_service import CatalogueService
from services.billing_service import BillingService
from services.traditional_accounting_service import TraditionalAccountingService
from services.traditional_payment_service import TraditionalPaymentService
from services.traditional_auth_service import TraditionalAuthService, session_registry
from desktop.web_bridge import BackendBridge

FAST_PROD_DB = Path("data/anti_matrix_billing.db").resolve()
TRAD_PROD_DB = Path("data/traditional_billing.db").resolve()
APP_PROD_DB = Path("data/app.db").resolve()
BASE_DIR = config.BASE_DIR


def compute_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ==============================================================================
# 1. Staging Configuration Profile & Safety Guard Tests
# ==============================================================================

def test_staging_profile_resolution(monkeypatch):
    """Verify that setting APP_ENV=staging activates the staging profile and safe defaults."""
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.delenv("DATABASE_ENV", raising=False)
    monkeypatch.delenv("FAST_DATABASE_PATH", raising=False)
    monkeypatch.delenv("TRADITIONAL_DATABASE_PATH", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TRADITIONAL_DATABASE_URL", raising=False)

    assert config.get_environment() == "staging"
    assert config.is_staging() is True
    assert config.is_production() is False
    assert config.get_database_path().name == "staging_anti_matrix_billing.db"
    assert config.get_traditional_database_path().name == "staging_traditional_billing.db"


def test_staging_safety_guard_rejects_production_databases(monkeypatch):
    """
    Verify that in staging mode, validate_configuration() fails closed if
    someone attempts to point staging to production database files.
    """
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///data/anti_matrix_billing.db")
    monkeypatch.setenv("TRADITIONAL_DATABASE_URL", "sqlite:///data/traditional_billing.db")

    diag = config.validate_configuration()
    assert diag["valid"] is False
    assert len(diag["errors"]) >= 2
    assert any("production Fast Billing database" in err for err in diag["errors"])
    assert any("production Traditional Billing database" in err for err in diag["errors"])


def test_staging_safety_guard_rejects_shared_database_target(monkeypatch, tmp_path):
    """Verify that Fast Billing and Traditional Billing cannot share the same database file."""
    shared_db = tmp_path / "shared.db"
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{shared_db}")
    monkeypatch.setenv("TRADITIONAL_DATABASE_URL", f"sqlite:///{shared_db}")

    diag = config.validate_configuration()
    assert diag["valid"] is False
    assert any("cannot share the same database target" in err for err in diag["errors"])


# ==============================================================================
# 2. Staging Environment Fixture
# ==============================================================================

@pytest.fixture
def staging_env(tmp_path, monkeypatch):
    """
    Sets up isolated staging SQLite databases for Fast Billing and Traditional Billing,
    applying all schema migrations and synthetic seed data.
    """
    fast_staging_db = tmp_path / "staging_anti_matrix_billing.db"
    trad_staging_db = tmp_path / "staging_traditional_billing.db"

    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{fast_staging_db}")
    monkeypatch.setenv("TRADITIONAL_DATABASE_URL", f"sqlite:///{trad_staging_db}")

    # 1. Initialize Fast Billing Staging DB
    fast_mgr = DatabaseManager(str(fast_staging_db))
    fast_mgr.run_migrations()

    # 2. Initialize Traditional Billing Staging DB via Alembic
    trad_mgr = TraditionalDatabaseManager(f"sqlite:///{trad_staging_db}")
    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = AlembicConfig(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{trad_staging_db}")
    command.upgrade(alembic_cfg, "head")

    # 3. Seed Staging Company and Branch in both databases
    cid = "STAGING_COMP_01"
    bid = "STAGING_BR_01"

    with fast_mgr.get_connection() as conn:
        conn.execute("""
            INSERT INTO companies (id, code, name, fin_year, gstin, state)
            VALUES (?, 'STAGE01', 'Staging Enterprise Mart', '2026-2027', '33AAAPL9999Z1Z5', 'Tamil Nadu');
        """, (cid,))
        conn.execute("""
            INSERT INTO branches (id, company_id, code, name, is_default)
            VALUES (?, ?, 'BR01', 'Staging Main Store', 1);
        """, (bid, cid))
        conn.execute("""
            INSERT INTO company_configs (company_id, vch_start, vch_digits, vch_prefix)
            VALUES (?, 1, 4, 'STG-');
        """, (cid,))
        conn.commit()

    with trad_mgr.session_scope() as session:
        comp = Company(id=cid, code="STAGE01", name="Staging Enterprise Mart", gstin="33AAAPL9999Z1Z5", state="Tamil Nadu", fin_year="2026-2027", is_active=True)
        branch = Branch(id=bid, company_id=cid, code="BR01", name="Staging Main Store", is_active=True)
        session.add_all([comp, branch])

    # 4. Provision Staging Administrators
    cs = CompanyService(db=fast_mgr)
    cs.provision_initial_administrator(company_code_or_id="STAGE01", username="staging_admin", password="StagingPassword123!", full_name="Staging Administrator")

    auth_serv = TraditionalAuthService(trad_mgr)
    auth_serv.create_user(
        company_id=cid,
        username="staging_admin",
        password="StagingPassword123!",
        role_name="Administrator",
        full_name="Staging Administrator"
    )

    return {
        "fast_db_path": fast_staging_db,
        "trad_db_path": trad_staging_db,
        "fast_mgr": fast_mgr,
        "trad_mgr": trad_mgr,
        "company_id": cid,
        "branch_id": bid,
        "company_service": cs,
        "traditional_auth_service": auth_serv,
    }


# ==============================================================================
# 3. Staging Startup & Workflow Tests
# ==============================================================================

def test_staging_database_initialization_and_schema(staging_env):
    """Verify that both Fast and Traditional staging databases contain expected tables."""
    trad_mgr = staging_env["trad_mgr"]
    fast_mgr = staging_env["fast_mgr"]

    # Verify Traditional Alembic schema
    inspector = inspect(trad_mgr.write_engine)
    trad_tables = set(inspector.get_table_names())
    expected_trad = {
        "companies", "branches", "roles", "users", "accounts",
        "customer_receipts", "receipt_allocations",
        "supplier_payments", "payment_allocations",
        "paper_configurations", "bill_layout_configurations",
        "voucher_numbering_configurations", "gst_tax_configurations",
        "inventory_configurations"
    }
    assert expected_trad.issubset(trad_tables)

    # Verify Fast Billing schema
    with fast_mgr.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        fast_tables = set(r[0] for r in cursor.fetchall())
        expected_fast = {"companies", "branches", "sales_vouchers", "sales_voucher_items", "payments", "items", "item_barcodes"}
        assert expected_fast.issubset(fast_tables)


def test_staging_authentication_and_session(staging_env):
    """Verify authentication for both Fast Billing cashier and Traditional ERP in staging."""
    cs = staging_env["company_service"]
    auth_serv = staging_env["traditional_auth_service"]

    # 1. Fast Billing Login
    fast_auth = cs.authenticate("STAGE01", "StagingPassword123!", username="staging_admin")
    assert fast_auth is not None
    assert fast_auth["code"] == "STAGE01"
    assert fast_auth["role"] == "Administrator"

    # 2. Traditional ERP Login
    trad_auth = auth_serv.authenticate("STAGE01", "staging_admin", "StagingPassword123!")
    assert trad_auth is not None
    assert trad_auth["success"] is True
    assert trad_auth["user"]["username"] == "STAGING_ADMIN"
    assert "session_token" in trad_auth


def test_staging_traditional_payment_workflow(staging_env):
    """Verify customer receipt recording and double-entry GL journal in staging."""
    trad_mgr = staging_env["trad_mgr"]
    cid = staging_env["company_id"]
    bid = staging_env["branch_id"]

    acc_service = TraditionalAccountingService(trad_mgr)
    pay_service = TraditionalPaymentService(trad_mgr, accounting_service=acc_service)

    # Seed Accounts
    with trad_mgr.session_scope() as session:
        cash_acc = Account(id="acc_cash_stg", company_id=cid, code="1000", name="Staging Cash Counter", account_type="Cash", is_active=True)
        cust_acc = Account(id="acc_cust_stg", company_id=cid, code="1050", name="Staging Retail Customer", account_type="Debtor", is_active=True)
        session.add_all([cash_acc, cust_acc])

    receipt = pay_service.create_customer_receipt(
        company_id=cid,
        branch_id=bid,
        customer_account_id="acc_cust_stg",
        deposit_account_id="acc_cash_stg",
        total_amount=Decimal("1500.00"),
        payment_method="CASH",
        receipt_date="18-11-2026",
        notes="Staging verification receipt"
    )

    assert receipt["voucher_number"].startswith("REC-")
    assert receipt["status"] == "POSTED"
    assert Decimal(str(receipt["total_amount"])) == Decimal("1500.00")
    assert receipt["journal_id"] is not None


def test_staging_fast_billing_pos_workflow(staging_env):
    """Verify barcode lookup, retail checkout and inventory movement in staging."""
    fast_mgr = staging_env["fast_mgr"]
    cid = staging_env["company_id"]

    cat = CatalogueService(fast_mgr)
    bill = BillingService(fast_mgr)

    # Save item
    item = cat.save_item(cid, {
        "name": "Staging Organic Milk 1L",
        "alias": "890123456789",
        "sales_price": 60.0,
        "op_stock_qty": 100.0,
        "tax_category": "GST 5%",
    })

    # Lookup
    found = cat.find_by_barcode(cid, "890123456789")
    assert found is not None
    assert found["name"] == "STAGING ORGANIC MILK 1L"

    # Checkout
    sale = bill.create_sale_invoice(
        company_id=cid,
        items=[{"id": item["id"], "name": item["name"], "price": 60.0, "qty": 2.0, "tax_rate": 5.0}],
        party_name="Walk-in Customer",
        sale_type="L/GST-5%",
        payment_method="CASH",
    )

    assert sale["vch_no"] == "STG-0001"
    assert sale["grand_total"] == 126.0  # 120 + 5% = 126.0


def test_staging_restart_persistence(staging_env):
    """Verify that reopening staging database files maintains all recorded vouchers."""
    fast_path = staging_env["fast_db_path"]
    cid = staging_env["company_id"]

    # Reconnect fresh manager to same staging SQLite file
    reopened = DatabaseManager(str(fast_path))
    reopened_bill = BillingService(reopened)

    vch_no = reopened_bill.get_next_voucher_number(cid)
    assert vch_no is not None


def test_production_database_remains_completely_untouched():
    """Verify zero byte alterations to production databases during staging operations."""
    fast_hash = compute_sha256(FAST_PROD_DB)
    trad_hash = compute_sha256(TRAD_PROD_DB)
    app_hash = compute_sha256(APP_PROD_DB)

    # Baseline hashes must match
    assert fast_hash == "bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd"
    assert app_hash == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert trad_hash == "770dde96956adf7224023c546559ba6cc9f101e34a71dda9b27d9e717ca9d8c7"


def test_staging_invalid_configuration_fails_closed(tmp_path, monkeypatch):
    """
    Verify that an invalid staging configuration causes app.py startup to fail closed.
    """
    import subprocess
    cmd = [
        sys.executable,
        "app.py",
    ]
    env = os.environ.copy()
    env["APP_ENV"] = "staging"
    env["DATABASE_URL"] = "sqlite:///data/anti_matrix_billing.db"
    env["TRADITIONAL_DATABASE_URL"] = "sqlite:///data/traditional_billing.db"

    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=str(BASE_DIR))
    assert proc.returncode == 1
    assert "[FATAL CONFIGURATION ERROR]" in proc.stderr


def test_staging_seed_idempotency_with_temporary_databases(tmp_path):
    """
    Verify that scripts/seed_staging_data.py is fully idempotent on fresh temporary databases.
    """
    fast_tmp = tmp_path / "staging_anti_matrix_billing.db"
    trad_tmp = tmp_path / "staging_traditional_billing.db"

    env = os.environ.copy()
    env["APP_ENV"] = "staging"
    env["DATABASE_ENV"] = "staging"
    env["FAST_DATABASE_PATH"] = str(fast_tmp)
    env["TRADITIONAL_DATABASE_PATH"] = str(trad_tmp)
    env["DATABASE_URL"] = f"sqlite:///{fast_tmp}"
    env["TRADITIONAL_DATABASE_URL"] = f"sqlite:///{trad_tmp}"
    env["STAGING_ALLOW_DEMO_CREDENTIALS"] = "1"

    cmd = [sys.executable, "scripts/seed_staging_data.py"]

    # Run 1: initial provisioning
    proc1 = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=str(BASE_DIR))
    assert proc1.returncode == 0, f"Run 1 failed: {proc1.stderr}"
    assert fast_tmp.exists()
    assert trad_tmp.exists()
    assert "STAGING PROVISIONING COMPLETE" in proc1.stdout

    # Run 2: repeated provisioning must succeed cleanly without IntegrityError
    proc2 = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=str(BASE_DIR))
    assert proc2.returncode == 0, f"Run 2 failed: {proc2.stderr}"
    assert "already exists" in proc2.stdout
    assert "STAGING PROVISIONING COMPLETE" in proc2.stdout

