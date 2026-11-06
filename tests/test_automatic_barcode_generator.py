"""
Automated Test Suite for Alpha Billing - Automatic Unique Barcode Generator in Item & Product Master

Verifies all requirements:
1. Internal Alpha Billing Code 128 Barcode generation with monotonic sequence (AB000000000001).
2. Database uniqueness enforcement across primary and alternate barcodes.
3. Concurrency safety: atomic sequence increment with zero duplicate barcode generation under load.
4. Collision avoidance: sequence safely skips any manually entered/pre-existing barcode numbers.
5. Standard GS1 Barcode validation:
   - Modulo-10 checksum validation for EAN-13, UPC-A, and EAN-8.
   - Internal Code 128 format recognition.
   - Generic alphanumeric Code 128 validation.
6. Multiple barcodes per product:
   - Manufacturer EAN-13, internal Code 128, alternate case barcode.
   - Both primary and alternate barcodes resolve to the exact same product.
   - Resolution works seamlessly across Traditional Billing, Fast Billing, and Catalogue lookups.
7. Sellable Product Variants:
   - "Milk Bikis 100g" and "Milk Bikis 200g" have distinct unique barcodes and resolve independently.
8. Duplicate barcode assignment rejection in Item Master:
   - Attempting to assign an in-use barcode to another product raises a descriptive ValueError.
9. SVG Barcode rendering with high-contrast lines and human-readable text.
10. Physical Barcode Label Printing generation:
   - Exact millimeter dimensions (50x25mm, 38x25mm, 50x38mm, A4 24 labels).
   - Decoupled from application screen zoom.
11. WebChannel BackendBridge integration:
   - JSON serialization of all pyqtSlots for desktop UI consumption.
12. Existing barcode preservation:
   - Saving/modifying unrelated product fields preserves existing manufacturer barcodes intact.
"""

import json
import uuid
import pytest
from concurrent.futures import ThreadPoolExecutor

from db.database import db_manager
from services.barcode_service import barcode_service
from services.catalogue_service import catalogue_service
from desktop.web_bridge import BackendBridge


@pytest.fixture(scope="module")
def active_company():
    """Retrieve or create test company."""
    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT id, name FROM companies LIMIT 1;").fetchone()
        if row:
            return {"id": row["id"], "name": row["name"]}
        comp_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO companies (id, code, name, state)
            VALUES (?, 'CMP-TEST-BC', 'Barcode Test Company', 'Tamil Nadu');
        """, (comp_id,))
        return {"id": comp_id, "name": "Barcode Test Company"}


@pytest.fixture(scope="module")
def active_branch(active_company):
    """Retrieve or create test branch."""
    with db_manager.get_connection() as conn:
        row = conn.execute(
            "SELECT id, name FROM branches WHERE company_id = ? LIMIT 1;",
            (active_company["id"],)
        ).fetchone()
        if row:
            return {"id": row["id"], "name": row["name"]}
        br_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO branches (id, company_id, code, name)
            VALUES (?, ?, 'BR-BC-1', 'Main Branch');
        """, (br_id, active_company["id"]))
        return {"id": br_id, "name": "Main Branch"}


class TestAutomaticBarcodeGenerator:
    """Test suite verifying Alpha Billing barcode generation, validation, uniqueness, and label printing."""

    def test_01_atomic_monotonic_internal_barcode_generation(self, active_company):
        """Test consecutive internal Code 128 barcode generation produces sequential AB... values."""
        res1 = barcode_service.generate_internal_barcode(company_id=active_company["id"])
        res2 = barcode_service.generate_internal_barcode(company_id=active_company["id"])

        b1 = res1["barcode"] if isinstance(res1, dict) else res1
        b2 = res2["barcode"] if isinstance(res2, dict) else res2

        assert b1.startswith("AB"), f"Expected prefix 'AB', got {b1}"
        assert b2.startswith("AB"), f"Expected prefix 'AB', got {b2}"
        assert len(b1) == 14, f"Expected length 14 (AB + 12 digits), got {len(b1)}"
        assert len(b2) == 14, f"Expected length 14 (AB + 12 digits), got {len(b2)}"

        num1 = int(b1[2:])
        num2 = int(b2[2:])
        assert num2 == num1 + 1, f"Expected sequential allocation: {num1} -> {num2}"

    def test_02_checksum_validation_gs1_and_code128(self):
        """Verify checksum algorithms for GS1 EAN-13, UPC-A, EAN-8 and Code 128."""
        # 1. Valid GS1 EAN-13 (Milk Bikis real manufacturer barcode)
        v_ean13 = barcode_service.validate_barcode("8901207033728")
        assert v_ean13["is_valid"] is True
        assert v_ean13["format"] == "EAN-13"

        # Invalid GS1 EAN-13 (wrong check digit: expected 8, provided 9)
        inv_ean13 = barcode_service.validate_barcode("8901207033729")
        assert inv_ean13["is_valid"] is False
        assert ("check digit" in inv_ean13["message"].lower() or "invalid" in inv_ean13["message"].lower())

        # 2. Valid UPC-A
        v_upc = barcode_service.validate_barcode("012345678905")
        assert v_upc["is_valid"] is True
        assert v_upc["format"] == "UPC-A"

        # Invalid UPC-A (wrong check digit)
        inv_upc = barcode_service.validate_barcode("012345678904")
        assert inv_upc["is_valid"] is False

        # 3. Valid EAN-8
        v_ean8 = barcode_service.validate_barcode("96385074")
        assert v_ean8["is_valid"] is True
        assert v_ean8["format"] == "EAN-8"

        # Invalid EAN-8
        inv_ean8 = barcode_service.validate_barcode("96385070")
        assert inv_ean8["is_valid"] is False

        # 4. Internal Alpha Billing Code 128
        v_alpha = barcode_service.validate_barcode("AB000000000042")
        assert v_alpha["is_valid"] is True
        assert v_alpha["format"] == "ALPHA_CODE128"

        # 5. Generic Alphanumeric Code 128
        v_c128 = barcode_service.validate_barcode("SKU-PROD-9988")
        assert v_c128["is_valid"] is True
        assert v_c128["format"] == "CODE128"

        # 6. Invalid empty/symbol barcode
        v_empty = barcode_service.validate_barcode("  ")
        assert v_empty["is_valid"] is False

    def test_03_concurrent_internal_barcode_generation(self, active_company):
        """Verify thread-safety and multi-request concurrency without duplicate IDs."""
        count = 15

        def generate_one(_):
            r = barcode_service.generate_internal_barcode(company_id=active_company["id"])
            return r["barcode"] if isinstance(r, dict) else r

        with ThreadPoolExecutor(max_workers=5) as executor:
            barcodes = list(executor.map(generate_one, range(count)))

        assert len(barcodes) == count
        assert len(set(barcodes)) == count, "Collision detected during concurrent generation!"

    def test_04_collision_avoidance_with_preexisting_barcodes(self, active_company):
        """Verify generator skips numbers that were manually created before sequence caught up."""
        # Peek at current sequence value
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT current_value FROM barcode_sequences WHERE sequence_name = 'INTERNAL_ALPHA_CODE128';"
            )
            row = cursor.fetchone()
            curr = int(row["current_value"]) if row else 0

        target_colliding_val = curr + 1
        colliding_barcode = f"AB{target_colliding_val:012d}"

        # Insert manual item with this colliding barcode
        manual_item_id = str(uuid.uuid4())
        manual_name = f"Manual Collision Pre-set {uuid.uuid4().hex[:6]}"
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO items (id, company_id, name, print_name, alias, mrp, sales_price)
                VALUES (?, ?, ?, ?, ?, 50.0, 45.0);
            """, (manual_item_id, active_company["id"], manual_name, manual_name, colliding_barcode))
            cursor.execute("""
                INSERT INTO item_barcodes (id, item_id, company_id, barcode, is_primary)
                VALUES (?, ?, ?, ?, 1);
            """, (str(uuid.uuid4()), manual_item_id, active_company["id"], colliding_barcode))
            conn.commit()

        # Now trigger generation - it must detect collision with colliding_barcode and skip to target_colliding_val + 1
        alloc_res = barcode_service.generate_internal_barcode(company_id=active_company["id"])
        allocated = alloc_res["barcode"] if isinstance(alloc_res, dict) else alloc_res
        assert allocated != colliding_barcode, "Generator allocated an already existing barcode!"
        assert int(allocated[2:]) > target_colliding_val

    def test_05_multiple_barcodes_per_product(self, active_company, active_branch):
        """Verify product can hold primary barcode and multiple alternates, all resolving to same product."""
        unique_suffix = uuid.uuid4().hex[:6].upper()
        primary_bc = f"8901207{unique_suffix}0"  # We'll use a unique string for testing
        alt_res = barcode_service.generate_internal_barcode(company_id=active_company["id"])
        alt_bc1 = alt_res["barcode"] if isinstance(alt_res, dict) else alt_res
        alt_bc2 = f"CASE-{unique_suffix}"

        item_payload = {
            "name": f"Parle-G Multi-Barcode {unique_suffix}",
            "print_name": f"Parle-G Multi-Barcode {unique_suffix}",
            "alias": primary_bc,
            "category": "Biscuits",
            "unit": "NOS",
            "mrp": 30.0,
            "sales_price": 28.0,
            "purchase_price": 22.0,
            "tax_rate": 5.0,
            "company_id": active_company["id"],
            "alternate_barcodes": [alt_bc1, alt_bc2]
        }

        saved = catalogue_service.save_item(item_payload)
        item_id = saved["id"]

        # 1. Verify item barcodes retrieved via barcode service
        item_bcs = barcode_service.get_item_barcodes(item_id)
        assert len(item_bcs) == 3
        codes = [b["barcode"] for b in item_bcs]
        assert primary_bc in codes
        assert alt_bc1 in codes
        assert alt_bc2 in codes

        # 2. Verify find_by_barcode resolves to same item via ANY of the 3 barcodes
        by_primary = catalogue_service.find_by_barcode(primary_bc, company_id=active_company["id"])
        assert by_primary is not None
        assert by_primary["id"] == item_id

        by_alt1 = catalogue_service.find_by_barcode(alt_bc1, company_id=active_company["id"])
        assert by_alt1 is not None
        assert by_alt1["id"] == item_id

        by_alt2 = catalogue_service.find_by_barcode(alt_bc2, company_id=active_company["id"])
        assert by_alt2 is not None
        assert by_alt2["id"] == item_id

        # 3. Verify Fast Billing cashier barcode scanner resolves via primary and alternate
        pos_primary = catalogue_service.get_cashier_product_by_barcode(primary_bc, active_branch["id"], active_company["id"])
        assert pos_primary is not None
        assert pos_primary["id"] == item_id

        pos_alt1 = catalogue_service.get_cashier_product_by_barcode(alt_bc1, active_branch["id"], active_company["id"])
        assert pos_alt1 is not None
        assert pos_alt1["id"] == item_id

    def test_06_product_variants_resolution(self, active_company, active_branch):
        """Verify sellable variants (Milk Bikis 100g vs 200g) have separate barcodes and resolve independently."""
        unique_code = uuid.uuid4().hex[:6]
        bc_100g = f"89012071{unique_code}"
        bc_200g = f"89012072{unique_code}"

        payload_100g = {
            "name": f"Milk Bikis 100g {unique_code}",
            "print_name": f"Milk Bikis 100g {unique_code}",
            "alias": bc_100g,
            "category": "Biscuits",
            "unit": "NOS",
            "mrp": 10.0,
            "sales_price": 10.0,
            "purchase_price": 8.0,
            "tax_rate": 5.0,
            "company_id": active_company["id"]
        }
        item_100g = catalogue_service.save_item(payload_100g)

        payload_200g = {
            "name": f"Milk Bikis 200g {unique_code}",
            "print_name": f"Milk Bikis 200g {unique_code}",
            "alias": bc_200g,
            "category": "Biscuits",
            "unit": "NOS",
            "mrp": 20.0,
            "sales_price": 19.0,
            "purchase_price": 16.0,
            "tax_rate": 5.0,
            "company_id": active_company["id"]
        }
        item_200g = catalogue_service.save_item(payload_200g)

        # Ensure distinct IDs
        assert item_100g["id"] != item_200g["id"]

        # Ensure exact isolated resolution
        res_100g = catalogue_service.find_by_barcode(bc_100g, company_id=active_company["id"])
        res_200g = catalogue_service.find_by_barcode(bc_200g, company_id=active_company["id"])

        assert res_100g["id"] == item_100g["id"]
        assert res_100g["name"].upper() == payload_100g["name"].upper()

        assert res_200g["id"] == item_200g["id"]
        assert res_200g["name"].upper() == payload_200g["name"].upper()

    def test_07_duplicate_barcode_assignment_prevention(self, active_company):
        """Verify assigning an existing barcode to another product is rejected."""
        unique_bc = f"DUP-CHECK-{uuid.uuid4().hex[:6]}"

        p1 = {
            "name": "Product Owner of Barcode",
            "print_name": "Product Owner of Barcode",
            "alias": unique_bc,
            "category": "General",
            "unit": "NOS",
            "mrp": 100.0,
            "sales_price": 90.0,
            "company_id": active_company["id"]
        }
        catalogue_service.save_item(p1)

        # Attempt to save a second product with the same primary barcode
        p2 = {
            "name": "Product Attempting Hijack",
            "print_name": "Product Attempting Hijack",
            "alias": unique_bc,
            "category": "General",
            "unit": "NOS",
            "mrp": 150.0,
            "sales_price": 140.0,
            "company_id": active_company["id"]
        }
        with pytest.raises(ValueError) as excinfo:
            catalogue_service.save_item(p2)
        assert ("already assigned" in str(excinfo.value).lower() or "already registered" in str(excinfo.value).lower())

        # Attempt to add this barcode as an alternate barcode to a third product
        p3 = {
            "name": "Product Attempting Alt Hijack",
            "print_name": "Product Attempting Alt Hijack",
            "alias": f"DIFF-BC-{uuid.uuid4().hex[:6]}",
            "category": "General",
            "unit": "NOS",
            "mrp": 200.0,
            "sales_price": 180.0,
            "company_id": active_company["id"],
            "alternate_barcodes": [unique_bc]
        }
        with pytest.raises(ValueError) as excinfo_alt:
            catalogue_service.save_item(p3)
        assert ("already assigned" in str(excinfo_alt.value).lower() or "already registered" in str(excinfo_alt.value).lower())

    def test_08_svg_barcode_rendering(self):
        """Verify SVG barcode generation renders high-contrast scannable vector graphics."""
        # Render Code 128
        svg_c128 = barcode_service.render_barcode_svg("AB000000000088", "CODE128", include_text=True)
        assert svg_c128.startswith("<svg") or "<svg" in svg_c128
        assert "</svg>" in svg_c128
        assert "AB000000000088" in svg_c128

        # Render EAN-13
        svg_ean13 = barcode_service.render_barcode_svg("8901207033728", "EAN13", include_text=True)
        assert "<svg" in svg_ean13
        assert "</svg>" in svg_ean13
        assert ("8901207033728" in svg_ean13 or ("901207" in svg_ean13 and "033728" in svg_ean13))

    def test_09_label_printing_html_dimensions_and_zoom_isolation(self, active_company):
        """Verify physical label generation produces exact millimeter dimensions isolated from zoom."""
        test_item = {
            "name": "Britannia Milk Bikis 100g",
            "alias": "8901207033728",
            "mrp": 10.0,
            "sales_price": 10.0
        }

        # 1. Standard 50x25mm
        html_50x25 = barcode_service.generate_label_html(test_item, label_size="50x25", copies=3)
        assert "@page { size: 50mm 25mm; margin: 0; }" in html_50x25
        assert "width: 50mm;" in html_50x25
        assert "height: 25mm;" in html_50x25
        assert "Britannia Milk Bikis 100g" in html_50x25
        assert "8901207033728" in html_50x25
        # Verify zoom decoupling
        assert "zoom: 1 !important" in html_50x25
        # Count label elements = 3 copies
        assert html_50x25.count("barcode-label-box") == 3

        # 2. Compact 38x25mm
        html_38x25 = barcode_service.generate_label_html(test_item, label_size="38x25", copies=1)
        assert "@page { size: 38mm 25mm; margin: 0; }" in html_38x25

        # 3. Large 50x38mm
        html_50x38 = barcode_service.generate_label_html(test_item, label_size="50x38", copies=1)
        assert "@page { size: 50mm 38mm; margin: 0; }" in html_50x38

        # 4. A4 Sheet (24 labels)
        html_a4 = barcode_service.generate_label_html(test_item, label_size="a4_24", copies=24)
        assert "@page { size: A4 portrait; margin: 8mm; }" in html_a4
        assert html_a4.count("barcode-label-box") == 24

    def test_10_desktop_web_bridge_pyqt_slots(self, active_company):
        """Verify BackendBridge pyqtSlots return valid JSON responses for frontend UI integration."""
        bridge = BackendBridge()

        # 1. generateUniqueBarcode
        gen_raw = bridge.generateUniqueBarcode()
        gen_res = json.loads(gen_raw)
        assert gen_res["success"] is True
        assert gen_res["data"]["barcode"].startswith("AB")
        assert len(gen_res["data"]["barcode"]) == 14
        assert "<svg" in gen_res["data"]["svg"]

        # 2. validateBarcode
        val_raw = bridge.validateBarcode("8901207033728")
        val_res = json.loads(val_raw)
        assert val_res["success"] is True
        assert val_res["data"]["is_valid"] is True
        assert val_res["data"]["format"] == "EAN-13"

        # 3. checkBarcodeAvailability
        avail_raw = bridge.checkBarcodeAvailability("NON-EXISTENT-BARCODE-999")
        avail_res = json.loads(avail_raw)
        assert avail_res["success"] is True
        assert avail_res["data"]["is_unique"] is True

        # 4. renderBarcodeSvg
        svg_raw = bridge.renderBarcodeSvg("AB000000000099", "CODE128", True)
        svg_res = json.loads(svg_raw)
        assert svg_res["success"] is True
        assert "<svg" in svg_res["svg"]

    def test_11_existing_barcode_preservation_on_update(self, active_company):
        """Verify updating other item fields (e.g. price, name) preserves existing manufacturer barcode."""
        uniq = uuid.uuid4().hex[:6].upper()
        original_bc = f"89012070{uniq}"
        item_payload = {
            "name": f"Preservation Test Product {uniq}",
            "print_name": f"Preservation Test Product {uniq}",
            "alias": original_bc,
            "category": "Beverages",
            "unit": "BTL",
            "mrp": 50.0,
            "sales_price": 45.0,
            "company_id": active_company["id"]
        }
        saved = catalogue_service.save_item(item_payload)
        item_id = saved["id"]

        # Now modify sales_price and tax_rate without changing barcode
        update_payload = {
            "id": item_id,
            "name": f"Preservation Test Product Updated {uniq}",
            "print_name": f"Preservation Test Product Updated {uniq}",
            "alias": original_bc,
            "category": "Beverages",
            "unit": "BTL",
            "mrp": 55.0,
            "sales_price": 50.0,
            "tax_rate": 12.0,
            "company_id": active_company["id"]
        }
        updated = catalogue_service.save_item(update_payload)
        assert updated["sales_price"] == 50.0

        # Verify barcode remains identical and resolves properly
        fetched = catalogue_service.get_item_by_id(item_id)
        assert fetched["alias"] == original_bc
        assert fetched["primary_barcode"] == original_bc

        res = catalogue_service.find_by_barcode(original_bc, company_id=active_company["id"])
        assert res is not None
        assert res["id"] == item_id
