# Báo cáo Vận hành Re-index và Kế hoạch Rollback (v1.0 → v1.1)

## 1. Bối cảnh Cập nhật Nghiệp vụ (Business Diff)

Nhằm nâng cao trải nghiệm mua sắm và bảo vệ quyền lợi người tiêu dùng, Ban Giám Đốc phê duyệt cập nhật Chính sách Đổi trả & Hoàn tiền từ phiên bản **1.0** lên phiên bản **1.1**.

### Bảng so sánh thay đổi chi tiết:
| Hạng mục chính sách | Phiên bản cũ (v1.0) | Phiên bản mới (v1.1) | Chunk bị ảnh hưởng |
| :--- | :--- | :--- | :--- |
| **Thời hạn đổi trả** | **07 ngày** kể từ ngày nhận | **14 ngày** kể từ ngày nhận (+7 ngày) | `POL-RETURN-01#c01` |
| **Chi phí đổi ý cá nhân**| Khách hàng trả cước 2 chiều (30-45k) | **Shop hỗ trợ 100% phí vận chuyển 2 chiều** | `POL-RETURN-01#c03` |
| **Đổi trả thực phẩm (cà phê)**| Không áp dụng đổi trả cà phê | Hỗ trợ đổi trả trong 7 ngày nếu túi zip chưa mở | `POL-RETURN-01#c02` |
| **Tốc độ hoàn tiền** | 3 - 5 ngày làm việc | **Siêu tốc trong 24 giờ làm việc** | `POL-RETURN-01#c03` |

---

## 2. Quản lý Phiên bản và Snapshots Chỉ mục (Index Snapshots)

Hệ thống quản lý việc cập nhật chỉ mục thông qua các gói Bundle nguyên tử (Atomic Index Bundle):

1. **Snapshot v1.0 (Current Baseline):**
   * File bundle: `artifacts/index_bundle.json`
   * Manifest: `data_config/corpus_manifest.json`
   * Tổng tài liệu: 12 docs, 31 chunks
   * Model: `deterministic-ngram-tfidf-v1`, DIM: 1024
2. **Candidate Bundle v1.1:**
   * File bundle: `artifacts/index_bundle_v1_1.json`
   * Manifest: `data_config/corpus_manifest_v1_1.json`
   * Toàn vẹn (Integrity check): Đạt 100% (31 chunks $\leftrightarrow$ 31 vectors).
3. **Quy trình Kích hoạt (Activation Procedure):**
   * Khi Admin kích hoạt re-index qua API `POST /api/v1/rag/reindex?version=1.1`, hệ thống nạp bundle ứng viên vào bộ nhớ tạm, chạy validation đối soát hash và số lượng chunk/vector.
   * Nếu hợp lệ, hệ thống hoán đổi con trỏ active index nguyên tử (Atomic Switch).
   * **Cache Invalidation:** Toàn bộ in-memory cache phản hồi truy vấn trước đó bị xóa bỏ lập tức để tránh trả lời lẫn lộn giữa hai chính sách.

---

## 3. Câu truy vấn Xác minh (Verification Queries)

Thực hiện truy vấn kiểm thử trước và sau khi kích hoạt:

* **Câu hỏi kiểm thử:** *"Thời hạn đổi trả hàng là bao nhiêu ngày và ai chịu phí ship?"*
* **Kết quả khi Active Index là v1.0:**
  * Status: `answered`
  * Answer: *"Theo Chính sách Đổi trả và Hoàn tiền (bản v1.0): Bạn được đổi trả trong vòng 07 ngày... khách thanh toán phí 2 chiều nếu đổi ý, shop chịu 100% phí nếu do lỗi sản xuất."*
  * Citation: `POL-RETURN-01#c03` (version: `1.0`)
* **Kết quả ngay sau khi kích hoạt v1.1:**
  * Status: `answered`
  * Answer: *"Theo Chính sách Đổi trả và Hoàn tiền (bản v1.1): Bạn được đổi trả trong vòng 14 ngày kể từ khi nhận hàng... Về chi phí: Cửa hàng hỗ trợ 100% phí vận chuyển 2 chiều."*
  * Citation: `POL-RETURN-01#c03` (version: `1.1`)
* **Bằng chứng an toàn:**
  * Câu trả lời v1.0 cũ hoàn toàn biến mất khỏi luồng trả lời của hệ thống.
  * Tài liệu phiên bản cũ không được nạp đồng thời vào context nhằm tránh việc LLM tự suy diễn hoặc bịa đặt giữa 7 ngày và 14 ngày.

---

## 4. Kế hoạch Hoàn nguyên (Rollback Procedure)

Trong trường hợp phát hiện sai sót dữ liệu hoặc có yêu cầu khẩn cấp từ ban điều hành:
1. Snapshot index `artifacts/index_bundle.json` (v1.0) luôn được lưu trữ dự phòng.
2. Quản trị viên chỉ cần thực hiện lệnh Rollback:
   ```powershell
   python -m src.indexer --version 1.0
   ```
3. Bộ nạp khôi phục index v1.0, xóa cache và kích hoạt lại tức thì. Thời gian gián đoạn dưới 100ms.
4. Kiểm tra đối soát xác nhận câu trả lời quay về mốc "07 ngày" an toàn.

---

## 5. Nhật ký Vận hành An toàn (Safe Audit & Logging)

* Các thao tác Re-index và Rollback được ghi nhận vào bảng `audit_logs` với action `rag_reindex_v1_1` và `rag_rollback_v1_0`.
* Log chỉ lưu trữ metadata an toàn: `timestamp`, `admin_id`, `bundle_hash`, `chunk_count`, `latency_ms`.
* **Tuyệt đối không lưu:** Secret API key, mật khẩu, PII người dùng hoặc nội dung tài liệu mật vào log hệ thống.
