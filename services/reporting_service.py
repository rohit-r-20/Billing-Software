"""
Reporting and Analytics Service for Anti Matrix Billing ERP.
Produces Daily Sales, Payment Method breakdowns, GST GSTR-1 summaries,
Stock Movement registers, and Gross Profit estimates based on cost prices.
"""
from typing import Dict, Any, List, Optional
from db.database import db_manager, DatabaseManager
from core.logging_config import logger


class ReportingService:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or db_manager

    def get_daily_sales_report(self, company_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        """Aggregates sales by date: total bills, taxable, tax, and revenue."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT vch_date as date,
                       COUNT(id) as total_bills,
                       SUM(subtotal) as total_taxable,
                       SUM(cgst_amount + sgst_amount + igst_amount) as total_tax,
                       SUM(grand_total) as total_revenue
                FROM sales_vouchers
                WHERE company_id = ? AND is_cancelled = 0
                GROUP BY vch_date
                ORDER BY created_at DESC
                LIMIT ?;
            """, (company_id, limit))
            return [dict(r) for r in cursor.fetchall()]

    def get_payment_summary(self, company_id: str) -> List[Dict[str, Any]]:
        """Payment collection breakdown across CASH, UPI, CARD, CREDIT."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.method, COUNT(p.id) as count, SUM(p.amount) as total_collected
                FROM payments p
                WHERE p.company_id = ?
                GROUP BY p.method
                ORDER BY total_collected DESC;
            """, (company_id,))
            return [dict(r) for r in cursor.fetchall()]

    def get_gst_summary(self, company_id: str) -> Dict[str, Any]:
        """Aggregate GST totals: Intra-state (CGST+SGST) vs Inter-state (IGST)."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    SUM(taxable_amount) as total_taxable,
                    SUM(cgst_amount) as total_cgst,
                    SUM(sgst_amount) as total_sgst,
                    SUM(igst_amount) as total_igst,
                    SUM(grand_total) as total_invoiced
                FROM sales_vouchers
                WHERE company_id = ? AND is_cancelled = 0;
            """, (company_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "total_taxable": float(row["total_taxable"] or 0.0),
                    "total_cgst": float(row["total_cgst"] or 0.0),
                    "total_sgst": float(row["total_sgst"] or 0.0),
                    "total_igst": float(row["total_igst"] or 0.0),
                    "total_gst": float((row["total_cgst"] or 0.0) + (row["total_sgst"] or 0.0) + (row["total_igst"] or 0.0)),
                    "total_invoiced": float(row["total_invoiced"] or 0.0)
                }
            return {"total_taxable": 0.0, "total_cgst": 0.0, "total_sgst": 0.0, "total_igst": 0.0, "total_gst": 0.0, "total_invoiced": 0.0}

    def get_gross_profit_report(self, company_id: str) -> Dict[str, Any]:
        """
        Estimates gross profit by comparing selling price to recorded purchase/cost price.
        Explicitly distinguishes revenue from profit.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    SUM(vi.amount) as total_sales_val,
                    SUM(vi.qty * COALESCE(i.purc_price, 0.0)) as total_cost_val
                FROM sales_voucher_items vi
                JOIN sales_vouchers v ON v.id = vi.voucher_id
                LEFT JOIN items i ON i.id = vi.item_id
                WHERE v.company_id = ? AND v.is_cancelled = 0;
            """, (company_id,))
            row = cursor.fetchone()
            sales_val = float(row["total_sales_val"] or 0.0) if row else 0.0
            cost_val = float(row["total_cost_val"] or 0.0) if row else 0.0
            gross_profit = sales_val - cost_val
            margin_pct = (gross_profit / sales_val * 100.0) if sales_val > 0 else 0.0

            return {
                "total_sales_revenue": round(sales_val, 2),
                "total_estimated_cost": round(cost_val, 2),
                "estimated_gross_profit": round(gross_profit, 2),
                "margin_percentage": round(margin_pct, 2)
            }


reporting_service = ReportingService()

