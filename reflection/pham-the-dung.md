# Reflection — Phạm Thế Dũng

Mã học viên: 2A202601985  
Vai trò: AI Engineer / Leader

> Đây là bản nháp dựa trên phần việc đã ghi trong repo. Tôi cần đọc lại và xác nhận
> nội dung đúng với phần mình thực sự thực hiện trước khi nộp.

## Phần tôi thực hiện

Tôi phụ trách định hình bài toán, phạm vi sản phẩm và logic AI. Nhóm chọn lát cắt tìm
lại bài Discord chất lượng thay vì trả lời logistics, vì kết quả tìm kiếm luôn có
link gốc để người học kiểm chứng và cost-of-error thấp hơn việc trả sai deadline.

Ở phần AI, tôi tham gia thiết kế luồng tóm tắt, gắn topic/tag, tìm kiếm và guardrail.
Hệ thống mặc định dùng xử lý local để không gửi dữ liệu Discord ra ngoài. Khi có sự
cho phép, `ai_analyzer.py` có thể gọi Gemini/OpenAI để tạo summary và tag. Phần tìm
kiếm hiện kết hợp semantic embedding, lexical match và quality score, nhưng vẫn yêu
cầu đủ evidence trước khi trả kết quả.

Tôi cũng tham gia xây golden set gồm 26 case, bao phủ happy path, truy vấn tag,
ranking, typo, mơ hồ, ngoài phạm vi và rủi ro domain. Quality bar được định nghĩa
bằng con số thay vì chỉ đánh giá theo cảm giác.

## AI đã hỗ trợ tôi như thế nào

AI hỗ trợ tôi brainstorm failure modes, viết các biến thể câu hỏi, phân tích output
và đề xuất guardrail. AI cũng giúp nhóm so sánh các phương án retrieval, diễn đạt
spec và kiểm tra sự nhất quán giữa code, eval và tài liệu.

Phần tôi cần tự quyết định là phạm vi nào hệ thống được phép trả lời, khi nào phải
từ chối và tiêu chí nào đủ để gọi một kết quả là có căn cứ. Tôi không chấp nhận việc
AI tự điền feedback người dùng hoặc tạo quote giả, vì những nội dung đó không thể
dùng làm evidence.

Một đề xuất không được dùng ngay là bật external RAG mặc định cho toàn bộ nội dung
Discord. Nhóm giữ tính năng này ở chế độ opt-in vì dữ liệu có thể chưa được phép gửi
cho provider ngoài và việc demo không cần đánh đổi quyền riêng tư để có câu trả lời
dài hơn.

## Một case fail của nhóm

Case fail quan trọng nhất là câu hỏi “Mai thời tiết như nào” từng trả về hai bài RAG
và Prompt Engineering. Nguyên nhân là retrieval tìm thấy các từ ngắn trùng ngẫu
nhiên như “thời” hoặc “tiết”, sau đó vẫn buộc phải trả top kết quả dù truy vấn nằm
ngoài phạm vi của kho bài kỹ thuật.

Nhóm sửa bằng cách thêm nhận diện ngoài phạm vi, ngưỡng evidence và hành vi
`no-answer`. Khi gặp câu hỏi thời tiết hoặc logistics không có nguồn chính thức, hệ
thống nói rõ giới hạn và hướng người dùng tới kênh phù hợp. Case này được đưa vào
golden set để tránh tái diễn.

Bài học của tôi là một hệ thống retrieval không chỉ cần tìm tốt mà còn phải biết khi
nào không nên trả kết quả. “Không tìm thấy” là một output hợp lệ và nhiều khi đáng
tin hơn một câu trả lời có vẻ hữu ích nhưng không có căn cứ.

## Điều tôi sẽ làm khác ở lần sau

Tôi sẽ bắt đầu từ failure set và no-answer policy trước khi tinh chỉnh prompt hoặc
model. Tôi cũng sẽ thu thập ít nhất 10 query thật từ người học sớm hơn để golden set
phản ánh cách dùng ngôn ngữ thực tế. Nếu có thêm thời gian, tôi sẽ thử multilingual
embedding và đo riêng retrieval relevance, thay vì chỉ nhìn tỷ lệ pass tổng hợp.

