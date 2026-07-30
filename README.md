# Tro ly Tong hop bai dang chat luong

Prototype hackathon cho bai toan tong hop, xep hang va tim kiem cac bai dang huu ich trong Discord khoa hoc.

## Thong tin nhom

| Thanh vien | Ma HV | Vai tro chinh |
|---|---|---|
| Nguyen Huy Nghia | 2A202601943 | Backend + Data |
| Pham The Dung | 2A202601985 | AI Engineer / Leader |
| Pham Van Luu | 2A202601857 | Frontend |

## Phan cong theo tung phan

| Phan viec | Nguoi phu trach | Mo ta |
|---|---|---|
| Product idea & problem framing | Pham The Dung | Chot lat cat demo, mo ta user pain, xac dinh pham vi prototype. |
| Backend + Data | Nguyen Huy Nghia | Thiet ke schema bai dang mock, metric engagement, xu ly cong thuc tinh diem chat luong. |
| AI logic / Mock AI output | Pham The Dung | Dinh nghia output tom tat, tag chu de, hanh vi tim kiem tu nhien dang mock. |
| Frontend Streamlit | Pham Van Luu | Xay giao dien bang Streamlit: bang bai dang, bo loc, sap xep, xem chi tiet. |
| Scoring model | Nguyen Huy Nghia, Pham The Dung | Chuan hoa cac chi so ve thang 0-100 va tinh weighted score theo cong thuc da chot. |
| Demo flow | Pham Van Luu, Pham The Dung | Chuan bi luong demo: xem danh sach, loc chu de, tim kiem tu nhien, xem chi tiet diem. |
| Repo & documentation | Nguyen Huy Nghia | Cap nhat README, requirements, gitignore va huong dan chay local. |

## Prototype hien tai

Thu muc prototype: `codebase/`

Chuc nang da co:

- Hien thi danh sach bai dang mock.
- Tinh diem chat luong theo cong thuc:

```text
Click 20% + Like 15% + Tim 20% + Thoi luong xem 25% + Ty le xem het 10% + Luu/Chia se 10%
```

- Chuan hoa tung chi so ve thang 0-100 truoc khi tinh diem tong.
- Loc theo chu de.
- Loc theo diem toi thieu.
- Sap xep theo diem, ngay moi nhat, hoac luu/chia se.
- Tim kiem tu nhien dang mock, vi du: `tim bai hay ve RAG va prompt`.
- Xem chi tiet bai dang: noi dung, mock summary, tags, link goc va bang phan ra diem.

## Cach chay

```powershell
cd codebase
pip install -r requirements.txt
streamlit run app.py
```

Sau khi chay, mo:

```text
http://localhost:8501
```

## Pham vi mock

- Du lieu bai dang la du lieu ao trong `codebase/mock_posts.csv`.
- Summary va tags la mock AI output, chua goi AI that.
- Tim kiem tu nhien hien dung keyword overlap + quality score, chua dung embedding.
- Link Discord la link gia lap de demo giao dien.

## Ghi chu bao mat

- Khong commit API key, file `.env`, `.streamlit/secrets.toml` hoac moi truong ao `.venv`.
- Neu dung du lieu Discord that trong cac vong sau, can an danh va chi trich dan phan toi thieu can thiet trong repo nop bai.
