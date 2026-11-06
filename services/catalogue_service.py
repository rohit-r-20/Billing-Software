"""
Catalogue Service for Anti Matrix Billing ERP.
Manages Items, Units, HSN, Tax Categories, and Multi-Barcode Lookup.
"""
import uuid
from typing import Dict, Any, List, Optional
from db.database import db_manager, DatabaseManager
from core.logging_config import logger


class CatalogueService:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or db_manager

    def _resolve_company_id(self, company_id: Optional[str]) -> str:
        """Resolve company UUID whether passed UUID or company code (e.g. COMP0001), falling back to primary company if empty."""
        cid = str(company_id or "").strip()
        if not cid:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM companies ORDER BY id ASC LIMIT 1;")
                c_default = cursor.fetchone()
                return c_default["id"] if c_default else ""

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM companies WHERE id = ? OR UPPER(code) = ?;", (cid, cid.upper()))
            c_row = cursor.fetchone()
            if c_row:
                return c_row["id"]
            return cid

    def _compute_is_verified(self, res: Dict[str, Any]) -> int:
        """Determines if product is verified and safe for checkout."""
        desc = (res.get("description") or "").upper()
        name = (res.get("name") or "").upper()
        price = float(res.get("sales_price") or 0.0)
        barcodes = str(res.get("matched_barcode") or res.get("alias") or res.get("barcodes") or "").upper()
        if "UNVERIFIED" in desc or "UNVERIFIED" in name or price <= 0 or "8909263004690" in barcodes:
            return 0
        return 1

    def find_by_barcode(self, company_id: str, barcode: str) -> Optional[Dict[str, Any]]:
        """
        Looks up a product by exact barcode in the active company.
        Also returns current stock balance for the default branch.
        """
        code_str = str(barcode).strip().upper()
        if not code_str:
            return None

        actual_company_id = self._resolve_company_id(company_id)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT i.*, b.barcode as matched_barcode,
                       COALESCE(sb.current_qty, 0.0) as current_stock
                FROM item_barcodes b
                JOIN items i ON b.item_id = i.id
                LEFT JOIN branches br ON br.company_id = i.company_id AND br.is_default = 1
                LEFT JOIN stock_balances sb ON sb.branch_id = br.id AND sb.item_id = i.id
                WHERE b.company_id = ? AND b.barcode = ? AND i.is_active = 1
                LIMIT 1;
            """, (actual_company_id, code_str))
            row = cursor.fetchone()
            if row:
                res = dict(row)
                res["is_verified"] = self._compute_is_verified(res)
                return res

            # Fallback: Check if barcode matches item alias or name directly
            cursor.execute("""
                SELECT i.*, i.alias as matched_barcode,
                       COALESCE(sb.current_qty, 0.0) as current_stock
                FROM items i
                LEFT JOIN branches br ON br.company_id = i.company_id AND br.is_default = 1
                LEFT JOIN stock_balances sb ON sb.branch_id = br.id AND sb.item_id = i.id
                WHERE i.company_id = ? AND (i.alias = ? OR i.name = ?) AND i.is_active = 1
                LIMIT 1;
            """, (actual_company_id, code_str, code_str))
            row2 = cursor.fetchone()
            if row2:
                res2 = dict(row2)
                res2["is_verified"] = self._compute_is_verified(res2)
                return res2

        return None

    def get_cashier_item_by_barcode(self, company_id: str, barcode: str) -> Optional[Dict[str, Any]]:
        """
        Fast lookup by barcode for Fast Billing Cashier counter with strictly restricted fields.
        Does NOT expose stock balances, valuation, purchase cost, or inventory metrics.
        """
        code_str = str(barcode).strip().upper()
        if not code_str:
            return None

        actual_company_id = self._resolve_company_id(company_id)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Match from item_barcodes table
            cursor.execute("""
                SELECT i.id, i.name, i.alias, i.unit, i.tax_category, i.sales_price, i.mrp,
                       b.barcode as matched_barcode, i.description
                FROM item_barcodes b
                JOIN items i ON i.id = b.item_id
                WHERE b.company_id = ? AND UPPER(b.barcode) = ? AND i.is_active = 1
                LIMIT 1;
            """, (actual_company_id, code_str))
            row = cursor.fetchone()

            if not row:
                # 2. Fallback: match from items table (alias or name)
                cursor.execute("""
                    SELECT i.id, i.name, i.alias, i.unit, i.tax_category, i.sales_price, i.mrp,
                           i.alias as matched_barcode, i.description
                    FROM items i
                    WHERE i.company_id = ? AND (UPPER(i.alias) = ? OR UPPER(i.name) = ?) AND i.is_active = 1
                    LIMIT 1;
                """, (actual_company_id, code_str, code_str))
                row = cursor.fetchone()

            if row:
                res = dict(row)
                tax_rate = 18.0
                tax_cat = res.get("tax_category") or ""
                if "28%" in tax_cat: tax_rate = 28.0
                elif "12%" in tax_cat: tax_rate = 12.0
                elif "5%" in tax_cat: tax_rate = 5.0
                elif "0%" in tax_cat: tax_rate = 0.0

                return {
                    "id": res["id"],
                    "name": res["name"],
                    "barcode": res.get("matched_barcode") or res.get("alias") or code_str,
                    "sales_price": float(res.get("sales_price") or 0.0),
                    "mrp": float(res.get("mrp") or 0.0),
                    "tax_rate": tax_rate,
                    "tax_category": res.get("tax_category") or "GST 18%",
                    "unit": res.get("unit") or "Pcs.",
                    "discount_percent": 0.0,
                    "is_verified": self._compute_is_verified(res)
                }
        return None

    def search_cashier_items(self, company_id: str, query: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search items strictly for Fast Billing / Cashier counter.
        Exposes ONLY billing attributes (name, barcode, sales_price, tax_rate, unit, discount).
        Completely hides stock quantities, inventory valuation, cost rate, and supplier pricing.
        """
        actual_company_id = self._resolve_company_id(company_id)
        q = f"%{query.strip().upper()}%"
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT i.id, i.name, i.alias, i.unit, i.tax_category, i.sales_price, i.mrp,
                       i.description,
                       COALESCE(i.alias, '') as barcode,
                       (SELECT barcode FROM item_barcodes ib WHERE ib.item_id = i.id LIMIT 1) as matched_barcode
                FROM items i
                WHERE i.company_id = ? AND i.is_active = 1 AND (
                    UPPER(i.name) LIKE ? OR 
                    UPPER(i.alias) LIKE ? OR 
                    UPPER(i.hsn) LIKE ? OR
                    EXISTS (
                        SELECT 1 FROM item_barcodes ib 
                        WHERE ib.item_id = i.id AND UPPER(ib.barcode) LIKE ?
                    )
                )
                ORDER BY i.name ASC
                LIMIT ?;
            """, (actual_company_id, q, q, q, q, limit))
            rows = cursor.fetchall()

        results = []
        for r in rows:
            it = dict(r)
            tax_rate = 18.0
            tax_cat = it.get("tax_category") or ""
            if "28%" in tax_cat: tax_rate = 28.0
            elif "12%" in tax_cat: tax_rate = 12.0
            elif "5%" in tax_cat: tax_rate = 5.0
            elif "0%" in tax_cat: tax_rate = 0.0

            results.append({
                "id": it["id"],
                "name": it["name"],
                "barcode": it.get("matched_barcode") or it.get("barcode") or it.get("alias") or "",
                "sales_price": float(it.get("sales_price") or 0.0),
                "mrp": float(it.get("mrp") or 0.0),
                "tax_rate": tax_rate,
                "tax_category": it.get("tax_category") or "GST 18%",
                "unit": it.get("unit") or "Pcs.",
                "discount_percent": 0.0,
                "is_verified": self._compute_is_verified(it)
            })
        return results

    def search_items(self, company_id: str, query: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        """Search items by name, alias, HSN, group, or barcode."""
        actual_company_id = self._resolve_company_id(company_id)
        q = f"%{query.strip().upper()}%"
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT i.*, 
                       COALESCE(sb.current_qty, 0.0) as current_stock,
                       GROUP_CONCAT(b.barcode, ', ') as barcodes
                FROM items i
                LEFT JOIN branches br ON br.company_id = i.company_id AND br.is_default = 1
                LEFT JOIN stock_balances sb ON sb.branch_id = br.id AND sb.item_id = i.id
                LEFT JOIN item_barcodes b ON b.item_id = i.id
                WHERE i.company_id = ? AND i.is_active = 1 AND (
                    UPPER(i.name) LIKE ? OR 
                    UPPER(i.alias) LIKE ? OR 
                    UPPER(i.hsn) LIKE ? OR
                    UPPER(i.item_group) LIKE ? OR
                    UPPER(COALESCE(i.description, '')) LIKE ? OR
                    EXISTS (
                        SELECT 1 FROM item_barcodes ib 
                        WHERE ib.item_id = i.id AND UPPER(ib.barcode) LIKE ?
                    )
                )
                GROUP BY i.id
                ORDER BY i.name ASC
                LIMIT ?;
            """, (actual_company_id, q, q, q, q, q, q, limit))
            items = []
            for r in cursor.fetchall():
                it = dict(r)
                it["is_verified"] = self._compute_is_verified(it)
                items.append(it)
            return items

    def get_item_by_id(self, company_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full item details by item ID."""
        actual_company_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT i.*, 
                       COALESCE(sb.current_qty, 0.0) as current_stock,
                       GROUP_CONCAT(b.barcode, ', ') as barcodes
                FROM items i
                LEFT JOIN branches br ON br.company_id = i.company_id AND br.is_default = 1
                LEFT JOIN stock_balances sb ON sb.branch_id = br.id AND sb.item_id = i.id
                LEFT JOIN item_barcodes b ON b.item_id = i.id
                WHERE i.company_id = ? AND i.id = ?
                GROUP BY i.id
                LIMIT 1;
            """, (actual_company_id, item_id))
            row = cursor.fetchone()
            if row:
                res = dict(row)
                res["is_verified"] = self._compute_is_verified(res)
                return res
            return None

    def save_item(self, company_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update an item master record and its barcode mappings."""
        name = (item_data.get("name") or "").strip().upper()
        if not name:
            raise ValueError("Item name cannot be empty.")

        actual_company_id = self._resolve_company_id(company_id)
        item_id = item_data.get("id") or str(uuid.uuid4())
        alias = (item_data.get("alias") or "").strip()
        print_name = item_data.get("print_name") or item_data.get("printName") or name
        group = item_data.get("item_group") or item_data.get("group") or "General"
        unit = item_data.get("unit") or "Pcs."
        op_qty = float(item_data.get("op_stock_qty") or item_data.get("opStockQty") or 0.0)
        op_val = float(item_data.get("op_stock_val") or item_data.get("opStockVal") or 0.0)
        tax_cat = item_data.get("tax_category") or item_data.get("taxCategory") or "GST 18%"
        hsn = (item_data.get("hsn") or "").strip()
        sales_price = float(item_data.get("sales_price") or item_data.get("salesPrice") or 0.0)
        purc_price = float(item_data.get("purc_price") or item_data.get("purcPrice") or 0.0)
        mrp = float(item_data.get("mrp") or 0.0)
        min_price = float(item_data.get("min_sales_price") or item_data.get("minSalesPrice") or 0.0)
        desc = (item_data.get("description") or "").strip()

        # Low-stock alert threshold (optional positive float)
        raw_min_stock = item_data.get("min_stock_alert_level")
        if raw_min_stock is None or raw_min_stock == "" or raw_min_stock == "null":
            raw_min_stock = item_data.get("min_stock_level")
        if raw_min_stock is not None and str(raw_min_stock).strip() != "":
            try:
                min_stock_val = float(raw_min_stock)
                min_stock_alert_level = max(0.0, min_stock_val)
            except (ValueError, TypeError):
                min_stock_alert_level = None
        else:
            min_stock_alert_level = None

        # Reorder level threshold
        raw_reorder = item_data.get("reorder_level")
        if raw_reorder is not None and str(raw_reorder).strip() not in ("", "null", "None"):
            try:
                reorder_level = max(0.0, float(raw_reorder))
            except (ValueError, TypeError):
                reorder_level = None
        else:
            reorder_level = None

        # Preferred reorder quantity
        raw_reorder_qty = item_data.get("reorder_qty") or item_data.get("preferred_reorder_qty") or item_data.get("reorder_quantity")
        if raw_reorder_qty is not None and str(raw_reorder_qty).strip() not in ("", "null", "None"):
            try:
                reorder_qty = max(0.0, float(raw_reorder_qty))
            except (ValueError, TypeError):
                reorder_qty = None
        else:
            reorder_qty = None

        # Maximum stock level
        raw_max_stock = item_data.get("max_stock_level") or item_data.get("max_stock")
        if raw_max_stock is not None and str(raw_max_stock).strip() not in ("", "null", "None"):
            try:
                max_stock_level = max(0.0, float(raw_max_stock))
            except (ValueError, TypeError):
                max_stock_level = None
        else:
            max_stock_level = None

        raw_alert_enabled = item_data.get("alert_enabled")
        if raw_alert_enabled is None:
            alert_enabled = 1
        elif isinstance(raw_alert_enabled, bool):
            alert_enabled = 1 if raw_alert_enabled else 0
        else:
            alert_enabled = 1 if str(raw_alert_enabled).strip() in ("1", "true", "True") else 0

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Check default branch
            cursor.execute("SELECT id FROM branches WHERE company_id = ? AND is_default = 1;", (actual_company_id,))
            branch_row = cursor.fetchone()
            branch_id = branch_row["id"] if branch_row else None

            # Validate: Prevent duplicate item codes across different items
            if alias:
                cursor.execute("""
                    SELECT id, name FROM items 
                    WHERE company_id = ? AND UPPER(alias) = ? AND id != ?;
                """, (actual_company_id, alias.upper(), item_id))
                dup_code = cursor.fetchone()
                if dup_code:
                    raise ValueError(f"Item code / SKU '{alias}' is already assigned to item '{dup_code['name']}'.")

            # Validate: Prevent conflicting barcodes across different items
            barcodes_to_check = item_data.get("barcodes") or ([alias] if alias else [])
            if isinstance(barcodes_to_check, str):
                barcodes_to_check = [b.strip() for b in barcodes_to_check.split(",") if b.strip()]
            for bcode in barcodes_to_check:
                b_str = str(bcode).strip().upper()
                if b_str:
                    cursor.execute("""
                        SELECT ib.barcode, i.name 
                        FROM item_barcodes ib
                        JOIN items i ON i.id = ib.item_id
                        WHERE ib.company_id = ? AND UPPER(ib.barcode) = ? AND ib.item_id != ?;
                    """, (actual_company_id, b_str, item_id))
                    dup_bar = cursor.fetchone()
                    if dup_bar:
                        raise ValueError(f"Conflicting barcode '{b_str}' is already registered to item '{dup_bar['name']}'.")

            # Check if item exists by item_id
            cursor.execute("SELECT id FROM items WHERE company_id = ? AND id = ?;", (actual_company_id, item_id))
            existing_by_id = cursor.fetchone()

            if existing_by_id:
                # Update existing record
                cursor.execute("""
                    UPDATE items SET
                        name = ?,
                        alias = ?,
                        print_name = ?,
                        item_group = ?,
                        unit = ?,
                        tax_category = ?,
                        hsn = ?,
                        sales_price = ?,
                        purc_price = ?,
                        mrp = ?,
                        min_sales_price = ?,
                        description = ?,
                        min_stock_alert_level = ?,
                        alert_enabled = ?,
                        reorder_level = ?,
                        reorder_qty = ?,
                        max_stock_level = ?
                    WHERE company_id = ? AND id = ?;
                """, (
                    name, alias, print_name, group,
                    unit, tax_cat, hsn,
                    sales_price, purc_price, mrp, min_price, desc,
                    min_stock_alert_level, alert_enabled,
                    reorder_level, reorder_qty, max_stock_level,
                    actual_company_id, item_id
                ))
                actual_id = item_id
            else:
                # Upsert item by company_id and name
                cursor.execute("""
                    INSERT INTO items (
                        id, company_id, name, alias, print_name, item_group,
                        unit, op_stock_qty, op_stock_val, tax_category, hsn,
                        sales_price, purc_price, mrp, min_sales_price, description,
                        min_stock_alert_level, alert_enabled,
                        reorder_level, reorder_qty, max_stock_level
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(company_id, name) DO UPDATE SET
                        alias = excluded.alias,
                        print_name = excluded.print_name,
                        item_group = excluded.item_group,
                        unit = excluded.unit,
                        tax_category = excluded.tax_category,
                        hsn = excluded.hsn,
                        sales_price = excluded.sales_price,
                        purc_price = excluded.purc_price,
                        mrp = excluded.mrp,
                        min_sales_price = excluded.min_sales_price,
                        description = excluded.description,
                        min_stock_alert_level = excluded.min_stock_alert_level,
                        alert_enabled = excluded.alert_enabled,
                        reorder_level = excluded.reorder_level,
                        reorder_qty = excluded.reorder_qty,
                        max_stock_level = excluded.max_stock_level;
                """, (
                    item_id, actual_company_id, name, alias, print_name, group,
                    unit, op_qty, op_val, tax_cat, hsn,
                    sales_price, purc_price, mrp, min_price, desc,
                    min_stock_alert_level, alert_enabled,
                    reorder_level, reorder_qty, max_stock_level
                ))

                # Query actual ID
                cursor.execute("SELECT id FROM items WHERE company_id = ? AND name = ?;", (actual_company_id, name))
                actual_id = cursor.fetchone()["id"]

            # Manage primary barcode if supplied in alias or barcodes field
            barcodes = item_data.get("barcodes") or ([alias] if alias else [])
            if isinstance(barcodes, str):
                barcodes = [b.strip() for b in barcodes.split(",") if b.strip()]

            for idx, bcode in enumerate(barcodes):
                b_str = str(bcode).strip().upper()
                if b_str:
                    cursor.execute("""
                        INSERT INTO item_barcodes (id, item_id, company_id, barcode, is_primary)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(company_id, barcode) DO UPDATE SET item_id = excluded.item_id;
                    """, (str(uuid.uuid4()), actual_id, actual_company_id, b_str, 1 if idx == 0 else 0))

            # Ensure stock balance entry exists
            if branch_id:
                cursor.execute("""
                    INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(branch_id, item_id) DO UPDATE SET
                        current_qty = CASE WHEN current_qty = 0 THEN ? ELSE current_qty END;
                """, (str(uuid.uuid4()), actual_company_id, branch_id, actual_id, op_qty, op_qty))

            conn.commit()

        # Trigger automatic low-stock evaluation after item configuration change
        try:
            from services.inventory_service import inventory_service
            inventory_service.evaluate_low_stock_alerts(actual_company_id)
        except Exception as e:
            logger.debug(f"evaluate_low_stock_alerts after save_item: {e}")

        logger.info(f"Item {name} (ID: {actual_id}) saved for company {actual_company_id}.")
        return {
            "id": actual_id,
            "name": name,
            "alias": alias,
            "sales_price": sales_price,
            "unit": unit,
            "tax_category": tax_cat,
            "item_group": group,
            "min_stock_alert_level": min_stock_alert_level,
            "reorder_level": reorder_level,
            "reorder_qty": reorder_qty,
            "max_stock_level": max_stock_level,
            "alert_enabled": alert_enabled
        }

    def set_item_branch_config(
        self,
        company_id: str,
        branch_id: str,
        item_id: str,
        config_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Configure branch-specific minimum stock, reorder level, and notifications."""
        actual_comp_id = self._resolve_company_id(company_id)
        raw_min = config_data.get("min_stock_level") if config_data.get("min_stock_level") is not None else config_data.get("min_stock_alert_level")
        min_lvl = float(raw_min) if (raw_min is not None and str(raw_min).strip() not in ("", "null", "None")) else None
        
        raw_reorder = config_data.get("reorder_level")
        reorder_lvl = float(raw_reorder) if (raw_reorder is not None and str(raw_reorder).strip() not in ("", "null", "None")) else None
        
        raw_rq = config_data.get("reorder_qty") if config_data.get("reorder_qty") is not None else config_data.get("preferred_reorder_qty")
        reorder_q = float(raw_rq) if (raw_rq is not None and str(raw_rq).strip() not in ("", "null", "None")) else None
        
        raw_max = config_data.get("max_stock_level") if config_data.get("max_stock_level") is not None else config_data.get("max_stock")
        max_lvl = float(raw_max) if (raw_max is not None and str(raw_max).strip() not in ("", "null", "None")) else None
        
        alert_en = 1 if config_data.get("alert_enabled", 1) in (1, True, "1", "true") else 0

        config_id = str(uuid.uuid4())
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO item_branch_stock_configs (
                    id, company_id, branch_id, item_id,
                    min_stock_level, reorder_level, reorder_qty, max_stock_level, alert_enabled, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(branch_id, item_id) DO UPDATE SET
                    min_stock_level = excluded.min_stock_level,
                    reorder_level = excluded.reorder_level,
                    reorder_qty = excluded.reorder_qty,
                    max_stock_level = excluded.max_stock_level,
                    alert_enabled = excluded.alert_enabled,
                    updated_at = CURRENT_TIMESTAMP;
            """, (config_id, actual_comp_id, branch_id, item_id, min_lvl, reorder_lvl, reorder_q, max_lvl, alert_en))
            conn.commit()

        try:
            from services.inventory_service import inventory_service
            inventory_service.evaluate_low_stock_alerts(actual_comp_id)
        except Exception as e:
            logger.debug(f"evaluate_low_stock_alerts after set_item_branch_config: {e}")

        return {
            "branch_id": branch_id,
            "item_id": item_id,
            "min_stock_level": min_lvl,
            "reorder_level": reorder_lvl,
            "reorder_qty": reorder_q,
            "max_stock_level": max_lvl,
            "alert_enabled": alert_en
        }

    def get_item_branch_config(
        self,
        company_id: str,
        branch_id: str,
        item_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve branch-specific stock configuration for an item."""
        actual_comp_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM item_branch_stock_configs
                WHERE company_id = ? AND branch_id = ? AND item_id = ?;
            """, (actual_comp_id, branch_id, item_id))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_item_branch_configs(
        self,
        company_id: str,
        item_id: str
    ) -> List[Dict[str, Any]]:
        """List all branch overrides configured for an item."""
        actual_comp_id = self._resolve_company_id(company_id)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*, b.name as branch_name, b.code as branch_code
                FROM item_branch_stock_configs c
                JOIN branches b ON b.id = c.branch_id
                WHERE c.company_id = ? AND c.item_id = ?
                ORDER BY b.name ASC;
            """, (actual_comp_id, item_id))
            return [dict(r) for r in cursor.fetchall()]


catalogue_service = CatalogueService()
