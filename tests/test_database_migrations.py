"""Unit tests for database migrations and backup mechanisms."""
import pytest
import sqlite3
import tempfile
from pathlib import Path
from db.database import DatabaseManager


def test_database_initialization_and_migration(tmp_path):
    test_db = tmp_path / "test.db"
    manager = DatabaseManager(test_db)
    
    # Run migrations
    applied = manager.run_migrations()
    assert "001_initial_schema.sql" in applied
    
    # Run again - must be idempotent (no new migrations applied)
    second_applied = manager.run_migrations()
    assert len(second_applied) == 0
    
    # Verify tables exist
    with manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "companies" in tables
        assert "accounts" in tables
        assert "items" in tables
        assert "item_barcodes" in tables
        assert "stock_balances" in tables
        assert "stock_movements" in tables
        assert "sales_vouchers" in tables
        assert "sales_voucher_items" in tables
        assert "payments" in tables
        assert "schema_migrations" in tables


def test_backup_and_restore(tmp_path):
    test_db = tmp_path / "live.db"
    manager = DatabaseManager(test_db)
    manager.run_migrations()
    
    # Insert test record
    with manager.get_connection() as conn:
        conn.execute(
            "INSERT INTO companies (id, code, name, fin_year) VALUES ('C1', 'COMP0001', 'TEST COMPANY', '2026-27');"
        )
        conn.commit()
        
    backup_dir = tmp_path / "backups"
    backup_file = manager.backup_database(backup_dir)
    assert backup_file.exists()
    assert manager.verify_database_integrity(backup_file) is True
    
    # Modify live record
    with manager.get_connection() as conn:
        conn.execute("UPDATE companies SET name = 'MODIFIED NAME' WHERE id = 'C1';")
        conn.commit()
        
    # Restore from backup
    manager.restore_database(backup_file)
    
    with manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM companies WHERE id = 'C1';")
        name = cursor.fetchone()[0]
        assert name == "TEST COMPANY"
