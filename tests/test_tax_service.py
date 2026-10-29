"""Unit tests for Indian GST Tax Engine."""
import pytest
from services.tax_service import TaxService, tax_service


def test_intra_state_gst_calculation():
    items = [
        {"price": 100.0, "qty": 2.0, "tax_rate": 18.0}
    ]
    # Company in Tamilnadu, customer in Tamilnadu (or CASH)
    result = tax_service.calculate_voucher_totals(items, company_state="Tamilnadu", customer_state="Tamilnadu")
    
    assert result["subtotal"] == 200.0
    assert result["taxable_amount"] == 200.0
    assert result["cgst_amount"] == 18.0  # 9% of 200
    assert result["sgst_amount"] == 18.0  # 9% of 200
    assert result["igst_amount"] == 0.0
    assert result["total_tax"] == 36.0
    assert result["grand_total"] == 236.0
    assert result["round_off"] == 0.0


def test_inter_state_gst_calculation():
    items = [
        {"price": 500.0, "qty": 1.0, "tax_rate": 18.0}
    ]
    # Company in Tamilnadu, customer in Karnataka
    result = tax_service.calculate_voucher_totals(items, company_state="Tamilnadu", customer_state="Karnataka")
    
    assert result["subtotal"] == 500.0
    assert result["taxable_amount"] == 500.0
    assert result["cgst_amount"] == 0.0
    assert result["sgst_amount"] == 0.0
    assert result["igst_amount"] == 90.0  # 18% of 500
    assert result["total_tax"] == 90.0
    assert result["grand_total"] == 590.0


def test_tax_inclusive_pricing():
    # Item price is ₹118 tax-inclusive at 18% GST -> taxable is 100, tax is 18
    line = TaxService.calculate_line_item(price=118.0, qty=1.0, tax_rate=18.0, is_tax_inclusive=True)
    assert line["taxable_amount"] == 100.0
    assert line["tax_amount"] == 18.0
    assert line["cgst_amount"] == 9.0
    assert line["sgst_amount"] == 9.0
    assert line["line_total"] == 118.0


def test_fractional_weight_and_round_off():
    # 0.250 kg of vegetables at ₹75/kg -> gross = ₹18.75, 5% GST = ₹0.94 -> total = ₹19.69
    # Auto round-off should round to ₹20.00 with round_off = +0.31
    items = [
        {"price": 75.0, "qty": 0.250, "tax_rate": 5.0}
    ]
    result = tax_service.calculate_voucher_totals(items, auto_round=True)
    assert result["subtotal"] == 18.75
    assert result["grand_total"] == 20.0
    assert round(result["round_off"], 2) == 0.31

