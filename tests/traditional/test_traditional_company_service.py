"""
Test Suite: Traditional Billing Company & Branch Service.
Tests company lifecycle, single BR01 branch enforcement,
atomic initial setup, and permanent setup lockout.
"""

from pathlib import Path
import pytest
from sqlalchemy import create_engine
from alembic.config import Config
from alembic import command

from db.traditional_database import TraditionalDatabaseManager
from services.traditional_company_service import TraditionalCompanyService
from db.traditional_models import Company, Branch, User, Account


@pytest.fixture
def company_env(tmp_path):
    db_file = tmp_path / "test_company.db"
    db_url = f"sqlite:///{db_file}"

    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    service = TraditionalCompanyService(db_manager=trad_mgr)

    yield service, trad_mgr

    trad_mgr.close()


def test_initial_setup_and_permanent_lockout(company_env):
    service, trad_mgr = company_env

    # 1. First run: company count is 0
    assert service.get_company_count() == 0

    setup_data = {
        "code": "CORP01",
        "name": "Alpha Retail Enterprise",
        "finYear": "2026-2027",
        "taxNo": "33AAAPL1234F1Z1",
        "state": "Tamilnadu",
        "adminUsername": "SUPERADMIN",
        "adminPassword": "SuperSecurePassword@2026",
    }

    # 2. Execute initial setup
    res = service.initial_setup(setup_data)
    assert res["companyCode"] == "CORP01"
    assert res["branchCode"] == "BR01"
    assert res["adminUsername"] == "SUPERADMIN"

    # 3. Assert count is now 1
    assert service.get_company_count() == 1

    # 4. Verify atomic records exist
    with trad_mgr.read_session_scope() as session:
        comp = session.query(Company).filter_by(code="CORP01").first()
        assert comp is not None
        assert comp.name == "Alpha Retail Enterprise"

        branch = session.query(Branch).filter_by(company_id=comp.id).first()
        assert branch is not None
        assert branch.code == "BR01"

        admin = session.query(User).filter_by(company_id=comp.id, username="SUPERADMIN").first()
        assert admin is not None
        assert admin.role_name == "Administrator"

        cash_acc = session.query(Account).filter_by(company_id=comp.id, code="CASH").first()
        assert cash_acc is not None
        sales_acc = session.query(Account).filter_by(company_id=comp.id, code="SALES").first()
        assert sales_acc is not None

    # 5. Second setup attempt MUST fail fail-closed
    with pytest.raises(PermissionError) as exc_info:
        service.initial_setup({
            "name": "Second Company Attempt",
            "adminPassword": "pwd",
        })
    assert "permanently closed" in str(exc_info.value)


def test_single_br01_branch_enforcement(company_env):
    service, trad_mgr = company_env

    # Setup initial company
    res = service.initial_setup({
        "code": "CORP01",
        "name": "Single Branch Test Corp",
        "adminPassword": "pwd",
    })
    comp_id = res["companyId"]

    # Attempting to insert a second branch for this company MUST fail unique constraint
    with pytest.raises(Exception):
        with trad_mgr.session_scope() as session:
            b2 = Branch(
                company_id=comp_id,
                code="BR01",
                name="Second Branch",
            )
            session.add(b2)
            session.commit()


def test_update_and_list_companies(company_env):
    service, trad_mgr = company_env

    res = service.initial_setup({
        "code": "CORP01",
        "name": "Alpha Retail Enterprise",
        "adminPassword": "pwd",
    })
    comp_id = res["companyId"]

    # Update company profile
    updated = service.update_company(comp_id, {
        "name": "Alpha Retail Enterprise Pvt Ltd",
        "finYear": "2026-2028",
    })
    assert updated["name"] == "Alpha Retail Enterprise Pvt Ltd"
    assert updated["finYear"] == "2026-2028"

    # List active companies
    active = service.list_active_companies()
    assert len(active) == 1
    assert active[0]["code"] == "CORP01"
    assert active[0]["name"] == "Alpha Retail Enterprise Pvt Ltd"
