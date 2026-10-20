from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import os
import secrets
import time
from uuid import uuid4
import re

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from .db import get_db
from .models import (
    AuditLog, Cart, CartItem, ChatLog, ChatState, DemoSession, Inventory, Order, OrderItem,
    Product, ProductVariant,
)
from .llm import PROMPT_VERSION, ProviderError, extract, norm
from .schemas import (
    CartItemRead, CartItemWrite, CartRead, CheckoutRequest, DemoSessionRead,
    HealthRead, OrderItemRead, OrderRead, ProductRead, ChatMessageWrite, ChatMessageRead,
)
from .seed import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Group 7 Shop API",
    description="Mock catalog and controlled demo checkout API.",
    version="0.2.0",
    lifespan=lifespan,
)
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
SESSION_COOKIE = "group7_demo_session"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
CHAT_RATE_WINDOW_SECONDS = 60
CHAT_RATE_LIMIT = 10
_chat_rate_windows: dict[int, tuple[int, int]] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request_id = uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def require_allowed_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        raise HTTPException(status_code=403, detail="Origin không được phép.")


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_current_session(
    request: Request, db: Session = Depends(get_db)
) -> DemoSession:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Phiên mua sắm đã hết hạn.")
    demo_session = db.scalar(
        select(DemoSession).where(
            DemoSession.token_hash == token_digest(token),
            DemoSession.expires_at > int(time.time()),
        )
    )
    if demo_session is None:
        raise HTTPException(status_code=401, detail="Phiên mua sắm đã hết hạn.")
    return demo_session


def get_or_create_cart(db: Session, session_id: int) -> Cart:
    cart = db.scalar(select(Cart).where(Cart.session_id == session_id))
    if cart is None:
        cart = Cart(session_id=session_id)
        db.add(cart)
        db.flush()
    return cart


def load_cart_items(db: Session, cart_id: int) -> list[CartItemRead]:
    rows = db.execute(
        select(CartItem, ProductVariant, Product, Inventory)
        .join(ProductVariant, ProductVariant.sku == CartItem.sku)
        .join(Product, Product.id == ProductVariant.product_id)
        .outerjoin(Inventory, Inventory.variant_id == ProductVariant.id)
        .where(CartItem.cart_id == cart_id)
        .order_by(CartItem.id)
    ).all()
    return [
        CartItemRead(
            sku=item.sku,
            product_name=product.name,
            attributes=variant.attributes or {},
            quantity=item.quantity,
            unit_price=variant.unit_price,
            currency=variant.currency,
            available_quantity=inventory.available_quantity if inventory else 0,
            line_total=item.quantity * variant.unit_price,
        )
        for item, variant, product, inventory in rows
    ]


def order_response(order: Order) -> OrderRead:
    return OrderRead(
        id=order.id,
        status=order.status,
        recipient_name=order.recipient_name,
        phone_number=order.phone_number,
        delivery_address=order.delivery_address,
        items=[
            OrderItemRead(
                sku=item.sku,
                product_name=item.product_name_snapshot,
                variant=item.variant_snapshot or {},
                quantity=item.quantity,
                unit_price=item.unit_price_snapshot,
                line_total=item.quantity * item.unit_price_snapshot,
            )
            for item in order.items
        ],
        total_amount=order.total_amount,
        created_at=order.created_at,
    )


@app.get("/api/v1/health", response_model=HealthRead, tags=["system"])
def health(db: Session = Depends(get_db)):
    return {"status": "ok", "database": "sqlite", "product_count": db.query(Product).count()}


@app.get("/api/v1/products", response_model=list[ProductRead], tags=["catalog"])
def list_products(
    q: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=60),
    db: Session = Depends(get_db),
):
    statement = (
        select(Product)
        .where(Product.active.is_(True))
        .options(selectinload(Product.variants).selectinload(ProductVariant.inventory))
        .order_by(Product.id)
    )
    if q and q.strip():
        term = f"%{q.strip()}%"
        statement = statement.where(
            or_(Product.name.ilike(term), Product.category.ilike(term), Product.description.ilike(term))
        )
    if category and category.lower() != "all":
        statement = statement.where(Product.category == category)

    products = db.scalars(statement).all()
    return [
        {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "description": product.description,
            "image_url": product.image_url,
            "aliases": product.aliases or [],
            "variants": [
                {
                    "sku": variant.sku,
                    "attributes": variant.attributes or {},
                    "unit_price": variant.unit_price,
                    "currency": variant.currency,
                    "available_quantity": variant.inventory.available_quantity if variant.inventory else 0,
                }
                for variant in product.variants
            ],
        }
        for product in products
    ]


@app.get("/api/v1/products/{product_id}", response_model=ProductRead, tags=["catalog"])
def get_product(product_id: int, db: Session = Depends(get_db)):
    statement = (
        select(Product)
        .where(Product.id == product_id, Product.active.is_(True))
        .options(selectinload(Product.variants).selectinload(ProductVariant.inventory))
    )
    product = db.scalar(statement)
    if product is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm.")
    return {
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "description": product.description,
        "image_url": product.image_url,
        "aliases": product.aliases or [],
        "variants": [
            {
                "sku": variant.sku,
                "attributes": variant.attributes or {},
                "unit_price": variant.unit_price,
                "currency": variant.currency,
                "available_quantity": variant.inventory.available_quantity if variant.inventory else 0,
            }
            for variant in product.variants
        ],
    }


@app.post("/api/v1/session", response_model=DemoSessionRead, tags=["demo session"])
def create_or_resume_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    require_allowed_origin(request)
    current_token = request.cookies.get(SESSION_COOKIE)
    demo_session = None
    if current_token:
        demo_session = db.scalar(
            select(DemoSession).where(
                DemoSession.token_hash == token_digest(current_token),
                DemoSession.expires_at > int(time.time()),
            )
        )
    if demo_session is None:
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        demo_session = DemoSession(
            token_hash=token_digest(token),
            created_at=datetime.now(timezone.utc),
            expires_at=now + SESSION_TTL_SECONDS,
        )
        db.add(demo_session)
        db.commit()
        response.set_cookie(
            key=SESSION_COOKIE,
            value=token,
            max_age=SESSION_TTL_SECONDS,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="lax",
            path="/",
        )
    return {"active": True, "expires_at": demo_session.expires_at}


@app.get("/api/v1/session", response_model=DemoSessionRead, tags=["demo session"])
def read_session(demo_session: DemoSession = Depends(get_current_session)):
    return {"active": True, "expires_at": demo_session.expires_at}


@app.get("/api/v1/cart", response_model=CartRead, tags=["cart"])
def read_cart(
    db: Session = Depends(get_db),
    demo_session: DemoSession = Depends(get_current_session),
):
    cart = get_or_create_cart(db, demo_session.id)
    db.commit()
    items = load_cart_items(db, cart.id)
    return {"items": items, "subtotal": sum(item.line_total for item in items)}


@app.post("/api/v1/cart/items", response_model=CartRead, tags=["cart"])
def add_cart_item(
    payload: CartItemWrite,
    request: Request,
    db: Session = Depends(get_db),
    demo_session: DemoSession = Depends(get_current_session),
):
    require_allowed_origin(request)
    variant = db.scalar(
        select(ProductVariant)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(ProductVariant.sku == payload.sku, Product.active.is_(True))
    )
    if variant is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phân loại sản phẩm.")
    inventory = db.scalar(select(Inventory).where(Inventory.variant_id == variant.id))
    available = inventory.available_quantity if inventory else 0
    cart = get_or_create_cart(db, demo_session.id)
    cart_item = db.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.sku == payload.sku)
    )
    new_quantity = payload.quantity + (cart_item.quantity if cart_item else 0)
    if new_quantity > available:
        raise HTTPException(status_code=409, detail=f"Chỉ còn {available} sản phẩm cho SKU này.")
    if cart_item:
        cart_item.quantity = new_quantity
    else:
        db.add(CartItem(cart_id=cart.id, sku=payload.sku, quantity=new_quantity))
    db.commit()
    items = load_cart_items(db, cart.id)
    return {"items": items, "subtotal": sum(item.line_total for item in items)}


@app.patch("/api/v1/cart/items/{sku}", response_model=CartRead, tags=["cart"])
def set_cart_item_quantity(
    sku: str,
    payload: CartItemWrite,
    request: Request,
    db: Session = Depends(get_db),
    demo_session: DemoSession = Depends(get_current_session),
):
    require_allowed_origin(request)
    if payload.sku != sku:
        raise HTTPException(status_code=422, detail="SKU trên URL và nội dung yêu cầu không khớp.")
    cart = db.scalar(select(Cart).where(Cart.session_id == demo_session.id))
    cart_item = db.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.sku == sku)
    ) if cart else None
    if cart_item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm trong giỏ.")
    inventory = db.scalar(
        select(Inventory)
        .join(ProductVariant, ProductVariant.id == Inventory.variant_id)
        .where(ProductVariant.sku == sku)
    )
    available = inventory.available_quantity if inventory else 0
    if payload.quantity > available:
        raise HTTPException(status_code=409, detail=f"Chỉ còn {available} sản phẩm cho SKU này.")
    cart_item.quantity = payload.quantity
    db.commit()
    items = load_cart_items(db, cart.id)
    return {"items": items, "subtotal": sum(item.line_total for item in items)}


@app.delete("/api/v1/cart/items/{sku}", status_code=status.HTTP_204_NO_CONTENT, tags=["cart"])
def delete_cart_item(
    sku: str,
    request: Request,
    db: Session = Depends(get_db),
    demo_session: DemoSession = Depends(get_current_session),
):
    require_allowed_origin(request)
    cart = db.scalar(select(Cart).where(Cart.session_id == demo_session.id))
    cart_item = db.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.sku == sku)
    ) if cart else None
    if cart_item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm trong giỏ.")
    db.delete(cart_item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/v1/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED, tags=["orders"])
def checkout(
    payload: CheckoutRequest,
    request: Request,
    db: Session = Depends(get_db),
    demo_session: DemoSession = Depends(get_current_session),
):
    require_allowed_origin(request)
    cart = db.scalar(select(Cart).where(Cart.session_id == demo_session.id))
    if cart is None:
        raise HTTPException(status_code=400, detail="Giỏ hàng đang trống.")
    cart_rows = db.execute(
        select(CartItem, ProductVariant, Product, Inventory)
        .join(ProductVariant, ProductVariant.sku == CartItem.sku)
        .join(Product, Product.id == ProductVariant.product_id)
        .outerjoin(Inventory, Inventory.variant_id == ProductVariant.id)
        .where(CartItem.cart_id == cart.id)
    ).all()
    if not cart_rows:
        raise HTTPException(status_code=400, detail="Giỏ hàng đang trống.")
    for cart_item, variant, product, inventory in cart_rows:
        available = inventory.available_quantity if inventory else 0
        if not product.active or cart_item.quantity > available:
            raise HTTPException(
                status_code=409,
                detail=f"Tồn kho của SKU {variant.sku} đã thay đổi. Vui lòng kiểm tra lại giỏ hàng.",
            )

    total = sum(item.quantity * variant.unit_price for item, variant, _, _ in cart_rows)
    order = Order(
        id=uuid4().hex,
        session_id=demo_session.id,
        status="pending_confirmation",
        recipient_name=payload.recipient_name,
        phone_number=payload.phone_number,
        delivery_address=payload.delivery_address,
        total_amount=total,
        created_at=datetime.now(timezone.utc),
    )
    for cart_item, variant, product, _ in cart_rows:
        order.items.append(
            OrderItem(
                sku=variant.sku,
                product_name_snapshot=product.name,
                variant_snapshot=variant.attributes or {},
                quantity=cart_item.quantity,
                unit_price_snapshot=variant.unit_price,
            )
        )
    db.add(order)
    # Materialize the order first so the audit row's foreign key is valid even
    # when the ORM cannot infer a relationship dependency from AuditLog.
    db.flush()
    db.add(
        AuditLog(
            request_id=request.state.request_id,
            order_id=order.id,
            actor_session_id=demo_session.id,
            action="order.created",
            details={"item_count": len(cart_rows), "total_amount": total},
            created_at=datetime.now(timezone.utc),
        )
    )
    for cart_item, _, _, _ in cart_rows:
        db.delete(cart_item)
    db.commit()
    db.refresh(order)
    return order_response(order)


@app.get("/api/v1/orders", response_model=list[OrderRead], tags=["orders"])
def list_orders(
    db: Session = Depends(get_db),
    demo_session: DemoSession = Depends(get_current_session),
):
    orders = db.scalars(
        select(Order)
        .where(Order.session_id == demo_session.id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    ).all()
    return [order_response(order) for order in orders]


@app.get("/api/v1/orders/{order_id}", response_model=OrderRead, tags=["orders"])
def get_order(
    order_id: str,
    db: Session = Depends(get_db),
    demo_session: DemoSession = Depends(get_current_session),
):
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.session_id == demo_session.id)
        .options(selectinload(Order.items))
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng.")
    return order_response(order)


@app.post("/api/v1/chat/messages", response_model=ChatMessageRead, tags=["chat"])
async def chat_message(
    payload: ChatMessageWrite, request: Request,
    db: Session = Depends(get_db), demo_session: DemoSession = Depends(get_current_session),
):
    require_allowed_origin(request)
    # Idempotency protects client retries from duplicating orders.
    previous = db.scalar(select(ChatLog).where(
        ChatLog.session_id == demo_session.id,
        ChatLog.client_message_id == payload.client_message_id,
    ))
    if previous:
        return previous.response_payload
    window = int(time.time()) // CHAT_RATE_WINDOW_SECONDS
    current_window, count = _chat_rate_windows.get(demo_session.id, (window, 0))
    if current_window != window:
        current_window, count = window, 0
    if count >= CHAT_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Bạn gửi tin nhắn hơi nhanh. Vui lòng thử lại sau một phút.")
    _chat_rate_windows[demo_session.id] = (current_window, count + 1)
    if len(_chat_rate_windows) > 5000:
        for session_id, (seen_window, _) in list(_chat_rate_windows.items()):
            if seen_window < window - 1:
                _chat_rate_windows.pop(session_id, None)
    try:
        result = await extract(payload.message)
    except ProviderError as exc:
        answer = {"route": "error", "message": "Trợ lý đang gặp sự cố kết nối. Bạn thử lại sau hoặc tiếp tục đặt hàng bằng giỏ hàng nhé."}
        db.add(ChatLog(session_id=demo_session.id, client_message_id=payload.client_message_id,
            request_id=request.state.request_id, model_id=os.getenv("OLLAMA_MODEL", "fake-rules-v1"),
            prompt_version=PROMPT_VERSION, intent=None, validation_status="provider_error",
            route="error", error_type=exc.error_type, retry_count=exc.retries,
            response_payload=answer, created_at=datetime.now(timezone.utc)))
        db.commit()
        return answer

    data = result.data
    if data.intent not in {"create_order", "check_stock", "check_price", "update_order", "unknown_or_handoff"}:
        data.intent = "unknown_or_handoff"
    answer: dict = {"route": "handoff", "message": "Mình chưa xác định được yêu cầu. Bạn có thể hỏi giá, kiểm tra tồn kho, đặt hàng hoặc yêu cầu nhân viên hỗ trợ."}
    order_id = None
    # Resolve product exclusively against active database catalog.
    products = db.scalars(select(Product).where(Product.active.is_(True)).options(
        selectinload(Product.variants).selectinload(ProductVariant.inventory))).all()
    query = norm(data.requested_product or payload.message)
    candidates = []
    for product in products:
        names = [product.name, *(product.aliases or [])]
        normalized_names = [norm(name) for name in names]
        if any(name and (name in query or query in name) for name in normalized_names):
            candidates.append(product)
        else:
            words = set(query.split())
            if any(len(words & set(name.split())) >= 2 for name in normalized_names):
                candidates.append(product)
    # A query without an explicit product can continue a pending order collection.
    state = db.scalar(select(ChatState).where(ChatState.session_id == demo_session.id))
    now = int(time.time())
    pending = dict(state.pending_order or {}) if state and state.expires_at > now else {}
    if state and state.expires_at <= now:
        db.delete(state); state = None

    # Continue only the pending order owned by this session; keep the structured
    # state short lived and never persist the raw chat message.
    if pending and data.intent in {"unknown_or_handoff", "create_order"} and not candidates:
        pending["name"] = data.name or pending.get("name")
        pending["phone"] = data.phone or pending.get("phone")
        pending["address"] = data.address or pending.get("address")
        pending["quantity"] = data.quantity or pending.get("quantity")
        if any((data.name, data.phone, data.address, data.quantity)):
            data.intent = "create_order"
            data.quantity = pending.get("quantity")
            variant_pending = db.scalar(select(ProductVariant).where(ProductVariant.sku == pending.get("sku")))
            product_pending = db.scalar(select(Product).where(Product.id == variant_pending.product_id)) if variant_pending else None
            candidates = [product_pending] if product_pending else []
        if state:
            state.pending_order = pending
            state.expires_at = now + 1800

    if data.intent in ("check_stock", "check_price", "create_order"):
        if len(candidates) != 1:
            answer = {"route":"needs_information", "message":"Bạn muốn hỏi về sản phẩm nào? Hãy gửi tên sản phẩm để mình tra cứu chính xác."}
        else:
            product = candidates[0]
            variants = product.variants
            normalized_message = norm(payload.message)
            mentioned = [
                v for v in variants
                if all(
                    re.search(rf"(?<!\w){re.escape(norm(str(value)))}(?!\w)", normalized_message)
                    for value in (v.attributes or {}).values() if value
                )
            ]
            if pending.get("sku"):
                mentioned = [v for v in variants if v.sku == pending.get("sku")]
            variant = mentioned[0] if len(mentioned) == 1 else (variants[0] if len(variants) == 1 else None)
            if data.intent == "check_price":
                prices = [f"{v.unit_price:,}₫" for v in ( [variant] if variant else variants )]
                answer = {"route":"answer", "message": f"{product.name} có giá {', '.join(prices)}" + ("." if variant else " tùy phân loại. Bạn muốn xem phân loại nào?")}
            elif data.intent == "check_stock":
                stock_variants = [variant] if variant else variants
                answer = {"route":"answer", "message": f"Tình trạng hàng của {product.name}: " + "; ".join(
                    f"{', '.join((v.attributes or {}).values()) or v.sku}: còn {v.inventory.available_quantity if v.inventory else 0}" for v in stock_variants) + ("." if variant else ". Bạn muốn kiểm tra phân loại cụ thể nào?")}
            elif data.intent == "create_order":
                if variant is None:
                    answer = {"route":"needs_information", "message":f"{product.name} có nhiều phân loại. Bạn muốn chọn: " + "; ".join(", ".join(v.attributes.values()) for v in variants) + "?"}
                else:
                    pending = {**pending, "sku":variant.sku,"quantity":data.quantity,"name":data.name or pending.get("name"),"phone":data.phone or pending.get("phone"),"address":data.address or pending.get("address")}
                    if data.quantity is None:
                        missing = ["số lượng"] + [label for key,label in (("name","tên người nhận"),("phone","số điện thoại demo"),("address","địa chỉ giao hàng demo")) if not pending.get(key)]
                        if state is None:
                            state = ChatState(session_id=demo_session.id, pending_order=pending, expires_at=now+1800); db.add(state)
                        else:
                            state.pending_order=pending; state.expires_at=now+1800
                        answer = {"route":"needs_information", "message":f"Bạn muốn đặt {product.name} ({', '.join(variant.attributes.values())}). Vui lòng gửi {', '.join(missing)}. Chỉ dùng thông tin giả cho demo nhé."}
                    else:
                        qty = data.quantity
                        available = variant.inventory.available_quantity if variant.inventory else 0
                        if qty > available:
                            answer = {"route":"out_of_stock", "message":f"Phân loại này hiện còn {available} sản phẩm, nên chưa thể đặt {qty}."}
                        else:
                            missing = [label for key,label in (("name","tên người nhận"),("phone","số điện thoại demo"),("address","địa chỉ giao hàng demo")) if not pending.get(key)]
                            if missing:
                                if state is None:
                                    state = ChatState(session_id=demo_session.id, pending_order=pending, expires_at=now+1800); db.add(state)
                                else:
                                    state.pending_order=pending; state.expires_at=now+1800
                                answer = {"route":"needs_information", "message":f"Mình đã ghi nhận {qty} × {product.name} ({', '.join(variant.attributes.values())}). Để tạo đơn nháp, bạn vui lòng gửi {', '.join(missing)}. Chỉ dùng thông tin giả cho demo nhé."}
                            else:
                                order = Order(id=uuid4().hex, session_id=demo_session.id,status="pending_confirmation",recipient_name=pending["name"],phone_number=pending["phone"],delivery_address=pending["address"],total_amount=qty*variant.unit_price,created_at=datetime.now(timezone.utc))
                                order.items.append(OrderItem(sku=variant.sku,product_name_snapshot=product.name,variant_snapshot=variant.attributes or {},quantity=qty,unit_price_snapshot=variant.unit_price))
                                db.add(order); db.flush(); order_id=order.id
                                db.add(AuditLog(request_id=request.state.request_id,order_id=order.id,actor_session_id=demo_session.id,action="order.created_from_chat",details={"item_count":1,"total_amount":order.total_amount},created_at=datetime.now(timezone.utc)))
                                if state: db.delete(state)
                                answer={"route":"pending_confirmation","order_id":order.id,"message":f"Đã tạo đơn nháp #{order.id[:10].upper()} cho {qty} × {product.name}, tổng {order.total_amount:,}₫. Đơn đang chờ xác nhận; chưa thanh toán hoặc trừ kho."}
    elif data.intent == "update_order":
        orders = db.scalars(select(Order).where(Order.session_id==demo_session.id,Order.status=="pending_confirmation").options(selectinload(Order.items))).all()
        ref=(data.order_reference or "").lower()
        matched=[o for o in orders if not ref or o.id.lower().startswith(ref)]
        if len(matched)==1 and len(matched[0].items)==1 and data.quantity:
            order=matched[0]; item=order.items[0]
            variant=db.scalar(select(ProductVariant).where(ProductVariant.sku==item.sku).options(selectinload(ProductVariant.inventory)))
            available=variant.inventory.available_quantity if variant and variant.inventory else 0
            if data.quantity>available:
                answer={"route":"out_of_stock","message":f"Kho hiện chỉ còn {available}; mình chưa thay đổi đơn."}
            else:
                item.quantity=data.quantity; item.unit_price_snapshot=variant.unit_price; order.total_amount=data.quantity*variant.unit_price
                db.add(AuditLog(request_id=request.state.request_id,order_id=order.id,actor_session_id=demo_session.id,action="order.updated_from_chat",details={"quantity":data.quantity,"total_amount":order.total_amount},created_at=datetime.now(timezone.utc)))
                answer={"route":"updated_order","order_id":order.id,"message":f"Đã cập nhật đơn nháp #{order.id[:10].upper()} thành số lượng {data.quantity}. Tổng mới {order.total_amount:,}₫; đơn vẫn chờ xác nhận."}
        else:
            answer={"route":"needs_information","message":"Mình chỉ có thể sửa đơn nháp đang chờ xác nhận. Vui lòng gửi mã đơn (10 ký tự đầu) và số lượng mới; nếu có nhiều sản phẩm cần chỉ rõ sản phẩm."}
    elif data.intent == "unknown_or_handoff" or data.requires_human_review:
        answer={"route":"handoff","message":"Yêu cầu này cần nhân viên hỗ trợ. Đây là bản demo nên mình chưa gửi tin cho nhân viên thật; bạn có thể tiếp tục hỏi về giá, tồn kho hoặc đơn nháp."}

    db.add(ChatLog(session_id=demo_session.id,client_message_id=payload.client_message_id,
        request_id=request.state.request_id,model_id=result.model_id,prompt_version=PROMPT_VERSION,
        intent=data.intent,validation_status=result.validation_status,route=answer["route"],
        latency_ms=result.latency_ms,input_tokens=result.input_tokens,output_tokens=result.output_tokens,
        retry_count=result.retry_count,response_payload=answer,created_at=datetime.now(timezone.utc)))
    db.commit()
    return answer
