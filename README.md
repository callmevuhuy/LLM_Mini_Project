# Group 7 — AI Live Commerce Order Assistant

Website marketplace demo Group 7 có trợ lý chat hỗ trợ tiếp nhận yêu cầu mua hàng tiếng Việt. Giao diện tham khảo bố cục marketplace trong tài liệu mẫu nhưng dùng nhận diện và dữ liệu mock riêng.

## Trạng thái triển khai

- **Phase A — hoàn tất:** FastAPI + SQLite, 12 SKU / 3 danh mục, seed, health/catalog API, marketplace UI.
- **Phase B — hoàn tất:** demo session cookie, cart lưu trong SQLite, chọn biến thể, cập nhật/xóa cart item, checkout tạo đơn `pending_confirmation`, xem danh sách/chi tiết đơn thuộc phiên, order item snapshot giá và audit log.
- **Phase C — hoàn tất:** chat widget tương tác, API chat theo phiên, FakeLLM mặc định, Ollama tùy chọn, intent routing và tạo/sửa đơn nháp có kiểm soát.
- **Phase D — hoàn tất:** 14 case evaluation cho FakeLLM và Ollama, kiểm tra bảo mật session/checkout, failure analysis và kịch bản demo 6–7 phút.

Tài liệu yêu cầu và ảnh tham khảo được gom trong [`given/`](given/). Workflow triển khai là [`given/workflow.md`](given/workflow.md).

## Chạy ứng dụng

Yêu cầu: Python 3.11+ (project đã dùng được môi trường Python hiện có), Node.js 20+ và npm.

### Chuẩn bị chung

```powershell
cd D:\VSCode\Project\LLM
python -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

Schema được tạo tự động khi API khởi động. Catalog được seed nếu bảng `products` đang trống. SQLite file: `backend/data/shop.db`. API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Đảm bảo Ollama chỉ chạy khi chọn cách B; cách A không cần model/API key.

### Cách A — FakeLLM (offline, mặc định)

FakeLLM dùng heuristic/rules, phù hợp kiểm tra UI, API và luồng nghiệp vụ ổn định. Mở terminal backend tại thư mục gốc:

```powershell
cd D:\VSCode\Project\LLM
$env:LLM_PROVIDER = "fake"
cd backend
..\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

### Cách B — Ollama (`qwen3.5:2b-q4_K_M`)

Đảm bảo Ollama đang chạy và đã pull đúng model. Trong terminal backend riêng:

```powershell
cd D:\VSCode\Project\LLM
$env:LLM_PROVIDER = "ollama"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:OLLAMA_MODEL = "qwen3.5:2b-q4_K_M"
$env:LLM_TIMEOUT_SECONDS = "30"
cd backend
..\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Ollama dùng JSON mode, `think=false`, context 4096 và temperature 0. Nếu Ollama/model không sẵn sàng hoặc JSON không hợp lệ, API trả lỗi và không tạo đơn. Khi thiếu quantity, hệ thống hỏi lại thay vì tự mặc định; quantity viết rõ cạnh động từ mua/chốt/lấy/đặt được đối chiếu trước khi kiểm tồn.

Nếu chạy qua HTTPS, đặt `$env:COOKIE_SECURE = "true"` trong terminal backend trước khi khởi động Uvicorn. Giá trị mặc định `false` chỉ dành cho demo local qua HTTP.

### Evaluation Phase D

Tại thư mục gốc, dùng virtualenv backend để chạy suite trên SQLite tạm (không đụng database demo):

```powershell
.\backend\.venv\Scripts\python.exe eval\run_evaluation.py --provider fake
.\backend\.venv\Scripts\python.exe eval\run_evaluation.py --provider ollama --model qwen3.5:2b-q4_K_M
```

Kết quả hiện tại: FakeLLM **14/14**, Ollama `qwen3.5:2b-q4_K_M` **14/14**; lần chạy toàn diện bao gồm API smoke cho catalog/session/cart/checkout, probe quyền sở hữu (order khác session → 404) và payload giả giá/tồn/trạng thái (422, không tạo order). Frontend production build và kiểm tra trình duyệt storefront/chat cũng đạt. Đây là kết quả trên 14 fixture, không phải bảo đảm chất lượng cho mọi câu chat. Chi tiết rubric, failure analysis và giới hạn ở [`docs/evaluation_results.md`](docs/evaluation_results.md); kịch bản demo 6–7 phút ở [`docs/demo_script.md`](docs/demo_script.md), báo cáo tổng thể tại [`Project_Report.MD`](Project_Report.MD).

### Frontend

Terminal thứ hai:

```powershell
cd frontend
npm install
npm run dev
```

Mở `http://127.0.0.1:5173`. Giữ hostname `127.0.0.1` để trình duyệt gửi demo cookie đúng với API mặc định. Nếu cần đổi URL API, tạo `frontend/.env.local` với `VITE_API_BASE_URL=...`; `.env.example` ở root là template, Vite không tự đọc file này từ root.

Chỉ dùng tên, điện thoại và địa chỉ **giả** trong demo. Không nhập dữ liệu khách hàng thật.

## API

Tất cả endpoint dùng prefix `/api/v1`.

| Method | Endpoint | Quyền | Mô tả |
| --- | --- | --- | --- |
| `GET` | `/health` | Public | Trạng thái API/SQLite, số sản phẩm |
| `GET` | `/products?q=&category=` | Public | Catalog từ database; tìm tên/category/mô tả và lọc danh mục |
| `GET` | `/products/{product_id}` | Public | Chi tiết sản phẩm, SKU, variants, giá, availability |
| `POST` | `/session` | Public, Origin allowlist | Tạo/khôi phục phiên demo; token opaque nằm trong cookie HttpOnly |
| `GET` | `/session` | Session cookie | Kiểm tra phiên hiện tại |
| `GET` | `/cart` | Session cookie | Đọc giỏ hàng và subtotal được tính từ giá DB |
| `POST` | `/cart/items` | Session cookie + Origin | Thêm SKU/quantity; server kiểm catalog và tồn |
| `PATCH` | `/cart/items/{sku}` | Session cookie + Origin | Đặt lại quantity; kiểm tồn kho |
| `DELETE` | `/cart/items/{sku}` | Session cookie + Origin | Xóa item khỏi cart của phiên hiện tại |
| `POST` | `/orders` | Session cookie + Origin | Checkout cart; server tính tổng, tạo `pending_confirmation`, ghi audit và xóa cart |
| `GET` | `/orders` | Session cookie | Chỉ liệt kê đơn thuộc phiên hiện tại |
| `GET` | `/orders/{order_id}` | Session cookie | Chỉ trả đơn thuộc phiên; đơn khác owner trả 404 |
| `POST` | `/chat/messages` | Session cookie + Origin | Xử lý chat; idempotency theo `client_message_id`; routes: answer/needs_information/pending_confirmation/updated_order/out_of_stock/handoff/error |

`POST /chat/messages` body: `{"message":"Còn hàng áo thun xanh size M không?","client_message_id":"<uuid>"}`. Tin nhắn tối đa 1500 ký tự. Tin nhắn gốc không được lưu trong DB; `chat_logs` chỉ lưu metadata, route và response không chứa contact fields. Thông tin có cấu trúc cần để tiếp tục đơn nháp có TTL 30 phút trong `chat_states`.

`POST /cart/items` body:

```json
{"sku": "TSHIRT-BLU-M", "quantity": 2}
```

`POST /orders` body chỉ chứa thông tin giao hàng:

```json
{
  "recipient_name": "Demo Customer",
  "phone_number": "0900000000",
  "delivery_address": "12 Demo Street, District 7"
}
```

Không gửi giá, subtotal, tồn kho, owner ID hay trạng thái. Các request schema từ chối field thừa; backend lấy giá/SKU/tồn từ SQLite. API từ chối Origin ngoài hai Vite dev origin đã cấu hình. Cookie demo có thời hạn 7 ngày, `HttpOnly`, `SameSite=Lax`; `COOKIE_SECURE=true` khi chạy HTTPS. Cấu hình hiện hướng tới demo local, chưa phải auth production.

## Dữ liệu và hành vi checkout

- `data/seed_catalog.json` là dữ liệu nguồn seed, không được frontend đọc trực tiếp.
- SQLite có `products`, `product_variants`, `inventory`, `demo_sessions`, `carts`, `cart_items`, `orders`, `order_items`, `audit_logs`, `chat_states`, `chat_logs`.
- `order_items` lưu snapshot tên/variant/giá được server xác nhận tại lúc checkout.
- Đơn được tạo ở `pending_confirmation`. Đây là yêu cầu chờ xác nhận, không thanh toán và không trừ/giữ tồn kho. API kiểm tồn lại ngay trước khi tạo.
- Audit log ghi order/request ID, actor session ID, action và tổng/item count; không lưu thông tin liên hệ vào audit.

## Giới hạn hiện tại

- Session chỉ là danh tính ẩn danh cho demo trình duyệt; chưa có đăng nhập/tài khoản thật hoặc CSRF token framework.
- Schema tự tạo bằng SQLAlchemy `create_all`; chưa có migration framework cho thay đổi schema về sau.
- Chat hiện hỗ trợ một sản phẩm/variant cho một yêu cầu tạo đơn; cập nhật chỉ áp dụng cho đơn nháp một item và cần số lượng rõ ràng.
- Chat rate limit là 10 tin/phút/session trong một process; nhiều worker cần limiter dùng chung. FakeLLM là heuristic, còn Ollama output vẫn phải qua schema/business validation.
- Mock availability không bị trừ sau khi tạo đơn; checkout chỉ kiểm tra lại tồn tại thời điểm request.
- Ảnh catalog lấy từ URL Unsplash trong seed nên cần internet để tải hình.

Đọc [`given/Project_Requirements.md`](given/Project_Requirements.md) để xem đề bài đầy đủ, [`given/workflow.md`](given/workflow.md) cho hướng dẫn agents/devs, và [`docs/architecture.md`](docs/architecture.md) để xem mô hình/luồng hiện tại.
