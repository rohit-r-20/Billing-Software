"""
Voucher Numbering Configuration & Generation Service for Anti-Matrix Billing V2.
Manages sequential numbering rules, custom prefixes, starting sequences, padding,
financial year inclusion, branch code inclusion, and series reset rules for:
1. sales_invoice
2. sales_return
3. purchase_invoice
4. purchase_return

Enforces strict company & branch isolation, concurrency-safe atomic sequence allocation,
historical voucher preservation, and separate isolated storage for Fast Billing.
"""

import copy
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy import select, and_, func

from core.configuration import config
from core.logging_config import logger
from db.traditional_database import traditional_db_manager
from db.traditional_models import (
    Company,
    Branch,
    VoucherSequence,
    SaleInvoice,
    VoucherNumberingConfiguration,
    utc_now,
)


VOUCHER_TYPES = ("sales_invoice", "sales_return", "purchase_invoice", "purchase_return")

DEFAULT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "sales_invoice": {
        "voucher_type": "sales_invoice",
        "is_custom_enabled": False,
        "prefix": "INV-",
        "start_number": 1,
        "padding": 4,
        "suffix": "",
        "include_financial_year": False,
        "fy_format": "YYYY-YY",
        "fy_separator": "/",
        "include_branch_code": False,
        "branch_position": "prefix",
        "series": "Main",
        "reset_frequency": "yearly",
    },
    "sales_return": {
        "voucher_type": "sales_return",
        "is_custom_enabled": False,
        "prefix": "SR-",
        "start_number": 1,
        "padding": 6,
        "suffix": "",
        "include_financial_year": False,
        "fy_format": "YYYY-YY",
        "fy_separator": "/",
        "include_branch_code": False,
        "branch_position": "prefix",
        "series": "Main",
        "reset_frequency": "yearly",
    },
    "purchase_invoice": {
        "voucher_type": "purchase_invoice",
        "is_custom_enabled": False,
        "prefix": "PUR-",
        "start_number": 1,
        "padding": 6,
        "suffix": "",
        "include_financial_year": False,
        "fy_format": "YYYY-YY",
        "fy_separator": "/",
        "include_branch_code": False,
        "branch_position": "prefix",
        "series": "Main",
        "reset_frequency": "yearly",
    },
    "purchase_return": {
        "voucher_type": "purchase_return",
        "is_custom_enabled": False,
        "prefix": "PR-",
        "start_number": 1,
        "padding": 6,
        "suffix": "",
        "include_financial_year": False,
        "fy_format": "YYYY-YY",
        "fy_separator": "/",
        "include_branch_code": False,
        "branch_position": "prefix",
        "series": "Main",
        "reset_frequency": "yearly",
    },
}

# Fast billing storage path
FAST_NUMBERING_CONFIG_PATH = config.DATA_DIR / "fast_voucher_numbering_configurations.json"

# Whitelist regex for prefix/suffix: letters, digits, hyphen, underscore, slash, dot
SAFE_AFFIX_PATTERN = re.compile(r"^[A-Za-z0-9\-_/. ]*$")


class VoucherNumberingService:
    """Service handling configuration, previewing, and atomic generation of voucher numbers."""

    def __init__(self, fast_storage_path: Optional[Path] = None):
        self.fast_storage_path = fast_storage_path or FAST_NUMBERING_CONFIG_PATH

    # =========================================================================
    # Validation & Formatting
    # =========================================================================

    def validate_config(self, data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validates configuration payload against business rules and safety constraints.
        Returns (is_valid, error_list, cleaned_config_dict).
        """
        errors: List[str] = []
        cleaned: Dict[str, Any] = {}

        vch_type = str(data.get("voucher_type") or "").strip().lower()
        if vch_type not in VOUCHER_TYPES:
            errors.append(f"Invalid voucher_type: '{vch_type}'. Must be one of: {', '.join(VOUCHER_TYPES)}.")
        cleaned["voucher_type"] = vch_type

        cleaned["is_custom_enabled"] = bool(data.get("is_custom_enabled", False))

        # Prefix validation
        raw_prefix = str(data.get("prefix") or "").strip()
        if not SAFE_AFFIX_PATTERN.match(raw_prefix):
            errors.append(
                "Prefix contains forbidden characters. Only alphanumeric, hyphen (-), "
                "underscore (_), slash (/), and dots are allowed."
            )
        cleaned["prefix"] = raw_prefix[:50]

        # Suffix validation
        raw_suffix = str(data.get("suffix") or "").strip()
        if not SAFE_AFFIX_PATTERN.match(raw_suffix):
            errors.append(
                "Suffix contains forbidden characters. Only alphanumeric, hyphen (-), "
                "underscore (_), slash (/), and dots are allowed."
            )
        cleaned["suffix"] = raw_suffix[:50]

        # Starting sequence number
        try:
            raw_start = data.get("start_number")
            if raw_start is None or raw_start == "":
                start_num = 1
            else:
                start_num = int(raw_start)
            if start_num < 1:
                errors.append("Starting sequence number must be greater than or equal to 1.")
            elif start_num > 100_000_000:
                errors.append("Starting sequence number cannot exceed 100,000,000.")
            cleaned["start_number"] = max(1, start_num)
        except (ValueError, TypeError):
            errors.append("Starting sequence number must be a valid positive integer.")
            cleaned["start_number"] = 1

        # Padding / Digits
        try:
            padding = int(data.get("padding") or 4)
            if padding < 3 or padding > 8:
                errors.append("Padding must be between 3 and 8 digits.")
            cleaned["padding"] = min(max(3, padding), 8)
        except (ValueError, TypeError):
            errors.append("Padding must be an integer between 3 and 8.")
            cleaned["padding"] = 4

        # Financial year inclusion & format
        cleaned["include_financial_year"] = bool(data.get("include_financial_year", False))
        raw_fy_fmt = str(data.get("fy_format") or "YYYY-YY").strip()
        if raw_fy_fmt not in ("YYYY-YY", "YY-YY", "YYYY", "YYYY-YYYY"):
            errors.append("Financial year format must be one of: 'YYYY-YY', 'YY-YY', 'YYYY', 'YYYY-YYYY'.")
            raw_fy_fmt = "YYYY-YY"
        cleaned["fy_format"] = raw_fy_fmt

        raw_fy_sep = str(data.get("fy_separator") if data.get("fy_separator") is not None else "/").strip()
        if raw_fy_sep not in ("/", "-", "_", ""):
            errors.append("Financial year separator must be one of: '/', '-', '_', or empty.")
            raw_fy_sep = "/"
        cleaned["fy_separator"] = raw_fy_sep

        # Branch code inclusion & position
        cleaned["include_branch_code"] = bool(data.get("include_branch_code", False))
        raw_br_pos = str(data.get("branch_position") or "prefix").strip().lower()
        if raw_br_pos not in ("prefix", "after_prefix", "after_fy", "suffix"):
            errors.append("Branch position must be one of: 'prefix', 'after_prefix', 'after_fy', 'suffix'.")
            raw_br_pos = "prefix"
        cleaned["branch_position"] = raw_br_pos

        # Reset frequency & series
        raw_reset = str(data.get("reset_frequency") or "yearly").strip().lower()
        if raw_reset not in ("yearly", "never"):
            errors.append("Reset frequency must be 'yearly' or 'never'.")
            raw_reset = "yearly"
        cleaned["reset_frequency"] = raw_reset

        cleaned["series"] = str(data.get("series") or "Main").strip() or "Main"

        # Coherence check: if custom is enabled, there should be an identifier (prefix, FY, or branch)
        if cleaned["is_custom_enabled"]:
            if not cleaned["prefix"] and not cleaned["include_financial_year"] and not cleaned["include_branch_code"]:
                errors.append(
                    "When custom numbering is enabled, specify at least a prefix, financial year, "
                    "or branch code to avoid bare unidentifiable numbers."
                )

        return len(errors) == 0, errors, cleaned

    def format_financial_year(self, fy_str: str, fy_format: str = "YYYY-YY") -> str:
        """
        Formats a financial year string (e.g. '2026-2027') to requested representation:
        - 'YYYY-YY' -> '2026-27'
        - 'YY-YY'   -> '26-27'
        - 'YYYY'    -> '2026'
        - 'YYYY-YYYY' -> '2026-2027'
        """
        if not fy_str:
            return ""
        parts = fy_str.split("-")
        if len(parts) == 2:
            s_yr, e_yr = parts[0].strip(), parts[1].strip()
            if fy_format == "YYYY-YY":
                return f"{s_yr}-{e_yr[-2:]}"
            elif fy_format == "YY-YY":
                return f"{s_yr[-2:]}-{e_yr[-2:]}"
            elif fy_format == "YYYY":
                return s_yr
            elif fy_format == "YYYY-YYYY":
                return f"{s_yr}-{e_yr}"
        return fy_str

    def format_voucher_number(
        self,
        cfg: Dict[str, Any],
        sequence_number: int,
        financial_year: str = "2026-2027",
        branch_code: str = "BR01",
    ) -> str:
        """
        Generates a formatted voucher number based on configuration, sequence, FY, and branch.
        Handles default and custom modes with exact matching to standard ERP conventions:
        Examples:
        - Default sales invoice: '0001' or 'INV-0001'
        - SI/2026-27/0001
        - BR01/INV/0001
        - PUR-2026-27-0001
        """
        padding = int(cfg.get("padding") or 4)
        padded_seq = str(sequence_number).zfill(padding)

        if not cfg.get("is_custom_enabled", False):
            # System standard default formatting
            prefix = cfg.get("prefix") or ""
            return f"{prefix}{padded_seq}"

        prefix = (cfg.get("prefix") or "").strip()
        suffix = (cfg.get("suffix") or "").strip()

        # Format Financial Year
        include_fy = bool(cfg.get("include_financial_year", False))
        fy_fmt = cfg.get("fy_format", "YYYY-YY")
        fy_sep = cfg.get("fy_separator", "/")
        sep = fy_sep if fy_sep else "/"

        formatted_fy = self.format_financial_year(financial_year, fy_fmt) if include_fy else ""

        # Branch Code
        include_branch = bool(cfg.get("include_branch_code", False))
        branch_pos = cfg.get("branch_position", "prefix")
        b_code = (branch_code or "").strip() if include_branch else ""

        # Check if user specified exact custom string with hyphen, slash, or underscore attached
        # e.g. prefix = 'INV-', 'SI/', or 'TX_' with no FY and no branch -> 'INV-0001'
        if prefix and not formatted_fy and not b_code and (prefix.endswith("-") or prefix.endswith("/") or prefix.endswith("_")):
            res = f"{prefix}{padded_seq}"
        else:
            parts: List[str] = []
            if b_code and branch_pos == "prefix":
                parts.append(b_code)

            if prefix:
                clean_p = prefix.rstrip("/-_")
                if clean_p:
                    parts.append(clean_p)

            if b_code and branch_pos == "after_prefix":
                parts.append(b_code)

            if formatted_fy:
                parts.append(formatted_fy)

            if b_code and branch_pos == "after_fy":
                parts.append(b_code)

            parts.append(padded_seq)
            res = sep.join(parts)

        # Suffix handling
        if suffix:
            if suffix.startswith("/") or suffix.startswith("-") or suffix.startswith("_"):
                res += suffix
            else:
                res += f"{sep}{suffix}"

        if b_code and branch_pos == "suffix":
            res += f"{sep}{b_code}"

        return res

    # =========================================================================
    # Traditional Billing Configuration (SQLite / PostgreSQL)
    # =========================================================================

    def get_traditional_config(
        self,
        company_id: str,
        voucher_type: str,
        branch_id: Optional[str] = None,
        series: str = "Main",
    ) -> Dict[str, Any]:
        """Retrieves voucher numbering configuration from Traditional database."""
        vch_type = str(voucher_type or "").strip().lower()
        if vch_type not in VOUCHER_TYPES:
            vch_type = "sales_invoice"

        clean_series = str(series or "Main").strip() or "Main"
        default_cfg = copy.deepcopy(DEFAULT_CONFIGS[vch_type])
        default_cfg["company_id"] = company_id
        default_cfg["branch_id"] = branch_id
        default_cfg["series"] = clean_series

        try:
            with traditional_db_manager.read_session_scope() as session:
                # 1. Try branch-specific config if branch_id provided
                cfg_row = None
                if branch_id:
                    cfg_row = session.scalar(
                        select(VoucherNumberingConfiguration).where(
                            and_(
                                VoucherNumberingConfiguration.company_id == company_id,
                                VoucherNumberingConfiguration.branch_id == branch_id,
                                VoucherNumberingConfiguration.voucher_type == vch_type,
                                VoucherNumberingConfiguration.series == clean_series,
                            )
                        )
                    )

                # 2. Fall back to company-level default (branch_id is null) or any config if branch_id is None
                if not cfg_row:
                    if branch_id is None:
                        cfg_row = session.scalar(
                            select(VoucherNumberingConfiguration).where(
                                and_(
                                    VoucherNumberingConfiguration.company_id == company_id,
                                    VoucherNumberingConfiguration.voucher_type == vch_type,
                                    VoucherNumberingConfiguration.series == clean_series,
                                )
                            )
                        )
                    else:
                        cfg_row = session.scalar(
                            select(VoucherNumberingConfiguration).where(
                                and_(
                                    VoucherNumberingConfiguration.company_id == company_id,
                                    VoucherNumberingConfiguration.branch_id.is_(None),
                                    VoucherNumberingConfiguration.voucher_type == vch_type,
                                    VoucherNumberingConfiguration.series == clean_series,
                                )
                            )
                        )

                if cfg_row:
                    return {
                        "voucher_type": cfg_row.voucher_type,
                        "is_custom_enabled": bool(cfg_row.is_custom_enabled),
                        "prefix": cfg_row.prefix,
                        "start_number": int(cfg_row.start_number),
                        "padding": int(cfg_row.padding),
                        "suffix": cfg_row.suffix,
                        "include_financial_year": bool(cfg_row.include_financial_year),
                        "fy_format": cfg_row.fy_format,
                        "fy_separator": cfg_row.fy_separator,
                        "include_branch_code": bool(cfg_row.include_branch_code),
                        "branch_position": cfg_row.branch_position,
                        "reset_frequency": cfg_row.reset_frequency,
                        "series": cfg_row.series,
                        "company_id": cfg_row.company_id,
                        "branch_id": cfg_row.branch_id,
                    }
        except Exception as e:
            logger.warning(f"Could not load Traditional voucher numbering config: {e}")

        return default_cfg

    def save_traditional_config(
        self,
        company_id: str,
        voucher_type: str,
        config_data: Optional[Dict[str, Any]] = None,
        branch_id: Optional[str] = None,
        series: str = "Main",
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Saves voucher numbering configuration to Traditional database inside transaction."""
        payload = config_data if config_data is not None else data
        merged = dict(payload or {})
        if voucher_type:
            merged.setdefault("voucher_type", voucher_type)
        if series:
            merged.setdefault("series", series)
        is_valid, errors, cleaned = self.validate_config(merged)
        if not is_valid:
            raise ValueError(f"Voucher numbering validation failed: {'; '.join(errors)}")

        vch_type = cleaned["voucher_type"]
        clean_series = cleaned["series"]

        with traditional_db_manager.session_scope() as session:
            # Query existing row
            query = select(VoucherNumberingConfiguration).where(
                and_(
                    VoucherNumberingConfiguration.company_id == company_id,
                    VoucherNumberingConfiguration.voucher_type == vch_type,
                    VoucherNumberingConfiguration.series == clean_series,
                )
            )
            if branch_id:
                query = query.where(VoucherNumberingConfiguration.branch_id == branch_id)
            else:
                query = query.where(VoucherNumberingConfiguration.branch_id.is_(None))

            row = session.scalar(query)
            now = utc_now()

            if not row:
                row = VoucherNumberingConfiguration(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    branch_id=branch_id,
                    voucher_type=vch_type,
                    series=clean_series,
                    is_custom_enabled=cleaned["is_custom_enabled"],
                    prefix=cleaned["prefix"],
                    start_number=cleaned["start_number"],
                    padding=cleaned["padding"],
                    suffix=cleaned["suffix"],
                    include_financial_year=cleaned["include_financial_year"],
                    fy_format=cleaned["fy_format"],
                    fy_separator=cleaned["fy_separator"],
                    include_branch_code=cleaned["include_branch_code"],
                    branch_position=cleaned["branch_position"],
                    reset_frequency=cleaned["reset_frequency"],
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.is_custom_enabled = cleaned["is_custom_enabled"]
                row.prefix = cleaned["prefix"]
                row.start_number = cleaned["start_number"]
                row.padding = cleaned["padding"]
                row.suffix = cleaned["suffix"]
                row.include_financial_year = cleaned["include_financial_year"]
                row.fy_format = cleaned["fy_format"]
                row.fy_separator = cleaned["fy_separator"]
                row.include_branch_code = cleaned["include_branch_code"]
                row.branch_position = cleaned["branch_position"]
                row.reset_frequency = cleaned["reset_frequency"]
                row.updated_at = now

        logger.info(
            f"Voucher numbering configuration saved for {vch_type} "
            f"(Company: {company_id}, Series: {clean_series}, Branch: {branch_id})"
        )
        return self.get_traditional_config(company_id, vch_type, branch_id=branch_id, series=clean_series)

    def reset_traditional_config(
        self,
        company_id: str,
        voucher_type: str,
        branch_id: Optional[str] = None,
        series: str = "Main",
    ) -> Dict[str, Any]:
        """Resets numbering configuration to default in Traditional database."""
        vch_type = str(voucher_type or "").strip().lower()
        if vch_type not in VOUCHER_TYPES:
            vch_type = "sales_invoice"
        clean_series = str(series or "Main").strip() or "Main"

        with traditional_db_manager.session_scope() as session:
            query = select(VoucherNumberingConfiguration).where(
                and_(
                    VoucherNumberingConfiguration.company_id == company_id,
                    VoucherNumberingConfiguration.voucher_type == vch_type,
                    VoucherNumberingConfiguration.series == clean_series,
                )
            )
            if branch_id:
                query = query.where(VoucherNumberingConfiguration.branch_id == branch_id)
            else:
                query = query.where(VoucherNumberingConfiguration.branch_id.is_(None))

            row = session.scalar(query)
            if row:
                session.delete(row)

        logger.info(f"Reset voucher numbering configuration to default for {vch_type} (Company: {company_id})")
        return self.get_traditional_config(company_id, vch_type, branch_id=branch_id, series=clean_series)

    # =========================================================================
    # Fast Billing Configuration (JSON Storage - SQLite Untouched)
    # =========================================================================

    def _read_fast_storage(self) -> Dict[str, Any]:
        """Reads isolated Fast Billing configurations."""
        if not self.fast_storage_path.exists():
            return {}
        try:
            return json.loads(self.fast_storage_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Error reading Fast Billing numbering configurations: {e}")
            return {}

    def _write_fast_storage(self, data: Dict[str, Any]) -> None:
        """Writes isolated Fast Billing configurations."""
        self.fast_storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.fast_storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_fast_config(
        self,
        company_id: str,
        voucher_type: str,
        series: str = "Main",
    ) -> Dict[str, Any]:
        """Retrieves voucher numbering configuration for Fast Billing."""
        vch_type = str(voucher_type or "").strip().lower()
        if vch_type not in VOUCHER_TYPES:
            vch_type = "sales_invoice"
        clean_series = str(series or "Main").strip() or "Main"

        store = self._read_fast_storage()
        key = f"{company_id}:{vch_type}:{clean_series}"
        if key in store:
            return store[key]

        fallback = copy.deepcopy(DEFAULT_CONFIGS[vch_type])
        fallback["company_id"] = company_id
        fallback["series"] = clean_series
        return fallback

    def save_fast_config(
        self,
        company_id: str,
        voucher_type: str,
        config_data: Optional[Dict[str, Any]] = None,
        series: str = "Main",
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Saves voucher numbering configuration for Fast Billing without touching SQLite DB."""
        payload = config_data if config_data is not None else data
        merged = dict(payload or {})
        if voucher_type:
            merged.setdefault("voucher_type", voucher_type)
        if series:
            merged.setdefault("series", series)
        is_valid, errors, cleaned = self.validate_config(merged)
        if not is_valid:
            raise ValueError(f"Fast Billing numbering validation failed: {'; '.join(errors)}")

        vch_type = cleaned["voucher_type"]
        clean_series = cleaned["series"]
        store = self._read_fast_storage()
        key = f"{company_id}:{vch_type}:{clean_series}"
        cleaned["company_id"] = company_id
        cleaned["updated_at"] = datetime.now(timezone.utc).isoformat()
        store[key] = cleaned
        self._write_fast_storage(store)
        return cleaned

    def reset_fast_config(
        self,
        company_id: str,
        voucher_type: str,
        series: str = "Main",
    ) -> Dict[str, Any]:
        """Resets voucher numbering configuration for Fast Billing to factory default."""
        vch_type = str(voucher_type or "").strip().lower()
        if vch_type not in VOUCHER_TYPES:
            vch_type = "sales_invoice"
        clean_series = str(series or "Main").strip() or "Main"

        store = self._read_fast_storage()
        key = f"{company_id}:{vch_type}:{clean_series}"
        if key in store:
            del store[key]
            self._write_fast_storage(store)
        return self.get_fast_config(company_id, vch_type, series=clean_series)

    # =========================================================================
    # Unified Mode-Aware Configuration Access
    # =========================================================================

    def get_config(
        self,
        company_id: str,
        voucher_type: str,
        branch_id: Optional[str] = None,
        series: str = "Main",
        billing_mode: str = "traditional",
    ) -> Dict[str, Any]:
        """Returns numbering configuration based on active billing mode."""
        if billing_mode == "fast_billing":
            return self.get_fast_config(company_id, voucher_type, series=series)
        return self.get_traditional_config(company_id, voucher_type, branch_id=branch_id, series=series)

    def save_config(
        self,
        company_id: str,
        voucher_type: str,
        config_data: Dict[str, Any],
        branch_id: Optional[str] = None,
        series: str = "Main",
        billing_mode: str = "traditional",
    ) -> Dict[str, Any]:
        """Saves numbering configuration based on active billing mode."""
        if billing_mode == "fast_billing":
            return self.save_fast_config(company_id, voucher_type, config_data, series=series)
        return self.save_traditional_config(company_id, voucher_type, config_data, branch_id=branch_id, series=series)

    def reset_config(
        self,
        company_id: str,
        voucher_type: str,
        branch_id: Optional[str] = None,
        series: str = "Main",
        billing_mode: str = "traditional",
    ) -> Dict[str, Any]:
        """Resets numbering configuration based on active billing mode."""
        if billing_mode == "fast_billing":
            return self.reset_fast_config(company_id, voucher_type, series=series)
        return self.reset_traditional_config(company_id, voucher_type, branch_id=branch_id, series=series)

    # =========================================================================
    # Live Preview & Status Inspection (No Sequence Consumption)
    # =========================================================================

    def preview_voucher_number(
        self,
        config_data: Dict[str, Any],
        company_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        financial_year: Optional[str] = None,
        series: str = "Main",
        billing_mode: str = "traditional",
    ) -> Dict[str, Any]:
        """
        Generates a non-mutating preview of the voucher number and projected sequence.
        Clearly marked as example; strictly guarantees NO sequence allocation or consumption.
        """
        is_valid, errors, cleaned = self.validate_config(config_data)
        vch_type = cleaned["voucher_type"] or "sales_invoice"

        # Determine effective financial year and branch code
        fy = financial_year or "2026-2027"
        br_code = "BR01"

        if company_id:
            try:
                with traditional_db_manager.read_session_scope() as session:
                    comp = session.scalar(select(Company).where(Company.id == company_id))
                    if comp and comp.fin_year:
                        fy = comp.fin_year
                    if branch_id:
                        br = session.scalar(select(Branch).where(Branch.id == branch_id))
                        if br and br.code:
                            br_code = br.code
            except Exception:
                pass

        # Estimate next sequence number from current configuration or existing sequence
        start_num = cleaned.get("start_number") or 1
        seq_sample = start_num

        sample_no = self.format_voucher_number(cleaned, seq_sample, fy, br_code)
        projected = [
            self.format_voucher_number(cleaned, seq_sample, fy, br_code),
            self.format_voucher_number(cleaned, seq_sample + 1, fy, br_code),
            self.format_voucher_number(cleaned, seq_sample + 2, fy, br_code),
        ]

        return {
            "preview_number": sample_no,
            "sample": sample_no,
            "sample_sequence": seq_sample,
            "projected_numbers": projected,
            "next_projections": projected,
            "financial_year": fy,
            "branch_code": br_code,
            "is_example": True,
            "is_valid": is_valid,
            "errors": errors,
            "notice": "Preview only. Sequence numbers are not reserved or consumed.",
        }

    def get_numbering_status(
        self,
        company_id: str,
        voucher_type: str,
        branch_id: Optional[str] = None,
        financial_year: Optional[str] = None,
        series: str = "Main",
        billing_mode: str = "traditional",
    ) -> Dict[str, Any]:
        """
        Reports live sequence allocation state and total committed transaction count
        without advancing the sequence counter.
        """
        cfg = self.get_config(company_id, voucher_type, branch_id=branch_id, series=series, billing_mode=billing_mode)
        clean_series = str(series or "Main").strip() or "Main"

        current_allocated = 0
        total_committed = 0
        fy = financial_year or "2026-2027"
        br_code = "BR01"

        if billing_mode == "traditional":
            try:
                with traditional_db_manager.read_session_scope() as session:
                    comp = session.scalar(select(Company).where(Company.id == company_id))
                    if comp and comp.fin_year:
                        fy = comp.fin_year
                    if branch_id:
                        br = session.scalar(select(Branch).where(Branch.id == branch_id))
                        if br and br.code:
                            br_code = br.code

                    # Sequence table row
                    seq_row = session.scalar(
                        select(VoucherSequence).where(
                            and_(
                                VoucherSequence.company_id == company_id,
                                VoucherSequence.financial_year == fy,
                                VoucherSequence.series == clean_series,
                            )
                        )
                    )
                    if seq_row:
                        current_allocated = seq_row.current_number

                    # Total committed count
                    if voucher_type == "sales_invoice":
                        total_committed = session.scalar(
                            select(func.count(SaleInvoice.id)).where(
                                and_(
                                    SaleInvoice.company_id == company_id,
                                    SaleInvoice.financial_year == fy,
                                    SaleInvoice.series == clean_series,
                                )
                            )
                        ) or 0
            except Exception as e:
                logger.debug(f"Could not read Traditional numbering status: {e}")
        else:
            # Fast billing status check
            try:
                from services.billing_service import billing_service
                with billing_service.db.get_connection() as conn:
                    cursor = conn.cursor()
                    if voucher_type == "sales_invoice":
                        cursor.execute(
                            "SELECT COUNT(id) FROM sales_vouchers WHERE company_id = ? AND series = ?;",
                            (company_id, clean_series),
                        )
                        r = cursor.fetchone()
                        total_committed = r[0] if r else 0
                    elif voucher_type == "sales_return":
                        cursor.execute(
                            "SELECT COUNT(id) FROM sales_returns WHERE company_id = ?;",
                            (company_id,),
                        )
                        r = cursor.fetchone()
                        total_committed = r[0] if r else 0
                    elif voucher_type == "purchase_invoice":
                        cursor.execute(
                            "SELECT COUNT(id) FROM purchase_vouchers WHERE company_id = ?;",
                            (company_id,),
                        )
                        r = cursor.fetchone()
                        total_committed = r[0] if r else 0
                    elif voucher_type == "purchase_return":
                        cursor.execute(
                            "SELECT COUNT(id) FROM purchase_returns WHERE company_id = ?;",
                            (company_id,),
                        )
                        r = cursor.fetchone()
                        total_committed = r[0] if r else 0
            except Exception as e:
                logger.debug(f"Could not read Fast Billing numbering status: {e}")

        next_seq = max(current_allocated + 1, int(cfg.get("start_number") or 1))
        next_formatted = self.format_voucher_number(cfg, next_seq, fy, br_code)

        return {
            "voucher_type": voucher_type,
            "company_id": company_id,
            "branch_id": branch_id,
            "branch_code": br_code,
            "financial_year": fy,
            "series": clean_series,
            "current_allocated_number": current_allocated,
            "total_committed_vouchers": total_committed,
            "next_sequence_number": next_seq,
            "next_formatted_voucher": next_formatted,
            "is_custom_enabled": cfg.get("is_custom_enabled", False),
        }


# Global singleton instance
voucher_numbering_service = VoucherNumberingService()
