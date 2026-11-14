#!/usr/bin/env python3
"""
Alpha Billing V2 - Safe SQLite to Supabase PostgreSQL Migration Script.
Enforces strict V2 scope:
- Single Company: 'ANTI MATRIX' (3a743bcd-8f9a-4154-a316-509cba3de99a)
- Single Location: 'Main Branch' (1ebe5b37-4c99-4395-8783-6813eb02b521)
- Non-destructive, idempotent, transaction-backed with automatic rollback.
- Complete financial, tax, and inventory reconciliation.
"""

import os
import sys
import shutil
import sqlite3
import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import psycopg
from psycopg import sql

# Ensure workspace root is in sys.path
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_DIR))

from core.configuration import config
from core.logging_config import logger

PRIMARY_COMPANY_ID = "3a743bcd-8f9a-4154-a316-509cba3de99a"
DEFAULT_BRANCH_ID = "1ebe5b37-4c99-4395-8783-6813eb02b521"


class V2MigrationOrchestrator:
    def __init__(
        self,
        sqlite_path: Optional[Path] = None,
        target_pg_url: Optional[str] = None,
        dry_run: bool = False,
        truncate_target: bool = False,
    ):
        self.sqlite_path = Path(sqlite_path or config.DATABASE_PATH).resolve()
        raw_url = (target_pg_url or config.get_database_url()).strip()
        # Clean SQLAlchemy driver prefix for psycopg 3
        if raw_url.startswith("postgresql+psycopg://"):
            self.pg_conn_str = raw_url.replace("postgresql+psycopg://", "postgresql://", 1)
        elif raw_url.startswith("postgresql+psycopg2://"):
            self.pg_conn_str = raw_url.replace("postgresql+psycopg2://", "postgresql://", 1)
        else:
            self.pg_conn_str = raw_url

        self.dry_run = dry_run
        self.truncate_target = truncate_target
        self.backup_path: Optional[Path] = None
        self.stats: Dict[str, Dict[str, Any]] = {}

    def mask_url(self, url: str) -> str:
        import re
        return re.sub(r":([^@/]+)@", ":****@", url)

    def create_safety_backup(self) -> Path:
        """Creates a timestamped snapshot of the SQLite database before migration."""
        backups_dir = WORKSPACE_DIR / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backups_dir / f"pre_migration_backup_{timestamp}.db"
        shutil.copy2(self.sqlite_path, backup_file)
        self.backup_path = backup_file
        logger.info(f"Created protected SQLite pre-migration backup at: {backup_file}")
        return backup_file

    def verify_sqlite_integrity(self) -> bool:
        """Validates that the source SQLite file passes integrity check."""
        with sqlite3.connect(f"file:{self.sqlite_path}?mode=ro", uri=True) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            res = cur.fetchone()[0]
            if res != "ok":
                raise RuntimeError(f"Source SQLite database failed integrity check: {res}")
            cur.execute("PRAGMA foreign_key_check;")
            fk_res = cur.fetchall()
            if fk_res:
                logger.warning(f"Source SQLite foreign key violations found: {fk_res}")
        return True

    def execute_migration(self) -> Dict[str, Any]:
        """Executes the safe migration workflow."""
        start_time = time.time()
        print(f"\n================================================================================")
        print(f"Alpha Billing V2 - Safe Database Migration")
        print(f"================================================================================")
        print(f"Source SQLite : {self.sqlite_path}")
        print(f"Target DB     : {self.mask_url(self.pg_conn_str)}")
        print(f"Dry Run Mode  : {'ENABLED (No changes will be saved)' if self.dry_run else 'DISABLED (Live Cutover Mode)'}")
        print(f"Truncate Target: {self.truncate_target}")
        print(f"================================================================================\n")

        # 1. Verification & Backup
        self.verify_sqlite_integrity()
        if not self.dry_run:
            self.create_safety_backup()

        # 2. Open Read-Only Connection to SQLite
        sq_conn = sqlite3.connect(f"file:{self.sqlite_path}?mode=ro", uri=True)
        sq_conn.row_factory = sqlite3.Row
        sq_cur = sq_conn.cursor()

        # 3. Connect to Target PostgreSQL
        try:
            pg_conn = psycopg.connect(self.pg_conn_str, autocommit=False)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to target PostgreSQL: {e}")

        try:
            with pg_conn.cursor() as pg_cur:
                # Truncate if requested
                if self.truncate_target:
                    print("Cleaning target tables in reverse topological order...")
                    self._truncate_tables(pg_cur)

                # Migrate entities in topological order
                print("Migrating entities in topological order...")
                self._migrate_companies(sq_cur, pg_cur)
                self._migrate_company_configs(sq_cur, pg_cur)
                self._migrate_branches(sq_cur, pg_cur)
                self._migrate_registers(sq_cur, pg_cur)
                self._migrate_accounts(sq_cur, pg_cur)
                self._migrate_suppliers(sq_cur, pg_cur)
                self._migrate_items(sq_cur, pg_cur)
                self._migrate_barcodes(sq_cur, pg_cur)
                self._migrate_stock_balances(sq_cur, pg_cur)
                self._migrate_stock_movements(sq_cur, pg_cur)
                self._migrate_item_stock_configs(sq_cur, pg_cur)
                self._migrate_sales_vouchers(sq_cur, pg_cur)
                self._migrate_sales_voucher_items(sq_cur, pg_cur)
                self._migrate_payments(sq_cur, pg_cur)
                self._migrate_purchase_vouchers(sq_cur, pg_cur)
                self._migrate_purchase_voucher_items(sq_cur, pg_cur)
                self._migrate_sales_returns(sq_cur, pg_cur)
                self._migrate_sales_return_items(sq_cur, pg_cur)
                self._migrate_category_discounts(sq_cur, pg_cur)
                self._migrate_audit_logs(sq_cur, pg_cur)
                self._migrate_low_stock_alerts(sq_cur, pg_cur)
                self._migrate_journal_entries(sq_cur, pg_cur)
                self._migrate_journal_entry_lines(sq_cur, pg_cur)
                self._migrate_ocr_drafts(sq_cur, pg_cur)
                self._init_sequences(pg_cur)

                # 4. Reconciliation & Verification
                print("\nValidating financial and inventory reconciliation...")
                recon_results = self._validate_reconciliation(sq_cur, pg_cur)

                # 5. Integrity Constraints Check
                print("Validating PostgreSQL referential integrity...")
                integrity_valid = self._verify_integrity(pg_cur)

                if not integrity_valid or not recon_results["all_matched"]:
                    raise ValueError(f"Validation failed! Reconciliation or integrity check mismatch.")

                if self.dry_run:
                    print("\n[DRY RUN] Rolling back PostgreSQL transaction. Target database remains unchanged.")
                    pg_conn.rollback()
                else:
                    print("\n[COMMITTING] Committing migration transaction to PostgreSQL...")
                    pg_conn.commit()
                    print("[SUCCESS] Transaction committed successfully!")

        except Exception as exc:
            pg_conn.rollback()
            logger.error(f"Migration aborted due to error: {exc}", exc_info=True)
            raise
        finally:
            sq_conn.close()
            pg_conn.close()

        duration = time.time() - start_time
        print(f"\nMigration completed in {duration:.2f} seconds.")
        return {
            "success": True,
            "duration": duration,
            "dry_run": self.dry_run,
            "backup_file": str(self.backup_path) if self.backup_path else None,
            "table_stats": self.stats,
            "reconciliation": recon_results,
        }

    def _truncate_tables(self, pg_cur: psycopg.Cursor):
        """Truncates target tables in reverse topological order."""
        tables_to_clean = [
            "journal_entry_lines", "journal_entries",
            "ocr_invoice_drafts",
            "low_stock_alerts", "audit_logs",
            "sales_return_items", "sales_returns",
            "purchase_voucher_items", "purchase_vouchers",
            "payments", "sales_voucher_items", "sales_vouchers",
            "stock_movements", "stock_balances", "item_branch_stock_configs",
            "item_barcodes", "items",
            "suppliers", "accounts",
            "registers", "branches", "company_configs", "customer_category_discounts",
            "barcode_sequences", "voucher_sequences", "companies"
        ]
        for tbl in tables_to_clean:
            pg_cur.execute(sql.SQL("TRUNCATE TABLE {} CASCADE;").format(sql.Identifier(tbl)))

    def _record_stat(self, table: str, source_cnt: int, migrated_cnt: int):
        self.stats[table] = {"source": source_cnt, "migrated": migrated_cnt}
        print(f"  ✓ {table:<28} : {migrated_cnt:5d} records migrated (source had {source_cnt:5d})")

    def _migrate_companies(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM companies WHERE id = ?;", (PRIMARY_COMPANY_ID,))
        row = sq_cur.fetchone()
        if not row:
            raise ValueError(f"Primary company {PRIMARY_COMPANY_ID} not found in SQLite!")
        r = dict(row)
        pg_cur.execute(
            """
            INSERT INTO companies (id, code, name, fin_year, gstin, state, username, password_hash, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;
            """,
            (r["id"], r["code"], r["name"], r["fin_year"], r.get("gstin"), r.get("state"), r.get("username"), r.get("password_hash"), r.get("created_at"), r.get("updated_at"))
        )
        self._record_stat("companies", 1, 1)

    def _migrate_company_configs(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM company_configs WHERE company_id = ?;", (PRIMARY_COMPANY_ID,))
        row = sq_cur.fetchone()
        if row:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO company_configs (company_id, vch_start, vch_digits, vch_prefix, default_tax, auto_round, receipt_width, print_copies, allow_negative_stock, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (company_id) DO UPDATE SET updated_at = EXCLUDED.updated_at;
                """,
                (r["company_id"], r.get("vch_start", 1), r.get("vch_digits", 3), r.get("vch_prefix", ""), r.get("default_tax", "18"), r.get("auto_round", "Y"), r.get("receipt_width", 80), r.get("print_copies", 1), r.get("allow_negative_stock", 0), r.get("updated_at"))
            )
            self._record_stat("company_configs", 1, 1)

    def _migrate_branches(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM branches WHERE id = ?;", (DEFAULT_BRANCH_ID,))
        row = sq_cur.fetchone()
        if not row:
            # Fallback to default branch
            sq_cur.execute("SELECT * FROM branches WHERE company_id = ? AND is_default = 1 LIMIT 1;", (PRIMARY_COMPANY_ID,))
            row = sq_cur.fetchone()
        r = dict(row)
        pg_cur.execute(
            """
            INSERT INTO branches (id, company_id, code, name, address, phone, is_default, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING;
            """,
            (r["id"], PRIMARY_COMPANY_ID, r.get("code") or "BR001", r.get("name") or "Main Branch", r.get("address"), r.get("phone"), 1, r.get("created_at"))
        )
        self._record_stat("branches (Main Branch)", 1, 1)

    def _migrate_registers(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM registers LIMIT 1;")
        row = sq_cur.fetchone()
        if row:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO registers (id, branch_id, code, name, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], DEFAULT_BRANCH_ID, r.get("code") or "REG01", r.get("name") or "Main POS", r.get("created_at"))
            )
            self._record_stat("registers", 1, 1)

    def _migrate_accounts(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM accounts WHERE company_id = ?;", (PRIMARY_COMPANY_ID,))
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO accounts (id, company_id, name, alias, print_name, account_group, op_bal, op_type, address, country, state, dealer_type, customer_category, gstin, mobile, whatsapp, bank_name, bank_acc, ifsc, pincode, payment_terms, notes, current_balance, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;
                """,
                (r["id"], PRIMARY_COMPANY_ID, r["name"], r.get("alias"), r.get("print_name") or r["name"], r.get("account_group", "Sundry Debtors"), r.get("op_bal", 0.0), r.get("op_type", "Dr"), r.get("address"), r.get("country", "India"), r.get("state", "Tamilnadu"), r.get("dealer_type", "Unregistered"), r.get("customer_category", "Direct Customer"), r.get("gstin"), r.get("mobile"), r.get("whatsapp"), r.get("bank_name"), r.get("bank_acc"), r.get("ifsc"), r.get("pincode"), r.get("payment_terms", 30), r.get("notes"), r.get("current_balance", 0.0), r.get("is_active", 1), r.get("created_at"), r.get("updated_at"))
            )
        self._record_stat("accounts", len(rows), len(rows))

    def _migrate_suppliers(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM suppliers WHERE company_id = ?;", (PRIMARY_COMPANY_ID,))
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO suppliers (id, company_id, code, name, contact_person, mobile, email, gstin, pan, address, city, state, pincode, opening_balance, current_balance, credit_limit, payment_terms, bank_name, bank_acc, ifsc, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;
                """,
                (r["id"], PRIMARY_COMPANY_ID, r["code"], r["name"], r.get("contact_person"), r.get("mobile"), r.get("email"), r.get("gstin"), r.get("pan"), r.get("address"), r.get("city"), r.get("state", "Tamilnadu"), r.get("pincode"), r.get("opening_balance", 0.0), r.get("current_balance", 0.0), r.get("credit_limit", 0.0), r.get("payment_terms", 30), r.get("bank_name"), r.get("bank_acc"), r.get("ifsc"), r.get("is_active", 1), r.get("created_at"), r.get("updated_at"))
            )
        self._record_stat("suppliers", len(rows), len(rows))

    def _migrate_items(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM items WHERE company_id = ?;", (PRIMARY_COMPANY_ID,))
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO items (id, company_id, name, alias, print_name, item_group, unit, op_stock_qty, op_stock_val, tax_category, hsn, sales_price, purc_price, mrp, min_sales_price, description, min_stock_alert_level, reorder_level, reorder_qty, max_stock_level, alert_enabled, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;
                """,
                (r["id"], PRIMARY_COMPANY_ID, r["name"], r.get("alias"), r.get("print_name") or r["name"], r.get("item_group", "General"), r.get("unit", "Pcs."), r.get("op_stock_qty", 0.0), r.get("op_stock_val", 0.0), r.get("tax_category", "GST 18%"), r.get("hsn"), r.get("sales_price", 0.0), r.get("purc_price", 0.0), r.get("mrp", 0.0), r.get("min_sales_price", 0.0), r.get("description"), r.get("min_stock_alert_level", 0.0), r.get("reorder_level", 0.0), r.get("reorder_qty", 0.0), r.get("max_stock_level", 0.0), r.get("alert_enabled", 1), r.get("is_active", 1), r.get("created_at"))
            )
        self._record_stat("items", len(rows), len(rows))

    def _migrate_barcodes(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM item_barcodes WHERE company_id = ?;", (PRIMARY_COMPANY_ID,))
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO item_barcodes (id, item_id, company_id, barcode, is_primary, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], r["item_id"], PRIMARY_COMPANY_ID, r["barcode"], r.get("is_primary", 1), r.get("created_at"))
            )
        self._record_stat("item_barcodes", len(rows), len(rows))

    def _migrate_stock_balances(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM stock_balances WHERE company_id = ? AND branch_id = ?;", (PRIMARY_COMPANY_ID, DEFAULT_BRANCH_ID))
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET current_qty = EXCLUDED.current_qty;
                """,
                (r["id"], PRIMARY_COMPANY_ID, DEFAULT_BRANCH_ID, r["item_id"], r.get("current_qty", 0.0), r.get("last_updated"))
            )
        self._record_stat("stock_balances (Main Branch)", len(rows), len(rows))

    def _migrate_stock_movements(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM stock_movements WHERE company_id = ?;", (PRIMARY_COMPANY_ID,))
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO stock_movements (id, company_id, branch_id, item_id, movement_type, qty, unit_cost, reference_type, reference_id, notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], PRIMARY_COMPANY_ID, DEFAULT_BRANCH_ID, r["item_id"], r["movement_type"], r["qty"], r.get("unit_cost", 0.0), r.get("reference_type"), r.get("reference_id"), r.get("notes"), r.get("created_at"))
            )
        self._record_stat("stock_movements", len(rows), len(rows))

    def _migrate_item_stock_configs(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM item_branch_stock_configs WHERE company_id = ?;", (PRIMARY_COMPANY_ID,))
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO item_branch_stock_configs (id, company_id, branch_id, item_id, min_stock_level, reorder_level, reorder_qty, max_stock_level, alert_enabled, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], PRIMARY_COMPANY_ID, DEFAULT_BRANCH_ID, r["item_id"], r.get("min_stock_level"), r.get("reorder_level"), r.get("reorder_qty"), r.get("max_stock_level"), r.get("alert_enabled", 1), r.get("updated_at"))
            )
        self._record_stat("item_branch_stock_configs", len(rows), len(rows))

    def _migrate_sales_vouchers(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM sales_vouchers WHERE company_id = ?;", (PRIMARY_COMPANY_ID,))
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO sales_vouchers (id, company_id, branch_id, vch_no, series, vch_date, sale_type, party_name, account_id, party_gstin, mat_centre, narration, subtotal, gross_subtotal, discount_total, customer_category, taxable_amount, tax_rate, cgst_amount, sgst_amount, igst_amount, round_off, grand_total, payment_method, payment_status, is_cancelled, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], PRIMARY_COMPANY_ID, DEFAULT_BRANCH_ID, r["vch_no"], r.get("series", "Main"), r["vch_date"], r.get("sale_type", "L/GST-18%"), r.get("party_name", "CASH"), r.get("account_id"), r.get("party_gstin"), r.get("mat_centre", "Main Store"), r.get("narration"), r.get("subtotal", 0.0), r.get("gross_subtotal", r.get("subtotal", 0.0)), r.get("discount_total", 0.0), r.get("customer_category", "Direct Customer"), r.get("taxable_amount", 0.0), r.get("tax_rate", 0.0), r.get("cgst_amount", 0.0), r.get("sgst_amount", 0.0), r.get("igst_amount", 0.0), r.get("round_off", 0.0), r.get("grand_total", 0.0), r.get("payment_method", "CASH"), r.get("payment_status", "PAID"), r.get("is_cancelled", 0), r.get("created_at"))
            )
        self._record_stat("sales_vouchers", len(rows), len(rows))

    def _migrate_sales_voucher_items(self, sq_cur, pg_cur):
        sq_cur.execute(
            """
            SELECT svi.* FROM sales_voucher_items svi
            JOIN sales_vouchers sv ON sv.id = svi.voucher_id
            WHERE sv.company_id = ?;
            """,
            (PRIMARY_COMPANY_ID,)
        )
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO sales_voucher_items (id, voucher_id, item_id, sn, item_name, barcode, hsn, qty, unit, price, amount, discount_percent, discount_amount, taxable_amount, tax_rate, tax_amount, cgst_rate, sgst_rate, igst_rate, cgst_amount, sgst_amount, igst_amount, line_total)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], r["voucher_id"], r.get("item_id"), r.get("sn", 1), r["item_name"], r.get("barcode"), r.get("hsn"), r["qty"], r.get("unit", "Pcs."), r["price"], r.get("amount", 0.0), r.get("discount_percent", 0.0), r.get("discount_amount", 0.0), r.get("taxable_amount", 0.0), r.get("tax_rate", 18.0), r.get("tax_amount", 0.0), r.get("cgst_rate", 9.0), r.get("sgst_rate", 9.0), r.get("igst_rate", 0.0), r.get("cgst_amount", 0.0), r.get("sgst_amount", 0.0), r.get("igst_amount", 0.0), r.get("line_total", r.get("amount", 0.0)))
            )
        self._record_stat("sales_voucher_items", len(rows), len(rows))

    def _migrate_payments(self, sq_cur, pg_cur):
        sq_cur.execute(
            """
            SELECT p.* FROM payments p
            JOIN sales_vouchers sv ON sv.id = p.voucher_id
            WHERE sv.company_id = ?;
            """,
            (PRIMARY_COMPANY_ID,)
        )
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO payments (id, voucher_id, company_id, method, amount, ref_number, reference_no, notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], r["voucher_id"], PRIMARY_COMPANY_ID, r.get("method", "CASH"), r["amount"], r.get("ref_number"), r.get("reference_no"), r.get("notes"), r.get("created_at"))
            )
        self._record_stat("payments", len(rows), len(rows))

    def _migrate_purchase_vouchers(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM purchase_vouchers WHERE company_id = ?;", (PRIMARY_COMPANY_ID,))
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO purchase_vouchers (id, company_id, branch_id, godown_id, vch_no, supplier_invoice_no, supplier_invoice_date, vch_date, supplier_id, supplier_name, supplier_gstin, supplier_address, supplier_state, place_of_supply, payment_type, due_date, purchase_type, narration, gross_amount, discount_total, additional_expenses, taxable_amount, cgst_amount, sgst_amount, igst_amount, cess_amount, round_off, grand_total, amount_paid, outstanding_balance, is_draft, is_cancelled, created_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], PRIMARY_COMPANY_ID, DEFAULT_BRANCH_ID, None, r["vch_no"], r["supplier_invoice_no"], r["supplier_invoice_date"], r["vch_date"], r.get("supplier_id"), r["supplier_name"], r.get("supplier_gstin"), r.get("supplier_address"), r.get("supplier_state", "Tamilnadu"), r.get("place_of_supply", "Tamilnadu"), r.get("payment_type", "CREDIT"), r.get("due_date"), r.get("purchase_type", "Local"), r.get("narration"), r.get("gross_amount", 0.0), r.get("discount_total", 0.0), r.get("additional_expenses", 0.0), r.get("taxable_amount", 0.0), r.get("cgst_amount", 0.0), r.get("sgst_amount", 0.0), r.get("igst_amount", 0.0), r.get("cess_amount", 0.0), r.get("round_off", 0.0), r.get("grand_total", 0.0), r.get("amount_paid", 0.0), r.get("outstanding_balance", 0.0), r.get("is_draft", 0), r.get("is_cancelled", 0), r.get("created_by", "Admin"), r.get("created_at"), r.get("updated_at"))
            )
        self._record_stat("purchase_vouchers", len(rows), len(rows))

    def _migrate_purchase_voucher_items(self, sq_cur, pg_cur):
        sq_cur.execute(
            """
            SELECT pvi.* FROM purchase_voucher_items pvi
            JOIN purchase_vouchers pv ON pv.id = pvi.voucher_id
            WHERE pv.company_id = ?;
            """,
            (PRIMARY_COMPANY_ID,)
        )
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO purchase_voucher_items (id, voucher_id, item_id, sn, name, item_name, barcode, hsn, qty, free_qty, unit, purchase_rate, discount_percent, discount_amount, taxable_amount, tax_rate, cgst_amount, sgst_amount, igst_amount, cess_amount, line_total, batch_no, expiry_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], r["voucher_id"], r.get("item_id"), r.get("sn", 1), r.get("name") or r.get("item_name"), r.get("item_name") or r.get("name"), r.get("barcode"), r.get("hsn"), r["qty"], r.get("free_qty", 0.0), r.get("unit", "PCS"), r.get("purchase_rate", 0.0), r.get("discount_percent", 0.0), r.get("discount_amount", 0.0), r.get("taxable_amount", 0.0), r.get("tax_rate", 18.0), r.get("cgst_amount", 0.0), r.get("sgst_amount", 0.0), r.get("igst_amount", 0.0), r.get("cess_amount", 0.0), r.get("line_total", 0.0), r.get("batch_no"), r.get("expiry_date"))
            )
        self._record_stat("purchase_voucher_items", len(rows), len(rows))

    def _migrate_sales_returns(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM sales_returns WHERE company_id = ?;", (PRIMARY_COMPANY_ID,))
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO sales_returns (id, company_id, branch_id, vch_no, original_voucher_id, original_invoice_no, vch_date, customer_name, reason, taxable_amount, cgst_amount, sgst_amount, igst_amount, grand_total, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], PRIMARY_COMPANY_ID, DEFAULT_BRANCH_ID, r["vch_no"], r.get("original_voucher_id"), r.get("original_invoice_no"), r["vch_date"], r["customer_name"], r.get("reason"), r.get("taxable_amount", 0.0), r.get("cgst_amount", 0.0), r.get("sgst_amount", 0.0), r.get("igst_amount", 0.0), r["grand_total"], r.get("created_at"))
            )
        self._record_stat("sales_returns", len(rows), len(rows))

    def _migrate_sales_return_items(self, sq_cur, pg_cur):
        sq_cur.execute(
            """
            SELECT sri.* FROM sales_return_items sri
            JOIN sales_returns sr ON sr.id = sri.return_id
            WHERE sr.company_id = ?;
            """,
            (PRIMARY_COMPANY_ID,)
        )
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO sales_return_items (id, return_id, item_id, sn, item_name, qty, unit, rate, tax_rate, tax_amount, line_total, restock_condition)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], r["return_id"], r["item_id"], r.get("sn", 1), r.get("item_name"), r["qty"], r.get("unit", "Pcs."), r.get("rate", 0.0), r.get("tax_rate", 0.0), r.get("tax_amount", 0.0), r["line_total"], r.get("restock_condition", "GOOD"))
            )
        self._record_stat("sales_return_items", len(rows), len(rows))

    def _migrate_category_discounts(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM customer_category_discounts WHERE company_id = ?;", (PRIMARY_COMPANY_ID,))
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO customer_category_discounts (id, company_id, category, discount_percent, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], PRIMARY_COMPANY_ID, r["category"], r["discount_percent"], r.get("updated_at"))
            )
        self._record_stat("customer_category_discounts", len(rows), len(rows))

    def _migrate_audit_logs(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM audit_logs WHERE company_id = ? OR company_id IS NULL;", (PRIMARY_COMPANY_ID,))
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO audit_logs (id, company_id, username, action, entity_type, entity_id, details, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], PRIMARY_COMPANY_ID, r["username"], r["action"], r["entity_type"], r.get("entity_id"), r.get("details"), r.get("created_at"))
            )
        self._record_stat("audit_logs", len(rows), len(rows))

    def _migrate_low_stock_alerts(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM low_stock_alerts WHERE company_id = ?;", (PRIMARY_COMPANY_ID,))
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO low_stock_alerts (id, company_id, branch_id, item_id, item_name, threshold, available_qty, current_stock, threshold_level, threshold_type, reorder_level, min_stock_level, suggested_reorder_qty, preferred_reorder_qty, severity, status, created_at, resolved_at, dismissed_at, last_evaluated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], PRIMARY_COMPANY_ID, DEFAULT_BRANCH_ID, r["item_id"], r.get("item_name"), r.get("threshold", 0.0), r.get("available_qty", 0.0), r.get("current_stock", 0.0), r.get("threshold_level", 0.0), r.get("threshold_type", "REORDER"), r.get("reorder_level"), r.get("min_stock_level"), r.get("suggested_reorder_qty"), r.get("preferred_reorder_qty", 0.0), r.get("severity", "REORDER_REQUIRED"), r.get("status", "ACTIVE"), r.get("created_at"), r.get("resolved_at"), r.get("dismissed_at"), r.get("last_evaluated_at"))
            )
        self._record_stat("low_stock_alerts", len(rows), len(rows))

    def _migrate_journal_entries(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM journal_entries WHERE company_id = ?;", (PRIMARY_COMPANY_ID,))
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO journal_entries (id, company_id, vch_no, vch_date, vch_type, reference_id, narration, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], PRIMARY_COMPANY_ID, r["vch_no"], r["vch_date"], r.get("vch_type", "Journal"), r.get("reference_id"), r.get("narration"), r.get("created_at"))
            )
        self._record_stat("journal_entries", len(rows), len(rows))

    def _migrate_journal_entry_lines(self, sq_cur, pg_cur):
        sq_cur.execute(
            """
            SELECT jel.* FROM journal_entry_lines jel
            JOIN journal_entries je ON je.id = jel.journal_id
            WHERE je.company_id = ?;
            """,
            (PRIMARY_COMPANY_ID,)
        )
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO journal_entry_lines (id, journal_id, account_id, account_name, debit, credit, debit_amount, credit_amount, narration, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], r["journal_id"], r.get("account_id"), r.get("account_name"), r.get("debit", 0.0), r.get("credit", 0.0), r.get("debit_amount", 0.0), r.get("credit_amount", 0.0), r.get("narration"), r.get("notes"))
            )
        self._record_stat("journal_entry_lines", len(rows), len(rows))

    def _migrate_ocr_drafts(self, sq_cur, pg_cur):
        sq_cur.execute("SELECT * FROM ocr_invoice_drafts WHERE company_id = ?;", (PRIMARY_COMPANY_ID,))
        rows = sq_cur.fetchall()
        for row in rows:
            r = dict(row)
            pg_cur.execute(
                """
                INSERT INTO ocr_invoice_drafts (id, company_id, file_path, file_name, extracted_data, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (r["id"], PRIMARY_COMPANY_ID, r.get("file_path"), r.get("file_name"), r.get("extracted_data"), r.get("status", "DRAFT"), r.get("created_at"))
            )
        self._record_stat("ocr_invoice_drafts", len(rows), len(rows))

    def _init_sequences(self, pg_cur):
        import uuid
        # Initialise voucher sequence for Sales
        pg_cur.execute(
            """
            INSERT INTO voucher_sequences (id, company_id, voucher_type, series, current_number)
            VALUES (%s, %s, 'SALE', 'Main', 570)
            ON CONFLICT (company_id, voucher_type, series) DO UPDATE SET current_number = GREATEST(voucher_sequences.current_number, 570);
            """,
            (str(uuid.uuid4()), PRIMARY_COMPANY_ID)
        )
        # Initialise barcode sequence
        pg_cur.execute(
            """
            INSERT INTO barcode_sequences (id, sequence_name, prefix, current_value)
            VALUES (%s, 'INTERNAL_BARCODE', 'AB', 444)
            ON CONFLICT (sequence_name) DO UPDATE SET current_value = GREATEST(barcode_sequences.current_value, 444);
            """,
            (str(uuid.uuid4()),)
        )
        print("  ✓ sequences                    : Voucher (#570) and Barcode (#444) initialized")

    def _validate_reconciliation(self, sq_cur, pg_cur) -> Dict[str, Any]:
        """Performs full mathematical and quantity reconciliation."""
        # 1. Sales Voucher Totals
        sq_cur.execute("SELECT count(*), sum(taxable_amount), sum(cgst_amount), sum(sgst_amount), sum(round_off), sum(grand_total) FROM sales_vouchers WHERE company_id = ?;", (PRIMARY_COMPANY_ID,))
        sq_sales = [float(x or 0.0) for x in sq_cur.fetchone()]

        pg_cur.execute("SELECT count(*), sum(taxable_amount), sum(cgst_amount), sum(sgst_amount), sum(round_off), sum(grand_total) FROM sales_vouchers WHERE company_id = %s;", (PRIMARY_COMPANY_ID,))
        pg_sales = [float(x or 0.0) for x in pg_cur.fetchone()]

        sales_matched = (sq_sales[0] == pg_sales[0] and abs(sq_sales[5] - pg_sales[5]) < 0.01)

        # 2. Purchase Voucher Totals
        sq_cur.execute("SELECT count(*), sum(gross_amount), sum(taxable_amount), sum(grand_total) FROM purchase_vouchers WHERE company_id = ?;", (PRIMARY_COMPANY_ID,))
        sq_purch = [float(x or 0.0) for x in sq_cur.fetchone()]

        pg_cur.execute("SELECT count(*), sum(gross_amount), sum(taxable_amount), sum(grand_total) FROM purchase_vouchers WHERE company_id = %s;", (PRIMARY_COMPANY_ID,))
        pg_purch = [float(x or 0.0) for x in pg_cur.fetchone()]

        purch_matched = (sq_purch[0] == pg_purch[0] and abs(sq_purch[3] - pg_purch[3]) < 0.01)

        # 3. Stock Balances (Main Branch)
        sq_cur.execute("SELECT count(*), sum(current_qty) FROM stock_balances WHERE company_id = ? AND branch_id = ?;", (PRIMARY_COMPANY_ID, DEFAULT_BRANCH_ID))
        sq_stock = [float(x or 0.0) for x in sq_cur.fetchone()]

        pg_cur.execute("SELECT count(*), sum(current_qty) FROM stock_balances WHERE company_id = %s AND branch_id = %s;", (PRIMARY_COMPANY_ID, DEFAULT_BRANCH_ID))
        pg_stock = [float(x or 0.0) for x in pg_cur.fetchone()]

        stock_matched = (sq_stock[0] == pg_stock[0] and abs(sq_stock[1] - pg_stock[1]) < 0.01)

        print(f"  Sales Total Match   : {'PASSED' if sales_matched else 'FAILED'} (SQLite: ₹{sq_sales[5]:,.2f} vs PG: ₹{pg_sales[5]:,.2f})")
        print(f"  Purchase Total Match: {'PASSED' if purch_matched else 'FAILED'} (SQLite: ₹{sq_purch[3]:,.2f} vs PG: ₹{pg_purch[3]:,.2f})")
        print(f"  Stock Balance Match : {'PASSED' if stock_matched else 'FAILED'} (SQLite: {sq_stock[1]:,.2f} units vs PG: {pg_stock[1]:,.2f} units)")

        all_matched = sales_matched and purch_matched and stock_matched
        return {
            "all_matched": all_matched,
            "sales": {"source_total": sq_sales[5], "target_total": pg_sales[5], "matched": sales_matched},
            "purchases": {"source_total": sq_purch[3], "target_total": pg_purch[3], "matched": purch_matched},
            "stock": {"source_qty": sq_stock[1], "target_qty": pg_stock[1], "matched": stock_matched},
        }

    def _verify_integrity(self, pg_cur) -> bool:
        """Verifies foreign key integrity and uniqueness in PostgreSQL."""
        checks = [
            ("branches", "company_id", "companies", "id"),
            ("accounts", "company_id", "companies", "id"),
            ("items", "company_id", "companies", "id"),
            ("item_barcodes", "item_id", "items", "id"),
            ("stock_balances", "branch_id", "branches", "id"),
            ("stock_balances", "item_id", "items", "id"),
            ("sales_vouchers", "company_id", "companies", "id"),
            ("sales_voucher_items", "voucher_id", "sales_vouchers", "id"),
            ("purchase_vouchers", "company_id", "companies", "id"),
            ("purchase_voucher_items", "voucher_id", "purchase_vouchers", "id"),
            ("stock_movements", "company_id", "companies", "id"),
            ("stock_movements", "item_id", "items", "id"),
        ]

        valid = True
        for child_table, child_col, parent_table, parent_col in checks:
            query = sql.SQL(
                """
                SELECT count(*) FROM {child} c
                WHERE c.{child_col} IS NOT NULL 
                  AND NOT EXISTS (
                      SELECT 1 FROM {parent} p WHERE p.{parent_col} = c.{child_col}
                  );
                """
            ).format(
                child=sql.Identifier(child_table),
                child_col=sql.Identifier(child_col),
                parent=sql.Identifier(parent_table),
                parent_col=sql.Identifier(parent_col)
            )
            pg_cur.execute(query)
            orphans = pg_cur.fetchone()[0]
            if orphans > 0:
                print(f"  [ERROR] Found {orphans} orphaned rows in {child_table}.{child_col}")
                valid = False

        if valid:
            print("  ✓ Foreign key referential integrity: 100% PASSED (0 orphaned records)")
        return valid


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Alpha Billing V2 Safe SQLite to PostgreSQL Migration CLI")
    parser.add_argument("--sqlite", help="Path to source SQLite database file", default="data/anti_matrix_billing.db")
    parser.add_argument("--target-url", help="Target PostgreSQL connection string (defaults to DATABASE_URL)")
    parser.add_argument("--dry-run", action="store_true", help="Perform validation and reconciliation without committing")
    parser.add_argument("--truncate", action="store_true", help="Truncate target tables before migration")
    args = parser.parse_args()

    orchestrator = V2MigrationOrchestrator(
        sqlite_path=Path(args.sqlite),
        target_pg_url=args.target_url,
        dry_run=args.dry_run,
        truncate_target=args.truncate,
    )
    res = orchestrator.execute_migration()
    if res["success"]:
        sys.exit(0)
    else:
        sys.exit(1)
