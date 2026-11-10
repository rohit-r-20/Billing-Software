"""
Account Service for Anti Matrix Billing ERP.
Manages Customer, Supplier, and other Party masters, classifications, balances,
and GSTIN details backed by permanent database tables.
"""
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from db.database import db_manager, DatabaseManager
from core.logging_config import logger


class AccountService:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or db_manager

    def _resolve_company_id(self, company_id: Optional[str]) -> str:
        """Resolve company UUID whether passed UUID or company code (e.g. COMP0001).
        Rejects missing, empty, or unresolvable company contexts."""
        cid = str(company_id or "").strip()
        if not cid:
            raise ValueError("Company context is required. Missing company identifier.")

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM companies WHERE id = ? OR UPPER(code) = ?;", (cid, cid.upper()))
            c_row = cursor.fetchone()
            if c_row:
                return c_row["id"]
        raise ValueError(f"Invalid company context: '{cid}' not found.")

    def list_accounts(
        self,
        company_id: str,
        group: Optional[str] = None,
        query: Optional[str] = None,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """List party master records from permanent database for company."""
        actual_comp_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            sql = "SELECT * FROM accounts WHERE company_id = ?"
            params: List[Any] = [actual_comp_id]

            if not include_inactive:
                sql += " AND (is_active = 1 OR is_active IS NULL)"

            if group and group.strip():
                g_clean = group.strip()
                if g_clean.upper() in ("CUSTOMER", "CUSTOMERS", "SUNDRY DEBTORS"):
                    sql += " AND account_group IN ('Sundry Debtors', 'Both (Customer & Supplier)', 'Sundry Debtors & Creditors')"
                elif g_clean.upper() in ("SUPPLIER", "SUPPLIERS", "SUNDRY CREDITORS"):
                    sql += " AND account_group IN ('Sundry Creditors', 'Both (Customer & Supplier)', 'Sundry Debtors & Creditors')"
                elif g_clean.upper() in ("BOTH", "BOTH (CUSTOMER & SUPPLIER)"):
                    sql += " AND account_group IN ('Both (Customer & Supplier)', 'Both (Debtor & Creditor)', 'Sundry Debtors & Creditors')"
                else:
                    sql += " AND account_group = ?"
                    params.append(g_clean)

            if query and query.strip():
                q = f"%{query.strip().upper()}%"
                sql += " AND (UPPER(name) LIKE ? OR UPPER(COALESCE(alias, '')) LIKE ? OR UPPER(COALESCE(mobile, '')) LIKE ? OR UPPER(COALESCE(gstin, '')) LIKE ?)"
                params.extend([q, q, q, q])

            sql += " ORDER BY name ASC;"
            cursor.execute(sql, params)
            rows = [dict(r) for r in cursor.fetchall()]

            for r in rows:
                for k, v in r.items():
                    if hasattr(v, "isoformat"):
                        r[k] = v.isoformat()
                grp = r.get("account_group") or "Sundry Debtors"
                if grp == "Sundry Debtors":
                    r["classification"] = "Customer"
                elif grp == "Sundry Creditors":
                    r["classification"] = "Supplier"
                elif grp in ("Both (Customer & Supplier)", "Both (Debtor & Creditor)", "Sundry Debtors & Creditors"):
                    r["classification"] = "Both (Customer & Supplier)"
                else:
                    r["classification"] = grp

            return rows

    def search_customers(self, company_id: str, query: str = "") -> List[Dict[str, Any]]:
        """Retrieve customers from permanent database."""
        return self.list_accounts(company_id, group="CUSTOMER", query=query)

    def search_suppliers(self, company_id: str, query: str = "") -> List[Dict[str, Any]]:
        """Retrieve suppliers from permanent database."""
        return self.list_accounts(company_id, group="SUPPLIER", query=query)

    def get_account_by_id(self, company_id: str, account_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve single party master by ID."""
        actual_comp_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM accounts
                WHERE company_id = ? AND id = ?
                LIMIT 1;
            """, (actual_comp_id, account_id))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            for k, v in res.items():
                if hasattr(v, "isoformat"):
                    res[k] = v.isoformat()
            grp = res.get("account_group") or "Sundry Debtors"
            if grp == "Sundry Debtors":
                res["classification"] = "Customer"
            elif grp == "Sundry Creditors":
                res["classification"] = "Supplier"
            elif grp in ("Both (Customer & Supplier)", "Both (Debtor & Creditor)", "Sundry Debtors & Creditors"):
                res["classification"] = "Both (Customer & Supplier)"
            else:
                res["classification"] = grp
            return res

    def save_account(self, company_id: str, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create or update an account master in the permanent database:
        - Validates mandatory fields (name, group)
        - Synchronises Print Name with Name
        - Supports customer and supplier classification (Sundry Debtors, Sundry Creditors, Both)
        - Mirrors supplier records to suppliers table with matching ID
        - Preserves existing transaction references
        """
        actual_comp_id = self._resolve_company_id(company_id)
        name = (account_data.get("name") or "").strip().upper()
        if not name:
            raise ValueError("Account name is required.")

        acc_id = account_data.get("id") or str(uuid.uuid4())
        alias = (account_data.get("alias") or "").strip()
        # In Masters, Print Name is automatically synchronised and matches Name
        print_name = name
        group = (account_data.get("group") or account_data.get("account_group") or "Sundry Debtors").strip()
        country = (account_data.get("country") or "India").strip()
        state = (account_data.get("state") or "Tamilnadu").strip()
        address = (account_data.get("address") or "").strip()
        dealer_type = (account_data.get("dealerType") or account_data.get("dealer_type") or "Unregistered").strip()
        gstin = (account_data.get("gstin") or "").strip().upper()
        mobile = (account_data.get("mobile") or "").strip()
        whatsapp = (account_data.get("whatsapp") or "").strip()
        pincode = (account_data.get("pincode") or "").strip()
        op_bal = float(account_data.get("opBal") or account_data.get("op_bal") or account_data.get("opening_balance") or 0.0)
        op_type = (account_data.get("opType") or account_data.get("op_type") or "Dr").strip()
        bank_name = (account_data.get("bankName") or account_data.get("bank_name") or "").strip()
        bank_acc = (account_data.get("bankAcc") or account_data.get("bank_acc") or "").strip()
        ifsc = (account_data.get("ifsc") or "").strip().upper()
        payment_terms = int(account_data.get("payment_terms") or account_data.get("paymentTerms") or 30)
        notes = (account_data.get("notes") or account_data.get("extra_info") or account_data.get("extraInfo") or "").strip()
        is_active = int(account_data.get("is_active") if "is_active" in account_data else 1)

        # Customer Category (Commercial, Sub-Commercial, Direct Customer)
        raw_cat = (account_data.get("customerCategory") or account_data.get("customer_category") or "Direct Customer").strip()
        if raw_cat in ("Commercial", "Sub-Commercial", "Direct Customer"):
            cust_cat = raw_cat
        else:
            cust_cat = "Direct Customer"

        # Classification helper
        if group == "Sundry Debtors":
            classification = "Customer"
        elif group == "Sundry Creditors":
            classification = "Supplier"
        elif group in ("Both (Customer & Supplier)", "Both (Debtor & Creditor)", "Sundry Debtors & Creditors"):
            classification = "Both (Customer & Supplier)"
        else:
            classification = group

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Check if record exists by ID
            cursor.execute("SELECT id, name FROM accounts WHERE company_id = ? AND id = ?;", (actual_comp_id, acc_id))
            existing_by_id = cursor.fetchone()

            if existing_by_id:
                # Update existing master by ID (preserves transaction references)
                cursor.execute("""
                    UPDATE accounts SET
                        name = ?,
                        alias = ?,
                        print_name = ?,
                        account_group = ?,
                        op_bal = ?,
                        op_type = ?,
                        address = ?,
                        country = ?,
                        state = ?,
                        dealer_type = ?,
                        gstin = ?,
                        mobile = ?,
                        whatsapp = ?,
                        pincode = ?,
                        bank_name = ?,
                        bank_acc = ?,
                        ifsc = ?,
                        payment_terms = ?,
                        notes = ?,
                        customer_category = ?,
                        is_active = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE company_id = ? AND id = ?;
                """, (
                    name, alias, print_name, group, op_bal, op_type,
                    address, country, state, dealer_type, gstin,
                    mobile, whatsapp, pincode, bank_name, bank_acc, ifsc,
                    payment_terms, notes, cust_cat, is_active,
                    actual_comp_id, acc_id
                ))
            else:
                # Check if account with same name already exists in company
                cursor.execute("SELECT id FROM accounts WHERE company_id = ? AND UPPER(name) = ?;", (actual_comp_id, name))
                existing_by_name = cursor.fetchone()

                if existing_by_name:
                    # Reuse existing ID to avoid duplicate identities
                    acc_id = existing_by_name["id"]
                    cursor.execute("""
                        UPDATE accounts SET
                            alias = ?,
                            print_name = ?,
                            account_group = ?,
                            op_bal = ?,
                            op_type = ?,
                            address = ?,
                            country = ?,
                            state = ?,
                            dealer_type = ?,
                            gstin = ?,
                            mobile = ?,
                            whatsapp = ?,
                            pincode = ?,
                            bank_name = ?,
                            bank_acc = ?,
                            ifsc = ?,
                            payment_terms = ?,
                            notes = ?,
                            customer_category = ?,
                            is_active = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE company_id = ? AND id = ?;
                    """, (
                        alias, print_name, group, op_bal, op_type,
                        address, country, state, dealer_type, gstin,
                        mobile, whatsapp, pincode, bank_name, bank_acc, ifsc,
                        payment_terms, notes, cust_cat, is_active,
                        actual_comp_id, acc_id
                    ))
                else:
                    # Insert new master
                    cursor.execute("""
                        INSERT INTO accounts (
                            id, company_id, name, alias, print_name, account_group,
                            op_bal, op_type, address, country, state, dealer_type, gstin,
                            mobile, whatsapp, pincode, bank_name, bank_acc, ifsc,
                            payment_terms, notes, current_balance, customer_category, is_active
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        acc_id, actual_comp_id, name, alias, print_name, group,
                        op_bal, op_type, address, country, state, dealer_type, gstin,
                        mobile, whatsapp, pincode, bank_name, bank_acc, ifsc,
                        payment_terms, notes, op_bal, cust_cat, is_active
                    ))

            # 2. If party acts as a Supplier (Sundry Creditors or Both), mirror into suppliers table
            if group in ("Sundry Creditors", "Both (Customer & Supplier)", "Both (Debtor & Creditor)", "Sundry Debtors & Creditors"):
                code = account_data.get("code") or f"SUP-{acc_id[:6].upper()}"
                cursor.execute("""
                    SELECT id FROM suppliers
                    WHERE id = ? OR (company_id = ? AND UPPER(name) = ?);
                """, (acc_id, actual_comp_id, name.strip().upper()))
                sup_existing = cursor.fetchone()
                if sup_existing:
                    cursor.execute("""
                        UPDATE suppliers SET
                            name = ?,
                            contact_person = ?,
                            mobile = ?,
                            gstin = ?,
                            address = ?,
                            state = ?,
                            pincode = ?,
                            payment_terms = ?,
                            bank_name = ?,
                            bank_acc = ?,
                            ifsc = ?,
                            is_active = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?;
                    """, (
                        name, alias, mobile, gstin,
                        address, state, pincode, payment_terms,
                        bank_name, bank_acc, ifsc, is_active,
                        sup_existing["id"]
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO suppliers (
                            id, company_id, code, name, contact_person, mobile, email, gstin,
                            pan, address, city, state, pincode, opening_balance, current_balance,
                            payment_terms, bank_name, bank_acc, ifsc, is_active
                        ) VALUES (?, ?, ?, ?, ?, ?, '', ?, '', ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        acc_id, actual_comp_id, code, name, alias, mobile, gstin,
                        address, state, pincode, op_bal, op_bal,
                        payment_terms, bank_name, bank_acc, ifsc, is_active
                    ))

            conn.commit()

        logger.info(f"Party Master {name} (ID: {acc_id}, Classification: {classification}) saved for company {actual_comp_id}.")
        return {
            "id": acc_id,
            "name": name,
            "print_name": print_name,
            "alias": alias,
            "group": group,
            "account_group": group,
            "classification": classification,
            "country": country,
            "state": state,
            "gstin": gstin,
            "mobile": mobile,
            "customer_category": cust_cat,
            "is_active": is_active
        }

    def deactivate_account(self, company_id: str, account_id: str) -> bool:
        """Deactivate a party master rather than deleting it."""
        actual_comp_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE accounts
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE company_id = ? AND id = ?;
            """, (actual_comp_id, account_id))
            acc_affected = cursor.rowcount
            cursor.execute("""
                UPDATE suppliers
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE company_id = ? AND id = ?;
            """, (actual_comp_id, account_id))
            sup_affected = cursor.rowcount
            conn.commit()
            return (acc_affected > 0) or (sup_affected > 0)

    def delete_account(self, company_id: str, account_id: str) -> bool:
        """
        Safely delete an account master only if not referenced in historical transactions.
        If referenced, raises ValueError and prevents accidental deletion.
        """
        actual_comp_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Check sales vouchers
            cursor.execute("SELECT COUNT(*) FROM sales_vouchers WHERE company_id = ? AND account_id = ?;", (actual_comp_id, account_id))
            if cursor.fetchone()[0] > 0:
                raise ValueError("Cannot delete party master referenced in existing sales invoices. Deactivate instead.")

            # Check purchase vouchers
            cursor.execute("SELECT COUNT(*) FROM purchase_vouchers WHERE company_id = ? AND supplier_id = ?;", (actual_comp_id, account_id))
            if cursor.fetchone()[0] > 0:
                raise ValueError("Cannot delete party master referenced in existing purchase invoices. Deactivate instead.")

            # Check journal entries
            cursor.execute("SELECT COUNT(*) FROM journal_entry_lines WHERE account_id = ?;", (account_id,))
            if cursor.fetchone()[0] > 0:
                raise ValueError("Cannot delete party master referenced in financial journals. Deactivate instead.")

            cursor.execute("DELETE FROM accounts WHERE company_id = ? AND id = ?;", (actual_comp_id, account_id))
            cursor.execute("DELETE FROM suppliers WHERE company_id = ? AND id = ?;", (actual_comp_id, account_id))
            conn.commit()
            return True


account_service = AccountService()
