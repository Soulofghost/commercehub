"""
E-Commerce Checkout, Cart Calculation & Order State Machine Engine
Calculates subtotals, shipping tiers, discounts, taxes, and manages order lifecycle transitions.
"""

from typing import List, Dict, Any, Optional, Tuple

VALID_ORDER_STATUSES = {"PENDING", "PAID", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"}

ALLOWED_ORDER_TRANSITIONS: Dict[str, set] = {
    "PENDING": {"PAID", "CANCELLED"},
    "PAID": {"PROCESSING", "CANCELLED"},
    "PROCESSING": {"SHIPPED", "CANCELLED"},
    "SHIPPED": {"DELIVERED"},
    "DELIVERED": set(),
    "CANCELLED": set()
}

SUPPORTED_COUPONS = {
    "WELCOME10": {"type": "PERCENT", "value": 10.0, "min_subtotal": 0.0},
    "SAVE20": {"type": "PERCENT", "value": 20.0, "min_subtotal": 50.0},
    "FREESHIP": {"type": "FREE_SHIPPING", "value": 0.0, "min_subtotal": 25.0},
    "VIP50": {"type": "FIXED", "value": 50.0, "min_subtotal": 150.0}
}


def calculate_cart_totals(
    items: List[Dict[str, Any]],
    shipping_method: str = "standard",
    coupon_code: Optional[str] = None,
    tax_rate: float = 0.0825
) -> Dict[str, Any]:
    """
    Computes cart subtotal, discount deductions, shipping freight, taxes, and final payable total.
    """
    subtotal = 0.0
    for itm in items:
        price = float(itm["unit_price"])
        qty = int(itm["quantity"])
        if qty <= 0:
            raise ValueError("Item quantity must be greater than zero")
        if price < 0:
            raise ValueError("Price cannot be negative")
        subtotal += price * qty

    subtotal = round(subtotal, 2)

    # Shipping Calculation
    shipping_method = shipping_method.lower()
    is_free_eligible = subtotal >= 100.00
    
    if shipping_method == "express":
        shipping_cost = 10.00 if is_free_eligible else 25.00
    else:
        shipping_cost = 0.00 if is_free_eligible else 15.00

    # Discount Calculation
    discount_amount = 0.0
    applied_coupon = None

    if coupon_code:
        code_upper = coupon_code.strip().upper()
        if code_upper in SUPPORTED_COUPONS:
            coupon = SUPPORTED_COUPONS[code_upper]
            if subtotal >= coupon["min_subtotal"]:
                applied_coupon = code_upper
                if coupon["type"] == "PERCENT":
                    discount_amount = round((subtotal * coupon["value"]) / 100.0, 2)
                elif coupon["type"] == "FIXED":
                    discount_amount = round(min(subtotal, coupon["value"]), 2)
                elif coupon["type"] == "FREE_SHIPPING":
                    shipping_cost = 0.00
            else:
                applied_coupon = None

    taxable_base = max(0.0, round(subtotal - discount_amount, 2))
    sales_tax = round(taxable_base * tax_rate, 2)
    grand_total = round(taxable_base + shipping_cost + sales_tax, 2)

    return {
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "applied_coupon": applied_coupon,
        "shipping_cost": shipping_cost,
        "shipping_method": shipping_method,
        "sales_tax": sales_tax,
        "tax_rate": tax_rate,
        "grand_total": grand_total,
        "item_count": sum(int(i["quantity"]) for i in items)
    }


def validate_order_transition(current_status: str, new_status: str) -> Tuple[bool, str]:
    """
    Validates state machine transitions for order lifecycle.
    """
    curr = current_status.upper()
    target = new_status.upper()

    if curr not in VALID_ORDER_STATUSES:
        return False, f"Invalid current status: {curr}"
    if target not in VALID_ORDER_STATUSES:
        return False, f"Invalid target status: {target}"

    if curr == target:
        return True, "No status change requested"

    allowed = ALLOWED_ORDER_TRANSITIONS.get(curr, set())
    if target not in allowed:
        return False, f"Cannot transition order from {curr} to {target}"

    return True, "Transition authorized"
