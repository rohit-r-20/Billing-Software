"""
Inventory Configuration Service for Anti-Matrix Billing V2 (Phase 6).
Provides centralized, company-aware and branch-aware inventory settings for:
- General inventory settings (UOM, decimal precision, fractional quantities, SKU/barcode)
- Stock control (Negative stock policy, availability validation, reorder/min/max stock levels)
- Stock valuation (Weighted Average Cost / FIFO)
- Warehouse & branch settings (Material centres, branch isolation, inter-branch transfers)
- Product tracking (Barcodes, Batches, Expiry date tracking, HSN linkage)
- Stock alerts & notifications (Low stock, out of stock, reorder notifications, expiry windows)

Guarantees accounting and transaction immutability, preserves historical stock movements,
and keeps Fast Billing JSON storage separate from Traditional Billing SQLite/Postgres.
"""

import copy
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, and_

from core.configuration import config
from core.logging_config import logger
from db.database import db_manager, DatabaseManager
from db.traditional_database import traditional_db_manager
from db.traditional_models import (
    Company,
    Branch,
    InventoryConfiguration,
    utc_now,
)


DEFAULT_INVENTORY_CONFIG: Dict[str, Any] = {
    "enable_inventory_tracking": True,
    "default_uom": "Pcs.",
    "qty_decimal_precision": 3,
    "allow_fractional_qty": True,
    "default_product_type": "Stockable",
    "auto_generate_sku": True,
    "barcode_symbology": "EAN-13",
    "allow_negative_stock": False,
    "validate_stock_on_sale": True,
    "stock_warning_behavior": "warn_and_allow",  # block_outward, warn_and_allow, silent_allow
    "low_stock_alert_enabled": True,
    "default_min_stock_level": 10.0,
    "default_reorder_level": 15.0,
    "default_reorder_qty": 50.0,
    "default_max_stock_level": 500.0,
    "valuation_method": "weighted_average",  # weighted_average, fifo
    "default_material_centre": "Main Store",
    "track_branch_stock": True,
    "allow_inter_branch_transfer": True,
    "enable_batch_tracking": False,
    "enable_expiry_tracking": False,
    "enable_barcode_tracking": True,
    "link_hsn_sac": True,
    "warn_on_low_stock": True,
    "warn_on_negative_stock": True,
    "warn_on_expiry": False,
    "expiry_warning_days": 30,
}


class InventoryConfigService:
    """Manages company and branch inventory configuration with strict auditability and isolation."""

    def __init__(
        self,
        fast_storage_path: Optional[Path] = None,
        db: Optional[DatabaseManager] = None
    ):
        self._fast_storage_path = (
            fast_storage_path
            if fast_storage_path is not None
            else Path("data/fast_inventory_configurations.json")
        )
        self.db = db or db_manager

    # =========================================================================
    # Validation & Utilities
    # =========================================================================

    def validate_config(self, data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validates complete inventory configuration payload.
        Returns (is_valid, errors_list, cleaned_dict).
        """
        errors: List[str] = []
        cleaned: Dict[str, Any] = copy.deepcopy(DEFAULT_INVENTORY_CONFIG)

        # 1. General Inventory Settings
        cleaned["enable_inventory_tracking"] = bool(data.get("enable_inventory_tracking", True))
        raw_uom = str(data.get("default_uom") or "Pcs.").strip()
        if not raw_uom:
            errors.append("Default unit of measurement (UOM) cannot be empty.")
        cleaned["default_uom"] = raw_uom[:30]

        try:
            prec = int(data.get("qty_decimal_precision") if data.get("qty_decimal_precision") is not None else 3)
            if prec < 0 or prec > 4:
                errors.append("Quantity decimal precision must be between 0 and 4.")
            cleaned["qty_decimal_precision"] = min(max(0, prec), 4)
        except (ValueError, TypeError):
            errors.append("Quantity decimal precision must be a valid integer.")
            cleaned["qty_decimal_precision"] = 3

        cleaned["allow_fractional_qty"] = bool(data.get("allow_fractional_qty", True))

        prod_type = str(data.get("default_product_type") or "Stockable").strip()
        if prod_type not in ("Stockable", "Consumable", "Service"):
            errors.append("Product type must be 'Stockable', 'Consumable', or 'Service'.")
            prod_type = "Stockable"
        cleaned["default_product_type"] = prod_type

        cleaned["auto_generate_sku"] = bool(data.get("auto_generate_sku", True))

        symb = str(data.get("barcode_symbology") or "EAN-13").strip()
        if symb not in ("EAN-13", "UPC-A", "Code 128", "EAN-8", "Custom"):
            errors.append("Barcode symbology must be 'EAN-13', 'UPC-A', 'Code 128', 'EAN-8', or 'Custom'.")
            symb = "EAN-13"
        cleaned["barcode_symbology"] = symb

        # 2. Stock Control & Negative Stock Policy
        cleaned["allow_negative_stock"] = bool(data.get("allow_negative_stock", False))
        cleaned["validate_stock_on_sale"] = bool(data.get("validate_stock_on_sale", True))

        warn_beh = str(data.get("stock_warning_behavior") or "warn_and_allow").strip()
        if warn_beh not in ("block_outward", "warn_and_allow", "silent_allow"):
            errors.append("Stock warning behavior must be 'block_outward', 'warn_and_allow', or 'silent_allow'.")
            warn_beh = "warn_and_allow"
        cleaned["stock_warning_behavior"] = warn_beh

        cleaned["low_stock_alert_enabled"] = bool(data.get("low_stock_alert_enabled", True))

        for fld, default_val in [
            ("default_min_stock_level", 10.0),
            ("default_reorder_level", 15.0),
            ("default_reorder_qty", 50.0),
            ("default_max_stock_level", 500.0),
        ]:
            try:
                val = float(data.get(fld) if data.get(fld) is not None else default_val)
                if val < 0.0:
                    errors.append(f"{fld.replace('_', ' ').capitalize()} cannot be negative.")
                cleaned[fld] = max(0.0, val)
            except (ValueError, TypeError):
                errors.append(f"{fld.replace('_', ' ').capitalize()} must be a valid number.")
                cleaned[fld] = default_val

        # Level coherence: min_stock <= reorder_level <= max_stock
        if cleaned["default_reorder_level"] < cleaned["default_min_stock_level"]:
            errors.append("Default reorder level cannot be less than minimum stock level.")

        if cleaned["default_max_stock_level"] < cleaned["default_reorder_level"]:
            errors.append("Default maximum stock level cannot be less than reorder level.")

        # 3. Stock Valuation
        val_method = str(data.get("valuation_method") or "weighted_average").strip().lower()
        if val_method not in ("weighted_average", "fifo"):
            errors.append("Stock valuation method must be 'weighted_average' or 'fifo'.")
            val_method = "weighted_average"
        cleaned["valuation_method"] = val_method

        # 4. Warehouse & Branch
        cleaned["default_material_centre"] = str(data.get("default_material_centre") or "Main Store").strip()[:100]
        cleaned["track_branch_stock"] = bool(data.get("track_branch_stock", True))
        cleaned["allow_inter_branch_transfer"] = bool(data.get("allow_inter_branch_transfer", True))

        # 5. Product Tracking
        cleaned["enable_batch_tracking"] = bool(data.get("enable_batch_tracking", False))
        cleaned["enable_expiry_tracking"] = bool(data.get("enable_expiry_tracking", False))
        cleaned["enable_barcode_tracking"] = bool(data.get("enable_barcode_tracking", True))
        cleaned["link_hsn_sac"] = bool(data.get("link_hsn_sac", True))

        # 6. Alerts & Notifications
        cleaned["warn_on_low_stock"] = bool(data.get("warn_on_low_stock", True))
        cleaned["warn_on_negative_stock"] = bool(data.get("warn_on_negative_stock", True))
        cleaned["warn_on_expiry"] = bool(data.get("warn_on_expiry", False))
        try:
            exp_days = int(data.get("expiry_warning_days") if data.get("expiry_warning_days") is not None else 30)
            cleaned["expiry_warning_days"] = max(1, exp_days)
        except (ValueError, TypeError):
            cleaned["expiry_warning_days"] = 30

        is_valid = len(errors) == 0
        return is_valid, errors, cleaned

    def validate_quantity(self, qty: float, cfg: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validates an item quantity against fractional quantity and decimal precision rules.
        """
        allow_fractional = cfg.get("allow_fractional_qty", True)
        precision = int(cfg.get("qty_decimal_precision", 3))

        if not allow_fractional:
            if abs(qty - round(qty)) > 1e-6:
                return False, f"Fractional quantity ({qty}) is not permitted. Only whole integer units are allowed."

        # Check precision
        qty_str = f"{qty:.8f}".rstrip("0").rstrip(".")
        if "." in qty_str:
            dec_len = len(qty_str.split(".")[1])
            if dec_len > precision:
                return False, f"Quantity precision ({dec_len} decimals) exceeds configured limit ({precision} decimals)."

        return True, "Valid quantity."

    def simulate_stock_transaction(
        self,
        cfg: Dict[str, Any],
        current_stock: float,
        inward_qty: float = 0.0,
        outward_qty: float = 0.0,
        unit_cost: float = 0.0,
        current_wac: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Runs an in-memory stock simulation without writing to database.
        Demonstrates projected balance, negative stock validation, and WAC rate updates.
        """
        allow_negative = bool(cfg.get("allow_negative_stock", False))
        min_level = float(cfg.get("default_min_stock_level", 10.0))
        reorder_level = float(cfg.get("default_reorder_level", 15.0))

        projected_stock = current_stock + inward_qty - outward_qty

        # Negative stock check
        is_blocked = False
        warning_msg = None
        if projected_stock < -1e-6 and not allow_negative:
            is_blocked = True
            warning_msg = f"Transaction blocked: Requested outward {outward_qty:g} would reduce stock to {projected_stock:g}. Negative stock is disabled."
        elif projected_stock < -1e-6 and allow_negative:
            warning_msg = f"Warning: Stock will drop negative ({projected_stock:g}). Permitted by company policy."

        # Valuation update (Weighted Average Cost)
        new_wac = current_wac
        if inward_qty > 0 and unit_cost > 0:
            existing_val = max(0.0, current_stock) * current_wac
            inward_val = inward_qty * unit_cost
            total_qty = max(0.0, current_stock) + inward_qty
            if total_qty > 0:
                new_wac = round((existing_val + inward_val) / total_qty, 2)

        # Status
        if projected_stock < 0:
            status = "NEGATIVE_STOCK"
        elif projected_stock == 0:
            status = "OUT_OF_STOCK"
        elif projected_stock <= min_level:
            status = "LOW_STOCK"
        elif projected_stock <= reorder_level:
            status = "REORDER_REQUIRED"
        else:
            status = "OPTIMAL"

        return {
            "current_stock": round(current_stock, 3),
            "inward_qty": round(inward_qty, 3),
            "outward_qty": round(outward_qty, 3),
            "projected_stock": round(projected_stock, 3),
            "is_blocked": is_blocked,
            "warning_msg": warning_msg,
            "valuation_rate": new_wac,
            "projected_valuation": round(max(0.0, projected_stock) * new_wac, 2),
            "status": status,
        }

    # =========================================================================
    # Synchronization with Company Negative Stock Policy
    # =========================================================================

    def sync_company_negative_stock(self, company_id: str, allow_negative: bool) -> None:
        """
        Synchronizes allow_negative_stock policy into SQLite company_configs table
        so that BillingService and InventoryService immediately enforce it.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                val = 1 if allow_negative else 0
                cursor.execute("""
                    INSERT INTO company_configs (company_id, allow_negative_stock, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(company_id) DO UPDATE SET
                        allow_negative_stock = excluded.allow_negative_stock,
                        updated_at = CURRENT_TIMESTAMP;
                """, (company_id, val))
                conn.commit()
                logger.info(f"Synchronized company_configs.allow_negative_stock={val} for company {company_id}")
        except Exception as e:
            logger.warning(f"Could not synchronize company_configs.allow_negative_stock: {e}")

    # =========================================================================
    # Traditional Billing Storage (SQLite / PostgreSQL)
    # =========================================================================

    def get_traditional_config(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieves inventory configuration from Traditional DB, falling back to company defaults."""
        fallback = copy.deepcopy(DEFAULT_INVENTORY_CONFIG)
        fallback["company_id"] = company_id
        fallback["branch_id"] = branch_id

        try:
            with traditional_db_manager.read_session_scope() as session:
                cfg_row = None
                if branch_id:
                    cfg_row = session.scalar(
                        select(InventoryConfiguration).where(
                            and_(
                                InventoryConfiguration.company_id == company_id,
                                InventoryConfiguration.branch_id == branch_id,
                            )
                        )
                    )

                if not cfg_row:
                    cfg_row = session.scalar(
                        select(InventoryConfiguration).where(
                            and_(
                                InventoryConfiguration.company_id == company_id,
                                InventoryConfiguration.branch_id.is_(None),
                            )
                        )
                    )

                if not cfg_row and branch_id is None:
                    cfg_row = session.scalar(
                        select(InventoryConfiguration).where(
                            InventoryConfiguration.company_id == company_id
                        )
                    )

                if cfg_row:
                    res = copy.deepcopy(fallback)
                    res["id"] = cfg_row.id
                    res["enable_inventory_tracking"] = cfg_row.enable_inventory_tracking
                    res["default_uom"] = cfg_row.default_uom
                    res["qty_decimal_precision"] = cfg_row.qty_decimal_precision
                    res["allow_fractional_qty"] = cfg_row.allow_fractional_qty
                    res["default_product_type"] = cfg_row.default_product_type
                    res["auto_generate_sku"] = cfg_row.auto_generate_sku
                    res["barcode_symbology"] = cfg_row.barcode_symbology
                    res["allow_negative_stock"] = cfg_row.allow_negative_stock
                    res["validate_stock_on_sale"] = cfg_row.validate_stock_on_sale
                    res["stock_warning_behavior"] = cfg_row.stock_warning_behavior
                    res["low_stock_alert_enabled"] = cfg_row.low_stock_alert_enabled
                    res["default_min_stock_level"] = float(cfg_row.default_min_stock_level)
                    res["default_reorder_level"] = float(cfg_row.default_reorder_level)
                    res["default_reorder_qty"] = float(cfg_row.default_reorder_qty)
                    res["default_max_stock_level"] = float(cfg_row.default_max_stock_level)
                    res["valuation_method"] = cfg_row.valuation_method
                    res["default_material_centre"] = cfg_row.default_material_centre
                    res["track_branch_stock"] = cfg_row.track_branch_stock
                    res["allow_inter_branch_transfer"] = cfg_row.allow_inter_branch_transfer
                    res["enable_batch_tracking"] = cfg_row.enable_batch_tracking
                    res["enable_expiry_tracking"] = cfg_row.enable_expiry_tracking
                    res["enable_barcode_tracking"] = cfg_row.enable_barcode_tracking
                    res["link_hsn_sac"] = cfg_row.link_hsn_sac
                    res["warn_on_low_stock"] = cfg_row.warn_on_low_stock
                    res["warn_on_negative_stock"] = cfg_row.warn_on_negative_stock
                    res["warn_on_expiry"] = cfg_row.warn_on_expiry
                    res["expiry_warning_days"] = cfg_row.expiry_warning_days
                    res["company_id"] = cfg_row.company_id
                    res["branch_id"] = cfg_row.branch_id
                    return res

        except Exception as e:
            logger.error(f"Error reading traditional inventory configuration: {e}")

        return fallback

    def save_traditional_config(
        self,
        company_id: str,
        config_data: Optional[Dict[str, Any]] = None,
        branch_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Saves inventory configuration to Traditional database and synchronizes company negative stock policy."""
        payload = config_data if config_data is not None else data
        is_valid, errors, cleaned = self.validate_config(payload or {})
        if not is_valid:
            raise ValueError(f"Inventory validation failed: {'; '.join(errors)}")

        with traditional_db_manager.session_scope() as session:
            query = select(InventoryConfiguration).where(
                InventoryConfiguration.company_id == company_id
            )
            if branch_id:
                query = query.where(InventoryConfiguration.branch_id == branch_id)
            else:
                query = query.where(InventoryConfiguration.branch_id.is_(None))

            cfg_row = session.scalar(query)
            if not cfg_row:
                cfg_row = InventoryConfiguration(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    branch_id=branch_id,
                )
                session.add(cfg_row)

            # Assign fields
            cfg_row.enable_inventory_tracking = cleaned["enable_inventory_tracking"]
            cfg_row.default_uom = cleaned["default_uom"]
            cfg_row.qty_decimal_precision = cleaned["qty_decimal_precision"]
            cfg_row.allow_fractional_qty = cleaned["allow_fractional_qty"]
            cfg_row.default_product_type = cleaned["default_product_type"]
            cfg_row.auto_generate_sku = cleaned["auto_generate_sku"]
            cfg_row.barcode_symbology = cleaned["barcode_symbology"]
            cfg_row.allow_negative_stock = cleaned["allow_negative_stock"]
            cfg_row.validate_stock_on_sale = cleaned["validate_stock_on_sale"]
            cfg_row.stock_warning_behavior = cleaned["stock_warning_behavior"]
            cfg_row.low_stock_alert_enabled = cleaned["low_stock_alert_enabled"]
            cfg_row.default_min_stock_level = cleaned["default_min_stock_level"]
            cfg_row.default_reorder_level = cleaned["default_reorder_level"]
            cfg_row.default_reorder_qty = cleaned["default_reorder_qty"]
            cfg_row.default_max_stock_level = cleaned["default_max_stock_level"]
            cfg_row.valuation_method = cleaned["valuation_method"]
            cfg_row.default_material_centre = cleaned["default_material_centre"]
            cfg_row.track_branch_stock = cleaned["track_branch_stock"]
            cfg_row.allow_inter_branch_transfer = cleaned["allow_inter_branch_transfer"]
            cfg_row.enable_batch_tracking = cleaned["enable_batch_tracking"]
            cfg_row.enable_expiry_tracking = cleaned["enable_expiry_tracking"]
            cfg_row.enable_barcode_tracking = cleaned["enable_barcode_tracking"]
            cfg_row.link_hsn_sac = cleaned["link_hsn_sac"]
            cfg_row.warn_on_low_stock = cleaned["warn_on_low_stock"]
            cfg_row.warn_on_negative_stock = cleaned["warn_on_negative_stock"]
            cfg_row.warn_on_expiry = cleaned["warn_on_expiry"]
            cfg_row.expiry_warning_days = cleaned["expiry_warning_days"]

            session.flush()

        # Synchronize negative stock policy to company_configs in database
        self.sync_company_negative_stock(company_id, cleaned["allow_negative_stock"])

        return self.get_traditional_config(company_id, branch_id=branch_id)

    def reset_traditional_config(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resets inventory configuration to standard factory defaults."""
        with traditional_db_manager.session_scope() as session:
            query = select(InventoryConfiguration).where(
                InventoryConfiguration.company_id == company_id
            )
            if branch_id:
                query = query.where(InventoryConfiguration.branch_id == branch_id)
            else:
                query = query.where(InventoryConfiguration.branch_id.is_(None))

            cfg_row = session.scalar(query)
            if cfg_row:
                session.delete(cfg_row)

        self.sync_company_negative_stock(company_id, False)
        return self.get_traditional_config(company_id, branch_id=branch_id)

    # =========================================================================
    # Fast Billing Storage (JSON File Isolation)
    # =========================================================================

    def _read_fast_storage(self) -> Dict[str, Any]:
        if not self._fast_storage_path.exists():
            return {}
        try:
            with open(self._fast_storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading fast inventory storage: {e}")
            return {}

    def _write_fast_storage(self, data: Dict[str, Any]) -> None:
        try:
            self._fast_storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._fast_storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error writing fast inventory storage: {e}")

    def get_fast_config(self, company_id: str = "default") -> Dict[str, Any]:
        """Retrieves inventory configuration for Fast Billing from JSON storage."""
        store = self._read_fast_storage()
        key = str(company_id)
        if key in store:
            cfg = copy.deepcopy(store[key])
            cfg["company_id"] = company_id
            return cfg

        fallback = copy.deepcopy(DEFAULT_INVENTORY_CONFIG)
        fallback["company_id"] = company_id
        return fallback

    def save_fast_config(
        self,
        company_id: Any = "default",
        config_data: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Saves inventory configuration for Fast Billing without touching SQLite DB."""
        if isinstance(company_id, dict):
            payload = company_id
            cid = str(payload.get("company_id") or "default")
        else:
            payload = config_data if config_data is not None else data
            cid = str(company_id or "default")

        is_valid, errors, cleaned = self.validate_config(payload or {})
        if not is_valid:
            raise ValueError(f"Fast Billing inventory validation failed: {'; '.join(errors)}")

        store = self._read_fast_storage()
        cleaned["company_id"] = cid
        store[cid] = cleaned
        self._write_fast_storage(store)
        return self.get_fast_config(cid)

    def reset_fast_config(self, company_id: str = "default") -> Dict[str, Any]:
        """Resets Fast Billing inventory configuration to factory defaults."""
        store = self._read_fast_storage()
        key = str(company_id)
        if key in store:
            del store[key]
            self._write_fast_storage(store)
        return self.get_fast_config(company_id)

    # =========================================================================
    # Unified Mode-Aware API
    # =========================================================================

    def get_config(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        billing_mode: str = "traditional",
    ) -> Dict[str, Any]:
        """Returns inventory configuration based on active billing mode."""
        if billing_mode == "fast_billing":
            return self.get_fast_config(company_id)
        return self.get_traditional_config(company_id, branch_id=branch_id)

    def save_config(
        self,
        company_id: str,
        data: Dict[str, Any],
        branch_id: Optional[str] = None,
        billing_mode: str = "traditional",
    ) -> Dict[str, Any]:
        """Saves inventory configuration based on active billing mode."""
        if billing_mode == "fast_billing":
            return self.save_fast_config(company_id, config_data=data)
        return self.save_traditional_config(company_id, config_data=data, branch_id=branch_id)

    def reset_config(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        billing_mode: str = "traditional",
    ) -> Dict[str, Any]:
        """Resets inventory configuration based on active billing mode."""
        if billing_mode == "fast_billing":
            return self.reset_fast_config(company_id)
        return self.reset_traditional_config(company_id, branch_id=branch_id)


inventory_config_service = InventoryConfigService()
