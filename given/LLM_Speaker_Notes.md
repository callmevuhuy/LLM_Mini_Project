# Speaker Notes: Group 7 AI Live Commerce Order Assistant

**Thời lượng:** khoảng 6–8 phút  
**Thông điệp chính:** LLM hiểu câu chat. Backend kiểm tra dữ liệu và quyết định có được thực hiện thao tác hay không.

## Slide 1: AI Live Commerce Order Assistant (khoảng 35 giây)

Chào thầy cô và các bạn. Đây là website demo của Group 7, nơi khách có thể xem sản phẩm rồi nhắn bằng tiếng Việt để hỏi hoặc đặt hàng. Bọn mình dùng React/Vite, FastAPI và SQLite. Điểm chính mình sẽ trình bày là vai trò của LLM trong luồng này. Model đọc hiểu câu chat, còn backend kiểm tra dữ liệu trước khi tạo đơn nháp.

## Slide 2: Bài toán chat đặt hàng (khoảng 45 giây)

Khi bạn đặt hàng qua chat, câu chữ thường ngắn và không theo một mẫu cố định. Ví dụ: “Chốt 2 áo xanh size M, giao về Quận 7.” Câu này cho biết khách muốn đặt hàng, sản phẩm, màu, size và số lượng. Tuy nhiên, địa chỉ giao hàng mới chỉ là một phần, và ta vẫn cần tên người nhận cùng số điện thoại. Hệ thống phải nhận ra thông tin nào còn thiếu rồi hỏi lại. Không nên tự điền giúp khách.

## Slide 3: Ai làm phần nào? (khoảng 50 giây)

LLM diễn giải câu khách gửi và đề xuất các trường như intent, sản phẩm, biến thể, số lượng. Backend tìm SKU trong catalog, lấy giá và tồn kho từ dữ liệu, rồi xác minh phiên trước khi thay đổi đơn. JSON hợp lệ chưa chắc đã đúng. Vì thế, model không kết nối database và không tự ghi đơn. Đây là ranh giới quan trọng nhất trong thiết kế.

## Slide 4: Luồng xử lý tin nhắn (khoảng 55 giây)

Đầu tiên, backend kiểm tra phiên, độ dài tin nhắn và giới hạn tần suất. Sau đó, extractor trả về JSON. Backend parse kết quả, kiểm tra schema và kiểu dữ liệu. Khi các bước này đạt, hệ thống mới tra catalog, kiểm tra SKU, giá, tồn kho và quyền của phiên. Cuối cùng, backend chọn cách phản hồi: trả lời, hỏi thêm, báo hết hàng, tạo đơn `pending_confirmation`, handoff hoặc trả lỗi. Nếu mạng khiến client gửi lại cùng message id, idempotency giúp tránh xử lý trùng.

## Slide 5: Prompt và JSON (khoảng 55 giây)

Prompt `order-extraction-v2` nêu rõ nhiệm vụ, phạm vi và cấu trúc JSON cần trả về. Nội dung khách gửi được xem là dữ liệu đầu vào, không phải chỉ dẫn để thay đổi luật của hệ thống. Nếu câu chat không có một trường, model phải để null hoặc nêu trường còn thiếu. Evidence giúp mình đối chiếu kết quả với câu gốc. Confidence chỉ hỗ trợ chọn route, chưa được hiệu chuẩn thành xác suất. Cấu hình Ollama trong lần đánh giá là JSON mode, `think=false`, temperature 0 và context 4096. JSON mode giúp giữ định dạng; nó không chứng minh dữ liệu bên trong đúng.

## Slide 6: Kiểm chứng giá, tồn kho và số lượng (khoảng 55 giây)

Khi bạn hỏi giá hoặc tồn kho, backend đọc catalog SQLite. Model không phải nguồn của những con số đó. Nếu câu chat thiếu quantity hoặc variant, hệ thống hỏi lại thay vì tự mặc định. Trong evaluation, Qwen từng hiểu “chốt 13” thành 1. Nhóm đã thêm bước đối chiếu số lượng ghi rõ trong câu với kết quả model trước khi kiểm tra tồn. Khi checkout, backend kiểm tra tồn lần nữa, tự tính giá và chỉ tạo đơn chờ xác nhận. Đơn này chưa được thanh toán và không giữ hay trừ tồn kho.

## Slide 7: FakeLLM và Ollama (khoảng 45 giây)

FakeLLM chạy offline bằng rule/heuristic, phù hợp khi cần demo ổn định hoặc kiểm tra luồng nghiệp vụ. Ollama chạy model `qwen3.5:2b-q4_K_M` trên máy cục bộ để thử khả năng trích xuất từ cách nói tự nhiên. Trong dự án, hai provider dùng chung schema, catalog lookup và business rules. Chỉ bước extraction thay đổi. Kết quả đánh giá của Ollama là trên môi trường đã ghi trong báo cáo, không phải cam kết hiệu năng trên mọi máy.

## Slide 8: Kết quả và giới hạn đánh giá (khoảng 60 giây)

FakeLLM đạt 14/14 và Ollama đạt 14/14 trên bộ 14 case nhóm đã viết cho mỗi provider. Các case bao gồm happy path, thiếu hoặc mơ hồ, catalog/tồn kho, lỗi provider/format, safety và update. API smoke đã kiểm tra các luồng session, catalog, cart, checkout và order. Truy cập đơn thuộc phiên khác trả 404. Payload giả giá, tồn kho hoặc trạng thái trả 422 và không tạo order. Frontend production build cùng browser smoke cũng đạt.

Kết quả 14/14 chỉ nói về các fixture đó. Nhóm chưa chấm câu trả lời bằng rubric người thật và chưa nghiệm thu checkout thủ công trên browser. Lỗi provider trong bộ test được inject ở extractor, không phải tắt Ollama hay gây timeout thật.

## Slide 9: Kết luận và bước tiếp theo (khoảng 45 giây)

Project đã hoàn thành MVP local cho website demo, catalog, giỏ hàng, đơn nháp và trợ lý chat. LLM giúp hiểu câu khách gửi; backend kiểm tra dữ liệu và quyết định có được tạo draft hay không. Tiếp theo, nhóm nên chạy hết luồng checkout trên browser và màn hình nhỏ, rồi nhờ người thật chấm độ rõ ràng, hữu ích của phản hồi. Nếu muốn triển khai production, cần bổ sung auth/CSRF, migrations và rate limit dùng chung. Handoff hiện chỉ báo cần nhân viên hỗ trợ, chưa gửi tin cho nhân viên thật. Project không có thanh toán thật, không giữ hoặc trừ tồn kho, và không dùng dữ liệu khách hàng thật.

## Câu hỏi có thể gặp

### Vì sao nhóm không fine-tune model?

MVP cần nhận diện intent và trích xuất field trong phạm vi catalog nhỏ. Prompt có schema kết hợp với catalog lookup và rule backend đủ để kiểm tra cách làm này. Fine-tuning sẽ cần dữ liệu gán nhãn cùng một vòng đánh giá riêng, chưa cần cho mục tiêu demo.

### Vì sao không để LLM tự tạo đơn?

Model có thể hiểu sai câu chat hoặc trả field không đúng. Backend phải kiểm tra SKU, quantity, giá, tồn kho, quyền sở hữu và trạng thái đơn trước side effect. Nhờ vậy, JSON từ model không thể tự ghi database.

### 14/14 có nghĩa là model luôn đúng không?

Không. Đây là kết quả trên 14 case được viết cho mỗi provider. Cần thêm câu chat đa dạng và chấm bởi người thật trước khi kết luận rộng hơn.

### Hệ thống xử lý giá và tồn kho thế nào?

Backend đọc giá và tồn kho từ SQLite. Model chỉ giúp nhận ra khách đang hỏi sản phẩm hoặc biến thể nào. Nếu không map được rõ ràng, hệ thống cần hỏi lại.

### Cần làm gì trước khi triển khai production?

Cần hoàn thiện xác thực và CSRF, migrations, rate limit dùng chung, kiểm thử tải, quan sát lỗi, chính sách lưu dữ liệu và một kênh handoff thực sự. Những phần này nằm ngoài phạm vi MVP hiện tại.

## Nhắc trước khi demo

Hãy dùng tên, số điện thoại và địa chỉ giả. Chọn FakeLLM nếu cần demo ổn định; chọn Ollama khi service và model đã sẵn sàng. Gọi rõ đơn được tạo là `pending_confirmation`, không phải đơn đã thanh toán hay xác nhận. Khi nói về kết quả, nhắc rằng mỗi provider chỉ được đánh giá trên 14 case.

## Canva

Bản Canva đã humanize, có thể chỉnh sửa: https://www.canva.com/d/rF0R3X5BJucxfzC
