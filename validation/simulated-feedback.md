# Feedback giả lập cho dry run

> **DỮ LIỆU GIẢ LẬP — KHÔNG PHẢI FEEDBACK NGƯỜI DÙNG THẬT.**
>
> File này chỉ dùng để luyện demo, dự đoán vấn đề và chuẩn bị câu hỏi. Không được
> sao chép sang `feedback-log.md`, slide 5 hoặc trình bày như evidence validation.

## Năm tình huống giả lập

| Người thử giả lập | Task | Quan sát giả lập | Nhận xét giả lập | Mức nghiêm trọng |
|---|---|---|---|---|
| Persona A | Tìm bài về RAG và mở bài gốc | Tìm được bài nhanh nhưng dừng lại để phân biệt điểm chất lượng và độ liên quan | “Tôi hiểu bài nào được ưu tiên, nhưng chưa rõ 59 điểm là chất lượng hay mức khớp câu hỏi.” | Vừa |
| Persona B | Tìm bài theo tag UX | Bấm Hot Topic và kiểm tra số bài trả về | “Số trên tag phải giống số bài sau khi bấm, nếu khác tôi sẽ nghĩ dữ liệu không ổn định.” | Cao |
| Persona C | Tìm bài được đánh giá cao nhất | Kỳ vọng kết quả được sắp theo điểm, không theo keyword | “Với câu hỏi cao nhất, tôi chỉ cần bài đứng đầu và lý do điểm cao, không cần nhiều kết quả.” | Vừa |
| Persona D | Hỏi thời tiết ngày mai | Hiểu hệ thống từ chối nhưng muốn biết bước tiếp theo | “Từ chối như vậy hợp lý; nếu có nút mở kênh thông báo chính thức thì sẽ hữu ích hơn.” | Thấp |
| Persona E | Tự chọn một chủ đề kỹ thuật | Muốn lọc thêm theo thời gian và nguồn Discord | “Tôi muốn biết bài này mới hay cũ và đến từ channel nào trước khi mở Discord.” | Vừa |

## Tổng hợp giả lập

- Chủ đề có khả năng lặp lại: người dùng có thể nhầm `quality score` với
  `relevance score`.
- Rủi ro đáng ưu tiên: badge Hot Topics và kết quả sau khi bấm phải tuyệt đối nhất
  quán.
- Thay đổi có thể cân nhắc: giải thích ngắn ý nghĩa quality score và bổ sung ngày
  đăng rõ hơn trên card.
- Backlog: bộ lọc thời gian/channel và đường dẫn tới nguồn chính thức cho case ngoài
  phạm vi.

## Cách dùng trong dry run

1. Một thành viên đóng vai Persona A hoặc B.
2. Người demo không giải thích trước khi persona thao tác.
3. Ghi lại ứng viên thay đổi nhưng chưa sửa chỉ dựa trên file giả lập.
4. Chỉ quyết định thay đổi chính thức sau khi phản hồi thật cho thấy cùng vấn đề.

