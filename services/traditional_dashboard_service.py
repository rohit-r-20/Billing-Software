"""
Traditional Billing Dashboard Service.
Provides database-backed operational metrics exclusively from the dedicated
Traditional Billing database. Never uses mock data, demo fallbacks, or Fast Billing.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, List
from sqlalchemy import select, func, and_, text

from db.traditional_database import traditional_db_manager, TraditionalDatabaseManager
from db.traditional_models import Company, Branch, Item, StockBalance
from core.logging_config import logger


class TraditionalDashboardService:
    def __init__(self, db_manager: Optional[TraditionalDatabaseManager] = None):
        self.db = db_manager or traditional_db_manager

    def get_dashboard_metrics(
        self,
        company_id: str,
        branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculates genuine operational metrics for the authenticated tenant.
        Strict fail-closed: derives company_id and branch_id exclusively from backend session.
        If a metric has no genuine source data implemented, it explicitly returns
        zero, empty lists, or None/Not available instead of fabricating values.
        """
        clean_cid = str(company_id or "").strip()
        if not clean_cid:
            raise ValueError("company_id is required for dashboard metrics.")

        with self.db.read_session_scope() as session:
            # 1. Validate company exists and is active
            comp = session.scalar(
                select(Company).where(
                    and_(
                        Company.id == clean_cid,
                        Company.is_active == True,
                    )
                )
            )
            if not comp:
                raise ValueError(f"Company '{clean_cid}' not found or inactive.")

            # 2. Total active SKUs
            active_skus_count = session.scalar(
                select(func.count(Item.id)).where(
                    and_(
                        Item.company_id == clean_cid,
                        Item.is_active == True,
                    )
                )
            ) or 0

            # 3. Stock Valuation & Low Stock
            stock_query = (
                select(
                    StockBalance.current_qty_scaled,
                    Item.cogs_amount,
                )
                .join(Item, StockBalance.item_id == Item.id)
                .where(
                    and_(
                        StockBalance.company_id == clean_cid,
                        Item.company_id == clean_cid,
                        Item.is_active == True,
                    )
                )
            )
            if branch_id:
                clean_bid = str(branch_id).strip()
                if clean_bid:
                    stock_query = stock_query.where(StockBalance.branch_id == clean_bid)

            stock_rows = session.execute(stock_query).all()
            total_valuation = Decimal("0.00")
            low_stock_count = 0

            for qty_scaled, cogs in stock_rows:
                qty = Decimal(qty_scaled) / Decimal(1000)
                cogs_dec = Decimal(str(cogs if cogs is not None else 0.00))
                total_valuation += (qty * cogs_dec)
                if qty_scaled <= 0:
                    low_stock_count += 1

            stock_value = float(total_valuation.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

            # 4. Check for dynamic transaction tables (Sales, Purchases, Payments, Expenses)
            existing_tables = set(
                r[0] for r in session.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                ).all()
            )

            # Sales
            today_sales = 0.00
            today_sales_count = 0
            today_sales_delta = ""
            sales_trend: List[Dict[str, Any]] = []
            recent_invoices: List[Dict[str, Any]] = []

            sales_table = None
            for tbl in ("sales_vouchers", "sales_invoices"):
                if tbl in existing_tables:
                    sales_table = tbl
                    break

            if sales_table:
                # Dynamically inspect columns in sales_table
                table_cols = {
                    r[1] for r in session.execute(text(f"PRAGMA table_info({sales_table})")).all()
                }
                amount_col = "total_amount" if "total_amount" in table_cols else "grand_total"
                mode_col = "payment_mode" if "payment_mode" in table_cols else ("payment_method" if "payment_method" in table_cols else "'CASH'")
                status_col = "status" if "status" in table_cols else "'PAID'"
                party_col = "party_name" if "party_name" in table_cols else "'Cash Customer'"
                vch_col = "voucher_number" if "voucher_number" in table_cols else "id"

                # Query genuine sales records
                sales_row = session.execute(
                    text(f"""
                        SELECT COALESCE(SUM({amount_col}), 0), COUNT(id)
                        FROM {sales_table}
                        WHERE company_id = :cid
                          AND DATE(created_at) = CURRENT_DATE
                    """),
                    {"cid": clean_cid}
                ).first()
                if sales_row:
                    today_sales = float(Decimal(str(sales_row[0])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                    today_sales_count = int(sales_row[1])

                # Sales trend (last 7 days)
                trend_rows = session.execute(
                    text(f"""
                        SELECT strftime('%Y-%m-%d', created_at) as day_date,
                               strftime('%w', created_at) as day_num,
                               COALESCE(SUM({amount_col}), 0) as daily_total
                        FROM {sales_table}
                        WHERE company_id = :cid
                          AND DATE(created_at) >= DATE('now', '-6 days')
                        GROUP BY day_date
                        ORDER BY day_date ASC
                    """),
                    {"cid": clean_cid}
                ).all()
                day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
                for r in trend_rows:
                    d_idx = int(r[1]) if r[1] is not None else 0
                    sales_trend.append({
                        "date": r[0],
                        "day": day_names[d_idx],
                        "label": r[0],
                        "sales": float(r[2]),
                        "purchases": 0.00
                    })

                # Recent invoices
                inv_rows = session.execute(
                    text(f"""
                        SELECT id, COALESCE({vch_col}, id) as vch,
                               COALESCE({party_col}, 'Cash Customer') as party,
                               {amount_col} as total_amt,
                               COALESCE({mode_col}, 'CASH') as mode,
                               COALESCE({status_col}, 'PAID') as status,
                               created_at
                        FROM {sales_table}
                        WHERE company_id = :cid
                        ORDER BY created_at DESC
                        LIMIT 5
                    """),
                    {"cid": clean_cid}
                ).all()
                for r in inv_rows:
                    recent_invoices.append({
                        "vchNo": str(r[1]),
                        "party": str(r[2]),
                        "amount": float(r[3]),
                        "mode": str(r[4]),
                        "status": str(r[5]),
                        "time": str(r[6])
                    })

            # Purchases
            today_purchases = 0.00
            today_purchases_count = 0
            today_purchases_delta = ""
            recent_purchases: List[Dict[str, Any]] = []

            purchase_table = None
            for tbl in ("purchase_vouchers", "purchases"):
                if tbl in existing_tables:
                    purchase_table = tbl
                    break

            if purchase_table:
                pur_row = session.execute(
                    text(f"""
                        SELECT COALESCE(SUM(total_amount), 0), COUNT(id)
                        FROM {purchase_table}
                        WHERE company_id = :cid
                          AND DATE(created_at) = CURRENT_DATE
                    """),
                    {"cid": clean_cid}
                ).first()
                if pur_row:
                    today_purchases = float(Decimal(str(pur_row[0])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                    today_purchases_count = int(pur_row[1])

                recent_pur_rows = session.execute(
                    text(f"""
                        SELECT id, COALESCE(voucher_number, id) as vch,
                               COALESCE(supplier_name, 'Supplier') as supplier,
                               total_amount,
                               COALESCE(tax_amount, 0.0) as tax,
                               COALESCE(status, 'VERIFIED') as status,
                               created_at
                        FROM {purchase_table}
                        WHERE company_id = :cid
                        ORDER BY created_at DESC
                        LIMIT 5
                    """),
                    {"cid": clean_cid}
                ).all()
                for r in recent_pur_rows:
                    recent_purchases.append({
                        "vchNo": str(r[1]),
                        "supplier": str(r[2]),
                        "amount": float(r[3]),
                        "tax": float(r[4]),
                        "status": str(r[5]),
                        "time": str(r[6])
                    })

            # Payment Breakdown & Recent Payments
            payment_summary: List[Dict[str, Any]] = []
            recent_payments: List[Dict[str, Any]] = []

            if "payments" in existing_tables:
                pay_rows = session.execute(
                    text("""
                        SELECT payment_mode, SUM(amount)
                        FROM payments
                        WHERE company_id = :cid
                        GROUP BY payment_mode
                    """),
                    {"cid": clean_cid}
                ).all()
                total_pay_amt = sum(float(r[1]) for r in pay_rows)
                mode_colors = {
                    "UPI": "#2563eb",
                    "CASH": "#10b981",
                    "CARD": "#f59e0b",
                    "CREDIT": "#8b5cf6",
                    "NEFT": "#06b6d4"
                }
                for mode, amt in pay_rows:
                    amt_f = float(amt)
                    pct = round((amt_f / total_pay_amt * 100), 1) if total_pay_amt > 0 else 0
                    mode_clean = str(mode).upper()
                    payment_summary.append({
                        "method": mode_clean,
                        "amount": amt_f,
                        "percent": pct,
                        "color": mode_colors.get(mode_clean, "#6b7280")
                    })

                rec_pay = session.execute(
                    text("""
                        SELECT id, COALESCE(voucher_number, id) as vch,
                               COALESCE(party_name, 'Party') as party,
                               amount,
                               COALESCE(payment_mode, 'CASH') as mode,
                               COALESCE(payment_type, 'COLLECTION') as ptype,
                               created_at
                        FROM payments
                        WHERE company_id = :cid
                        ORDER BY created_at DESC
                        LIMIT 5
                    """),
                    {"cid": clean_cid}
                ).all()
                for r in rec_pay:
                    recent_payments.append({
                        "vchNo": str(r[1]),
                        "party": str(r[2]),
                        "amount": float(r[3]),
                        "mode": str(r[4]),
                        "type": str(r[5]),
                        "time": str(r[6])
                    })

            # Expenses
            today_expenses = 0.00
            held_bills = 0
            expense_table = None
            for tbl in ("expenses", "expense_vouchers"):
                if tbl in existing_tables:
                    expense_table = tbl
                    break

            if expense_table:
                exp_row = session.execute(
                    text(f"""
                        SELECT COALESCE(SUM(amount), 0)
                        FROM {expense_table}
                        WHERE company_id = :cid
                          AND DATE(created_at) = CURRENT_DATE
                    """),
                    {"cid": clean_cid}
                ).first()
                if exp_row:
                    today_expenses = float(Decimal(str(exp_row[0])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

            # Stock Adjustments
            stock_adjustments: List[Dict[str, Any]] = []
            adj_table = None
            for tbl in ("stock_adjustments", "stock_transfers"):
                if tbl in existing_tables:
                    adj_table = tbl
                    break

            if adj_table:
                adj_rows = session.execute(
                    text(f"""
                        SELECT id, item_name, adjustment_type, quantity, reason, created_at
                        FROM {adj_table}
                        WHERE company_id = :cid
                        ORDER BY created_at DESC
                        LIMIT 5
                    """),
                    {"cid": clean_cid}
                ).all()
                for r in adj_rows:
                    stock_adjustments.append({
                        "item": str(r[1]),
                        "type": str(r[2]),
                        "qty": str(r[3]),
                        "reason": str(r[4]),
                        "date": str(r[5])
                    })

            # 5. Receivables & Payables
            # Since customer & supplier ledger balances / transactions are not implemented in Traditional schema yet:
            # Explicitly return None / "Not available" instead of fabricating values.
            receivables = None
            receivables_display = "Not available"
            receivables_overdue_count = None
            receivables_overdue_display = "N/A"

            payables = None
            payables_display = "Not available"
            payables_due_count = None
            payables_due_display = "N/A"

            # 6. Gross Margin & Revenue vs Expense comparison
            # Calculate only when valid historical revenue and COGS data are available.
            gross_margin = None
            gross_margin_display = "Not available"
            revenue_expense: List[Dict[str, Any]] = []

            return {
                "todaySales": today_sales,
                "todaySalesDisplay": f"₹ {today_sales:,.2f}",
                "todaySalesCount": today_sales_count,
                "todaySalesDelta": today_sales_delta,
                "todayPurchases": today_purchases,
                "todayPurchasesDisplay": f"₹ {today_purchases:,.2f}",
                "todayPurchasesCount": today_purchases_count,
                "todayPurchasesDelta": today_purchases_delta,
                "stockValue": stock_value,
                "stockValueDisplay": f"₹ {stock_value:,.2f}",
                "stockItemsCount": active_skus_count,
                "lowStockCount": low_stock_count,
                "receivables": receivables,
                "receivablesDisplay": receivables_display,
                "receivablesOverdueCount": receivables_overdue_count,
                "receivablesOverdueDisplay": receivables_overdue_display,
                "payables": payables,
                "payablesDisplay": payables_display,
                "payablesDueCount": payables_due_count,
                "payablesDueDisplay": payables_due_display,
                "todayExpenses": today_expenses,
                "todayExpensesDisplay": f"₹ {today_expenses:,.2f}",
                "heldBills": held_bills,
                "grossMargin": gross_margin,
                "grossMarginDisplay": gross_margin_display,
                "salesTrend": sales_trend,
                "paymentSummary": payment_summary,
                "revenueExpense": revenue_expense,
                "recentInvoices": recent_invoices,
                "recentPurchases": recent_purchases,
                "recentPayments": recent_payments,
                "stockAdjustments": stock_adjustments,
            }
