"""Unit tests for Backup and Restore Service."""
import pytest
from pathlib import Path
from db.database import DatabaseManager
from services.backup_service import BackupService


@pytest.fixture
def backup_test_env(tmp_path):
    db_file = tmp_path / "live.db"
    manager = DatabaseManager(db_file)
    manager.run_migrations()
    
    with manager.get_connection() as conn:
        conn.execute("INSERT INTO companies (id, code, name, fin_year) VALUES ('C1', 'COMP0001', 'INITIAL CO', '2026-27');")
        conn.commit()
        
    return manager, tmp_path


def test_backup_and_missing_external_drive(backup_test_env):
    manager, tmp_path = backup_test_env
    service = BackupService(manager)
    
    local_dir = tmp_path / "local_backups"
    missing_external = tmp_path / "non_existent_usb"
    
    res = service.perform_backup(local_dest=local_dir, external_dest=missing_external)
    assert res["success"] is True
    assert res["local_backup_file"] is not None
    assert res["external_status"] == "DRIVE_UNAVAILABLE"
    assert "unreachable" in res["message"]


def test_backup_and_successful_mirror(backup_test_env):
    manager, tmp_path = backup_test_env
    service = BackupService(manager)
    
    local_dir = tmp_path / "local_backups"
    mounted_usb = tmp_path / "usb_drive"
    mounted_usb.mkdir()
    
    res = service.perform_backup(local_dest=local_dir, external_dest=mounted_usb)
    assert res["success"] is True
    assert res["external_status"] == "SUCCESS"
    assert Path(res["external_backup_file"]).exists()


def test_restore_workflow(backup_test_env):
    manager, tmp_path = backup_test_env
    service = BackupService(manager)
    
    local_dir = tmp_path / "local_backups"
    res = service.perform_backup(local_dest=local_dir)
    backup_file = res["local_backup_file"]
    
    # Mutate live record
    with manager.get_connection() as conn:
        conn.execute("UPDATE companies SET name = 'CORRUPTED';")
        conn.commit()
        
    # Restore
    restore_res = service.restore_from_file(backup_file)
    assert restore_res["success"] is True
    
    # Verify original data restored
    with manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM companies WHERE id = 'C1';")
        assert cursor.fetchone()[0] == "INITIAL CO"
