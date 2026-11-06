"""
Account Service for Anti Matrix Billing ERP.
Manages Customer and Vendor masters, balances, and GSTIN details.
"""
import uuid
from typing import Dict, Any, List, Optional
from db.database import db_manager, DatabaseManager
from core.logging_config import logger


class AccountService:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or db_manager

    def list_accounts(self, company_id: str, group: Optional[str] = None) -> List[Dict[str, Any]]:
        """List accounts for active company."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if group:
                cursor.execute("""
                    SELECT * FROM accounts
                    WHERE company_id = ? AND account_group = ?
                    ORDER BY name ASC;
                """, (company_id, group))
            else:
                cursor.execute("""
                    SELECT * FROM accounts
                    WHERE company_id = ?
                    ORDER BY name ASC;
                """, (company_id,))
            return [dict(r) for r in cursor.fetchall()]

    def get_account_by_id(self, company_id: str, account_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve single account master by ID."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM accounts
                WHERE company_id = ? AND id = ?
                LIMIT 1;
            """, (company_id, account_id))
            row = cursor.fetchone()
            return dict(row) if row else None

    def save_account(self, company_id: str, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update an account master."""
        name = account_data.get("name", "").strip().upper()
        if not name:
            raise ValueError("Account name is required.")

        acc_id = account_data.get("id") or str(uuid.uuid4())
        alias = account_data.get("alias", "").strip()
        # In Masters, Print Name is automatically synchronised and matches Name
        print_name = name
        group = account_data.get("group") or account_data.get("account_group") or "Sundry Debtors"
        op_bal = float(account_data.get("opBal") or account_data.get("op_bal") or 0.0)
        op_type = account_data.get("opType") or account_data.get("op_type") or "Dr"
        address = account_data.get("address", "").strip()
        state = account_data.get("state", "Tamilnadu").strip()
        dealer_type = account_data.get("dealerType") or account_data.get("dealer_type") or "Unregistered"
        gstin = (account_data.get("gstin") or "").strip().upper()
        mobile = account_data.get("mobile", "").strip()
        bank_name = account_data.get("bankName") or account_data.get("bank_name") or ""
        bank_acc = account_data.get("bankAcc") or account_data.get("bank_acc") or ""
        ifsc = (account_data.get("ifsc") or "").strip().upper()
        
        # Customer Category (Commercial, Sub-Commercial, Direct Customer)
        raw_cat = (account_data.get("customerCategory") or account_data.get("customer_category") or "Direct Customer").strip()
        if raw_cat in ("Commercial", "Sub-Commercial", "Direct Customer"):
            cust_cat = raw_cat
        else:
            cust_cat = "Direct Customer"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO accounts (
                    id, company_id, name, alias, print_name, account_group,
                    op_bal, op_type, address, state, dealer_type, gstin,
                    mobile, bank_name, bank_acc, ifsc, current_balance, customer_category
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_id, name) DO UPDATE SET
                    alias = excluded.alias,
                    print_name = excluded.print_name,
                    account_group = excluded.account_group,
                    address = excluded.address,
                    state = excluded.state,
                    dealer_type = excluded.dealer_type,
                    gstin = excluded.gstin,
                    mobile = excluded.mobile,
                    bank_name = excluded.bank_name,
                    bank_acc = excluded.bank_acc,
                    ifsc = excluded.ifsc,
                    customer_category = excluded.customer_category;
            """, (
                acc_id, company_id, name, alias, print_name, group,
                op_bal, op_type, address, state, dealer_type, gstin,
                mobile, bank_name, bank_acc, ifsc, op_bal, cust_cat
            ))
            conn.commit()

        logger.info(f"Account {name} saved for company {company_id} (Category: {cust_cat}).")
        return {
            "id": acc_id,
            "name": name,
            "print_name": print_name,
            "alias": alias,
            "group": group,
            "gstin": gstin,
            "customer_category": cust_cat
        }


account_service = AccountService()

