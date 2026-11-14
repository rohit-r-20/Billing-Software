"""
Test Suite: Traditional Billing Database Isolation Verification.
Proves that Traditional Billing operates independently of Fast Billing
and never reads, writes, or modifies the Fast Billing database (data/anti_matrix_billing.db).
"""

import os
import hashlib
from pathlib import Path
import pytest
from sqlalchemy import text

from db.traditional_database import (
    TraditionalDatabaseManager,
    TraditionalConfigurationError,
    validate_traditional_database_target,
)
from core.configuration import config


def _calculate_file_sha256(filepath: Path) -> str:
    """Calculates SHA256 checksum of a file if it exists."""
    if not filepath.exists():
        return ""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def test_validation_guard_rejects_fast_billing_database():
    """Verify that targeting Fast Billing database directly or indirectly raises an error."""
    fast_db_str = "data/anti_matrix_billing.db"
    with pytest.raises(TraditionalConfigurationError):
        validate_traditional_database_target(fast_db_str)

    with pytest.raises(TraditionalConfigurationError):
        validate_traditional_database_target(f"sqlite:///{fast_db_str}")

    with pytest.raises(TraditionalConfigurationError):
        validate_traditional_database_target(str(config.DATABASE_PATH))

    with pytest.raises(TraditionalConfigurationError):
        TraditionalDatabaseManager(database_url=f"sqlite:///{fast_db_str}")


def test_traditional_db_does_not_modify_fast_billing_db(tmp_path):
    """
    Ensure Traditional Billing operations in an isolated database do not touch
    the Fast Billing database file in any way.
    """
    fast_db_path = Path(config.DATABASE_PATH).resolve()
    
    # 1. Take snapshot of Fast Billing DB state (if it exists)
    initial_exists = fast_db_path.exists()
    initial_sha = _calculate_file_sha256(fast_db_path) if initial_exists else None
    initial_mtime = fast_db_path.stat().st_mtime if initial_exists else None

    # 2. Perform operations in Traditional DB
    trad_db_path = tmp_path / "test_isolated_traditional.db"
    trad_mgr = TraditionalDatabaseManager(database_url=f"sqlite:///{trad_db_path}")

    with trad_mgr.session_scope() as session:
        session.execute(text("CREATE TABLE test_isolation (id INTEGER PRIMARY KEY, msg TEXT);"))
        session.execute(text("INSERT INTO test_isolation (msg) VALUES ('traditional_payload');"))

    with trad_mgr.read_session_scope() as rsession:
        rows = rsession.execute(text("SELECT msg FROM test_isolation;")).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "traditional_payload"

    trad_mgr.close()

    # 3. Assert Fast Billing DB remains unchanged
    if initial_exists:
        assert fast_db_path.exists()
        current_sha = _calculate_file_sha256(fast_db_path)
        current_mtime = fast_db_path.stat().st_mtime
        assert current_sha == initial_sha, "Fast Billing database file hash was modified!"
        assert current_mtime == initial_mtime, "Fast Billing database file mtime changed!"
    else:
        assert not fast_db_path.exists(), "Fast Billing database was unexpectedly created!"


def test_sqlite_engine_pragmas(tmp_path):
    """Verify WAL mode and pragmas on write and read engines."""
    trad_db_path = tmp_path / "test_pragmas.db"
    trad_mgr = TraditionalDatabaseManager(database_url=f"sqlite:///{trad_db_path}")

    # Write engine check
    with trad_mgr.get_write_connection() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode;")).scalar()
        assert str(journal_mode).lower() == "wal"
        foreign_keys = conn.execute(text("PRAGMA foreign_keys;")).scalar()
        assert foreign_keys == 1

    # Read engine check
    with trad_mgr.get_connection() as rconn:
        query_only = rconn.execute(text("PRAGMA query_only;")).scalar()
        assert query_only == 1
        foreign_keys = rconn.execute(text("PRAGMA foreign_keys;")).scalar()
        assert foreign_keys == 1

    trad_mgr.close()
