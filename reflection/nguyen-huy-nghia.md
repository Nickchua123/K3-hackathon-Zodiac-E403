# Reflection — Nguyễn Huy Nghĩa

Mã học viên: 2A202601943  
Vai trò: Backend + Data

> Đây là bản nháp dựa trên phần việc đã ghi trong repo. Tôi cần đọc lại và xác nhận
> nội dung đúng với phần mình thực sự thực hiện trước khi nộp.

## Phần tôi thực hiện

Trong dự án, tôi phụ trách phần backend và dữ liệu. Tôi tham gia thiết kế cách lưu
bài viết, các chỉ số engagement và công thức tính quality score. Khi hệ thống được
nâng cấp, dữ liệu runtime được chuyển từ CSV sang SQLite với ba nhóm thông tin chính:
bài viết, embedding và lịch sử đồng bộ Discord.

Tôi lựa chọn cơ chế upsert theo `post_id` để background worker có thể chạy lại mà
không tạo bài trùng. SQLite được cấu hình WAL và transaction để việc đọc dữ liệu của
API không bị phụ thuộc vào thời điểm worker đang ghi dữ liệu. Tôi cũng tham gia ghép
embedding, lexical match và quality score thành hybrid search, đồng thời giữ các
intent xếp hạng cao nhất/thấp nhất thành luồng riêng.

Tôi kiểm tra phần mình phụ trách bằng lệnh quản trị dữ liệu, API status và bộ eval.
Kết quả hiện tại có 23 bài, 23 embedding và bộ kiểm thử đạt 26/26 case.

## AI đã hỗ trợ tôi như thế nào

AI hỗ trợ tôi rà soát schema, đề xuất các trường cần lưu, viết migration/upsert và
gợi ý những trường hợp dễ gây lỗi khi worker chạy lặp. AI cũng hỗ trợ tạo script
kiểm tra, phân tích kết quả eval và cập nhật tài liệu vận hành.

Tôi không dùng kết quả của AI như bằng chứng rằng code chắc chắn đúng. Tôi kiểm tra
lại bằng cách xem dữ liệu trong SQLite, chạy reindex, gọi API và chạy toàn bộ golden
set sau mỗi thay đổi lớn.

Một phương án được cân nhắc nhưng chưa dùng là triển khai ngay vector database và
embedding từ dịch vụ bên ngoài. Với quy mô prototype, phương án này làm tăng phụ
thuộc, chi phí và rủi ro gửi dữ liệu Discord ra ngoài. Nhóm chọn SQLite và embedding
local trước, nhưng vẫn lưu model/version để có thể thay thế sau.

## Một case fail của nhóm

Case fail tôi nhớ rõ là hai câu hỏi “bài viết đánh giá thấp nhất” và “bài viết đánh
giá cao nhất” từng trả về kết quả gần giống nhau. Hệ thống lúc đó coi câu hỏi ranking
như truy vấn tìm kiếm thông thường, nên các từ “bài viết” và “đánh giá” ảnh hưởng đến
độ liên quan nhiều hơn yêu cầu cao nhất/thấp nhất.

Nhóm sửa bằng cách nhận diện intent ranking trước khi gọi hybrid search. Với intent
này, hệ thống sắp xếp trực tiếp theo `quality_score` tăng hoặc giảm và không dùng
semantic match để thay đổi thứ tự. Sau khi sửa, nhóm thêm hai case riêng vào golden
set và chạy lại toàn bộ 26 case.

Bài học của tôi là không nên ép mọi truy vấn đi qua cùng một thuật toán. Những yêu
cầu có semantics rõ như max/min, filter theo tag hoặc ngoài phạm vi cần được định
tuyến trước khi thực hiện retrieval chung.

## Điều tôi sẽ làm khác ở lần sau

Lần sau tôi sẽ thiết kế schema và contract API cùng với bộ test intent ngay từ đầu,
thay vì đợi lỗi xuất hiện trên giao diện mới bổ sung. Tôi cũng sẽ tách background
workflow thành queue có retry, dead-letter và metric quan sát lỗi. Cuối cùng, tôi
sẽ thu thập tín hiệu engagement thật sớm hơn để quality score không phụ thuộc nhiều
vào proxy của dữ liệu demo.

