"""
GST & Tax Configuration Service for Anti-Matrix Billing V2.
Manages company-aware and branch-aware GST registration settings, tax rates,
calculation rules (inclusive/exclusive, intra/inter-state, rounding), HSN compliance,
and transaction defaults for:
1. Sales Invoice
2. Sales Return
3. Purchase Invoice
4. Purchase Return

Preserves historical transaction immutability, guarantees multi-tenant isolation,
and keeps Fast Billing configuration isolated without modifying SQLite DB.
"""

import copy
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, and_

from core.configuration import config
from core.logging_config import logger
from db.traditional_database import traditional_db_manager
from db.traditional_models import (
    Company,
    Branch,
    GstTaxConfiguration,
    utc_now,
)
from services.tax_service import tax_service, TaxService


# Standard GSTIN regex: 2 digits state + 5 alpha PAN + 4 digits PAN + 1 alpha PAN + 1 entity num/alpha + 'Z' + 1 checksum
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")

# Indian State Codes Mapping
INDIAN_STATE_CODES = {
    "01": "Jammu & Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra & Nagar Haveli and Daman & Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman & Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory",
}

DEFAULT_GST_CONFIG: Dict[str, Any] = {
    "is_gst_enabled": True,
    "gstin": "",
    "legal_name": "",
    "trade_name": "",
    "state": "Tamil Nadu (33)",
    "state_code": "33",
    "registration_type": "Regular",  # Regular, Composition, Exempt, Unregistered
    "default_place_of_supply": "Tamil Nadu (33)",
    "default_tax_mode": "exclusive",  # exclusive, inclusive
    "default_tax_rate": 18.00,
    "supported_tax_rates": ["0.00", "5.00", "12.00", "18.00", "28.00"],
    "enable_cess": False,
    "default_cess_rate": 0.00,
    "tax_rounding_rule": "nearest_rupee",  # nearest_rupee, two_decimals, none
    "decimal_precision_currency": 2,
    "decimal_precision_qty": 3,
    "hsn_enforcement_mode": "optional",  # optional, 4_digit, 6_digit, 8_digit
    "show_hsn_summary": True,
    "enable_rcm": False,
    "transaction_defaults": {
        "sales_invoice": {"tax_mode": "exclusive", "default_rate": 18.0},
        "sales_return": {"tax_mode": "exclusive", "default_rate": 18.0},
        "purchase_invoice": {"tax_mode": "exclusive", "default_rate": 18.0},
        "purchase_return": {"tax_mode": "exclusive", "default_rate": 18.0},
    },
    "effective_from": "2026-11-16",
}


class GstTaxConfigService:
    """Manages company and branch GST/Tax settings with strict auditability and isolation."""

    def __init__(self, fast_storage_path: Optional[Path] = None):
        self._fast_storage_path = (
            fast_storage_path
            if fast_storage_path is not None
            else Path("data/fast_gst_tax_configurations.json")
        )

    # =========================================================================
    # Validation & Utilities
    # =========================================================================

    def validate_gstin(self, gstin: Optional[str]) -> Tuple[bool, str, Dict[str, str]]:
        """
        Validates 15-character GSTIN format and extracts state code and PAN.
        Returns (is_valid, error_or_success_message, components_dict).
        """
        if not gstin or not str(gstin).strip():
            return False, "GSTIN cannot be empty.", {}

        clean_gstin = str(gstin).strip().upper()
        if len(clean_gstin) != 15:
            return False, f"GSTIN must be exactly 15 characters (provided: {len(clean_gstin)}).", {}

        if not GSTIN_REGEX.match(clean_gstin):
            return (
                False,
                "Invalid GSTIN structure. Expected format: 2-digit state code + 10-char PAN + 1 entity num + 'Z' + 1 checksum char (e.g. 33AAAPL9876C1Z2).",
                {},
            )

        state_code = clean_gstin[:2]
        pan = clean_gstin[2:12]
        entity_num = clean_gstin[12]
        checksum = clean_gstin[14]
        state_name = INDIAN_STATE_CODES.get(state_code, "Unknown Territory")

        return True, "Valid GSTIN format.", {
            "gstin": clean_gstin,
            "state_code": state_code,
            "state_name": state_name,
            "pan": pan,
            "entity_number": entity_num,
            "checksum": checksum,
        }

    def validate_hsn(self, hsn: Optional[str], mode: str = "optional") -> Tuple[bool, str]:
        """Validates HSN/SAC code format based on enforcement rule."""
        if not hsn or not str(hsn).strip():
            if mode == "optional":
                return True, "Optional HSN"
            return False, f"HSN/SAC code is mandatory under '{mode}' enforcement."

        clean = str(hsn).strip()
        if not clean.isdigit():
            return False, "HSN/SAC code must contain only numeric digits."

        length = len(clean)
        if mode == "4_digit" and length < 4:
            return False, f"HSN code must be at least 4 digits (provided: {length})."
        elif mode == "6_digit" and length < 6:
            return False, f"HSN code must be at least 6 digits (provided: {length})."
        elif mode == "8_digit" and length != 8:
            return False, f"HSN code must be exactly 8 digits (provided: {length})."
        elif length < 2 or length > 8:
            return False, "HSN/SAC code must be between 2 and 8 digits."

        return True, "Valid HSN/SAC code."

    def validate_config(self, data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validates complete GST/Tax configuration payload.
        Returns (is_valid, errors_list, cleaned_dict).
        """
        errors: List[str] = []
        cleaned: Dict[str, Any] = copy.deepcopy(DEFAULT_GST_CONFIG)

        # 1. GST Registration
        cleaned["is_gst_enabled"] = bool(data.get("is_gst_enabled", True))
        raw_gstin = str(data.get("gstin") or "").strip().upper()
        if cleaned["is_gst_enabled"] and raw_gstin:
            is_v, msg, comps = self.validate_gstin(raw_gstin)
            if not is_v:
                errors.append(msg)
            else:
                cleaned["gstin"] = raw_gstin
                if not data.get("state_code"):
                    cleaned["state_code"] = comps["state_code"]
        else:
            cleaned["gstin"] = raw_gstin

        cleaned["legal_name"] = str(data.get("legal_name") or "").strip()[:255]
        cleaned["trade_name"] = str(data.get("trade_name") or "").strip()[:255]
        cleaned["state"] = str(data.get("state") or DEFAULT_GST_CONFIG["state"]).strip()[:100]
        cleaned["state_code"] = str(data.get("state_code") or DEFAULT_GST_CONFIG["state_code"]).strip()[:10]

        reg_type = str(data.get("registration_type") or "Regular").strip()
        if reg_type not in ("Regular", "Composition", "Exempt", "Unregistered"):
            errors.append("Registration type must be 'Regular', 'Composition', 'Exempt', or 'Unregistered'.")
            reg_type = "Regular"
        cleaned["registration_type"] = reg_type

        cleaned["default_place_of_supply"] = str(
            data.get("default_place_of_supply") or cleaned["state"]
        ).strip()[:100]

        # 2. Tax Rates
        try:
            d_rate = float(data.get("default_tax_rate") if data.get("default_tax_rate") is not None else 18.0)
            if d_rate < 0.0 or d_rate > 100.0:
                errors.append("Default tax rate must be between 0% and 100%.")
            cleaned["default_tax_rate"] = d_rate
        except (ValueError, TypeError):
            errors.append("Default tax rate must be a valid number.")
            cleaned["default_tax_rate"] = 18.0

        raw_supported = data.get("supported_tax_rates")
        if isinstance(raw_supported, list):
            valid_rates = []
            for r in raw_supported:
                try:
                    f = float(r)
                    if 0.0 <= f <= 100.0:
                        valid_rates.append(f"{f:.2f}")
                except (ValueError, TypeError):
                    pass
            if valid_rates:
                cleaned["supported_tax_rates"] = sorted(list(set(valid_rates)), key=lambda x: float(x))
        elif isinstance(raw_supported, str):
            try:
                parsed = json.loads(raw_supported)
                if isinstance(parsed, list):
                    cleaned["supported_tax_rates"] = [f"{float(r):.2f}" for r in parsed]
            except Exception:
                pass

        cleaned["enable_cess"] = bool(data.get("enable_cess", False))
        try:
            cess_rate = float(data.get("default_cess_rate") if data.get("default_cess_rate") is not None else 0.0)
            cleaned["default_cess_rate"] = max(0.0, cess_rate)
        except (ValueError, TypeError):
            cleaned["default_cess_rate"] = 0.0

        # 3. Tax Calculation & Rounding
        tax_mode = str(data.get("default_tax_mode") or "exclusive").strip().lower()
        if tax_mode not in ("exclusive", "inclusive"):
            errors.append("Default pricing mode must be 'exclusive' or 'inclusive'.")
            tax_mode = "exclusive"
        cleaned["default_tax_mode"] = tax_mode

        round_rule = str(data.get("tax_rounding_rule") or "nearest_rupee").strip().lower()
        if round_rule not in ("nearest_rupee", "two_decimals", "none"):
            errors.append("Tax rounding rule must be 'nearest_rupee', 'two_decimals', or 'none'.")
            round_rule = "nearest_rupee"
        cleaned["tax_rounding_rule"] = round_rule

        try:
            prec_curr = int(data.get("decimal_precision_currency") or 2)
            cleaned["decimal_precision_currency"] = min(max(2, prec_curr), 4)
        except (ValueError, TypeError):
            cleaned["decimal_precision_currency"] = 2

        try:
            prec_qty = int(data.get("decimal_precision_qty") or 3)
            cleaned["decimal_precision_qty"] = min(max(0, prec_qty), 4)
        except (ValueError, TypeError):
            cleaned["decimal_precision_qty"] = 3

        # 4. HSN & Compliance
        hsn_mode = str(data.get("hsn_enforcement_mode") or "optional").strip().lower()
        if hsn_mode not in ("optional", "4_digit", "6_digit", "8_digit"):
            errors.append("HSN enforcement mode must be 'optional', '4_digit', '6_digit', or '8_digit'.")
            hsn_mode = "optional"
        cleaned["hsn_enforcement_mode"] = hsn_mode
        cleaned["show_hsn_summary"] = bool(data.get("show_hsn_summary", True))
        cleaned["enable_rcm"] = bool(data.get("enable_rcm", False))

        # 5. Transaction Defaults
        tx_defs = data.get("transaction_defaults")
        if isinstance(tx_defs, dict):
            cleaned["transaction_defaults"] = tx_defs
        elif isinstance(tx_defs, str):
            try:
                cleaned["transaction_defaults"] = json.loads(tx_defs)
            except Exception:
                pass

        cleaned["effective_from"] = str(data.get("effective_from") or datetime.now().strftime("%Y-%m-%d")).strip()

        is_valid = len(errors) == 0
        return is_valid, errors, cleaned

    # =========================================================================
    # Traditional Billing Storage (SQLite / PostgreSQL)
    # =========================================================================

    def get_traditional_config(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieves GST/Tax configuration from Traditional DB, falling back to company master data."""
        fallback = copy.deepcopy(DEFAULT_GST_CONFIG)
        fallback["company_id"] = company_id
        fallback["branch_id"] = branch_id

        try:
            with traditional_db_manager.read_session_scope() as session:
                # 1. Load actual company master to pre-populate registered name, state, and GSTIN
                comp = session.get(Company, company_id)
                if comp:
                    if comp.gstin:
                        fallback["gstin"] = comp.gstin
                    if comp.name:
                        fallback["legal_name"] = comp.name
                        fallback["trade_name"] = comp.name
                    if comp.state:
                        fallback["state"] = comp.state
                        fallback["default_place_of_supply"] = comp.state
                        # Extract 2-digit code if present in format 'State (XX)'
                        m = re.search(r"\((\d{2})\)", comp.state)
                        if m:
                            fallback["state_code"] = m.group(1)

                # 2. Query saved gst_tax_configurations table
                cfg_row = None
                if branch_id:
                    cfg_row = session.scalar(
                        select(GstTaxConfiguration).where(
                            and_(
                                GstTaxConfiguration.company_id == company_id,
                                GstTaxConfiguration.branch_id == branch_id,
                            )
                        )
                    )

                if not cfg_row:
                    cfg_row = session.scalar(
                        select(GstTaxConfiguration).where(
                            and_(
                                GstTaxConfiguration.company_id == company_id,
                                GstTaxConfiguration.branch_id.is_(None),
                            )
                        )
                    )

                if not cfg_row and branch_id is None:
                    cfg_row = session.scalar(
                        select(GstTaxConfiguration).where(
                            GstTaxConfiguration.company_id == company_id
                        )
                    )

                if cfg_row:
                    res = copy.deepcopy(fallback)
                    res["id"] = cfg_row.id
                    res["is_gst_enabled"] = cfg_row.is_gst_enabled
                    res["gstin"] = cfg_row.gstin or fallback["gstin"]
                    res["legal_name"] = cfg_row.legal_name or fallback["legal_name"]
                    res["trade_name"] = cfg_row.trade_name or fallback["trade_name"]
                    res["state"] = cfg_row.state or fallback["state"]
                    res["state_code"] = cfg_row.state_code or fallback["state_code"]
                    res["registration_type"] = cfg_row.registration_type
                    res["default_place_of_supply"] = cfg_row.default_place_of_supply or fallback["default_place_of_supply"]
                    res["default_tax_mode"] = cfg_row.default_tax_mode
                    res["default_tax_rate"] = float(cfg_row.default_tax_rate)
                    try:
                        res["supported_tax_rates"] = json.loads(cfg_row.supported_tax_rates_json)
                    except Exception:
                        res["supported_tax_rates"] = fallback["supported_tax_rates"]
                    res["enable_cess"] = cfg_row.enable_cess
                    res["default_cess_rate"] = float(cfg_row.default_cess_rate)
                    res["tax_rounding_rule"] = cfg_row.tax_rounding_rule
                    res["decimal_precision_currency"] = cfg_row.decimal_precision_currency
                    res["decimal_precision_qty"] = cfg_row.decimal_precision_qty
                    res["hsn_enforcement_mode"] = cfg_row.hsn_enforcement_mode
                    res["show_hsn_summary"] = cfg_row.show_hsn_summary
                    res["enable_rcm"] = cfg_row.enable_rcm
                    try:
                        res["transaction_defaults"] = json.loads(cfg_row.transaction_defaults_json)
                    except Exception:
                        res["transaction_defaults"] = fallback["transaction_defaults"]
                    res["effective_from"] = cfg_row.effective_from or fallback["effective_from"]
                    res["company_id"] = cfg_row.company_id
                    res["branch_id"] = cfg_row.branch_id
                    return res

        except Exception as e:
            logger.error(f"Error reading traditional GST tax configuration: {e}")

        return fallback

    def save_traditional_config(
        self,
        company_id: str,
        config_data: Optional[Dict[str, Any]] = None,
        branch_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Saves GST/Tax configuration to Traditional database and synchronizes company master."""
        payload = config_data if config_data is not None else data
        is_valid, errors, cleaned = self.validate_config(payload or {})
        if not is_valid:
            raise ValueError(f"GST tax validation failed: {'; '.join(errors)}")

        with traditional_db_manager.session_scope() as session:
            # Query existing row
            query = select(GstTaxConfiguration).where(
                GstTaxConfiguration.company_id == company_id
            )
            if branch_id:
                query = query.where(GstTaxConfiguration.branch_id == branch_id)
            else:
                query = query.where(GstTaxConfiguration.branch_id.is_(None))

            cfg_row = session.scalar(query)
            if not cfg_row:
                cfg_row = GstTaxConfiguration(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    branch_id=branch_id,
                )
                session.add(cfg_row)

            # Assign fields
            cfg_row.is_gst_enabled = cleaned["is_gst_enabled"]
            cfg_row.gstin = cleaned["gstin"]
            cfg_row.legal_name = cleaned["legal_name"]
            cfg_row.trade_name = cleaned["trade_name"]
            cfg_row.state = cleaned["state"]
            cfg_row.state_code = cleaned["state_code"]
            cfg_row.registration_type = cleaned["registration_type"]
            cfg_row.default_place_of_supply = cleaned["default_place_of_supply"]
            cfg_row.default_tax_mode = cleaned["default_tax_mode"]
            cfg_row.default_tax_rate = cleaned["default_tax_rate"]
            cfg_row.supported_tax_rates_json = json.dumps(cleaned["supported_tax_rates"])
            cfg_row.enable_cess = cleaned["enable_cess"]
            cfg_row.default_cess_rate = cleaned["default_cess_rate"]
            cfg_row.tax_rounding_rule = cleaned["tax_rounding_rule"]
            cfg_row.decimal_precision_currency = cleaned["decimal_precision_currency"]
            cfg_row.decimal_precision_qty = cleaned["decimal_precision_qty"]
            cfg_row.hsn_enforcement_mode = cleaned["hsn_enforcement_mode"]
            cfg_row.show_hsn_summary = cleaned["show_hsn_summary"]
            cfg_row.enable_rcm = cleaned["enable_rcm"]
            cfg_row.transaction_defaults_json = json.dumps(cleaned["transaction_defaults"])
            cfg_row.effective_from = cleaned["effective_from"]
            cfg_row.updated_at = utc_now()

            # Synchronize Company master fields if updated
            comp = session.get(Company, company_id)
            if comp:
                if cleaned.get("gstin"):
                    comp.gstin = cleaned["gstin"]
                if cleaned.get("state"):
                    comp.state = cleaned["state"]

        return self.get_traditional_config(company_id, branch_id=branch_id)

    def reset_traditional_config(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resets GST/Tax configuration to factory defaults in Traditional DB."""
        with traditional_db_manager.session_scope() as session:
            query = select(GstTaxConfiguration).where(
                GstTaxConfiguration.company_id == company_id
            )
            if branch_id:
                query = query.where(GstTaxConfiguration.branch_id == branch_id)
            else:
                query = query.where(GstTaxConfiguration.branch_id.is_(None))

            cfg_row = session.scalar(query)
            if cfg_row:
                session.delete(cfg_row)

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
            logger.error(f"Error reading fast GST tax storage: {e}")
            return {}

    def _write_fast_storage(self, data: Dict[str, Any]) -> None:
        try:
            self._fast_storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._fast_storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error writing fast GST tax storage: {e}")

    def get_fast_config(self, company_id: str = "default") -> Dict[str, Any]:
        """Retrieves GST/Tax configuration for Fast Billing from JSON storage."""
        store = self._read_fast_storage()
        key = str(company_id)
        if key in store:
            cfg = copy.deepcopy(store[key])
            cfg["company_id"] = company_id
            return cfg

        fallback = copy.deepcopy(DEFAULT_GST_CONFIG)
        fallback["company_id"] = company_id
        return fallback

    def save_fast_config(
        self,
        company_id: Any = "default",
        config_data: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Saves GST/Tax configuration for Fast Billing without touching SQLite DB."""
        if isinstance(company_id, dict):
            payload = company_id
            cid = str(payload.get("company_id") or "default")
        else:
            payload = config_data if config_data is not None else data
            cid = str(company_id or "default")

        is_valid, errors, cleaned = self.validate_config(payload or {})
        if not is_valid:
            raise ValueError(f"Fast Billing GST validation failed: {'; '.join(errors)}")

        store = self._read_fast_storage()
        cleaned["company_id"] = cid
        store[cid] = cleaned
        self._write_fast_storage(store)
        return self.get_fast_config(cid)

    def reset_fast_config(self, company_id: str = "default") -> Dict[str, Any]:
        """Resets Fast Billing GST configuration to factory defaults."""
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
        """Returns GST configuration based on active billing mode."""
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
        """Saves GST configuration based on active billing mode."""
        if billing_mode == "fast_billing":
            return self.save_fast_config(company_id, data=data)
        return self.save_traditional_config(company_id, data=data, branch_id=branch_id)

    def reset_config(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
        billing_mode: str = "traditional",
    ) -> Dict[str, Any]:
        """Resets GST configuration based on active billing mode."""
        if billing_mode == "fast_billing":
            return self.reset_fast_config(company_id)
        return self.reset_traditional_config(company_id, branch_id=branch_id)

    # =========================================================================
    # Calculation Sandbox & Preview
    # =========================================================================

    def calculate_sample_tax(
        self,
        cfg: Dict[str, Any],
        items: List[Dict[str, Any]],
        customer_state: Optional[str] = None,
        sale_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Runs tax calculation sandbox using the configured settings without mutating any state.
        Demonstrates intra-state vs inter-state splits, inclusive vs exclusive pricing, and rounding rules.
        """
        company_state = cfg.get("state") or "Tamil Nadu (33)"
        is_tax_inc = cfg.get("default_tax_mode") == "inclusive"
        auto_round = cfg.get("tax_rounding_rule") == "nearest_rupee"

        # If items is a single dictionary, wrap into list
        raw_list = [items] if isinstance(items, dict) else list(items)

        # Apply default tax inclusion mode to items if not specified
        adapted_items = []
        for it in raw_list:
            item_copy = dict(it)
            if "is_tax_inclusive" not in item_copy:
                item_copy["is_tax_inclusive"] = is_tax_inc
            if customer_state is None and "customer_state" in item_copy:
                customer_state = item_copy["customer_state"]
            adapted_items.append(item_copy)

        return tax_service.calculate_voucher_totals(
            items=adapted_items,
            company_state=company_state,
            customer_state=customer_state,
            sale_type=sale_type,
            auto_round=auto_round,
        )


gst_tax_config_service = GstTaxConfigService()
