#!/usr/bin/env python3
"""
CLI script to seed or safely cleanup demo test products for scanner testing.
Usage:
    python seed_demo_products.py          # Seeds demo products idempotently
    python seed_demo_products.py --clean  # Safely cleans up unreferenced demo products
    python seed_demo_products.py --status # Displays current demo product status
"""
import sys
import argparse
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from services.demo_product_service import demo_product_service


def main():
    parser = argparse.ArgumentParser(description="Anti Matrix Demo Product Seeder")
    parser.add_argument("--clean", action="store_true", help="Remove demo products (only if no dependent sales records exist)")
    parser.add_argument("--status", action="store_true", help="Check status of demo products in database")
    parser.add_argument("--company", type=str, default=None, help="Target specific company code (default: all)")
    args = parser.parse_args()

    if args.status:
        items = demo_product_service.get_status()
        print(f"\n--- Demo Products in Database ({len(items)} found) ---")
        for it in items:
            v_info = f"[Sales Transactions: {it['transactions_count']}]"
            print(f"• {it['name']} | Barcode: {it['barcode']} | Price: ₹{it['sales_price']} | Stock: {it['current_stock']} {v_info}")
        print("")
        return

    if args.clean:
        print("\n--- Cleaning up Demo Test Products ---")
        res = demo_product_service.cleanup_demo_products(company_id=args.company)
        print(f"Removed records: {len(res['removed'])}")
        for r in res["removed"]:
            print(f"  ✓ Deleted: {r['name']} ({r['barcode']})")
        if res["retained_due_to_transactions"]:
            print(f"Retained (has transaction history): {len(res['retained_due_to_transactions'])}")
            for r in res["retained_due_to_transactions"]:
                print(f"  ! Retained: {r['name']} ({r['vouchers_count']} sales vouchers depend on this item)")
        print("")
        return

    print("\n--- Seeding Demo Test Products for Scanner Testing ---")
    res = demo_product_service.seed_demo_products(company_id=args.company)
    print(f"Newly Seeded: {len(res['seeded'])}")
    for s in res["seeded"]:
        print(f"  + Added: {s['name']} | Barcode: {s['barcode']} | Price: ₹{s['price']} | Category: {s['category']}")
    if res["skipped_already_present"]:
        print(f"Already Present (idempotent skip): {len(res['skipped_already_present'])}")
        for s in res["skipped_already_present"]:
            print(f"  = Skipped: {s['name']} ({s['barcode']})")
    if res["skipped_conflict_with_real_item"]:
        print(f"Conflict with real products (never overwritten): {len(res['skipped_conflict_with_real_item'])}")
        for s in res["skipped_conflict_with_real_item"]:
            print(f"  ! Skipped: {s['name']} ({s['barcode']})")
    if res["errors"]:
        print(f"Errors encountered: {res['errors']}")
    print("\nSeeding finished successfully.\n")


if __name__ == "__main__":
    main()
