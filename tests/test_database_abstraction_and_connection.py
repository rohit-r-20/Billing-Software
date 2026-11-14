"""
Comprehensive Automated Test Suite for Alpha Billing V2 Database Abstraction & Connection.
Validates:
1. Environment-driven configuration loading & credential masking.
2. SQLAlchemy 2.x Engine creation, connection pooling & disposal.
3. Session lifecycle, transaction commit, and transaction rollback.
4. Connection health checks & diagnostic reporting.
5. Graceful connection failure handling.
6. Alembic migration script discovery and revision validation.
7. Declarative model metadata compatibility.
8. Non-destructive guarantee: Historical SQLite database remains untouched.
"""

import os
import sqlite3
import pytest
from pathlib import Path
from sqlalchemy import text

from core.configuration import config, AppConfig
from db.database import DatabaseManager, db_manager
from db.models import Base


def test_database_configuration_loading():
    """Validates environment-driven database configuration and credential masking."""
    env = config.get_database_env()
    assert env in ("development", "testing", "production"), f"Unexpected environment: {env}"

    url = config.get_database_url()
    assert url is not None and len(url) > 0, "Database URL must not be empty"

    # Test URL masking
    test_raw_url = "postgresql+psycopg://myuser:SuperSecretPassword123@db.supabase.co:5432/mydb"
    masked = config.mask_database_url(test_raw_url)
    assert "SuperSecretPassword123" not in masked
    assert "myuser:****@db.supabase.co" in masked

    # Test pool config
    pool_cfg = config.get_pool_config()
    assert isinstance(pool_cfg["pool_size"], int)
    assert isinstance(pool_cfg["max_overflow"], int)
    assert isinstance(pool_cfg["pool_timeout"], int)
    assert isinstance(pool_cfg["pool_recycle"], int)
    assert pool_cfg["pool_pre_ping"] is True


def test_engine_creation_and_disposal():
    """Validates single engine creation, pooling, and safe connection disposal."""
    mgr = DatabaseManager()
    engine = mgr.engine
    assert engine is not None
    assert hasattr(engine, "connect")

    # Safe disposal test
    mgr.dispose()
    assert mgr._engine is None
    assert mgr._session_factory is None

    # Re-initialization on demand
    new_engine = mgr.engine
    assert new_engine is not None


def test_session_lifecycle_and_transaction_commit():
    """Validates session lifecycle and automatic commit on success."""
    mgr = DatabaseManager()
    with mgr.session_scope() as session:
        result = session.execute(text("SELECT 1 AS alive")).scalar()
        assert result == 1


def test_session_lifecycle_and_transaction_rollback():
    """Validates session rollback on exception within transactional scope."""
    mgr = DatabaseManager()
    with pytest.raises(RuntimeError):
        with mgr.session_scope() as session:
            session.execute(text("SELECT 1 AS alive"))
            # Trigger intentional exception
            raise RuntimeError("Intentional error to trigger rollback")


def test_connection_health_check():
    """Validates connection health check and diagnostic reporting."""
    mgr = DatabaseManager()
    health = mgr.check_health()
    assert isinstance(health, dict)
    assert "healthy" in health
    assert "latency_ms" in health
    assert "dialect" in health
    assert "url_masked" in health
    assert health["latency_ms"] >= 0.0

    # Ensure password is NOT leaked in the report
    assert "Alphabilling%40123" not in health["url_masked"]
    assert "SuperSecret" not in health["url_masked"]


def test_connection_failure_handling():
    """Validates that invalid connection strings report clean failure without crashing."""
    invalid_url = "postgresql+psycopg://nonexistent_user:dummy_password@127.0.0.1:59999/nonexistent_db"
    mgr = DatabaseManager(database_url=invalid_url)
    health = mgr.check_health()
    assert health["healthy"] is False
    assert "error" in health
    assert health["latency_ms"] >= 0.0


def test_alembic_migration_discovery():
    """Validates Alembic configuration and migration file discovery."""
    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory

    ini_path = config.BASE_DIR / "alembic.ini"
    assert ini_path.exists(), "alembic.ini must exist in project root"

    alembic_cfg = AlembicConfig(str(ini_path))
    script_dir = ScriptDirectory.from_config(alembic_cfg)
    revisions = list(script_dir.walk_revisions())
    assert len(revisions) >= 4, f"Expected at least 4 migration revisions, found {len(revisions)}"
    
    # Assert latest revision head is discovered
    head_rev = script_dir.get_current_head()
    assert head_rev == "63b87d829649"


def test_model_metadata_compatibility():
    """Validates that Base metadata declares all approved V2 operational tables."""
    tables = Base.metadata.tables.keys()
    required_tables = [
        "companies",
        "company_configs",
        "branches",
        "registers",
        "accounts",
        "suppliers",
        "items",
        "item_barcodes",
        "stock_balances",
        "stock_movements",
        "sales_vouchers",
        "sales_voucher_items",
        "purchase_vouchers",
        "purchase_voucher_items",
        "payments",
        "roles",
        "users",
        "user_permissions",
        "voucher_sequences",
        "audit_logs",
    ]
    for table in required_tables:
        assert table in tables, f"Model table '{table}' missing from SQLAlchemy Base metadata"


def test_sqlite_untouched_guarantee():
    """Validates that the historical SQLite database remains 100% untouched and uncorrupted."""
    sqlite_file = config.DATABASE_PATH
    assert sqlite_file.exists(), f"Historical SQLite file must exist at {sqlite_file}"

    with sqlite3.connect(f"file:{sqlite_file}?mode=ro", uri=True) as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        assert cur.fetchone()[0] == "ok", "SQLite database must pass integrity check"

        # Verify operational row counts are strictly intact
        cur.execute("SELECT count(*) FROM sales_vouchers;")
        assert cur.fetchone()[0] == 570, "Sales vouchers count in SQLite must remain exactly 570"
        cur.execute("SELECT count(*) FROM items;")
        assert cur.fetchone()[0] == 805, "Items count in SQLite must remain exactly 805"
        cur.execute("SELECT count(*) FROM accounts;")
        assert cur.fetchone()[0] == 364, "Accounts count in SQLite must remain exactly 364"
