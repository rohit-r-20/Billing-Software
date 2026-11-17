"""
Comprehensive Automated Test Suite: Traditional Billing Inventory Engine.
Validates all 18 architecture, security, transaction, and isolation invariants:
1. Opening stock creation.
2. Purchase inward movement.
3. Sales outward movement.
4. Insufficient stock rejection.
5. Negative-stock policy enforcement.
6. Stock adjustment (positive and negative).
7. Stock transfer between branches.
8. Sales return (Credit Note).
9. Purchase return (Debit Note).
10. Duplicate posting prevention (idempotency key).
11. Multi-tenant company isolation.
12. Branch isolation.
13. Transaction rollback on failure.
14. Ledger and balance consistency (sum of movements matches balance).
15. Concurrent stock deduction under multi-threading.
16. Traditional/Fast database isolation (anti_matrix_billing.db untouched).
17. Migration upgrade from an empty Traditional database.
18. Migration upgrade from existing Traditional schema (rev 003 -> 004) on a disposable copy.
"""

import os
import shutil
import hashlib
import concurrent.futures
from pathlib import Path
from decimal import Decimal
import pytest
from sqlalchemy import select, and_, text
from alembic.config import Config
from alembic import command

from db.traditional_database import TraditionalDatabaseManager
from db.traditional_models import (
    Company,
    Branch,
    Item,
    StockBalance,
    StockMovement,
    StockAdjustment,
    StockTransfer,
)
from services.traditional_company_service import TraditionalCompanyService
from services.traditional_product_service import TraditionalProductService
from services.traditional_inventory_service import (
    TraditionalInventoryService,
    InsufficientStockError,
    InvalidMovementError,
    TraditionalInventoryError,
    scaled_to_qty,
    qty_to_scaled,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FAST_DB_PATH = BASE_DIR / "data" / "anti_matrix_billing.db"


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture
def inv_env(tmp_path):
    """Provides an isolated, fully migrated Traditional SQLite database for inventory tests."""
    db_file = tmp_path / "test_traditional_inv.db"
    db_url = f"sqlite:///{db_file}"

    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    company_service = TraditionalCompanyService(db_manager=trad_mgr)
    product_service = TraditionalProductService(db_manager=trad_mgr)
    inventory_service = TraditionalInventoryService(db=trad_mgr)

    # Setup initial company & branch
    setup_data = {
        "code": "CORP_INV",
        "name": "Inventory Test Corp",
        "finYear": "2026-2027",
        "taxNo": "33AAACL1234F1Z1",
        "state": "Tamilnadu",
        "adminUsername": "INVADMIN",
        "adminPassword": "InventoryAdmin@2026",
    }
    company_info = company_service.initial_setup(setup_data)
    cid = company_info["companyId"]

    # Retrieve default branch BR01
    with trad_mgr.read_session_scope() as session:
        branch = session.scalar(select(Branch).where(Branch.company_id == cid))
        bid = branch.id

    # Create a test product
    user_id = company_info["adminUserId"]
    prod_data = {
        "sku": "ITEM-INV-001",
        "name": "Organic Whole Milk",
        "sellingPrice": "45.00",
        "cogsAmount": "32.00",
        "unit": "Ltr.",
        "taxRatePercent": "5.00",
        "taxCategory": "GST 5%",
    }
    prod = product_service.save_product(cid, user_id, prod_data)
    item_id = prod["id"]

    yield {
        "trad_mgr": trad_mgr,
        "company_service": company_service,
        "product_service": product_service,
        "inventory_service": inventory_service,
        "company_id": cid,
        "branch_id": bid,
        "user_id": user_id,
        "item_id": item_id,
        "db_file": db_file,
    }

    trad_mgr.close()


# -----------------------------------------------------------------------------
# 1. Opening stock creation
# -----------------------------------------------------------------------------
def test_opening_stock_creation(inv_env):
    inv_svc = inv_env["inventory_service"]
    cid = inv_env["company_id"]
    bid = inv_env["branch_id"]
    item_id = inv_env["item_id"]

    res = inv_svc.record_opening_stock(
        company_id=cid,
        branch_id=bid,
        item_id=item_id,
        qty="100.000",
        unit_cost="30.00",
        reference_id="OP-2026-001",
        notes="Opening inventory intake",
    )
    assert res["success"] is True
    assert res["new_balance"] == Decimal("100.000")
    assert res["movement_type"] == "OPENING"

    # Verify query balance
    bal = inv_svc.get_stock_balance(cid, item_id, bid)
    assert bal["current_qty"] == Decimal("100.000")
    assert bal["current_qty_scaled"] == 100000


# -----------------------------------------------------------------------------
# 2. Purchase inward movement
# -----------------------------------------------------------------------------
def test_purchase_inward_movement(inv_env):
    inv_svc = inv_env["inventory_service"]
    cid = inv_env["company_id"]
    bid = inv_env["branch_id"]
    item_id = inv_env["item_id"]

    res = inv_svc.record_stock_inward(
        company_id=cid,
        branch_id=bid,
        item_id=item_id,
        qty="50.500",
        unit_cost="32.00",
        reference_type="PURCHASE_VOUCHER",
        reference_id="PUR-000001",
    )
    assert res["success"] is True
    assert res["new_balance"] == Decimal("50.500")

    # Add another purchase batch
    res2 = inv_svc.record_stock_inward(
        company_id=cid,
        branch_id=bid,
        item_id=item_id,
        qty="25.250",
        unit_cost="33.00",
        reference_type="PURCHASE_VOUCHER",
        reference_id="PUR-000002",
    )
    assert res2["new_balance"] == Decimal("75.750")

    bal = inv_svc.get_stock_balance(cid, item_id, bid)
    assert bal["current_qty"] == Decimal("75.750")


# -----------------------------------------------------------------------------
# 3. Sales outward movement
# -----------------------------------------------------------------------------
def test_sales_outward_movement(inv_env):
    inv_svc = inv_env["inventory_service"]
    cid = inv_env["company_id"]
    bid = inv_env["branch_id"]
    item_id = inv_env["item_id"]

    # Seed stock
    inv_svc.record_stock_inward(cid, bid, item_id, qty="40.000")

    # Deduct sale
    res = inv_svc.record_stock_outward(
        company_id=cid,
        branch_id=bid,
        item_id=item_id,
        qty="15.000",
        allow_negative_stock=False,
        reference_type="SALES_INVOICE",
        reference_id="INV-000001",
    )
    assert res["success"] is True
    assert res["new_balance"] == Decimal("25.000")
    assert res["movement_type"] == "SALE"

    bal = inv_svc.get_stock_balance(cid, item_id, bid)
    assert bal["current_qty"] == Decimal("25.000")


# -----------------------------------------------------------------------------
# 4. Insufficient stock rejection
# -----------------------------------------------------------------------------
def test_insufficient_stock_rejection(inv_env):
    inv_svc = inv_env["inventory_service"]
    cid = inv_env["company_id"]
    bid = inv_env["branch_id"]
    item_id = inv_env["item_id"]

    inv_svc.record_stock_inward(cid, bid, item_id, qty="10.000")

    # Attempting to deduct 15 units when only 10 available MUST raise InsufficientStockError
    with pytest.raises(InsufficientStockError) as exc_info:
        inv_svc.record_stock_outward(
            company_id=cid,
            branch_id=bid,
            item_id=item_id,
            qty="15.000",
            allow_negative_stock=False,
        )
    assert "Insufficient stock" in str(exc_info.value)

    # Balance must remain unchanged at 10.000
    bal = inv_svc.get_stock_balance(cid, item_id, bid)
    assert bal["current_qty"] == Decimal("10.000")


# -----------------------------------------------------------------------------
# 5. Negative-stock policy enforcement
# -----------------------------------------------------------------------------
def test_negative_stock_policy_enforcement(inv_env):
    inv_svc = inv_env["inventory_service"]
    cid = inv_env["company_id"]
    bid = inv_env["branch_id"]
    item_id = inv_env["item_id"]

    # Initial stock is 5.000
    inv_svc.record_stock_inward(cid, bid, item_id, qty="5.000")

    items = [{"item_id": item_id, "qty": "12.000"}]

    # When allow_negative_stock is False: pre-validation fails
    valid, errors = inv_svc.validate_stock_availability(cid, bid, items, allow_negative_stock=False)
    assert valid is False
    assert len(errors) == 1
    assert "Insufficient stock" in errors[0]

    # When allow_negative_stock is True: pre-validation passes
    valid_neg, errors_neg = inv_svc.validate_stock_availability(cid, bid, items, allow_negative_stock=True)
    assert valid_neg is True
    assert len(errors_neg) == 0


# -----------------------------------------------------------------------------
# 6. Stock adjustment (positive and negative)
# -----------------------------------------------------------------------------
def test_stock_adjustment(inv_env):
    inv_svc = inv_env["inventory_service"]
    cid = inv_env["company_id"]
    bid = inv_env["branch_id"]
    item_id = inv_env["item_id"]

    inv_svc.record_stock_inward(cid, bid, item_id, qty="30.000")

    # Negative adjustment (damage)
    res_neg = inv_svc.adjust_stock(
        company_id=cid,
        branch_id=bid,
        item_id=item_id,
        qty_delta="-3.000",
        adjustment_type="DAMAGE",
        reason="Broken bottles during transit",
        authorized_by="Store Manager",
    )
    assert res_neg["success"] is True
    assert res_neg["new_balance"] == Decimal("27.000")

    # Positive adjustment (found stock in physical audit)
    res_pos = inv_svc.adjust_stock(
        company_id=cid,
        branch_id=bid,
        item_id=item_id,
        qty_delta="5.000",
        adjustment_type="PHYSICAL_COUNT",
        reason="Annual physical stock variance count",
    )
    assert res_pos["success"] is True
    assert res_pos["new_balance"] == Decimal("32.000")


# -----------------------------------------------------------------------------
# 7. Stock transfer between branches
# -----------------------------------------------------------------------------
def test_stock_transfer_between_branches(inv_env):
    inv_svc = inv_env["inventory_service"]
    trad_mgr = inv_env["trad_mgr"]
    cid1 = inv_env["company_id"]
    bid1 = inv_env["branch_id"]
    item_id = inv_env["item_id"]

    inv_svc.record_stock_inward(cid1, bid1, item_id, qty="50.000")

    # 1. Transfer to the exact same branch MUST be rejected
    with pytest.raises(InvalidMovementError) as exc_info_same:
        inv_svc.transfer_stock(cid1, bid1, bid1, item_id, qty="5.000")
    assert "Source and destination branches cannot be the same" in str(exc_info_same.value)

    # 2. Transfer to a non-existent branch MUST be rejected
    with pytest.raises(TraditionalInventoryError):
        inv_svc.transfer_stock(cid1, bid1, "NON_EXISTENT_BRANCH", item_id, qty="5.000")

    # 3. Create Company B and its Branch BR01
    with trad_mgr.session_scope() as session:
        cb = Company(
            id="COMPANY_TRANSFER_TEST_B",
            code="CORP_TRF_B",
            name="Branch Transfer Test Corp B",
            is_active=True,
        )
        session.add(cb)
        session.flush()
        bb = Branch(
            id="BRANCH_TRANSFER_TEST_B",
            company_id=cb.id,
            code="BR01",
            name="Branch BR01 Company B",
            is_active=True,
        )
        session.add(bb)
        session.flush()
        bid_b = bb.id

    # 4. Attempting cross-company transfer MUST be rejected by tenant validation
    with pytest.raises(TraditionalInventoryError) as exc_info_cross:
        inv_svc.transfer_stock(cid1, bid1, bid_b, item_id, qty="5.000")
    assert "not found for company" in str(exc_info_cross.value)

    # 5. Stock balance at source branch remains untouched at 50.000
    bal = inv_svc.get_stock_balance(cid1, item_id, bid1)
    assert bal["current_qty"] == Decimal("50.000")


# -----------------------------------------------------------------------------
# 8. Sales return (Credit Note)
# -----------------------------------------------------------------------------
def test_sales_return(inv_env):
    inv_svc = inv_env["inventory_service"]
    cid = inv_env["company_id"]
    bid = inv_env["branch_id"]
    item_id = inv_env["item_id"]

    inv_svc.record_stock_inward(cid, bid, item_id, qty="20.000")
    inv_svc.record_stock_outward(cid, bid, item_id, qty="5.000")
    assert inv_svc.get_stock_balance(cid, item_id, bid)["current_qty"] == Decimal("15.000")

    # Customer returns 2 units
    ret = inv_svc.record_sales_return(
        company_id=cid,
        branch_id=bid,
        item_id=item_id,
        qty="2.000",
        reference_type="SALES_RETURN",
        reference_id="SR-000001",
        notes="Customer return of unopened milk",
    )
    assert ret["success"] is True
    assert ret["new_balance"] == Decimal("17.000")
    assert ret["movement_type"] == "SALES_RETURN"

    bal = inv_svc.get_stock_balance(cid, item_id, bid)
    assert bal["current_qty"] == Decimal("17.000")


# -----------------------------------------------------------------------------
# 9. Purchase return (Debit Note)
# -----------------------------------------------------------------------------
def test_purchase_return(inv_env):
    inv_svc = inv_env["inventory_service"]
    cid = inv_env["company_id"]
    bid = inv_env["branch_id"]
    item_id = inv_env["item_id"]

    inv_svc.record_stock_inward(cid, bid, item_id, qty="40.000")

    # Return 10 units to supplier
    ret = inv_svc.record_purchase_return(
        company_id=cid,
        branch_id=bid,
        item_id=item_id,
        qty="10.000",
        reference_type="PURCHASE_RETURN",
        reference_id="PR-000001",
        notes="Defective packaging returned to vendor",
    )
    assert ret["success"] is True
    assert ret["new_balance"] == Decimal("30.000")
    assert ret["movement_type"] == "PURCHASE_RETURN"

    bal = inv_svc.get_stock_balance(cid, item_id, bid)
    assert bal["current_qty"] == Decimal("30.000")


# -----------------------------------------------------------------------------
# 10. Duplicate posting prevention (idempotency key)
# -----------------------------------------------------------------------------
def test_duplicate_posting_prevention(inv_env):
    inv_svc = inv_env["inventory_service"]
    cid = inv_env["company_id"]
    bid = inv_env["branch_id"]
    item_id = inv_env["item_id"]

    inv_svc.record_stock_inward(cid, bid, item_id, qty="100.000")

    idem_key = "SALE-VCH-888-ITEM-001"

    # First outward posting
    res1 = inv_svc.record_stock_outward(
        company_id=cid,
        branch_id=bid,
        item_id=item_id,
        qty="20.000",
        idempotency_key=idem_key,
    )
    assert res1["success"] is True
    assert res1["is_idempotent_replay"] is False
    assert res1["new_balance"] == Decimal("80.000")

    # Second outward posting with identical idempotency key (simulating network retry or double-click)
    res2 = inv_svc.record_stock_outward(
        company_id=cid,
        branch_id=bid,
        item_id=item_id,
        qty="20.000",
        idempotency_key=idem_key,
    )
    assert res2["success"] is True
    assert res2["is_idempotent_replay"] is True
    assert res2["movement_id"] == res1["movement_id"]
    # Stock balance MUST NOT be double deducted
    assert res2["new_balance"] == Decimal("80.000")

    bal = inv_svc.get_stock_balance(cid, item_id, bid)
    assert bal["current_qty"] == Decimal("80.000")


# -----------------------------------------------------------------------------
# 11. Multi-tenant company isolation
# -----------------------------------------------------------------------------
def test_company_isolation(inv_env):
    inv_svc = inv_env["inventory_service"]
    trad_mgr = inv_env["trad_mgr"]
    cid1 = inv_env["company_id"]
    bid1 = inv_env["branch_id"]
    item_id1 = inv_env["item_id"]

    # Directly insert Company B and its Branch BR01
    with trad_mgr.session_scope() as session:
        cb = Company(
            id="COMPANY_ISOLATION_TEST_B",
            code="CORP_B_ISO",
            name="Beta Wholesale Ltd",
            is_active=True,
        )
        session.add(cb)
        session.flush()
        bb = Branch(
            id="BRANCH_ISOLATION_TEST_B",
            company_id=cb.id,
            code="BR01",
            name="Main Branch",
            is_active=True,
        )
        session.add(bb)
        session.flush()
        cid2 = cb.id

    # Seed stock in Company A
    inv_svc.record_stock_inward(cid1, bid1, item_id1, qty="50.000")

    # Attempting to query Company A's item using Company B context MUST fail fail-closed
    with pytest.raises(TraditionalInventoryError):
        inv_svc.get_stock_balance(cid2, item_id1)

    # Attempting to deduct stock from Company A using Company B context MUST fail
    with pytest.raises(TraditionalInventoryError):
        inv_svc.record_stock_outward(cid2, bid1, item_id1, qty="10.000")


# -----------------------------------------------------------------------------
# 12. Branch isolation
# -----------------------------------------------------------------------------
def test_branch_isolation(inv_env):
    inv_svc = inv_env["inventory_service"]
    trad_mgr = inv_env["trad_mgr"]
    cid1 = inv_env["company_id"]
    bid1 = inv_env["branch_id"]
    item_id = inv_env["item_id"]

    # In Traditional Billing, each company enforces a single BR01 branch
    # Create Company B with its own BR01 branch
    with trad_mgr.session_scope() as session:
        cb = Company(
            id="COMPANY_BRANCH_ISO_B",
            code="CORP_BR_ISO_B",
            name="Branch Isolation Company B",
            is_active=True,
        )
        session.add(cb)
        session.flush()
        bb = Branch(
            id="BRANCH_BR_ISO_B",
            company_id=cb.id,
            code="BR01",
            name="Branch BR01",
            is_active=True,
        )
        session.add(bb)
        session.flush()
        bid2 = bb.id

    # Seed 100 units at Branch 1
    inv_svc.record_stock_inward(cid1, bid1, item_id, qty="100.000")

    # Attempting to access Branch 2 under Company 1 context MUST fail
    with pytest.raises(TraditionalInventoryError) as exc_info:
        inv_svc.record_stock_outward(cid1, bid2, item_id, qty="10.000")
    assert "not found for company" in str(exc_info.value)

    # Branch 1 balance remains 100.000
    bal = inv_svc.get_stock_balance(cid1, item_id, bid1)
    assert bal["current_qty"] == Decimal("100.000")


# -----------------------------------------------------------------------------
# 13. Transaction rollback on failure
# -----------------------------------------------------------------------------
def test_transaction_rollback_on_failure(inv_env):
    inv_svc = inv_env["inventory_service"]
    trad_mgr = inv_env["trad_mgr"]
    cid = inv_env["company_id"]
    bid = inv_env["branch_id"]
    item_id = inv_env["item_id"]

    inv_svc.record_stock_inward(cid, bid, item_id, qty="25.000")

    # Simulate an outward call that fails due to insufficient stock
    with pytest.raises(InsufficientStockError):
        inv_svc.record_stock_outward(cid, bid, item_id, qty="100.000", allow_negative_stock=False)

    # Balance remains exactly 25.000
    bal = inv_svc.get_stock_balance(cid, item_id, bid)
    assert bal["current_qty"] == Decimal("25.000")

    # Confirm ledger has zero outward records
    ledger = inv_svc.get_stock_ledger(cid, item_id, bid)
    assert len(ledger) == 1
    assert ledger[0]["movement_type"] == "PURCHASE"


# -----------------------------------------------------------------------------
# 14. Ledger and balance consistency
# -----------------------------------------------------------------------------
def test_ledger_and_balance_consistency(inv_env):
    inv_svc = inv_env["inventory_service"]
    cid = inv_env["company_id"]
    bid = inv_env["branch_id"]
    item_id = inv_env["item_id"]

    # Perform varied sequence of operations
    inv_svc.record_opening_stock(cid, bid, item_id, qty="50.000")
    inv_svc.record_stock_inward(cid, bid, item_id, qty="100.000")
    inv_svc.record_stock_outward(cid, bid, item_id, qty="40.000")
    inv_svc.record_sales_return(cid, bid, item_id, qty="5.000")
    inv_svc.record_purchase_return(cid, bid, item_id, qty="15.000")
    inv_svc.adjust_stock(cid, bid, item_id, qty_delta="-2.000", adjustment_type="DAMAGE")

    # Expected: 50 + 100 - 40 + 5 - 15 - 2 = 98.000
    breakdown = inv_svc.calculate_stock_breakdown(cid, item_id, bid)
    assert breakdown["is_reconciled"] is True
    assert breakdown["calculated_stock"] == Decimal("98.000")
    assert breakdown["materialized_balance"] == Decimal("98.000")

    # Reconcile helper asserts equality
    recon = inv_svc.reconcile_balance_with_ledger(cid, bid, item_id)
    assert recon["is_reconciled"] is True


# -----------------------------------------------------------------------------
# 15. Concurrent stock deduction
# -----------------------------------------------------------------------------
def test_concurrent_stock_deduction(inv_env):
    inv_svc = inv_env["inventory_service"]
    cid = inv_env["company_id"]
    bid = inv_env["branch_id"]
    item_id = inv_env["item_id"]

    # Initial stock: 100 units
    inv_svc.record_stock_inward(cid, bid, item_id, qty="100.000")

    # Launch 10 concurrent threads each attempting to deduct 10 units
    def deduct_worker(i):
        try:
            return inv_svc.record_stock_outward(
                company_id=cid,
                branch_id=bid,
                item_id=item_id,
                qty="10.000",
                idempotency_key=f"CONC-THREAD-{i}",
            )
        except Exception as e:
            return {"error": str(e)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(deduct_worker, i) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # Count successful deductions
    successes = [r for r in results if r.get("success") is True]
    assert len(successes) == 10

    # Final balance must be exactly 100 - (10 * 10) = 0.000
    bal = inv_svc.get_stock_balance(cid, item_id, bid)
    assert bal["current_qty"] == Decimal("0.000")

    recon = inv_svc.reconcile_balance_with_ledger(cid, bid, item_id)
    assert recon["is_reconciled"] is True


# -----------------------------------------------------------------------------
# 16. Traditional/Fast database isolation
# -----------------------------------------------------------------------------
def test_traditional_fast_database_isolation(inv_env):
    if not FAST_DB_PATH.exists():
        pytest.skip("Fast Billing DB path not found")

    initial_fast_hash = compute_sha256(FAST_DB_PATH)

    inv_svc = inv_env["inventory_service"]
    cid = inv_env["company_id"]
    bid = inv_env["branch_id"]
    item_id = inv_env["item_id"]

    # Execute traditional inventory operations
    inv_svc.record_stock_inward(cid, bid, item_id, qty="200.000")
    inv_svc.record_stock_outward(cid, bid, item_id, qty="50.000")
    inv_svc.adjust_stock(cid, bid, item_id, qty_delta="10.000")

    post_fast_hash = compute_sha256(FAST_DB_PATH)

    # Fast Billing database SHA-256 MUST be 100% untouched
    assert initial_fast_hash == post_fast_hash


# -----------------------------------------------------------------------------
# 17. Migration upgrade from an empty Traditional database
# -----------------------------------------------------------------------------
def test_migration_upgrade_from_empty_traditional_database(tmp_path):
    empty_db = tmp_path / "empty_trad.db"
    db_url = f"sqlite:///{empty_db}"

    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Upgrade from empty (base -> head)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    with trad_mgr.get_connection() as conn:
        cur = conn.connection.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = set(r[0] for r in cur.fetchall())

    expected = {"companies", "branches", "items", "stock_balances", "stock_movements", "stock_adjustments", "stock_transfers"}
    assert expected.issubset(tables)

    trad_mgr.close()


# -----------------------------------------------------------------------------
# 18. Migration upgrade from existing Traditional schema (rev 003 -> 004)
# -----------------------------------------------------------------------------
def test_migration_upgrade_from_existing_traditional_schema(tmp_path):
    copy_db = tmp_path / "copy_rev003.db"
    db_url = f"sqlite:///{copy_db}"

    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade only up to rev 003
    command.upgrade(alembic_cfg, "003_sales_voucher_sequences")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    comp_svc = TraditionalCompanyService(db_manager=trad_mgr)
    c_info = comp_svc.initial_setup({
        "code": "PRE_004",
        "name": "Pre-004 Enterprise",
        "adminUsername": "ADMIN_PRE",
        "adminPassword": "PrePassword@2026",
    })
    cid = c_info["companyId"]
    trad_mgr.close()

    # 2. Upgrade from 003 to 004 (head)
    command.upgrade(alembic_cfg, "head")

    # 3. Verify existing company and user data remain intact
    trad_mgr2 = TraditionalDatabaseManager(database_url=db_url)
    with trad_mgr2.read_session_scope() as session:
        c = session.scalar(select(Company).where(Company.id == cid))
        assert c is not None
        assert c.code == "PRE_004"
        assert c.name == "Pre-004 Enterprise"

    trad_mgr2.close()
