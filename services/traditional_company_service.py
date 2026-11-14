"""
Traditional Billing Company & Branch Service.
Enforces single BR01 operational branch per company, tenant isolation,
and one-time atomic bootstrap onboarding.
"""

import uuid
from typing import Optional, Dict, Any, List
from sqlalchemy import select, func, and_

from db.traditional_database import traditional_db_manager, TraditionalDatabaseManager
from db.traditional_models import Company, Branch, User, Account, AuditLog, utc_now
from services.traditional_auth_service import hash_password
from core.logging_config import logger


class TraditionalCompanyService:
    def __init__(self, db_manager: Optional[TraditionalDatabaseManager] = None):
        self.db = db_manager or traditional_db_manager

    def get_company_count(self) -> int:
        """Returns total count of companies in the Traditional Billing database."""
        with self.db.read_session_scope() as session:
            return session.scalar(select(func.count(Company.id))) or 0

    def list_active_companies(self) -> List[Dict[str, Any]]:
        """Public sanitized listing of active companies for the login screen."""
        with self.db.read_session_scope() as session:
            companies = session.scalars(
                select(Company).where(Company.is_active == True).order_by(Company.code.asc())
            ).all()
            return [
                {
                    "id": c.id,
                    "code": c.code,
                    "name": c.name,
                    "finYear": c.fin_year,
                    "state": c.state,
                }
                for c in companies
            ]

    def get_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Returns full company profile and its associated BR01 branch."""
        with self.db.read_session_scope() as session:
            comp = session.scalar(select(Company).where(Company.id == company_id))
            if not comp:
                return None

            branch = session.scalar(
                select(Branch).where(and_(Branch.company_id == company_id, Branch.code == "BR01"))
            )

            return {
                "id": comp.id,
                "code": comp.code,
                "name": comp.name,
                "finYear": comp.fin_year,
                "taxNo": comp.gstin,
                "state": comp.state,
                "isActive": comp.is_active,
                "createdAt": comp.created_at.isoformat() if comp.created_at else None,
                "branch": {
                    "id": branch.id if branch else None,
                    "code": branch.code if branch else "BR01",
                    "name": branch.name if branch else "Main Branch",
                } if branch else None,
            }

    def update_company(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update company metadata (Admin only)."""
        with self.db.session_scope() as session:
            comp = session.scalar(select(Company).where(Company.id == company_id))
            if not comp:
                raise ValueError(f"Company '{company_id}' not found.")

            if "name" in data and str(data["name"]).strip():
                comp.name = str(data["name"]).strip()
            if "finYear" in data:
                comp.fin_year = str(data["finYear"]).strip() if data["finYear"] else None
            if "taxNo" in data:
                comp.gstin = str(data["taxNo"]).strip().upper() if data["taxNo"] else None
            if "state" in data:
                comp.state = str(data["state"]).strip() if data["state"] else None

            comp.updated_at = utc_now()
            session.flush()

            return {
                "id": comp.id,
                "code": comp.code,
                "name": comp.name,
                "finYear": comp.fin_year,
                "taxNo": comp.gstin,
                "state": comp.state,
            }

    def initial_setup(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        One-time atomic onboarding transaction.
        Creates the first Company, its single BR01 Branch, the initial Administrator,
        default ledger accounts, and audit log.
        Permanently locks out subsequent setup calls once committed.
        """
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("Company name is required for initial setup.")

        code = str(data.get("code") or "COMP0001").strip().upper()
        fin_year = str(data.get("finYear") or "2026-2027").strip()
        gstin = str(data.get("taxNo") or "").strip().upper() or None
        state = str(data.get("state") or "Tamilnadu").strip()

        admin_username = str(data.get("adminUsername") or data.get("username") or "ADMIN").strip().upper()
        admin_password = str(data.get("adminPassword") or data.get("password") or "").strip()
        if not admin_password:
            raise ValueError("Administrator password is required for initial setup.")

        with self.db.session_scope() as session:
            # 1. Authoritative permanent lockout check inside write lock
            existing_count = session.scalar(select(func.count(Company.id))) or 0
            if existing_count > 0:
                raise PermissionError("Initial setup is permanently closed. One or more companies already exist.")

            comp_id = str(uuid.uuid4())
            branch_id = str(uuid.uuid4())
            admin_id = str(uuid.uuid4())

            # 2. Insert Company
            comp = Company(
                id=comp_id,
                code=code,
                name=name,
                fin_year=fin_year,
                gstin=gstin,
                state=state,
                is_active=True,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(comp)

            # 3. Insert single BR01 Branch
            branch = Branch(
                id=branch_id,
                company_id=comp_id,
                code="BR01",
                name="Main Branch",
                is_active=True,
                created_at=utc_now(),
            )
            session.add(branch)

            # 4. Insert initial Administrator user
            pwd_hash = hash_password(admin_password)
            admin_user = User(
                id=admin_id,
                company_id=comp_id,
                username=admin_username,
                password_hash=pwd_hash,
                full_name="System Administrator",
                role_name="Administrator",
                is_active=True,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(admin_user)

            # 5. Insert standard initial ledger accounts
            cash_acc = Account(
                id=str(uuid.uuid4()),
                company_id=comp_id,
                code="CASH",
                name="Cash in Hand",
                account_type="Cash",
                is_active=True,
                created_at=utc_now(),
            )
            sales_acc = Account(
                id=str(uuid.uuid4()),
                company_id=comp_id,
                code="SALES",
                name="General Sales",
                account_type="Sales",
                is_active=True,
                created_at=utc_now(),
            )
            session.add(cash_acc)
            session.add(sales_acc)

            # 6. Audit log entry
            audit = AuditLog(
                id=str(uuid.uuid4()),
                company_id=comp_id,
                user_id=admin_id,
                event_type="INITIAL_SETUP_COMPLETED",
                entity_type="COMPANY",
                entity_id=comp_id,
                payload_json=f'{{"code":"{code}","name":"{name}","admin":"{admin_username}"}}',
                created_at=utc_now(),
            )
            session.add(audit)
            session.flush()

            logger.info(f"Traditional Billing initial setup completed for '{name}' ({code}).")
            return {
                "companyId": comp_id,
                "companyCode": code,
                "companyName": name,
                "branchId": branch_id,
                "branchCode": "BR01",
                "adminUserId": admin_id,
                "adminUsername": admin_username,
            }
