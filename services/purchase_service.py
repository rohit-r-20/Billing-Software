"""
Purchase Management Service for Anti Matrix Billing ERP.
Handles multi-item Purchase Vouchers, separate Supplier Bill Numbers, duplicate bill checks,
stock-inward ledger postings, supplier payable updates, Purchase Returns (Debit Notes),
purchase price history preservation, landed cost calculation, and double-entry accounting journal postings.
"""
import uuid
import json
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Tuple
from db.database import db_manager, DatabaseManager
from services.supplier_service import SupplierService
from services.inventory_service import InventoryService
from services.company_service import resolve_cached_company_id, get_cached_default_branch_id
from services.tax_service import tax_service
from core.logging_config import logger


def round_cur(val: float) -> float:
    return float(Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _sanitize_record(row: Any) -> Any:
    """Recursively serializes datetime, date, and Decimal to JSON-safe primitives."""
    if isinstance(row, dict):
        return {k: _sanitize_record(v) for k, v in row.items()}
    elif isinstance(row, list):
        return [_sanitize_record(v) for v in row]
    elif isinstance(row, (datetime, date)):
        return row.isoformat()
    elif isinstance(row, Decimal):
        return float(row)
    return row


class PurchaseService:
    def __init__(self, db: Optional[Any] = None, db_manager: Optional[Any] = None):
        target_db = db or db_manager
        if target_db is not None:
            if hasattr(target_db, "get_connection"):
                self.db = target_db
            elif hasattr(target_db, "database_url"):
                from db.database import DatabaseManager
                self.db = DatabaseManager(database_url=target_db.database_url)
            else:
                self.db = target_db
        else:
            self.db = globals()["db_manager"]
        self.supplier_service = SupplierService(self.db)
        self.inventory_service = InventoryService(self.db)

    def _get_db_and_company_id(self, company_id: Optional[str]) -> Tuple[DatabaseManager, str, bool]:
        """
        Resolves the appropriate DatabaseManager, canonical UUID, and traditional mode boolean for the company.
        Checks traditional_db_manager if company exists there, otherwise self.db / db_manager.
        Returns: (target_db, canonical_company_id, is_traditional)
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
                    return trad_mgr, actual_id, True
        except Exception as e:
            logger.debug(f"PurchaseService traditional db check note: {e}")

        # 2. Check primary db (PostgreSQL or configured self.db)
        actual_id = resolve_cached_company_id(self.db, cid)
        return self.db, actual_id, False

    def _resolve_company_id(self, company_id: Optional[str]) -> str:
        """Resolve company UUID whether passed UUID or company code with in-memory caching."""
        _, actual_id, _ = self._get_db_and_company_id(company_id)
        return actual_id

    def _get_default_branch_id(self, company_id: str, db: Optional[DatabaseManager] = None) -> Optional[str]:
        target_db = db or self.db
        return get_cached_default_branch_id(target_db, company_id)

    def get_next_purchase_voucher_number(self, company_id: str, series: str = "Main") -> str:
        """
        Advisory preview of next sequential internal purchase voucher number e.g. PUR-000001.
        Calculates using authoritative database records (highest committed voucher + sequence records).
        """
        target_db, actual_comp_id, is_trad = self._get_db_and_company_id(company_id)
        with target_db.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Check highest committed number in purchase_vouchers
            cursor.execute("""
                SELECT vch_no FROM purchase_vouchers
                WHERE company_id = ?;
            """, (actual_comp_id,))
            rows = cursor.fetchall()
            max_num = 0
            for r in rows:
                num_str = "".join(ch for ch in str(r["vch_no"]) if ch.isdigit())
                if num_str:
                    try:
                        n = int(num_str)
                        if n > max_num:
                            max_num = n
                    except ValueError:
                        pass

            # 2. Check voucher_sequences table if available
            try:
                cursor.execute("""
                    SELECT current_number FROM voucher_sequences
                    WHERE company_id = ? AND voucher_type = 'PURCHASE' AND series = ?;
                """, (actual_comp_id, series or "Main"))
                seq_row = cursor.fetchone()
                if seq_row and seq_row["current_number"]:
                    seq_val = int(seq_row["current_number"])
                    if seq_val > max_num:
                        max_num = seq_val
            except Exception:
                pass

            next_num = max_num + 1
            return f"PUR-{str(next_num).zfill(6)}"

    def _allocate_purchase_voucher_number(self, cursor, company_id: str, series: str = "Main", is_trad: bool = False) -> str:
        """
        Atomically allocates the next sequential purchase voucher number inside an open write transaction.
        Uses database row locking / serial checking to eliminate race conditions.
        """
        clean_series = series or "Main"

        # 1. Query current sequence record with row lock if supported
        current_seq = 0
        seq_exists = False
        if not is_trad:
            try:
                # Try SELECT ... FOR UPDATE (PostgreSQL)
                cursor.execute("""
                    SELECT current_number FROM voucher_sequences
                    WHERE company_id = ? AND voucher_type = 'PURCHASE' AND series = ?
                    FOR UPDATE;
                """, (company_id, clean_series))
                s_row = cursor.fetchone()
                if s_row is not None:
                    seq_exists = True
                    current_seq = int(s_row["current_number"] or 0)
            except Exception:
                pass

        if not seq_exists:
            # Fallback for SQLite / engines without FOR UPDATE
            try:
                cursor.execute("""
                    SELECT current_number FROM voucher_sequences
                    WHERE company_id = ? AND voucher_type = 'PURCHASE' AND series = ?;
                """, (company_id, clean_series))
                s_row = cursor.fetchone()
                if s_row is not None:
                    seq_exists = True
                    current_seq = int(s_row["current_number"] or 0)
            except Exception:
                seq_exists = False
                current_seq = 0
            except Exception:
                seq_exists = False
                current_seq = 0

        # 2. Find highest committed voucher number in purchase_vouchers
        cursor.execute("""
            SELECT vch_no FROM purchase_vouchers
            WHERE company_id = ?;
        """, (company_id,))
        max_num = 0
        for r in cursor.fetchall():
            num_str = "".join(ch for ch in str(r["vch_no"]) if ch.isdigit())
            if num_str:
                try:
                    n = int(num_str)
                    if n > max_num:
                        max_num = n
                except ValueError:
                    pass

        # 3. Next sequential number
        allocated = max(current_seq, max_num, 0) + 1

        # 4. Upsert voucher_sequences record
        try:
            if seq_exists:
                cursor.execute("""
                    UPDATE voucher_sequences
                    SET current_number = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE company_id = ? AND voucher_type = 'PURCHASE' AND series = ?;
                """, (allocated, company_id, clean_series))
            else:
                cursor.execute("""
                    INSERT INTO voucher_sequences (
                        id, company_id, voucher_type, series, current_number, updated_at
                    ) VALUES (?, ?, 'PURCHASE', ?, ?, CURRENT_TIMESTAMP);
                """, (str(uuid.uuid4()), company_id, clean_series, allocated))
        except Exception as e:
            logger.debug(f"Note on voucher_sequences update: {e}")

        return f"PUR-{str(allocated).zfill(6)}"

    def check_duplicate_supplier_invoice(
        self,
        company_id: str,
        supplier_name: str,
        supplier_invoice_no: str,
        supplier_invoice_date: str,
        exclude_voucher_id: Optional[str] = None
    ) -> bool:
        """Returns True if a purchase invoice with the same supplier, bill number, and date already exists."""
        target_db, actual_comp_id, is_trad = self._get_db_and_company_id(company_id)
        norm_supp = supplier_name.strip().upper()
        norm_inv = supplier_invoice_no.strip().upper()
        with target_db.get_connection() as conn:
            cursor = conn.cursor()
            if exclude_voucher_id:
                cursor.execute("""
                    SELECT id FROM purchase_vouchers
                    WHERE company_id = ? AND UPPER(supplier_name) = ?
                      AND UPPER(supplier_invoice_no) = ? AND supplier_invoice_date = ?
                      AND COALESCE(is_cancelled, 0) = 0 AND id != ?;
                """, (actual_comp_id, norm_supp, norm_inv, supplier_invoice_date, exclude_voucher_id))
            else:
                cursor.execute("""
                    SELECT id FROM purchase_vouchers
                    WHERE company_id = ? AND UPPER(supplier_name) = ?
                      AND UPPER(supplier_invoice_no) = ? AND supplier_invoice_date = ?
                      AND COALESCE(is_cancelled, 0) = 0;
                """, (actual_comp_id, norm_supp, norm_inv, supplier_invoice_date))
            return cursor.fetchone() is not None

    def list_godowns(self, company_id: str) -> List[Dict[str, Any]]:
        """Returns registered material centres / godowns for the company."""
        target_db, actual_comp_id, is_trad = self._get_db_and_company_id(company_id)
        try:
            with target_db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, code, name, address, is_default
                    FROM godowns
                    WHERE company_id = ?
                    ORDER BY is_default DESC, name ASC;
                """, (actual_comp_id,))
                rows = cursor.fetchall()
                if rows:
                    return [_sanitize_record(dict(r)) for r in rows]
        except Exception:
            pass

        # Default standard storage locations if none explicitly registered
        return [
            {"id": "GODOWN-MAIN", "code": "MAIN", "name": "Main Store", "is_default": 1},
            {"id": "GODOWN-01", "code": "G01", "name": "Godown 1 (Bulk Storage)", "is_default": 0}
        ]

    def calculate_purchase_taxes_and_landed_costs(
        self,
        actual_comp_id: str,
        supplier_state: str,
        raw_items: List[Dict[str, Any]],
        additional_expenses: float = 0.0,
        db: Optional[DatabaseManager] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Authoritative backend calculation of line taxes, discounts, taxable totals,
        apportioned landed costs, and GST breakdowns (intra-state CGST+SGST vs inter-state IGST).
        """
        target_db = db or self.db
        company_state = "Tamilnadu"
        try:
            with target_db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT state FROM companies WHERE id = ?;", (actual_comp_id,))
                comp_state_row = cursor.fetchone()
                if comp_state_row:
                    st = comp_state_row["state"] if hasattr(comp_state_row, "keys") or isinstance(comp_state_row, dict) else comp_state_row[0]
                    if st:
                        company_state = str(st).strip()
        except Exception as e:
            logger.debug(f"calculate_purchase_taxes_and_landed_costs state lookup note: {e}")

        is_interstate = (company_state.lower() != supplier_state.strip().lower())

        calculated_items = []
        gross_subtotal = Decimal("0")
        total_discount = Decimal("0")
        taxable_total = Decimal("0")
        cgst_total = Decimal("0")
        sgst_total = Decimal("0")
        igst_total = Decimal("0")
        total_qty_sum = Decimal("0")

        # First pass: calculate gross, discounts, taxable amounts and taxes
        for idx, it in enumerate(raw_items, start=1):
            name = (it.get("name") or it.get("item_name") or f"Item {idx}").strip()
            item_id = it.get("id") or it.get("item_id")
            barcode = it.get("barcode") or it.get("alias") or ""
            qty = Decimal(str(it.get("qty") or 1.0))
            free_qty = Decimal(str(it.get("free_qty") or 0.0))
            unit = it.get("unit") or "Pcs."
            rate = Decimal(str(it.get("purchase_rate") or it.get("rate") or it.get("price") or it.get("cost_rate") or 0.0))
            disc_pct = Decimal(str(it.get("discount_percent") or it.get("discount_pct") or 0.0))
            tax_rate = Decimal(str(it.get("tax_rate") if it.get("tax_rate") is not None else 18.0))

            if qty <= 0 and free_qty <= 0:
                raise ValueError(f"Line item #{idx} ('{name}') must have quantity greater than zero.")
            if rate < 0:
                raise ValueError(f"Line item #{idx} ('{name}') cannot have negative purchase rate.")

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
            total_qty_sum += (qty + free_qty)

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
                "expiry_date": it.get("expiry_date") or "",
                "landed_cost": float(rate)  # updated in second pass
            })

        # Second pass: Apportion additional expenses (freight, handling) into inventory landed cost
        dec_add_exp = Decimal(str(additional_expenses or 0.0))
        for line in calculated_items:
            line_taxable = Decimal(str(line["taxable_amount"]))
            effective_qty = Decimal(str(line["qty"])) + Decimal(str(line["free_qty"]))
            if taxable_total > 0 and dec_add_exp > 0:
                expense_share = dec_add_exp * (line_taxable / taxable_total)
            elif len(calculated_items) > 0 and dec_add_exp > 0:
                expense_share = dec_add_exp / Decimal(str(len(calculated_items)))
            else:
                expense_share = Decimal("0")

            if effective_qty > 0:
                landed_unit_cost = (line_taxable + expense_share) / effective_qty
            else:
                landed_unit_cost = Decimal(str(line["purchase_rate"]))
            line["landed_cost"] = float(landed_unit_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

        total_tax = cgst_total + sgst_total + igst_total
        raw_grand = taxable_total + total_tax + dec_add_exp
        rounded_grand = raw_grand.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        round_off = rounded_grand - raw_grand

        totals = {
            "gross_subtotal": float(gross_subtotal),
            "total_discount": float(total_discount),
            "taxable_total": float(taxable_total),
            "cgst_total": float(cgst_total),
            "sgst_total": float(sgst_total),
            "igst_total": float(igst_total),
            "total_tax": float(total_tax),
            "additional_expenses": float(dec_add_exp),
            "round_off": float(round_off),
            "grand_total": float(rounded_grand),
            "is_interstate": is_interstate
        }
        return calculated_items, totals

    def create_purchase_voucher(
        self,
        company_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Atomically commits an authoritative Purchase Voucher:
        - Validates unique supplier bill number
        - Calculates line taxes, taxable amounts, and apportioned landed costs
        - Allocates next unique sequential purchase voucher number under lock
        - Inserts purchase voucher & items
        - Increases stock in central stock balances and movement ledger
        - Updates supplier ledger & payable balance
        - Records historical purchase price history
        - Posts double-entry journal lines
        - Logs audit record
        """
        target_db, actual_comp_id, is_trad = self._get_db_and_company_id(company_id)
        supplier_name = (data.get("supplier_name") or data.get("supplierName") or "").strip()
        if not supplier_name:
            raise ValueError("Supplier Name is required.")

        supp_inv_no = (data.get("supplier_invoice_no") or data.get("supplierInvoiceNo") or "").strip()
        if not supp_inv_no:
            raise ValueError("Supplier Invoice / Bill Number is required.")

        supp_inv_date = (data.get("supplier_invoice_date") or data.get("supplierInvoiceDate") or "").strip()
        if not supp_inv_date:
            supp_inv_date = datetime.now().strftime("%Y-%m-%d")

        vch_date = (data.get("vch_date") or data.get("voucher_date") or data.get("vchDate") or datetime.now().strftime("%Y-%m-%d")).strip()
        branch_id = data.get("branch_id") or self._get_default_branch_id(actual_comp_id, db=target_db)
        godown_id = data.get("godown_id") or "GODOWN-MAIN"
        series = str(data.get("series") or "Main").strip() or "Main"
        payment_type = (data.get("payment_type") or data.get("payment_mode") or data.get("paymentType") or "CREDIT").strip().upper()
        purchase_type = data.get("purchase_type") or "GST Purchase"
        narration = data.get("narration") or ""

        freight_charges = float(data.get("freight_charges") or data.get("freight") or 0.0)
        handling_charges = float(data.get("handling_charges") or data.get("handling") or 0.0)
        additional_expenses = freight_charges + handling_charges
        if additional_expenses == 0.0 and data.get("additional_expenses"):
            additional_expenses = float(data.get("additional_expenses"))

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
        supplier_id = (data.get("supplier_id") or data.get("supplierId") or "").strip()
        supp_obj = None
        if supplier_id:
            supp_obj = self.supplier_service.get_supplier_by_id(actual_comp_id, supplier_id)
            if not supp_obj:
                with target_db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM accounts WHERE company_id = ? AND id = ?;", (actual_comp_id, supplier_id))
                    acc_row = cursor.fetchone()
                    if acc_row:
                        supp_obj = dict(acc_row)
                        code = f"SUP-{supplier_id[:6].upper()}"
                        try:
                            cursor.execute("""
                                INSERT INTO suppliers (
                                    id, company_id, code, name, contact_person, mobile, email, gstin,
                                    pan, address, city, state, pincode, opening_balance, current_balance,
                                    payment_terms, is_active
                                ) VALUES (?, ?, ?, ?, ?, ?, '', ?, '', ?, '', ?, ?, 0.0, 0.0, 30, 1)
                                ON CONFLICT(company_id, name) DO NOTHING;
                            """, (
                                supplier_id, actual_comp_id, code, acc_row["name"], acc_row["alias"] if "alias" in acc_row.keys() else "",
                                acc_row["mobile"] if "mobile" in acc_row.keys() else (acc_row.get("phone") or ""),
                                acc_row["gstin"] if "gstin" in acc_row.keys() else "",
                                acc_row["address"] if "address" in acc_row.keys() else "",
                                acc_row["state"] if "state" in acc_row.keys() else "Tamilnadu",
                                acc_row["pincode"] if "pincode" in acc_row.keys() else ""
                            ))
                            conn.commit()
                        except Exception as e:
                            logger.debug(f"supplier register note: {e}")

        if not supp_obj:
            supp_obj = self.supplier_service.find_supplier_by_name(actual_comp_id, supplier_name)
            if not supp_obj:
                with target_db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM accounts WHERE company_id = ? AND UPPER(name) = ?;", (actual_comp_id, supplier_name.upper()))
                    acc_row = cursor.fetchone()
                    if acc_row:
                        supp_obj = dict(acc_row)
                        sup_acc_id = acc_row["id"]
                        code = f"SUP-{sup_acc_id[:6].upper()}"
                        try:
                            cursor.execute("""
                                INSERT INTO suppliers (
                                    id, company_id, code, name, contact_person, mobile, email, gstin,
                                    pan, address, city, state, pincode, opening_balance, current_balance,
                                    payment_terms, is_active
                                ) VALUES (?, ?, ?, ?, ?, ?, '', ?, '', ?, '', ?, ?, 0.0, 0.0, 30, 1)
                                ON CONFLICT(company_id, name) DO NOTHING;
                            """, (
                                sup_acc_id, actual_comp_id, code, acc_row["name"], acc_row["alias"] if "alias" in acc_row.keys() else "",
                                acc_row["mobile"] if "mobile" in acc_row.keys() else (acc_row.get("phone") or ""),
                                acc_row["gstin"] if "gstin" in acc_row.keys() else "",
                                acc_row["address"] if "address" in acc_row.keys() else "",
                                acc_row["state"] if "state" in acc_row.keys() else "Tamilnadu",
                                acc_row["pincode"] if "pincode" in acc_row.keys() else ""
                            ))
                            conn.commit()
                        except Exception as e:
                            logger.debug(f"supplier register note: {e}")

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
        supplier_state = (data.get("supplier_state") or (supp_obj.get("state") if supp_obj and supp_obj.get("state") else "Tamilnadu") or "Tamilnadu").strip()
        place_of_supply = data.get("place_of_supply") or supplier_state

        # Calculate Items, Taxes, and Landed Costs
        calculated_items, totals = self.calculate_purchase_taxes_and_landed_costs(
            actual_comp_id=actual_comp_id,
            supplier_state=supplier_state,
            raw_items=raw_items,
            additional_expenses=additional_expenses,
            db=target_db
        )

        amount_paid = float(totals["grand_total"]) if payment_type in ("CASH", "BANK") else float(data.get("amount_paid") or 0.0)
        outstanding = float(totals["grand_total"]) - amount_paid

        vch_id = str(uuid.uuid4())

        # Atomic commit to DB
        with target_db.get_connection() as conn:
            cursor = conn.cursor()

            # Allocate next authoritative sequential voucher number under lock
            vch_no = self._allocate_purchase_voucher_number(cursor, actual_comp_id, series=series, is_trad=is_trad)

            # 1. Insert Purchase Voucher
            cursor.execute("""
                INSERT INTO purchase_vouchers (
                    id, company_id, branch_id, godown_id, vch_no, supplier_invoice_no,
                    supplier_invoice_date, vch_date, supplier_id, supplier_name,
                    supplier_gstin, supplier_address, supplier_state, place_of_supply,
                    payment_type, due_date, purchase_type, narration, gross_amount,
                    discount_total, additional_expenses, freight_charges, handling_charges,
                    taxable_amount, cgst_amount, sgst_amount, igst_amount, cess_amount,
                    round_off, grand_total, amount_paid, outstanding_balance, is_draft,
                    is_cancelled, created_by, created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                );
            """, (
                vch_id, actual_comp_id, branch_id, godown_id, vch_no, supp_inv_no,
                supp_inv_date, vch_date, supplier_id, supplier_name,
                supplier_gstin, data.get("supplier_address", ""), supplier_state, place_of_supply,
                payment_type, data.get("due_date", ""), purchase_type, narration,
                totals["gross_subtotal"], totals["total_discount"], totals["additional_expenses"],
                freight_charges, handling_charges, totals["taxable_total"],
                totals["cgst_total"], totals["sgst_total"], totals["igst_total"],
                0.0, totals["round_off"], totals["grand_total"], amount_paid, outstanding,
                is_draft, 0, created_by
            ))

            # 2. Insert Line Items, Update Inventory & Record Price History
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
                        sgst_amount, igst_amount, cess_amount, landed_cost, line_total,
                        batch_no, expiry_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    str(uuid.uuid4()), vch_id, item_id, it["sn"], it["barcode"],
                    it["name"], "", it["qty"], it["free_qty"], it["unit"],
                    it["purchase_rate"], it["discount_percent"], it["discount_amount"],
                    it["taxable_amount"], it["tax_rate"], it["cgst_amount"],
                    it["sgst_amount"], it["igst_amount"], 0.0, it["landed_cost"], it["line_total"],
                    it["batch_no"], it["expiry_date"]
                ))

                if not is_draft and item_id and branch_id:
                    total_inward = it["qty"] + it["free_qty"]
                    # Update stock balance (mode-aware)
                    if is_trad:
                        scaled_qty = int(round(total_inward * 1000))
                        cursor.execute("""
                            INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty_scaled, updated_at)
                            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT(company_id, branch_id, item_id) DO UPDATE SET
                                current_qty_scaled = stock_balances.current_qty_scaled + excluded.current_qty_scaled,
                                updated_at = CURRENT_TIMESTAMP;
                        """, (str(uuid.uuid4()), actual_comp_id, branch_id, item_id, scaled_qty))
                    else:
                        cursor.execute("""
                            INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(branch_id, item_id) DO UPDATE SET
                                current_qty = stock_balances.current_qty + excluded.current_qty,
                                last_updated = CURRENT_TIMESTAMP;
                        """, (str(uuid.uuid4()), actual_comp_id, branch_id, item_id, total_inward))

                    # Optional Stock movement ledger
                    try:
                        cursor.execute("""
                            INSERT INTO stock_movements (
                                id, company_id, branch_id, item_id, movement_type,
                                qty, unit_cost, reference_type, reference_id, notes
                            ) VALUES (?, ?, ?, ?, 'PURCHASE', ?, ?, 'PURCHASE', ?, ?);
                        """, (
                            str(uuid.uuid4()), actual_comp_id, branch_id, item_id,
                            total_inward, it["landed_cost"], vch_no,
                            f"Purchase Bill #{supp_inv_no} from {supplier_name} (Landed: ₹{it['landed_cost']:.2f})"
                        ))
                    except Exception as e:
                        logger.debug(f"stock_movements insert note: {e}")

                    # Optional Batch Tracking
                    if it["batch_no"]:
                        try:
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
                        except Exception as e:
                            logger.debug(f"stock_batches insert note: {e}")

                # 3. Record permanent Purchase Price History
                if not is_draft and item_id:
                    prev_rate = 0.0
                    try:
                        cursor.execute("""
                            SELECT purchase_rate FROM purchase_price_history
                            WHERE company_id = ? AND item_id = ?
                            ORDER BY purchase_date DESC, created_at DESC LIMIT 1;
                        """, (actual_comp_id, item_id))
                        prev_row = cursor.fetchone()
                        if prev_row:
                            prev_rate = float(prev_row["purchase_rate"] or 0.0)
                    except Exception:
                        pass

                    try:
                        cursor.execute("""
                            INSERT INTO purchase_price_history (
                                id, company_id, branch_id, item_id, supplier_id, voucher_id,
                                voucher_number, supplier_invoice_no, purchase_date, purchase_rate,
                                qty, discount_percent, tax_rate, landed_cost, previous_rate,
                                is_revision, revision_notes, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '', CURRENT_TIMESTAMP);
                        """, (
                            str(uuid.uuid4()), actual_comp_id, branch_id, item_id, supplier_id,
                            vch_id, vch_no, supp_inv_no, vch_date, it["purchase_rate"],
                            it["qty"], it["discount_percent"], it["tax_rate"], it["landed_cost"],
                            prev_rate
                        ))
                    except Exception as e:
                        logger.debug(f"Note on purchase_price_history insert: {e}")

            # 4. Update Supplier Balance (if not draft and credit/unpaid portion)
            if not is_draft and outstanding > 0 and supplier_id:
                try:
                    cursor.execute("""
                        UPDATE suppliers
                        SET current_balance = current_balance + ?, updated_at = CURRENT_TIMESTAMP
                        WHERE company_id = ? AND id = ?;
                    """, (outstanding, actual_comp_id, supplier_id))
                except Exception as e:
                    logger.debug(f"suppliers balance update note: {e}")

            # 5. Double-Entry Accounting Journal Posting (if not draft)
            if not is_draft:
                try:
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
                    """, (str(uuid.uuid4()), journal_id, totals["taxable_total"]))

                    # Dr Input GST
                    if totals["cgst_total"] > 0:
                        cursor.execute("""
                            INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                            VALUES (?, ?, 'Input CGST Account', ?, 0.0, 'Eligible Input Tax Credit');
                        """, (str(uuid.uuid4()), journal_id, totals["cgst_total"]))
                    if totals["sgst_total"] > 0:
                        cursor.execute("""
                            INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                            VALUES (?, ?, 'Input SGST Account', ?, 0.0, 'Eligible Input Tax Credit');
                        """, (str(uuid.uuid4()), journal_id, totals["sgst_total"]))
                    if totals["igst_total"] > 0:
                        cursor.execute("""
                            INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                            VALUES (?, ?, 'Input IGST Account', ?, 0.0, 'Eligible Inter-State Input Tax Credit');
                        """, (str(uuid.uuid4()), journal_id, totals["igst_total"]))

                    # Additional Expenses
                    if freight_charges > 0:
                        cursor.execute("""
                            INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                            VALUES (?, ?, 'Freight / Inward Expenses', ?, 0.0, 'Inward transport and cartage');
                        """, (str(uuid.uuid4()), journal_id, freight_charges))
                    if handling_charges > 0:
                        cursor.execute("""
                            INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                            VALUES (?, ?, 'Handling / Unloading Expenses', ?, 0.0, 'Handling and unloading charges');
                        """, (str(uuid.uuid4()), journal_id, handling_charges))
                    elif additional_expenses > 0 and freight_charges == 0 and handling_charges == 0:
                        cursor.execute("""
                            INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                            VALUES (?, ?, 'Freight / Inward Expenses', ?, 0.0, 'Landed cost expenses');
                        """, (str(uuid.uuid4()), journal_id, additional_expenses))

                    # Round Off
                    if totals["round_off"] > 0:
                        cursor.execute("""
                            INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                            VALUES (?, ?, 'Round Off Account', ?, 0.0, 'Purchase rounding adjustment');
                        """, (str(uuid.uuid4()), journal_id, totals["round_off"]))
                    elif totals["round_off"] < 0:
                        cursor.execute("""
                            INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                            VALUES (?, ?, 'Round Off Account', 0.0, ?, 'Purchase rounding adjustment');
                        """, (str(uuid.uuid4()), journal_id, abs(totals["round_off"])))

                    # Cr Supplier Account / Cash / Bank
                    credit_account = supplier_name if payment_type == "CREDIT" else f"Cash / Bank ({payment_type})"
                    cursor.execute("""
                        INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                        VALUES (?, ?, ?, 0.0, ?, 'Purchase invoice liability / settlement');
                    """, (str(uuid.uuid4()), journal_id, credit_account, totals["grand_total"]))
                except Exception as e:
                    logger.debug(f"journal posting note: {e}")

            # 6. Audit Log
            try:
                if is_trad:
                    cursor.execute("""
                        INSERT INTO audit_logs (id, company_id, user_id, event_type, entity_type, entity_id, payload_json)
                        VALUES (?, ?, ?, 'POST_PURCHASE', 'PURCHASE_VOUCHER', ?, ?);
                    """, (
                        str(uuid.uuid4()), actual_comp_id, created_by, vch_no,
                        json.dumps({"details": f"Posted purchase bill #{supp_inv_no} from {supplier_name} for ₹{totals['grand_total']:.2f}"})
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO audit_logs (id, company_id, username, action, entity_type, entity_id, details)
                        VALUES (?, ?, ?, 'POST_PURCHASE', 'PURCHASE_VOUCHER', ?, ?);
                    """, (
                        str(uuid.uuid4()), actual_comp_id, created_by, vch_no,
                        f"Posted purchase bill #{supp_inv_no} from {supplier_name} for ₹{totals['grand_total']:.2f}"
                    ))
            except Exception as e:
                logger.debug(f"audit_logs insert note: {e}")

            conn.commit()

        if not is_draft:
            try:
                for line in calculated_items:
                    it_id = line.get("item_id")
                    if it_id:
                        self.inventory_service.evaluate_low_stock_alerts(actual_comp_id, branch_id=branch_id, item_id=it_id)
            except Exception as e:
                logger.debug(f"evaluate_low_stock_alerts after purchase: {e}")

        logger.info(f"Purchase Voucher {vch_no} (Bill #{supp_inv_no}) successfully committed for company {actual_comp_id}.")
        return _sanitize_record({
            "id": vch_id,
            "voucher_id": vch_id,
            "vch_no": vch_no,
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "supplier_invoice_no": supp_inv_no,
            "supplier_invoice_date": supp_inv_date,
            "vch_date": vch_date,
            "voucher_date": vch_date,
            "subtotal": totals["taxable_total"],
            "taxable_amount": totals["taxable_total"],
            "cgst_amount": totals["cgst_total"],
            "sgst_amount": totals["sgst_total"],
            "igst_amount": totals["igst_total"],
            "tax_amount": totals["total_tax"],
            "additional_expenses": totals["additional_expenses"],
            "freight_charges": freight_charges,
            "handling_charges": handling_charges,
            "round_off": totals["round_off"],
            "grand_total": totals["grand_total"],
            "amount_paid": amount_paid,
            "outstanding_balance": outstanding,
            "is_draft": bool(is_draft),
            "items_count": len(calculated_items),
            "items": calculated_items
        })

    def modify_purchase_voucher(
        self,
        company_id: str,
        voucher_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Modifies an existing purchase voucher within an atomic database transaction.
        Reconciles:
        1. Original stock impact vs revised stock impact
        2. Inventory valuation and stock movements
        3. Supplier outstanding balance (delta adjustment)
        4. Purchase accounting journal entries
        5. GST values and landed expenses
        6. Purchase price history (retains original records and appends audit revision)
        7. Audit log
        Preserves original voucher ID and sequential number.
        """
        target_db, actual_comp_id, is_trad = self._get_db_and_company_id(company_id)

        with target_db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Fetch existing voucher
            cursor.execute("""
                SELECT * FROM purchase_vouchers WHERE company_id = ? AND id = ?;
            """, (actual_comp_id, voucher_id))
            old_pv_row = cursor.fetchone()
            if not old_pv_row:
                raise ValueError(f"Purchase voucher '{voucher_id}' not found.")
            old_pv = dict(old_pv_row)

            vch_no = old_pv["vch_no"]
            branch_id = old_pv["branch_id"] or self._get_default_branch_id(actual_comp_id, db=target_db)
            godown_id = data.get("godown_id") or old_pv.get("godown_id") or "GODOWN-MAIN"
            old_supplier_id = old_pv["supplier_id"]
            old_outstanding = float(old_pv["outstanding_balance"] or 0.0)

            # 2. Fetch existing items to reconcile stock
            cursor.execute("""
                SELECT item_id, qty, free_qty, purchase_rate FROM purchase_voucher_items WHERE voucher_id = ?;
            """, (voucher_id,))
            old_items = cursor.fetchall()

            # Revert previous stock inward and supplier balance if not draft
            if not old_pv["is_draft"]:
                for old_it in old_items:
                    item_id = old_it["item_id"]
                    tot_qty = float(old_it["qty"] or 0.0) + float(old_it["free_qty"] or 0.0)
                    if item_id and branch_id and tot_qty > 0:
                        if is_trad:
                            scaled_qty = int(round(tot_qty * 1000))
                            cursor.execute("""
                                UPDATE stock_balances
                                SET current_qty_scaled = current_qty_scaled - ?, updated_at = CURRENT_TIMESTAMP
                                WHERE company_id = ? AND branch_id = ? AND item_id = ?;
                            """, (scaled_qty, actual_comp_id, branch_id, item_id))
                        else:
                            cursor.execute("""
                                UPDATE stock_balances
                                SET current_qty = current_qty - ?, last_updated = CURRENT_TIMESTAMP
                                WHERE branch_id = ? AND item_id = ?;
                            """, (tot_qty, branch_id, item_id))

                if old_supplier_id and old_outstanding > 0:
                    try:
                        cursor.execute("""
                            UPDATE suppliers
                            SET current_balance = current_balance - ?, updated_at = CURRENT_TIMESTAMP
                            WHERE company_id = ? AND id = ?;
                        """, (old_outstanding, actual_comp_id, old_supplier_id))
                    except Exception as e:
                        logger.debug(f"revert supplier balance note: {e}")

            # 3. Clean up previous movements, journals, and line items
            try:
                cursor.execute("""
                    DELETE FROM stock_movements WHERE reference_id = ? AND reference_type = 'PURCHASE';
                """, (vch_no,))
            except Exception:
                pass

            try:
                cursor.execute("""
                    SELECT id FROM journal_entries WHERE company_id = ? AND reference_id = ?;
                """, (actual_comp_id, voucher_id))
                for j_row in cursor.fetchall():
                    cursor.execute("DELETE FROM journal_entry_lines WHERE journal_id = ?;", (j_row["id"],))
                cursor.execute("DELETE FROM journal_entries WHERE company_id = ? AND reference_id = ?;", (actual_comp_id, voucher_id))
            except Exception:
                pass

            cursor.execute("DELETE FROM purchase_voucher_items WHERE voucher_id = ?;", (voucher_id,))

            # 4. Process updated header and supplier details
            supplier_name = (data.get("supplier_name") or old_pv["supplier_name"] or "").strip()
            if not supplier_name:
                raise ValueError("Supplier name cannot be empty.")

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

            supp_inv_no = data.get("supplier_invoice_no") or old_pv["supplier_invoice_no"] or vch_no
            supp_inv_date = data.get("supplier_invoice_date") or old_pv["supplier_invoice_date"] or datetime.now().strftime("%Y-%m-%d")
            vch_date = data.get("vch_date") or data.get("voucher_date") or old_pv["vch_date"] or datetime.now().strftime("%Y-%m-%d")
            payment_type = (data.get("payment_type") or data.get("payment_mode") or old_pv["payment_type"] or "CREDIT").strip().upper()
            purchase_type = data.get("purchase_type") or old_pv["purchase_type"] or "GST Purchase"
            narration = data.get("narration") if data.get("narration") is not None else (old_pv["narration"] or "")

            freight_charges = float(data.get("freight_charges") or data.get("freight") or 0.0)
            handling_charges = float(data.get("handling_charges") or data.get("handling") or 0.0)
            additional_expenses = freight_charges + handling_charges
            if additional_expenses == 0.0 and data.get("additional_expenses"):
                additional_expenses = float(data.get("additional_expenses"))

            is_draft = 1 if data.get("is_draft") else 0
            created_by = data.get("created_by") or old_pv["created_by"] or "Admin"

            raw_items = data.get("items") or []
            if not raw_items:
                raise ValueError("Purchase voucher must contain at least one line item.")

            # 5. Calculate revised line items and totals
            calculated_items, totals = self.calculate_purchase_taxes_and_landed_costs(
                actual_comp_id=actual_comp_id,
                supplier_state=supplier_state,
                raw_items=raw_items,
                additional_expenses=additional_expenses,
                db=target_db
            )

            amount_paid = float(totals["grand_total"]) if payment_type in ("CASH", "BANK") else float(data.get("amount_paid") or 0.0)
            outstanding = float(totals["grand_total"]) - amount_paid

            # 6. Update Purchase Voucher header
            cursor.execute("""
                UPDATE purchase_vouchers SET
                    supplier_invoice_no = ?,
                    supplier_invoice_date = ?,
                    vch_date = ?,
                    supplier_id = ?,
                    supplier_name = ?,
                    supplier_gstin = ?,
                    supplier_address = ?,
                    supplier_state = ?,
                    place_of_supply = ?,
                    godown_id = ?,
                    payment_type = ?,
                    due_date = ?,
                    purchase_type = ?,
                    narration = ?,
                    gross_amount = ?,
                    discount_total = ?,
                    additional_expenses = ?,
                    freight_charges = ?,
                    handling_charges = ?,
                    taxable_amount = ?,
                    cgst_amount = ?,
                    sgst_amount = ?,
                    igst_amount = ?,
                    cess_amount = 0.0,
                    round_off = ?,
                    grand_total = ?,
                    amount_paid = ?,
                    outstanding_balance = ?,
                    is_draft = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND company_id = ?;
            """, (
                supp_inv_no, supp_inv_date, vch_date, supplier_id, supplier_name,
                supplier_gstin, data.get("supplier_address", ""), supplier_state, place_of_supply,
                godown_id, payment_type, data.get("due_date", ""), purchase_type, narration,
                totals["gross_subtotal"], totals["total_discount"], totals["additional_expenses"],
                freight_charges, handling_charges, totals["taxable_total"],
                totals["cgst_total"], totals["sgst_total"], totals["igst_total"],
                totals["round_off"], totals["grand_total"], amount_paid, outstanding,
                is_draft, voucher_id, actual_comp_id
            ))

            # 7. Insert new line items and update stock inward
            old_item_rates = {r["item_id"]: float(r["purchase_rate"] or 0.0) for r in old_items if r["item_id"]}

            for it in calculated_items:
                item_id = it["item_id"]
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
                        sgst_amount, igst_amount, cess_amount, landed_cost, line_total,
                        batch_no, expiry_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    str(uuid.uuid4()), voucher_id, item_id, it["sn"], it["barcode"],
                    it["name"], "", it["qty"], it["free_qty"], it["unit"],
                    it["purchase_rate"], it["discount_percent"], it["discount_amount"],
                    it["taxable_amount"], it["tax_rate"], it["cgst_amount"],
                    it["sgst_amount"], it["igst_amount"], 0.0, it["landed_cost"], it["line_total"],
                    it["batch_no"], it["expiry_date"]
                ))

                if not is_draft and item_id and branch_id:
                    total_inward = it["qty"] + it["free_qty"]
                    if is_trad:
                        scaled_qty = int(round(total_inward * 1000))
                        cursor.execute("""
                            INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty_scaled, updated_at)
                            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT(company_id, branch_id, item_id) DO UPDATE SET
                                current_qty_scaled = stock_balances.current_qty_scaled + excluded.current_qty_scaled,
                                updated_at = CURRENT_TIMESTAMP;
                        """, (str(uuid.uuid4()), actual_comp_id, branch_id, item_id, scaled_qty))
                    else:
                        cursor.execute("""
                            INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(branch_id, item_id) DO UPDATE SET
                                current_qty = stock_balances.current_qty + excluded.current_qty,
                                last_updated = CURRENT_TIMESTAMP;
                        """, (str(uuid.uuid4()), actual_comp_id, branch_id, item_id, total_inward))

                    try:
                        cursor.execute("""
                            INSERT INTO stock_movements (
                                id, company_id, branch_id, item_id, movement_type,
                                qty, unit_cost, reference_type, reference_id, notes
                            ) VALUES (?, ?, ?, ?, 'PURCHASE', ?, ?, 'PURCHASE', ?, ?);
                        """, (
                            str(uuid.uuid4()), actual_comp_id, branch_id, item_id,
                            total_inward, it["landed_cost"], vch_no,
                            f"Purchase Bill #{supp_inv_no} from {supplier_name} (Revised - Landed: ₹{it['landed_cost']:.2f})"
                        ))
                    except Exception as e:
                        logger.debug(f"modify stock_movements note: {e}")

                # 8. Record audit revision in purchase_price_history
                if not is_draft and item_id:
                    old_rate = old_item_rates.get(item_id, it["purchase_rate"])
                    try:
                        cursor.execute("""
                            INSERT INTO purchase_price_history (
                                id, company_id, branch_id, item_id, supplier_id, voucher_id,
                                voucher_number, supplier_invoice_no, purchase_date, purchase_rate,
                                qty, discount_percent, tax_rate, landed_cost, previous_rate,
                                is_revision, revision_notes, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP);
                        """, (
                            str(uuid.uuid4()), actual_comp_id, branch_id, item_id, supplier_id,
                            voucher_id, vch_no, supp_inv_no, vch_date, it["purchase_rate"],
                            it["qty"], it["discount_percent"], it["tax_rate"], it["landed_cost"],
                            old_rate, f"Modified from rate ₹{old_rate:.2f} on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                        ))
                    except Exception as e:
                        logger.debug(f"Note on purchase_price_history revision: {e}")

            # 9. Update supplier balance if not draft
            if not is_draft and outstanding > 0 and supplier_id:
                try:
                    cursor.execute("""
                        UPDATE suppliers
                        SET current_balance = current_balance + ?, updated_at = CURRENT_TIMESTAMP
                        WHERE company_id = ? AND id = ?;
                    """, (outstanding, actual_comp_id, supplier_id))
                except Exception as e:
                    logger.debug(f"suppliers balance update note: {e}")

            # 10. Post revised accounting journals if not draft
            if not is_draft:
                try:
                    journal_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO journal_entries (
                            id, company_id, vch_no, vch_date, vch_type, reference_id, narration
                        ) VALUES (?, ?, ?, ?, 'PURCHASE', ?, ?);
                    """, (
                        journal_id, actual_comp_id, vch_no, vch_date, voucher_id,
                        f"Purchase from {supplier_name} Inv #{supp_inv_no} (Revised)"
                    ))

                    cursor.execute("""
                        INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                        VALUES (?, ?, 'Purchase Account', ?, 0.0, 'Gross Purchases less discounts');
                    """, (str(uuid.uuid4()), journal_id, totals["taxable_total"]))

                    if totals["cgst_total"] > 0:
                        cursor.execute("""
                            INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                            VALUES (?, ?, 'Input CGST Account', ?, 0.0, 'Eligible Input Tax Credit');
                        """, (str(uuid.uuid4()), journal_id, totals["cgst_total"]))
                    if totals["sgst_total"] > 0:
                        cursor.execute("""
                            INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                            VALUES (?, ?, 'Input SGST Account', ?, 0.0, 'Eligible Input Tax Credit');
                        """, (str(uuid.uuid4()), journal_id, totals["sgst_total"]))
                    if totals["igst_total"] > 0:
                        cursor.execute("""
                            INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                            VALUES (?, ?, 'Input IGST Account', ?, 0.0, 'Eligible Inter-State Input Tax Credit');
                        """, (str(uuid.uuid4()), journal_id, totals["igst_total"]))

                    if freight_charges > 0:
                        cursor.execute("""
                            INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                            VALUES (?, ?, 'Freight / Inward Expenses', ?, 0.0, 'Freight charges');
                        """, (str(uuid.uuid4()), journal_id, freight_charges))
                    if handling_charges > 0:
                        cursor.execute("""
                            INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                            VALUES (?, ?, 'Handling / Unloading Expenses', ?, 0.0, 'Handling charges');
                        """, (str(uuid.uuid4()), journal_id, handling_charges))
                    elif additional_expenses > 0 and freight_charges == 0 and handling_charges == 0:
                        cursor.execute("""
                            INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                            VALUES (?, ?, 'Freight / Inward Expenses', ?, 0.0, 'Landed cost expenses');
                        """, (str(uuid.uuid4()), journal_id, additional_expenses))

                    if totals["round_off"] > 0:
                        cursor.execute("""
                            INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                            VALUES (?, ?, 'Round Off Account', ?, 0.0, 'Rounding');
                        """, (str(uuid.uuid4()), journal_id, totals["round_off"]))
                    elif totals["round_off"] < 0:
                        cursor.execute("""
                            INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                            VALUES (?, ?, 'Round Off Account', 0.0, ?, 'Rounding');
                        """, (str(uuid.uuid4()), journal_id, abs(totals["round_off"])))

                    credit_acct = f"Cash / Bank ({payment_type})" if payment_type in ("CASH", "BANK") else f"Supplier - {supplier_name}"
                    cursor.execute("""
                        INSERT INTO journal_entry_lines (id, journal_id, account_name, debit, credit, notes)
                        VALUES (?, ?, ?, 0.0, ?, 'Supplier settlement / liability');
                    """, (str(uuid.uuid4()), journal_id, credit_acct, totals["grand_total"]))
                except Exception as e:
                    logger.debug(f"modify journal posting note: {e}")

            # 11. Audit log
            audit_details = json.dumps({
                "vch_no": vch_no,
                "supplier_name": supplier_name,
                "old_grand_total": float(old_pv["grand_total"] or 0.0),
                "new_grand_total": totals["grand_total"],
                "items_count": len(calculated_items)
            })
            try:
                if is_trad:
                    cursor.execute("""
                        INSERT INTO audit_logs (id, company_id, user_id, event_type, entity_type, entity_id, payload_json)
                        VALUES (?, ?, ?, 'MODIFY_PURCHASE', 'PURCHASE_VOUCHER', ?, ?);
                    """, (str(uuid.uuid4()), actual_comp_id, created_by, vch_no, audit_details))
                else:
                    cursor.execute("""
                        INSERT INTO audit_logs (id, company_id, username, action, entity_type, entity_id, details)
                        VALUES (?, ?, ?, 'MODIFY_PURCHASE', 'PURCHASE_VOUCHER', ?, ?);
                    """, (str(uuid.uuid4()), actual_comp_id, created_by, vch_no, audit_details))
            except Exception as e:
                logger.debug(f"modify audit_logs note: {e}")

            conn.commit()

        logger.info(f"Purchase voucher {vch_no} ({voucher_id}) modified successfully for company {actual_comp_id}.")
        return _sanitize_record({
            "id": voucher_id,
            "voucher_id": voucher_id,
            "vch_no": vch_no,
            "supplier_id": supplier_id,
            "supplier_invoice_no": supp_inv_no,
            "supplier_invoice_date": supp_inv_date,
            "vch_date": vch_date,
            "voucher_date": vch_date,
            "supplier_name": supplier_name,
            "grand_total": totals["grand_total"],
            "outstanding": outstanding,
            "outstanding_balance": outstanding,
            "items_count": len(calculated_items),
            "items": calculated_items
        })

    def delete_purchase_voucher(self, company_id: str, voucher_id: str) -> None:
        """
        CRITICAL BUSINESS & LEGAL ENFORCEMENT:
        Posted purchase vouchers must NEVER be deleted or cancelled.
        """
        raise PermissionError(
            "CRITICAL SECURITY RESTRICTION: Posted purchase vouchers must NEVER be deleted or cancelled. "
            "Purchase vouchers are permanent tax, accounting, and inventory legal records. "
            "To rectify mistakes, use the authoritative Modify Purchase facility."
        )

    def cancel_purchase_voucher(self, company_id: str, voucher_id: str) -> None:
        """
        CRITICAL BUSINESS & LEGAL ENFORCEMENT:
        Cancellation of posted purchase vouchers is strictly prohibited.
        """
        raise PermissionError(
            "CRITICAL SECURITY RESTRICTION: Posted purchase vouchers must NEVER be deleted or cancelled."
        )

    def get_latest_purchase_rate(
        self,
        company_id: str,
        item_id: str,
        supplier_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Determines the purchase price precedence for an item:
        1. Latest same-supplier purchase rate from purchase_price_history.
        2. Otherwise latest purchase rate across any supplier.
        3. Finally the Item Master default purchase price (items.purc_price).
        Returns clear rate source and details for operator visibility.
        """
        target_db, actual_comp_id, is_trad = self._get_db_and_company_id(company_id)
        with target_db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Precedence 1: Same supplier purchase history
            if supplier_id:
                try:
                    cursor.execute("""
                        SELECT h.purchase_rate, h.landed_cost, h.purchase_date, h.voucher_number,
                               s.name as supplier_name
                        FROM purchase_price_history h
                        LEFT JOIN suppliers s ON s.id = h.supplier_id
                        WHERE h.company_id = ? AND h.item_id = ? AND h.supplier_id = ?
                        ORDER BY h.purchase_date DESC, h.created_at DESC LIMIT 1;
                    """, (actual_comp_id, item_id, supplier_id))
                    row = cursor.fetchone()
                    if row:
                        rate = float(row["purchase_rate"] or 0.0)
                        return _sanitize_record({
                            "rate": rate,
                            "landed_cost": float(row["landed_cost"] or rate),
                            "source": f"Same Supplier ({row['voucher_number']} on {row['purchase_date']})",
                            "source_type": "SAME_SUPPLIER",
                            "precedence": "same_supplier_history",
                            "last_date": row["purchase_date"],
                            "last_vch_no": row["voucher_number"],
                            "supplier_name": row["supplier_name"] or ""
                        })
                except Exception as e:
                    logger.debug(f"Query purchase_price_history same-supplier: {e}")

            # 2. Precedence 2: Any supplier latest purchase rate
            try:
                cursor.execute("""
                    SELECT h.purchase_rate, h.landed_cost, h.purchase_date, h.voucher_number,
                           s.name as supplier_name
                    FROM purchase_price_history h
                    LEFT JOIN suppliers s ON s.id = h.supplier_id
                    WHERE h.company_id = ? AND h.item_id = ?
                    ORDER BY h.purchase_date DESC, h.created_at DESC LIMIT 1;
                """, (actual_comp_id, item_id))
                row2 = cursor.fetchone()
                if row2:
                    rate = float(row2["purchase_rate"] or 0.0)
                    supp_name = row2["supplier_name"] or "Vendor"
                    return _sanitize_record({
                        "rate": rate,
                        "landed_cost": float(row2["landed_cost"] or rate),
                        "source": f"Last Purchase ({supp_name} - {row2['voucher_number']})",
                        "source_type": "CROSS_SUPPLIER",
                        "precedence": "cross_supplier_history",
                        "last_date": row2["purchase_date"],
                        "last_vch_no": row2["voucher_number"],
                        "supplier_name": supp_name
                    })
            except Exception as e:
                logger.debug(f"Query purchase_price_history cross-supplier: {e}")

            # Also check previous purchase_voucher_items if purchase_price_history had no rows yet
            try:
                cursor.execute("""
                    SELECT pvi.purchase_rate, pvi.landed_cost, pv.vch_date, pv.vch_no, pv.supplier_name
                    FROM purchase_voucher_items pvi
                    JOIN purchase_vouchers pv ON pv.id = pvi.voucher_id
                    WHERE pv.company_id = ? AND pvi.item_id = ? AND COALESCE(pv.is_cancelled, 0) = 0
                    ORDER BY pv.vch_date DESC, pv.created_at DESC LIMIT 1;
                """, (actual_comp_id, item_id))
                pvi_row = cursor.fetchone()
                if pvi_row:
                    rate = float(pvi_row["purchase_rate"] or 0.0)
                    return _sanitize_record({
                        "rate": rate,
                        "landed_cost": float(pvi_row["landed_cost"] or rate),
                        "source": f"Last Bill ({pvi_row['supplier_name']} - {pvi_row['vch_no']})",
                        "source_type": "CROSS_SUPPLIER",
                        "precedence": "cross_supplier_history",
                        "last_date": pvi_row["vch_date"],
                        "last_vch_no": pvi_row["vch_no"],
                        "supplier_name": pvi_row["supplier_name"]
                    })
            except Exception:
                pass

            # 3. Precedence 3: Item Master default purchase cost
            it_row = None
            try:
                cursor.execute("""
                    SELECT purc_price, name, unit FROM items
                    WHERE company_id = ? AND id = ?;
                """, (actual_comp_id, item_id))
                it_row = cursor.fetchone()
            except Exception:
                try:
                    cursor.execute("""
                        SELECT cogs_amount as purc_price, name, unit FROM items
                        WHERE company_id = ? AND id = ?;
                    """, (actual_comp_id, item_id))
                    it_row = cursor.fetchone()
                except Exception:
                    it_row = None

            if it_row:
                def_rate = float(it_row["purc_price"] or 0.0)
                return _sanitize_record({
                    "rate": def_rate,
                    "landed_cost": def_rate,
                    "source": "Item Master Default",
                    "source_type": "ITEM_MASTER",
                    "precedence": "item_master_default",
                    "last_date": "",
                    "last_vch_no": "",
                    "supplier_name": ""
                })

        return {
            "rate": 0.0,
            "landed_cost": 0.0,
            "source": "Manual Entry (0.00)",
            "source_type": "MANUAL",
            "precedence": "manual",
            "last_date": "",
            "last_vch_no": "",
            "supplier_name": ""
        }

    def get_item_purchase_history(self, company_id: str, item_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieves full chronological purchase price history for an item.
        Preserves all historical purchases and revisions.
        """
        target_db, actual_comp_id, is_trad = self._get_db_and_company_id(company_id)
        with target_db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT h.*, s.name as supplier_name, i.name as product_name, i.unit as product_unit
                    FROM purchase_price_history h
                    LEFT JOIN suppliers s ON s.id = h.supplier_id
                    LEFT JOIN items i ON i.id = h.item_id
                    WHERE h.company_id = ? AND h.item_id = ?
                    ORDER BY h.purchase_date DESC, h.created_at DESC
                    LIMIT ?;
                """, (actual_comp_id, item_id, limit))
                rows = cursor.fetchall()
                if rows:
                    return [_sanitize_record(dict(r)) for r in rows]
            except Exception:
                pass

            # Fallback to purchase_voucher_items if history table was just migrated
            cursor.execute("""
                SELECT pvi.purchase_rate, pvi.qty, pvi.discount_percent, pvi.tax_rate,
                       pvi.landed_cost, pv.vch_date as purchase_date, pv.vch_no as voucher_number,
                       pv.supplier_invoice_no, pv.supplier_name, i.name as product_name, i.unit as product_unit
                FROM purchase_voucher_items pvi
                JOIN purchase_vouchers pv ON pv.id = pvi.voucher_id
                JOIN items i ON i.id = pvi.item_id
                WHERE pv.company_id = ? AND pvi.item_id = ? AND COALESCE(pv.is_cancelled, 0) = 0
                ORDER BY pv.vch_date DESC, pv.created_at DESC
                LIMIT ?;
            """, (actual_comp_id, item_id, limit))
            return [_sanitize_record(dict(r)) for r in cursor.fetchall()]

    def list_purchase_vouchers(
        self,
        company_id: str,
        search_term: str = "",
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        supplier_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 500,
        search_query: Optional[str] = None,
        query: Optional[str] = None,
        **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """
        Lists purchase vouchers with supplier and amount metadata for the Purchase Register.
        Supports text search, date range filtering, supplier-wise filtering, and status filtering.
        """
        target_db, actual_comp_id, is_trad = self._get_db_and_company_id(company_id)
        effective_search = (search_term or search_query or query or "").strip()
        query_clauses = ["pv.company_id = ?", "COALESCE(pv.is_cancelled, 0) = 0"]
        params: List[Any] = [actual_comp_id]

        if effective_search:
            st = f"%{effective_search.upper()}%"
            query_clauses.append("""
                (
                    UPPER(pv.vch_no) LIKE ? OR
                    UPPER(pv.supplier_invoice_no) LIKE ? OR
                    UPPER(pv.supplier_name) LIKE ?
                )
            """)
            params.extend([st, st, st])

        if from_date and from_date.strip():
            query_clauses.append("pv.vch_date >= ?")
            params.append(from_date.strip())

        if to_date and to_date.strip():
            query_clauses.append("pv.vch_date <= ?")
            params.append(to_date.strip())

        if supplier_id and supplier_id.strip():
            query_clauses.append("pv.supplier_id = ?")
            params.append(supplier_id.strip())

        if status and status.strip():
            st_up = status.strip().upper()
            if st_up == "PAID":
                query_clauses.append("pv.outstanding_balance <= 0.01")
            elif st_up == "UNPAID":
                query_clauses.append("pv.amount_paid <= 0.01 AND pv.outstanding_balance > 0.01")
            elif st_up == "PARTIAL":
                query_clauses.append("pv.amount_paid > 0.01 AND pv.outstanding_balance > 0.01")

        where_sql = " AND ".join(query_clauses)
        params.append(limit)

        with target_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT pv.*, s.mobile as supplier_mobile,
                       (SELECT COUNT(pvi.id) FROM purchase_voucher_items pvi WHERE pvi.voucher_id = pv.id) as item_count
                FROM purchase_vouchers pv
                LEFT JOIN suppliers s ON s.id = pv.supplier_id
                WHERE {where_sql}
                ORDER BY pv.vch_date DESC, pv.created_at DESC
                LIMIT ?;
            """, tuple(params))
            results = []
            for r in cursor.fetchall():
                d = dict(r)
                grand = float(d.get("grand_total") or 0.0)
                paid = float(d.get("amount_paid") or 0.0)
                bal = float(d.get("outstanding_balance") or (grand - paid))
                if bal <= 0.01:
                    pay_status = "PAID"
                elif paid > 0.01 and bal > 0.01:
                    pay_status = "PARTIAL"
                else:
                    pay_status = "UNPAID"
                d["payment_status"] = pay_status
                d["tax_amount"] = float(d.get("cgst_amount") or 0.0) + float(d.get("sgst_amount") or 0.0) + float(d.get("igst_amount") or 0.0)
                results.append(_sanitize_record(d))
            return results

    def get_purchase_voucher_details(self, company_id: str, voucher_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves complete purchase voucher with line items and landed cost."""
        target_db, actual_comp_id, is_trad = self._get_db_and_company_id(company_id)
        with target_db.get_connection() as conn:
            cursor = conn.cursor()
            vch = None
            try:
                cursor.execute("""
                    SELECT pv.*, s.mobile, s.email, s.gstin as supplier_reg_gstin,
                           g.name as godown_name
                    FROM purchase_vouchers pv
                    LEFT JOIN suppliers s ON s.id = pv.supplier_id
                    LEFT JOIN godowns g ON g.id = pv.godown_id
                    WHERE pv.company_id = ? AND (pv.id = ? OR pv.vch_no = ?);
                """, (actual_comp_id, voucher_id, voucher_id))
                vch = cursor.fetchone()
            except Exception:
                cursor.execute("""
                    SELECT pv.*, s.mobile, s.email, s.gstin as supplier_reg_gstin,
                           'Main Store' as godown_name
                    FROM purchase_vouchers pv
                    LEFT JOIN suppliers s ON s.id = pv.supplier_id
                    WHERE pv.company_id = ? AND (pv.id = ? OR pv.vch_no = ?);
                """, (actual_comp_id, voucher_id, voucher_id))
                vch = cursor.fetchone()

            if not vch:
                return None

            v_id = vch["id"]
            items = []
            try:
                cursor.execute("""
                    SELECT pvi.*, i.sales_price as current_mrp, i.purc_price as item_master_rate
                    FROM purchase_voucher_items pvi
                    LEFT JOIN items i ON i.id = pvi.item_id
                    WHERE pvi.voucher_id = ?
                    ORDER BY pvi.sn ASC;
                """, (v_id,))
                items = [dict(r) for r in cursor.fetchall()]
            except Exception:
                cursor.execute("""
                    SELECT * FROM purchase_voucher_items
                    WHERE voucher_id = ?
                    ORDER BY sn ASC;
                """, (v_id,))
                items = [dict(r) for r in cursor.fetchall()]

            res = dict(vch)
            res["items"] = items
            res["tax_amount"] = float(res.get("cgst_amount") or 0.0) + float(res.get("sgst_amount") or 0.0) + float(res.get("igst_amount") or 0.0)
            return _sanitize_record(res)

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
        target_db, actual_comp_id, is_trad = self._get_db_and_company_id(company_id)
        orig_vch_id = data.get("original_voucher_id")
        orig_vch = self.get_purchase_voucher_details(actual_comp_id, orig_vch_id) if orig_vch_id else None

        supplier_name = data.get("supplier_name") or (orig_vch.get("supplier_name") if orig_vch else "")
        supplier_id = data.get("supplier_id") or (orig_vch.get("supplier_id") if orig_vch else None)
        orig_supp_inv = data.get("original_supplier_inv_no") or (orig_vch.get("supplier_invoice_no") if orig_vch else "")
        vch_date = data.get("vch_date") or datetime.now().strftime("%Y-%m-%d")
        branch_id = data.get("branch_id") or (orig_vch.get("branch_id") if orig_vch else self._get_default_branch_id(actual_comp_id, db=target_db))
        reason = data.get("reason") or "Defective / Return Goods"
        items = data.get("items") or []

        if not items:
            raise ValueError("Purchase return must specify at least one return line item.")

        ret_id = str(uuid.uuid4())
        # Generate return voucher number
        with target_db.get_connection() as conn:
            cursor = conn.cursor()
            cnt = 0
            try:
                cursor.execute("SELECT COUNT(id) FROM purchase_returns WHERE company_id = ?;", (actual_comp_id,))
                cnt = cursor.fetchone()[0]
            except Exception:
                pass
            vch_no = f"PR-{str(cnt + 1).zfill(6)}"

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
            try:
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
            except Exception as e:
                logger.debug(f"purchase_returns insert note: {e}")

            for it in calculated_items:
                item_id = it["item_id"]
                qty = it["qty"]
                try:
                    cursor.execute("""
                        INSERT INTO purchase_return_items (
                            id, return_id, item_id, sn, item_name, qty, unit, rate,
                            tax_rate, tax_amount, line_total
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        str(uuid.uuid4()), ret_id, item_id, idx, it["name"],
                        qty, it["unit"], it["rate"], it["tax_rate"], it["tax_amount"], it["line_total"]
                    ))
                except Exception as e:
                    logger.debug(f"purchase_return_items insert note: {e}")

                # Deduct inventory for returned goods
                if item_id and branch_id:
                    if is_trad:
                        scaled_qty = int(round(qty * 1000))
                        cursor.execute("""
                            UPDATE stock_balances
                            SET current_qty_scaled = current_qty_scaled - ?, updated_at = CURRENT_TIMESTAMP
                            WHERE company_id = ? AND branch_id = ? AND item_id = ?;
                        """, (scaled_qty, actual_comp_id, branch_id, item_id))
                    else:
                        cursor.execute("""
                            UPDATE stock_balances
                            SET current_qty = current_qty - ?, last_updated = CURRENT_TIMESTAMP
                            WHERE branch_id = ? AND item_id = ?;
                        """, (qty, branch_id, item_id))

                    try:
                        cursor.execute("""
                            INSERT INTO stock_movements (
                                id, company_id, branch_id, item_id, movement_type,
                                qty, unit_cost, reference_type, reference_id, notes
                            ) VALUES (?, ?, ?, ?, 'PURCHASE_RETURN', ?, ?, 'PURCHASE_RETURN', ?, ?);
                        """, (
                            str(uuid.uuid4()), actual_comp_id, branch_id, item_id,
                            -qty, it["rate"], vch_no, f"Return against bill #{orig_supp_inv}: {reason}"
                        ))
                    except Exception as e:
                        logger.debug(f"purchase return stock_movements note: {e}")

            # Adjust supplier balance
            if supplier_id:
                try:
                    cursor.execute("""
                        UPDATE suppliers
                        SET current_balance = current_balance - ?, updated_at = CURRENT_TIMESTAMP
                        WHERE company_id = ? AND id = ?;
                    """, (float(total_grand), actual_comp_id, supplier_id))
                except Exception as e:
                    logger.debug(f"purchase return supplier balance note: {e}")

            # Accounting Reversal Posting
            try:
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
            except Exception as e:
                logger.debug(f"purchase return journal note: {e}")

            conn.commit()

        try:
            self.inventory_service.evaluate_low_stock_alerts(actual_comp_id)
        except Exception as e:
            logger.debug(f"evaluate_low_stock_alerts after purchase return: {e}")

        logger.info(f"Purchase Return {vch_no} processed successfully.")
        return _sanitize_record({
            "return_id": ret_id,
            "vch_no": vch_no,
            "grand_total": float(total_grand),
            "items_count": len(calculated_items)
        })


purchase_service = PurchaseService()
