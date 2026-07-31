# AI Trace

Thư mục này lưu bằng chứng một lời gọi AI thật ở quyết định trung tâm.

Chỉ sử dụng dữ liệu mock hoặc dữ liệu đã được phép gửi tới provider ngoài. Không
commit API key, Discord token, author, user ID hoặc URL riêng tư.

File `ai-call.template.json` là schema mẫu, chưa phải bằng chứng AI call thật.
Sau khi chạy, tạo một bản `ai-call-YYYYMMDD.json` đã loại bỏ thông tin nhạy cảm.

Trace thật hiện có: `ai-call-20260731.json`, tạo từ bài mock P001 bằng Gemini.
File xác nhận `is_real_ai=true` và không lưu content, API key, author hoặc URL.

Chạy trace bằng một bài mock:

```powershell
cd codebase
python run_ai_trace.py
```

Script chỉ chấp nhận kết quả có `is_real_ai=true`. Nếu provider fallback, script
dừng và không tạo evidence sai.
