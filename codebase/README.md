# Discord Quality Digest Prototype

Prototype Streamlit mock cho y tuong "Tro ly Tong hop bai dang chat luong".
Flow chinh la chatbot: user hoi mot chu de, bot tra top 3 bai lien quan co diem chat luong cao nhat.

## Chay local

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Cau hinh Gemini

Tao file `.env` trong thu muc `codebase/`:

```text
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
```

Neu khong co `.env`, app van chay voi mock summary/tag.

## Pham vi mock

- Du lieu bai dang nam trong `mock_posts.csv`.
- Output AI summary/tag mac dinh la mock san trong file du lieu.
- Tab `Chatbot` la man hinh chinh: hoi chu de va nhan top 3 bai dang co score cao kem summary, reason va link goc.
- Tab `Knowledge base` dung de xem bang du lieu, loc/sap xep va xem chi tiet bai.
- Tab `Admin` dung de chay batch AI processing va tai ket qua AI.
- Khi co `GEMINI_API_KEY`, bam `Generate AI summary/tag` o man hinh chi tiet de goi AI that cho bai dang dang chon.
- Bam `Analyze visible posts` de chay batch AI cho toan bo bai dang dang hien thi sau khi loc/tim kiem.
- Co the tai ket qua AI tam thoi bang `Download AI results CSV`.
- Tim kiem tu nhien dang dung keyword overlap + quality score, chua dung embedding.
- Diem chat luong dung cong thuc da chot:
  - Click: 20%
  - Like: 15%
  - Tim: 20%
  - Thoi luong xem: 25%
  - Ty le xem het: 10%
  - Luu/Chia se: 10%

Moi chi so duoc chuan hoa ve thang 0-100 truoc khi tinh diem tong.
