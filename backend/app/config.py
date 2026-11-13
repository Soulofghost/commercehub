import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "commercehub.db"))
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
DEFAULT_SALES_TAX_RATE = 0.0825  # 8.25% standard sales tax
FREE_SHIPPING_THRESHOLD = 100.00
STANDARD_SHIPPING_FEE = 15.00
EXPRESS_SHIPPING_FEE = 25.00
