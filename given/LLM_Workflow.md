# Archived LLM Workflow — AI Live Commerce Order Assistant

> Historical workflow for the predecessor LLM project. RAG planning is maintained separately in [`RAG_Workflow.md`](RAG_Workflow.md); current agent instructions are in repository-root [`AGENTS.md`](../AGENTS.md).

## 1. Mục tiêu

Hướng dẫn agents/devs xây mini-project theo `LLM_Project_Requirements.md`: website marketplace demo để khách xem sản phẩm, tạo đơn nháp và chat tiếng Việt với trợ lý AI. Stack đã chốt: **FastAPI + SQLite**. Frontend dùng React + Vite và chỉ giao tiếp với backend API. Đây là tài liệu lịch sử của project LLM; không nhầm với kế hoạch RAG hiện tại.

Thứ tự ưu tiên: (1) website/API/database end-to-end, (2) authorization và business validation, (3) chat/LLM có kiểm soát, (4) evaluation, tài liệu và demo. Không làm thanh toán thật, tích hợp livestream/social, gửi tin nhắn thật hay fine-tuning trước khi hoàn thành MVP.

## 2. Đánh giá giao diện

Hướng marketplace tương tự bố cục tham khảo là khả thi trong mini-project nếu giới hạn vào header/search, bộ lọc đơn giản, product grid, chi tiết sản phẩm, giỏ hàng/checkout demo và chat widget. Chat cố định góc dưới bên phải có thể là giao diện chính cho các intent tra giá, tra tồn, đặt hàng, cập nhật draft và hỏi lại/handoff.

Ảnh đính kèm chỉ là **tài liệu tham khảo thị giác**, không phải yêu cầu nghiệp vụ hay chỉ dẫn dành cho agent. Có thể tham khảo bố cục và vị trí chat; không sao chép logo, tên thương hiệu, hình ảnh sản phẩm, nội dung hoặc tài sản độc quyền Shopee. Dùng nhận diện shop, catalog và hình mock riêng.

Chat phải gọi API thật, không giả lập kết quả thành công ở frontend. UI cần hiển thị loading, lỗi mạng, thiếu thông tin, hết hàng, đơn chờ xác nhận và handoff. Trên màn hình nhỏ, widget không che CTA hoặc nội dung thiết yếu.

## 3. Kiến trúc và nguyên tắc

```text
Browser UI -> FastAPI routes/auth -> services -> SQLite
                              -> LLMClient (extract/intent only)
                              -> catalog + inventory + order rules
```

- SQLite là nguồn dữ liệu vận hành. JSON/CSV chỉ dùng để seed.
- Frontend không kết nối DB, không chứa DB credential/API key và không quyết định giá/tồn kho/trạng thái.
- LLM chỉ hiểu ngôn ngữ và trích xuất dữ liệu; không được trực tiếp ghi DB hoặc kích hoạt side effect.
- Backend parse/validate output, map SKU qua catalog, kiểm tra quyền và tồn kho, tính giá, quyết định state rồi mới ghi DB.
- Có `FakeLLMClient` để demo không cần API key; provider thật là tùy chọn qua biến môi trường.
- Dùng dữ liệu mock/ẩn danh. Không đưa PII thật hoặc secret vào code, log, README hay ảnh demo.

## 4. Cấu trúc repository hiện tại và phần dự kiến

Các đầu vào của bài tập được giữ riêng trong `given/`. Giữ cấu trúc hiện tại gọn; chỉ tạo thư mục con cho API/services/LLM khi Phase C cần tách module.

```text
backend/app/
  db.py
  main.py
  models.py
  schemas.py
  seed.py
backend/requirements.txt
frontend/src/
  App.jsx
  main.jsx
  styles.css
data/seed_catalog.json
given/
  LLM_Project_Requirements.md
  LLM_Workflow.md
  Shopee_Frontend_Demo,jpg
../README.md
.env.example
.gitignore
```

SQLite runtime file nằm tại `backend/data/shop.db` và được Git ignore.

## 5. Database/domain

Tối thiểu các bảng/thực thể:

- `products`: tên, category, aliases, trạng thái.
- `product_variants`: SKU duy nhất, màu/size hoặc thuộc tính khác, giá.
- `inventory`: số lượng mock theo SKU.
- `demo_sessions`: hash token phiên demo và thời điểm hết hạn; token thô chỉ nằm trong cookie HttpOnly của browser.
- `carts` / `cart_items`: giỏ hàng theo session, chỉ lưu SKU và quantity; giá luôn được đọc từ catalog.
- `orders`: ID khó đoán, owner/session, state, thông tin giao nhận cần thiết, timestamps.
- `order_items`: SKU, quantity, snapshot tên/variant/giá backend xác nhận.
- `audit_logs`: request/order ID, actor đã ẩn danh, action, timestamp và metadata tối thiểu.

Tạo ít nhất 10 SKU trên 3 nhóm sản phẩm. Dùng khóa chính/ngoại, unique SKU, quantity nguyên dương và transaction phù hợp. Seed phải có thể chạy lặp lại mà không nhân bản dữ liệu. README hoặc `LLM_Architecture.md` mô tả schema và cách khởi tạo.

## 6. API tối thiểu

Dùng prefix nhất quán, ví dụ `/api/v1`; mô tả request/response, quyền và lỗi trong README/OpenAPI.

| Endpoint gợi ý                    | Công dụng                              | Ràng buộc                                                       |
| ----------------------------------- | ---------------------------------------- | ----------------------------------------------------------------- |
| `GET /products`                   | Danh sách, tìm kiếm/lọc cơ bản     | Đọc từ DB                                                      |
| `GET /products/{id}`              | Chi tiết và variants                   | Đọc từ DB                                                      |
| `POST /session`, `GET /session` | Tạo/khôi phục và đọc demo identity | Opaque HttpOnly cookie; không nhận owner từ body               |
| `GET /cart`                       | Xem giỏ của phiên                     | Server tính giá/subtotal từ catalog                            |
| `POST /cart/items`                | Thêm SKU/quantity                       | Kiểm tra catalog và availability                                |
| `PATCH /cart/items/{sku}`         | Đặt quantity                           | Kiểm tra tồn kho, không nhận giá                             |
| `DELETE /cart/items/{sku}`        | Xóa cart item                           | Chỉ cart của session hiện tại                                 |
| `POST /orders`                    | Checkout cart thành draft               | Server tính snapshot giá/tổng, kiểm tồn, audit và xóa cart |
| `GET /orders`                     | Liệt kê đơn của phiên              | Ownership lọc tại backend                                       |
| `GET /orders/{id}`                | Xem đơn                                | Chỉ owner; đơn không thuộc quyền trả 404                   |
| `POST /chat/messages`             | Xử lý chat                             | Rate limit hợp lý; LLM không ghi DB                            |

Có thể đổi route nhưng phải bao phủ catalog, đặt/xem/sửa đơn có kiểm soát và chat. Không tin `user_id`, role, giá, tổng tiền, inventory hoặc state do client gửi. Trả lỗi có cấu trúc, không lộ stack trace/SQL/secret.

## 7. LLM contract và xử lý chat

Dùng schema (ví dụ Pydantic) với prompt có version (hiện tại `order-extraction-v2`), intent tối thiểu: `create_order`, `check_stock`, `check_price`, `update_order`, `unknown_or_handoff`.

Ví dụ dữ liệu trích xuất:

```json
{
  "intent": "create_order",
  "confidence": "medium",
  "items": [{"requested_product": "áo xanh", "variant": {"color": "xanh", "size": "M"}, "quantity": 2}],
  "customer": {"name": null, "phone": null, "address": "Quận 7"},
  "missing_information": ["recipient_name", "phone_number", "full_delivery_address"],
  "requires_human_review": false,
  "evidence": ["Chốt 2 áo xanh size M, giao về Quận 7"]
}
```

Trình tự xử lý:

1. Kiểm tra session/ownership, độ dài input và rate limit.
2. Gọi LLM với prompt có role, scope, delimiters, JSON contract, quy tắc không bịa và cảnh báo input không tin cậy.
3. Parse JSON; invalid/empty output tạo error state, không thực hiện ghi dữ liệu.
4. Validate schema, enum và kiểu dữ liệu; quantity phải là số nguyên dương.
5. Map sản phẩm/variant sang SKU qua catalog. Không match hoặc match mơ hồ thì hỏi lại/handoff.
6. `check_price`/`check_stock` trả dữ liệu lấy từ DB, không từ LLM.
7. `create_order`/`update_order` kiểm tra thông tin cần thiết, tồn kho, ownership và state. Draft đủ điều kiện ở `pending_confirmation`; thiếu dữ liệu thì `needs_information`.
8. Ghi audit/log metadata tối thiểu, trả route rõ: `answer`, `needs_information`, `pending_confirmation`, `handoff` hoặc `error`.

Không coi confidence là bằng chứng chắc chắn. Không dùng SKU/giá/tồn do model đề xuất nếu backend chưa xác minh. “Đơn lúc nãy” chỉ được cập nhật khi xác định duy nhất đơn trong phiên và đơn còn ở state cho phép; nếu không thì yêu cầu reference hoặc handoff.

## 8. UI marketplace và chat

### Marketplace

- Header/nhận diện shop mock, tìm kiếm, giỏ hàng.
- Lưới product cards và bộ lọc danh mục/giá/tình trạng ở mức MVP.
- Chi tiết sản phẩm cho phép chọn variant/SKU và quantity.
- Catalog, giá và availability lấy từ API; hiển thị availability tại thời điểm query.
- Checkout nhập thông tin demo cần thiết; chỉ báo thành công khi API thành công.

### Chat góc dưới bên phải

- Nút đóng/mở cố định; panel có header, history phiên, message composer, send và trạng thái đang xử lý.
- Gợi ý câu hỏi: “Còn size M không?”, “Giá bao nhiêu?”, “Tôi muốn đặt hàng”.
- Với giá/tồn, câu trả lời grounded từ API. Khi đặt, tóm tắt item/variant/quantity đã xác minh và nói rõ draft chờ xác nhận.
- Thiếu thông tin thì hỏi đúng field và tiếp tục trong cùng phiên.
- Handoff phải nói rõ cần nhân viên hỗ trợ; không giả vờ đã gửi tin cho nhân viên thật.
- Hỗ trợ lỗi mạng/retry, keyboard focus cơ bản và responsive.

## 9. Security, privacy, reliability

- Phase B dùng cookie opaque `HttpOnly`, `SameSite=Lax`, thời hạn 7 ngày; chỉ lưu hash token trong DB. Client không tự chọn owner ID. `COOKIE_SECURE=true` khi chạy HTTPS; mặc định local HTTP chỉ dành cho demo.
- Endpoint ghi dữ liệu kiểm tra Origin nếu có và chỉ nhận origin dev allowlist. Production cần CSRF strategy đầy đủ, TLS, rate limiting và quản lý session/secret phù hợp.
- Mọi thao tác xem/sửa order kiểm tra ownership ở backend (chống IDOR/BOLA).
- Nếu client gửi giá/tổng tiền/tồn/state giả, server bỏ qua hoặc từ chối; dữ liệu lưu vẫn do DB/rule quyết định.
- Có `.env.example` placeholder; `.env` nằm trong `.gitignore`.
- Không log API key, token, password, raw PII hoặc toàn bộ chat không cần thiết. Log request ID, prompt version, model ID, intent, validation status, route, latency, token counts nếu có, retry count và error type.
- LLM request có timeout; retry tối đa 2–3 lần cho lỗi tạm thời; không retry auth/validation/policy errors hoặc side effect không idempotent.
- Giới hạn độ dài input và rate limit endpoint chat; lỗi trả về không lộ chi tiết nội bộ.

## 10. Các phase triển khai và tiêu chí hoàn tất

### Phase A — Khung, schema và catalog

Dựng backend/frontend, cấu hình, SQLite schema/migration, seed >=10 SKU/3 nhóm, health check và API đọc catalog.

**Xong khi:** app khởi động được, seed lặp an toàn, UI/API đọc dữ liệu từ SQLite.

**Trạng thái:** Hoàn tất. Đã có storefront Group 7, API catalog/health, SQLite và 12 SKU trên 3 danh mục. Tài liệu đầu vào chuyển vào `given/`.

### Phase B — Mua hàng cơ bản

Xây marketplace, tìm kiếm/lọc cơ bản, product detail/variant selection, cart và checkout demo. Tạo order qua API với validation server-side, ownership và audit log.

**Xong khi:** khách demo tạo/xem draft của mình qua UI; client sửa giá không làm đổi giá lưu.

**Trạng thái:** Hoàn tất. Đã có chọn SKU, cart server-side theo phiên, chỉnh quantity/xóa item, checkout, `pending_confirmation`, order list/detail theo owner và audit record. Giá/tổng do backend tính; checkout kiểm tồn nhưng không trừ/giữ tồn. UI chỉ dùng dữ liệu liên hệ giả.

### Phase C — Chat và LLM

Xây widget và chat endpoint; `FakeLLMClient`, prompt versioned, parser/schema validation; nối intent với catalog/order service; thêm handoff. Provider thật tùy chọn, cấu hình qua env.

**Trạng thái:** Hoàn tất MVP. Chat widget gửi/hiện message và route state; `POST /chat/messages` yêu cầu demo session, hỗ trợ idempotency; FakeLLM là mặc định, Ollama dùng `httpx` với timeout/retry bounded, prompt `order-extraction-v2`, JSON/Pydantic validation. Backend chỉ match product/variant trong SQLite, tra giá/tồn và kiểm tra owner/state trước khi tạo/sửa đơn. Có hỏi lại thông tin nhận hàng với pending state TTL 30 phút, response không nhắc lại PII, audit metadata và chat logs không lưu raw message. UI hiển thị loading/error, needs information, out of stock, handoff và pending confirmation. Quantity nêu tường minh sau động từ đặt/mua/chốt/lấy được đối chiếu với tin nhắn gốc; quantity bị thiếu không tự mặc định bằng 1.

**Giới hạn đã biết:** FakeLLM dùng heuristic tiếng Việt, không thay thế model; chat order MVP xử lý một SKU/dòng hàng mỗi lần; sửa chỉ dành cho đơn `pending_confirmation` một item và cần quantity rõ; variant mơ hồ sẽ hỏi lại. Có rate limit 10 tin/phút/session trong một process; triển khai nhiều worker cần limiter dùng chung. Chỉ chạy local demo, không dùng PII thật. Ollama là tùy chọn, không phải dependency để chạy Fake mode.

### Phase D — Evaluation và bàn giao

Hoàn tất tối thiểu 12 test cases đúng nhóm yêu cầu, rubric, ít nhất 2 failure analyses và revision notes. Tài liệu hóa setup, schema, API, mock mode, giới hạn và kịch bản demo 5–8 phút.

**Trạng thái:** Hoàn tất tại project LLM. Có 14 case: 3 happy path, 4 missing/ambiguous (có multi-turn), 2 catalog/inventory, 2 lỗi provider/format được inject, 2 safety và 1 update. Runner dùng SQLite tạm và smoke toàn luồng 12 endpoint status từ session/catalog đến cart/checkout/order. Ngày 2026-10-20: FakeLLM 14/14, Ollama `qwen3.5:2b-q4_K_M` 14/14; cross-session order → 404, payload giả giá/tồn/trạng thái → 422 và số order không đổi. Frontend build thành công; trình duyệt hiển thị catalog, mở chat và hỏi giá API-grounded thành công. UX checkout qua trình duyệt và chấm phản hồi bởi người thật chưa được xác nhận trong lượt này. Chi tiết ở `LLM_Evaluation_Results.md`, kịch bản demo 6–7 phút tại `LLM_Demo_Script.md`, kết quả thô ở `../eval/results_*.json`.

## 11. Hướng dẫn cho agents/devs

- Trước khi sửa project LLM, đọc `LLM_Project_Requirements.md`, `LLM_Workflow.md`, README và cấu trúc hiện tại.
- Thống nhất contract API/schema trước khi code; cập nhật tài liệu cùng khi contract đổi.
- Không tự đổi stack, trust boundary, intent hay order state mà không ghi lý do và cập nhật tài liệu.
- Giữ routes mỏng; business rules ở services/backend, prompt chỉ hỗ trợ extraction.
- Không thêm secret, PII thật, dữ liệu thương mại thật hoặc tài sản thương hiệu chưa được cấp quyền.
- Mọi function trong backend cần docstring tiếng Anh ngắn gọn; riêng chat/LLM phải ghi rõ trust boundary, validation, side effects và dữ liệu được lưu.
- Khi bàn giao, nêu file đã sửa, luồng đã làm, cách chạy và phần còn thiếu. Chỉ khẳng định kiểm chứng nếu đã thực sự chạy kiểm chứng.
- Tạo/running tests khi được yêu cầu hoặc khi tiêu chí hoàn tất của phase phụ thuộc vào kết quả đó; ghi lại lệnh và kết quả.

## 12. Checklist tổng

- [x] FastAPI + SQLite là backend/data source; frontend chỉ gọi API.
- [x] >=10 SKU, >=3 nhóm; dữ liệu mock và seed lặp lại an toàn.
- [x] Website xem/tìm sản phẩm, chọn variant, cart và tạo draft.
- [x] Chat widget dưới bên phải gọi backend và hiển thị các trạng thái nghiệp vụ.
- [x] Đủ intents: create, stock, price, update, unknown/handoff.
- [x] LLM output được parse/schema/business validate; backend quyết SKU/giá/tồn/state.
- [x] Demo session, ownership checks, audit log.
- [x] Prompt có version, delimiter, untrusted-input rule và JSON contract.
- [x] Fake mode chạy không cần secret; `.env.example`/`.gitignore` có placeholder cấu hình.
- [x] Có >=12 evaluation cases, rubric và >=2 failure analyses (`../eval/`, `LLM_Evaluation_Results.md`).
- [x] README/architecture/workflow, evaluation results và demo script đã cập nhật sau Phase D.
- [x] Các function backend có docstring tiếng Anh; chat/LLM flow có giải thích validation/trust boundary.
- [x] Full verification ngày 2026-10-22: FakeLLM 14/14, Ollama 14/14, API/security smoke, npm clean install/build và browser checkout.

## 13. Nhật ký tiến độ

- **2026-10-20 — Phase A:** dựng nền FastAPI/SQLite/catalog API và marketplace Group 7; gom đề bài, workflow và ảnh tham khảo vào `given/`.
- **2026-10-20 — Phase B:** thêm demo session cookie HttpOnly, cart API/SQLite, chọn variant, checkout draft, order reads có ownership, snapshot giá và audit log; cập nhật README, architecture và checklist này.
- **2026-10-20 — Phase C:** thêm FakeLLM/Ollama extraction adapter, chat API idempotent theo phiên, kiểm chứng product/variant/giá/tồn bằng SQLite, tạo/sửa draft giới hạn, pending info TTL, log metadata không raw message và chat widget; cập nhật README, architecture và workflow. Phase D còn lại.
- **2026-10-20 — Phase D:** thêm 14 case và runner SQLite cô lập, rubric 5 chiều, báo cáo kết quả, failure analyses, demo script; kết quả Fake 14/14, Ollama 14/14. Evaluation phát hiện quantity `13` có thể bị Qwen đọc thành `1`; thêm reconciliation deterministic cho quantity được nêu rõ, cập nhật prompt/workflow/README/architecture.
- **2026-10-21 — Toàn diện sau Phase D:** README tách hướng chạy FakeLLM/Ollama; evaluator mở rộng smoke session/catalog/cart/checkout/order và probe spoof cả price/stock/status; chạy lại cả hai provider, frontend production build và browser smoke storefront/chat. Tạo `LLM_Project_Report.md` với ma trận tiêu chí đạt/partial và giới hạn chưa kiểm chứng.
- **2026-10-22 — A–Z và backend documentation:** thêm English docstring cho toàn bộ function backend và giải thích rõ từng trust boundary của chat/LLM. Rà soát dependency/setup; FakeLLM và Ollama đều 14/14, API/security probes, `npm ci`, Vite production build và browser test catalog → chat price → cart → checkout đều đạt. Cập nhật README, architecture, evaluation results và `LLM_Project_Report.md`.
