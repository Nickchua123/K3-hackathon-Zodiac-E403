# Nguồn của các case trong Golden Set

Mục tiêu rubric: ít nhất 10 case được lấy hoặc phát triển từ chatlog thật.

Hiện tại `eval/README.md` xác nhận bộ eval chạy trên dữ liệu mock cố định. Repo chưa
có bằng chứng cho phép gắn nhãn case nào là phát triển từ chatlog thật, vì vậy bảng
dưới đây ghi trung thực trạng thái hiện tại.

| Nhóm case | Số lượng | Trạng thái nguồn hiện tại |
|---|---:|---|
| N01–N10 | 10 | Nhóm tự xây từ dữ liệu mock |
| T01 | 1 | Nhóm tự xây từ lỗi tìm tag |
| Q01–Q03 | 3 | Nhóm tự xây từ lỗi ranking theo điểm và tín hiệu tương tác |
| S01–S02 | 2 | Nhóm tự xây để kiểm tra không bịa nguồn |
| A01–A02 | 2 | Nhóm tự xây cho truy vấn mơ hồ |
| O01–O03 | 3 | Nhóm tự xây cho ngoài phạm vi |
| D01–D02 | 2 | Nhóm tự xây cho rủi ro domain |
| R02–R04 | 3 | Nhóm tự xây cho typo/query hiếm |
| **Tổng** | **26** | **Chưa có case nào được chứng minh từ chatlog thật** |

## Cách hoàn thiện

Với mỗi case phát triển từ chatlog thật, bổ sung:

| Case ID | Mã chatlog đã ẩn danh | Query gốc hoặc mô tả | Cách biến thành test | Người kiểm tra |
|---|---|---|---|---|
| `[ID]` | `[Nguồn]` | `[Nội dung đã được phép]` | `[Biến đổi gì]` | `[Tên]` |

Không đưa tên, Discord user ID, URL riêng tư hoặc nội dung chưa được phép vào repo.
