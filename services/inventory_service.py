"""
Inventory Service for Anti Matrix Billing ERP.
Maintains branch-level stock balances, stock movement ledger, and low stock warnings.
"""
import uuid
from typing import Dict, Any, List, Optional
from db.database import db_manager, DatabaseManager
from core.logging_config import logger


class InventoryService:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or db_manager

    def get_stock(self, company_id: str, item_id: str, branch_id: Optional[str] = None) -> float:
        """Returns the current available quantity for an item."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if branch_id:
                cursor.execute("""
                    SELECT current_qty FROM stock_balances
                    WHERE branch_id = ? AND item_id = ?;
                """, (branch_id, item_id))
            else:
                cursor.execute("""
                    SELECT SUM(current_qty) FROM stock_balances
                    WHERE company_id = ? AND item_id = ?;
                """, (company_id, item_id))
            row = cursor.fetchone()
            if row and row[0] is not None:
                return float(row[0])
            return 0.0

    def adjust_stock(
        self,
        company_id: str,
        branch_id: str,
        item_id: str,
        qty_delta: float,
        movement_type: str = "ADJUSTMENT",
        unit_cost: float = 0.0,
        reference_type: str = "MANUAL",
        reference_id: Optional[str] = None,
        notes: str = ""
    ) -> float:
        """
        Adjust stock quantity atomically and record a movement in the ledger.
        Positive qty_delta increases stock; negative qty_delta decreases stock.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Update stock balance
            cursor.execute("""
                INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(branch_id, item_id) DO UPDATE SET
                    current_qty = current_qty + excluded.current_qty,
                    last_updated = CURRENT_TIMESTAMP;
            """, (str(uuid.uuid4()), company_id, branch_id, item_id, qty_delta))

            # Query updated balance
            cursor.execute("SELECT current_qty FROM stock_balances WHERE branch_id = ? AND item_id = ?;", (branch_id, item_id))
            new_balance = cursor.fetchone()["current_qty"]

            # Record movement ledger entry
            cursor.execute("""
                INSERT INTO stock_movements (
                    id, company_id, branch_id, item_id, movement_type,
                    qty, unit_cost, reference_type, reference_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                str(uuid.uuid4()),
                company_id,
                branch_id,
                item_id,
                movement_type,
                qty_delta,
                unit_cost,
                reference_type,
                reference_id or "",
                notes
            ))
            conn.commit()

        logger.info(f"Stock adjusted for item {item_id}: delta={qty_delta}, new_balance={new_balance}")
        return float(new_balance)

    def get_low_stock_report(self, company_id: str, threshold: float = 10.0) -> List[Dict[str, Any]]:
        """List all active items with stock at or below the given threshold."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT i.id, i.name, i.unit, i.sales_price,
                       COALESCE(sb.current_qty, 0.0) as current_qty
                FROM items i
                LEFT JOIN branches br ON br.company_id = i.company_id AND br.is_default = 1
                LEFT JOIN stock_balances sb ON sb.branch_id = br.id AND sb.item_id = i.id
                WHERE i.company_id = ? AND i.is_active = 1 AND COALESCE(sb.current_qty, 0.0) <= ?
                ORDER BY current_qty ASC;
            """, (company_id, threshold))
            return [dict(r) for r in cursor.fetchall()]


inventory_service = InventoryService()

