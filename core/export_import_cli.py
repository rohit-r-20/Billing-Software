"""
CLI utility for exporting and importing browser data to/from SQLite database.
"""
import sys
import json
import argparse
from pathlib import Path
from services.migration_service import migration_service
from db.database import db_manager


def main():
    parser = argparse.ArgumentParser(description="Anti Matrix Billing Data Migration CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Import command
    import_parser = subparsers.add_parser("import", help="Import localStorage JSON file into SQLite database")
    import_parser.add_argument("file", help="Path to exported localStorage JSON file")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export SQLite company data to JSON")
    export_parser.add_argument("company_code", help="Company code to export (e.g. COMP0001)")
    export_parser.add_argument("output", help="Output JSON file path")

    args = parser.parse_args()

    if args.command == "import":
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File {file_path} not found.")
            sys.exit(1)
        summary = migration_service.import_from_json_file(file_path)
        print("Import completed successfully:")
        for k, v in summary.items():
            print(f"  {k}: {v}")

    elif args.command == "export":
        code = args.company_code.strip().upper()
        out_path = Path(args.output)
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM companies WHERE code = ?;", (code,))
            comp = cursor.fetchone()
            if not comp:
                print(f"Error: Company {code} not found in database.")
                sys.exit(1)
            comp_id = comp["id"]

            cursor.execute("SELECT * FROM company_configs WHERE company_id = ?;", (comp_id,))
            cfg = cursor.fetchone()

            cursor.execute("SELECT * FROM accounts WHERE company_id = ?;", (comp_id,))
            accounts = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT * FROM items WHERE company_id = ?;", (comp_id,))
            items = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT * FROM sales_vouchers WHERE company_id = ?;", (comp_id,))
            vouchers = [dict(row) for row in cursor.fetchall()]

            data = {
                "alpha_companies": [dict(comp)],
                f"alpha_config_{code}": dict(cfg) if cfg else {},
                f"alpha_accounts_{code}": accounts,
                f"alpha_items_{code}": items,
                f"alpha_vouchers_{code}": vouchers
            }

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            print(f"Exported data for {code} to {out_path}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

