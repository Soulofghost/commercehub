import sqlite3
import datetime
import uuid
from typing import Optional
from backend.app.config import DB_PATH

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    if not path.startswith(":memory:") and "mode=memory" not in path:
        conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path: Optional[str] = None):
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        base_price REAL NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sku_variants (
        id TEXT PRIMARY KEY,
        product_id TEXT NOT NULL,
        sku TEXT UNIQUE NOT NULL,
        variant_name TEXT NOT NULL,
        price_override REAL,
        stock_quantity INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        order_number TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        customer_email TEXT NOT NULL,
        shipping_address TEXT NOT NULL,
        subtotal REAL NOT NULL,
        discount_amount REAL DEFAULT 0.0,
        coupon_code TEXT DEFAULT '',
        shipping_cost REAL NOT NULL,
        sales_tax REAL NOT NULL,
        grand_total REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'PAID',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        sku_id TEXT NOT NULL,
        product_title TEXT NOT NULL,
        variant_name TEXT NOT NULL,
        sku TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        line_total REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    );
    """)

    # Seed products if empty
    cursor.execute("SELECT COUNT(*) FROM products;")
    if cursor.fetchone()[0] == 0:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        p1_id = "prod-cyberdeck-kb"
        cursor.execute("""
        INSERT INTO products (id, title, slug, description, category, base_price, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            p1_id,
            "Titanium Cyberdeck Mechanical Keyboard",
            "titanium-cyberdeck-keyboard",
            "CNC machined aerospace-grade titanium frame, hot-swappable switches, PBT dye-sublimated keycaps, and QMK/VIA firmware.",
            "Hardware & Peripherals",
            249.00,
            now
        ))

        cursor.executemany("""
        INSERT INTO sku_variants (id, product_id, sku, variant_name, price_override, stock_quantity)
        VALUES (?, ?, ?, ?, ?, ?);
        """, [
            (str(uuid.uuid4()), p1_id, "KB-TITAN-BLU", "Cherry MX Blue (Clicky)", 249.00, 35),
            (str(uuid.uuid4()), p1_id, "KB-TITAN-BRN", "Gateron Silent Brown (Tactile)", 259.00, 20),
            (str(uuid.uuid4()), p1_id, "KB-TITAN-RED", "Kailh Box Red (Linear)", 249.00, 15)
        ])

        p2_id = "prod-quantum-oled"
        cursor.execute("""
        INSERT INTO products (id, title, slug, description, category, base_price, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            p2_id,
            "Quantum-Dot OLED 34-Inch Curved Display",
            "quantum-oled-34-curved",
            "3440x1440 WQHD resolution, 0.03ms GtG response time, true 10-bit color, 99.3% DCI-P3 gamut, and dual Thunderbolt 4 ports.",
            "Displays & Monitors",
            899.00,
            now
        ))

        cursor.executemany("""
        INSERT INTO sku_variants (id, product_id, sku, variant_name, price_override, stock_quantity)
        VALUES (?, ?, ?, ?, ?, ?);
        """, [
            (str(uuid.uuid4()), p2_id, "MON-OLED-175", "175Hz Refresh / Stealth Matte", 899.00, 18),
            (str(uuid.uuid4()), p2_id, "MON-OLED-240", "240Hz Refresh / Glossy Pro", 999.00, 12)
        ])

        p3_id = "prod-ergo-chair"
        cursor.execute("""
        INSERT INTO products (id, title, slug, description, category, base_price, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            p3_id,
            "AeroMesh Ergonomic Task Chair",
            "aeromesh-ergonomic-task-chair",
            "Multi-directional dynamic lumbar stabilization, 4D adjustable armrests, breathable elastomer mesh, and aluminum base.",
            "Furniture & Workspace",
            495.00,
            now
        ))

        cursor.executemany("""
        INSERT INTO sku_variants (id, product_id, sku, variant_name, price_override, stock_quantity)
        VALUES (?, ?, ?, ?, ?, ?);
        """, [
            (str(uuid.uuid4()), p3_id, "CHR-AERO-BLK", "Onyx Black Mesh", 495.00, 25),
            (str(uuid.uuid4()), p3_id, "CHR-AERO-SLV", "Lunar Silver Mesh", 525.00, 14)
        ])

    conn.commit()
    return conn
