"""
Indian GST Tax Calculation Engine for Anti Matrix Billing.
Handles Intra-state (CGST + SGST), Inter-state (IGST), Tax-inclusive, Tax-exclusive,
and round-off calculations with decimal safety.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional


def round_money(val: Decimal) -> Decimal:
    """Rounds a Decimal value to 2 decimal places using ROUND_HALF_UP."""
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def round_qty(val: Decimal) -> Decimal:
    """Rounds a quantity to 3 decimal places (e.g. 0.250 kg)."""
    return val.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


class TaxService:
    @staticmethod
    def is_interstate(company_state: str, customer_state: Optional[str] = None, sale_type: Optional[str] = None) -> bool:
        """Determine if transaction is inter-state (IGST) or intra-state (CGST+SGST)."""
        if sale_type and sale_type.startswith("I/"):
            return True
        if not customer_state:
            return False
        c_state = (company_state or "Tamilnadu").strip().lower()
        cust_state = customer_state.strip().lower()
        if cust_state in ("", "cash", "local"):
            return False
        return c_state != cust_state

    @classmethod
    def calculate_line_item(
        cls,
        price: float,
        qty: float,
        tax_rate: float,
        discount_percent: float = 0.0,
        is_tax_inclusive: bool = False,
        is_interstate: bool = False
    ) -> Dict[str, Any]:
        """
        Calculates line item taxable value, tax split, and final line total.
        """
        d_price = Decimal(str(price))
        d_qty = Decimal(str(qty))
        d_tax_rate = Decimal(str(tax_rate))
        d_disc_pct = Decimal(str(discount_percent))

        gross_price = d_price * d_qty
        discount_amount = round_money(gross_price * (d_disc_pct / Decimal("100")))
        net_after_discount = gross_price - discount_amount

        if is_tax_inclusive and d_tax_rate > 0:
            # Net amount already includes tax
            # Taxable = Net / (1 + Rate / 100)
            taxable_amount = round_money(net_after_discount / (Decimal("1") + (d_tax_rate / Decimal("100"))))
            tax_amount = round_money(net_after_discount - taxable_amount)
            line_total = round_money(net_after_discount)
        else:
            taxable_amount = round_money(net_after_discount)
            tax_amount = round_money(taxable_amount * (d_tax_rate / Decimal("100")))
            line_total = round_money(taxable_amount + tax_amount)

        if is_interstate:
            cgst_rate = Decimal("0")
            cgst_amount = Decimal("0")
            sgst_rate = Decimal("0")
            sgst_amount = Decimal("0")
            igst_rate = d_tax_rate
            igst_amount = tax_amount
        else:
            half_rate = d_tax_rate / Decimal("2")
            cgst_rate = half_rate
            cgst_amount = round_money(tax_amount / Decimal("2"))
            sgst_rate = half_rate
            sgst_amount = tax_amount - cgst_amount  # Avoid penny discrepancy
            igst_rate = Decimal("0")
            igst_amount = Decimal("0")

        return {
            "price": float(d_price),
            "qty": float(d_qty),
            "tax_rate": float(d_tax_rate),
            "discount_amount": float(discount_amount),
            "taxable_amount": float(taxable_amount),
            "tax_amount": float(tax_amount),
            "cgst_rate": float(cgst_rate),
            "cgst_amount": float(cgst_amount),
            "sgst_rate": float(sgst_rate),
            "sgst_amount": float(sgst_amount),
            "igst_rate": float(igst_rate),
            "igst_amount": float(igst_amount),
            "line_total": float(line_total)
        }

    @classmethod
    def calculate_voucher_totals(
        cls,
        items: List[Dict[str, Any]],
        company_state: str = "Tamilnadu",
        customer_state: Optional[str] = None,
        sale_type: Optional[str] = None,
        auto_round: bool = True
    ) -> Dict[str, Any]:
        """
        Calculates voucher subtotal, aggregate taxes, round-off, and grand total.
        """
        is_inter = cls.is_interstate(company_state, customer_state, sale_type)

        subtotal = Decimal("0")
        taxable_total = Decimal("0")
        cgst_total = Decimal("0")
        sgst_total = Decimal("0")
        igst_total = Decimal("0")
        discount_total = Decimal("0")

        calculated_items = []
        for it in items:
            p = float(it.get("price") or 0.0)
            q = float(it.get("qty") or 0.0)
            rate = float(it.get("tax_rate") if it.get("tax_rate") is not None else 18.0)
            disc = float(it.get("discount_percent") or 0.0)
            inc = bool(it.get("is_tax_inclusive", False))

            calc = cls.calculate_line_item(
                price=p,
                qty=q,
                tax_rate=rate,
                discount_percent=disc,
                is_tax_inclusive=inc,
                is_interstate=is_inter
            )
            # Copy original item metadata and attach calculated numbers
            item_record = {**it, **calc}
            calculated_items.append(item_record)

            subtotal += Decimal(str(calc["price"])) * Decimal(str(calc["qty"]))
            taxable_total += Decimal(str(calc["taxable_amount"]))
            cgst_total += Decimal(str(calc["cgst_amount"]))
            sgst_total += Decimal(str(calc["sgst_amount"]))
            igst_total += Decimal(str(calc["igst_amount"]))
            discount_total += Decimal(str(calc["discount_amount"]))

        total_tax = cgst_total + sgst_total + igst_total
        raw_grand_total = taxable_total + total_tax

        if auto_round:
            rounded_total = raw_grand_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            round_off = rounded_total - raw_grand_total
        else:
            rounded_total = raw_grand_total
            round_off = Decimal("0")

        return {
            "items": calculated_items,
            "subtotal": float(round_money(subtotal)),
            "discount_total": float(round_money(discount_total)),
            "taxable_amount": float(round_money(taxable_total)),
            "cgst_amount": float(round_money(cgst_total)),
            "sgst_amount": float(round_money(sgst_total)),
            "igst_amount": float(round_money(igst_total)),
            "total_tax": float(round_money(total_tax)),
            "round_off": float(round_off),
            "grand_total": float(rounded_total),
            "is_interstate": is_inter
        }


tax_service = TaxService()

