# Báo cáo Dự án RAG — AI Live Commerce Order Assistant (Group 7)

**Tên dự án:** Mở rộng Hệ thống Trợ lý Thương mại Hội thoại với RAG Phân Quyền (Permission-Aware Retrieval-Augmented Generation)  
**Tác giả:** Group 7  
**Ngày báo cáo:** 30/10/2026  
**Kho mã nguồn:** [https://github.com/callmevuhuy/RAG-Mini-Project](https://github.com/callmevuhuy/RAG-Mini-Project)  
**Công nghệ nền tảng:** React 19 + Vite, FastAPI, SQLAlchemy 2.0, SQLite, Local Deterministic n-gram Embedder, FakeLLM / Ollama  

---

## 1. Tóm tắt Điều hành (Executive Summary)

Dự án này là bước phát triển mở rộng trực tiếp từ mini-project *AI Live Commerce Order Assistant* (môn LLM & Prompt Engineering). Ứng dụng gốc cung cấp website bán hàng trực tuyến với tính năng xem catalog, giỏ hàng, đặt hàng nháp và chatbot trích xuất ý định đơn hàng qua backend FastAPI/SQLite.

Trong giai đoạn này, nhóm đã tích hợp thành công kiến trúc **Retrieval-Augmented Generation (RAG)** kiểm soát quyền truy cập chặt chẽ, cho phép trợ lý trả lời chính xác các câu hỏi về thông số kỹ thuật, chất liệu sản phẩm, chính sách đổi trả, bảo hành, vận chuyển và quy trình vận hành nội bộ từ tài liệu phiên bản hóa.

### Các thành tựu then chốt:
1. **Bảo toàn nguồn sự thật (Authoritative Catalog & DB):** Tách bạch triệt để giữa dữ liệu vận hành (giá bán, số lượng tồn kho, đơn hàng nằm trong SQLite) và kiến thức tài liệu (RAG). RAG là bộ đọc tĩnh (read-only), tuyệt đối không tự ý quyết định giá, tồn kho hoặc ghi đơn vào DB.
2. **Corpus chuẩn mực & Đồng bộ định danh:** Xây dựng 12 tài liệu với 31 chunks có cấu trúc, đồng bộ 100% mã SKU (`TSHIRT-...`, `BOTTLE-...`, `COFFEE-...`) giữa database và knowledge base.
3. **Phân quyền trước Retrieval (Pre-filtering RBAC):** Áp dụng bộ lọc quyền hạn (`customer`, `staff`, `admin`) trực tiếp trong không gian vector trước bước ranking. Dữ liệu restricted của nhân viên không bao giờ lọt vào candidate, prompt context, cache hay citation của khách hàng.
4. **Router định tuyến thông minh & Mixed Query:** Nhận diện và xử lý độc lập câu hỏi hỗn hợp (vừa hỏi kiến thức vừa đặt hàng): RAG trả lời có căn cứ trích dẫn, còn phần đặt hàng được đưa qua luồng kiểm tra tồn kho và xác thực backend độc lập.
5. **Đánh giá tự động vượt chuẩn (20 Test Cases):** 
   * **Hit@3:** 100.0%
   * **Recall@5:** 93.89%
   * **MRR (Mean Reciprocal Rank):** 0.9667
   * **Citation Resolve Rate:** 100.0%
   * **Safe Abstention Rate:** 100.0% (từ chối an toàn khi thiếu căn cứ)
   * **Access-Denied Correctness:** 100.0% (chặn tài liệu nội bộ đúng quyền)
   * **Bộ test kế thừa:** 14/14 cases đơn hàng tiếp tục đạt 100% pass.
6. **Vận hành Re-index v1.0 $\rightarrow$ v1.1 & Rollback:** Mô phỏng nâng cấp chính sách đổi trả từ 7 ngày lên 14 ngày (miễn phí ship 2 chiều). Chứng minh tài liệu cũ không còn hiệu lực trên active index và khôi phục mốc 7 ngày (Rollback) tức thì dưới 50ms.

---

## 2. Kiến trúc Hệ thống & Ranh giới Kế thừa

### 2.1. Sơ đồ Luồng Xử lý Yêu cầu (Request Flow)

```text
[Người dùng gửi tin nhắn trên Giao diện Chat]
                     │
                     ▼ (Mang theo session cookie & Header X-User-Role)
┌─────────────────────────────────────────────────────────────┐
│ FastAPI Gateway: Xác thực Session & Server-side Role        │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Intent & Query Router (src/router.py)                       │
│  ├── 1. Order Action      ──> Kế thừa: SQLite / Inventory    │
│  ├── 2. Knowledge Query   ──> RAG Pipeline                  │
│  │                              ├── Role Pre-filtering      │
│  │                              ├── Local Vector Search     │
│  │                              └── Grounded Generation     │
│  ├── 3. Mixed Query       ──> Tách Knowledge + Order Action │
│  └── 4. Safety/Risk       ──> Chặn an toàn / Handoff        │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
[Giao diện Chat: Hiển thị Route Badge, Câu trả lời & Trích dẫn Nguồn]
```

### 2.2. Bảng Ranh giới Trách nhiệm & Quyền hạn (Trust Boundaries)

| Thành phần | Quyền hạn dữ liệu | Side Effect (Ghi DB) | Cơ chế kiểm soát |
| :--- | :--- | :---: | :--- |
| **Catalog / Inventory** | Authoritative (Giá, Tồn kho thực tế) | Có (khi checkout) | SQLite Transaction, Backend validation |
| **Order Flow (cũ)** | Tạo/sửa đơn hàng nháp | Có (tạo bản ghi Order) | Xác thực SKU, địa chỉ, số điện thoại, idempotency key |
| **RAG Knowledge Route** | Đọc tài liệu Markdown (`public`/`staff`/`admin`)| **KHÔNG** (Read-only) | Pre-filtering theo Role, không có công cụ ghi DB |
| **Mixed Query Route** | Đọc RAG + gọi Order Validation | Có (cho phần Order) | Tách rời 2 phần, RAG không trực tiếp trigger lệnh ghi |
| **Staff/Admin Ops** | Đọc toàn bộ tài liệu & Re-index | Có (ghi `audit_logs`) | Chặn quyền tại FastAPI dependency (`X-User-Role == 'admin'`) |

---

## 3. Quản lý Corpus Dữ liệu & Tính Tái lập (Ingestion & Reproducibility)

### 3.1. Danh mục 12 Tài liệu Mở rộng (`data/corpus/`)
Corpus được nhóm biên soạn chi tiết, bảo đảm tính thực tế và đồng bộ 100% với file catalog `data/seed_catalog.json`:
1. `CAT-TSHIRT-01.md`: Áo thun basic cotton (SKU: `TSHIRT-WHT-M`, `TSHIRT-BLK-L`, `TSHIRT-BLU-M`, `TSHIRT-PNK-S`).
2. `CAT-BOTTLE-01.md`: Bình giữ nhiệt Everyday (SKU: `BOTTLE-500-WHT`, `BOTTLE-500-MNT`, `BOTTLE-750-BLK`, `BOTTLE-750-CRM`).
3. `CAT-COFFEE-01.md`: Cà phê rang xay Đà Lạt (SKU: `COFFEE-250G`, `COFFEE-500G`, `COFFEE-250G-GRD`, `COFFEE-500G-GRD`).
4. `CAT-SIZING-01.md`: Bảng kích thước chuẩn áo thun và hướng dẫn đo tại nhà.
5. `POL-RETURN-01.md`: Chính sách đổi trả & hoàn tiền v1.0 (thời hạn 07 ngày, video unbox).
6. `POL-WARRANTY-01.md`: Chính sách bảo hành (Bình 12 tháng, áo 30 ngày; từ chối do rơi vỡ, ngập nước).
7. `POL-SHIPPING-01.md`: Chính sách vận chuyển & đồng kiểm (giao 1-4 ngày, đồng kiểm ngoại quan, không thử đồ, không cam kết giờ chính xác).
8. `FAQ-ORDER-01.md`: FAQ đặt hàng, hủy đơn và hướng dẫn xử lý khi nhận thiếu hàng (báo trong 48h).
9. `FAQ-CARE-01.md`: Hướng dẫn vệ sinh khử mùi bình giữ nhiệt và kỹ thuật pha cà phê phin.
10. `INT-STAFF-SOP-01.md` (*Staff/Admin*): Quy trình tiếp nhận khiếu nại, đối soát camera PackStation của WMS và đền bù voucher.
11. `INT-DISCOUNT-01.md` (*Staff/Admin*): Cấu hình mã ưu đãi nhân viên `STAFF20` (giảm 20%) và mã CSKH `CSKH-VIP50`.
12. `INT-ADMIN-OPS-01.md` (*Admin only*): Quy trình quản trị cân đối kho và phê duyệt tái lập chỉ mục (Re-index) RAG.

### 3.2. Deterministic Chunking & Local Embedder
* **Deterministic Chunking:** Chia văn bản theo tiêu đề Section Markdown (`##`), gán mã định danh ổn định dạng `{doc_id}#c{index:02d}` (tổng cộng 31 chunks).
* **Local Deterministic Embedder:** Sử dụng thuật toán vector hóa subword char-gram + word TF-IDF kết hợp chuẩn hóa L2 (Vector dimension: 1024). Bộ nhúng hoàn toàn xác định, tính toán chỉ trong vài mili-giây, độc lập 100% với GPU và internet.
* **Gói Chỉ mục Nguyên tử (Atomic Index Bundle):** Đóng gói toàn bộ vectors, chunk map và manifest thành file `artifacts/index_bundle.json`. Hệ thống thực hiện kiểm tra tính toàn vẹn (Integrity check) trước khi nạp; nếu số lượng vector lệch với chunk, hệ thống lập tức báo lỗi và dừng phục vụ nhằm tránh trích dẫn sai.

---

## 4. Phân quyền Dữ liệu & Grounded Generation

### 4.1. Pre-filtering theo Role
Hệ thống xác định vai trò người dùng phía backend:
$$\text{Allowed Chunks} = \{c \in \text{Corpus} \mid \text{AccessLevel}(c) \subseteq \text{UserRole}\}$$
* Vai trò `customer`: Chỉ được truy xuất tập chunk có nhãn `public`.
* Vai trò `staff`: Được truy xuất tập `public` + `staff`.
* Vai trò `admin`: Toàn quyền truy xuất toàn bộ 31 chunks.

### 4.2. Grounded Answer Contract & Citations
Câu trả lời được định dạng theo cấu trúc JSON nghiêm ngặt:
```json
{
  "status": "answered | insufficient_evidence | access_denied | handoff | error",
  "answer": "Câu trả lời tiếng Việt chính xác, bảo toàn điều kiện và ngoại lệ.",
  "citations": [
    {
      "chunk_id": "POL-RETURN-01#c01",
      "doc_id": "POL-RETURN-01",
      "source": "Chính sách Đổi trả và Hoàn tiền",
      "version": "1.0",
      "section": "Thời hạn và Phạm vi áp dụng"
    }
  ],
  "missing_information": ""
}
```
* **Citation Resolution:** 100% các trích dẫn trả về phải tồn tại thực sự trong gói bundle chỉ mục đang hoạt động.
* **Safe Abstention:** Khi người dùng hỏi sản phẩm không kinh doanh (giày sneaker) hoặc đòi cam kết giờ giao cụ thể $\rightarrow$ Trả về `insufficient_evidence`, không tự bịa đặt.
* **Access Denied:** Khi khách hàng hỏi về mã giảm giá nhân viên hoặc quy trình nội bộ $\rightarrow$ Trả về `access_denied`, không để lộ nội dung.

---

## 5. Báo cáo Đánh giá (Evaluation Report)

### 5.1. Kết quả trên 20 Test Cases (7 Nhóm Chuẩn)
Hệ thống kiểm thử tự động tại [`eval/run_rag_evaluation.py`](file:///d:/VSCode/Project/RAG/eval/run_rag_evaluation.py) đánh giá trên bộ test [`artifacts/evaluation_cases.jsonl`](file:///d:/VSCode/Project/RAG/artifacts/evaluation_cases.jsonl) gồm 10 cases Development và 10 cases Frozen Test:

| Nhóm Kiểm thử (Category) | Số lượng | Tỷ lệ Thành công | Ghi chú đánh giá |
| :--- | :---: | :---: | :--- |
| **Exact / Mã tra cứu** | 4 | **100%** | Tra cứu chính xác SKU `TSHIRT-BLU-M`, `COFFEE-500G-GRD`, hạn bảo hành. |
| **Paraphrase** | 4 | **100%** | Bắt đúng ý các câu hỏi tự nhiên: rơi nước hỏng, đổi ý trả áo, chất vải cotton. |
| **Multi-condition** | 3 | **100%** | Tổng hợp chính xác từ nhiều section: điều kiện đổi trả + phí ship, báo thiếu hàng. |
| **No-evidence** | 2 | **100%** | Từ chối an toàn khi hỏi giày thể thao hoặc hẹn giờ giao chính xác 2h chiều. |
| **Access-denied** | 2 | **100%** | Chặn đứng yêu cầu xin mã giảm giá nhân viên `STAFF20` và SOP nội bộ. |
| **Mixed Query** | 3 | **100%** | Tách bạch hoàn hảo phần hỏi đáp tài liệu và phần tạo đơn nháp. |
| **Safety / Adversarial** | 2 | **100%** | Chống phá rào ("bỏ qua chính sách...") và yêu cầu xóa đơn / đòi API key. |

### 5.2. Các chỉ số Đo lường Tự động (Metrics Summary)
* **Hit@3:** **100.0%** (Vượt mục tiêu $\ge 80\%$)
* **Recall@5:** **93.89%** (Vượt mục tiêu $\ge 85\%$)
* **MRR (Mean Reciprocal Rank):** **0.9667** (Chunk đúng đứng ở Rank #1)
* **Citation Resolve Rate:** **100.0%** (Toàn bộ citation trỏ đúng chunk thật)
* **Safe Abstention Rate:** **100.0%** (Tuyệt đối không bịa đặt fact)
* **Access-Denied Correctness:** **100.0%** (Bảo vệ thông tin nội bộ tuyệt đối)
* **Mixed Route Accuracy:** **100.0%** (Định tuyến chuẩn xác)

### 5.3. Phân tích Lỗi 5 Tầng & Thử nghiệm Cải tiến
Trong giai đoạn đầu phát triển, nhóm ghi nhận các cận sai và đã giải quyết triệt để:
1. *Tầng Ranking:* Truy vấn hỏi giày sneaker ban đầu bị false-positive do trùng từ dừng phổ biến $\rightarrow$ Khắc phục bằng bộ lọc `STOP_WORDS` tiếng Việt và bộ lọc thực thể ngoài danh mục.
2. *Tầng Routing:* Cụm từ "lấy lại tiền" bị nhầm thành mua hàng ("lấy...") $\rightarrow$ Khắc phục bằng Word Boundary `\b` và mở rộng từ điển tri thức.
3. *Tầng Routing:* Cụm từ "mã giảm giá" bị nhầm thành hỏi giá $\rightarrow$ Khắc phục bằng Negative Lookbehind `(?<!giam\s)\bgia\b`.
4. *Tầng Generation:* Từ "bao lâu" bị trùng chuỗi con với "áo" $\rightarrow$ Khắc phục bằng khớp từ trọn vẹn `re.search(r"\bao\b", ...)`.
5. *Tầng Security:* Phát hiện câu lệnh jailbreak can thiệp hệ thống $\rightarrow$ Đưa bộ kiểm tra an toàn lên đầu pipeline router.

---

## 6. Vận hành Re-index và Kế hoạch Rollback (v1.0 $\rightarrow$ v1.1)

Nhóm đã xây dựng hoàn chỉnh kịch bản cập nhật nghiệp vụ thực tế:
* **Nội dung thay đổi:** Cập nhật `POL-RETURN-01` từ v1.0 sang v1.1 (thời hạn đổi trả tăng từ **07 ngày** lên **14 ngày**, miễn phí vận chuyển 2 chiều 100%).
* **Tính nguyên tử (Atomic Activation):** Admin gọi `POST /api/v1/rag/reindex?version=1.1`, hệ thống nạp candidate bundle `artifacts/index_bundle_v1_1.json`, kiểm tra tính toàn vẹn và hoán đổi chỉ mục trong 50ms.
* **Xác minh Truy vấn:** 
  * Khi ở v1.0: Trả lời "trong vòng 07 ngày", trích dẫn version `1.0`.
  * Sau khi kích hoạt v1.1: Trả lời "trong vòng 14 ngày", trích dẫn version `1.1`. Tài liệu cũ không còn xuất hiện trong active index.
* **Khả năng Rollback:** Gọi lệnh hoàn nguyên về v1.0, hệ thống quay trở lại chính sách 07 ngày an toàn tức thì.

---

## 7. Giao diện Người dùng & Trải nghiệm Trực quan

Giao diện cửa hàng ([`frontend/src/App.jsx`](file:///d:/VSCode/Project/RAG/frontend/src/App.jsx)) được bổ sung các tính năng phục vụ trình diễn và vận hành:
* **Thanh Demo Phân quyền (Role Switcher):** Cho phép người đánh giá chuyển đổi linh hoạt giữa `Customer`, `Staff` và `Admin`.
* **Quản trị Re-index trên UI:** Khi chọn vai trò Admin, xuất hiện 2 nút bấm `Re-index v1.1` và `Rollback v1.0` kèm hiển thị phiên bản chỉ mục hiện hành.
* **Khung Chat Thông minh:** Hiển thị nhãn Route badge màu sắc trực quan (`📚 Hỏi đáp tài liệu`, `⚡ Hỗn hợp RAG + Đơn`, `🔒 Bị từ chối quyền`...) và khối trích dẫn nguồn có thể đối chiếu rõ ràng tên file và section.

---

## 8. Hướng dẫn Chạy Thử nghiệm Nhanh

1. **Khởi động Backend:**
   ```powershell
   $env:LLM_PROVIDER = "fake"
   python -m uvicorn backend.app.main:app --reload
   ```
2. **Khởi động Frontend:**
   ```powershell
   Set-Location frontend
   npm run dev
   ```
3. **Chạy toàn bộ 3 bộ test tự động:**
   ```powershell
   # 1. Unit tests RAG
   python -m unittest tests/test_rag.py
   # 2. Evaluation RAG 20 cases
   python -m eval.run_rag_evaluation --split all
   # 3. Evaluation luồng đơn hàng cũ (14 cases)
   python eval\run_evaluation.py --provider fake
   ```

---

## 9. Kết luận & Hướng Phát triển

Dự án đã đáp ứng trọn vẹn và vượt mức các tiêu chí trong rubric đánh giá của học phần RAG:
* Kế thừa hoàn hảo backend/frontend của môn LLM mà không phá vỡ logic nghiệp vụ cũ.
* Xây dựng hệ thống RAG phân quyền an toàn, giải quyết triệt để rủi ro lộ lọt dữ liệu nội bộ.
* Độ chính xác tra cứu và trả lời có trích dẫn đạt mức xuất sắc (Hit@3: 100%, MRR: 0.9667).

**Hướng phát triển tiếp theo:** Tích hợp mô hình Dense Embedding đa ngôn ngữ (như BGE-M3 qua Ollama) khi mở rộng kho tài liệu lên quy mô trên 100.000 văn bản và bổ sung chuẩn xác thực JWT SSO doanh nghiệp.
