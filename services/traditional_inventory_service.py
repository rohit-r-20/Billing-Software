"""
Traditional Billing Inventory Service.
Dedicated, authoritative stock ledger and balance management engine for Traditional Billing.
Maintains physical and logical separation from Fast Billing (data/anti_matrix_billing.db).

Key Architectural Invariants:
1. Strict multi-tenant company and branch isolation.
2. Fixed-point / Decimal quantity representation (scale = 1000) eliminating floating-point rounding.
3. Atomic transaction boundaries: stock balance mutations and ledger insertions succeed or rollback together.
4. Immutable stock ledger: stock_movements records are never updated or deleted. Corrections are posted as reversals.
5. Concurrency safety: SQLite write engine operates under WAL + BEGIN IMMEDIATE; select FOR UPDATE on PostgreSQL.
6. Idempotency protection: optional idempotency_key prevents duplicate postings across retries or double clicks.
"""

import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Union

from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import Session

from db.traditional_database import traditional_db_manager, TraditionalDatabaseManager
from db.traditional_models import (
    Company,
    Branch,
    Item,
    StockBalance,
    StockMovement,
    StockAdjustment,
    StockTransfer,
    utc_now,
    ensure_utc,
)
from core.logging_config import logger

QTY_SCALE = 1000
DECIMAL_ZERO = Decimal("0.000")
CURRENCY_ZERO = Decimal("0.00")


class TraditionalInventoryError(Exception):
    """Base exception for Traditional Inventory operations."""
    pass


class InsufficientStockError(TraditionalInventoryError):
    """Raised when an outward stock operation exceeds available quantity and negative stock is disabled."""
    pass


class InvalidMovementError(TraditionalInventoryError):
    """Raised when an invalid movement type, branch target, or quantity is submitted."""
    pass


def parse_decimal_qty(val: Union[Decimal, float, int, str], field_name: str = "Quantity") -> Decimal:
    """Parses and quantizes quantity to 3 decimal places using Decimal arithmetic."""
    if val is None:
        raise InvalidMovementError(f"{field_name} cannot be None.")
    try:
        dec = Decimal(str(val).strip()).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        return dec
    except (InvalidOperation, ValueError, TypeError) as e:
        raise InvalidMovementError(f"Invalid {field_name} format: '{val}'. Expected decimal number.") from e


def parse_decimal_cost(val: Union[Decimal, float, int, str], field_name: str = "Unit Cost") -> Decimal:
    """Parses and quantizes unit cost to 2 decimal places."""
    if val is None:
        return CURRENCY_ZERO
    try:
        dec = Decimal(str(val).strip()).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return dec
    except (InvalidOperation, ValueError, TypeError) as e:
        raise InvalidMovementError(f"Invalid {field_name} format: '{val}'. Expected monetary decimal.") from e


def qty_to_scaled(qty: Decimal) -> int:
    """Converts Decimal quantity to scaled integer (e.g. Decimal('2.500') -> 2500)."""
    return int(qty * Decimal(QTY_SCALE))


def scaled_to_qty(scaled: int) -> Decimal:
    """Converts scaled integer back to Decimal quantity (e.g. 2500 -> Decimal('2.500'))."""
    if scaled is None:
        return DECIMAL_ZERO
    return (Decimal(scaled) / Decimal(QTY_SCALE)).quantize(Decimal("0.001"))


class TraditionalInventoryService:
    """
    Dedicated inventory engine for Traditional Billing.
    Completely isolated from Fast Billing InventoryService.
    """

    def __init__(self, db: Optional[TraditionalDatabaseManager] = None):
        self.db = db or traditional_db_manager

    def _validate_context(
        self,
        session: Session,
        company_id: str,
        branch_id: Optional[str] = None,
        item_id: Optional[str] = None
    ) -> Tuple[Company, Optional[Branch], Optional[Item]]:
        """
        Validates company, branch, and item exist and belong to the same tenant.
        Prevents cross-tenant access.
        """
        if not company_id or not str(company_id).strip():
            raise TraditionalInventoryError("Company context is required.")
        clean_cid = str(company_id).strip()

        company = session.scalar(select(Company).where(Company.id == clean_cid))
        if not company:
            raise TraditionalInventoryError(f"Company '{clean_cid}' not found.")

        branch = None
        if branch_id:
            clean_bid = str(branch_id).strip()
            branch = session.scalar(
                select(Branch).where(and_(Branch.company_id == clean_cid, Branch.id == clean_bid))
            )
            if not branch:
                raise TraditionalInventoryError(f"Branch '{clean_bid}' not found for company '{clean_cid}'.")

        item = None
        if item_id:
            clean_iid = str(item_id).strip()
            item = session.scalar(
                select(Item).where(and_(Item.company_id == clean_cid, Item.id == clean_iid))
            )
            if not item:
                raise TraditionalInventoryError(f"Product '{clean_iid}' not found in company '{clean_cid}'.")

        return company, branch, item

    def _get_or_create_stock_balance(
        self,
        session: Session,
        company_id: str,
        branch_id: str,
        item_id: str
    ) -> StockBalance:
        """
        Fetches or creates a StockBalance record for (company, branch, item) with pessimistic lock.
        """
        stmt = (
            select(StockBalance)
            .where(
                and_(
                    StockBalance.company_id == company_id,
                    StockBalance.branch_id == branch_id,
                    StockBalance.item_id == item_id,
                )
            )
            .with_for_update()
        )
        balance = session.scalar(stmt)
        if not balance:
            balance = StockBalance(
                id=str(uuid.uuid4()),
                company_id=company_id,
                branch_id=branch_id,
                item_id=item_id,
                current_qty_scaled=0,
                updated_at=utc_now(),
            )
            session.add(balance)
            session.flush()
        return balance

    # -------------------------------------------------------------------------
    # 1. Balance & Availability Queries
    # -------------------------------------------------------------------------

    def get_stock_balance(
        self,
        company_id: str,
        item_id: str,
        branch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Returns the authoritative current stock balance for an item in Traditional Billing.
        If branch_id is specified, returns branch balance; otherwise sums across all company branches.
        """
        with self.db.read_session_scope() as session:
            _, branch, item = self._validate_context(session, company_id, branch_id, item_id)
            clean_cid = str(company_id).strip()
            clean_iid = str(item_id).strip()

            if branch:
                bal = session.scalar(
                    select(StockBalance).where(
                        and_(
                            StockBalance.company_id == clean_cid,
                            StockBalance.branch_id == branch.id,
                            StockBalance.item_id == clean_iid,
                        )
                    )
                )
                scaled_qty = bal.current_qty_scaled if bal else 0
                updated_at = bal.updated_at if bal else None
            else:
                scaled_sum = session.scalar(
                    select(func.coalesce(func.sum(StockBalance.current_qty_scaled), 0)).where(
                        and_(
                            StockBalance.company_id == clean_cid,
                            StockBalance.item_id == clean_iid,
                        )
                    )
                )
                scaled_qty = int(scaled_sum or 0)
                updated_at = None

            return {
                "company_id": clean_cid,
                "branch_id": branch.id if branch else None,
                "item_id": clean_iid,
                "item_name": item.name,
                "sku": item.sku,
                "unit": item.unit,
                "current_qty": scaled_to_qty(scaled_qty),
                "current_qty_scaled": scaled_qty,
                "updated_at": updated_at.isoformat() if updated_at else None,
            }

    def validate_stock_availability(
        self,
        company_id: str,
        branch_id: str,
        items: List[Dict[str, Any]],
        allow_negative_stock: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Validates stock availability for a batch of items before an outward operation.
        Returns (is_valid, list_of_error_messages).
        If allow_negative_stock is True, returns (True, []) immediately.
        """
        if allow_negative_stock:
            return True, []

        if not items:
            return True, []

        with self.db.read_session_scope() as session:
            self._validate_context(session, company_id, branch_id)
            clean_cid = str(company_id).strip()
            clean_bid = str(branch_id).strip()

            # Aggregate required quantity per item
            aggregated: Dict[str, Decimal] = {}
            item_names: Dict[str, str] = {}

            for it in items:
                item_id = it.get("item_id") or it.get("id")
                if not item_id:
                    continue
                clean_id = str(item_id).strip()
                qty = parse_decimal_qty(it.get("qty") or it.get("quantity") or 0)
                aggregated[clean_id] = aggregated.get(clean_id, DECIMAL_ZERO) + qty
                if clean_id not in item_names:
                    item_names[clean_id] = it.get("name") or it.get("item_name") or "Product"

            errors: List[str] = []
            for clean_id, total_needed in aggregated.items():
                bal = session.scalar(
                    select(StockBalance).where(
                        and_(
                            StockBalance.company_id == clean_cid,
                            StockBalance.branch_id == clean_bid,
                            StockBalance.item_id == clean_id,
                        )
                    )
                )
                available = scaled_to_qty(bal.current_qty_scaled) if bal else DECIMAL_ZERO
                if available < total_needed:
                    pname = item_names.get(clean_id, "Product")
                    errors.append(
                        f"Insufficient stock for '{pname}'. Available: {available:g}, Requested: {total_needed:g}."
                    )

            return len(errors) == 0, errors

    # -------------------------------------------------------------------------
    # 2. Inward Movements (Purchases & Receipts)
    # -------------------------------------------------------------------------

    def record_stock_inward(
        self,
        company_id: str,
        branch_id: str,
        item_id: str,
        qty: Union[Decimal, float, int, str],
        unit_cost: Union[Decimal, float, int, str] = CURRENCY_ZERO,
        reference_type: str = "PURCHASE_VOUCHER",
        reference_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        notes: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Records an inward stock movement (e.g., purchase, goods receipt).
        Atomically increments branch StockBalance and appends to StockMovement ledger.
        """
        dec_qty = parse_decimal_qty(qty, "Inward Quantity")
        if dec_qty <= DECIMAL_ZERO:
            raise InvalidMovementError(f"Inward quantity must be positive. Received: {dec_qty}")
        dec_cost = parse_decimal_cost(unit_cost, "Unit Cost")
        scaled_delta = qty_to_scaled(dec_qty)

        with self.db.session_scope() as session:
            _, branch, item = self._validate_context(session, company_id, branch_id, item_id)
            clean_cid = str(company_id).strip()
            clean_bid = branch.id
            clean_iid = item.id

            # Idempotency verification
            if idempotency_key:
                existing_m = session.scalar(
                    select(StockMovement).where(
                        and_(
                            StockMovement.company_id == clean_cid,
                            StockMovement.idempotency_key == idempotency_key,
                        )
                    )
                )
                if existing_m:
                    logger.info(f"[Traditional Inventory] Idempotent inward replay: {idempotency_key}")
                    bal = self._get_or_create_stock_balance(session, clean_cid, clean_bid, clean_iid)
                    return {
                        "success": True,
                        "movement_id": existing_m.id,
                        "is_idempotent_replay": True,
                        "movement_type": existing_m.movement_type,
                        "quantity": dec_qty,
                        "new_balance": scaled_to_qty(bal.current_qty_scaled),
                        "branch_id": clean_bid,
                        "item_id": clean_iid,
                    }

            # Update Stock Balance
            balance = self._get_or_create_stock_balance(session, clean_cid, clean_bid, clean_iid)
            balance.current_qty_scaled += scaled_delta
            balance.updated_at = utc_now()

            # Record Ledger Movement
            movement = StockMovement(
                id=str(uuid.uuid4()),
                company_id=clean_cid,
                branch_id=clean_bid,
                item_id=clean_iid,
                movement_type="PURCHASE",
                qty_scaled=scaled_delta,
                unit_cost=dec_cost,
                reference_type=reference_type,
                reference_id=reference_id,
                idempotency_key=idempotency_key,
                notes=notes,
                user_id=user_id,
                created_at=utc_now(),
            )
            session.add(movement)
            session.flush()

            return {
                "success": True,
                "movement_id": movement.id,
                "is_idempotent_replay": False,
                "movement_type": "PURCHASE",
                "quantity": dec_qty,
                "new_balance": scaled_to_qty(balance.current_qty_scaled),
                "branch_id": clean_bid,
                "item_id": clean_iid,
                "timestamp": movement.created_at.isoformat(),
            }

    # -------------------------------------------------------------------------
    # 3. Outward Movements (Sales & Dispatch)
    # -------------------------------------------------------------------------

    def record_stock_outward(
        self,
        company_id: str,
        branch_id: str,
        item_id: str,
        qty: Union[Decimal, float, int, str],
        allow_negative_stock: bool = False,
        unit_cost: Union[Decimal, float, int, str] = CURRENCY_ZERO,
        reference_type: str = "SALES_INVOICE",
        reference_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        notes: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Records an outward stock movement (e.g., sale checkout).
        Atomically decrements branch StockBalance and appends to StockMovement ledger.
        Enforces negative-stock policy before modifying balance.
        """
        dec_qty = parse_decimal_qty(qty, "Outward Quantity")
        if dec_qty <= DECIMAL_ZERO:
            raise InvalidMovementError(f"Outward quantity must be positive. Received: {dec_qty}")
        dec_cost = parse_decimal_cost(unit_cost, "Unit Cost")
        scaled_delta = qty_to_scaled(dec_qty)

        with self.db.session_scope() as session:
            _, branch, item = self._validate_context(session, company_id, branch_id, item_id)
            clean_cid = str(company_id).strip()
            clean_bid = branch.id
            clean_iid = item.id

            # Idempotency verification
            if idempotency_key:
                existing_m = session.scalar(
                    select(StockMovement).where(
                        and_(
                            StockMovement.company_id == clean_cid,
                            StockMovement.idempotency_key == idempotency_key,
                        )
                    )
                )
                if existing_m:
                    logger.info(f"[Traditional Inventory] Idempotent outward replay: {idempotency_key}")
                    bal = self._get_or_create_stock_balance(session, clean_cid, clean_bid, clean_iid)
                    return {
                        "success": True,
                        "movement_id": existing_m.id,
                        "is_idempotent_replay": True,
                        "movement_type": existing_m.movement_type,
                        "quantity": dec_qty,
                        "new_balance": scaled_to_qty(bal.current_qty_scaled),
                        "branch_id": clean_bid,
                        "item_id": clean_iid,
                    }

            # Fetch locked balance
            balance = self._get_or_create_stock_balance(session, clean_cid, clean_bid, clean_iid)
            current_avail = scaled_to_qty(balance.current_qty_scaled)

            # Strict policy enforcement
            if not allow_negative_stock and balance.current_qty_scaled < scaled_delta:
                raise InsufficientStockError(
                    f"Insufficient stock for '{item.name}'. Available: {current_avail:g}, "
                    f"Requested: {dec_qty:g}. Negative stock is disabled by company policy."
                )

            # Deduct balance
            balance.current_qty_scaled -= scaled_delta
            balance.updated_at = utc_now()

            # Record Ledger Movement (negative scaled qty for outward)
            movement = StockMovement(
                id=str(uuid.uuid4()),
                company_id=clean_cid,
                branch_id=clean_bid,
                item_id=clean_iid,
                movement_type="SALE",
                qty_scaled=-scaled_delta,
                unit_cost=dec_cost,
                reference_type=reference_type,
                reference_id=reference_id,
                idempotency_key=idempotency_key,
                notes=notes,
                user_id=user_id,
                created_at=utc_now(),
            )
            session.add(movement)
            session.flush()

            return {
                "success": True,
                "movement_id": movement.id,
                "is_idempotent_replay": False,
                "movement_type": "SALE",
                "quantity": dec_qty,
                "new_balance": scaled_to_qty(balance.current_qty_scaled),
                "branch_id": clean_bid,
                "item_id": clean_iid,
                "timestamp": movement.created_at.isoformat(),
            }

    # -------------------------------------------------------------------------
    # 4. Opening Stock
    # -------------------------------------------------------------------------

    def record_opening_stock(
        self,
        company_id: str,
        branch_id: str,
        item_id: str,
        qty: Union[Decimal, float, int, str],
        unit_cost: Union[Decimal, float, int, str] = CURRENCY_ZERO,
        reference_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        notes: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Records opening stock for an item at a specific branch.
        """
        dec_qty = parse_decimal_qty(qty, "Opening Quantity")
        if dec_qty < DECIMAL_ZERO:
            raise InvalidMovementError(f"Opening stock cannot be negative. Received: {dec_qty}")
        dec_cost = parse_decimal_cost(unit_cost, "Unit Cost")
        scaled_delta = qty_to_scaled(dec_qty)

        with self.db.session_scope() as session:
            _, branch, item = self._validate_context(session, company_id, branch_id, item_id)
            clean_cid = str(company_id).strip()
            clean_bid = branch.id
            clean_iid = item.id

            if idempotency_key:
                existing_m = session.scalar(
                    select(StockMovement).where(
                        and_(
                            StockMovement.company_id == clean_cid,
                            StockMovement.idempotency_key == idempotency_key,
                        )
                    )
                )
                if existing_m:
                    bal = self._get_or_create_stock_balance(session, clean_cid, clean_bid, clean_iid)
                    return {
                        "success": True,
                        "movement_id": existing_m.id,
                        "is_idempotent_replay": True,
                        "movement_type": "OPENING",
                        "quantity": dec_qty,
                        "new_balance": scaled_to_qty(bal.current_qty_scaled),
                        "branch_id": clean_bid,
                        "item_id": clean_iid,
                    }

            balance = self._get_or_create_stock_balance(session, clean_cid, clean_bid, clean_iid)
            balance.current_qty_scaled += scaled_delta
            balance.updated_at = utc_now()

            movement = StockMovement(
                id=str(uuid.uuid4()),
                company_id=clean_cid,
                branch_id=clean_bid,
                item_id=clean_iid,
                movement_type="OPENING",
                qty_scaled=scaled_delta,
                unit_cost=dec_cost,
                reference_type="OPENING",
                reference_id=reference_id or "OPENING_BALANCE",
                idempotency_key=idempotency_key,
                notes=notes or "Opening inventory initialization",
                user_id=user_id,
                created_at=utc_now(),
            )
            session.add(movement)
            session.flush()

            return {
                "success": True,
                "movement_id": movement.id,
                "is_idempotent_replay": False,
                "movement_type": "OPENING",
                "quantity": dec_qty,
                "new_balance": scaled_to_qty(balance.current_qty_scaled),
                "branch_id": clean_bid,
                "item_id": clean_iid,
                "timestamp": movement.created_at.isoformat(),
            }

    # -------------------------------------------------------------------------
    # 5. Stock Adjustments (Damage, Expiry, Physical Count Variance)
    # -------------------------------------------------------------------------

    def adjust_stock(
        self,
        company_id: str,
        branch_id: str,
        item_id: str,
        qty_delta: Union[Decimal, float, int, str],
        adjustment_type: str = "PHYSICAL_COUNT",
        reason: Optional[str] = None,
        authorized_by: str = "Admin",
        unit_cost: Union[Decimal, float, int, str] = CURRENCY_ZERO,
        allow_negative_stock: bool = False,
        idempotency_key: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes a formal Stock Adjustment.
        Supports positive (found stock) or negative (shrinkage, damage, expiry) delta.
        Atomically updates StockBalance, inserts StockAdjustment record, and appends to StockMovement ledger.
        """
        dec_delta = parse_decimal_qty(qty_delta, "Adjustment Delta Quantity")
        if dec_delta == DECIMAL_ZERO:
            raise InvalidMovementError("Adjustment quantity delta cannot be zero.")
        dec_cost = parse_decimal_cost(unit_cost, "Unit Cost")
        scaled_delta = qty_to_scaled(dec_delta)
        adj_type = str(adjustment_type or "PHYSICAL_COUNT").strip().upper()

        with self.db.session_scope() as session:
            _, branch, item = self._validate_context(session, company_id, branch_id, item_id)
            clean_cid = str(company_id).strip()
            clean_bid = branch.id
            clean_iid = item.id

            if idempotency_key:
                existing_adj = session.scalar(
                    select(StockAdjustment).where(
                        and_(
                            StockAdjustment.company_id == clean_cid,
                            StockAdjustment.idempotency_key == idempotency_key,
                        )
                    )
                )
                if existing_adj:
                    bal = self._get_or_create_stock_balance(session, clean_cid, clean_bid, clean_iid)
                    return {
                        "success": True,
                        "adjustment_id": existing_adj.id,
                        "is_idempotent_replay": True,
                        "adjustment_type": existing_adj.adjustment_type,
                        "quantity": dec_delta,
                        "new_balance": scaled_to_qty(bal.current_qty_scaled),
                        "branch_id": clean_bid,
                        "item_id": clean_iid,
                    }

            balance = self._get_or_create_stock_balance(session, clean_cid, clean_bid, clean_iid)

            # If decreasing stock, verify availability
            if scaled_delta < 0 and not allow_negative_stock:
                if balance.current_qty_scaled < abs(scaled_delta):
                    available = scaled_to_qty(balance.current_qty_scaled)
                    needed = abs(dec_delta)
                    raise InsufficientStockError(
                        f"Insufficient stock for adjustment of '{item.name}'. Available: {available:g}, "
                        f"Requested reduction: {needed:g}. Negative stock is disabled."
                    )

            balance.current_qty_scaled += scaled_delta
            balance.updated_at = utc_now()

            # Record Adjustment Header / Details
            adj_id = str(uuid.uuid4())
            adjustment = StockAdjustment(
                id=adj_id,
                company_id=clean_cid,
                branch_id=clean_bid,
                item_id=clean_iid,
                item_name=item.name,
                adjustment_type=adj_type,
                quantity_scaled=scaled_delta,
                quantity=dec_delta,
                unit_cost=dec_cost,
                reason=reason or f"Stock adjustment ({adj_type})",
                authorized_by=authorized_by,
                idempotency_key=idempotency_key,
                created_at=utc_now(),
            )
            session.add(adjustment)

            # Record Ledger Movement
            movement = StockMovement(
                id=str(uuid.uuid4()),
                company_id=clean_cid,
                branch_id=clean_bid,
                item_id=clean_iid,
                movement_type="ADJUSTMENT",
                qty_scaled=scaled_delta,
                unit_cost=dec_cost,
                reference_type="STOCK_ADJUSTMENT",
                reference_id=adj_id,
                idempotency_key=f"MOV-{idempotency_key}" if idempotency_key else None,
                notes=reason or f"Stock adjustment: {adj_type}",
                user_id=user_id,
                created_at=utc_now(),
            )
            session.add(movement)
            session.flush()

            return {
                "success": True,
                "adjustment_id": adj_id,
                "movement_id": movement.id,
                "is_idempotent_replay": False,
                "adjustment_type": adj_type,
                "quantity": dec_delta,
                "new_balance": scaled_to_qty(balance.current_qty_scaled),
                "branch_id": clean_bid,
                "item_id": clean_iid,
                "timestamp": adjustment.created_at.isoformat(),
            }

    # -------------------------------------------------------------------------
    # 6. Inter-Branch Stock Transfers
    # -------------------------------------------------------------------------

    def transfer_stock(
        self,
        company_id: str,
        source_branch_id: str,
        dest_branch_id: str,
        item_id: str,
        qty: Union[Decimal, float, int, str],
        transfer_number: Optional[str] = None,
        reason: Optional[str] = None,
        authorized_by: str = "Admin",
        unit_cost: Union[Decimal, float, int, str] = CURRENCY_ZERO,
        allow_negative_stock: bool = False,
        idempotency_key: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes an atomic inventory transfer between two branches.
        Decreases source branch balance, increases destination branch balance.
        Maintains net company stock conservation.
        """
        dec_qty = parse_decimal_qty(qty, "Transfer Quantity")
        if dec_qty <= DECIMAL_ZERO:
            raise InvalidMovementError(f"Transfer quantity must be positive. Received: {dec_qty}")
        if source_branch_id == dest_branch_id:
            raise InvalidMovementError("Source and destination branches cannot be the same.")
        dec_cost = parse_decimal_cost(unit_cost, "Unit Cost")
        scaled_delta = qty_to_scaled(dec_qty)

        with self.db.session_scope() as session:
            _, src_branch, item = self._validate_context(session, company_id, source_branch_id, item_id)
            _, dst_branch, _ = self._validate_context(session, company_id, dest_branch_id)
            clean_cid = str(company_id).strip()
            clean_iid = item.id

            if idempotency_key:
                existing_t = session.scalar(
                    select(StockTransfer).where(
                        and_(
                            StockTransfer.company_id == clean_cid,
                            StockTransfer.idempotency_key == idempotency_key,
                        )
                    )
                )
                if existing_t:
                    bal_src = self._get_or_create_stock_balance(session, clean_cid, src_branch.id, clean_iid)
                    bal_dst = self._get_or_create_stock_balance(session, clean_cid, dst_branch.id, clean_iid)
                    return {
                        "success": True,
                        "transfer_id": existing_t.id,
                        "is_idempotent_replay": True,
                        "transfer_number": existing_t.transfer_number,
                        "quantity": dec_qty,
                        "source_balance": scaled_to_qty(bal_src.current_qty_scaled),
                        "dest_balance": scaled_to_qty(bal_dst.current_qty_scaled),
                    }

            # 1. Source branch deduction
            bal_src = self._get_or_create_stock_balance(session, clean_cid, src_branch.id, clean_iid)
            if not allow_negative_stock and bal_src.current_qty_scaled < scaled_delta:
                available = scaled_to_qty(bal_src.current_qty_scaled)
                raise InsufficientStockError(
                    f"Insufficient stock for transfer of '{item.name}' at branch '{src_branch.name}'. "
                    f"Available: {available:g}, Requested: {dec_qty:g}."
                )

            bal_src.current_qty_scaled -= scaled_delta
            bal_src.updated_at = utc_now()

            # 2. Destination branch addition
            bal_dst = self._get_or_create_stock_balance(session, clean_cid, dst_branch.id, clean_iid)
            bal_dst.current_qty_scaled += scaled_delta
            bal_dst.updated_at = utc_now()

            # 3. Transfer Header
            tx_id = str(uuid.uuid4())
            tx_number = transfer_number or f"TRF-{uuid.uuid4().hex[:8].upper()}"
            transfer = StockTransfer(
                id=tx_id,
                company_id=clean_cid,
                source_branch_id=src_branch.id,
                dest_branch_id=dst_branch.id,
                item_id=clean_iid,
                item_name=item.name,
                quantity_scaled=scaled_delta,
                quantity=dec_qty,
                transfer_number=tx_number,
                reason=reason or "Branch transfer",
                authorized_by=authorized_by,
                idempotency_key=idempotency_key,
                created_at=utc_now(),
            )
            session.add(transfer)

            # 4. Outward movement on source branch
            mov_out = StockMovement(
                id=str(uuid.uuid4()),
                company_id=clean_cid,
                branch_id=src_branch.id,
                item_id=clean_iid,
                movement_type="TRANSFER_OUT",
                qty_scaled=-scaled_delta,
                unit_cost=dec_cost,
                reference_type="STOCK_TRANSFER",
                reference_id=tx_id,
                idempotency_key=f"TRF-OUT-{idempotency_key}" if idempotency_key else None,
                notes=f"Transfer to branch {dst_branch.name} ({tx_number})",
                user_id=user_id,
                created_at=utc_now(),
            )
            session.add(mov_out)

            # 5. Inward movement on destination branch
            mov_in = StockMovement(
                id=str(uuid.uuid4()),
                company_id=clean_cid,
                branch_id=dst_branch.id,
                item_id=clean_iid,
                movement_type="TRANSFER_IN",
                qty_scaled=scaled_delta,
                unit_cost=dec_cost,
                reference_type="STOCK_TRANSFER",
                reference_id=tx_id,
                idempotency_key=f"TRF-IN-{idempotency_key}" if idempotency_key else None,
                notes=f"Transfer from branch {src_branch.name} ({tx_number})",
                user_id=user_id,
                created_at=utc_now(),
            )
            session.add(mov_in)
            session.flush()

            return {
                "success": True,
                "transfer_id": tx_id,
                "transfer_number": tx_number,
                "is_idempotent_replay": False,
                "quantity": dec_qty,
                "source_branch_id": src_branch.id,
                "source_balance": scaled_to_qty(bal_src.current_qty_scaled),
                "dest_branch_id": dst_branch.id,
                "dest_balance": scaled_to_qty(bal_dst.current_qty_scaled),
                "timestamp": transfer.created_at.isoformat(),
            }

    # -------------------------------------------------------------------------
    # 7. Returns Integration (Sales Return / Purchase Return)
    # -------------------------------------------------------------------------

    def record_sales_return(
        self,
        company_id: str,
        branch_id: str,
        item_id: str,
        qty: Union[Decimal, float, int, str],
        unit_cost: Union[Decimal, float, int, str] = CURRENCY_ZERO,
        reference_type: str = "SALES_RETURN",
        reference_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        notes: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Records a Sales Return (Credit Note).
        Restores stock back into branch inventory (+qty) and posts to movement ledger.
        """
        dec_qty = parse_decimal_qty(qty, "Sales Return Quantity")
        if dec_qty <= DECIMAL_ZERO:
            raise InvalidMovementError(f"Sales return quantity must be positive. Received: {dec_qty}")
        dec_cost = parse_decimal_cost(unit_cost, "Unit Cost")
        scaled_delta = qty_to_scaled(dec_qty)

        with self.db.session_scope() as session:
            _, branch, item = self._validate_context(session, company_id, branch_id, item_id)
            clean_cid = str(company_id).strip()
            clean_bid = branch.id
            clean_iid = item.id

            if idempotency_key:
                existing_m = session.scalar(
                    select(StockMovement).where(
                        and_(
                            StockMovement.company_id == clean_cid,
                            StockMovement.idempotency_key == idempotency_key,
                        )
                    )
                )
                if existing_m:
                    bal = self._get_or_create_stock_balance(session, clean_cid, clean_bid, clean_iid)
                    return {
                        "success": True,
                        "movement_id": existing_m.id,
                        "is_idempotent_replay": True,
                        "movement_type": "SALES_RETURN",
                        "quantity": dec_qty,
                        "new_balance": scaled_to_qty(bal.current_qty_scaled),
                    }

            balance = self._get_or_create_stock_balance(session, clean_cid, clean_bid, clean_iid)
            balance.current_qty_scaled += scaled_delta
            balance.updated_at = utc_now()

            movement = StockMovement(
                id=str(uuid.uuid4()),
                company_id=clean_cid,
                branch_id=clean_bid,
                item_id=clean_iid,
                movement_type="SALES_RETURN",
                qty_scaled=scaled_delta,
                unit_cost=dec_cost,
                reference_type=reference_type,
                reference_id=reference_id,
                idempotency_key=idempotency_key,
                notes=notes or "Customer sales return",
                user_id=user_id,
                created_at=utc_now(),
            )
            session.add(movement)
            session.flush()

            return {
                "success": True,
                "movement_id": movement.id,
                "is_idempotent_replay": False,
                "movement_type": "SALES_RETURN",
                "quantity": dec_qty,
                "new_balance": scaled_to_qty(balance.current_qty_scaled),
                "branch_id": clean_bid,
                "item_id": clean_iid,
                "timestamp": movement.created_at.isoformat(),
            }

    def record_purchase_return(
        self,
        company_id: str,
        branch_id: str,
        item_id: str,
        qty: Union[Decimal, float, int, str],
        allow_negative_stock: bool = False,
        unit_cost: Union[Decimal, float, int, str] = CURRENCY_ZERO,
        reference_type: str = "PURCHASE_RETURN",
        reference_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        notes: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Records a Purchase Return (Debit Note).
        Deducts stock returned to supplier (-qty) and posts to movement ledger.
        """
        dec_qty = parse_decimal_qty(qty, "Purchase Return Quantity")
        if dec_qty <= DECIMAL_ZERO:
            raise InvalidMovementError(f"Purchase return quantity must be positive. Received: {dec_qty}")
        dec_cost = parse_decimal_cost(unit_cost, "Unit Cost")
        scaled_delta = qty_to_scaled(dec_qty)

        with self.db.session_scope() as session:
            _, branch, item = self._validate_context(session, company_id, branch_id, item_id)
            clean_cid = str(company_id).strip()
            clean_bid = branch.id
            clean_iid = item.id

            if idempotency_key:
                existing_m = session.scalar(
                    select(StockMovement).where(
                        and_(
                            StockMovement.company_id == clean_cid,
                            StockMovement.idempotency_key == idempotency_key,
                        )
                    )
                )
                if existing_m:
                    bal = self._get_or_create_stock_balance(session, clean_cid, clean_bid, clean_iid)
                    return {
                        "success": True,
                        "movement_id": existing_m.id,
                        "is_idempotent_replay": True,
                        "movement_type": "PURCHASE_RETURN",
                        "quantity": dec_qty,
                        "new_balance": scaled_to_qty(bal.current_qty_scaled),
                    }

            balance = self._get_or_create_stock_balance(session, clean_cid, clean_bid, clean_iid)

            if not allow_negative_stock and balance.current_qty_scaled < scaled_delta:
                available = scaled_to_qty(balance.current_qty_scaled)
                raise InsufficientStockError(
                    f"Insufficient stock for purchase return of '{item.name}'. Available: {available:g}, "
                    f"Requested: {dec_qty:g}."
                )

            balance.current_qty_scaled -= scaled_delta
            balance.updated_at = utc_now()

            movement = StockMovement(
                id=str(uuid.uuid4()),
                company_id=clean_cid,
                branch_id=clean_bid,
                item_id=clean_iid,
                movement_type="PURCHASE_RETURN",
                qty_scaled=-scaled_delta,
                unit_cost=dec_cost,
                reference_type=reference_type,
                reference_id=reference_id,
                idempotency_key=idempotency_key,
                notes=notes or "Supplier purchase return",
                user_id=user_id,
                created_at=utc_now(),
            )
            session.add(movement)
            session.flush()

            return {
                "success": True,
                "movement_id": movement.id,
                "is_idempotent_replay": False,
                "movement_type": "PURCHASE_RETURN",
                "quantity": dec_qty,
                "new_balance": scaled_to_qty(balance.current_qty_scaled),
                "branch_id": clean_bid,
                "item_id": clean_iid,
                "timestamp": movement.created_at.isoformat(),
            }

    # -------------------------------------------------------------------------
    # 8. Ledger History, Breakdown & Audit Reconciliation
    # -------------------------------------------------------------------------

    def get_stock_ledger(
        self,
        company_id: str,
        item_id: str,
        branch_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Returns chronological, immutable stock movements for an item.
        """
        with self.db.read_session_scope() as session:
            self._validate_context(session, company_id, branch_id, item_id)
            clean_cid = str(company_id).strip()
            clean_iid = str(item_id).strip()

            stmt = select(StockMovement).where(
                and_(
                    StockMovement.company_id == clean_cid,
                    StockMovement.item_id == clean_iid,
                )
            )
            if branch_id:
                stmt = stmt.where(StockMovement.branch_id == str(branch_id).strip())
            if start_date:
                stmt = stmt.where(StockMovement.created_at >= ensure_utc(start_date))
            if end_date:
                stmt = stmt.where(StockMovement.created_at <= ensure_utc(end_date))

            stmt = stmt.order_by(StockMovement.created_at.asc(), StockMovement.id.asc()).limit(limit)
            movements = session.scalars(stmt).all()

            results = []
            for m in movements:
                results.append({
                    "id": m.id,
                    "company_id": m.company_id,
                    "branch_id": m.branch_id,
                    "item_id": m.item_id,
                    "movement_type": m.movement_type,
                    "quantity": scaled_to_qty(m.qty_scaled),
                    "quantity_scaled": m.qty_scaled,
                    "unit_cost": str(m.unit_cost),
                    "reference_type": m.reference_type,
                    "reference_id": m.reference_id,
                    "idempotency_key": m.idempotency_key,
                    "notes": m.notes,
                    "created_at": m.created_at.isoformat(),
                })
            return results

    def calculate_stock_breakdown(
        self,
        company_id: str,
        item_id: str,
        branch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Authoritative stock breakdown adhering to ERP auditing standards:
        - Opening Stock
        - Purchased Quantity
        - Sold Quantity
        - Sales Return Quantity
        - Purchase Return Quantity
        - Stock Transfer In
        - Stock Transfer Out
        - Stock Adjustments
        - Calculated Available Stock vs Materialized Balance
        """
        with self.db.read_session_scope() as session:
            _, branch, item = self._validate_context(session, company_id, branch_id, item_id)
            clean_cid = str(company_id).strip()
            clean_iid = item.id

            stmt = select(
                StockMovement.movement_type,
                func.sum(StockMovement.qty_scaled)
            ).where(
                and_(
                    StockMovement.company_id == clean_cid,
                    StockMovement.item_id == clean_iid,
                )
            )
            if branch:
                stmt = stmt.where(StockMovement.branch_id == branch.id)

            stmt = stmt.group_by(StockMovement.movement_type)
            rows = session.execute(stmt).all()

            opening_scaled = 0
            purchased_scaled = 0
            sold_scaled = 0
            sales_return_scaled = 0
            purchase_return_scaled = 0
            transfer_in_scaled = 0
            transfer_out_scaled = 0
            adjustment_scaled = 0

            for mtype, total_scaled in rows:
                scaled = int(total_scaled or 0)
                m = (mtype or "").upper()
                if m == "OPENING":
                    opening_scaled += scaled
                elif m == "PURCHASE":
                    purchased_scaled += scaled
                elif m == "SALE":
                    sold_scaled += abs(scaled)
                elif m == "SALES_RETURN":
                    sales_return_scaled += scaled
                elif m == "PURCHASE_RETURN":
                    purchase_return_scaled += abs(scaled)
                elif m == "TRANSFER_IN":
                    transfer_in_scaled += scaled
                elif m == "TRANSFER_OUT":
                    transfer_out_scaled += abs(scaled)
                elif m in ("ADJUSTMENT", "DAMAGE", "PHYSICAL_COUNT", "EXPIRED"):
                    adjustment_scaled += scaled

            net_calculated_scaled = (
                opening_scaled
                + purchased_scaled
                - sold_scaled
                + sales_return_scaled
                - purchase_return_scaled
                + transfer_in_scaled
                - transfer_out_scaled
                + adjustment_scaled
            )

            # Materialized balance query
            if branch:
                bal = session.scalar(
                    select(StockBalance).where(
                        and_(
                            StockBalance.company_id == clean_cid,
                            StockBalance.branch_id == branch.id,
                            StockBalance.item_id == clean_iid,
                        )
                    )
                )
                materialized_scaled = bal.current_qty_scaled if bal else 0
            else:
                sum_mat = session.scalar(
                    select(func.coalesce(func.sum(StockBalance.current_qty_scaled), 0)).where(
                        and_(
                            StockBalance.company_id == clean_cid,
                            StockBalance.item_id == clean_iid,
                        )
                    )
                )
                materialized_scaled = int(sum_mat or 0)

            return {
                "item_id": clean_iid,
                "item_name": item.name,
                "sku": item.sku,
                "unit": item.unit,
                "branch_id": branch.id if branch else None,
                "opening_stock": scaled_to_qty(opening_scaled),
                "purchased_quantity": scaled_to_qty(purchased_scaled),
                "sold_quantity": scaled_to_qty(sold_scaled),
                "sales_return_quantity": scaled_to_qty(sales_return_scaled),
                "purchase_return_quantity": scaled_to_qty(purchase_return_scaled),
                "stock_transfer_in": scaled_to_qty(transfer_in_scaled),
                "stock_transfer_out": scaled_to_qty(transfer_out_scaled),
                "stock_adjustments": scaled_to_qty(adjustment_scaled),
                "calculated_stock": scaled_to_qty(net_calculated_scaled),
                "materialized_balance": scaled_to_qty(materialized_scaled),
                "is_reconciled": (net_calculated_scaled == materialized_scaled),
            }

    def reconcile_balance_with_ledger(
        self,
        company_id: str,
        branch_id: str,
        item_id: str
    ) -> Dict[str, Any]:
        """
        Audit verification: confirms that the materialized stock_balances record
        exactly matches the sum of historical stock_movements.
        """
        breakdown = self.calculate_stock_breakdown(company_id, item_id, branch_id)
        if not breakdown["is_reconciled"]:
            raise TraditionalInventoryError(
                f"Ledger reconciliation mismatch for item {item_id}: "
                f"Ledger sum={breakdown['calculated_stock']}, Materialized={breakdown['materialized_balance']}"
            )
        return breakdown


# Global singleton instance
traditional_inventory_service = TraditionalInventoryService()
