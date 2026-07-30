# Trợ lý Tổng hợp bài đăng chất lượng

Prototype Streamlit cho bài toán biến nhiều bài đăng Discord thành danh sách ưu tiên,
bản tổng hợp dễ đọc và câu trả lời có căn cứ cho cộng đồng AI20K.

## Sản phẩm hiện có

- Hiển thị và xếp hạng bài đăng theo quality score.
- Tìm kiếm tự nhiên bằng keyword overlap kết hợp quality score.
- Lọc theo chủ đề, điểm tối thiểu và cách sắp xếp.
- Xem nội dung, tóm tắt, tags, link nguồn và bảng phân rã điểm.
- Chatbot dạng bong bóng `💬`: bấm icon để hỏi trợ lý, xem lịch sử và xóa hội thoại.
- Agent đọc context các bài đăng phù hợp, ưu tiên deadline, thông báo, bug report,
  workshop, tài nguyên và evidence.
- Bộ CP3 golden set gồm 21 câu, có cả câu trong phạm vi và câu ngoài phạm vi,
  kèm bảng kết quả kiểm thử.

## Dataset

- `mock_posts.csv`: 16 bài đăng đã ẩn danh, tổng hợp từ các mẫu thông báo,
  hướng dẫn, hỗ trợ, bug report, tài liệu và hackathon của cộng đồng AI20K.
- `golden_set.csv`: 21 câu kiểm thử để đánh giá khả năng trả lời của agent.
- Dữ liệu hiện là sample/mock đã cấu trúc; chưa kết nối trực tiếp Discord API.
- Agent sử dụng retrieval/context trong prompt, chưa fine-tune model.

## Công thức quality score

- Click: 20%
- Like: 15%
- Tim: 20%
- Thời lượng xem: 25%
- Tỷ lệ xem hết: 10%
- Lưu/Chia sẻ: 10%

Mỗi chỉ số được chuẩn hóa về thang 0–100 trước khi tính điểm tổng.

## Chạy local

```powershell
cd codebase
python -m pip install -r requirements.txt
```

### Dùng Groq cho demo

Groq được cấu hình mặc định vì endpoint tương thích OpenAI. Tạo key tại
<https://console.groq.com/keys>, sau đó chạy:

```powershell
$env:LLM_PROVIDER = "groq"
$env:GROQ_API_KEY = "KEY_GROQ_CUA_BAN"
$env:GROQ_MODEL = "llama-3.3-70b-versatile"
python -m streamlit run app.py
```

Mở <http://localhost:8501>.

Không ghi API key vào source code, `.env`, CSV hoặc commit GitHub.

## Demo CP3

1. Mở ứng dụng và bấm icon `💬` để mở trợ lý.
2. Hỏi thử:

```text
Các deadline quan trọng hiện nay là gì?
Hãy tổng hợp các thông báo quan trọng nhất.
Bài nào nói về PCB defect detection?
Tôi không vào được GitHub Classroom thì cần làm gì?
Thời tiết hôm nay thế nào?
```

3. Mở phần `CP3 - Golden set` ở sidebar.
4. Bấm `Chạy toàn bộ golden set` để tạo bảng câu hỏi, phản hồi AI,
   từ khóa khớp và trạng thái đạt sơ bộ.

## Kênh Discord nguồn tham khảo

- Tài nguyên: <https://discord.com/channels/1526532830627102781/1527920166397018164>
- Chung: <https://discord.com/channels/1526532830627102781/1527920177390293164>
- Thông báo: <https://discord.com/channels/1526532830627102781/1527920171963125953>
- Lý thuyết: <https://discord.com/channels/1526532830627102781/1529103552297963630>
- Thông báo khóa 3: <https://discord.com/channels/1526532830627102781/1529105265369157732>

## Phạm vi và hướng phát triển

- Chưa lấy dữ liệu Discord tự động; cần bot có quyền đọc channel và lịch sử tin nhắn.
- Search hiện chưa dùng embedding/vector database.
- Quality score hiện dùng dữ liệu tương tác mẫu.
- Bước tiếp theo: kết nối Discord API, ẩn danh dữ liệu, bổ sung embedding và cập nhật golden set
  bằng các câu hỏi thực tế của người dùng.
