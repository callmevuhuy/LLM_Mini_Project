# Báo cáo Project RAG — AI Live Commerce Order Assistant

**Ngày cập nhật:** 30/10/2026
**Phạm vi:** trạng thái code, tài liệu và kết quả kiểm tra hiện có; không kiểm tra Ollama.

## 1. Project này dùng để làm gì?

Đây là phần mở rộng của project AI Live Commerce Order Assistant từ môn LLM & Prompt Engineering. Ứng dụng kế thừa website bán hàng, chat, catalog, tồn kho, giỏ hàng và luồng tạo/cập nhật đơn nháp; phần RAG bổ sung khả năng tra cứu tài liệu sản phẩm, FAQ và chính sách bằng hội thoại.

Project có hai luồng nghiệp vụ cần giữ tách biệt:

- **Tra cứu kiến thức:** tìm tài liệu phù hợp, kiểm tra quyền, trả lời kèm citation hoặc nêu rõ khi thiếu bằng chứng.
- **Thao tác vận hành:** giá hiện tại, tồn kho, SKU, quyền sở hữu và trạng thái đơn được kiểm tra từ backend/SQLite. RAG không được tự ghi hoặc thay đổi dữ liệu này.

## 2. Công nghệ và thành phần

| Thành phần | Công nghệ / vai trò |
|---|---|
| Giao diện | React 19, Vite; storefront, chat, route badge, citations và thao tác demo |
| API | FastAPI; định tuyến chat, session, authorization và RAG endpoints |
| Dữ liệu vận hành | SQLAlchemy và SQLite; catalog, biến thể/SKU, tồn kho, cart, đơn, audit/chat logs |
| RAG core | Python trong `src/rag.py`; manifest ingestion, Markdown H2 chunking, retrieval và answer templates |
| Router | `src/router.py`; phân biệt knowledge, order, mixed, safety và handoff bằng rule/regex |
| Chỉ mục | Bundle JSON chứa vector, chunk mapping và manifest; lọc quyền trước khi xếp hạng, cosine top-k |
| Provider kế thừa | Fake provider phục vụ demo và kiểm tra order flow; Ollama nằm ngoài phạm vi xác minh của báo cáo này |

**Lưu ý về embedding:** vector hiện tại là hashed word/character n-gram term-frequency, 1024 chiều và chuẩn hóa L2. Đây là vectorizer lexical chạy offline, không phải semantic embedding model. Vì thế retrieval có thể bắt từ khóa/mã chính xác nhưng chưa bảo đảm hiểu paraphrase hoặc ý nghĩa gần nhau như yêu cầu RAG ở mức đầy đủ.

## 3. Dữ liệu và nội dung hiện có

- Corpus mẫu có **12 tài liệu, 31 chunks**; 9 tài liệu public, 2 staff và 1 admin theo manifest hiện tại.
- Nhóm tài liệu gồm catalog sản phẩm/size, chính sách đổi trả/bảo hành/vận chuyển, FAQ và quy trình nội bộ giả lập.
- Có manifest riêng và corpus phiên bản 1.0, candidate 1.1; thay đổi demo chính là chính sách đổi trả từ 07 lên 14 ngày.
- Ingestion yêu cầu metadata thiết yếu, từ chối ID/tên file trùng, file không hợp lệ/rỗng, access level không hợp lệ và đường dẫn thoát khỏi corpus root.
- Giá, tồn kho và định danh SKU vận hành vẫn lấy từ catalog trong DB; tài liệu RAG không thay thế nguồn này.
- Bundle ghi model/vectorizer ID, revision, encoding, normalization, metric, chunk config, source hash, kích thước và số lượng. Loader xác minh checksum, mapping và vector dimensions trước khi sử dụng.

## 4. Luồng xử lý

```text
Người dùng / React
       |
       v
FastAPI: session, origin, role-token checks
       |
       v
Router
  |-- knowledge --> lọc quyền --> retrieval --> câu trả lời + citations
  |-- order ------> extractor kế thừa --> business validation --> SQLite
  |-- mixed ------> knowledge response + action qua luồng order có kiểm tra
  |-- safety/handoff --> từ chối an toàn hoặc chuyển hỗ trợ demo
```

`customer` chỉ tìm trên tài liệu public; `staff` cần token cấu hình phía backend và được tìm public/staff; `admin` cần token riêng và được tìm toàn bộ nội dung được cấp quyền. `X-User-Role` tự nó không phải chứng thực. Re-index yêu cầu session, origin hợp lệ khi có Origin, và admin token; active bundle được chọn qua file pointer để các tiến trình cùng host nạp lại.

## 5. Đã thực hiện đến đâu?

| Hạng mục | Trạng thái | Nhận xét |
|---|---|---|
| Kế thừa project LLM | **Đạt cho demo** | Giữ frontend, API, DB và order/cart flows. Fake evaluation hiện chạy 14/14 cùng API smoke/security probes. |
| Corpus/provenance | **Đạt với dữ liệu mẫu** | Đạt mức tối thiểu 12 docs/30 chunks, có access level, version, author và nguồn catalog giả lập. |
| Ingestion/chunking | **Đạt cho prototype** | Manifest-driven, H2 chunking ổn định, kiểm tra metadata và đường dẫn. |
| Embedding/retrieval | **Một phần** | Có vector và cosine retrieval, nhưng vectorizer lexical chưa đạt semantic embedding; recall vẫn có lỗi trên dev cases. |
| Phân quyền | **Đạt ở mức demo cục bộ** | Pre-filter trước ranking; backend yêu cầu role token cho staff/admin. Chưa phải hệ thống xác thực doanh nghiệp. |
| Grounding/citation | **Một phần** | Có citation resolve được tới chunk/metadata; đã sửa một lỗi chọn nhầm tài liệu đổi trả/giao hàng. Câu trả lời vẫn có heuristic templates và chưa qua human claim review. |
| Tích hợp UI/API | **Đạt ở mức demo** | Có knowledge/order/mixed/handoff, citation và thao tác re-index. Đánh giá mixed tự động hiện chưa chứng minh end-to-end action correctness cho từng case. |
| Evaluation | **Một phần** | Có 20 case, split dev/test và các metric cơ bản. Claim-support là string proxy; báo cáo chưa có human review và failure analysis đủ sâu theo tối thiểu 5 case/layer. |
| Re-index/rollback | **Đã triển khai; nghiệm thu một phần** | Có bundle v1.0/v1.1, pointer nguyên tử và audit event. Đã kiểm tra API activation/reload với môi trường tạm; chưa có kiểm soát đa host hoặc đo tải/độ trễ sản xuất. |
| Demo/tài liệu | **Một phần** | README, architecture, workflow, evaluation/re-index reports và demo script có; một số bước demo cần chạy lại sau thay đổi câu trả lời để xác nhận đúng UI thực tế. |

## 6. Kết quả kiểm tra được ghi nhận

| Lệnh/kiểm tra | Kết quả gần nhất |
|---|---:|
| `python -m unittest tests/test_rag.py -v` | 10/10 passed |
| RAG evaluation — toàn bộ 20 case | Hit@3 100%; Recall@5 93.89%; MRR 0.9000 |
| Route/status expected-match | 100% / 100% trên authored set |
| Citation metadata + role eligibility | 100% resolve trong evaluator hiện tại |
| Claim-support string proxy | 70% toàn bộ; Dev 70%; Test 70% |
| Safe abstention / access denied | 100% / 100% trên case tương ứng |
| Legacy Fake flow | 14/14; API smoke và các security probes trong runner đạt |
| Frontend `npm run build` | Thành công |
| Probe API bổ sung | Role admin giả không token bị 403; re-index thiếu token bị 403; token hợp lệ được chấp nhận; CORS preflight 200 |

Các kết quả này xác nhận hành vi trên bộ dữ liệu demo đã viết. Chúng không chứng minh chất lượng production: evaluator kiểm tra chuỗi kỳ vọng cho claim support, citation resolve kiểm tra định danh/metadata, và bộ case chỉ có 20 câu.

## 7. Đối chiếu với guiding docs

Nguồn đối chiếu chính là [`Project_RAG_Requirements.pdf`](Project_RAG_Requirements.pdf), [`RAG_Workflow.md`](RAG_Workflow.md), [`RAG_Architecture.md`](RAG_Architecture.md), cùng README và evaluation report.

| Yêu cầu guiding docs | Đánh giá hiện tại |
|---|---|
| Giữ website/API/DB/catalog/order từ project LLM; RAG không tự ghi đơn | **Đạt ở demo**; kế thừa và order evaluation 14/14. |
| Có knowledge corpus tối thiểu 12 tài liệu hoặc 30 chunks, có provenance và phân quyền | **Đạt với corpus mẫu**; manifest có 12 docs/31 chunks và các role level. |
| Ingestion validate file, ID, encoding, metadata; chunk có source/version/access/section | **Đạt phần chính**; kiểm tra hiện có trong ingestion và chunk model. Cần tiếp tục kiểm thử các lỗi encoding/corpus độc hại ở pipeline tích hợp. |
| Bundle ghi thông tin embedding/encoding/metric/chunk config và validate trước khi serve | **Đạt ở cấu trúc prototype**; metadata có đủ trường, checksum phát hiện hỏng vô ý. Hash không ký nguồn gốc bundle. |
| Embedding tương thích cho query/document và đáp ứng tra cứu ngữ nghĩa | **Chưa đạt đầy đủ**; hiện mới là hashed lexical vectorizer, chưa có semantic model và đánh giá paraphrase độc lập đủ mạnh. |
| Role pre-filter trước ranking/context/citation | **Đạt trong code path đã kiểm tra**; staff/admin demo roles được bảo vệ bằng token backend, nhưng chưa có user identity/SSO hay multi-tenant policy. |
| Xử lý empty/no-candidate/index lỗi, no-evidence, access-denied và câu hỏi mâu thuẫn | **Một phần**; no-evidence/access-denied có case; xử lý evidence mâu thuẫn và lỗi index qua API/UI chưa được đánh giá toàn diện. |
| Claim quan trọng chỉ được nói khi có evidence và citation hỗ trợ | **Một phần**; citation resolve tốt nhưng chỉ 70% expected strings xuất hiện và chưa có reviewer gán supported/partial/unsupported/contradicted/unverifiable. |
| Mixed query tách tri thức và action, action qua validation cũ | **Đạt một phần**; router/UI có luồng mixed, nhưng metric mixed chỉ kiểm tra route+citation chứ chưa thực thi mỗi action case qua API trong RAG evaluator. |
| Tối thiểu 20 case, đủ 7 nhóm, dev/test, đo retrieval/safety/access/mixed | **Đạt mức tối thiểu về số lượng và nhóm**; metrics đã có, song evidence coverage, false refusal và human claim review còn thiếu/đơn giản. |
| Phân tích ít nhất 5 lỗi/near-miss theo các tầng và cải tiến có kiểm soát | **Chưa chứng minh đủ**; đã sửa một số lỗi ranking/routing/grounding, nhưng báo cáo hiện thiếu bảng case-by-case có nguyên nhân, layer, thay đổi và kết quả trước/sau cho ít nhất 5 lỗi. |
| Re-index 1.0→1.1, xác minh version, activate, rollback, audit an toàn | **Đạt một phần**; API pointer và audit có, version switching đã thử bằng DB/pointer tạm; cần bổ sung regression test tự động cho answer/citation 7→14→7 ngày và concurrency. |
| Demo 10–12 phút + Q&A thể hiện các luồng bắt buộc | **Một phần**; script đã có nhưng cần kiểm tra lại từng lời thoại với behavior UI sau các thay đổi mới nhất. |

## 8. Hạn chế và việc nên làm tiếp

### Ưu tiên cao

1. **Bổ sung semantic embedding** phù hợp môi trường không dùng Ollama; ghi model/version, encoding/query-document, normalization và cách tái tạo bundle. So sánh với baseline lexical trên dev trước khi đánh giá frozen test.
2. **Nâng cấp đánh giá grounding:** reviewer chấm từng claim/citation theo supported, partial, unsupported, contradicted hoặc unverifiable; bổ sung evidence coverage, false refusal và citation support rate.
3. **Viết lại failure analysis có bằng chứng:** ít nhất 5 case ghi rõ lỗi, tầng gây lỗi, nguyên nhân, thay đổi thử trên dev và kết quả trên test.
4. **Bổ sung integration tests cho RAG API:** mixed knowledge+order, access boundary, citation fields, re-index 1.0→1.1→1.0 và version/citation sau reload.

### Trước khi triển khai ngoài demo

- Thay shared demo tokens bằng identity/authZ phù hợp, quản lý/rotate secret và bật HTTPS/CSRF policy.
- Dùng signature hoặc registry tin cậy cho bundle; checksum đặt trong cùng file chỉ phát hiện corruption không chủ ý.
- Thiết kế activation có lock/transaction phù hợp nếu chạy nhiều host; hiện pointer chỉ chia sẻ qua filesystem cùng host.
- Đánh giá query rỗng, conflict/version policy, lỗi index, tải lớn, logging/privacy và khả năng phục hồi bằng kịch bản triển khai thật.
- Chỉ dùng dữ liệu mock/anonymized; không nạp PII hoặc tài liệu nội bộ thật vào demo.

## 9. Cách chạy lại các kiểm tra

```powershell
python -m unittest tests/test_rag.py -v
python -m eval.run_rag_evaluation --split dev
python -m eval.run_rag_evaluation --split test
python -m eval.run_rag_evaluation --split all
python eval/run_evaluation.py --provider fake
Set-Location frontend; npm run build
```

Không chạy Ollama trong lần đánh giá này theo phạm vi đã thống nhất.
