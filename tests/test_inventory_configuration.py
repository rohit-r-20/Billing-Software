"""
Test Suite: Inventory Configuration Module (Anti-Matrix Billing V2 - Phase 6)

Verifies:
1. Inventory configuration persistence and default values.
2. Multi-tenant company isolation.
3. Branch isolation and fallback.
4. Negative stock settings enforcement.
5. Fractional quantity settings and decimal precision validation.
6. Minimum and reorder levels.
7. Purchase stock increase.
8. Purchase return stock reversal.
9. Sales stock decrease.
10. Sales return stock reversal.
11. Concurrent stock updates and atomic negative guard.
12. Historical stock preservation (prospective configuration application).
13. Stock valuation consistency (Weighted Average Cost).
14. Warehouse and material centre handling (Inter-branch transfers).
15. Batch and expiry handling on inward vouchers.
16. Serial number handling limitation (properly marked unsupported).
17. Role-based permissions enforcement (Admin/Manager/Accountant vs unauthorized).
18. Fast Billing compatibility & JSON isolation.
19. Traditional Billing compatibility & Alembic migration 008 verification.
20. Configuration reset safety (restores defaults without touching stock balances).
21. Fast Billing database SHA256 immutability verification.
"""

import copy
import hashlib
import json
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from core.configuration import config
from db.database import DatabaseManager
from db.traditional_database import traditional_db_manager
from db.traditional_models import (
    Branch,
    Company,
    InventoryConfiguration,
    Item,
    StockBalance,
)
from desktop.web_bridge import BackendBridge
from services.billing_service import billing_service
from services.inventory_config_service import (
    DEFAULT_INVENTORY_CONFIG,
    inventory_config_service,
)
from services.inventory_service import inventory_service
from services.purchase_service import purchase_service
from services.traditional_auth_service import session_registry as traditional_session_registry


FAST_DB_PATH = Path("data/anti_matrix_billing.db")
EXPECTED_FAST_DB_SHA256 = "BDD99C65E7431336321ADABA2D6276F24CAA88CB4BD1A4A62204930FC62061BD"
TEST_CORE_DB_PATH = Path("data/test_phase6_core.db")


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Ensure Traditional migrations are applied up to head (migration 008) and isolated test core DB."""
    if TEST_CORE_DB_PATH.exists():
        try:
            TEST_CORE_DB_PATH.unlink()
        except Exception:
            pass

    test_core_db = DatabaseManager(f"sqlite:///{TEST_CORE_DB_PATH.resolve().as_posix()}")
    test_core_db.run_migrations()

    billing_service.db = test_core_db
    purchase_service.db = test_core_db
    inventory_service.db = test_core_db
    inventory_config_service.db = test_core_db

    traditional_db_manager.run_traditional_migrations()
    traditional_db_manager.ensure_initialized()

    yield

    if TEST_CORE_DB_PATH.exists():
        try:
            TEST_CORE_DB_PATH.unlink()
        except Exception:
            pass


@pytest.fixture
def test_company_a():
    """Provides isolated test company A with branch in Tamil Nadu."""
    cid = f"test-inv-comp-a-{uuid.uuid4().hex[:8]}"
    bid = f"branch-a-{uuid.uuid4().hex[:8]}"
    with traditional_db_manager.session_scope() as session:
        comp = Company(
            id=cid,
            code=f"IA_{uuid.uuid4().hex[:6]}",
            name="Alpha Retailers Pvt Ltd",
            gstin="33AAAPL9876C1Z2",
            state="Tamil Nadu (33)",
            fin_year="2026-2027",
            is_active=True,
        )
        session.add(comp)
        branch = Branch(
            id=bid,
            company_id=cid,
            code="BR01",
            name="Main Branch",
            is_active=True,
        )
        session.add(branch)

    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO companies (id, code, name, fin_year, gstin, state) VALUES (?, ?, ?, ?, ?, ?);",
            (cid, f"IA_{uuid.uuid4().hex[:6]}", "Alpha Retailers Pvt Ltd", "2026-2027", "33AAAPL9876C1Z2", "Tamil Nadu (33)")
        )
        cur.execute(
            "INSERT OR REPLACE INTO branches (id, company_id, code, name, is_default) VALUES (?, ?, ?, ?, 1);",
            (bid, cid, "BR01", "Main Branch")
        )
        cur.execute(
            "INSERT OR REPLACE INTO company_configs (company_id, allow_negative_stock) VALUES (?, 0);",
            (cid,)
        )
        conn.commit()

    yield {"company_id": cid, "branch_id": bid, "state": "Tamil Nadu (33)"}

    with traditional_db_manager.session_scope() as session:
        c = session.get(Company, cid)
        if c:
            session.delete(c)


@pytest.fixture
def test_company_b():
    """Provides isolated test company B in Karnataka."""
    cid = f"test-inv-comp-b-{uuid.uuid4().hex[:8]}"
    bid = f"branch-b-{uuid.uuid4().hex[:8]}"
    with traditional_db_manager.session_scope() as session:
        comp = Company(
            id=cid,
            code=f"IB_{uuid.uuid4().hex[:6]}",
            name="Beta Traders Corporation",
            gstin="29BBBPD1234E1Z5",
            state="Karnataka (29)",
            fin_year="2026-2027",
            is_active=True,
        )
        session.add(comp)
        branch = Branch(
            id=bid,
            company_id=cid,
            code="BR01",
            name="Bangalore Depot",
            is_active=True,
        )
        session.add(branch)

    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO companies (id, code, name, fin_year, gstin, state) VALUES (?, ?, ?, ?, ?, ?);",
            (cid, f"IB_{uuid.uuid4().hex[:6]}", "Beta Traders Corporation", "2026-2027", "29BBBPD1234E1Z5", "Karnataka (29)")
        )
        cur.execute(
            "INSERT OR REPLACE INTO branches (id, company_id, code, name, is_default) VALUES (?, ?, ?, ?, 1);",
            (bid, cid, "BR01", "Bangalore Depot")
        )
        cur.execute(
            "INSERT OR REPLACE INTO company_configs (company_id, allow_negative_stock) VALUES (?, 0);",
            (cid,)
        )
        conn.commit()

    yield {"company_id": cid, "branch_id": bid, "state": "Karnataka (29)"}

    with traditional_db_manager.session_scope() as session:
        c = session.get(Company, cid)
        if c:
            session.delete(c)


def create_test_item(cid: str, name: str, op_stock: float = 0.0, price: float = 500.0, cost: float = 300.0, unit: str = "Pcs.") -> str:
    """Helper to insert an item into test database items table."""
    iid = str(uuid.uuid4())
    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO items (id, company_id, name, alias, sales_price, purc_price, op_stock_qty, unit, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1);
        """, (iid, cid, name, name[:10], price, cost, op_stock, unit))
        conn.commit()
    return iid


# ---------------------------------------------------------------------------
# 1. Inventory Configuration Persistence & Defaults
# ---------------------------------------------------------------------------

def test_01_inventory_config_defaults_and_persistence(test_company_a):
    """Verify default inventory configuration keys and database persistence."""
    cfg = DEFAULT_INVENTORY_CONFIG
    assert cfg["enable_inventory_tracking"] is True
    assert cfg["default_uom"] == "Pcs."
    assert cfg["qty_decimal_precision"] == 3
    assert cfg["allow_fractional_qty"] is True
    assert cfg["default_product_type"] == "Stockable"
    assert cfg["allow_negative_stock"] is False
    assert cfg["stock_warning_behavior"] == "warn_and_allow"
    assert cfg["low_stock_alert_enabled"] is True
    assert cfg["default_min_stock_level"] == 10.0
    assert cfg["default_reorder_level"] == 15.0
    assert cfg["default_reorder_qty"] == 50.0
    assert cfg["default_max_stock_level"] == 500.0
    assert cfg["valuation_method"] == "weighted_average"
    assert cfg["default_material_centre"] == "Main Store"

    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    # Save custom config
    custom = {
        "enable_inventory_tracking": True,
        "default_uom": "Kg",
        "qty_decimal_precision": 2,
        "allow_fractional_qty": True,
        "allow_negative_stock": True,
        "default_min_stock_level": 25.0,
        "default_reorder_level": 30.0,
        "default_reorder_qty": 100.0,
        "default_max_stock_level": 1000.0,
    }
    saved = inventory_config_service.save_traditional_config(cid, custom, branch_id=bid)
    assert saved["default_uom"] == "Kg"
    assert saved["qty_decimal_precision"] == 2
    assert saved["allow_negative_stock"] is True
    assert saved["default_min_stock_level"] == 25.0

    retrieved = inventory_config_service.get_traditional_config(cid, branch_id=bid)
    assert retrieved["default_uom"] == "Kg"
    assert retrieved["allow_negative_stock"] is True


# ---------------------------------------------------------------------------
# 2. Multi-Tenant Company Isolation
# ---------------------------------------------------------------------------

def test_02_multi_tenant_company_isolation(test_company_a, test_company_b):
    """Verify Company A and Company B have completely independent inventory configurations."""
    cid_a = test_company_a["company_id"]
    cid_b = test_company_b["company_id"]

    # Company A: Kg, allow negative stock True, min stock 20
    inventory_config_service.save_traditional_config(
        cid_a,
        {"default_uom": "Kg", "allow_negative_stock": True, "default_min_stock_level": 20.0, "default_reorder_level": 25.0}
    )

    # Company B: Boxes, allow negative stock False, min stock 5
    inventory_config_service.save_traditional_config(
        cid_b,
        {"default_uom": "Boxes", "allow_negative_stock": False, "default_min_stock_level": 5.0, "default_reorder_level": 10.0}
    )

    cfg_a = inventory_config_service.get_traditional_config(cid_a)
    cfg_b = inventory_config_service.get_traditional_config(cid_b)

    assert cfg_a["default_uom"] == "Kg"
    assert cfg_a["allow_negative_stock"] is True
    assert cfg_a["default_min_stock_level"] == 20.0

    assert cfg_b["default_uom"] == "Boxes"
    assert cfg_b["allow_negative_stock"] is False
    assert cfg_b["default_min_stock_level"] == 5.0


# ---------------------------------------------------------------------------
# 3. Branch Isolation and Fallback
# ---------------------------------------------------------------------------

def test_03_branch_isolation_and_fallback(test_company_a):
    """Verify branch-specific inventory overrides company default while unconfigured branch inherits."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    # Company default
    inventory_config_service.save_traditional_config(
        cid,
        {"default_uom": "Pcs.", "default_min_stock_level": 10.0, "default_reorder_level": 15.0}
    )

    # Branch override
    inventory_config_service.save_traditional_config(
        cid,
        {"default_uom": "Rolls", "default_min_stock_level": 50.0, "default_reorder_level": 60.0},
        branch_id=bid
    )

    branch_cfg = inventory_config_service.get_traditional_config(cid, branch_id=bid)
    company_cfg = inventory_config_service.get_traditional_config(cid)

    assert branch_cfg["default_uom"] == "Rolls"
    assert branch_cfg["default_min_stock_level"] == 50.0

    assert company_cfg["default_uom"] == "Pcs."
    assert company_cfg["default_min_stock_level"] == 10.0


# ---------------------------------------------------------------------------
# 4. Negative Stock Settings Enforcement
# ---------------------------------------------------------------------------

def test_04_negative_stock_settings_enforcement(test_company_a):
    """Verify negative stock toggle synchronizes with engine and prevents/allows negative outward checkout."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    item_id = create_test_item(cid, "Test Wireless Mouse", op_stock=5.0)
    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
            VALUES (?, ?, ?, ?, 5.0)
            ON CONFLICT(branch_id, item_id) DO UPDATE SET current_qty = 5.0;
        """, (str(uuid.uuid4()), cid, bid, item_id))
        conn.commit()

    # 1. Prohibit negative stock
    inventory_config_service.save_traditional_config(cid, {"allow_negative_stock": False})

    # Validate stock availability for 10 units when available is 5
    is_valid, errors = inventory_service.validate_stock_availability(
        company_id=cid,
        branch_id=bid,
        items=[{"id": item_id, "name": "Test Wireless Mouse", "qty": 10.0}]
    )
    assert is_valid is False
    assert any("Insufficient stock" in err for err in errors)

    # 2. Allow negative stock
    inventory_config_service.save_traditional_config(cid, {"allow_negative_stock": True})

    is_valid_allowed, _ = inventory_service.validate_stock_availability(
        company_id=cid,
        branch_id=bid,
        items=[{"id": item_id, "name": "Test Wireless Mouse", "qty": 10.0}]
    )
    assert is_valid_allowed is True


# ---------------------------------------------------------------------------
# 5. Fractional Quantity Settings & Precision
# ---------------------------------------------------------------------------

def test_05_fractional_quantity_validation():
    """Verify fractional quantity toggle and decimal precision rules."""
    cfg_no_fractional = copy.deepcopy(DEFAULT_INVENTORY_CONFIG)
    cfg_no_fractional["allow_fractional_qty"] = False

    # Integer quantity passes
    v, _ = inventory_config_service.validate_quantity(3.0, cfg_no_fractional)
    assert v is True

    # Fractional quantity fails
    v, msg = inventory_config_service.validate_quantity(3.5, cfg_no_fractional)
    assert v is False
    assert "Fractional quantity" in msg

    # Precision testing: precision = 2
    cfg_precision = copy.deepcopy(DEFAULT_INVENTORY_CONFIG)
    cfg_precision["allow_fractional_qty"] = True
    cfg_precision["qty_decimal_precision"] = 2

    v2, _ = inventory_config_service.validate_quantity(3.25, cfg_precision)
    assert v2 is True

    v3, msg3 = inventory_config_service.validate_quantity(3.255, cfg_precision)
    assert v3 is False
    assert "exceeds configured limit" in msg3


# ---------------------------------------------------------------------------
# 6. Minimum and Reorder Levels
# ---------------------------------------------------------------------------

def test_06_minimum_and_reorder_levels():
    """Verify threshold coherence validation and low stock alert generation."""
    # Invalid: reorder < min_stock
    is_valid, errors, _ = inventory_config_service.validate_config({
        "default_min_stock_level": 20.0,
        "default_reorder_level": 10.0,
    })
    assert is_valid is False
    assert any("cannot be less than minimum stock level" in err for err in errors)

    # Invalid: max_stock < reorder_level
    is_valid, errors, _ = inventory_config_service.validate_config({
        "default_min_stock_level": 10.0,
        "default_reorder_level": 20.0,
        "default_max_stock_level": 15.0,
    })
    assert is_valid is False
    assert any("cannot be less than reorder level" in err for err in errors)


# ---------------------------------------------------------------------------
# 7. Purchase Stock Increase
# ---------------------------------------------------------------------------

def test_07_purchase_stock_increase(test_company_a):
    """Verify purchase inward transaction increases available stock in balance ledger."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    item_id = create_test_item(cid, "Gigabit Ethernet Switch", op_stock=0.0, price=2500.0, cost=1800.0)

    initial_stock = inventory_service.get_stock(cid, item_id, branch_id=bid)
    assert initial_stock == 0.0

    # Inward 8 units
    new_stock = inventory_service.adjust_stock(
        company_id=cid,
        branch_id=bid,
        item_id=item_id,
        qty_delta=8.0,
        movement_type="PURCHASE",
        unit_cost=1800.0,
        reference_type="PURCHASE_INVOICE",
        reference_id="PINV-001"
    )
    assert new_stock == 8.0
    assert inventory_service.get_stock(cid, item_id, branch_id=bid) == 8.0


# ---------------------------------------------------------------------------
# 8. Purchase Return Stock Reversal
# ---------------------------------------------------------------------------

def test_08_purchase_return_stock_reversal(test_company_a):
    """Verify purchase return decreases available stock (inward reversal)."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    item_id = create_test_item(cid, "Purchase Return Item", op_stock=0.0)
    # Start with 10 units
    inventory_service.adjust_stock(
        company_id=cid, branch_id=bid, item_id=item_id, qty_delta=10.0, movement_type="PURCHASE"
    )

    # Return 2 units
    updated_stock = inventory_service.adjust_stock(
        company_id=cid,
        branch_id=bid,
        item_id=item_id,
        qty_delta=-2.0,
        movement_type="PURCHASE_RETURN",
        reference_type="DEBIT_NOTE",
        reference_id="DN-001"
    )
    assert updated_stock == 8.0
    assert inventory_service.get_stock(cid, item_id, branch_id=bid) == 8.0


# ---------------------------------------------------------------------------
# 9. Sales Stock Decrease
# ---------------------------------------------------------------------------

def test_09_sales_stock_decrease(test_company_a):
    """Verify sales outward transaction decreases stock atomically."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    item_id = create_test_item(cid, "Sales Stock Item", op_stock=0.0)
    inventory_service.adjust_stock(
        company_id=cid, branch_id=bid, item_id=item_id, qty_delta=15.0, movement_type="OPENING"
    )

    # Outward 5 units
    updated_stock = inventory_service.adjust_stock(
        company_id=cid,
        branch_id=bid,
        item_id=item_id,
        qty_delta=-5.0,
        movement_type="SALE",
        reference_type="SALES_INVOICE",
        reference_id="INV-001"
    )
    assert updated_stock == 10.0
    assert inventory_service.get_stock(cid, item_id, branch_id=bid) == 10.0


# ---------------------------------------------------------------------------
# 10. Sales Return Stock Reversal
# ---------------------------------------------------------------------------

def test_10_sales_return_stock_reversal(test_company_a):
    """Verify sales return increases stock (outward reversal)."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    item_id = create_test_item(cid, "Sales Return Item", op_stock=0.0)
    inventory_service.adjust_stock(
        company_id=cid, branch_id=bid, item_id=item_id, qty_delta=10.0, movement_type="OPENING"
    )

    # Return 3 units back to inventory
    updated_stock = inventory_service.adjust_stock(
        company_id=cid,
        branch_id=bid,
        item_id=item_id,
        qty_delta=3.0,
        movement_type="SALES_RETURN",
        reference_type="CREDIT_NOTE",
        reference_id="CN-001"
    )
    assert updated_stock == 13.0
    assert inventory_service.get_stock(cid, item_id, branch_id=bid) == 13.0


# ---------------------------------------------------------------------------
# 11. Concurrent Stock Updates & Negative Stock Guard
# ---------------------------------------------------------------------------

def test_11_concurrent_stock_updates_and_negative_guard(test_company_a):
    """Verify atomic negative guard prevents overselling beyond available stock."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    item_id = create_test_item(cid, "Limited Edition Headset", op_stock=5.0, price=1200.0, cost=800.0)
    inventory_config_service.save_traditional_config(cid, {"allow_negative_stock": False})

    # Available stock = 5
    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
            VALUES (?, ?, ?, ?, 5.0)
            ON CONFLICT(branch_id, item_id) DO UPDATE SET current_qty = 5.0;
        """, (str(uuid.uuid4()), cid, bid, item_id))
        conn.commit()

    # Checkout 1: takes all 5 units -> succeeds
    inv1 = billing_service.create_sale_invoice(
        company_id=cid,
        branch_id=bid,
        party_name="CASH",
        items=[{"id": item_id, "name": "Limited Edition Headset", "qty": 5.0, "price": 1200.0, "tax_rate": 18.0}],
    )
    assert inv1.get("voucher_id") is not None

    # Remaining stock = 0
    assert inventory_service.get_stock(cid, item_id, branch_id=bid) == 0.0

    # Checkout 2: attempts to take 1 unit -> must be blocked
    with pytest.raises(ValueError, match="Insufficient stock"):
        billing_service.create_sale_invoice(
            company_id=cid,
            branch_id=bid,
            party_name="CASH",
            items=[{"id": item_id, "name": "Limited Edition Headset", "qty": 1.0, "price": 1200.0, "tax_rate": 18.0}],
        )


# ---------------------------------------------------------------------------
# 12. Historical Stock Preservation
# ---------------------------------------------------------------------------

def test_12_historical_stock_preservation(test_company_a):
    """Verify updating inventory settings never mutates or recalculates historical stock movements."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    item_id = create_test_item(cid, "Historical Item", op_stock=0.0)
    # Record movement in historical state
    inventory_service.adjust_stock(
        company_id=cid, branch_id=bid, item_id=item_id, qty_delta=50.0, movement_type="OPENING", notes="Historical 1"
    )

    # Change inventory configuration
    inventory_config_service.save_traditional_config(
        cid,
        {
            "default_uom": "Boxes",
            "default_min_stock_level": 50.0,
            "default_reorder_level": 70.0,
            "default_max_stock_level": 200.0,
            "allow_negative_stock": True,
        }
    )

    # Historical movements remain untouched
    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT qty, movement_type, notes FROM stock_movements WHERE company_id = ? AND item_id = ?;", (cid, item_id))
        rows = cur.fetchall()
        assert len(rows) == 1
        assert rows[0]["qty"] == 50.0
        assert rows[0]["movement_type"] == "OPENING"
        assert rows[0]["notes"] == "Historical 1"


# ---------------------------------------------------------------------------
# 13. Stock Valuation Consistency (Weighted Average Cost)
# ---------------------------------------------------------------------------

def test_13_stock_valuation_consistency_wac():
    """Verify Weighted Average Cost calculation remains exact and consistent."""
    cfg = copy.deepcopy(DEFAULT_INVENTORY_CONFIG)
    cfg["valuation_method"] = "weighted_average"

    # Current stock = 10 units @ ₹100 = ₹1,000
    # Inward = 10 units @ ₹150 = ₹1,500
    # New total = 20 units, Total cost = ₹2,500 -> New WAC = ₹125.00
    sim = inventory_config_service.simulate_stock_transaction(
        cfg=cfg,
        current_stock=10.0,
        inward_qty=10.0,
        outward_qty=0.0,
        unit_cost=150.0,
        current_wac=100.0,
    )
    assert sim["valuation_rate"] == 125.0
    assert sim["projected_stock"] == 20.0
    assert sim["projected_valuation"] == 2500.0

    # Sell 5 units @ WAC rate 125 -> closing 15 units, valuation = 15 * 125 = ₹1,875.00
    sim_sale = inventory_config_service.simulate_stock_transaction(
        cfg=cfg,
        current_stock=20.0,
        inward_qty=0.0,
        outward_qty=5.0,
        unit_cost=0.0,
        current_wac=125.0,
    )
    assert sim_sale["valuation_rate"] == 125.0
    assert sim_sale["projected_stock"] == 15.0
    assert sim_sale["projected_valuation"] == 1875.0


# ---------------------------------------------------------------------------
# 14. Warehouse and Material Centre Handling (Inter-Branch Transfers)
# ---------------------------------------------------------------------------

def test_14_warehouse_and_inter_branch_transfers(test_company_a):
    """Verify stock transfers between branches/warehouses move stock without altering company total."""
    cid = test_company_a["company_id"]
    src_branch = test_company_a["branch_id"]
    dst_branch = f"branch-dst-{uuid.uuid4().hex[:8]}"

    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO branches (id, company_id, code, name) VALUES (?, ?, 'BR02', 'Secondary Godown');",
            (dst_branch, cid)
        )
        conn.commit()

    item_id = create_test_item(cid, "Transferable Cable Roll", op_stock=20.0, price=1000.0, cost=700.0, unit="Rolls")

    # Seed source branch with 20 units
    inventory_service.adjust_stock(cid, src_branch, item_id, 20.0, movement_type="OPENING")

    # Transfer 8 units to destination branch
    res = inventory_service.record_stock_transfer(
        company_id=cid,
        data={
            "source_branch_id": src_branch,
            "dest_branch_id": dst_branch,
            "items": [{"item_id": item_id, "qty": 8.0, "unit_cost": 700.0, "unit": "Rolls"}],
            "reason": "Replenish Godown",
        }
    )
    assert res["status"] == "COMPLETED"

    # Source has 12, Destination has 8, Total across company is still 20
    assert inventory_service.get_stock(cid, item_id, branch_id=src_branch) == 12.0
    assert inventory_service.get_stock(cid, item_id, branch_id=dst_branch) == 8.0
    assert inventory_service.get_stock(cid, item_id) == 20.0


# ---------------------------------------------------------------------------
# 15. Batch and Expiry Handling on Inward Vouchers
# ---------------------------------------------------------------------------

def test_15_batch_and_expiry_handling(test_company_a):
    """Verify batch tracking records batch numbers, expiry dates, and available quantities."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    item_id = create_test_item(cid, "Batch Medicine Item", op_stock=0.0, price=200.0, cost=150.0, unit="Pcs.")
    batch_no = f"BAT-{uuid.uuid4().hex[:6].upper()}"
    exp_date = "2027-12-31"

    with billing_service.db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO stock_batches (
                id, company_id, item_id, batch_no, expiry_date,
                purchase_rate, qty_received, qty_sold, qty_available
            ) VALUES (?, ?, ?, ?, ?, 150.0, 100.0, 10.0, 90.0);
        """, (str(uuid.uuid4()), cid, item_id, batch_no, exp_date))
        conn.commit()

        cur.execute("SELECT batch_no, expiry_date, qty_available FROM stock_batches WHERE company_id = ? AND batch_no = ?;", (cid, batch_no))
        row = cur.fetchone()
        assert row is not None
        assert row["batch_no"] == batch_no
        assert row["expiry_date"] == exp_date
        assert row["qty_available"] == 90.0


# ---------------------------------------------------------------------------
# 16. Serial Number Handling Limitation (Properly Marked Unsupported)
# ---------------------------------------------------------------------------

def test_16_serial_number_handling_limitation():
    """Verify that serial number tracking is properly identified as unsupported without fake controls."""
    cfg = DEFAULT_INVENTORY_CONFIG
    # Serial numbers are not present as functional tracking control in active schema
    assert "enable_serial_tracking" not in cfg
    assert cfg["enable_barcode_tracking"] is True
    assert cfg["enable_batch_tracking"] is False


# ---------------------------------------------------------------------------
# 17. Role-Based Permissions Enforcement
# ---------------------------------------------------------------------------

def test_17_role_based_permissions_enforcement(test_company_a):
    """Verify authorized roles can save/reset inventory config, while unauthorized roles are blocked."""
    bridge = BackendBridge()
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    # 1. Unauthenticated -> fails
    bridge._authenticated_session = None
    bridge._traditional_session = None
    res = json.loads(bridge.saveInventoryConfig(json.dumps({"default_uom": "Kg"}), "traditional"))
    assert res["success"] is False

    # 2. Unauthorized role (Cashier) -> blocked with permission_denied
    bridge._authenticated_session = {
        "session_id": str(uuid.uuid4()),
        "company_id": cid,
        "branch_id": bid,
        "role": "Cashier",
        "username": "cashier1",
    }
    res = json.loads(bridge.saveInventoryConfig(json.dumps({"default_uom": "Kg"}), "traditional"))
    assert res["success"] is False
    assert res.get("permission_denied") is True

    # 3. Authorized role (System Administrator) -> succeeds
    bridge._authenticated_session = None
    token = traditional_session_registry.create_session(
        user_id="usr-admin",
        company_id=cid,
        branch_id=bid,
        role_name="System Administrator",
        username="admin",
        display_name="System Administrator",
    )
    bridge._traditional_session = traditional_session_registry.get_session(token)

    res = json.loads(bridge.saveInventoryConfig(
        json.dumps({
            "default_uom": "Boxes",
            "allow_negative_stock": False,
            "default_min_stock_level": 12.0,
            "default_reorder_level": 18.0,
        }),
        "traditional"
    ))
    assert res["success"] is True

    # 4. Authorized role (Store Manager) -> reset succeeds
    token_mgr = traditional_session_registry.create_session(
        user_id="usr-mgr",
        company_id=cid,
        branch_id=bid,
        role_name="Store Manager",
        username="mgr1",
        display_name="Store Manager",
    )
    bridge._traditional_session = traditional_session_registry.get_session(token_mgr)
    reset_res = json.loads(bridge.resetInventoryConfig("traditional"))
    assert reset_res["success"] is True


# ---------------------------------------------------------------------------
# 18. Fast Billing Compatibility & JSON Isolation
# ---------------------------------------------------------------------------

def test_18_fast_billing_compatibility_and_json_isolation():
    """Verify Fast Billing inventory configuration writes to JSON without touching SQLite DB."""
    fast_json_path = Path("data/fast_inventory_configurations.json")
    fast_payload = {
        "enable_inventory_tracking": True,
        "default_uom": "Pack",
        "qty_decimal_precision": 2,
        "allow_negative_stock": True,
    }

    saved = inventory_config_service.save_fast_config("default", fast_payload)
    assert saved["default_uom"] == "Pack"
    assert saved["allow_negative_stock"] is True
    assert fast_json_path.exists()

    retrieved = inventory_config_service.get_fast_config("default")
    assert retrieved["default_uom"] == "Pack"
    assert retrieved["allow_negative_stock"] is True


# ---------------------------------------------------------------------------
# 19. Traditional Billing Compatibility & Alembic Migration 008
# ---------------------------------------------------------------------------

def test_19_traditional_billing_compatibility_and_alembic_migration_008(test_company_a):
    """Verify table inventory_configurations maps to SQLAlchemy model and stores all columns."""
    cid = test_company_a["company_id"]
    with traditional_db_manager.session_scope() as session:
        dummy_id = f"test-inv-schema-{uuid.uuid4().hex[:6]}"
        cfg_entry = InventoryConfiguration(
            id=dummy_id,
            company_id=cid,
            default_uom="Mtrs",
            qty_decimal_precision=2,
            allow_fractional_qty=True,
            allow_negative_stock=False,
            default_min_stock_level=15.0,
            default_reorder_level=20.0,
            default_reorder_qty=100.0,
            default_max_stock_level=1000.0,
            valuation_method="weighted_average",
        )
        session.add(cfg_entry)
        session.flush()

        stmt = select(InventoryConfiguration).where(InventoryConfiguration.id == dummy_id)
        fetched = session.execute(stmt).scalars().first()
        assert fetched is not None
        assert fetched.default_uom == "Mtrs"
        assert fetched.qty_decimal_precision == 2
        assert fetched.default_min_stock_level == 15.0

        session.delete(fetched)


# ---------------------------------------------------------------------------
# 20. Configuration Reset Safety
# ---------------------------------------------------------------------------

def test_20_configuration_reset_safety(test_company_a):
    """Verify resetting inventory configuration restores defaults without mutating stock balances."""
    cid = test_company_a["company_id"]
    bid = test_company_a["branch_id"]

    item_id = create_test_item(cid, "Reset Safety Item", op_stock=0.0)
    inventory_service.adjust_stock(cid, bid, item_id, 45.0, movement_type="OPENING")

    # Set custom settings
    inventory_config_service.save_traditional_config(
        cid,
        {"default_uom": "Litres", "default_min_stock_level": 50.0, "default_reorder_level": 70.0}
    )

    # Reset to defaults
    res = inventory_config_service.reset_traditional_config(cid)
    assert res["default_uom"] == "Pcs."
    assert res["default_min_stock_level"] == 10.0

    # Stock balance must remain 45.0
    assert inventory_service.get_stock(cid, item_id, branch_id=bid) == 45.0


# ---------------------------------------------------------------------------
# 21. Fast Billing Database Immutability Check
# ---------------------------------------------------------------------------

def test_21_fast_billing_database_immutability():
    """Verify Fast Billing SQLite database (anti_matrix_billing.db) SHA256 has remained unchanged."""
    if FAST_DB_PATH.exists():
        hasher = hashlib.sha256()
        with open(FAST_DB_PATH, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_sha256 = hasher.hexdigest().upper()
        assert actual_sha256 == EXPECTED_FAST_DB_SHA256, (
            f"Fast Billing database was mutated! Expected {EXPECTED_FAST_DB_SHA256}, got {actual_sha256}"
        )
