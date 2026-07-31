# CP1 Canvas — Discord Quality Digest

Trạng thái: bản tổng hợp từ `spec.md`; evidence và willing users vẫn cần xác nhận
bằng log thật.

1. **Hướng:** B — Trợ lý Học viên Discord; tính năng mới.
2. **Job executor:** Học viên đang ôn tập hoặc xử lý một vấn đề kỹ thuật và muốn
   tìm lại bài chia sẻ hữu ích đã xuất hiện trong Discord.
3. **Pain:** Bài viết phân tán, tiêu đề và tag không đồng nhất; học viên phải nhớ từ
   khóa, mở nhiều bài và tự đánh giá bài nào đáng đọc.
4. **Evidence ban đầu:** Prototype hiện có 12 bài mock và 11 bài Discord lưu local.
   Đây mới là evidence về khả năng xây sản phẩm, chưa phải evidence chuẩn A/B cho
   mức độ pain. Kế hoạch hoàn thiện nằm trong `evidence/mining-log.md`.
5. **Lát cắt một câu:** Một học viên hỏi về một chủ đề kỹ thuật; hệ thống chọn các
   bài Discord liên quan và có điểm chất lượng tốt; học viên mở đúng bài gốc để đọc.
6. **Automation:** Conditional — hệ thống tự xử lý và xếp hạng khi có đủ evidence;
   truy vấn ngoài phạm vi hoặc thiếu căn cứ được từ chối. Lý do: sai recommendation
   có thể sửa bằng link gốc, nhưng bịa kết quả sẽ làm mất niềm tin.
7. **Willing users dự kiến và phân công:**
   - Người dùng dự kiến: Nguyễn Thế Anh, Hà Duy Anh, Nguyễ Đức Sơn,
     Nguyễn Sỹ Đức và Vũ Văn Phong; cần xác nhận chính tả, vai trò và đồng ý thử.
   - Phạm Thế Dũng: product framing, AI logic, prompt và eval.
   - Nguyễn Huy Nghĩa: backend, data, scoring, SQLite và workflow.
   - Phạm Văn Lưu: frontend, demo flow và UI validation.

## Việc cần xác nhận trước khi dùng Canvas làm evidence

- Ít nhất 3 người trong danh sách xác nhận đồng ý dùng thử.
- Hoàn thành mining chuẩn B hoặc khảo sát chuẩn A.
- Không dùng số bài hiện có để thay thế số liệu chứng minh pain người dùng.
