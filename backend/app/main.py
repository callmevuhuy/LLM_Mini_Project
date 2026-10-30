from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import json
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
from pathlib import Path
import sys
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.rag import RAGIndex, generate_grounded_answer, DEFAULT_BUNDLE_PATH
from src.router import route_message

_active_rag_index: RAGIndex | None = None
ACTIVE_INDEX_POINTER = REPO_ROOT / "artifacts" / "active_index.json"


def get_active_rag_index() -> RAGIndex:
    global _active_rag_index
    bundle_name = "index_bundle.json"
    if ACTIVE_INDEX_POINTER.exists():
        pointer = json.loads(ACTIVE_INDEX_POINTER.read_text(encoding="utf-8"))
        bundle_name = pointer.get("bundle", "")
        if bundle_name not in {"index_bundle.json", "index_bundle_v1_1.json"}:
            raise ValueError("Active index pointer contains an invalid bundle name")
    bundle_file = REPO_ROOT / "artifacts" / bundle_name
    if _active_rag_index is None or _active_rag_index.manifest_meta.get("index_bundle") != bundle_name:
        if not bundle_file.exists():
            from src.indexer import run_indexing
            _active_rag_index = run_indexing(output_bundle=str(bundle_file), version="1.0")
        else:
            _active_rag_index = RAGIndex.load(bundle_file)
        _active_rag_index.manifest_meta["index_bundle"] = bundle_name
    return _active_rag_index


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Prepare the SQLite schema and seed data before accepting API requests."""
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
    allow_headers=["Content-Type", "X-User-Role", "X-Demo-Role-Token"],
)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    """Assign a correlation ID to the request and expose it on the response."""
    request_id = uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def require_allowed_origin(request: Request) -> None:
    """Reject browser writes from origins outside the local demo allowlist."""
    origin = request.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        raise HTTPException(status_code=403, detail="Origin không được phép.")


def resolve_demo_role(request: Request) -> str:
    """Resolve demo roles only when the caller presents a server-configured token."""
    role = request.headers.get("x-user-role", "customer").lower()
    if role == "customer":
        return role
    token_env = {"staff": "DEMO_STAFF_TOKEN", "admin": "DEMO_ADMIN_TOKEN"}.get(role)
    expected = os.getenv(token_env, "") if token_env else ""
    provided = request.headers.get("x-demo-role-token", "")
    if not expected or not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Vai trò demo không hợp lệ hoặc chưa được cấu hình.")
    return role


def token_digest(token: str) -> str:
    """Hash the opaque session cookie before looking it up in the database."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_current_session(
    request: Request, db: Session = Depends(get_db)
) -> DemoSession:
    """Resolve a non-expired demo session from its HttpOnly cookie."""
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
    """Return the session's cart, creating it in the current transaction if absent."""
    cart = db.scalar(select(Cart).where(Cart.session_id == session_id))
    if cart is None:
        cart = Cart(session_id=session_id)
        db.add(cart)
        db.flush()
    return cart


def load_cart_items(db: Session, cart_id: int) -> list[CartItemRead]:
    """Join cart rows to trusted catalog data and calculate display line totals."""
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
    """Build an API response from the order's persisted catalog snapshots."""
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
    """Report API/database readiness and the number of catalog products."""
    return {"status": "ok", "database": "sqlite", "product_count": db.query(Product).count()}


@app.get("/api/v1/products", response_model=list[ProductRead], tags=["catalog"])
def list_products(
    q: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=60),
    db: Session = Depends(get_db),
):
    """List active catalog products, optionally filtering by text and category."""
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
    """Return one active product with variants, prices, and current stock."""
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
    """Resume a valid demo session or issue a new opaque HttpOnly cookie."""
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
    """Return active session status without exposing its internal database ID."""
    return {"active": True, "expires_at": demo_session.expires_at}


@app.get("/api/v1/cart", response_model=CartRead, tags=["cart"])
def read_cart(
    db: Session = Depends(get_db),
    demo_session: DemoSession = Depends(get_current_session),
):
    """Read the caller's cart and calculate its subtotal from SQLite prices."""
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
    """Add a catalog SKU after checking its active state and available inventory."""
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
    """Replace a cart item's quantity after validating its SKU and inventory."""
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
    """Delete one SKU only from the authenticated session's cart."""
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
    """Create a pending order using server-owned prices and the caller's cart.

    Checkout rechecks inventory, snapshots catalog values, writes an audit record,
    and clears the cart. It does not collect payment or reserve/decrement stock.
    """
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
    """List only orders owned by the authenticated demo session."""
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
    """Fetch an order only when its owner is the authenticated demo session."""
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
    """Route a chat turn through extraction, catalog checks, and controlled actions.

    The LLM only classifies intent and extracts candidate fields. The backend then
    checks idempotency, rate limits, catalog matches, stock, required fields, order
    ownership, and allowed order state. Only deterministic checks authorize writes.
    Chat logs keep operational metadata and the response, not the raw user message.
    """
    require_allowed_origin(request)
    # Replay the saved response for a repeated key so a browser retry cannot create
    # a duplicate order or repeat another chat side effect.
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
    user_role = resolve_demo_role(request)

    route_decision = route_message(payload.message)

    if route_decision.primary_route == "knowledge_query":
        rag_index = get_active_rag_index()
        retrieved = rag_index.retrieve(payload.message, user_role=user_role)
        rag_res = generate_grounded_answer(payload.message, retrieved, user_role=user_role)
        answer = {
            "route": "knowledge_query",
            "status": rag_res["status"],
            "message": rag_res["answer"],
            "citations": rag_res["citations"],
            "missing_information": rag_res.get("missing_information", "")
        }
        db.add(ChatLog(session_id=demo_session.id, client_message_id=payload.client_message_id,
            request_id=request.state.request_id, model_id="rag-ngram-v1", prompt_version=PROMPT_VERSION,
            intent="knowledge_query", validation_status="valid", route="knowledge_query",
            latency_ms=5, retry_count=0, response_payload=answer, created_at=datetime.now(timezone.utc)))
        db.commit()
        return answer

    if route_decision.primary_route == "safety_adversarial" and not route_decision.order_query:
        answer = {
            "route": "handoff",
            "status": "access_denied",
            "message": "Yêu cầu bị từ chối: Hệ thống không chấp nhận các lệnh can thiệp bảo mật, xóa dữ liệu hoặc truy cập nội bộ.",
            "citations": []
        }
        db.add(ChatLog(session_id=demo_session.id, client_message_id=payload.client_message_id,
            request_id=request.state.request_id, model_id="rag-v1", prompt_version=PROMPT_VERSION,
            intent="safety_adversarial", validation_status="rejected", route="handoff",
            latency_ms=1, retry_count=0, response_payload=answer, created_at=datetime.now(timezone.utc)))
        db.commit()
        return answer

    pending_followup = False
    if route_decision.primary_route == "handoff":
        pending_followup = db.scalar(select(ChatState).where(
            ChatState.session_id == demo_session.id, ChatState.expires_at > int(time.time())
        )) is not None
    if route_decision.primary_route == "handoff" and not pending_followup:
        answer = {"route": "handoff", "message": "Yêu cầu này cần nhân viên hỗ trợ. Đây là bản demo nên mình chưa gửi tin cho nhân viên thật; bạn có thể tiếp tục hỏi về sản phẩm, chính sách hoặc đơn nháp."}
        db.add(ChatLog(session_id=demo_session.id, client_message_id=payload.client_message_id,
            request_id=request.state.request_id, model_id="router-v1", prompt_version=PROMPT_VERSION,
            intent="unknown_or_handoff", validation_status="needs_human_review", route="handoff",
            latency_ms=1, retry_count=0, response_payload=answer, created_at=datetime.now(timezone.utc)))
        db.commit()
        return answer

    rag_mixed_res = None
    extract_target = payload.message
    if route_decision.primary_route == "mixed":
        k_query = route_decision.knowledge_query or payload.message
        rag_index = get_active_rag_index()
        retrieved = rag_index.retrieve(k_query, user_role=user_role)
        rag_mixed_res = generate_grounded_answer(k_query, retrieved, user_role=user_role)
        extract_target = route_decision.order_query or payload.message

    try:
        # Provider failures become a safe response and metadata-only log. No partial
        # or malformed model output is allowed to reach business handling.
        result = await extract(extract_target)
    except ProviderError as exc:
        answer = {"route": "error", "message": "Trợ lý đang gặp sự cố kết nối. Bạn thử lại sau hoặc tiếp tục đặt hàng bằng giỏ hàng nhé."}
        db.add(ChatLog(session_id=demo_session.id, client_message_id=payload.client_message_id,
            request_id=request.state.request_id, model_id=os.getenv("OLLAMA_MODEL", "fake-rules-v1"),
            prompt_version=PROMPT_VERSION, intent=None, validation_status="provider_error",
            route="error", error_type=exc.error_type, retry_count=exc.retries,
            response_payload=answer, created_at=datetime.now(timezone.utc)))
        db.commit()
        return answer

    # Schema validation checks structure, not factual correctness or authorization.
    # Treat every extracted field as untrusted until checked against backend state.
    data = result.data
    if data.intent not in {"create_order", "check_stock", "check_price", "update_order", "unknown_or_handoff"}:
        data.intent = "unknown_or_handoff"
    answer: dict = {"route": "handoff", "message": "Mình chưa xác định được yêu cầu. Bạn có thể hỏi giá, kiểm tra tồn kho, đặt hàng hoặc yêu cầu nhân viên hỗ trợ."}
    order_id = None
    # Resolve candidates exclusively against active SQLite catalog records. Model
    # output never supplies an authoritative SKU, price, stock value, or order state.
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
    # Load only this session's short-lived structured state and discard expired data.
    state = db.scalar(select(ChatState).where(ChatState.session_id == demo_session.id))
    now = int(time.time())
    pending = dict(state.pending_order or {}) if state and state.expires_at > now else {}
    if state and state.expires_at <= now:
        db.delete(state); state = None

    # Continue collecting only this owner's order, for at most 30 minutes. Store
    # structured fields only; the raw customer message is never persisted.
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
        # Ambiguous or missing catalog matches trigger clarification rather than
        # allowing the model to choose a product arbitrarily.
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
            # Price and availability answers are assembled from database rows,
            # never trusted from generated model text.
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
                    # Never guess missing quantity or recipient fields. Persist only
                    # structured, session-scoped pending state with a short TTL.
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
                                # Create a draft only after SKU, quantity, current
                                # stock, and every required delivery field pass checks.
                                order = Order(id=uuid4().hex, session_id=demo_session.id,status="pending_confirmation",recipient_name=pending["name"],phone_number=pending["phone"],delivery_address=pending["address"],total_amount=qty*variant.unit_price,created_at=datetime.now(timezone.utc))
                                order.items.append(OrderItem(sku=variant.sku,product_name_snapshot=product.name,variant_snapshot=variant.attributes or {},quantity=qty,unit_price_snapshot=variant.unit_price))
                                db.add(order); db.flush(); order_id=order.id
                                db.add(AuditLog(request_id=request.state.request_id,order_id=order.id,actor_session_id=demo_session.id,action="order.created_from_chat",details={"item_count":1,"total_amount":order.total_amount},created_at=datetime.now(timezone.utc)))
                                if state: db.delete(state)
                                answer={"route":"pending_confirmation","order_id":order.id,"message":f"Đã tạo đơn nháp #{order.id[:10].upper()} cho {qty} × {product.name}, tổng {order.total_amount:,}₫. Đơn đang chờ xác nhận; chưa thanh toán hoặc trừ kho."}
    elif data.intent == "update_order":
        # Update only this owner's pending, single-item draft. A supplied reference
        # must resolve to one order; inventory is checked again before the write.
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

    if rag_mixed_res:
        answer["route"] = "mixed"
        answer["status"] = rag_mixed_res["status"]
        answer["citations"] = rag_mixed_res["citations"]
        answer["message"] = f"{rag_mixed_res['answer']}\n\n[Thao tác đơn hàng]: {answer['message']}"

    # Save operational metadata and the response only. Exclude raw user messages
    # and extracted delivery details from the chat log.
    db.add(ChatLog(session_id=demo_session.id,client_message_id=payload.client_message_id,
        request_id=request.state.request_id,model_id=result.model_id,prompt_version=PROMPT_VERSION,
        intent=data.intent,validation_status=result.validation_status,route=answer["route"],
        latency_ms=result.latency_ms,input_tokens=result.input_tokens,output_tokens=result.output_tokens,
        retry_count=result.retry_count,response_payload=answer,created_at=datetime.now(timezone.utc)))
    db.commit()
    return answer


@app.get("/api/v1/rag/status")
def get_rag_status():
    index = get_active_rag_index()
    return {
        "active_version": index.manifest_meta.get("corpus_version", "1.0"),
        "total_documents": index.manifest_meta.get("total_documents", 12),
        "total_chunks": len(index.chunks),
        "embedding_model": index.manifest_meta.get("embedding_model", "deterministic-ngram-tfidf-v1"),
        "created_at": index.manifest_meta.get("created_at"),
    }


@app.post("/api/v1/rag/reindex")
def trigger_rag_reindex(
    request: Request,
    version: Literal["1.0", "1.1"] = Query("1.1"),
    db: Session = Depends(get_db),
    demo_session: DemoSession = Depends(get_current_session),
):
    global _active_rag_index
    require_allowed_origin(request)
    user_role = resolve_demo_role(request)
    if user_role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên (Admin) mới có quyền re-index.")
    
    target_bundle = REPO_ROOT / "artifacts" / ("index_bundle_v1_1.json" if version == "1.1" else "index_bundle.json")
    if not target_bundle.exists():
        from src.indexer import run_indexing
        if version == "1.1":
            run_indexing(corpus_dir=REPO_ROOT / "data" / "corpus_v1_1", manifest_path=REPO_ROOT / "data_config" / "corpus_manifest_v1_1.json", output_bundle=str(target_bundle), version="1.1")
        else:
            run_indexing(output_bundle=str(target_bundle), version="1.0")
    
    new_index = RAGIndex.load(target_bundle)
    req_id = getattr(request.state, "request_id", uuid4().hex)
    db.add(AuditLog(request_id=req_id, action=f"rag_reindex_{version}",
        actor_session_id=demo_session.id, details={"version": version, "total_chunks": len(new_index.chunks)},
        created_at=datetime.now(timezone.utc)))
    db.commit()
    bundle_name = target_bundle.name
    pointer_path = ACTIVE_INDEX_POINTER.with_name(f".{ACTIVE_INDEX_POINTER.name}.{uuid4().hex}.tmp")
    try:
        pointer_path.write_text(json.dumps({"bundle": bundle_name}), encoding="utf-8")
        os.replace(pointer_path, ACTIVE_INDEX_POINTER)
    finally:
        pointer_path.unlink(missing_ok=True)
    new_index.manifest_meta["index_bundle"] = bundle_name
    _active_rag_index = new_index
    return {
        "status": "reindexed",
        "active_version": new_index.manifest_meta.get("corpus_version", version),
        "total_chunks": len(_active_rag_index.chunks),
        "message": f"Chỉ mục RAG phiên bản {version} đã được kích hoạt thành công."
    }
