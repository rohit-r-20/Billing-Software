#!/usr/bin/env python3
"""
Adds 'Odonil Room Spray – Lavender Mist' (Barcode: 8901207033728) to the active company catalogue.
Idempotent: Does not create duplicate items or barcodes if already present.
Leaves MRP, selling price, purchase price, tax rate, and stock unconfigured (0.0).
"""
import sys
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from db.database import db_manager, DatabaseManager
from services.catalogue_service import catalogue_service, CatalogueService
from core.logging_config import logger


ODONIL_PRODUCT = {
    "name": "ODONIL ROOM SPRAY - LAVENDER MIST",
    "print_name": "Odonil Room Spray – Lavender Mist",
    "brand": "Odonil",
    "category": "Home Care / Air Freshener",
    "item_group": "Home Care / Air Freshener",
    "barcode": "8901207033728",
    "barcode_format": "EAN-13",
    "pack_size": "220 ml",
    "unit": "Can",
    "qty_per_sale_unit": 1,
    "sales_price": 0.0,
    "purc_price": 0.0,
    "mrp": 0.0,
    "min_sales_price": 0.0,
    "tax_category": "UNCONFIGURED / PENDING VERIFICATION",
    "hsn": "",
    "op_stock_qty": 0.0,
    "op_stock_val": 0.0,
    "description": (
        "Brand: Odonil | Odonil Room Spray – Lavender Mist | Pack Size: 220 ml | "
        "Category: Home Care / Air Freshener | Barcode: 8901207033728 (EAN-13) | "
        "Unit: Can | Qty per sale unit: 1. Price, tax, and stock pending configuration in Item Master."
    )
}


def add_or_update_odonil_product(company_id: Optional[str] = None, db: Optional[DatabaseManager] = None) -> Dict[str, Any]:
    """
    Idempotently adds or updates Odonil Room Spray in the specified or primary company catalogue.
    """
    database = db or db_manager
    cat_svc = CatalogueService(database)
    actual_company_id = cat_svc._resolve_company_id(company_id)

    with database.get_connection() as conn:
        cursor = conn.cursor()

        # 1. Fetch company code & name for reporting
        cursor.execute("SELECT id, code, name FROM companies WHERE id = ?;", (actual_company_id,))
        comp_row = cursor.fetchone()
        if not comp_row:
            raise ValueError(f"Company ID '{actual_company_id}' not found in database.")
        company_info = dict(comp_row)

        # 2. Check if barcode already exists
        cursor.execute("""
            SELECT ib.id as barcode_id, ib.barcode, i.id as item_id, i.name, i.sales_price, i.tax_category
            FROM item_barcodes ib
            JOIN items i ON ib.item_id = i.id
            WHERE ib.company_id = ? AND ib.barcode = ?;
        """, (actual_company_id, ODONIL_PRODUCT["barcode"]))
        existing_barcode = cursor.fetchone()

        if existing_barcode:
            item_id = existing_barcode["item_id"]
            action = "existing_barcode_found"
            logger.info(f"Barcode {ODONIL_PRODUCT['barcode']} already mapped to item ID {item_id}.")
        else:
            # 3. Check if item exists by name (handling hyphen or en-dash)
            cursor.execute("""
                SELECT id, name, sales_price, tax_category
                FROM items
                WHERE company_id = ? AND (
                    UPPER(name) = ? OR 
                    UPPER(name) = 'ODONIL ROOM SPRAY – LAVENDER MIST' OR
                    UPPER(name) = 'ODONIL ROOM SPRAY - LAVENDER MIST'
                );
            """, (actual_company_id, ODONIL_PRODUCT["name"]))
            existing_item = cursor.fetchone()

            if existing_item:
                item_id = existing_item["id"]
                action = "existing_item_barcode_added"
            else:
                item_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO items (
                        id, company_id, name, alias, print_name, item_group,
                        unit, op_stock_qty, op_stock_val, tax_category, hsn,
                        sales_price, purc_price, mrp, min_sales_price, description, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1);
                """, (
                    item_id,
                    actual_company_id,
                    ODONIL_PRODUCT["name"],
                    ODONIL_PRODUCT["barcode"],
                    ODONIL_PRODUCT["print_name"],
                    ODONIL_PRODUCT["item_group"],
                    ODONIL_PRODUCT["unit"],
                    ODONIL_PRODUCT["op_stock_qty"],
                    ODONIL_PRODUCT["op_stock_val"],
                    ODONIL_PRODUCT["tax_category"],
                    ODONIL_PRODUCT["hsn"],
                    ODONIL_PRODUCT["sales_price"],
                    ODONIL_PRODUCT["purc_price"],
                    ODONIL_PRODUCT["mrp"],
                    ODONIL_PRODUCT["min_sales_price"],
                    ODONIL_PRODUCT["description"]
                ))
                action = "new_item_created"

            # Register barcode mapping
            cursor.execute("""
                INSERT INTO item_barcodes (id, item_id, company_id, barcode, is_primary)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(company_id, barcode) DO UPDATE SET item_id = excluded.item_id;
            """, (str(uuid.uuid4()), item_id, actual_company_id, ODONIL_PRODUCT["barcode"]))

            # Ensure stock balance entry exists for default branch
            cursor.execute("SELECT id FROM branches WHERE company_id = ? AND is_default = 1;", (actual_company_id,))
            branch_row = cursor.fetchone()
            if branch_row:
                cursor.execute("""
                    INSERT INTO stock_balances (id, company_id, branch_id, item_id, current_qty)
                    VALUES (?, ?, ?, ?, 0.0)
                    ON CONFLICT(branch_id, item_id) DO NOTHING;
                """, (str(uuid.uuid4()), actual_company_id, branch_row["id"], item_id))

            conn.commit()

        # 4. Fetch the verified stored item record
        cursor.execute("""
            SELECT i.*, 
                   COALESCE(sb.current_qty, 0.0) as current_stock,
                   GROUP_CONCAT(b.barcode, ', ') as barcodes
            FROM items i
            LEFT JOIN branches br ON br.company_id = i.company_id AND br.is_default = 1
            LEFT JOIN stock_balances sb ON sb.branch_id = br.id AND sb.item_id = i.id
            LEFT JOIN item_barcodes b ON b.item_id = i.id
            WHERE i.id = ?
            GROUP BY i.id;
        """, (item_id,))
        final_row = cursor.fetchone()
        stored_item = dict(final_row) if final_row else {}

    return {
        "success": True,
        "action": action,
        "company": company_info,
        "product_id": item_id,
        "barcode": ODONIL_PRODUCT["barcode"],
        "barcode_format": ODONIL_PRODUCT["barcode_format"],
        "item": stored_item,
        "price_configuration_status": "Unconfigured (₹ 0.00) — Checkout blocked until configured in Item Master"
    }


if __name__ == "__main__":
    res = add_or_update_odonil_product()
    print("\n=======================================================")
    print("  ALPHA BILLING SOFTWARE — PRODUCT CATALOGUE ADDITION")
    print("=======================================================")
    print(f"Status:                      {res['action']}")
    print(f"Product ID:                  {res['product_id']}")
    print(f"Company Association:         {res['company']['name']} ({res['company']['code']} / ID: {res['company']['id']})")
    print(f"Product Name:                {res['item'].get('name')}")
    print(f"Print Name:                  {res['item'].get('print_name')}")
    print(f"Category / Item Group:       {res['item'].get('item_group')}")
    print(f"Unit:                        {res['item'].get('unit')}")
    print(f"Barcode:                     {res['barcode']} ({res['barcode_format']})")
    print(f"Registered Barcodes:         {res['item'].get('barcodes')}")
    print(f"Sales Price:                 ₹ {res['item'].get('sales_price'):.2f}")
    print(f"Purchase Price:              ₹ {res['item'].get('purc_price'):.2f}")
    print(f"MRP:                         ₹ {res['item'].get('mrp'):.2f}")
    print(f"Stock Quantity:              {res['item'].get('current_stock')} {res['item'].get('unit')}")
    print(f"Tax Category:                {res['item'].get('tax_category')}")
    print(f"Price Configuration Status:  {res['price_configuration_status']}")
    print("=======================================================\n")

