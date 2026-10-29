"""
Database Management Layer for Anti Matrix Billing.
Handles SQLite connections, PRAGMAs, migrations, transactions, and backups.
"""
import sqlite3
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from core.configuration import config
from core.logging_config import logger


class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or config.DATABASE_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_connection_settings()

    def get_connection(self) -> sqlite3.Connection:
        """Create and return a configured SQLite connection."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = sqlite3.Row
        # Enforce foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON;")
        # Enable write-ahead logging for concurrency & durability
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_connection_settings(self):
        with self.get_connection() as conn:
            pass

    def run_migrations(self, migrations_dir: Optional[Path] = None) -> List[str]:
        """Apply all pending SQL migrations in sequential order."""
        mig_dir = migrations_dir or (Path(__file__).resolve().parent / "migrations")
        if not mig_dir.exists():
            return []

        applied = []
        with self.get_connection() as conn:
            # Ensure migration tracking table exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cursor = conn.cursor()
            cursor.execute("SELECT version FROM schema_migrations ORDER BY version;")
            applied_versions = {row["version"] for row in cursor.fetchall()}

            sql_files = sorted(mig_dir.glob("*.sql"))
            for sql_file in sql_files:
                # Expected format: 001_initial_schema.sql
                parts = sql_file.name.split("_", 1)
                try:
                    version = int(parts[0])
                except ValueError:
                    continue

                if version not in applied_versions:
                    logger.info(f"Applying migration {sql_file.name} (v{version})...")
                    script = sql_file.read_text(encoding="utf-8")
                    conn.executescript(script)
                    conn.execute(
                        "INSERT INTO schema_migrations (version, name) VALUES (?, ?);",
                        (version, sql_file.name)
                    )
                    applied.append(sql_file.name)
                    logger.info(f"Migration {sql_file.name} applied successfully.")

        return applied

    def backup_database(self, destination_dir: Optional[Path] = None) -> Path:
        """
        Creates an online, atomic backup using the SQLite backup API.
        Never blindly copies an active file to avoid partial write corruption.
        """
        dest_dir = destination_dir or config.BACKUP_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = dest_dir / f"backup_anti_matrix_{timestamp}.db"

        with self.get_connection() as src_conn:
            dest_conn = sqlite3.connect(str(backup_file))
            try:
                src_conn.backup(dest_conn)
                logger.info(f"Consistent database backup created at {backup_file}")
            finally:
                dest_conn.close()

        # Validate that the backup database is readable
        self.verify_database_integrity(backup_file)
        return backup_file

    def restore_database(self, backup_file_path: Path) -> bool:
        """
        Restores database from a verified backup file.
        Safely creates a pre-restore safety copy first.
        """
        backup_path = Path(backup_file_path)
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        # 1. Verify backup file integrity before replacing live data
        self.verify_database_integrity(backup_path)

        # 2. Take a pre-restore safety snapshot of the live database
        if self.db_path.exists():
            safety_copy = self.backup_database(config.BACKUP_DIR / "pre_restore_safety")
            logger.info(f"Pre-restore safety snapshot saved to {safety_copy}")

        # 3. Restore using online backup API to ensure safety
        dest_conn = self.get_connection()
        src_conn = sqlite3.connect(str(backup_path))
        try:
            src_conn.backup(dest_conn)
            logger.info(f"Database successfully restored from {backup_path}")
            return True
        finally:
            src_conn.close()
            dest_conn.close()

    @staticmethod
    def verify_database_integrity(db_file: Path) -> bool:
        """Executes PRAGMA integrity_check to verify database validity."""
        if not db_file.exists():
            raise FileNotFoundError(f"Database file does not exist: {db_file}")

        conn = sqlite3.connect(str(db_file))
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()[0]
            if result != "ok":
                raise ValueError(f"Integrity check failed for {db_file}: {result}")
            return True
        finally:
            conn.close()


db_manager = DatabaseManager()

