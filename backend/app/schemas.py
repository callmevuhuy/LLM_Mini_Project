from datetime import datetime
import re

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class VariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku: str
    attributes: dict[str, str]
    unit_price: int
    currency: str
    available_quantity: int


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    description: str
    image_url: str
    aliases: list[str]
    variants: list[VariantRead]


class HealthRead(BaseModel):
    status: str
    database: str
    product_count: int = Field(ge=0)


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DemoSessionRead(BaseModel):
    active: bool
    expires_at: int


class CartItemWrite(StrictRequest):
    sku: str = Field(min_length=1, max_length=80)
    quantity: StrictInt = Field(ge=1, le=99)


class CartItemRead(BaseModel):
    sku: str
    product_name: str
    attributes: dict[str, str]
    quantity: int
    unit_price: int
    currency: str
    available_quantity: int
    line_total: int


class CartRead(BaseModel):
    items: list[CartItemRead]
    subtotal: int


class CheckoutRequest(StrictRequest):
    recipient_name: str = Field(min_length=2, max_length=120)
    phone_number: str = Field(min_length=8, max_length=30)
    delivery_address: str = Field(min_length=10, max_length=500)

    @field_validator("recipient_name", "phone_number", "delivery_address")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Trường này không được để trống.")
        return value

    @field_validator("phone_number")
    @classmethod
    def validate_demo_phone(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9+()\-\s]{8,30}", value) or sum(char.isdigit() for char in value) < 8:
            raise ValueError("Số điện thoại không đúng định dạng.")
        return value


class OrderItemRead(BaseModel):
    sku: str
    product_name: str
    variant: dict[str, str]
    quantity: int
    unit_price: int
    line_total: int


class OrderRead(BaseModel):
    id: str
    status: str
    recipient_name: str
    phone_number: str
    delivery_address: str
    items: list[OrderItemRead]
    total_amount: int
    created_at: datetime


class ChatMessageWrite(StrictRequest):
    message: str = Field(min_length=1, max_length=1500)
    client_message_id: str = Field(min_length=8, max_length=64)


class ChatMessageRead(BaseModel):
    route: str
    message: str
    order_id: str | None = None
