"""
Authoritative Barcode Management Service for Alpha Billing ERP.
Handles:
1. Atomic, unique internal barcode sequence generation (Code 128, e.g. AB000000000001).
2. GS1 External Barcode format and checksum validation (EAN-13, UPC-A, EAN-8).
3. Database-level barcode uniqueness across products and alternate barcode records.
4. Multiple barcode assignments per product.
5. High-contrast, scannable Code 128 / EAN-13 SVG barcode rendering.
6. Millimeter-accurate physical barcode label printing decoupled from screen zoom.
"""

import re
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from db.database import db_manager, DatabaseManager
from core.logging_config import logger


class BarcodeService:
    DEFAULT_INTERNAL_PREFIX = "AB"
    INTERNAL_DIGITS = 12  # e.g. AB000000000001 (14 characters total)
    SEQUENCE_NAME = "INTERNAL_ALPHA_CODE128"

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or db_manager
        self._ensure_sequence_table_sqlite()

    def _ensure_sequence_table_sqlite(self):
        """Ensures the barcode_sequences table exists in SQLite if running offline/local."""
        if self.db.is_sqlite:
            try:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS barcode_sequences (
                            id TEXT PRIMARY KEY,
                            sequence_name TEXT UNIQUE NOT NULL,
                            prefix TEXT NOT NULL DEFAULT 'AB',
                            current_value INTEGER NOT NULL DEFAULT 0,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    conn.commit()
            except Exception as e:
                logger.debug(f"SQLite barcode_sequences check: {e}")

    # ==========================================================================
    # 1. Internal Barcode Sequence Generation (Code 128)
    # ==========================================================================

    def generate_internal_barcode(self, company_id: Optional[str] = None, prefix: Optional[str] = None) -> Dict[str, Any]:
        """
        Atomically allocates the next unique internal Code 128 barcode.
        - Guaranteed unique sequence across all concurrent computers.
        - Format: AB000000000001 (prefix + 12 zero-padded digits).
        - Collision-safe: Checks against existing item_barcodes and items.alias,
          skipping any number that was previously entered manually.
        - Monotonic: Never reuses numbers from deactivated or deleted items.
        """
        eff_prefix = (prefix or self.DEFAULT_INTERNAL_PREFIX).strip().upper()
        if not eff_prefix:
            eff_prefix = self.DEFAULT_INTERNAL_PREFIX

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Ensure sequence row exists
            cursor.execute("SELECT current_value FROM barcode_sequences WHERE sequence_name = ?;", (self.SEQUENCE_NAME,))
            seq_row = cursor.fetchone()

            if not seq_row:
                # Initialize sequence counter by checking existing highest AB... in DB
                initial_val = self._find_max_existing_sequence(cursor, eff_prefix)
                cursor.execute("""
                    INSERT INTO barcode_sequences (id, sequence_name, prefix, current_value, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP);
                """, (str(uuid.uuid4()), self.SEQUENCE_NAME, eff_prefix, initial_val))
                conn.commit()

            # Loop with atomic increments until an unassigned candidate is found
            max_attempts = 1000
            for _ in range(max_attempts):
                cursor.execute("""
                    UPDATE barcode_sequences
                    SET current_value = current_value + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE sequence_name = ?;
                """, (self.SEQUENCE_NAME,))

                cursor.execute("SELECT current_value FROM barcode_sequences WHERE sequence_name = ?;", (self.SEQUENCE_NAME,))
                curr_row = cursor.fetchone()
                next_val = int(curr_row[0] if curr_row else 1)

                candidate = f"{eff_prefix}{str(next_val).zfill(self.INTERNAL_DIGITS)}"

                # Collision check across item_barcodes and items
                cursor.execute("""
                    SELECT 1 FROM item_barcodes WHERE UPPER(barcode) = ?
                    UNION
                    SELECT 1 FROM items WHERE UPPER(alias) = ?;
                """, (candidate, candidate))

                if not cursor.fetchone():
                    # Unused unique candidate found
                    conn.commit()
                    svg_markup = self.render_barcode_svg(candidate, standard="CODE128")
                    return {
                        "barcode": candidate,
                        "prefix": eff_prefix,
                        "sequence_number": next_val,
                        "standard": "Code 128 (Internal)",
                        "type": "INTERNAL_CODE128",
                        "svg": svg_markup,
                        "human_readable": candidate
                    }

            conn.commit()
            raise RuntimeError("Exceeded maximum collision retry attempts while generating internal barcode.")

    def _find_max_existing_sequence(self, cursor, prefix: str) -> int:
        """Finds the maximum sequence number already present in DB matching the prefix."""
        max_num = 0
        try:
            # Check item_barcodes
            cursor.execute("SELECT barcode FROM item_barcodes WHERE barcode LIKE ?;", (f"{prefix}%",))
            for r in cursor.fetchall():
                b = str(r[0] or "").strip().upper()
                if b.startswith(prefix) and b[len(prefix):].isdigit():
                    try:
                        val = int(b[len(prefix):])
                        if val > max_num:
                            max_num = val
                    except ValueError:
                        pass

            # Check items.alias
            cursor.execute("SELECT alias FROM items WHERE alias LIKE ?;", (f"{prefix}%",))
            for r in cursor.fetchall():
                b = str(r[0] or "").strip().upper()
                if b.startswith(prefix) and b[len(prefix):].isdigit():
                    try:
                        val = int(b[len(prefix):])
                        if val > max_num:
                            max_num = val
                    except ValueError:
                        pass
        except Exception as e:
            logger.debug(f"Error finding max existing sequence: {e}")

        return max_num

    # ==========================================================================
    # 2. Barcode Validation & Standards
    # ==========================================================================

    @staticmethod
    def calculate_ean_check_digit(code_without_check: str) -> int:
        """Calculates standard GS1 modulo-10 check digit for EAN-13, UPC-A, and EAN-8."""
        digits = [int(ch) for ch in code_without_check]
        # Reverse digits so weight 3 is applied to position 1 from right
        rev = list(reversed(digits))
        weighted_sum = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(rev))
        return (10 - (weighted_sum % 10)) % 10

    def validate_barcode(self, barcode: str) -> Dict[str, Any]:
        """
        Validates format and check digit for:
        - Internal Alpha Billing (Code 128)
        - GS1 EAN-13 (13 digits with modulo-10 checksum)
        - GS1 UPC-A (12 digits with modulo-10 checksum)
        - GS1 EAN-8 (8 digits with modulo-10 checksum)
        - Standard Code 128 alphanumeric
        """
        clean_code = str(barcode or "").strip().upper()
        if not clean_code:
            return {
                "is_valid": False,
                "barcode": "",
                "standard": "Unknown",
                "is_internal": False,
                "check_digit_valid": None,
                "message": "Barcode cannot be empty."
            }

        # 1. Internal Alpha Billing Code 128 (e.g. AB000000000001)
        if clean_code.startswith(self.DEFAULT_INTERNAL_PREFIX) and clean_code[len(self.DEFAULT_INTERNAL_PREFIX):].isdigit():
            return {
                "is_valid": True,
                "barcode": clean_code,
                "format": "ALPHA_CODE128",
                "standard": "Code 128 (Alpha Billing Internal)",
                "is_internal": True,
                "check_digit_valid": True,
                "message": "Valid internal Alpha Billing product identifier."
            }

        # 2. GS1 EAN-13 (13 digits)
        if len(clean_code) == 13 and clean_code.isdigit():
            expected_cd = self.calculate_ean_check_digit(clean_code[:12])
            actual_cd = int(clean_code[12])
            is_valid = (expected_cd == actual_cd)
            return {
                "is_valid": is_valid,
                "barcode": clean_code,
                "format": "EAN-13",
                "standard": "GS1 EAN-13 (Manufacturer)",
                "is_internal": False,
                "check_digit_valid": is_valid,
                "expected_check_digit": expected_cd,
                "actual_check_digit": actual_cd,
                "message": "Valid GS1 EAN-13 barcode." if is_valid else f"Invalid EAN-13 check digit (expected {expected_cd}, got {actual_cd})."
            }

        # 3. GS1 UPC-A (12 digits)
        if len(clean_code) == 12 and clean_code.isdigit():
            expected_cd = self.calculate_ean_check_digit(clean_code[:11])
            actual_cd = int(clean_code[11])
            is_valid = (expected_cd == actual_cd)
            return {
                "is_valid": is_valid,
                "barcode": clean_code,
                "format": "UPC-A",
                "standard": "GS1 UPC-A (Manufacturer)",
                "is_internal": False,
                "check_digit_valid": is_valid,
                "expected_check_digit": expected_cd,
                "actual_check_digit": actual_cd,
                "message": "Valid GS1 UPC-A barcode." if is_valid else f"Invalid UPC-A check digit (expected {expected_cd}, got {actual_cd})."
            }

        # 4. GS1 EAN-8 (8 digits)
        if len(clean_code) == 8 and clean_code.isdigit():
            expected_cd = self.calculate_ean_check_digit(clean_code[:7])
            actual_cd = int(clean_code[7])
            is_valid = (expected_cd == actual_cd)
            return {
                "is_valid": is_valid,
                "barcode": clean_code,
                "format": "EAN-8",
                "standard": "GS1 EAN-8 (Compact)",
                "is_internal": False,
                "check_digit_valid": is_valid,
                "expected_check_digit": expected_cd,
                "actual_check_digit": actual_cd,
                "message": "Valid GS1 EAN-8 barcode." if is_valid else f"Invalid EAN-8 check digit (expected {expected_cd}, got {actual_cd})."
            }

        # 5. General Code 128 Alphanumeric (printable ASCII)
        if all(32 <= ord(ch) <= 126 for ch in clean_code):
            return {
                "is_valid": True,
                "barcode": clean_code,
                "format": "CODE128",
                "standard": "Code 128 (Alphanumeric)",
                "is_internal": False,
                "check_digit_valid": True,
                "message": "Valid Code 128 alphanumeric identifier."
            }

        return {
            "is_valid": False,
            "barcode": clean_code,
            "format": "UNKNOWN",
            "standard": "Unsupported",
            "is_internal": False,
            "check_digit_valid": False,
            "message": "Barcode contains unsupported characters."
        }

    # ==========================================================================
    # 3. Database Uniqueness & Duplicate Detection
    # ==========================================================================

    def check_barcode_uniqueness(
        self,
        arg1: str,
        arg2: Optional[str] = None,
        exclude_item_id: Optional[str] = None,
        company_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verifies whether a barcode is available or already assigned to another product.
        Checks both item_barcodes table and items.alias.
        Supports both signatures:
          check_barcode_uniqueness(company_id, barcode, exclude_item_id)
          check_barcode_uniqueness(barcode, exclude_item_id=..., company_id=...)
        """
        if arg2 is not None:
            eff_company_id = arg1
            code_str = str(arg2 or "").strip().upper()
            eff_exclude_id = exclude_item_id
        else:
            eff_company_id = company_id
            code_str = str(arg1 or "").strip().upper()
            eff_exclude_id = exclude_item_id

        if not code_str:
            return {"is_unique": True, "barcode": "", "existing_product": None}

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Check item_barcodes table
            if eff_company_id:
                if eff_exclude_id:
                    cursor.execute("""
                        SELECT ib.barcode, i.id, i.name, i.alias
                        FROM item_barcodes ib
                        JOIN items i ON i.id = ib.item_id
                        WHERE ib.company_id = ? AND UPPER(ib.barcode) = ? AND ib.item_id != ?;
                    """, (eff_company_id, code_str, eff_exclude_id))
                else:
                    cursor.execute("""
                        SELECT ib.barcode, i.id, i.name, i.alias
                        FROM item_barcodes ib
                        JOIN items i ON i.id = ib.item_id
                        WHERE ib.company_id = ? AND UPPER(ib.barcode) = ?;
                    """, (eff_company_id, code_str))
            else:
                if eff_exclude_id:
                    cursor.execute("""
                        SELECT ib.barcode, i.id, i.name, i.alias
                        FROM item_barcodes ib
                        JOIN items i ON i.id = ib.item_id
                        WHERE UPPER(ib.barcode) = ? AND ib.item_id != ?;
                    """, (code_str, eff_exclude_id))
                else:
                    cursor.execute("""
                        SELECT ib.barcode, i.id, i.name, i.alias
                        FROM item_barcodes ib
                        JOIN items i ON i.id = ib.item_id
                        WHERE UPPER(ib.barcode) = ?;
                    """, (code_str,))

            row = cursor.fetchone()
            if row:
                return {
                    "is_unique": False,
                    "barcode": code_str,
                    "existing_product": {
                        "id": row["id"],
                        "name": row["name"],
                        "sku": row["alias"]
                    },
                    "message": f"Barcode '{code_str}' is already assigned to '{row['name']}'."
                }

            # 2. Check items.alias
            if eff_company_id:
                if eff_exclude_id:
                    cursor.execute("""
                        SELECT id, name, alias FROM items
                        WHERE company_id = ? AND UPPER(alias) = ? AND id != ?;
                    """, (eff_company_id, code_str, eff_exclude_id))
                else:
                    cursor.execute("""
                        SELECT id, name, alias FROM items
                        WHERE company_id = ? AND UPPER(alias) = ?;
                    """, (eff_company_id, code_str))
            else:
                if eff_exclude_id:
                    cursor.execute("""
                        SELECT id, name, alias FROM items
                        WHERE UPPER(alias) = ? AND id != ?;
                    """, (code_str, eff_exclude_id))
                else:
                    cursor.execute("""
                        SELECT id, name, alias FROM items
                        WHERE UPPER(alias) = ?;
                    """, (code_str,))

            row2 = cursor.fetchone()
            if row2:
                return {
                    "is_unique": False,
                    "barcode": code_str,
                    "existing_product": {
                        "id": row2["id"],
                        "name": row2["name"],
                        "sku": row2["alias"]
                    },
                    "message": f"Barcode / SKU '{code_str}' is already assigned to '{row2['name']}'."
                }

        return {
            "is_unique": True,
            "barcode": code_str,
            "existing_product": None,
            "message": "Barcode is unique and available."
        }

    # ==========================================================================
    # 4. Multiple Barcodes Per Product Management
    # ==========================================================================

    def get_item_barcodes(self, arg1: str, arg2: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all barcodes associated with a product (primary + alternates).
        Supports get_item_barcodes(company_id, item_id) and get_item_barcodes(item_id)."""
        if arg2 is not None:
            eff_company_id = arg1
            eff_item_id = arg2
        else:
            eff_company_id = None
            eff_item_id = arg1

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if eff_company_id:
                cursor.execute("""
                    SELECT id, barcode, is_primary, created_at
                    FROM item_barcodes
                    WHERE company_id = ? AND item_id = ?
                    ORDER BY is_primary DESC, created_at ASC;
                """, (eff_company_id, eff_item_id))
            else:
                cursor.execute("""
                    SELECT id, barcode, is_primary, created_at
                    FROM item_barcodes
                    WHERE item_id = ?
                    ORDER BY is_primary DESC, created_at ASC;
                """, (eff_item_id,))
            rows = cursor.fetchall()

            result = []
            for r in rows:
                b = r["barcode"]
                val_info = self.validate_barcode(b)
                result.append({
                    "id": r["id"],
                    "barcode": b,
                    "is_primary": bool(r["is_primary"]),
                    "standard": val_info["standard"],
                    "is_internal": val_info["is_internal"],
                    "created_at": str(r["created_at"]) if r["created_at"] else ""
                })
            return result

    # ==========================================================================
    # 5. Visual Barcode Rendering (Code 128 / EAN-13 SVG)
    # ==========================================================================

    def render_barcode_svg(
        self,
        barcode: str,
        standard: Optional[str] = None,
        height_px: int = 48,
        bar_width_px: float = 1.5,
        human_readable: bool = True,
        include_text: Optional[bool] = None
    ) -> str:
        """
        Renders a high-contrast, scalable SVG barcode graphic with adequate quiet zones.
        Uses ReportLab barcode drawing engine with pure SVG fallback.
        """
        if include_text is not None:
            human_readable = include_text
        code_str = str(barcode or "").strip().upper()
        if not code_str:
            return '<svg width="200" height="50" xmlns="http://www.w3.org/2000/svg"><text x="10" y="30" fill="#94a3b8">No Barcode</text></svg>'

        # Determine best barcode standard
        std_upper = (standard or "").upper()
        if "EAN" in std_upper or (len(code_str) == 13 and code_str.isdigit()):
            barcode_type = "EAN13"
        elif "UPC" in std_upper or (len(code_str) == 12 and code_str.isdigit()):
            barcode_type = "EAN13"  # Render UPC as 13-digit with leading 0 or standard
        else:
            barcode_type = "Code128"

        try:
            from reportlab.graphics.barcode import createBarcodeDrawing
            from reportlab.graphics import renderSVG

            d = createBarcodeDrawing(
                barcode_type,
                value=code_str,
                barHeight=height_px,
                barWidth=bar_width_px,
                humanReadable=human_readable
            )
            raw_svg = renderSVG.drawToString(d)

            # Clean XML declaration to allow clean inline embedding in HTML
            clean_svg = re.sub(r'<\?xml[^>]*\?>', '', raw_svg)
            clean_svg = re.sub(r'<!DOCTYPE[^>]*>', '', clean_svg)
            return clean_svg.strip()
        except Exception as e:
            logger.debug(f"ReportLab SVG generation fallback for {code_str}: {e}")
            return self._fallback_code128_svg(code_str, height_px, bar_width_px, human_readable)

    def _fallback_code128_svg(self, code: str, height: int = 48, bar_width: float = 1.5, human_readable: bool = True) -> str:
        """Lightweight pure SVG Code 128 generator if ReportLab drawing encounters any edge case."""
        # Standard Code 128B character patterns (107 patterns, 11 modules each)
        C128_PATTERNS = [
            "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
            "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
            "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
            "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
            "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
            "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
            "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
            "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
            "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
            "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
            "114131", "311141", "411131", "211412", "211214", "211232", "2331112"
        ]
        start_b = 104
        stop = 106

        # Encode ASCII in Code 128B
        indices = [ord(c) - 32 for c in code if 32 <= ord(c) <= 126]
        checksum = (start_b + sum((i + 1) * idx for i, idx in enumerate(indices))) % 103
        all_indices = [start_b] + indices + [checksum, stop]

        pattern_str = "".join(C128_PATTERNS[idx] for idx in all_indices)

        # Build SVG bars
        x = 15.0  # Quiet zone
        rects = []
        is_bar = True
        for digit in pattern_str:
            width = int(digit) * bar_width
            if is_bar:
                rects.append(f'<rect x="{x:.1f}" y="4" width="{width:.1f}" height="{height}" fill="#000000"/>')
            x += width
            is_bar = not is_bar

        total_width = x + 15.0  # Quiet zone right
        total_height = height + (20 if human_readable else 8)

        text_element = f'<text x="{total_width / 2:.1f}" y="{height + 16}" font-family="monospace" font-size="12" font-weight="bold" text-anchor="middle" fill="#000000">{code}</text>' if human_readable else ""

        return (
            f'<svg width="{total_width:.1f}" height="{total_height}" viewBox="0 0 {total_width:.1f} {total_height}" '
            f'xmlns="http://www.w3.org/2000/svg" style="background:#ffffff; max-width: 100%; height: auto;">'
            f'{"".join(rects)}{text_element}</svg>'
        )

    # ==========================================================================
    # 6. Physical Barcode Label Printing (Zoom Decoupled)
    # ==========================================================================

    def generate_label_html(
        self,
        item_data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
        label_size: Optional[str] = None,
        include_name: Optional[bool] = None,
        include_price: Optional[bool] = None,
        include_mrp: Optional[bool] = None,
        include_sku: Optional[bool] = None,
        copies: Optional[int] = None
    ) -> str:
        """
        Generates physical millimeter-accurate barcode label HTML for thermal printers.
        Screen zoom is strictly decoupled via @media print { zoom: 1 !important; transform: none !important; }.
        """
        opts = dict(options or {})
        if label_size is not None:
            opts["size"] = label_size
        if include_name is not None:
            opts["include_name"] = include_name
        if include_price is not None:
            opts["include_price"] = include_price
        if include_mrp is not None:
            opts["include_mrp"] = include_mrp
        if include_sku is not None:
            opts["include_sku"] = include_sku
        if copies is not None:
            opts["copies"] = copies

        size_key = opts.get("size", "50x25")  # '50x25', '38x25', '50x38', 'a4_24'
        inc_name = opts.get("include_name", True)
        inc_price = opts.get("include_price", True)
        inc_mrp = opts.get("include_mrp", True)
        inc_sku = opts.get("include_sku", True)
        copies_count = max(1, int(opts.get("copies", 1)))

        name = item_data.get("name", "Product").strip()
        barcode = item_data.get("barcode") or item_data.get("alias", "")
        sales_price = float(item_data.get("sales_price") or 0.0)
        mrp = float(item_data.get("mrp") or 0.0)
        sku = item_data.get("alias", "")

        # Size parameters (in mm)
        dimensions = {
            "50x25": {"w_mm": 50, "h_mm": 25, "bar_h": 32, "font_size": 9},
            "38x25": {"w_mm": 38, "h_mm": 25, "bar_h": 28, "font_size": 8},
            "50x38": {"w_mm": 50, "h_mm": 38, "bar_h": 40, "font_size": 10},
            "a4_24": {"w_mm": 63.5, "h_mm": 33.9, "bar_h": 36, "font_size": 9}
        }
        dim = dimensions.get(size_key, dimensions["50x25"])
        w_mm = dim["w_mm"]
        h_mm = dim["h_mm"]
        bar_h = dim["bar_h"]

        svg_barcode = self.render_barcode_svg(barcode, height_px=bar_h, bar_width_px=1.2, human_readable=True)

        page_rule = f"@page {{ size: A4 portrait; margin: 8mm; }}" if size_key == "a4_24" else f"@page {{ size: {w_mm}mm {h_mm}mm; margin: 0; }}"

        # Single Label Template
        label_inner = f"""
        <div class="physical-barcode-label barcode-label-box" style="width: {w_mm}mm; height: {h_mm}mm; padding: 1.5mm; box-sizing: border-box; display: flex; flex-direction: column; justify-content: space-between; align-items: center; text-align: center; background: #fff; border: 1px dashed #e2e8f0; page-break-inside: avoid;">
            {f'<div class="label-prod-name" style="font-size: {dim["font_size"]}pt; font-weight: 700; line-height: 1.1; max-height: 2.4em; overflow: hidden; width: 100%;">{name}</div>' if inc_name else ''}
            <div class="label-barcode-graphic" style="width: 100%; display: flex; justify-content: center; align-items: center; margin: 1mm 0;">
                {svg_barcode}
            </div>
            <div class="label-meta-row" style="display: flex; justify-content: space-between; align-items: center; width: 100%; font-size: {dim["font_size"] - 1}pt; font-weight: 600;">
                {f'<span class="label-sku">SKU: {sku}</span>' if inc_sku and sku else '<span></span>'}
                <div class="label-pricing" style="display: flex; gap: 4px;">
                    {f'<span class="label-mrp" style="text-decoration: line-through; color: #475569;">MRP: ₹{mrp:.2f}</span>' if inc_mrp and mrp > sales_price else ''}
                    {f'<span class="label-price" style="font-weight: 800; color: #000;">₹{sales_price:.2f}</span>' if inc_price and sales_price > 0 else ''}
                </div>
            </div>
        </div>
        """

        # Generate copies
        labels_html = "\n".join([label_inner for _ in range(copies_count)])

        html_doc = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Barcode Label - {barcode}</title>
    <style>
        {page_rule}
        @media print {{
            html, body {{
                zoom: 1 !important;
                transform: none !important;
                margin: 0 !important;
                padding: 0 !important;
                background: #ffffff !important;
            }}
            .physical-barcode-label {{
                border: none !important;
                page-break-after: always;
            }}
        }}
        body {{
            margin: 0;
            padding: 10px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            background: #f1f5f9;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: center;
        }}
    </style>
</head>
<body>
    {labels_html}
    <script>
        window.onload = function() {{
            if (window.location.search.includes('autoprint=true')) {{
                window.print();
            }}
        }};
    </script>
</body>
</html>
"""
        return html_doc
        return html_doc


barcode_service = BarcodeService()
