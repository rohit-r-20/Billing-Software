"""
Billing and POS Transaction Engine for Anti Matrix Billing ERP.
Manages atomic invoice creation, sequential numbering, stock movement deduction,
payment recording, and sales returns with full transaction rollback protection.
"""
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from db.database import db_manager, DatabaseManager
from services.tax_service import tax_service
from core.logging_config import logger


class BillingService:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or db_manager

    def get_next_voucher_number(self, company_id: str, series: str = "Main") -> str:
        """
        Calculates the next sequential unique invoice number for the active company.
        Format: <prefix><sequential_number_padded>
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Fetch company configuration
            cursor.execute("SELECT * FROM company_configs WHERE company_id = ?;", (company_id,))
            cfg = cursor.fetchone()
            start_num = cfg["vch_start"] if cfg else 1
            digits = cfg["vch_digits"] if cfg else 3
            prefix = cfg["vch_prefix"] if cfg else ""

            # Find maximum sequence number stored
            cursor.execute("""
                SELECT vch_no FROM sales_vouchers
                WHERE company_id = ? AND series = ?;
            """, (company_id, series))
            rows = cursor.fetchall()

            max_seq = 0
            for r in rows:
                vch_no = r["vch_no"]
                # Strip prefix if matches
                if prefix and vch_no.startswith(prefix):
                    num_str = vch_no[len(prefix):]
                else:
                    num_str = "".join(ch for ch in vch_no if ch.isdigit())
                try:
                    num = int(num_str)
                    if num > max_seq:
                        max_seq = num
                except ValueError:
                    pass

            next_seq = max(max_seq + 1, start_num)
            return f"{prefix}{str(next_seq).zfill(digits)}"

    def create_sale_invoice(
        self,
        company_id: str,
        items: List[Dict[str, Any]],
        party_name: str = "CASH",
        account_id: Optional[str] = None,
        sale_type: str = "L/GST-18%",
        payment_method: str = "CASH",
        payments: Optional[List[Dict[str, Any]]] = None,
        branch_id: Optional[str] = None,
        vch_date: Optional[str] = None,
        narration: str = "",
        series: str = "Main",
        cashier_username: str = "A"
    ) -> Dict[str, Any]:
        """
        Atomically commits a complete sale invoice with:
        - Invoice header
        - Item snapshots & line items
        - Payment splits
        - Stock balance deductions
        - Stock movement ledger
        - Audit log
        If anything fails, rolls back completely.
        """
        if not items:
            raise ValueError("Cannot checkout an empty invoice. At least one line item is required.")

        # Set default date if omitted (DD-MM-YYYY)
        if not vch_date:
            vch_date = datetime.now().strftime("%d-%m-%Y")

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Verify active company
            cursor.execute("SELECT name, state FROM companies WHERE id = ?;", (company_id,))
            comp_row = cursor.fetchone()
            if not comp_row:
                raise ValueError(f"Company {company_id} does not exist.")
            company_state = comp_row["state"] or "Tamilnadu"

            # Determine default branch if not provided
            if not branch_id:
                cursor.execute("SELECT id FROM branches WHERE company_id = ? AND is_default = 1;", (company_id,))
                b_row = cursor.fetchone()
                branch_id = b_row["id"] if b_row else None

            # Calculate line items and voucher totals using TaxService
            totals = tax_service.calculate_voucher_totals(
                items=items,
                company_state=company_state,
                sale_type=sale_type,
                auto_round=True
            )

            # Generate next voucher number
            vch_no = self.get_next_voucher_number(company_id, series)
            vch_id = str(uuid.uuid4())

            # 1. Insert Voucher Header
            cursor.execute("""
                INSERT INTO sales_vouchers (
                    id, company_id, branch_id, vch_no, series, vch_date,
                    sale_type, party_name, account_id, mat_centre, narration,
                    subtotal, taxable_amount, tax_rate, cgst_amount, sgst_amount,
                    igst_amount, round_off, grand_total, payment_method, payment_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Main Store', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PAID');
            """, (
                vch_id,
                company_id,
                branch_id,
                vch_no,
                series,
                vch_date,
                sale_type,
                party_name,
                account_id,
                narration,
                totals["subtotal"],
                totals["taxable_amount"],
                18.0,  # general rate ref
                totals["cgst_amount"],
                totals["sgst_amount"],
                totals["igst_amount"],
                totals["round_off"],
                totals["grand_total"],
                payment_method
            ))

            # 2. Insert Line Items and Deduct Stock
            for idx, line in enumerate(totals["items"], start=1):
                item_id = line.get("id") or line.get("item_id")
                qty = float(line["qty"])
                price = float(line["price"])
                amount = float(line["line_total"])
                tax_rate = float(line.get("tax_rate", 0.0))
                tax_amt = float(line.get("tax_amount", 0.0))

                cursor.execute("""
                    INSERT INTO sales_voucher_items (
                        id, voucher_id, item_id, sn, item_name, hsn,
                        qty, unit, price, amount, tax_rate, tax_amount
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    str(uuid.uuid4()),
                    vch_id,
                    item_id,
                    idx,
                    line.get("name", f"Item {idx}"),
                    line.get("hsn", ""),
                    qty,
                    line.get("unit", "Pcs."),
                    price,
                    amount,
                    tax_rate,
                    tax_amt
                ))

                # Deduct inventory if item is linked and branch is present
                if item_id and branch_id:
                    cursor.execute("""
                        INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(branch_id, item_id) DO UPDATE SET
                            current_qty = current_qty - excluded.current_qty,
                            last_updated = CURRENT_TIMESTAMP;
                    """, (str(uuid.uuid4()), company_id, branch_id, item_id, qty))

                    cursor.execute("""
                        INSERT INTO stock_movements (
                            id, company_id, branch_id, item_id, movement_type,
                            qty, unit_cost, reference_type, reference_id, notes
                        ) VALUES (?, ?, ?, ?, 'SALE', ?, ?, 'INVOICE', ?, ?);
                    """, (
                        str(uuid.uuid4()),
                        company_id,
                        branch_id,
                        item_id,
                        -qty,
                        price,
                        vch_no,
                        f"Sale checkout by {cashier_username}"
                    ))

            # 3. Record Payments
            payment_list = payments or [{"method": payment_method, "amount": totals["grand_total"]}]
            for p in payment_list:
                cursor.execute("""
                    INSERT INTO payments (
                        id, company_id, voucher_id, method, amount, ref_number, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (
                    str(uuid.uuid4()),
                    company_id,
                    vch_id,
                    p.get("method", "CASH"),
                    float(p.get("amount") or totals["grand_total"]),
                    p.get("ref_number", ""),
                    p.get("notes", "")
                ))

            # 4. Audit Log
            cursor.execute("""
                INSERT INTO audit_logs (
                    id, company_id, username, action, entity_type, entity_id, details
                ) VALUES (?, ?, ?, 'CREATE_SALE', 'INVOICE', ?, ?);
            """, (
                str(uuid.uuid4()),
                company_id,
                cashier_username,
                vch_no,
                f"Completed sale for ₹{totals['grand_total']} to {party_name}"
            ))

            conn.commit()

        logger.info(f"Invoice {vch_no} saved successfully for company {company_id}. Total: ₹{totals['grand_total']}")
        return {
            "voucher_id": vch_id,
            "vch_no": vch_no,
            "grand_total": totals["grand_total"],
            "totals": totals
        }

    def get_voucher_details(self, company_id: str, voucher_id_or_no: str) -> Optional[Dict[str, Any]]:
        """Retrieve full voucher header, line items, and payment breakdown."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.*, c.name as company_name, c.gstin as company_gstin, c.state as company_state
                FROM sales_vouchers v
                JOIN companies c ON c.id = v.company_id
                WHERE v.company_id = ? AND (v.id = ? OR v.vch_no = ?);
            """, (company_id, voucher_id_or_no, voucher_id_or_no))
            vch_row = cursor.fetchone()
            if not vch_row:
                return None

            vch = dict(vch_row)
            # Fetch line items
            cursor.execute("""
                SELECT * FROM sales_voucher_items
                WHERE voucher_id = ?
                ORDER BY sn ASC;
            """, (vch["id"],))
            vch["items"] = [dict(r) for r in cursor.fetchall()]

            # Fetch payments
            cursor.execute("""
                SELECT * FROM payments WHERE voucher_id = ?;
            """, (vch["id"],))
            vch["payments"] = [dict(r) for r in cursor.fetchall()]

            return vch

    def list_vouchers(self, company_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """List recent sales vouchers for active company."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, vch_no, vch_date, party_name, sale_type, subtotal, grand_total, payment_method, is_cancelled
                FROM sales_vouchers
                WHERE company_id = ?
                ORDER BY created_at DESC
                LIMIT ?;
            """, (company_id, limit))
            return [dict(r) for r in cursor.fetchall()]


billing_service = BillingService()
