# Demo Script — Discord Quality Digest

Thời lượng mục tiêu: 5 phút. Mỗi thành viên trình bày ít nhất một phần.

## Chuẩn bị trước khi demo

- Chạy ứng dụng: `cd codebase` rồi `uvicorn main:app --reload`.
- Mở `http://127.0.0.1:8000`.
- Kiểm tra `/api/status` hiển thị `storage: sqlite`, đủ bài và embedding.
- Giữ sẵn hai truy vấn:
  - Happy path: `tìm bài về RAG và prompt`
  - Case khó: `Mai thời tiết như nào`
- Phương án dự phòng: dùng ảnh trong `demo-backup/`.

## 0:00–0:45 — User & Job

Người trình bày: Phạm Thế Dũng.

> Học viên thường nhớ lờ mờ một chủ đề đã đọc trên Discord nhưng không nhớ bài nằm
> ở đâu. Họ phải dò keyword, mở nhiều bài và tự đánh giá bài nào đáng đọc. Nhóm xây
> một trợ lý giúp tìm lại bài liên quan, xếp hạng theo chất lượng và luôn trả link gốc.

Ghi chú: thay phần pain bằng số liệu mining/khảo sát thật trước khi demo.

## 0:45–1:25 — Vì sao chọn lát cắt này

Người trình bày: Phạm Thế Dũng.

- So với trả lời deadline/logistics, tìm bài kỹ thuật có cost-of-error thấp hơn.
- So với bản tin cho TA, flow tìm bài dễ kiểm chứng bằng link Discord gốc.
- Lát cắt một câu:

> Một học viên hỏi về một chủ đề kỹ thuật; hệ thống chọn các bài Discord liên quan
> và có điểm chất lượng tốt; học viên mở đúng bài gốc để đọc tiếp.

## 1:25–3:15 — Giải pháp và demo live

Người trình bày: Phạm Văn Lưu.

### Case chuẩn

1. Nhập `tìm bài về RAG và prompt`.
2. Chỉ vào kết quả:
   - Tiêu đề và tag.
   - Quality score.
   - Tóm tắt.
   - Nút mở bài Discord gốc.
3. Giải thích ngắn:

> Hệ thống dùng hybrid search gồm semantic embedding, lexical match và quality
> score. Vì vậy kết quả không chỉ phụ thuộc một từ khóa trùng khớp.

### Case khó

1. Nhập `Mai thời tiết như nào`.
2. Chỉ ra hệ thống từ chối tìm bài kỹ thuật không liên quan.
3. Giải thích:

> Khi không đủ bằng chứng, hệ thống không ép trả một bài có từ trùng ngẫu nhiên.
> Đây là guardrail cho câu hỏi ngoài phạm vi.

### Kiến trúc một câu

> Background worker lấy bài Discord mới, làm sạch và upsert vào SQLite; embedding
> được tạo local; API tìm kiếm đọc SQLite và trả kết quả đã xếp hạng.

## 3:15–4:05 — Kết quả đo

Người trình bày: Nguyễn Huy Nghĩa.

- Golden set: 26 case.
- Kết quả hiện tại: 26/26 case pass.
- Relevance: 100%.
- Groundedness: 100%.
- Transparency: 100%.
- Response behavior: 100%.
- Quality bar đã đạt.

Ghi rõ giới hạn:

> Eval hiện dùng bộ dữ liệu mock cố định để lặp lại được. Nhóm cần bổ sung mapping
> nguồn cho ít nhất 10 case phát triển từ chatlog thật.

## 4:05–4:40 — User thật nói gì

Người trình bày: Phạm Văn Lưu.

Phần này chỉ điền sau validation:

- Quote 1: `[Tên/vai trò] — [quote nguyên văn]`
- Quote 2: `[Tên/vai trò] — [quote nguyên văn]`
- Thay đổi đã làm: `[thay đổi xuất phát từ feedback]`

## 4:40–5:00 — Nếu có thêm một tuần

Người trình bày: Nguyễn Huy Nghĩa.

1. Thay local hash embedding bằng multilingual neural embedding.
2. Bổ sung dữ liệu engagement thật và hiệu chỉnh quality score.
3. Thêm hàng đợi workflow, retry và quan sát lỗi cho Discord worker.

Kết:

> Nhóm không cố trả lời thay bài viết. Sản phẩm giúp học viên tìm đúng nguồn,
> hiểu vì sao bài được ưu tiên và tự kiểm chứng trên Discord.

## Câu hỏi dự phòng

- `Bài viết đánh giá cao nhất`
- `Bài viết có đánh giá thấp nhất`
- `tìm bài đăng theo tag UX`
- `Kubernetes autoscaling HPA`

