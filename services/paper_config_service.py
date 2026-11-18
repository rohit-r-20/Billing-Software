"""
Paper Configuration Service for Anti Matrix Billing ERP V2.
Manages database persistence, validation, default settings, and test printing
for A4, A5, and Thermal paper formats with strict mode and tenant isolation.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple

from sqlalchemy import select

from db.traditional_database import traditional_db_manager, TraditionalDatabaseManager
from db.traditional_models import PaperConfiguration, Company, Branch, utc_now
from core.configuration import config
from core.logging_config import logger


# ==============================================================================
# Standard Specifications & Default Settings
# ==============================================================================

DEFAULT_A4_CONFIG: Dict[str, Any] = {
    "paper_format": "a4",
    "width_mm": 210.0,
    "height_mm": 297.0,
    "orientation": "portrait",
    "margin_top_mm": 10.0,
    "margin_bottom_mm": 10.0,
    "margin_left_mm": 10.0,
    "margin_right_mm": 10.0,
    "default_printer": "",
    "print_scaling": 100,
    "header_spacing_mm": 5.0,
    "footer_spacing_mm": 5.0,
    "page_numbering": True,
}

DEFAULT_A5_CONFIG: Dict[str, Any] = {
    "paper_format": "a5",
    "width_mm": 148.0,
    "height_mm": 210.0,
    "orientation": "portrait",
    "margin_top_mm": 8.0,
    "margin_bottom_mm": 8.0,
    "margin_left_mm": 8.0,
    "margin_right_mm": 8.0,
    "default_printer": "",
    "print_scaling": 100,
    "header_spacing_mm": 4.0,
    "footer_spacing_mm": 4.0,
    "page_numbering": True,
}

DEFAULT_THERMAL_CONFIG: Dict[str, Any] = {
    "paper_format": "thermal",
    "thermal_paper_width_type": "80mm",
    "width_mm": 80.0,
    "height_mm": None,
    "printable_width_mm": 72.0,
    "margin_top_mm": 4.0,
    "margin_bottom_mm": 4.0,
    "margin_left_mm": 2.0,
    "margin_right_mm": 2.0,
    "default_printer": "",
    "print_density": "Normal",
    "font_size": 10,
    "line_spacing": 1.2,
    "char_alignment": "left",
    "auto_cut": True,
}


class PaperConfigService:
    """Enterprise service for Paper Configuration persistence and validation."""

    def __init__(self, db_manager: Optional[TraditionalDatabaseManager] = None):
        self._db_manager = db_manager or traditional_db_manager
        self._fast_config_file = config.DATA_DIR / "fast_paper_configurations.json"

    # =========================================================================
    # Validation Rules
    # =========================================================================

    def get_default_config(self, paper_format: str, thermal_width_type: str = "80mm") -> Dict[str, Any]:
        """Returns fresh default dictionary for the requested paper format."""
        fmt = (paper_format or "").strip().lower()
        if fmt == "a4":
            return dict(DEFAULT_A4_CONFIG)
        elif fmt == "a5":
            return dict(DEFAULT_A5_CONFIG)
        elif fmt == "thermal":
            cfg = dict(DEFAULT_THERMAL_CONFIG)
            if thermal_width_type == "58mm":
                cfg.update({
                    "thermal_paper_width_type": "58mm",
                    "width_mm": 58.0,
                    "printable_width_mm": 48.0,
                    "font_size": 9,
                })
            return cfg
        else:
            raise ValueError(f"Unsupported paper format: '{paper_format}'. Must be a4, a5, or thermal.")

    def validate_paper_config(self, paper_format: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates paper dimensions, margins, and output parameters.
        Returns cleaned, normalized dictionary or raises ValueError.
        """
        fmt = (paper_format or "").strip().lower()
        if fmt not in ("a4", "a5", "thermal"):
            raise ValueError(f"Invalid paper format '{paper_format}'. Supported formats: a4, a5, thermal.")

        validated: Dict[str, Any] = {"paper_format": fmt}

        # Orientation
        orientation = str(data.get("orientation") or "portrait").strip().lower()
        if orientation not in ("portrait", "landscape"):
            raise ValueError("Orientation must be 'portrait' or 'landscape'.")
        validated["orientation"] = orientation

        # Scaling
        try:
            scaling = int(data.get("print_scaling", 100))
            if not (25 <= scaling <= 300):
                raise ValueError("Print scaling must be between 25% and 300%.")
            validated["print_scaling"] = scaling
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid print scaling: {e}")

        # Margins
        try:
            m_top = float(data.get("margin_top_mm", 0.0))
            m_bottom = float(data.get("margin_bottom_mm", 0.0))
            m_left = float(data.get("margin_left_mm", 0.0))
            m_right = float(data.get("margin_right_mm", 0.0))
            if m_top < 0 or m_bottom < 0 or m_left < 0 or m_right < 0:
                raise ValueError("Margin values cannot be negative.")
            validated["margin_top_mm"] = round(m_top, 2)
            validated["margin_bottom_mm"] = round(m_bottom, 2)
            validated["margin_left_mm"] = round(m_left, 2)
            validated["margin_right_mm"] = round(m_right, 2)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid margin values: {e}")

        # Spacings
        try:
            h_space = max(0.0, float(data.get("header_spacing_mm", 0.0)))
            f_space = max(0.0, float(data.get("footer_spacing_mm", 0.0)))
            validated["header_spacing_mm"] = round(h_space, 2)
            validated["footer_spacing_mm"] = round(f_space, 2)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid header/footer spacing: {e}")

        # Printer
        validated["default_printer"] = str(data.get("default_printer") or "").strip()

        # Format-specific validations
        if fmt == "a4":
            try:
                width = float(data.get("width_mm", 210.0))
                height = float(data.get("height_mm", 297.0))
            except (TypeError, ValueError):
                raise ValueError("A4 dimensions must be valid numbers.")

            if not (100.0 <= width <= 350.0):
                raise ValueError("A4 width must be between 100 mm and 350 mm.")
            if not (100.0 <= height <= 500.0):
                raise ValueError("A4 height must be between 100 mm and 500 mm.")
            if m_left + m_right >= width:
                raise ValueError(f"Total horizontal margins ({m_left + m_right}mm) must be less than paper width ({width}mm).")
            if m_top + m_bottom >= height:
                raise ValueError(f"Total vertical margins ({m_top + m_bottom}mm) must be less than paper height ({height}mm).")

            validated["width_mm"] = round(width, 2)
            validated["height_mm"] = round(height, 2)
            validated["page_numbering"] = bool(data.get("page_numbering", True))

        elif fmt == "a5":
            try:
                width = float(data.get("width_mm", 148.0))
                height = float(data.get("height_mm", 210.0))
            except (TypeError, ValueError):
                raise ValueError("A5 dimensions must be valid numbers.")

            if not (80.0 <= width <= 250.0):
                raise ValueError("A5 width must be between 80 mm and 250 mm.")
            if not (100.0 <= height <= 350.0):
                raise ValueError("A5 height must be between 100 mm and 350 mm.")
            if m_left + m_right >= width:
                raise ValueError(f"Total horizontal margins ({m_left + m_right}mm) must be less than paper width ({width}mm).")
            if m_top + m_bottom >= height:
                raise ValueError(f"Total vertical margins ({m_top + m_bottom}mm) must be less than paper height ({height}mm).")

            validated["width_mm"] = round(width, 2)
            validated["height_mm"] = round(height, 2)
            validated["page_numbering"] = bool(data.get("page_numbering", True))

        elif fmt == "thermal":
            width_type = str(data.get("thermal_paper_width_type") or "80mm").strip()
            if width_type not in ("58mm", "80mm", "custom"):
                raise ValueError("Thermal paper width must be '58mm', '80mm', or 'custom'.")
            validated["thermal_paper_width_type"] = width_type

            if width_type == "58mm":
                width = 58.0
            elif width_type == "80mm":
                width = 80.0
            else:
                try:
                    width = float(data.get("width_mm", 80.0))
                except (TypeError, ValueError):
                    raise ValueError("Custom thermal width must be a valid number.")
                if not (30.0 <= width <= 120.0):
                    raise ValueError("Custom thermal paper width must be between 30 mm and 120 mm.")

            validated["width_mm"] = round(width, 2)
            validated["height_mm"] = None  # Continuous receipt roll

            if m_left + m_right >= width:
                raise ValueError(f"Thermal margins ({m_left + m_right}mm) must be strictly less than paper width ({width}mm).")

            # Printable width
            try:
                printable_width = float(data.get("printable_width_mm") or (width - m_left - m_right))
            except (TypeError, ValueError):
                printable_width = width - m_left - m_right

            max_printable = width - m_left - m_right
            if printable_width <= 0:
                raise ValueError("Printable width must be greater than 0 mm.")
            if printable_width > max_printable:
                raise ValueError(f"Printable width ({printable_width}mm) cannot exceed available width ({max_printable}mm).")
            validated["printable_width_mm"] = round(printable_width, 2)

            # Density
            density = str(data.get("print_density") or "Normal").strip()
            if density not in ("Light", "Normal", "Dark"):
                density = "Normal"
            validated["print_density"] = density

            # Font Size
            try:
                font_sz = int(data.get("font_size", 10))
                if not (6 <= font_sz <= 20):
                    raise ValueError("Thermal font size must be between 6 pt and 20 pt.")
                validated["font_size"] = font_sz
            except (TypeError, ValueError):
                validated["font_size"] = 10

            # Line Spacing
            try:
                l_spacing = float(data.get("line_spacing", 1.2))
                if not (0.8 <= l_spacing <= 3.0):
                    raise ValueError("Line spacing must be between 0.8 and 3.0.")
                validated["line_spacing"] = round(l_spacing, 2)
            except (TypeError, ValueError):
                validated["line_spacing"] = 1.2

            # Alignment
            align = str(data.get("char_alignment") or "left").strip().lower()
            if align not in ("left", "center", "right"):
                align = "left"
            validated["char_alignment"] = align

            # Auto Cut
            validated["auto_cut"] = bool(data.get("auto_cut", True))

        return validated

    # =========================================================================
    # Traditional Billing Persistence (data/traditional_billing.db)
    # =========================================================================

    def get_paper_config(
        self,
        company_id: str,
        paper_format: str,
        branch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieves paper configuration for company and format from Traditional Billing database.
        Returns saved configuration or standard defaults if not yet configured.
        """
        if not company_id:
            raise ValueError("company_id is required.")
        fmt = (paper_format or "").strip().lower()
        if fmt not in ("a4", "a5", "thermal"):
            raise ValueError(f"Unsupported paper format: '{paper_format}'.")

        self._db_manager.ensure_initialized()

        with self._db_manager.read_session_scope() as session:
            stmt = select(PaperConfiguration).where(
                PaperConfiguration.company_id == company_id,
                PaperConfiguration.paper_format == fmt
            )
            row = session.scalars(stmt).first()
            if row:
                return self._row_to_dict(row)

        # Return default if not yet saved in database
        defaults = self.get_default_config(fmt)
        defaults["company_id"] = company_id
        defaults["branch_id"] = branch_id
        defaults["is_default"] = True
        return defaults

    def save_paper_config(
        self,
        company_id: str,
        paper_format: str,
        config_data: Dict[str, Any],
        branch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Saves or updates paper configuration in Traditional Billing database.
        Guarantees idempotency: updates existing without creating duplicates.
        """
        if not company_id:
            raise ValueError("company_id is required.")

        validated = self.validate_paper_config(paper_format, config_data)
        fmt = validated["paper_format"]

        self._db_manager.ensure_initialized()

        with self._db_manager.session_scope() as session:
            # Verify company exists
            comp = session.get(Company, company_id)
            if not comp:
                raise ValueError(f"Company '{company_id}' not found in Traditional Billing.")

            # Resolve branch if not provided
            target_branch_id = branch_id
            if not target_branch_id:
                branch_stmt = select(Branch).where(
                    Branch.company_id == company_id,
                    Branch.code == "BR01"
                )
                br = session.scalars(branch_stmt).first()
                if br:
                    target_branch_id = br.id

            stmt = select(PaperConfiguration).where(
                PaperConfiguration.company_id == company_id,
                PaperConfiguration.paper_format == fmt
            )
            existing = session.scalars(stmt).first()

            if existing:
                # Update existing record
                for key, val in validated.items():
                    if hasattr(existing, key):
                        setattr(existing, key, val)
                existing.branch_id = target_branch_id
                existing.updated_at = utc_now()
                target_obj = existing
                logger.info(f"Updated Paper Configuration [{fmt}] for Company {company_id}.")
            else:
                # Insert new record
                target_obj = PaperConfiguration(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    branch_id=target_branch_id,
                    created_at=utc_now(),
                    updated_at=utc_now(),
                    **validated
                )
                session.add(target_obj)
                logger.info(f"Created Paper Configuration [{fmt}] for Company {company_id}.")

            session.flush()
            result = self._row_to_dict(target_obj)

        result["is_default"] = False
        return result

    def reset_paper_config(
        self,
        company_id: str,
        paper_format: str,
        branch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resets paper configuration in Traditional Billing to factory defaults.
        Deletes custom saved record from database if present.
        """
        if not company_id:
            raise ValueError("company_id is required.")
        fmt = (paper_format or "").strip().lower()

        self._db_manager.ensure_initialized()

        with self._db_manager.session_scope() as session:
            stmt = select(PaperConfiguration).where(
                PaperConfiguration.company_id == company_id,
                PaperConfiguration.paper_format == fmt
            )
            existing = session.scalars(stmt).first()
            if existing:
                session.delete(existing)
                logger.info(f"Reset Paper Configuration [{fmt}] for Company {company_id} to defaults.")

        defaults = self.get_default_config(fmt)
        defaults["company_id"] = company_id
        defaults["branch_id"] = branch_id
        defaults["is_default"] = True
        return defaults

    def _row_to_dict(self, row: PaperConfiguration) -> Dict[str, Any]:
        """Converts ORM model instance to JSON-serializable dictionary."""
        return {
            "id": row.id,
            "company_id": row.company_id,
            "branch_id": row.branch_id,
            "paper_format": row.paper_format,
            "width_mm": float(row.width_mm) if row.width_mm is not None else None,
            "height_mm": float(row.height_mm) if row.height_mm is not None else None,
            "orientation": row.orientation,
            "margin_top_mm": float(row.margin_top_mm),
            "margin_bottom_mm": float(row.margin_bottom_mm),
            "margin_left_mm": float(row.margin_left_mm),
            "margin_right_mm": float(row.margin_right_mm),
            "default_printer": row.default_printer or "",
            "print_scaling": row.print_scaling,
            "header_spacing_mm": float(row.header_spacing_mm),
            "footer_spacing_mm": float(row.footer_spacing_mm),
            "page_numbering": bool(row.page_numbering),
            "thermal_paper_width_type": row.thermal_paper_width_type,
            "printable_width_mm": float(row.printable_width_mm) if row.printable_width_mm is not None else None,
            "print_density": row.print_density or "Normal",
            "font_size": row.font_size or 10,
            "line_spacing": float(row.line_spacing) if row.line_spacing is not None else 1.2,
            "char_alignment": row.char_alignment or "left",
            "auto_cut": bool(row.auto_cut) if row.auto_cut is not None else True,
            "is_default": False,
        }

    # =========================================================================
    # Fast Billing Isolation (Guarantees data/anti_matrix_billing.db is untouched)
    # =========================================================================

    def _read_fast_configs(self) -> Dict[str, Any]:
        """Reads persisted Fast Billing paper configs from isolated JSON store."""
        if self._fast_config_file.exists():
            try:
                with open(self._fast_config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error reading fast paper configs: {e}")
        return {}

    def _write_fast_configs(self, configs: Dict[str, Any]) -> None:
        """Writes Fast Billing paper configs to isolated JSON store."""
        self._fast_config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._fast_config_file, "w", encoding="utf-8") as f:
            json.dump(configs, f, indent=2)

    def get_fast_paper_config(self, company_id: str, paper_format: str) -> Dict[str, Any]:
        """Loads paper config for Fast Billing mode."""
        fmt = (paper_format or "").strip().lower()
        key = f"{company_id}::{fmt}"
        store = self._read_fast_configs()
        if key in store:
            cfg = dict(store[key])
            cfg["is_default"] = False
            return cfg
        defaults = self.get_default_config(fmt)
        defaults["company_id"] = company_id
        defaults["is_default"] = True
        return defaults

    def save_fast_paper_config(self, company_id: str, paper_format: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Saves paper config for Fast Billing mode without modifying Fast Billing database."""
        validated = self.validate_paper_config(paper_format, config_data)
        fmt = validated["paper_format"]
        key = f"{company_id}::{fmt}"
        store = self._read_fast_configs()
        validated["company_id"] = company_id
        validated["updated_at"] = datetime.now(timezone.utc).isoformat()
        store[key] = validated
        self._write_fast_configs(store)
        validated["is_default"] = False
        return validated

    def reset_fast_paper_config(self, company_id: str, paper_format: str) -> Dict[str, Any]:
        """Resets Fast Billing paper config to defaults."""
        fmt = (paper_format or "").strip().lower()
        key = f"{company_id}::{fmt}"
        store = self._read_fast_configs()
        if key in store:
            del store[key]
            self._write_fast_configs(store)
        defaults = self.get_default_config(fmt)
        defaults["company_id"] = company_id
        defaults["is_default"] = True
        return defaults

    # =========================================================================
    # Test Print Generation
    # =========================================================================

    def generate_test_print(
        self,
        paper_format: str,
        config_data: Dict[str, Any],
        output_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Generates neutral test print output (PDF for A4/A5, formatted text stream for Thermal).
        Does NOT use sales/purchase invoice content.
        """
        validated = self.validate_paper_config(paper_format, config_data)
        fmt = validated["paper_format"]
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_dir = Path(output_dir) if output_dir else (config.DATA_DIR / "test_prints")
        target_dir.mkdir(parents=True, exist_ok=True)

        if fmt in ("a4", "a5"):
            return self._generate_sheet_test_pdf(fmt, validated, target_dir / f"test_print_{fmt}_{timestamp_str}.pdf")
        else:
            return self._generate_thermal_test_receipt(validated)

    def _generate_sheet_test_pdf(self, fmt: str, cfg: Dict[str, Any], output_path: Path) -> Dict[str, Any]:
        """Builds a neutral test PDF document using reportlab."""
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm

        width_pt = cfg["width_mm"] * mm
        height_pt = cfg["height_mm"] * mm
        if cfg["orientation"] == "landscape":
            pagesize = (height_pt, width_pt)
        else:
            pagesize = (width_pt, height_pt)

        margin_l = cfg["margin_left_mm"] * mm
        margin_r = cfg["margin_right_mm"] * mm
        margin_t = cfg["margin_top_mm"] * mm
        margin_b = cfg["margin_bottom_mm"] * mm

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=pagesize,
            leftMargin=margin_l,
            rightMargin=margin_r,
            topMargin=margin_t,
            bottomMargin=margin_b
        )

        styles = getSampleStyleSheet()
        elements = []

        title_style = ParagraphStyle(
            "TestTitle",
            parent=styles["Heading1"],
            fontSize=14 if fmt == "a4" else 11,
            leading=18 if fmt == "a4" else 14,
            textColor=colors.HexColor("#1e3a8a"),
            alignment=1
        )
        subtitle_style = ParagraphStyle(
            "TestSubtitle",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#475569"),
            alignment=1
        )
        body_style = ParagraphStyle(
            "TestBody",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#334155")
        )

        # Header
        elements.append(Paragraph("ANTI-MATRIX BILLING ERP — HARDWARE TEST PRINT", title_style))
        elements.append(Spacer(1, cfg["header_spacing_mm"] * mm))
        elements.append(Paragraph(
            f"Paper Format: <b>{fmt.upper()}</b> &bull; Orientation: <b>{cfg['orientation'].upper()}</b> &bull; Scaling: <b>{cfg['print_scaling']}%</b>",
            subtitle_style
        ))
        elements.append(Spacer(1, 10))

        # Specifications Table
        specs_data = [
            ["Parameter", "Configured Value", "Parameter", "Configured Value"],
            ["Paper Width", f"{cfg['width_mm']} mm", "Left Margin", f"{cfg['margin_left_mm']} mm"],
            ["Paper Height", f"{cfg['height_mm']} mm", "Right Margin", f"{cfg['margin_right_mm']} mm"],
            ["Top Margin", f"{cfg['margin_top_mm']} mm", "Bottom Margin", f"{cfg['margin_bottom_mm']} mm"],
            ["Header Spacing", f"{cfg['header_spacing_mm']} mm", "Footer Spacing", f"{cfg['footer_spacing_mm']} mm"],
            ["Target Printer", cfg.get("default_printer") or "Default System Printer", "Page Numbering", "Enabled" if cfg.get("page_numbering") else "Disabled"],
        ]
        col_w = (pagesize[0] - margin_l - margin_r) / 4.0
        specs_table = Table(specs_data, colWidths=[col_w] * 4)
        specs_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e40af")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(specs_table)
        elements.append(Spacer(1, 12))

        # Neutral Sample Grid
        sample_rows = [
            ["#", "Test Alignment Indicator", "Qty", "Scale Metric", "Status"],
            ["1", "Left Boundary & Text Margin Test", "1.00", "OK", "PASS"],
            ["2", "Horizontal Printable Width Check", "1.00", "OK", "PASS"],
            ["3", "Vertical Spacing & Font Rendering", "1.00", "OK", "PASS"],
        ]
        sample_table = Table(sample_rows, colWidths=[col_w * 0.4, col_w * 2.0, col_w * 0.5, col_w * 0.6, col_w * 0.5])
        sample_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(sample_table)
        elements.append(Spacer(1, cfg["footer_spacing_mm"] * mm))

        if cfg.get("page_numbering"):
            footer_text = f"Test Pattern &bull; Generated: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')} &bull; Page 1 of 1"
            elements.append(Paragraph(footer_text, subtitle_style))

        doc.build(elements)
        logger.info(f"Test print PDF successfully created at {output_path}")
        return {
            "success": True,
            "format": fmt,
            "file_path": str(output_path),
            "printer": cfg.get("default_printer") or "Default System Printer",
            "message": f"{fmt.upper()} test print PDF generated successfully."
        }

    def _generate_thermal_test_receipt(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Formats a neutral thermal receipt text stream and ESC/POS preview."""
        width_mm = cfg["width_mm"]
        cols = 32 if width_mm <= 60 else (42 if width_mm <= 72 else 48)
        line_sep = "-" * cols
        double_sep = "=" * cols

        align = cfg.get("char_alignment", "left")

        lines = [
            double_sep,
            "*** ANTI-MATRIX TEST RECEIPT ***".center(cols),
            "HARDWARE ALIGNMENT TEST".center(cols),
            double_sep,
            f"Paper Width: {width_mm:.1f} mm ({cfg.get('thermal_paper_width_type', '80mm')})",
            f"Printable Width: {cfg.get('printable_width_mm', width_mm):.1f} mm",
            f"Margins: L:{cfg.get('margin_left_mm', 0)}mm R:{cfg.get('margin_right_mm', 0)}mm",
            f"Font Size: {cfg.get('font_size', 10)}pt | Spacing: {cfg.get('line_spacing', 1.2)}",
            f"Print Density: {cfg.get('print_density', 'Normal')}",
            f"Target Printer: {cfg.get('default_printer') or 'Default Thermal'}",
            line_sep,
            "TEST ITEM / ALIGNMENT PATTERN".center(cols),
            line_sep,
        ]

        # Alignment lines
        test_items = [
            ("Thermal Line Test 01", "1.0", "OK"),
            ("Margin Boundary 02", "1.0", "OK"),
            ("Density & Feed Check", "1.0", "OK"),
        ]

        if cols >= 48:
            lines.append(f"{'Description':<26} {'Qty':>6} {'Status':>12}")
            lines.append(line_sep)
            for desc, qty, status in test_items:
                lines.append(f"{desc:<26} {qty:>6} {status:>12}")
        else:
            lines.append(f"{'Description':<16} {'Qty':>5} {'Status':>9}")
            lines.append(line_sep)
            for desc, qty, status in test_items:
                lines.append(f"{desc[:15]:<16} {qty:>5} {status:>9}")

        lines.extend([
            double_sep,
            f"TEST PRINT TIMESTAMP: {datetime.now().strftime('%H:%M:%S')}",
            double_sep,
        ])

        if cfg.get("auto_cut", True):
            lines.extend([
                "",
                "[ === AUTOMATIC PAPER CUT SIGNAL === ]".center(cols),
                ""
            ])

        receipt_text = "\n".join(lines)
        return {
            "success": True,
            "format": "thermal",
            "width_mm": width_mm,
            "columns": cols,
            "receipt_text": receipt_text,
            "printer": cfg.get("default_printer") or "Default Thermal Printer",
            "auto_cut_enabled": cfg.get("auto_cut", True),
            "message": f"Thermal ({width_mm:.0f}mm) test receipt formatted successfully."
        }


paper_config_service = PaperConfigService()
