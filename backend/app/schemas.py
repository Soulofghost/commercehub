from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional

class CartItemSchema(BaseModel):
    sku_id: str
    quantity: int = Field(..., gt=0)

class CartCalculateRequest(BaseModel):
    items: List[CartItemSchema]
    shipping_method: str = "standard"
    coupon_code: Optional[str] = None

class CheckoutRequest(BaseModel):
    customer_name: str = Field(..., min_length=2, max_length=150)
    customer_email: str = Field(..., min_length=5, max_length=150)
    shipping_address: str = Field(..., min_length=5, max_length=250)
    shipping_method: str = "standard"
    coupon_code: Optional[str] = None
    items: List[CartItemSchema]

class OrderStatusUpdate(BaseModel):
    status: str
