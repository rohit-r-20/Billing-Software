"""
Test Suite: Traditional Billing Bootstrap Setup Token Lifecycle & Authorization.
Covers:
1. Explicit provisioning creates secure 0600 token file.
2. Existing token is not silently overwritten without force=True.
3. Token is NOT generated during startup or traditional_getSetupState().
4. Missing token fails closed.
5. Correct token authorizes initial setup.
6. Incorrect token rejects initial setup.
7. Successful setup removes the token.
8. Existing company permanently blocks setup token provisioning and initial setup.
9. Token value never appears in RPC responses.
"""

import os
import json
import pytest
from pathlib import Path
from alembic.config import Config
from alembic import command

from core.configuration import config
from db.traditional_database import TraditionalDatabaseManager
from services.traditional_company_service import TraditionalCompanyService
from services.traditional_setup_token import (
    get_canonical_setup_token_path,
    provision_setup_token,
    verify_setup_token,
    consume_setup_token,
)
from desktop.web_bridge import BackendBridge


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """
    Creates an isolated temporary environment with its own SQLite database
    and temporary token file location.
    """
    db_file = tmp_path / "test_traditional.db"
    db_url = f"sqlite:///{db_file}"

    # Apply alembic migrations to tmp DB
    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    company_service = TraditionalCompanyService(trad_mgr)

    token_file = tmp_path / ".traditional_setup_token"
    # Point canonical token path helper to temp token file
    monkeypatch.setattr(
        "services.traditional_setup_token.get_canonical_setup_token_path",
        lambda: token_file,
    )
    monkeypatch.setattr(
        "desktop.web_bridge.get_canonical_setup_token_path",
        lambda: token_file,
    )

    yield trad_mgr, company_service, token_file

    trad_mgr.close()


def test_explicit_provisioning_creates_secure_token_file(isolated_env):
    trad_mgr, company_service, token_file = isolated_env

    assert not token_file.exists()
    assert company_service.get_company_count() == 0

    success, token, msg = provision_setup_token(0, token_path=token_file)
    assert success is True
    assert len(token) == 48  # secrets.token_hex(24) -> 48 chars
    assert token_file.exists()
    assert token_file.read_text(encoding="utf-8").strip() == token

    # Check 0600 permissions on POSIX
    if os.name == "posix":
        mode = stat_mode = os.stat(token_file).st_mode & 0o777
        assert mode == 0o600, f"Expected 0o600 permissions, got {oct(mode)}"


def test_existing_token_not_silently_overwritten(isolated_env):
    trad_mgr, company_service, token_file = isolated_env

    # First provisioning
    success1, token1, _ = provision_setup_token(0, token_path=token_file)
    assert success1 is True

    # Second provisioning without force: must preserve token1
    success2, token2, msg2 = provision_setup_token(0, token_path=token_file, force=False)
    assert success2 is False
    assert token2 == token1
    assert "already exists" in msg2
    assert token_file.read_text(encoding="utf-8").strip() == token1

    # Third provisioning with force: must rotate
    success3, token3, _ = provision_setup_token(0, token_path=token_file, force=True)
    assert success3 is True
    assert token3 != token1
    assert token_file.read_text(encoding="utf-8").strip() == token3


def test_token_not_generated_during_startup_or_get_setup_state(isolated_env):
    trad_mgr, company_service, token_file = isolated_env

    # 1. Startup ensure_initialized does not generate token
    trad_mgr.ensure_initialized()
    assert not token_file.exists(), "ensure_initialized() must NOT create setup token"

    # 2. WebBridge instantiation does not generate token
    bridge = BackendBridge(parent=None)
    bridge._traditional_company_service = company_service
    assert not token_file.exists(), "BackendBridge initialization must NOT create setup token"

    # 3. traditional_getSetupState RPC does not generate token
    res = json.loads(bridge.traditional_getSetupState())
    assert res["success"] is True
    assert res["data"]["is_first_run"] is True
    assert not token_file.exists(), "traditional_getSetupState() must NOT create setup token"


def test_missing_token_fails_closed(isolated_env):
    trad_mgr, company_service, token_file = isolated_env

    assert not token_file.exists()

    bridge = BackendBridge(parent=None)
    bridge._traditional_company_service = company_service

    setup_payload = json.dumps({
        "code": "CORP01",
        "name": "Alpha Enterprise",
        "adminUsername": "ADMIN",
        "adminPassword": "Password@2026",
    })

    # Call initial setup with NO token file on disk
    resp = json.loads(bridge.traditional_initialSetup(setup_payload))
    assert resp["success"] is False
    assert "not found" in resp["error"]
    assert company_service.get_company_count() == 0, "No company should be created when token is missing"


def test_correct_token_authorizes_setup_and_removes_token(isolated_env):
    trad_mgr, company_service, token_file = isolated_env

    # Explicitly provision token
    success, token, _ = provision_setup_token(0, token_path=token_file)
    assert success is True
    assert token_file.exists()

    bridge = BackendBridge(parent=None)
    bridge._traditional_company_service = company_service

    setup_payload = json.dumps({
        "code": "CORP01",
        "name": "Alpha Enterprise",
        "adminUsername": "SUPERADMIN",
        "adminPassword": "SuperSecretPassword@2026",
    })

    # In headless mode (parent_window=None), bridge reads token_file directly for entered_token
    resp = json.loads(bridge.traditional_initialSetup(setup_payload))
    assert resp["success"] is True, f"Setup failed: {resp.get('error')}"
    assert resp["data"]["companyCode"] == "CORP01"
    assert resp["data"]["adminUsername"] == "SUPERADMIN"

    # Verify company is created
    assert company_service.get_company_count() == 1

    # Verify token is safely removed post-commit
    assert not token_file.exists(), "Setup token file must be deleted after successful commit"


def test_incorrect_token_rejects_setup(isolated_env, monkeypatch):
    trad_mgr, company_service, token_file = isolated_env

    success, token, _ = provision_setup_token(0, token_path=token_file)
    assert success is True

    bridge = BackendBridge(parent=None)
    bridge._traditional_company_service = company_service

    # Monkeypatch verify_setup_token to simulate invalid token entered
    monkeypatch.setattr(
        "desktop.web_bridge.verify_setup_token",
        lambda entered, path: False,
    )

    setup_payload = json.dumps({
        "code": "CORP01",
        "name": "Alpha Enterprise",
        "adminUsername": "ADMIN",
        "adminPassword": "Password@2026",
    })

    resp = json.loads(bridge.traditional_initialSetup(setup_payload))
    assert resp["success"] is False
    assert "Invalid setup token" in resp["error"]
    assert company_service.get_company_count() == 0
    # Token file should NOT be deleted on failed attempt, permitting retry
    assert token_file.exists()


def test_existing_company_permanently_blocks_provisioning_and_setup(isolated_env):
    trad_mgr, company_service, token_file = isolated_env

    # Provision first token and complete setup
    provision_setup_token(0, token_path=token_file)
    bridge = BackendBridge(parent=None)
    bridge._traditional_company_service = company_service

    setup_payload = json.dumps({
        "code": "CORP01",
        "name": "Alpha Enterprise",
        "adminUsername": "ADMIN",
        "adminPassword": "Password@2026",
    })
    resp1 = json.loads(bridge.traditional_initialSetup(setup_payload))
    assert resp1["success"] is True
    assert company_service.get_company_count() == 1

    # 1. Attempting to provision a new token MUST be rejected
    success, _, msg = provision_setup_token(1, token_path=token_file)
    assert success is False
    assert "permanently locked out" in msg

    # 2. Attempting initial setup again MUST fail closed
    resp2 = json.loads(bridge.traditional_initialSetup(setup_payload))
    assert resp2["success"] is False
    assert "permanently closed" in resp2["error"]


def test_token_never_appears_in_rpc_responses(isolated_env):
    trad_mgr, company_service, token_file = isolated_env

    success, token, _ = provision_setup_token(0, token_path=token_file)
    assert success is True

    bridge = BackendBridge(parent=None)
    bridge._traditional_company_service = company_service

    # Check setup state response
    state_raw = bridge.traditional_getSetupState()
    assert token not in state_raw, "Token must not appear in traditional_getSetupState response"

    # Check initial setup response
    setup_payload = json.dumps({
        "code": "CORP01",
        "name": "Alpha Enterprise",
        "adminUsername": "ADMIN",
        "adminPassword": "Password@2026",
    })
    setup_raw = bridge.traditional_initialSetup(setup_payload)
    assert token not in setup_raw, "Token must not appear in traditional_initialSetup response"
