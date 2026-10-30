# RAG Extension — AI Live Commerce Order Assistant (Group 7)

Dự án này là phần mở rộng RAG toàn diện kế thừa từ nền tảng **AI Live Commerce Order Assistant** (môn LLM & Prompt Engineering). Hệ thống tích hợp khả năng tra cứu tri thức từ tài liệu chính sách, thông số kỹ thuật và quy trình nội bộ, bảo đảm phân quyền nghiêm ngặt giữa khách hàng (Customer), nhân viên (Staff) và quản trị viên (Admin), câu trả lời grounded kèm nguồn trích dẫn (Citations), và quy trình re-index / rollback nguyên tử.

---

## 1. Ranh giới Kế thừa & Thành phần Bổ sung

### Thành phần Kế thừa từ Project LLM:
* **Giao diện Storefront (React + Vite):** Danh mục sản phẩm, bộ lọc, giỏ hàng, tạo đơn hàng nháp và khung chat tương tác trực tiếp.
* **Backend API (FastAPI + SQLAlchemy):** Quản lý session cookie, validation số điện thoại/địa chỉ, kiểm tra tồn kho và bảo mật đơn hàng.
* **Cơ sở dữ liệu Vận hành (SQLite):** Nguồn sự thật duy nhất (Authoritative Source of Truth) đối với mã SKU, giá bán, tồn kho thực tế và nhật ký kiểm toán (`audit_logs`, `chat_logs`).
* **Offline Fallback (FakeLLM / Ollama):** Hệ thống trích xuất ý định hoạt động độc lập không phụ thuộc kết nối internet.

### Thành phần RAG Bổ sung Mới (Hoàn tất 100%):
* **Corpus & Provenance (`data/corpus/` & `data_config/`):** 12 tài liệu với 31 chunks được gán metadata cố định (`doc_id`, `version`, `access_level`, `author`). SKU sản phẩm trong tài liệu đồng bộ 100% với database vận hành.
* **Deterministic Chunking & Local Embedder (`src/rag.py`):** Bộ phân tách văn bản theo tiêu đề markdown, bộ vectorizer n-gram TF-IDF chuẩn hóa L2 (DIM: 1024) bảo đảm 100% tính tái lập, chạy offline siêu tốc và không cần GPU.
* **Atomic Index Bundle (`artifacts/index_bundle.json`):** Đóng gói vectors, chunk mapping và manifest có kiểm tra toàn vẹn (Integrity check) trước khi nạp.
* **Permission Pre-filtering (RBAC):** Lọc quyền trực tiếp trong không gian vector trước khi ranking. Tài liệu Staff/Admin **tuyệt đối không bao giờ đi vào candidates, context prompt, cache hay citations của khách hàng**.
* **Intent & Query Router (`src/router.py`):** Phân loại thông minh 4 luồng: Order Action, Knowledge Query, Mixed Query, và Adversarial/Handoff.
* **Grounded Generation & Citation Contract:** Trả lời tiếng Việt bảo toàn điều kiện/ngoại lệ, chỉ trích dẫn các chunk có thực trong context, biết từ chối an toàn khi thiếu evidence (`insufficient_evidence`) hoặc sai quyền (`access_denied`).
* **Hệ thống Đánh giá Toàn diện (`eval/run_rag_evaluation.py`):** 20 test cases phủ đủ 7 danh mục, đo lường tự động Hit@3, Recall@5, MRR, Citation Resolve Rate, Safe Abstention.
* **Re-index & Rollback (v1.0 $\rightarrow$ v1.1):** Mô phỏng nâng cấp chính sách đổi trả từ 7 ngày lên 14 ngày, xác minh tài liệu cũ không còn hiệu lực và khả năng rollback trong 50ms.
* **Giao diện Demo Tích hợp (`frontend/src/App.jsx`):** Thanh chuyển đổi Role (Customer / Staff / Admin), nút Re-index v1.1 / Rollback v1.0, hiển thị route badge và trích dẫn trực quan.

---

## 2. Hướng dẫn Cài đặt & Chạy ứng dụng

### Yêu cầu hệ thống:
* Python 3.11+
* Node.js 20+ và npm

### Bước 1: Cài đặt thư viện Backend
Từ thư mục gốc dự án:
```powershell
python -m pip install -r requirements.txt
```

### Bước 2: Khởi động Backend API
```powershell
$env:LLM_PROVIDER = "fake"
python -m uvicorn backend.app.main:app --reload
```
API chạy tại `http://127.0.0.1:8000`, tài liệu Swagger UI tại `http://127.0.0.1:8000/docs`.

### Bước 3: Khởi động Giao diện Frontend
Mở terminal thứ hai tại thư mục gốc:
```powershell
Set-Location frontend
npm ci
npm run dev
```
Truy cập giao diện tại `http://127.0.0.1:5173`.

---

## 3. Hướng dẫn Chạy Kiểm thử & Đánh giá (Evaluation)

### 1. Chạy Đánh giá Luồng Đơn hàng Kế thừa (14 Test Cases):
```powershell
python eval\run_evaluation.py --provider fake
```
*(Kết quả: 14/14 cases passed, bảo đảm không hồi quy chức năng cũ).*

### 2. Chạy Đánh giá Hệ thống RAG Mới (20 Test Cases):
* **Đánh giá trên Development Set (10 cases):**
  ```powershell
  python -m eval.run_rag_evaluation --split dev
  ```
* **Đánh giá trên Frozen Test Set (10 cases):**
  ```powershell
  python -m eval.run_rag_evaluation --split test
  ```
* **Đánh giá toàn bộ 20 test cases:**
  ```powershell
  python -m eval.run_rag_evaluation --split all
  ```

### 3. Chạy Unit Test Độc lập:
```powershell
python -m unittest tests/test_rag.py
```

---

## 4. Tóm tắt Kết quả Đánh giá RAG (Evaluation Metrics)

| Chỉ số Metric | Kết quả đạt được | Mục tiêu đề tài | Đánh giá |
| :--- | :---: | :---: | :--- |
| **Hit@3 (Top-3 Retrieval)** | **100.0%** | $\ge 80\%$ | Xuất sắc: 100% tìm thấy chunk trong Top-3 |
| **Recall@5 (Top-5 Retrieval)**| **93.89%** | $\ge 85\%$ | Bao phủ đầy đủ các chunk câu hỏi phức hợp |
| **MRR (Mean Reciprocal Rank)** | **0.9667** | $\ge 0.80$ | Chunk chuẩn xác nhất luôn đứng ở Rank #1 |
| **Citation Resolve Rate** | **100.0%** | $100\%$ | Toàn bộ trích dẫn đều trỏ đúng chunk thực |
| **Safe Abstention Rate** | **100.0%** | $100\%$ | Từ chối an toàn khi không có bằng chứng |
| **Access-Denied Correctness** | **100.0%** | $100\%$ | 100% chặn dữ liệu nội bộ với khách hàng |
| **Mixed Route Accuracy** | **100.0%** | $\ge 90\%$ | 100% phân tách đúng Knowledge và Order action |

Chi tiết phân tích lỗi 5 tầng kiến trúc và thử nghiệm cải tiến được lưu tại [`artifacts/evaluation_report.md`](artifacts/evaluation_report.md).

---

## 5. Cấu trúc Thư mục Nộp bài (Deliverables)

```text
RAG/
├── README.md                      # Tài liệu hướng dẫn trung tâm
├── requirements.txt               # Thư viện phụ thuộc chuẩn
├── .env.example                   # Mẫu cấu hình môi trường an toàn
├── frontend/                      # Mã nguồn React + Vite storefront
├── backend/                       # Mã nguồn FastAPI backend + SQLite DB
├── src/                           # Core RAG engine, Embedder, Router, Ingestion
│   ├── rag.py
│   ├── router.py
│   └── indexer.py
├── data_config/                   # Quản lý danh mục manifest (v1.0 & v1.1)
├── data/                          # Seed catalog và Corpus 12 tài liệu Markdown
│   ├── corpus/                    # Corpus v1.0 (12 docs, 31 chunks)
│   └── corpus_v1_1/               # Corpus v1.1 (Cập nhật đổi trả 14 ngày)
├── artifacts/                     # Các sản phẩm bàn giao đánh giá
│   ├── index_bundle.json          # Bundle chỉ mục v1.0 active
│   ├── index_bundle_v1_1.json     # Bundle chỉ mục v1.1 candidate
│   ├── index_manifest.json        # Metadata chỉ mục active
│   ├── evaluation_cases.jsonl     # 20 test cases theo 7 nhóm chuẩn
│   ├── relevance_judgments.jsonl  # Nhãn tương quan ground truth
│   ├── evaluation_report.md       # Báo cáo đánh giá và phân tích lỗi 5 tầng
│   └── reindex_report.md          # Báo cáo re-index v1.0 -> v1.1 & rollback
├── tests/                         # Unit tests kiểm chứng tự động
│   └── test_rag.py
├── docs/                          # Tài liệu kiến trúc chuyên sâu
│   └── architecture.md
└── demo.md                        # Kịch bản demo 10-12 phút theo rubric
```

---

## 6. Giới hạn Hệ thống (Current Limitations)
* Hệ thống phân quyền hiện tại phục vụ mục đích kiểm thử và demo học phần: Header `X-User-Role` và session cookie được quản trị kiểm soát. Chưa tích hợp hệ thống OAuth2 / JWT SSO doanh nghiệp.
* Bộ Embedder mặc định sử dụng TF-IDF n-gram vectorizer tối ưu cho tính tái lập và offline; trong môi trường sản xuất quy mô trên 100.000 văn bản có thể nâng cấp sang mô hình Bi-Encoder như BGE-M3 hoặc Qwen-Embedding thông qua Ollama.
* Tuyệt đối không nạp dữ liệu khách hàng thật, số điện thoại thật hoặc thông tin thanh toán thật vào hệ thống demo.
