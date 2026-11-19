"""
Supplier Master Service for Anti Matrix Billing ERP.
Manages suppliers, contact details, GSTIN, credit limits, payment terms,
and supplier accounts payable ledgers.
"""
import uuid
import re
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from db.database import db_manager, DatabaseManager
from services.company_service import resolve_cached_company_id
from core.logging_config import logger


def _sanitize_supplier_row(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize datetime and Decimal objects for JSON serialization."""
    res = {}
    for k, v in row_dict.items():
        if isinstance(v, (datetime, date)):
            res[k] = v.isoformat()
        elif isinstance(v, Decimal):
            res[k] = float(v)
        else:
            res[k] = v
    return res


class SupplierService:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or db_manager

    def _ensure_suppliers_table(self, db_mgr: DatabaseManager) -> None:
        """Ensure suppliers table exists in the target database."""
        try:
            with db_mgr.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS suppliers (
                        id VARCHAR(36) PRIMARY KEY,
                        company_id VARCHAR(36) NOT NULL,
                        code VARCHAR(50) NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        contact_person VARCHAR(255),
                        mobile VARCHAR(50),
                        email VARCHAR(255),
                        gstin VARCHAR(15),
                        pan VARCHAR(10),
                        address TEXT,
                        city VARCHAR(100),
                        state VARCHAR(100) DEFAULT 'Tamilnadu',
                        pincode VARCHAR(20),
                        opening_balance NUMERIC(15, 2) DEFAULT 0.0,
                        current_balance NUMERIC(15, 2) DEFAULT 0.0,
                        credit_limit NUMERIC(15, 2) DEFAULT 0.0,
                        payment_terms INTEGER DEFAULT 30,
                        bank_name VARCHAR(255),
                        bank_acc VARCHAR(100),
                        ifsc VARCHAR(50),
                        is_active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                        UNIQUE (company_id, code),
                        UNIQUE (company_id, name)
                    );
                """)
                conn.commit()
        except Exception as e:
            logger.debug(f"ensure suppliers table note: {e}")

    def _get_db_and_company_id(self, company_id: Optional[str]) -> Tuple[DatabaseManager, str]:
        """
        Resolves the appropriate DatabaseManager and canonical UUID for the company.
        Checks traditional_db_manager if company exists there, otherwise self.db / db_manager.
        """
        cid = str(company_id or "").strip()
        if not cid:
            raise ValueError("Company context is required. Missing company identifier.")

        # 1. Check traditional database if it exists
        try:
            from db.traditional_database import traditional_db_manager
            trad_mgr = DatabaseManager(database_url=traditional_db_manager.database_url)
            with trad_mgr.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, code FROM companies WHERE id = ? OR UPPER(code) = ? LIMIT 1;", (cid, cid.upper()))
                c_row = cursor.fetchone()
                if c_row:
                    actual_id = c_row["id"] if hasattr(c_row, "keys") or isinstance(c_row, dict) else c_row[0]
                    self._ensure_suppliers_table(trad_mgr)
                    return trad_mgr, actual_id
        except Exception as e:
            logger.debug(f"SupplierService trad_db check: {e}")

        # 2. Check main database (self.db or db_manager)
        target_db = self.db or db_manager
        try:
            with target_db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, code FROM companies WHERE id = ? OR UPPER(code) = ? LIMIT 1;", (cid, cid.upper()))
                c_row = cursor.fetchone()
                if c_row:
                    actual_id = c_row["id"] if hasattr(c_row, "keys") or isinstance(c_row, dict) else c_row[0]
                    self._ensure_suppliers_table(target_db)
                    return target_db, actual_id
        except Exception as e:
            logger.debug(f"SupplierService primary_db check: {e}")

        raise ValueError(f"Invalid company context: '{cid}' not found.")

    def _resolve_company_id(self, company_id: Optional[str]) -> str:
        """Resolve company UUID whether passed UUID or company code."""
        _, actual_cid = self._get_db_and_company_id(company_id)
        return actual_cid

    def list_suppliers(self, company_id: str, query: str = "") -> List[Dict[str, Any]]:
        """List all active suppliers for a company, optionally matching a query."""
        target_db, actual_comp_id = self._get_db_and_company_id(company_id)
        q = f"%{query.strip().upper()}%"
        with target_db.get_connection() as conn:
            cursor = conn.cursor()
            if query.strip():
                cursor.execute("""
                    SELECT * FROM suppliers
                    WHERE company_id = ? AND is_active = 1 AND (
                        UPPER(name) LIKE ? OR
                        UPPER(code) LIKE ? OR
                        UPPER(COALESCE(gstin, '')) LIKE ? OR
                        UPPER(COALESCE(mobile, '')) LIKE ?
                    )
                    ORDER BY name ASC;
                """, (actual_comp_id, q, q, q, q))
            else:
                cursor.execute("""
                    SELECT * FROM suppliers
                    WHERE company_id = ? AND is_active = 1
                    ORDER BY name ASC;
                """, (actual_comp_id,))
            return [_sanitize_supplier_row(dict(r)) for r in cursor.fetchall()]

    def get_supplier_by_id(self, company_id: str, supplier_id: str) -> Optional[Dict[str, Any]]:
        target_db, actual_comp_id = self._get_db_and_company_id(company_id)
        with target_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM suppliers
                WHERE company_id = ? AND id = ?;
            """, (actual_comp_id, supplier_id))
            row = cursor.fetchone()
            return _sanitize_supplier_row(dict(row)) if row else None

    def find_supplier_by_name(self, company_id: str, name: str) -> Optional[Dict[str, Any]]:
        target_db, actual_comp_id = self._get_db_and_company_id(company_id)
        norm_name = name.strip().upper()
        with target_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM suppliers
                WHERE company_id = ? AND UPPER(name) = ?;
            """, (actual_comp_id, norm_name))
            row = cursor.fetchone()
            return _sanitize_supplier_row(dict(row)) if row else None

    def get_next_supplier_code(self, company_id: str) -> str:
        """Generates next supplier code e.g. SUP-001."""
        target_db, actual_comp_id = self._get_db_and_company_id(company_id)
        with target_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT code FROM suppliers WHERE company_id = ?;
            """, (actual_comp_id,))
            rows = cursor.fetchall()
            max_num = 0
            for r in rows:
                code_str = r["code"]
                digits = "".join(ch for ch in code_str if ch.isdigit())
                if digits:
                    try:
                        num = int(digits)
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        pass
            next_num = max_num + 1
            return f"SUP-{str(next_num).zfill(3)}"

    def save_supplier(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a supplier record."""
        target_db, actual_comp_id = self._get_db_and_company_id(company_id)
        name = (data.get("name") or "").strip().upper()
        if not name:
            raise ValueError("Supplier name is required.")

        # Strict 10-digit phone number limit: letters/special characters blocked, must be exactly 10 digits
        raw_phone = str(data.get("phone") or data.get("mobile") or "").strip()
        if raw_phone:
            if not (raw_phone.isdigit() and len(raw_phone) == 10):
                raise ValueError("Contact phone number must be exactly 10 numeric digits.")
            mobile = raw_phone
        else:
            mobile = ""

        supp_id = data.get("id") or str(uuid.uuid4())
        code = (data.get("code") or "").strip().upper()
        if not code:
            code = self.get_next_supplier_code(actual_comp_id)

        contact = (data.get("contact_person") or data.get("contact") or "").strip()
        email = (data.get("email") or "").strip()
        gstin = (data.get("gstin") or "").strip().upper()
        pan = (data.get("pan") or "").strip().upper()
        address = (data.get("address") or "").strip()
        city = (data.get("city") or "").strip()
        state = (data.get("state") or "Tamilnadu").strip()
        pincode = (data.get("pincode") or "").strip()
        op_bal = float(data.get("opening_balance") or data.get("op_bal") or 0.0)
        credit_limit = float(data.get("credit_limit") or 0.0)
        payment_terms = int(data.get("payment_terms") or 30)
        bank_name = (data.get("bank_name") or "").strip()
        bank_acc = (data.get("bank_acc") or "").strip()
        ifsc = (data.get("ifsc") or "").strip().upper()

        with target_db.get_connection() as conn:
            cursor = conn.cursor()
            # Check existing by ID
            cursor.execute("SELECT id, current_balance FROM suppliers WHERE company_id = ? AND id = ?;", (actual_comp_id, supp_id))
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE suppliers SET
                        name = ?,
                        code = ?,
                        contact_person = ?,
                        mobile = ?,
                        email = ?,
                        gstin = ?,
                        pan = ?,
                        address = ?,
                        city = ?,
                        state = ?,
                        pincode = ?,
                        credit_limit = ?,
                        payment_terms = ?,
                        bank_name = ?,
                        bank_acc = ?,
                        ifsc = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE company_id = ? AND id = ?;
                """, (
                    name, code, contact, mobile, email, gstin, pan,
                    address, city, state, pincode, credit_limit, payment_terms,
                    bank_name, bank_acc, ifsc, actual_comp_id, supp_id
                ))
                actual_id = supp_id
            else:
                # Upsert by name
                cursor.execute("""
                    INSERT INTO suppliers (
                        id, company_id, code, name, contact_person, mobile, email,
                        gstin, pan, address, city, state, pincode, opening_balance,
                        credit_limit, payment_terms, bank_name, bank_acc, ifsc, current_balance
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(company_id, name) DO UPDATE SET
                        contact_person = excluded.contact_person,
                        mobile = excluded.mobile,
                        email = excluded.email,
                        gstin = excluded.gstin,
                        pan = excluded.pan,
                        address = excluded.address,
                        city = excluded.city,
                        state = excluded.state,
                        pincode = excluded.pincode,
                        credit_limit = excluded.credit_limit,
                        payment_terms = excluded.payment_terms,
                        bank_name = excluded.bank_name,
                        bank_acc = excluded.bank_acc,
                        ifsc = excluded.ifsc,
                        updated_at = CURRENT_TIMESTAMP;
                """, (
                    supp_id, actual_comp_id, code, name, contact, mobile, email,
                    gstin, pan, address, city, state, pincode, op_bal,
                    credit_limit, payment_terms, bank_name, bank_acc, ifsc, op_bal
                ))
                cursor.execute("SELECT id FROM suppliers WHERE company_id = ? AND name = ?;", (actual_comp_id, name))
                actual_id = cursor.fetchone()["id"]

            # Keep traditional accounts table in sync if accounts table exists
            try:
                cursor.execute("SELECT id FROM accounts WHERE company_id = ? AND id = ?;", (actual_comp_id, actual_id))
                acc_row = cursor.fetchone()
                if acc_row:
                    cursor.execute("""
                        UPDATE accounts SET
                            name = ?, code = ?, phone = ?, email = ?, address = ?, gstin = ?, state = ?, is_active = 1, updated_at = CURRENT_TIMESTAMP
                        WHERE company_id = ? AND id = ?;
                    """, (name, code, mobile, email, address, gstin, state, actual_comp_id, actual_id))
                else:
                    cursor.execute("""
                        INSERT INTO accounts (id, company_id, code, name, account_type, phone, email, address, gstin, state, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, ?, 'Creditor', ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                    """, (actual_id, actual_comp_id, code, name, mobile, email, address, gstin, state))
            except Exception as e:
                logger.debug(f"accounts sync note: {e}")

            conn.commit()

        logger.info(f"Supplier {name} ({code}) saved for company {actual_comp_id}.")
        return {
            "id": actual_id,
            "code": code,
            "name": name,
            "gstin": gstin,
            "state": state,
            "phone": mobile,
            "mobile": mobile,
            "credit_limit": credit_limit,
            "current_balance": op_bal,
            "opening_balance": op_bal
        }

    def update_supplier_balance(self, company_id: str, supplier_id: str, delta_amount: float) -> float:
        """Atomically adjusts a supplier's current balance (positive increases payable, negative decreases)."""
        target_db, actual_comp_id = self._get_db_and_company_id(company_id)
        with target_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE suppliers
                SET current_balance = current_balance + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE company_id = ? AND id = ?;
            """, (delta_amount, actual_comp_id, supplier_id))
            cursor.execute("SELECT current_balance FROM suppliers WHERE company_id = ? AND id = ?;", (actual_comp_id, supplier_id))
            row = cursor.fetchone()
            conn.commit()
            return float(row["current_balance"]) if row else 0.0

    def get_supplier_ledger(self, company_id: str, supplier_id: str) -> Dict[str, Any]:
        """Returns chronological statement of purchases, returns, and payments for a supplier."""
        target_db, actual_comp_id = self._get_db_and_company_id(company_id)
        supplier = self.get_supplier_by_id(actual_comp_id, supplier_id)
        if not supplier:
            return {"supplier": None, "entries": [], "closing_balance": 0.0}

        entries = []
        with target_db.get_connection() as conn:
            cursor = conn.cursor()
            # Purchases
            try:
                cursor.execute("""
                    SELECT 'PURCHASE' as type, vch_no, supplier_invoice_no, vch_date as date,
                           grand_total as debit, amount_paid, payment_type, narration
                    FROM purchase_vouchers
                    WHERE company_id = ? AND supplier_id = ? AND is_cancelled = 0
                    ORDER BY vch_date ASC, created_at ASC;
                """, (actual_comp_id, supplier_id))
                purchases = [dict(r) for r in cursor.fetchall()]
            except Exception:
                purchases = []

            # Returns
            try:
                cursor.execute("""
                    SELECT 'PURCHASE_RETURN' as type, vch_no, original_supplier_inv_no, vch_date as date,
                           grand_total as credit, reason as narration
                    FROM purchase_returns
                    WHERE company_id = ? AND supplier_id = ?
                    ORDER BY vch_date ASC, created_at ASC;
                """, (actual_comp_id, supplier_id))
                returns = [dict(r) for r in cursor.fetchall()]
            except Exception:
                returns = []

        # Combine and compute running balance
        running = supplier.get("opening_balance", 0.0)
        combined = []
        combined.append({
            "date": supplier.get("created_at", "")[:10] if supplier.get("created_at") else "",
            "type": "OPENING_BALANCE",
            "ref_no": "-",
            "debit": 0.0,
            "credit": running,
            "balance": running,
            "narration": "Opening Balance"
        })

        all_tx = sorted(purchases + returns, key=lambda x: str(x.get("date", "")))
        for tx in all_tx:
            t = tx.get("type")
            if t == "PURCHASE":
                amt = float(tx.get("debit") or 0.0)
                paid = float(tx.get("amount_paid") or 0.0)
                unpaid = amt - paid
                running += unpaid
                combined.append({
                    "date": tx.get("date"),
                    "type": "PURCHASE",
                    "ref_no": f"{tx.get('vch_no')} (Bill: {tx.get('supplier_invoice_no')})",
                    "debit": 0.0,
                    "credit": amt,
                    "balance": running,
                    "narration": tx.get("narration") or f"Purchase Bill #{tx.get('supplier_invoice_no')}"
                })
                if paid > 0:
                    running -= paid
                    combined.append({
                        "date": tx.get("date"),
                        "type": "PAYMENT",
                        "ref_no": tx.get("vch_no"),
                        "debit": paid,
                        "credit": 0.0,
                        "balance": running,
                        "narration": f"Immediate Payment ({tx.get('payment_type')})"
                    })
            elif t == "PURCHASE_RETURN":
                amt = float(tx.get("credit") or 0.0)
                running -= amt
                combined.append({
                    "date": tx.get("date"),
                    "type": "PURCHASE_RETURN",
                    "ref_no": tx.get("vch_no"),
                    "debit": amt,
                    "credit": 0.0,
                    "balance": running,
                    "narration": tx.get("narration") or "Goods Return"
                })

        return {
            "supplier": supplier,
            "entries": combined,
            "closing_balance": running
        }


supplier_service = SupplierService()
