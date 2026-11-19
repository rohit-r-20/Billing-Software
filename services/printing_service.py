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
    def format_thermal_receipt(voucher_data: Dict[str, Any], width_mm: int = 80, company_id: Optional[str] = None, voucher_type: Optional[str] = None) -> str:
        """
        Formats a clean, aligned thermal receipt text stream suitable for 58mm or 80mm printers.
        Integrates Phase 1 Paper Settings and Phase 2 Bill Layout Configuration when available.
        """
        cid = company_id or voucher_data.get("company_id")
        vt = voucher_type or voucher_data.get("voucher_type") or "sales_invoice"
        if cid:
            try:
                from services.bill_layout_config_service import bill_layout_service
                return bill_layout_service.format_invoice_thermal(
                    voucher_data=voucher_data,
                    company_id=cid,
                    voucher_type=vt
                )
            except Exception as e:
                logger.warning(f"Error compiling thermal layout, falling back to legacy format: {e}")

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

        disc_total = float(voucher_data.get("discount_total") or 0.0)
        if disc_total > 0:
            gross = float(voucher_data.get("gross_subtotal") or (subtotal + disc_total))
            lines.extend([
                line_sep,
                f"{'Gross Total:':<{cols - 12}} {gross:>10.2f}",
                f"{'Discount:':<{cols - 12}} -{disc_total:>9.2f}",
                f"{'Taxable Subtotal:':<{cols - 12}} {subtotal:>10.2f}"
            ])
        else:
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
    def generate_pdf_invoice(
        cls,
        voucher_data: Dict[str, Any],
        output_path: Path,
        paper_format: str = "a4",
        company_id: Optional[str] = None,
        voucher_type: Optional[str] = None
    ) -> Path:
        """
        Generates an Invoice PDF combining Phase 1 Paper Settings and Phase 2 Bill Layout Configurations.
        """
        cid = company_id or voucher_data.get("company_id")
        vt = voucher_type or voucher_data.get("voucher_type") or "sales_invoice"
        if cid:
            try:
                from services.bill_layout_config_service import bill_layout_service
                res = bill_layout_service.compile_invoice_pdf(
                    voucher_data=voucher_data,
                    company_id=cid,
                    voucher_type=vt,
                    paper_format=paper_format,
                    output_path=output_path
                )
                if res.get("success") and res.get("file_path"):
                    return Path(res["file_path"])
            except Exception as e:
                logger.warning(f"Error compiling bill layout PDF, falling back to default format: {e}")

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

    @staticmethod
    def number_to_indian_rupees(amount: float) -> str:
        """Converts an amount into Indian words (Lakhs, Crores format)."""
        amt = round(float(amount or 0.0), 2)
        if amt < 0:
            return "Negative " + PrintingService.number_to_indian_rupees(abs(amt))
        if amt == 0:
            return "Zero Rupees Only"

        rupees = int(amt)
        paise = int(round((amt - rupees) * 100))

        ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
                "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
                "Seventeen", "Eighteen", "Nineteen"]
        tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

        def _two_digits(n: int) -> str:
            if n == 0:
                return ""
            if n < 20:
                return ones[n]
            return (tens[n // 10] + (" " + ones[n % 10] if n % 10 != 0 else "")).strip()

        def _three_digits(n: int) -> str:
            h = n // 100
            rest = n % 100
            res = ""
            if h > 0:
                res += ones[h] + " Hundred"
                if rest > 0:
                    res += " "
            if rest > 0:
                res += _two_digits(rest)
            return res

        parts = []
        crores = rupees // 10000000
        rupees %= 10000000
        lakhs = rupees // 100000
        rupees %= 100000
        thousands = rupees // 1000
        rupees %= 1000
        hundreds = rupees

        if crores > 0:
            parts.append(_three_digits(crores) + " Crore")
        if lakhs > 0:
            parts.append(_three_digits(lakhs) + " Lakh")
        if thousands > 0:
            parts.append(_three_digits(thousands) + " Thousand")
        if hundreds > 0:
            parts.append(_three_digits(hundreds))

        rupee_str = " ".join(parts).strip() + " Rupees" if parts else "Zero Rupees"
        if paise > 0:
            paise_str = _two_digits(paise) + " Paise"
            return f"{rupee_str} and {paise_str} Only"
        return f"{rupee_str} Only"

    @classmethod
    def format_purchase_voucher_html(
        cls,
        voucher_data: Dict[str, Any],
        company_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generates an A4 professional HTML layout for purchase vouchers.
        Suitable for print previews and document export.
        """
        c_info = company_info or {}
        comp_name = voucher_data.get("company_name") or c_info.get("name") or "ALPHA BILLING ENTERPRISE"
        comp_gstin = voucher_data.get("company_gstin") or c_info.get("gstin") or ""
        comp_address = voucher_data.get("company_address") or c_info.get("address") or ""
        comp_state = voucher_data.get("company_state") or c_info.get("state") or "Tamilnadu"

        vch_no = voucher_data.get("vch_no") or "PUR-000000"
        vch_date = voucher_data.get("vch_date") or voucher_data.get("voucher_date") or datetime.now().strftime("%Y-%m-%d")
        supp_inv_no = voucher_data.get("supplier_invoice_no") or ""
        supp_inv_date = voucher_data.get("supplier_invoice_date") or ""
        supp_name = voucher_data.get("supplier_name") or "SUPPLIER"
        supp_gstin = voucher_data.get("supplier_gstin") or voucher_data.get("supplier_reg_gstin") or "URP / Unregistered"
        supp_address = voucher_data.get("supplier_address") or ""
        supp_state = voucher_data.get("supplier_state") or "Tamilnadu"
        pay_mode = voucher_data.get("payment_type") or voucher_data.get("payment_mode") or "CREDIT"
        godown = voucher_data.get("godown_name") or voucher_data.get("godown_id") or "Main Store"
        narration = voucher_data.get("narration") or ""

        items = voucher_data.get("items") or []
        subtotal = float(voucher_data.get("taxable_amount") or voucher_data.get("subtotal") or 0.0)
        cgst = float(voucher_data.get("cgst_amount") or 0.0)
        sgst = float(voucher_data.get("sgst_amount") or 0.0)
        igst = float(voucher_data.get("igst_amount") or 0.0)
        freight = float(voucher_data.get("freight_charges") or 0.0)
        handling = float(voucher_data.get("handling_charges") or 0.0)
        total_exp = float(voucher_data.get("additional_expenses") or (freight + handling))
        round_off = float(voucher_data.get("round_off") or 0.0)
        grand_total = float(voucher_data.get("grand_total") or 0.0)
        words = cls.number_to_indian_rupees(grand_total)

        # Build table rows
        rows_html = []
        for idx, it in enumerate(items, start=1):
            name = it.get("item_name") or it.get("name") or f"Item {idx}"
            barcode = it.get("barcode") or ""
            batch = it.get("batch_no") or "-"
            exp = it.get("expiry_date") or "-"
            batch_exp = f"{batch} / {exp}" if (batch != "-" or exp != "-") else "-"
            qty = float(it.get("qty") or it.get("quantity") or 0.0)
            free_qty = float(it.get("free_qty") or 0.0)
            unit = it.get("unit") or "Pcs."
            rate = float(it.get("purchase_rate") or it.get("cost_rate") or it.get("price") or 0.0)
            disc_pct = float(it.get("discount_percent") or it.get("discount_pct") or 0.0)
            taxable = float(it.get("taxable_amount") or 0.0)
            tax_rate = float(it.get("tax_rate") or 0.0)
            line_tot = float(it.get("line_total") or it.get("total_amount") or 0.0)
            landed = float(it.get("landed_cost") or 0.0)

            rows_html.append(f"""
                <tr>
                    <td style="text-align:center;">{idx}</td>
                    <td><b>{name}</b><br/><small style="color:#64748b;">Code: {barcode or 'N/A'}</small></td>
                    <td style="text-align:center; font-size:11px;">{batch_exp}</td>
                    <td style="text-align:right; font-weight:700;">{qty:g}</td>
                    <td style="text-align:right;">{free_qty:g}</td>
                    <td style="text-align:center;">{unit}</td>
                    <td style="text-align:right;">₹ {rate:.2f}</td>
                    <td style="text-align:right;">{disc_pct:g}%</td>
                    <td style="text-align:right;">₹ {taxable:.2f}</td>
                    <td style="text-align:center;">{tax_rate:g}%</td>
                    <td style="text-align:right; font-weight:700;">₹ {line_tot:.2f}</td>
                </tr>
            """)

        tax_rows = []
        if cgst > 0 or sgst > 0:
            tax_rows.append(f"<tr><td>CGST:</td><td style='text-align:right;'>₹ {cgst:.2f}</td></tr>")
            tax_rows.append(f"<tr><td>SGST:</td><td style='text-align:right;'>₹ {sgst:.2f}</td></tr>")
        if igst > 0:
            tax_rows.append(f"<tr><td>IGST:</td><td style='text-align:right;'>₹ {igst:.2f}</td></tr>")
        if freight > 0:
            tax_rows.append(f"<tr><td>Freight &amp; Cartage:</td><td style='text-align:right;'>₹ {freight:.2f}</td></tr>")
        if handling > 0:
            tax_rows.append(f"<tr><td>Handling &amp; Other:</td><td style='text-align:right;'>₹ {handling:.2f}</td></tr>")
        elif total_exp > 0 and freight == 0 and handling == 0:
            tax_rows.append(f"<tr><td>Additional Expenses:</td><td style='text-align:right;'>₹ {total_exp:.2f}</td></tr>")
        if round_off != 0.0:
            tax_rows.append(f"<tr><td>Round Off:</td><td style='text-align:right;'>{round_off:+.2f}</td></tr>")

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"/>
    <title>Purchase Voucher - {vch_no}</title>
    <style>
        @page {{ size: A4 portrait; margin: 15mm 15mm 15mm 15mm; }}
        body {{
            font-family: Arial, Helvetica, sans-serif;
            color: #0f172a;
            margin: 0;
            padding: 10px;
            font-size: 12px;
            line-height: 1.4;
            background: #ffffff;
        }}
        .voucher-box {{
            border: 2px solid #1e3a8a;
            border-radius: 4px;
            padding: 16px;
            max-width: 800px;
            margin: 0 auto;
        }}
        .voucher-header {{
            text-align: center;
            border-bottom: 2px solid #1e3a8a;
            padding-bottom: 10px;
            margin-bottom: 12px;
        }}
        .comp-title {{
            font-size: 20px;
            font-weight: 800;
            color: #1e3a8a;
            text-transform: uppercase;
            margin: 0 0 4px 0;
        }}
        .doc-badge {{
            display: inline-block;
            background: #1e3a8a;
            color: #ffffff;
            font-size: 12px;
            font-weight: 700;
            padding: 3px 12px;
            border-radius: 3px;
            margin-top: 6px;
            letter-spacing: 0.5px;
        }}
        .info-grid {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 12px;
            gap: 16px;
        }}
        .info-panel {{
            flex: 1;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            padding: 8px 12px;
            background: #f8fafc;
        }}
        .info-panel h4 {{
            margin: 0 0 6px 0;
            font-size: 11px;
            text-transform: uppercase;
            color: #475569;
            border-bottom: 1px solid #cbd5e1;
            padding-bottom: 4px;
        }}
        .items-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 12px;
            font-size: 11px;
        }}
        .items-table th {{
            background: #1e3a8a;
            color: #ffffff;
            padding: 6px 8px;
            font-weight: 700;
            border: 1px solid #1e3a8a;
        }}
        .items-table td {{
            padding: 5px 8px;
            border: 1px solid #cbd5e1;
        }}
        .summary-container {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
            gap: 16px;
        }}
        .summary-left {{
            flex: 1;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            padding: 10px;
            background: #f8fafc;
            font-size: 11px;
        }}
        .summary-right {{
            width: 280px;
        }}
        .calc-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}
        .calc-table td {{
            padding: 4px 6px;
        }}
        .grand-row {{
            border-top: 2px solid #1e3a8a;
            border-bottom: 2px solid #1e3a8a;
            font-weight: 800;
            font-size: 14px;
            color: #1e3a8a;
            background: #eff6ff;
        }}
        .signatures {{
            display: flex;
            justify-content: space-between;
            margin-top: 40px;
            padding-top: 10px;
            border-top: 1px dashed #94a3b8;
        }}
        .sig-block {{
            text-align: center;
            width: 200px;
        }}
        .sig-line {{
            border-top: 1px solid #0f172a;
            margin-bottom: 4px;
        }}
        @media print {{
            body {{ padding: 0; }}
            .voucher-box {{ border: none; padding: 0; }}
            .no-print {{ display: none !important; }}
        }}
    </style>
</head>
<body>
    <div class="voucher-box">
        <div class="voucher-header">
            <h1 class="comp-title">{comp_name}</h1>
            {f'<div style="font-size:11px; color:#475569;">{comp_address}</div>' if comp_address else ''}
            <div style="font-size:11px; font-weight:700; color:#1e293b; margin-top:2px;">
                GSTIN: {comp_gstin or 'N/A'} | State: {comp_state}
            </div>
            <div class="doc-badge">GOODS INWARD PURCHASE VOUCHER</div>
        </div>

        <div class="info-grid">
            <div class="info-panel">
                <h4>Supplier / Vendor Details</h4>
                <div style="font-size:13px; font-weight:800; color:#0f172a;">{supp_name}</div>
                {f'<div style="font-size:11px; color:#475569;">{supp_address}</div>' if supp_address else ''}
                <div style="margin-top:4px;"><b>GSTIN:</b> {supp_gstin}</div>
                <div><b>State:</b> {supp_state}</div>
            </div>

            <div class="info-panel">
                <h4>Voucher &amp; Invoice Reference</h4>
                <div><b>Internal Voucher No:</b> <span style="font-weight:800; color:#1e3a8a;">{vch_no}</span></div>
                <div><b>Voucher Date:</b> {vch_date}</div>
                <div style="margin-top:4px;"><b>Supplier Bill No:</b> <span style="font-weight:700; color:#b91c1c;">{supp_inv_no}</span></div>
                <div><b>Supplier Bill Date:</b> {supp_inv_date or '-'}</div>
                <div style="margin-top:4px;"><b>Godown / Store:</b> {godown}</div>
                <div><b>Payment Terms:</b> {pay_mode}</div>
            </div>
        </div>

        <table class="items-table">
            <thead>
                <tr>
                    <th style="width:30px;">#</th>
                    <th>Item Description</th>
                    <th style="width:75px;">Batch / Exp</th>
                    <th style="width:50px; text-align:right;">Qty</th>
                    <th style="width:45px; text-align:right;">Free</th>
                    <th style="width:45px; text-align:center;">Unit</th>
                    <th style="width:75px; text-align:right;">Cost (₹)</th>
                    <th style="width:50px; text-align:right;">Disc %</th>
                    <th style="width:75px; text-align:right;">Taxable (₹)</th>
                    <th style="width:50px; text-align:center;">GST</th>
                    <th style="width:85px; text-align:right;">Total (₹)</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows_html)}
            </tbody>
        </table>

        <div class="summary-container">
            <div class="summary-left">
                <div style="margin-bottom:8px;">
                    <b>Amount in Words:</b><br/>
                    <i style="color:#1e3a8a; font-weight:700;">{words}</i>
                </div>
                {f'<div><b>Narration:</b> {narration}</div>' if narration else ''}
                <div style="margin-top:8px; font-size:10px; color:#64748b;">
                    * Computer-generated goods inward voucher under Anti-Matrix ERP. Inward quantities verified into inventory.
                </div>
            </div>

            <div class="summary-right">
                <table class="calc-table">
                    <tr>
                        <td>Taxable Subtotal:</td>
                        <td style="text-align:right; font-weight:600;">₹ {subtotal:.2f}</td>
                    </tr>
                    {''.join(tax_rows)}
                    <tr class="grand-row">
                        <td>GRAND TOTAL:</td>
                        <td style="text-align:right;">₹ {grand_total:.2f}</td>
                    </tr>
                </table>
            </div>
        </div>

        <div class="signatures">
            <div class="sig-block">
                <div class="sig-line"></div>
                <div style="font-size:11px; font-weight:600;">Goods Received By</div>
            </div>
            <div class="sig-block">
                <div class="sig-line"></div>
                <div style="font-size:11px; font-weight:600;">Verified &amp; Inspected</div>
            </div>
            <div class="sig-block">
                <div class="sig-line"></div>
                <div style="font-size:11px; font-weight:700; color:#1e3a8a;">For {comp_name}</div>
                <div style="font-size:10px; color:#64748b;">Authorized Signatory</div>
            </div>
        </div>
    </div>
</body>
</html>
"""
        return html

    @classmethod
    def generate_pdf_purchase_voucher(
        cls,
        voucher_data: Dict[str, Any],
        output_path: Path,
        company_info: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Generates an A4 Purchase Voucher PDF using ReportLab adhering to enterprise ERP standards.
        Accurately renders:
        - Company name, address, GSTIN, state, phone, email
        - Voucher number, voucher date, payment mode, destination godown
        - Supplier name, address, state, GSTIN, supplier invoice no & date
        - Multi-column itemized goods inward table (Sl No, Description, HSN/SAC, Qty, Free, Unit, Rate, Disc %, Taxable, GST %, Total)
        - Tax breakdown (CGST, SGST, IGST), additional expenses, round off, grand total
        - Amount in words in Indian Rupees
        - Narration / remarks and goods verification declaration
        - Signatory blocks (Store Incharge & Authorized Signatory)
        """
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )
        styles = getSampleStyleSheet()
        elements = []

        c_info = company_info or {}
        comp_name = voucher_data.get("company_name") or c_info.get("name") or "ANTI-MATRIX ENTERPRISE"
        comp_gstin = voucher_data.get("company_gstin") or c_info.get("gstin") or ""
        comp_addr = voucher_data.get("company_address") or c_info.get("address") or ""
        comp_phone = voucher_data.get("company_phone") or c_info.get("phone") or ""
        comp_email = voucher_data.get("company_email") or c_info.get("email") or ""
        comp_state = voucher_data.get("company_state") or c_info.get("state") or ""

        vch_no = voucher_data.get("vch_no") or "PUR-000000"
        vch_date = voucher_data.get("vch_date") or voucher_data.get("voucher_date") or datetime.now().strftime("%Y-%m-%d")
        supp_name = voucher_data.get("supplier_name") or "SUPPLIER"
        supp_addr = voucher_data.get("supplier_address") or ""
        supp_state = voucher_data.get("supplier_state") or ""
        supp_gstin = voucher_data.get("supplier_gstin") or voucher_data.get("supplier_reg_gstin") or "URP / Unregistered"
        supp_inv_no = voucher_data.get("supplier_invoice_no") or ""
        supp_inv_date = voucher_data.get("supplier_invoice_date") or ""
        pay_mode = voucher_data.get("payment_type") or voucher_data.get("payment_mode") or "CREDIT"
        godown = voucher_data.get("godown_name") or voucher_data.get("godown_id") or "Main Store"
        narration = voucher_data.get("narration") or ""

        # Styles
        title_style = ParagraphStyle(
            "PurDocTitle",
            parent=styles["Heading1"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#1e3a8a"),
            alignment=1,
            fontName="Helvetica-Bold"
        )
        comp_title_style = ParagraphStyle(
            "PurCompTitle",
            parent=styles["Normal"],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#0f172a"),
            alignment=1,
            fontName="Helvetica-Bold"
        )
        comp_sub_style = ParagraphStyle(
            "PurCompSub",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#475569"),
            alignment=1
        )
        meta_cell_style = ParagraphStyle(
            "PurMetaCell",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#1e293b")
        )
        item_desc_style = ParagraphStyle(
            "PurItemDesc",
            parent=styles["Normal"],
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#0f172a")
        )

        # 1. Header
        elements.append(Paragraph("GOODS INWARD / PURCHASE VOUCHER", title_style))
        elements.append(Paragraph(f"<b>{comp_name.upper()}</b>", comp_title_style))

        comp_meta_parts = []
        if comp_addr:
            comp_meta_parts.append(comp_addr)
        if comp_phone:
            comp_meta_parts.append(f"Phone: {comp_phone}")
        if comp_email:
            comp_meta_parts.append(f"Email: {comp_email}")
        if comp_gstin:
            comp_meta_parts.append(f"GSTIN: <b>{comp_gstin}</b>")
        if comp_state:
            comp_meta_parts.append(f"State: {comp_state}")

        if comp_meta_parts:
            elements.append(Paragraph(" | ".join(comp_meta_parts), comp_sub_style))
        elements.append(Spacer(1, 8))

        # 2. Metadata Grid (Voucher Details & Supplier Details)
        left_meta_html = (
            f"<b>Voucher No:</b> <font color='#1e3a8a'><b>{vch_no}</b></font><br/>"
            f"<b>Voucher Date:</b> {vch_date}<br/>"
            f"<b>Payment Mode:</b> {pay_mode}<br/>"
            f"<b>Destination Godown:</b> {godown}"
        )
        supp_details_lines = [f"<b>Supplier:</b> <b>{supp_name}</b>"]
        if supp_addr:
            supp_details_lines.append(f"<b>Address:</b> {supp_addr}")
        supp_gst_part = f"<b>GSTIN:</b> {supp_gstin}"
        if supp_state:
            supp_gst_part += f" | <b>State:</b> {supp_state}"
        supp_details_lines.append(supp_gst_part)
        inv_part = f"<b>Supplier Bill No:</b> {supp_inv_no or 'N/A'}"
        if supp_inv_date:
            inv_part += f" | <b>Date:</b> {supp_inv_date}"
        supp_details_lines.append(inv_part)
        right_meta_html = "<br/>".join(supp_details_lines)

        meta_table = Table(
            [[Paragraph(left_meta_html, meta_cell_style), Paragraph(right_meta_html, meta_cell_style)]],
            colWidths=[265, 270]
        )
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 8))

        # 3. Items Table
        headers = ["#", "Item Description", "HSN/SAC", "Qty", "Free", "Unit", "Cost (₹)", "Disc %", "Taxable (₹)", "GST %", "Total (₹)"]
        col_widths = [20, 135, 42, 36, 26, 30, 48, 34, 54, 38, 72]
        table_rows = [headers]

        items = voucher_data.get("items") or []
        for idx, it in enumerate(items, start=1):
            name = it.get("item_name") or it.get("name") or f"Item {idx}"
            barcode = it.get("barcode") or ""
            batch = it.get("batch_no") or ""
            exp = it.get("expiry_date") or ""
            hsn = it.get("hsn_code") or it.get("hsn") or "-"
            qty = float(it.get("qty") or it.get("quantity") or 0.0)
            free_qty = float(it.get("free_qty") or 0.0)
            unit = it.get("unit") or "Pcs."
            rate = float(it.get("purchase_rate") or it.get("cost_rate") or it.get("price") or 0.0)
            disc_pct = float(it.get("discount_percent") or it.get("discount_pct") or 0.0)
            taxable = float(it.get("taxable_amount") or 0.0)
            tax_rate = float(it.get("tax_rate") or (float(it.get("cgst_rate") or 0) + float(it.get("sgst_rate") or 0) + float(it.get("igst_rate") or 0)))
            line_tot = float(it.get("line_total") or it.get("total_amount") or 0.0)

            desc_parts = [f"<b>{name}</b>"]
            extra_info = []
            if barcode:
                extra_info.append(f"Code: {barcode}")
            if batch or exp:
                extra_info.append(f"Batch: {batch or '-'}")
                if exp:
                    extra_info.append(f"Exp: {exp}")
            if extra_info:
                desc_parts.append(f"<font size=6.5 color='#64748b'>{' | '.join(extra_info)}</font>")

            desc_p = Paragraph("<br/>".join(desc_parts), item_desc_style)

            table_rows.append([
                str(idx),
                desc_p,
                str(hsn),
                f"{qty:g}",
                f"{free_qty:g}" if free_qty > 0 else "-",
                unit,
                f"{rate:.2f}",
                f"{disc_pct:g}%" if disc_pct > 0 else "0%",
                f"{taxable:.2f}",
                f"{tax_rate:g}%",
                f"{line_tot:.2f}"
            ])

        items_table = Table(table_rows, colWidths=col_widths, repeatRows=1)
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e3a8a")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 7.5),
            ('BOTTOMPADDING', (0,0), (-1,0), 4),
            ('TOPPADDING', (0,0), (-1,0), 4),
            ('ALIGN', (0,1), (0,-1), 'CENTER'),
            ('ALIGN', (2,1), (2,-1), 'CENTER'),
            ('ALIGN', (3,1), (4,-1), 'RIGHT'),
            ('ALIGN', (5,1), (5,-1), 'CENTER'),
            ('ALIGN', (6,1), (8,-1), 'RIGHT'),
            ('ALIGN', (9,1), (9,-1), 'CENTER'),
            ('ALIGN', (10,1), (10,-1), 'RIGHT'),
            ('FONTSIZE', (0,1), (-1,-1), 7.5),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
            ('PADDING', (0,1), (-1,-1), 3),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 8))

        # 4. Summary & Totals Block
        subtotal = float(voucher_data.get("taxable_amount") or voucher_data.get("subtotal") or 0.0)
        cgst = float(voucher_data.get("cgst_amount") or 0.0)
        sgst = float(voucher_data.get("sgst_amount") or 0.0)
        igst = float(voucher_data.get("igst_amount") or 0.0)
        freight = float(voucher_data.get("freight_charges") or 0.0)
        handling = float(voucher_data.get("handling_charges") or 0.0)
        total_exp = float(voucher_data.get("additional_expenses") or (freight + handling))
        round_off = float(voucher_data.get("round_off") or 0.0)
        grand_total = float(voucher_data.get("grand_total") or 0.0)
        words = cls.number_to_indian_rupees(grand_total)

        left_summary_parts = [
            f"<b>Amount in Words:</b><br/>{words}"
        ]
        if narration:
            left_summary_parts.append(f"<br/><b>Remarks / Narration:</b> {narration}")
        left_summary_parts.append(
            "<br/><br/><font size=6.5 color='#64748b'><b>Declaration:</b> Received the goods in good condition and as per specifications. Subject to verification & acceptance.</font>"
        )
        left_summary_p = Paragraph("<br/>".join(left_summary_parts), meta_cell_style)

        right_summary_data = [
            ["Taxable Subtotal:", f"₹ {subtotal:.2f}"]
        ]
        if cgst > 0 or sgst > 0:
            right_summary_data.append(["CGST:", f"₹ {cgst:.2f}"])
            right_summary_data.append(["SGST:", f"₹ {sgst:.2f}"])
        if igst > 0:
            right_summary_data.append(["IGST:", f"₹ {igst:.2f}"])
        if total_exp > 0:
            right_summary_data.append(["Freight / Other:", f"₹ {total_exp:.2f}"])
        if round_off != 0.0:
            right_summary_data.append(["Round Off:", f"{round_off:+.2f}"])
        right_summary_data.append(["GRAND TOTAL:", f"₹ {grand_total:.2f}"])

        right_summary_table = Table(right_summary_data, colWidths=[110, 110])
        right_summary_table.setStyle(TableStyle([
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ALIGN', (0,0), (0,-1), 'LEFT'),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),
            ('PADDING', (0,0), (-1,-1), 2.5),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,-1), (-1,-1), 9.5),
            ('TEXTCOLOR', (0,-1), (-1,-1), colors.HexColor("#1e3a8a")),
            ('LINEBELOW', (0,-1), (-1,-1), 1.5, colors.HexColor("#1e3a8a")),
            ('LINEABOVE', (0,-1), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ]))

        combined_summary = Table(
            [[left_summary_p, right_summary_table]],
            colWidths=[315, 220]
        )
        combined_summary.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('PADDING', (0,0), (-1,-1), 4),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ]))

        # 5. Signatory Block
        sig_data = [
            [
                Paragraph("<b>Received / Checked By:</b><br/><br/><br/>___________________________<br/>Store Incharge", meta_cell_style),
                Paragraph(f"<b>For {comp_name}:</b><br/><br/><br/>___________________________<br/>Authorized Signatory", ParagraphStyle("PurSigRight", parent=meta_cell_style, alignment=2))
            ]
        ]
        sig_table = Table(sig_data, colWidths=[265, 270])
        sig_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))

        footer_p = Paragraph(
            "<font size=6.5 color='#94a3b8'>This is a computer-generated Purchase Voucher (Goods Inward Note) and does not require a physical seal.</font>",
            ParagraphStyle("PurFoot", parent=styles["Normal"], alignment=1)
        )

        elements.append(KeepTogether([
            combined_summary,
            Spacer(1, 14),
            sig_table,
            Spacer(1, 6),
            footer_p
        ]))

        doc.build(elements)
        logger.info(f"Purchase voucher PDF generated at {output_path}")
        return output_path



printing_service = PrintingService()

