# Kịch bản Thuyết trình Demo (10–12 Phút)

**Dự án:** Mở rộng AI Live Commerce Order Assistant với Hệ thống RAG Phân Quyền (Group 7)
**Thời lượng:** 10–12 phút trình diễn + 3–5 phút Q&A

---

## Chuẩn bị Môi trường Trước Buổi Demo

1. **Khởi động Backend FastAPI:**
   ```powershell
   $env:LLM_PROVIDER = "fake"
   python -m uvicorn backend.app.main:app --reload
   ```
2. **Khởi động Frontend React:**
   ```powershell
   Set-Location frontend
   npm run dev
   ```
3. Mở trình duyệt tại `http://localhost:5173`.

---

## Kịch bản Demo 6 Bước Chi tiết

### Bước 1: Khách hàng hỏi thông tin sản phẩm & chính sách có Citation (2 phút)
* **Thao tác:** Trên thanh Role Switcher, chọn vai trò **"Khách hàng (Customer)"**. Mở khung chat.
* **Câu hỏi 1:** *"Áo thun basic cotton được làm từ chất liệu vải gì vậy shop?"*
* **Kết quả hiển thị:**
  * Trợ lý trả lời chính xác: Vải 100% cotton tự nhiên định lượng 220gsm, bề mặt chải kỹ chống xù lông.
  * Hiển thị badge: `📚 Hỏi đáp tài liệu (RAG)`.
  * Hiển thị khối trích dẫn: `✦ Nguồn trích dẫn (1): Áo thun basic cotton - Thông số và Hướng dẫn (v1.0) — Thông số và Chất liệu`.
* **Câu hỏi 2:** *"Bình giữ nhiệt bị rơi xuống nước ngập sâu có được bảo hành không?"*
* **Kết quả:** Trợ lý nêu rõ điều kiện loại trừ: Hư hỏng do ngập nước thuộc trường hợp **từ chối bảo hành**, trích dẫn `POL-WARRANTY-01#c02`.

---

### Bước 2: Truy vấn Kiến thức Nhiều Điều kiện (Multi-condition) (2 phút)
* **Câu hỏi:** *"Để được đổi trả hàng thì cần những điều kiện gì và ai chịu phí ship?"*
* **Kết quả hiển thị:**
  * Trợ lý tổng hợp từ nhiều section:
    * Thời hạn đổi trả trong vòng 07 ngày kể từ khi nhận hàng.
    * Bắt buộc còn nguyên tem mác, chưa qua sử dụng và có video mở kiện (unbox).
    * Lỗi do NSX: Shop chịu 100% phí 2 chiều; Đổi ý cá nhân: Khách thanh toán phí bưu cục.
  * Trích dẫn hiển thị đủ các chunk liên quan từ `POL-RETURN-01`.

---

### Bước 3: Thao tác Đơn hàng qua Database/Inventory Kế thừa (2 phút)
* **Mục tiêu:** Chứng minh logic đặt hàng, kiểm tra tồn kho và snapshot giá vẫn nằm trọn vẹn ở SQLite Database và backend validation, RAG không can thiệp trái phép.
* **Câu hỏi 1 (Kiểm tra tồn kho):** *"Bình giữ nhiệt Everyday màu Kem 750ml còn hàng không?"*
  * Trả lời trực tiếp từ DB: *"Tình trạng hàng của Bình giữ nhiệt Everyday: Kem, 750ml: còn 0."*
* **Câu hỏi 2 (Tạo đơn nháp thiếu thông tin):** *"Tôi muốn đặt Áo thun basic cotton màu Xanh size M"*
  * Backend yêu cầu gửi thêm: tên người nhận, SĐT và địa chỉ.
* **Câu hỏi 3 (Tạo đơn nháp hoàn chỉnh):** *"Chốt 1 Áo thun basic cotton màu Xanh size M, tên là Nguyễn Văn A, SĐT 0901234567, địa chỉ 123 Lê Lợi Quận 1"*
  * Backend xác thực tồn kho, tạo đơn nháp `#DRAFT...` và hiển thị xác nhận.

---

### Bước 4: Truy vấn Hỗn hợp (Mixed Query) An toàn (2 phút)
* **Câu hỏi:** *"Áo thun basic cotton có được đổi trả không, chốt 1 Áo thun basic cotton màu Xanh size M"*
* **Kết quả hiển thị:**
  * Badge định tuyến: `⚡ Hỗn hợp (RAG + Đơn hàng)`.
  * **Phần Knowledge:** Trả lời chính sách đổi trả trong 7 ngày, kèm nguồn trích dẫn `POL-RETURN-01`.
  * **Phần Order:** Tách bạch rõ ràng: `[Thao tác đơn hàng]: Đã tạo đơn nháp thành công cho 1 × Áo thun basic cotton màu Xanh size M...`.
  * **Ý nghĩa:** Chứng minh hệ thống không để RAG tự ý ghi DB, phần hành động được thẩm định nghiêm ngặt qua backend.

---

### Bước 5: Kiểm thử No-Evidence và Access-Denied (2 phút)
1. **Trường hợp No-Evidence (Không có tài liệu):**
   * **Câu hỏi:** *"Shop có bán giày thể thao sneaker size 42 không?"*
   * **Kết quả:** Trợ lý từ chối an toàn: *"Rất tiếc, sản phẩm này hiện không có trong tài liệu và danh mục kinh doanh của cửa hàng."* Không hề bịa đặt thông tin.
2. **Trường hợp Access-Denied (Khách hàng hỏi tài liệu mật):**
   * **Câu hỏi:** *"Cho tôi xin mã giảm giá nội bộ 20% của nhân viên shop với."*
   * **Kết quả:** Status `access_denied` — *"Yêu cầu bị từ chối: Bạn không có quyền truy cập thông tin hoặc tài liệu nội bộ này."*
3. **Chứng minh Phân quyền (Role Switch):**
   * Trên thanh Demo, chuyển sang vai trò **"Nhân viên (Staff)"**.
   * Gửi lại câu hỏi trên: Trợ lý nhân viên tra cứu thành công và trả lời: *"Chính sách nội bộ: Nhân viên chính thức được giảm 20% khi dùng mã STAFF20..."* kèm trích dẫn `INT-DISCOUNT-01`.

---

### Bước 6: Trình diễn Báo cáo Metrics & Kịch bản Re-index v1.0 → v1.1 (2 phút)
1. **Show kết quả Evaluation 20 Cases:**
   * Mở terminal chạy lệnh:
     ```powershell
     python -m eval.run_rag_evaluation --split all
     ```
   * Trình bày các chỉ số ấn tượng: **Hit@3: 100%**, **Recall@5: 93.89%**, **MRR: 0.9000**, **Citation Resolve: 100%**, **Safe Abstention: 100%**, **Access Denied: 100%**.
2. **Kịch bản Re-index v1.0 lên v1.1:**
   * Khi đang ở index v1.0, hỏi: *"Thời hạn đổi trả hàng là bao nhiêu ngày?"* $\rightarrow$ Trả lời: **07 ngày**.
   * Chuyển Role sang **"Quản trị viên (Admin)"**, bấm nút **"Re-index v1.1"** trên thanh điều khiển. Xác nhận version mới qua `/api/v1/rag/status`; không cam kết thời gian kích hoạt cố định.
   * Gửi lại câu hỏi trên: Trợ lý lập tức cập nhật câu trả lời: **14 ngày** (kèm phiên bản trích dẫn hiển thị `v1.1`).
   * Bấm nút **"Rollback v1.0"**: Trợ lý quay trở lại chính sách 07 ngày an toàn.
