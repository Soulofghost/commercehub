import uuid
import datetime
from fastapi import APIRouter, HTTPException, Query, status
from typing import Optional, List, Dict, Any

from backend.app.database import get_connection
from backend.app.schemas import CartCalculateRequest, CheckoutRequest, OrderStatusUpdate
from backend.app.engine.checkout_inventory import (
    calculate_cart_totals,
    validate_order_transition,
    SUPPORTED_COUPONS
)

router = APIRouter(prefix="/api", tags=["commerce"])

@router.get("/health")
def healthcheck():
    return {"status": "ok", "service": "CommerceHub", "version": "1.0.0"}

@router.get("/products")
def list_products(category: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM products WHERE 1=1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY created_at DESC;"
    cursor.execute(query, params)
    prods = cursor.fetchall()

    results = []
    for p in prods:
        cursor.execute("SELECT * FROM sku_variants WHERE product_id = ? ORDER BY price_override ASC;", (p["id"],))
        variants = [{
            "id": v["id"],
            "sku": v["sku"],
            "variant_name": v["variant_name"],
            "price": v["price_override"] or p["base_price"],
            "stock_quantity": v["stock_quantity"]
        } for v in cursor.fetchall()]

        results.append({
            "id": p["id"],
            "title": p["title"],
            "slug": p["slug"],
            "description": p["description"],
            "category": p["category"],
            "base_price": p["base_price"],
            "variants": variants
        })

    conn.close()
    return {"total": len(results), "products": results}

@router.get("/products/{id_or_slug}")
def get_product(id_or_slug: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM products WHERE id = ? OR slug = ?;", (id_or_slug, id_or_slug))
    p = cursor.fetchone()
    if not p:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")

    cursor.execute("SELECT * FROM sku_variants WHERE product_id = ?;", (p["id"],))
    variants = [{
        "id": v["id"],
        "sku": v["sku"],
        "variant_name": v["variant_name"],
        "price": v["price_override"] or p["base_price"],
        "stock_quantity": v["stock_quantity"]
    } for v in cursor.fetchall()]

    conn.close()
    return {
        "id": p["id"],
        "title": p["title"],
        "slug": p["slug"],
        "description": p["description"],
        "category": p["category"],
        "base_price": p["base_price"],
        "variants": variants
    }

@router.post("/cart/calculate")
def calculate_cart(payload: CartCalculateRequest):
    if not payload.items:
        return {
            "subtotal": 0.0,
            "discount_amount": 0.0,
            "applied_coupon": None,
            "shipping_cost": 0.0,
            "shipping_method": payload.shipping_method,
            "sales_tax": 0.0,
            "grand_total": 0.0,
            "item_count": 0,
            "items_detail": []
        }

    conn = get_connection()
    cursor = conn.cursor()

    items_detail = []
    calc_items = []

    for itm in payload.items:
        cursor.execute("""
        SELECT v.*, p.title as product_title, p.base_price
        FROM sku_variants v
        JOIN products p ON v.product_id = p.id
        WHERE v.id = ? OR v.sku = ?;
        """, (itm.sku_id, itm.sku_id))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=400, detail=f"Invalid SKU item: {itm.sku_id}")

        unit_price = row["price_override"] or row["base_price"]
        calc_items.append({"unit_price": unit_price, "quantity": itm.quantity})
        items_detail.append({
            "sku_id": row["id"],
            "sku": row["sku"],
            "product_title": row["product_title"],
            "variant_name": row["variant_name"],
            "unit_price": unit_price,
            "quantity": itm.quantity,
            "available_stock": row["stock_quantity"],
            "line_total": round(unit_price * itm.quantity, 2)
        })

    conn.close()

    totals = calculate_cart_totals(
        items=calc_items,
        shipping_method=payload.shipping_method,
        coupon_code=payload.coupon_code
    )
    totals["items_detail"] = items_detail
    return totals

@router.post("/orders/checkout", status_code=status.HTTP_201_CREATED)
def checkout_order(payload: CheckoutRequest):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Cart cannot be empty")

    conn = get_connection()
    cursor = conn.cursor()

    # Step 1: Validate stock & resolve prices
    resolved_items = []
    calc_items = []

    for itm in payload.items:
        cursor.execute("""
        SELECT v.*, p.title as product_title, p.base_price
        FROM sku_variants v
        JOIN products p ON v.product_id = p.id
        WHERE v.id = ? OR v.sku = ?;
        """, (itm.sku_id, itm.sku_id))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=400, detail=f"Invalid SKU: {itm.sku_id}")

        if row["stock_quantity"] < itm.quantity:
            conn.close()
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient inventory for {row['product_title']} ({row['variant_name']}). Requested: {itm.quantity}, Available: {row['stock_quantity']}"
            )

        unit_price = row["price_override"] or row["base_price"]
        line_total = round(unit_price * itm.quantity, 2)

        resolved_items.append({
            "sku_id": row["id"],
            "sku": row["sku"],
            "product_title": row["product_title"],
            "variant_name": row["variant_name"],
            "quantity": itm.quantity,
            "unit_price": unit_price,
            "line_total": line_total
        })
        calc_items.append({"unit_price": unit_price, "quantity": itm.quantity})

    # Step 2: Compute totals
    totals = calculate_cart_totals(
        items=calc_items,
        shipping_method=payload.shipping_method,
        coupon_code=payload.coupon_code
    )

    # Step 3: Atomically decrement stock and insert order
    order_id = str(uuid.uuid4())
    cursor.execute("SELECT COUNT(*) FROM orders;")
    order_seq = 1001 + cursor.fetchone()[0]
    order_number = f"ORD-{order_seq}"
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    cursor.execute("""
    INSERT INTO orders (
        id, order_number, customer_name, customer_email, shipping_address,
        subtotal, discount_amount, coupon_code, shipping_cost, sales_tax,
        grand_total, status, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PAID', ?, ?);
    """, (
        order_id, order_number, payload.customer_name, payload.customer_email,
        payload.shipping_address, totals["subtotal"], totals["discount_amount"],
        totals["applied_coupon"] or "", totals["shipping_cost"], totals["sales_tax"],
        totals["grand_total"], now_iso, now_iso
    ))

    for item in resolved_items:
        # Insert item
        cursor.execute("""
        INSERT INTO order_items (id, order_id, sku_id, product_title, variant_name, sku, quantity, unit_price, line_total)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            str(uuid.uuid4()), order_id, item["sku_id"], item["product_title"],
            item["variant_name"], item["sku"], item["quantity"], item["unit_price"], item["line_total"]
        ))

        # Decrement stock
        cursor.execute("""
        UPDATE sku_variants SET stock_quantity = stock_quantity - ? WHERE id = ?;
        """, (item["quantity"], item["sku_id"]))

    conn.commit()
    conn.close()

    return {
        "order_id": order_id,
        "order_number": order_number,
        "status": "PAID",
        "customer_name": payload.customer_name,
        "customer_email": payload.customer_email,
        "subtotal": totals["subtotal"],
        "discount_amount": totals["discount_amount"],
        "applied_coupon": totals["applied_coupon"],
        "shipping_cost": totals["shipping_cost"],
        "sales_tax": totals["sales_tax"],
        "grand_total": totals["grand_total"],
        "created_at": now_iso
    }

@router.get("/orders")
def list_orders(status_filter: Optional[str] = Query(None, alias="status")):
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM orders WHERE 1=1"
    params = []
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter.upper())

    query += " ORDER BY created_at DESC;"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "order_number": r["order_number"],
            "customer_name": r["customer_name"],
            "customer_email": r["customer_email"],
            "subtotal": r["subtotal"],
            "discount_amount": r["discount_amount"],
            "grand_total": r["grand_total"],
            "status": r["status"],
            "created_at": r["created_at"]
        })

    return {"total": len(results), "orders": results}

@router.get("/orders/{id_or_number}")
def get_order_details(id_or_number: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM orders WHERE id = ? OR order_number = ?;", (id_or_number, id_or_number))
    order = cursor.fetchone()
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="Order not found")

    o_id = order["id"]
    cursor.execute("SELECT * FROM order_items WHERE order_id = ?;", (o_id,))
    items = [{
        "sku": itm["sku"],
        "product_title": itm["product_title"],
        "variant_name": itm["variant_name"],
        "quantity": itm["quantity"],
        "unit_price": itm["unit_price"],
        "line_total": itm["line_total"]
    } for itm in cursor.fetchall()]

    conn.close()

    return {
        "id": order["id"],
        "order_number": order["order_number"],
        "customer_name": order["customer_name"],
        "customer_email": order["customer_email"],
        "shipping_address": order["shipping_address"],
        "subtotal": order["subtotal"],
        "discount_amount": order["discount_amount"],
        "coupon_code": order["coupon_code"],
        "shipping_cost": order["shipping_cost"],
        "sales_tax": order["sales_tax"],
        "grand_total": order["grand_total"],
        "status": order["status"],
        "created_at": order["created_at"],
        "updated_at": order["updated_at"],
        "items": items
    }

@router.patch("/orders/{id_or_number}/status")
def update_order_status(id_or_number: str, payload: OrderStatusUpdate):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM orders WHERE id = ? OR order_number = ?;", (id_or_number, id_or_number))
    order = cursor.fetchone()
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="Order not found")

    o_id = order["id"]
    curr_status = order["status"]

    valid, reason = validate_order_transition(curr_status, payload.status)
    if not valid:
        conn.close()
        raise HTTPException(status_code=400, detail=reason)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    target_status = payload.status.upper()

    # If cancelling, restock items back into inventory
    if target_status == "CANCELLED":
        cursor.execute("SELECT sku_id, quantity FROM order_items WHERE order_id = ?;", (o_id,))
        for itm in cursor.fetchall():
            cursor.execute("UPDATE sku_variants SET stock_quantity = stock_quantity + ? WHERE id = ?;",
                           (itm["quantity"], itm["sku_id"]))

    cursor.execute("UPDATE orders SET status = ?, updated_at = ? WHERE id = ?;", (target_status, now_iso, o_id))
    conn.commit()
    conn.close()

    return {
        "id": o_id,
        "order_number": order["order_number"],
        "previous_status": curr_status,
        "new_status": target_status,
        "updated_at": now_iso
    }

@router.get("/analytics/store-metrics")
def get_store_metrics():
    conn = get_connection()
    cursor = conn.cursor()

    # Total Sales (non cancelled)
    cursor.execute("SELECT COALESCE(SUM(grand_total), 0.0), COUNT(*) FROM orders WHERE status != 'CANCELLED';")
    tot_row = cursor.fetchone()
    revenue = round(tot_row[0], 2)
    orders_count = tot_row[1]

    # Low stock SKUs
    cursor.execute("""
    SELECT v.sku, v.variant_name, v.stock_quantity, p.title as product_title
    FROM sku_variants v
    JOIN products p ON v.product_id = p.id
    WHERE v.stock_quantity <= 20
    ORDER BY v.stock_quantity ASC;
    """)
    low_stock = [{
        "sku": r["sku"],
        "product_title": r["product_title"],
        "variant_name": r["variant_name"],
        "stock": r["stock_quantity"]
    } for r in cursor.fetchall()]

    conn.close()

    return {
        "total_revenue": revenue,
        "completed_orders": orders_count,
        "low_stock_skus_count": len(low_stock),
        "low_stock_inventory": low_stock
    }
