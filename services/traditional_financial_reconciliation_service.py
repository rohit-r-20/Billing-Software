"""
Traditional Billing Financial Reconciliation & Subsystem Hardening Service.
Phase 3.5 — Anti-Matrix Billing V2 Core Backend Architecture.

Provides non-destructive, strictly read-only diagnostics to verify and enforce
reconciliation between:
1. Customer Receipts, Subledger Invoices, and General Ledger Accounts Receivable (AR).
2. Supplier Payments, Subledger Bills, and General Ledger Accounts Payable (AP).
3. Cash-in-Hand and Bank Ledger Accounts against posted payment and receipt journals.
4. Customer and Supplier Advance disbursements and allocations.
5. Orphan and duplicate double-entry accounting journal references.
6. Overall multi-tenant financial reconciliation health summary.
"""

import json
from decimal import Decimal
from typing import Dict, Any, List, Optional, Union
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import Session

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
    JournalEntry,
    JournalEntryLine,
    AuditLog,
)
from services.traditional_accounting_service import (
    TraditionalAccountingService,
    round_money,
)
from services.traditional_payment_service import (
    TraditionalPaymentService,
)
from core.logging_config import logger


# ==============================================================================
# Domain Exceptions
# ==============================================================================

def _normalize_date(d_str: Optional[str]) -> Optional[str]:
    """Converts DD-MM-YYYY or ISO date string to YYYY-MM-DD for reliable chronological comparison."""
    if not d_str:
        return None
    s = str(d_str).strip()
    if len(s) == 10 and s[2] == "-" and s[5] == "-":
        parts = s.split("-")
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return s


class FinancialReconciliationError(Exception):
    """Base exception for financial reconciliation diagnostics."""
    pass


class CompanyNotFoundError(FinancialReconciliationError):
    """Raised when the specified company is not found."""
    pass


class DiscrepancyFoundError(FinancialReconciliationError):
    """Raised when a reconciliation check detects a discrepancy in strict validation mode."""
    pass


# ==============================================================================
# Traditional Financial Reconciliation Service
# ==============================================================================

class TraditionalFinancialReconciliationService:
    """
    Dedicated read-only reconciliation and diagnostic engine for Traditional Billing.
    Enforces that General Ledger control accounts, subledger invoice/bill allocations,
    and cash/bank books reconcile with mathematical precision.
    """

    def __init__(
        self,
        db_manager: Optional[TraditionalDatabaseManager] = None,
        accounting_service: Optional[TraditionalAccountingService] = None,
        payment_service: Optional[TraditionalPaymentService] = None,
    ):
        self.db = db_manager or traditional_db_manager
        self.accounting_service = accounting_service or TraditionalAccountingService(db_manager=self.db)
        self.payment_service = payment_service or TraditionalPaymentService(
            db_manager=self.db, accounting_service=self.accounting_service
        )

    def _validate_company(self, session: Session, company_id: str) -> Company:
        if not company_id:
            raise ValueError("company_id is required.")
        company = session.scalar(select(Company).where(Company.id == company_id))
        if not company:
            raise CompanyNotFoundError(f"Company '{company_id}' not found.")
        return company

    # ==========================================================================
    # 1. Customer Accounts Receivable (AR) Reconciliation
    # ==========================================================================

    def reconcile_customer_ar(
        self,
        company_id: str,
        customer_account_id: Optional[str] = None,
        as_of_date: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Reconciles Customer Accounts Receivable:
        GL Control Account Balance (Debits minus Credits) must exactly equal:
        Sum(Unpaid/Partially Paid Invoices) - Sum(Unallocated Advance Receipts).

        Formula:
            Difference = GL Control Balance - (Invoice Outstanding - Unallocated Advances)
            Status = BALANCED if Difference == 0.00 else MISMATCHED
        """
        def _execute(sess: Session):
            self._validate_company(sess, company_id)

            query = select(Account).where(
                and_(
                    Account.company_id == company_id,
                    Account.account_type.in_(["Debtor", "Both"]),
                    Account.is_active == True,
                )
            )
            if customer_account_id:
                query = query.where(Account.id == customer_account_id)

            customers = sess.scalars(query.order_by(Account.name.asc())).all()

            results = []
            total_gl = Decimal("0.00")
            total_subledger = Decimal("0.00")
            mismatched_count = 0

            for cust in customers:
                # 1. GL Balance
                gl_data = self.accounting_service.get_general_ledger(
                    company_id=company_id,
                    account_id=cust.id,
                    end_date=as_of_date,
                    session=sess,
                )
                closing_val = Decimal(gl_data["closing_balance"])
                gl_tag = gl_data["closing_balance_type"]
                net_gl_ar = closing_val if gl_tag == "Dr" else -closing_val

                norm_as_of = _normalize_date(as_of_date)

                # 2. Dynamic Invoices Outstanding
                inv_query = select(SaleInvoice).where(
                    and_(
                        SaleInvoice.company_id == company_id,
                        SaleInvoice.account_id == cust.id,
                        SaleInvoice.status != "CANCELLED",
                    )
                )
                invoices = sess.scalars(inv_query).all()

                cust_invoice_outstanding = Decimal("0.00")
                unpaid_inv_count = 0
                for inv in invoices:
                    if norm_as_of and _normalize_date(inv.vch_date) > norm_as_of:
                        continue
                    inv_out_dict = self.payment_service.get_customer_invoice_outstanding(
                        company_id=company_id, invoice_id=inv.id, session=sess
                    )
                    inv_out = Decimal(inv_out_dict["outstanding_amount"])
                    if inv_out > Decimal("0.00"):
                        cust_invoice_outstanding += inv_out
                        unpaid_inv_count += 1

                # 3. Unallocated Advances
                advances = sess.scalars(
                    select(CustomerReceipt).where(
                        and_(
                            CustomerReceipt.company_id == company_id,
                            CustomerReceipt.customer_account_id == cust.id,
                            CustomerReceipt.status == "POSTED",
                            CustomerReceipt.unallocated_amount > Decimal("0.00"),
                        )
                    )
                ).all()
                if norm_as_of:
                    advances = [r for r in advances if _normalize_date(r.receipt_date) <= norm_as_of]
                total_advances = sum((Decimal(str(r.unallocated_amount)) for r in advances), Decimal("0.00"))

                # 4. Net Subledger Balance = Invoices - Advances
                subledger_net = cust_invoice_outstanding - total_advances
                diff = round_money(net_gl_ar - subledger_net)
                is_balanced = (diff == Decimal("0.00"))

                if not is_balanced:
                    mismatched_count += 1

                total_gl += net_gl_ar
                total_subledger += subledger_net

                results.append({
                    "customer_account_id": cust.id,
                    "customer_code": cust.code,
                    "customer_name": cust.name,
                    "gl_balance": str(net_gl_ar),
                    "gl_balance_type": gl_tag,
                    "subledger_invoices_outstanding": str(cust_invoice_outstanding),
                    "subledger_unallocated_advances": str(total_advances),
                    "subledger_net_balance": str(subledger_net),
                    "difference": str(diff),
                    "status": "BALANCED" if is_balanced else "MISMATCHED",
                    "unpaid_invoices_count": unpaid_inv_count,
                    "unallocated_receipts_count": len(advances),
                    "discrepancy_details": None if is_balanced else (
                        f"GL AR ({net_gl_ar}) differs from Subledger Net AR ({subledger_net}) by {diff}"
                    ),
                })

            total_diff = round_money(total_gl - total_subledger)
            overall_status = "BALANCED" if (total_diff == Decimal("0.00") and mismatched_count == 0) else "MISMATCHED"

            return {
                "company_id": company_id,
                "as_of_date": as_of_date,
                "status": overall_status,
                "total_gl_control_balance": str(total_gl),
                "total_subledger_balance": str(total_subledger),
                "total_difference": str(total_diff),
                "customer_count": len(customers),
                "mismatched_count": mismatched_count,
                "customers": results,
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    # ==========================================================================
    # 2. Supplier Accounts Payable (AP) Reconciliation
    # ==========================================================================

    def reconcile_supplier_ap(
        self,
        company_id: str,
        supplier_account_id: Optional[str] = None,
        as_of_date: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Reconciles Supplier Accounts Payable:
        GL Control Account Balance (Credits minus Debits) must exactly equal:
        Sum(Unpaid Purchase Bills) - Sum(Unallocated Advance Payments).

        Formula:
            Difference = GL Control Balance - (Bills Outstanding - Unallocated Advances)
            Status = BALANCED if Difference == 0.00 else MISMATCHED
        """
        def _execute(sess: Session):
            self._validate_company(sess, company_id)

            query = select(Account).where(
                and_(
                    Account.company_id == company_id,
                    Account.account_type.in_(["Creditor", "Both"]),
                    Account.is_active == True,
                )
            )
            if supplier_account_id:
                query = query.where(Account.id == supplier_account_id)

            suppliers = sess.scalars(query.order_by(Account.name.asc())).all()

            results = []
            total_gl = Decimal("0.00")
            total_subledger = Decimal("0.00")
            mismatched_count = 0

            for supp in suppliers:
                # 1. GL Balance
                gl_data = self.accounting_service.get_general_ledger(
                    company_id=company_id,
                    account_id=supp.id,
                    end_date=as_of_date,
                    session=sess,
                )
                closing_val = Decimal(gl_data["closing_balance"])
                gl_tag = gl_data["closing_balance_type"]
                net_gl_ap = closing_val if gl_tag == "Cr" else -closing_val

                norm_as_of = _normalize_date(as_of_date)

                # 2. Total Purchases Credited to Supplier (from PURCHASE or OPENING_BALANCE vouchers)
                purchase_lines_q = (
                    select(
                        JournalEntry.voucher_date,
                        JournalEntryLine.credit,
                    )
                    .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_id)
                    .where(
                        and_(
                            JournalEntry.company_id == company_id,
                            JournalEntry.status == "POSTED",
                            JournalEntry.voucher_type.in_(["PURCHASE", "OPENING_BALANCE"]),
                            JournalEntryLine.account_id == supp.id,
                        )
                    )
                )
                p_lines = sess.execute(purchase_lines_q).all()
                total_purchased_credit = Decimal("0.00")
                for pl in p_lines:
                    if norm_as_of and _normalize_date(pl[0]) > norm_as_of:
                        continue
                    total_purchased_credit += Decimal(str(pl[1]))

                # 3. Sum Allocations and Discounts against Supplier's Bills from POSTED Payments
                alloc_lines_q = (
                    select(
                        SupplierPayment.payment_date,
                        PaymentAllocation.allocated_amount,
                        PaymentAllocation.discount_amount,
                    )
                    .join(SupplierPayment, SupplierPayment.id == PaymentAllocation.payment_id)
                    .where(
                        and_(
                            SupplierPayment.company_id == company_id,
                            SupplierPayment.supplier_account_id == supp.id,
                            SupplierPayment.status == "POSTED",
                        )
                    )
                )
                alloc_lines = sess.execute(alloc_lines_q).all()
                total_allocated_to_bills = Decimal("0.00")
                total_discounts = Decimal("0.00")
                for al in alloc_lines:
                    if norm_as_of and _normalize_date(al[0]) > norm_as_of:
                        continue
                    total_allocated_to_bills += Decimal(str(al[1]))
                    total_discounts += Decimal(str(al[2]))

                bills_outstanding = max(
                    Decimal("0.00"), total_purchased_credit - total_allocated_to_bills - total_discounts
                )

                # 4. Unallocated Advance Payments
                advances = sess.scalars(
                    select(SupplierPayment).where(
                        and_(
                            SupplierPayment.company_id == company_id,
                            SupplierPayment.supplier_account_id == supp.id,
                            SupplierPayment.status == "POSTED",
                            SupplierPayment.unallocated_amount > Decimal("0.00"),
                        )
                    )
                ).all()
                if norm_as_of:
                    advances = [p for p in advances if _normalize_date(p.payment_date) <= norm_as_of]
                total_advances = sum((Decimal(str(p.unallocated_amount)) for p in advances), Decimal("0.00"))

                # 5. Net Subledger Balance = Bills Outstanding - Advances
                subledger_net = bills_outstanding - total_advances
                diff = round_money(net_gl_ap - subledger_net)
                is_balanced = (diff == Decimal("0.00"))

                if not is_balanced:
                    mismatched_count += 1

                total_gl += net_gl_ap
                total_subledger += subledger_net

                results.append({
                    "supplier_account_id": supp.id,
                    "supplier_code": supp.code,
                    "supplier_name": supp.name,
                    "gl_balance": str(net_gl_ap),
                    "gl_balance_type": gl_tag,
                    "subledger_bills_outstanding": str(bills_outstanding),
                    "subledger_unallocated_advances": str(total_advances),
                    "subledger_net_balance": str(subledger_net),
                    "difference": str(diff),
                    "status": "BALANCED" if is_balanced else "MISMATCHED",
                    "unallocated_payments_count": len(advances),
                    "discrepancy_details": None if is_balanced else (
                        f"GL AP ({net_gl_ap}) differs from Subledger Net AP ({subledger_net}) by {diff}"
                    ),
                })

            total_diff = round_money(total_gl - total_subledger)
            overall_status = "BALANCED" if (total_diff == Decimal("0.00") and mismatched_count == 0) else "MISMATCHED"

            return {
                "company_id": company_id,
                "as_of_date": as_of_date,
                "status": overall_status,
                "total_gl_control_balance": str(total_gl),
                "total_subledger_balance": str(total_subledger),
                "total_difference": str(total_diff),
                "supplier_count": len(suppliers),
                "mismatched_count": mismatched_count,
                "suppliers": results,
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    # ==========================================================================
    # 3. Cash and Bank Accounts Reconciliation
    # ==========================================================================

    def reconcile_cash_and_bank(
        self,
        company_id: str,
        account_id: Optional[str] = None,
        as_of_date: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Reconciles Cash and Bank ledger accounts against posted customer receipts,
        supplier payments, and their respective double-entry general ledger impacts.
        Verifies that every voucher has an intact, balanced, and matching journal entry.
        """
        def _execute(sess: Session):
            self._validate_company(sess, company_id)

            # Discover Cash and Bank accounts
            query = select(Account).where(
                and_(
                    Account.company_id == company_id,
                    Account.is_active == True,
                    or_(
                        Account.account_type.in_(["Cash", "Bank"]),
                        Account.code == "CASH",
                        Account.code.like("BANK%"),
                    ),
                )
            )
            if account_id:
                query = query.where(Account.id == account_id)

            accounts = sess.scalars(query.order_by(Account.code.asc())).all()

            results = []
            mismatched_count = 0

            for acc in accounts:
                gl_data = self.accounting_service.get_general_ledger(
                    company_id=company_id,
                    account_id=acc.id,
                    end_date=as_of_date,
                    session=sess,
                )
                gl_closing = Decimal(gl_data["closing_balance"])
                gl_type = gl_data["closing_balance_type"]
                net_gl = gl_closing if gl_type == "Dr" else -gl_closing

                discrepancies: List[str] = []

                # Audit Customer Receipts deposited to this account
                receipts = sess.scalars(
                    select(CustomerReceipt).where(
                        and_(
                            CustomerReceipt.company_id == company_id,
                            CustomerReceipt.deposit_account_id == acc.id,
                        )
                    )
                ).all()

                tot_rc_posted = Decimal("0.00")
                tot_rc_reversed = Decimal("0.00")

                for r in receipts:
                    if r.status == "POSTED":
                        tot_rc_posted += Decimal(str(r.total_amount))
                        # Verify GL journal exists and debits this account
                        if not r.journal_id:
                            discrepancies.append(f"Receipt '{r.voucher_number}' has status POSTED but missing journal_id.")
                        else:
                            jrn = sess.scalar(select(JournalEntry).where(JournalEntry.id == r.journal_id))
                            if not jrn:
                                discrepancies.append(f"Receipt '{r.voucher_number}' references non-existent journal '{r.journal_id}'.")
                            elif jrn.status != "POSTED":
                                discrepancies.append(f"Receipt '{r.voucher_number}' journal is in status '{jrn.status}', expected POSTED.")
                            else:
                                match_line = any(
                                    line.account_id == acc.id and Decimal(str(line.debit)) == Decimal(str(r.total_amount))
                                    for line in jrn.lines
                                )
                                if not match_line:
                                    discrepancies.append(
                                        f"Receipt '{r.voucher_number}' journal lines do not debit account '{acc.code}' for {r.total_amount}."
                                    )
                    elif r.status == "REVERSED":
                        tot_rc_reversed += Decimal(str(r.total_amount))

                # Audit Supplier Payments disbursed from this account
                payments = sess.scalars(
                    select(SupplierPayment).where(
                        and_(
                            SupplierPayment.company_id == company_id,
                            SupplierPayment.source_account_id == acc.id,
                        )
                    )
                ).all()

                tot_pay_posted = Decimal("0.00")
                tot_pay_reversed = Decimal("0.00")

                for p in payments:
                    if p.status == "POSTED":
                        tot_pay_posted += Decimal(str(p.total_amount))
                        if not p.journal_id:
                            discrepancies.append(f"Payment '{p.voucher_number}' has status POSTED but missing journal_id.")
                        else:
                            jrn = sess.scalar(select(JournalEntry).where(JournalEntry.id == p.journal_id))
                            if not jrn:
                                discrepancies.append(f"Payment '{p.voucher_number}' references non-existent journal '{p.journal_id}'.")
                            elif jrn.status != "POSTED":
                                discrepancies.append(f"Payment '{p.voucher_number}' journal is in status '{jrn.status}', expected POSTED.")
                            else:
                                match_line = any(
                                    line.account_id == acc.id and Decimal(str(line.credit)) == Decimal(str(p.total_amount))
                                    for line in jrn.lines
                                )
                                if not match_line:
                                    discrepancies.append(
                                        f"Payment '{p.voucher_number}' journal lines do not credit account '{acc.code}' for {p.total_amount}."
                                    )
                    elif p.status == "REVERSED":
                        tot_pay_reversed += Decimal(str(p.total_amount))

                is_balanced = (len(discrepancies) == 0)
                if not is_balanced:
                    mismatched_count += 1

                results.append({
                    "account_id": acc.id,
                    "account_code": acc.code,
                    "account_name": acc.name,
                    "account_type": acc.account_type,
                    "gl_closing_balance": str(net_gl),
                    "gl_balance_type": gl_type,
                    "period_debit": gl_data.get("period_debit", "0.00"),
                    "period_credit": gl_data.get("period_credit", "0.00"),
                    "total_receipts_posted": str(tot_rc_posted),
                    "total_receipts_reversed": str(tot_rc_reversed),
                    "total_payments_posted": str(tot_pay_posted),
                    "total_payments_reversed": str(tot_pay_reversed),
                    "status": "BALANCED" if is_balanced else "MISMATCHED",
                    "discrepancies": discrepancies,
                })

            overall_status = "BALANCED" if mismatched_count == 0 else "MISMATCHED"

            return {
                "company_id": company_id,
                "as_of_date": as_of_date,
                "status": overall_status,
                "account_count": len(accounts),
                "mismatched_count": mismatched_count,
                "accounts": results,
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    # ==========================================================================
    # 4. Customer Advances Integrity Reconciliation
    # ==========================================================================

    def reconcile_customer_advances(
        self,
        company_id: str,
        customer_account_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Reconciles customer advance receipts:
        1. Verifies allocated_amount + unallocated_amount == total_amount for all receipts.
        2. Verifies sum of line allocations == allocated_amount.
        3. Verifies that unallocated amounts are non-negative.
        """
        def _execute(sess: Session):
            self._validate_company(sess, company_id)

            query = select(CustomerReceipt).where(
                and_(
                    CustomerReceipt.company_id == company_id,
                    CustomerReceipt.status == "POSTED",
                )
            )
            if customer_account_id:
                query = query.where(CustomerReceipt.customer_account_id == customer_account_id)

            receipts = sess.scalars(query).all()

            violations: List[Dict[str, Any]] = []
            total_unallocated = Decimal("0.00")
            advance_receipts_count = 0

            for r in receipts:
                tot = Decimal(str(r.total_amount))
                alloc = Decimal(str(r.allocated_amount))
                unalloc = Decimal(str(r.unallocated_amount))

                # Sum of actual allocation child records
                actual_alloc_sum = sess.scalar(
                    select(func.coalesce(func.sum(ReceiptAllocation.allocated_amount), Decimal("0.00"))).where(
                        ReceiptAllocation.receipt_id == r.id
                    )
                ) or Decimal("0.00")
                actual_alloc_sum = Decimal(str(actual_alloc_sum))

                # Invariant 1: alloc + unalloc == tot
                if round_money(alloc + unalloc) != tot:
                    violations.append({
                        "receipt_id": r.id,
                        "voucher_number": r.voucher_number,
                        "customer_account_id": r.customer_account_id,
                        "total_amount": str(tot),
                        "allocated_amount": str(alloc),
                        "unallocated_amount": str(unalloc),
                        "sum_of_allocations": str(actual_alloc_sum),
                        "violation_type": "HEADER_BALANCE_MISMATCH",
                    })

                # Invariant 2: sum of child allocations == allocated_amount
                if round_money(actual_alloc_sum) != alloc:
                    violations.append({
                        "receipt_id": r.id,
                        "voucher_number": r.voucher_number,
                        "customer_account_id": r.customer_account_id,
                        "total_amount": str(tot),
                        "allocated_amount": str(alloc),
                        "unallocated_amount": str(unalloc),
                        "sum_of_allocations": str(actual_alloc_sum),
                        "violation_type": "ALLOCATION_SUM_MISMATCH",
                    })

                # Invariant 3: non-negative balances
                if unalloc < Decimal("0.00") or alloc < Decimal("0.00"):
                    violations.append({
                        "receipt_id": r.id,
                        "voucher_number": r.voucher_number,
                        "customer_account_id": r.customer_account_id,
                        "total_amount": str(tot),
                        "allocated_amount": str(alloc),
                        "unallocated_amount": str(unalloc),
                        "sum_of_allocations": str(actual_alloc_sum),
                        "violation_type": "NEGATIVE_BALANCE_ERROR",
                    })

                if unalloc > Decimal("0.00"):
                    total_unallocated += unalloc
                    advance_receipts_count += 1

            status = "BALANCED" if len(violations) == 0 else "MISMATCHED"

            return {
                "company_id": company_id,
                "status": status,
                "total_advance_receipts_count": advance_receipts_count,
                "total_unallocated_advances": str(total_unallocated),
                "violations_count": len(violations),
                "violations": violations,
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    # ==========================================================================
    # 5. Supplier Advances Integrity Reconciliation
    # ==========================================================================

    def reconcile_supplier_advances(
        self,
        company_id: str,
        supplier_account_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Reconciles supplier advance disbursements:
        1. Verifies allocated_amount + unallocated_amount == total_amount for all payments.
        2. Verifies sum of line allocations == allocated_amount.
        3. Verifies that unallocated amounts are non-negative.
        """
        def _execute(sess: Session):
            self._validate_company(sess, company_id)

            query = select(SupplierPayment).where(
                and_(
                    SupplierPayment.company_id == company_id,
                    SupplierPayment.status == "POSTED",
                )
            )
            if supplier_account_id:
                query = query.where(SupplierPayment.supplier_account_id == supplier_account_id)

            payments = sess.scalars(query).all()

            violations: List[Dict[str, Any]] = []
            total_unallocated = Decimal("0.00")
            advance_payments_count = 0

            for p in payments:
                tot = Decimal(str(p.total_amount))
                alloc = Decimal(str(p.allocated_amount))
                unalloc = Decimal(str(p.unallocated_amount))

                actual_alloc_sum = sess.scalar(
                    select(func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0.00"))).where(
                        PaymentAllocation.payment_id == p.id
                    )
                ) or Decimal("0.00")
                actual_alloc_sum = Decimal(str(actual_alloc_sum))

                # Invariant 1: alloc + unalloc == tot
                if round_money(alloc + unalloc) != tot:
                    violations.append({
                        "payment_id": p.id,
                        "voucher_number": p.voucher_number,
                        "supplier_account_id": p.supplier_account_id,
                        "total_amount": str(tot),
                        "allocated_amount": str(alloc),
                        "unallocated_amount": str(unalloc),
                        "sum_of_allocations": str(actual_alloc_sum),
                        "violation_type": "HEADER_BALANCE_MISMATCH",
                    })

                # Invariant 2: sum of child allocations == allocated_amount
                if round_money(actual_alloc_sum) != alloc:
                    violations.append({
                        "payment_id": p.id,
                        "voucher_number": p.voucher_number,
                        "supplier_account_id": p.supplier_account_id,
                        "total_amount": str(tot),
                        "allocated_amount": str(alloc),
                        "unallocated_amount": str(unalloc),
                        "sum_of_allocations": str(actual_alloc_sum),
                        "violation_type": "ALLOCATION_SUM_MISMATCH",
                    })

                # Invariant 3: non-negative balances
                if unalloc < Decimal("0.00") or alloc < Decimal("0.00"):
                    violations.append({
                        "payment_id": p.id,
                        "voucher_number": p.voucher_number,
                        "supplier_account_id": p.supplier_account_id,
                        "total_amount": str(tot),
                        "allocated_amount": str(alloc),
                        "unallocated_amount": str(unalloc),
                        "sum_of_allocations": str(actual_alloc_sum),
                        "violation_type": "NEGATIVE_BALANCE_ERROR",
                    })

                if unalloc > Decimal("0.00"):
                    total_unallocated += unalloc
                    advance_payments_count += 1

            status = "BALANCED" if len(violations) == 0 else "MISMATCHED"

            return {
                "company_id": company_id,
                "status": status,
                "total_advance_payments_count": advance_payments_count,
                "total_unallocated_advances": str(total_unallocated),
                "violations_count": len(violations),
                "violations": violations,
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    # ==========================================================================
    # 6. Orphan and Duplicate Journal Reference Audit
    # ==========================================================================

    def detect_orphan_or_duplicate_journals(
        self,
        company_id: str,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Audits integrity of voucher-journal relationships:
        1. Identifies customer receipts or supplier payments referencing nonexistent journals.
        2. Identifies customer receipts or supplier payments with missing journal IDs.
        3. Identifies duplicate journal ID references across different vouchers.
        4. Identifies orphan receipt/payment journal entries with no referencing voucher.
        """
        def _execute(sess: Session):
            self._validate_company(sess, company_id)

            orphan_receipts: List[str] = []
            orphan_payments: List[str] = []
            orphan_journals: List[str] = []
            duplicate_receipt_journals: List[str] = []
            duplicate_payment_journals: List[str] = []

            # 1. Audit Receipts
            receipts = sess.scalars(
                select(CustomerReceipt).where(CustomerReceipt.company_id == company_id)
            ).all()

            seen_rc_journals: Dict[str, str] = {}
            for r in receipts:
                if not r.journal_id:
                    orphan_receipts.append(f"Receipt '{r.voucher_number}' ({r.id}) has NULL journal_id.")
                else:
                    j_exists = sess.scalar(select(JournalEntry.id).where(JournalEntry.id == r.journal_id))
                    if not j_exists:
                        orphan_receipts.append(
                            f"Receipt '{r.voucher_number}' ({r.id}) references missing journal '{r.journal_id}'."
                        )
                    if r.journal_id in seen_rc_journals:
                        duplicate_receipt_journals.append(
                            f"Journal '{r.journal_id}' referenced by both receipt '{seen_rc_journals[r.journal_id]}' and '{r.voucher_number}'."
                        )
                    else:
                        seen_rc_journals[r.journal_id] = r.voucher_number

            # 2. Audit Payments
            payments = sess.scalars(
                select(SupplierPayment).where(SupplierPayment.company_id == company_id)
            ).all()

            seen_pay_journals: Dict[str, str] = {}
            for p in payments:
                if not p.journal_id:
                    orphan_payments.append(f"Payment '{p.voucher_number}' ({p.id}) has NULL journal_id.")
                else:
                    j_exists = sess.scalar(select(JournalEntry.id).where(JournalEntry.id == p.journal_id))
                    if not j_exists:
                        orphan_payments.append(
                            f"Payment '{p.voucher_number}' ({p.id}) references missing journal '{p.journal_id}'."
                        )
                    if p.journal_id in seen_pay_journals:
                        duplicate_payment_journals.append(
                            f"Journal '{p.journal_id}' referenced by both payment '{seen_pay_journals[p.journal_id]}' and '{p.voucher_number}'."
                        )
                    else:
                        seen_pay_journals[p.journal_id] = p.voucher_number

            # 3. Audit Journals for Orphan Entries
            payment_receipt_journals = sess.scalars(
                select(JournalEntry).where(
                    and_(
                        JournalEntry.company_id == company_id,
                        JournalEntry.reference_type.in_(["CUSTOMER_RECEIPT", "SUPPLIER_PAYMENT"]),
                    )
                )
            ).all()

            valid_receipt_j_ids = {r.journal_id for r in receipts if r.journal_id}
            valid_payment_j_ids = {p.journal_id for p in payments if p.journal_id}

            for j in payment_receipt_journals:
                if j.reference_type == "CUSTOMER_RECEIPT" and j.id not in valid_receipt_j_ids:
                    # Check if it was a reversal journal referenced via audit log or note
                    orphan_journals.append(
                        f"Journal '{j.voucher_number}' ({j.id}) tagged CUSTOMER_RECEIPT has no referencing receipt voucher."
                    )
                elif j.reference_type == "SUPPLIER_PAYMENT" and j.id not in valid_payment_j_ids:
                    orphan_journals.append(
                        f"Journal '{j.voucher_number}' ({j.id}) tagged SUPPLIER_PAYMENT has no referencing payment voucher."
                    )

            total_anomalies = (
                len(orphan_receipts)
                + len(orphan_payments)
                + len(orphan_journals)
                + len(duplicate_receipt_journals)
                + len(duplicate_payment_journals)
            )

            status = "CLEAN" if total_anomalies == 0 else "DISCREPANCIES_FOUND"

            return {
                "company_id": company_id,
                "status": status,
                "total_anomalies_count": total_anomalies,
                "orphan_receipt_vouchers_count": len(orphan_receipts),
                "orphan_payment_vouchers_count": len(orphan_payments),
                "orphan_journals_count": len(orphan_journals),
                "duplicate_receipt_journal_refs_count": len(duplicate_receipt_journals),
                "duplicate_payment_journal_refs_count": len(duplicate_payment_journals),
                "details": {
                    "orphan_receipts": orphan_receipts,
                    "orphan_payments": orphan_payments,
                    "orphan_journals": orphan_journals,
                    "duplicate_receipt_journals": duplicate_receipt_journals,
                    "duplicate_payment_journals": duplicate_payment_journals,
                },
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)

    # ==========================================================================
    # 7. Overall Financial Reconciliation Summary
    # ==========================================================================

    def get_financial_reconciliation_summary(
        self,
        company_id: str,
        as_of_date: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Executes an end-to-end multi-dimensional reconciliation audit across:
        1. Customer Accounts Receivable.
        2. Supplier Accounts Payable.
        3. Cash and Bank Books.
        4. Customer Advances.
        5. Supplier Advances.
        6. Journal Integrity & Orphan Detection.
        """
        def _execute(sess: Session):
            company = self._validate_company(sess, company_id)

            ar_res = self.reconcile_customer_ar(company_id, as_of_date=as_of_date, session=sess)
            ap_res = self.reconcile_supplier_ap(company_id, as_of_date=as_of_date, session=sess)
            cb_res = self.reconcile_cash_and_bank(company_id, as_of_date=as_of_date, session=sess)
            cust_adv_res = self.reconcile_customer_advances(company_id, session=sess)
            supp_adv_res = self.reconcile_supplier_advances(company_id, session=sess)
            audit_res = self.detect_orphan_or_duplicate_journals(company_id, session=sess)

            all_healthy = (
                ar_res["status"] == "BALANCED"
                and ap_res["status"] == "BALANCED"
                and cb_res["status"] == "BALANCED"
                and cust_adv_res["status"] == "BALANCED"
                and supp_adv_res["status"] == "BALANCED"
                and audit_res["status"] == "CLEAN"
            )

            overall_verdict = "HEALTHY" if all_healthy else "ATTENTION_REQUIRED"

            return {
                "company_id": company.id,
                "company_code": company.code,
                "company_name": company.name,
                "financial_year": company.fin_year,
                "as_of_date": as_of_date,
                "overall_verdict": overall_verdict,
                "subsystems": {
                    "customer_ar": {
                        "status": ar_res["status"],
                        "total_gl_balance": ar_res["total_gl_control_balance"],
                        "total_subledger_balance": ar_res["total_subledger_balance"],
                        "difference": ar_res["total_difference"],
                        "mismatches": ar_res["mismatched_count"],
                    },
                    "supplier_ap": {
                        "status": ap_res["status"],
                        "total_gl_balance": ap_res["total_gl_control_balance"],
                        "total_subledger_balance": ap_res["total_subledger_balance"],
                        "difference": ap_res["total_difference"],
                        "mismatches": ap_res["mismatched_count"],
                    },
                    "cash_and_bank": {
                        "status": cb_res["status"],
                        "accounts_audited": cb_res["account_count"],
                        "mismatched_accounts": cb_res["mismatched_count"],
                    },
                    "customer_advances": {
                        "status": cust_adv_res["status"],
                        "total_unallocated_advances": cust_adv_res["total_unallocated_advances"],
                        "violations_count": cust_adv_res["violations_count"],
                    },
                    "supplier_advances": {
                        "status": supp_adv_res["status"],
                        "total_unallocated_advances": supp_adv_res["total_unallocated_advances"],
                        "violations_count": supp_adv_res["violations_count"],
                    },
                    "journal_integrity": {
                        "status": audit_res["status"],
                        "total_anomalies": audit_res["total_anomalies_count"],
                    },
                },
            }

        if session is not None:
            return _execute(session)
        with self.db.read_session_scope() as sess:
            return _execute(sess)
