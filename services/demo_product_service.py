"""
Demo Product Seeding and Safe Cleanup Service for Anti Matrix Billing ERP.
Manages test/demo catalogue products without overwriting real business data.
"""
import uuid
from typing import Dict, Any, List, Optional
from db.database import db_manager, DatabaseManager
from core.logging_config import logger


# Specific demo product dataset requested for scanner testing
DEMO_PRODUCTS = [
    {
        "name": "MILK BIKIS [DEMO]",
        "barcode": "890_TEST_001",
        "category": "Biscuits",
        "sales_price": 10.0,
        "purc_price": 8.0,
        "mrp": 10.0,
        "unit": "Pcs.",
        "tax_category": "GST 18%",
        "op_stock_qty": 100.0,
        "is_verified": 1,
        "description": "DEMO_PRODUCT_SEED: Milk Bikis demo test item (Placeholder test data)"
    },
    {
        "name": "HIDE & SEEK [DEMO]",
        "barcode": "890_TEST_002",
        "category": "Biscuits",
        "sales_price": 20.0,
        "purc_price": 16.0,
        "mrp": 20.0,
        "unit": "Pcs.",
        "tax_category": "GST 18%",
        "op_stock_qty": 100.0,
        "is_verified": 1,
        "description": "DEMO_PRODUCT_SEED: Hide & Seek demo test item (Placeholder test data)"
    },
    {
        "name": "LEVOSALBUTAMOL SULFATE [DEMO/UNVERIFIED]",
        "barcode": "8909263004690",
        "category": "Medical",
        "sales_price": 0.0,  # Unconfigured to prevent accidental real commercial sale
        "purc_price": 0.0,
        "mrp": 0.0,
        "unit": "Pcs.",
        "tax_category": "UNVERIFIED / EXEMPT",
        "op_stock_qty": 0.0,
        "is_verified": 0,
        "description": "DEMO_PRODUCT_SEED: DEMO/TEST RECORD. Strength, dosage form, manufacturer, pack size, MRP, selling price, and GST rate are NOT configured. Package verification required before real commercial sale."
    }
]


class DemoProductService:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or db_manager

    def seed_demo_products(self, company_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Idempotently inserts the demo products into the catalogue.
        Rules:
        - Never overwrites existing real products with the same barcode.
        - Checks for duplicate barcodes before insertion.
        - Re-running does not duplicate records.
        """
        results = {
            "seeded": [],
            "skipped_already_present": [],
            "skipped_conflict_with_real_item": [],
            "errors": []
        }

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Determine target company
            if company_id:
                cursor.execute("SELECT id, code, name FROM companies WHERE id = ? OR UPPER(code) = ?;", (company_id, company_id.upper()))
                companies = [dict(r) for r in cursor.fetchall()]
            else:
                cursor.execute("SELECT id, code, name FROM companies;")
                companies = [dict(r) for r in cursor.fetchall()]

            if not companies:
                results["errors"].append("No companies found in database to seed demo products into.")
                return results

            for comp in companies:
                c_id = comp["id"]

                # Get default branch for stock balances
                cursor.execute("SELECT id FROM branches WHERE company_id = ? AND is_default = 1;", (c_id,))
                branch_row = cursor.fetchone()
                branch_id = branch_row["id"] if branch_row else None

                for item_spec in DEMO_PRODUCTS:
                    bcode = item_spec["barcode"].strip().upper()
                    name = item_spec["name"]

                    # 1. Check if barcode is already registered in item_barcodes
                    cursor.execute("""
                        SELECT b.barcode, i.id as item_id, i.name as item_name, i.description
                        FROM item_barcodes b
                        JOIN items i ON b.item_id = i.id
                        WHERE b.company_id = ? AND b.barcode = ?;
                    """, (c_id, bcode))
                    existing_bcode = cursor.fetchone()

                    if existing_bcode:
                        desc = existing_bcode["description"] or ""
                        if "DEMO_PRODUCT_SEED" in desc:
                            results["skipped_already_present"].append({
                                "company": comp["code"],
                                "barcode": bcode,
                                "name": existing_bcode["item_name"],
                                "reason": "Already seeded as demo product."
                            })
                        else:
                            results["skipped_conflict_with_real_item"].append({
                                "company": comp["code"],
                                "barcode": bcode,
                                "name": existing_bcode["item_name"],
                                "reason": "Barcode belongs to an existing real item. Never overwritten."
                            })
                        continue

                    # 2. Check if item name already exists in items table
                    cursor.execute("SELECT id, description FROM items WHERE company_id = ? AND name = ?;", (c_id, name))
                    existing_item = cursor.fetchone()

                    if existing_item:
                        item_id = existing_item["id"]
                    else:
                        item_id = str(uuid.uuid4())
                        cursor.execute("""
                            INSERT INTO items (
                                id, company_id, name, alias, print_name, item_group,
                                unit, op_stock_qty, op_stock_val, tax_category, hsn,
                                sales_price, purc_price, mrp, min_sales_price, description, is_active
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1);
                        """, (
                            item_id, c_id, name, bcode, name, item_spec["category"],
                            item_spec["unit"], item_spec["op_stock_qty"], 0.0,
                            item_spec["tax_category"], "", item_spec["sales_price"],
                            item_spec["purc_price"], item_spec["mrp"], 0.0,
                            item_spec["description"]
                        ))

                    # 3. Insert primary barcode mapping
                    barcode_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO item_barcodes (id, item_id, company_id, barcode, is_primary)
                        VALUES (?, ?, ?, ?, 1);
                    """, (barcode_id, item_id, c_id, bcode))

                    # 4. Insert initial stock balance if branch exists
                    if branch_id and item_spec["op_stock_qty"] > 0:
                        cursor.execute("""
                            INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(branch_id, item_id) DO UPDATE SET current_qty = stock_balances.current_qty + excluded.current_qty;
                        """, (str(uuid.uuid4()), c_id, branch_id, item_id, item_spec["op_stock_qty"]))

                    results["seeded"].append({
                        "company": comp["code"],
                        "name": name,
                        "barcode": bcode,
                        "category": item_spec["category"],
                        "price": item_spec["sales_price"],
                        "verified": item_spec["is_verified"]
                    })

            conn.commit()

        logger.info(f"Demo product seeding complete: {len(results['seeded'])} added, {len(results['skipped_already_present'])} already present.")
        return results

    def cleanup_demo_products(self, company_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Reversible cleanup: removes only the exact test records created by this seed process,
        and ONLY when they have no dependent sales vouchers or invoice transactions.
        """
        results = {
            "removed": [],
            "retained_due_to_transactions": [],
            "errors": []
        }

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT id, name, alias, company_id FROM items WHERE description LIKE '%DEMO_PRODUCT_SEED%'"
            params = []
            if company_id:
                query += " AND (company_id = ? OR company_id IN (SELECT id FROM companies WHERE UPPER(code) = ?))"
                params.extend([company_id, company_id.upper()])

            cursor.execute(query, tuple(params))
            demo_items = [dict(r) for r in cursor.fetchall()]

            for it in demo_items:
                item_id = it["id"]
                name = it["name"]

                # Check for dependent transaction records
                cursor.execute("SELECT COUNT(*) FROM sales_voucher_items WHERE item_id = ?;", (item_id,))
                voucher_count = cursor.fetchone()[0]

                if voucher_count > 0:
                    results["retained_due_to_transactions"].append({
                        "id": item_id,
                        "name": name,
                        "vouchers_count": voucher_count,
                        "reason": "Preserved to protect sales transaction history integrity."
                    })
                    continue

                # Safe to delete - remove barcode mappings, stock balances, and item
                cursor.execute("DELETE FROM item_barcodes WHERE item_id = ?;", (item_id,))
                cursor.execute("DELETE FROM stock_balances WHERE item_id = ?;", (item_id,))
                cursor.execute("DELETE FROM items WHERE id = ?;", (item_id,))

                results["removed"].append({
                    "id": item_id,
                    "name": name,
                    "barcode": it["alias"]
                })

            conn.commit()

        logger.info(f"Demo product cleanup complete: {len(results['removed'])} removed, {len(results['retained_due_to_transactions'])} preserved.")
        return results

    def get_status(self) -> List[Dict[str, Any]]:
        """List status of all demo products in the database."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT i.id, i.name, b.barcode, i.item_group, i.sales_price,
                       i.tax_category, COALESCE(sb.current_qty, 0.0) as current_stock,
                       i.created_at,
                       (SELECT COUNT(*) FROM sales_voucher_items WHERE item_id = i.id) as transactions_count
                FROM items i
                LEFT JOIN item_barcodes b ON b.item_id = i.id
                LEFT JOIN stock_balances sb ON sb.item_id = i.id
                WHERE i.description LIKE '%DEMO_PRODUCT_SEED%'
                ORDER BY i.name ASC;
            """)
            return [dict(r) for r in cursor.fetchall()]


demo_product_service = DemoProductService()

