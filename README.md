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
| Frontend Streamlit | Pham Van Luu | Xay giao dien chatbot bang Streamlit: nhap chu de, hien top 3 bai dang phu hop. |
| Scoring model | Nguyen Huy Nghia, Pham The Dung | Chuan hoa cac chi so ve thang 0-100 va tinh weighted score theo cong thuc da chot. |
| Demo flow | Pham Van Luu, Pham The Dung | Chuan bi luong demo chatbot: hoi chu de, xem top 3 bai dang, mo link goc. |
| Repo & documentation | Nguyen Huy Nghia | Cap nhat README, requirements, gitignore va huong dan chay local. |

## Prototype hien tai

Thu muc prototype: `codebase/`

Chuc nang da co:

- Chatbot nhan cau hoi chu de va tra top 3 bai dang phu hop nhat.
- Tinh diem chat luong theo cong thuc:

```text
Click 20% + Like 15% + Tim 20% + Thoi luong xem 25% + Ty le xem het 10% + Luu/Chia se 10%
```

- Chuan hoa tung chi so ve thang 0-100 truoc khi tinh diem tong.
- Tim kiem tu nhien dang mock, vi du: `tim bai hay ve RAG va prompt`.
- Hien summary, tags, ly do nen doc, diem chat luong va link goc cho tung ket qua.

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
- Neu cau hinh Discord bot, script `codebase/discord_bot.py` co the sync du lieu that vao `codebase/discord_posts.csv`; chatbot tu dong doc them file nay.
- Summary va tags la mock AI output, chua goi AI that.
- Tim kiem tu nhien hien dung keyword overlap + quality score, chua dung embedding.
- Link Discord la link gia lap de demo giao dien.

## Ghi chu bao mat

- Khong commit API key, file `.env`, `.streamlit/secrets.toml` hoac moi truong ao `.venv`.
- Neu dung du lieu Discord that trong cac vong sau, can an danh va chi trich dan phan toi thieu can thiet trong repo nop bai.
