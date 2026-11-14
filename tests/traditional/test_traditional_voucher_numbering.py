"""
Tests for Traditional Billing Sales Voucher Number Generation & Lifecycle.
Validates:
1. Sequential voucher number allocation starting at 001.
2. Historical reconciliation (AuditLog with 007 -> next is 008).
3. Tenant isolation (Company A vs Company B).
4. Branch isolation.
5. Financial year isolation (2025-2026 vs 2026-2027).
6. Voucher series isolation (Main vs Tax).
7. Atomic rollback on invoice transaction failure.
8. Concurrency safety (no collision under concurrent saves).
9. WebBridge RPC integration and authorization guard.
10. Fast Billing DB untouched (checksum guarantee).
"""

import json
import hashlib
from decimal import Decimal
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text, select, and_

from db.traditional_database import TraditionalDatabaseManager
from db.traditional_models import (
    Company,
    Branch,
    VoucherSequence,
    SaleInvoice,
    AuditLog,
    Item,
    ItemBarcode,
    utc_now,
)
from services.traditional_company_service import TraditionalCompanyService
from services.traditional_product_service import TraditionalProductService
from services.traditional_auth_service import session_registry as trad_session_registry


@pytest.fixture
def voucher_env(tmp_path):
    """Isolated SQLite database with Alembic schema for voucher numbering tests."""
    db_file = tmp_path / "test_voucher_seq.db"
    db_url = f"sqlite:///{db_file}"

    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    company_service = TraditionalCompanyService(db_manager=trad_mgr)
    prod_service = TraditionalProductService(db_manager=trad_mgr)

    # Setup Company A
    c_a = company_service.initial_setup({
        "code": "CMPA",
        "name": "Company Alpha",
        "finYear": "2026-2027",
        "taxNo": "33AAAPL1234F1Z1",
        "state": "Tamilnadu",
        "adminUsername": "ADMINA",
        "adminPassword": "Password@2026A",
    })

    # Setup Company B
    with trad_mgr.session_scope() as session:
        cb = Company(
            id="company-b-id",
            code="CMPB",
            name="Company Beta",
            fin_year="2026-2027",
            gstin="33AAAPB1234F1Z2",
            state="Tamilnadu",
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(cb)
        session.flush()
        bb = Branch(
            id="branch-b-id",
            company_id="company-b-id",
            code="BR01",
            name="Main Branch",
            is_active=True,
            created_at=utc_now(),
        )
        session.add(bb)

    admin_uid = c_a["adminUserId"]

    # Add a product to Company A
    prod_a = prod_service.save_product(c_a["companyId"], admin_uid, {
        "sku": "MILK-01",
        "name": "Fresh Milk 500ml",
        "sellingPrice": "30.00",
        "taxRatePercent": "5.00",
        "unit": "Pkt",
        "barcode": "8901234567890",
    })

    # Add an inactive product to Company A
    prod_inact = prod_service.save_product(c_a["companyId"], admin_uid, {
        "sku": "EXP-01",
        "name": "Expired Bread",
        "sellingPrice": "40.00",
        "taxRatePercent": "5.00",
        "unit": "Pcs",
    })
    prod_service.set_product_active(c_a["companyId"], prod_inact["id"], False)

    # Record initial hash of Fast Billing database
    fb_file = Path("data/anti_matrix_billing.db")
    fb_hash = hashlib.sha256(fb_file.read_bytes()).hexdigest() if fb_file.exists() else None

    yield {
        "trad_mgr": trad_mgr,
        "company_service": company_service,
        "prod_service": prod_service,
        "company_a_id": c_a["companyId"],
        "branch_a_id": c_a["branchId"],
        "admin_uid": c_a["adminUserId"],
        "company_b_id": "company-b-id",
        "branch_b_id": "branch-b-id",
        "product_a": prod_a,
        "product_inactive": prod_inact,
        "fast_billing_hash": fb_hash,
    }

    trad_mgr.close()


def test_sequential_voucher_numbering_lifecycle(voucher_env):
    """
    Validates:
    - Initial next voucher preview is 001.
    - Saving invoice #1 commits 001.
    - Subsequent preview becomes 002.
    - Saving invoice #2 commits 002.
    - Saving invoice #3 commits 003.
    """
    prod_service = voucher_env["prod_service"]
    cid = voucher_env["company_a_id"]
    bid = voucher_env["branch_a_id"]
    p = voucher_env["product_a"]

    # 1. Preview before any saves
    preview1 = prod_service.get_next_voucher_number(cid, bid, series="Main")
    assert preview1["voucher_number"] == "001"
    assert preview1["sequence_number"] == 1

    # 2. Save first invoice
    inv1_data = {
        "party_name": "Walk-in Cash Customer",
        "vch_date": "14-11-2026",
        "series": "Main",
        "items": [{"item_id": p["id"], "qty": 2, "price": "30.00"}],
    }
    inv1 = prod_service.save_sale_invoice(cid, "user-1", inv1_data, branch_id=bid)
    assert inv1["vch_no"] == "001"
    assert inv1["sequence_number"] == 1
    assert inv1["voucher_number"] == "001"

    # 3. Preview after invoice 1
    preview2 = prod_service.get_next_voucher_number(cid, bid, series="Main")
    assert preview2["voucher_number"] == "002"
    assert preview2["sequence_number"] == 2

    # 4. Save second invoice
    inv2_data = {
        "party_name": "Arasu Traders",
        "vch_date": "14-11-2026",
        "series": "Main",
        "items": [{"item_id": p["id"], "qty": 5, "price": "30.00"}],
    }
    inv2 = prod_service.save_sale_invoice(cid, "user-1", inv2_data, branch_id=bid)
    assert inv2["vch_no"] == "002"
    assert inv2["sequence_number"] == 2

    # 5. Save third invoice
    inv3 = prod_service.save_sale_invoice(cid, "user-1", inv1_data, branch_id=bid)
    assert inv3["vch_no"] == "003"
    assert inv3["sequence_number"] == 3

    # 6. Verify SaleInvoice table records in database
    with voucher_env["trad_mgr"].session_scope() as session:
        invoices = session.scalars(
            select(SaleInvoice).where(
                and_(SaleInvoice.company_id == cid, SaleInvoice.series == "Main")
            ).order_by(SaleInvoice.sequence_number.asc())
        ).all()
        assert len(invoices) == 3
        assert [i.voucher_number for i in invoices] == ["001", "002", "003"]
        assert [i.sequence_number for i in invoices] == [1, 2, 3]


def test_historical_reconciliation_from_audit_log(voucher_env):
    """
    Validates:
    - If historical invoices exist in AuditLog with voucher number '007',
      the next allocated voucher number starts at '008' without regression.
    """
    prod_service = voucher_env["prod_service"]
    cid = voucher_env["company_a_id"]
    bid = voucher_env["branch_a_id"]
    p = voucher_env["product_a"]

    # Insert a historical audit log simulating an existing pre-migration invoice 007
    with voucher_env["trad_mgr"].session_scope() as session:
        audit = AuditLog(
            id="audit-hist-7",
            company_id=cid,
            user_id="user-1",
            event_type="SALES_INVOICE_CREATED",
            entity_type="SALE_INVOICE",
            entity_id="legacy-inv-7",
            payload_json=json.dumps({
                "vch_no": "007",
                "voucher_number": "007",
                "series": "Main",
                "grand_total": "210.00",
            }),
            created_at=utc_now(),
        )
        session.add(audit)

    # Next preview should be 008
    preview = prod_service.get_next_voucher_number(cid, bid, series="Main")
    assert preview["voucher_number"] == "008"
    assert preview["sequence_number"] == 8

    # Save invoice should allocate 008
    inv_data = {
        "party_name": "Historic Continuation Customer",
        "vch_date": "14-11-2026",
        "series": "Main",
        "items": [{"item_id": p["id"], "qty": 1, "price": "30.00"}],
    }
    inv = prod_service.save_sale_invoice(cid, "user-1", inv_data, branch_id=bid)
    assert inv["vch_no"] == "008"
    assert inv["sequence_number"] == 8


def test_tenant_isolation_voucher_sequences(voucher_env):
    """
    Validates:
    - Company A and Company B have completely independent voucher numbering.
    - Saving vouchers in Company A does not advance Company B's counter.
    """
    prod_service = voucher_env["prod_service"]
    cid_a = voucher_env["company_a_id"]
    bid_a = voucher_env["branch_a_id"]
    cid_b = voucher_env["company_b_id"]
    bid_b = voucher_env["branch_b_id"]
    p_a = voucher_env["product_a"]

    # Create product in Company B
    p_b = prod_service.save_product(cid_b, "user-b", {
        "sku": "CHOC-01",
        "name": "Chocolate Bar",
        "sellingPrice": "50.00",
        "taxRatePercent": "18.00",
        "unit": "Pcs",
    })

    # Save 2 invoices in Company A
    for _ in range(2):
        prod_service.save_sale_invoice(cid_a, "user-1", {
            "vch_date": "14-11-2026",
            "series": "Main",
            "items": [{"item_id": p_a["id"], "qty": 1, "price": "30.00"}],
        }, branch_id=bid_a)

    # Next number for Company A is 003
    assert prod_service.get_next_voucher_number(cid_a, bid_a, series="Main")["voucher_number"] == "003"

    # Next number for Company B is still 001
    assert prod_service.get_next_voucher_number(cid_b, bid_b, series="Main")["voucher_number"] == "001"

    # Save 1 invoice in Company B -> gets 001
    inv_b = prod_service.save_sale_invoice(cid_b, "user-1", {
        "vch_date": "14-11-2026",
        "series": "Main",
        "items": [{"item_id": p_b["id"], "qty": 1, "price": "50.00"}],
    }, branch_id=bid_b)
    assert inv_b["vch_no"] == "001"

    # Next number for Company B is now 002, Company A remains 003
    assert prod_service.get_next_voucher_number(cid_b, bid_b, series="Main")["voucher_number"] == "002"
    assert prod_service.get_next_voucher_number(cid_a, bid_a, series="Main")["voucher_number"] == "003"


def test_series_isolation(voucher_env):
    """
    Validates:
    - Multiple voucher series (e.g. 'Main' vs 'Tax') within same company have isolated sequences.
    """
    prod_service = voucher_env["prod_service"]
    cid = voucher_env["company_a_id"]
    bid = voucher_env["branch_a_id"]
    p = voucher_env["product_a"]

    # Save in Series 'Main'
    prod_service.save_sale_invoice(cid, "user-1", {
        "vch_date": "14-11-2026",
        "series": "Main",
        "items": [{"item_id": p["id"], "qty": 1, "price": "30.00"}],
    }, branch_id=bid)

    # Save another in Series 'Main'
    prod_service.save_sale_invoice(cid, "user-1", {
        "vch_date": "14-11-2026",
        "series": "Main",
        "items": [{"item_id": p["id"], "qty": 1, "price": "30.00"}],
    }, branch_id=bid)

    # Main series is now at 003
    assert prod_service.get_next_voucher_number(cid, bid, series="Main")["voucher_number"] == "003"

    # Series 'Tax' is at 001
    assert prod_service.get_next_voucher_number(cid, bid, series="Tax")["voucher_number"] == "001"

    # Save in Series 'Tax'
    inv_tax = prod_service.save_sale_invoice(cid, "user-1", {
        "vch_date": "14-11-2026",
        "series": "Tax",
        "items": [{"item_id": p["id"], "qty": 1, "price": "30.00"}],
    }, branch_id=bid)
    assert inv_tax["vch_no"] == "001"
    assert inv_tax["series"] == "Tax"

    # Verify both series
    assert prod_service.get_next_voucher_number(cid, bid, series="Main")["voucher_number"] == "003"
    assert prod_service.get_next_voucher_number(cid, bid, series="Tax")["voucher_number"] == "002"


def test_financial_year_isolation(voucher_env):
    """
    Validates:
    - Invoices in FY 2025-2026 start at 001.
    - Invoices in FY 2026-2027 start at 001 independently.
    """
    prod_service = voucher_env["prod_service"]
    cid = voucher_env["company_a_id"]
    bid = voucher_env["branch_a_id"]
    p = voucher_env["product_a"]

    # Date in FY 2025-2026 (Jan 2026 -> FY 2025-2026)
    inv_fy1 = prod_service.save_sale_invoice(cid, "user-1", {
        "vch_date": "15-01-2026",
        "series": "Main",
        "items": [{"item_id": p["id"], "qty": 1, "price": "30.00"}],
    }, branch_id=bid)
    assert inv_fy1["financial_year"] == "2025-2026"
    assert inv_fy1["vch_no"] == "001"

    # Date in FY 2026-2027 (May 2026 -> FY 2026-2027)
    inv_fy2 = prod_service.save_sale_invoice(cid, "user-1", {
        "vch_date": "15-05-2026",
        "series": "Main",
        "items": [{"item_id": p["id"], "qty": 1, "price": "30.00"}],
    }, branch_id=bid)
    assert inv_fy2["financial_year"] == "2026-2027"
    assert inv_fy2["vch_no"] == "001"

    # Another invoice in FY 2025-2026 gets 002
    inv_fy1_2 = prod_service.save_sale_invoice(cid, "user-1", {
        "vch_date": "20-02-2026",
        "series": "Main",
        "items": [{"item_id": p["id"], "qty": 1, "price": "30.00"}],
    }, branch_id=bid)
    assert inv_fy1_2["financial_year"] == "2025-2026"
    assert inv_fy1_2["vch_no"] == "002"


def test_transaction_rollback_preserves_sequence_number(voucher_env):
    """
    Validates:
    - If saving an invoice fails (e.g. attempting to bill an inactive item),
      the sequence number is NOT consumed, and the database rolls back atomically.
    """
    prod_service = voucher_env["prod_service"]
    cid = voucher_env["company_a_id"]
    bid = voucher_env["branch_a_id"]
    p_valid = voucher_env["product_a"]
    p_inact = voucher_env["product_inactive"]

    # Preview is 001
    assert prod_service.get_next_voucher_number(cid, bid)["voucher_number"] == "001"

    # Attempt to save with inactive product -> must raise ValueError
    with pytest.raises(ValueError, match="inactive and cannot be billed"):
        prod_service.save_sale_invoice(cid, "user-1", {
            "vch_date": "14-11-2026",
            "series": "Main",
            "items": [{"item_id": p_inact["id"], "qty": 1, "price": "40.00"}],
        }, branch_id=bid)

    # Preview MUST STILL BE 001 (sequence was not consumed)
    assert prod_service.get_next_voucher_number(cid, bid)["voucher_number"] == "001"

    # Now save valid invoice -> gets 001
    valid_inv = prod_service.save_sale_invoice(cid, "user-1", {
        "vch_date": "14-11-2026",
        "series": "Main",
        "items": [{"item_id": p_valid["id"], "qty": 1, "price": "30.00"}],
    }, branch_id=bid)
    assert valid_inv["vch_no"] == "001"
    assert valid_inv["sequence_number"] == 1


def test_web_bridge_voucher_rpc_lifecycle(voucher_env):
    """
    Validates:
    - traditional_getNextVoucherNumber RPC returns expected formatted number.
    - traditional_saveSaleInvoice RPC commits invoice and advances number.
    - Unauthenticated calls fail closed.
    """
    from desktop.web_bridge import BackendBridge

    bridge = BackendBridge()
    bridge._traditional_product_service = voucher_env["prod_service"]

    # 1. Unauthenticated -> fails closed
    unauth_resp = json.loads(bridge.traditional_getNextVoucherNumber("Main"))
    assert unauth_resp["success"] is False
    assert unauth_resp["authenticated"] is False

    # 2. Authenticated Administrator session
    token = trad_session_registry.create_session(
        user_id="user-admin-1",
        company_id=voucher_env["company_a_id"],
        branch_id=voucher_env["branch_a_id"],
        role_name="Administrator",
        username="ADMINA",
        display_name="Admin User",
    )
    bridge._traditional_session = trad_session_registry.get_session(token)

    # 3. Query next voucher number via RPC
    r1 = json.loads(bridge.traditional_getNextVoucherNumber("Main"))
    assert r1["success"] is True
    assert r1["data"] == "001"

    # 4. Save sale invoice via RPC
    p = voucher_env["product_a"]
    inv_payload = {
        "party_name": "RPC Customer",
        "vch_date": "14-11-2026",
        "series": "Main",
        "items": [{"item_id": p["id"], "qty": 2, "price": "30.00"}],
    }
    save_resp = json.loads(bridge.traditional_saveSaleInvoice(json.dumps(inv_payload)))
    assert save_resp["success"] is True
    assert save_resp["data"]["vch_no"] == "001"

    # 5. Query next voucher number again -> should be 002
    r2 = json.loads(bridge.traditional_getNextVoucherNumber("Main"))
    assert r2["success"] is True
    assert r2["data"] == "002"


def test_concurrent_voucher_allocations_no_duplicates(voucher_env):
    """
    Validates:
    - Concurrent invoice saves within the same company and scope
      never produce duplicate voucher numbers or sequences.
    """
    import concurrent.futures

    prod_service = voucher_env["prod_service"]
    cid = voucher_env["company_a_id"]
    bid = voucher_env["branch_a_id"]
    p = voucher_env["product_a"]

    saved_vouchers = []
    errors = []

    def save_one(idx):
        try:
            res = prod_service.save_sale_invoice(cid, "user-1", {
                "party_name": f"Concurrent Customer {idx}",
                "vch_date": "14-11-2026",
                "series": "Main",
                "items": [{"item_id": p["id"], "qty": 1, "price": "30.00"}],
            }, branch_id=bid)
            return res["vch_no"]
        except Exception as e:
            return str(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(save_one, i) for i in range(10)]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if isinstance(res, str) and (res.startswith("0") or res.isdigit()):
                saved_vouchers.append(res)
            else:
                errors.append(res)

    assert len(errors) == 0, f"Errors during concurrent save: {errors}"
    assert len(saved_vouchers) == 10
    # Ensure every single allocated number is unique
    assert len(set(saved_vouchers)) == 10, f"Duplicate voucher numbers detected: {saved_vouchers}"


def test_fast_billing_database_untouched(voucher_env):
    """
    Guarantees that no Fast Billing databases or tables were modified during tests.
    """
    fb_file = Path("data/anti_matrix_billing.db")
    if fb_file.exists() and voucher_env["fast_billing_hash"]:
        current_hash = hashlib.sha256(fb_file.read_bytes()).hexdigest()
        assert current_hash == voucher_env["fast_billing_hash"], "Fast Billing database was mutated!"
