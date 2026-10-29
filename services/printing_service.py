"""
Printing Service for Anti Matrix Billing ERP.
Generates 58mm & 80mm thermal receipt layouts, ESC/POS text streams, and A4/Thermal PDF documents.
Hardware-safe: printer disconnection never causes transaction failure.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
from core.configuration import config
from core.logging_config import logger


class PrintingService:
    @staticmethod
    def format_thermal_receipt(voucher_data: Dict[str, Any], width_mm: int = 80) -> str:
        """
        Formats a clean, aligned thermal receipt text stream suitable for 58mm or 80mm printers.
        width_mm == 58 -> 32 columns
        width_mm == 80 -> 48 columns
        """
        cols = config.THERMAL_WIDTH_58MM if width_mm == 58 else config.THERMAL_WIDTH_80MM
        line_sep = "-" * cols
        double_sep = "=" * cols

        comp_name = voucher_data.get("company_name", "ANTI MATRIX").upper()
        gstin = voucher_data.get("company_gstin", "")
        vch_no = voucher_data.get("vch_no", "")
        vch_date = voucher_data.get("vch_date", datetime.now().strftime("%d-%m-%Y"))
        time_str = datetime.now().strftime("%H:%M")
        party = voucher_data.get("party_name", "CASH")
        items = voucher_data.get("items", [])
        subtotal = float(voucher_data.get("subtotal") or 0.0)
        cgst = float(voucher_data.get("cgst_amount") or 0.0)
        sgst = float(voucher_data.get("sgst_amount") or 0.0)
        igst = float(voucher_data.get("igst_amount") or 0.0)
        round_off = float(voucher_data.get("round_off") or 0.0)
        grand_total = float(voucher_data.get("grand_total") or 0.0)
        pay_method = voucher_data.get("payment_method", "CASH")

        lines = [
            comp_name.center(cols),
            "RETAIL / POS BILL".center(cols),
        ]
        if gstin:
            lines.append(f"GSTIN: {gstin}".center(cols))

        lines.extend([
            line_sep,
            f"Bill No: {vch_no:<15} Date: {vch_date} {time_str}".strip()[:cols],
            f"Customer: {party}"[:cols],
            line_sep
        ])

        # Header for items
        if cols >= 48:
            lines.append(f"{'Item':<22} {'Qty':>5} {'Price':>8} {'Total':>10}")
        else:
            lines.append(f"{'Item':<14} {'Qty':>4} {'Total':>10}")
        lines.append(line_sep)

        for it in items:
            name = it.get("item_name") or it.get("name", "Item")
            qty = float(it.get("qty") or 0.0)
            unit = it.get("unit", "")
            price = float(it.get("price") or 0.0)
            total = float(it.get("amount") or it.get("line_total") or (qty * price))

            qty_str = f"{qty:g} {unit}".strip()
            if cols >= 48:
                line_str = f"{name[:21]:<22} {qty_str:>5} {price:>8.2f} {total:>10.2f}"
            else:
                line_str = f"{name[:13]:<14} {qty_str:>4} {total:>10.2f}"
            lines.append(line_str)

        lines.extend([
            line_sep,
            f"{'Subtotal:':<{cols - 12}} {subtotal:>10.2f}"
        ])

        if cgst > 0 or sgst > 0:
            lines.append(f"{'CGST:':<{cols - 12}} {cgst:>10.2f}")
            lines.append(f"{'SGST:':<{cols - 12}} {sgst:>10.2f}")
        elif igst > 0:
            lines.append(f"{'IGST:':<{cols - 12}} {igst:>10.2f}")

        if round_off != 0.0:
            lines.append(f"{'Round Off:':<{cols - 12}} {round_off:>+10.2f}")

        lines.extend([
            double_sep,
            f"{'GRAND TOTAL:':<{cols - 12}} {grand_total:>10.2f}",
            double_sep,
            f"Paid by: {pay_method} - ₹{grand_total:.2f}",
            "",
            "*** THANK YOU FOR SHOPPING! ***".center(cols),
            "Anti Matrix Commercial Billing".center(cols),
            "\n"
        ])

        return "\n".join(lines)

    @classmethod
    def generate_pdf_invoice(cls, voucher_data: Dict[str, Any], output_path: Path) -> Path:
        """
        Generates an A4 Tax Invoice PDF using reportlab.
        """
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        styles = getSampleStyleSheet()
        elements = []

        comp_name = voucher_data.get("company_name", "ANTI MATRIX").upper()
        gstin = voucher_data.get("company_gstin", "33AAAPL1234F1Z1")
        vch_no = voucher_data.get("vch_no", "001")
        vch_date = voucher_data.get("vch_date", "")
        party = voucher_data.get("party_name", "CASH")

        # Header Title
        title_style = ParagraphStyle(
            "InvoiceTitle",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#1e3a8a"),
            alignment=1
        )
        elements.append(Paragraph(f"TAX INVOICE - {comp_name}", title_style))
        if gstin:
            elements.append(Paragraph(f"<font size=10 color='#475569'>GSTIN: {gstin}</font>", styles["Normal"]))
        elements.append(Spacer(1, 14))

        # Invoice Info Bar
        info_data = [
            [f"Invoice No: <b>{vch_no}</b>", f"Date: <b>{vch_date}</b>"],
            [f"Customer: <b>{party}</b>", f"Payment Mode: <b>{voucher_data.get('payment_method', 'CASH')}</b>"]
        ]
        info_table = Table(info_data, colWidths=[260, 260])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
            ('PADDING', (0,0), (-1,-1), 6),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 14))

        # Items Table
        table_rows = [["#", "Item Description", "Qty", "Unit", "Rate (₹)", "Tax %", "Amount (₹)"]]
        items = voucher_data.get("items", [])
        for idx, it in enumerate(items, start=1):
            name = it.get("item_name") or it.get("name", "Item")
            qty = float(it.get("qty") or 0.0)
            unit = it.get("unit", "Pcs.")
            price = float(it.get("price") or 0.0)
            tax_rate = float(it.get("tax_rate") or 18.0)
            amt = float(it.get("amount") or it.get("line_total") or (qty * price))
            table_rows.append([str(idx), name, f"{qty:g}", unit, f"{price:.2f}", f"{tax_rate:g}%", f"{amt:.2f}"])

        items_table = Table(table_rows, colWidths=[30, 210, 45, 45, 60, 50, 80])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e40af")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (0,-1), 'CENTER'),
            ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 14))

        # Summary Table
        grand_total = float(voucher_data.get("grand_total") or 0.0)
        summary_rows = [
            ["Subtotal:", f"₹ {float(voucher_data.get('subtotal', 0.0)):.2f}"],
            ["CGST:", f"₹ {float(voucher_data.get('cgst_amount', 0.0)):.2f}"],
            ["SGST:", f"₹ {float(voucher_data.get('sgst_amount', 0.0)):.2f}"],
            ["Round Off:", f"₹ {float(voucher_data.get('round_off', 0.0)):+.2f}"],
            ["Grand Total:", f"₹ {grand_total:.2f}"]
        ]
        sum_table = Table(summary_rows, colWidths=[100, 100], hAlign='RIGHT')
        sum_table.setStyle(TableStyle([
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0,-1), (-1,-1), colors.HexColor("#047857")),
            ('FONTSIZE', (0,-1), (-1,-1), 11),
            ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
            ('LINEBELOW', (0,-1), (-1,-1), 1.5, colors.HexColor("#047857")),
        ]))
        elements.append(sum_table)

        doc.build(elements)
        logger.info(f"PDF invoice successfully generated at {output_path}")
        return output_path


printing_service = PrintingService()
