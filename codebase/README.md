# Discord Quality Digest Prototype

Prototype Streamlit mock cho y tuong "Tro ly Tong hop bai dang chat luong".
Flow chinh la chatbot: user hoi mot chu de, bot tra top 3 bai lien quan co diem chat luong cao nhat.

## Chay local

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Lay du lieu Discord that

1. Tao Discord bot trong Discord Developer Portal.
2. Trong Bot settings, bat `Message Content Intent` neu can doc noi dung tin nhan.
3. Invite bot vao server voi quyen `View Channel` va `Read Message History`.
4. Bat Developer Mode trong Discord, copy ID cua channel/forum/thread can lay du lieu.
5. Tao file `.env` trong thu muc `codebase/`:

```text
DISCORD_BOT_TOKEN=your_discord_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_here
```

Neu can lay nhieu kenh:

```text
DISCORD_CHANNEL_IDS=channel_id_1,channel_id_2,channel_id_3
```

Chay sync:

```powershell
cd codebase
python discord_bot.py --limit 50
```

Hoac truyen channel ID truc tiep:

```powershell
python discord_bot.py 123456789012345678 --limit 50
```

Du lieu that duoc luu local vao `discord_posts.csv` va bi `.gitignore` bo qua. App chatbot tu dong doc them file nay neu ton tai.

Mac dinh sync khong goi AI de tranh ton API. Neu muon dung API tao summary/topic/tag khi sync, them key va flag:

```text
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
```

```powershell
python discord_bot.py --limit 50 --with-ai
```

Neu khong co `.env` hoac chua sync Discord, app van chay voi data mock trong `mock_posts.csv`.

## Pham vi mock

- Du lieu bai dang nam trong `mock_posts.csv`.
- Output AI summary/tag mac dinh la mock san trong file du lieu.
- Man hinh chinh chi con chatbot: hoi chu de va nhan top 3 bai dang co score cao kem summary, reason va link goc.
- Tim kiem tu nhien dang dung keyword overlap + quality score, chua dung embedding.
- Diem chat luong dung cong thuc da chot:
  - Click: 20%
  - Like: 15%
  - Tim: 20%
  - Thoi luong xem: 25%
  - Ty le xem het: 10%
  - Luu/Chia se: 10%

Moi chi so duoc chuan hoa ve thang 0-100 truoc khi tinh diem tong.
