# Discord Quality Digest

Ứng dụng FastAPI + HTML/CSS/JS giúp tìm và xếp hạng bài đăng chất lượng trong Discord.
Người dùng hỏi bằng ngôn ngữ tự nhiên, hệ thống trả các bài liên quan kèm tóm tắt,
chủ đề, điểm chất lượng và link bài gốc.

## Kiến trúc hiện tại

```text
Discord background worker
        ↓
Làm sạch → Tóm tắt/Gắn tag → Chấm điểm
        ↓
SQLite (posts + embeddings + sync history)
        ↓
Hybrid search (semantic + lexical + quality)
        ↓
FastAPI API → Web UI
```

- SQLite là nguồn dữ liệu runtime chính tại `data/quality_hub.db`.
- `mock_posts.csv` và `discord_posts.csv` là nguồn nhập/migration tương thích.
- Khi app khởi động lần đầu, dữ liệu CSV được upsert vào SQLite theo `post_id`.
- Embedding mặc định là vector local `local-hash-ngram-v1`, không gọi API ngoài.
- Background worker đồng bộ Discord ngay khi app khởi động và lặp lại theo interval.
- API tìm kiếm chỉ đọc SQLite; việc mở trang hoặc gửi câu hỏi không kích hoạt sync.

## Chạy local

```powershell
cd codebase
pip install -r requirements.txt
uvicorn main:app --reload
```

Mở `http://127.0.0.1:8000`. Có thể kiểm tra runtime tại
`http://127.0.0.1:8000/api/status`.

Nếu chưa cấu hình Discord, app vẫn chạy bằng 12 bài mock đã được migrate vào SQLite.

## Cấu hình

Copy `.env.example` thành `.env`, sau đó điền các biến cần dùng:

```text
QUALITY_HUB_DB_PATH=data/quality_hub.db

DISCORD_BOT_TOKEN=your_discord_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_here
DISCORD_SYNC_LIMIT=50
DISCORD_SYNC_INTERVAL_SECONDS=120
DISCORD_SYNC_WITH_AI=false
```

Nếu cần lấy nhiều kênh:

```text
DISCORD_CHANNEL_IDS=channel_id_1,channel_id_2,channel_id_3
```

Trong Discord Developer Portal, bật `Message Content Intent` khi cần đọc nội dung.
Bot cần quyền `View Channel` và `Read Message History`.

`DISCORD_SYNC_WITH_AI=false` giữ toàn bộ bước tóm tắt/gắn tag ở local bằng heuristic.
Khi bật `true`, cấu hình thêm provider:

```text
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
AI_PROVIDER=gemini
```

## Hybrid search

Điểm xếp hạng tìm kiếm gồm:

```text
50% semantic embedding + 20% lexical match + 30% quality score
```

- Semantic score dùng cosine similarity giữa vector câu hỏi và vector bài viết.
- Lexical score ưu tiên match ở title, topic, tags và cụm từ chính xác.
- Quality score dùng các tín hiệu engagement đã chuẩn hóa.
- Guardrail yêu cầu đủ bằng chứng lexical hoặc semantic, nên câu hỏi ngoài phạm vi
  không bị ép trả bài không liên quan.
- Truy vấn “cao nhất/thấp nhất” dùng intent xếp hạng riêng thay vì semantic search.

Embedding local hiện tại là feature-hashing trên từ, cụm từ và character n-gram.
Nó ổn định, không cần model/API tải ngoài và phù hợp prototype. Bảng embedding lưu cả
`model` và `dimensions`, nên có thể thay bằng model neural sau mà không đổi schema.

## Công cụ dữ liệu

Chạy từ thư mục `codebase/`:

```powershell
python manage_data.py migrate
python manage_data.py stats
python manage_data.py reindex
python manage_data.py sync
```

- `migrate`: upsert dữ liệu CSV vào SQLite và tạo embedding còn thiếu.
- `stats`: xem số bài, số vector, nguồn dữ liệu và lần sync gần nhất.
- `reindex`: tạo lại toàn bộ embedding.
- `sync`: chạy một lần đồng bộ Discord ngay lập tức.

Các thao tác ghi SQLite dùng transaction, WAL và upsert idempotent. Vì vậy một bài
Discord đã có sẽ được cập nhật, không nhân bản khi worker chạy lại.

## RAG ngoài hệ thống

FastAPI không gửi nội dung sang API ngoài theo mặc định. Nếu muốn bật phần tổng hợp
câu trả lời bằng provider:

```text
RAG_ENABLED=true
RAG_PROVIDER=gemini
RAG_INCLUDE_DISCORD_DATA=false
```

Chỉ đặt `RAG_INCLUDE_DISCORD_DATA=true` khi đã được phép gửi nội dung Discord sang
provider bên ngoài. Context gửi đi không bao gồm author và URL.

## Chấm điểm chất lượng

```text
Click 20% + Like 15% + Tim 20% + Thời lượng xem 25%
+ Tỷ lệ xem hết 10% + Lưu/Chia sẻ 10%
```

Mỗi chỉ số được chuẩn hóa về thang 0–100 trước khi tính điểm tổng.

## Chạy eval

Từ thư mục gốc của dự án:

```powershell
codebase\.venv\Scripts\python.exe eval\run_eval.py --strict
```

Golden set có 26 case, dùng dữ liệu cố định và không gọi API ngoài. Kết quả chi tiết
được ghi vào `eval/results.csv`; tóm tắt nằm trong `eval/summary.json`.
