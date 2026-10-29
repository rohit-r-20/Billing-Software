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

    def save_account(self, company_id: str, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update an account master."""
        name = account_data.get("name", "").strip().upper()
        if not name:
            raise ValueError("Account name is required.")

        acc_id = account_data.get("id") or str(uuid.uuid4())
        alias = account_data.get("alias", "").strip()
        print_name = account_data.get("printName") or account_data.get("print_name") or name
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

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO accounts (
                    id, company_id, name, alias, print_name, account_group,
                    op_bal, op_type, address, state, dealer_type, gstin,
                    mobile, bank_name, bank_acc, ifsc, current_balance
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    ifsc = excluded.ifsc;
            """, (
                acc_id, company_id, name, alias, print_name, group,
                op_bal, op_type, address, state, dealer_type, gstin,
                mobile, bank_name, bank_acc, ifsc, op_bal
            ))
            conn.commit()

        logger.info(f"Account {name} saved for company {company_id}.")
        return {"id": acc_id, "name": name, "group": group, "gstin": gstin}


account_service = AccountService()

