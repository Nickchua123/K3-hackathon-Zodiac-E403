# Eval - Discord Quality Digest

Bộ eval dùng `codebase/mock_posts.csv` làm nguồn cố định, không đọc dữ liệu Discord
runtime và luôn tắt external RAG. Vì vậy kết quả có thể lặp lại mà không cần API key
hay kết nối mạng.

## Thành phần

- `golden_set.csv`: 26 case phủ luồng thường, tìm theo tag, xếp hạng điểm, bốn lớp tình huống
  khó và các truy vấn hiếm.
- `run_eval.py`: chạy đúng logic search, ranking và định dạng kết quả trong
  `codebase/main.py`.
- `results.csv`: bảng kết quả chi tiết được tạo sau mỗi lần chạy.
- `summary.json`: tổng hợp tỷ lệ pass và quality bar.

## Chạy trên Windows

Từ thư mục gốc của dự án:

```powershell
codebase\.venv\Scripts\python.exe eval\run_eval.py
```

Chạy ở chế độ CI, trả exit code `1` nếu có case chưa đạt:

```powershell
codebase\.venv\Scripts\python.exe eval\run_eval.py --strict
```

Nếu chưa có môi trường:

```powershell
python -m venv codebase\.venv
codebase\.venv\Scripts\python.exe -m pip install -r codebase\requirements.txt
codebase\.venv\Scripts\python.exe eval\run_eval.py
```

## Cách chấm

- `retrieve`: số bài đúng trong top 3 phải đạt `min_relevant_in_top_k`.
- `reject_no_evidence`: không trả bài khi nguồn không có nội dung phù hợp.
- `refuse`: không trả bài và hướng người dùng tới nguồn chính thức cho câu hỏi
  logistics ngoài phạm vi.
- `retrieve_with_caveat`: trả đúng bài nhưng phải nói rõ điểm chất lượng không
  bảo chứng tính đúng sai chuyên môn.
- Groundedness: mọi `post_id` và URL phải trùng với nguồn mock.
- Transparency: mọi kết quả phải có quality score và đủ sáu dòng chi tiết điểm.

Quality bar hiện dùng đúng spec: relevance tối thiểu 80%, groundedness 100%,
transparency 100% và không có post ID bị bịa.
