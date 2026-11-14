"""
Traditional Billing User & Role Master Service.
Enforces multi-tenant user management, bcrypt password hashing,
last-Administrator transactional protection, and Store Manager privilege barriers.
"""

import uuid
from typing import Optional, Dict, Any, List
from sqlalchemy import select, func, and_

from db.traditional_database import traditional_db_manager, TraditionalDatabaseManager
from db.traditional_models import User, Role, utc_now
from services.traditional_auth_service import (
    hash_password,
    session_registry,
    TraditionalSessionRegistry,
    RECOGNIZED_SYSTEM_ROLES,
)
from core.logging_config import logger


class TraditionalUserService:
    def __init__(
        self,
        db_manager: Optional[TraditionalDatabaseManager] = None,
        registry: Optional[TraditionalSessionRegistry] = None,
    ):
        self.db = db_manager or traditional_db_manager
        self.registry = registry or session_registry

    def list_roles(self) -> List[Dict[str, str]]:
        """Returns recognized system roles."""
        return [{"name": r} for r in sorted(RECOGNIZED_SYSTEM_ROLES)]

    def list_users(self, company_id: str) -> List[Dict[str, Any]]:
        """List all users for the specified company, excluding password hashes."""
        with self.db.read_session_scope() as session:
            users = session.scalars(
                select(User).where(User.company_id == company_id).order_by(User.username.asc())
            ).all()
            return [
                {
                    "id": u.id,
                    "companyId": u.company_id,
                    "username": u.username,
                    "fullName": u.full_name or u.username,
                    "role": u.role_name,
                    "isActive": u.is_active,
                    "createdAt": u.created_at.isoformat() if u.created_at else None,
                    "updatedAt": u.updated_at.isoformat() if u.updated_at else None,
                }
                for u in users
            ]

    def get_user(self, company_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get single user profile within company."""
        with self.db.read_session_scope() as session:
            u = session.scalar(
                select(User).where(and_(User.company_id == company_id, User.id == user_id))
            )
            if not u:
                return None
            return {
                "id": u.id,
                "companyId": u.company_id,
                "username": u.username,
                "fullName": u.full_name or u.username,
                "role": u.role_name,
                "isActive": u.is_active,
                "createdAt": u.created_at.isoformat() if u.created_at else None,
                "updatedAt": u.updated_at.isoformat() if u.updated_at else None,
            }

    def create_user(
        self,
        company_id: str,
        caller_role: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a new user with bcrypt password hash.
        Store Manager barrier: Store Managers cannot create Administrator accounts.
        """
        username = str(data.get("username") or "").strip().upper()
        if not username:
            raise ValueError("Username is required.")

        raw_role = str(data.get("role") or data.get("role_name") or "").strip()
        matched_role = next((r for r in RECOGNIZED_SYSTEM_ROLES if r.lower() == raw_role.lower()), None)
        if not matched_role:
            raise ValueError(f"Unrecognized role '{raw_role}'. Recognized: {', '.join(sorted(RECOGNIZED_SYSTEM_ROLES))}")

        # Store Manager Barrier: cannot assign Administrator role
        if caller_role.lower() == "store manager" and matched_role.lower() == "administrator":
            raise PermissionError("Access Denied: Store Managers cannot create or assign Administrator accounts.")

        password = str(data.get("password") or "").strip()
        if not password:
            raise ValueError("Password is required.")

        full_name = str(data.get("fullName") or data.get("full_name") or username).strip()

        with self.db.session_scope() as session:
            # Check duplicate username within company
            existing = session.scalar(
                select(User).where(and_(User.company_id == company_id, User.username == username))
            )
            if existing:
                raise ValueError(f"Username '{username}' already exists in this company.")

            pwd_hash = hash_password(password)
            new_user = User(
                id=str(uuid.uuid4()),
                company_id=company_id,
                username=username,
                password_hash=pwd_hash,
                full_name=full_name,
                role_name=matched_role,
                is_active=True,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(new_user)
            session.flush()

            logger.info(f"User '{username}' ({matched_role}) created in company '{company_id}'.")
            return {
                "id": new_user.id,
                "companyId": new_user.company_id,
                "username": new_user.username,
                "fullName": new_user.full_name,
                "role": new_user.role_name,
                "isActive": new_user.is_active,
            }

    def update_user(
        self,
        company_id: str,
        caller_role: str,
        caller_user_id: str,
        target_user_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update user profile or role.
        Enforces Last Administrator Protection and Store Manager Barrier.
        """
        with self.db.session_scope() as session:
            target = session.scalar(
                select(User).where(and_(User.company_id == company_id, User.id == target_user_id))
            )
            if not target:
                raise ValueError(f"User '{target_user_id}' not found.")

            # Store Manager Barrier: cannot modify an Administrator
            if caller_role.lower() == "store manager" and target.role_name.lower() == "administrator":
                raise PermissionError("Access Denied: Store Managers cannot modify Administrator accounts.")

            # Role change handling
            if "role" in data or "role_name" in data:
                raw_role = str(data.get("role") or data.get("role_name")).strip()
                matched_role = next((r for r in RECOGNIZED_SYSTEM_ROLES if r.lower() == raw_role.lower()), None)
                if not matched_role:
                    raise ValueError(f"Unrecognized role '{raw_role}'.")

                if caller_role.lower() == "store manager" and matched_role.lower() == "administrator":
                    raise PermissionError("Access Denied: Store Managers cannot promote accounts to Administrator.")

                # Last Administrator Protection: cannot demote the last active Administrator
                if target.role_name == "Administrator" and matched_role != "Administrator":
                    active_admin_count = session.scalar(
                        select(func.count(User.id)).where(
                            and_(
                                User.company_id == company_id,
                                User.role_name == "Administrator",
                                User.is_active == True,
                                User.id != target_user_id,
                            )
                        )
                    ) or 0
                    if active_admin_count == 0:
                        raise ValueError(
                            "Operation rejected: Cannot demote the last active Administrator. "
                            "Every company must retain at least one active Administrator."
                        )

                target.role_name = matched_role

            if "fullName" in data or "full_name" in data:
                fn = str(data.get("fullName") or data.get("full_name") or "").strip()
                if fn:
                    target.full_name = fn

            target.updated_at = utc_now()
            session.flush()

            # Revoke active sessions for target user upon role change
            self.registry.revoke_user_sessions(company_id, target_user_id)

            return {
                "id": target.id,
                "companyId": target.company_id,
                "username": target.username,
                "fullName": target.full_name,
                "role": target.role_name,
                "isActive": target.is_active,
            }

    def set_user_active(
        self,
        company_id: str,
        caller_role: str,
        caller_user_id: str,
        target_user_id: str,
        is_active: bool,
    ) -> bool:
        """
        Activate or deactivate a user account.
        Enforces Last Administrator Protection, Self-Deactivation Barrier, and Store Manager Barrier.
        """
        with self.db.session_scope() as session:
            target = session.scalar(
                select(User).where(and_(User.company_id == company_id, User.id == target_user_id))
            )
            if not target:
                raise ValueError(f"User '{target_user_id}' not found.")

            # Store Manager Barrier: cannot deactivate an Administrator
            if caller_role.lower() == "store manager" and target.role_name.lower() == "administrator":
                raise PermissionError("Access Denied: Store Managers cannot deactivate Administrator accounts.")

            # Self-deactivation barrier: Administrators cannot deactivate their own account
            if not is_active and caller_user_id == target_user_id:
                raise ValueError("Operation rejected: Users cannot deactivate their own active account.")

            # Last Administrator Protection
            if not is_active and target.role_name == "Administrator":
                active_admin_count = session.scalar(
                    select(func.count(User.id)).where(
                        and_(
                            User.company_id == company_id,
                            User.role_name == "Administrator",
                            User.is_active == True,
                            User.id != target_user_id,
                        )
                    )
                ) or 0
                if active_admin_count == 0:
                    raise ValueError(
                        "Operation rejected: Cannot deactivate the last active Administrator. "
                        "Every company must retain at least one active Administrator."
                    )

            target.is_active = bool(is_active)
            target.updated_at = utc_now()

        # Invalidate active sessions immediately upon deactivation
        if not is_active:
            self.registry.revoke_user_sessions(company_id, target_user_id)

        return True

    def reset_password(
        self,
        company_id: str,
        caller_role: str,
        target_user_id: str,
        new_password: str,
    ) -> bool:
        """
        Reset user password.
        Enforces Store Manager Barrier and purges all active sessions for the user.
        """
        clean_pwd = str(new_password or "").strip()
        if not clean_pwd:
            raise ValueError("Password cannot be empty.")

        with self.db.session_scope() as session:
            target = session.scalar(
                select(User).where(and_(User.company_id == company_id, User.id == target_user_id))
            )
            if not target:
                raise ValueError(f"User '{target_user_id}' not found.")

            # Store Manager Barrier: cannot reset an Administrator password
            if caller_role.lower() == "store manager" and target.role_name.lower() == "administrator":
                raise PermissionError("Access Denied: Store Managers cannot reset Administrator passwords.")

            target.password_hash = hash_password(clean_pwd)
            target.updated_at = utc_now()

        # Revoke all active sessions for this user
        self.registry.revoke_user_sessions(company_id, target_user_id)
        return True
