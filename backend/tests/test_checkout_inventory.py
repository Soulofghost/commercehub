import pytest
from backend.app.engine.checkout_inventory import (
    calculate_cart_totals,
    validate_order_transition
)

def test_cart_calculation_under_threshold():
    items = [{"unit_price": 40.0, "quantity": 2}]  # Subtotal = $80.00
    res = calculate_cart_totals(items, shipping_method="standard")

    assert res["subtotal"] == 80.0
    assert res["shipping_cost"] == 15.0  # Standard shipping (< $100)
    assert res["sales_tax"] == 6.60      # 80 * 0.0825
    assert res["grand_total"] == 101.60

def test_cart_calculation_free_shipping_tier():
    items = [{"unit_price": 120.0, "quantity": 1}]  # Subtotal = $120.00
    res = calculate_cart_totals(items, shipping_method="standard")

    assert res["subtotal"] == 120.0
    assert res["shipping_cost"] == 0.0  # Free shipping (>= $100)
    assert res["sales_tax"] == 9.90
    assert res["grand_total"] == 129.90

def test_cart_coupon_percent_discount():
    items = [{"unit_price": 200.0, "quantity": 1}]
    res = calculate_cart_totals(items, coupon_code="WELCOME10")

    assert res["subtotal"] == 200.0
    assert res["discount_amount"] == 20.0  # 10% off
    assert res["applied_coupon"] == "WELCOME10"
    taxable = 180.0
    assert res["sales_tax"] == 14.85  # 180 * 0.0825
    assert res["grand_total"] == 194.85

def test_validate_order_transition():
    ok, _ = validate_order_transition("PAID", "PROCESSING")
    assert ok is True

    ok, _ = validate_order_transition("PROCESSING", "SHIPPED")
    assert ok is True

    ok, _ = validate_order_transition("SHIPPED", "DELIVERED")
    assert ok is True

    # Terminal state
    ok, _ = validate_order_transition("DELIVERED", "CANCELLED")
    assert ok is False

    ok, _ = validate_order_transition("CANCELLED", "PAID")
    assert ok is False
