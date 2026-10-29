"""
Company and Tenant Service for Anti Matrix Billing ERP.
Manages multi-tenant companies, branches, authentication, and configurations.
"""
import uuid
from typing import Dict, Any, List, Optional
from db.database import db_manager, DatabaseManager
from core.security import hash_password, verify_password
from core.logging_config import logger


class CompanyService:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or db_manager

    def list_companies(self) -> List[Dict[str, Any]]:
        """List all registered companies."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, code, name, fin_year as finYear, gstin as taxNo, state, username
                FROM companies
                ORDER BY code ASC;
            """)
            return [dict(r) for r in cursor.fetchall()]

    def authenticate(self, code: str, password: str) -> Optional[Dict[str, Any]]:
        """Verify password for the selected company."""
        code_str = code.strip().upper()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM companies WHERE UPPER(code) = ?;", (code_str,))
            row = cursor.fetchone()
            if not row:
                return None
            comp = dict(row)
            stored_hash = comp.get("password_hash") or ""
            if verify_password(stored_hash, password):
                return {
                    "id": comp["id"],
                    "code": comp["code"],
                    "name": comp["name"],
                    "finYear": comp["fin_year"],
                    "taxNo": comp["gstin"],
                    "state": comp["state"],
                    "username": comp["username"]
                }
            return None

    def create_company(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new company with default branch, register, and configuration."""
        name = data.get("name", "").strip().upper()
        if not name:
            raise ValueError("Company name is required.")

        code = data.get("code", "").strip().upper()
        if not code:
            code = self.generate_next_code()

        fin_year = data.get("finYear", "2026-2027 (1 Yr)").strip()
        gstin = data.get("taxNo", "").strip().upper()
        state = data.get("state", "Tamilnadu").strip()
        username = data.get("username", "A").strip()
        pwd = data.get("password", "")
        pwd_hash = hash_password(pwd)

        comp_id = str(uuid.uuid4())
        branch_id = str(uuid.uuid4())
        reg_id = str(uuid.uuid4())

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO companies (id, code, name, fin_year, gstin, state, username, password_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (comp_id, code, name, fin_year, gstin, state, username, pwd_hash))

            # Default Branch & Register
            cursor.execute("""
                INSERT INTO branches (id, company_id, code, name, is_default)
                VALUES (?, ?, 'BR01', 'Main Branch', 1);
            """, (branch_id, comp_id))

            cursor.execute("""
                INSERT INTO registers (id, branch_id, code, name)
                VALUES (?, ?, 'REG01', 'Register 01');
            """, (reg_id, branch_id))

            # Default Configuration
            cursor.execute("""
                INSERT INTO company_configs (company_id, vch_start, vch_digits, vch_prefix, default_tax, auto_round)
                VALUES (?, 1, 3, '', '18', 'Y');
            """, (comp_id,))

            conn.commit()

        logger.info(f"Company {name} ({code}) created successfully.")
        return {
            "id": comp_id,
            "code": code,
            "name": name,
            "finYear": fin_year,
            "taxNo": gstin,
            "state": state,
            "username": username
        }

    def generate_next_code(self) -> str:
        """Generates next available company code: COMP0001, COMP0002..."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT code FROM companies;")
            codes = [r[0] for r in cursor.fetchall()]

        max_num = 0
        for c in codes:
            num_part = "".join(ch for ch in c if ch.isdigit())
            if num_part:
                try:
                    val = int(num_part)
                    if val > max_num:
                        max_num = val
                except ValueError:
                    pass
        return f"COMP{str(max_num + 1).zfill(4)}"

    def get_config(self, company_id_or_code: str) -> Dict[str, Any]:
        """Fetch voucher configuration for company."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cc.* FROM company_configs cc
                JOIN companies c ON c.id = cc.company_id
                WHERE cc.company_id = ? OR c.code = ?;
            """, (company_id_or_code, company_id_or_code))
            row = cursor.fetchone()
            if row:
                return {
                    "vchStart": row["vch_start"],
                    "vchDigits": row["vch_digits"],
                    "vchPrefix": row["vch_prefix"],
                    "defaultTax": row["default_tax"],
                    "autoRound": row["auto_round"],
                    "receiptWidth": row["receipt_width"]
                }
            return {
                "vchStart": 1,
                "vchDigits": 3,
                "vchPrefix": "",
                "defaultTax": "18",
                "autoRound": "Y",
                "receiptWidth": 80
            }

    def save_config(self, company_id_or_code: str, config_data: Dict[str, Any]):
        """Save voucher configuration."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM companies WHERE id = ? OR code = ?;", (company_id_or_code, company_id_or_code))
            row = cursor.fetchone()
            if not row:
                raise ValueError("Company not found.")
            comp_id = row["id"]

            cursor.execute("""
                INSERT INTO company_configs (company_id, vch_start, vch_digits, vch_prefix, default_tax, auto_round, receipt_width)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_id) DO UPDATE SET
                    vch_start = excluded.vch_start,
                    vch_digits = excluded.vch_digits,
                    vch_prefix = excluded.vch_prefix,
                    default_tax = excluded.default_tax,
                    auto_round = excluded.auto_round,
                    receipt_width = excluded.receipt_width;
            """, (
                comp_id,
                int(config_data.get("vchStart", 1)),
                int(config_data.get("vchDigits", 3)),
                str(config_data.get("vchPrefix", "")),
                str(config_data.get("defaultTax", "18")),
                str(config_data.get("autoRound", "Y")),
                int(config_data.get("receiptWidth", 80))
            ))
            conn.commit()


company_service = CompanyService()
