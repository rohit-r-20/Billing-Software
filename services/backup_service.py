"""
Backup & Restore Service for Anti Matrix Billing ERP.
Supports local automated/manual backups, external drive mirroring,
retention cleanup, and integrity verification.
"""
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from core.configuration import config
from core.logging_config import logger
from db.database import db_manager, DatabaseManager


class BackupService:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or db_manager

    def perform_backup(
        self,
        local_dest: Optional[Path] = None,
        external_dest: Optional[Path] = None,
        retention_count: int = 15
    ) -> Dict[str, Any]:
        """
        Creates an atomic backup in the local destination, then attempts mirroring
        to the external drive if specified.
        Returns a status dictionary detailing both destinations.
        """
        local_dir = local_dest or config.BACKUP_DIR
        local_dir.mkdir(parents=True, exist_ok=True)

        result = {
            "success": False,
            "timestamp": datetime.now().isoformat(),
            "local_backup_file": None,
            "external_backup_file": None,
            "external_status": "NOT_CONFIGURED",
            "message": ""
        }

        # 1. Create atomic local backup
        try:
            local_backup = self.db.backup_database(local_dir)
            result["local_backup_file"] = str(local_backup)
            result["success"] = True
            logger.info(f"Local backup created: {local_backup}")
        except Exception as e:
            result["message"] = f"Local backup failed: {str(e)}"
            logger.error(result["message"])
            return result

        # 2. Mirror to external destination if configured
        if external_dest:
            ext_path = Path(external_dest)
            try:
                if not ext_path.exists() or not ext_path.is_dir():
                    result["external_status"] = "DRIVE_UNAVAILABLE"
                    result["message"] = f"External backup drive not mounted or unreachable: {ext_path}"
                    logger.warning(result["message"])
                else:
                    ext_target = ext_path / local_backup.name
                    shutil.copy2(local_backup, ext_target)
                    # Verify external copy integrity
                    self.db.verify_database_integrity(ext_target)
                    result["external_backup_file"] = str(ext_target)
                    result["external_status"] = "SUCCESS"
                    logger.info(f"External backup mirrored and verified: {ext_target}")
            except Exception as e:
                result["external_status"] = "MIRROR_FAILED"
                result["message"] = f"External mirror failed: {str(e)}"
                logger.error(result["message"])

        # 3. Apply retention cleanup on local backups
        if retention_count > 0:
            self._prune_old_backups(local_dir, retention_count)

        if not result["message"]:
            result["message"] = "Backup completed successfully."
        return result

    def _prune_old_backups(self, backup_dir: Path, max_keep: int):
        """Remove oldest backup files exceeding retention limit."""
        backups = sorted(backup_dir.glob("backup_anti_matrix_*.db"), key=lambda f: f.stat().st_mtime)
        while len(backups) > max_keep:
            oldest = backups.pop(0)
            try:
                oldest.unlink()
                logger.info(f"Pruned old backup: {oldest.name}")
            except Exception as e:
                logger.warning(f"Could not delete old backup {oldest}: {e}")

    def list_backups(self, backup_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
        """List available local backups with sizes and creation dates."""
        b_dir = backup_dir or config.BACKUP_DIR
        if not b_dir.exists():
            return []

        file_list = []
        for f in sorted(b_dir.glob("backup_anti_matrix_*.db"), key=lambda x: x.stat().st_mtime, reverse=True):
            stat = f.stat()
            file_list.append({
                "filename": f.name,
                "filepath": str(f),
                "size_kb": round(stat.st_size / 1024, 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%d-%m-%Y %H:%M:%S")
            })
        return file_list

    def restore_from_file(self, backup_filepath: str) -> Dict[str, Any]:
        """Restore database from a specified backup file after verifying integrity."""
        path = Path(backup_filepath)
        try:
            self.db.restore_database(path)
            return {"success": True, "message": f"Successfully restored from {path.name}"}
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return {"success": False, "message": f"Restore failed: {str(e)}"}


backup_service = BackupService()

