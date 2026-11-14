"""
Traditional Billing Customer & Account Master Service.
Manages Debtor/Creditor/General ledger accounts, tenant-scoped sequential code generation,
GSTIN & phone validation, and concurrency protection.
"""

import uuid
import re
import threading
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import select, and_, or_
from sqlalchemy.exc import IntegrityError

from db.traditional_database import traditional_db_manager, TraditionalDatabaseManager
from db.traditional_models import Account, utc_now
from core.logging_config import logger


def validate_gstin_format(gstin: Optional[str]) -> Optional[str]:
    """Validate 15-character Indian GSTIN format."""
    if not gstin or not str(gstin).strip():
        return None
    clean = str(gstin).strip().upper()
    # 2 digits state code + 10 alphanumeric PAN + 1 entity num + 1 'Z' + 1 checksum char
    if not re.match(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$", clean):
        raise ValueError(f"Invalid GSTIN format: '{clean}'. Expected 15-character GSTIN (e.g. 33AAAPL1234F1Z1).")
    return clean


def validate_phone_format(phone: Optional[str]) -> Optional[str]:
    """Validate 10-digit mobile/phone format."""
    if not phone or not str(phone).strip():
        return None
    clean = re.sub(r"[\s\-\+\(\)]", "", str(phone).strip())
    if len(clean) == 12 and clean.startswith("91"):
        clean = clean[2:]
    elif len(clean) == 11 and clean.startswith("0"):
        clean = clean[1:]

    if not clean.isdigit() or len(clean) != 10:
        raise ValueError(f"Invalid phone number: '{phone}'. Expected 10-digit mobile number.")
    return clean


def resolve_account_type_and_prefix(data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Determine internal account_type and auto-code prefix based on group or account_type.
    Returns: (account_type, prefix)
    """
    raw_type = str(data.get("account_type") or data.get("accountType") or "").strip()
    raw_group = str(data.get("account_group") or data.get("group") or "").strip()

    # 1. Match recognized explicit account types
    norm_type = raw_type.capitalize()
    if norm_type in ("Debtor", "Creditor", "Bank", "Cash", "Sales", "Purchase", "Both"):
        if norm_type == "Debtor":
            return "Debtor", "CUS-"
        elif norm_type == "Creditor":
            return "Creditor", "SUP-"
        elif norm_type == "Bank":
            return "Bank", "BNK-"
        elif norm_type == "Cash":
            return "Cash", "CSH-"
        elif norm_type == "Sales":
            return "Sales", "SAL-"
        elif norm_type == "Purchase":
            return "Purchase", "PUR-"
        elif norm_type == "Both":
            return "Both", "ACC-"

    # 2. Inspect account group name
    grp_lower = raw_group.lower()
    if "debtor" in grp_lower or "customer" in grp_lower:
        return "Debtor", "CUS-"
    elif "creditor" in grp_lower or "supplier" in grp_lower:
        return "Creditor", "SUP-"
    elif "both" in grp_lower:
        return "Both", "ACC-"
    elif "bank" in grp_lower:
        return "Bank", "BNK-"
    elif "cash" in grp_lower:
        return "Cash", "CSH-"
    elif "sales" in grp_lower:
        return "Sales", "SAL-"
    elif "purchase" in grp_lower:
        return "Purchase", "PUR-"
    elif raw_group:
        return raw_group, "ACC-"

    # Default to Debtor / Customer
    return "Debtor", "CUS-"


def _account_to_dict(acc: Account, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Serialize Account model to dictionary enriched with group and compatibility fields."""
    group_map = {
        "Debtor": "Sundry Debtors",
        "Creditor": "Sundry Creditors",
        "Both": "Both (Customer & Supplier)",
        "Bank": "Bank Accounts",
        "Cash": "Cash-in-hand",
        "Sales": "Sales Accounts",
        "Purchase": "Purchase Accounts",
    }
    grp = group_map.get(acc.account_type, acc.account_type)
    res = {
        "id": acc.id,
        "code": acc.code,
        "customer_code": acc.code,
        "customerCode": acc.code,
        "name": acc.name,
        "account_type": acc.account_type,
        "accountType": acc.account_type,
        "group": grp,
        "account_group": grp,
        "accountGroup": grp,
        "phone": acc.phone,
        "mobile": acc.phone,
        "email": acc.email,
        "address": acc.address,
        "gstin": acc.gstin,
        "state": acc.state,
        "isActive": acc.is_active,
        "is_active": acc.is_active,
        "createdAt": acc.created_at.isoformat() if acc.created_at else None,
        "created_at": acc.created_at.isoformat() if acc.created_at else None,
        "updatedAt": acc.updated_at.isoformat() if acc.updated_at else None,
        "updated_at": acc.updated_at.isoformat() if acc.updated_at else None,
    }
    if extra:
        for k in ("alias", "printName", "print_name", "opBal", "op_bal", "opType", "op_type", "customerCategory", "customer_category"):
            if k in extra:
                res[k] = extra[k]
    return res


class TraditionalCustomerService:
    def __init__(self, db_manager: Optional[TraditionalDatabaseManager] = None):
        self.db = db_manager or traditional_db_manager
        self._lock = threading.RLock()

    def _generate_next_code(self, session, company_id: str, prefix: str) -> str:
        """
        Generate next sequential unique account code for company with given prefix.
        Queries existing codes starting with prefix, extracts numeric sequence, and increments max.
        Example: CUS-000001, CUS-000002, etc.
        """
        existing_codes = session.scalars(
            select(Account.code).where(
                and_(
                    Account.company_id == company_id,
                    Account.code.like(f"{prefix}%"),
                )
            )
        ).all()

        max_seq = 0
        for c in existing_codes:
            if c and c.startswith(prefix):
                suffix = c[len(prefix):]
                if suffix.isdigit():
                    val = int(suffix)
                    if val > max_seq:
                        max_seq = val

        next_seq = max_seq + 1
        return f"{prefix}{next_seq:06d}"

    def list_customers(
        self,
        company_id: str,
        search_term: Optional[str] = None,
        active_only: bool = True,
        account_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List accounts for company. By default filters customers (Debtor, Both)."""
        with self.db.read_session_scope() as session:
            query = select(Account).where(Account.company_id == company_id)

            if account_type:
                at_upper = account_type.upper()
                if at_upper == "ALL":
                    pass  # No type filter
                elif at_upper == "DEBTOR":
                    query = query.where(Account.account_type.in_(["Debtor", "Both"]))
                elif at_upper == "CREDITOR":
                    query = query.where(Account.account_type.in_(["Creditor", "Both"]))
                else:
                    query = query.where(Account.account_type == account_type)
            else:
                # Default: customers (Debtor and Both)
                query = query.where(Account.account_type.in_(["Debtor", "Both"]))

            if active_only:
                query = query.where(Account.is_active == True)

            if search_term and search_term.strip():
                st = f"%{search_term.strip()}%"
                query = query.where(
                    or_(
                        Account.code.ilike(st),
                        Account.name.ilike(st),
                        Account.phone.ilike(st),
                        Account.gstin.ilike(st),
                    )
                )

            query = query.order_by(Account.name.asc())
            accounts = session.scalars(query).all()
            return [_account_to_dict(a) for a in accounts]

    def list_accounts(
        self,
        company_id: str,
        search_term: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """List all accounts for company across all types (Debtor, Creditor, Bank, Cash, etc.)."""
        return self.list_customers(
            company_id=company_id,
            search_term=search_term,
            active_only=active_only,
            account_type="ALL",
        )

    def get_customer(self, company_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve single customer or account profile."""
        with self.db.read_session_scope() as session:
            cust = session.scalar(
                select(Account).where(
                    and_(
                        Account.company_id == company_id,
                        Account.id == customer_id,
                    )
                )
            )
            if not cust:
                return None
            return _account_to_dict(cust)

    def save_customer(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create or update customer/account with validation and automatic unique code generation.
        - Automatically generates unique readable code (e.g. CUS-000001, SUP-000001) if not provided.
        - Retains original code when editing an existing customer.
        - Enforces tenant isolation and collision-free concurrency protection.
        - Preserves customer classification, supplier workflows, and ledger accounts.
        """
        name = str(data.get("name") or "").strip()
        account_type, prefix = resolve_account_type_and_prefix(data)

        if not name:
            if prefix == "CUS-" or account_type == "Debtor":
                raise ValueError("Customer name is required.")
            raise ValueError("Account name is required.")

        phone = validate_phone_format(data.get("phone") or data.get("mobile"))
        email = str(data.get("email") or "").strip() or None
        address = str(data.get("address") or "").strip() or None
        gstin = validate_gstin_format(data.get("gstin") or data.get("taxNo"))
        state = str(data.get("state") or "Tamilnadu").strip()

        customer_id = data.get("id")
        raw_code = str(data.get("code") or data.get("customer_code") or "").strip().upper()

        if customer_id:
            # --- MODIFY EXISTING ACCOUNT ---
            with self.db.session_scope() as session:
                cust = session.scalar(
                    select(Account).where(
                        and_(
                            Account.company_id == company_id,
                            Account.id == customer_id,
                        )
                    )
                )
                if not cust:
                    raise ValueError(f"Account '{customer_id}' not found.")

                if raw_code:
                    code = raw_code
                    code_conflict = session.scalar(
                        select(Account.id).where(
                            and_(
                                Account.company_id == company_id,
                                Account.code == code,
                                Account.id != customer_id,
                            )
                        )
                    )
                    if code_conflict:
                        raise ValueError(f"Account code '{code}' is already assigned to another account.")
                else:
                    # Retain existing code! Never re-generate code on edit
                    code = cust.code

                cust.code = code
                cust.name = name
                cust.account_type = account_type
                cust.phone = phone
                cust.email = email
                cust.address = address
                cust.gstin = gstin
                cust.state = state
                cust.updated_at = utc_now()
                session.flush()
                return _account_to_dict(cust, extra=data)

        # --- CREATE NEW ACCOUNT ---
        if raw_code:
            # Explicit code specified: validate uniqueness
            code = raw_code
            with self.db.session_scope() as session:
                code_conflict = session.scalar(
                    select(Account.id).where(
                        and_(
                            Account.company_id == company_id,
                            Account.code == code,
                        )
                    )
                )
                if code_conflict:
                    entity_label = "Customer" if prefix == "CUS-" else "Account"
                    raise ValueError(f"{entity_label} code '{code}' already exists.")

                cust = Account(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    code=code,
                    name=name,
                    account_type=account_type,
                    phone=phone,
                    email=email,
                    address=address,
                    gstin=gstin,
                    state=state,
                    is_active=True,
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                session.add(cust)
                session.flush()
                return _account_to_dict(cust, extra=data)

        # Automatic code generation with concurrency protection (lock + collision retry)
        with self._lock:
            max_retries = 10
            for attempt in range(max_retries):
                try:
                    with self.db.session_scope() as session:
                        code = self._generate_next_code(session, company_id, prefix)
                        cust = Account(
                            id=str(uuid.uuid4()),
                            company_id=company_id,
                            code=code,
                            name=name,
                            account_type=account_type,
                            phone=phone,
                            email=email,
                            address=address,
                            gstin=gstin,
                            state=state,
                            is_active=True,
                            created_at=utc_now(),
                            updated_at=utc_now(),
                        )
                        session.add(cust)
                        session.flush()
                        return _account_to_dict(cust, extra=data)
                except IntegrityError as e:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Collision on auto-generated code '{code}' for company '{company_id}', "
                            f"retrying ({attempt + 1}/{max_retries}): {e}"
                        )
                        continue
                    raise

    def set_customer_active(self, company_id: str, customer_id: str, is_active: bool) -> bool:
        """Toggle customer active status."""
        with self.db.session_scope() as session:
            cust = session.scalar(
                select(Account).where(
                    and_(
                        Account.company_id == company_id,
                        Account.id == customer_id,
                    )
                )
            )
            if not cust:
                raise ValueError(f"Account '{customer_id}' not found.")
            cust.is_active = bool(is_active)
            cust.updated_at = utc_now()
        return True
