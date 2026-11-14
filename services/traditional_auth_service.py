"""
Traditional Billing Authentication and Session Management Service.
Enforces strict multi-tenant isolation, fail-closed role verification,
bcrypt password hashing, and durable session tracking.
"""

import os
import secrets
import threading
import hashlib
import binascii
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

import bcrypt
from sqlalchemy import select, and_, func

from db.traditional_database import traditional_db_manager, TraditionalDatabaseManager
from db.traditional_models import Company, Branch, User, Role, ensure_utc
from core.logging_config import logger

RECOGNIZED_SYSTEM_ROLES = frozenset({"Administrator", "Store Manager", "Manager", "Cashier"})


def utc_now() -> datetime:
    """Current UTC timestamp."""
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with salt rounds = 12."""
    if not password:
        raise ValueError("Password cannot be empty.")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("ascii")


def verify_password(stored_hash: str, provided_password: str) -> bool:
    """
    Verify a password against stored hash.
    Strict fail-closed: empty password or empty hash is rejected.
    Supports bcrypt ($2b$, $2a$, $2y$) and legacy PBKDF2 (salt$hash) compatibility.
    """
    if not stored_hash or not provided_password:
        return False

    stored_str = stored_hash.strip()

    # 1. Bcrypt verification
    if stored_str.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(provided_password.encode("utf-8"), stored_str.encode("ascii"))
        except Exception as e:
            logger.warning(f"Bcrypt verification failed with exception: {e}")
            return False

    # 2. Legacy PBKDF2 verification (Stage 1 backward-compatibility fallback)
    if "$" in stored_str:
        try:
            parts = stored_str.split("$", 1)
            if len(parts) == 2:
                salt_hex, hash_hex = parts
                salt = binascii.unhexlify(salt_hex.encode("ascii"))
                dk = hashlib.pbkdf2_hmac("sha256", provided_password.encode("utf-8"), salt, 100000)
                return binascii.hexlify(dk).decode("ascii") == hash_hex
        except Exception as e:
            logger.warning(f"PBKDF2 fallback verification exception: {e}")
            return False

    return False


@dataclass
class TraditionalSession:
    token: str
    user_id: str
    company_id: str
    branch_id: str
    role_name: str
    username: str
    display_name: str
    created_at: datetime = field(default_factory=utc_now)
    last_activity: datetime = field(default_factory=utc_now)
    idle_timeout_seconds: int = 8 * 3600    # 8 hours idle timeout
    shift_limit_seconds: int = 24 * 3600    # 24 hours absolute limit

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        now_dt = ensure_utc(now) if now is not None else utc_now()
        created_dt = ensure_utc(self.created_at)
        last_dt = ensure_utc(self.last_activity)
        if (now_dt - created_dt).total_seconds() > self.shift_limit_seconds:
            return True
        if (now_dt - last_dt).total_seconds() > self.idle_timeout_seconds:
            return True
        return False


class TraditionalSessionRegistry:
    """Thread-safe in-memory session registry for Traditional Billing."""

    def __init__(self):
        self._sessions: Dict[str, TraditionalSession] = {}
        self._lock = threading.RLock()

    def create_session(
        self,
        user_id: str,
        company_id: str,
        branch_id: str,
        role_name: str,
        username: str,
        display_name: Optional[str] = None,
        idle_timeout_seconds: int = 8 * 3600,
        shift_limit_seconds: int = 24 * 3600,
    ) -> str:
        token = secrets.token_urlsafe(32)
        session = TraditionalSession(
            token=token,
            user_id=user_id,
            company_id=company_id,
            branch_id=branch_id,
            role_name=role_name,
            username=username,
            display_name=display_name or username,
            created_at=utc_now(),
            last_activity=utc_now(),
            idle_timeout_seconds=idle_timeout_seconds,
            shift_limit_seconds=shift_limit_seconds,
        )
        with self._lock:
            self._sessions[token] = session
        return token

    def get_session(self, token: str) -> Optional[TraditionalSession]:
        if not token:
            return None
        with self._lock:
            session = self._sessions.get(token)
            if not session:
                return None
            if session.is_expired():
                del self._sessions[token]
                return None
            # Update last activity timestamp
            session.last_activity = utc_now()
            return session

    def revoke_session(self, token: str) -> bool:
        with self._lock:
            return self._sessions.pop(token, None) is not None

    def revoke_user_sessions(self, company_id: str, user_id: str) -> int:
        revoked = 0
        with self._lock:
            tokens_to_remove = [
                token for token, s in self._sessions.items()
                if s.company_id == company_id and s.user_id == user_id
            ]
            for token in tokens_to_remove:
                del self._sessions[token]
                revoked += 1
        return revoked

    def cleanup_expired(self) -> int:
        now = utc_now()
        cleaned = 0
        with self._lock:
            tokens_to_remove = [
                token for token, s in self._sessions.items()
                if s.is_expired(now)
            ]
            for token in tokens_to_remove:
                del self._sessions[token]
                cleaned += 1
        return cleaned


# Global session registry singleton
session_registry = TraditionalSessionRegistry()


class TraditionalAuthService:
    """Service handling multi-tenant user authentication and sessions for Traditional Billing."""

    def __init__(
        self,
        db_manager: Optional[TraditionalDatabaseManager] = None,
        registry: Optional[TraditionalSessionRegistry] = None,
    ):
        self.db = db_manager or traditional_db_manager
        self.registry = registry or session_registry

    def authenticate(
        self,
        company_code: str,
        username: str,
        password: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Authenticate user credentials for a specific company.
        Strict fail-closed: validates active company, active user, bcrypt password,
        and recognized system role.
        """
        code = (company_code or "").strip().upper()
        uname = (username or "").strip().upper()
        pwd = (password or "").strip()

        if not code or not uname or not pwd:
            logger.warning("Auth rejected: missing company code, username, or password.")
            return None

        with self.db.session_scope() as session:
            # 1. Fetch company
            comp = session.scalars(
                select(Company).where(
                    and_(
                        func.upper(Company.code) == code,
                        Company.is_active == True,
                    )
                )
            ).first()

            if not comp:
                logger.warning(f"Auth failed: Company '{code}' not found or inactive.")
                return None

            # 2. Fetch user
            user = session.scalars(
                select(User).where(
                    and_(
                        User.company_id == comp.id,
                        func.upper(User.username) == uname,
                        User.is_active == True,
                    )
                )
            ).first()

            if not user:
                logger.warning(f"Auth failed: User '{uname}' not found or inactive in company '{code}'.")
                return None

            # 3. Verify password
            if not verify_password(user.password_hash, pwd):
                logger.warning(f"Auth failed: Invalid password for user '{uname}' in company '{code}'.")
                return None

            # 4. Strict role validation
            role_name = (user.role_name or "").strip()
            matched_role = next((r for r in RECOGNIZED_SYSTEM_ROLES if r.lower() == role_name.lower()), None)
            if not matched_role:
                logger.warning(f"Auth failed: User '{uname}' has unrecognized role '{role_name}'.")
                return None

            # 5. Fetch operational branch BR01
            branch = session.scalars(
                select(Branch).where(
                    and_(
                        Branch.company_id == comp.id,
                        Branch.code == "BR01",
                        Branch.is_active == True,
                    )
                )
            ).first()

            if not branch:
                # Auto-initialize default branch BR01 if not present
                branch = Branch(
                    company_id=comp.id,
                    code="BR01",
                    name="Main Branch",
                    is_active=True,
                )
                session.add(branch)
                session.flush()

            # 6. Issue session
            session_token = self.registry.create_session(
                user_id=user.id,
                company_id=comp.id,
                branch_id=branch.id,
                role_name=matched_role,
                username=user.username,
                display_name=user.full_name or user.username,
            )

            return {
                "success": True,
                "session_token": session_token,
                "company": {
                    "id": comp.id,
                    "code": comp.code,
                    "name": comp.name,
                    "fin_year": comp.fin_year,
                    "gstin": comp.gstin,
                    "state": comp.state,
                },
                "branch": {
                    "id": branch.id,
                    "code": branch.code,
                    "name": branch.name,
                },
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "displayName": user.full_name or user.username,
                    "role": matched_role,
                },
            }

    def create_user(
        self,
        company_id: str,
        username: str,
        password: str,
        role_name: str,
        full_name: Optional[str] = None,
    ) -> User:
        """Create a new user with bcrypt password hash."""
        clean_user = (username or "").strip().upper()
        if not clean_user:
            raise ValueError("Username cannot be empty.")

        matched_role = next((r for r in RECOGNIZED_SYSTEM_ROLES if r.lower() == role_name.strip().lower()), None)
        if not matched_role:
            raise ValueError(f"Role '{role_name}' is not a recognized system role.")

        pwd_hash = hash_password(password)

        with self.db.session_scope() as session:
            new_user = User(
                company_id=company_id,
                username=clean_user,
                password_hash=pwd_hash,
                role_name=matched_role,
                full_name=full_name,
                is_active=True,
            )
            session.add(new_user)
            session.flush()
            session.refresh(new_user)
            return new_user

    def change_password(
        self,
        company_id: str,
        user_id: str,
        old_password: str,
        new_password: str,
    ) -> bool:
        """Change password, hash with bcrypt, and revoke existing sessions."""
        with self.db.session_scope() as session:
            user = session.scalars(
                select(User).where(
                    and_(
                        User.id == user_id,
                        User.company_id == company_id,
                    )
                )
            ).first()

            if not user:
                return False

            if not verify_password(user.password_hash, old_password):
                return False

            user.password_hash = hash_password(new_password)
            user.updated_at = utc_now()

        # Invalidate active sessions
        self.registry.revoke_user_sessions(company_id, user_id)
        return True
