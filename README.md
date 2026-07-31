# Trợ lý Tổng hợp bài đăng chất lượng

Prototype hackathon giúp học viên tìm lại các bài chia sẻ đáng đọc trong Discord
bằng chatbot tìm kiếm kết hợp và bảng xếp hạng chất lượng.

## Thành viên

| Thành viên | Mã HV | Vai trò chính |
|---|---|---|
| Nguyễn Huy Nghĩa | 2A202601943 | Backend + Data |
| Phạm Thế Dũng | 2A202601985 | AI Engineer / Leader |
| Phạm Văn Lưu | 2A202601857 | Frontend |

## Chức năng hiện có

- Giao diện split-screen FastAPI + HTML/CSS/JS, không còn phụ thuộc Streamlit.
- Chatbot nhận câu hỏi chủ đề và trả các bài phù hợp kèm summary, tag, điểm và link gốc.
- SQLite là nguồn dữ liệu runtime cho bài viết, embedding và lịch sử đồng bộ.
- Tự migrate dữ liệu mock/Discord CSV vào SQLite theo cơ chế upsert.
- Hybrid search kết hợp semantic embedding, lexical match và quality score.
- Guardrail từ chối câu hỏi ngoài phạm vi thay vì trả bài khớp từ khóa yếu.
- Intent riêng cho “bài đánh giá cao nhất/thấp nhất”.
- Background workflow tự lấy và xử lý bài Discord mới theo interval.
- Top Quality Posts và Hot Topics đều được tính từ cùng dữ liệu đã lọc trong SQLite.

## Luồng hệ thống

```text
Discord
   ↓
Background worker phát hiện bài mới
   ↓
Làm sạch → Tóm tắt → Gắn chủ đề/tag → Chấm điểm
   ↓
SQLite + local embeddings
   ↓
Người dùng đặt câu hỏi
   ↓
Hybrid search → xếp hạng → trả link Discord gốc
```

## Cách chạy

```powershell
cd codebase
pip install -r requirements.txt
uvicorn main:app --reload
```

Mở `http://127.0.0.1:8000`. Xem cấu hình chi tiết, cách sync và reindex trong
[`codebase/README.md`](codebase/README.md).

## Công thức điểm chất lượng

```text
Click 20% + Like 15% + Tim 20% + Thời lượng xem 25%
+ Tỷ lệ xem hết 10% + Lưu/Chia sẻ 10%
```

Mỗi chỉ số được chuẩn hóa về 0–100 trước khi tính điểm tổng. Điểm chất lượng là tín
hiệu ưu tiên bài đáng đọc, không phải xác nhận kiến thức trong bài đúng tuyệt đối.

## Kiểm thử

```powershell
codebase\.venv\Scripts\python.exe eval\run_eval.py --strict
```

Bộ golden set hiện có 26 case, bao gồm happy path, truy vấn tag, typo, ranking,
ngoài phạm vi và truy vấn không có dữ liệu.

## Hồ sơ demo và nộp bài

- `demo-slides.pptx` và `demo-slides.pdf`: bộ slide nháp 6 trang.
- `demo-script.md`: kịch bản demo 5 phút cho ba thành viên.
- `demo-backup/`: ảnh tổng quan, happy path và case ngoài phạm vi.
- `validation/feedback-log.md`: đã có danh sách 5 người dự kiến, chờ log và quote thật.
- `evidence/mining-log.md`: template evidence chuẩn B, chờ mining dữ liệu được phép.
- `reflection/`: ba bản nháp reflection cá nhân, chờ từng thành viên xác nhận.
- `canvas.md`: Canvas CP1 tổng hợp từ spec hiện tại.
- `traces/`: đã có trace một lần gọi Gemini thật bằng bài mock P001.

## Bảo mật dữ liệu

- Không commit `.env`, API key, token Discord, `.venv` hoặc database runtime.
- Hybrid embedding mặc định chạy local và không gửi nội dung ra ngoài.
- Chỉ bật `RAG_INCLUDE_DISCORD_DATA=true` khi đã được phép dùng provider ngoài.
- Các tín hiệu click/watch-time/completion/save-share của dữ liệu Discord hiện vẫn
  là proxy phục vụ prototype vì Discord API không cung cấp trực tiếp.
