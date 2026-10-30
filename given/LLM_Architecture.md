# Archived LLM Architecture — Phase A, B, C and D

> Describes only the inherited LLM application. It is not the architecture of the planned RAG extension.

## Components

```text
React/Vite storefront (127.0.0.1:5173)
  -> public catalog endpoints
  -> demo session cookie (HttpOnly, SameSite=Lax)
  -> cart and checkout endpoints
FastAPI (127.0.0.1:8000)
  -> request validation + session ownership
  -> SQLAlchemy models/routes and chat orchestration
  -> FakeLLM default / optional Ollama extraction adapter
  -> catalog + inventory + order business rules
  -> SQLite (backend/data/shop.db)
```

Frontend does not read seed files or connect to SQLite. Product listing/detail, cart, order and chat data are served through API. Chat sends only the current message and an idempotency UUID; it does not send owner, SKU, price, stock, or order state.

## Data model

- `products`: name, category, description, image URL, aliases, active flag.
- `product_variants`: unique SKU, JSON variant attributes, unit price/currency, product foreign key.
- `inventory`: available mock quantity, unique foreign key to variant.
- `demo_sessions`: SHA-256 hash of an opaque random session token, creation time and expiry. Raw token is held only in an HttpOnly cookie.
- `carts` / `cart_items`: one cart per session; cart lines store SKU and integer quantity. Prices are always read from the current catalog.
- `orders`: UUID-derived unguessable identifier, owner session, `pending_confirmation` state, recipient fields, server-calculated total and creation time.
- `order_items`: SKU and snapshots of product name, variant attributes, quantity and backend-confirmed unit price.
- `audit_logs`: request ID, order ID, actor session ID, action, non-PII metadata and timestamp.
- `chat_states`: one short-lived (30-minute) structured pending order per session, containing only SKU/quantity and contact fields needed to finish that draft.
- `chat_logs`: idempotency key, request/session IDs, provider/prompt metadata, validated intent/route, latency/token/retry/error metadata and response cache. Raw user messages and provider secrets are not stored.

The schema is initialized with SQLAlchemy `create_all` at app startup. The seed file contains 3 products and 12 unique variants. Existing SQLite files get new tables on next startup; there is not yet a migration framework for evolving columns.

## Session and browser boundary

`POST /api/v1/session` creates or resumes a seven-day demo session. Only the SHA-256 token digest is stored in SQLite. The raw random token is set as `group7_demo_session` with `HttpOnly`, `SameSite=Lax`, root path and `Secure` controlled by `COOKIE_SECURE` (false for local HTTP, true for HTTPS). The client never supplies a session/user ID.

Session-protected cart/order routes derive their owner from the cookie. A request for an order owned by another session returns 404. Write routes reject a present Origin header outside the two local Vite origins. This is a demo boundary; deployment beyond localhost requires HTTPS, rate limiting and a production-grade CSRF/auth setup.

## API and business rules

- Catalog GET routes return database-backed product data and variants.
- Cart add/update validates SKU, positive integer quantity and availability. Cart prices/subtotal are calculated from catalog values; client-supplied price fields are not part of the request schemas.
- Checkout accepts only recipient name, phone and delivery address. It loads the session cart, rechecks active products and stock, calculates the total from server-side prices, writes the order and item snapshots, writes an audit event and clears cart items in one DB commit.
- New orders use `pending_confirmation`. Checkout does not take payment, reserve stock or decrement mock inventory. Availability is checked when adding/updating cart lines and again at checkout.
- Audit details contain item count and total only; recipient PII is not duplicated into audit metadata.
- Chat extraction uses FakeLLM rules by default or optional Ollama (`qwen3.5:2b-q4_K_M` validated locally). Model output is untrusted: intent is allowlisted and payload parsed by Pydantic; catalog mapping, stock, price, owner, order status and writes are always decided by backend rules. Prompt version is `order-extraction-v2`; Ollama uses JSON mode, `think=false`, temperature 0 and context 4096.
- Chat price/stock answers come from active SQLite products. Create order checks active variant/quantity/availability and creates one-item `pending_confirmation` draft only with complete recipient details. Missing details are held in session-owned 30-minute pending state. Update is limited to an unambiguously selected one-item pending draft and a positive quantity; it rechecks stock and recalculates from DB price.
- Chat message IDs are idempotent per session so a network retry returns the cached result. Chat logs keep metadata/response only; do not enable raw prompt or PII logging. Rate limit is 10 messages/minute/session in-process; use a shared limiter if deploying multiple workers.
- Explicit quantities adjacent to an action word (`chốt`, `mua`, `lấy`, `đặt`, `số lượng`) are reconciled against the original message before stock validation. Missing quantity is never defaulted to one; the assistant requests clarification.

## Evaluation and demo

`eval/run_evaluation.py` runs 14 cases plus API workflow/security probes against an isolated temporary SQLite DB, in FakeLLM or Ollama mode. Full reports are in `eval/results_fake.json` and `eval/results_ollama.json`. On 2026-10-22 both passed 14/14, full API smoke and the cross-session 404/spoofed checkout 422 probes; local browser validation also exercised catalog, chat, cart, and checkout. The provider/format failures are injected at the extractor boundary, not an actual Ollama outage. See [`LLM_Evaluation_Results.md`](LLM_Evaluation_Results.md) for rubric, failure analysis and limits, and [`LLM_Demo_Script.md`](LLM_Demo_Script.md) for the timed demo.

## API inventory

- `GET /api/v1/health`
- `GET /api/v1/products?q=&category=`
- `GET /api/v1/products/{product_id}`
- `POST /api/v1/session`, `GET /api/v1/session`
- `GET /api/v1/cart`
- `POST /api/v1/cart/items`, `PATCH /api/v1/cart/items/{sku}`, `DELETE /api/v1/cart/items/{sku}`
- `POST /api/v1/orders`, `GET /api/v1/orders`, `GET /api/v1/orders/{order_id}`
- `POST /api/v1/chat/messages`

Set `LLM_PROVIDER=fake` for offline demo. Optional Ollama uses `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and `LLM_TIMEOUT_SECONDS`; see README. Provider errors and invalid JSON fail without an order side effect.

See the [root README](../README.md) for local setup and request examples. The predecessor course requirements and UI reference are archived alongside this file.
