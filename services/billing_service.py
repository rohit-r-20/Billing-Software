"""
Billing and POS Transaction Engine for Anti Matrix Billing ERP.
Manages atomic invoice creation, sequential numbering, stock movement deduction,
payment recording, and sales returns with full transaction rollback protection.
"""
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from db.database import db_manager, DatabaseManager
from services.tax_service import tax_service
from core.logging_config import logger


class BillingService:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or db_manager

    def _resolve_company_id(self, company_id: Optional[str]) -> str:
        """Resolve company UUID whether passed UUID or company code (e.g. COMP0001), falling back to primary company if empty."""
        cid = str(company_id or "").strip()
        if not cid:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM companies ORDER BY id ASC LIMIT 1;")
                c_default = cursor.fetchone()
                return c_default["id"] if c_default else ""

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM companies WHERE id = ? OR UPPER(code) = ?;", (cid, cid.upper()))
            c_row = cursor.fetchone()
            if c_row:
                return c_row["id"]
            return cid

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
        cashier_username: str = "A",
        customer_category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Atomically commits a complete sale invoice with:
        - Invoice header (including customer category snapshot)
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
                cursor.execute("SELECT id FROM branches WHERE company_id = ? ORDER BY is_default DESC, id ASC LIMIT 1;", (company_id,))
                b_row = cursor.fetchone()
                if b_row:
                    branch_id = b_row["id"]
                else:
                    branch_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO branches (id, company_id, code, name, is_default)
                        VALUES (?, ?, 'MAIN', 'Main Branch', 1);
                    """, (branch_id, company_id))

            # Resolve customer category and account_id if not explicitly provided
            if not account_id and party_name and party_name.upper() not in ("CASH", "CASH SALE", "WALK-IN"):
                cursor.execute("""
                    SELECT id, customer_category FROM accounts
                    WHERE company_id = ? AND (UPPER(name) = ? OR UPPER(print_name) = ? OR UPPER(alias) = ?)
                    LIMIT 1;
                """, (company_id, party_name.strip().upper(), party_name.strip().upper(), party_name.strip().upper()))
                acc_row = cursor.fetchone()
                if acc_row:
                    account_id = acc_row["id"]
                    if not customer_category and acc_row["customer_category"]:
                        customer_category = acc_row["customer_category"]

            resolved_category = (customer_category or "").strip()
            if not resolved_category:
                if account_id:
                    cursor.execute("SELECT customer_category FROM accounts WHERE id = ?;", (account_id,))
                    acc_row = cursor.fetchone()
                    resolved_category = acc_row["customer_category"] if acc_row and acc_row["customer_category"] else "Direct Customer"
                elif party_name and party_name.upper() not in ("CASH", "CASH SALE", "WALK-IN"):
                    cursor.execute("SELECT customer_category FROM accounts WHERE company_id = ? AND UPPER(name) = ?;", (company_id, party_name.strip().upper()))
                    acc_row = cursor.fetchone()
                    resolved_category = acc_row["customer_category"] if acc_row and acc_row["customer_category"] else "Direct Customer"
                else:
                    resolved_category = "Direct Customer"

            # Calculate line items and voucher totals using TaxService
            totals = tax_service.calculate_voucher_totals(
                items=items,
                company_state=company_state,
                sale_type=sale_type,
                auto_round=True
            )

            # Check company negative stock policy & validate availability
            cursor.execute("SELECT allow_negative_stock FROM company_configs WHERE company_id = ?;", (company_id,))
            cfg_row = cursor.fetchone()
            allow_negative = bool(cfg_row and cfg_row["allow_negative_stock"]) if cfg_row else False

            # Pre-resolve item IDs and validate quantities
            resolved_item_lines = []
            needed_quantities: Dict[str, float] = {}
            item_display_names: Dict[str, str] = {}

            for line in totals["items"]:
                item_id = line.get("id") or line.get("item_id")
                line_name = (line.get("name") or "Product").strip()
                if not item_id or len(str(item_id)) < 10:
                    cursor.execute("""
                        SELECT id, name FROM items WHERE company_id = ? AND (UPPER(name) = ? OR UPPER(alias) = ?);
                    """, (company_id, line_name.upper(), line_name.upper()))
                    resolved_row = cursor.fetchone()
                    if resolved_row:
                        item_id = resolved_row["id"]
                        item_display_names[item_id] = resolved_row["name"]
                    else:
                        item_display_names[item_id or line_name] = line_name
                else:
                    item_display_names[item_id] = line_name

                qty = float(line["qty"])
                if item_id:
                    needed_quantities[item_id] = needed_quantities.get(item_id, 0.0) + qty
                resolved_item_lines.append((item_id, line))

            # Strictly validate stock availability before any invoice generation if negative stock prohibited
            if not allow_negative and branch_id:
                for it_id, total_needed in needed_quantities.items():
                    cursor.execute("""
                        SELECT current_qty FROM stock_balances
                        WHERE branch_id = ? AND item_id = ?;
                    """, (branch_id, it_id))
                    sb_row = cursor.fetchone()
                    if sb_row and sb_row["current_qty"] is not None:
                        current_avail = float(sb_row["current_qty"])
                    else:
                        cursor.execute("SELECT COALESCE(op_stock_qty, 0.0) FROM items WHERE id = ?;", (it_id,))
                        it_rec = cursor.fetchone()
                        current_avail = float(it_rec[0]) if it_rec else 0.0

                    if current_avail - total_needed < -1e-6:
                        prod_name = item_display_names.get(it_id, "Product")
                        raise ValueError(
                            f"Insufficient stock for '{prod_name}'. Available: {current_avail:g}, Requested: {total_needed:g}. "
                            f"Negative stock is disabled by company policy."
                        )

            # Generate next voucher number with concurrency collision resolution
            import time
            import sqlite3
            vch_id = str(uuid.uuid4())
            vch_no = None

            for attempt in range(10):
                vch_no = self.get_next_voucher_number(company_id, series)
                try:
                    # 1. Insert Voucher Header
                    cursor.execute("""
                        INSERT INTO sales_vouchers (
                            id, company_id, branch_id, vch_no, series, vch_date,
                            sale_type, party_name, account_id, mat_centre, narration,
                            subtotal, gross_subtotal, discount_total, taxable_amount, tax_rate, cgst_amount, sgst_amount,
                            igst_amount, round_off, grand_total, payment_method, payment_status, customer_category
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Main Store', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PAID', ?);
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
                        totals["subtotal"],
                        totals.get("discount_total", 0.0),
                        totals["taxable_amount"],
                        18.0,  # general rate ref
                        totals["cgst_amount"],
                        totals["sgst_amount"],
                        totals["igst_amount"],
                        totals["round_off"],
                        totals["grand_total"],
                        payment_method,
                        resolved_category
                    ))
                    break
                except sqlite3.IntegrityError as e:
                    if ("sales_vouchers" in str(e).lower() or "unique" in str(e).lower()) and attempt < 9:
                        time.sleep(0.01 * (attempt + 1))
                        continue
                    raise

            # 2. Insert Line Items and Deduct Stock
            for idx, (item_id, line) in enumerate(resolved_item_lines, start=1):
                qty = float(line["qty"])
                price = float(line["price"])
                amount = float(line["line_total"])
                disc_pct = float(line.get("discount_percent", 0.0))
                disc_amt = float(line.get("discount_amount", 0.0))
                taxable_amt = float(line.get("taxable_amount", 0.0))
                tax_rate = float(line.get("tax_rate", 0.0))
                tax_amt = float(line.get("tax_amount", 0.0))

                cursor.execute("""
                    INSERT INTO sales_voucher_items (
                        id, voucher_id, item_id, sn, item_name, hsn,
                        qty, unit, price, amount, discount_percent, discount_amount,
                        taxable_amount, tax_rate, tax_amount
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
                    disc_pct,
                    disc_amt,
                    taxable_amt,
                    tax_rate,
                    tax_amt
                ))

                # Deduct inventory atomically with negative stock guard
                if item_id and branch_id:
                    # Ensure stock balance row exists initialized from item opening stock if unseeded
                    cursor.execute("""
                        INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                        SELECT ?, ?, ?, ?, COALESCE(op_stock_qty, 0.0)
                        FROM items WHERE id = ?
                        ON CONFLICT(branch_id, item_id) DO NOTHING;
                    """, (str(uuid.uuid4()), company_id, branch_id, item_id, item_id))

                    if not allow_negative:
                        cursor.execute("""
                            UPDATE stock_balances
                            SET current_qty = current_qty - ?, last_updated = CURRENT_TIMESTAMP
                            WHERE branch_id = ? AND item_id = ? AND current_qty >= ?;
                        """, (qty, branch_id, item_id, qty))
                        if cursor.rowcount == 0:
                            cursor.execute("SELECT current_qty FROM stock_balances WHERE branch_id = ? AND item_id = ?;", (branch_id, item_id))
                            row_sb = cursor.fetchone()
                            act_avail = float(row_sb["current_qty"]) if row_sb else 0.0
                            raise ValueError(
                                f"Insufficient stock for '{item_display_names.get(item_id, 'Product')}'. "
                                f"Available: {act_avail:g}, Requested: {qty:g}. Negative stock is disabled."
                            )
                    else:
                        cursor.execute("""
                            UPDATE stock_balances
                            SET current_qty = current_qty - ?, last_updated = CURRENT_TIMESTAMP
                            WHERE branch_id = ? AND item_id = ?;
                        """, (qty, branch_id, item_id))

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

            # 4. Double-Entry Accounting Journal Posting
            journal_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO journal_entries (
                    id, company_id, vch_no, vch_date, vch_type, reference_id, narration
                ) VALUES (?, ?, ?, ?, 'SALE', ?, ?);
            """, (
                journal_id, company_id, vch_no, vch_date, vch_id,
                f"Sales Invoice #{vch_no} to {party_name}"
            ))

            debit_account = f"Cash / Bank ({payment_method})" if party_name == "CASH" else party_name
            cursor.execute("""
                INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                VALUES (?, ?, ?, ?, 0.0, 'Settlement / Customer receivable');
            """, (str(uuid.uuid4()), journal_id, debit_account, float(totals["grand_total"])))

            cursor.execute("""
                INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                VALUES (?, ?, 'Sales Account', 0.0, ?, 'Net sales revenue');
            """, (str(uuid.uuid4()), journal_id, float(totals["taxable_amount"])))

            if totals["cgst_amount"] > 0:
                cursor.execute("""
                    INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                    VALUES (?, ?, 'Output CGST Account', 0.0, ?, 'CGST collected on sales');
                """, (str(uuid.uuid4()), journal_id, float(totals["cgst_amount"])))
            if totals["sgst_amount"] > 0:
                cursor.execute("""
                    INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                    VALUES (?, ?, 'Output SGST Account', 0.0, ?, 'SGST collected on sales');
                """, (str(uuid.uuid4()), journal_id, float(totals["sgst_amount"])))
            if totals["igst_amount"] > 0:
                cursor.execute("""
                    INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                    VALUES (?, ?, 'Output IGST Account', 0.0, ?, 'IGST collected on interstate sales');
                """, (str(uuid.uuid4()), journal_id, float(totals["igst_amount"])))

            if totals.get("round_off"):
                round_val = float(totals["round_off"])
                if round_val > 0:
                    cursor.execute("""
                        INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                        VALUES (?, ?, 'Round Off Account', 0.0, ?, 'Rounding adjustment');
                    """, (str(uuid.uuid4()), journal_id, round_val))
                elif round_val < 0:
                    cursor.execute("""
                        INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                        VALUES (?, ?, 'Round Off Account', ?, 0.0, 'Rounding adjustment');
                    """, (str(uuid.uuid4()), journal_id, abs(round_val)))

            # 5. Audit Log
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

        # Authoritatively evaluate low-stock alerts after real-time inventory deduction
        try:
            from services.inventory_service import inventory_service
            inventory_service.evaluate_low_stock_alerts(company_id)
        except Exception as e:
            logger.debug(f"evaluate_low_stock_alerts after sale checkout: {e}")

        logger.info(f"Invoice {vch_no} saved successfully for company {company_id}. Total: ₹{totals['grand_total']} (Category: {resolved_category})")
        return {
            "voucher_id": vch_id,
            "vch_no": vch_no,
            "customer_category": resolved_category,
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

    def modify_sale_invoice(
        self,
        company_id: str,
        vch_id: str,
        items: List[Dict[str, Any]],
        party_name: str = "CASH",
        account_id: Optional[str] = None,
        sale_type: str = "L/GST-18%",
        payment_method: str = "CASH",
        payments: Optional[List[Dict[str, Any]]] = None,
        branch_id: Optional[str] = None,
        vch_date: Optional[str] = None,
        narration: str = "",
        cashier_username: str = "A",
        customer_category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Modifies an existing sales invoice within an atomic database transaction.
        Reconciles stock balances, replaces stock movements, re-posts double-entry accounting journals,
        and logs the modification audit trail, preserving the original invoice identity and sequential number.

        CRITICAL SECURITY RULE:
        A saved sales bill must NEVER be deleted.
        """
        if not items:
            raise ValueError("Cannot save an empty invoice. At least one line item is required.")

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Fetch existing voucher
            cursor.execute("""
                SELECT * FROM sales_vouchers WHERE company_id = ? AND id = ?;
            """, (company_id, vch_id))
            old_vch = cursor.fetchone()
            if not old_vch:
                raise ValueError(f"Sales Invoice with ID '{vch_id}' not found.")

            vch_no = old_vch["vch_no"]
            series = old_vch["series"] or "Main"
            actual_branch_id = branch_id or old_vch["branch_id"]
            if not actual_branch_id:
                cursor.execute("SELECT id FROM branches WHERE company_id = ? AND is_default = 1;", (company_id,))
                b_row = cursor.fetchone()
                actual_branch_id = b_row["id"] if b_row else None

            # Get company state
            cursor.execute("SELECT state FROM companies WHERE id = ?;", (company_id,))
            c_row = cursor.fetchone()
            company_state = c_row["state"] if c_row and c_row["state"] else "Tamilnadu"

            # 2. Revert previous inventory deductions
            cursor.execute("""
                SELECT item_id, qty FROM sales_voucher_items WHERE voucher_id = ?;
            """, (vch_id,))
            old_items = cursor.fetchall()
            if actual_branch_id:
                for o_it in old_items:
                    o_item_id = o_it["item_id"]
                    o_qty = float(o_it["qty"] or 0.0)
                    if o_item_id and o_qty > 0:
                        cursor.execute("""
                            UPDATE stock_balances
                            SET current_qty = current_qty + ?, last_updated = CURRENT_TIMESTAMP
                            WHERE branch_id = ? AND item_id = ?;
                        """, (o_qty, actual_branch_id, o_item_id))

            # 3. Clean up previous movements, journals, payments, and line items
            cursor.execute("""
                DELETE FROM stock_movements WHERE reference_id = ? AND reference_type = 'INVOICE';
            """, (vch_no,))

            cursor.execute("""
                SELECT id FROM journal_entries WHERE company_id = ? AND reference_id = ?;
            """, (company_id, vch_id))
            for j_row in cursor.fetchall():
                cursor.execute("DELETE FROM journal_entry_lines WHERE journal_id = ?;", (j_row["id"],))
            cursor.execute("DELETE FROM journal_entries WHERE company_id = ? AND reference_id = ?;", (company_id, vch_id))

            cursor.execute("DELETE FROM payments WHERE voucher_id = ?;", (vch_id,))
            cursor.execute("DELETE FROM sales_voucher_items WHERE voucher_id = ?;", (vch_id,))

            # 4. Resolve customer category and account_id
            if not account_id and party_name and party_name.upper() not in ("CASH", "CASH SALE", "WALK-IN"):
                cursor.execute("""
                    SELECT id, customer_category FROM accounts
                    WHERE company_id = ? AND (UPPER(name) = ? OR UPPER(print_name) = ? OR UPPER(alias) = ?)
                    LIMIT 1;
                """, (company_id, party_name.strip().upper(), party_name.strip().upper(), party_name.strip().upper()))
                acc_row = cursor.fetchone()
                if acc_row:
                    account_id = acc_row["id"]
                    if not customer_category and acc_row["customer_category"]:
                        customer_category = acc_row["customer_category"]
            if not account_id:
                account_id = old_vch["account_id"] if "account_id" in old_vch.keys() else None

            resolved_category = (customer_category or "").strip()
            if not resolved_category:
                if account_id:
                    cursor.execute("SELECT customer_category FROM accounts WHERE id = ?;", (account_id,))
                    acc_row = cursor.fetchone()
                    resolved_category = acc_row["customer_category"] if acc_row and acc_row["customer_category"] else "Direct Customer"
                elif party_name and party_name.upper() not in ("CASH", "CASH SALE", "WALK-IN"):
                    cursor.execute("SELECT customer_category FROM accounts WHERE company_id = ? AND UPPER(name) = ?;", (company_id, party_name.strip().upper()))
                    acc_row = cursor.fetchone()
                    resolved_category = acc_row["customer_category"] if acc_row and acc_row["customer_category"] else "Direct Customer"
                else:
                    resolved_category = old_vch["customer_category"] or "Direct Customer"

            # 5. Calculate updated voucher totals
            totals = tax_service.calculate_voucher_totals(
                items=items,
                company_state=company_state,
                sale_type=sale_type,
                auto_round=True
            )

            # Check company negative stock policy & validate availability
            cursor.execute("SELECT allow_negative_stock FROM company_configs WHERE company_id = ?;", (company_id,))
            cfg_row = cursor.fetchone()
            allow_negative = bool(cfg_row and cfg_row["allow_negative_stock"]) if cfg_row else False

            resolved_mod_lines = []
            needed_mod_quantities: Dict[str, float] = {}
            mod_item_display_names: Dict[str, str] = {}

            for line in totals["items"]:
                item_id = line.get("id") or line.get("item_id")
                line_name = (line.get("name") or "Product").strip()
                if not item_id or len(str(item_id)) < 10:
                    cursor.execute("""
                        SELECT id, name FROM items WHERE company_id = ? AND (UPPER(name) = ? OR UPPER(alias) = ?);
                    """, (company_id, line_name.upper(), line_name.upper()))
                    resolved_row = cursor.fetchone()
                    if resolved_row:
                        item_id = resolved_row["id"]
                        mod_item_display_names[item_id] = resolved_row["name"]
                    else:
                        mod_item_display_names[item_id or line_name] = line_name
                else:
                    mod_item_display_names[item_id] = line_name

                qty = float(line["qty"])
                if item_id:
                    needed_mod_quantities[item_id] = needed_mod_quantities.get(item_id, 0.0) + qty
                resolved_mod_lines.append((item_id, line))

            if not allow_negative and actual_branch_id:
                for it_id, total_needed in needed_mod_quantities.items():
                    cursor.execute("""
                        SELECT current_qty FROM stock_balances
                        WHERE branch_id = ? AND item_id = ?;
                    """, (actual_branch_id, it_id))
                    sb_row = cursor.fetchone()
                    current_avail = float(sb_row["current_qty"]) if sb_row and sb_row["current_qty"] is not None else 0.0
                    if current_avail - total_needed < -1e-6:
                        prod_name = mod_item_display_names.get(it_id, "Product")
                        raise ValueError(
                            f"Insufficient stock for '{prod_name}'. Available: {current_avail:g}, Requested: {total_needed:g}. "
                            f"Negative stock is disabled by company policy."
                        )

            # Date fallback
            updated_date = vch_date or old_vch["vch_date"] or datetime.now().strftime("%d-%m-%Y")

            # 6. Update sales_vouchers header (preserves ID, vch_no, created_at)
            cursor.execute("""
                UPDATE sales_vouchers SET
                    vch_date = ?,
                    sale_type = ?,
                    party_name = ?,
                    account_id = ?,
                    narration = ?,
                    subtotal = ?,
                    gross_subtotal = ?,
                    discount_total = ?,
                    taxable_amount = ?,
                    tax_rate = ?,
                    cgst_amount = ?,
                    sgst_amount = ?,
                    igst_amount = ?,
                    round_off = ?,
                    grand_total = ?,
                    payment_method = ?,
                    customer_category = ?
                WHERE id = ? AND company_id = ?;
            """, (
                updated_date,
                sale_type,
                party_name,
                account_id,
                narration,
                totals["subtotal"],
                totals["subtotal"],
                totals.get("discount_total", 0.0),
                totals["taxable_amount"],
                18.0,
                totals["cgst_amount"],
                totals["sgst_amount"],
                totals["igst_amount"],
                totals["round_off"],
                totals["grand_total"],
                payment_method,
                resolved_category,
                vch_id,
                company_id
            ))

            # 7. Insert new line items and deduct updated stock
            for idx, (item_id, line) in enumerate(resolved_mod_lines, start=1):
                qty = float(line["qty"])
                price = float(line["price"])
                amount = float(line["line_total"])
                disc_pct = float(line.get("discount_percent", 0.0))
                disc_amt = float(line.get("discount_amount", 0.0))
                taxable_amt = float(line.get("taxable_amount", 0.0))
                tax_rate = float(line.get("tax_rate", 0.0))
                tax_amt = float(line.get("tax_amount", 0.0))

                cursor.execute("""
                    INSERT INTO sales_voucher_items (
                        id, voucher_id, item_id, sn, item_name, hsn,
                        qty, unit, price, amount, discount_percent, discount_amount,
                        taxable_amount, tax_rate, tax_amount
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
                    disc_pct,
                    disc_amt,
                    taxable_amt,
                    tax_rate,
                    tax_amt
                ))

                if item_id and actual_branch_id:
                    cursor.execute("""
                        INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(branch_id, item_id) DO UPDATE SET
                            current_qty = current_qty - excluded.current_qty,
                            last_updated = CURRENT_TIMESTAMP;
                    """, (str(uuid.uuid4()), company_id, actual_branch_id, item_id, qty))

                    cursor.execute("""
                        INSERT INTO stock_movements (
                            id, company_id, branch_id, item_id, movement_type,
                            qty, unit_cost, reference_type, reference_id, notes
                        ) VALUES (?, ?, ?, ?, 'SALE', ?, ?, 'INVOICE', ?, ?);
                    """, (
                        str(uuid.uuid4()),
                        company_id,
                        actual_branch_id,
                        item_id,
                        -qty,
                        price,
                        vch_no,
                        f"Sale invoice modified by {cashier_username}"
                    ))

            # 8. Insert new Payments
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

            # 9. Double-Entry Accounting Journal Posting
            journal_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO journal_entries (
                    id, company_id, vch_no, vch_date, vch_type, reference_id, narration
                ) VALUES (?, ?, ?, ?, 'SALE', ?, ?);
            """, (
                journal_id, company_id, vch_no, updated_date, vch_id,
                f"Sales Invoice #{vch_no} to {party_name} (Modified)"
            ))

            debit_account = f"Cash / Bank ({payment_method})" if party_name == "CASH" else party_name
            cursor.execute("""
                INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                VALUES (?, ?, ?, ?, 0.0, 'Settlement / Customer receivable');
            """, (str(uuid.uuid4()), journal_id, debit_account, float(totals["grand_total"])))

            cursor.execute("""
                INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                VALUES (?, ?, 'Sales Account', 0.0, ?, 'Net sales revenue');
            """, (str(uuid.uuid4()), journal_id, float(totals["taxable_amount"])))

            if totals["cgst_amount"] > 0:
                cursor.execute("""
                    INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                    VALUES (?, ?, 'Output CGST Account', 0.0, ?, 'CGST collected on sales');
                """, (str(uuid.uuid4()), journal_id, float(totals["cgst_amount"])))
            if totals["sgst_amount"] > 0:
                cursor.execute("""
                    INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                    VALUES (?, ?, 'Output SGST Account', 0.0, ?, 'SGST collected on sales');
                """, (str(uuid.uuid4()), journal_id, float(totals["sgst_amount"])))
            if totals["igst_amount"] > 0:
                cursor.execute("""
                    INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                    VALUES (?, ?, 'Output IGST Account', 0.0, ?, 'IGST collected on interstate sales');
                """, (str(uuid.uuid4()), journal_id, float(totals["igst_amount"])))

            if totals.get("round_off"):
                round_val = float(totals["round_off"])
                if round_val > 0:
                    cursor.execute("""
                        INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                        VALUES (?, ?, 'Round Off Account', 0.0, ?, 'Rounding adjustment');
                    """, (str(uuid.uuid4()), journal_id, round_val))
                elif round_val < 0:
                    cursor.execute("""
                        INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                        VALUES (?, ?, 'Round Off Account', ?, 0.0, 'Rounding adjustment');
                    """, (str(uuid.uuid4()), journal_id, abs(round_val)))

            # 10. Audit Log of Modification
            audit_details = json.dumps({
                "vch_no": vch_no,
                "old_grand_total": float(old_vch["grand_total"] or 0.0),
                "new_grand_total": float(totals["grand_total"]),
                "old_party": old_vch["party_name"],
                "new_party": party_name,
                "items_count": len(totals["items"])
            })
            cursor.execute("""
                INSERT INTO audit_logs (
                    id, company_id, username, action, entity_type, entity_id, details
                ) VALUES (?, ?, ?, 'MODIFY_SALE', 'INVOICE', ?, ?);
            """, (
                str(uuid.uuid4()),
                company_id,
                cashier_username,
                vch_no,
                audit_details
            ))

            conn.commit()

        # Re-evaluate low-stock alerts
        try:
            from services.inventory_service import inventory_service
            inventory_service.evaluate_low_stock_alerts(company_id)
        except Exception as e:
            logger.debug(f"evaluate_low_stock_alerts after sale modify: {e}")

        logger.info(f"Invoice {vch_no} ({vch_id}) modified successfully for company {company_id}. New Total: ₹{totals['grand_total']}")
        return {
            "voucher_id": vch_id,
            "vch_no": vch_no,
            "grand_total": totals["grand_total"],
            "totals": totals
        }

    def delete_sale_invoice(self, company_id: str, vch_id: str) -> None:
        """
        CRITICAL SALES SECURITY RULE:
        A saved sales bill must NEVER be deletable through the Modify option or any service method.
        """
        logger.warning(f"Blocked deletion attempt for sales invoice {vch_id} in company {company_id}.")
        raise PermissionError(
            "Security Rule Violation: A saved sales bill must NEVER be deleted. "
            "Use controlled modification or appropriate sales return / credit note workflow."
        )

    def create_sales_return(
        self,
        company_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Processes a Sales Return (Credit Note).
        - Linked to original sales invoice
        - Restores saleable stock in stock_balances and stock_movements
        - Reverses sales revenue and output tax liability in double-entry journal
        """
        orig_vch_id = data.get("original_voucher_id")
        orig_vch = self.get_voucher_details(company_id, orig_vch_id) if orig_vch_id else None

        customer_name = data.get("customer_name") or (orig_vch.get("party_name") if orig_vch else "CASH")
        orig_inv_no = data.get("original_invoice_no") or (orig_vch.get("vch_no") if orig_vch else "")
        vch_date = data.get("vch_date") or datetime.now().strftime("%d-%m-%Y")
        branch_id = data.get("branch_id") or (orig_vch.get("branch_id") if orig_vch else None)
        reason = data.get("reason") or "Customer Return"
        items = data.get("items") or []

        if not items:
            raise ValueError("Sales return must contain at least one returned item.")

        ret_id = str(uuid.uuid4())
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(id) FROM sales_returns WHERE company_id = ?;", (company_id,))
            cnt = cursor.fetchone()[0] + 1
            vch_no = f"SR-{str(cnt).zfill(6)}"

            total_taxable = 0.0
            total_cgst = 0.0
            total_sgst = 0.0
            total_grand = 0.0

            calculated_items = []
            for idx, it in enumerate(items, start=1):
                item_id = it.get("item_id") or it.get("id")
                name = it.get("name") or it.get("item_name") or f"Item {idx}"
                if not item_id or len(str(item_id)) < 10:
                    cursor.execute("""
                        SELECT id FROM items WHERE company_id = ? AND (UPPER(name) = ? OR UPPER(alias) = ?);
                    """, (company_id, name.strip().upper(), name.strip().upper()))
                    row_it = cursor.fetchone()
                    if row_it:
                        item_id = row_it["id"]

                qty = float(it.get("qty") or 1.0)
                rate = float(it.get("rate") or it.get("price") or 0.0)
                tax_rate = float(it.get("tax_rate") if it.get("tax_rate") is not None else 18.0)
                restock = (it.get("restock_condition") or "SALEABLE").upper()

                taxable = round(qty * rate, 2)
                tax = round(taxable * (tax_rate / 100.0), 2)
                cgst = round(tax / 2.0, 2)
                sgst = round(tax - cgst, 2)
                line_tot = round(taxable + tax, 2)

                total_taxable += taxable
                total_cgst += cgst
                total_sgst += sgst
                total_grand += line_tot

                calculated_items.append({
                    "item_id": item_id,
                    "name": name,
                    "qty": qty,
                    "unit": it.get("unit", "Pcs."),
                    "rate": rate,
                    "tax_rate": tax_rate,
                    "tax_amount": tax,
                    "line_total": line_tot,
                    "restock_condition": restock
                })

            cursor.execute("""
                INSERT INTO sales_returns (
                    id, company_id, branch_id, vch_no, original_voucher_id,
                    original_invoice_no, vch_date, customer_name, reason,
                    taxable_amount, cgst_amount, sgst_amount, igst_amount, grand_total
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?);
            """, (
                ret_id, company_id, branch_id, vch_no, orig_vch_id,
                orig_inv_no, vch_date, customer_name, reason,
                total_taxable, total_cgst, total_sgst, total_grand
            ))

            for it in calculated_items:
                cursor.execute("""
                    INSERT INTO sales_return_items (
                        id, return_id, item_id, sn, item_name, qty, unit, rate,
                        tax_rate, tax_amount, line_total, restock_condition
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    str(uuid.uuid4()), ret_id, it["item_id"], idx, it["name"],
                    it["qty"], it["unit"], it["rate"], it["tax_rate"], it["tax_amount"],
                    it["line_total"], it["restock_condition"]
                ))

                if it["restock_condition"] == "SALEABLE" and it["item_id"] and branch_id:
                    cursor.execute("""
                        INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(branch_id, item_id) DO UPDATE SET
                            current_qty = current_qty + excluded.current_qty,
                            last_updated = CURRENT_TIMESTAMP;
                    """, (str(uuid.uuid4()), company_id, branch_id, it["item_id"], it["qty"]))

                    cursor.execute("""
                        INSERT INTO stock_movements (
                            id, company_id, branch_id, item_id, movement_type,
                            qty, unit_cost, reference_type, reference_id, notes
                        ) VALUES (?, ?, ?, ?, 'SALES_RETURN', ?, ?, 'SALES_RETURN', ?, ?);
                    """, (
                        str(uuid.uuid4()), company_id, branch_id, it["item_id"],
                        it["qty"], it["rate"], vch_no, f"Sales Return from {customer_name}: {reason}"
                    ))

            journal_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO journal_entries (
                    id, company_id, vch_no, vch_date, vch_type, reference_id, narration
                ) VALUES (?, ?, ?, ?, 'SALES_RETURN', ?, ?);
            """, (
                journal_id, company_id, vch_no, vch_date, ret_id,
                f"Sales Return from {customer_name} Credit Note #{vch_no}"
            ))

            cursor.execute("""
                INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                VALUES (?, ?, 'Sales Returns Account', ?, 0.0, 'Reversal of sales revenue');
            """, (str(uuid.uuid4()), journal_id, total_taxable))

            if total_cgst > 0:
                cursor.execute("""
                    INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                    VALUES (?, ?, 'Output CGST Reversal', ?, 0.0, 'Reversal of output tax liability');
                """, (str(uuid.uuid4()), journal_id, total_cgst))
            if total_sgst > 0:
                cursor.execute("""
                    INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                    VALUES (?, ?, 'Output SGST Reversal', ?, 0.0, 'Reversal of output tax liability');
                """, (str(uuid.uuid4()), journal_id, total_sgst))

            cursor.execute("""
                INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                VALUES (?, ?, ?, 0.0, ?, 'Refund / credit note to customer');
            """, (str(uuid.uuid4()), journal_id, f"Customer / Cash ({customer_name})", total_grand))

            conn.commit()

        try:
            from services.inventory_service import inventory_service
            inventory_service.evaluate_low_stock_alerts(company_id)
        except Exception as e:
            logger.debug(f"evaluate_low_stock_alerts after sales return: {e}")

        logger.info(f"Sales Return {vch_no} processed successfully.")
        return {
            "id": ret_id,
            "return_id": ret_id,
            "vch_no": vch_no,
            "grand_total": total_grand,
            "items_count": len(calculated_items)
        }

    def list_sales_returns(self, company_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sales_returns
                WHERE company_id = ?
                ORDER BY vch_date DESC, created_at DESC
                LIMIT ?;
            """, (company_id, limit))
            return [dict(r) for r in cursor.fetchall()]

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

    def get_daily_discount(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        business_date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves the active daily discount setting for the specified company, branch, and business date.
        If no date is supplied, uses current local date (YYYY-MM-DD).
        Discounts configured for previous dates automatically expire and return None.
        """
        today_str = business_date or datetime.now().strftime("%Y-%m-%d")

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if branch_id:
                cursor.execute("""
                    SELECT * FROM daily_discount_configs
                    WHERE company_id = ? AND branch_id = ? AND business_date = ? AND is_active = 1;
                """, (company_id, branch_id, today_str))
            else:
                cursor.execute("""
                    SELECT * FROM daily_discount_configs
                    WHERE company_id = ? AND business_date = ? AND is_active = 1
                    ORDER BY updated_at DESC LIMIT 1;
                """, (company_id, today_str))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def set_daily_discount(
        self,
        company_id: str,
        branch_id: Optional[str],
        business_date: str,
        discount_percent: float,
        is_active: bool = True,
        enabled_by: str = "Admin"
    ) -> Dict[str, Any]:
        """
        Saves or updates the daily discount configuration for a given business date.
        Scoped to company and branch.
        """
        cfg_id = str(uuid.uuid4())
        active_val = 1 if is_active else 0
        disc_val = max(0.0, min(100.0, float(discount_percent)))

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO daily_discount_configs (
                    id, company_id, branch_id, business_date, discount_percent, is_active, enabled_by, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(company_id, branch_id, business_date) DO UPDATE SET
                    discount_percent = excluded.discount_percent,
                    is_active = excluded.is_active,
                    enabled_by = excluded.enabled_by,
                    updated_at = CURRENT_TIMESTAMP;
            """, (cfg_id, company_id, branch_id, business_date, disc_val, active_val, enabled_by))
            conn.commit()

        logger.info(
            f"Daily discount set: Company={company_id}, Branch={branch_id}, Date={business_date}, "
            f"Discount={disc_val}%, Active={is_active}, User={enabled_by}"
        )
        return {
            "company_id": company_id,
            "branch_id": branch_id,
            "business_date": business_date,
            "discount_percent": disc_val,
            "is_active": is_active,
            "enabled_by": enabled_by
        }

    def get_customer_category_discounts(self, company_id: str) -> Dict[str, float]:
        """
        Retrieves configured discount percentages for customer categories.
        Defaults: Commercial = 5.0%, Sub-Commercial = 2.5%, Direct Customer = 0.0%.
        """
        defaults = {
            "Commercial": 5.0,
            "Sub-Commercial": 2.5,
            "Direct Customer": 0.0
        }
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT category, discount_percent FROM customer_category_discounts
                WHERE company_id = ?;
            """, (company_id,))
            rows = cursor.fetchall()
            if rows:
                for r in rows:
                    cat = r["category"]
                    defaults[cat] = float(r["discount_percent"])
            else:
                for cat, pct in defaults.items():
                    cursor.execute("""
                        INSERT INTO customer_category_discounts (id, company_id, category, discount_percent)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(company_id, category) DO NOTHING;
                    """, (str(uuid.uuid4()), company_id, cat, pct))
                conn.commit()
        return defaults

    def set_customer_category_discounts(
        self,
        company_id: str,
        discounts: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Saves updated discount percentages for customer categories.
        Validates 0.0 <= discount_percent <= 100.0.
        """
        updated = {}
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            for cat, val in discounts.items():
                if cat not in ("Commercial", "Sub-Commercial", "Direct Customer"):
                    continue
                try:
                    pct = float(val)
                except (ValueError, TypeError):
                    pct = 0.0
                if pct < 0.0 or pct > 100.0:
                    raise ValueError(f"Discount percentage for {cat} must be between 0.00% and 100.00%.")
                pct = round(pct, 2)
                cursor.execute("""
                    INSERT INTO customer_category_discounts (id, company_id, category, discount_percent, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(company_id, category) DO UPDATE SET
                        discount_percent = excluded.discount_percent,
                        updated_at = CURRENT_TIMESTAMP;
                """, (str(uuid.uuid4()), company_id, cat, pct))
                updated[cat] = pct
            conn.commit()
        logger.info(f"Customer category discounts updated for company {company_id}: {updated}")
        return self.get_customer_category_discounts(company_id)

    def calculate_authoritative_discount(
        self,
        company_id: str,
        customer_category: str = "Direct Customer",
        manual_discount_percent: Optional[float] = None,
        apply_daily_discount: bool = False,
        business_date: Optional[str] = None
    ) -> float:
        """
        Determines the authoritative line discount percentage following precedence rules:
        1. Manual cashier override on line item takes explicit precedence if > 0.
        2. Customer Category Discount sets the baseline rate.
        3. If Daily Discount is active and apply_daily_discount is True, prevents double-discounting
           by applying max(category_discount, daily_discount).
        4. Caps discount between 0.0% and 100.0%.
        """
        if manual_discount_percent is not None and float(manual_discount_percent) > 0.0:
            return round(min(100.0, max(0.0, float(manual_discount_percent))), 2)

        rates = self.get_customer_category_discounts(company_id)
        cat_rate = rates.get(customer_category, 0.0)

        daily_rate = 0.0
        if apply_daily_discount:
            daily_cfg = self.get_daily_discount(company_id, business_date=business_date)
            if daily_cfg and daily_cfg.get("is_active"):
                daily_rate = float(daily_cfg.get("discount_percent") or 0.0)

        effective_rate = max(cat_rate, daily_rate)
        return round(min(100.0, max(0.0, effective_rate)), 2)

    def get_today_sales_history(
        self,
        company_id: str,
        branch_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves sales invoices created for the active company and branch ONLY on the current business date.
        Date restriction is enforced server-side.
        No previous-date or arbitrary historical date access permitted.
        """
        actual_comp_id = self._resolve_company_id(company_id)
        now = datetime.now()
        today_dash = now.strftime("%d-%m-%Y")
        today_iso = now.strftime("%Y-%m-%d")

        query = """
            SELECT sv.id, sv.vch_no, sv.vch_date, sv.created_at, sv.party_name, sv.grand_total,
                   COALESCE(sv.payment_method, 'CASH') as payment_method,
                   COALESCE(sv.payment_status, 'PAID') as payment_status,
                   sv.subtotal, sv.taxable_amount, sv.cgst_amount, sv.sgst_amount, sv.round_off,
                   sv.discount_total, sv.customer_category
            FROM sales_vouchers sv
            WHERE sv.company_id = ?
              AND (
                  sv.vch_date = ? 
                  OR sv.vch_date = ? 
                  OR substr(sv.created_at, 1, 10) = ?
              )
        """
        params = [actual_comp_id, today_dash, today_iso, today_iso]
        if branch_id and str(branch_id).strip():
            query += " AND (sv.branch_id = ? OR sv.branch_id IS NULL)"
            params.append(str(branch_id).strip())

        query += " ORDER BY sv.created_at DESC;"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

        results = []
        for r in rows:
            row_dict = dict(r)
            # Fetch item count for summary
            with self.db.get_connection() as conn2:
                c2 = conn2.cursor()
                c2.execute("SELECT COUNT(*), SUM(qty) FROM sales_voucher_items WHERE voucher_id = ?;", (row_dict["id"],))
                cnt_row = c2.fetchone()
                row_dict["item_count"] = cnt_row[0] if cnt_row else 0
                row_dict["total_qty"] = float(cnt_row[1] or 0.0) if cnt_row else 0.0
            results.append(row_dict)

        logger.info(f"Retrieved {len(results)} today's sales invoices for company {company_id} on {today_iso}")
        return results


billing_service = BillingService()

