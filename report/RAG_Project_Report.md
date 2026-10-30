# Báo cáo Dự án RAG — AI Live Commerce Order Assistant

**Cập nhật:** 30/10/2026
**Phạm vi:** tiếp quản và kiểm tra project RAG kế thừa; Ollama không nằm trong lần xác minh này.

## Tóm tắt

Project nối RAG vào trợ lý thương mại LLM hiện có. Backend/SQLite tiếp tục là nguồn dữ liệu chuẩn cho SKU, giá, tồn kho và đơn hàng. Corpus mẫu có 12 tài liệu/31 chunks, phân quyền `public`, `staff`, `admin`; index được tạo offline bằng hashed word/character n-gram term-frequency vectors 1024 chiều.

Vectorizer hiện tại là lexical, không phải semantic embedding model. Câu trả lời dùng template xác định và citations từ corpus, không gọi Ollama. API kiểm tra role token demo cho staff/admin, lọc tài liệu trước ranking, và lưu lựa chọn bundle active qua file pointer cùng host.

## Các cập nhật trong lượt tiếp quản

- Chặn giả mạo `X-User-Role`: staff/admin cần token cấu hình ở backend; re-index cần session, origin hợp lệ và admin token.
- Ingestion từ chối metadata phân quyền thiếu; loader kiểm tra SHA-256, số lượng, vector dimensions, access levels và chunk IDs.
- Sửa trường hợp truy vấn thời hạn đổi trả bị chọn nhầm tài liệu giao hàng; citation thu hẹp theo nguồn chủ đề.
- Hoàn thiện route cho SKU, quy cách, thiếu hàng, sizing và câu safety. Bảo toàn các follow-up của order nháp.
- Cập nhật evaluator để báo route/status và xác minh citation metadata/role eligibility.
- Đồng bộ workflow, architecture, README và báo cáo để xóa các kết luận lỗi thời.

## Kết quả kiểm tra

| Kiểm tra | Kết quả |
|---|---:|
| RAG unit tests | 9/9 |
| RAG cases | 20; Hit@3 100%, Recall@5 93.89%, MRR 0.9000 |
| Route / status accuracy | 100% / 100% |
| Citation metadata resolution | 100% |
| Claim string-support proxy | 70% |
| Safe abstention / access denied | 100% / 100% |
| Inherited Fake provider flow | 14/14; API smoke và security probes đạt |
| Frontend production build | Thành công |
| API authorization probes | Header admin giả mạo 403; re-index thiếu token 403; token đúng role demo được chấp nhận; CORS preflight 200 |

Claim-support chỉ kiểm tra chuỗi expected trong câu trả lời; mixed evaluator xác nhận route/citation, không tự chứng minh mỗi thao tác đơn hàng đã thực thi. Các con số chỉ phản ánh test set demo nhỏ do nhóm viết.

## Rủi ro và giới hạn còn lại

1. Shared demo tokens không thay thế xác thực danh tính doanh nghiệp, SSO, phân tenant hay rotation secrets.
2. Checksum không ký nguồn gốc bundle; người có quyền sửa cả file và hash có thể tạo bundle thay thế.
3. Active pointer dùng filesystem cùng host, chưa có distributed lock/multi-host consistency.
4. Router, retrieval và answer templates là heuristic; paraphrase ngoài test set có thể sai hoặc abstain.
5. Chưa kiểm tra hiệu năng tải lớn, kiểm toán claim bởi con người, artifact signing hoặc Ollama/provider ngoài.

Chi tiết kiến trúc ở [`given/RAG_Architecture.md`](../given/RAG_Architecture.md), workflow ở [`given/RAG_Workflow.md`](../given/RAG_Workflow.md), và lần đo evaluator ở [`artifacts/evaluation_report.md`](../artifacts/evaluation_report.md).
