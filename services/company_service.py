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

    def authenticate(self, code_or_user: str, password: str, username: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Verify password for the selected company code or username across users and company records."""
        ident = (code_or_user or "").strip().upper()
        uname = (username or "").strip().upper()
        if not ident:
            return None

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Match company code
            cursor.execute("SELECT * FROM companies WHERE UPPER(code) = ?;", (ident,))
            row = cursor.fetchone()
            # 2. If not found by code, try matching company username
            if not row:
                cursor.execute("SELECT * FROM companies WHERE UPPER(username) = ?;", (ident,))
                row = cursor.fetchone()

            if not row:
                return None

            comp = dict(row)

            # Step A: Check users table if a specific username is provided
            if uname:
                try:
                    cursor.execute("""
                        SELECT u.id, u.company_id, u.username, u.password_hash, u.full_name, u.role_name, u.is_active
                        FROM users u
                        WHERE u.company_id = ? AND UPPER(u.username) = ? AND (u.is_active = 1 OR u.is_active IS NULL);
                    """, (comp["id"], uname))
                    u_row = cursor.fetchone()
                    if u_row:
                        user_data = dict(u_row)
                        stored_pwd = user_data.get("password_hash") or ""
                        if verify_password(stored_pwd, password):
                            return {
                                "id": comp["id"],
                                "code": comp["code"],
                                "name": comp["name"],
                                "finYear": comp["fin_year"],
                                "taxNo": comp["gstin"],
                                "state": comp["state"],
                                "userId": user_data["id"],
                                "username": user_data["username"],
                                "displayName": user_data.get("full_name") or user_data["username"],
                                "role": user_data.get("role_name") or "Administrator"
                            }
                        return None
                except Exception as e:
                    logger.debug(f"Users table lookup note: {e}")

            # Step B: Fallback to company admin credentials
            # If a username was specified, verify it matches the company admin username
            if uname and comp.get("username") and comp["username"].strip().upper() != uname:
                return None

            stored_hash = comp.get("password_hash") or ""
            if verify_password(stored_hash, password):
                return {
                    "id": comp["id"],
                    "code": comp["code"],
                    "name": comp["name"],
                    "finYear": comp["fin_year"],
                    "taxNo": comp["gstin"],
                    "state": comp["state"],
                    "userId": f"usr-{comp['code']}",
                    "username": comp.get("username") or "A",
                    "displayName": comp.get("username") or "Administrator",
                    "role": "Administrator"
                }
            return None

    def _ensure_sqlite_user_tables(self):
        """On SQLite test environments, ensure roles and users tables exist."""
        if not self.db.is_postgres:
            try:
                with self.db.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS roles (
                            id VARCHAR(36) PRIMARY KEY,
                            name VARCHAR(50) NOT NULL UNIQUE,
                            description TEXT
                        );
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id VARCHAR(36) PRIMARY KEY,
                            company_id VARCHAR(36) NOT NULL,
                            username VARCHAR(100) NOT NULL,
                            email VARCHAR(255),
                            password_hash VARCHAR(255) NOT NULL,
                            full_name VARCHAR(255),
                            role_id VARCHAR(36),
                            role_name VARCHAR(50) DEFAULT 'Administrator',
                            is_active INTEGER DEFAULT 1,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
                        );
                    """)
                    conn.commit()
            except Exception as e:
                logger.debug(f"SQLite user tables init note: {e}")

    def create_user(
        self,
        company_id: str,
        username: str,
        password: str,
        full_name: Optional[str] = None,
        role_name: str = "Administrator"
    ) -> Dict[str, Any]:
        """Create a user record in the users table with secure password hashing."""
        self._ensure_sqlite_user_tables()
        uname = (username or "").strip()
        if not uname:
            raise ValueError("Username is required.")
        cid = (company_id or "").strip()
        if not cid:
            raise ValueError("Company ID is required.")

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Resolve real company primary key if code was passed
            cursor.execute("SELECT id FROM companies WHERE id = ? OR UPPER(code) = ? LIMIT 1;", (cid, cid.upper()))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Company '{company_id}' not found.")
            real_company_id = row["id"] if isinstance(row, dict) or hasattr(row, "keys") else row[0]

            # Check for existing user in this company
            cursor.execute(
                "SELECT id FROM users WHERE company_id = ? AND UPPER(username) = ?;",
                (real_company_id, uname.upper())
            )
            if cursor.fetchone():
                raise ValueError(f"User '{uname}' already exists for company '{company_id}'.")

            # Ensure role exists
            r_name = (role_name or "Administrator").strip()
            cursor.execute("SELECT id FROM roles WHERE UPPER(name) = ? LIMIT 1;", (r_name.upper(),))
            r_row = cursor.fetchone()
            if r_row:
                role_id = r_row["id"] if isinstance(r_row, dict) or hasattr(r_row, "keys") else r_row[0]
            else:
                role_id = f"role-{r_name.lower()[:20]}"
                try:
                    cursor.execute(
                        "INSERT INTO roles (id, name, description) VALUES (?, ?, ?);",
                        (role_id, r_name, f"{r_name} role")
                    )
                except Exception:
                    role_id = None

            user_id = str(uuid.uuid4())
            pwd_hash = hash_password(password)

            cursor.execute("""
                INSERT INTO users (id, company_id, username, password_hash, full_name, role_id, role_name, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1);
            """, (user_id, real_company_id, uname, pwd_hash, full_name or uname, role_id, r_name))

            return {
                "id": user_id,
                "company_id": real_company_id,
                "username": uname,
                "full_name": full_name or uname,
                "role_name": r_name,
                "role_id": role_id
            }

    def provision_initial_administrator(
        self,
        company_code_or_id: str = "COMP0001",
        username: str = "A",
        password: str = "a",
        full_name: str = "System Administrator"
    ) -> Dict[str, Any]:
        """
        Idempotently provision the initial administrator for the specified company.
        If user already exists, returns the existing record without creating duplicates.
        Preserves existing testing credentials (COMP0001 / A / a).
        """
        self._ensure_sqlite_user_tables()
        ident = (company_code_or_id or "").strip()
        uname = (username or "").strip()
        if not ident or not uname:
            raise ValueError("Company identifier and username are required.")

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Resolve company
            cursor.execute("SELECT id, code, name FROM companies WHERE id = ? OR UPPER(code) = ? LIMIT 1;", (ident, ident.upper()))
            comp_row = cursor.fetchone()
            if not comp_row:
                raise ValueError(f"Company '{ident}' not found. Cannot provision administrator.")
            comp_id = comp_row["id"] if isinstance(comp_row, dict) or hasattr(comp_row, "keys") else comp_row[0]

            # 2. Ensure Administrator role exists
            cursor.execute("SELECT id FROM roles WHERE UPPER(name) = 'ADMINISTRATOR' LIMIT 1;")
            role_row = cursor.fetchone()
            if role_row:
                admin_role_id = role_row["id"] if isinstance(role_row, dict) or hasattr(role_row, "keys") else role_row[0]
            else:
                admin_role_id = "role-admin"
                try:
                    cursor.execute(
                        "INSERT INTO roles (id, name, description) VALUES (?, ?, ?);",
                        (admin_role_id, "Administrator", "System Administrator with full access")
                    )
                except Exception as e:
                    logger.debug(f"Role insertion note: {e}")

            # 3. Check if user already exists
            cursor.execute(
                "SELECT id, company_id, username, full_name, role_name, is_active FROM users WHERE company_id = ? AND UPPER(username) = ?;",
                (comp_id, uname.upper())
            )
            existing_user = cursor.fetchone()
            if existing_user:
                u_dict = dict(existing_user)
                return {
                    "id": u_dict["id"],
                    "company_id": u_dict["company_id"],
                    "username": u_dict["username"],
                    "full_name": u_dict.get("full_name") or u_dict["username"],
                    "role_name": u_dict.get("role_name") or "Administrator",
                    "is_active": u_dict.get("is_active", 1),
                    "created": False
                }

            # 4. Create new administrator record
            user_id = str(uuid.uuid4())
            pwd_hash = hash_password(password)
            cursor.execute("""
                INSERT INTO users (id, company_id, username, password_hash, full_name, role_id, role_name, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1);
            """, (user_id, comp_id, uname, pwd_hash, full_name or uname, admin_role_id, "Administrator"))

            return {
                "id": user_id,
                "company_id": comp_id,
                "username": uname,
                "full_name": full_name or uname,
                "role_name": "Administrator",
                "is_active": 1,
                "created": True
            }

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
                    "receiptWidth": row["receipt_width"],
                    "allowNegativeStock": bool(row["allow_negative_stock"]) if "allow_negative_stock" in row.keys() else False
                }
            return {
                "vchStart": 1,
                "vchDigits": 3,
                "vchPrefix": "",
                "defaultTax": "18",
                "autoRound": "Y",
                "receiptWidth": 80,
                "allowNegativeStock": False
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

            allow_neg = 1 if config_data.get("allowNegativeStock") or config_data.get("allow_negative_stock") else 0

            cursor.execute("""
                INSERT INTO company_configs (company_id, vch_start, vch_digits, vch_prefix, default_tax, auto_round, receipt_width, allow_negative_stock)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_id) DO UPDATE SET
                    vch_start = excluded.vch_start,
                    vch_digits = excluded.vch_digits,
                    vch_prefix = excluded.vch_prefix,
                    default_tax = excluded.default_tax,
                    auto_round = excluded.auto_round,
                    receipt_width = excluded.receipt_width,
                    allow_negative_stock = excluded.allow_negative_stock;
            """, (
                comp_id,
                int(config_data.get("vchStart", 1)),
                int(config_data.get("vchDigits", 3)),
                str(config_data.get("vchPrefix", "")),
                str(config_data.get("defaultTax", "18")),
                str(config_data.get("autoRound", "Y")),
                int(config_data.get("receiptWidth", 80)),
                allow_neg
            ))
            conn.commit()


company_service = CompanyService()

