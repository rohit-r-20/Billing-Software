"""
Traditional Billing Company & Administrator Recovery Service.
Handles:
1. Public inspection of company recovery profile (without passwords/hashes).
2. Atomic update of company name, code, administrator username, and password reset.
3. Preserves company ID, existing business records, branch relationships, items, and sequences.
4. Validates company code and administrator username uniqueness.
5. Invalidates existing active sessions for the administrator user upon credential modification.
6. Writes audit log entries.
"""

import uuid
import json
from typing import Optional, Dict, Any, List
from sqlalchemy import select, and_, func

from db.traditional_database import traditional_db_manager, TraditionalDatabaseManager
from db.traditional_models import (
    Company,
    Branch,
    User,
    AuditLog,
    utc_now,
)
from services.traditional_auth_service import hash_password, session_registry
from core.logging_config import logger


class TraditionalRecoveryService:
    def __init__(self, db_manager: Optional[TraditionalDatabaseManager] = None):
        self.db = db_manager or traditional_db_manager

    def get_recovery_profile(self, company_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieves company details and Administrator username for the recovery screen.
        Strictly omits any password or password hash.
        """
        with self.db.read_session_scope() as session:
            comp = None
            if company_id:
                comp = session.scalar(select(Company).where(Company.id == company_id))
            if not comp:
                comp = session.scalar(select(Company).order_by(Company.code.asc()))

            if not comp:
                raise ValueError("No company found in Traditional Billing database. Please complete initial setup first.")

            # Find the primary Administrator user for this company
            admin_user = session.scalar(
                select(User)
                .where(and_(User.company_id == comp.id, User.role_name == "Administrator"))
                .order_by(User.created_at.asc())
            )
            if not admin_user:
                # Fallback to the earliest created user in company
                admin_user = session.scalar(
                    select(User).where(User.company_id == comp.id).order_by(User.created_at.asc())
                )

            return {
                "company_id": comp.id,
                "company_name": comp.name,
                "company_code": comp.code,
                "fin_year": comp.fin_year or "2026-2027",
                "gstin": comp.gstin or "",
                "state": comp.state or "",
                "admin_user_id": admin_user.id if admin_user else None,
                "admin_username": admin_user.username if admin_user else "ADMIN",
            }

    def recover_company_and_admin(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Atomically updates company name, company code, Administrator username,
        and resets Administrator password.

        Preserves:
        - company.id and all foreign key relationships (branches, users, items, invoices, sequences).
        - Existing stock, accounts, and historical logs.
        """
        company_id = str(data.get("company_id") or "").strip()
        if not company_id:
            raise ValueError("Company ID is required for recovery.")

        new_company_name = str(data.get("company_name") or "").strip()
        if not new_company_name:
            raise ValueError("Company name cannot be empty.")

        new_company_code = str(data.get("company_code") or "").strip().upper()
        if not new_company_code:
            raise ValueError("Company code cannot be empty.")

        new_admin_username = str(data.get("admin_username") or "").strip().upper()
        if not new_admin_username:
            raise ValueError("Administrator username cannot be empty.")

        admin_user_id = data.get("admin_user_id")
        new_password = data.get("new_password")
        password_was_reset = False

        if new_password is not None and str(new_password).strip() != "":
            clean_pwd = str(new_password).strip()
            if len(clean_pwd) < 4:
                raise ValueError("New password must be at least 4 characters.")
            password_was_reset = True
        else:
            clean_pwd = None

        with self.db.session_scope() as session:
            # 1. Fetch Company
            comp = session.scalar(select(Company).where(Company.id == company_id))
            if not comp:
                raise ValueError(f"Company '{company_id}' does not exist.")

            # 2. Check Company Code uniqueness
            code_conflict = session.scalar(
                select(Company.id).where(
                    and_(Company.code == new_company_code, Company.id != company_id)
                )
            )
            if code_conflict:
                raise ValueError(f"Company code '{new_company_code}' is already used by another company.")

            # 3. Fetch Administrator User
            admin_user = None
            if admin_user_id:
                admin_user = session.scalar(
                    select(User).where(and_(User.company_id == company_id, User.id == admin_user_id))
                )
            if not admin_user:
                admin_user = session.scalar(
                    select(User)
                    .where(and_(User.company_id == company_id, User.role_name == "Administrator"))
                    .order_by(User.created_at.asc())
                )
            if not admin_user:
                admin_user = session.scalar(
                    select(User).where(User.company_id == company_id).order_by(User.created_at.asc())
                )

            if not admin_user:
                raise ValueError(f"No Administrator user found for company '{company_id}'.")

            # 4. Check Username uniqueness within company
            username_conflict = session.scalar(
                select(User.id).where(
                    and_(
                        User.company_id == company_id,
                        func.upper(User.username) == new_admin_username.upper(),
                        User.id != admin_user.id,
                    )
                )
            )
            if username_conflict:
                raise ValueError(f"Username '{new_admin_username}' is already in use by another user in this company.")

            # Track old values for audit log
            old_company_name = comp.name
            old_company_code = comp.code
            old_admin_username = admin_user.username

            # 5. Apply Company Updates
            comp.name = new_company_name
            comp.code = new_company_code
            comp.updated_at = utc_now()

            # 6. Apply Administrator Updates
            admin_user.username = new_admin_username
            if clean_pwd is not None:
                admin_user.password_hash = hash_password(clean_pwd)
            admin_user.updated_at = utc_now()

            # 7. Write Audit Log entry
            audit_payload = {
                "company_id": comp.id,
                "old_company_name": old_company_name,
                "new_company_name": new_company_name,
                "old_company_code": old_company_code,
                "new_company_code": new_company_code,
                "admin_user_id": admin_user.id,
                "old_admin_username": old_admin_username,
                "new_admin_username": new_admin_username,
                "password_reset": password_was_reset,
                "recovered_at": utc_now().isoformat(),
            }
            audit = AuditLog(
                id=str(uuid.uuid4()),
                company_id=comp.id,
                user_id=admin_user.id,
                event_type="COMPANY_ADMIN_RECOVERED",
                entity_type="COMPANY_RECOVERY",
                entity_id=comp.id,
                payload_json=json.dumps(audit_payload),
                created_at=utc_now(),
            )
            session.add(audit)
            session.flush()

            # Invalidate any active sessions for the administrator
            session_registry.revoke_user_sessions(comp.id, admin_user.id)

            logger.info(
                f"Traditional Billing Recovery completed for company '{comp.id}': "
                f"name='{new_company_name}', code='{new_company_code}', admin='{new_admin_username}'."
            )

            return {
                "company_id": comp.id,
                "company_name": comp.name,
                "company_code": comp.code,
                "admin_user_id": admin_user.id,
                "admin_username": admin_user.username,
                "password_reset": password_was_reset,
            }
