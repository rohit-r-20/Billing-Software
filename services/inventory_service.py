"""
Centralized Inventory Service for Anti Matrix Billing ERP.
Authoritative stock ledger, branch & godown stock balances, valuation engine (Weighted Average Cost),
stock adjustments, inter-godown/branch transfers, and real-time reconciliation.
Shared identically by Traditional Billing and Fast Billing.
"""
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from db.database import db_manager, DatabaseManager
from core.logging_config import logger


class InventoryService:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or db_manager

    def _resolve_company_id(self, company_id: Optional[str]) -> str:
        cid = str(company_id or "").strip()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if cid:
                cursor.execute("SELECT id FROM companies WHERE id = ? OR UPPER(code) = ?;", (cid, cid.upper()))
                c_row = cursor.fetchone()
                if c_row:
                    return c_row["id"]
            cursor.execute("SELECT id FROM companies ORDER BY id ASC LIMIT 1;")
            c_default = cursor.fetchone()
            return c_default["id"] if c_default else cid

    def _get_default_branch_id(self, company_id: str) -> Optional[str]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM branches WHERE company_id = ? AND is_default = 1;", (company_id,))
            row = cursor.fetchone()
            if row:
                return row["id"]
            cursor.execute("SELECT id FROM branches WHERE company_id = ? LIMIT 1;", (company_id,))
            row2 = cursor.fetchone()
            return row2["id"] if row2 else None

    def get_stock(self, company_id: str, item_id: str, branch_id: Optional[str] = None) -> float:
        """Returns the current authoritative available quantity for an item."""
        actual_comp_id = self._resolve_company_id(company_id)
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
                """, (actual_comp_id, item_id))
            row = cursor.fetchone()
            if row and row[0] is not None:
                return float(row[0])
            return 0.0

    def validate_stock_availability(
        self,
        company_id: str,
        branch_id: Optional[str],
        items: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str]]:
        """
        Validates stock availability against the retail negative stock policy.
        Returns (is_valid, list_of_error_messages).
        """
        actual_comp_id = self._resolve_company_id(company_id)
        actual_branch = branch_id or self._get_default_branch_id(actual_comp_id)
        errors = []

        for it in items:
            item_id = it.get("id") or it.get("item_id")
            qty_needed = float(it.get("qty") or 0.0)
            name = it.get("name") or "Product"

            if item_id and actual_branch:
                current = self.get_stock(actual_comp_id, item_id, actual_branch)
                if current - qty_needed < 0:
                    errors.append(
                        f"Insufficient stock for '{name}'. Requested: {qty_needed:g}, Available: {current:g}."
                    )

        return (len(errors) == 0, errors)

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
        Adjust stock quantity atomically and record a movement in the authoritative ledger.
        Positive qty_delta increases stock; negative qty_delta decreases stock.
        """
        actual_comp_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Update materialized stock balance
            cursor.execute("""
                INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(branch_id, item_id) DO UPDATE SET
                    current_qty = current_qty + excluded.current_qty,
                    last_updated = CURRENT_TIMESTAMP;
            """, (str(uuid.uuid4()), actual_comp_id, branch_id, item_id, qty_delta))

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
                actual_comp_id,
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

        try:
            self.evaluate_low_stock_alerts(actual_comp_id)
        except Exception as e:
            logger.debug(f"evaluate_low_stock_alerts after adjust_stock: {e}")

        logger.info(f"Authoritative stock updated for item {item_id}: delta={qty_delta}, new_balance={new_balance} ({movement_type})")
        return float(new_balance)

    def record_stock_adjustment(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Records a formal Stock Adjustment voucher (Damage, Expiry, Physical Count Variance, Opening).
        Atomically updates inventory balances and creates permanent audit ledger movements.
        """
        actual_comp_id = self._resolve_company_id(company_id)
        branch_id = data.get("branch_id") or self._get_default_branch_id(actual_comp_id)
        adj_type = data.get("adj_type") or "DAMAGE"
        reason = data.get("reason") or "Physical Inventory Adjustment"
        auth_by = data.get("authorized_by") or "Admin"
        items = data.get("items") or []
        adj_date = data.get("adj_date") or datetime.now().strftime("%Y-%m-%d")

        if not items:
            raise ValueError("Adjustment voucher must contain at least one item.")

        adj_id = str(uuid.uuid4())
        # Generate next adjustment voucher number
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(id) FROM stock_adjustments WHERE company_id = ?;", (actual_comp_id,))
            cnt = cursor.fetchone()[0] + 1
            vch_no = f"SA-{str(cnt).zfill(6)}"

            cursor.execute("""
                INSERT INTO stock_adjustments (
                    id, company_id, branch_id, vch_no, adj_date, adj_type,
                    reason, authorized_by, notes, total_items
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                adj_id, actual_comp_id, branch_id, vch_no, adj_date, adj_type,
                reason, auth_by, data.get("notes", ""), len(items)
            ))

            for it in items:
                item_id = it["item_id"]
                diff_qty = float(it["diff_qty"])  # positive = increase, negative = write-off/decrease
                unit_cost = float(it.get("unit_cost") or 0.0)

                cursor.execute("""
                    INSERT INTO stock_adjustment_items (
                        id, adjustment_id, item_id, system_qty, physical_qty, diff_qty, unit_cost, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    str(uuid.uuid4()), adj_id, item_id,
                    float(it.get("system_qty") or 0.0),
                    float(it.get("physical_qty")) if it.get("physical_qty") is not None else None,
                    diff_qty, unit_cost, it.get("notes", "")
                ))

                # Update stock balance
                cursor.execute("""
                    INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(branch_id, item_id) DO UPDATE SET
                        current_qty = current_qty + excluded.current_qty,
                        last_updated = CURRENT_TIMESTAMP;
                """, (str(uuid.uuid4()), actual_comp_id, branch_id, item_id, diff_qty))

                # Movement ledger entry
                cursor.execute("""
                    INSERT INTO stock_movements (
                        id, company_id, branch_id, item_id, movement_type,
                        qty, unit_cost, reference_type, reference_id, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ADJUSTMENT', ?, ?);
                """, (
                    str(uuid.uuid4()), actual_comp_id, branch_id, item_id,
                    adj_type, diff_qty, unit_cost, vch_no, f"{reason} (Auth by: {auth_by})"
                ))

            conn.commit()

        try:
            self.evaluate_low_stock_alerts(actual_comp_id)
        except Exception as e:
            logger.debug(f"evaluate_low_stock_alerts after adjustment: {e}")

        logger.info(f"Stock Adjustment {vch_no} posted successfully ({len(items)} items).")
        return {"id": adj_id, "vch_no": vch_no, "adj_type": adj_type, "items_count": len(items)}

    def record_stock_transfer(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transfers stock between branches or godowns.
        Decreases source branch stock and increases destination branch stock.
        Company-wide stock remains identical.
        """
        actual_comp_id = self._resolve_company_id(company_id)
        src_branch = data.get("source_branch_id")
        dst_branch = data.get("dest_branch_id")
        items = data.get("items") or []
        transfer_date = data.get("transfer_date") or datetime.now().strftime("%Y-%m-%d")
        reason = data.get("reason") or "Internal Transfer"
        created_by = data.get("created_by") or "Admin"

        if not src_branch or not dst_branch:
            raise ValueError("Source and destination branches are required.")
        if src_branch == dst_branch:
            raise ValueError("Source and destination branches cannot be the same.")
        if not items:
            raise ValueError("Transfer must contain at least one item.")

        # Check source availability
        for it in items:
            item_id = it["item_id"]
            qty = float(it["qty"])
            avail = self.get_stock(actual_comp_id, item_id, src_branch)
            if avail < qty:
                raise ValueError(f"Insufficient stock at source branch. Requested: {qty:g}, Available: {avail:g}.")

        transfer_id = str(uuid.uuid4())
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(id) FROM stock_transfers WHERE company_id = ?;", (actual_comp_id,))
            cnt = cursor.fetchone()[0] + 1
            transfer_no = f"TR-{str(cnt).zfill(6)}"

            cursor.execute("""
                INSERT INTO stock_transfers (
                    id, company_id, transfer_no, transfer_date, source_branch_id,
                    dest_branch_id, status, reason, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, 'COMPLETED', ?, ?);
            """, (transfer_id, actual_comp_id, transfer_no, transfer_date, src_branch, dst_branch, reason, created_by))

            for it in items:
                item_id = it["item_id"]
                qty = float(it["qty"])
                unit_cost = float(it.get("unit_cost") or 0.0)

                cursor.execute("""
                    INSERT INTO stock_transfer_items (
                        id, transfer_id, item_id, qty, unit, unit_cost
                    ) VALUES (?, ?, ?, ?, ?, ?);
                """, (str(uuid.uuid4()), transfer_id, item_id, qty, it.get("unit", "Pcs."), unit_cost))

                # 1. Deduct from source branch
                cursor.execute("""
                    UPDATE stock_balances
                    SET current_qty = current_qty - ?, last_updated = CURRENT_TIMESTAMP
                    WHERE branch_id = ? AND item_id = ?;
                """, (qty, src_branch, item_id))

                cursor.execute("""
                    INSERT INTO stock_movements (
                        id, company_id, branch_id, item_id, movement_type,
                        qty, unit_cost, reference_type, reference_id, notes
                    ) VALUES (?, ?, ?, ?, 'TRANSFER_OUT', ?, ?, 'TRANSFER', ?, ?);
                """, (str(uuid.uuid4()), actual_comp_id, src_branch, item_id, -qty, unit_cost, transfer_no, f"Transfer to branch {dst_branch}"))

                # 2. Add to destination branch
                cursor.execute("""
                    INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(branch_id, item_id) DO UPDATE SET
                        current_qty = current_qty + excluded.current_qty,
                        last_updated = CURRENT_TIMESTAMP;
                """, (str(uuid.uuid4()), actual_comp_id, dst_branch, item_id, qty))

                cursor.execute("""
                    INSERT INTO stock_movements (
                        id, company_id, branch_id, item_id, movement_type,
                        qty, unit_cost, reference_type, reference_id, notes
                    ) VALUES (?, ?, ?, ?, 'TRANSFER_IN', ?, ?, 'TRANSFER', ?, ?);
                """, (str(uuid.uuid4()), actual_comp_id, dst_branch, item_id, qty, unit_cost, transfer_no, f"Transfer from branch {src_branch}"))

            conn.commit()

        logger.info(f"Stock Transfer {transfer_no} completed from {src_branch} to {dst_branch}.")
        return {"id": transfer_id, "transfer_no": transfer_no, "status": "COMPLETED"}

    def get_stock_summary(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        query: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Authoritative Stock Summary item-wise report.
        Reconciles:
        Opening Stock + Purchases Inward + Sales Returns + Adjustments In
        - Sales Outward - Purchase Returns - Adjustments Out
        = Closing Stock.
        Calculates Weighted Average Cost and total stock value.
        """
        actual_comp_id = self._resolve_company_id(company_id)
        target_branch = branch_id or self._get_default_branch_id(actual_comp_id)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Fetch all active items
            cursor.execute("""
                SELECT i.id, i.name, i.alias, i.item_group, i.unit, i.op_stock_qty,
                       i.op_stock_val, i.purc_price, i.sales_price,
                       i.min_stock_alert_level, i.alert_enabled,
                       COALESCE(sb.current_qty, 0.0) as closing_stock,
                       GROUP_CONCAT(ib.barcode, ', ') as barcodes
                FROM items i
                LEFT JOIN stock_balances sb ON sb.item_id = i.id AND sb.branch_id = ?
                LEFT JOIN item_barcodes ib ON ib.item_id = i.id
                WHERE i.company_id = ? AND i.is_active = 1
                GROUP BY i.id
                ORDER BY i.name ASC;
            """, (target_branch, actual_comp_id))
            item_rows = [dict(r) for r in cursor.fetchall()]

            # Fetch aggregated movements per item
            cursor.execute("""
                SELECT item_id,
                       movement_type,
                       SUM(CASE WHEN qty > 0 THEN qty ELSE 0 END) as positive_qty,
                       SUM(CASE WHEN qty < 0 THEN ABS(qty) ELSE 0 END) as negative_qty,
                       SUM(CASE WHEN movement_type IN ('PURCHASE', 'OPENING') AND qty > 0 THEN qty * unit_cost ELSE 0 END) as total_purchase_cost,
                       SUM(CASE WHEN movement_type IN ('PURCHASE', 'OPENING') AND qty > 0 THEN qty ELSE 0 END) as total_purchase_qty
                FROM stock_movements
                WHERE company_id = ? AND (? IS NULL OR branch_id = ?)
                GROUP BY item_id, movement_type;
            """, (actual_comp_id, target_branch, target_branch))
            mov_rows = cursor.fetchall()

        # Aggregate movements by item_id
        mov_map = {}
        for m in mov_rows:
            iid = m["item_id"]
            if iid not in mov_map:
                mov_map[iid] = {
                    "purchase_inward": 0.0,
                    "sales_outward": 0.0,
                    "purchase_returns": 0.0,
                    "sales_returns": 0.0,
                    "adjustments_in": 0.0,
                    "adjustments_out": 0.0,
                    "cost_pool": 0.0,
                    "qty_pool": 0.0
                }
            mtype = m["movement_type"]
            p_qty = float(m["positive_qty"] or 0.0)
            n_qty = float(m["negative_qty"] or 0.0)

            if mtype in ("PURCHASE", "INWARD"):
                mov_map[iid]["purchase_inward"] += p_qty
                mov_map[iid]["cost_pool"] += float(m["total_purchase_cost"] or 0.0)
                mov_map[iid]["qty_pool"] += float(m["total_purchase_qty"] or 0.0)
            elif mtype in ("SALE", "OUTWARD"):
                mov_map[iid]["sales_outward"] += n_qty
            elif mtype == "PURCHASE_RETURN":
                mov_map[iid]["purchase_returns"] += n_qty
            elif mtype == "SALES_RETURN":
                mov_map[iid]["sales_returns"] += p_qty
            elif mtype in ("ADJUSTMENT", "DAMAGE", "EXPIRED", "TRANSFER_OUT", "TRANSFER_IN"):
                mov_map[iid]["adjustments_in"] += p_qty
                mov_map[iid]["adjustments_out"] += n_qty

        report = []
        for it in item_rows:
            iid = it["id"]
            m = mov_map.get(iid, {
                "purchase_inward": 0.0, "sales_outward": 0.0,
                "purchase_returns": 0.0, "sales_returns": 0.0,
                "adjustments_in": 0.0, "adjustments_out": 0.0,
                "cost_pool": 0.0, "qty_pool": 0.0
            })
            op_qty = float(it["op_stock_qty"] or 0.0)
            purc_in = m["purchase_inward"]
            sales_out = m["sales_outward"]
            purc_ret = m["purchase_returns"]
            sales_ret = m["sales_returns"]
            adj_net = m["adjustments_in"] - m["adjustments_out"]
            closing = float(it["closing_stock"] or 0.0)

            # Valuation: Weighted Average Cost (WAC)
            # Add opening balance to cost pool
            op_cost = float(it["op_stock_val"] or (op_qty * (it["purc_price"] or 0.0)))
            total_cost_pool = op_cost + m["cost_pool"]
            total_qty_pool = op_qty + m["qty_pool"]

            if total_qty_pool > 0 and total_cost_pool > 0:
                wac_rate = round(total_cost_pool / total_qty_pool, 2)
            else:
                wac_rate = float(it["purc_price"] or 0.0)

            stock_val = round(closing * wac_rate, 2)
            raw_min_stock = it.get("min_stock_alert_level")
            alert_enabled = int(it.get("alert_enabled") if it.get("alert_enabled") is not None else 1) == 1

            if raw_min_stock is not None and alert_enabled:
                reorder_lvl = float(raw_min_stock)
                has_threshold = True
            else:
                reorder_lvl = None
                has_threshold = False

            if closing < 0:
                status = "NEGATIVE_STOCK"
            elif closing == 0:
                status = "OUT_OF_STOCK"
            elif has_threshold and closing < reorder_lvl:
                status = "LOW_STOCK"
            else:
                status = "OPTIMAL"

            is_low_stock = (closing < reorder_lvl) if has_threshold else False

            report.append({
                "item_id": iid,
                "item_code": it.get("alias") or it["name"][:6],
                "product_name": it["name"],
                "barcode": it.get("barcodes") or it.get("alias") or "-",
                "category": it.get("item_group") or "General",
                "unit": it.get("unit") or "Pcs.",
                "opening_stock": op_qty,
                "purchase_inward": purc_in,
                "sales_outward": sales_out,
                "purchase_returns": purc_ret,
                "sales_returns": sales_ret,
                "stock_adjustments": adj_net,
                "closing_stock": closing,
                "valuation_rate": wac_rate,
                "stock_value": stock_val,
                "reorder_level": reorder_lvl,
                "min_stock_alert_level": reorder_lvl,
                "alert_enabled": 1 if alert_enabled else 0,
                "is_low_stock": is_low_stock,
                "status": status,
                "sales_price": float(it.get("sales_price") or 0.0)
            })

        if query.strip():
            qup = query.strip().upper()
            report = [r for r in report if qup in r["product_name"].upper() or qup in r["barcode"].upper() or qup in r["category"].upper()]

        return report

    def get_stock_item_ledger(
        self,
        company_id: str,
        item_id: str,
        branch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Returns the complete chronological ledger of stock movements for an item.
        Displays date, voucher no, movement type, reference, inward, outward, and running balance.
        """
        actual_comp_id = self._resolve_company_id(company_id)
        target_branch = branch_id or self._get_default_branch_id(actual_comp_id)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM items WHERE id = ?;", (item_id,))
            item_row = cursor.fetchone()
            if not item_row:
                return {"item": None, "ledger": [], "closing_balance": 0.0}

            cursor.execute("""
                SELECT sm.*, b.name as branch_name
                FROM stock_movements sm
                LEFT JOIN branches b ON b.id = sm.branch_id
                WHERE sm.company_id = ? AND sm.item_id = ? AND (? IS NULL OR sm.branch_id = ?)
                ORDER BY sm.created_at ASC, sm.id ASC;
            """, (actual_comp_id, item_id, target_branch, target_branch))
            movs = [dict(r) for r in cursor.fetchall()]

        running_balance = 0.0
        ledger = []

        # Opening entry
        op_qty = float(item_row["op_stock_qty"] or 0.0)
        if op_qty > 0:
            running_balance += op_qty
            ledger.append({
                "date": str(item_row["created_at"])[:10],
                "voucher_no": "OPENING",
                "transaction_type": "Opening Stock",
                "reference_no": "-",
                "inward_qty": op_qty,
                "outward_qty": 0.0,
                "running_balance": running_balance,
                "unit_cost": float(item_row["purc_price"] or 0.0),
                "notes": "Opening balance"
            })

        for m in movs:
            qty = float(m["qty"])
            inward = qty if qty > 0 else 0.0
            outward = abs(qty) if qty < 0 else 0.0
            running_balance += qty

            ledger.append({
                "date": str(m["created_at"])[:10],
                "voucher_no": m.get("reference_id") or "-",
                "transaction_type": m.get("movement_type"),
                "reference_no": f"{m.get('reference_type')}: {m.get('reference_id')}",
                "inward_qty": inward,
                "outward_qty": outward,
                "running_balance": round(running_balance, 3),
                "unit_cost": float(m.get("unit_cost") or 0.0),
                "notes": m.get("notes") or ""
            })

        return {
            "item": dict(item_row),
            "ledger": ledger,
            "closing_balance": round(running_balance, 3)
        }

    def get_inventory_dashboard(self, company_id: str) -> Dict[str, Any]:
        """Provides high-level KPI metrics for the Inventory Master view."""
        actual_comp_id = self._resolve_company_id(company_id)
        summary = self.get_stock_summary(actual_comp_id)

        total_items = len(summary)
        total_qty = sum(r["closing_stock"] for r in summary)
        total_val = sum(r["stock_value"] for r in summary)
        low_stock = sum(1 for r in summary if r["status"] == "LOW_STOCK")
        out_of_stock = sum(1 for r in summary if r["status"] == "OUT_OF_STOCK")
        neg_stock = sum(1 for r in summary if r["status"] == "NEGATIVE_STOCK")

        return {
            "total_active_products": total_items,
            "total_stock_quantity": round(total_qty, 2),
            "total_stock_valuation": round(total_val, 2),
            "low_stock_count": low_stock,
            "out_of_stock_count": out_of_stock,
            "negative_stock_exceptions": neg_stock
        }

    def get_low_stock_report(self, company_id: str, threshold: float = 10.0) -> List[Dict[str, Any]]:
        actual_comp_id = self._resolve_company_id(company_id)
        summary = self.get_stock_summary(actual_comp_id)
        return [r for r in summary if r["closing_stock"] <= threshold]

    def evaluate_low_stock_alerts(self, company_id: str) -> List[Dict[str, Any]]:
        """
        Authoritatively evaluates items with configured low-stock thresholds against
        real-time stock balances across default branch / company.
        Creates or updates 'ACTIVE' alerts in low_stock_alerts table when stock < min_stock_alert_level.
        Automatically resolves alerts when stock >= min_stock_alert_level.
        Returns list of active low-stock alerts.
        """
        actual_comp_id = self._resolve_company_id(company_id)
        default_branch = self._get_default_branch_id(actual_comp_id)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT i.id, i.name, i.alias, i.unit, i.min_stock_alert_level, i.alert_enabled,
                       COALESCE(sb.current_qty, 0.0) as available_qty,
                       GROUP_CONCAT(ib.barcode, ', ') as barcodes
                FROM items i
                LEFT JOIN stock_balances sb ON sb.item_id = i.id AND sb.branch_id = ?
                LEFT JOIN item_barcodes ib ON ib.item_id = i.id
                WHERE i.company_id = ? AND i.is_active = 1 
                  AND i.alert_enabled = 1 AND i.min_stock_alert_level IS NOT NULL
                GROUP BY i.id
                ORDER BY i.name ASC;
            """, (default_branch, actual_comp_id))
            items_to_check = [dict(r) for r in cursor.fetchall()]

            active_alerts = []

            for it in items_to_check:
                item_id = it["id"]
                threshold = float(it["min_stock_alert_level"])
                available = float(it["available_qty"])
                bcode = it.get("barcodes") or it.get("alias") or "-"

                if available < threshold:
                    shortfall = round(threshold - available, 2)
                    cursor.execute("""
                        SELECT id, status FROM low_stock_alerts
                        WHERE company_id = ? AND item_id = ? AND status IN ('ACTIVE', 'DISMISSED');
                    """, (actual_comp_id, item_id))
                    existing = cursor.fetchone()

                    if existing:
                        alert_id = existing["id"]
                        current_status = existing["status"]
                        cursor.execute("""
                            UPDATE low_stock_alerts
                            SET available_qty = ?, threshold = ?, last_evaluated_at = CURRENT_TIMESTAMP
                            WHERE id = ?;
                        """, (available, threshold, alert_id))
                    else:
                        alert_id = str(uuid.uuid4())
                        current_status = "ACTIVE"
                        cursor.execute("""
                            INSERT INTO low_stock_alerts (
                                id, company_id, item_id, threshold, available_qty, status, last_evaluated_at
                            ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', CURRENT_TIMESTAMP);
                        """, (alert_id, actual_comp_id, item_id, threshold, available))

                    active_alerts.append({
                        "alert_id": alert_id,
                        "item_id": item_id,
                        "product_name": it["name"],
                        "barcode": bcode,
                        "unit": it.get("unit") or "Pcs.",
                        "current_stock": available,
                        "threshold": threshold,
                        "shortfall": shortfall,
                        "status": current_status,
                        "is_negative": available < 0,
                        "is_zero": available == 0
                    })
                else:
                    cursor.execute("""
                        UPDATE low_stock_alerts
                        SET status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP, last_evaluated_at = CURRENT_TIMESTAMP
                        WHERE company_id = ? AND item_id = ? AND status IN ('ACTIVE', 'DISMISSED');
                    """, (actual_comp_id, item_id))

            conn.commit()

        return active_alerts

    def get_active_low_stock_alerts(self, company_id: str, include_dismissed: bool = False) -> List[Dict[str, Any]]:
        """Retrieve authoritative active low stock alerts."""
        actual_comp_id = self._resolve_company_id(company_id)
        all_alerts = self.evaluate_low_stock_alerts(actual_comp_id)
        if not include_dismissed:
            return [a for a in all_alerts if a["status"] == "ACTIVE"]
        return all_alerts

    def dismiss_low_stock_alert(self, company_id: str, alert_id: Optional[str] = None) -> bool:
        """Dismiss a specific alert or all active alerts for current session."""
        actual_comp_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if alert_id:
                cursor.execute("""
                    UPDATE low_stock_alerts
                    SET status = 'DISMISSED', dismissed_at = CURRENT_TIMESTAMP
                    WHERE company_id = ? AND id = ?;
                """, (actual_comp_id, alert_id))
            else:
                cursor.execute("""
                    UPDATE low_stock_alerts
                    SET status = 'DISMISSED', dismissed_at = CURRENT_TIMESTAMP
                    WHERE company_id = ? AND status = 'ACTIVE';
                """, (actual_comp_id,))
            conn.commit()
        return True


inventory_service = InventoryService()
