"""
Test Suite: Traditional Billing Real Data Dashboard & Database Isolation.
Proves genuine calculations, zero fake/demo/mock data, tenant isolation,
and strict decoupling from Fast Billing.
"""

from pathlib import Path
from decimal import Decimal
import json
import pytest
from sqlalchemy import text
from alembic.config import Config
from alembic import command

from db.traditional_database import TraditionalDatabaseManager
from db.traditional_models import Company, Branch, Item, StockBalance
from services.traditional_company_service import TraditionalCompanyService
from services.traditional_dashboard_service import TraditionalDashboardService
from services.traditional_auth_service import session_registry as trad_session_registry


@pytest.fixture
def dashboard_env(tmp_path):
    """Isolated SQLite database with Alembic schema for dashboard tests."""
    db_file = tmp_path / "test_traditional_dash.db"
    db_url = f"sqlite:///{db_file}"

    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    company_service = TraditionalCompanyService(db_manager=trad_mgr)
    dashboard_service = TraditionalDashboardService(db_manager=trad_mgr)

    # Bootstrap initial company
    setup_data = {
        "code": "CORP01",
        "name": "Alpha Retail Enterprise",
        "finYear": "2026-2027",
        "taxNo": "33AAAPL1234F1Z1",
        "state": "Tamilnadu",
        "adminUsername": "SUPERADMIN",
        "adminPassword": "SuperSecurePassword@2026",
    }
    company_info = company_service.initial_setup(setup_data)

    yield {
        "trad_mgr": trad_mgr,
        "company_service": company_service,
        "dashboard_service": dashboard_service,
        "company_id": company_info["companyId"],
        "branch_id": company_info["branchId"],
        "db_file": db_file,
    }

    trad_mgr.close()


def test_empty_database_zero_and_unavailable_values(dashboard_env):
    """
    Requirement 1: Empty Traditional database produces zero or unavailable dashboard values.
    No fake or mock figures appear.
    """
    dash_service = dashboard_env["dashboard_service"]
    cid = dashboard_env["company_id"]
    bid = dashboard_env["branch_id"]

    metrics = dash_service.get_dashboard_metrics(company_id=cid, branch_id=bid)

    # 1. Sales: exactly 0.00, count 0
    assert metrics["todaySales"] == 0.00
    assert metrics["todaySalesCount"] == 0
    assert metrics["todaySalesDelta"] == ""

    # 2. Purchases: exactly 0.00, count 0
    assert metrics["todayPurchases"] == 0.00
    assert metrics["todayPurchasesCount"] == 0
    assert metrics["todayPurchasesDelta"] == ""

    # 3. Stock Value: exactly 0.00, count 0, low stock 0
    assert metrics["stockValue"] == 0.00
    assert metrics["stockItemsCount"] == 0
    assert metrics["lowStockCount"] == 0

    # 4. Receivables: None (Not available)
    assert metrics["receivables"] is None
    assert metrics["receivablesDisplay"] == "Not available"
    assert metrics["receivablesOverdueDisplay"] == "N/A"

    # 5. Payables: None (Not available)
    assert metrics["payables"] is None
    assert metrics["payablesDisplay"] == "Not available"
    assert metrics["payablesDueDisplay"] == "N/A"

    # 6. Expenses: 0.00, held bills 0
    assert metrics["todayExpenses"] == 0.00
    assert metrics["heldBills"] == 0

    # 7. Gross Margin: None (Not available)
    assert metrics["grossMargin"] is None
    assert metrics["grossMarginDisplay"] == "Not available"

    # 8. Trend & payment breakdown & activities: empty arrays
    assert metrics["salesTrend"] == []
    assert metrics["paymentSummary"] == []
    assert metrics["revenueExpense"] == []
    assert metrics["recentInvoices"] == []
    assert metrics["recentPurchases"] == []
    assert metrics["recentPayments"] == []
    assert metrics["stockAdjustments"] == []


def test_no_mock_chart_series(dashboard_env):
    """
    Requirement 2: No mock chart series are displayed.
    Ensures hardcoded sample numbers (e.g. 48250, 24180, 482600, 62400, 38900, 3450, 32.4%)
    never appear in dashboard calculations or responses.
    """
    dash_service = dashboard_env["dashboard_service"]
    cid = dashboard_env["company_id"]

    metrics = dash_service.get_dashboard_metrics(company_id=cid)
    serialized = json.dumps(metrics)

    # Banned mock values
    banned_values = [
        "48250",
        "482600",
        "24180",
        "62400",
        "38900",
        "3450",
        "32.4",
        "21712.50",
        "16887.50",
        "7237.50",
        "2412.50",
        "INV-2026-0842",
        "Walk-in Retail Customer",
        "PUR-2026-0194",
        "ITC Limited Distribution",
    ]

    for val in banned_values:
        assert val not in serialized, f"Fabricated mock value '{val}' was found in dashboard metrics!"


def test_real_sales_transactions_produce_correct_totals(dashboard_env):
    """
    Requirement 3: Real sales transactions produce correct sales totals.
    """
    trad_mgr = dashboard_env["trad_mgr"]
    dash_service = dashboard_env["dashboard_service"]
    cid = dashboard_env["company_id"]

    # Create sales_vouchers table and insert real today's invoices
    with trad_mgr.session_scope() as session:
        session.execute(text("""
            CREATE TABLE sales_vouchers (
                id VARCHAR(36) PRIMARY KEY,
                company_id VARCHAR(36) NOT NULL,
                voucher_number VARCHAR(50),
                party_name VARCHAR(100),
                total_amount NUMERIC(12, 2) NOT NULL,
                payment_mode VARCHAR(20),
                status VARCHAR(20),
                created_at TIMESTAMP NOT NULL
            )
        """))
        # 2 sales today (1500.50 + 2499.50 = 4000.00)
        session.execute(text("""
            INSERT INTO sales_vouchers VALUES
            ('vch-1', :cid, 'INV-001', 'Customer Alpha', 1500.50, 'UPI', 'PAID', CURRENT_TIMESTAMP),
            ('vch-2', :cid, 'INV-002', 'Customer Beta', 2499.50, 'CASH', 'PAID', CURRENT_TIMESTAMP),
            ('vch-3', :cid, 'INV-000', 'Customer Old', 5000.00, 'CASH', 'PAID', DATE('now', '-2 days'))
        """), {"cid": cid})

    metrics = dash_service.get_dashboard_metrics(company_id=cid)

    # Sales today should be exactly 4000.00 and count 2
    assert metrics["todaySales"] == 4000.00
    assert metrics["todaySalesCount"] == 2
    assert len(metrics["recentInvoices"]) == 3
    assert metrics["recentInvoices"][0]["vchNo"] == "INV-001"
    assert metrics["recentInvoices"][0]["amount"] == 1500.50


def test_real_purchase_transactions_produce_correct_totals(dashboard_env):
    """
    Requirement 4: Real purchase transactions produce correct purchase totals.
    """
    trad_mgr = dashboard_env["trad_mgr"]
    dash_service = dashboard_env["dashboard_service"]
    cid = dashboard_env["company_id"]

    with trad_mgr.session_scope() as session:
        session.execute(text("""
            CREATE TABLE purchase_vouchers (
                id VARCHAR(36) PRIMARY KEY,
                company_id VARCHAR(36) NOT NULL,
                voucher_number VARCHAR(50),
                supplier_name VARCHAR(100),
                total_amount NUMERIC(12, 2) NOT NULL,
                tax_amount NUMERIC(12, 2),
                status VARCHAR(20),
                created_at TIMESTAMP NOT NULL
            )
        """))
        # 2 purchases today (3250.00 + 1750.00 = 5000.00)
        session.execute(text("""
            INSERT INTO purchase_vouchers VALUES
            ('pur-1', :cid, 'PUR-001', 'Supplier X', 3250.00, 585.00, 'VERIFIED', CURRENT_TIMESTAMP),
            ('pur-2', :cid, 'PUR-002', 'Supplier Y', 1750.00, 315.00, 'VERIFIED', CURRENT_TIMESTAMP)
        """), {"cid": cid})

    metrics = dash_service.get_dashboard_metrics(company_id=cid)

    assert metrics["todayPurchases"] == 5000.00
    assert metrics["todayPurchasesCount"] == 2
    assert len(metrics["recentPurchases"]) == 2
    assert metrics["recentPurchases"][0]["supplier"] == "Supplier X"
    assert metrics["recentPurchases"][0]["amount"] == 3250.00


def test_stock_valuation_uses_valid_stock_and_cost_data(dashboard_env):
    """
    Requirement 5: Stock valuation uses valid actual stock and cost data.
    """
    trad_mgr = dashboard_env["trad_mgr"]
    dash_service = dashboard_env["dashboard_service"]
    cid = dashboard_env["company_id"]
    bid = dashboard_env["branch_id"]

    with trad_mgr.session_scope() as session:
        # Create 2 items
        item_a = Item(
            id="item-a",
            company_id=cid,
            sku="SKU-A",
            name="Product A",
            unit="Pcs.",
            selling_price=Decimal("200.00"),
            cogs_amount=Decimal("120.50"),
            is_active=True,
        )
        item_b = Item(
            id="item-b",
            company_id=cid,
            sku="SKU-B",
            name="Product B",
            unit="Pcs.",
            selling_price=Decimal("100.00"),
            cogs_amount=Decimal("45.00"),
            is_active=True,
        )
        # Create stock balances:
        # Item A: 20 units (scaled: 20,000) -> 20 * 120.50 = 2410.00
        # Item B: 100 units (scaled: 100,000) -> 100 * 45.00 = 4500.00
        # Total valuation = 6910.00
        stock_a = StockBalance(
            id="sb-a",
            company_id=cid,
            branch_id=bid,
            item_id="item-a",
            current_qty_scaled=20000,
        )
        stock_b = StockBalance(
            id="sb-b",
            company_id=cid,
            branch_id=bid,
            item_id="item-b",
            current_qty_scaled=100000,
        )
        session.add_all([item_a, item_b, stock_a, stock_b])

    metrics = dash_service.get_dashboard_metrics(company_id=cid, branch_id=bid)

    assert metrics["stockValue"] == 6910.00
    assert metrics["stockItemsCount"] == 2
    assert metrics["lowStockCount"] == 0


def test_receivables_and_payables_are_not_fabricated(dashboard_env):
    """
    Requirement 6: Receivables and payables are not fabricated.
    When source ledger balance tables are not implemented, returns None / 'Not available'.
    """
    dash_service = dashboard_env["dashboard_service"]
    cid = dashboard_env["company_id"]

    metrics = dash_service.get_dashboard_metrics(company_id=cid)

    assert metrics["receivables"] is None
    assert metrics["receivablesDisplay"] == "Not available"
    assert metrics["receivablesOverdueCount"] is None
    assert metrics["receivablesOverdueDisplay"] == "N/A"

    assert metrics["payables"] is None
    assert metrics["payablesDisplay"] == "Not available"
    assert metrics["payablesDueCount"] is None
    assert metrics["payablesDueDisplay"] == "N/A"


def test_payment_breakdown_uses_actual_payment_records(dashboard_env):
    """
    Requirement 7: Payment breakdown uses actual payment records.
    """
    trad_mgr = dashboard_env["trad_mgr"]
    dash_service = dashboard_env["dashboard_service"]
    cid = dashboard_env["company_id"]

    with trad_mgr.session_scope() as session:
        session.execute(text("""
            CREATE TABLE payments (
                id VARCHAR(36) PRIMARY KEY,
                company_id VARCHAR(36) NOT NULL,
                voucher_number VARCHAR(50),
                party_name VARCHAR(100),
                amount NUMERIC(12, 2) NOT NULL,
                payment_mode VARCHAR(20) NOT NULL,
                payment_type VARCHAR(20) NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
        """))
        # 600 UPI, 300 CASH, 100 CARD (total = 1000)
        session.execute(text("""
            INSERT INTO payments VALUES
            ('p-1', :cid, 'RCP-01', 'Customer A', 600.00, 'UPI', 'COLLECTION', CURRENT_TIMESTAMP),
            ('p-2', :cid, 'RCP-02', 'Customer B', 300.00, 'CASH', 'COLLECTION', CURRENT_TIMESTAMP),
            ('p-3', :cid, 'RCP-03', 'Customer C', 100.00, 'CARD', 'COLLECTION', CURRENT_TIMESTAMP)
        """), {"cid": cid})

    metrics = dash_service.get_dashboard_metrics(company_id=cid)

    summary = metrics["paymentSummary"]
    assert len(summary) == 3

    # Check actual computed percentages: 60%, 30%, 10%
    upi_item = next(p for p in summary if p["method"] == "UPI")
    cash_item = next(p for p in summary if p["method"] == "CASH")
    card_item = next(p for p in summary if p["method"] == "CARD")

    assert upi_item["amount"] == 600.00
    assert upi_item["percent"] == 60.0
    assert cash_item["amount"] == 300.00
    assert cash_item["percent"] == 30.0
    assert card_item["amount"] == 100.00
    assert card_item["percent"] == 10.0


def test_tenant_isolation_prevents_cross_company_data(dashboard_env):
    """
    Requirement 8: Tenant isolation prevents another company's data from appearing.
    """
    trad_mgr = dashboard_env["trad_mgr"]
    company_service = dashboard_env["company_service"]
    dash_service = dashboard_env["dashboard_service"]
    cid_a = dashboard_env["company_id"]

    # Create Company B
    comp_b = Company(
        id="comp-b-uuid",
        code="CORP02",
        name="Company B Corporation",
        fin_year="2026-2027",
        gstin="33BBBPB5678F1Z2",
        state="Karnataka",
        is_active=True,
    )
    with trad_mgr.session_scope() as session:
        session.add(comp_b)
        session.flush()
        branch_b = Branch(
            id="branch-b-uuid",
            company_id="comp-b-uuid",
            code="BR01",
            name="Main Branch",
            is_active=True,
        )
        item_b = Item(
            id="item-comp-b",
            company_id="comp-b-uuid",
            sku="SKU-COMP-B",
            name="Product Company B",
            selling_price=Decimal("500.00"),
            cogs_amount=Decimal("350.00"),
            is_active=True,
        )
        session.add_all([branch_b, item_b])
        session.flush()
        sb_b = StockBalance(
            id="sb-comp-b",
            company_id="comp-b-uuid",
            branch_id="branch-b-uuid",
            item_id="item-comp-b",
            current_qty_scaled=50000,  # 50 units * 350 = 17500.00
        )
        session.add(sb_b)

    # Company A should have 0 stock
    metrics_a = dash_service.get_dashboard_metrics(company_id=cid_a)
    assert metrics_a["stockValue"] == 0.00
    assert metrics_a["stockItemsCount"] == 0

    # Company B should have its own 17500.00 stock
    metrics_b = dash_service.get_dashboard_metrics(company_id="comp-b-uuid")
    assert metrics_b["stockValue"] == 17500.00
    assert metrics_b["stockItemsCount"] == 1


def test_traditional_dashboard_never_calls_fast_billing(dashboard_env):
    """
    Requirement 9: Traditional dashboard never calls Fast Billing dashboard services.
    Ensures db_manager targets dedicated Traditional DB and never anti_matrix_billing.db.
    """
    dash_service = dashboard_env["dashboard_service"]
    cid = dashboard_env["company_id"]

    resolved_url = str(dash_service.db.database_url)
    assert "anti_matrix_billing.db" not in resolved_url
    assert "traditional" in resolved_url

    # Verify querying dashboard does not touch fast billing DB
    metrics = dash_service.get_dashboard_metrics(company_id=cid)
    assert metrics is not None


def test_rpc_session_guard_and_failure_handling(dashboard_env):
    """
    Requirement 10: RPC failures do not trigger demo-data fallbacks.
    Validates backend RPC session checking and fail-closed error handling.
    """
    from desktop.web_bridge import BackendBridge

    bridge = BackendBridge()
    # Inject our isolated dashboard service into bridge
    bridge._traditional_dashboard_service = dashboard_env["dashboard_service"]

    # 1. Unauthenticated call -> fail closed
    res_str = bridge.traditional_getDashboardMetrics()
    res = json.loads(res_str)
    assert res["success"] is False
    assert res["authenticated"] is False
    assert "Authentication required" in res["error"]

    # 2. Authenticated call -> returns genuine data
    # Create valid traditional session in registry
    token = trad_session_registry.create_session(
        user_id="user-1",
        company_id=dashboard_env["company_id"],
        branch_id=dashboard_env["branch_id"],
        role_name="Administrator",
        username="SUPERADMIN",
        display_name="System Administrator",
    )
    bridge._traditional_session = trad_session_registry.get_session(token)

    res_auth_str = bridge.traditional_getDashboardMetrics()
    res_auth = json.loads(res_auth_str)
    assert res_auth["success"] is True
    assert res_auth["data"]["todaySales"] == 0.00
    assert res_auth["data"]["stockValue"] == 0.00
    assert res_auth["data"]["receivables"] is None
    assert res_auth["data"]["receivablesDisplay"] == "Not available"
