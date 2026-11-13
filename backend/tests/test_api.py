import pytest
from fastapi.testclient import TestClient
import backend.app.database as db_mod
import backend.app.config as cfg_mod
from backend.app.main import app

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    test_db_dir = tmp_path_factory.mktemp("db")
    test_db = str(test_db_dir / "test_commercehub.db")

    cfg_mod.DB_PATH = test_db
    db_mod.DB_PATH = test_db

    holding_conn = db_mod.init_db(test_db)

    with TestClient(app) as c:
        yield c

    holding_conn.close()

def test_healthcheck(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["service"] == "CommerceHub"

def test_product_catalog(client):
    res = client.get("/api/products")
    assert res.status_code == 200
    prods = res.json()["products"]
    assert len(prods) >= 3

    # Inspect first product variants
    p1 = prods[0]
    assert len(p1["variants"]) >= 2
    assert p1["variants"][0]["stock_quantity"] > 0

def test_cart_calculation_endpoint(client):
    res = client.get("/api/products")
    variant = res.json()["products"][0]["variants"][0]
    sku_id = variant["id"]

    calc_res = client.post("/api/cart/calculate", json={
        "items": [{"sku_id": sku_id, "quantity": 1}],
        "shipping_method": "standard",
        "coupon_code": "WELCOME10"
    })
    assert calc_res.status_code == 200
    calc_data = calc_res.json()
    assert calc_data["subtotal"] == variant["price"]
    assert calc_data["discount_amount"] > 0
    assert calc_data["grand_total"] > 0

def test_order_checkout_inventory_decrement_and_restock(client):
    # 1. Get SKU initial stock
    prod_res = client.get("/api/products/titanium-cyberdeck-keyboard")
    assert prod_res.status_code == 200
    sku = prod_res.json()["variants"][0]
    initial_stock = sku["stock_quantity"]
    sku_id = sku["id"]

    # 2. Checkout 2 units
    checkout_res = client.post("/api/orders/checkout", json={
        "customer_name": "Jordan Vance",
        "customer_email": "jordan.vance@techcorp.io",
        "shipping_address": "742 Evergreen Terrace, Springfield, OR 97477",
        "shipping_method": "standard",
        "coupon_code": "WELCOME10",
        "items": [{"sku_id": sku_id, "quantity": 2}]
    })
    assert checkout_res.status_code == 201
    order = checkout_res.json()
    order_id = order["order_id"]
    assert order["order_number"].startswith("ORD-")
    assert order["status"] == "PAID"

    # 3. Verify stock was decremented
    chk_prod = client.get("/api/products/titanium-cyberdeck-keyboard")
    new_stock = chk_prod.json()["variants"][0]["stock_quantity"]
    assert new_stock == initial_stock - 2

    # 4. Attempt to checkout more than remaining stock (should fail 400)
    oversell_res = client.post("/api/orders/checkout", json={
        "customer_name": "Greedy Buyer",
        "customer_email": "greedy@buyer.com",
        "shipping_address": "123 Stockout Ave",
        "items": [{"sku_id": sku_id, "quantity": 99999}]
    })
    assert oversell_res.status_code == 400
    assert "Insufficient inventory" in oversell_res.json()["detail"]

    # 5. Transition order to PROCESSING
    proc_res = client.patch(f"/api/orders/{order_id}/status", json={"status": "PROCESSING"})
    assert proc_res.status_code == 200
    assert proc_res.json()["new_status"] == "PROCESSING"

    # 6. Cancel order and verify stock was restocked
    cancel_res = client.patch(f"/api/orders/{order_id}/status", json={"status": "CANCELLED"})
    assert cancel_res.status_code == 200
    assert cancel_res.json()["new_status"] == "CANCELLED"

    restocked_prod = client.get("/api/products/titanium-cyberdeck-keyboard")
    restocked_stock = restocked_prod.json()["variants"][0]["stock_quantity"]
    assert restocked_stock == initial_stock

def test_store_analytics(client):
    res = client.get("/api/analytics/store-metrics")
    assert res.status_code == 200
    metrics = res.json()
    assert "total_revenue" in metrics
    assert "completed_orders" in metrics
    assert "low_stock_skus_count" in metrics
