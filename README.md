# RAG Extension — AI Live Commerce Order Assistant

Dự án mở rộng từ trợ lý đặt hàng LLM kế thừa, bổ sung tra cứu tài liệu có phân quyền. RAG dùng corpus mẫu local và vectorizer hashed n-gram; pipeline không phụ thuộc Ollama. Giá, SKU, tồn kho và đơn hàng vẫn do API/SQLite quản lý.

## Trạng thái hiện tại

- 12 tài liệu, 31 chunks; corpus v1.0 và candidate v1.1.
- Tìm kiếm lexical bằng hashed word/character n-gram term-frequency vectors (1024 chiều), cosine similarity. Đây **không phải semantic embedding model**.
- Customer chỉ xem tài liệu public; staff/admin yêu cầu token demo do backend cấu hình.
- API kiểm tra bundle SHA-256, truy vấn có citations, no-evidence/access-denied, mixed query, và đổi version qua active pointer.
- Đạt 20/20 expected route và status trong bộ RAG cases hiện tại. Bộ test nhỏ do nhóm biên soạn, chưa chứng minh chất lượng production.

## Chạy local

Yêu cầu Python 3.11+ và Node.js 20+.

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
$env:LLM_PROVIDER = "fake"
python -m uvicorn backend.app.main:app --reload
```

Mở terminal khác:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Frontend mặc định chạy `http://127.0.0.1:5173`, API tại `http://127.0.0.1:8000`; Swagger ở `/docs`. Demo staff/admin bị tắt nếu chưa đặt `DEMO_STAFF_TOKEN` và `DEMO_ADMIN_TOKEN` trong môi trường backend. Chỉ sử dụng token giả cho demo local; UI sẽ hỏi token và giữ trong bộ nhớ tab.

## Build index

```powershell
python -m src.indexer --version 1.0
python -m src.indexer --version 1.1 --corpus data/corpus_v1_1 --manifest data_config/corpus_manifest_v1_1.json --output artifacts/index_bundle_v1_1.json
```

Bundle có SHA-256 để phát hiện hỏng vô ý, metadata vectorizer/chunking và source hashes. Hash không phải chữ ký chống sửa đổi có chủ ý. API re-index chỉ nhận version đã biết, cần session và admin token; activation dùng `artifacts/active_index.json` để các worker cùng host nạp lại version mới. Hệ thống chưa có distributed lock cho nhiều máy chủ.

## Kiểm tra

```powershell
python -m unittest tests/test_rag.py -v
python -m eval.run_rag_evaluation --split dev
python -m eval.run_rag_evaluation --split test
python -m eval.run_rag_evaluation --split all
python eval/run_evaluation.py --provider fake
Set-Location frontend; npm run build
```

Kết quả RAG hiện tại (20 authored cases): Hit@3 **100%**, Recall@5 **93.89%**, MRR **0.9000**, citation metadata resolution **100%**, claim-support string proxy **70%**, safe abstention **100%**, access-denied **100%**, route/status accuracy **100%**. Inherited fake-flow suite: **14/14**. Đây là kiểm tra tái lập trên dữ liệu demo; citation resolution và string matching không thay thế đánh giá claim bởi người đọc.

## Cấu trúc

- `backend/`: FastAPI, SQLite, order handling và API RAG
- `src/`: ingestion, vectorizer, retrieval, answer templates và router
- `frontend/`: React/Vite storefront và chat
- `data/`, `data_config/`: corpus và manifests giả lập
- `artifacts/`: index bundles, evaluation cases và báo cáo
- `given/`: workflow và architecture guide
- `tests/`, `eval/`: unit/integration/evaluation scripts

## Giới hạn bảo mật và chất lượng

Đây là demo local: role tokens là shared secrets, không có SSO hay danh tính doanh nghiệp; frontend giữ token trong bộ nhớ tab; HTTP local không mã hóa. Không đưa dữ liệu khách hàng thật hoặc secret vào corpus. SHA-256 trong bundle không cung cấp xác thực nguồn gốc. Retriever dùng lexical features nên có thể bỏ lỡ cách diễn đạt mới; answer templates và router là heuristic. Xem [kiến trúc](given/RAG_Architecture.md), [workflow](given/RAG_Workflow.md), và [báo cáo đánh giá](artifacts/evaluation_report.md).
