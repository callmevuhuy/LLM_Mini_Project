# RAG Project Workflow

## Mục tiêu

Mở rộng trợ lý thương mại LLM kế thừa bằng ingestion tài liệu, vector retrieval có phân quyền, câu trả lời tiếng Việt có nguồn, và đánh giá. Giá, tồn kho, SKU hợp lệ và trạng thái đơn vẫn do backend/SQLite quyết định; câu trả lời RAG không được ghi dữ liệu nghiệp vụ.

## Trạng thái hiện tại (30/10/2026)

| Giai đoạn | Trạng thái | Bằng chứng / giới hạn |
|---|---|---|
| Baseline LLM và tích hợp | Hoàn tất cho demo | FastAPI, React, SQLite, luồng giỏ hàng/đơn, Fake provider; legacy eval chạy 14/14 sau cập nhật router. |
| Corpus và provenance | Hoàn tất cho corpus mẫu | 12 tài liệu, 31 chunks, public/staff/admin; manifest bắt buộc metadata và từ chối đường dẫn ra ngoài corpus. |
| Ingestion và index | Một phần | Chunk Markdown H2, vector hashed word/character n-gram TF, bundle có SHA-256 và metadata. Có retrieval offline nhưng chưa dùng semantic embedding model, nên mục tiêu embedding chất lượng ngữ nghĩa chưa hoàn tất. |
| Permission-aware RAG | Hoàn tất cho demo cục bộ | Lọc role trước xếp hạng; staff/admin cần token backend cấu hình. Token không đồng nghĩa với SSO hay danh tính người dùng doanh nghiệp. |
| API/UI | Hoàn tất cho demo | Knowledge, mixed, order và handoff; role token chỉ giữ trong bộ nhớ frontend. API re-index yêu cầu admin token, session và origin hợp lệ. |
| Evaluation | Đạt bộ case đã viết | 20 RAG cases, route/status accuracy 100%, claim-support proxy 70%; 14/14 inherited fake-flow cases. Đây là corpus test nhỏ, không đại diện chất lượng sản xuất. |
| Re-index/rollback | Đã triển khai; cần vận hành kiểm soát | Bundle v1.0/v1.1 đã có; API đổi file con trỏ active bằng replace nguyên tử. Không có distributed lock hoặc kiểm soát đa máy chủ. |

## Quy tắc làm việc

1. Đọc `RAG_Architecture.md`, `Project_RAG_Requirements.pdf`, README và tài liệu LLM kế thừa trước khi đổi pipeline.
2. Giữ dữ liệu vận hành trong DB. Không dùng RAG làm nguồn giá/tồn kho hoặc cho phép câu trả lời RAG gọi hành động ghi.
3. Chỉ dùng dữ liệu giả đã được phép; không commit secret, PII thật hoặc tài liệu nội bộ chưa được duyệt.
4. Sửa code thì cập nhật caller, tests, fixture/config và tài liệu liên quan. Báo cáo số liệu từ lần chạy thực tế, ghi rõ giới hạn của evaluator.

## Các ranh giới phải giữ

- Customer chỉ truy xuất `public`; staff truy xuất `public` + `staff`; admin truy xuất tất cả.
- Header `X-User-Role` là lựa chọn role demo, không phải chứng thực. Staff/admin chỉ được chấp nhận khi token khớp `DEMO_STAFF_TOKEN`/`DEMO_ADMIN_TOKEN` phía backend.
- Index bundle phải qua checksum và kiểm tra cấu trúc trước khi load. SHA-256 trong cùng file phát hiện hỏng vô ý; nó không chứng minh nguồn gốc trước kẻ có thể sửa cả bundle lẫn hash.
- Citation phải resolve đúng metadata chunk. Không dùng citation resolution như bằng chứng tự động rằng mọi claim đều đúng.
- Các case có expected evidence rỗng không tính Recall@5. Bộ test giữ split dev/test nhưng do con người soạn và còn nhỏ.

## Lệnh kiểm tra

```powershell
python -m unittest tests/test_rag.py -v
python -m eval.run_rag_evaluation --split all
python eval/run_evaluation.py --provider fake
Set-Location frontend; npm run build
```

Không chạy Ollama nếu chưa có model/service và yêu cầu hiện tại không cần kiểm tra provider đó.
