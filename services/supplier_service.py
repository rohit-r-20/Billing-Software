"""
Supplier Master Service for Anti Matrix Billing ERP.
Manages suppliers, contact details, GSTIN, credit limits, payment terms,
and supplier accounts payable ledgers.
"""
import uuid
from typing import Dict, Any, List, Optional
from db.database import db_manager, DatabaseManager
from core.logging_config import logger


class SupplierService:
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

    def list_suppliers(self, company_id: str, query: str = "") -> List[Dict[str, Any]]:
        """List all active suppliers for a company, optionally matching a query."""
        actual_comp_id = self._resolve_company_id(company_id)
        q = f"%{query.strip().upper()}%"
        with self.db.get_connection() as conn:
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
            return [dict(r) for r in cursor.fetchall()]

    def get_supplier_by_id(self, company_id: str, supplier_id: str) -> Optional[Dict[str, Any]]:
        actual_comp_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM suppliers
                WHERE company_id = ? AND id = ?;
            """, (actual_comp_id, supplier_id))
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_supplier_by_name(self, company_id: str, name: str) -> Optional[Dict[str, Any]]:
        actual_comp_id = self._resolve_company_id(company_id)
        norm_name = name.strip().upper()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM suppliers
                WHERE company_id = ? AND UPPER(name) = ?;
            """, (actual_comp_id, norm_name))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_next_supplier_code(self, company_id: str) -> str:
        """Generates next supplier code e.g. SUP-001."""
        actual_comp_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
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
        actual_comp_id = self._resolve_company_id(company_id)
        name = (data.get("name") or "").strip().upper()
        if not name:
            raise ValueError("Supplier name is required.")

        supp_id = data.get("id") or str(uuid.uuid4())
        code = (data.get("code") or "").strip().upper()
        if not code:
            code = self.get_next_supplier_code(actual_comp_id)

        contact = (data.get("contact_person") or data.get("contact") or "").strip()
        mobile = (data.get("mobile") or "").strip()
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

        with self.db.get_connection() as conn:
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

            conn.commit()

        logger.info(f"Supplier {name} ({code}) saved for company {actual_comp_id}.")
        return {
            "id": actual_id,
            "code": code,
            "name": name,
            "gstin": gstin,
            "state": state
        }

    def update_supplier_balance(self, company_id: str, supplier_id: str, delta_amount: float) -> float:
        """Atomically adjusts a supplier's current balance (positive increases payable, negative decreases)."""
        actual_comp_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
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
        actual_comp_id = self._resolve_company_id(company_id)
        supplier = self.get_supplier_by_id(actual_comp_id, supplier_id)
        if not supplier:
            return {"supplier": None, "entries": [], "closing_balance": 0.0}

        entries = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Purchases
            cursor.execute("""
                SELECT 'PURCHASE' as type, vch_no, supplier_invoice_no, vch_date as date,
                       grand_total as debit, amount_paid, payment_type, narration
                FROM purchase_vouchers
                WHERE company_id = ? AND supplier_id = ? AND is_cancelled = 0
                ORDER BY vch_date ASC, created_at ASC;
            """, (actual_comp_id, supplier_id))
            purchases = [dict(r) for r in cursor.fetchall()]

            # Returns
            cursor.execute("""
                SELECT 'PURCHASE_RETURN' as type, vch_no, original_supplier_inv_no, vch_date as date,
                       grand_total as credit, reason as narration
                FROM purchase_returns
                WHERE company_id = ? AND supplier_id = ?
                ORDER BY vch_date ASC, created_at ASC;
            """, (actual_comp_id, supplier_id))
            returns = [dict(r) for r in cursor.fetchall()]

        # Combine and compute running balance
        running = supplier.get("opening_balance", 0.0)
        combined = []
        combined.append({
            "date": supplier.get("created_at", "")[:10],
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

