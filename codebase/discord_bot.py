"""
discord_bot.py - Module gọi Discord REST API để tự động lấy bài viết từ Server Discord.
Hỗ trợ lấy bài từ Kênh Diễn Đàn (Forum Channel), Kênh Văn Bản (Text Channel), Thread và Guild.
"""

from __future__ import annotations

import os
import sys

_CWD = os.getcwd()
if _CWD not in sys.path:
    sys.path.insert(0, _CWD)

_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
if _FILE_DIR not in sys.path:
    sys.path.insert(0, _FILE_DIR)

import csv
import json
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_analyzer import analyze_post_content


APP_DIR = Path(_FILE_DIR)
ROOT_DIR = APP_DIR.parent
DATA_PATH = APP_DIR / "mock_posts.csv"


def get_discord_token() -> str | None:
    """Tự động đọc DISCORD_BOT_TOKEN hoặc DISCORD_USER_TOKEN từ biến môi trường hoặc .env."""
    token = os.environ.get("DISCORD_BOT_TOKEN") or os.environ.get("DISCORD_USER_TOKEN")
    if token:
        return token

    for env_file in [APP_DIR / ".env", ROOT_DIR / ".env"]:
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DISCORD_BOT_TOKEN=") or line.startswith("DISCORD_TOKEN="):
                        return line.split("=", 1)[1].strip(" '\"")
                    if line.startswith("DISCORD_USER_TOKEN="):
                        return line.split("=", 1)[1].strip(" '\"")
    return None


def get_discord_channel_id() -> str | None:
    """Tự động đọc DISCORD_CHANNEL_ID từ biến môi trường hoặc .env."""
    channel_id = os.environ.get("DISCORD_CHANNEL_ID")
    if channel_id:
        return channel_id

    for env_file in [APP_DIR / ".env", ROOT_DIR / ".env"]:
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DISCORD_CHANNEL_ID="):
                        return line.split("=", 1)[1].strip(" '\"")
    return None


def _safe_print(text: str):
    """In an toàn ra console trên Windows tránh lỗi UnicodeEncodeError."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "ignore").decode("ascii"))


def _make_discord_request(url: str, token: str) -> dict[str, Any] | list[Any] | None:
    """Gọi HTTP GET tới Discord REST API hỗ trợ cả Bot Token và User Token."""
    auth_header = token if token.startswith("Bot ") or token.startswith("Bearer ") else f"Bot {token}"
    headers = {
        "Authorization": auth_header,
        "User-Agent": "DiscordBot (https://github.com/vlearn, v1.0)",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        if err.code == 401 and not token.startswith("Bot ") and not token.startswith("Bearer "):
            headers["Authorization"] = token
            req = urllib.request.Request(url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=10) as resp2:
                    return json.loads(resp2.read().decode("utf-8"))
            except Exception as e2:
                _safe_print(f"[Discord API Error] HTTP {err.code}: {e2}")
        elif err.code == 403:
            _safe_print(f"[Discord API Warning] HTTP 403 Forbidden: Token/Bot khong co quyen truy cap ({url})")
        elif err.code == 404:
            pass
        else:
            _safe_print(f"[Discord API Warning] HTTP {err.code}: {err.reason} ({url})")
    except Exception as err:
        _safe_print(f"[Discord API Error] {err}")

    return None


def fetch_channel_info(channel_id: str, token: str) -> dict[str, Any] | None:
    """Lấy thông tin chi tiết của Channel / Thread / Guild."""
    url = f"https://discord.com/api/v10/channels/{channel_id}"
    res = _make_discord_request(url, token)
    return res if isinstance(res, dict) else None


def fetch_channel_messages(channel_id: str, token: str, limit: int = 20) -> list[dict[str, Any]]:
    """Gọi Discord REST API lấy danh sách bài đăng từ một Channel/Thread ID."""
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit={limit}"
    data = _make_discord_request(url, token)
    return data if isinstance(data, list) else []


def fetch_forum_threads(channel_id: str, token: str) -> list[dict[str, Any]]:
    """
    Lấy các bài đăng trong Kênh Diễn Đàn (Forum Channel).
    Kiểm tra cả Active Threads (bài đang mở) và Archived Threads (bài lưu trữ).
    """
    threads = []
    seen_ids = set()

    active_url = f"https://discord.com/api/v10/channels/{channel_id}/threads/active"
    active_res = _make_discord_request(active_url, token)
    if isinstance(active_res, dict) and "threads" in active_res:
        for t in active_res["threads"]:
            if t["id"] not in seen_ids:
                threads.append(t)
                seen_ids.add(t["id"])

    archived_url = f"https://discord.com/api/v10/channels/{channel_id}/threads/archived/public"
    archived_res = _make_discord_request(archived_url, token)
    if isinstance(archived_res, dict) and "threads" in archived_res:
        for t in archived_res["threads"]:
            if t["id"] not in seen_ids:
                threads.append(t)
                seen_ids.add(t["id"])

    return threads


def fetch_guild_threads(guild_id: str, token: str) -> list[dict[str, Any]]:
    """Thử lấy tất cả Active Threads từ Guild ID nếu truyền nhầm Server ID."""
    url = f"https://discord.com/api/v10/guilds/{guild_id}/threads/active"
    res = _make_discord_request(url, token)
    if isinstance(res, dict) and "threads" in res:
        return res["threads"]
    return []


def sync_discord_posts_to_csv(channel_id: str, token: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """
    Hàm chính: Gọi Discord API lấy bài viết -> Phân tích AI -> Lưu/Cập nhật vào file CSV mock_posts.csv.
    """
    bot_token = token or get_discord_token()
    if not bot_token:
        _safe_print("[Discord Bot Warning] Chua tim thay DISCORD_BOT_TOKEN trong file codebase/.env")
        return []

    _safe_print(f"=== Inspector: Dang kiem tra thông tin Discord ID '{channel_id}' ===")
    
    raw_posts_to_process = []
    target_forum_channel_id = channel_id

    # 1. Kiểm tra loại Channel (Channel, Forum, Thread, hay Server)
    ch_info = fetch_channel_info(channel_id, bot_token)

    if ch_info:
        ch_type = ch_info.get("type")
        ch_name = ch_info.get("name", "Unknown Channel")
        _safe_print(f"[Discord Inspector] Da tim thay Kenh '{ch_name}' (Type {ch_type})")

        if ch_type in [11, 12] and "parent_id" in ch_info:
            target_forum_channel_id = ch_info["parent_id"]
            _safe_print(f"[Discord Inspector] ID nay la 1 Thread thuoc Forum parent_id: '{target_forum_channel_id}'")
    else:
        _safe_print(f"[Discord Inspector] Zero info return. Thu quet Forum Threads va Guild Threads...")

    # A. Thử lấy bài từ Forum Threads (Channel ID hoặc Parent Forum Channel ID)
    forum_threads = fetch_forum_threads(target_forum_channel_id, bot_token)
    
    # B. Nếu không thấy bài, thử lấy tất cả Threads của Guild/Server
    if not forum_threads and ch_info and "guild_id" in ch_info:
        forum_threads = fetch_guild_threads(ch_info["guild_id"], bot_token)

    if forum_threads:
        _safe_print(f"[Discord Bot] Tim thay {len(forum_threads)} bai dang (Threads) trong Kenh Dien Dan!")

    for thread in forum_threads:
        thread_id = thread.get("id")
        thread_title = thread.get("name", "Bai viet Forum Discord")
        
        thread_msgs = fetch_channel_messages(thread_id, bot_token, limit=1)
        if thread_msgs:
            starter_msg = thread_msgs[0]
            raw_posts_to_process.append({
                "id": thread_id,
                "title": thread_title,
                "content": starter_msg.get("content", "") or thread_title,
                "author": starter_msg.get("author", {}),
                "reactions": starter_msg.get("reactions", []),
                "guild_id": thread.get("guild_id", "@me"),
                "channel_id": target_forum_channel_id,
            })
        else:
            raw_posts_to_process.append({
                "id": thread_id,
                "title": thread_title,
                "content": f"Bai viet voi tieu de: {thread_title}",
                "author": {"username": "Discord Member"},
                "reactions": [],
                "guild_id": thread.get("guild_id", "@me"),
                "channel_id": target_forum_channel_id,
            })

    # C. Nếu không có Forum Threads, thử lấy tin nhắn trực tiếp Kênh Văn Bản
    if not raw_posts_to_process:
        direct_msgs = fetch_channel_messages(channel_id, bot_token, limit=limit)
        if direct_msgs:
            for msg in direct_msgs:
                raw_posts_to_process.append({
                    "id": msg.get("id"),
                    "title": (msg.get("content", "").split("\n")[0] if msg.get("content") else "Bai chia se Discord"),
                    "content": msg.get("content", ""),
                    "author": msg.get("author", {}),
                    "reactions": msg.get("reactions", []),
                    "guild_id": msg.get("guild_id", "@me"),
                    "channel_id": channel_id,
                })

    if not raw_posts_to_process:
        _safe_print("\n[Discord Bot Log Error] Khong tim thay bai dang nao tu Discord.")
        _safe_print("----------------------------------------------------------------------")
        _safe_print(" NGUYEN NHAN CHINH KHUYEN NGO:")
        _safe_print(" 1. DISCORD_BOT_TOKEN chua duoc moi (Add) vao Máy Chủ Discord nay.")
        _safe_print("    -> Vao Discord Developer Portal -> Bot -> Invite Link (voi quyen Read Messages/View Channels).")
        _safe_print(" 2. Hoac ID truyen vao chua phai la Channel ID / Thread ID cua Discord.")
        _safe_print("----------------------------------------------------------------------")
        return []

    processed_posts = []

    for post in raw_posts_to_process:
        post_id_short = str(post["id"])[-4:]
        title = post["title"]
        if len(title) > 80:
            title = title[:77] + "..."

        content = post["content"].strip()
        author_info = post.get("author", {})
        author_name = author_info.get("global_name") or author_info.get("username") or "Discord User"

        reactions = post.get("reactions", [])
        like_count = sum(r.get("count", 0) for r in reactions if r.get("emoji", {}).get("name") in ["👍", "like", "upvote"]) or 5
        heart_count = sum(r.get("count", 0) for r in reactions if r.get("emoji", {}).get("name") in ["❤️", "💖", "heart"]) or 3

        msg_url = f"https://discord.com/channels/{post['guild_id']}/{post['channel_id']}/{post['id']}"

        ai_analysis = analyze_post_content(title, content or title)

        post_record = {
            "post_id": f"DISC-{post_id_short}",
            "author": author_name,
            "title": title,
            "content": content or title,
            "topic": ai_analysis.get("topic", "Chia sẻ"),
            "url": msg_url,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "clicks": max(10, len(content) // 5),
            "likes": max(1, like_count),
            "hearts": max(1, heart_count),
            "watch_time_sec": max(30, len(content.split()) * 3),
            "completion_rate": 0.85,
            "save_shares": max(1, len(reactions)),
            "mock_summary": ai_analysis.get("summary", "Tom tat tu Discord Bot"),
            "mock_tags": ";".join(ai_analysis.get("tags", ["Discord"])),
        }
        processed_posts.append(post_record)

    if processed_posts and DATA_PATH.exists():
        existing_df = pd_read_csv_safe(DATA_PATH)
        existing_ids = set(existing_df["post_id"].astype(str)) if hasattr(existing_df, "empty") and not existing_df.empty else set()

        new_rows = [p for p in processed_posts if p["post_id"] not in existing_ids]

        if new_rows:
            fieldnames = list(processed_posts[0].keys())
            with open(DATA_PATH, "a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                for row in new_rows:
                    writer.writerow(row)
            _safe_print(f"[Discord Bot] Da dong bo thanh cong {len(new_rows)} bai viet moi vao database CSV!")
        else:
            _safe_print(f"[Discord Bot] Tat ca {len(processed_posts)} bai viet Discord da duoc dong bo truoc do.")

    return processed_posts


def pd_read_csv_safe(file_path: Path):
    """Đọc CSV an toàn."""
    try:
        import pandas as pd
        return pd.read_csv(file_path)
    except Exception:
        return None


if __name__ == "__main__":
    channel = sys.argv[1] if len(sys.argv) > 1 else (get_discord_channel_id() or "")
    if not channel or channel in ["your_channel_id_here", "1234567890"]:
        _safe_print("[Discord Bot Error] Vui long truyen Channel ID hoac cau hinh DISCORD_CHANNEL_ID trong file codebase/.env!")
        sys.exit(1)

    token = get_discord_token()
    if token and token != "your_discord_bot_token_here":
        posts = sync_discord_posts_to_csv(channel, token)
        _safe_print(f"Done processing {len(posts)} posts from Discord channel.")
    else:
        _safe_print("Vui long them DISCORD_BOT_TOKEN hop le vao file codebase/.env!")
