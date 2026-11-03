"""
Accounting Service for Anti Matrix Billing ERP.
Manages Chart of Accounts, Double-Entry General Ledger, Day Book,
Trial Balance, and Profit & Loss statements.
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from db.database import db_manager, DatabaseManager
from core.logging_config import logger


class AccountingService:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or db_manager

    def _resolve_company_id(self, company_id: Optional[str]) -> str:
        cid = str(company_id or "").strip()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if cid:
                cursor.execute("SELECT id FROM companies WHERE id = ? OR UPPER(code) = ?;", (cid, cid.upper()))
                c_row = cursor.fetchone()
                if c_row:
                    return c_row["id"]
            cursor.execute("SELECT id FROM companies ORDER BY id ASC LIMIT 1;")
            c_default = cursor.fetchone()
            return c_default["id"] if c_default else cid

    def get_chart_of_accounts(self, company_id: str) -> List[Dict[str, Any]]:
        """Returns standard chart of accounts grouped by accounting nature."""
        actual_comp_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Accounts table
            cursor.execute("""
                SELECT name, account_group, current_balance, gstin, state
                FROM accounts WHERE company_id = ?
                ORDER BY name ASC;
            """, (actual_comp_id,))
            accs = [dict(r) for r in cursor.fetchall()]

            # 2. Suppliers table
            cursor.execute("""
                SELECT name, 'Sundry Creditors' as account_group, current_balance, gstin, state
                FROM suppliers WHERE company_id = ? AND is_active = 1
                ORDER BY name ASC;
            """, (actual_comp_id,))
            supps = [dict(r) for r in cursor.fetchall()]

        # Combine system standard ledgers
        system_ledgers = [
            {"name": "Sales Account", "account_group": "Sales Accounts", "current_balance": 0.0, "state": "Tamilnadu"},
            {"name": "Purchase Account", "account_group": "Purchase Accounts", "current_balance": 0.0, "state": "Tamilnadu"},
            {"name": "Input CGST Account", "account_group": "Duties & Taxes (ITC)", "current_balance": 0.0, "state": "Tamilnadu"},
            {"name": "Input SGST Account", "account_group": "Duties & Taxes (ITC)", "current_balance": 0.0, "state": "Tamilnadu"},
            {"name": "Input IGST Account", "account_group": "Duties & Taxes (ITC)", "current_balance": 0.0, "state": "Tamilnadu"},
            {"name": "Output CGST Account", "account_group": "Duties & Taxes (Liability)", "current_balance": 0.0, "state": "Tamilnadu"},
            {"name": "Output SGST Account", "account_group": "Duties & Taxes (Liability)", "current_balance": 0.0, "state": "Tamilnadu"},
            {"name": "Output IGST Account", "account_group": "Duties & Taxes (Liability)", "current_balance": 0.0, "state": "Tamilnadu"},
            {"name": "Cash-in-Hand", "account_group": "Cash-in-Hand", "current_balance": 0.0, "state": "Tamilnadu"},
            {"name": "Main Bank Account", "account_group": "Bank Accounts", "current_balance": 0.0, "state": "Tamilnadu"}
        ]

        return system_ledgers + accs + supps

    def get_day_book(self, company_id: str, business_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Chronological Day Book of all vouchers (Sales, Purchases, Returns)
        posted on a given date.
        """
        actual_comp_id = self._resolve_company_id(company_id)
        target_date = business_date or datetime.now().strftime("%Y-%m-%d")

        vouchers = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Sales vouchers
            cursor.execute("""
                SELECT 'SALE' as voucher_type, vch_no, vch_date as date, party_name as party,
                       subtotal as taxable_amount, (cgst_amount + sgst_amount + igst_amount) as tax_amount,
                       grand_total, payment_method, narration
                FROM sales_vouchers
                WHERE company_id = ? AND is_cancelled = 0
                ORDER BY created_at ASC;
            """, (actual_comp_id,))
            for r in cursor.fetchall():
                row = dict(r)
                if not business_date or target_date in row["date"]:
                    vouchers.append(row)

            # Purchase vouchers
            cursor.execute("""
                SELECT 'PURCHASE' as voucher_type, vch_no, vch_date as date, supplier_name as party,
                       taxable_amount, (cgst_amount + sgst_amount + igst_amount) as tax_amount,
                       grand_total, payment_type as payment_method, narration
                FROM purchase_vouchers
                WHERE company_id = ? AND is_cancelled = 0
                ORDER BY created_at ASC;
            """, (actual_comp_id,))
            for r in cursor.fetchall():
                row = dict(r)
                if not business_date or target_date in row["date"]:
                    vouchers.append(row)

            # Purchase Returns
            cursor.execute("""
                SELECT 'PURCHASE_RETURN' as voucher_type, vch_no, vch_date as date, supplier_name as party,
                       taxable_amount, (cgst_amount + sgst_amount + igst_amount) as tax_amount,
                       grand_total, 'DEBIT_NOTE' as payment_method, reason as narration
                FROM purchase_returns
                WHERE company_id = ?
                ORDER BY created_at ASC;
            """, (actual_comp_id,))
            for r in cursor.fetchall():
                row = dict(r)
                if not business_date or target_date in row["date"]:
                    vouchers.append(row)

            # Sales Returns
            cursor.execute("""
                SELECT 'SALES_RETURN' as voucher_type, vch_no, vch_date as date, customer_name as party,
                       taxable_amount, (cgst_amount + sgst_amount + igst_amount) as tax_amount,
                       grand_total, 'CREDIT_NOTE' as payment_method, reason as narration
                FROM sales_returns
                WHERE company_id = ?
                ORDER BY created_at ASC;
            """, (actual_comp_id,))
            for r in cursor.fetchall():
                row = dict(r)
                if not business_date or target_date in row["date"]:
                    vouchers.append(row)

        return sorted(vouchers, key=lambda x: str(x.get("date", "")))

    def get_trial_balance(self, company_id: str) -> Dict[str, Any]:
        """
        Calculates Trial Balance across all double-entry journal postings.
        Reconciles total debits and total credits.
        """
        actual_comp_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT jl.account_name,
                       SUM(jl.debit) as total_debit,
                       SUM(jl.credit) as total_credit
                FROM journal_entry_lines jl
                JOIN journal_entries j ON j.id = jl.journal_id
                WHERE j.company_id = ?
                GROUP BY jl.account_name
                ORDER BY jl.account_name ASC;
            """, (actual_comp_id,))
            rows = cursor.fetchall()

        accounts = []
        grand_debit = 0.0
        grand_credit = 0.0
        for r in rows:
            deb = float(r["total_debit"] or 0.0)
            cred = float(r["total_credit"] or 0.0)
            grand_debit += deb
            grand_credit += cred
            accounts.append({
                "account_name": r["account_name"],
                "debit": round(deb, 2),
                "credit": round(cred, 2),
                "net_balance": round(deb - cred, 2)
            })

        diff = round(abs(grand_debit - grand_credit), 2)
        return {
            "accounts": accounts,
            "total_debit": round(grand_debit, 2),
            "total_credit": round(grand_credit, 2),
            "difference": diff,
            "is_balanced": diff < 0.01
        }


accounting_service = AccountingService()
