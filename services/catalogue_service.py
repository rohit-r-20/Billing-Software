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

    def find_by_barcode(self, company_id: str, barcode: str) -> Optional[Dict[str, Any]]:
        """
        Looks up a product by exact barcode in the active company.
        Also returns current stock balance for the default branch.
        """
        code_str = str(barcode).strip().upper()
        if not code_str:
            return None

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
            """, (company_id, code_str))
            row = cursor.fetchone()
            if row:
                return dict(row)

            # Fallback: Check if barcode matches item alias or name directly
            cursor.execute("""
                SELECT i.*, i.alias as matched_barcode,
                       COALESCE(sb.current_qty, 0.0) as current_stock
                FROM items i
                LEFT JOIN branches br ON br.company_id = i.company_id AND br.is_default = 1
                LEFT JOIN stock_balances sb ON sb.branch_id = br.id AND sb.item_id = i.id
                WHERE i.company_id = ? AND (i.alias = ? OR i.name = ?) AND i.is_active = 1
                LIMIT 1;
            """, (company_id, code_str, code_str))
            row2 = cursor.fetchone()
            if row2:
                return dict(row2)

        return None

    def search_items(self, company_id: str, query: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        """Search items by name, alias, HSN, or group."""
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
                WHERE i.company_id = ? AND (
                    UPPER(i.name) LIKE ? OR 
                    UPPER(i.alias) LIKE ? OR 
                    UPPER(i.hsn) LIKE ? OR
                    UPPER(i.item_group) LIKE ?
                )
                GROUP BY i.id
                ORDER BY i.name ASC
                LIMIT ?;
            """, (company_id, q, q, q, q, limit))
            return [dict(r) for r in cursor.fetchall()]

    def save_item(self, company_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update an item master record and its barcode mappings."""
        name = item_data.get("name", "").strip().upper()
        if not name:
            raise ValueError("Item name cannot be empty.")

        item_id = item_data.get("id") or str(uuid.uuid4())
        alias = item_data.get("alias", "").strip()
        print_name = item_data.get("print_name") or name
        group = item_data.get("item_group", "General")
        unit = item_data.get("unit", "Pcs.")
        op_qty = float(item_data.get("op_stock_qty") or 0.0)
        op_val = float(item_data.get("op_stock_val") or 0.0)
        tax_cat = item_data.get("tax_category", "GST 18%")
        hsn = item_data.get("hsn", "").strip()
        sales_price = float(item_data.get("sales_price") or 0.0)
        purc_price = float(item_data.get("purc_price") or 0.0)
        mrp = float(item_data.get("mrp") or 0.0)
        min_price = float(item_data.get("min_sales_price") or 0.0)
        desc = item_data.get("description", "").strip()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Check default branch
            cursor.execute("SELECT id FROM branches WHERE company_id = ? AND is_default = 1;", (company_id,))
            branch_row = cursor.fetchone()
            branch_id = branch_row["id"] if branch_row else None

            # Upsert item
            cursor.execute("""
                INSERT INTO items (
                    id, company_id, name, alias, print_name, item_group,
                    unit, op_stock_qty, op_stock_val, tax_category, hsn,
                    sales_price, purc_price, mrp, min_sales_price, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    description = excluded.description;
            """, (
                item_id, company_id, name, alias, print_name, group,
                unit, op_qty, op_val, tax_cat, hsn,
                sales_price, purc_price, mrp, min_price, desc
            ))

            # Query the actual item_id in case it was an existing record
            cursor.execute("SELECT id FROM items WHERE company_id = ? AND name = ?;", (company_id, name))
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
                    """, (str(uuid.uuid4()), actual_id, company_id, b_str, 1 if idx == 0 else 0))

            # Ensure stock balance entry exists
            if branch_id:
                cursor.execute("""
                    INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(branch_id, item_id) DO NOTHING;
                """, (str(uuid.uuid4()), company_id, branch_id, actual_id, op_qty))

            conn.commit()

        logger.info(f"Item {name} saved for company {company_id}.")
        return {"id": actual_id, "name": name, "sales_price": sales_price, "unit": unit}


catalogue_service = CatalogueService()

