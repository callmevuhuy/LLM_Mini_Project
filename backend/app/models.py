from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("sku", name="uq_product_variant_sku"),
        CheckConstraint("unit_price >= 0", name="ck_variant_price_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    sku: Mapped[str] = mapped_column(String(80), index=True)
    attributes: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    unit_price: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="VND")
    product: Mapped[Product] = relationship(back_populates="variants")
    inventory: Mapped["Inventory"] = relationship(
        back_populates="variant", cascade="all, delete-orphan", uselist=False
    )


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("available_quantity >= 0", name="ck_inventory_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("product_variants.id"), unique=True, index=True
    )
    available_quantity: Mapped[int] = mapped_column(Integer, default=0)
    variant: Mapped[ProductVariant] = relationship(back_populates="inventory")


class DemoSession(Base):
    __tablename__ = "demo_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[int] = mapped_column(Integer, index=True)
    cart: Mapped["Cart"] = relationship(back_populates="session", uselist=False)


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("demo_sessions.id"), unique=True)
    session: Mapped[DemoSession] = relationship(back_populates="cart")
    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart", cascade="all, delete-orphan"
    )


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "sku", name="uq_cart_sku"),
        CheckConstraint("quantity > 0", name="ck_cart_quantity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), index=True)
    sku: Mapped[str] = mapped_column(ForeignKey("product_variants.sku"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    cart: Mapped[Cart] = relationship(back_populates="items")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_order_total_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("demo_sessions.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True, default="pending_confirmation")
    recipient_name: Mapped[str] = mapped_column(String(120))
    phone_number: Mapped[str] = mapped_column(String(30))
    delivery_address: Mapped[str] = mapped_column(String(500))
    total_amount: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_item_quantity_positive"),
        CheckConstraint("unit_price_snapshot >= 0", name="ck_order_item_price_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    sku: Mapped[str] = mapped_column(ForeignKey("product_variants.sku"))
    product_name_snapshot: Mapped[str] = mapped_column(String(160))
    variant_snapshot: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_snapshot: Mapped[int] = mapped_column(Integer)
    order: Mapped[Order] = relationship(back_populates="items")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)
    actor_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("demo_sessions.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict[str, str | int | bool]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ChatState(Base):
    __tablename__ = "chat_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("demo_sessions.id"), unique=True)
    pending_order: Mapped[dict] = mapped_column(JSON, default=dict)
    expires_at: Mapped[int] = mapped_column(Integer, index=True)


class ChatLog(Base):
    __tablename__ = "chat_logs"
    __table_args__ = (
        UniqueConstraint("session_id", "client_message_id", name="uq_chat_idempotency"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("demo_sessions.id"), index=True)
    client_message_id: Mapped[str] = mapped_column(String(64))
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    model_id: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(80))
    intent: Mapped[str | None] = mapped_column(String(40), nullable=True)
    validation_status: Mapped[str] = mapped_column(String(40))
    route: Mapped[str] = mapped_column(String(40))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    response_payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
