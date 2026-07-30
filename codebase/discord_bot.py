from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_analyzer import analyze_post_content


APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
DISCORD_DATA_PATH = APP_DIR / "discord_posts.csv"
DISCORD_API_BASE = "https://discord.com/api/v10"

CSV_COLUMNS = [
    "post_id",
    "title",
    "author",
    "topic",
    "content",
    "clicks",
    "likes",
    "hearts",
    "watch_time_sec",
    "completion_rate",
    "save_shares",
    "url",
    "created_at",
    "mock_summary",
    "mock_tags",
]

TEXT_CHANNEL_TYPES = {0, 5}
THREAD_CHANNEL_TYPES = {10, 11, 12}
FORUM_CHANNEL_TYPES = {15, 16}
MIN_CONTENT_CHARS = 40


def read_env_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for env_file in [APP_DIR / ".env", ROOT_DIR / ".env"]:
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def get_discord_token() -> str | None:
    values = read_env_values()
    return os.getenv("DISCORD_BOT_TOKEN") or values.get("DISCORD_BOT_TOKEN") or values.get("DISCORD_TOKEN")


def get_discord_channel_ids() -> list[str]:
    values = read_env_values()
    raw_value = os.getenv("DISCORD_CHANNEL_IDS") or values.get("DISCORD_CHANNEL_IDS")
    raw_value = raw_value or os.getenv("DISCORD_CHANNEL_ID") or values.get("DISCORD_CHANNEL_ID") or ""
    return [part.strip() for part in re.split(r"[,;\s]+", raw_value) if part.strip()]


def get_discord_channel_id() -> str | None:
    channel_ids = get_discord_channel_ids()
    return channel_ids[0] if channel_ids else None


def safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "ignore").decode("ascii"))


def discord_get(path: str, token: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any] | None:
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{DISCORD_API_BASE}{path}{query}"
    auth_header = token if token.startswith("Bot ") else f"Bot {token}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "User-Agent": "DiscordQualityDigest/1.0",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        if exc.code == 429:
            retry_after = 1.0
            try:
                retry_after = float(json.loads(body).get("retry_after", 1.0))
            except Exception:
                pass
            safe_print(f"[Discord] Rate limited. Retrying after {retry_after:.1f}s")
            time.sleep(retry_after)
            return discord_get(path, token, params)
        if exc.code == 403:
            safe_print(f"[Discord] 403 Forbidden: bot lacks View Channel or Read Message History for {path}")
        elif exc.code == 404:
            safe_print(f"[Discord] 404 Not Found: check channel/thread/guild id for {path}")
        elif exc.code == 401:
            safe_print("[Discord] 401 Unauthorized: check DISCORD_BOT_TOKEN")
        else:
            safe_print(f"[Discord] HTTP {exc.code}: {exc.reason} {body[:200]}")
    except Exception as exc:
        safe_print(f"[Discord] Request failed for {path}: {exc}")
    return None


def fetch_channel_info(channel_id: str, token: str) -> dict[str, Any] | None:
    data = discord_get(f"/channels/{channel_id}", token)
    return data if isinstance(data, dict) and "id" in data else None


def fetch_channel_messages(channel_id: str, token: str, limit: int = 50) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    before: str | None = None

    while len(messages) < limit:
        batch_size = min(100, limit - len(messages))
        params: dict[str, Any] = {"limit": batch_size}
        if before:
            params["before"] = before

        data = discord_get(f"/channels/{channel_id}/messages", token, params)
        if not isinstance(data, list) or not data:
            break

        messages.extend(item for item in data if isinstance(item, dict))
        before = str(data[-1].get("id"))
        if len(data) < batch_size:
            break

    return messages


def fetch_single_message(channel_id: str, message_id: str, token: str) -> dict[str, Any] | None:
    data = discord_get(f"/channels/{channel_id}/messages/{message_id}", token)
    return data if isinstance(data, dict) and "id" in data else None


def fetch_guild_active_threads(guild_id: str, token: str) -> list[dict[str, Any]]:
    data = discord_get(f"/guilds/{guild_id}/threads/active", token)
    if isinstance(data, dict) and isinstance(data.get("threads"), list):
        return [thread for thread in data["threads"] if isinstance(thread, dict)]
    return []


def fetch_public_archived_threads(channel_id: str, token: str, limit: int = 50) -> list[dict[str, Any]]:
    threads: list[dict[str, Any]] = []
    before: str | None = None

    while len(threads) < limit:
        params: dict[str, Any] = {"limit": min(100, limit - len(threads))}
        if before:
            params["before"] = before

        data = discord_get(f"/channels/{channel_id}/threads/archived/public", token, params)
        if not isinstance(data, dict) or not isinstance(data.get("threads"), list):
            break

        batch = [thread for thread in data["threads"] if isinstance(thread, dict)]
        threads.extend(batch)
        if not data.get("has_more") or not batch:
            break
        before = batch[-1].get("thread_metadata", {}).get("archive_timestamp")

    return threads


def fetch_forum_threads(channel_info: dict[str, Any], token: str, limit: int = 50) -> list[dict[str, Any]]:
    channel_id = str(channel_info["id"])
    guild_id = str(channel_info.get("guild_id") or "")
    seen_ids: set[str] = set()
    threads: list[dict[str, Any]] = []

    if guild_id:
        for thread in fetch_guild_active_threads(guild_id, token):
            if str(thread.get("parent_id")) != channel_id:
                continue
            thread_id = str(thread.get("id"))
            if thread_id not in seen_ids:
                seen_ids.add(thread_id)
                threads.append(thread)

    for thread in fetch_public_archived_threads(channel_id, token, limit=limit):
        thread_id = str(thread.get("id"))
        if thread_id not in seen_ids:
            seen_ids.add(thread_id)
            threads.append(thread)

    return threads[:limit]


def message_url(guild_id: str | None, channel_id: str, message_id: str) -> str:
    return f"https://discord.com/channels/{guild_id or '@me'}/{channel_id}/{message_id}"


def snowflake_datetime(snowflake_id: str) -> str:
    try:
        timestamp_ms = (int(snowflake_id) >> 22) + 1420070400000
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def clean_title(text: str, fallback: str) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), fallback)
    first_line = re.sub(r"`+", "", first_line)
    title = re.sub(r"\s+", " ", first_line).strip() or fallback
    return title[:77] + "..." if len(title) > 80 else title


def clean_discord_content(text: str) -> str:
    cleaned = re.sub(r"```[\s\S]*?```", "\n[Đã lược bỏ đoạn code]\n", text)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def count_reactions(message: dict[str, Any], names: set[str]) -> int:
    total = 0
    for reaction in message.get("reactions", []) or []:
        emoji_name = str(reaction.get("emoji", {}).get("name", "")).lower()
        if emoji_name in names:
            total += int(reaction.get("count", 0) or 0)
    return total


def simple_metadata(title: str, content: str) -> dict[str, Any]:
    text = f"{title} {content}".lower()
    topic_rules = [
        ("RAG", ["rag", "retrieval", "vector", "embedding", "chunk"]),
        ("Prompt Engineering", ["prompt", "system prompt", "instruction"]),
        ("Evaluation", ["eval", "evaluation", "golden set", "rubric", "test"]),
        ("AI Agent", ["agent", "tool", "function call"]),
        ("Frontend", ["streamlit", "frontend", "ui", "ux"]),
        ("AI Safety", ["guardrail", "safety", "bao mat", "api key"]),
        ("Product", ["product", "spec", "jtbd", "impact", "demo"]),
    ]
    matched = [topic for topic, keywords in topic_rules if any(keyword in text for keyword in keywords)]
    topic = matched[0] if matched else "Discord"
    tags = matched[:4] if matched else ["Discord", "Chia se"]

    sentences = [part.strip() for part in re.split(r"[.!?\n]", content) if part.strip()]
    summary = sentences[0] if sentences else title
    if len(summary) > 220:
        summary = summary[:217] + "..."

    return {
        "topic": topic,
        "tags": tags,
        "summary": summary,
    }


def raw_post_from_message(
    message: dict[str, Any],
    channel_id: str,
    guild_id: str | None,
    title: str | None = None,
) -> dict[str, Any] | None:
    message_id = str(message.get("id") or "")
    content = clean_discord_content(str(message.get("content") or ""))
    if not message_id or len(content) < MIN_CONTENT_CHARS:
        return None
    return {
        "id": message_id,
        "title": title or clean_title(content, "Discord message"),
        "content": content,
        "author": message.get("author", {}),
        "reactions": message.get("reactions", []),
        "guild_id": guild_id,
        "channel_id": channel_id,
    }


def collect_raw_posts(channel_id: str, token: str, limit: int) -> list[dict[str, Any]]:
    channel_info = fetch_channel_info(channel_id, token)
    if not channel_info:
        safe_print(f"[Discord] Cannot inspect id {channel_id}")
        return []

    channel_type = int(channel_info.get("type", -1))
    channel_name = channel_info.get("name", channel_id)
    guild_id = channel_info.get("guild_id")
    safe_print(f"[Discord] Reading {channel_name} ({channel_id}), type={channel_type}")

    if channel_type in THREAD_CHANNEL_TYPES:
        messages = fetch_channel_messages(channel_id, token, limit=limit)
        return [
            raw
            for raw in (raw_post_from_message(message, channel_id, guild_id) for message in messages)
            if raw is not None
        ]

    if channel_type in FORUM_CHANNEL_TYPES:
        raw_posts: list[dict[str, Any]] = []
        for thread in fetch_forum_threads(channel_info, token, limit=limit):
            thread_id = str(thread.get("id") or "")
            if not thread_id:
                continue
            starter = fetch_single_message(thread_id, thread_id, token)
            if starter is None:
                messages = fetch_channel_messages(thread_id, token, limit=1)
                starter = messages[0] if messages else {}
            raw = raw_post_from_message(
                starter,
                channel_id=thread_id,
                guild_id=str(thread.get("guild_id") or guild_id or ""),
                title=str(thread.get("name") or "Discord forum post"),
            )
            if raw:
                raw["url_channel_id"] = thread_id
                raw_posts.append(raw)
        return raw_posts

    if channel_type in TEXT_CHANNEL_TYPES:
        messages = fetch_channel_messages(channel_id, token, limit=limit)
        return [
            raw
            for raw in (raw_post_from_message(message, channel_id, guild_id) for message in messages)
            if raw is not None
        ]

    safe_print(f"[Discord] Unsupported channel type {channel_type} for id {channel_id}")
    return []


def build_post_record(raw_post: dict[str, Any], with_ai: bool) -> dict[str, Any]:
    post_id = str(raw_post["id"])
    title = clean_title(str(raw_post["title"]), "Discord post")
    content = str(raw_post["content"]).strip()
    author = raw_post.get("author", {}) or {}
    author_name = author.get("global_name") or author.get("username") or "Discord User"

    if with_ai:
        analysis = analyze_post_content(title, content)
        topic = str(analysis.get("topic") or "Discord")
        tags = analysis.get("tags") or ["Discord"]
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        summary = str(analysis.get("summary") or title)
    else:
        analysis = simple_metadata(title, content)
        topic = analysis["topic"]
        tags = analysis["tags"]
        summary = analysis["summary"]

    like_count = count_reactions(raw_post, {"\U0001f44d", "+1", "like", "upvote"})
    heart_count = count_reactions(raw_post, {"\u2764", "\u2764\ufe0f", "\U0001f496", "heart"})
    reaction_count = sum(int(item.get("count", 0) or 0) for item in raw_post.get("reactions", []) or [])
    word_count = len(content.split())

    channel_id = str(raw_post.get("url_channel_id") or raw_post.get("channel_id") or "")
    guild_id = str(raw_post.get("guild_id") or "@me")

    return {
        "post_id": f"DISC-{post_id}",
        "title": title,
        "author": author_name,
        "topic": topic,
        "content": content,
        "clicks": max(10, word_count * 2 + reaction_count * 4),
        "likes": like_count,
        "hearts": heart_count,
        "watch_time_sec": max(30, word_count * 3),
        "completion_rate": 0.85 if word_count >= 20 else 0.65,
        "save_shares": reaction_count,
        "url": message_url(guild_id, channel_id, post_id),
        "created_at": snowflake_datetime(post_id),
        "mock_summary": summary,
        "mock_tags": ";".join(str(tag) for tag in tags[:5]),
    }


def read_existing_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sync_discord_posts_to_csv(
    channel_id: str | None = None,
    token: str | None = None,
    limit: int = 50,
    output_path: Path = DISCORD_DATA_PATH,
    with_ai: bool = False,
) -> list[dict[str, Any]]:
    bot_token = token or get_discord_token()
    if not bot_token or bot_token == "your_discord_bot_token_here":
        raise RuntimeError("Missing DISCORD_BOT_TOKEN in codebase/.env")

    channel_ids = [channel_id] if channel_id else get_discord_channel_ids()
    channel_ids = [item for item in channel_ids if item and item != "your_channel_id_here"]
    if not channel_ids:
        raise RuntimeError("Missing DISCORD_CHANNEL_ID or DISCORD_CHANNEL_IDS in codebase/.env")

    raw_posts: list[dict[str, Any]] = []
    for current_channel_id in channel_ids:
        raw_posts.extend(collect_raw_posts(current_channel_id, bot_token, limit=limit))

    if not raw_posts:
        safe_print("[Discord] No usable posts found.")
        return []

    new_records = [build_post_record(raw_post, with_ai=with_ai) for raw_post in raw_posts]
    existing_rows = read_existing_rows(output_path)
    rows_by_id = {str(row.get("post_id")): row for row in existing_rows}
    for record in new_records:
        rows_by_id[record["post_id"]] = record

    merged_rows = list(rows_by_id.values())
    merged_rows.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
    write_rows(output_path, merged_rows)

    safe_print(f"[Discord] Synced {len(new_records)} posts into {output_path}")
    safe_print(f"[Discord] Total rows in CSV: {len(merged_rows)}")
    return new_records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync real Discord posts into discord_posts.csv")
    parser.add_argument("channel_id", nargs="?", help="Discord channel/forum/thread id. Defaults to .env")
    parser.add_argument("--limit", type=int, default=50, help="Max posts/messages per channel")
    parser.add_argument("--output", default=str(DISCORD_DATA_PATH), help="Output CSV path")
    parser.add_argument("--with-ai", action="store_true", help="Call configured AI API for summary/topic/tags")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        sync_discord_posts_to_csv(
            channel_id=args.channel_id,
            limit=args.limit,
            output_path=Path(args.output),
            with_ai=args.with_ai,
        )
    except Exception as exc:
        safe_print(f"[Discord] Sync failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
