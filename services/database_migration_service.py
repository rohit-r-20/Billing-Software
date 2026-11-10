"""
Database Migration Service for Alpha Billing ERP.
Migrates existing SQLite business data into PostgreSQL (Supabase / Self-Managed)
safely, non-destructively, preserving referential integrity and verifying records.
"""

import os
import sys
import time
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

import psycopg
from psycopg import sql

from core.configuration import config
from core.logging_config import logger
from db.database import db_manager


# Topological order for table insertion (parents before children)
TOPOLOGICAL_TABLE_ORDER = [
    # 1. Core Tenants & Hierarchy
    "companies",
    "branches",
    "roles",
    "users",
    "user_permissions",
    "registers",
    "company_configs",
    "customer_category_discounts",
    "daily_discount_configs",
    "godowns",

    # 2. Master Entities
    "suppliers",
    "accounts",
    "items",
    "item_barcodes",
    "item_branch_stock_configs",
    "stock_balances",
    "voucher_sequences",

    # 3. Transactions & Lines
    "sales_vouchers",
    "sales_voucher_items",
    "payments",
    "sales_returns",
    "sales_return_items",
    "purchase_vouchers",
    "purchase_voucher_items",
    "purchase_returns",
    "purchase_return_items",

    # 4. Movements, Alerts, Adjustments & Journals
    "stock_movements",
    "low_stock_alerts",
    "audit_logs",
    "ocr_invoice_drafts",
    "stock_adjustments",
    "stock_adjustment_items",
    "stock_transfers",
    "stock_transfer_items",
    "stock_batches",
    "journal_entries",
    "journal_entry_lines",
    "unit_conversions",
]


@dataclass
class TableMigrationStats:
    table_name: str
    source_count: int = 0
    target_count: int = 0
    status: str = "PENDING"
    error: Optional[str] = None


@dataclass
class MigrationResult:
    success: bool
    source_db: str
    target_db: str
    total_tables: int = 0
    total_rows: int = 0
    table_stats: Dict[str, TableMigrationStats] = field(default_factory=dict)
    referential_integrity_valid: bool = False
    uniqueness_valid: bool = False
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "source_db": self.source_db,
            "target_db": self.target_db,
            "total_tables": self.total_tables,
            "total_rows": self.total_rows,
            "duration_seconds": round(self.duration_seconds, 3),
            "referential_integrity_valid": self.referential_integrity_valid,
            "uniqueness_valid": self.uniqueness_valid,
            "errors": self.errors,
            "tables": {
                name: {
                    "source": s.source_count,
                    "target": s.target_count,
                    "status": s.status,
                    "error": s.error
                }
                for name, s in self.table_stats.items()
            }
        }


class DatabaseMigrationService:
    """
    Orchestrates the safe, non-destructive migration of business data from SQLite
    to PostgreSQL (Supabase / Self-Managed).
    """

    def __init__(self, sqlite_path: Optional[Path] = None, postgres_url: Optional[str] = None):
        self.sqlite_path = Path(sqlite_path or config.DATABASE_PATH)
        self.postgres_url = (postgres_url or config.get_database_url()).strip()
        # Clean postgres URL for psycopg
        if self.postgres_url.startswith("postgresql+psycopg://"):
            self._pg_conn_str = self.postgres_url.replace("postgresql+psycopg://", "postgresql://", 1)
        elif self.postgres_url.startswith("postgresql+psycopg2://"):
            self._pg_conn_str = self.postgres_url.replace("postgresql+psycopg2://", "postgresql://", 1)
        else:
            self._pg_conn_str = self.postgres_url

    def migrate(self, truncate_target: bool = False, batch_size: int = 500) -> MigrationResult:
        """
        Executes end-to-end data migration from SQLite to PostgreSQL.
        Preserves SQLite data completely untouched.
        """
        start_time = time.time()
        result = MigrationResult(
            success=False,
            source_db=str(self.sqlite_path),
            target_db=self._mask_url(self._pg_conn_str)
        )

        # 1. Verify SQLite database existence
        if not self.sqlite_path.exists():
            err = f"Source SQLite database not found at {self.sqlite_path}"
            logger.error(err)
            result.errors.append(err)
            return result

        # 2. Verify target PostgreSQL connectivity
        try:
            with psycopg.connect(self._pg_conn_str, connect_timeout=10) as test_conn:
                with test_conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    pg_version = cur.fetchone()[0]
                    logger.info(f"Connected to target PostgreSQL: {pg_version}")
        except Exception as e:
            err = f"Failed to connect to target PostgreSQL: {e}"
            logger.error(err)
            result.errors.append(err)
            return result

        # 3. Ensure Alembic migrations are executed on PostgreSQL
        try:
            logger.info("Ensuring target PostgreSQL schema is up-to-date with Alembic...")
            db_manager.run_alembic_migrations()
        except Exception as e:
            err = f"Alembic schema migration failed: {e}"
            logger.error(err)
            result.errors.append(err)
            return result

        # 4. Open read-only SQLite connection and PostgreSQL transaction
        try:
            sqlite_conn = sqlite3.connect(f"file:{self.sqlite_path}?mode=ro", uri=True)
            sqlite_conn.row_factory = sqlite3.Row
            sqlite_cur = sqlite_conn.cursor()
        except Exception as e:
            # Fallback if URI mode is not supported by OS SQLite
            sqlite_conn = sqlite3.connect(str(self.sqlite_path))
            sqlite_conn.row_factory = sqlite3.Row
            sqlite_cur = sqlite_conn.cursor()

        pg_conn = None
        try:
            pg_conn = psycopg.connect(self._pg_conn_str)
            pg_conn.autocommit = False
            pg_cur = pg_conn.cursor()

            # Optional: Truncate target tables in reverse topological order if requested
            if truncate_target:
                logger.info("Truncating target PostgreSQL tables in reverse dependency order...")
                for table in reversed(TOPOLOGICAL_TABLE_ORDER):
                    try:
                        pg_cur.execute(sql.SQL("TRUNCATE TABLE {} CASCADE;").format(sql.Identifier(table)))
                    except Exception as e:
                        # Table might not exist yet or ignore
                        pg_conn.rollback()

            total_migrated_rows = 0

            # 5. Migrate each table in topological order
            for table in TOPOLOGICAL_TABLE_ORDER:
                stats = TableMigrationStats(table_name=table)
                result.table_stats[table] = stats

                # Check if table exists in SQLite
                sqlite_cur.execute(
                    "SELECT count(*) FROM sqlite_master WHERE type='table' AND name = ?;",
                    (table,)
                )
                if sqlite_cur.fetchone()[0] == 0:
                    stats.status = "SKIPPED_NOT_IN_SOURCE"
                    continue

                # Get SQLite columns
                sqlite_cur.execute(f'PRAGMA table_info("{table}");')
                sqlite_cols = [row[1] for row in sqlite_cur.fetchall()]

                # Get PostgreSQL columns
                pg_cur.execute(
                    """
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = %s;
                    """,
                    (table,)
                )
                pg_cols = set(row[0] for row in pg_cur.fetchall())

                if not pg_cols:
                    stats.status = "SKIPPED_NOT_IN_TARGET"
                    continue

                # Intersection of columns present in both SQLite and PostgreSQL
                common_cols = [c for c in sqlite_cols if c in pg_cols]
                if not common_cols:
                    stats.status = "SKIPPED_NO_COMMON_COLS"
                    continue

                # Count rows in SQLite
                sqlite_cur.execute(f'SELECT count(*) FROM "{table}";')
                stats.source_count = sqlite_cur.fetchone()[0]

                if stats.source_count == 0:
                    stats.status = "EMPTY"
                    continue

                # Read from SQLite and insert into PostgreSQL
                col_names_str = ", ".join([f'"{c}"' for c in common_cols])
                sqlite_query = f'SELECT {col_names_str} FROM "{table}";'
                sqlite_cur.execute(sqlite_query)

                insert_sql = sql.SQL(
                    "INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING;"
                ).format(
                    table=sql.Identifier(table),
                    cols=sql.SQL(", ").join([sql.Identifier(c) for c in common_cols]),
                    placeholders=sql.SQL(", ").join([sql.Placeholder() for _ in common_cols])
                )

                migrated_table_rows = 0
                while True:
                    rows = sqlite_cur.fetchmany(batch_size)
                    if not rows:
                        break

                    data_batch = [tuple(r) for r in rows]
                    pg_cur.executemany(insert_sql, data_batch)
                    migrated_table_rows += len(data_batch)

                total_migrated_rows += migrated_table_rows
                stats.target_count = migrated_table_rows
                stats.status = "MIGRATED"
                logger.info(f"Table '{table}': Migrated {migrated_table_rows} rows from SQLite to PostgreSQL.")

            # Commit the PostgreSQL transaction
            pg_conn.commit()
            logger.info("PostgreSQL migration transaction committed successfully.")

            # 6. Verification & Validation Step
            logger.info("Running post-migration verification checks...")
            ref_valid = self._verify_referential_integrity(pg_cur)
            uniq_valid = self._verify_uniqueness_constraints(pg_cur)
            row_count_valid = self._verify_table_row_counts(sqlite_cur, pg_cur, result.table_stats)

            result.referential_integrity_valid = ref_valid
            result.uniqueness_valid = uniq_valid
            result.total_tables = len([s for s in result.table_stats.values() if s.status == "MIGRATED"])
            result.total_rows = total_migrated_rows
            result.duration_seconds = time.time() - start_time

            if ref_valid and uniq_valid and row_count_valid:
                result.success = True
                logger.info("Migration completed and fully validated successfully!")
            else:
                result.success = False
                if not ref_valid:
                    result.errors.append("Referential integrity check failed.")
                if not uniq_valid:
                    result.errors.append("Uniqueness constraints verification failed.")
                if not row_count_valid:
                    result.errors.append("Row count validation between SQLite and PostgreSQL failed.")

        except Exception as e:
            if pg_conn:
                pg_conn.rollback()
            err = f"Migration failed with transaction rollback: {e}"
            logger.exception(err)
            result.errors.append(err)
            result.success = False
        finally:
            if sqlite_conn:
                sqlite_conn.close()
            if pg_conn:
                pg_conn.close()

        result.duration_seconds = time.time() - start_time
        return result

    def _verify_table_row_counts(
        self,
        sqlite_cur: sqlite3.Cursor,
        pg_cur: psycopg.Cursor,
        table_stats: Dict[str, TableMigrationStats]
    ) -> bool:
        """Validates that PostgreSQL row counts match or exceed SQLite source counts."""
        all_matched = True
        for table, stats in table_stats.items():
            if stats.source_count == 0:
                continue

            pg_cur.execute(sql.SQL("SELECT count(*) FROM {};").format(sql.Identifier(table)))
            pg_cnt = pg_cur.fetchone()[0]
            stats.target_count = pg_cnt

            if pg_cnt < stats.source_count:
                logger.warning(
                    f"Row count mismatch in table '{table}': SQLite has {stats.source_count}, PostgreSQL has {pg_cnt}"
                )
                all_matched = False
            else:
                logger.debug(f"Row count verified for '{table}': {pg_cnt}/{stats.source_count}")

        return all_matched

    def _verify_referential_integrity(self, pg_cur: psycopg.Cursor) -> bool:
        """Validates that foreign keys point to valid existing parent rows."""
        checks = [
            ("branches", "company_id", "companies", "id"),
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
                logger.error(f"Referential integrity failure: {orphans} orphaned records in {child_table}.{child_col}")
                valid = False

        return valid

    def _verify_uniqueness_constraints(self, pg_cur: psycopg.Cursor) -> bool:
        """Validates uniqueness of barcodes and voucher numbers within tenant."""
        valid = True

        # 1. Barcode uniqueness per company
        pg_cur.execute(
            """
            SELECT company_id, barcode, count(*) 
            FROM item_barcodes 
            GROUP BY company_id, barcode 
            HAVING count(*) > 1;
            """
        )
        duplicate_barcodes = pg_cur.fetchall()
        if duplicate_barcodes:
            logger.error(f"Duplicate barcodes found: {duplicate_barcodes}")
            valid = False

        # 2. Sales Voucher number uniqueness per company
        pg_cur.execute(
            """
            SELECT company_id, vch_no, count(*) 
            FROM sales_vouchers 
            GROUP BY company_id, vch_no 
            HAVING count(*) > 1;
            """
        )
        duplicate_vouchers = pg_cur.fetchall()
        if duplicate_vouchers:
            logger.error(f"Duplicate sales vouchers found: {duplicate_vouchers}")
            valid = False

        return valid

    @staticmethod
    def _mask_url(url: str) -> str:
        """Masks password credentials in database connection string for logs/reports."""
        import re
        return re.sub(r":([^@/]+)@", ":****@", url)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Alpha Billing SQLite to PostgreSQL Migration CLI")
    parser.add_argument("--sqlite", help="Path to source SQLite database file")
    parser.add_argument("--pg", help="Target PostgreSQL connection string")
    parser.add_argument("--truncate", action="store_true", help="Truncate target tables before migration")
    args = parser.parse_args()

    service = DatabaseMigrationService(sqlite_path=args.sqlite, postgres_url=args.pg)
    print(f"Starting migration from {service.sqlite_path} to {service._mask_url(service._pg_conn_str)}...")
    res = service.migrate(truncate_target=args.truncate)

    if res.success:
        print(f"\n[SUCCESS] Migration completed in {res.duration_seconds:.2f}s!")
        print(f"Total tables migrated: {res.total_tables}")
        print(f"Total rows migrated: {res.total_rows}")
        print(f"Referential integrity: {'PASSED' if res.referential_integrity_valid else 'FAILED'}")
        print(f"Uniqueness constraints: {'PASSED' if res.uniqueness_valid else 'FAILED'}")
        sys.exit(0)
    else:
        print(f"\n[FAILED] Migration encountered errors:")
        for err in res.errors:
            print(f"  - {err}")
        sys.exit(1)
