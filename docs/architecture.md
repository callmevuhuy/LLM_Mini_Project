# Tài liệu Kiến trúc Hệ thống RAG (RAG System Architecture)

## 1. Bối cảnh và Ranh giới Kế thừa

Dự án RAG này là phần mở rộng trực tiếp từ **AI Live Commerce Order Assistant** (môn LLM & Prompting):
- **Cơ sở dữ liệu Vận hành (Operational DB - SQLite):** Giữ quyền kiểm soát duy nhất (Authoritative Source of Truth) đối với danh mục SKU sản phẩm, giá bán hiện hành, số lượng tồn kho theo thời gian thực, phiên mua sắm và trạng thái đơn hàng.
- **RAG Knowledge Base:** Đóng vai trò tra cứu kiến thức phi cấu trúc (thông số kỹ thuật, chất liệu, xuất xứ, chính sách đổi trả, bảo hành, vận chuyển, quy trình nội bộ). **RAG tuyệt đối không tự ý thực hiện ghi/sửa đơn hàng hoặc tự phán đoán giá/tồn kho.**
- **Frontend React/Vite:** Giao diện người dùng duy nhất, giao tiếp với FastAPI qua REST API chuẩn mực (`/api/v1`), không bao giờ kết nối trực tiếp vào SQLite.

---

## 2. Luồng Xử lý Yêu cầu (Target Request Flow & Router)

```text
[Người dùng gửi tin nhắn qua Chat UI]
                │
                ▼ (Kèm X-User-Role: customer | staff | admin)
┌───────────────────────────────────────────────────────────────┐
│ FastAPI Gateway: Xác thực Session & Server-side Authorization  │
└───────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────┐
│ Intent Router (src/router.py)                                 │
│  ├── 1. Order Flow (cũ)   ──> LLM Intent & DB Validation      │
│  ├── 2. Knowledge Flow    ──> RAG Pipeline                    │
│  │                              ├── Pre-filtering theo Role   │
│  │                              ├── Vector Similarity Search  │
│  │                              └── Grounded Answer + Cites   │
│  ├── 3. Mixed Query       ──> Tách Knowledge + Action an toàn│
│  └── 4. Adversarial/Risk  ──> Chặn an toàn / Handoff          │
└───────────────────────────────────────────────────────────────┘
```

### Các loại định tuyến chính:
1. **`order_action` (Thao tác đơn hàng / Tồn kho / Giá):**
   * Chuyển thẳng về pipeline trích xuất LLM và kiểm tra nghiệp vụ backend kế thừa.
   * Tạo đơn nháp chỉ khi đủ thông tin người nhận, SKU hợp lệ và còn tồn kho.
2. **`knowledge_query` (Tra cứu kiến thức):**
   * Lọc quyền trước retrieval (`access_level <= user_role`).
   * Trả về câu trả lời có trích dẫn `citations` chỉ rõ `chunk_id`, `doc_id`, `version`.
   * Từ chối trả lời (`insufficient_evidence`) nếu không có tài liệu hỗ trợ.
   * Từ chối truy cập (`access_denied`) nếu câu hỏi thuộc dữ liệu nội bộ và người dùng là khách hàng.
3. **`mixed` (Yêu cầu hỗn hợp):**
   * Tách câu hỏi kiến thức để gọi RAG trả lời có căn cứ.
   * Tách yêu cầu đơn hàng chuyển sang backend validation độc lập.
   * Trả về kết quả ghép đôi: phần thông tin có trích dẫn, phần đơn hàng hiển thị trạng thái xử lý rõ ràng.
4. **`safety_adversarial` / `handoff`:**
   * Phát hiện các câu lệnh cố tình phá rào (prompt injection, đòi API key, xóa đơn hàng), chặn ngay lập tức và đưa ra cảnh báo an toàn.

---

## 3. Kiến trúc Ingestion, Deterministic Chunking & Index Bundle

1. **Manifest-Driven Ingestion:**
   * Quản trị viên quản lý danh mục tài liệu qua `data_config/corpus_manifest.json`.
   * Kiểm tra nghiêm ngặt: định dạng file, mã hóa UTF-8, không rỗng, ID không trùng lặp, đầy đủ metadata phân quyền (`public`, `staff`, `admin`).
2. **Deterministic Chunking:**
   * Cắt đoạn văn bản theo cấu trúc tiêu đề section markdown (`## `).
   * Tạo định danh chunk cố định dạng `{doc_id}#c{index:02d}` (ví dụ: `POL-RETURN-01#c01`).
3. **Reproducible Local Embedder:**
   * Sử dụng thuật toán vector hóa subword char-gram + word TF-IDF kết hợp chuẩn hóa L2 norm (DIM: 1024).
   * 100% tái lập (deterministic), chạy offline siêu tốc, không cần kết nối internet hay GPU.
4. **Index Bundle:**
   * Đóng gói toàn bộ chỉ mục thành tệp bundle nguyên tử (`artifacts/index_bundle.json`).
   * Kiểm tra tính toàn vẹn (Integrity check): Đảm bảo số lượng vectors luôn khớp 100% với danh sách chunks trước khi cho phép phục vụ truy vấn.

---

## 4. Mô hình Phân quyền & Ranh giới Bảo mật (Trust Boundaries)

* **Phân cấp 3 vai trò:**
  * `customer`: Chỉ được phép truy xuất các tài liệu có `access_level == 'public'` (Catalog, Chính sách đổi trả/bảo hành/vận chuyển, FAQ).
  * `staff`: Được phép truy xuất thêm tài liệu nội bộ hỗ trợ khách hàng (`INT-STAFF-SOP-01`, `INT-DISCOUNT-01`).
  * `admin`: Toàn quyền truy xuất, xem nhật ký kiểm toán và kích hoạt quy trình re-index / rollback.
* **Pre-filtering bắt buộc:**
  * Bộ lọc quyền được áp dụng trực tiếp tại bước lọc candidates trong vector space. Dữ liệu restricted của nhân viên **không bao giờ đi vào danh sách ứng viên, context prompt, bộ nhớ đệm (cache) hay trích dẫn (citations) của khách hàng**.

---

## 5. Vòng đời Chỉ mục và Kế hoạch Nâng cấp (Lifecycle & Re-index)

* Hệ thống hỗ trợ cập nhật chỉ mục nguyên tử từ phiên bản **1.0** lên **1.1** (mô phỏng thay đổi chính sách đổi trả từ 7 ngày lên 14 ngày).
* Khi kích hoạt phiên bản mới:
  * Nạp và kiểm tra tính toàn vẹn của bundle mới.
  * Hoán đổi con trỏ chỉ mục active.
  * Hủy bỏ cache truy vấn cũ (Cache Invalidation).
  * Ghi nhận kiểm toán an toàn vào bảng `audit_logs` (chỉ ghi metadata, không chứa secrets hay PII).
* Khả năng **Rollback** tức thì trong 100ms khi phát hiện sự cố.
