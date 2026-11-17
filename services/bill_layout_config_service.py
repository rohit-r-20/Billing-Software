"""
Bill Layout Configuration Service for Anti-Matrix Billing V2.
Manages invoice design, company header, product table columns,
totals & tax breakdown, and footer options for 4 voucher types:
1. sales_invoice
2. sales_return
3. purchase_invoice
4. purchase_return

Maintains strict company/branch isolation in Traditional Billing (data/traditional_billing.db)
and independent isolated storage for Fast Billing (data/fast_bill_layout_configurations.json).
Integrates directly with Phase 1 Paper Configuration.
"""
import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import select

from core.configuration import config
from core.logging_config import logger
from db.traditional_database import traditional_db_manager
from db.traditional_models import Company, Branch, BillLayoutConfiguration, utc_now
from services.paper_config_service import paper_config_service


VOUCHER_TYPES = ("sales_invoice", "sales_return", "purchase_invoice", "purchase_return")

DEFAULT_COLUMNS: List[Dict[str, Any]] = [
    {"key": "sl_no", "label": "S.No", "visible": True, "order": 1, "width": "5%", "align": "center"},
    {"key": "name", "label": "Product Description", "visible": True, "order": 2, "width": "24%", "align": "left"},
    {"key": "sku", "label": "SKU", "visible": False, "order": 3, "width": "8%", "align": "left"},
    {"key": "hsn", "label": "HSN/SAC", "visible": True, "order": 4, "width": "8%", "align": "center"},
    {"key": "barcode", "label": "Barcode", "visible": False, "order": 5, "width": "10%", "align": "left"},
    {"key": "description", "label": "Description", "visible": False, "order": 6, "width": "12%", "align": "left"},
    {"key": "qty", "label": "Qty", "visible": True, "order": 7, "width": "6%", "align": "right"},
    {"key": "unit", "label": "Unit", "visible": True, "order": 8, "width": "6%", "align": "center"},
    {"key": "rate", "label": "Rate", "visible": True, "order": 9, "width": "8%", "align": "right"},
    {"key": "discount", "label": "Disc.", "visible": True, "order": 10, "width": "6%", "align": "right"},
    {"key": "taxable_amount", "label": "Taxable Amt", "visible": True, "order": 11, "width": "9%", "align": "right"},
    {"key": "cgst", "label": "CGST", "visible": True, "order": 12, "width": "6%", "align": "right"},
    {"key": "sgst", "label": "SGST", "visible": True, "order": 13, "width": "6%", "align": "right"},
    {"key": "igst", "label": "IGST", "visible": False, "order": 14, "width": "6%", "align": "right"},
    {"key": "gst_rate", "label": "GST %", "visible": True, "order": 15, "width": "5%", "align": "right"},
    {"key": "total", "label": "Line Total", "visible": True, "order": 16, "width": "10%", "align": "right"},
]


def amount_to_words_inr(amount: float) -> str:
    """
    Converts a currency amount to Indian English words.
    Example: 1250.50 -> 'One Thousand Two Hundred Fifty Rupees and Fifty Paise Only'
    """
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def convert_below_thousand(n: int) -> str:
        res = []
        if n >= 100:
            res.append(ones[n // 100] + " Hundred")
            n %= 100
        if n >= 20:
            t = tens[n // 10]
            if n % 10:
                t += "-" + ones[n % 10]
            res.append(t)
        elif n > 0:
            res.append(ones[n])
        return " ".join(res)

    try:
        amt = round(float(amount or 0.0), 2)
    except Exception:
        return ""

    if amt == 0:
        return "Zero Rupees Only"

    rupees = int(amt)
    paise = int(round((amt - rupees) * 100))

    crores = rupees // 10000000
    rupees %= 10000000
    lakhs = rupees // 100000
    rupees %= 100000
    thousands = rupees // 1000
    rupees %= 1000
    hundreds = rupees

    parts = []
    if crores > 0:
        parts.append(convert_below_thousand(crores) + " Crore")
    if lakhs > 0:
        parts.append(convert_below_thousand(lakhs) + " Lakh")
    if thousands > 0:
        parts.append(convert_below_thousand(thousands) + " Thousand")
    if hundreds > 0:
        parts.append(convert_below_thousand(hundreds))

    rupees_str = " ".join(parts).strip() + " Rupees" if parts else ""
    paise_str = (convert_below_thousand(paise) + " Paise") if paise > 0 else ""

    if rupees_str and paise_str:
        return f"{rupees_str} and {paise_str} Only"
    elif rupees_str:
        return f"{rupees_str} Only"
    elif paise_str:
        return f"{paise_str} Only"
    return "Zero Rupees Only"


VOUCHER_TITLES: Dict[str, str] = {
    "sales_invoice": "TAX INVOICE",
    "sales_return": "CREDIT NOTE / SALES RETURN",
    "purchase_invoice": "PURCHASE INVOICE",
    "purchase_return": "DEBIT NOTE / PURCHASE RETURN",
}

VOUCHER_PARTY_LABELS: Dict[str, str] = {
    "sales_invoice": "Customer (Billed To)",
    "sales_return": "Customer (Credit To)",
    "purchase_invoice": "Supplier (Vendor)",
    "purchase_return": "Supplier (Debit To)",
}


class BillLayoutConfigService:
    """Service handling bill layout configuration, database persistence, and printing layout compilation."""

    def __init__(self, db_manager=None):
        self._db_manager = db_manager or traditional_db_manager
        self._fast_config_file = config.DATA_DIR / "fast_bill_layout_configurations.json"

    # =========================================================================
    # Factory Defaults & Normalization
    # =========================================================================

    def get_default_config(self, voucher_type: str) -> Dict[str, Any]:
        """Returns standard factory default dictionary for the requested voucher type."""
        vt = (voucher_type or "sales_invoice").strip().lower()
        if vt not in VOUCHER_TYPES:
            raise ValueError(f"Invalid voucher type '{voucher_type}'. Supported: {', '.join(VOUCHER_TYPES)}")

        title = VOUCHER_TITLES.get(vt, "TAX INVOICE")
        party_label = VOUCHER_PARTY_LABELS.get(vt, "Customer")

        return {
            "voucher_type": vt,
            "layout_name": f"Default {title} Layout",
            "header_config": {
                "show_company_name": True,
                "show_logo": False,
                "logo_data": "",
                "logo_position": "left",  # left, center, right
                "logo_width_mm": 30.0,
                "logo_height_mm": 20.0,
                "show_address": True,
                "show_phone": True,
                "show_email": True,
                "show_website": True,
                "show_gstin": True,
                "show_state": True,
                "show_reg_details": True,
                "custom_header_text": "",
            },
            "invoice_info_config": {
                "title": title,
                "show_title": True,
                "show_voucher_no": True,
                "voucher_no_label": "Invoice No" if "sales" in vt else "Voucher No",
                "show_date": True,
                "date_label": "Date",
                "show_due_date": True,
                "due_date_label": "Due Date",
                "show_party_name": True,
                "party_name_label": party_label,
                "show_party_address": True,
                "show_party_gstin": True,
                "show_party_state": True,
                "show_party_contact": True,
                "show_place_of_supply": True,
                "show_reference_no": True,
                "reference_no_label": "Ref. / Order No",
            },
            "columns_config": copy.deepcopy(DEFAULT_COLUMNS),
            "totals_config": {
                "show_subtotal": True,
                "show_discount_total": True,
                "show_taxable_amount": True,
                "show_cgst_total": True,
                "show_sgst_total": True,
                "show_igst_total": True,
                "show_round_off": True,
                "show_grand_total": True,
                "show_amount_in_words": True,
                "show_payment_method": True,
                "show_amount_paid": True,
                "show_balance_due": True,
            },
            "footer_config": {
                "show_terms": True,
                "terms_and_conditions": (
                    "1. Goods once sold will not be taken back.\n"
                    "2. Interest @ 18% p.a. will be charged if payment is not made within the due date.\n"
                    "3. Subject to local jurisdiction."
                ),
                "show_bank_details": True,
                "bank_name": "",
                "account_number": "",
                "ifsc_code": "",
                "upi_id": "",
                "show_customer_notes": True,
                "customer_notes": "Thank you for your business!",
                "show_authorized_signatory": True,
                "signatory_title": "Authorized Signatory",
                "show_signature_box": True,
                "show_company_seal": True,
            },
            "style_config": {
                "font_family": "Helvetica",
                "base_font_size": 9,
                "primary_color": "#1e40af",
                "header_bg_color": "#1e40af",
                "header_text_color": "#ffffff",
                "border_color": "#cbd5e1",
                "compact_mode": False,
            },
            "is_default": True,
        }

    def validate_layout_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates and sanitizes all sections of a bill layout configuration.
        Ensures columns list contains all required keys and valid ordering.
        """
        vt = str(config_data.get("voucher_type") or "sales_invoice").strip().lower()
        if vt not in VOUCHER_TYPES:
            raise ValueError(f"Invalid voucher_type '{vt}'. Supported: {', '.join(VOUCHER_TYPES)}")

        defaults = self.get_default_config(vt)
        validated: Dict[str, Any] = {
            "voucher_type": vt,
            "layout_name": str(config_data.get("layout_name") or defaults["layout_name"]).strip()[:100],
        }

        # 1. Header Config
        raw_header = config_data.get("header_config") or {}
        if isinstance(raw_header, str):
            try:
                raw_header = json.loads(raw_header)
            except Exception:
                raw_header = {}
        h_cfg = dict(defaults["header_config"])
        for k in h_cfg:
            if k in raw_header:
                if isinstance(h_cfg[k], bool):
                    h_cfg[k] = bool(raw_header[k])
                elif isinstance(h_cfg[k], (int, float)):
                    try:
                        h_cfg[k] = max(5.0, min(150.0, float(raw_header[k])))
                    except (TypeError, ValueError):
                        pass
                else:
                    h_cfg[k] = str(raw_header[k])
        if h_cfg["logo_position"] not in ("left", "center", "right"):
            h_cfg["logo_position"] = "left"
        validated["header_config"] = h_cfg

        # 2. Invoice Info Config
        raw_info = config_data.get("invoice_info_config") or {}
        if isinstance(raw_info, str):
            try:
                raw_info = json.loads(raw_info)
            except Exception:
                raw_info = {}
        i_cfg = dict(defaults["invoice_info_config"])
        for k in i_cfg:
            if k in raw_info:
                if isinstance(i_cfg[k], bool):
                    i_cfg[k] = bool(raw_info[k])
                else:
                    i_cfg[k] = str(raw_info[k]).strip()
        validated["invoice_info_config"] = i_cfg

        # 3. Columns Config
        raw_cols = config_data.get("columns_config") or defaults["columns_config"]
        if isinstance(raw_cols, str):
            try:
                raw_cols = json.loads(raw_cols)
            except Exception:
                raw_cols = defaults["columns_config"]
        if not isinstance(raw_cols, list):
            raw_cols = defaults["columns_config"]

        col_map = {c["key"]: c for c in raw_cols if isinstance(c, dict) and "key" in c}
        sanitized_cols = []
        for def_col in DEFAULT_COLUMNS:
            ckey = def_col["key"]
            user_col = col_map.get(ckey, {})
            merged = {
                "key": ckey,
                "label": str(user_col.get("label") or def_col["label"]).strip()[:50],
                "visible": bool(user_col.get("visible", def_col["visible"])),
                "order": int(user_col.get("order", def_col["order"])),
                "width": str(user_col.get("width") or def_col["width"]).strip(),
                "align": str(user_col.get("align") or def_col["align"]).strip().lower(),
            }
            if merged["align"] not in ("left", "center", "right"):
                merged["align"] = def_col["align"]
            sanitized_cols.append(merged)

        # Sort columns by order
        sanitized_cols.sort(key=lambda x: x["order"])
        validated["columns_config"] = sanitized_cols

        # 4. Totals Config
        raw_totals = config_data.get("totals_config") or {}
        if isinstance(raw_totals, str):
            try:
                raw_totals = json.loads(raw_totals)
            except Exception:
                raw_totals = {}
        t_cfg = dict(defaults["totals_config"])
        for k in t_cfg:
            if k in raw_totals:
                t_cfg[k] = bool(raw_totals[k])
        validated["totals_config"] = t_cfg

        # 5. Footer Config
        raw_footer = config_data.get("footer_config") or {}
        if isinstance(raw_footer, str):
            try:
                raw_footer = json.loads(raw_footer)
            except Exception:
                raw_footer = {}
        f_cfg = dict(defaults["footer_config"])
        for k in f_cfg:
            if k in raw_footer:
                if isinstance(f_cfg[k], bool):
                    f_cfg[k] = bool(raw_footer[k])
                else:
                    f_cfg[k] = str(raw_footer[k])
        validated["footer_config"] = f_cfg

        # 6. Style Config
        raw_style = config_data.get("style_config") or {}
        if isinstance(raw_style, str):
            try:
                raw_style = json.loads(raw_style)
            except Exception:
                raw_style = {}
        s_cfg = dict(defaults["style_config"])
        for k in s_cfg:
            if k in raw_style:
                if isinstance(s_cfg[k], bool):
                    s_cfg[k] = bool(raw_style[k])
                elif isinstance(s_cfg[k], int):
                    try:
                        s_cfg[k] = max(7, min(16, int(raw_style[k])))
                    except (TypeError, ValueError):
                        pass
                else:
                    s_cfg[k] = str(raw_style[k])
        validated["style_config"] = s_cfg

        return validated

    # =========================================================================
    # Traditional Billing Persistence (data/traditional_billing.db)
    # =========================================================================

    def get_layout_config(
        self,
        company_id: str,
        voucher_type: str,
        branch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieves layout configuration for company and voucher_type from Traditional Billing database.
        Returns saved configuration or standard defaults if not yet customized.
        """
        if not company_id:
            raise ValueError("company_id is required.")
        vt = (voucher_type or "sales_invoice").strip().lower()
        if vt not in VOUCHER_TYPES:
            raise ValueError(f"Invalid voucher type '{voucher_type}'. Supported: {', '.join(VOUCHER_TYPES)}")

        self._db_manager.ensure_initialized()

        with self._db_manager.read_session_scope() as session:
            stmt = select(BillLayoutConfiguration).where(
                BillLayoutConfiguration.company_id == company_id,
                BillLayoutConfiguration.voucher_type == vt
            )
            row = session.scalars(stmt).first()
            if row:
                return self._row_to_dict(row)

        defaults = self.get_default_config(vt)
        defaults["company_id"] = company_id
        defaults["branch_id"] = branch_id
        defaults["is_default"] = True
        return defaults

    def save_layout_config(
        self,
        company_id: str,
        voucher_type: str,
        config_data: Dict[str, Any],
        branch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Saves or updates bill layout configuration in Traditional Billing database.
        Idempotent: updates existing without duplicates.
        """
        if not company_id:
            raise ValueError("company_id is required.")

        config_data["voucher_type"] = voucher_type
        validated = self.validate_layout_config(config_data)
        vt = validated["voucher_type"]

        self._db_manager.ensure_initialized()

        with self._db_manager.session_scope() as session:
            comp = session.get(Company, company_id)
            if not comp:
                raise ValueError(f"Company '{company_id}' not found in Traditional Billing.")

            target_branch_id = branch_id
            if not target_branch_id:
                branch_stmt = select(Branch).where(
                    Branch.company_id == company_id,
                    Branch.code == "BR01"
                )
                br = session.scalars(branch_stmt).first()
                if br:
                    target_branch_id = br.id

            stmt = select(BillLayoutConfiguration).where(
                BillLayoutConfiguration.company_id == company_id,
                BillLayoutConfiguration.voucher_type == vt
            )
            existing = session.scalars(stmt).first()

            if existing:
                existing.layout_name = validated["layout_name"]
                existing.header_config = json.dumps(validated["header_config"])
                existing.invoice_info_config = json.dumps(validated["invoice_info_config"])
                existing.columns_config = json.dumps(validated["columns_config"])
                existing.totals_config = json.dumps(validated["totals_config"])
                existing.footer_config = json.dumps(validated["footer_config"])
                existing.style_config = json.dumps(validated["style_config"])
                existing.branch_id = target_branch_id
                existing.updated_at = utc_now()
                target_obj = existing
                logger.info(f"Updated Bill Layout [{vt}] for Company {company_id}.")
            else:
                target_obj = BillLayoutConfiguration(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    branch_id=target_branch_id,
                    voucher_type=vt,
                    layout_name=validated["layout_name"],
                    header_config=json.dumps(validated["header_config"]),
                    invoice_info_config=json.dumps(validated["invoice_info_config"]),
                    columns_config=json.dumps(validated["columns_config"]),
                    totals_config=json.dumps(validated["totals_config"]),
                    footer_config=json.dumps(validated["footer_config"]),
                    style_config=json.dumps(validated["style_config"]),
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                session.add(target_obj)
                logger.info(f"Created Bill Layout [{vt}] for Company {company_id}.")

            session.flush()
            result = self._row_to_dict(target_obj)

        result["is_default"] = False
        return result

    def reset_layout_config(
        self,
        company_id: str,
        voucher_type: str,
        section: Optional[str] = None,
        branch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resets entire layout or a specific section ('header', 'columns', 'totals', 'footer', 'style')
        to factory defaults.
        """
        if not company_id:
            raise ValueError("company_id is required.")
        vt = (voucher_type or "sales_invoice").strip().lower()
        if vt not in VOUCHER_TYPES:
            raise ValueError(f"Invalid voucher type '{voucher_type}'.")

        defaults = self.get_default_config(vt)
        self._db_manager.ensure_initialized()

        with self._db_manager.session_scope() as session:
            stmt = select(BillLayoutConfiguration).where(
                BillLayoutConfiguration.company_id == company_id,
                BillLayoutConfiguration.voucher_type == vt
            )
            existing = session.scalars(stmt).first()

            if existing:
                if section and section in ("header_config", "invoice_info_config", "columns_config", "totals_config", "footer_config", "style_config"):
                    # Partial reset of single section
                    sec_key = section if section.endswith("_config") else f"{section}_config"
                    if sec_key in defaults:
                        setattr(existing, sec_key, json.dumps(defaults[sec_key]))
                        existing.updated_at = utc_now()
                        session.flush()
                        res = self._row_to_dict(existing)
                        res["is_default"] = False
                        return res
                else:
                    # Full reset: delete custom record
                    session.delete(existing)
                    logger.info(f"Reset entire Bill Layout [{vt}] for Company {company_id} to defaults.")

        defaults["company_id"] = company_id
        defaults["branch_id"] = branch_id
        defaults["is_default"] = True
        return defaults

    def duplicate_layout_config(
        self,
        company_id: str,
        from_voucher_type: str,
        to_voucher_type: str,
        branch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Duplicates settings from an existing voucher layout as a starting point for another voucher type.
        Adjusts the invoice title and party labels appropriately.
        """
        source = self.get_layout_config(company_id, from_voucher_type, branch_id=branch_id)
        duplicated = copy.deepcopy(source)

        to_vt = to_voucher_type.strip().lower()
        if to_vt not in VOUCHER_TYPES:
            raise ValueError(f"Invalid target voucher type '{to_voucher_type}'.")

        duplicated["voucher_type"] = to_vt
        duplicated["layout_name"] = f"Copy of {source.get('layout_name', from_voucher_type)} for {VOUCHER_TITLES.get(to_vt, to_vt)}"
        # Retain target-specific titles
        duplicated["invoice_info_config"]["title"] = VOUCHER_TITLES.get(to_vt, "INVOICE")
        duplicated["invoice_info_config"]["party_name_label"] = VOUCHER_PARTY_LABELS.get(to_vt, "Customer")

        return self.save_layout_config(company_id, to_vt, duplicated, branch_id=branch_id)

    def get_company_details(self, company_id: str) -> Dict[str, Any]:
        """Loads actual company information from database records (Traditional or Fast Billing)."""
        self._db_manager.ensure_initialized()
        with self._db_manager.read_session_scope() as session:
            comp = session.get(Company, company_id)
            if not comp:
                comp = session.query(Company).filter((Company.id == company_id) | (Company.code == company_id)).first()
            if comp:
                return {
                    "company_id": comp.id,
                    "company_name": comp.name,
                    "code": comp.code,
                    "gstin": comp.gstin or "",
                    "state": comp.state or "",
                    "fin_year": comp.fin_year or "",
                    "address": getattr(comp, "address", "") or "Main Business Complex, Market Road",
                    "phone": getattr(comp, "phone", "") or "+91 98765 43210",
                    "email": getattr(comp, "email", "") or "billing@antimatrix.local",
                    "website": getattr(comp, "website", "") or "www.antimatrix.local",
                }

        # Check Fast Billing database if not found in Traditional DB
        try:
            from db.database import db_manager
            with db_manager.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM companies WHERE id = ? OR code = ?;", (company_id, company_id))
                row = cur.fetchone()
                if row:
                    r = dict(row)
                    return {
                        "company_id": r.get("id", company_id),
                        "company_name": r.get("name") or "ANTI MATRIX",
                        "code": r.get("code") or "",
                        "gstin": r.get("gstin") or r.get("tax_no") or "",
                        "state": r.get("state") or "",
                        "fin_year": r.get("fin_year") or r.get("fin_yr") or "",
                        "address": r.get("address") or "Main Business Complex, Market Road",
                        "phone": r.get("phone") or "+91 98765 43210",
                        "email": r.get("email") or "billing@antimatrix.local",
                        "website": r.get("website") or "www.antimatrix.local",
                    }
        except Exception as e:
            logger.debug(f"Fast billing company detail lookup: {e}")

        return {
            "company_name": "ANTI MATRIX COMMERCIAL BILLING",
            "gstin": "",
            "state": "",
            "code": "",
            "fin_year": "",
            "address": "",
            "phone": "",
            "email": "",
            "website": "",
        }

    def _row_to_dict(self, row: BillLayoutConfiguration) -> Dict[str, Any]:
        """Converts ORM model instance to JSON-serializable dictionary."""
        return {
            "id": row.id,
            "company_id": row.company_id,
            "branch_id": row.branch_id,
            "voucher_type": row.voucher_type,
            "layout_name": row.layout_name,
            "header_config": json.loads(row.header_config) if isinstance(row.header_config, str) else row.header_config,
            "invoice_info_config": json.loads(row.invoice_info_config) if isinstance(row.invoice_info_config, str) else row.invoice_info_config,
            "columns_config": json.loads(row.columns_config) if isinstance(row.columns_config, str) else row.columns_config,
            "totals_config": json.loads(row.totals_config) if isinstance(row.totals_config, str) else row.totals_config,
            "footer_config": json.loads(row.footer_config) if isinstance(row.footer_config, str) else row.footer_config,
            "style_config": json.loads(row.style_config) if isinstance(row.style_config, str) else row.style_config,
            "is_default": False,
        }

    # =========================================================================
    # Fast Billing Isolation (data/fast_bill_layout_configurations.json)
    # Guarantees data/anti_matrix_billing.db is untouched!
    # =========================================================================

    def _read_fast_layouts(self) -> Dict[str, Any]:
        """Reads persisted Fast Billing layout configs from isolated JSON store."""
        if self._fast_config_file.exists():
            try:
                with open(self._fast_config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error reading fast bill layouts: {e}")
        return {}

    def _write_fast_layouts(self, store: Dict[str, Any]) -> None:
        """Writes Fast Billing layout configs to isolated JSON store."""
        self._fast_config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._fast_config_file, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2)

    def get_fast_layout_config(self, company_id: str, voucher_type: str) -> Dict[str, Any]:
        """Loads bill layout for Fast Billing mode."""
        vt = (voucher_type or "sales_invoice").strip().lower()
        key = f"{company_id}::{vt}"
        store = self._read_fast_layouts()
        if key in store:
            cfg = dict(store[key])
            cfg["is_default"] = False
            return cfg
        defaults = self.get_default_config(vt)
        defaults["company_id"] = company_id
        defaults["is_default"] = True
        return defaults

    def save_fast_layout_config(self, company_id: str, voucher_type: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Saves bill layout for Fast Billing mode without touching SQLite database."""
        config_data["voucher_type"] = voucher_type
        validated = self.validate_layout_config(config_data)
        vt = validated["voucher_type"]
        key = f"{company_id}::{vt}"
        store = self._read_fast_layouts()
        validated["company_id"] = company_id
        validated["updated_at"] = datetime.now(timezone.utc).isoformat()
        store[key] = validated
        self._write_fast_layouts(store)
        validated["is_default"] = False
        return validated

    def reset_fast_layout_config(self, company_id: str, voucher_type: str) -> Dict[str, Any]:
        """Resets Fast Billing layout to defaults."""
        vt = (voucher_type or "sales_invoice").strip().lower()
        key = f"{company_id}::{vt}"
        store = self._read_fast_layouts()
        if key in store:
            del store[key]
            self._write_fast_layouts(store)
        defaults = self.get_default_config(vt)
        defaults["company_id"] = company_id
        defaults["is_default"] = True
        return defaults

    def duplicate_fast_layout_config(self, company_id: str, from_voucher_type: str, to_voucher_type: str) -> Dict[str, Any]:
        """Duplicates Fast Billing layout."""
        source = self.get_fast_layout_config(company_id, from_voucher_type)
        duplicated = copy.deepcopy(source)
        to_vt = to_voucher_type.strip().lower()
        duplicated["voucher_type"] = to_vt
        duplicated["invoice_info_config"]["title"] = VOUCHER_TITLES.get(to_vt, "INVOICE")
        return self.save_fast_layout_config(company_id, to_vt, duplicated)

    # =========================================================================
    # Printing & Live Preview Compiler
    # Integrates Phase 1 Paper Configuration with Phase 2 Bill Layout Configuration
    # =========================================================================

    def compile_invoice_pdf(
        self,
        voucher_data: Dict[str, Any],
        company_id: str,
        voucher_type: str,
        paper_format: str = "a4",
        output_path: Optional[Path] = None,
        is_fast_billing: bool = False,
        orientation: Optional[str] = None,
        custom_width_mm: Optional[float] = None,
        custom_height_mm: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Compiles a high-fidelity PDF invoice combining:
        1. Paper settings from Phase 1 (width, height, orientation, margins, scaling).
        2. Bill layout configuration from Phase 2 (header, columns, totals, footer, styling).
        3. Voucher transaction data.
        """
        from reportlab.lib import colors
        from reportlab import rl_config
        rl_config.allowTableBoundsErrors = 1
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as ReportLabImage
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm

        fmt = (paper_format or "a4").strip().lower()
        if fmt not in ("a4", "a5", "custom"):
            fmt = "a4"

        # 1. Load Paper Settings from Phase 1
        query_fmt = "a4" if fmt == "custom" else fmt
        if is_fast_billing:
            paper_cfg = paper_config_service.get_fast_paper_config(company_id, query_fmt)
        else:
            paper_cfg = paper_config_service.get_paper_config(company_id, query_fmt)

        # 2. Load Bill Layout Settings from Phase 2
        if is_fast_billing:
            layout_cfg = self.get_fast_layout_config(company_id, voucher_type)
        else:
            layout_cfg = self.get_layout_config(company_id, voucher_type)

        # Extract paper geometry
        if fmt == "custom":
            def_w = float(custom_width_mm or paper_cfg.get("width_mm") or 100.0)
            def_h = float(custom_height_mm or paper_cfg.get("height_mm") or 150.0)
            width_pt = def_w * mm
            height_pt = def_h * mm
        elif fmt == "a5":
            width_pt = float(paper_cfg.get("width_mm", 148.0)) * mm
            height_pt = float(paper_cfg.get("height_mm", 210.0)) * mm
        else:
            width_pt = float(paper_cfg.get("width_mm", 210.0)) * mm
            height_pt = float(paper_cfg.get("height_mm", 297.0)) * mm

        orient = (orientation or paper_cfg.get("orientation") or "portrait").strip().lower()
        if orient == "landscape":
            pagesize = (height_pt, width_pt)
        else:
            pagesize = (width_pt, height_pt)

        margin_l = float(paper_cfg.get("margin_left_mm", 8.0 if fmt == "a5" else 10.0)) * mm
        margin_r = float(paper_cfg.get("margin_right_mm", 8.0 if fmt == "a5" else 10.0)) * mm
        margin_t = float(paper_cfg.get("margin_top_mm", 8.0 if fmt == "a5" else 10.0)) * mm
        margin_b = float(paper_cfg.get("margin_bottom_mm", 8.0 if fmt == "a5" else 10.0)) * mm

        printable_width = max(100.0, pagesize[0] - margin_l - margin_r)

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_dir = config.DATA_DIR / "invoices"
        target_dir.mkdir(parents=True, exist_ok=True)
        out_file = Path(output_path) if output_path else (target_dir / f"invoice_{voucher_type}_{fmt}_{timestamp_str}.pdf")

        doc = SimpleDocTemplate(
            str(out_file),
            pagesize=pagesize,
            leftMargin=margin_l,
            rightMargin=margin_r,
            topMargin=margin_t,
            bottomMargin=margin_b
        )

        styles = getSampleStyleSheet()
        style_cfg = layout_cfg.get("style_config", {})
        primary_hex = style_cfg.get("primary_color", "#1e40af")
        header_bg_hex = style_cfg.get("header_bg_color", "#1e40af")
        header_text_hex = style_cfg.get("header_text_color", "#ffffff")
        base_font_sz = float(style_cfg.get("base_font_size", 9))
        if fmt == "a5":
            base_font_sz = max(7.0, base_font_sz - 1.5)

        elements = []

        # ---------------------------------------------------------
        # Section A: Company Header & Logo
        # ---------------------------------------------------------
        header_cfg = layout_cfg.get("header_config", {})
        company_details = self.get_company_details(company_id)
        comp_name = company_details.get("company_name", "ANTI MATRIX")

        header_lines = []
        if header_cfg.get("show_company_name", True):
            header_lines.append(f"<font size={int(base_font_sz + 4)} color='{primary_hex}'><b>{comp_name}</b></font>")

        addr_parts = []
        if header_cfg.get("show_address", True) and company_details.get("address"):
            addr_parts.append(company_details["address"])
        if header_cfg.get("show_state", True) and company_details.get("state"):
            addr_parts.append(f"State: {company_details['state']}")
        if addr_parts:
            header_lines.append(f"<font size={int(max(6, base_font_sz - 1))} color='#475569'>{' &bull; '.join(addr_parts)}</font>")

        contact_parts = []
        if header_cfg.get("show_phone", True) and company_details.get("phone"):
            contact_parts.append(f"Ph: {company_details['phone']}")
        if header_cfg.get("show_email", True) and company_details.get("email"):
            contact_parts.append(f"Email: {company_details['email']}")
        if header_cfg.get("show_website", True) and company_details.get("website"):
            contact_parts.append(f"Web: {company_details['website']}")
        if contact_parts:
            header_lines.append(f"<font size={int(max(6, base_font_sz - 1))} color='#475569'>{' &bull; '.join(contact_parts)}</font>")

        reg_parts = []
        if header_cfg.get("show_gstin", True) and company_details.get("gstin"):
            reg_parts.append(f"GSTIN: <b>{company_details['gstin']}</b>")
        if header_cfg.get("show_reg_details", True) and company_details.get("code"):
            reg_parts.append(f"Reg No: <b>{company_details['code']}</b>")
        if reg_parts:
            header_lines.append(f"<font size={int(max(6, base_font_sz - 1))} color='#1e293b'>{' | '.join(reg_parts)}</font>")

        header_p = Paragraph("<br/>".join(header_lines), styles["Normal"])
        elements.append(header_p)
        elements.append(Spacer(1, float(paper_cfg.get("header_spacing_mm", 4.0)) * mm))

        # ---------------------------------------------------------
        # Section B: Invoice Metadata & Party Info
        # ---------------------------------------------------------
        info_cfg = layout_cfg.get("invoice_info_config", {})
        if info_cfg.get("show_title", True):
            title_text = info_cfg.get("title", VOUCHER_TITLES.get(voucher_type, "TAX INVOICE"))
            title_p = Paragraph(f"<font size={int(base_font_sz + 2)} color='{primary_hex}'><b>{title_text.upper()}</b></font>", ParagraphStyle('InvTitle', alignment=1))
            elements.append(title_p)
            elements.append(Spacer(1, 5))

        # Two-column box: Left = Party / Billed To, Right = Voucher Info
        vch_no = voucher_data.get("vch_no") or voucher_data.get("voucher_no") or "INV-0001"
        vch_date = voucher_data.get("vch_date") or voucher_data.get("date") or datetime.now().strftime("%d-%m-%Y")
        due_date = voucher_data.get("due_date") or datetime.now().strftime("%d-%m-%Y")
        ref_no = voucher_data.get("reference_no") or voucher_data.get("order_no") or "-"

        party_name = voucher_data.get("party_name") or voucher_data.get("customer_name") or "Cash Customer"
        party_gstin = voucher_data.get("party_gstin") or "-"
        party_state = voucher_data.get("party_state") or company_details.get("state") or "-"
        party_addr = voucher_data.get("party_address") or "-"

        meta_font_sz = int(max(6.5, base_font_sz - 1))
        left_info = []
        if info_cfg.get("show_party_name", True):
            left_info.append(f"<font size={meta_font_sz}><b>{info_cfg.get('party_name_label', 'Billed To')}:</b> {party_name}</font>")
        if info_cfg.get("show_party_address", True) and party_addr != "-":
            left_info.append(f"<font size={meta_font_sz}>Address: {party_addr}</font>")
        if info_cfg.get("show_party_gstin", True) and party_gstin != "-":
            left_info.append(f"<font size={meta_font_sz}>GSTIN: <b>{party_gstin}</b></font>")
        if info_cfg.get("show_party_state", True) and party_state != "-":
            left_info.append(f"<font size={meta_font_sz}>State: {party_state}</font>")

        right_info = []
        if info_cfg.get("show_voucher_no", True):
            right_info.append(f"<font size={meta_font_sz}><b>{info_cfg.get('voucher_no_label', 'Invoice No')}:</b> {vch_no}</font>")
        if info_cfg.get("show_date", True):
            right_info.append(f"<font size={meta_font_sz}><b>{info_cfg.get('date_label', 'Date')}:</b> {vch_date}</font>")
        if info_cfg.get("show_due_date", True):
            right_info.append(f"<font size={meta_font_sz}><b>{info_cfg.get('due_date_label', 'Due Date')}:</b> {due_date}</font>")
        if info_cfg.get("show_reference_no", True) and ref_no != "-":
            right_info.append(f"<font size={meta_font_sz}><b>{info_cfg.get('reference_no_label', 'Ref No')}:</b> {ref_no}</font>")

        left_p = Paragraph("<br/>".join(left_info) if left_info else "Party: Cash", styles["Normal"])
        right_p = Paragraph("<br/>".join(right_info) if right_info else "Voucher Info", styles["Normal"])

        col_w = printable_width / 2.0
        meta_table = Table([[left_p, right_p]], colWidths=[col_w, col_w])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 6))

        # ---------------------------------------------------------
        # Section C: Configurable Product Table
        # ---------------------------------------------------------
        active_cols = [c for c in layout_cfg.get("columns_config", DEFAULT_COLUMNS) if c.get("visible", True)]
        if not active_cols:
            active_cols = [c for c in DEFAULT_COLUMNS if c["key"] in ("sl_no", "name", "qty", "rate", "total")]

        # Allocate column widths proportionally
        total_active = len(active_cols)
        table_col_widths = []
        for c in active_cols:
            w_str = str(c.get("width", "")).strip()
            if w_str.endswith("%"):
                try:
                    pct = float(w_str[:-1]) / 100.0
                    table_col_widths.append(printable_width * pct)
                except Exception:
                    table_col_widths.append(printable_width / total_active)
            else:
                table_col_widths.append(printable_width / total_active)

        # Normalize total width to exactly printable_width
        curr_sum = sum(table_col_widths)
        if curr_sum > 0:
            ratio = printable_width / curr_sum
            table_col_widths = [w * ratio for w in table_col_widths]

        tbl_font_sz = max(6.0, base_font_sz - 1.5)
        p_hdr_style = ParagraphStyle(
            'THdr',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=tbl_font_sz,
            leading=tbl_font_sz + 1.5,
            textColor=colors.HexColor(header_text_hex)
        )
        p_cell_left = ParagraphStyle(
            'TCellL',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=tbl_font_sz,
            leading=tbl_font_sz + 1.5,
            alignment=0
        )
        p_cell_center = ParagraphStyle(
            'TCellC',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=tbl_font_sz,
            leading=tbl_font_sz + 1.5,
            alignment=1
        )
        p_cell_right = ParagraphStyle(
            'TCellR',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=tbl_font_sz,
            leading=tbl_font_sz + 1.5,
            alignment=2
        )

        header_row = []
        for c in active_cols:
            align = 2 if c.get("align") == "right" else (1 if c.get("align") == "center" else 0)
            h_style = ParagraphStyle(f'THdr_{c["key"]}', parent=p_hdr_style, alignment=align)
            header_row.append(Paragraph(f"<b>{c['label']}</b>", h_style))

        items_data = [header_row]
        raw_items = voucher_data.get("items") or [
            {"name": "Standard Sample Item 01", "qty": 2.0, "unit": "Pcs", "rate": 500.0, "taxable_amount": 1000.0, "cgst": 90.0, "sgst": 90.0, "total": 1180.0, "gst_rate": 18.0, "hsn": "8471"},
            {"name": "Standard Sample Item 02", "qty": 1.0, "unit": "Box", "rate": 1200.0, "taxable_amount": 1200.0, "cgst": 108.0, "sgst": 108.0, "total": 1416.0, "gst_rate": 18.0, "hsn": "8473"},
        ]

        for idx, it in enumerate(raw_items, start=1):
            row = []
            for col in active_cols:
                k = col["key"]
                if k == "sl_no":
                    val_str = str(idx)
                elif k == "name":
                    val_str = str(it.get("item_name") or it.get("name", "Item"))
                elif k == "sku":
                    val_str = str(it.get("sku", "-"))
                elif k == "hsn":
                    val_str = str(it.get("hsn_code") or it.get("hsn", "-"))
                elif k == "barcode":
                    val_str = str(it.get("barcode", "-"))
                elif k == "description":
                    val_str = str(it.get("description", "-"))
                elif k == "qty":
                    val_str = f"{float(it.get('qty', 0.0)):g}"
                elif k == "unit":
                    val_str = str(it.get("unit", ""))
                elif k == "rate":
                    val_str = f"{float(it.get('rate') or it.get('price', 0.0)):.2f}"
                elif k == "discount":
                    val_str = f"{float(it.get('discount', 0.0)):.2f}"
                elif k == "taxable_amount":
                    val_str = f"{float(it.get('taxable_amount', 0.0)):.2f}"
                elif k == "cgst":
                    val_str = f"{float(it.get('cgst_amount') or it.get('cgst', 0.0)):.2f}"
                elif k == "sgst":
                    val_str = f"{float(it.get('sgst_amount') or it.get('sgst', 0.0)):.2f}"
                elif k == "igst":
                    val_str = f"{float(it.get('igst_amount') or it.get('igst', 0.0)):.2f}"
                elif k == "gst_rate":
                    val_str = f"{float(it.get('tax_rate') or it.get('gst_rate', 0.0)):g}%"
                elif k == "total":
                    val_str = f"{float(it.get('line_total') or it.get('total') or it.get('amount', 0.0)):.2f}"
                else:
                    val_str = "-"

                align_mode = col.get("align", "left")
                c_style = p_cell_right if align_mode == "right" else (p_cell_center if align_mode == "center" else p_cell_left)
                row.append(Paragraph(val_str, c_style))

            items_data.append(row)

        is_a5 = (fmt == "a5")
        col_pad = 1.0 if (is_a5 or fmt == "custom") else 2.5
        prod_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(header_bg_hex)),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('LEFTPADDING', (0, 0), (-1, -1), col_pad),
            ('RIGHTPADDING', (0, 0), (-1, -1), col_pad),
            ('TOPPADDING', (0, 0), (-1, -1), col_pad + 1.0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), col_pad + 1.0),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        prod_table = Table(items_data, colWidths=table_col_widths, style=TableStyle(prod_style))
        elements.append(prod_table)
        elements.append(Spacer(1, 6))

        # ---------------------------------------------------------
        # Section D: Totals & Tax Summary
        # ---------------------------------------------------------
        totals_cfg = layout_cfg.get("totals_config", {})
        subtotal = float(voucher_data.get("subtotal", 2200.0))
        disc_tot = float(voucher_data.get("discount_total", 0.0))
        taxable = float(voucher_data.get("taxable_amount", 2200.0))
        cgst_tot = float(voucher_data.get("cgst_amount", 198.0))
        sgst_tot = float(voucher_data.get("sgst_amount", 198.0))
        igst_tot = float(voucher_data.get("igst_amount", 0.0))
        round_off = float(voucher_data.get("round_off", 0.0))
        grand_tot = float(voucher_data.get("grand_total", 2596.0))
        amt_paid = float(voucher_data.get("amount_paid", grand_tot))
        bal_due = float(voucher_data.get("balance_due", 0.0))

        tot_rows = []
        if totals_cfg.get("show_subtotal", True):
            tot_rows.append(["Subtotal:", f"₹ {subtotal:.2f}"])
        if totals_cfg.get("show_discount_total", True) and disc_tot > 0:
            tot_rows.append(["Discount:", f"-₹ {disc_tot:.2f}"])
        if totals_cfg.get("show_taxable_amount", True):
            tot_rows.append(["Taxable Value:", f"₹ {taxable:.2f}"])
        if totals_cfg.get("show_cgst_total", True) and cgst_tot > 0:
            tot_rows.append(["CGST:", f"₹ {cgst_tot:.2f}"])
        if totals_cfg.get("show_sgst_total", True) and sgst_tot > 0:
            tot_rows.append(["SGST:", f"₹ {sgst_tot:.2f}"])
        if totals_cfg.get("show_igst_total", True) and igst_tot > 0:
            tot_rows.append(["IGST:", f"₹ {igst_tot:.2f}"])
        if totals_cfg.get("show_round_off", True) and round_off != 0:
            tot_rows.append(["Round Off:", f"₹ {round_off:+.2f}"])
        if totals_cfg.get("show_grand_total", True):
            tot_rows.append(["Grand Total:", f"₹ {grand_tot:.2f}"])
        if totals_cfg.get("show_amount_paid", True):
            tot_rows.append(["Amount Paid:", f"₹ {amt_paid:.2f}"])
        if totals_cfg.get("show_balance_due", True) and bal_due > 0:
            tot_rows.append(["Balance Due:", f"₹ {bal_due:.2f}"])

        if tot_rows:
            tot_w = min(220.0, printable_width * 0.5)
            tot_table = Table(tot_rows, colWidths=[tot_w * 0.55, tot_w * 0.45], hAlign='RIGHT')
            tot_style = [
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTSIZE', (0, 0), (-1, -1), int(base_font_sz)),
                ('PADDING', (0, 0), (-1, -1), 2),
            ]
            # Bold grand total
            for r_idx, r in enumerate(tot_rows):
                if "Grand Total" in r[0]:
                    tot_style.extend([
                        ('FONTNAME', (0, r_idx), (-1, r_idx), 'Helvetica-Bold'),
                        ('TEXTCOLOR', (0, r_idx), (-1, r_idx), colors.HexColor("#047857")),
                        ('LINEABOVE', (0, r_idx), (-1, r_idx), 1, colors.HexColor("#047857")),
                        ('LINEBELOW', (0, r_idx), (-1, r_idx), 1, colors.HexColor("#047857")),
                    ])
            tot_table.setStyle(TableStyle(tot_style))
            elements.append(tot_table)
            elements.append(Spacer(1, 6))

        if totals_cfg.get("show_amount_in_words", True):
            words = voucher_data.get("amount_in_words") or amount_to_words_inr(grand_tot)
            words_p = Paragraph(f"<font size={int(max(6.5, base_font_sz - 1))}><b>Amount in Words:</b> <i>{words}</i></font>", styles["Normal"])
            elements.append(words_p)
            elements.append(Spacer(1, 5))

        # ---------------------------------------------------------
        # Section E: Footer, Bank Details & Signature
        # ---------------------------------------------------------
        footer_cfg = layout_cfg.get("footer_config", {})
        f_left_parts = []
        if footer_cfg.get("show_terms", True) and footer_cfg.get("terms_and_conditions"):
            f_left_parts.append(f"<b>Terms & Conditions:</b><br/>{footer_cfg['terms_and_conditions'].replace(chr(10), '<br/>')}")

        bank_parts = []
        if footer_cfg.get("show_bank_details", True):
            if footer_cfg.get("bank_name"):
                bank_parts.append(f"Bank: {footer_cfg['bank_name']}")
            if footer_cfg.get("account_number"):
                bank_parts.append(f"A/c: {footer_cfg['account_number']}")
            if footer_cfg.get("ifsc_code"):
                bank_parts.append(f"IFSC: {footer_cfg['ifsc_code']}")
            if footer_cfg.get("upi_id"):
                bank_parts.append(f"UPI: {footer_cfg['upi_id']}")
        if bank_parts:
            f_left_parts.append(f"<b>Bank Details:</b><br/>{' &bull; '.join(bank_parts)}")

        f_right_parts = []
        if footer_cfg.get("show_authorized_signatory", True):
            f_right_parts.append("<br/><br/>________________________")
            f_right_parts.append(f"<b>{footer_cfg.get('signatory_title', 'Authorized Signatory')}</b>")
            f_right_parts.append(f"<font size=7 color='#64748b'>For {comp_name}</font>")

        ftr_font_sz = int(max(6.5, base_font_sz - 1.5))
        f_left_p = Paragraph(f"<font size={ftr_font_sz}>" + "<br/><br/>".join(f_left_parts) + "</font>" if f_left_parts else "", styles["Normal"])
        f_right_p = Paragraph(f"<font size={ftr_font_sz}>" + "<br/>".join(f_right_parts) + "</font>" if f_right_parts else "", ParagraphStyle('SignStyle', alignment=2))

        footer_table = Table([[f_left_p, f_right_p]], colWidths=[printable_width * 0.62, printable_width * 0.38])
        footer_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(footer_table)

        doc.build(elements)
        logger.info(f"Compiled invoice PDF at {out_file}")

        return {
            "success": True,
            "file_path": str(out_file),
            "voucher_type": voucher_type,
            "paper_format": fmt,
            "orientation": orient,
            "printable_width": printable_width,
            "message": f"{voucher_type} invoice PDF generated successfully."
        }

    def format_invoice_thermal(
        self,
        voucher_data: Dict[str, Any],
        company_id: str,
        voucher_type: str,
        paper_format: str = "thermal",
        is_fast_billing: bool = False,
    ) -> str:
        """
        Formats a thermal receipt adapting Phase 2 Bill Layout Configuration
        (selected columns, visible headers, totals) to thermal receipt streams (58mm/80mm).
        """
        import textwrap

        # 1. Load Thermal Paper Settings from Phase 1
        if is_fast_billing:
            paper_cfg = paper_config_service.get_fast_paper_config(company_id, "thermal")
        else:
            paper_cfg = paper_config_service.get_paper_config(company_id, "thermal")

        # 2. Load Bill Layout Settings from Phase 2
        if is_fast_billing:
            layout_cfg = self.get_fast_layout_config(company_id, voucher_type)
        else:
            layout_cfg = self.get_layout_config(company_id, voucher_type)

        fmt = (paper_format or "thermal").strip().lower()
        if "58" in fmt:
            width_mm = 58.0
        elif "80" in fmt:
            width_mm = 80.0
        else:
            width_mm = float(paper_cfg.get("width_mm", 80.0))
        cols = 32 if width_mm <= 60 else (42 if width_mm <= 75 else 48)
        line_sep = "-" * cols
        double_sep = "=" * cols

        company_details = self.get_company_details(company_id)
        comp_name = company_details.get("company_name", "ANTI MATRIX").upper()
        header_cfg = layout_cfg.get("header_config", {})
        info_cfg = layout_cfg.get("invoice_info_config", {})
        title = info_cfg.get("title", VOUCHER_TITLES.get(voucher_type, "TAX INVOICE"))

        lines = [
            comp_name[:cols].center(cols),
            title[:cols].center(cols),
        ]
        if header_cfg.get("show_gstin", True) and company_details.get("gstin"):
            lines.append(f"GSTIN: {company_details['gstin']}"[:cols].center(cols))
        if header_cfg.get("show_phone", True) and company_details.get("phone"):
            lines.append(f"Ph: {company_details['phone']}"[:cols].center(cols))

        vch_no = voucher_data.get("vch_no") or voucher_data.get("voucher_no") or "001"
        vch_date = voucher_data.get("vch_date") or datetime.now().strftime("%d-%m-%Y")
        party = voucher_data.get("party_name") or voucher_data.get("customer_name") or "CASH"

        lines.extend([
            line_sep,
            f"Vch: {vch_no:<10} Date: {vch_date}"[:cols],
            f"Party: {party}"[:cols],
            line_sep,
        ])

        if cols >= 42:
            lines.append(f"{'Item':<20} {'Qty':>4} {'Price':>7} {'Total':>8}")
        else:
            lines.append(f"{'Item':<18} {'Total':>12}")
        lines.append(line_sep)

        raw_items = voucher_data.get("items") or [
            {"name": "Standard Sample Item 01", "qty": 2.0, "rate": 500.0, "total": 1000.0},
            {"name": "Standard Sample Item 02", "qty": 1.0, "rate": 1200.0, "total": 1200.0},
        ]
        for it in raw_items:
            name = str(it.get("item_name") or it.get("name", "Item")).strip()
            qty = float(it.get("qty", 0.0))
            price = float(it.get("rate") or it.get("price", 0.0))
            total = float(it.get("total") or it.get("amount") or (qty * price))
            if cols >= 42:
                if len(name) > 20:
                    lines.append(f"{name[:20]:<20} {qty:>4g} {price:>7.2f} {total:>8.2f}")
                    rem = name[20:].strip()
                    while rem:
                        lines.append(f"  {rem[:cols-4]}")
                        rem = rem[cols-4:].strip()
                else:
                    lines.append(f"{name:<20} {qty:>4g} {price:>7.2f} {total:>8.2f}")
            else:
                # 58mm compact layout
                while len(name) > 32:
                    lines.append(name[:32])
                    name = name[32:].strip()
                lines.append(name)
                unit_str = str(it.get('unit', '')).strip()
                unit_part = f" {unit_str}" if unit_str else ""
                q_p = f"  {qty:g}{unit_part} @ {price:.2f}"
                tot_str = f"{total:.2f}"
                sp = max(1, cols - len(q_p) - len(tot_str))
                lines.append(f"{q_p}{' ' * sp}{tot_str}"[:cols])

        lines.append(line_sep)

        totals_cfg = layout_cfg.get("totals_config", {})
        subtotal = float(voucher_data.get("subtotal", 2200.0))
        grand_total = float(voucher_data.get("grand_total", 2200.0))

        val_w = 9
        label_w = cols - val_w - 2
        if totals_cfg.get("show_subtotal", True):
            lines.append(f"{'Subtotal:':<{label_w}}  {subtotal:>{val_w}.2f}")
        if totals_cfg.get("show_cgst_total", True) and float(voucher_data.get("cgst_amount", 0.0)) > 0:
            lines.append(f"{'CGST:':<{label_w}}  {float(voucher_data['cgst_amount']):>{val_w}.2f}")
        if totals_cfg.get("show_sgst_total", True) and float(voucher_data.get("sgst_amount", 0.0)) > 0:
            lines.append(f"{'SGST:':<{label_w}}  {float(voucher_data['sgst_amount']):>{val_w}.2f}")
        if totals_cfg.get("show_round_off", True) and float(voucher_data.get("round_off", 0.0)) != 0:
            lines.append(f"{'Round Off:':<{label_w}}  {float(voucher_data['round_off']):>{val_w}.2f}")

        if totals_cfg.get("show_grand_total", True):
            lines.extend([
                double_sep,
                f"{'GRAND TOTAL:':<{label_w}}  {grand_total:>{val_w}.2f}",
                double_sep,
            ])

        if totals_cfg.get("show_amount_in_words", True):
            words = voucher_data.get("amount_in_words") or amount_to_words_inr(grand_total)
            wrapped_w = textwrap.wrap(f"Words: {words}", width=cols)
            lines.extend(wrapped_w)

        footer_cfg = layout_cfg.get("footer_config", {})
        if footer_cfg.get("show_customer_notes", True) and footer_cfg.get("customer_notes"):
            wrapped_notes = textwrap.wrap(footer_cfg["customer_notes"], width=cols)
            lines.extend([n.center(cols) for n in wrapped_notes])

        if paper_cfg.get("auto_cut", True):
            lines.extend(["", "[ === PAPER CUT === ]".center(cols), ""])

        return "\n".join(lines)


bill_layout_service = BillLayoutConfigService()
