# Reflection — Phạm Văn Lưu

Mã học viên: 2A202601857  
Vai trò: Frontend

> Đây là bản nháp dựa trên phần việc đã ghi trong repo. Tôi cần đọc lại và xác nhận
> nội dung đúng với phần mình thực sự thực hiện trước khi nộp.

## Phần tôi thực hiện

Tôi phụ trách thiết kế và triển khai giao diện web. Giao diện ban đầu được cân nhắc
theo hướng Streamlit có nhiều tab, nhưng nhóm chuyển sang FastAPI kết hợp
HTML/CSS/JavaScript để có trải nghiệm giống sản phẩm web thật và tập trung hơn vào
luồng demo chính.

Tôi xây bố cục split-screen: khu vực chat ở bên trái và Content Overview ở bên phải.
Trong hội thoại, mỗi kết quả hiển thị tiêu đề, summary, tag, quality score, link bài
gốc và phần chi tiết cách tính điểm. Bên phải hiển thị Top Quality Posts và Hot
Topics. Trạng thái SQLite và số embedding cũng được đưa lên header để người demo
biết hệ thống đang đọc dữ liệu runtime nào.

Tôi kiểm tra giao diện bằng các truy vấn RAG, tag UX, ranking cao nhất/thấp nhất và
câu hỏi ngoài phạm vi. Tôi cũng kiểm tra lại JavaScript, trạng thái loading, cách
cuộn hội thoại và ảnh chụp dự phòng cho demo.

## AI đã hỗ trợ tôi như thế nào

AI hỗ trợ tạo wireframe, đề xuất hierarchy, viết một phần HTML/CSS/JavaScript và tìm
các nguyên nhân khiến giao diện hiển thị sai số lượng. Sau mỗi đề xuất, tôi cần kiểm
tra lại trên trình duyệt vì code đúng cú pháp chưa chắc đã tạo ra trải nghiệm đúng.

Tôi giữ lại hướng giao diện sáng, ít nhiễu và dùng card cho kết quả bài viết. Tôi
không giữ các màn Knowledge Base và Admin trong UI chính vì chúng làm loãng câu
chuyện demo 5 phút. Quyết định này giúp người dùng tập trung vào hành động hỏi, xem
kết quả và mở bài gốc.

## Một case fail của nhóm

Một lỗi dễ thấy là Hot Topics hiển thị một tag có số lượng 2, nhưng khi bấm vào chỉ
còn một bài; tag UX cũng từng không trả kết quả. Nguyên nhân là dữ liệu có nhiều cách
viết khác nhau như chữ hoa/chữ thường, trong khi phần đếm và phần lọc không dùng
cùng quy tắc chuẩn hóa.

Nhóm sửa bằng cách chuẩn hóa tag theo dạng không phân biệt hoa thường, gộp các biến
thể khi đếm và dùng cùng khóa chuẩn hóa khi người dùng bấm tìm. Sau đó Top Topics,
số lượng trên badge và kết quả chat đều được lấy từ cùng nguồn dữ liệu đã xử lý.

Bài học của tôi là mọi con số có thể bấm được phải dùng cùng định nghĩa với kết quả
sau khi bấm. Nếu giao diện hiển thị “2” nhưng trả về “1”, người dùng sẽ mất niềm tin
dù thuật toán phía sau có phức tạp đến đâu.

## Điều tôi sẽ làm khác ở lần sau

Tôi sẽ định nghĩa sớm các UI state cho loading, empty, error, out-of-scope và
low-confidence, thay vì chỉ thiết kế happy path. Tôi cũng sẽ tạo test cho quan hệ
giữa badge count và danh sách kết quả. Trước demo, tôi sẽ cho người ngoài nhóm thao
tác mà không hướng dẫn để phát hiện các nhãn hoặc nút mà nhóm đã quá quen nên không
nhận ra là khó hiểu.

