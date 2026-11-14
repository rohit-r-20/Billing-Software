"""
Test Suite: Traditional Billing Datetime & Timezone Consistency.

Verifies:
1. Naive UTC database timestamp versus aware UTC current time.
2. Aware UTC timestamp comparison.
3. Valid active reservation.
4. Expired reservation rejection.
5. Reservation ownership mismatch.
6. Successful barcode promotion.
7. Failed product validation preserves the reservation.
8. Product save works with the SQLite Traditional Billing database.
"""

import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
import zoneinfo
import pytest
from sqlalchemy import select, and_, delete
from alembic.config import Config
from alembic import command

from db.traditional_database import TraditionalDatabaseManager
from db.traditional_models import (
    Company,
    Branch,
    User,
    Item,
    ItemBarcode,
    BarcodeReservation,
    utc_now,
    ensure_utc,
    UTCDateTime,
)
from services.traditional_company_service import TraditionalCompanyService
from services.traditional_product_service import TraditionalProductService


@pytest.fixture
def tz_env(tmp_path):
    """Isolated SQLite database with Alembic schema for datetime & timezone tests."""
    db_file = tmp_path / "test_traditional_tz.db"
    db_url = f"sqlite:///{db_file}"

    ini_path = Path("traditional_alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    trad_mgr = TraditionalDatabaseManager(database_url=db_url)
    company_service = TraditionalCompanyService(db_manager=trad_mgr)
    product_service = TraditionalProductService(db_manager=trad_mgr)

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
        "product_service": product_service,
        "company_id": company_info["companyId"],
        "user_id": company_info["adminUserId"],
        "db_file": db_file,
    }

    trad_mgr.close()


def test_naive_utc_database_timestamp_versus_aware_utc_current_time():
    """
    Requirement 1: Naive UTC database timestamp versus aware UTC current time.
    Normalizing naive UTC timestamps originating from SQLite storage ensures they
    are treated as UTC (replace tzinfo=timezone.utc), never converted as local time,
    and compare cleanly against aware UTC current time.
    """
    # Simulate a naive UTC timestamp loaded from SQLite storage
    naive_db_dt = datetime(2026, 11, 14, 10, 30, 0)
    assert naive_db_dt.tzinfo is None

    # Normalization helper
    aware_dt = ensure_utc(naive_db_dt)
    assert aware_dt is not None
    assert aware_dt.tzinfo == timezone.utc
    # Confirm timestamp was NOT shifted by local timezone offset (e.g. IST +5:30)
    assert aware_dt.hour == 10
    assert aware_dt.minute == 30

    # Compare directly with aware UTC current time - must not raise TypeError
    current_utc = utc_now()
    # Comparison succeeds without error
    is_past = aware_dt < current_utc
    assert isinstance(is_past, bool)


def test_aware_utc_timestamp_comparison():
    """
    Requirement 2: Aware UTC timestamp comparison.
    Timezone-aware timestamps (both UTC and other timezones like Asia/Kolkata)
    are accurately converted to UTC and compare mathematically correctly.
    """
    utc_instant = datetime(2026, 11, 14, 12, 0, 0, tzinfo=timezone.utc)

    # Equivalent instant in IST (+05:30)
    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    ist_instant = datetime(2026, 11, 14, 17, 30, 0, tzinfo=ist)

    norm_ist = ensure_utc(ist_instant)
    assert norm_ist.tzinfo == timezone.utc
    assert norm_ist.hour == 12
    assert norm_ist.minute == 0
    assert norm_ist == utc_instant

    # Non-equivalent instant comparison
    past_ist = datetime(2026, 11, 14, 16, 0, 0, tzinfo=ist)  # 10:30 UTC
    norm_past = ensure_utc(past_ist)
    assert norm_past < utc_instant


def test_valid_active_reservation(tz_env):
    """
    Requirement 3: Valid active reservation.
    Generating a barcode and saving a product with that barcode succeeds cleanly
    without 'can't compare offset-naive and offset-aware datetimes'.
    """
    prod_svc = tz_env["product_service"]
    cid = tz_env["company_id"]
    uid = tz_env["user_id"]

    # 1. Allocate reservation
    barcode = prod_svc.generate_barcode(cid, uid)
    assert barcode.startswith("AM")

    # 2. Save product with the reserved barcode
    product_data = {
        "name": "Murukku Crisp",
        "sku": "MURUKKU-CRISP-01",
        "barcode": barcode,
        "sellingPrice": "45.00",
        "cogsAmount": "28.00",
    }
    saved = prod_svc.save_product(cid, uid, product_data)
    assert saved["id"] is not None
    assert saved["sku"] == "MURUKKU-CRISP-01"
    assert barcode in saved["barcodes"]


def test_expired_reservation_rejection(tz_env):
    """
    Requirement 4: Expired reservation rejection.
    A reservation whose expires_at is in the past is strictly rejected with a clear ValueError.
    Does not silently extend expired reservations.
    """
    trad_mgr = tz_env["trad_mgr"]
    prod_svc = tz_env["product_service"]
    cid = tz_env["company_id"]
    uid = tz_env["user_id"]

    expired_bc = "AMEXPIRED001"

    # Insert an expired reservation (expired 5 minutes ago)
    with trad_mgr.session_scope() as session:
        res = BarcodeReservation(
            id="expired-res-uuid",
            company_id=cid,
            barcode=expired_bc,
            reserved_by=uid,
            expires_at=utc_now() - timedelta(minutes=5),
            created_at=utc_now() - timedelta(minutes=20),
        )
        session.add(res)

    product_data = {
        "name": "Expired Barcode Product",
        "sku": "EXP-BC-01",
        "barcode": expired_bc,
        "sellingPrice": "50.00",
    }

    with pytest.raises(ValueError, match="has expired"):
        prod_svc.save_product(cid, uid, product_data)


def test_reservation_ownership_mismatch(tz_env):
    """
    Requirement 5: Reservation ownership mismatch.
    Attempting to save a product with a barcode reserved by another user fails with PermissionError.
    """
    trad_mgr = tz_env["trad_mgr"]
    prod_svc = tz_env["product_service"]
    cid = tz_env["company_id"]
    uid_a = tz_env["user_id"]
    uid_b = "user-other-b-uuid"

    reserved_bc = "AMOTHERUSER1"

    # Insert User B and a reservation owned by User B
    with trad_mgr.session_scope() as session:
        user_b = User(
            id=uid_b,
            company_id=cid,
            username="CASHIER02",
            password_hash="fake-hash-placeholder",
            role_name="Administrator",
            is_active=True,
        )
        session.add(user_b)
        session.flush()

        res = BarcodeReservation(
            id="other-user-res-uuid",
            company_id=cid,
            barcode=reserved_bc,
            reserved_by=uid_b,
            expires_at=utc_now() + timedelta(minutes=15),
            created_at=utc_now(),
        )
        session.add(res)

    # User A tries to consume User B's reservation
    product_data = {
        "name": "Steolen Barcode Product",
        "sku": "STEAL-BC-01",
        "barcode": reserved_bc,
        "sellingPrice": "50.00",
    }

    with pytest.raises(PermissionError, match="reserved by another user"):
        prod_svc.save_product(cid, uid_a, product_data)


def test_successful_barcode_promotion(tz_env):
    """
    Requirement 6: Successful barcode promotion.
    Active reservation is promoted to item_barcodes and atomically deleted from barcode_reservations.
    """
    trad_mgr = tz_env["trad_mgr"]
    prod_svc = tz_env["product_service"]
    cid = tz_env["company_id"]
    uid = tz_env["user_id"]

    bc = prod_svc.generate_barcode(cid, uid)

    # Verify reservation exists before save
    with trad_mgr.session_scope() as session:
        r_before = session.scalar(
            select(BarcodeReservation).where(
                and_(BarcodeReservation.company_id == cid, BarcodeReservation.barcode == bc)
            )
        )
        assert r_before is not None

    # Save product
    saved = prod_svc.save_product(
        cid,
        uid,
        {
            "name": "Promoted Product",
            "sku": "PROM-BC-01",
            "barcode": bc,
            "sellingPrice": "30.00",
        },
    )

    # Verify reservation deleted and promoted to item_barcodes
    with trad_mgr.session_scope() as session:
        r_after = session.scalar(
            select(BarcodeReservation).where(
                and_(BarcodeReservation.company_id == cid, BarcodeReservation.barcode == bc)
            )
        )
        assert r_after is None, "Reservation must be deleted upon promotion"

        bc_row = session.scalar(
            select(ItemBarcode).where(
                and_(ItemBarcode.company_id == cid, ItemBarcode.barcode == bc)
            )
        )
        assert bc_row is not None
        assert bc_row.item_id == saved["id"]


def test_failed_product_validation_preserves_reservation(tz_env):
    """
    Requirement 7: Failed product validation preserves the reservation.
    If product creation fails business validation (e.g. selling_price > mrp),
    the reservation is NOT consumed or deleted.
    """
    trad_mgr = tz_env["trad_mgr"]
    prod_svc = tz_env["product_service"]
    cid = tz_env["company_id"]
    uid = tz_env["user_id"]

    bc = prod_svc.generate_barcode(cid, uid)

    # Attempt to save with invalid pricing: Selling Price (100) > MRP (50)
    with pytest.raises(ValueError, match="cannot exceed MRP"):
        prod_svc.save_product(
            cid,
            uid,
            {
                "name": "Invalid Price Product",
                "sku": "INVALID-PRICE-01",
                "barcode": bc,
                "sellingPrice": "100.00",
                "mrp": "50.00",
            },
        )

    # Verify reservation is STILL present and intact
    with trad_mgr.session_scope() as session:
        res = session.scalar(
            select(BarcodeReservation).where(
                and_(BarcodeReservation.company_id == cid, BarcodeReservation.barcode == bc)
            )
        )
        assert res is not None, "Reservation must be preserved on validation failure"
        assert res.reserved_by == uid

    # User can subsequently fix the validation error and successfully save with the same barcode
    saved = prod_svc.save_product(
        cid,
        uid,
        {
            "name": "Valid Price Product",
            "sku": "VALID-PRICE-01",
            "barcode": bc,
            "sellingPrice": "40.00",
            "mrp": "50.00",
        },
    )
    assert saved["id"] is not None
    assert bc in saved["barcodes"]


def test_product_save_works_with_sqlite_traditional_billing_database(tz_env):
    """
    Requirement 8: Product save works with the SQLite Traditional Billing database.
    Direct reproduction of the reported Murukku product scenario with generated barcode AMWYSBJ4PWPX.
    """
    trad_mgr = tz_env["trad_mgr"]
    prod_svc = tz_env["product_service"]
    cid = tz_env["company_id"]
    uid = tz_env["user_id"]

    # Explicit barcode as reported in bug description
    reported_bc = "AMWYSBJ4PWPX"

    # Reserve the barcode via reservation table in SQLite
    with trad_mgr.session_scope() as session:
        session.add(
            BarcodeReservation(
                id="res-murukku-uuid",
                company_id=cid,
                barcode=reported_bc,
                reserved_by=uid,
                expires_at=utc_now() + timedelta(minutes=15),
                created_at=utc_now(),
            )
        )

    product_payload = {
        "name": "Murukku",
        "alias": reported_bc,
        "barcode": reported_bc,
        "sku": reported_bc,
        "sellingPrice": "50.00",
        "cogsAmount": "30.00",
        "unit": "Pcs.",
        "category": "Snacks",
    }

    # Save product in SQLite Traditional Billing database
    saved_product = prod_svc.save_product(cid, uid, product_payload)

    assert saved_product["id"] is not None
    assert saved_product["name"] == "Murukku"
    assert saved_product["sku"] == reported_bc
    assert reported_bc in saved_product["barcodes"]
    assert saved_product["sellingPrice"] == "50.00"
    assert saved_product["cogsAmount"] == "30.00"

    # Verify retrieval from database
    retrieved = prod_svc.get_product(cid, saved_product["id"])
    assert retrieved is not None
    assert retrieved["name"] == "Murukku"
    assert reported_bc in retrieved["barcodes"]
