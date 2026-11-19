"""
Traditional Billing Double-Entry Accounting Service.
Anti-Matrix Billing V2 — Core Backend Architecture.

Provides:
- Chart of Accounts with strict 5-nature hierarchy (ASSET, LIABILITY, EQUITY, INCOME, EXPENSE)
- Hierarchical Account Groups and Account Group Mappings
- Double-entry Journal Entry posting and atomic verification
- Idempotency deduplication and concurrency controls
- Period controls (closure, reopening, posting guards)
- Journal Reversal mechanics (immutable ledger audit trail)
- Standard Financial Reports:
    * General Ledger
    * Day Book
    * Trial Balance
    * Profit and Loss Statement
    * Balance Sheet
    * Cash Book & Bank Book
    * Accounts Receivable & Accounts Payable Aging/Outstandings
- Integration helper blueprints for Sales, Purchase, Returns, Payments, and Receipts
"""

import uuid
import threading
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, List, Union, Tuple
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import Session

from db.traditional_database import traditional_db_manager, TraditionalDatabaseManager
from db.traditional_models import (
    Company,
    Branch,
    User,
    Account,
    AccountGroup,
    AccountGroupMapping,
    AccountingPeriod,
    JournalEntry,
    JournalEntryLine,
    FinancialYearClosing,
    AuditLog,
    utc_now,
)
from core.logging_config import logger


# ==============================================================================
# Precision Helpers & Custom Exceptions
# ==============================================================================

def round_money(val: Union[Decimal, float, int, str]) -> Decimal:
    """Quantizes monetary amount to 2 decimal places using ROUND_HALF_UP."""
    if val is None:
        return Decimal("0.00")
    if not isinstance(val, Decimal):
        val = Decimal(str(val).strip() or "0")
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class TraditionalAccountingError(Exception):
    """Base exception for Traditional Billing accounting errors."""
    pass


class UnbalancedJournalError(TraditionalAccountingError):
    """Raised when total debits do not equal total credits."""
    pass


class InsufficientJournalLinesError(TraditionalAccountingError):
    """Raised when a journal entry has fewer than 2 valid lines."""
    pass


class InvalidJournalAmountError(TraditionalAccountingError):
    """Raised when a debit or credit amount is negative, zero on both sides, or both non-zero."""
    pass


class ClosedPeriodError(TraditionalAccountingError):
    """Raised when attempting to post into a closed accounting period."""
    pass


class AccountNotFoundError(TraditionalAccountingError):
    """Raised when an account is not found or violates tenant isolation."""
    pass


class DuplicateJournalError(TraditionalAccountingError):
    """Raised when a voucher number or idempotency key already exists."""
    pass


class JournalReversalError(TraditionalAccountingError):
    """Raised when an invalid reversal operation is attempted."""
    pass


class ImmutableJournalError(TraditionalAccountingError):
    """Raised when attempting to modify or delete a posted journal."""
    pass


class FinancialYearClosedError(TraditionalAccountingError):
    """Raised when an operation is attempted on an already closed financial year."""
    pass


class UnauthorizedAccountingActionError(TraditionalAccountingError, PermissionError):
    """Raised when a sensitive accounting action (e.g. opening balances, closing FY) lacks explicit authorization."""
    pass


# ==============================================================================
# Standard Account Groups Definition
# ==============================================================================

STANDARD_ACCOUNT_GROUPS = [
    # Top-Level Natures:
    # 1. ASSET
    {"code": "GRP_CURR_ASSETS", "name": "Current Assets", "nature": "ASSET", "parent_code": None},
    {"code": "GRP_CASH", "name": "Cash-in-Hand", "nature": "ASSET", "parent_code": "GRP_CURR_ASSETS"},
    {"code": "GRP_BANK", "name": "Bank Accounts", "nature": "ASSET", "parent_code": "GRP_CURR_ASSETS"},
    {"code": "GRP_SUNDRY_DEBTORS", "name": "Sundry Debtors", "nature": "ASSET", "parent_code": "GRP_CURR_ASSETS"},
    {"code": "GRP_STOCK", "name": "Stock-in-Hand", "nature": "ASSET", "parent_code": "GRP_CURR_ASSETS"},
    {"code": "GRP_INPUT_GST", "name": "Duties & Taxes (Input GST)", "nature": "ASSET", "parent_code": "GRP_CURR_ASSETS"},
    {"code": "GRP_LOANS_ADV", "name": "Loans & Advances (Asset)", "nature": "ASSET", "parent_code": "GRP_CURR_ASSETS"},
    {"code": "GRP_FIXED_ASSETS", "name": "Fixed Assets", "nature": "ASSET", "parent_code": None},

    # 2. LIABILITY
    {"code": "GRP_CURR_LIAB", "name": "Current Liabilities", "nature": "LIABILITY", "parent_code": None},
    {"code": "GRP_SUNDRY_CREDITORS", "name": "Sundry Creditors", "nature": "LIABILITY", "parent_code": "GRP_CURR_LIAB"},
    {"code": "GRP_OUTPUT_GST", "name": "Duties & Taxes (Output GST)", "nature": "LIABILITY", "parent_code": "GRP_CURR_LIAB"},
    {"code": "GRP_DUTIES_TAXES", "name": "Duties & Taxes (Payable)", "nature": "LIABILITY", "parent_code": "GRP_CURR_LIAB"},
    {"code": "GRP_PROVISIONS", "name": "Provisions", "nature": "LIABILITY", "parent_code": "GRP_CURR_LIAB"},
    {"code": "GRP_LOANS_LIAB", "name": "Loans (Liability)", "nature": "LIABILITY", "parent_code": None},
    {"code": "GRP_BANK_OD", "name": "Bank OD / CC Accounts", "nature": "LIABILITY", "parent_code": "GRP_LOANS_LIAB"},

    # 3. EQUITY
    {"code": "GRP_CAPITAL", "name": "Capital Account", "nature": "EQUITY", "parent_code": None},
    {"code": "GRP_RESERVES", "name": "Reserves & Surplus", "nature": "EQUITY", "parent_code": None},
    {"code": "GRP_RETAINED_EARNINGS", "name": "Retained Earnings", "nature": "EQUITY", "parent_code": "GRP_RESERVES"},

    # 4. INCOME
    {"code": "GRP_SALES", "name": "Sales Accounts", "nature": "INCOME", "parent_code": None},
    {"code": "GRP_DIRECT_INCOME", "name": "Direct Income", "nature": "INCOME", "parent_code": None},
    {"code": "GRP_INDIRECT_INCOME", "name": "Indirect Income", "nature": "INCOME", "parent_code": None},

    # 5. EXPENSE
    {"code": "GRP_PURCHASE", "name": "Purchase Accounts", "nature": "EXPENSE", "parent_code": None},
    {"code": "GRP_DIRECT_EXPENSES", "name": "Direct Expenses", "nature": "EXPENSE", "parent_code": None},
    {"code": "GRP_INDIRECT_EXPENSES", "name": "Indirect Expenses", "nature": "EXPENSE", "parent_code": None},
]


# ==============================================================================
# Traditional Accounting Service Implementation
# ==============================================================================

class TraditionalAccountingService:
    def __init__(self, db_manager: Optional[TraditionalDatabaseManager] = None):
        self.db = db_manager or traditional_db_manager
        self._lock = threading.RLock()

    # --------------------------------------------------------------------------
    # 1. Chart of Accounts & Account Groups
    # --------------------------------------------------------------------------

    def ensure_standard_account_groups(self, company_id: str, session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """
        Seeds standard account groups for a company if they do not exist yet.
        Enforces tenant isolation and builds hierarchical parent relationships.
        """
        if not company_id:
            raise ValueError("company_id is required.")

        def _execute(sess: Session):
            existing_groups = sess.scalars(
                select(AccountGroup).where(AccountGroup.company_id == company_id)
            ).all()
            by_code = {g.code: g for g in existing_groups}

            # 1. First pass: Create groups without parent links
            for item in STANDARD_ACCOUNT_GROUPS:
                code = item["code"]
                if code not in by_code:
                    grp = AccountGroup(
                        id=str(uuid.uuid4()),
                        company_id=company_id,
                        code=code,
                        name=item["name"],
                        nature=item["nature"],
                        is_system=True,
                        created_at=utc_now(),
                    )
                    sess.add(grp)
                    by_code[code] = grp

            sess.flush()

            # 2. Second pass: Wire parent links
            for item in STANDARD_ACCOUNT_GROUPS:
                code = item["code"]
                parent_code = item.get("parent_code")
                if parent_code and parent_code in by_code:
                    by_code[code].parent_group_id = by_code[parent_code].id

            sess.flush()
            return [
                {
                    "id": g.id,
                    "code": g.code,
                    "name": g.name,
                    "nature": g.nature,
                    "parent_group_id": g.parent_group_id,
                    "is_system": g.is_system,
                }
                for g in by_code.values()
            ]

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)


    def ensure_standard_accounts(self, company_id: str, session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """
        Ensures standard core ledger accounts (Cash, Sales, Purchases, GST, Round-Off)
        exist for the company and are mapped to proper account groups via AccountGroupMapping.
        """
        if not company_id:
            raise ValueError("company_id is required.")

        def _execute(sess: Session):
            self.ensure_standard_account_groups(company_id, session=sess)
            groups = sess.scalars(select(AccountGroup).where(AccountGroup.company_id == company_id)).all()
            grp_by_code = {g.code: g for g in groups}

            core_accounts = [
                ("CASH", "Cash in Hand", "Cash", "ASSET", "GRP_CASH"),
                ("SALES", "General Sales", "Sales", "INCOME", "GRP_SALES"),
                ("PURCHASE", "General Purchase", "Purchase", "EXPENSE", "GRP_PURCHASE"),
                ("INPUT_CGST", "Input CGST", "Asset", "ASSET", "GRP_INPUT_GST"),
                ("INPUT_SGST", "Input SGST", "Asset", "ASSET", "GRP_INPUT_GST"),
                ("INPUT_IGST", "Input IGST", "Asset", "ASSET", "GRP_INPUT_GST"),
                ("OUTPUT_CGST", "Output CGST", "Liability", "LIABILITY", "GRP_OUTPUT_GST"),
                ("OUTPUT_SGST", "Output SGST", "Liability", "LIABILITY", "GRP_OUTPUT_GST"),
                ("OUTPUT_IGST", "Output IGST", "Liability", "LIABILITY", "GRP_OUTPUT_GST"),
                ("ROUND_OFF", "Round Off Account", "Expense", "EXPENSE", "GRP_INDIRECT_EXPENSES"),
                ("STOCK_IN_HAND", "Stock-in-Hand", "Asset", "ASSET", "GRP_STOCK"),
                ("RETAINED_EARNINGS", "Retained Earnings", "Equity", "EQUITY", "GRP_RETAINED_EARNINGS"),
                ("OPENING_BALANCE_EQUITY", "Opening Balance Equity", "Equity", "EQUITY", "GRP_RESERVES"),
            ]

            existing_accs = sess.scalars(select(Account).where(Account.company_id == company_id)).all()
            acc_by_code = {a.code: a for a in existing_accs}

            results = []
            for code, name, acc_type, nature, grp_code in core_accounts:
                grp = grp_by_code.get(grp_code)
                grp_id = grp.id if grp else None

                if code in acc_by_code:
                    acc = acc_by_code[code]
                else:
                    acc = Account(
                        id=str(uuid.uuid4()),
                        company_id=company_id,
                        code=code,
                        name=name,
                        account_type=acc_type,
                        is_active=True,
                        created_at=utc_now(),
                    )
                    sess.add(acc)
                    acc_by_code[code] = acc

                # Ensure AccountGroupMapping
                mapping = sess.scalar(
                    select(AccountGroupMapping).where(
                        and_(AccountGroupMapping.company_id == company_id, AccountGroupMapping.account_id == acc.id)
                    )
                )
                if not mapping and grp_id:
                    mapping = AccountGroupMapping(
                        id=str(uuid.uuid4()),
                        company_id=company_id,
                        account_id=acc.id,
                        group_id=grp_id,
                        account_nature=nature,
                        opening_balance=Decimal("0.00"),
                        opening_balance_type="DR",
                        created_at=utc_now(),
                        updated_at=utc_now(),
                    )
                    sess.add(mapping)

                results.append({
                    "id": acc.id,
                    "code": acc.code,
                    "name": acc.name,
                    "account_type": acc.account_type,
                    "account_nature": nature,
                    "group_id": grp_id,
                })

            # Also ensure mappings for any pre-existing customer/supplier accounts
            for acc in existing_accs:
                mapping = sess.scalar(
                    select(AccountGroupMapping).where(
                        and_(AccountGroupMapping.company_id == company_id, AccountGroupMapping.account_id == acc.id)
                    )
                )
                if not mapping:
                    at = str(acc.account_type or "").capitalize()
                    grp_code = None
                    nature = "ASSET"
                    if at in ("Debtor", "Both"):
                        grp_code = "GRP_SUNDRY_DEBTORS"
                        nature = "ASSET"
                    elif at == "Creditor":
                        grp_code = "GRP_SUNDRY_CREDITORS"
                        nature = "LIABILITY"
                    elif at == "Bank":
                        grp_code = "GRP_BANK"
                        nature = "ASSET"
                    elif at == "Cash":
                        grp_code = "GRP_CASH"
                        nature = "ASSET"

                    if grp_code and grp_code in grp_by_code:
                        grp = grp_by_code[grp_code]
                        m = AccountGroupMapping(
                            id=str(uuid.uuid4()),
                            company_id=company_id,
                            account_id=acc.id,
                            group_id=grp.id,
                            account_nature=nature,
                            opening_balance=Decimal("0.00"),
                            opening_balance_type="DR",
                            created_at=utc_now(),
                            updated_at=utc_now(),
                        )
                        sess.add(m)

            sess.flush()
            return results

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)


    def create_account_group(
        self,
        company_id: str,
        code: str,
        name: str,
        nature: str,
        parent_group_code: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Creates a custom user-defined account group under the standard 5 natures."""
        nature_clean = str(nature).strip().upper()
        if nature_clean not in ("ASSET", "LIABILITY", "EQUITY", "INCOME", "EXPENSE"):
            raise ValueError(f"Invalid nature '{nature}'. Expected ASSET, LIABILITY, EQUITY, INCOME, or EXPENSE.")

        def _execute(sess: Session):
            clean_code = str(code).strip().upper()
            clean_name = str(name).strip()
            if not clean_code or not clean_name:
                raise ValueError("Group code and name are required.")

            parent_id = None
            if parent_group_code:
                parent = sess.scalar(
                    select(AccountGroup).where(
                        and_(AccountGroup.company_id == company_id, AccountGroup.code == parent_group_code.strip().upper())
                    )
                )
                if not parent:
                    raise ValueError(f"Parent group '{parent_group_code}' not found.")
                parent_id = parent.id

            grp = AccountGroup(
                id=str(uuid.uuid4()),
                company_id=company_id,
                code=clean_code,
                name=clean_name,
                nature=nature_clean,
                parent_group_id=parent_id,
                is_system=False,
                created_at=utc_now(),
            )
            sess.add(grp)
            sess.flush()
            return {
                "id": grp.id,
                "code": grp.code,
                "name": grp.name,
                "nature": grp.nature,
                "parent_group_id": grp.parent_group_id,
            }

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)


    def create_account(
        self,
        company_id: str,
        code: str,
        name: str,
        group_code: str,
        account_type: Optional[str] = None,
        opening_balance: Union[Decimal, float, int, str] = Decimal("0.00"),
        opening_balance_type: str = "DR",
        phone: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
        gstin: Optional[str] = None,
        state: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Creates a ledger account linked to a specific account group and nature."""
        clean_code = str(code).strip().upper()
        clean_name = str(name).strip()
        op_bal = round_money(opening_balance)
        op_type = str(opening_balance_type).strip().upper()
        if op_type not in ("DR", "CR"):
            raise ValueError("opening_balance_type must be 'DR' or 'CR'.")

        def _execute(sess: Session):
            self.ensure_standard_account_groups(company_id, session=sess)
            grp = sess.scalar(
                select(AccountGroup).where(
                    and_(AccountGroup.company_id == company_id, AccountGroup.code == group_code.strip().upper())
                )
            )
            if not grp:
                raise ValueError(f"AccountGroup '{group_code}' not found for company.")

            acc = Account(
                id=str(uuid.uuid4()),
                company_id=company_id,
                code=clean_code,
                name=clean_name,
                account_type=account_type or grp.name,
                phone=phone,
                email=email,
                address=address,
                gstin=gstin,
                state=state,
                is_active=True,
                created_at=utc_now(),
            )
            sess.add(acc)

            mapping = AccountGroupMapping(
                id=str(uuid.uuid4()),
                company_id=company_id,
                account_id=acc.id,
                group_id=grp.id,
                account_nature=grp.nature,
                opening_balance=op_bal,
                opening_balance_type=op_type,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            sess.add(mapping)
            sess.flush()

            initial_balance = op_bal if op_type == "DR" else -op_bal
            return {
                "id": acc.id,
                "code": acc.code,
                "name": acc.name,
                "account_type": acc.account_type,
                "account_nature": grp.nature,
                "group_id": grp.id,
                "group_name": grp.name,
                "opening_balance": str(op_bal),
                "opening_balance_type": op_type,
                "current_balance": str(op_bal),
            }

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)


    def get_chart_of_accounts(self, company_id: str, session: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Returns full structured Chart of Accounts grouped by the 5 fundamental natures."""
        def _execute(sess: Session):
            self.ensure_standard_accounts(company_id, session=sess)
            accs = sess.scalars(
                select(Account).where(
                    and_(Account.company_id == company_id, Account.is_active == True)
                ).order_by(Account.code.asc())
            ).all()

            mappings = sess.scalars(
                select(AccountGroupMapping).where(AccountGroupMapping.company_id == company_id)
            ).all()
            map_by_acc = {m.account_id: m for m in mappings}

            groups = sess.scalars(
                select(AccountGroup).where(AccountGroup.company_id == company_id)
            ).all()
            grp_map = {g.id: g for g in groups}

            # Pre-aggregate journal balances per account
            bal_q = (
                select(
                    JournalEntryLine.account_id,
                    func.coalesce(func.sum(JournalEntryLine.debit), 0).label("tot_deb"),
                    func.coalesce(func.sum(JournalEntryLine.credit), 0).label("tot_cred")
                )
                .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_id)
                .where(
                    and_(
                        JournalEntry.company_id == company_id,
                        JournalEntry.status.in_(["POSTED", "REVERSED"]),
                    )
                )
                .group_by(JournalEntryLine.account_id)
            )
            ledger_totals = {r.account_id: (round_money(r.tot_deb), round_money(r.tot_cred)) for r in sess.execute(bal_q)}

            # Check which accounts have posted OPENING journals
            opening_acc_ids = set(
                sess.scalars(
                    select(JournalEntryLine.account_id)
                    .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_id)
                    .where(
                        and_(
                            JournalEntry.company_id == company_id,
                            JournalEntry.voucher_type == "OPENING",
                            JournalEntry.status == "POSTED",
                        )
                    )
                ).all()
            )

            result = []
            for a in accs:
                m = map_by_acc.get(a.id)
                grp = grp_map.get(m.group_id) if m else None
                nature = m.account_nature if m else (grp.nature if grp else "ASSET")

                # If account has a posted OPENING journal entry, its opening balance is
                # already captured in ledger_totals (deb, cred) as an authoritative journal.
                # Base op is set to 0.00 for net balance calculation to prevent double-counting.
                if a.id in opening_acc_ids:
                    base_op_calc = Decimal("0.00")
                else:
                    base_op_calc = round_money(m.opening_balance if m else Decimal("0.00"))
                base_op_display = round_money(m.opening_balance if m else Decimal("0.00"))
                op_type = m.opening_balance_type if m else "DR"
                net_op = base_op_calc if op_type == "DR" else -base_op_calc

                deb, cred = ledger_totals.get(a.id, (Decimal("0.00"), Decimal("0.00")))
                net = net_op + (deb - cred)

                if nature in ("ASSET", "EXPENSE"):
                    cur_bal = net
                else:
                    cur_bal = -net

                result.append({
                    "id": a.id,
                    "code": a.code,
                    "name": a.name,
                    "account_type": a.account_type,
                    "nature": nature,
                    "group_code": grp.code if grp else None,
                    "group_name": grp.name if grp else None,
                    "opening_balance": str(base_op_display),
                    "opening_balance_type": op_type,
                    "current_balance": str(round_money(cur_bal)),
                    "gstin": a.gstin,
                    "state": a.state,
                })
            return result

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    # --------------------------------------------------------------------------
    # 2. Financial Year & Accounting Period Controls
    # --------------------------------------------------------------------------

    @staticmethod
    def derive_financial_year(vch_date_str: Optional[str] = None, fallback_fy: Optional[str] = None) -> str:
        """Derives Indian Financial Year (Apr 1 - Mar 31) string: e.g. '2026-2027'."""
        if vch_date_str:
            try:
                parts = str(vch_date_str).strip().split("-")
                if len(parts) == 3:
                    if len(parts[0]) == 4:  # YYYY-MM-DD
                        yr, mo = int(parts[0]), int(parts[1])
                    else:  # DD-MM-YYYY
                        yr, mo = int(parts[2]), int(parts[1])
                    if 1 <= mo <= 12 and 1900 <= yr <= 2100:
                        if mo >= 4:
                            return f"{yr}-{yr+1}"
                        else:
                            return f"{yr-1}-{yr}"
            except Exception:
                pass

        if fallback_fy and len(str(fallback_fy).strip()) >= 4:
            return str(fallback_fy).strip()

        now = utc_now()
        if now.month >= 4:
            return f"{now.year}-{now.year+1}"
        return f"{now.year-1}-{now.year}"

    def create_accounting_period(
        self,
        company_id: str,
        financial_year: str,
        period_name: str,
        start_date: str,
        end_date: str,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Creates an accounting period control block."""
        def _execute(sess: Session):
            if start_date > end_date:
                raise ValueError(f"start_date ({start_date}) cannot be greater than end_date ({end_date}).")

            existing = sess.scalar(
                select(AccountingPeriod).where(
                    and_(
                        AccountingPeriod.company_id == company_id,
                        AccountingPeriod.financial_year == financial_year,
                        AccountingPeriod.period_name == period_name,
                    )
                )
            )
            if existing:
                raise ValueError(f"Period '{period_name}' already exists for financial year '{financial_year}'.")

            period = AccountingPeriod(
                id=str(uuid.uuid4()),
                company_id=company_id,
                financial_year=financial_year,
                period_name=period_name,
                start_date=start_date,
                end_date=end_date,
                is_closed=False,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            sess.add(period)
            sess.flush()
            return {
                "id": period.id,
                "financial_year": period.financial_year,
                "period_name": period.period_name,
                "start_date": period.start_date,
                "end_date": period.end_date,
                "is_closed": period.is_closed,
            }

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)


    def close_accounting_period(
        self,
        company_id: str,
        period_id_or_name: str,
        user_id: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Closes an accounting period to permanently reject subsequent journal postings."""
        def _execute(sess: Session):
            period = sess.scalar(
                select(AccountingPeriod).where(
                    and_(
                        AccountingPeriod.company_id == company_id,
                        or_(AccountingPeriod.id == period_id_or_name, AccountingPeriod.period_name == period_id_or_name)
                    )
                )
            )
            if not period:
                raise ValueError(f"AccountingPeriod '{period_id_or_name}' not found.")

            period.is_closed = True
            period.closed_at = utc_now()
            period.closed_by = user_id
            period.updated_at = utc_now()
            sess.flush()
            return {
                "id": period.id,
                "period_name": period.period_name,
                "is_closed": period.is_closed,
                "closed_at": period.closed_at.isoformat() if period.closed_at else None,
            }

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)


    def reopen_accounting_period(
        self,
        company_id: str,
        period_id_or_name: str,
        user_id: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Reopens a previously closed accounting period (authorized operations only)."""
        def _execute(sess: Session):
            period = sess.scalar(
                select(AccountingPeriod).where(
                    and_(
                        AccountingPeriod.company_id == company_id,
                        or_(AccountingPeriod.id == period_id_or_name, AccountingPeriod.period_name == period_id_or_name)
                    )
                )
            )
            if not period:
                raise ValueError(f"AccountingPeriod '{period_id_or_name}' not found.")

            period.is_closed = False
            period.closed_at = None
            period.closed_by = None
            period.updated_at = utc_now()
            sess.flush()
            return {
                "id": period.id,
                "period_name": period.period_name,
                "is_closed": period.is_closed,
            }

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)


    def validate_period_is_open(self, company_id: str, voucher_date: str, session: Session) -> None:
        """
        Validates that voucher_date does not fall into any closed accounting period for the company.
        Raises ClosedPeriodError if the target date is closed.
        """
        closed_period = session.scalar(
            select(AccountingPeriod).where(
                and_(
                    AccountingPeriod.company_id == company_id,
                    AccountingPeriod.is_closed == True,
                    AccountingPeriod.start_date <= voucher_date,
                    AccountingPeriod.end_date >= voucher_date,
                )
            )
        )
        if closed_period:
            raise ClosedPeriodError(
                f"Cannot post journal on date '{voucher_date}': Accounting Period '{closed_period.period_name}' "
                f"({closed_period.start_date} to {closed_period.end_date}) is CLOSED."
            )

    # --------------------------------------------------------------------------
    # 3. Double-Entry Journal Posting Engine
    # --------------------------------------------------------------------------

    def post_journal_entry(
        self,
        company_id: str,
        branch_id: str,
        voucher_type: str,
        voucher_date: str,
        lines: List[Dict[str, Any]],
        voucher_number: Optional[str] = None,
        narration: Optional[str] = None,
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        financial_year: Optional[str] = None,
        posted_by: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Posts a balanced, double-entry journal entry atomically.
        """
        if not company_id or not branch_id:
            raise ValueError("company_id and branch_id are required.")
        if not voucher_type or not voucher_date:
            raise ValueError("voucher_type and voucher_date are required.")
        if not lines or len(lines) < 2:
            raise InsufficientJournalLinesError(
                f"Every journal entry must contain at least 2 lines. Received {len(lines) if lines else 0}."
            )

        def _execute(sess: Session):
            # 1. Idempotency Deduplication Guard
            if idempotency_key:
                clean_key = str(idempotency_key).strip()
                existing = sess.scalar(
                    select(JournalEntry).where(
                        and_(JournalEntry.company_id == company_id, JournalEntry.idempotency_key == clean_key)
                    )
                )
                if existing:
                    logger.info(f"Duplicate journal posting ignored via idempotency_key '{clean_key}'.")
                    return self._journal_to_dict(existing)

            # 2. Company & Branch Context Validation
            company = sess.scalar(select(Company).where(Company.id == company_id))
            if not company:
                raise ValueError(f"Company '{company_id}' not found.")
            branch = sess.scalar(
                select(Branch).where(and_(Branch.company_id == company_id, Branch.id == branch_id))
            )
            if not branch:
                raise ValueError(f"Branch '{branch_id}' not found for company '{company_id}'.")

            # 3. Closed Period Validation
            self.validate_period_is_open(company_id, voucher_date, session=sess)

            # 4. Financial Year Resolution
            fy = financial_year or self.derive_financial_year(voucher_date, fallback_fy=company.fin_year)

            # 5. Line Processing & Balance Summation
            total_debit = Decimal("0.00")
            total_credit = Decimal("0.00")
            processed_lines: List[Dict[str, Any]] = []

            # Pre-load accounts referenced in lines
            account_ids = set()
            for idx, raw_line in enumerate(lines, start=1):
                aid = str(raw_line.get("account_id") or "").strip()
                if not aid:
                    raise AccountNotFoundError(f"Line {idx} is missing account_id.")
                account_ids.add(aid)

            acc_records = sess.scalars(
                select(Account).where(and_(Account.company_id == company_id, Account.id.in_(account_ids)))
            ).all()
            acc_map = {a.id: a for a in acc_records}

            for idx, raw_line in enumerate(lines, start=1):
                aid = str(raw_line.get("account_id") or "").strip()
                acc = acc_map.get(aid)
                if not acc:
                    raise AccountNotFoundError(
                        f"Line {idx}: Account '{aid}' not found or does not belong to company '{company_id}'."
                    )

                debit = round_money(raw_line.get("debit", 0))
                credit = round_money(raw_line.get("credit", 0))

                if debit < Decimal("0.00") or credit < Decimal("0.00"):
                    raise InvalidJournalAmountError(
                        f"Line {idx}: Debit ({debit}) and Credit ({credit}) must be non-negative."
                    )
                if debit > Decimal("0.00") and credit > Decimal("0.00"):
                    raise InvalidJournalAmountError(
                        f"Line {idx}: A single line cannot contain both Debit ({debit}) and Credit ({credit}) greater than zero."
                    )
                if debit == Decimal("0.00") and credit == Decimal("0.00"):
                    raise InvalidJournalAmountError(
                        f"Line {idx}: Line must contain either a non-zero Debit or Credit amount."
                    )

                total_debit += debit
                total_credit += credit

                processed_lines.append({
                    "line_number": idx,
                    "account_id": acc.id,
                    "account": acc,
                    "debit": debit,
                    "credit": credit,
                    "narration": raw_line.get("narration"),
                    "party_type": raw_line.get("party_type"),
                    "party_id": raw_line.get("party_id"),
                })

            # 6. Double-Entry Invariant Check
            if total_debit != total_credit:
                raise UnbalancedJournalError(
                    f"Journal is unbalanced: Total Debits ({total_debit}) != Total Credits ({total_credit}). Difference: {abs(total_debit - total_credit)}."
                )
            if total_debit <= Decimal("0.00"):
                raise InvalidJournalAmountError("Total journal amount must be strictly greater than zero.")

            # 7. Voucher Number Generation
            if not voucher_number:
                prefix = voucher_type[:3].upper()
                count = sess.scalar(
                    select(func.count(JournalEntry.id)).where(
                        and_(
                            JournalEntry.company_id == company_id,
                            JournalEntry.financial_year == fy,
                            JournalEntry.voucher_type == voucher_type,
                        )
                    )
                ) or 0
                vch_num = f"{prefix}-{fy[-4:]}-{count + 1:06d}"
            else:
                vch_num = str(voucher_number).strip()

            # 8. Create JournalEntry Record
            journal_id = str(uuid.uuid4())
            journal = JournalEntry(
                id=journal_id,
                company_id=company_id,
                branch_id=branch_id,
                financial_year=fy,
                voucher_number=vch_num,
                voucher_type=voucher_type.upper(),
                voucher_date=voucher_date,
                narration=narration,
                total_debit=total_debit,
                total_credit=total_credit,
                status="POSTED",
                reference_type=reference_type,
                reference_id=reference_id,
                idempotency_key=str(idempotency_key).strip() if idempotency_key else None,
                posted_by=posted_by,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            sess.add(journal)

            # 9. Create JournalEntryLine Records
            for p_line in processed_lines:
                acc = p_line["account"]
                line_entry = JournalEntryLine(
                    id=str(uuid.uuid4()),
                    journal_id=journal_id,
                    company_id=company_id,
                    line_number=p_line["line_number"],
                    account_id=acc.id,
                    debit=p_line["debit"],
                    credit=p_line["credit"],
                    narration=p_line["narration"],
                    party_type=p_line["party_type"],
                    party_id=p_line["party_id"],
                    created_at=utc_now(),
                )
                sess.add(line_entry)

            # 10. Audit Log Record
            audit = AuditLog(
                id=str(uuid.uuid4()),
                company_id=company_id,
                user_id=posted_by,
                event_type="JOURNAL_POSTED",
                entity_type="JOURNAL_ENTRY",
                entity_id=journal_id,
                payload_json=f'{{"vch_no":"{vch_num}","type":"{voucher_type}","amount":"{total_debit}","date":"{voucher_date}"}}',
                created_at=utc_now(),
            )
            sess.add(audit)
            sess.flush()

            logger.info(f"Journal '{vch_num}' ({voucher_type}) of amount {total_debit} posted successfully.")
            return self._journal_to_dict(journal)

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)


    def reverse_journal_entry(
        self,
        company_id: str,
        journal_id: str,
        reversal_reason: str,
        reversal_date: Optional[str] = None,
        user_id: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Reverses a posted journal entry by generating an inverse compensating journal.
        Strictly preserves the immutable audit trail (no deletes or silent edits).
        """
        if not reversal_reason or not str(reversal_reason).strip():
            raise ValueError("reversal_reason is required to reverse a posted journal.")

        def _execute(sess: Session):
            orig = sess.scalar(
                select(JournalEntry).where(
                    and_(JournalEntry.company_id == company_id, JournalEntry.id == journal_id)
                )
            )
            if not orig:
                raise ValueError(f"JournalEntry '{journal_id}' not found.")
            if orig.status != "POSTED":
                raise JournalReversalError(f"Cannot reverse journal in status '{orig.status}'. Only POSTED journals can be reversed.")

            rev_date = reversal_date or orig.voucher_date
            self.validate_period_is_open(company_id, rev_date, session=sess)

            # Invert lines (swap debits and credits)
            orig_lines = sess.scalars(
                select(JournalEntryLine).where(JournalEntryLine.journal_id == orig.id).order_by(JournalEntryLine.line_number.asc())
            ).all()

            reversed_lines = []
            for line in orig_lines:
                reversed_lines.append({
                    "account_id": line.account_id,
                    "debit": line.credit,   # Swap
                    "credit": line.debit,   # Swap
                    "narration": f"Reversal of Line {line.line_number}: {line.narration or ''}".strip(),
                    "party_type": line.party_type,
                    "party_id": line.party_id,
                })

            rev_narration = f"Reversal of {orig.voucher_type} #{orig.voucher_number}: {reversal_reason.strip()}"
            reversal_voucher = self.post_journal_entry(
                company_id=company_id,
                branch_id=orig.branch_id,
                voucher_type="REVERSAL",
                voucher_date=rev_date,
                lines=reversed_lines,
                voucher_number=f"REV-{orig.voucher_number}",
                narration=rev_narration,
                reference_type="JOURNAL_ENTRY",
                reference_id=orig.id,
                financial_year=orig.financial_year,
                posted_by=user_id,
                session=sess,
            )

            # Mark original as REVERSED
            orig.status = "REVERSED"
            orig.reversed_by_id = reversal_voucher["id"]
            orig.reversal_reason = reversal_reason.strip()
            orig.updated_at = utc_now()

            # Link reversal back
            rev_obj = sess.scalar(select(JournalEntry).where(JournalEntry.id == reversal_voucher["id"]))
            if rev_obj:
                rev_obj.reversal_of_id = orig.id

            sess.flush()
            return reversal_voucher

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)


    def delete_journal_entry(self, company_id: str, journal_id: str, session: Optional[Session] = None) -> bool:
        """
        Guards posted journals from deletion.
        Only unposted DRAFT journals can be removed; POSTED/REVERSED journals raise ImmutableJournalError.
        """
        def _execute(sess: Session):
            journal = sess.scalar(
                select(JournalEntry).where(
                    and_(JournalEntry.company_id == company_id, JournalEntry.id == journal_id)
                )
            )
            if not journal:
                return False
            if journal.status in ("POSTED", "REVERSED"):
                raise ImmutableJournalError(
                    f"Accounting Security Invariant: Journal '{journal.voucher_number}' has status '{journal.status}' "
                    f"and cannot be deleted. Use reverse_journal_entry() to compensate."
                )
            sess.delete(journal)
            sess.flush()
            return True

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)

    # --------------------------------------------------------------------------
    # 3.1. Opening Balances & Year-End Closing Workflow
    # --------------------------------------------------------------------------

    def post_opening_balances(
        self,
        company_id: str,
        financial_year: str,
        opening_balances: List[Dict[str, Any]],
        voucher_date: Optional[str] = None,
        branch_id: Optional[str] = None,
        authorization_confirmed: bool = False,
        posted_by: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Posts authoritative opening balance journal entry for eligible Asset, Liability, and Equity accounts.
        - Requires explicit authorization (authorization_confirmed=True).
        - Generates balanced double-entry voucher (type='OPENING', voucher_number='OP-{financial_year}').
        - Balances unequal submissions automatically using OPENING_BALANCE_EQUITY.
        - Strictly rejects nominal (INCOME and EXPENSE) accounts.
        - Enforces idempotency: rejects duplicate active opening journal for (company_id, financial_year).
        - Prevents posting to an already closed financial year.
        - Updates AccountGroupMapping.opening_balance for display metadata.
        - Logs audit trail (OPENING_JOURNAL_POSTED).
        """
        if not authorization_confirmed:
            raise UnauthorizedAccountingActionError(
                "Opening balances posting is a sensitive operation and requires explicit authorization confirmation."
            )
        if not company_id:
            raise ValueError("company_id is required.")
        if not financial_year:
            raise ValueError("financial_year is required.")
        if not opening_balances:
            raise TraditionalAccountingError("Opening balances list cannot be empty.")

        def _execute(sess: Session):
            self.ensure_standard_accounts(company_id, session=sess)

            # Check if FY is already closed
            closed_rec = sess.scalar(
                select(FinancialYearClosing).where(
                    and_(
                        FinancialYearClosing.company_id == company_id,
                        FinancialYearClosing.financial_year == financial_year,
                        FinancialYearClosing.status == "CLOSED",
                    )
                )
            )
            if closed_rec:
                raise FinancialYearClosedError(
                    f"Financial year '{financial_year}' is closed. Cannot post opening balances."
                )

            # Check for duplicate active opening journal
            existing_op = sess.scalar(
                select(JournalEntry).where(
                    and_(
                        JournalEntry.company_id == company_id,
                        JournalEntry.financial_year == financial_year,
                        JournalEntry.voucher_type == "OPENING",
                        JournalEntry.status == "POSTED",
                    )
                )
            )
            if existing_op:
                raise DuplicateJournalError(
                    f"Opening balances for financial year '{financial_year}' have already been posted (Voucher #{existing_op.voucher_number})."
                )

            # Determine branch
            b_id = branch_id
            if not b_id:
                branch = sess.scalar(select(Branch).where(Branch.company_id == company_id))
                b_id = branch.id if branch else "BR01"

            # Determine voucher date (default to start of FY: e.g. '2026-04-01')
            start_yr = financial_year.split("-")[0]
            v_date = voucher_date or f"{start_yr}-04-01"

            # Validate date is not in a closed accounting period
            self.validate_period_is_open(company_id, v_date, session=sess)

            # Pre-load accounts for company
            accs = sess.scalars(select(Account).where(Account.company_id == company_id)).all()
            acc_by_id = {a.id: a for a in accs}
            acc_by_code = {a.code: a for a in accs}

            mappings = sess.scalars(
                select(AccountGroupMapping).where(AccountGroupMapping.company_id == company_id)
            ).all()
            map_by_acc = {m.account_id: m for m in mappings}

            # Process input lines
            journal_lines: List[Dict[str, Any]] = []
            total_dr = Decimal("0.00")
            total_cr = Decimal("0.00")
            submitted_acc_mappings: List[Tuple[AccountGroupMapping, Decimal, str]] = []
            non_zero_count = 0

            for idx, item in enumerate(opening_balances, start=1):
                raw_aid = item.get("account_id")
                raw_code = item.get("account_code")
                acc = acc_by_id.get(raw_aid) or acc_by_code.get(raw_code)
                if not acc:
                    raise AccountNotFoundError(f"Line {idx}: Account '{raw_aid or raw_code}' not found for company.")

                mapping = map_by_acc.get(acc.id)
                nature = (mapping.account_nature if mapping else "ASSET").upper()

                # Rule: Only Asset, Liability, and Equity accounts can have opening balances
                if nature in ("INCOME", "EXPENSE"):
                    raise TraditionalAccountingError(
                        f"Line {idx}: Account '{acc.code}' ({acc.name}) is a nominal account ({nature}). "
                        f"Opening balances are strictly prohibited for Income and Expense accounts."
                    )

                amt = round_money(item.get("amount", 0))
                if amt < Decimal("0.00"):
                    raise InvalidJournalAmountError(f"Line {idx}: Opening balance amount ({amt}) cannot be negative.")

                if amt == Decimal("0.00"):
                    continue

                non_zero_count += 1
                b_type = str(item.get("balance_type") or "").strip().upper()
                if not b_type:
                    # Default direction based on accounting nature
                    b_type = "DR" if nature == "ASSET" else "CR"
                elif b_type not in ("DR", "CR"):
                    raise ValueError(f"Line {idx}: Invalid balance_type '{b_type}'. Must be 'DR' or 'CR'.")

                if b_type == "DR":
                    line_dr = amt
                    line_cr = Decimal("0.00")
                    total_dr += amt
                else:
                    line_dr = Decimal("0.00")
                    line_cr = amt
                    total_cr += amt

                journal_lines.append({
                    "account_id": acc.id,
                    "debit": line_dr,
                    "credit": line_cr,
                    "narration": f"Opening Balance for {acc.name}",
                })
                if mapping:
                    submitted_acc_mappings.append((mapping, amt, b_type))

            if non_zero_count == 0:
                raise TraditionalAccountingError(
                    "Opening balances submission must contain at least one account with a non-zero balance."
                )

            # Auto-balance with Opening Balance Equity if Debits != Credits
            diff = round_money(abs(total_dr - total_cr))
            if diff > Decimal("0.00"):
                obe_acc = acc_by_code.get("OPENING_BALANCE_EQUITY")
                if not obe_acc:
                    raise AccountNotFoundError("Standard account 'OPENING_BALANCE_EQUITY' not found.")
                obe_mapping = map_by_acc.get(obe_acc.id)
                if total_dr > total_cr:
                    # Debits exceed Credits: credit Opening Balance Equity
                    journal_lines.append({
                        "account_id": obe_acc.id,
                        "debit": Decimal("0.00"),
                        "credit": diff,
                        "narration": f"Opening Balance Equity Offset ({diff} Cr)",
                    })
                    if obe_mapping:
                        submitted_acc_mappings.append((obe_mapping, diff, "CR"))
                else:
                    # Credits exceed Debits: debit Opening Balance Equity
                    journal_lines.append({
                        "account_id": obe_acc.id,
                        "debit": diff,
                        "credit": Decimal("0.00"),
                        "narration": f"Opening Balance Equity Offset ({diff} Dr)",
                    })
                    if obe_mapping:
                        submitted_acc_mappings.append((obe_mapping, diff, "DR"))

            # Post the journal entry atomically
            vch_num = f"OP-{financial_year}"
            journal = self.post_journal_entry(
                company_id=company_id,
                branch_id=b_id,
                voucher_type="OPENING",
                voucher_date=v_date,
                lines=journal_lines,
                voucher_number=vch_num,
                narration=f"Opening balances for Financial Year {financial_year}",
                financial_year=financial_year,
                posted_by=posted_by,
                session=sess,
            )

            # Synchronize AccountGroupMapping metadata
            for m, amt, b_type in submitted_acc_mappings:
                m.opening_balance = amt
                m.opening_balance_type = b_type
                m.updated_at = utc_now()

            # Record audit log
            audit = AuditLog(
                id=str(uuid.uuid4()),
                company_id=company_id,
                user_id=posted_by,
                event_type="OPENING_JOURNAL_POSTED",
                entity_type="JOURNAL_ENTRY",
                entity_id=journal["id"],
                payload_json=f'{{"financial_year":"{financial_year}","voucher_number":"{vch_num}","total":"{journal["total_debit"]}"}}',
                created_at=utc_now(),
            )
            sess.add(audit)
            sess.flush()

            logger.info(f"Opening balances for FY {financial_year} posted successfully: Voucher {vch_num}.")
            return journal

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)

    def reverse_opening_balances(
        self,
        company_id: str,
        financial_year: str,
        reversal_reason: str,
        reversal_date: Optional[str] = None,
        authorization_confirmed: bool = False,
        user_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Reverses posted opening balances for a financial year.
        - Requires explicit authorization.
        - Generates inverse compensating reversal journal (voucher_type='REVERSAL').
        - Resets AccountGroupMapping.opening_balance back to 0.00.
        - Records audit log (OPENING_JOURNAL_REVERSED).
        """
        if not authorization_confirmed:
            raise UnauthorizedAccountingActionError(
                "Reversing opening balances is a sensitive operation and requires explicit authorization confirmation."
            )
        if not reversal_reason or not str(reversal_reason).strip():
            raise ValueError("reversal_reason is required to reverse opening balances.")

        def _execute(sess: Session):
            op_journal = sess.scalar(
                select(JournalEntry).where(
                    and_(
                        JournalEntry.company_id == company_id,
                        JournalEntry.financial_year == financial_year,
                        JournalEntry.voucher_type == "OPENING",
                        JournalEntry.status == "POSTED",
                    )
                )
            )
            if not op_journal:
                raise TraditionalAccountingError(
                    f"No active POSTED opening journal found for financial year '{financial_year}'."
                )

            # Reverse the journal entry
            rev_date = reversal_date or op_journal.voucher_date
            rev_result = self.reverse_journal_entry(
                company_id=company_id,
                journal_id=op_journal.id,
                reversal_reason=reversal_reason.strip(),
                reversal_date=rev_date,
                user_id=user_id,
                session=sess,
            )

            # Reset opening balance metadata on accounts in that journal
            lines = sess.scalars(
                select(JournalEntryLine).where(JournalEntryLine.journal_id == op_journal.id)
            ).all()
            acc_ids = {l.account_id for l in lines}
            mappings = sess.scalars(
                select(AccountGroupMapping).where(
                    and_(
                        AccountGroupMapping.company_id == company_id,
                        AccountGroupMapping.account_id.in_(acc_ids),
                    )
                )
            ).all()
            for m in mappings:
                m.opening_balance = Decimal("0.00")
                m.opening_balance_type = "DR"
                m.updated_at = utc_now()

            # Record audit log
            audit = AuditLog(
                id=str(uuid.uuid4()),
                company_id=company_id,
                user_id=user_id,
                event_type="OPENING_JOURNAL_REVERSED",
                entity_type="JOURNAL_ENTRY",
                entity_id=op_journal.id,
                payload_json=f'{{"financial_year":"{financial_year}","reversal_id":"{rev_result["id"]}","reason":"{reversal_reason}"}}',
                created_at=utc_now(),
            )
            sess.add(audit)
            sess.flush()

            logger.info(f"Opening balances for FY {financial_year} reversed: Reversal Journal {rev_result['voucher_number']}.")
            return rev_result

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)

    def close_financial_year(
        self,
        company_id: str,
        financial_year: str,
        closing_date: Optional[str] = None,
        user_id: Optional[str] = None,
        notes: Optional[str] = None,
        authorization_confirmed: bool = False,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Executes year-end closing for a financial year:
        - Requires explicit authorization (authorization_confirmed=True).
        - Verifies the financial year is not already closed.
        - Calculates operational Net Profit or Net Loss for the financial year.
        - Generates closing journal entry (voucher_type='YEAR_END_CLOSING', voucher_number='CLS-{financial_year}'):
            * Debits all Income accounts to zero their credit balances.
            * Credits all Expense accounts to zero their debit balances.
            * Transfers Net Profit (Credit) or Net Loss (Debit) to Retained Earnings (Equity).
        - Preserves Asset, Liability, and Equity ledger balances intact.
        - Records closing record in FinancialYearClosing with status='CLOSED'.
        - Logs audit trail (FINANCIAL_YEAR_CLOSED).
        """
        if not authorization_confirmed:
            raise UnauthorizedAccountingActionError(
                "Financial year closing is a sensitive operation and requires explicit authorization confirmation."
            )
        if not company_id:
            raise ValueError("company_id is required.")
        if not financial_year:
            raise ValueError("financial_year is required.")

        def _execute(sess: Session):
            self.ensure_standard_accounts(company_id, session=sess)

            # Check if already closed
            existing_closing = sess.scalar(
                select(FinancialYearClosing).where(
                    and_(
                        FinancialYearClosing.company_id == company_id,
                        FinancialYearClosing.financial_year == financial_year,
                    )
                )
            )
            if existing_closing and existing_closing.status == "CLOSED":
                raise FinancialYearClosedError(f"Financial year '{financial_year}' is already closed.")

            # Determine closing date (default to end of FY: e.g. '2027-03-31')
            end_yr = financial_year.split("-")[1]
            c_date = closing_date or f"{end_yr}-03-31"

            # Determine branch
            branch = sess.scalar(select(Branch).where(Branch.company_id == company_id))
            b_id = branch.id if branch else "BR01"

            # 1. Calculate operational P&L for this FY
            pnl = self.get_profit_and_loss(
                company_id=company_id,
                financial_year=financial_year,
                end_date=c_date,
                session=sess,
            )
            net_profit = Decimal(pnl["net_profit"])
            is_profit = (net_profit >= Decimal("0.00"))

            # 2. Query all Income and Expense account balances for this FY
            # Exclude any existing YEAR_END_CLOSING entries
            inc_exp_q = (
                select(
                    JournalEntryLine.account_id,
                    func.coalesce(func.sum(JournalEntryLine.debit), 0).label("tot_deb"),
                    func.coalesce(func.sum(JournalEntryLine.credit), 0).label("tot_cred")
                )
                .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_id)
                .where(
                    and_(
                        JournalEntry.company_id == company_id,
                        JournalEntry.financial_year == financial_year,
                        JournalEntry.voucher_date <= c_date,
                        JournalEntry.status.in_(["POSTED", "REVERSED"]),
                        JournalEntry.voucher_type != "YEAR_END_CLOSING",
                    )
                )
                .group_by(JournalEntryLine.account_id)
            )
            acc_balances = {row.account_id: (round_money(row.tot_deb), round_money(row.tot_cred)) for row in sess.execute(inc_exp_q)}

            # Get account objects and natures
            accs = sess.scalars(select(Account).where(Account.company_id == company_id)).all()
            acc_by_id = {a.id: a for a in accs}
            acc_by_code = {a.code: a for a in accs}

            mappings = sess.scalars(select(AccountGroupMapping).where(AccountGroupMapping.company_id == company_id)).all()
            nature_by_acc = {m.account_id: m.account_nature.upper() for m in mappings}

            closing_lines: List[Dict[str, Any]] = []

            for aid, (deb, cred) in acc_balances.items():
                acc = acc_by_id.get(aid)
                if not acc:
                    continue
                nature = nature_by_acc.get(aid, "EXPENSE")
                if nature == "INCOME":
                    # Income accounts normal credit balance: net = cred - deb
                    net_inc = round_money(cred - deb)
                    if net_inc > Decimal("0.00"):
                        # Debit income account to zero out balance
                        closing_lines.append({
                            "account_id": aid,
                            "debit": net_inc,
                            "credit": Decimal("0.00"),
                            "narration": f"Close {acc.name} to Retained Earnings",
                        })
                    elif net_inc < Decimal("0.00"):
                        closing_lines.append({
                            "account_id": aid,
                            "debit": Decimal("0.00"),
                            "credit": abs(net_inc),
                            "narration": f"Close {acc.name} to Retained Earnings",
                        })
                elif nature == "EXPENSE":
                    # Expense accounts normal debit balance: net = deb - cred
                    net_exp = round_money(deb - cred)
                    if net_exp > Decimal("0.00"):
                        # Credit expense account to zero out balance
                        closing_lines.append({
                            "account_id": aid,
                            "debit": Decimal("0.00"),
                            "credit": net_exp,
                            "narration": f"Close {acc.name} to Retained Earnings",
                        })
                    elif net_exp < Decimal("0.00"):
                        closing_lines.append({
                            "account_id": aid,
                            "debit": abs(net_exp),
                            "credit": Decimal("0.00"),
                            "narration": f"Close {acc.name} to Retained Earnings",
                        })

            # Retained Earnings transfer line
            ret_acc = acc_by_code.get("RETAINED_EARNINGS")
            if not ret_acc:
                raise AccountNotFoundError("Standard account 'RETAINED_EARNINGS' not found.")

            if net_profit > Decimal("0.00"):
                # Net Profit: Credit Retained Earnings
                closing_lines.append({
                    "account_id": ret_acc.id,
                    "debit": Decimal("0.00"),
                    "credit": net_profit,
                    "narration": f"Transfer of Net Profit to Retained Earnings for FY {financial_year}",
                })
            elif net_profit < Decimal("0.00"):
                # Net Loss: Debit Retained Earnings
                closing_lines.append({
                    "account_id": ret_acc.id,
                    "debit": abs(net_profit),
                    "credit": Decimal("0.00"),
                    "narration": f"Transfer of Net Loss to Retained Earnings for FY {financial_year}",
                })

            closing_journal = None
            if closing_lines and len(closing_lines) >= 2:
                vch_num = f"CLS-{financial_year}"
                closing_journal = self.post_journal_entry(
                    company_id=company_id,
                    branch_id=b_id,
                    voucher_type="YEAR_END_CLOSING",
                    voucher_date=c_date,
                    lines=closing_lines,
                    voucher_number=vch_num,
                    narration=f"Year-End Closing Journal for Financial Year {financial_year}",
                    financial_year=financial_year,
                    posted_by=user_id,
                    session=sess,
                )

            # Record or update FinancialYearClosing
            if existing_closing:
                existing_closing.status = "CLOSED"
                existing_closing.closing_date = c_date
                existing_closing.closing_journal_id = closing_journal["id"] if closing_journal else None
                existing_closing.net_profit = net_profit
                existing_closing.closed_by = user_id
                existing_closing.reopened_at = None
                existing_closing.reopened_by = None
                existing_closing.reopen_reason = None
                existing_closing.updated_at = utc_now()
                closing_rec = existing_closing
            else:
                closing_rec = FinancialYearClosing(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    branch_id=b_id,
                    financial_year=financial_year,
                    closing_date=c_date,
                    closing_journal_id=closing_journal["id"] if closing_journal else None,
                    net_profit=net_profit,
                    status="CLOSED",
                    closed_by=user_id,
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                sess.add(closing_rec)

            # Audit Log
            audit = AuditLog(
                id=str(uuid.uuid4()),
                company_id=company_id,
                user_id=user_id,
                event_type="FINANCIAL_YEAR_CLOSED",
                entity_type="FINANCIAL_YEAR_CLOSING",
                entity_id=closing_rec.id,
                payload_json=f'{{"financial_year":"{financial_year}","net_profit":"{net_profit}","is_profit":{str(is_profit).lower()},"closing_journal_id":"{closing_rec.closing_journal_id}"}}',
                created_at=utc_now(),
            )
            sess.add(audit)
            sess.flush()

            logger.info(f"Financial year {financial_year} closed successfully. Net Profit/Loss: {net_profit}.")
            return {
                "id": closing_rec.id,
                "company_id": company_id,
                "branch_id": closing_rec.branch_id,
                "financial_year": financial_year,
                "closing_date": c_date,
                "closing_journal_id": closing_rec.closing_journal_id,
                "closing_journal": closing_journal,
                "net_profit": str(net_profit),
                "net_profit_or_loss": str(net_profit),
                "is_profit": is_profit,
                "status": "CLOSED",
                "notes": notes,
            }

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)

    def reopen_financial_year(
        self,
        company_id: str,
        financial_year: str,
        reopen_reason: str,
        user_id: Optional[str] = None,
        authorization_confirmed: bool = False,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Reopens a previously closed financial year:
        - Requires explicit authorization.
        - Reverses next year carry-forward opening journal if present.
        - Reverses closing journal entry (voucher_type='YEAR_END_CLOSING').
        - Sets FinancialYearClosing.status = 'REOPENED'.
        - Restores operational P&L and Balance Sheet to open state.
        - Logs audit trail (FINANCIAL_YEAR_REOPENED).
        """
        if not authorization_confirmed:
            raise UnauthorizedAccountingActionError(
                "Reopening a financial year is a sensitive operation and requires explicit authorization confirmation."
            )
        if not reopen_reason or not str(reopen_reason).strip():
            raise ValueError("reopen_reason is required to reopen a financial year.")

        def _execute(sess: Session):
            closing = sess.scalar(
                select(FinancialYearClosing).where(
                    and_(
                        FinancialYearClosing.company_id == company_id,
                        FinancialYearClosing.financial_year == financial_year,
                    )
                )
            )
            if not closing or closing.status != "CLOSED":
                raise TraditionalAccountingError(
                    f"Financial year '{financial_year}' is not in CLOSED status (current status: '{closing.status if closing else 'NONE'}')."
                )

            # 1. Check if next year carry forward opening journal exists
            if closing.next_opening_journal_id:
                next_journal = sess.scalar(
                    select(JournalEntry).where(
                        and_(
                            JournalEntry.company_id == company_id,
                            JournalEntry.id == closing.next_opening_journal_id,
                        )
                    )
                )
                if next_journal and next_journal.status == "POSTED":
                    # Reverse next year's carry-forward opening journal
                    self.reverse_journal_entry(
                        company_id=company_id,
                        journal_id=next_journal.id,
                        reversal_reason=f"Rollback carry-forward due to reopening of FY {financial_year}",
                        user_id=user_id,
                        session=sess,
                    )
                closing.next_opening_journal_id = None

            # 2. Reverse the closing journal entry
            if closing.closing_journal_id:
                closing_journal = sess.scalar(
                    select(JournalEntry).where(
                        and_(
                            JournalEntry.company_id == company_id,
                            JournalEntry.id == closing.closing_journal_id,
                        )
                    )
                )
                if closing_journal and closing_journal.status == "POSTED":
                    self.reverse_journal_entry(
                        company_id=company_id,
                        journal_id=closing_journal.id,
                        reversal_reason=f"Reopening FY {financial_year}: {reopen_reason.strip()}",
                        user_id=user_id,
                        session=sess,
                    )

            # 3. Update closing record
            closing.status = "REOPENED"
            closing.reopened_at = utc_now()
            closing.reopened_by = user_id
            closing.reopen_reason = reopen_reason.strip()
            closing.updated_at = utc_now()

            # 4. Audit Log
            audit = AuditLog(
                id=str(uuid.uuid4()),
                company_id=company_id,
                user_id=user_id,
                event_type="FINANCIAL_YEAR_REOPENED",
                entity_type="FINANCIAL_YEAR_CLOSING",
                entity_id=closing.id,
                payload_json=f'{{"financial_year":"{financial_year}","reason":"{reopen_reason}"}}',
                created_at=utc_now(),
            )
            sess.add(audit)
            sess.flush()

            logger.info(f"Financial year {financial_year} reopened successfully.")
            return {
                "id": closing.id,
                "company_id": company_id,
                "financial_year": financial_year,
                "status": "REOPENED",
                "reopened_at": closing.reopened_at.isoformat() if closing.reopened_at else None,
                "reopened_by": user_id,
                "reopen_reason": reopen_reason,
            }

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)

    def carry_forward_to_next_financial_year(
        self,
        company_id: str,
        current_financial_year: str,
        next_financial_year: Optional[str] = None,
        carry_forward_date: Optional[str] = None,
        user_id: Optional[str] = None,
        authorization_confirmed: bool = False,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Carries forward permanent account balances (Asset, Liability, Equity with updated Retained Earnings)
        from a closed financial year to establish the opening journal of the next financial year.
        - Requires explicit authorization.
        - Enforces that current financial year is CLOSED.
        - Carries forward only permanent accounts (Asset, Liability, Equity). Nominal accounts (Income/Expense) are strictly 0.
        - Generates balanced opening journal (voucher_type='OPENING', voucher_number='OP-{next_financial_year}').
        - Updates FinancialYearClosing.next_opening_journal_id link.
        - Synchronizes AccountGroupMapping.opening_balance for next FY.
        - Logs audit trail (FINANCIAL_YEAR_CARRY_FORWARD_POSTED).
        """
        if not authorization_confirmed:
            raise UnauthorizedAccountingActionError(
                "Financial year carry-forward is a sensitive operation and requires explicit authorization confirmation."
            )
        if not current_financial_year:
            raise ValueError("current_financial_year is required.")

        def _execute(sess: Session):
            self.ensure_standard_accounts(company_id, session=sess)

            # Verify current FY is closed
            closing = sess.scalar(
                select(FinancialYearClosing).where(
                    and_(
                        FinancialYearClosing.company_id == company_id,
                        FinancialYearClosing.financial_year == current_financial_year,
                    )
                )
            )
            if not closing or closing.status != "CLOSED":
                raise TraditionalAccountingError(
                    f"Cannot carry forward: Financial year '{current_financial_year}' is not CLOSED (current status: '{closing.status if closing else 'NONE'}')."
                )

            # Determine next financial year
            if not next_financial_year:
                parts = current_financial_year.split("-")
                next_fy = f"{int(parts[0]) + 1}-{int(parts[1]) + 1}"
            else:
                next_fy = next_financial_year.strip()

            # Determine carry forward date (first day of next FY: e.g. '2027-04-01')
            start_yr = next_fy.split("-")[0]
            cf_date = carry_forward_date or f"{start_yr}-04-01"

            # Check if opening journal already exists for next FY
            existing_next_op = sess.scalar(
                select(JournalEntry).where(
                    and_(
                        JournalEntry.company_id == company_id,
                        JournalEntry.financial_year == next_fy,
                        JournalEntry.voucher_type == "OPENING",
                        JournalEntry.status == "POSTED",
                    )
                )
            )
            if existing_next_op:
                raise DuplicateJournalError(
                    f"Opening balances for next financial year '{next_fy}' have already been posted (Voucher #{existing_next_op.voucher_number})."
                )

            # Determine branch
            branch = sess.scalar(select(Branch).where(Branch.company_id == company_id))
            b_id = branch.id if branch else "BR01"

            # Extract permanent account balances at the end of closed FY
            # (including closing journal entries!)
            accounts = sess.scalars(
                select(Account).where(
                    and_(Account.company_id == company_id, Account.is_active == True)
                )
            ).all()
            mappings = sess.scalars(
                select(AccountGroupMapping).where(AccountGroupMapping.company_id == company_id)
            ).all()
            map_by_acc = {m.account_id: m for m in mappings}

            # Check opening accounts for current FY
            opening_acc_ids = set(
                sess.scalars(
                    select(JournalEntryLine.account_id)
                    .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_id)
                    .where(
                        and_(
                            JournalEntry.company_id == company_id,
                            JournalEntry.financial_year == current_financial_year,
                            JournalEntry.voucher_type == "OPENING",
                            JournalEntry.status == "POSTED",
                        )
                    )
                ).all()
            )

            # Sum all journal movements in current FY (up to closing date)
            mov_q = (
                select(
                    JournalEntryLine.account_id,
                    func.coalesce(func.sum(JournalEntryLine.debit), 0).label("tot_deb"),
                    func.coalesce(func.sum(JournalEntryLine.credit), 0).label("tot_cred")
                )
                .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_id)
                .where(
                    and_(
                        JournalEntry.company_id == company_id,
                        JournalEntry.financial_year == current_financial_year,
                        JournalEntry.status.in_(["POSTED", "REVERSED"]),
                    )
                )
                .group_by(JournalEntryLine.account_id)
            )
            totals_map = {row.account_id: (round_money(row.tot_deb), round_money(row.tot_cred)) for row in sess.execute(mov_q)}

            cf_lines: List[Dict[str, Any]] = []
            total_dr = Decimal("0.00")
            total_cr = Decimal("0.00")
            mapping_updates: List[Tuple[AccountGroupMapping, Decimal, str]] = []

            for acc in accounts:
                m = map_by_acc.get(acc.id)
                nature = (m.account_nature if m else "ASSET").upper()

                # ONLY permanent accounts (Asset, Liability, Equity) participate in carry-forward
                if nature not in ("ASSET", "LIABILITY", "EQUITY"):
                    continue

                if acc.id in opening_acc_ids:
                    base_op = Decimal("0.00")
                else:
                    base_op = round_money(m.opening_balance if m else Decimal("0.00"))
                op_type = m.opening_balance_type if m else "DR"
                net_op = base_op if op_type == "DR" else -base_op

                deb, cred = totals_map.get(acc.id, (Decimal("0.00"), Decimal("0.00")))
                net = net_op + (deb - cred)

                if net == Decimal("0.00"):
                    continue

                if nature == "ASSET":
                    if net > Decimal("0.00"):
                        line_dr = net
                        line_cr = Decimal("0.00")
                        b_type = "DR"
                    else:
                        line_dr = Decimal("0.00")
                        line_cr = abs(net)
                        b_type = "CR"
                else:
                    # Liability & Equity
                    val = -net
                    if val > Decimal("0.00"):
                        line_dr = Decimal("0.00")
                        line_cr = val
                        b_type = "CR"
                    else:
                        line_dr = abs(val)
                        line_cr = Decimal("0.00")
                        b_type = "DR"

                total_dr += line_dr
                total_cr += line_cr

                cf_lines.append({
                    "account_id": acc.id,
                    "debit": line_dr,
                    "credit": line_cr,
                    "narration": f"Carry-forward opening balance from FY {current_financial_year}",
                })
                if m:
                    mapping_updates.append((m, abs(net), b_type))

            # In double-entry, Asset = Liability + Equity, so total_dr must equal total_cr.
            # If tiny rounding difference exists, balance with OPENING_BALANCE_EQUITY
            diff = round_money(abs(total_dr - total_cr))
            if diff > Decimal("0.00"):
                accs_by_code = {a.code: a for a in accounts}
                obe_acc = accs_by_code.get("OPENING_BALANCE_EQUITY")
                if total_dr > total_cr:
                    cf_lines.append({
                        "account_id": obe_acc.id,
                        "debit": Decimal("0.00"),
                        "credit": diff,
                        "narration": f"Opening Balance Equity Offset ({diff} Cr)",
                    })
                else:
                    cf_lines.append({
                        "account_id": obe_acc.id,
                        "debit": diff,
                        "credit": Decimal("0.00"),
                        "narration": f"Opening Balance Equity Offset ({diff} Dr)",
                    })

            # Post the opening journal for the next financial year
            vch_num = f"OP-{next_fy}"
            next_journal = self.post_journal_entry(
                company_id=company_id,
                branch_id=b_id,
                voucher_type="OPENING",
                voucher_date=cf_date,
                lines=cf_lines,
                voucher_number=vch_num,
                narration=f"Opening balances carried forward from FY {current_financial_year}",
                financial_year=next_fy,
                posted_by=user_id,
                session=sess,
            )

            # Update FinancialYearClosing link
            closing.next_opening_journal_id = next_journal["id"]
            closing.updated_at = utc_now()

            # Synchronize AccountGroupMapping opening balance metadata
            for m, amt, b_type in mapping_updates:
                m.opening_balance = amt
                m.opening_balance_type = b_type
                m.updated_at = utc_now()

            # Audit Log
            audit = AuditLog(
                id=str(uuid.uuid4()),
                company_id=company_id,
                user_id=user_id,
                event_type="FINANCIAL_YEAR_CARRY_FORWARD_POSTED",
                entity_type="FINANCIAL_YEAR_CLOSING",
                entity_id=closing.id,
                payload_json=f'{{"source_financial_year":"{current_financial_year}","next_financial_year":"{next_fy}","next_opening_journal_id":"{next_journal["id"]}"}}',
                created_at=utc_now(),
            )
            sess.add(audit)
            sess.flush()

            logger.info(f"Opening balances carried forward from FY {current_financial_year} to FY {next_fy}: Voucher {vch_num}.")
            return {
                "source_financial_year": current_financial_year,
                "next_financial_year": next_fy,
                "carry_forward_date": cf_date,
                "opening_journal": next_journal,
                "lines_count": len(cf_lines),
                "total_carried_forward": str(next_journal["total_debit"]),
            }

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)

    def get_financial_year_closing(
        self,
        company_id: str,
        financial_year: str,
        session: Optional[Session] = None,
    ) -> Optional[Dict[str, Any]]:
        """Returns the closing status and details of a financial year."""
        def _execute(sess: Session):
            closing = sess.scalar(
                select(FinancialYearClosing).where(
                    and_(
                        FinancialYearClosing.company_id == company_id,
                        FinancialYearClosing.financial_year == financial_year,
                    )
                )
            )
            if not closing:
                return None
            return {
                "id": closing.id,
                "company_id": closing.company_id,
                "branch_id": closing.branch_id,
                "financial_year": closing.financial_year,
                "closing_date": closing.closing_date,
                "closing_journal_id": closing.closing_journal_id,
                "next_opening_journal_id": closing.next_opening_journal_id,
                "net_profit": str(closing.net_profit),
                "net_profit_or_loss": str(closing.net_profit),
                "is_profit": closing.net_profit >= Decimal("0.00"),
                "status": closing.status,
                "closed_by": closing.closed_by,
                "reopened_at": closing.reopened_at.isoformat() if closing.reopened_at else None,
                "reopened_by": closing.reopened_by,
                "reopen_reason": closing.reopen_reason,
                "created_at": closing.created_at.isoformat() if closing.created_at else None,
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    # --------------------------------------------------------------------------
    # 4. Financial Reports Calculation Engines
    # --------------------------------------------------------------------------

    def get_general_ledger(
        self,
        company_id: str,
        account_id: str,
        branch_id: Optional[str] = None,
        financial_year: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Calculates chronological General Ledger statement with exact opening and running balances."""
        def _execute(sess: Session):
            acc = sess.scalar(
                select(Account).where(and_(Account.company_id == company_id, Account.id == account_id))
            )
            if not acc:
                raise AccountNotFoundError(f"Account '{account_id}' not found for company '{company_id}'.")

            mapping = sess.scalar(
                select(AccountGroupMapping).where(
                    and_(AccountGroupMapping.company_id == company_id, AccountGroupMapping.account_id == account_id)
                )
            )
            nature = (mapping.account_nature if mapping else "ASSET").upper()

            # Check if this account has an OPENING journal entry posted.
            # If so, base_op is set to 0.00 to avoid double-counting between the opening journal and metadata.
            has_opening_journal = sess.scalar(
                select(func.count(JournalEntry.id))
                .join(JournalEntryLine, JournalEntryLine.journal_id == JournalEntry.id)
                .where(
                    and_(
                        JournalEntry.company_id == company_id,
                        JournalEntryLine.account_id == account_id,
                        JournalEntry.voucher_type == "OPENING",
                        JournalEntry.status == "POSTED",
                    )
                )
            ) > 0

            if has_opening_journal:
                base_op = Decimal("0.00")
            else:
                base_op = round_money(mapping.opening_balance if mapping else Decimal("0.00"))
            op_type = mapping.opening_balance_type if mapping else "DR"

            # 1. Calculate historical movements prior to start_date
            prior_debit = Decimal("0.00")
            prior_credit = Decimal("0.00")
            if start_date:
                prior_q = (
                    select(
                        func.coalesce(func.sum(JournalEntryLine.debit), 0),
                        func.coalesce(func.sum(JournalEntryLine.credit), 0)
                    )
                    .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_id)
                    .where(
                        and_(
                            JournalEntry.company_id == company_id,
                            JournalEntryLine.account_id == account_id,
                            JournalEntry.voucher_date < start_date,
                            JournalEntry.status.in_(["POSTED", "REVERSED"]),
                        )
                    )
                )
                if branch_id:
                    prior_q = prior_q.where(JournalEntry.branch_id == branch_id)
                if financial_year:
                    prior_q = prior_q.where(JournalEntry.financial_year == financial_year)

                p_deb, p_cred = sess.execute(prior_q).one()
                prior_debit = round_money(p_deb)
                prior_credit = round_money(p_cred)

            # Initial opening balance in net debit terms
            net_opening = (base_op if op_type == "DR" else -base_op) + (prior_debit - prior_credit)

            # 2. Query period transactions
            tx_q = (
                select(
                    JournalEntryLine.id,
                    JournalEntryLine.debit,
                    JournalEntryLine.credit,
                    JournalEntryLine.narration.label("line_narration"),
                    JournalEntry.id.label("journal_id"),
                    JournalEntry.voucher_number,
                    JournalEntry.voucher_type,
                    JournalEntry.voucher_date,
                    JournalEntry.narration.label("journal_narration"),
                    JournalEntry.status,
                )
                .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_id)
                .where(
                    and_(
                        JournalEntry.company_id == company_id,
                        JournalEntryLine.account_id == account_id,
                        JournalEntry.status.in_(["POSTED", "REVERSED"]),
                    )
                )
            )
            if start_date:
                tx_q = tx_q.where(JournalEntry.voucher_date >= start_date)
            if end_date:
                tx_q = tx_q.where(JournalEntry.voucher_date <= end_date)
            if branch_id:
                tx_q = tx_q.where(JournalEntry.branch_id == branch_id)
            if financial_year:
                tx_q = tx_q.where(JournalEntry.financial_year == financial_year)

            tx_q = tx_q.order_by(JournalEntry.voucher_date.asc(), JournalEntry.created_at.asc())
            rows = sess.execute(tx_q).all()

            running_net = net_opening
            entries = []
            period_debit = Decimal("0.00")
            period_credit = Decimal("0.00")

            for r in rows:
                deb = round_money(r.debit)
                cred = round_money(r.credit)
                period_debit += deb
                period_credit += cred
                running_net += (deb - cred)

                # Format running balance based on account nature
                if nature in ("ASSET", "EXPENSE"):
                    bal_val = running_net
                    bal_tag = "Dr" if running_net >= Decimal("0.00") else "Cr"
                else:
                    bal_val = -running_net
                    bal_tag = "Cr" if running_net <= Decimal("0.00") else "Dr"

                entries.append({
                    "id": r.id,
                    "journal_id": r.journal_id,
                    "date": r.voucher_date,
                    "voucher_type": r.voucher_type,
                    "voucher_number": r.voucher_number,
                    "narration": r.line_narration or r.journal_narration,
                    "debit": str(deb),
                    "credit": str(cred),
                    "running_balance": str(abs(round_money(bal_val))),
                    "balance_type": bal_tag,
                    "status": r.status,
                })

            closing_net = running_net
            if nature in ("ASSET", "EXPENSE"):
                closing_val = closing_net
                closing_tag = "Dr" if closing_net >= Decimal("0.00") else "Cr"
            else:
                closing_val = -closing_net
                closing_tag = "Cr" if closing_net <= Decimal("0.00") else "Dr"

            return {
                "account_id": acc.id,
                "account_code": acc.code,
                "account_name": acc.name,
                "nature": nature,
                "opening_balance": str(abs(round_money(net_opening))),
                "opening_balance_type": "Dr" if net_opening >= Decimal("0.00") else "Cr",
                "period_debit": str(period_debit),
                "period_credit": str(period_credit),
                "closing_balance": str(abs(round_money(closing_val))),
                "closing_balance_type": closing_tag,
                "entries": entries,
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def get_day_book(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        session: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Returns chronological list of all double-entry vouchers posted on a date / date range."""
        def _execute(sess: Session):
            query = select(JournalEntry).where(JournalEntry.company_id == company_id)
            if branch_id:
                query = query.where(JournalEntry.branch_id == branch_id)

            if date:
                query = query.where(JournalEntry.voucher_date == date)
            else:
                if start_date:
                    query = query.where(JournalEntry.voucher_date >= start_date)
                if end_date:
                    query = query.where(JournalEntry.voucher_date <= end_date)

            query = query.order_by(JournalEntry.voucher_date.asc(), JournalEntry.created_at.asc())
            journals = sess.scalars(query).all()
            return [self._journal_to_dict(j) for j in journals]

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def get_trial_balance(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        financial_year: Optional[str] = None,
        as_of_date: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Calculates Trial Balance across all accounts.
        Reconciles total debit and total credit columns to guarantee double-entry integrity.
        """
        def _execute(sess: Session):
            self.ensure_standard_accounts(company_id, session=sess)
            accounts = sess.scalars(
                select(Account).where(
                    and_(Account.company_id == company_id, Account.is_active == True)
                ).order_by(Account.code.asc())
            ).all()

            mappings = sess.scalars(
                select(AccountGroupMapping).where(AccountGroupMapping.company_id == company_id)
            ).all()
            map_by_acc = {m.account_id: m for m in mappings}

            # Aggregate journal line totals per account up to as_of_date (POSTED only)
            sum_q = (
                select(
                    JournalEntryLine.account_id,
                    func.coalesce(func.sum(JournalEntryLine.debit), 0).label("tot_debit"),
                    func.coalesce(func.sum(JournalEntryLine.credit), 0).label("tot_credit")
                )
                .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_id)
                .where(
                    and_(
                        JournalEntry.company_id == company_id,
                        JournalEntry.status.in_(["POSTED", "REVERSED"]),
                    )
                )
            )
            if branch_id:
                sum_q = sum_q.where(JournalEntry.branch_id == branch_id)
            if financial_year:
                sum_q = sum_q.where(JournalEntry.financial_year == financial_year)
            if as_of_date:
                sum_q = sum_q.where(JournalEntry.voucher_date <= as_of_date)

            sum_q = sum_q.group_by(JournalEntryLine.account_id)
            totals_map = {row.account_id: (round_money(row.tot_debit), round_money(row.tot_credit)) for row in sess.execute(sum_q)}

            # Identify accounts with posted OPENING journal lines to prevent double-counting
            op_q = (
                select(JournalEntryLine.account_id)
                .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_id)
                .where(
                    and_(
                        JournalEntry.company_id == company_id,
                        JournalEntry.voucher_type == "OPENING",
                        JournalEntry.status == "POSTED",
                    )
                )
            )
            if branch_id:
                op_q = op_q.where(JournalEntry.branch_id == branch_id)
            if financial_year:
                op_q = op_q.where(JournalEntry.financial_year == financial_year)
            if as_of_date:
                op_q = op_q.where(JournalEntry.voucher_date <= as_of_date)
            opening_acc_ids = set(sess.scalars(op_q).all())

            trial_lines = []
            grand_debit = Decimal("0.00")
            grand_credit = Decimal("0.00")

            for acc in accounts:
                m = map_by_acc.get(acc.id)
                if acc.id in opening_acc_ids:
                    base_op = Decimal("0.00")
                else:
                    base_op = round_money(m.opening_balance if m else Decimal("0.00"))
                op_type = m.opening_balance_type if m else "DR"
                net_op = base_op if op_type == "DR" else -base_op

                deb, cred = totals_map.get(acc.id, (Decimal("0.00"), Decimal("0.00")))
                net_balance = net_op + (deb - cred)

                # Skip zero-balance accounts with no activity
                if net_balance == Decimal("0.00") and deb == Decimal("0.00") and cred == Decimal("0.00"):
                    continue

                if net_balance > Decimal("0.00"):
                    col_deb = net_balance
                    col_cred = Decimal("0.00")
                elif net_balance < Decimal("0.00"):
                    col_deb = Decimal("0.00")
                    col_cred = abs(net_balance)
                else:
                    col_deb = Decimal("0.00")
                    col_cred = Decimal("0.00")

                grand_debit += col_deb
                grand_credit += col_cred

                trial_lines.append({
                    "account_id": acc.id,
                    "account_code": acc.code,
                    "account_name": acc.name,
                    "nature": m.account_nature if m else "ASSET",
                    "debit": str(col_deb),
                    "credit": str(col_cred),
                    "net_balance": str(abs(net_balance)),
                    "balance_type": "Dr" if net_balance >= Decimal("0.00") else "Cr",
                })

            diff = round_money(abs(grand_debit - grand_credit))
            return {
                "accounts": trial_lines,
                "total_debit": str(grand_debit),
                "total_credit": str(grand_credit),
                "difference": str(diff),
                "is_balanced": diff == Decimal("0.00"),
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def get_profit_and_loss(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        financial_year: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Calculates Profit and Loss statement:
        Income (Credits in INCOME accounts) minus Expenses (Debits in EXPENSE accounts).
        """
        def _execute(sess: Session):
            self.ensure_standard_accounts(company_id, session=sess)
            mappings = sess.scalars(
                select(AccountGroupMapping).where(
                    and_(
                        AccountGroupMapping.company_id == company_id,
                        AccountGroupMapping.account_nature.in_(["INCOME", "EXPENSE"]),
                    )
                )
            ).all()
            map_by_acc = {m.account_id: m for m in mappings}
            acc_ids = list(map_by_acc.keys())

            accs = sess.scalars(
                select(Account).where(and_(Account.company_id == company_id, Account.id.in_(acc_ids)))
            ).all()

            # Aggregate period movements
            tx_q = (
                select(
                    JournalEntryLine.account_id,
                    func.coalesce(func.sum(JournalEntryLine.debit), 0).label("tot_debit"),
                    func.coalesce(func.sum(JournalEntryLine.credit), 0).label("tot_credit")
                )
                .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_id)
                .where(
                    and_(
                        JournalEntry.company_id == company_id,
                        JournalEntry.status.in_(["POSTED", "REVERSED"]),
                        JournalEntry.voucher_type != "YEAR_END_CLOSING",
                    )
                )
            )
            if start_date:
                tx_q = tx_q.where(JournalEntry.voucher_date >= start_date)
            if end_date:
                tx_q = tx_q.where(JournalEntry.voucher_date <= end_date)
            if branch_id:
                tx_q = tx_q.where(JournalEntry.branch_id == branch_id)
            if financial_year:
                tx_q = tx_q.where(JournalEntry.financial_year == financial_year)

            tx_q = tx_q.group_by(JournalEntryLine.account_id)
            totals_map = {row.account_id: (round_money(row.tot_debit), round_money(row.tot_credit)) for row in sess.execute(tx_q)}

            income_items = []
            expense_items = []
            total_income = Decimal("0.00")
            total_expense = Decimal("0.00")

            for acc in accs:
                m = map_by_acc.get(acc.id)
                nature = m.account_nature if m else "INCOME"
                deb, cred = totals_map.get(acc.id, (Decimal("0.00"), Decimal("0.00")))
                if nature == "INCOME":
                    # Income: Credits increase revenue, Debits decrease
                    net_inc = cred - deb
                    if net_inc != Decimal("0.00") or cred > 0:
                        total_income += net_inc
                        income_items.append({
                            "account_id": acc.id,
                            "account_code": acc.code,
                            "account_name": acc.name,
                            "amount": str(net_inc),
                        })
                elif nature == "EXPENSE":
                    # Expense: Debits increase expense, Credits decrease
                    net_exp = deb - cred
                    if net_exp != Decimal("0.00") or deb > 0:
                        total_expense += net_exp
                        expense_items.append({
                            "account_id": acc.id,
                            "account_code": acc.code,
                            "account_name": acc.name,
                            "amount": str(net_exp),
                        })

            net_profit = round_money(total_income - total_expense)
            return {
                "income": income_items,
                "expenses": expense_items,
                "total_income": str(total_income),
                "total_expense": str(total_expense),
                "net_profit": str(net_profit),
                "is_profit": net_profit >= Decimal("0.00"),
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def get_balance_sheet(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        financial_year: Optional[str] = None,
        as_of_date: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Calculates Balance Sheet:
        Assets = Liabilities + Equity + Net Profit (Period).
        """
        def _execute(sess: Session):
            self.ensure_standard_accounts(company_id, session=sess)
            mappings = sess.scalars(
                select(AccountGroupMapping).where(
                    and_(
                        AccountGroupMapping.company_id == company_id,
                        AccountGroupMapping.account_nature.in_(["ASSET", "LIABILITY", "EQUITY"]),
                    )
                )
            ).all()
            map_by_acc = {m.account_id: m for m in mappings}
            acc_ids = list(map_by_acc.keys())

            accounts = sess.scalars(
                select(Account).where(and_(Account.company_id == company_id, Account.id.in_(acc_ids)))
            ).all()

            # Aggregate movements up to as_of_date (POSTED only)
            sum_q = (
                select(
                    JournalEntryLine.account_id,
                    func.coalesce(func.sum(JournalEntryLine.debit), 0).label("tot_debit"),
                    func.coalesce(func.sum(JournalEntryLine.credit), 0).label("tot_credit")
                )
                .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_id)
                .where(
                    and_(
                        JournalEntry.company_id == company_id,
                        JournalEntry.status.in_(["POSTED", "REVERSED"]),
                    )
                )
            )
            if branch_id:
                sum_q = sum_q.where(JournalEntry.branch_id == branch_id)
            if financial_year:
                sum_q = sum_q.where(JournalEntry.financial_year == financial_year)
            if as_of_date:
                sum_q = sum_q.where(JournalEntry.voucher_date <= as_of_date)

            sum_q = sum_q.group_by(JournalEntryLine.account_id)
            totals_map = {row.account_id: (round_money(row.tot_debit), round_money(row.tot_credit)) for row in sess.execute(sum_q)}

            # Identify accounts with posted OPENING journal lines to prevent double-counting
            op_q = (
                select(JournalEntryLine.account_id)
                .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_id)
                .where(
                    and_(
                        JournalEntry.company_id == company_id,
                        JournalEntry.voucher_type == "OPENING",
                        JournalEntry.status == "POSTED",
                    )
                )
            )
            if branch_id:
                op_q = op_q.where(JournalEntry.branch_id == branch_id)
            if financial_year:
                op_q = op_q.where(JournalEntry.financial_year == financial_year)
            if as_of_date:
                op_q = op_q.where(JournalEntry.voucher_date <= as_of_date)
            opening_acc_ids = set(sess.scalars(op_q).all())

            asset_items = []
            liability_items = []
            equity_items = []
            total_assets = Decimal("0.00")
            total_liabilities = Decimal("0.00")
            total_equity = Decimal("0.00")

            for acc in accounts:
                m = map_by_acc.get(acc.id)
                nature = m.account_nature if m else "ASSET"
                if acc.id in opening_acc_ids:
                    base_op = Decimal("0.00")
                else:
                    base_op = round_money(m.opening_balance if m else Decimal("0.00"))
                op_type = m.opening_balance_type if m else "DR"
                net_op = base_op if op_type == "DR" else -base_op

                deb, cred = totals_map.get(acc.id, (Decimal("0.00"), Decimal("0.00")))
                net = net_op + (deb - cred)

                item = {
                    "account_id": acc.id,
                    "account_code": acc.code,
                    "account_name": acc.name,
                    "amount": str(abs(net)),
                }

                if nature == "ASSET":
                    if net != Decimal("0.00") or deb > 0:
                        total_assets += net
                        asset_items.append(item)
                elif nature == "LIABILITY":
                    # Normal credit balance
                    liab_val = -net
                    if liab_val != Decimal("0.00") or cred > 0:
                        total_liabilities += liab_val
                        liability_items.append(item)
                elif nature == "EQUITY":
                    eq_val = -net
                    if eq_val != Decimal("0.00") or cred > 0:
                        total_equity += eq_val
                        equity_items.append(item)

            # Check if financial year is closed
            resolved_fy = financial_year or self.derive_financial_year(as_of_date)
            closing_rec = sess.scalar(
                select(FinancialYearClosing).where(
                    and_(
                        FinancialYearClosing.company_id == company_id,
                        FinancialYearClosing.financial_year == resolved_fy,
                        FinancialYearClosing.status == "CLOSED",
                    )
                )
            )
            is_fy_closed = closing_rec is not None

            # Compute Net Profit from P&L up to as_of_date
            pnl = self.get_profit_and_loss(
                company_id=company_id,
                branch_id=branch_id,
                financial_year=financial_year,
                end_date=as_of_date,
                session=sess
            )
            operational_net_profit = Decimal(pnl["net_profit"])

            if is_fy_closed:
                # When FY is closed, net profit was already transferred to RETAINED_EARNINGS (Equity)
                # through the year-end closing journal entry.
                # Adding it again would double-count profit in equity.
                net_profit_period = Decimal("0.00")
            else:
                net_profit_period = operational_net_profit

            total_liab_and_equity = round_money(total_liabilities + total_equity + net_profit_period)
            total_assets_rounded = round_money(total_assets)
            difference = round_money(abs(total_assets_rounded - total_liab_and_equity))

            return {
                "assets": asset_items,
                "liabilities": liability_items,
                "equity": equity_items,
                "net_profit_for_period": str(operational_net_profit if not is_fy_closed else Decimal("0.00")),
                "operational_net_profit": str(operational_net_profit),
                "is_financial_year_closed": is_fy_closed,
                "total_assets": str(total_assets_rounded),
                "total_liabilities": str(total_liabilities),
                "total_equity": str(total_equity),
                "total_liabilities_and_equity": str(total_liab_and_equity),
                "difference": str(difference),
                "is_balanced": difference == Decimal("0.00"),
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def get_cash_book(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Calculates Cash Book statement for Cash-in-hand accounts."""
        def _execute(sess: Session):
            self.ensure_standard_accounts(company_id, session=sess)
            cash_acc = sess.scalar(
                select(Account).where(
                    and_(Account.company_id == company_id, Account.code == "CASH")
                )
            )
            if not cash_acc:
                raise AccountNotFoundError("Cash in Hand account ('CASH') not found.")
            return self.get_general_ledger(
                company_id=company_id,
                account_id=cash_acc.id,
                branch_id=branch_id,
                start_date=start_date,
                end_date=end_date,
                session=sess,
            )

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def get_bank_book(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        account_id: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Calculates Bank Book statement for Bank accounts."""
        def _execute(sess: Session):
            self.ensure_standard_accounts(company_id, session=sess)
            if account_id:
                bank_acc = sess.scalar(
                    select(Account).where(and_(Account.company_id == company_id, Account.id == account_id))
                )
            else:
                bank_acc = sess.scalar(
                    select(Account).where(
                        and_(Account.company_id == company_id, Account.account_type == "Bank")
                    )
                )

            if not bank_acc:
                return {
                    "account_code": "BANK",
                    "account_name": "Bank Accounts",
                    "opening_balance": "0.00",
                    "opening_balance_type": "Dr",
                    "period_debit": "0.00",
                    "period_credit": "0.00",
                    "closing_balance": "0.00",
                    "closing_balance_type": "Dr",
                    "entries": [],
                }

            return self.get_general_ledger(
                company_id=company_id,
                account_id=bank_acc.id,
                branch_id=branch_id,
                start_date=start_date,
                end_date=end_date,
                session=sess,
            )

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def get_receivables_report(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        as_of_date: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Calculates Accounts Receivable outstanding report across all customers (Sundry Debtors)."""
        def _execute(sess: Session):
            self.ensure_standard_accounts(company_id, session=sess)
            debtors = sess.scalars(
                select(Account).where(
                    and_(
                        Account.company_id == company_id,
                        Account.account_type.in_(["Debtor", "Both"]),
                        Account.is_active == True,
                    )
                ).order_by(Account.name.asc())
            ).all()

            results = []
            total_receivable = Decimal("0.00")

            for d in debtors:
                led = self.get_general_ledger(
                    company_id=company_id,
                    account_id=d.id,
                    branch_id=branch_id,
                    end_date=as_of_date,
                    session=sess,
                )
                closing_val = Decimal(led["closing_balance"])
                tag = led["closing_balance_type"]
                net_receivable = closing_val if tag == "Dr" else -closing_val

                if net_receivable != Decimal("0.00") or led["period_debit"] != "0.00":
                    total_receivable += net_receivable
                    results.append({
                        "customer_id": d.id,
                        "customer_code": d.code,
                        "customer_name": d.name,
                        "phone": d.phone,
                        "gstin": d.gstin,
                        "total_billed": led["period_debit"],
                        "total_paid": led["period_credit"],
                        "outstanding_amount": str(net_receivable),
                        "balance_type": tag,
                    })

            return {
                "customers": results,
                "total_receivable": str(total_receivable),
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def get_payables_report(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        as_of_date: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Calculates Accounts Payable outstanding report across all suppliers (Sundry Creditors)."""
        def _execute(sess: Session):
            self.ensure_standard_accounts(company_id, session=sess)
            creditors = sess.scalars(
                select(Account).where(
                    and_(
                        Account.company_id == company_id,
                        Account.account_type.in_(["Creditor", "Both"]),
                        Account.is_active == True,
                    )
                ).order_by(Account.name.asc())
            ).all()

            results = []
            total_payable = Decimal("0.00")

            for c in creditors:
                led = self.get_general_ledger(
                    company_id=company_id,
                    account_id=c.id,
                    branch_id=branch_id,
                    end_date=as_of_date,
                    session=sess,
                )
                closing_val = Decimal(led["closing_balance"])
                tag = led["closing_balance_type"]
                net_payable = closing_val if tag == "Cr" else -closing_val

                if net_payable != Decimal("0.00") or led["period_credit"] != "0.00":
                    total_payable += net_payable
                    results.append({
                        "supplier_id": c.id,
                        "supplier_code": c.code,
                        "supplier_name": c.name,
                        "phone": c.phone,
                        "gstin": c.gstin,
                        "total_purchased": led["period_credit"],
                        "total_paid": led["period_debit"],
                        "outstanding_amount": str(net_payable),
                        "balance_type": tag,
                    })

            return {
                "suppliers": results,
                "total_payable": str(total_payable),
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    # --------------------------------------------------------------------------
    # 5. Integration Helper Endpoints (Sales, Purchase, Payments, Receipts)
    # --------------------------------------------------------------------------

    def record_sales_journal(
        self,
        company_id: str,
        branch_id: str,
        invoice_id: str,
        invoice_number: str,
        invoice_date: str,
        customer_account_id: str,
        sales_amount: Union[Decimal, float, int, str],
        output_cgst: Union[Decimal, float, int, str] = Decimal("0.00"),
        output_sgst: Union[Decimal, float, int, str] = Decimal("0.00"),
        output_igst: Union[Decimal, float, int, str] = Decimal("0.00"),
        round_off: Union[Decimal, float, int, str] = Decimal("0.00"),
        is_cash_sale: bool = False,
        cash_or_bank_account_id: Optional[str] = None,
        narration: Optional[str] = None,
        user_id: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Integration helper for Sales module:
        - Debit Cash/Bank OR Customer Accounts Receivable
        - Credit Sales Account
        - Credit Output CGST, SGST, IGST
        - Credit/Debit Round Off Account
        """
        def _execute(sess: Session):
            self.ensure_standard_accounts(company_id, session=sess)
            accs = {a.code: a for a in sess.scalars(select(Account).where(Account.company_id == company_id)).all()}

            dr_account_id = cash_or_bank_account_id if (is_cash_sale and cash_or_bank_account_id) else (
                accs["CASH"].id if is_cash_sale else customer_account_id
            )

            s_amt = round_money(sales_amount)
            cgst = round_money(output_cgst)
            sgst = round_money(output_sgst)
            igst = round_money(output_igst)
            ro = round_money(round_off)

            total_due = round_money(s_amt + cgst + sgst + igst + ro)

            lines = [
                # Debit Customer or Cash
                {"account_id": dr_account_id, "debit": total_due, "credit": Decimal("0.00"), "narration": f"Invoice #{invoice_number}"},
                # Credit Sales
                {"account_id": accs["SALES"].id, "debit": Decimal("0.00"), "credit": s_amt, "narration": "Sales Revenue"},
            ]
            if cgst > Decimal("0.00"):
                lines.append({"account_id": accs["OUTPUT_CGST"].id, "debit": Decimal("0.00"), "credit": cgst, "narration": "Output CGST"})
            if sgst > Decimal("0.00"):
                lines.append({"account_id": accs["OUTPUT_SGST"].id, "debit": Decimal("0.00"), "credit": sgst, "narration": "Output SGST"})
            if igst > Decimal("0.00"):
                lines.append({"account_id": accs["OUTPUT_IGST"].id, "debit": Decimal("0.00"), "credit": igst, "narration": "Output IGST"})
            if ro != Decimal("0.00"):
                if ro > Decimal("0.00"):
                    # Credit Round Off
                    lines.append({"account_id": accs["ROUND_OFF"].id, "debit": Decimal("0.00"), "credit": ro, "narration": "Round Off"})
                else:
                    # Debit Round Off
                    lines.append({"account_id": accs["ROUND_OFF"].id, "debit": abs(ro), "credit": Decimal("0.00"), "narration": "Round Off"})

            idempotency_key = f"SALES_JOURNAL:{invoice_id}"
            return self.post_journal_entry(
                company_id=company_id,
                branch_id=branch_id,
                voucher_type="SALES",
                voucher_date=invoice_date,
                lines=lines,
                voucher_number=f"JV-{invoice_number}",
                narration=narration or f"Sales Invoice #{invoice_number}",
                reference_type="SALES_INVOICE",
                reference_id=invoice_id,
                idempotency_key=idempotency_key,
                posted_by=user_id,
                session=sess,
            )

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)


    def record_purchase_journal(
        self,
        company_id: str,
        branch_id: str,
        bill_id: str,
        bill_number: str,
        bill_date: str,
        supplier_account_id: str,
        purchase_amount: Union[Decimal, float, int, str],
        input_cgst: Union[Decimal, float, int, str] = Decimal("0.00"),
        input_sgst: Union[Decimal, float, int, str] = Decimal("0.00"),
        input_igst: Union[Decimal, float, int, str] = Decimal("0.00"),
        round_off: Union[Decimal, float, int, str] = Decimal("0.00"),
        is_cash_purchase: bool = False,
        cash_or_bank_account_id: Optional[str] = None,
        narration: Optional[str] = None,
        user_id: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Integration helper for Purchase module:
        - Debit Purchase Account
        - Debit Input CGST, SGST, IGST
        - Credit/Debit Round Off Account
        - Credit Cash/Bank OR Supplier Accounts Payable
        """
        def _execute(sess: Session):
            self.ensure_standard_accounts(company_id, session=sess)
            accs = {a.code: a for a in sess.scalars(select(Account).where(Account.company_id == company_id)).all()}

            cr_account_id = cash_or_bank_account_id if (is_cash_purchase and cash_or_bank_account_id) else (
                accs["CASH"].id if is_cash_purchase else supplier_account_id
            )

            p_amt = round_money(purchase_amount)
            cgst = round_money(input_cgst)
            sgst = round_money(input_sgst)
            igst = round_money(input_igst)
            ro = round_money(round_off)

            total_payable = round_money(p_amt + cgst + sgst + igst + ro)

            lines = [
                # Debit Purchase
                {"account_id": accs["PURCHASE"].id, "debit": p_amt, "credit": Decimal("0.00"), "narration": "Purchase Expense"},
            ]
            if cgst > Decimal("0.00"):
                lines.append({"account_id": accs["INPUT_CGST"].id, "debit": cgst, "credit": Decimal("0.00"), "narration": "Input CGST"})
            if sgst > Decimal("0.00"):
                lines.append({"account_id": accs["INPUT_SGST"].id, "debit": sgst, "credit": Decimal("0.00"), "narration": "Input SGST"})
            if igst > Decimal("0.00"):
                lines.append({"account_id": accs["INPUT_IGST"].id, "debit": igst, "credit": Decimal("0.00"), "narration": "Input IGST"})
            if ro != Decimal("0.00"):
                if ro > Decimal("0.00"):
                    # Debit Round Off
                    lines.append({"account_id": accs["ROUND_OFF"].id, "debit": ro, "credit": Decimal("0.00"), "narration": "Round Off"})
                else:
                    # Credit Round Off
                    lines.append({"account_id": accs["ROUND_OFF"].id, "debit": Decimal("0.00"), "credit": abs(ro), "narration": "Round Off"})

            # Credit Supplier or Cash
            lines.append({"account_id": cr_account_id, "debit": Decimal("0.00"), "credit": total_payable, "narration": f"Purchase Bill #{bill_number}"})

            idempotency_key = f"PURCHASE_JOURNAL:{bill_id}"
            return self.post_journal_entry(
                company_id=company_id,
                branch_id=branch_id,
                voucher_type="PURCHASE",
                voucher_date=bill_date,
                lines=lines,
                voucher_number=f"JV-PUR-{bill_number}",
                narration=narration or f"Purchase Bill #{bill_number}",
                reference_type="PURCHASE_BILL",
                reference_id=bill_id,
                idempotency_key=idempotency_key,
                posted_by=user_id,
                session=sess,
            )

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)


    def record_customer_receipt(
        self,
        company_id: str,
        branch_id: str,
        receipt_number: str,
        receipt_date: str,
        customer_account_id: str,
        cash_or_bank_account_id: str,
        amount: Union[Decimal, float, int, str],
        discount_amount: Union[Decimal, float, int, str] = Decimal("0.00"),
        narration: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        user_id: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Records receipt from customer:
        - Debit Cash or Bank Account
        - Debit Discount Allowed (if any)
        - Credit Customer Accounts Receivable
        """
        def _execute(sess: Session):
            self.ensure_standard_accounts(company_id, session=sess)
            amt = round_money(amount)
            disc = round_money(discount_amount)
            total_cr = round_money(amt + disc)

            lines = [
                {"account_id": cash_or_bank_account_id, "debit": amt, "credit": Decimal("0.00"), "narration": "Receipt received"},
            ]
            if disc > Decimal("0.00"):
                # Indirect expense: Discount Allowed
                accs = {a.code: a for a in sess.scalars(select(Account).where(Account.company_id == company_id)).all()}
                round_off_acc = accs.get("ROUND_OFF")
                lines.append({"account_id": round_off_acc.id, "debit": disc, "credit": Decimal("0.00"), "narration": "Discount Allowed"})

            lines.append({"account_id": customer_account_id, "debit": Decimal("0.00"), "credit": total_cr, "narration": f"Receipt #{receipt_number}"})

            return self.post_journal_entry(
                company_id=company_id,
                branch_id=branch_id,
                voucher_type="RECEIPT",
                voucher_date=receipt_date,
                lines=lines,
                voucher_number=f"REC-{receipt_number}",
                narration=narration or f"Customer Receipt #{receipt_number}",
                reference_type="CUSTOMER_RECEIPT",
                idempotency_key=idempotency_key,
                posted_by=user_id,
                session=sess,
            )

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)


    def record_supplier_payment(
        self,
        company_id: str,
        branch_id: str,
        payment_number: str,
        payment_date: str,
        supplier_account_id: str,
        cash_or_bank_account_id: str,
        amount: Union[Decimal, float, int, str],
        discount_amount: Union[Decimal, float, int, str] = Decimal("0.00"),
        narration: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        user_id: Optional[str] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Records payment to supplier:
        - Debit Supplier Accounts Payable
        - Credit Cash or Bank Account
        - Credit Discount Received (if any)
        """
        def _execute(sess: Session):
            self.ensure_standard_accounts(company_id, session=sess)
            amt = round_money(amount)
            disc = round_money(discount_amount)
            total_dr = round_money(amt + disc)

            lines = [
                {"account_id": supplier_account_id, "debit": total_dr, "credit": Decimal("0.00"), "narration": f"Payment #{payment_number}"},
                {"account_id": cash_or_bank_account_id, "debit": Decimal("0.00"), "credit": amt, "narration": "Payment disbursed"},
            ]
            if disc > Decimal("0.00"):
                accs = {a.code: a for a in sess.scalars(select(Account).where(Account.company_id == company_id)).all()}
                round_off_acc = accs.get("ROUND_OFF")
                lines.append({"account_id": round_off_acc.id, "debit": Decimal("0.00"), "credit": disc, "narration": "Discount Received"})

            return self.post_journal_entry(
                company_id=company_id,
                branch_id=branch_id,
                voucher_type="PAYMENT",
                voucher_date=payment_date,
                lines=lines,
                voucher_number=f"PAY-{payment_number}",
                narration=narration or f"Supplier Payment #{payment_number}",
                reference_type="SUPPLIER_PAYMENT",
                idempotency_key=idempotency_key,
                posted_by=user_id,
                session=sess,
            )

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)


    # --------------------------------------------------------------------------
    # Helper Serializers
    # --------------------------------------------------------------------------

    @staticmethod
    def _journal_to_dict(j: JournalEntry) -> Dict[str, Any]:
        """Serializes JournalEntry and its lines into dictionary format."""
        return {
            "id": j.id,
            "company_id": j.company_id,
            "branch_id": j.branch_id,
            "financial_year": j.financial_year,
            "voucher_number": j.voucher_number,
            "voucher_type": j.voucher_type,
            "voucher_date": j.voucher_date,
            "narration": j.narration,
            "total_debit": str(j.total_debit),
            "total_credit": str(j.total_credit),
            "status": j.status,
            "reference_type": j.reference_type,
            "reference_id": j.reference_id,
            "reversal_of_id": j.reversal_of_id,
            "reversed_by_id": j.reversed_by_id,
            "reversal_reason": j.reversal_reason,
            "idempotency_key": j.idempotency_key,
            "posted_by": j.posted_by,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "lines": [
                {
                    "id": line.id,
                    "line_number": line.line_number,
                    "account_id": line.account_id,
                    "account_code": line.account.code if line.account else None,
                    "account_name": line.account.name if line.account else None,
                    "debit": str(line.debit),
                    "credit": str(line.credit),
                    "narration": line.narration,
                    "party_type": line.party_type,
                    "party_id": line.party_id,
                }
                for line in (j.lines or [])
            ] if hasattr(j, "lines") and j.lines else [],
        }


# Global singleton instance
traditional_accounting_service = TraditionalAccountingService()
