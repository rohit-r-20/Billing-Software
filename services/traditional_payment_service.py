"""
Traditional Billing Payment & Customer Receipt Service.
Phase 3.3 — Anti-Matrix Billing V2 Core Backend Architecture.

Manages the complete lifecycle of Customer Receipts in Traditional Billing:
1. Multi-method receipt recording (Cash, Bank, UPI, Cheque, Card).
2. Atomic voucher numbering and multi-tenant scoping.
3. Dynamic invoice outstanding balance calculations without mutating SaleInvoice.
4. Partial and multi-invoice settlement and advance customer receipts.
5. Atomic double-entry accounting journal integration (Debit Cash/Bank, Credit AR).
6. Controlled immutable receipt reversals with automatic balance restoration.
7. Strict tenant isolation, period open validation, and tamper-resistant audit logging.
"""

import uuid
import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Union
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from db.traditional_database import (
    traditional_db_manager,
    TraditionalDatabaseManager,
)
from db.traditional_models import (
    CustomerReceipt,
    ReceiptAllocation,
    SupplierPayment,
    PaymentAllocation,
    SaleInvoice,
    Account,
    AccountGroup,
    AccountGroupMapping,
    Company,
    Branch,
    User,
    JournalEntry,
    JournalEntryLine,
    AuditLog,
    VoucherSequence,
    utc_now,
    ensure_utc,
)
from services.traditional_accounting_service import (
    TraditionalAccountingService,
    TraditionalAccountingError,
    ClosedPeriodError,
    AccountNotFoundError,
    DuplicateJournalError,
    round_money,
)
from core.logging_config import logger


# ==============================================================================
# Domain Exceptions
# ==============================================================================

class TraditionalPaymentError(Exception):
    """Base exception for traditional payment and receipt service."""
    pass


class CustomerReceiptNotFoundError(TraditionalPaymentError):
    """Raised when a customer receipt voucher is not found."""
    pass


class SupplierPaymentNotFoundError(TraditionalPaymentError):
    """Raised when a supplier payment voucher is not found."""
    pass


class InvalidCustomerAccountError(TraditionalPaymentError):
    """Raised when customer account is missing, inactive, or not a Debtor/Both account."""
    pass


class InvalidSupplierAccountError(TraditionalPaymentError):
    """Raised when supplier account is missing, inactive, or not a Creditor/Both account."""
    pass


class InvalidDepositAccountError(TraditionalPaymentError):
    """Raised when deposit account is missing, inactive, or not a Cash/Bank account."""
    pass


class InvalidSourceAccountError(TraditionalPaymentError):
    """Raised when source disbursement account is missing, inactive, or not a Cash/Bank account."""
    pass


class OverAllocationError(TraditionalPaymentError):
    """Raised when an allocation exceeds invoice outstanding balance or receipt amount."""
    pass


class InvoiceAlreadySettledError(TraditionalPaymentError):
    """Raised when an allocation is attempted on a fully settled invoice."""
    pass


class DuplicateReceiptError(TraditionalPaymentError):
    """Raised when voucher number or idempotency key collision occurs."""
    pass


class DuplicateReversalError(TraditionalPaymentError):
    """Raised when attempting to reverse an already reversed customer receipt."""
    pass


# ==============================================================================
# Traditional Payment Service
# ==============================================================================

class TraditionalPaymentService:
    """
    Core backend service managing Traditional Billing Payment & Customer Receipt transactions.
    Ensures absolute transaction atomicity, ledger integrity, and dual-database isolation.
    """

    def __init__(
        self,
        db_manager: Optional[TraditionalDatabaseManager] = None,
        accounting_service: Optional[TraditionalAccountingService] = None,
    ):
        self.db = db_manager or traditional_db_manager
        self.accounting_service = accounting_service or TraditionalAccountingService(db_manager=self.db)

    # --------------------------------------------------------------------------
    # Helper: Context Resolution & Validation
    # --------------------------------------------------------------------------

    def _resolve_branch_id(self, session: Session, company_id: str, branch_id: Optional[str] = None) -> str:
        """Resolves and validates branch ID for the company context."""
        if branch_id:
            bid = str(branch_id).strip()
            branch = session.scalar(
                select(Branch).where(and_(Branch.company_id == company_id, Branch.id == bid))
            )
            if branch:
                return branch.id

        # Fallback to default branch
        branch = session.scalar(
            select(Branch).where(Branch.company_id == company_id).order_by(Branch.code.asc())
        )
        if not branch:
            raise ValueError(f"No valid branch found for company '{company_id}'.")
        return branch.id

    def _validate_deposit_account(
        self, session: Session, company_id: str, deposit_account_id: str, payment_method: str
    ) -> Account:
        """
        Validates that deposit account exists, belongs to company, is active,
        and is an authorized Cash or Bank ledger account consistent with payment_method.
        """
        if not deposit_account_id:
            raise InvalidDepositAccountError("deposit_account_id is required.")

        acc = session.scalar(
            select(Account).where(and_(Account.company_id == company_id, Account.id == deposit_account_id))
        )
        if not acc:
            raise InvalidDepositAccountError(f"Deposit account '{deposit_account_id}' not found for company '{company_id}'.")

        if not acc.is_active:
            raise InvalidDepositAccountError(f"Deposit account '{acc.name}' ({acc.code}) is inactive.")

        # Inspect account group mapping
        mapping = session.scalar(
            select(AccountGroupMapping).where(
                and_(AccountGroupMapping.company_id == company_id, AccountGroupMapping.account_id == acc.id)
            )
        )
        group_code = None
        if mapping:
            grp = session.scalar(select(AccountGroup).where(AccountGroup.id == mapping.group_id))
            if grp:
                group_code = grp.code

        acc_type = (acc.account_type or "").capitalize()
        is_cash = group_code == "GRP_CASH" or acc_type == "Cash" or acc.code == "CASH"
        is_bank = group_code == "GRP_BANK" or acc_type == "Bank" or (acc.code or "").startswith("BANK")

        if not (is_cash or is_bank):
            raise InvalidDepositAccountError(
                f"Account '{acc.name}' ({acc.code}) is neither a Cash nor a Bank ledger account (type: {acc_type}, group: {group_code})."
            )

        pm = (payment_method or "CASH").strip().upper()
        if pm == "CASH" and not is_cash:
            raise InvalidDepositAccountError(
                f"Payment method 'CASH' requires a Cash-in-Hand ledger account, but '{acc.name}' is a Bank account."
            )
        if pm in ("CHEQUE", "NEFT_RTGS", "UPI", "CARD", "BANK", "IMPS") and not is_bank:
            raise InvalidDepositAccountError(
                f"Payment method '{pm}' requires a Bank ledger account, but '{acc.name}' is a Cash account."
            )

        return acc

    def _validate_customer_account(
        self, session: Session, company_id: str, customer_account_id: str
    ) -> Account:
        """Validates that customer account exists, belongs to company, is active, and is a Debtor/Both account."""
        if not customer_account_id:
            raise InvalidCustomerAccountError("customer_account_id is required.")

        acc = session.scalar(
            select(Account).where(and_(Account.company_id == company_id, Account.id == customer_account_id))
        )
        if not acc:
            raise InvalidCustomerAccountError(f"Customer account '{customer_account_id}' not found for company '{company_id}'.")

        if not acc.is_active:
            raise InvalidCustomerAccountError(f"Customer account '{acc.name}' ({acc.code}) is inactive.")

        acc_type = (acc.account_type or "").strip()
        if acc_type not in ("Debtor", "Both"):
            raise InvalidCustomerAccountError(
                f"Account '{acc.name}' ({acc.code}) is of type '{acc_type}'. Only 'Debtor' or 'Both' accounts can receive customer receipts."
            )

        return acc

    def _allocate_voucher_number(
        self, session: Session, company_id: str, branch_id: str, financial_year: str, series: str = "Main"
    ) -> str:
        """Atomically allocates the next sequential voucher number for customer receipts."""
        clean_series = series.strip() if series else "Main"

        seq_query = select(VoucherSequence).where(
            and_(
                VoucherSequence.company_id == company_id,
                VoucherSequence.branch_id == branch_id,
                VoucherSequence.financial_year == financial_year,
                VoucherSequence.series == f"REC_{clean_series}",
            )
        )
        if not self.db.is_sqlite:
            seq_query = seq_query.with_for_update()

        seq_row = session.scalar(seq_query)

        # Reconcile with highest existing receipt sequence
        max_existing = session.scalar(
            select(func.count(CustomerReceipt.id)).where(
                and_(
                    CustomerReceipt.company_id == company_id,
                    CustomerReceipt.financial_year == financial_year,
                )
            )
        ) or 0

        current_seq = seq_row.current_number if seq_row else 0
        allocated_seq = max(current_seq, max_existing, 0) + 1
        prefix = seq_row.prefix if seq_row and seq_row.prefix is not None else "REC-"
        padding = seq_row.padding if seq_row and seq_row.padding else 4
        vch_no = f"{prefix}{allocated_seq:0{padding}d}"

        if not seq_row:
            seq_row = VoucherSequence(
                id=str(uuid.uuid4()),
                company_id=company_id,
                branch_id=branch_id,
                financial_year=financial_year,
                series=f"REC_{clean_series}",
                current_number=allocated_seq,
                prefix=prefix,
                padding=padding,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(seq_row)
        else:
            seq_row.current_number = allocated_seq
            seq_row.updated_at = utc_now()

        session.flush()
        return vch_no

    def peek_next_receipt_number(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        financial_year: Optional[str] = None,
        series: str = "Main",
        prefix: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> str:
        """Inspects the next receipt voucher number without mutating sequence state."""
        def _execute(sess: Session):
            bid = branch_id or self._resolve_branch_id(sess, company_id, branch_id)
            fy = financial_year or self.accounting_service.derive_financial_year()
            clean_series = series.strip() if series else "Main"
            seq_row = sess.scalar(
                select(VoucherSequence).where(
                    and_(
                        VoucherSequence.company_id == company_id,
                        VoucherSequence.branch_id == bid,
                        VoucherSequence.financial_year == fy,
                        VoucherSequence.series == f"REC_{clean_series}",
                    )
                )
            )
            max_existing = sess.scalar(
                select(func.count(CustomerReceipt.id)).where(
                    and_(
                        CustomerReceipt.company_id == company_id,
                        CustomerReceipt.financial_year == fy,
                    )
                )
            ) or 0
            current_seq = seq_row.current_number if seq_row else 0
            allocated_seq = max(current_seq, max_existing, 0) + 1
            pref = prefix if prefix is not None else (seq_row.prefix if seq_row and seq_row.prefix is not None else "REC-")
            padding = seq_row.padding if seq_row and seq_row.padding else 4
            return f"{pref}{allocated_seq:0{padding}d}"

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    # --------------------------------------------------------------------------
    # 1. Authoritative Dynamic Outstanding Calculation
    # --------------------------------------------------------------------------

    def get_customer_invoice_outstanding(
        self, company_id: str, invoice_id: str, session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Calculates individual sales invoice outstanding balance dynamically:
        Outstanding = Invoice Grand Total - Valid Posted Allocations - Valid Discounts
        Excludes allocations belonging to REVERSED or CANCELLED receipts.
        """
        if not company_id or not invoice_id:
            raise ValueError("company_id and invoice_id are required.")

        def _execute(sess: Session):
            invoice = sess.scalar(
                select(SaleInvoice).where(
                    and_(SaleInvoice.company_id == company_id, SaleInvoice.id == invoice_id)
                )
            )
            if not invoice:
                raise ValueError(f"Sale invoice '{invoice_id}' not found for company '{company_id}'.")

            # Sum allocations where parent CustomerReceipt is POSTED
            alloc_query = (
                select(
                    func.coalesce(func.sum(ReceiptAllocation.allocated_amount), Decimal("0.00")),
                    func.coalesce(func.sum(ReceiptAllocation.discount_amount), Decimal("0.00")),
                )
                .join(CustomerReceipt, CustomerReceipt.id == ReceiptAllocation.receipt_id)
                .where(
                    and_(
                        ReceiptAllocation.invoice_id == invoice_id,
                        CustomerReceipt.company_id == company_id,
                        CustomerReceipt.status == "POSTED",
                    )
                )
            )
            res = sess.execute(alloc_query).first()
            total_allocated = Decimal(str(res[0])) if res else Decimal("0.00")
            total_discount = Decimal(str(res[1])) if res else Decimal("0.00")
            grand_total = Decimal(str(invoice.grand_total))
            outstanding = max(Decimal("0.00"), grand_total - total_allocated - total_discount)

            return {
                "invoice_id": invoice.id,
                "voucher_number": invoice.voucher_number,
                "vch_date": invoice.vch_date,
                "customer_account_id": invoice.account_id,
                "party_name": invoice.party_name,
                "grand_total": str(grand_total),
                "total_allocated": str(total_allocated),
                "total_discount": str(total_discount),
                "outstanding_amount": str(outstanding),
                "is_settled": outstanding == Decimal("0.00"),
                "status": invoice.status,
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def get_customer_outstanding(
        self,
        company_id: str,
        customer_account_id: str,
        as_of_date: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Calculates total outstanding for a customer across:
        1. General Ledger Net Closing Balance (Accounts Receivable Debits minus Credits).
        2. Dynamic sum of unpaid/partially paid sales invoices.
        3. Total unallocated advance receipts.
        """
        if not company_id or not customer_account_id:
            raise ValueError("company_id and customer_account_id are required.")

        def _execute(sess: Session):
            customer = self._validate_customer_account(sess, company_id, customer_account_id)

            # 1. General Ledger AR position
            led = self.accounting_service.get_general_ledger(
                company_id=company_id,
                account_id=customer_account_id,
                end_date=as_of_date,
                session=sess,
            )
            gl_closing = Decimal(led["closing_balance"])
            gl_type = led["closing_balance_type"]
            net_gl_outstanding = gl_closing if gl_type == "Dr" else -gl_closing

            # 2. Invoices with outstanding balances
            invoices = sess.scalars(
                select(SaleInvoice).where(
                    and_(
                        SaleInvoice.company_id == company_id,
                        SaleInvoice.account_id == customer_account_id,
                        SaleInvoice.status != "CANCELLED",
                    )
                ).order_by(SaleInvoice.created_at.asc())
            ).all()

            unpaid_invoices = []
            total_invoice_outstanding = Decimal("0.00")

            for inv in invoices:
                out = self.get_customer_invoice_outstanding(company_id, inv.id, session=sess)
                inv_out = Decimal(out["outstanding_amount"])
                if inv_out > Decimal("0.00"):
                    total_invoice_outstanding += inv_out
                    unpaid_invoices.append(out)

            # 3. Unallocated advance receipts
            advances_res = sess.scalars(
                select(CustomerReceipt).where(
                    and_(
                        CustomerReceipt.company_id == company_id,
                        CustomerReceipt.customer_account_id == customer_account_id,
                        CustomerReceipt.status == "POSTED",
                        CustomerReceipt.unallocated_amount > Decimal("0.00"),
                    )
                )
            ).all()

            total_advances = sum((Decimal(str(r.unallocated_amount)) for r in advances_res), Decimal("0.00"))

            return {
                "customer_account_id": customer.id,
                "customer_code": customer.code,
                "customer_name": customer.name,
                "net_ledger_outstanding": str(net_gl_outstanding),
                "balance_type": gl_type,
                "total_unpaid_invoices_amount": str(total_invoice_outstanding),
                "total_unallocated_advances": str(total_advances),
                "unpaid_invoices_count": len(unpaid_invoices),
                "unpaid_invoices": unpaid_invoices,
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    # --------------------------------------------------------------------------
    # 2. Customer Receipt Creation (Single Atomic Transaction)
    # --------------------------------------------------------------------------

    def create_customer_receipt(
        self,
        company_id: str,
        customer_account_id: str,
        deposit_account_id: str,
        total_amount: Union[Decimal, float, int, str],
        payment_method: str = "CASH",
        branch_id: Optional[str] = None,
        receipt_date: Optional[str] = None,
        voucher_number: Optional[str] = None,
        financial_year: Optional[str] = None,
        reference_number: Optional[str] = None,
        reference_date: Optional[str] = None,
        notes: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        allocations: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Creates a customer receipt voucher, processes line-item invoice allocations,
        calculates unallocated advances, and posts a balanced double-entry accounting journal
        all within a SINGLE atomic database transaction.
        """
        if not company_id:
            raise ValueError("company_id is required.")

        parsed_total = round_money(total_amount)
        if parsed_total <= Decimal("0.00"):
            raise ValueError(f"Total receipt amount must be strictly positive. Received: {total_amount}")

        clean_pm = (payment_method or "CASH").strip().upper()
        clean_date = str(receipt_date or utc_now().strftime("%d-%m-%Y")).strip()

        def _execute(sess: Session):
            # 1. Idempotency Check
            clean_idempotency = str(idempotency_key).strip() if idempotency_key else None
            if clean_idempotency:
                existing = sess.scalar(
                    select(CustomerReceipt).where(
                        and_(
                            CustomerReceipt.company_id == company_id,
                            CustomerReceipt.idempotency_key == clean_idempotency,
                        )
                    )
                )
                if existing:
                    logger.info(f"Customer receipt returning existing record via idempotency key '{clean_idempotency}'.")
                    return self._receipt_to_dict(existing, session=sess)

            # 2. Company & Branch Context Validation
            company = sess.scalar(select(Company).where(Company.id == company_id))
            if not company:
                raise ValueError(f"Company '{company_id}' not found.")
            resolved_branch_id = self._resolve_branch_id(sess, company_id, branch_id)

            # 3. Closed Accounting Period Validation
            self.accounting_service.validate_period_is_open(company_id, clean_date, session=sess)

            # 4. Financial Year Resolution
            fy = financial_year or self.accounting_service.derive_financial_year(
                clean_date, fallback_fy=company.fin_year
            )

            # 5. Master Account Validations
            cust_acc = self._validate_customer_account(sess, company_id, customer_account_id)
            dep_acc = self._validate_deposit_account(sess, company_id, deposit_account_id, clean_pm)

            # 6. Voucher Number Resolution & Uniqueness
            if voucher_number:
                vch_no = str(voucher_number).strip()
                dup = sess.scalar(
                    select(CustomerReceipt).where(
                        and_(
                            CustomerReceipt.company_id == company_id,
                            CustomerReceipt.financial_year == fy,
                            CustomerReceipt.voucher_number == vch_no,
                        )
                    )
                )
                if dup:
                    raise DuplicateReceiptError(
                        f"Receipt voucher number '{vch_no}' already exists for financial year '{fy}'."
                    )
            else:
                vch_no = self._allocate_voucher_number(sess, company_id, resolved_branch_id, fy)

            # 7. Invoice Allocation Validation & Summation
            total_allocated = Decimal("0.00")
            total_discount = Decimal("0.00")
            processed_allocations: List[Dict[str, Any]] = []
            seen_invoices = set()

            raw_allocations = allocations or []
            for idx, alloc in enumerate(raw_allocations, start=1):
                inv_id = str(alloc.get("invoice_id") or "").strip()
                if not inv_id:
                    raise ValueError(f"Allocation line {idx} is missing invoice_id.")

                if inv_id in seen_invoices:
                    raise ValueError(f"Duplicate allocation line for invoice '{inv_id}' in the same receipt.")
                seen_invoices.add(inv_id)

                inv_query = select(SaleInvoice).where(
                    and_(SaleInvoice.company_id == company_id, SaleInvoice.id == inv_id)
                )
                if not self.db.is_sqlite:
                    inv_query = inv_query.with_for_update()
                inv = sess.scalar(inv_query)
                if not inv:
                    raise ValueError(f"Invoice '{inv_id}' does not belong to company '{company_id}'.")

                if inv.account_id != customer_account_id:
                    raise ValueError(
                        f"Invoice '{inv.voucher_number}' belongs to customer '{inv.party_name}', "
                        f"not the paying customer '{cust_acc.name}'."
                    )

                if inv.status in ("CANCELLED", "VOID"):
                    raise ValueError(f"Invoice '{inv.voucher_number}' is {inv.status} and cannot be settled.")

                alloc_amt = round_money(alloc.get("allocated_amount", 0))
                disc_amt = round_money(alloc.get("discount_amount", 0))

                if alloc_amt <= Decimal("0.00"):
                    raise ValueError(f"Allocation amount for invoice '{inv.voucher_number}' must be strictly positive.")
                if disc_amt < Decimal("0.00"):
                    raise ValueError(f"Discount amount for invoice '{inv.voucher_number}' cannot be negative.")

                # Dynamic outstanding check inside transaction
                inv_out_data = self.get_customer_invoice_outstanding(company_id, inv_id, session=sess)
                current_outstanding = Decimal(inv_out_data["outstanding_amount"])

                if current_outstanding <= Decimal("0.00"):
                    raise InvoiceAlreadySettledError(f"Invoice '{inv.voucher_number}' is already fully settled.")

                if (alloc_amt + disc_amt) > current_outstanding:
                    raise OverAllocationError(
                        f"Allocation ({alloc_amt + disc_amt}) exceeds current outstanding balance "
                        f"({current_outstanding}) for invoice '{inv.voucher_number}'."
                    )

                total_allocated += alloc_amt
                total_discount += disc_amt

                processed_allocations.append({
                    "invoice_id": inv.id,
                    "allocated_amount": alloc_amt,
                    "discount_amount": disc_amt,
                })

            if total_allocated > parsed_total:
                raise OverAllocationError(
                    f"Total allocated amount ({total_allocated}) exceeds total receipt amount ({parsed_total})."
                )

            unallocated_amount = parsed_total - total_allocated

            # 8. Create CustomerReceipt Header
            receipt_id = str(uuid.uuid4())
            receipt = CustomerReceipt(
                id=receipt_id,
                company_id=company_id,
                branch_id=resolved_branch_id,
                financial_year=fy,
                voucher_number=vch_no,
                receipt_date=clean_date,
                customer_account_id=customer_account_id,
                deposit_account_id=deposit_account_id,
                payment_method=clean_pm,
                total_amount=parsed_total,
                allocated_amount=total_allocated,
                unallocated_amount=unallocated_amount,
                discount_amount=total_discount,
                reference_number=str(reference_number).strip() if reference_number else None,
                reference_date=str(reference_date).strip() if reference_date else None,
                notes=str(notes).strip() if notes else None,
                status="POSTED",
                idempotency_key=clean_idempotency,
                created_by=user_id,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            sess.add(receipt)
            sess.flush()

            # 9. Create ReceiptAllocation Records
            for p_alloc in processed_allocations:
                alloc_record = ReceiptAllocation(
                    id=str(uuid.uuid4()),
                    receipt_id=receipt_id,
                    invoice_id=p_alloc["invoice_id"],
                    allocated_amount=p_alloc["allocated_amount"],
                    discount_amount=p_alloc["discount_amount"],
                    created_by=user_id,
                    created_at=utc_now(),
                )
                sess.add(alloc_record)
            sess.flush()

            # 10. Atomic Double-Entry Accounting Journal Creation
            journal_res = self.accounting_service.record_customer_receipt(
                company_id=company_id,
                branch_id=resolved_branch_id,
                receipt_number=vch_no,
                receipt_date=clean_date,
                customer_account_id=customer_account_id,
                cash_or_bank_account_id=deposit_account_id,
                amount=parsed_total,
                discount_amount=total_discount,
                narration=notes or f"Customer Receipt #{vch_no} ({cust_acc.name})",
                idempotency_key=f"RECEIPT_JOURNAL:{receipt_id}",
                user_id=user_id,
                session=sess,  # <--- Atomic: Flushes to outer session without independent commit
            )
            receipt.journal_id = journal_res["id"]
            sess.flush()

            # 11. Create AuditLog Record
            payload = {
                "receipt_id": receipt_id,
                "voucher_number": vch_no,
                "customer_account_id": customer_account_id,
                "deposit_account_id": deposit_account_id,
                "amount": str(parsed_total),
                "allocated": str(total_allocated),
                "unallocated": str(unallocated_amount),
                "discount": str(total_discount),
                "journal_id": journal_res["id"],
            }
            audit = AuditLog(
                id=str(uuid.uuid4()),
                company_id=company_id,
                user_id=user_id,
                event_type="CUSTOMER_RECEIPT_CREATED",
                entity_type="CUSTOMER_RECEIPT",
                entity_id=receipt_id,
                payload_json=json.dumps(payload),
                created_at=utc_now(),
            )
            sess.add(audit)
            sess.flush()

            logger.info(f"Customer Receipt '{vch_no}' created and journalized atomically.")
            return self._receipt_to_dict(receipt, session=sess)

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)

    # --------------------------------------------------------------------------
    # 3. Customer Receipt Querying & Listing
    # --------------------------------------------------------------------------

    def get_customer_receipt(
        self, company_id: str, receipt_id: str, session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Retrieves a single customer receipt by ID."""
        if not company_id or not receipt_id:
            raise ValueError("company_id and receipt_id are required.")

        def _execute(sess: Session):
            rc = sess.scalar(
                select(CustomerReceipt).where(
                    and_(CustomerReceipt.company_id == company_id, CustomerReceipt.id == receipt_id)
                )
            )
            if not rc:
                raise CustomerReceiptNotFoundError(f"Customer receipt '{receipt_id}' not found.")
            return self._receipt_to_dict(rc, session=sess)

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def get_customer_receipt_details(
        self, company_id: str, receipt_id: str, session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Retrieves comprehensive customer receipt details with allocations and party metadata."""
        if not company_id or not receipt_id:
            raise ValueError("company_id and receipt_id are required.")

        def _execute(sess: Session):
            rc = sess.scalar(
                select(CustomerReceipt).where(
                    and_(CustomerReceipt.company_id == company_id, CustomerReceipt.id == receipt_id)
                )
            )
            if not rc:
                raise CustomerReceiptNotFoundError(f"Customer receipt '{receipt_id}' not found.")

            res = self._receipt_to_dict(rc, session=sess)
            res["customer_name"] = rc.customer_account.name if rc.customer_account else None
            res["customer_code"] = rc.customer_account.code if rc.customer_account else None
            res["deposit_account_name"] = rc.deposit_account.name if rc.deposit_account else None
            res["deposit_account_code"] = rc.deposit_account.code if rc.deposit_account else None
            return res

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def list_customer_receipts(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        customer_account_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        status: Optional[str] = None,
        payment_method: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Lists customer receipts with filtering and pagination."""
        if not company_id:
            raise ValueError("company_id is required.")

        cid = customer_account_id or customer_id

        def _execute(sess: Session):
            query = select(CustomerReceipt).where(CustomerReceipt.company_id == company_id)

            if branch_id:
                query = query.where(CustomerReceipt.branch_id == branch_id)
            if cid:
                query = query.where(CustomerReceipt.customer_account_id == cid)
            if from_date:
                query = query.where(CustomerReceipt.receipt_date >= from_date)
            if to_date:
                query = query.where(CustomerReceipt.receipt_date <= to_date)
            if status:
                query = query.where(CustomerReceipt.status == status.strip().upper())
            if payment_method:
                query = query.where(CustomerReceipt.payment_method == payment_method.strip().upper())
            if search:
                clean_search = f"%{search.strip()}%"
                query = query.outerjoin(Account, Account.id == CustomerReceipt.customer_account_id).where(
                    or_(
                        CustomerReceipt.voucher_number.ilike(clean_search),
                        CustomerReceipt.reference_number.ilike(clean_search),
                        Account.name.ilike(clean_search),
                        Account.code.ilike(clean_search),
                    )
                )

            total_count = sess.scalar(select(func.count()).select_from(query.subquery())) or 0
            receipts = sess.scalars(
                query.order_by(CustomerReceipt.created_at.desc()).limit(limit).offset(offset)
            ).all()

            return {
                "receipts": [self._receipt_to_dict(r, session=sess) for r in receipts],
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    # --------------------------------------------------------------------------
    # 4. Subsequent Invoice Allocation (Advance Receipt Application)
    # --------------------------------------------------------------------------

    def allocate_customer_receipt(
        self,
        company_id: str,
        receipt_id: str,
        allocations: List[Dict[str, Any]],
        user_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Applies unallocated advance funds from an existing posted receipt to unpaid invoices.
        Does not create duplicate accounting entries because advance was already credited to AR.
        """
        if not company_id or not receipt_id:
            raise ValueError("company_id and receipt_id are required.")
        if not allocations:
            raise ValueError("At least one allocation item is required.")

        def _execute(sess: Session):
            rc_query = select(CustomerReceipt).where(
                and_(CustomerReceipt.company_id == company_id, CustomerReceipt.id == receipt_id)
            )
            if not self.db.is_sqlite:
                rc_query = rc_query.with_for_update()
            receipt = sess.scalar(rc_query)
            if not receipt:
                raise CustomerReceiptNotFoundError(f"Customer receipt '{receipt_id}' not found.")

            if receipt.status != "POSTED":
                raise ValueError(f"Cannot allocate against receipt with status '{receipt.status}'.")

            unallocated_available = Decimal(str(receipt.unallocated_amount))
            if unallocated_available <= Decimal("0.00"):
                raise OverAllocationError("Customer receipt has no unallocated advance balance available.")

            total_new_allocated = Decimal("0.00")
            new_records: List[ReceiptAllocation] = []

            for idx, alloc in enumerate(allocations, start=1):
                inv_id = str(alloc.get("invoice_id") or "").strip()
                if not inv_id:
                    raise ValueError(f"Allocation line {idx} is missing invoice_id.")

                inv_query = select(SaleInvoice).where(
                    and_(SaleInvoice.company_id == company_id, SaleInvoice.id == inv_id)
                )
                if not self.db.is_sqlite:
                    inv_query = inv_query.with_for_update()
                inv = sess.scalar(inv_query)
                if not inv:
                    raise ValueError(f"Invoice '{inv_id}' does not belong to company '{company_id}'.")

                if inv.account_id != receipt.customer_account_id:
                    raise ValueError(
                        f"Invoice '{inv.voucher_number}' belongs to another customer, not receipt customer."
                    )

                if inv.status in ("CANCELLED", "VOID"):
                    raise ValueError(f"Invoice '{inv.voucher_number}' is {inv.status} and cannot be settled.")

                alloc_amt = round_money(alloc.get("allocated_amount", 0))
                disc_amt = round_money(alloc.get("discount_amount", 0))

                if alloc_amt <= Decimal("0.00"):
                    raise ValueError(f"Allocation amount must be strictly positive.")

                # Dynamic outstanding check
                inv_out_data = self.get_customer_invoice_outstanding(company_id, inv_id, session=sess)
                current_outstanding = Decimal(inv_out_data["outstanding_amount"])

                if (alloc_amt + disc_amt) > current_outstanding:
                    raise OverAllocationError(
                        f"Allocation ({alloc_amt + disc_amt}) exceeds invoice outstanding balance "
                        f"({current_outstanding}) for invoice '{inv.voucher_number}'."
                    )

                total_new_allocated += alloc_amt

                # Check if an allocation already exists for this (receipt, invoice)
                existing_alloc = sess.scalar(
                    select(ReceiptAllocation).where(
                        and_(
                            ReceiptAllocation.receipt_id == receipt.id,
                            ReceiptAllocation.invoice_id == inv.id,
                        )
                    )
                )
                if existing_alloc:
                    existing_alloc.allocated_amount += alloc_amt
                    existing_alloc.discount_amount += disc_amt
                else:
                    new_alloc = ReceiptAllocation(
                        id=str(uuid.uuid4()),
                        receipt_id=receipt.id,
                        invoice_id=inv.id,
                        allocated_amount=alloc_amt,
                        discount_amount=disc_amt,
                        created_by=user_id,
                        created_at=utc_now(),
                    )
                    sess.add(new_alloc)

            if total_new_allocated > unallocated_available:
                raise OverAllocationError(
                    f"Total allocations ({total_new_allocated}) exceed available unallocated receipt balance "
                    f"({unallocated_available})."
                )

            # Update receipt header balances
            receipt.allocated_amount += total_new_allocated
            receipt.unallocated_amount -= total_new_allocated
            receipt.updated_at = utc_now()
            sess.flush()

            # Audit Log
            audit = AuditLog(
                id=str(uuid.uuid4()),
                company_id=company_id,
                user_id=user_id,
                event_type="CUSTOMER_RECEIPT_ALLOCATED",
                entity_type="CUSTOMER_RECEIPT",
                entity_id=receipt.id,
                payload_json=f'{{"applied_amount":"{total_new_allocated}","remaining_unallocated":"{receipt.unallocated_amount}"}}',
                created_at=utc_now(),
            )
            sess.add(audit)
            sess.flush()

            return self._receipt_to_dict(receipt, session=sess)

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)

    # --------------------------------------------------------------------------
    # 5. Customer Receipt Reversal (Immutable Audit Trail)
    # --------------------------------------------------------------------------

    def reverse_customer_receipt(
        self,
        company_id: str,
        receipt_id: str,
        reversal_reason: str,
        user_id: Optional[str] = None,
        reversal_date: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Reverses a posted customer receipt:
        1. Validates receipt is POSTED and not already reversed.
        2. Posts an inverse compensating double-entry journal via TraditionalAccountingService.
        3. Marks CustomerReceipt.status = 'REVERSED'.
        4. Preserves allocation rows for audit trail while automatically restoring invoice outstanding balances.
        """
        if not company_id or not receipt_id:
            raise ValueError("company_id and receipt_id are required.")
        if not reversal_reason or not str(reversal_reason).strip():
            raise ValueError("reversal_reason is required to reverse a customer receipt.")

        clean_reason = str(reversal_reason).strip()

        def _execute(sess: Session):
            rc_query = select(CustomerReceipt).where(
                and_(CustomerReceipt.company_id == company_id, CustomerReceipt.id == receipt_id)
            )
            if not self.db.is_sqlite:
                rc_query = rc_query.with_for_update()
            receipt = sess.scalar(rc_query)
            if not receipt:
                raise CustomerReceiptNotFoundError(f"Customer receipt '{receipt_id}' not found.")

            if receipt.status == "REVERSED":
                raise DuplicateReversalError(f"Customer receipt '{receipt.voucher_number}' has already been reversed.")

            if receipt.status != "POSTED":
                raise ValueError(f"Cannot reverse customer receipt with status '{receipt.status}'.")

            rev_date = str(reversal_date or utc_now().strftime("%d-%m-%Y")).strip()
            self.accounting_service.validate_period_is_open(company_id, rev_date, session=sess)

            # Reverse the double-entry accounting journal
            reversal_journal_id = None
            if receipt.journal_id:
                rev_journal = self.accounting_service.reverse_journal_entry(
                    company_id=company_id,
                    journal_id=receipt.journal_id,
                    reversal_reason=clean_reason,
                    reversal_date=rev_date,
                    user_id=user_id,
                    session=sess,
                )
                reversal_journal_id = rev_journal["id"]

            # Update receipt status to REVERSED
            receipt.status = "REVERSED"
            receipt.reversal_reason = clean_reason
            receipt.updated_at = utc_now()
            sess.flush()

            # Audit Log
            audit = AuditLog(
                id=str(uuid.uuid4()),
                company_id=company_id,
                user_id=user_id,
                event_type="CUSTOMER_RECEIPT_REVERSED",
                entity_type="CUSTOMER_RECEIPT",
                entity_id=receipt.id,
                payload_json=f'{{"vch_no":"{receipt.voucher_number}","reason":"{clean_reason}","reversal_date":"{rev_date}","reversal_journal_id":"{reversal_journal_id}"}}',
                created_at=utc_now(),
            )
            sess.add(audit)
            sess.flush()

            logger.info(f"Customer receipt '{receipt.voucher_number}' reversed successfully.")
            result_dict = self._receipt_to_dict(receipt, session=sess)
            result_dict["reversal_journal_id"] = reversal_journal_id
            return result_dict

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)

    # --------------------------------------------------------------------------
    # Helper Serializers
    # --------------------------------------------------------------------------

    def _receipt_to_dict(self, receipt: CustomerReceipt, session: Optional[Session] = None) -> Dict[str, Any]:
        """Serializes CustomerReceipt and its allocations to a clean dictionary."""
        allocs = []
        if receipt.allocations:
            for a in receipt.allocations:
                allocs.append({
                    "id": a.id,
                    "invoice_id": a.invoice_id,
                    "allocated_amount": str(a.allocated_amount),
                    "discount_amount": str(a.discount_amount),
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                })

        return {
            "id": receipt.id,
            "company_id": receipt.company_id,
            "branch_id": receipt.branch_id,
            "financial_year": receipt.financial_year,
            "voucher_number": receipt.voucher_number,
            "receipt_voucher_number": receipt.voucher_number,
            "receipt_date": receipt.receipt_date,
            "customer_account_id": receipt.customer_account_id,
            "deposit_account_id": receipt.deposit_account_id,
            "payment_method": receipt.payment_method,
            "total_amount": str(receipt.total_amount),
            "allocated_amount": str(receipt.allocated_amount),
            "unallocated_amount": str(receipt.unallocated_amount),
            "discount_amount": str(receipt.discount_amount),
            "reference_number": receipt.reference_number,
            "reference_date": receipt.reference_date,
            "notes": receipt.notes,
            "journal_id": receipt.journal_id,
            "status": receipt.status,
            "reversal_of_id": receipt.reversal_of_id,
            "reversal_reason": receipt.reversal_reason,
            "idempotency_key": receipt.idempotency_key,
            "allocations": allocs,
            "created_by": receipt.created_by,
            "customer_name": receipt.customer_account.name if receipt.customer_account else None,
            "customer_code": receipt.customer_account.code if receipt.customer_account else None,
            "deposit_account_name": receipt.deposit_account.name if receipt.deposit_account else None,
            "deposit_account_code": receipt.deposit_account.code if receipt.deposit_account else None,
            "created_at": receipt.created_at.isoformat() if receipt.created_at else None,
            "updated_at": receipt.updated_at.isoformat() if receipt.updated_at else None,
        }

    # ==========================================================================
    # Supplier Payment Helpers & Validations
    # ==========================================================================

    def _validate_source_account(
        self, session: Session, company_id: str, source_account_id: str, payment_method: str
    ) -> Account:
        """
        Validates that disbursement source account exists, belongs to company, is active,
        and is an authorized Cash or Bank ledger account consistent with payment_method.
        """
        if not source_account_id:
            raise InvalidSourceAccountError("source_account_id is required.")

        acc = session.scalar(
            select(Account).where(and_(Account.company_id == company_id, Account.id == source_account_id))
        )
        if not acc:
            raise InvalidSourceAccountError(f"Source account '{source_account_id}' not found for company '{company_id}'.")

        if not acc.is_active:
            raise InvalidSourceAccountError(f"Source account '{acc.name}' ({acc.code}) is inactive.")

        mapping = session.scalar(
            select(AccountGroupMapping).where(
                and_(AccountGroupMapping.company_id == company_id, AccountGroupMapping.account_id == acc.id)
            )
        )
        group_code = None
        if mapping:
            grp = session.scalar(select(AccountGroup).where(AccountGroup.id == mapping.group_id))
            if grp:
                group_code = grp.code

        acc_type = (acc.account_type or "").capitalize()
        is_cash = group_code == "GRP_CASH" or acc_type == "Cash" or acc.code == "CASH"
        is_bank = group_code == "GRP_BANK" or acc_type == "Bank" or (acc.code or "").startswith("BANK")

        if not (is_cash or is_bank):
            raise InvalidSourceAccountError(
                f"Account '{acc.name}' ({acc.code}) is neither a Cash nor a Bank ledger account (type: {acc_type}, group: {group_code})."
            )

        pm = (payment_method or "CASH").strip().upper()
        if pm == "CASH" and not is_cash:
            raise InvalidSourceAccountError(
                f"Payment method 'CASH' requires a Cash-in-Hand ledger account, but '{acc.name}' is a Bank account."
            )
        if pm in ("CHEQUE", "NEFT_RTGS", "UPI", "CARD", "BANK", "IMPS") and not is_bank:
            raise InvalidSourceAccountError(
                f"Payment method '{pm}' requires a Bank ledger account, but '{acc.name}' is a Cash account."
            )

        return acc

    def _validate_supplier_account(
        self, session: Session, company_id: str, supplier_account_id: str
    ) -> Account:
        """Validates that supplier account exists, belongs to company, is active, and is a Creditor/Both account."""
        if not supplier_account_id:
            raise InvalidSupplierAccountError("supplier_account_id is required.")

        acc = session.scalar(
            select(Account).where(and_(Account.company_id == company_id, Account.id == supplier_account_id))
        )
        if not acc:
            raise InvalidSupplierAccountError(f"Supplier account '{supplier_account_id}' not found for company '{company_id}'.")

        if not acc.is_active:
            raise InvalidSupplierAccountError(f"Supplier account '{acc.name}' ({acc.code}) is inactive.")

        acc_type = (acc.account_type or "").strip()
        if acc_type not in ("Creditor", "Both"):
            raise InvalidSupplierAccountError(
                f"Account '{acc.name}' ({acc.code}) is of type '{acc_type}'. Only 'Creditor' or 'Both' accounts can receive supplier disbursements."
            )

        return acc

    def _allocate_payment_voucher_number(
        self, session: Session, company_id: str, branch_id: str, financial_year: str, series: str = "Main"
    ) -> str:
        """Atomically allocates the next sequential voucher number for supplier payments."""
        clean_series = series.strip() if series else "Main"

        seq_query = select(VoucherSequence).where(
            and_(
                VoucherSequence.company_id == company_id,
                VoucherSequence.branch_id == branch_id,
                VoucherSequence.financial_year == financial_year,
                VoucherSequence.series == f"PAY_{clean_series}",
            )
        )
        if not self.db.is_sqlite:
            seq_query = seq_query.with_for_update()

        seq_row = session.scalar(seq_query)

        max_existing = session.scalar(
            select(func.count(SupplierPayment.id)).where(
                and_(
                    SupplierPayment.company_id == company_id,
                    SupplierPayment.financial_year == financial_year,
                )
            )
        ) or 0

        current_seq = seq_row.current_number if seq_row else 0
        allocated_seq = max(current_seq, max_existing, 0) + 1
        prefix = seq_row.prefix if seq_row and seq_row.prefix is not None else "PAY-"
        padding = seq_row.padding if seq_row and seq_row.padding else 4
        vch_no = f"{prefix}{allocated_seq:0{padding}d}"

        if not seq_row:
            seq_row = VoucherSequence(
                id=str(uuid.uuid4()),
                company_id=company_id,
                branch_id=branch_id,
                financial_year=financial_year,
                series=f"PAY_{clean_series}",
                current_number=allocated_seq,
                prefix=prefix,
                padding=padding,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(seq_row)
        else:
            seq_row.current_number = allocated_seq
            seq_row.updated_at = utc_now()

        session.flush()
        return vch_no

    def peek_next_payment_number(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        financial_year: Optional[str] = None,
        series: str = "Main",
        prefix: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> str:
        """Inspects the next supplier payment voucher number without mutating sequence state."""
        def _execute(sess: Session):
            bid = branch_id or self._resolve_branch_id(sess, company_id, branch_id)
            fy = financial_year or self.accounting_service.derive_financial_year()
            clean_series = series.strip() if series else "Main"
            seq_row = sess.scalar(
                select(VoucherSequence).where(
                    and_(
                        VoucherSequence.company_id == company_id,
                        VoucherSequence.branch_id == bid,
                        VoucherSequence.financial_year == fy,
                        VoucherSequence.series == f"PAY_{clean_series}",
                    )
                )
            )
            max_existing = sess.scalar(
                select(func.count(SupplierPayment.id)).where(
                    and_(
                        SupplierPayment.company_id == company_id,
                        SupplierPayment.financial_year == fy,
                    )
                )
            ) or 0
            current_seq = seq_row.current_number if seq_row else 0
            allocated_seq = max(current_seq, max_existing, 0) + 1
            pref = prefix if prefix is not None else (seq_row.prefix if seq_row and seq_row.prefix is not None else "PAY-")
            padding = seq_row.padding if seq_row and seq_row.padding else 4
            return f"{pref}{allocated_seq:0{padding}d}"

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    # ==========================================================================
    # Supplier Payment Core Operations
    # ==========================================================================

    def create_supplier_payment(
        self,
        company_id: str,
        supplier_account_id: str,
        source_account_id: str,
        total_amount: Union[Decimal, float, int, str],
        payment_method: str = "CASH",
        branch_id: Optional[str] = None,
        payment_date: Optional[str] = None,
        voucher_number: Optional[str] = None,
        financial_year: Optional[str] = None,
        reference_number: Optional[str] = None,
        reference_date: Optional[str] = None,
        notes: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        allocations: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Creates a supplier payment voucher, processes purchase bill allocations / advance / on-account payments,
        and posts a balanced double-entry accounting journal all within a SINGLE atomic database transaction.
        """
        if not company_id:
            raise ValueError("company_id is required.")

        parsed_total = round_money(total_amount)
        if parsed_total <= Decimal("0.00"):
            raise ValueError(f"Total payment amount must be strictly positive. Received: {total_amount}")

        clean_pm = (payment_method or "CASH").strip().upper()
        clean_date = str(payment_date or utc_now().strftime("%d-%m-%Y")).strip()

        def _execute(sess: Session):
            # 1. Idempotency Check
            clean_idempotency = str(idempotency_key).strip() if idempotency_key else None
            if clean_idempotency:
                existing = sess.scalar(
                    select(SupplierPayment).where(
                        and_(
                            SupplierPayment.company_id == company_id,
                            SupplierPayment.idempotency_key == clean_idempotency,
                        )
                    )
                )
                if existing:
                    logger.info(f"Supplier payment returning existing record via idempotency key '{clean_idempotency}'.")
                    return self._payment_to_dict(existing, session=sess)

            # 2. Company & Branch Context Validation
            company = sess.scalar(select(Company).where(Company.id == company_id))
            if not company:
                raise ValueError(f"Company '{company_id}' not found.")
            resolved_branch_id = self._resolve_branch_id(sess, company_id, branch_id)

            # 3. Closed Accounting Period Validation
            self.accounting_service.validate_period_is_open(company_id, clean_date, session=sess)

            # 4. Financial Year Resolution
            fy = financial_year or self.accounting_service.derive_financial_year(
                clean_date, fallback_fy=company.fin_year
            )

            # 5. Master Account Validations
            supp_acc = self._validate_supplier_account(sess, company_id, supplier_account_id)
            src_acc = self._validate_source_account(sess, company_id, source_account_id, clean_pm)

            # 6. Voucher Number Resolution & Uniqueness
            if voucher_number:
                vch_no = str(voucher_number).strip()
                dup = sess.scalar(
                    select(SupplierPayment).where(
                        and_(
                            SupplierPayment.company_id == company_id,
                            SupplierPayment.financial_year == fy,
                            SupplierPayment.voucher_number == vch_no,
                        )
                    )
                )
                if dup:
                    raise DuplicateReceiptError(
                        f"Payment voucher number '{vch_no}' already exists for financial year '{fy}'."
                    )
            else:
                vch_no = self._allocate_payment_voucher_number(sess, company_id, resolved_branch_id, fy)

            # 7. Bill Allocations Processing & Validation
            total_allocated = Decimal("0.00")
            total_discount = Decimal("0.00")
            processed_allocations: List[Dict[str, Any]] = []
            seen_bills = set()

            raw_allocations = allocations or []
            for idx, alloc in enumerate(raw_allocations, start=1):
                alloc_amt = round_money(alloc.get("allocated_amount", 0))
                disc_amt = round_money(alloc.get("discount_amount", 0))

                if alloc_amt <= Decimal("0.00"):
                    raise ValueError(f"Allocation line {idx} amount must be strictly positive.")
                if disc_amt < Decimal("0.00"):
                    raise ValueError(f"Discount line {idx} amount cannot be negative.")

                # Cross-supplier check if specified in allocation dict
                alloc_supp_id = alloc.get("supplier_account_id")
                if alloc_supp_id and str(alloc_supp_id).strip() != supplier_account_id:
                    raise ValueError(f"Allocation line {idx} belongs to another supplier, not payee supplier.")

                # Cross-company check if specified in allocation dict
                alloc_co_id = alloc.get("company_id")
                if alloc_co_id and str(alloc_co_id).strip() != company_id:
                    raise ValueError(f"Allocation line {idx} belongs to another company.")

                bill_no = str(alloc.get("bill_number") or "").strip() or None
                pv_id = str(alloc.get("purchase_voucher_id") or "").strip() or None

                ref_key = pv_id or bill_no
                if ref_key:
                    if ref_key in seen_bills:
                        raise ValueError(f"Duplicate allocation line for bill '{ref_key}' in the same payment.")
                    seen_bills.add(ref_key)

                total_allocated += alloc_amt
                total_discount += disc_amt

                processed_allocations.append({
                    "purchase_voucher_id": pv_id,
                    "bill_number": bill_no,
                    "allocated_amount": alloc_amt,
                    "discount_amount": disc_amt,
                })

            if total_allocated > parsed_total:
                raise OverAllocationError(
                    f"Total allocated amount ({total_allocated}) exceeds total payment amount ({parsed_total})."
                )

            unallocated_amount = parsed_total - total_allocated

            # 8. Create SupplierPayment Header
            payment_id = str(uuid.uuid4())
            payment = SupplierPayment(
                id=payment_id,
                company_id=company_id,
                branch_id=resolved_branch_id,
                financial_year=fy,
                voucher_number=vch_no,
                payment_date=clean_date,
                supplier_account_id=supplier_account_id,
                source_account_id=source_account_id,
                payment_method=clean_pm,
                total_amount=parsed_total,
                allocated_amount=total_allocated,
                unallocated_amount=unallocated_amount,
                discount_amount=total_discount,
                reference_number=str(reference_number).strip() if reference_number else None,
                reference_date=str(reference_date).strip() if reference_date else None,
                notes=str(notes).strip() if notes else None,
                status="POSTED",
                idempotency_key=clean_idempotency,
                created_by=user_id,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            sess.add(payment)
            sess.flush()

            # 9. Create PaymentAllocation Records
            for p_alloc in processed_allocations:
                alloc_record = PaymentAllocation(
                    id=str(uuid.uuid4()),
                    payment_id=payment_id,
                    purchase_voucher_id=p_alloc["purchase_voucher_id"],
                    bill_number=p_alloc["bill_number"],
                    allocated_amount=p_alloc["allocated_amount"],
                    discount_amount=p_alloc["discount_amount"],
                    created_by=user_id,
                    created_at=utc_now(),
                )
                sess.add(alloc_record)
            sess.flush()

            # 10. Atomic Double-Entry Accounting Journal Creation
            journal_res = self.accounting_service.record_supplier_payment(
                company_id=company_id,
                branch_id=resolved_branch_id,
                payment_number=vch_no,
                payment_date=clean_date,
                supplier_account_id=supplier_account_id,
                cash_or_bank_account_id=source_account_id,
                amount=parsed_total,
                discount_amount=total_discount,
                narration=notes or f"Supplier Payment #{vch_no} ({supp_acc.name})",
                idempotency_key=f"PAYMENT_JOURNAL:{payment_id}",
                user_id=user_id,
                session=sess,  # <--- Atomic execution
            )
            payment.journal_id = journal_res["id"]
            sess.flush()

            # 11. Create AuditLog Record
            payload = {
                "payment_id": payment_id,
                "voucher_number": vch_no,
                "supplier_account_id": supplier_account_id,
                "source_account_id": source_account_id,
                "amount": str(parsed_total),
                "allocated": str(total_allocated),
                "unallocated": str(unallocated_amount),
                "discount": str(total_discount),
                "journal_id": journal_res["id"],
            }
            audit = AuditLog(
                id=str(uuid.uuid4()),
                company_id=company_id,
                user_id=user_id,
                event_type="SUPPLIER_PAYMENT_CREATED",
                entity_type="SUPPLIER_PAYMENT",
                entity_id=payment_id,
                payload_json=json.dumps(payload),
                created_at=utc_now(),
            )
            sess.add(audit)
            sess.flush()

            logger.info(f"Supplier Payment '{vch_no}' created and journalized atomically.")
            return self._payment_to_dict(payment, session=sess)

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)

    def get_supplier_payment(
        self, company_id: str, payment_id: str, session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Retrieves a single supplier payment by ID."""
        if not company_id or not payment_id:
            raise ValueError("company_id and payment_id are required.")

        def _execute(sess: Session):
            py = sess.scalar(
                select(SupplierPayment).where(
                    and_(SupplierPayment.company_id == company_id, SupplierPayment.id == payment_id)
                )
            )
            if not py:
                raise SupplierPaymentNotFoundError(f"Supplier payment '{payment_id}' not found.")
            return self._payment_to_dict(py, session=sess)

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def get_supplier_payment_details(
        self, company_id: str, payment_id: str, session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Retrieves comprehensive supplier payment details with party metadata and allocations."""
        if not company_id or not payment_id:
            raise ValueError("company_id and payment_id are required.")

        def _execute(sess: Session):
            py = sess.scalar(
                select(SupplierPayment).where(
                    and_(SupplierPayment.company_id == company_id, SupplierPayment.id == payment_id)
                )
            )
            if not py:
                raise SupplierPaymentNotFoundError(f"Supplier payment '{payment_id}' not found.")

            res = self._payment_to_dict(py, session=sess)
            res["supplier_name"] = py.supplier_account.name if py.supplier_account else None
            res["supplier_code"] = py.supplier_account.code if py.supplier_account else None
            res["source_account_name"] = py.source_account.name if py.source_account else None
            res["source_account_code"] = py.source_account.code if py.source_account else None
            return res

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def list_supplier_payments(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        supplier_account_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        status: Optional[str] = None,
        payment_method: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Lists supplier payments with filtering and pagination."""
        if not company_id:
            raise ValueError("company_id is required.")

        sid = supplier_account_id or supplier_id

        def _execute(sess: Session):
            query = select(SupplierPayment).where(SupplierPayment.company_id == company_id)

            if branch_id:
                query = query.where(SupplierPayment.branch_id == branch_id)
            if sid:
                query = query.where(SupplierPayment.supplier_account_id == sid)
            if from_date:
                query = query.where(SupplierPayment.payment_date >= from_date)
            if to_date:
                query = query.where(SupplierPayment.payment_date <= to_date)
            if status:
                query = query.where(SupplierPayment.status == status.strip().upper())
            if payment_method:
                query = query.where(SupplierPayment.payment_method == payment_method.strip().upper())
            if search:
                clean_search = f"%{search.strip()}%"
                query = query.outerjoin(Account, Account.id == SupplierPayment.supplier_account_id).where(
                    or_(
                        SupplierPayment.voucher_number.ilike(clean_search),
                        SupplierPayment.reference_number.ilike(clean_search),
                        Account.name.ilike(clean_search),
                        Account.code.ilike(clean_search),
                    )
                )

            total_count = sess.scalar(select(func.count()).select_from(query.subquery())) or 0
            payments = sess.scalars(
                query.order_by(SupplierPayment.created_at.desc()).limit(limit).offset(offset)
            ).all()

            return {
                "payments": [self._payment_to_dict(p, session=sess) for p in payments],
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def allocate_supplier_payment(
        self,
        company_id: str,
        payment_id: str,
        allocations: List[Dict[str, Any]],
        user_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Applies unallocated advance funds from an existing posted supplier payment to purchase bills.
        """
        if not company_id or not payment_id:
            raise ValueError("company_id and payment_id are required.")
        if not allocations:
            raise ValueError("At least one allocation item is required.")

        def _execute(sess: Session):
            p_query = select(SupplierPayment).where(
                and_(SupplierPayment.company_id == company_id, SupplierPayment.id == payment_id)
            )
            if not self.db.is_sqlite:
                p_query = p_query.with_for_update()
            payment = sess.scalar(p_query)
            if not payment:
                raise SupplierPaymentNotFoundError(f"Supplier payment '{payment_id}' not found.")

            if payment.status != "POSTED":
                raise ValueError(f"Cannot allocate against supplier payment with status '{payment.status}'.")

            unallocated_available = Decimal(str(payment.unallocated_amount))
            if unallocated_available <= Decimal("0.00"):
                raise OverAllocationError("Supplier payment has no unallocated advance balance available.")

            total_new_allocated = Decimal("0.00")
            for idx, alloc in enumerate(allocations, start=1):
                alloc_amt = round_money(alloc.get("allocated_amount", 0))
                disc_amt = round_money(alloc.get("discount_amount", 0))

                if alloc_amt <= Decimal("0.00"):
                    raise ValueError(f"Allocation line {idx} amount must be strictly positive.")

                # Cross-supplier check
                alloc_supp_id = alloc.get("supplier_account_id")
                if alloc_supp_id and str(alloc_supp_id).strip() != payment.supplier_account_id:
                    raise ValueError("Allocation belongs to another supplier, not payee supplier.")

                bill_no = str(alloc.get("bill_number") or "").strip() or None
                pv_id = str(alloc.get("purchase_voucher_id") or "").strip() or None

                total_new_allocated += alloc_amt

                new_alloc = PaymentAllocation(
                    id=str(uuid.uuid4()),
                    payment_id=payment.id,
                    purchase_voucher_id=pv_id,
                    bill_number=bill_no,
                    allocated_amount=alloc_amt,
                    discount_amount=disc_amt,
                    created_by=user_id,
                    created_at=utc_now(),
                )
                sess.add(new_alloc)

            if total_new_allocated > unallocated_available:
                raise OverAllocationError(
                    f"Total allocations ({total_new_allocated}) exceed available unallocated payment balance "
                    f"({unallocated_available})."
                )

            payment.allocated_amount += total_new_allocated
            payment.unallocated_amount -= total_new_allocated
            payment.updated_at = utc_now()
            sess.flush()

            # Audit Log
            audit = AuditLog(
                id=str(uuid.uuid4()),
                company_id=company_id,
                user_id=user_id,
                event_type="SUPPLIER_PAYMENT_ALLOCATED",
                entity_type="SUPPLIER_PAYMENT",
                entity_id=payment.id,
                payload_json=f'{{"applied_amount":"{total_new_allocated}","remaining_unallocated":"{payment.unallocated_amount}"}}',
                created_at=utc_now(),
            )
            sess.add(audit)
            sess.flush()

            return self._payment_to_dict(payment, session=sess)

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)

    def get_supplier_invoice_outstanding(
        self,
        company_id: str,
        bill_number_or_voucher_id: str,
        supplier_account_id: Optional[str] = None,
        total_bill_amount: Optional[Union[Decimal, float, int, str]] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Calculates dynamic outstanding for a supplier purchase bill / voucher:
        Outstanding = Total Bill Amount - Valid Posted Allocations - Valid Discounts
        Excludes allocations from REVERSED or CANCELLED supplier payments.
        """
        if not company_id or not bill_number_or_voucher_id:
            raise ValueError("company_id and bill_number_or_voucher_id are required.")

        ref = str(bill_number_or_voucher_id).strip()

        def _execute(sess: Session):
            query = (
                select(
                    func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0.00")),
                    func.coalesce(func.sum(PaymentAllocation.discount_amount), Decimal("0.00")),
                )
                .join(SupplierPayment, SupplierPayment.id == PaymentAllocation.payment_id)
                .where(
                    and_(
                        SupplierPayment.company_id == company_id,
                        SupplierPayment.status == "POSTED",
                        or_(
                            PaymentAllocation.bill_number == ref,
                            PaymentAllocation.purchase_voucher_id == ref,
                        ),
                    )
                )
            )
            if supplier_account_id:
                query = query.where(SupplierPayment.supplier_account_id == supplier_account_id)

            res = sess.execute(query).first()
            total_allocated = Decimal(str(res[0])) if res else Decimal("0.00")
            total_discount = Decimal(str(res[1])) if res else Decimal("0.00")

            bill_amt = round_money(total_bill_amount) if total_bill_amount is not None else None
            outstanding = max(Decimal("0.00"), bill_amt - total_allocated - total_discount) if bill_amt is not None else None

            return {
                "bill_reference": ref,
                "supplier_account_id": supplier_account_id,
                "total_bill_amount": str(bill_amt) if bill_amt is not None else None,
                "total_allocated": str(total_allocated),
                "total_discount": str(total_discount),
                "outstanding_amount": str(outstanding) if outstanding is not None else None,
                "is_settled": (outstanding == Decimal("0.00")) if outstanding is not None else False,
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def get_supplier_outstanding(
        self,
        company_id: str,
        supplier_account_id: str,
        as_of_date: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Calculates total Accounts Payable position for a supplier:
        1. General Ledger Net Closing Balance (Credits minus Debits).
        2. Total unallocated advance supplier payments.
        """
        if not company_id or not supplier_account_id:
            raise ValueError("company_id and supplier_account_id are required.")

        def _execute(sess: Session):
            supplier = self._validate_supplier_account(sess, company_id, supplier_account_id)

            # 1. General Ledger AP position
            led = self.accounting_service.get_general_ledger(
                company_id=company_id,
                account_id=supplier_account_id,
                end_date=as_of_date,
                session=sess,
            )
            gl_closing = Decimal(led["closing_balance"])
            gl_type = led["closing_balance_type"]
            net_gl_payable = gl_closing if gl_type == "Cr" else -gl_closing

            # 2. Unallocated advance payments
            advances_res = sess.scalars(
                select(SupplierPayment).where(
                    and_(
                        SupplierPayment.company_id == company_id,
                        SupplierPayment.supplier_account_id == supplier_account_id,
                        SupplierPayment.status == "POSTED",
                        SupplierPayment.unallocated_amount > Decimal("0.00"),
                    )
                )
            ).all()

            total_advances = sum((Decimal(str(p.unallocated_amount)) for p in advances_res), Decimal("0.00"))

            # 3. Allocations summary
            total_disbursed_period = Decimal(led.get("period_debit", "0.00"))
            total_purchased_period = Decimal(led.get("period_credit", "0.00"))

            return {
                "supplier_account_id": supplier.id,
                "supplier_code": supplier.code,
                "supplier_name": supplier.name,
                "net_ledger_payable": str(net_gl_payable),
                "balance_type": gl_type,
                "total_unallocated_advances": str(total_advances),
                "period_payments_disbursed": str(total_disbursed_period),
                "period_purchases_billed": str(total_purchased_period),
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def reverse_supplier_payment(
        self,
        company_id: str,
        payment_id: str,
        reversal_reason: str,
        user_id: Optional[str] = None,
        reversal_date: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Reverses a posted supplier payment:
        1. Validates payment is POSTED and not already reversed.
        2. Posts an inverse compensating double-entry journal via TraditionalAccountingService.
        3. Marks SupplierPayment.status = 'REVERSED'.
        4. Preserves allocation rows for audit trail while automatically restoring supplier payable balances.
        """
        if not company_id or not payment_id:
            raise ValueError("company_id and payment_id are required.")
        if not reversal_reason or not str(reversal_reason).strip():
            raise ValueError("reversal_reason is required to reverse a supplier payment.")

        clean_reason = str(reversal_reason).strip()

        def _execute(sess: Session):
            p_query = select(SupplierPayment).where(
                and_(SupplierPayment.company_id == company_id, SupplierPayment.id == payment_id)
            )
            if not self.db.is_sqlite:
                p_query = p_query.with_for_update()
            payment = sess.scalar(p_query)
            if not payment:
                raise SupplierPaymentNotFoundError(f"Supplier payment '{payment_id}' not found.")

            if payment.status == "REVERSED":
                raise DuplicateReversalError(f"Supplier payment '{payment.voucher_number}' has already been reversed.")

            if payment.status != "POSTED":
                raise ValueError(f"Cannot reverse supplier payment with status '{payment.status}'.")

            rev_date = str(reversal_date or utc_now().strftime("%d-%m-%Y")).strip()
            self.accounting_service.validate_period_is_open(company_id, rev_date, session=sess)

            # Reverse the double-entry accounting journal
            reversal_journal_id = None
            if payment.journal_id:
                rev_journal = self.accounting_service.reverse_journal_entry(
                    company_id=company_id,
                    journal_id=payment.journal_id,
                    reversal_reason=clean_reason,
                    reversal_date=rev_date,
                    user_id=user_id,
                    session=sess,
                )
                reversal_journal_id = rev_journal["id"]

            # Update payment status to REVERSED
            payment.status = "REVERSED"
            payment.reversal_reason = clean_reason
            payment.updated_at = utc_now()
            sess.flush()

            # Audit Log
            audit = AuditLog(
                id=str(uuid.uuid4()),
                company_id=company_id,
                user_id=user_id,
                event_type="SUPPLIER_PAYMENT_REVERSED",
                entity_type="SUPPLIER_PAYMENT",
                entity_id=payment.id,
                payload_json=f'{{"vch_no":"{payment.voucher_number}","reason":"{clean_reason}","reversal_date":"{rev_date}","reversal_journal_id":"{reversal_journal_id}"}}',
                created_at=utc_now(),
            )
            sess.add(audit)
            sess.flush()

            logger.info(f"Supplier payment '{payment.voucher_number}' reversed successfully.")
            result_dict = self._payment_to_dict(payment, session=sess)
            result_dict["reversal_journal_id"] = reversal_journal_id
            return result_dict

        if session is not None:
            return _execute(session)
        with self.db.session_scope() as sess:
            return _execute(sess)

    def _payment_to_dict(self, payment: SupplierPayment, session: Optional[Session] = None) -> Dict[str, Any]:
        """Serializes SupplierPayment and its allocations to a clean dictionary."""
        allocs = []
        if payment.allocations:
            for a in payment.allocations:
                allocs.append({
                    "id": a.id,
                    "purchase_voucher_id": a.purchase_voucher_id,
                    "bill_number": a.bill_number,
                    "allocated_amount": str(a.allocated_amount),
                    "discount_amount": str(a.discount_amount),
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                })

        return {
            "id": payment.id,
            "company_id": payment.company_id,
            "branch_id": payment.branch_id,
            "financial_year": payment.financial_year,
            "voucher_number": payment.voucher_number,
            "payment_voucher_number": payment.voucher_number,
            "payment_date": payment.payment_date,
            "supplier_account_id": payment.supplier_account_id,
            "source_account_id": payment.source_account_id,
            "payment_method": payment.payment_method,
            "total_amount": str(payment.total_amount),
            "allocated_amount": str(payment.allocated_amount),
            "unallocated_amount": str(payment.unallocated_amount),
            "discount_amount": str(payment.discount_amount),
            "reference_number": payment.reference_number,
            "reference_date": payment.reference_date,
            "notes": payment.notes,
            "journal_id": payment.journal_id,
            "status": payment.status,
            "reversal_of_id": payment.reversal_of_id,
            "reversal_reason": payment.reversal_reason,
            "idempotency_key": payment.idempotency_key,
            "allocations": allocs,
            "created_by": payment.created_by,
            "supplier_name": payment.supplier_account.name if payment.supplier_account else None,
            "supplier_code": payment.supplier_account.code if payment.supplier_account else None,
            "source_account_name": payment.source_account.name if payment.source_account else None,
            "source_account_code": payment.source_account.code if payment.source_account else None,
            "created_at": payment.created_at.isoformat() if payment.created_at else None,
            "updated_at": payment.updated_at.isoformat() if payment.updated_at else None,
        }

    # --------------------------------------------------------------------------
    # 7. Helper & Query Methods for UI & WebBridge Integration
    # --------------------------------------------------------------------------
    def list_cash_and_bank_accounts(
        self, company_id: str, session: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves active Cash-in-Hand and Bank ledger accounts for the company,
        suitable for selection in receipt and payment vouchers.
        """
        if not company_id:
            raise ValueError("company_id is required.")

        def _execute(sess: Session):
            self.accounting_service.ensure_standard_accounts(company_id, session=sess)
            stmt = (
                select(Account, AccountGroup.code.label("group_code"))
                .outerjoin(
                    AccountGroupMapping,
                    and_(AccountGroupMapping.account_id == Account.id, AccountGroupMapping.company_id == company_id),
                )
                .outerjoin(AccountGroup, AccountGroup.id == AccountGroupMapping.group_id)
                .where(and_(Account.company_id == company_id, Account.is_active == True))
                .order_by(Account.name.asc())
            )
            rows = sess.execute(stmt).all()
            res = []
            for acc, grp_code in rows:
                acc_type = (acc.account_type or "").capitalize()
                is_cash = grp_code == "GRP_CASH" or acc_type == "Cash" or acc.code == "CASH"
                is_bank = grp_code in ("GRP_BANK", "GRP_BANK_OD") or acc_type == "Bank" or (acc.code or "").startswith("BANK")
                if is_cash or is_bank:
                    res.append({
                        "id": acc.id,
                        "code": acc.code,
                        "name": acc.name,
                        "account_type": "Cash" if is_cash else "Bank",
                        "group_code": grp_code or ("GRP_CASH" if is_cash else "GRP_BANK"),
                    })
            return res

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    def get_customer_invoices_for_receipt(
        self,
        company_id: str,
        customer_id: str,
        as_of_date: Optional[str] = None,
        branch_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves unsettled and partially settled sales invoices for a customer,
        including current outstanding amounts ready for allocation.
        """
        out = self.get_customer_outstanding(
            company_id=company_id,
            customer_account_id=customer_id,
            as_of_date=as_of_date,
            session=session,
        )
        return out.get("unpaid_invoices", [])

    def get_supplier_bills_for_payment(
        self,
        company_id: str,
        supplier_id: str,
        as_of_date: Optional[str] = None,
        branch_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves purchase bills for a supplier. When Friend 2's Purchase module
        is pending, returns structured guidance enabling direct on-account payments.
        """
        return {
            "supplier_id": supplier_id,
            "bills": [],
            "message": "Purchase module integration pending (Friend 2). Direct on-account payments and supplier advances are fully enabled.",
        }

    def list_customers_outstanding(
        self,
        company_id: str,
        as_of_date: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Returns full Accounts Receivable outstanding report across all customers.
        """
        return self.accounting_service.get_receivables_report(
            company_id=company_id,
            as_of_date=as_of_date,
            session=session,
        )

    def list_suppliers_outstanding(
        self,
        company_id: str,
        as_of_date: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Returns full Accounts Payable outstanding report across all suppliers.
        """
        return self.accounting_service.get_payables_report(
            company_id=company_id,
            as_of_date=as_of_date,
            session=session,
        )

