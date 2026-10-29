"""
Unit tests for Authentication Flow, User Roles, and Company Service in Anti Matrix Billing ERP.
"""
import pytest
from services.company_service import CompanyService
from services.migration_service import MigrationService
from db.database import DatabaseManager


@pytest.fixture
def test_company_service(tmp_path):
    db_file = tmp_path / "test_auth.db"
    db_mgr = DatabaseManager(str(db_file))
    db_mgr.run_migrations()

    # Seed company record with password 'a'
    migrator = MigrationService(db_mgr)
    migrator.import_localstorage_payload({
        "alpha_companies": [
            {
                "id": "COMP0001",
                "name": "ANTI MATRIX",
                "code": "COMP0001",
                "finYear": "2026-2027 (1 Yr)",
                "taxNo": "33AAAPL1234F1Z1",
                "state": "Tamilnadu",
                "username": "A",
                "password": "a"
            }
        ]
    })
    return CompanyService(db=db_mgr)


def test_successful_authentication_with_code_and_password(test_company_service):
    # Default seeded company COMP0001 with password 'a'
    comp = test_company_service.authenticate("COMP0001", "a")
    assert comp is not None
    assert comp["code"] == "COMP0001"
    assert comp["name"] == "ANTI MATRIX"
    assert comp["username"] == "A"
    assert comp["role"] == "Administrator"


def test_successful_authentication_with_username_and_password(test_company_service):
    # Authenticate with username 'A' and password 'a'
    comp = test_company_service.authenticate("A", "a")
    assert comp is not None
    assert comp["code"] == "COMP0001"
    assert comp["username"] == "A"
    assert comp["role"] == "Administrator"


def test_failed_authentication_with_invalid_password(test_company_service):
    # Incorrect password should return None
    comp = test_company_service.authenticate("COMP0001", "wrong_password_123")
    assert comp is None

    # Empty string should not bypass authentication when a password is set
    comp2 = test_company_service.authenticate("COMP0001", "wrong")
    assert comp2 is None


def test_failed_authentication_with_nonexistent_user_or_company(test_company_service):
    comp = test_company_service.authenticate("NON_EXISTENT_999", "a")
    assert comp is None


def test_authentication_with_code_and_matching_username(test_company_service):
    # Both code and username provided
    comp = test_company_service.authenticate("COMP0001", "a", username="A")
    assert comp is not None
    assert comp["code"] == "COMP0001"

    # Mismatched username
    mismatch = test_company_service.authenticate("COMP0001", "a", username="DIFFERENT_USER")
    assert mismatch is None


def test_company_listing_for_login_dropdown(test_company_service):
    comps = test_company_service.list_companies()
    assert len(comps) >= 1
    codes = [c["code"] for c in comps]
    assert "COMP0001" in codes
