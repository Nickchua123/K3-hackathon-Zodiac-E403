# Discord Quality Digest Prototype

Prototype Streamlit mock cho y tuong "Tro ly Tong hop bai dang chat luong".

## Chay local

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Pham vi mock

- Du lieu bai dang nam trong `mock_posts.csv`.
- Output AI summary/tag la mock san trong file du lieu.
- Tim kiem tu nhien dang dung keyword overlap + quality score, chua dung embedding.
- Diem chat luong dung cong thuc da chot:
  - Click: 20%
  - Like: 15%
  - Tim: 20%
  - Thoi luong xem: 25%
  - Ty le xem het: 10%
  - Luu/Chia se: 10%

Moi chi so duoc chuan hoa ve thang 0-100 truoc khi tinh diem tong.
