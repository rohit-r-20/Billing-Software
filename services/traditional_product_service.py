"""
Traditional Billing Product & Barcode Master Service.
Enforces exact Decimal pricing, nullable MRP invariants, retail barcode checksums,
and concurrency-safe barcode reservation and promotion.
"""

import uuid
import secrets
import re
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import select, and_, or_, delete, func

from db.traditional_database import traditional_db_manager, TraditionalDatabaseManager
from db.traditional_models import (
    Company,
    Branch,
    User,
    Item,
    ItemBarcode,
    BarcodeReservation,
    AuditLog,
    VoucherSequence,
    SaleInvoice,
    utc_now,
    ensure_utc,
)
from core.logging_config import logger

BARCODE_CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 32 unambiguous characters


def validate_barcode_checksum(barcode: str) -> bool:
    """Validates standard retail barcode checksums (EAN-13, UPC-A, EAN-8)."""
    digits = [int(c) for c in barcode]
    if len(digits) == 13:
        # EAN-13: sum odd digits * 1, even digits * 3 (from right to left, excluding check digit)
        check = digits[-1]
        calc = sum(d * (3 if i % 2 == 1 else 1) for i, d in enumerate(digits[:-1]))
        mod = (10 - (calc % 10)) % 10
        return check == mod
    elif len(digits) == 12:
        # UPC-A: odd positions * 3, even positions * 1
        check = digits[-1]
        calc = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(digits[:-1]))
        mod = (10 - (calc % 10)) % 10
        return check == mod
    elif len(digits) == 8:
        # EAN-8: odd positions * 3, even positions * 1
        check = digits[-1]
        calc = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(digits[:-1]))
        mod = (10 - (calc % 10)) % 10
        return check == mod
    return True


def validate_barcode_format(barcode: str) -> str:
    """Validates supported barcode formats (EAN-13, UPC-A, EAN-8, Code 128 / SKU)."""
    clean = str(barcode or "").strip().upper()
    if not clean:
        raise ValueError("Barcode cannot be empty.")
    if " " in clean:
        raise ValueError("Barcode cannot contain spaces.")

    # Numeric barcodes
    if clean.isdigit():
        if len(clean) in (8, 12, 13):
            if not validate_barcode_checksum(clean):
                raise ValueError(f"Invalid barcode checksum for standard format: {clean}")
            return clean
        elif 3 <= len(clean) <= 50:
            return clean
        else:
            raise ValueError(f"Numeric barcode length ({len(clean)}) must be between 3 and 50 digits.")

    # Alphanumeric barcodes (Code 128 / custom SKU)
    if not re.match(r"^[A-Z0-9_\-\.]{3,50}$", clean):
        raise ValueError("Alphanumeric barcode must contain only letters, numbers, hyphens, and underscores (3-50 chars).")

    return clean


def parse_decimal(val: Any, field_name: str, required: bool = True) -> Optional[Decimal]:
    """Parse exact Decimal value with 2-digit quantization, strictly rejecting float."""
    if val is None or str(val).strip() == "":
        if required:
            raise ValueError(f"'{field_name}' is required.")
        return None

    if isinstance(val, float):
        raise TypeError(f"'{field_name}' cannot be passed as float to prevent precision drift; pass string or Decimal.")

    try:
        d = Decimal(str(val).strip()).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        raise ValueError(f"'{field_name}' must be a valid numeric amount.")

    if d < Decimal("0.00"):
        raise ValueError(f"'{field_name}' cannot be negative.")

    return d


class TraditionalProductService:
    def __init__(self, db_manager: Optional[TraditionalDatabaseManager] = None):
        self.db = db_manager or traditional_db_manager

    def generate_barcode(self, company_id: str, user_id: str) -> str:
        """
        Generates 10 independent random characters prefixed with AM and reserves it
        for 15 minutes in barcode_reservations.
        """
        with self.db.session_scope() as session:
            # 1. Purge expired reservations
            session.execute(
                delete(BarcodeReservation).where(
                    and_(
                        BarcodeReservation.company_id == company_id,
                        BarcodeReservation.expires_at < utc_now(),
                    )
                )
            )

            # 2. Allocation loop with up to 5 attempts
            for _ in range(5):
                random_part = "".join(secrets.choice(BARCODE_CHARSET) for _ in range(10))
                candidate = f"AM{random_part}"

                # Check permanent barcodes
                perm_exists = session.scalar(
                    select(ItemBarcode.id).where(
                        and_(ItemBarcode.company_id == company_id, ItemBarcode.barcode == candidate)
                    )
                )
                if perm_exists:
                    continue

                # Check active reservations
                res_exists = session.scalar(
                    select(BarcodeReservation.id).where(
                        and_(BarcodeReservation.company_id == company_id, BarcodeReservation.barcode == candidate)
                    )
                )
                if res_exists:
                    continue

                # Create reservation
                reservation = BarcodeReservation(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    barcode=candidate,
                    reserved_by=user_id,
                    expires_at=utc_now() + timedelta(minutes=15),
                    created_at=utc_now(),
                )
                session.add(reservation)
                session.flush()
                return candidate

            raise RuntimeError("Unable to allocate unique barcode after 5 attempts. Please retry.")

    @staticmethod
    def _format_product_dict(item: Item, barcodes: List[str]) -> Dict[str, Any]:
        """Canonical dictionary representation for a Traditional product."""
        selling_price_str = str(item.selling_price)
        cogs_str = str(item.cogs_amount) if item.cogs_amount is not None else "0.00"
        mrp_str = str(item.mrp) if item.mrp is not None else None
        min_sales_price_str = str(item.min_sales_price) if item.min_sales_price is not None else None
        tax_rate_str = str(item.tax_rate_percent) if item.tax_rate_percent is not None else "0.00"

        return {
            "id": item.id,
            "sku": item.sku,
            "alias": item.sku,
            "name": item.name,
            "printName": item.print_name or item.name,
            "print_name": item.print_name or item.name,
            "unit": item.unit,
            "category": item.category,
            "item_group": item.category,
            "group": item.category,
            "hsn": item.hsn,
            "taxCategory": item.tax_category,
            "tax_category": item.tax_category,
            "taxRatePercent": tax_rate_str,
            "tax_rate_percent": tax_rate_str,
            "tax_rate": tax_rate_str,
            # Database selling price (exact Decimal representation)
            "sellingPrice": selling_price_str,
            "selling_price": selling_price_str,
            "salesPrice": selling_price_str,
            "sales_price": selling_price_str,
            # COGS / Purchase Cost (strictly separated from selling price)
            "cogsAmount": cogs_str,
            "cogs_amount": cogs_str,
            "purc_price": cogs_str,
            "mrp": mrp_str,
            "minSalesPrice": min_sales_price_str,
            "min_sales_price": min_sales_price_str,
            "barcodes": list(barcodes),
            "primary_barcode": barcodes[0] if barcodes else item.sku,
            "barcode": barcodes[0] if barcodes else item.sku,
            "isActive": item.is_active,
            "is_active": item.is_active,
        }

    def list_products(
        self,
        company_id: str,
        search_term: Optional[str] = None,
        category: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """List products with barcodes and exact pricing."""
        with self.db.read_session_scope() as session:
            query = select(Item).where(Item.company_id == company_id)

            if active_only:
                query = query.where(Item.is_active == True)

            if category and category.strip():
                query = query.where(Item.category == category.strip())

            if search_term and search_term.strip():
                st = f"%{search_term.strip()}%"
                barcode_item_ids = select(ItemBarcode.item_id).where(
                    and_(
                        ItemBarcode.company_id == company_id,
                        ItemBarcode.barcode.ilike(st),
                    )
                )
                query = query.where(
                    or_(
                        Item.sku.ilike(st),
                        Item.name.ilike(st),
                        Item.print_name.ilike(st),
                        Item.id.in_(barcode_item_ids),
                    )
                )

            query = query.order_by(Item.name.asc())
            items = session.scalars(query).all()

            # Batch load barcodes
            item_ids = [i.id for i in items]
            barcodes_map: Dict[str, List[str]] = {i_id: [] for i_id in item_ids}
            if item_ids:
                bc_rows = session.scalars(
                    select(ItemBarcode).where(
                        and_(
                            ItemBarcode.company_id == company_id,
                            ItemBarcode.item_id.in_(item_ids),
                        )
                    )
                ).all()
                for b in bc_rows:
                    barcodes_map[b.item_id].append(b.barcode)

            return [self._format_product_dict(item, barcodes_map.get(item.id, [])) for item in items]

    def get_product(self, company_id: str, product_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve single product with all barcodes."""
        with self.db.read_session_scope() as session:
            item = session.scalar(
                select(Item).where(and_(Item.company_id == company_id, Item.id == product_id))
            )
            if not item:
                return None

            barcodes = session.scalars(
                select(ItemBarcode.barcode).where(
                    and_(ItemBarcode.company_id == company_id, ItemBarcode.item_id == product_id)
                )
            ).all()

            return self._format_product_dict(item, list(barcodes))

    def save_product(
        self,
        company_id: str,
        user_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create or update a product with exact Decimal pricing, nullable MRP invariants,
        and atomic barcode promotion with strict ownership enforcement.
        """
        # Resolve SKU: accept explicit sku, or fall back to alias/barcode if using unified field
        raw_sku = data.get("sku")
        if raw_sku is None or str(raw_sku).strip() == "":
            raw_sku = data.get("alias") or data.get("barcode")
        sku = str(raw_sku or "").strip().upper()
        name = str(data.get("name") or "").strip()
        if not sku:
            raise ValueError("Product SKU is required.")
        if not name:
            raise ValueError("Product Name is required.")

        print_name = str(data.get("printName") or data.get("print_name") or name).strip()
        unit = str(data.get("unit") or "Pcs.").strip()
        category = str(data.get("category") or data.get("group") or data.get("item_group") or "").strip() or None
        hsn = str(data.get("hsn") or "").strip().upper() or None
        tax_category = str(data.get("taxCategory") or data.get("tax_category") or "GST 18%").strip()

        # Parse monetary values
        selling_price = parse_decimal(data.get("sellingPrice") or data.get("sales_price") or data.get("selling_price"), "Selling Price", required=True)
        cogs_amount = parse_decimal(data.get("cogsAmount") or data.get("cogs_amount") or data.get("purc_price") or "0.00", "COGS Amount", required=False) or Decimal("0.00")
        mrp = parse_decimal(data.get("mrp"), "MRP", required=False)
        min_sales_price = parse_decimal(data.get("minSalesPrice") or data.get("min_sales_price"), "Minimum Sales Price", required=False)

        # Enforce Pricing Invariants
        if mrp is not None and mrp < selling_price:
            raise ValueError(f"Selling price ({selling_price}) cannot exceed MRP ({mrp}).")

        if min_sales_price is not None and min_sales_price > selling_price:
            raise ValueError(f"Minimum sales price ({min_sales_price}) cannot exceed selling price ({selling_price}).")

        tax_rate = parse_decimal(data.get("taxRatePercent") or data.get("tax_rate_percent") or "0.00", "Tax Rate Percent", required=False) or Decimal("0.00")

        product_id = data.get("id")
        barcode_raw = data.get("barcode")
        if barcode_raw is None or str(barcode_raw).strip() == "":
            if data.get("alias"):
                barcode_raw = data.get("alias")
            elif isinstance(data.get("barcodes"), list) and data.get("barcodes"):
                barcode_raw = data.get("barcodes")[0]
        barcode = validate_barcode_format(barcode_raw) if barcode_raw else None

        with self.db.session_scope() as session:
            # 1. Fetch or create Item
            if product_id:
                item = session.scalar(
                    select(Item).where(and_(Item.company_id == company_id, Item.id == product_id))
                )
                if not item:
                    raise ValueError(f"Product '{product_id}' not found.")

                # Check SKU duplicate on other items
                sku_conflict = session.scalar(
                    select(Item.id).where(
                        and_(Item.company_id == company_id, Item.sku == sku, Item.id != product_id)
                    )
                )
                if sku_conflict:
                    raise ValueError(f"Product SKU '{sku}' is already assigned to another item.")
            else:
                sku_conflict = session.scalar(
                    select(Item.id).where(and_(Item.company_id == company_id, Item.sku == sku))
                )
                if sku_conflict:
                    raise ValueError(f"Product SKU '{sku}' already exists.")

                item = Item(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    sku=sku,
                    is_active=True,
                    created_at=utc_now(),
                )
                session.add(item)

            # Update item attributes
            item.sku = sku
            item.name = name
            item.print_name = print_name
            item.unit = unit
            item.category = category
            item.hsn = hsn
            item.tax_category = tax_category
            item.tax_rate_percent = tax_rate
            item.selling_price = selling_price
            item.cogs_amount = cogs_amount
            item.mrp = mrp
            item.min_sales_price = min_sales_price
            item.updated_at = utc_now()
            session.flush()

            # 2. Handle Barcode Registration & Reservation Promotion
            if barcode:
                # Check if already permanently assigned to another item
                existing_bc = session.scalar(
                    select(ItemBarcode).where(
                        and_(
                            ItemBarcode.company_id == company_id,
                            ItemBarcode.barcode == barcode,
                            ItemBarcode.item_id != item.id,
                        )
                    )
                )
                if existing_bc:
                    raise ValueError(f"Barcode '{barcode}' is already assigned to another item in this company.")

                # Check reservation status
                reservation = session.scalar(
                    select(BarcodeReservation).where(
                        and_(
                            BarcodeReservation.company_id == company_id,
                            BarcodeReservation.barcode == barcode,
                        )
                    )
                )

                if reservation:
                    # Barcode was reserved: verify ownership and freshness
                    if reservation.reserved_by != user_id:
                        raise PermissionError(
                            f"Access Denied: Barcode '{barcode}' is actively reserved by another user."
                        )
                    if ensure_utc(reservation.expires_at) < utc_now():
                        raise ValueError(f"Barcode reservation '{barcode}' has expired. Please allocate a new barcode.")

                    # Delete reservation with all 3 conditions: company_id, barcode, reserved_by
                    del_stmt = delete(BarcodeReservation).where(
                        and_(
                            BarcodeReservation.company_id == company_id,
                            BarcodeReservation.barcode == barcode,
                            BarcodeReservation.reserved_by == user_id,
                        )
                    )
                    res_del = session.execute(del_stmt)
                    if res_del.rowcount != 1:
                        session.rollback()
                        raise PermissionError("Barcode promotion failed: Reservation ownership could not be verified.")

                # Check if this item already has this barcode
                has_this_bc = session.scalar(
                    select(ItemBarcode.id).where(
                        and_(
                            ItemBarcode.company_id == company_id,
                            ItemBarcode.item_id == item.id,
                            ItemBarcode.barcode == barcode,
                        )
                    )
                )
                if not has_this_bc:
                    new_item_bc = ItemBarcode(
                        id=str(uuid.uuid4()),
                        company_id=company_id,
                        item_id=item.id,
                        barcode=barcode,
                    )
                    session.add(new_item_bc)
                    session.flush()

            # Handle extra alternate barcodes if passed
            extra_barcodes = []
            if isinstance(data.get("alternate_barcodes"), list):
                extra_barcodes.extend(data.get("alternate_barcodes"))
            elif isinstance(data.get("barcodes"), list):
                extra_barcodes.extend(data.get("barcodes"))

            for alt_raw in set(extra_barcodes):
                alt_clean = validate_barcode_format(alt_raw) if alt_raw else None
                if alt_clean and alt_clean != barcode:
                    alt_conflict = session.scalar(
                        select(ItemBarcode.id).where(
                            and_(
                                ItemBarcode.company_id == company_id,
                                ItemBarcode.barcode == alt_clean,
                                ItemBarcode.item_id != item.id,
                            )
                        )
                    )
                    if alt_conflict:
                        raise ValueError(f"Barcode '{alt_clean}' is already assigned to another item in this company.")

                    has_alt = session.scalar(
                        select(ItemBarcode.id).where(
                            and_(
                                ItemBarcode.company_id == company_id,
                                ItemBarcode.item_id == item.id,
                                ItemBarcode.barcode == alt_clean,
                            )
                        )
                    )
                    if not has_alt:
                        session.add(
                            ItemBarcode(
                                id=str(uuid.uuid4()),
                                company_id=company_id,
                                item_id=item.id,
                                barcode=alt_clean,
                            )
                        )
                        session.flush()

            all_barcodes = session.scalars(
                select(ItemBarcode.barcode).where(
                    and_(ItemBarcode.company_id == company_id, ItemBarcode.item_id == item.id)
                )
            ).all()

            return {
                "id": item.id,
                "sku": item.sku,
                "name": item.name,
                "printName": item.print_name,
                "unit": item.unit,
                "category": item.category,
                "hsn": item.hsn,
                "taxCategory": item.tax_category,
                "taxRatePercent": str(item.tax_rate_percent),
                "sellingPrice": str(item.selling_price),
                "cogsAmount": str(item.cogs_amount),
                "mrp": str(item.mrp) if item.mrp is not None else None,
                "minSalesPrice": str(item.min_sales_price) if item.min_sales_price is not None else None,
                "barcode": barcode or (all_barcodes[0] if all_barcodes else None),
                "barcodes": list(all_barcodes),
                "isActive": item.is_active,
            }

    def set_product_active(self, company_id: str, product_id: str, is_active: bool) -> bool:
        """Toggle product active status."""
        with self.db.session_scope() as session:
            item = session.scalar(
                select(Item).where(and_(Item.company_id == company_id, Item.id == product_id))
            )
            if not item:
                raise ValueError(f"Product '{product_id}' not found.")
            item.is_active = bool(is_active)
            item.updated_at = utc_now()
        return True

    def add_barcode(self, company_id: str, product_id: str, barcode: str) -> Dict[str, Any]:
        """Attach an additional / alternate barcode to an existing product."""
        clean_bc = validate_barcode_format(barcode)
        with self.db.session_scope() as session:
            item = session.scalar(
                select(Item).where(and_(Item.company_id == company_id, Item.id == product_id))
            )
            if not item:
                raise ValueError(f"Product '{product_id}' not found.")

            conflict = session.scalar(
                select(ItemBarcode.id).where(
                    and_(
                        ItemBarcode.company_id == company_id,
                        ItemBarcode.barcode == clean_bc,
                        ItemBarcode.item_id != product_id,
                    )
                )
            )
            if conflict:
                raise ValueError(f"Barcode '{clean_bc}' is already assigned to another item in this company.")

            existing = session.scalar(
                select(ItemBarcode).where(
                    and_(
                        ItemBarcode.company_id == company_id,
                        ItemBarcode.item_id == product_id,
                        ItemBarcode.barcode == clean_bc,
                    )
                )
            )
            if not existing:
                session.add(
                    ItemBarcode(
                        id=str(uuid.uuid4()),
                        company_id=company_id,
                        item_id=product_id,
                        barcode=clean_bc,
                    )
                )
        return self.get_product(company_id, product_id)

    def lookup_product(self, company_id: str, query: str) -> Optional[Dict[str, Any]]:
        """
        Unified product lookup for Traditional Billing.
        Searches in strict precedence:
        1. Exact Barcode match in item_barcodes (primary or alternate barcode)
        2. Exact SKU match in items
        3. Exact Name match in items (case-insensitive)
        4. Name prefix match in items (case-insensitive)
        """
        clean_q = str(query or "").strip().upper()
        if not clean_q:
            return None

        with self.db.read_session_scope() as session:
            # 1. Barcode match in item_barcodes
            bc_row = session.scalar(
                select(ItemBarcode).where(
                    and_(ItemBarcode.company_id == company_id, ItemBarcode.barcode == clean_q)
                )
            )
            item = None
            if bc_row:
                item = session.scalar(
                    select(Item).where(and_(Item.company_id == company_id, Item.id == bc_row.item_id))
                )

            # 2. Exact SKU match
            if not item:
                item = session.scalar(
                    select(Item).where(
                        and_(Item.company_id == company_id, Item.sku == clean_q)
                    )
                )

            # 3. Exact Name match (case-insensitive)
            if not item:
                item = session.scalar(
                    select(Item).where(
                        and_(Item.company_id == company_id, Item.name.ilike(clean_q))
                    )
                )

            # 4. Name prefix match
            if not item:
                item = session.scalar(
                    select(Item).where(
                        and_(Item.company_id == company_id, Item.name.ilike(f"{clean_q}%"))
                    ).order_by(Item.name.asc())
                )

            if not item:
                return None

            if not item.is_active:
                raise ValueError(f"Product '{item.name}' is inactive and cannot be billed.")

            barcodes = session.scalars(
                select(ItemBarcode.barcode).where(
                    and_(ItemBarcode.company_id == company_id, ItemBarcode.item_id == item.id)
                )
            ).all()

            return self._format_product_dict(item, list(barcodes))

    def find_product_by_barcode(self, company_id: str, barcode: str) -> Optional[Dict[str, Any]]:
        """Unified barcode / SKU / name lookup for Traditional Billing."""
        return self.lookup_product(company_id, barcode)

    def validate_invoice_items(
        self,
        company_id: str,
        items: List[Dict[str, Any]],
        strict_price: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Validates invoice items against the Traditional database:
        - Confirms product exists and belongs to the authenticated company.
        - Rejects inactive products.
        - Enforces that supplied price matches database selling_price (unless explicitly overridden).
        - Computes line amounts using exact Decimal arithmetic.
        """
        if not items:
            raise ValueError("Invoice must contain at least one line item.")

        validated_items = []
        with self.db.read_session_scope() as session:
            for idx, raw_it in enumerate(items, start=1):
                item_id = raw_it.get("item_id") or raw_it.get("id")
                name = str(raw_it.get("name") or "").strip()
                sku = str(raw_it.get("sku") or "").strip()

                item_record = None
                if item_id:
                    item_record = session.scalar(
                        select(Item).where(and_(Item.company_id == company_id, Item.id == item_id))
                    )
                if not item_record and sku:
                    item_record = session.scalar(
                        select(Item).where(and_(Item.company_id == company_id, Item.sku == sku.upper()))
                    )
                if not item_record and name:
                    item_record = session.scalar(
                        select(Item).where(and_(Item.company_id == company_id, Item.name.ilike(name)))
                    )

                if not item_record:
                    raise ValueError(f"Line {idx}: Product '{name or sku or item_id}' does not exist or not found in company catalogue.")

                if not item_record.is_active:
                    raise ValueError(f"Line {idx}: Product '{item_record.name}' is inactive and cannot be billed.")

                # Determine and validate unit selling price
                db_price = item_record.selling_price
                supplied_price_raw = raw_it.get("price") if raw_it.get("price") is not None else raw_it.get("sellingPrice")
                if supplied_price_raw is not None and strict_price:
                    supplied_dec = parse_decimal(supplied_price_raw, f"Line {idx} Price", required=True)
                    if supplied_dec != db_price:
                        raise ValueError(
                            f"Manipulated price detected for product '{item_record.name}': backend price is ₹{db_price}, received ₹{supplied_dec}."
                        )

                # Quantity calculation
                qty_raw = raw_it.get("qty", 1)
                try:
                    qty = Decimal(str(qty_raw))
                    if qty <= 0:
                        raise ValueError()
                except Exception:
                    raise ValueError(f"Line {idx}: Invalid quantity '{qty_raw}'. Must be greater than 0.")

                # Discount calculation
                disc_pct_raw = raw_it.get("discount_percent") or raw_it.get("discountPercent") or 0
                try:
                    disc_pct = Decimal(str(disc_pct_raw))
                except Exception:
                    disc_pct = Decimal("0.00")

                gross_amount = (qty * db_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                disc_amount = (gross_amount * (disc_pct / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                line_amount = (gross_amount - disc_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                validated_items.append({
                    "sn": idx,
                    "item_id": item_record.id,
                    "sku": item_record.sku,
                    "name": item_record.name,
                    "unit": item_record.unit,
                    "tax_category": item_record.tax_category or "GST 18%",
                    "tax_rate_percent": str(item_record.tax_rate_percent or Decimal("18.00")),
                    "hsn": item_record.hsn or "",
                    "selling_price": str(db_price),
                    "price": str(db_price),
                    "qty": str(qty),
                    "gross_amount": str(gross_amount),
                    "discount_percent": str(disc_pct),
                    "discount_amount": str(disc_amount),
                    "amount": str(line_amount),
                    "line_total": str(line_amount),
                })

        return validated_items

    def calculate_invoice_totals(
        self,
        items: List[Dict[str, Any]],
        sale_type: str = "L/GST-18%",
    ) -> Dict[str, Any]:
        """
        Calculates subtotal, CGST/SGST/IGST, round-off and grand total
        using exact Decimal arithmetic and approved monetary precision.
        """
        subtotal = sum(Decimal(it["amount"]) for it in items).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        clean_st = str(sale_type or "L/GST-18%").strip()
        is_interstate = clean_st.startswith("I/GST")
        tax_rate = Decimal("0.00")
        if "28%" in clean_st:
            tax_rate = Decimal("28.00")
        elif "18%" in clean_st:
            tax_rate = Decimal("18.00")
        elif "12%" in clean_st:
            tax_rate = Decimal("12.00")
        elif "5%" in clean_st:
            tax_rate = Decimal("5.00")
        elif "Exempt" in clean_st or "0%" in clean_st:
            tax_rate = Decimal("0.00")
        else:
            tax_rate = Decimal("18.00")

        cgst = Decimal("0.00")
        sgst = Decimal("0.00")
        igst = Decimal("0.00")

        if tax_rate > 0:
            if is_interstate:
                igst = (subtotal * (tax_rate / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                half_rate = tax_rate / Decimal("2")
                cgst = (subtotal * (half_rate / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                sgst = (subtotal * (half_rate / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        raw_total = subtotal + cgst + sgst + igst
        # Integer rounding to nearest rupee as in retail standard
        grand_total = raw_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        round_off = (grand_total - raw_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return {
            "subtotal": str(subtotal),
            "taxable_amount": str(subtotal),
            "sale_type": clean_st,
            "tax_rate_percent": str(tax_rate),
            "is_interstate": is_interstate,
            "cgst_amount": str(cgst),
            "sgst_amount": str(sgst),
            "igst_amount": str(igst),
            "total_tax_amount": str(cgst + sgst + igst),
            "round_off_amount": str(round_off),
            "grand_total": str(grand_total),
        }

    @staticmethod
    def derive_financial_year(vch_date_str: Optional[str] = None, fallback_fy: Optional[str] = None) -> str:
        """
        Derives Indian Financial Year (Apr 1 - Mar 31) string: e.g. '2026-2027'.
        Parses DD-MM-YYYY or YYYY-MM-DD. If unavailable, falls back to fallback_fy or current UTC date.
        """
        if vch_date_str:
            try:
                parts = str(vch_date_str).strip().split("-")
                if len(parts) == 3:
                    if len(parts[0]) == 4:  # YYYY-MM-DD
                        yr, mo = int(parts[0]), int(parts[1])
                    else:  # DD-MM-YYYY
                        yr, mo = int(parts[2]), int(parts[1])
                    if 1 <= mo <= 12 and 1900 <= yr <= 2100:
                        if mo >= 4:
                            return f"{yr}-{yr+1}"
                        else:
                            return f"{yr-1}-{yr}"
            except Exception:
                pass

        if fallback_fy and len(str(fallback_fy).strip()) >= 4:
            return str(fallback_fy).strip()

        now = utc_now()
        if now.month >= 4:
            return f"{now.year}-{now.year+1}"
        return f"{now.year-1}-{now.year}"

    def _resolve_branch_id(self, session, company_id: str, branch_id: Optional[str] = None) -> str:
        """Resolves active branch ID for tenant or creates default BR01 branch."""
        if branch_id:
            branch = session.scalar(
                select(Branch).where(and_(Branch.company_id == company_id, Branch.id == branch_id))
            )
            if branch:
                return branch.id

        # Query first branch for company
        branch = session.scalar(
            select(Branch).where(Branch.company_id == company_id).order_by(Branch.created_at.asc())
        )
        if branch:
            return branch.id

        # Fallback create default BR01
        new_branch = Branch(
            id=str(uuid.uuid4()),
            company_id=company_id,
            code="BR01",
            name="Main Branch",
            is_active=True,
            created_at=utc_now(),
        )
        session.add(new_branch)
        session.flush()
        return new_branch.id

    @staticmethod
    def _extract_trailing_int(text: Any) -> Optional[int]:
        """Extracts trailing integer from a voucher number string (e.g. '007' -> 7, 'VCH-042' -> 42)."""
        if text is None:
            return None
        s = str(text).strip()
        if not s:
            return None
        if s.isdigit():
            return int(s)
        m = re.search(r"(\d+)$", s)
        if m:
            return int(m.group(1))
        return None

    def _scan_audit_log_max_vch_no(self, session, company_id: str, series: str, financial_year: Optional[str] = None) -> int:
        """Historical reconciliation: scans AuditLog for previously saved sales invoices in company."""
        audit_logs = session.scalars(
            select(AuditLog.payload_json).where(
                and_(
                    AuditLog.company_id == company_id,
                    AuditLog.event_type == "SALES_INVOICE_CREATED",
                )
            )
        ).all()
        max_num = 0
        clean_series = (series or "Main").strip().lower()
        clean_fy = str(financial_year).strip() if financial_year else None
        for p_json in audit_logs:
            if not p_json:
                continue
            try:
                p = json.loads(p_json)
                p_series = str(p.get("series") or "Main").strip().lower()
                if p_series != clean_series:
                    continue
                p_fy = p.get("financial_year")
                if clean_fy and p_fy and str(p_fy).strip() != clean_fy:
                    continue
                v_no = p.get("vch_no") or p.get("voucher_number")
                num = self._extract_trailing_int(v_no)
                if num is not None and num > max_num:
                    max_num = num
            except Exception:
                continue
        return max_num

    def get_next_voucher_number(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        financial_year: Optional[str] = None,
        series: str = "Main",
        vch_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Computes the next available sequential voucher number for the given scope
        without mutating or reserving sequence state (read-only preview).
        Scope: (company_id, branch_id, financial_year, series).
        """
        clean_series = str(series or "Main").strip() or "Main"

        with self.db.read_session_scope() as session:
            # 1. Resolve branch
            resolved_branch_id = self._resolve_branch_id(session, company_id, branch_id)

            # 2. Resolve financial year
            company = session.scalar(select(Company).where(Company.id == company_id))
            company_fy = company.fin_year if company else None
            fy = financial_year or self.derive_financial_year(vch_date, fallback_fy=company_fy)

            # 3. Read sequence record
            seq_row = session.scalar(
                select(VoucherSequence).where(
                    and_(
                        VoucherSequence.company_id == company_id,
                        VoucherSequence.branch_id == resolved_branch_id,
                        VoucherSequence.financial_year == fy,
                        VoucherSequence.series == clean_series,
                    )
                )
            )
            seq_current = seq_row.current_number if seq_row else 0
            prefix = seq_row.prefix if seq_row and seq_row.prefix is not None else ""
            padding = seq_row.padding if seq_row and seq_row.padding else 3

            # 4. Check highest committed invoice in sales_invoices
            max_inv_seq = session.scalar(
                select(func.max(SaleInvoice.sequence_number)).where(
                    and_(
                        SaleInvoice.company_id == company_id,
                        SaleInvoice.branch_id == resolved_branch_id,
                        SaleInvoice.financial_year == fy,
                        SaleInvoice.series == clean_series,
                    )
                )
            ) or 0

            # 5. Check historical audit logs
            max_audit_seq = self._scan_audit_log_max_vch_no(session, company_id, clean_series, financial_year=fy)

            max_committed = max(seq_current, max_inv_seq, max_audit_seq, 0)
            next_num = max_committed + 1

            formatted_no = f"{prefix}{next_num:0{padding}d}"

            return {
                "voucher_number": formatted_no,
                "sequence_number": next_num,
                "series": clean_series,
                "financial_year": fy,
                "branch_id": resolved_branch_id,
                "company_id": company_id,
            }

    def save_sale_invoice(
        self,
        company_id: str,
        user_id: str,
        invoice_data: Dict[str, Any],
        branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validates invoice items and prices against Traditional database,
        computes financial totals, atomically allocates the scoped voucher sequence number,
        inserts SaleInvoice and AuditLog records inside a single transaction.
        """
        items_raw = invoice_data.get("items", [])
        validated_items = self.validate_invoice_items(company_id, items_raw, strict_price=True)
        sale_type = invoice_data.get("sale_type") or "L/GST-18%"
        totals = self.calculate_invoice_totals(validated_items, sale_type=sale_type)

        vch_date = str(invoice_data.get("vch_date") or utc_now().strftime("%d-%m-%Y")).strip()
        series = str(invoice_data.get("series") or "Main").strip() or "Main"

        with self.db.session_scope() as session:
            # 1. Resolve branch
            resolved_branch_id = self._resolve_branch_id(session, company_id, branch_id or invoice_data.get("branch_id"))

            # 2. Resolve financial year
            company = session.scalar(select(Company).where(Company.id == company_id))
            company_fy = company.fin_year if company else None
            fy = invoice_data.get("financial_year") or self.derive_financial_year(vch_date, fallback_fy=company_fy)

            # 3. Concurrency-safe atomic sequence allocation
            seq_query = select(VoucherSequence).where(
                and_(
                    VoucherSequence.company_id == company_id,
                    VoucherSequence.branch_id == resolved_branch_id,
                    VoucherSequence.financial_year == fy,
                    VoucherSequence.series == series,
                )
            )
            if not self.db.is_sqlite:
                seq_query = seq_query.with_for_update()

            seq_row = session.scalar(seq_query)

            max_inv_seq = session.scalar(
                select(func.max(SaleInvoice.sequence_number)).where(
                    and_(
                        SaleInvoice.company_id == company_id,
                        SaleInvoice.branch_id == resolved_branch_id,
                        SaleInvoice.financial_year == fy,
                        SaleInvoice.series == series,
                    )
                )
            ) or 0

            max_audit_seq = self._scan_audit_log_max_vch_no(session, company_id, series, financial_year=fy)
            current_seq = seq_row.current_number if seq_row else 0
            allocated_seq = max(current_seq, max_inv_seq, max_audit_seq, 0) + 1
            padding = seq_row.padding if seq_row and seq_row.padding else 3
            prefix = seq_row.prefix if seq_row and seq_row.prefix is not None else ""
            vch_no = f"{prefix}{allocated_seq:0{padding}d}"

            if not seq_row:
                seq_row = VoucherSequence(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    branch_id=resolved_branch_id,
                    financial_year=fy,
                    series=series,
                    current_number=allocated_seq,
                    prefix=prefix,
                    padding=padding,
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                session.add(seq_row)
            else:
                seq_row.current_number = allocated_seq
                seq_row.updated_at = utc_now()

            session.flush()

            # 4. Insert SaleInvoice
            invoice_id = str(uuid.uuid4())
            voucher_id = str(uuid.uuid4())
            party_name = invoice_data.get("party_name") or "CASH"
            payment_method = invoice_data.get("payment_method") or "CASH"

            valid_user_id = None
            if user_id:
                user_exists = session.scalar(
                    select(User.id).where(and_(User.company_id == company_id, User.id == user_id))
                )
                if user_exists:
                    valid_user_id = user_id

            sale_inv = SaleInvoice(
                id=invoice_id,
                voucher_id=voucher_id,
                company_id=company_id,
                branch_id=resolved_branch_id,
                user_id=valid_user_id,
                financial_year=fy,
                series=series,
                sequence_number=allocated_seq,
                voucher_number=vch_no,
                vch_date=vch_date,
                party_name=party_name,
                account_id=invoice_data.get("account_id"),
                customer_category=invoice_data.get("customer_category") or "Direct Customer",
                sale_type=totals["sale_type"],
                payment_method=payment_method,
                payment_mode=payment_method,
                status="PAID",
                narration=invoice_data.get("narration") or "",
                subtotal=Decimal(totals["subtotal"]),
                taxable_amount=Decimal(totals["taxable_amount"]),
                cgst_amount=Decimal(totals["cgst_amount"]),
                sgst_amount=Decimal(totals["sgst_amount"]),
                igst_amount=Decimal(totals["igst_amount"]),
                round_off_amount=Decimal(totals["round_off_amount"]),
                grand_total=Decimal(totals["grand_total"]),
                total_amount=Decimal(totals["grand_total"]),
                items_json=json.dumps(validated_items),
                created_at=utc_now(),
            )
            session.add(sale_inv)
            session.flush()

            # 5. Commit AuditLog entry
            result_payload = {
                "id": invoice_id,
                "voucher_id": voucher_id,
                "vch_no": vch_no,
                "voucher_number": vch_no,
                "sequence_number": allocated_seq,
                "company_id": company_id,
                "branch_id": resolved_branch_id,
                "financial_year": fy,
                "series": series,
                "party_name": party_name,
                "account_id": invoice_data.get("account_id"),
                "customer_category": invoice_data.get("customer_category") or "Direct Customer",
                "sale_type": totals["sale_type"],
                "payment_method": payment_method,
                "vch_date": vch_date,
                "narration": invoice_data.get("narration") or "",
                "items": validated_items,
                "subtotal": totals["subtotal"],
                "taxable_amount": totals["taxable_amount"],
                "cgst_amount": totals["cgst_amount"],
                "sgst_amount": totals["sgst_amount"],
                "igst_amount": totals["igst_amount"],
                "round_off_amount": totals["round_off_amount"],
                "grand_total": totals["grand_total"],
                "total_amount": totals["grand_total"],
                "created_at": sale_inv.created_at.isoformat(),
            }

            audit = AuditLog(
                id=str(uuid.uuid4()),
                company_id=company_id,
                user_id=user_id,
                event_type="SALES_INVOICE_CREATED",
                entity_type="SALE_INVOICE",
                entity_id=invoice_id,
                payload_json=json.dumps(result_payload),
                created_at=utc_now(),
            )
            session.add(audit)

        return result_payload
