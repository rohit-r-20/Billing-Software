"""
Migration Service for Anti Matrix Billing ERP.
Imports browser localStorage data (companies, configs, accounts, items, sales vouchers)
into the canonical SQLite database idempotently without duplicates.
"""
import json
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from db.database import db_manager, DatabaseManager
from core.security import hash_password
from core.logging_config import logger


class MigrationService:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or db_manager

    def import_from_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Load and import from a JSON file export of browser localStorage."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Export file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self.import_localstorage_payload(data)

    def import_localstorage_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses and imports a dictionary containing alpha_* localStorage keys.
        Returns a detailed summary of imported, skipped, and updated records.
        """
        summary = {
            "companies_imported": 0,
            "companies_skipped": 0,
            "configs_imported": 0,
            "accounts_imported": 0,
            "accounts_skipped": 0,
            "items_imported": 0,
            "items_skipped": 0,
            "vouchers_imported": 0,
            "vouchers_skipped": 0,
            "stock_movements_created": 0,
            "errors": []
        }

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Process Companies
            raw_companies = payload.get("alpha_companies")
            if isinstance(raw_companies, str):
                try:
                    raw_companies = json.loads(raw_companies)
                except Exception:
                    raw_companies = []

            if not raw_companies:
                # Default seed company if no companies in payload
                raw_companies = [
                    {
                        "id": "COMP0001",
                        "name": "ANTI MATRIX",
                        "code": "COMP0001",
                        "finYear": "2026-2027 (1 Yr)",
                        "taxNo": "33AAAPL1234F1Z1",
                        "state": "Tamilnadu",
                        "username": "A",
                        "password": "a"
                    }
                ]

            company_id_map = {}  # code -> db id

            for comp in raw_companies:
                code = comp.get("code") or comp.get("id") or "COMP0001"
                code = code.strip().upper()
                name = (comp.get("name") or "ANTI MATRIX").strip().upper()
                fin_year = comp.get("finYear") or "2026-2027 (1 Yr)"
                gstin = (comp.get("taxNo") or "").strip().upper()
                state = comp.get("state") or "Tamilnadu"
                username = comp.get("username") or "A"
                raw_pwd = comp.get("password") or "a"
                pwd_hash = hash_password(raw_pwd)

                # Check if company already exists
                cursor.execute("SELECT id FROM companies WHERE code = ?;", (code,))
                row = cursor.fetchone()
                if row:
                    comp_id = row["id"]
                    summary["companies_skipped"] += 1
                else:
                    comp_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO companies (id, code, name, fin_year, gstin, state, username, password_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """, (comp_id, code, name, fin_year, gstin, state, username, pwd_hash))
                    summary["companies_imported"] += 1

                company_id_map[code] = comp_id

                # Ensure Default Branch and Register exist for this company
                cursor.execute("SELECT id FROM branches WHERE company_id = ? AND is_default = 1;", (comp_id,))
                branch_row = cursor.fetchone()
                if not branch_row:
                    branch_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO branches (id, company_id, code, name, is_default)
                        VALUES (?, ?, 'BR01', 'Main Branch', 1);
                    """, (branch_id, comp_id))
                else:
                    branch_id = branch_row["id"]

                cursor.execute("SELECT id FROM registers WHERE branch_id = ? AND code = 'REG01';", (branch_id,))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO registers (id, branch_id, code, name)
                        VALUES (?, ?, 'REG01', 'Cashier Register 1');
                    """, (str(uuid.uuid4()), branch_id))

            # 2. Process Company Configurations
            for code, comp_id in company_id_map.items():
                cfg_key = f"alpha_config_{code}"
                raw_cfg = payload.get(cfg_key, {})
                if isinstance(raw_cfg, str):
                    try:
                        raw_cfg = json.loads(raw_cfg)
                    except Exception:
                        raw_cfg = {}

                vch_start = int(raw_cfg.get("vchStart", 1))
                vch_digits = int(raw_cfg.get("vchDigits", 3))
                vch_prefix = str(raw_cfg.get("vchPrefix", ""))
                default_tax = str(raw_cfg.get("defaultTax", "18"))
                auto_round = str(raw_cfg.get("autoRound", "Y"))

                cursor.execute("""
                    INSERT INTO company_configs (company_id, vch_start, vch_digits, vch_prefix, default_tax, auto_round)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(company_id) DO UPDATE SET
                        vch_start = excluded.vch_start,
                        vch_digits = excluded.vch_digits,
                        vch_prefix = excluded.vch_prefix,
                        default_tax = excluded.default_tax,
                        auto_round = excluded.auto_round;
                """, (comp_id, vch_start, vch_digits, vch_prefix, default_tax, auto_round))
                summary["configs_imported"] += 1

            # 3. Process Accounts
            for code, comp_id in company_id_map.items():
                acc_key = f"alpha_accounts_{code}"
                raw_accounts = payload.get(acc_key, [])
                if isinstance(raw_accounts, str):
                    try:
                        raw_accounts = json.loads(raw_accounts)
                    except Exception:
                        raw_accounts = []

                for acc in raw_accounts:
                    acc_name = acc.get("name", "").strip()
                    if not acc_name:
                        continue

                    cursor.execute("SELECT id FROM accounts WHERE company_id = ? AND name = ?;", (comp_id, acc_name))
                    if cursor.fetchone():
                        summary["accounts_skipped"] += 1
                        continue

                    acc_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO accounts (
                            id, company_id, name, alias, print_name, account_group,
                            op_bal, op_type, address, state, dealer_type, gstin,
                            mobile, bank_name, bank_acc, ifsc, current_balance
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        acc_id,
                        comp_id,
                        acc_name,
                        acc.get("alias", ""),
                        acc.get("printName", acc_name),
                        acc.get("group", "Sundry Debtors"),
                        float(acc.get("opBal") or 0.0),
                        acc.get("opType", "Dr"),
                        acc.get("address", ""),
                        acc.get("state", "Tamilnadu"),
                        acc.get("dealerType", "Unregistered"),
                        acc.get("gstin", ""),
                        acc.get("mobile", ""),
                        acc.get("bankName", ""),
                        acc.get("bankAcc", ""),
                        acc.get("ifsc", ""),
                        float(acc.get("opBal") or 0.0)
                    ))
                    summary["accounts_imported"] += 1

            # 4. Process Items & Initial Stock
            item_id_map = {}  # (company_id, item_name_lower) -> item_id
            for code, comp_id in company_id_map.items():
                cursor.execute("SELECT id FROM branches WHERE company_id = ? AND is_default = 1;", (comp_id,))
                default_branch_id = cursor.fetchone()["id"]

                item_key = f"alpha_items_{code}"
                raw_items = payload.get(item_key, [])
                if isinstance(raw_items, str):
                    try:
                        raw_items = json.loads(raw_items)
                    except Exception:
                        raw_items = []

                for it in raw_items:
                    it_name = it.get("name", "").strip()
                    if not it_name:
                        continue

                    cursor.execute("SELECT id FROM items WHERE company_id = ? AND name = ?;", (comp_id, it_name))
                    existing = cursor.fetchone()
                    if existing:
                        it_id = existing["id"]
                        item_id_map[(comp_id, it_name.upper())] = it_id
                        summary["items_skipped"] += 1
                        continue

                    it_id = str(uuid.uuid4())
                    item_id_map[(comp_id, it_name.upper())] = it_id

                    op_qty = float(it.get("opStockQty") or 0.0)
                    op_val = float(it.get("opStockVal") or 0.0)
                    sales_price = float(it.get("salesPrice") or 0.0)
                    purc_price = float(it.get("purcPrice") or 0.0)
                    mrp = float(it.get("mrp") or 0.0)
                    min_price = float(it.get("minSalesPrice") or 0.0)

                    cursor.execute("""
                        INSERT INTO items (
                            id, company_id, name, alias, print_name, item_group,
                            unit, op_stock_qty, op_stock_val, tax_category, hsn,
                            sales_price, purc_price, mrp, min_sales_price, description
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        it_id,
                        comp_id,
                        it_name,
                        it.get("alias", ""),
                        it.get("printName", it_name),
                        it.get("group", "General"),
                        it.get("unit", "Pcs."),
                        op_qty,
                        op_val,
                        it.get("taxCategory", "GST 18%"),
                        it.get("hsn", ""),
                        sales_price,
                        purc_price,
                        mrp,
                        min_price,
                        it.get("description", "")
                    ))
                    summary["items_imported"] += 1

                    # Register barcode if alias or code looks like a barcode
                    barcode = it.get("barcode") or it.get("alias")
                    if barcode and len(str(barcode).strip()) >= 3:
                        cursor.execute("""
                            INSERT OR IGNORE INTO item_barcodes (id, item_id, company_id, barcode, is_primary)
                            VALUES (?, ?, ?, ?, 1);
                        """, (str(uuid.uuid4()), it_id, comp_id, str(barcode).strip().upper()))

                    # Setup Stock Balance
                    cursor.execute("""
                        INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(branch_id, item_id) DO UPDATE SET current_qty = current_qty + excluded.current_qty;
                    """, (str(uuid.uuid4()), comp_id, default_branch_id, it_id, op_qty))

                    # Record Opening Stock Movement
                    if op_qty > 0:
                        cursor.execute("""
                            INSERT INTO stock_movements (
                                id, company_id, branch_id, item_id, movement_type,
                                qty, unit_cost, reference_type, notes
                            ) VALUES (?, ?, ?, ?, 'OPENING', ?, ?, 'MIGRATION', 'Opening stock from browser data');
                        """, (str(uuid.uuid4()), comp_id, default_branch_id, it_id, op_qty, purc_price))
                        summary["stock_movements_created"] += 1

            # 5. Process Sales Vouchers (Invoices)
            for code, comp_id in company_id_map.items():
                cursor.execute("SELECT id FROM branches WHERE company_id = ? AND is_default = 1;", (comp_id,))
                default_branch_id = cursor.fetchone()["id"]

                vch_key = f"alpha_vouchers_{code}"
                raw_vouchers = payload.get(vch_key, [])
                if isinstance(raw_vouchers, str):
                    try:
                        raw_vouchers = json.loads(raw_vouchers)
                    except Exception:
                        raw_vouchers = []

                for vch in raw_vouchers:
                    vch_no = str(vch.get("vchNo", "")).strip()
                    if not vch_no:
                        continue

                    cursor.execute("SELECT id FROM sales_vouchers WHERE company_id = ? AND vch_no = ?;", (comp_id, vch_no))
                    if cursor.fetchone():
                        summary["vouchers_skipped"] += 1
                        continue

                    vch_id = str(uuid.uuid4())
                    subtotal = float(vch.get("subtotal") or 0.0)
                    raw_gt = str(vch.get("grandTotal", "0")).replace("₹", "").replace(",", "").strip()
                    grand_total = float(raw_gt or 0.0)

                    # Extract tax amounts from voucher or calculate from items
                    party_name = vch.get("party", "CASH").strip()
                    sale_type = vch.get("saleType", "L/GST-18%").strip()

                    # Tax rate approximation from sale type
                    tax_rate = 18.0
                    if "28%" in sale_type:
                        tax_rate = 28.0
                    elif "12%" in sale_type:
                        tax_rate = 12.0
                    elif "5%" in sale_type:
                        tax_rate = 5.0
                    elif "Exempt" in sale_type or "0%" in sale_type:
                        tax_rate = 0.0

                    is_interstate = "I/GST" in sale_type
                    total_tax = max(grand_total - subtotal, 0.0)
                    if is_interstate:
                        igst_amt = total_tax
                        cgst_amt = 0.0
                        sgst_amt = 0.0
                    else:
                        igst_amt = 0.0
                        cgst_amt = round(total_tax / 2.0, 2)
                        sgst_amt = round(total_tax / 2.0, 2)

                    round_off = round(grand_total - (subtotal + total_tax), 2)

                    cursor.execute("""
                        INSERT INTO sales_vouchers (
                            id, company_id, branch_id, vch_no, series, vch_date,
                            sale_type, party_name, mat_centre, narration,
                            subtotal, taxable_amount, tax_rate, cgst_amount, sgst_amount,
                            igst_amount, round_off, grand_total, payment_method, payment_status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CASH', 'PAID');
                    """, (
                        vch_id,
                        comp_id,
                        default_branch_id,
                        vch_no,
                        vch.get("series", "Main"),
                        vch.get("date", ""),
                        sale_type,
                        party_name,
                        vch.get("matCentre", "Main Store"),
                        vch.get("narration", ""),
                        subtotal,
                        subtotal,
                        tax_rate,
                        cgst_amt,
                        sgst_amt,
                        igst_amt,
                        round_off,
                        grand_total
                    ))
                    summary["vouchers_imported"] += 1

                    # Line items
                    items = vch.get("items", [])
                    for idx, line in enumerate(items, start=1):
                        line_name = line.get("name", "").strip()
                        line_qty = float(line.get("qty") or 0.0)
                        line_price = float(line.get("price") or 0.0)
                        line_amt = float(line.get("amount") or (line_qty * line_price))
                        matched_item_id = item_id_map.get((comp_id, line_name.upper()))

                        cursor.execute("""
                            INSERT INTO sales_voucher_items (
                                id, voucher_id, item_id, sn, item_name, qty, unit, price, amount
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """, (
                            str(uuid.uuid4()),
                            vch_id,
                            matched_item_id,
                            idx,
                            line_name,
                            line_qty,
                            line.get("unit", "Pcs."),
                            line_price,
                            line_amt
                        ))

                        # If item is matched, update stock movement and balance
                        if matched_item_id and line_qty > 0:
                            cursor.execute("""
                                UPDATE stock_balances
                                SET current_qty = current_qty - ?, last_updated = CURRENT_TIMESTAMP
                                WHERE branch_id = ? AND item_id = ?;
                            """, (line_qty, default_branch_id, matched_item_id))

                            cursor.execute("""
                                INSERT INTO stock_movements (
                                    id, company_id, branch_id, item_id, movement_type,
                                    qty, unit_cost, reference_type, reference_id, notes
                                ) VALUES (?, ?, ?, ?, 'SALE', ?, ?, 'INVOICE', ?, 'Sale voucher migration');
                            """, (
                                str(uuid.uuid4()),
                                comp_id,
                                default_branch_id,
                                matched_item_id,
                                -line_qty,
                                line_price,
                                vch_no
                            ))
                            summary["stock_movements_created"] += 1

            conn.commit()

        logger.info(f"Migration completed with summary: {summary}")
        return summary


migration_service = MigrationService()
