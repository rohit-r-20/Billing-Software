"""
Purchase Management Service for Anti Matrix Billing ERP.
Handles multi-item Purchase Vouchers, separate Supplier Bill Numbers, duplicate bill checks,
stock-inward ledger postings, supplier payable updates, Purchase Returns (Debit Notes),
and double-entry accounting journal postings.
"""
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Tuple
from db.database import db_manager, DatabaseManager
from services.supplier_service import SupplierService
from services.tax_service import tax_service
from core.logging_config import logger


def round_cur(val: float) -> float:
    return float(Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class PurchaseService:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or db_manager
        self.supplier_service = SupplierService(self.db)

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

    def _get_default_branch_id(self, company_id: str) -> Optional[str]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM branches WHERE company_id = ? AND is_default = 1;", (company_id,))
            row = cursor.fetchone()
            if row:
                return row["id"]
            cursor.execute("SELECT id FROM branches WHERE company_id = ? LIMIT 1;", (company_id,))
            row2 = cursor.fetchone()
            return row2["id"] if row2 else None

    def get_next_purchase_voucher_number(self, company_id: str, series: str = "Main") -> str:
        """Calculates next sequential internal purchase voucher number e.g. PUR-000001."""
        actual_comp_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT vch_no FROM purchase_vouchers
                WHERE company_id = ?;
            """, (actual_comp_id,))
            rows = cursor.fetchall()
            max_num = 0
            for r in rows:
                num_str = "".join(ch for ch in r["vch_no"] if ch.isdigit())
                if num_str:
                    try:
                        n = int(num_str)
                        if n > max_num:
                            max_num = n
                    except ValueError:
                        pass
            next_num = max_num + 1
            return f"PUR-{str(next_num).zfill(6)}"

    def check_duplicate_supplier_invoice(
        self,
        company_id: str,
        supplier_name: str,
        supplier_invoice_no: str,
        supplier_invoice_date: str,
        exclude_voucher_id: Optional[str] = None
    ) -> bool:
        """Returns True if a purchase invoice with the same supplier, bill number, and date already exists."""
        actual_comp_id = self._resolve_company_id(company_id)
        norm_supp = supplier_name.strip().upper()
        norm_inv = supplier_invoice_no.strip().upper()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if exclude_voucher_id:
                cursor.execute("""
                    SELECT id FROM purchase_vouchers
                    WHERE company_id = ? AND UPPER(supplier_name) = ?
                      AND UPPER(supplier_invoice_no) = ? AND supplier_invoice_date = ?
                      AND is_cancelled = 0 AND id != ?;
                """, (actual_comp_id, norm_supp, norm_inv, supplier_invoice_date, exclude_voucher_id))
            else:
                cursor.execute("""
                    SELECT id FROM purchase_vouchers
                    WHERE company_id = ? AND UPPER(supplier_name) = ?
                      AND UPPER(supplier_invoice_no) = ? AND supplier_invoice_date = ?
                      AND is_cancelled = 0;
                """, (actual_comp_id, norm_supp, norm_inv, supplier_invoice_date))
            return cursor.fetchone() is not None

    def create_purchase_voucher(
        self,
        company_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Atomically commits an authoritative Purchase Voucher:
        - Validates unique supplier bill number
        - Calculates line taxes, taxable amounts, and additional expenses
        - Inserts purchase voucher & items
        - Increases stock in central stock balances and movement ledger
        - Updates supplier ledger & payable balance
        - Posts double-entry journal lines
        - Logs audit record
        """
        actual_comp_id = self._resolve_company_id(company_id)
        supplier_name = (data.get("supplier_name") or data.get("supplierName") or "").strip()
        if not supplier_name:
            raise ValueError("Supplier Name is required.")

        supp_inv_no = (data.get("supplier_invoice_no") or data.get("supplierInvoiceNo") or "").strip()
        if not supp_inv_no:
            raise ValueError("Supplier Invoice / Bill Number is required.")

        supp_inv_date = (data.get("supplier_invoice_date") or data.get("supplierInvoiceDate") or "").strip()
        if not supp_inv_date:
            supp_inv_date = datetime.now().strftime("%Y-%m-%d")

        vch_date = (data.get("vch_date") or data.get("vchDate") or datetime.now().strftime("%Y-%m-%d")).strip()
        branch_id = data.get("branch_id") or self._get_default_branch_id(actual_comp_id)
        payment_type = (data.get("payment_type") or data.get("paymentType") or "CREDIT").strip().upper()
        purchase_type = data.get("purchase_type") or "GST Purchase"
        narration = data.get("narration") or ""
        additional_expenses = float(data.get("additional_expenses") or 0.0)
        is_draft = 1 if data.get("is_draft") else 0
        created_by = data.get("created_by") or "Admin"

        raw_items = data.get("items") or []
        if not raw_items:
            raise ValueError("Purchase voucher must contain at least one line item.")

        # Duplicate Supplier Invoice Check (unless draft)
        if not is_draft and self.check_duplicate_supplier_invoice(actual_comp_id, supplier_name, supp_inv_no, supp_inv_date):
            raise ValueError(
                f"Duplicate Supplier Invoice detected! A purchase invoice with Supplier '{supplier_name}', "
                f"Invoice Number '{supp_inv_no}', and Date '{supp_inv_date}' is already posted in this company."
            )

        # Supplier resolution / automatic registration
        supp_obj = self.supplier_service.find_supplier_by_name(actual_comp_id, supplier_name)
        if not supp_obj:
            saved_supp = self.supplier_service.save_supplier(actual_comp_id, {
                "name": supplier_name,
                "gstin": data.get("supplier_gstin", ""),
                "state": data.get("supplier_state", "Tamilnadu"),
                "address": data.get("supplier_address", "")
            })
            supplier_id = saved_supp["id"]
        else:
            supplier_id = supp_obj["id"]

        supplier_gstin = data.get("supplier_gstin") or (supp_obj.get("gstin") if supp_obj else "")
        supplier_state = data.get("supplier_state") or (supp_obj.get("state") if supp_obj else "Tamilnadu")
        place_of_supply = data.get("place_of_supply") or supplier_state

        # Calculate Items & Taxes
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT state FROM companies WHERE id = ?;", (actual_comp_id,))
            comp_state_row = cursor.fetchone()
            company_state = comp_state_row["state"] if comp_state_row else "Tamilnadu"

        is_interstate = (company_state.strip().lower() != supplier_state.strip().lower())

        calculated_items = []
        gross_subtotal = Decimal("0")
        total_discount = Decimal("0")
        taxable_total = Decimal("0")
        cgst_total = Decimal("0")
        sgst_total = Decimal("0")
        igst_total = Decimal("0")

        for idx, it in enumerate(raw_items, start=1):
            name = (it.get("name") or it.get("item_name") or f"Item {idx}").strip()
            item_id = it.get("id") or it.get("item_id")
            barcode = it.get("barcode") or it.get("alias") or ""
            qty = Decimal(str(it.get("qty") or 1.0))
            free_qty = Decimal(str(it.get("free_qty") or 0.0))
            unit = it.get("unit") or "Pcs."
            rate = Decimal(str(it.get("purchase_rate") or it.get("rate") or it.get("price") or 0.0))
            disc_pct = Decimal(str(it.get("discount_percent") or 0.0))
            tax_rate = Decimal(str(it.get("tax_rate") if it.get("tax_rate") is not None else 18.0))

            # Line calculations
            gross = rate * qty
            disc_amt = gross * (disc_pct / Decimal("100"))
            taxable = gross - disc_amt
            tax = taxable * (tax_rate / Decimal("100"))
            line_tot = taxable + tax

            if is_interstate:
                cgst = Decimal("0")
                sgst = Decimal("0")
                igst = tax
            else:
                cgst = (tax / Decimal("2")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                sgst = tax - cgst
                igst = Decimal("0")

            gross_subtotal += gross
            total_discount += disc_amt
            taxable_total += taxable
            cgst_total += cgst
            sgst_total += sgst
            igst_total += igst

            calculated_items.append({
                "sn": idx,
                "item_id": item_id,
                "name": name,
                "barcode": barcode,
                "qty": float(qty),
                "free_qty": float(free_qty),
                "unit": unit,
                "purchase_rate": float(rate),
                "discount_percent": float(disc_pct),
                "discount_amount": float(disc_amt),
                "taxable_amount": float(taxable),
                "tax_rate": float(tax_rate),
                "cgst_amount": float(cgst),
                "sgst_amount": float(sgst),
                "igst_amount": float(igst),
                "cess_amount": 0.0,
                "line_total": float(line_tot),
                "batch_no": it.get("batch_no") or "",
                "expiry_date": it.get("expiry_date") or ""
            })

        total_tax = cgst_total + sgst_total + igst_total
        raw_grand = taxable_total + total_tax + Decimal(str(additional_expenses))
        rounded_grand = raw_grand.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        round_off = rounded_grand - raw_grand

        amount_paid = float(rounded_grand) if payment_type in ("CASH", "BANK") else float(data.get("amount_paid") or 0.0)
        outstanding = float(rounded_grand) - amount_paid

        vch_id = str(uuid.uuid4())
        vch_no = data.get("vch_no") or self.get_next_purchase_voucher_number(actual_comp_id)

        # Atomic commit to DB
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Insert Purchase Voucher
            cursor.execute("""
                INSERT INTO purchase_vouchers (
                    id, company_id, branch_id, vch_no, supplier_invoice_no,
                    supplier_invoice_date, vch_date, supplier_id, supplier_name,
                    supplier_gstin, supplier_address, supplier_state, place_of_supply,
                    payment_type, due_date, purchase_type, narration, gross_amount,
                    discount_total, additional_expenses, taxable_amount, cgst_amount,
                    sgst_amount, igst_amount, cess_amount, round_off, grand_total,
                    amount_paid, outstanding_balance, is_draft, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                vch_id, actual_comp_id, branch_id, vch_no, supp_inv_no,
                supp_inv_date, vch_date, supplier_id, supplier_name,
                supplier_gstin, data.get("supplier_address", ""), supplier_state, place_of_supply,
                payment_type, data.get("due_date", ""), purchase_type, narration,
                float(gross_subtotal), float(total_discount), additional_expenses,
                float(taxable_total), float(cgst_total), float(sgst_total), float(igst_total),
                0.0, float(round_off), float(rounded_grand), amount_paid, outstanding,
                is_draft, created_by
            ))

            # 2. Insert Line Items and Update Inventory (if not draft)
            for it in calculated_items:
                item_id = it["item_id"]
                # Resolve item_id if missing by name or barcode
                if not item_id:
                    cursor.execute("""
                        SELECT id FROM items WHERE company_id = ? AND UPPER(name) = ?;
                    """, (actual_comp_id, it["name"].upper()))
                    row_it = cursor.fetchone()
                    if row_it:
                        item_id = row_it["id"]

                cursor.execute("""
                    INSERT INTO purchase_voucher_items (
                        id, voucher_id, item_id, sn, barcode, item_name,
                        hsn, qty, free_qty, unit, purchase_rate, discount_percent,
                        discount_amount, taxable_amount, tax_rate, cgst_amount,
                        sgst_amount, igst_amount, cess_amount, line_total,
                        batch_no, expiry_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    str(uuid.uuid4()), vch_id, item_id, it["sn"], it["barcode"],
                    it["name"], "", it["qty"], it["free_qty"], it["unit"],
                    it["purchase_rate"], it["discount_percent"], it["discount_amount"],
                    it["taxable_amount"], it["tax_rate"], it["cgst_amount"],
                    it["sgst_amount"], it["igst_amount"], 0.0, it["line_total"],
                    it["batch_no"], it["expiry_date"]
                ))

                if not is_draft and item_id and branch_id:
                    total_inward = it["qty"] + it["free_qty"]
                    # Update stock balance
                    cursor.execute("""
                        INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(branch_id, item_id) DO UPDATE SET
                            current_qty = current_qty + excluded.current_qty,
                            last_updated = CURRENT_TIMESTAMP;
                    """, (str(uuid.uuid4()), actual_comp_id, branch_id, item_id, total_inward))

                    # Update stock movement ledger
                    cursor.execute("""
                        INSERT INTO stock_movements (
                            id, company_id, branch_id, item_id, movement_type,
                            qty, unit_cost, reference_type, reference_id, notes
                        ) VALUES (?, ?, ?, ?, 'PURCHASE', ?, ?, 'PURCHASE', ?, ?);
                    """, (
                        str(uuid.uuid4()), actual_comp_id, branch_id, item_id,
                        total_inward, it["purchase_rate"], vch_no,
                        f"Purchase Bill #{supp_inv_no} from {supplier_name}"
                    ))

                    # Optional Batch Tracking
                    if it["batch_no"]:
                        cursor.execute("""
                            INSERT INTO stock_batches (
                                id, company_id, item_id, batch_no, expiry_date,
                                purchase_rate, qty_received, qty_available, supplier_id, purchase_voucher_id
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(company_id, item_id, batch_no) DO UPDATE SET
                                qty_received = qty_received + excluded.qty_received,
                                qty_available = qty_available + excluded.qty_available;
                        """, (
                            str(uuid.uuid4()), actual_comp_id, item_id, it["batch_no"],
                            it["expiry_date"], it["purchase_rate"], total_inward,
                            total_inward, supplier_id, vch_id
                        ))

            # 3. Update Supplier Balance (if not draft and credit/unpaid portion)
            if not is_draft and outstanding > 0 and supplier_id:
                cursor.execute("""
                    UPDATE suppliers
                    SET current_balance = current_balance + ?, updated_at = CURRENT_TIMESTAMP
                    WHERE company_id = ? AND id = ?;
                """, (outstanding, actual_comp_id, supplier_id))

            # 4. Double-Entry Accounting Journal Posting (if not draft)
            if not is_draft:
                journal_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO journal_entries (
                        id, company_id, vch_no, vch_date, vch_type, reference_id, narration
                    ) VALUES (?, ?, ?, ?, 'PURCHASE', ?, ?);
                """, (
                    journal_id, actual_comp_id, vch_no, vch_date, vch_id,
                    f"Purchase from {supplier_name} Inv #{supp_inv_no}"
                ))

                # Dr Purchase / Inventory Account
                cursor.execute("""
                    INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                    VALUES (?, ?, 'Purchase Account', ?, 0.0, 'Gross Purchases less discounts');
                """, (str(uuid.uuid4()), journal_id, float(taxable_total)))

                # Dr Input GST
                if cgst_total > 0:
                    cursor.execute("""
                        INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                        VALUES (?, ?, 'Input CGST Account', ?, 0.0, 'Eligible Input Tax Credit');
                    """, (str(uuid.uuid4()), journal_id, float(cgst_total)))
                if sgst_total > 0:
                    cursor.execute("""
                        INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                        VALUES (?, ?, 'Input SGST Account', ?, 0.0, 'Eligible Input Tax Credit');
                    """, (str(uuid.uuid4()), journal_id, float(sgst_total)))
                if igst_total > 0:
                    cursor.execute("""
                        INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                        VALUES (?, ?, 'Input IGST Account', ?, 0.0, 'Eligible Inter-State Input Tax Credit');
                    """, (str(uuid.uuid4()), journal_id, float(igst_total)))

                # Additional Expenses
                if additional_expenses > 0:
                    cursor.execute("""
                        INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                        VALUES (?, ?, 'Freight / Inward Expenses', ?, 0.0, 'Landed cost expenses');
                    """, (str(uuid.uuid4()), journal_id, additional_expenses))

                # Round Off
                if round_off > 0:
                    cursor.execute("""
                        INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                        VALUES (?, ?, 'Round Off Account', ?, 0.0, 'Purchase rounding adjustment');
                    """, (str(uuid.uuid4()), journal_id, float(round_off)))
                elif round_off < 0:
                    cursor.execute("""
                        INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                        VALUES (?, ?, 'Round Off Account', 0.0, ?, 'Purchase rounding adjustment');
                    """, (str(uuid.uuid4()), journal_id, float(abs(round_off))))

                # Cr Supplier Account / Cash / Bank
                credit_account = supplier_name if payment_type == "CREDIT" else f"Cash / Bank ({payment_type})"
                cursor.execute("""
                    INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                    VALUES (?, ?, ?, 0.0, ?, 'Purchase invoice liability / settlement');
                """, (str(uuid.uuid4()), journal_id, credit_account, float(rounded_grand)))

            # 5. Audit Log
            cursor.execute("""
                INSERT INTO audit_logs (id, company_id, username, action, entity_type, entity_id, details)
                VALUES (?, ?, ?, 'POST_PURCHASE', 'PURCHASE_VOUCHER', ?, ?);
            """, (
                str(uuid.uuid4()), actual_comp_id, created_by, vch_no,
                f"Posted purchase bill #{supp_inv_no} from {supplier_name} for ₹{float(rounded_grand):.2f}"
            ))

            conn.commit()

        if not is_draft:
            try:
                self.inventory_service.evaluate_low_stock_alerts(actual_comp_id)
            except Exception as e:
                logger.debug(f"evaluate_low_stock_alerts after purchase: {e}")

        logger.info(f"Purchase Voucher {vch_no} (Bill #{supp_inv_no}) successfully committed for company {actual_comp_id}.")
        return {
            "voucher_id": vch_id,
            "vch_no": vch_no,
            "supplier_invoice_no": supp_inv_no,
            "grand_total": float(rounded_grand),
            "amount_paid": amount_paid,
            "outstanding_balance": outstanding,
            "is_draft": bool(is_draft),
            "items_count": len(calculated_items)
        }

    def list_purchase_vouchers(self, company_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Lists purchase vouchers with supplier and amount metadata for the Purchase Register."""
        actual_comp_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT pv.*, s.mobile as supplier_mobile
                FROM purchase_vouchers pv
                LEFT JOIN suppliers s ON s.id = pv.supplier_id
                WHERE pv.company_id = ? AND pv.is_cancelled = 0
                ORDER BY pv.vch_date DESC, pv.created_at DESC
                LIMIT ?;
            """, (actual_comp_id, limit))
            return [dict(r) for r in cursor.fetchall()]

    def get_purchase_voucher_details(self, company_id: str, voucher_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves complete purchase voucher with line items."""
        actual_comp_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT pv.*, s.mobile, s.email, s.gstin as supplier_reg_gstin
                FROM purchase_vouchers pv
                LEFT JOIN suppliers s ON s.id = pv.supplier_id
                WHERE pv.company_id = ? AND pv.id = ?;
            """, (actual_comp_id, voucher_id))
            vch = cursor.fetchone()
            if not vch:
                return None

            cursor.execute("""
                SELECT pvi.*, i.sales_price as current_mrp
                FROM purchase_voucher_items pvi
                LEFT JOIN items i ON i.id = pvi.item_id
                WHERE pvi.voucher_id = ?
                ORDER BY pvi.sn ASC;
            """, (voucher_id,))
            items = [dict(r) for r in cursor.fetchall()]

            res = dict(vch)
            res["items"] = items
            return res

    def create_purchase_return(
        self,
        company_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Records a Purchase Return (Debit Note).
        - Validates against original purchase voucher
        - Decreases stock from authoritative inventory
        - Reverses supplier balance and accounts payable
        - Posts reversal journal entry
        """
        actual_comp_id = self._resolve_company_id(company_id)
        orig_vch_id = data.get("original_voucher_id")
        orig_vch = self.get_purchase_voucher_details(actual_comp_id, orig_vch_id) if orig_vch_id else None

        supplier_name = data.get("supplier_name") or (orig_vch.get("supplier_name") if orig_vch else "")
        supplier_id = data.get("supplier_id") or (orig_vch.get("supplier_id") if orig_vch else None)
        orig_supp_inv = data.get("original_supplier_inv_no") or (orig_vch.get("supplier_invoice_no") if orig_vch else "")
        vch_date = data.get("vch_date") or datetime.now().strftime("%Y-%m-%d")
        branch_id = data.get("branch_id") or (orig_vch.get("branch_id") if orig_vch else self._get_default_branch_id(actual_comp_id))
        reason = data.get("reason") or "Defective / Return Goods"
        items = data.get("items") or []

        if not items:
            raise ValueError("Purchase return must specify at least one return line item.")

        ret_id = str(uuid.uuid4())
        # Generate return voucher number
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(id) FROM purchase_returns WHERE company_id = ?;", (actual_comp_id,))
            cnt = cursor.fetchone()[0] + 1
            vch_no = f"PR-{str(cnt).zfill(6)}"

            total_taxable = Decimal("0")
            total_cgst = Decimal("0")
            total_sgst = Decimal("0")
            total_igst = Decimal("0")
            total_grand = Decimal("0")

            calculated_items = []
            for idx, it in enumerate(items, start=1):
                item_id = it.get("item_id") or it.get("id")
                name = it.get("name") or it.get("item_name") or f"Item {idx}"
                qty = Decimal(str(it.get("qty") or 1.0))
                rate = Decimal(str(it.get("rate") or it.get("purchase_rate") or 0.0))
                tax_rate = Decimal(str(it.get("tax_rate") or 18.0))

                taxable = rate * qty
                tax = taxable * (tax_rate / Decimal("100"))
                line_tot = taxable + tax

                total_taxable += taxable
                total_cgst += tax / Decimal("2")
                total_sgst += tax / Decimal("2")
                total_grand += line_tot

                calculated_items.append({
                    "item_id": item_id,
                    "name": name,
                    "qty": float(qty),
                    "unit": it.get("unit", "Pcs."),
                    "rate": float(rate),
                    "tax_rate": float(tax_rate),
                    "tax_amount": float(tax),
                    "line_total": float(line_tot)
                })

            # Insert Purchase Return Header
            cursor.execute("""
                INSERT INTO purchase_returns (
                    id, company_id, branch_id, vch_no, original_voucher_id,
                    original_supplier_inv_no, vch_date, supplier_id, supplier_name,
                    reason, taxable_amount, cgst_amount, sgst_amount, igst_amount, grand_total
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                ret_id, actual_comp_id, branch_id, vch_no, orig_vch_id,
                orig_supp_inv, vch_date, supplier_id, supplier_name,
                reason, float(total_taxable), float(total_cgst), float(total_sgst),
                float(total_igst), float(total_grand)
            ))

            for it in calculated_items:
                item_id = it["item_id"]
                qty = it["qty"]
                cursor.execute("""
                    INSERT INTO purchase_return_items (
                        id, return_id, item_id, sn, item_name, qty, unit, rate,
                        tax_rate, tax_amount, line_total
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    str(uuid.uuid4()), ret_id, item_id, idx, it["name"],
                    qty, it["unit"], it["rate"], it["tax_rate"], it["tax_amount"], it["line_total"]
                ))

                # Deduct inventory for returned goods
                if item_id and branch_id:
                    cursor.execute("""
                        UPDATE stock_balances
                        SET current_qty = current_qty - ?, last_updated = CURRENT_TIMESTAMP
                        WHERE branch_id = ? AND item_id = ?;
                    """, (qty, branch_id, item_id))

                    cursor.execute("""
                        INSERT INTO stock_movements (
                            id, company_id, branch_id, item_id, movement_type,
                            qty, unit_cost, reference_type, reference_id, notes
                        ) VALUES (?, ?, ?, ?, 'PURCHASE_RETURN', ?, ?, 'PURCHASE_RETURN', ?, ?);
                    """, (
                        str(uuid.uuid4()), actual_comp_id, branch_id, item_id,
                        -qty, it["rate"], vch_no, f"Return against bill #{orig_supp_inv}: {reason}"
                    ))

            # Adjust supplier balance
            if supplier_id:
                cursor.execute("""
                    UPDATE suppliers
                    SET current_balance = current_balance - ?, updated_at = CURRENT_TIMESTAMP
                    WHERE company_id = ? AND id = ?;
                """, (float(total_grand), actual_comp_id, supplier_id))

            # Accounting Reversal Posting
            journal_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO journal_entries (
                    id, company_id, vch_no, vch_date, vch_type, reference_id, narration
                ) VALUES (?, ?, ?, ?, 'PURCHASE_RETURN', ?, ?);
            """, (
                journal_id, actual_comp_id, vch_no, vch_date, ret_id,
                f"Purchase Return to {supplier_name} Ref #{vch_no}"
            ))

            # Dr Supplier Account (liability reduction)
            cursor.execute("""
                INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                VALUES (?, ?, ?, ?, 0.0, 'Debit Note against purchase return');
            """, (str(uuid.uuid4()), journal_id, supplier_name, float(total_grand)))

            # Cr Purchase Return / Inventory
            cursor.execute("""
                INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                VALUES (?, ?, 'Purchase Returns Account', 0.0, ?, 'Goods returned to vendor');
            """, (str(uuid.uuid4()), journal_id, float(total_taxable)))

            if total_cgst > 0:
                cursor.execute("""
                    INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                    VALUES (?, ?, 'Input CGST Reversal', 0.0, ?, 'Reversal of Input Tax Credit');
                """, (str(uuid.uuid4()), journal_id, float(total_cgst)))
            if total_sgst > 0:
                cursor.execute("""
                    INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                    VALUES (?, ?, 'Input SGST Reversal', 0.0, ?, 'Reversal of Input Tax Credit');
                """, (str(uuid.uuid4()), journal_id, float(total_sgst)))

            conn.commit()

        logger.info(f"Purchase Return {vch_no} processed successfully.")
        return {
            "return_id": ret_id,
            "vch_no": vch_no,
            "grand_total": float(total_grand),
            "items_count": len(calculated_items)
        }


purchase_service = PurchaseService()
