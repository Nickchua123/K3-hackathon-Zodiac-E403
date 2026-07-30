from __future__ import annotations

import os
import re
import time
from pathlib import Path
from threading import Lock
from typing import Any

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request


APP_DIR = Path(__file__).resolve().parent
DATA_PATH = APP_DIR / "mock_posts.csv"
DISCORD_DATA_PATH = APP_DIR / "discord_posts.csv"
ENV_PATH = APP_DIR / ".env"
DEFAULT_DISCORD_SYNC_LIMIT = "50"
DEFAULT_DISCORD_SYNC_INTERVAL_SECONDS = "120"

REQUIRED_COLUMNS = [
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

WEIGHTS = {
    "click_score": 0.20,
    "like_score": 0.15,
    "heart_score": 0.20,
    "watch_time_score": 0.25,
    "completion_score": 0.10,
    "save_share_score": 0.10,
}

METRIC_DETAILS = {
    "click_score": ("Click", "clicks", "Số lượt bấm/xem bài"),
    "like_score": ("Like", "likes", "Số lượt like"),
    "heart_score": ("Tim", "hearts", "Số lượt thả tim"),
    "watch_time_score": ("Thời lượng xem", "watch_time_sec", "Tổng thời lượng xem ước tính"),
    "completion_score": ("Tỷ lệ xem hết", "completion_percent", "Phần trăm người xem hết nội dung"),
    "save_share_score": ("Lưu/Chia sẻ", "save_shares", "Số lượt lưu hoặc chia sẻ"),
}

STOPWORDS = {
    "tim",
    "tìm",
    "bai",
    "bài",
    "hay",
    "ve",
    "về",
    "va",
    "và",
    "cho",
    "cach",
    "cách",
    "cac",
    "các",
    "nhung",
    "những",
    "mot",
    "một",
    "co",
    "có",
    "la",
    "là",
}


class ChatRequest(BaseModel):
    query: str


app = FastAPI(title="Discord Quality Digest")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")

sync_lock = Lock()
last_sync_at = 0.0
last_sync_message = "Chưa đồng bộ Discord trong phiên này."


def read_env_values() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}

    values: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_config_value(key: str, default: str | None = None) -> str | None:
    values = read_env_values()
    return os.getenv(key) or values.get(key) or default


def get_int_config(key: str, default: str) -> int:
    try:
        return int(get_config_value(key, default) or default)
    except ValueError:
        return int(default)


def has_discord_config() -> bool:
    token = get_config_value("DISCORD_BOT_TOKEN")
    channel_id = get_config_value("DISCORD_CHANNEL_ID")
    channel_ids = get_config_value("DISCORD_CHANNEL_IDS")
    return bool(token and token != "your_discord_bot_token_here" and (channel_id or channel_ids))


def auto_sync_discord() -> None:
    global last_sync_at, last_sync_message

    if not has_discord_config():
        last_sync_message = "Chưa cấu hình Discord bot."
        return

    sync_interval = max(
        30,
        get_int_config("DISCORD_SYNC_INTERVAL_SECONDS", DEFAULT_DISCORD_SYNC_INTERVAL_SECONDS),
    )
    now = time.time()
    if now - last_sync_at < sync_interval:
        return

    if not sync_lock.acquire(blocking=False):
        return

    try:
        now = time.time()
        if now - last_sync_at < sync_interval:
            return

        from discord_bot import sync_discord_posts_to_csv

        sync_limit = get_int_config("DISCORD_SYNC_LIMIT", DEFAULT_DISCORD_SYNC_LIMIT)
        synced_posts = sync_discord_posts_to_csv(limit=sync_limit)
        last_sync_at = time.time()
        last_sync_message = f"Đã đồng bộ {len(synced_posts)} bài từ Discord."
    except Exception as exc:
        last_sync_at = time.time()
        last_sync_message = f"Không đồng bộ được Discord: {exc}"
    finally:
        sync_lock.release()


def normalize(series: pd.Series) -> pd.Series:
    min_value = series.min()
    max_value = series.max()
    if min_value == max_value:
        return pd.Series([100.0] * len(series), index=series.index)
    return ((series - min_value) / (max_value - min_value) * 100).round(1)


def add_scores(df: pd.DataFrame) -> pd.DataFrame:
    scored = df.copy()
    numeric_columns = ["clicks", "likes", "hearts", "watch_time_sec", "completion_rate", "save_shares"]
    for column in numeric_columns:
        scored[column] = pd.to_numeric(scored[column], errors="coerce").fillna(0)

    scored["click_score"] = normalize(scored["clicks"])
    scored["like_score"] = normalize(scored["likes"])
    scored["heart_score"] = normalize(scored["hearts"])
    scored["watch_time_score"] = normalize(scored["watch_time_sec"])
    scored["completion_score"] = (scored["completion_rate"] * 100).round(1)
    scored["completion_percent"] = scored["completion_score"]
    scored["save_share_score"] = normalize(scored["save_shares"])
    scored["quality_score"] = sum(scored[column] * weight for column, weight in WEIGHTS.items()).round(1)
    return scored.sort_values("quality_score", ascending=False).reset_index(drop=True)


def load_posts() -> pd.DataFrame:
    frames = []
    for path, source in [(DATA_PATH, "mock"), (DISCORD_DATA_PATH, "discord")]:
        if not path.exists():
            continue
        frame = pd.read_csv(path, encoding="utf-8-sig")
        if frame.empty:
            continue
        missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
        if missing:
            continue
        frame = frame[REQUIRED_COLUMNS].copy()
        frame["source"] = source
        frames.append(frame)

    if not frames:
        return pd.DataFrame(columns=REQUIRED_COLUMNS + ["source"])

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["post_id"], keep="last")
    return add_scores(df)


def tokenize(text: str) -> set[str]:
    tokens = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
    return {token for token in tokens if token and token not in STOPWORDS}


def search_posts(df: pd.DataFrame, query: str) -> pd.DataFrame:
    if not query.strip():
        return df

    query_terms = tokenize(query)
    if not query_terms:
        return df

    def row_score(row: pd.Series) -> float:
        haystack = " ".join(
            [
                str(row["title"]),
                str(row["topic"]),
                str(row["content"]),
                str(row["mock_summary"]),
                str(row["mock_tags"]),
            ]
        )
        row_terms = tokenize(haystack)
        overlap = len(query_terms & row_terms)
        phrase_bonus = 2 if query.lower().strip() in haystack.lower() else 0
        return overlap * 12 + phrase_bonus + row["quality_score"] * 0.35

    ranked = df.copy()
    ranked["match_score"] = ranked.apply(row_score, axis=1)
    ranked = ranked[ranked["match_score"] > ranked["quality_score"] * 0.35]
    return ranked.sort_values(["match_score", "quality_score"], ascending=False)


def score_detail(row: pd.Series) -> list[dict[str, Any]]:
    details = []
    for score_column, weight in WEIGHTS.items():
        label, raw_column, description = METRIC_DETAILS[score_column]
        raw_value = row[raw_column]
        if raw_column == "completion_percent":
            raw_display = f"{float(raw_value):.0f}%"
        elif raw_column == "watch_time_sec":
            raw_display = f"{int(float(raw_value))} giây"
        else:
            raw_display = str(int(float(raw_value)))

        score = float(row[score_column])
        details.append(
            {
                "signal": label,
                "raw_value": raw_display,
                "score": round(score, 1),
                "weight": f"{int(weight * 100)}%",
                "contribution": round(score * weight, 1),
                "description": description,
            }
        )
    return details


def post_to_result(row: pd.Series) -> dict[str, Any]:
    tags = [tag.strip() for tag in str(row["mock_tags"]).split(";") if tag.strip()]
    return {
        "post_id": row["post_id"],
        "title": row["title"],
        "author": row["author"],
        "topic": row["topic"],
        "summary": row["mock_summary"],
        "quality_reason": "Bài được ưu tiên vì khớp nội dung tìm kiếm và có điểm chất lượng cao.",
        "quality_score": float(row["quality_score"]),
        "url": row["url"],
        "source": row.get("source", "mock"),
        "tags": tags,
        "score_detail": score_detail(row),
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    auto_sync_discord()
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/status")
def status() -> dict[str, Any]:
    auto_sync_discord()
    df = load_posts()
    return {
        "post_count": len(df),
        "discord_configured": has_discord_config(),
        "last_sync_at": last_sync_at,
        "last_sync_message": last_sync_message,
    }


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict[str, Any]:
    auto_sync_discord()
    df = load_posts()
    ranked = search_posts(df, payload.query)
    results = [post_to_result(row) for _, row in ranked.head(3).iterrows()]
    answer = "Mình tìm thấy top 3 bài phù hợp nhất, sắp xếp ưu tiên theo điểm chất lượng."
    if not results:
        answer = "Mình chưa tìm thấy bài phù hợp với câu hỏi này."
    return {"answer": answer, "results": results}
