#!/usr/bin/env python3
"""
Staging Data Provisioner for Anti-Matrix Billing V2.

Safely populates synthetic test data for staging validation.
STRICT SAFETY ENFORCEMENT:
- Refuses to execute if active profile is 'production'.
- Refuses to execute if targeting production database files.
- Operates strictly on staging databases (staging_anti_matrix_billing.db and staging_traditional_billing.db).
"""

import sys
import os
import uuid
import secrets
from pathlib import Path
from alembic.config import Config as AlembicConfig
from alembic import command

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Enforce staging environment profile if not explicitly set
if not os.getenv("APP_ENV") and not os.getenv("DATABASE_ENV"):
    os.environ["APP_ENV"] = "staging"
    os.environ["DATABASE_ENV"] = "staging"

# Ensure staging databases are isolated from any lingering production DATABASE_URL
if "staging" not in (os.getenv("DATABASE_URL") or "").lower():
    os.environ["DATABASE_URL"] = f"sqlite:///{BASE_DIR / 'data' / 'staging_anti_matrix_billing.db'}"
if "staging" not in (os.getenv("TRADITIONAL_DATABASE_URL") or "").lower():
    os.environ["TRADITIONAL_DATABASE_URL"] = f"sqlite:///{BASE_DIR / 'data' / 'staging_traditional_billing.db'}"

from sqlalchemy import func
from core.configuration import config
from core.logging_config import logger
from db.database import db_manager
from db.traditional_database import traditional_db_manager
from db.models import Company, Branch, User, Role, Item, ItemBarcode
from db.traditional_models import (
    Company as TradCompany,
    Branch as TradBranch,
    Account,
    User as TradUser,
    VoucherSequence,
    SaleInvoice as TradSaleInvoice,
    CustomerReceipt,
    ReceiptAllocation,
)
from services.company_service import company_service
from services.traditional_auth_service import TraditionalAuthService
from services.traditional_payment_service import TraditionalPaymentService
from services.catalogue_service import catalogue_service
from services.billing_service import billing_service


def seed_staging_environment():
    print("=" * 70)
    print("ANTI-MATRIX BILLING V2 — STAGING SYNTHETIC DATA PROVISIONER")
    print("=" * 70)

    # 1. Strict Environment Safety Verification
    current_env = config.get_environment()
    print(f"[*] Verifying environment profile: '{current_env}'...")
    if config.is_production():
        print("[FATAL ERROR]: Refusing to run in PRODUCTION environment!", file=sys.stderr)
        sys.exit(1)

    fast_db = config.get_database_path()
    trad_db = config.get_traditional_database_path()
    print(f"[*] Fast Billing Staging DB:        {fast_db}")
    print(f"[*] Traditional Billing Staging DB: {trad_db}")

    if "staging" not in fast_db.name or "staging" not in trad_db.name:
        print(f"[FATAL ERROR]: Database path does not contain 'staging': {fast_db.name}, {trad_db.name}", file=sys.stderr)
        sys.exit(1)

    # Validate configuration rules
    diag = config.validate_configuration()
    if not diag["valid"]:
        print("[FATAL ERROR]: Configuration validation failed:", file=sys.stderr)
        for err in diag["errors"]:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    print("[✓] Environment and database isolation verified safe for staging.\n")

    # 2. Initialize Schemas
    print("[*] Initializing Fast Billing staging database schema via migrations...")
    db_manager.run_migrations()
    print("[✓] Fast Billing staging schema initialized.")

    print("[*] Initializing Traditional Billing staging database schema via Alembic...")
    ini_path = (BASE_DIR / "traditional_alembic.ini").resolve()
    alembic_cfg = AlembicConfig(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{trad_db}")
    command.upgrade(alembic_cfg, "head")
    print("[✓] Traditional Billing staging schema initialized.\n")

    # 3. Seed Fast Billing Data
    print("[*] Seeding Fast Billing staging company & users...")
    cid = "COMP0001"
    bid = "BR0001"
    with db_manager.get_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO companies (id, code, name, fin_year, gstin, state)
            VALUES (?, 'STAGE01', 'Staging Enterprise Mart', '2026-2027', '33AAAPL9999Z1Z5', 'Tamil Nadu');
        """, (cid,))
        conn.execute("""
            INSERT OR IGNORE INTO branches (id, company_id, code, name, is_default)
            VALUES (?, ?, 'BR01', 'Staging Main Store', 1);
        """, (bid, cid))

    company_info = company_service.provision_initial_administrator()
    print(f"[✓] Fast Billing primary company verified (ID: {company_info.get('company_id')}).")

    with db_manager.session_scope() as session:
        comp = session.query(Company).first()
        branch = session.query(Branch).filter_by(company_id=comp.id).first()
        
        # Add Cashier user if not existing
        cashier = session.query(User).filter_by(username="staging_cashier").first()
        cashier_pwd = None
        if not cashier:
            cashier_pwd = os.getenv("STAGING_CASHIER_PASSWORD")
            if not cashier_pwd:
                if os.getenv("STAGING_ALLOW_DEMO_CREDENTIALS") == "1":
                    cashier_pwd = "Cashier@123"
                else:
                    cashier_pwd = secrets.token_urlsafe(16)
            company_service.create_user(
                company_id=comp.id,
                username="staging_cashier",
                password=cashier_pwd,
                full_name="Staging POS Cashier",
                role_name="Cashier",
            )
            print("[✓] Provisioned Fast Billing staging cashier: 'staging_cashier'")
        else:
            print("[✓] Fast Billing cashier 'staging_cashier' already exists (skipping creation).")

        # Seed sample POS products
        sample_barcodes = [["8901030000018"], ["8901030000025"], ["8901030000032"]]
        sample_names = ["Staging Soap Bar 100g", "Staging Wheat Flour 1kg", "Staging Tea Leaves 250g"]
        sample_prices = [35.00, 60.00, 120.00]

        for codes, name, price in zip(sample_barcodes, sample_names, sample_prices):
            existing = catalogue_service.find_by_barcode(comp.id, codes[0])
            if not existing:
                catalogue_service.save_item(
                    comp.id,
                    {
                        "name": name,
                        "sales_price": price,
                        "tax_rate": 18.0,
                        "barcodes": codes,
                        "stock_qty": 100,
                    },
                )
        print(f"[✓] Seeded Fast Billing POS products via CatalogueService.")

    # 4. Seed Traditional Billing Data
    print("\n[*] Seeding Traditional Billing staging company, accounts, and ledger...")
    with traditional_db_manager.session_scope() as trad_session:
        # Verify or create company
        t_comp = trad_session.query(TradCompany).first()
        if not t_comp:
            t_comp = TradCompany(
                code="STAGING-CORP",
                name="Apex Staging Enterprises Ltd",
                fin_year="2026-2027",
                gstin="33AAAPL9999Z1Z5",
                state="Tamil Nadu",
                is_active=True,
            )
            trad_session.add(t_comp)
            trad_session.flush()

        t_branch = trad_session.query(TradBranch).filter_by(company_id=t_comp.id).first()
        if not t_branch:
            t_branch = TradBranch(
                company_id=t_comp.id,
                code="BR01",
                name="Staging Corporate HQ",
                is_active=True,
            )
            trad_session.add(t_branch)
            trad_session.flush()

        # Seed Core Accounts including Debtors (Customers) and Creditors (Suppliers)
        accounts_to_seed = [
            ("1001", "Cash on Hand", "Cash"),
            ("1002", "Staging Corporate Bank A/c", "Bank"),
            ("2001", "Sundry Debtors (AR)", "Debtor"),
            ("2002", "Apex Retail Staging Client", "Debtor"),
            ("3001", "Sundry Creditors (AP)", "Creditor"),
            ("3002", "Metro Wholesale Staging Supplies", "Creditor"),
            ("4001", "Sales Revenue", "Revenue"),
            ("5001", "Cost of Goods Sold", "Expense"),
        ]
        created_accs = {}
        for code, name, acc_type in accounts_to_seed:
            acc = trad_session.query(Account).filter_by(company_id=t_comp.id, code=code).first()
            if not acc:
                acc = Account(
                    company_id=t_comp.id,
                    code=code,
                    name=name,
                    account_type=acc_type,
                    is_active=True,
                )
                trad_session.add(acc)
                trad_session.flush()
            created_accs[code] = acc

        trad_session.commit()
        print(f"[✓] Seeded Traditional Chart of Accounts, Customers, and Suppliers.")

    # Seed Traditional Admin User (outside transaction block as auth_service manages its own session)
    auth_service = TraditionalAuthService(traditional_db_manager)
    with traditional_db_manager.session_scope() as trad_session:
        t_user = trad_session.query(TradUser).filter(
            TradUser.company_id == t_comp.id,
            func.upper(TradUser.username) == "STAGING_ADMIN"
        ).first()
    admin_pwd = None
    if not t_user:
        admin_pwd = os.getenv("STAGING_ADMIN_PASSWORD")
        if not admin_pwd:
            if os.getenv("STAGING_ALLOW_DEMO_CREDENTIALS") == "1":
                admin_pwd = "Admin@Staging123"
            else:
                admin_pwd = secrets.token_urlsafe(16)
        t_user = auth_service.create_user(
            company_id=t_comp.id,
            username="staging_admin",
            password=admin_pwd,
            role_name="Administrator",
            full_name="Staging ERP Administrator",
        )
        print("[✓] Provisioned Traditional Billing staging admin: 'staging_admin'")
    else:
        print("[✓] Traditional Billing admin 'staging_admin' already exists (skipping creation).")

    print("\n" + "=" * 70)
    print("STAGING PROVISIONING COMPLETE — READY FOR VALIDATION")
    print("=" * 70)
    if cashier_pwd or admin_pwd:
        print("Newly Generated Credentials (Record Securely; NOT Logged to Disk):")
        if cashier_pwd:
            print(f"  Fast Billing POS:   username: staging_cashier  | password: {cashier_pwd}")
        if admin_pwd:
            print(f"  Traditional ERP:    username: staging_admin    | password: {admin_pwd}")
        print("\n[SECURITY NOTICE]: Rotate all staging credentials before exposing to remote networks.")
    else:
        print("Existing credentials preserved without modification.")
    print("=" * 70)


if __name__ == "__main__":
    seed_staging_environment()
