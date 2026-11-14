"""
Test Suite: Traditional Billing Alembic Migration Verification.
Executes upgrade head and downgrade base against an isolated development database,
asserting that all 9 foundation tables, constraints, indices, and seeded roles are established.
"""

from pathlib import Path
import pytest
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic import command


def test_traditional_alembic_migration_lifecycle(tmp_path):
    """
    Run upgrade head on isolated SQLite database, verify 9 tables + constraints,
    then run downgrade base and verify clean teardown.
    """
    db_file = tmp_path / "migration_test_traditional.db"
    db_url = f"sqlite:///{db_file}"

    # Setup Alembic Config for Traditional Billing
    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Run upgrade head
    command.upgrade(alembic_cfg, "head")

    # 2. Inspect created tables
    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    expected_tables = {
        "companies",
        "branches",
        "roles",
        "users",
        "accounts",
        "items",
        "item_barcodes",
        "barcode_reservations",
        "stock_balances",
        "audit_logs",
        "traditional_alembic_version",
    }

    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"

    # 3. Verify seeded roles
    with engine.connect() as conn:
        roles = conn.execute(text("SELECT name FROM roles ORDER BY name ASC;")).fetchall()
        role_names = [r[0] for r in roles]
        assert "Administrator" in role_names
        assert "Store Manager" in role_names
        assert "Manager" in role_names
        assert "Cashier" in role_names

        # 4. Verify branch check constraint (code = 'BR01')
        conn.execute(text("PRAGMA foreign_keys = ON;"))
        conn.execute(
            text("INSERT INTO companies (id, code, name, created_at, updated_at) VALUES ('c1', 'COMP1', 'Test Corp', datetime('now'), datetime('now'));")
        )
        conn.commit()

        # Inserting BR01 should succeed
        conn.execute(
            text("INSERT INTO branches (id, company_id, code, name, created_at) VALUES ('b1', 'c1', 'BR01', 'Main Branch', datetime('now'));")
        )
        conn.commit()

        # Inserting BR02 must fail check constraint
        with pytest.raises(Exception):
            conn.execute(
                text("INSERT INTO branches (id, company_id, code, name, created_at) VALUES ('b2', 'c1', 'BR02', 'Second Branch', datetime('now'));")
            )
            conn.commit()

        # 5. Verify stock balance check constraint (current_qty_scaled >= 0)
        conn.execute(
            text("INSERT INTO items (id, company_id, sku, name, selling_price, created_at, updated_at) VALUES ('i1', 'c1', 'SKU01', 'Widget', 10.00, datetime('now'), datetime('now'));")
        )
        conn.commit()

        # Inserting negative stock balance must fail check constraint
        with pytest.raises(Exception):
            conn.execute(
                text("INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty_scaled, updated_at) VALUES ('sb1', 'c1', 'b1', 'i1', -50, datetime('now'));")
            )
            conn.commit()

    # 6. Run downgrade base
    command.downgrade(alembic_cfg, "base")

    # 7. Confirm tables dropped
    inspector_post = inspect(engine)
    post_tables = set(inspector_post.get_table_names())
    # All foundation tables should be dropped, only traditional_alembic_version might remain empty
    for t in expected_tables - {"traditional_alembic_version"}:
        assert t not in post_tables, f"Table {t} was not dropped by downgrade!"

    engine.dispose()
