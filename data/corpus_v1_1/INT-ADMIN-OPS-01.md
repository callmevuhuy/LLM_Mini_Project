# Quy trình Quản trị Vận hành Kho và Tái lập Chỉ mục RAG [ADMIN ONLY]

## Quy trình Kiểm kê và Cân đối Tồn kho Định kỳ
- Quản trị viên hệ thống (Admin) thực hiện đối soát dữ liệu tồn kho thực tế tại kho hàng với bảng `inventories` trong SQLite vào lúc 23:00 hằng ngày.
- Mọi điều chỉnh tăng/giảm tồn kho thủ công bắt buộc phải ghi log vào bảng `audit_logs` với `action = 'inventory_adjustment'` kèm lý do cụ thể.

## Quy trình Phê duyệt và Tái lập Chỉ mục (Re-index) RAG
- Khi có sự thay đổi về chính sách (ví dụ cập nhật thời hạn đổi trả từ v1.0 lên v1.1), tài liệu sửa đổi phải được Admin ký duyệt trước khi đưa vào thư mục corpus active.
- Lệnh kích hoạt Re-index tạo ra một Index Bundle ứng viên mới (Candidate Bundle), thực hiện kiểm tra tính toàn vẹn (Integrity Check) giữa số lượng chunk và vector embedding trước khi ghi đè chỉ mục đang chạy.
- Toàn bộ cache truy vấn cũ bị hủy bỏ (Cache Invalidation) ngay khi bundle mới được kích hoạt. Lưu trữ snapshot index phiên bản trước để đảm bảo khả năng Rollback khi có sự cố.
