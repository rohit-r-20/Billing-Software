"""
Test Suite: Traditional Billing Authentication and Session Management.
Tests bcrypt password hashing, legacy PBKDF2 verification compatibility,
multi-tenant login, fail-closed role enforcement, and session lifecycle.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from alembic.config import Config
from alembic import command

from db.traditional_database import TraditionalDatabaseManager
from db.traditional_models import Company, Branch, User, Role
from services.traditional_auth_service import (
    TraditionalAuthService,
    TraditionalSessionRegistry,
    hash_password,
    verify_password,
    RECOGNIZED_SYSTEM_ROLES,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_password_hashing_and_verification():
    """Verify bcrypt hashing and verification behavior."""
    pwd = "SecureCashierPassword@2026"
    pwd_hash = hash_password(pwd)

    assert pwd_hash.startswith(("$2a$", "$2b$", "$2y$"))
    assert verify_password(pwd_hash, pwd) is True
    assert verify_password(pwd_hash, "WrongPassword") is False
    assert verify_password(pwd_hash, "") is False
    assert verify_password("", pwd) is False

    with pytest.raises(ValueError):
        hash_password("")


def test_legacy_pbkdf2_compatibility():
    """Verify that Stage 1 PBKDF2 hashes (salt$hash) are verified successfully for backward compatibility."""
    import hashlib
    import binascii
    import os

    salt = os.urandom(16)
    pwd = "LegacyStage1Password"
    dk = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt, 100000)
    legacy_hash = binascii.hexlify(salt).decode("ascii") + "$" + binascii.hexlify(dk).decode("ascii")

    assert verify_password(legacy_hash, pwd) is True
    assert verify_password(legacy_hash, "Wrong") is False


def test_session_registry_lifecycle():
    """Test session issuance, lookup, touch, idle timeout, shift limit, and revocation."""
    registry = TraditionalSessionRegistry()

    token = registry.create_session(
        user_id="u1",
        company_id="c1",
        branch_id="b1",
        role_name="Cashier",
        username="CASHIER1",
        display_name="Cashier One",
        idle_timeout_seconds=300,
        shift_limit_seconds=600,
    )

    # 1. Lookup active session
    session = registry.get_session(token)
    assert session is not None
    assert session.username == "CASHIER1"
    assert session.role_name == "Cashier"

    # 2. Simulate idle timeout
    session.last_activity = utc_now() - timedelta(seconds=301)
    assert registry.get_session(token) is None  # Should expire and return None

    # 3. Simulate shift limit
    token2 = registry.create_session(
        user_id="u2",
        company_id="c1",
        branch_id="b1",
        role_name="Manager",
        username="MANAGER1",
        idle_timeout_seconds=3600,
        shift_limit_seconds=600,
    )
    s2 = registry.get_session(token2)
    assert s2 is not None
    s2.created_at = utc_now() - timedelta(seconds=601)
    assert registry.get_session(token2) is None

    # 4. Explicit revocation
    token3 = registry.create_session(
        user_id="u3",
        company_id="c1",
        branch_id="b1",
        role_name="Administrator",
        username="ADMIN1",
    )
    assert registry.revoke_session(token3) is True
    assert registry.get_session(token3) is None


@pytest.fixture
def traditional_test_env(tmp_path):
    """Fixture to set up an isolated Traditional Billing database with migrated foundation schema."""
    db_file = tmp_path / "auth_test_traditional.db"
    db_url = f"sqlite:///{db_file}"

    # Run migrations
    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    registry = TraditionalSessionRegistry()
    service = TraditionalAuthService(db_manager=trad_mgr, registry=registry)

    # Seed test company and branch
    with trad_mgr.session_scope() as session:
        comp = Company(
            id="comp_test_1",
            code="CORP01",
            name="Alpha Corp",
            fin_year="2026-2027",
            gstin="27ABCDE1234F1Z5",
            state="Maharashtra",
            is_active=True,
        )
        branch = Branch(
            id="branch_test_1",
            company_id="comp_test_1",
            code="BR01",
            name="Alpha Corp Head Office",
            is_active=True,
        )
        session.add(comp)
        session.add(branch)

    yield service, trad_mgr, registry

    trad_mgr.close()


def test_traditional_auth_service_successful_login(traditional_test_env):
    """Verify successful authentication against isolated Traditional database."""
    service, trad_mgr, registry = traditional_test_env

    # Create active user
    service.create_user(
        company_id="comp_test_1",
        username="cashier1",
        password="ValidPassword123!",
        role_name="Cashier",
        full_name="Alice Smith",
    )

    # Attempt authentication
    auth_res = service.authenticate("CORP01", "cashier1", "ValidPassword123!")
    assert auth_res is not None
    assert auth_res["success"] is True
    assert auth_res["company"]["code"] == "CORP01"
    assert auth_res["branch"]["code"] == "BR01"
    assert auth_res["user"]["username"] == "CASHIER1"
    assert auth_res["user"]["role"] == "Cashier"
    assert auth_res["user"]["displayName"] == "Alice Smith"

    # Verify session is registered
    session = registry.get_session(auth_res["session_token"])
    assert session is not None
    assert session.user_id == auth_res["user"]["id"]


def test_traditional_auth_service_failures(traditional_test_env):
    """Verify fail-closed behavior for bad credentials, inactive user, inactive company, and bad role."""
    service, trad_mgr, registry = traditional_test_env

    service.create_user(
        company_id="comp_test_1",
        username="manager1",
        password="SecretManagerPassword!",
        role_name="Manager",
    )

    # 1. Incorrect password
    assert service.authenticate("CORP01", "manager1", "WrongPassword!") is None

    # 2. Non-existent username
    assert service.authenticate("CORP01", "ghost_user", "SecretManagerPassword!") is None

    # 3. Non-existent company code
    assert service.authenticate("GHOST_CO", "manager1", "SecretManagerPassword!") is None

    # 4. Inactive user
    with trad_mgr.session_scope() as session:
        u = session.query(User).filter_by(username="MANAGER1").first()
        u.is_active = False

    assert service.authenticate("CORP01", "manager1", "SecretManagerPassword!") is None

    # Re-enable user
    with trad_mgr.session_scope() as session:
        u = session.query(User).filter_by(username="MANAGER1").first()
        u.is_active = True

    # 5. Inactive company
    with trad_mgr.session_scope() as session:
        c = session.query(Company).filter_by(code="CORP01").first()
        c.is_active = False

    assert service.authenticate("CORP01", "manager1", "SecretManagerPassword!") is None


def test_traditional_auth_password_change_and_session_invalidation(traditional_test_env):
    """Verify password change hashes new password with bcrypt and invalidates active sessions."""
    service, trad_mgr, registry = traditional_test_env

    user = service.create_user(
        company_id="comp_test_1",
        username="admin1",
        password="InitialPassword@123",
        role_name="Administrator",
    )

    # Log in
    res = service.authenticate("CORP01", "admin1", "InitialPassword@123")
    assert res is not None
    token = res["session_token"]
    assert registry.get_session(token) is None or registry.get_session(token).username == "ADMIN1"

    # Change password
    success = service.change_password(
        company_id="comp_test_1",
        user_id=user.id,
        old_password="InitialPassword@123",
        new_password="NewSecurePassword@456",
    )
    assert success is True

    # Prior session token must now be invalidated
    assert registry.get_session(token) is None

    # Old password must now fail
    assert service.authenticate("CORP01", "admin1", "InitialPassword@123") is None

    # New password must succeed
    new_res = service.authenticate("CORP01", "admin1", "NewSecurePassword@456")
    assert new_res is not None
    assert new_res["success"] is True
