from __future__ import annotations

import asyncio
import json
import os
import re
import time
import unicodedata
import urllib.request
from contextlib import asynccontextmanager, suppress
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

import sqlite_storage
from embedding_index import (
    MODEL_NAME as EMBEDDING_MODEL,
    cosine_similarity,
    deserialize_vector,
    embed_post,
    embed_text,
)


APP_DIR = Path(__file__).resolve().parent
DATA_PATH = APP_DIR / "mock_posts.csv"
DISCORD_DATA_PATH = APP_DIR / "discord_posts.csv"
ENV_PATH = APP_DIR / ".env"
DEFAULT_DISCORD_SYNC_LIMIT = "50"
DEFAULT_DISCORD_SYNC_INTERVAL_SECONDS = "120"
DEFAULT_TOP_K_RESULTS = "3"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_RAG_ENABLED = "false"
DEFAULT_RAG_PROVIDER = "gemini"
DEFAULT_RAG_INCLUDE_DISCORD_DATA = "false"
DEFAULT_DISCORD_SYNC_WITH_AI = "false"
HYBRID_SEMANTIC_WEIGHT = 0.50
HYBRID_LEXICAL_WEIGHT = 0.20
HYBRID_QUALITY_WEIGHT = 0.30
MIN_SEMANTIC_EVIDENCE = 18.0

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
    "chat",
    "chất",
    "dang",
    "đăng",
    "luong",
    "lượng",
    "nhung",
    "những",
    "mot",
    "một",
    "co",
    "có",
    "la",
    "là",
    "tag",
    "theo",
}

OUT_OF_SCOPE_PATTERNS = {
    "deadline",
    "han nop",
    "link nop bai",
    "nop bai o dau",
    "lich hoc",
    "hoc phi",
    "thoi tiet",
    "du bao thoi tiet",
    "xo so",
    "gia vang",
}
GENERIC_DISCOVERY_PATTERNS = {
    "tim bai hay",
    "goi y bai hay",
    "bai noi bat",
    "bai chat luong",
}
SCOPE_STOPWORDS = {
    "bai",
    "ban",
    "bao",
    "cac",
    "can",
    "cach",
    "cau",
    "cho",
    "chu",
    "co",
    "cua",
    "duoc",
    "gi",
    "giup",
    "hay",
    "hom",
    "khong",
    "la",
    "mai",
    "minh",
    "mot",
    "muon",
    "nao",
    "nay",
    "nhu",
    "nhung",
    "o",
    "roi",
    "the",
    "thoi",
    "tiet",
    "tim",
    "toi",
    "ve",
    "va",
}
SHORT_DOMAIN_TERMS = {"ai", "db", "js", "ml", "qa", "ui", "ux"}
QUALITY_LOW_PATTERNS = {"diem thap", "kem nhat", "te nhat", "thap nhat"}
QUALITY_HIGH_PATTERNS = {"cao nhat", "diem cao", "tot nhat"}
RANKING_QUERY_STOPWORDS = {
    "baid",
    "bai",
    "cao",
    "chat",
    "co",
    "danh",
    "diem",
    "duoc",
    "gia",
    "hang",
    "kem",
    "luong",
    "nhat",
    "te",
    "thap",
    "top",
    "viet",
    "xep",
}
QUALITY_DISCLAIMER = (
    "Diem chat luong chi dung de uu tien bai nen doc, "
    "khong phai xac nhan kien thuc dung tuyet doi."
)


class ChatRequest(BaseModel):
    query: str
    topic: str | None = None
    top_k: int | None = None


@asynccontextmanager
async def app_lifespan(application: FastAPI):
    await asyncio.to_thread(ensure_database_ready)
    stop_event = asyncio.Event()
    worker = asyncio.create_task(discord_background_worker(stop_event))
    application.state.discord_worker = worker
    try:
        yield
    finally:
        stop_event.set()
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker


app = FastAPI(title="Discord Quality Digest", lifespan=app_lifespan)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")

sync_lock = Lock()
database_ready_lock = Lock()
database_ready = False
last_sync_at = 0.0
last_sync_message = "Đang khởi tạo SQLite và background workflow."


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


def get_bool_config(key: str, default: str) -> bool:
    value = str(get_config_value(key, default) or default).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default.strip().lower() in {"1", "true", "yes", "on"}


def get_top_k_results() -> int:
    return min(10, max(1, get_int_config("TOP_K_RESULTS", DEFAULT_TOP_K_RESULTS)))


def has_discord_config() -> bool:
    token = get_config_value("DISCORD_BOT_TOKEN")
    channel_id = get_config_value("DISCORD_CHANNEL_ID")
    channel_ids = get_config_value("DISCORD_CHANNEL_IDS")
    return bool(token and token != "your_discord_bot_token_here" and (channel_id or channel_ids))


def _validated_csv_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if frame.empty:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"{path.name} thiếu cột: {', '.join(missing)}")
    return frame[REQUIRED_COLUMNS].copy()


def ensure_database_ready() -> None:
    global database_ready, last_sync_message

    if database_ready:
        return
    with database_ready_lock:
        if database_ready:
            return

        sqlite_storage.initialize_database()
        migration_stats = []
        for path, source in [(DATA_PATH, "mock"), (DISCORD_DATA_PATH, "discord")]:
            frame = _validated_csv_frame(path)
            if frame.empty:
                continue
            stats = sqlite_storage.upsert_dataframe(frame, source=source)
            migration_stats.append(
                f"{source}: {stats['seen']} bài, {stats['embedded']} embedding mới"
            )

        database_ready = True
        if migration_stats:
            last_sync_message = "SQLite sẵn sàng · " + " · ".join(migration_stats)
        else:
            last_sync_message = "SQLite sẵn sàng nhưng chưa có dữ liệu nguồn."


def sync_discord_once(force: bool = False) -> None:
    global last_sync_at, last_sync_message

    ensure_database_ready()
    if not has_discord_config():
        last_sync_message = "Background worker đang chờ cấu hình Discord bot."
        return

    sync_interval = max(
        30,
        get_int_config("DISCORD_SYNC_INTERVAL_SECONDS", DEFAULT_DISCORD_SYNC_INTERVAL_SECONDS),
    )
    now = time.time()
    if not force and now - last_sync_at < sync_interval:
        return

    if not sync_lock.acquire(blocking=False):
        return

    started_at = sqlite_storage.utc_now()
    try:
        now = time.time()
        if not force and now - last_sync_at < sync_interval:
            return

        from discord_bot import sync_discord_posts_to_csv

        sync_limit = get_int_config("DISCORD_SYNC_LIMIT", DEFAULT_DISCORD_SYNC_LIMIT)
        with_ai = get_bool_config("DISCORD_SYNC_WITH_AI", DEFAULT_DISCORD_SYNC_WITH_AI)
        synced_posts = sync_discord_posts_to_csv(limit=sync_limit, with_ai=with_ai)
        stats = sqlite_storage.upsert_posts(synced_posts, source="discord")
        changed = stats["inserted"] + stats["updated"]
        last_sync_at = time.time()
        last_sync_message = (
            f"Background sync đã xử lý {stats['seen']} bài Discord · "
            f"{changed} bài mới/cập nhật · {stats['embedded']} embedding mới."
        )
        sqlite_storage.record_sync_run(
            source="discord",
            status="success",
            posts_seen=stats["seen"],
            posts_changed=changed,
            message=last_sync_message,
            started_at=started_at,
        )
    except Exception as exc:
        last_sync_at = time.time()
        last_sync_message = f"Không đồng bộ được Discord: {exc}"
        sqlite_storage.record_sync_run(
            source="discord",
            status="error",
            posts_seen=0,
            posts_changed=0,
            message=last_sync_message,
            started_at=started_at,
        )
    finally:
        sync_lock.release()


async def discord_background_worker(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        await asyncio.to_thread(sync_discord_once, True)
        interval = max(
            30,
            get_int_config(
                "DISCORD_SYNC_INTERVAL_SECONDS",
                DEFAULT_DISCORD_SYNC_INTERVAL_SECONDS,
            ),
        )
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            continue


def normalize(series: pd.Series) -> pd.Series:
    min_value = series.min()
    max_value = series.max()
    if min_value == max_value:
        return pd.Series([0.0] * len(series), index=series.index)
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
    scored["completion_score"] = (scored["completion_rate"].clip(lower=0, upper=1) * 100).round(1)
    scored["completion_percent"] = scored["completion_score"]
    scored["save_share_score"] = normalize(scored["save_shares"])
    scored["quality_score"] = sum(scored[column] * weight for column, weight in WEIGHTS.items()).round(1)
    return scored.sort_values("quality_score", ascending=False).reset_index(drop=True)


def load_posts() -> pd.DataFrame:
    ensure_database_ready()
    df = sqlite_storage.load_posts_dataframe()
    if df.empty:
        return pd.DataFrame(
            columns=REQUIRED_COLUMNS
            + ["source", "embedding_model", "embedding_dimensions", "embedding_vector"]
        )
    return add_scores(df)


def tokenize(text: str) -> set[str]:
    tokens = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
    return {token for token in tokens if token and token not in STOPWORDS}


def normalize_rule_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    without_accents = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    ).replace("đ", "d")
    return " ".join(re.findall(r"\w+", without_accents, flags=re.UNICODE))


def is_out_of_scope_query(query: str) -> bool:
    normalized_query = normalize_rule_text(query)
    return any(pattern in normalized_query for pattern in OUT_OF_SCOPE_PATTERNS)


def scope_tokens(text: str) -> set[str]:
    normalized_text = normalize_rule_text(text)
    return {
        token
        for token in re.findall(r"\w+", normalized_text, flags=re.UNICODE)
        if token and token not in SCOPE_STOPWORDS
    }


def query_has_domain_signal(query: str, df: pd.DataFrame) -> bool:
    normalized_query = normalize_rule_text(query)
    if any(pattern in normalized_query for pattern in GENERIC_DISCOVERY_PATTERNS):
        return True

    query_terms = scope_tokens(query)
    if not query_terms or df.empty:
        return False

    corpus_terms: set[str] = set()
    strong_domain_terms: set[str] = set()
    searchable_columns = ["title", "topic", "content", "mock_summary", "mock_tags"]
    for column in searchable_columns:
        if column not in df.columns:
            continue
        column_terms = scope_tokens(" ".join(df[column].fillna("").astype(str)))
        corpus_terms.update(column_terms)
        if column in {"title", "topic", "mock_tags"}:
            strong_domain_terms.update(column_terms)
    matched_terms = query_terms & corpus_terms
    meaningful_matches = {
        term
        for term in matched_terms
        if len(term) >= 3 or term in SHORT_DOMAIN_TERMS
    }
    return bool(meaningful_matches & strong_domain_terms) or len(meaningful_matches) >= 2


def detect_quality_ranking_intent(query: str) -> str | None:
    normalized_query = normalize_rule_text(query)
    if any(pattern in normalized_query for pattern in QUALITY_LOW_PATTERNS):
        return "lowest"
    if any(pattern in normalized_query for pattern in QUALITY_HIGH_PATTERNS):
        return "highest"
    return None


def requested_ranking_limit(query: str) -> int:
    normalized_query = normalize_rule_text(query)
    match = re.search(r"\btop\s*(\d+)\b", normalized_query)
    if match is None:
        match = re.search(r"\b(\d+)\s*bai\b", normalized_query)
    return min(10, max(1, int(match.group(1)))) if match else 1


def ranking_subject_terms(query: str, df: pd.DataFrame) -> set[str]:
    query_terms = scope_tokens(query) - RANKING_QUERY_STOPWORDS
    if not query_terms or df.empty:
        return set()

    strong_terms: set[str] = set()
    for column in ["title", "topic", "mock_tags"]:
        if column in df.columns:
            strong_terms.update(scope_tokens(" ".join(df[column].fillna("").astype(str))))
    return query_terms & strong_terms


def rank_posts_by_quality(df: pd.DataFrame, query: str, intent: str) -> pd.DataFrame:
    ranked = df.copy()
    subject_terms = ranking_subject_terms(query, ranked)
    if subject_terms:
        searchable_columns = ["title", "topic", "mock_tags"]

        def matches_subject(row: pd.Series) -> bool:
            haystack = " ".join(str(row.get(column, "")) for column in searchable_columns)
            return bool(scope_tokens(haystack) & subject_terms)

        ranked = ranked[ranked.apply(matches_subject, axis=1)]

    ranked["match_score"] = ranked["quality_score"]
    return ranked.sort_values("quality_score", ascending=intent == "lowest")


def quality_ranking_answer(intent: str, rows: list[pd.Series]) -> str:
    if not rows:
        return "Mình chưa tìm thấy bài phù hợp với yêu cầu xếp hạng này."

    direction = "cao nhất" if intent == "highest" else "thấp nhất"
    if len(rows) == 1:
        row = rows[0]
        return (
            f'Bài có điểm chất lượng {direction} là "{row["title"]}" '
            f'với {float(row["quality_score"]):.1f}/100.'
        )
    return f"Đây là {len(rows)} bài có điểm chất lượng {direction}, đã được sắp xếp theo điểm."


def search_posts(df: pd.DataFrame, query: str) -> pd.DataFrame:
    ranked = df.copy()
    if ranked.empty:
        ranked["match_score"] = []
        ranked["lexical_score"] = []
        ranked["semantic_score"] = []
        return ranked

    if not query.strip():
        ranked["match_score"] = ranked["quality_score"] * 0.35
        ranked["lexical_score"] = 0.0
        ranked["semantic_score"] = 0.0
        return ranked.sort_values("match_score", ascending=False)

    query_terms = tokenize(query)
    if not query_terms:
        ranked["match_score"] = ranked["quality_score"] * 0.35
        ranked["lexical_score"] = 0.0
        ranked["semantic_score"] = 0.0
        return ranked.sort_values("match_score", ascending=False)

    query_vector = embed_text(query)

    def row_scores(row: pd.Series) -> pd.Series:
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
        coverage = overlap / max(1, len(query_terms))

        strong_haystack = " ".join(
            [
                str(row["title"]),
                str(row["topic"]),
                str(row["mock_tags"]),
            ]
        )
        strong_terms = tokenize(strong_haystack)
        strong_coverage = len(query_terms & strong_terms) / max(1, len(query_terms))
        phrase_bonus = 10.0 if query.lower().strip() in haystack.lower() else 0.0
        lexical_score = min(
            100.0,
            coverage * 65.0 + strong_coverage * 25.0 + phrase_bonus,
        )

        stored_vector = row.get("embedding_vector")
        stored_model = str(row.get("embedding_model") or "")
        if stored_model == EMBEDDING_MODEL and isinstance(
            stored_vector,
            (bytes, bytearray, memoryview),
        ):
            post_vector = deserialize_vector(stored_vector)
        else:
            post_vector = embed_post(row)
        semantic_score = max(0.0, cosine_similarity(query_vector, post_vector)) * 100.0

        match_score = (
            semantic_score * HYBRID_SEMANTIC_WEIGHT
            + lexical_score * HYBRID_LEXICAL_WEIGHT
            + float(row["quality_score"]) * HYBRID_QUALITY_WEIGHT
        )
        return pd.Series(
            {
                "lexical_score": round(lexical_score, 2),
                "semantic_score": round(semantic_score, 2),
                "match_score": round(match_score, 2),
            }
        )

    score_columns = ranked.apply(row_scores, axis=1)
    ranked[["lexical_score", "semantic_score", "match_score"]] = score_columns
    ranked = ranked[
        (ranked["lexical_score"] > 0)
        | (ranked["semantic_score"] >= MIN_SEMANTIC_EVIDENCE)
    ]
    return ranked.sort_values("match_score", ascending=False)


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


def build_context_posts(rows: list[pd.Series]) -> list[dict[str, Any]]:
    context_posts = []
    for row in rows:
        context_posts.append(
            {
                "post_id": str(row["post_id"]),
                "title": str(row["title"]),
                "topic": str(row["topic"]),
                "content": str(row["content"])[:1600],
                "summary": str(row["mock_summary"]),
                "tags": [tag.strip() for tag in str(row["mock_tags"]).split(";") if tag.strip()],
                "quality_score": float(row["quality_score"]),
                "match_score": float(row.get("match_score", 0)),
            }
        )
    return context_posts


def extract_json_object(raw_text: str) -> dict[str, Any]:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(raw_text[start : end + 1])


def build_rag_prompt(query: str, context_posts: list[dict[str, Any]]) -> str:
    return f"""
Ban la tro ly hoi dap cho hoc vien AI. Chi tra loi dua tren CONTEXT bai viet duoc cung cap.
Neu context khong du de ket luan, hay noi ro phan nao chua chac, khong bia them.

USER_QUERY:
{query}

CONTEXT_POSTS_JSON:
{json.dumps(context_posts, ensure_ascii=False)}

Hay tra ve DUY NHAT mot JSON object hop le theo schema:
{{
  "answer": "Cau tra loi tong hop tu nhien, thong minh, bang tieng Viet, dua tren cac bai viet lien quan.",
  "reasons": {{
    "post_id_1": "Ly do nen doc cu the: neu dung diem cham giua cau hoi va noi dung bai viet.",
    "post_id_2": "..."
  }}
}}

Yeu cau:
- answer phai tra loi truc tiep cau hoi user, khong chi liet ke bai viet.
- moi reason phai cu the theo tung bai, tranh cau chung chung.
- giu reason ngan gon 1-2 cau.
"""


def call_gemini_rag(query: str, context_posts: list[dict[str, Any]]) -> dict[str, Any]:
    api_key = get_config_value("GEMINI_API_KEY") or get_config_value("GOOGLE_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise RuntimeError("Gemini API key is not configured")

    model = get_config_value("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    prompt = build_rag_prompt(query, context_posts)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    candidates = data.get("candidates", [])
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    if not parts or "text" not in parts[0]:
        raise RuntimeError("Gemini response is empty")
    return extract_json_object(parts[0]["text"])


def call_openai_rag(query: str, context_posts: list[dict[str, Any]]) -> dict[str, Any]:
    api_key = get_config_value("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        raise RuntimeError("OpenAI API key is not configured")

    model = get_config_value("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    prompt = build_rag_prompt(query, context_posts)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a Vietnamese RAG assistant. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.25,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    choices = data.get("choices", [])
    content = choices[0].get("message", {}).get("content", "") if choices else ""
    if not content:
        raise RuntimeError("OpenAI response is empty")
    return extract_json_object(content)


def fallback_reason(query: str, row: pd.Series) -> str:
    haystack = " ".join(
        [
            str(row["title"]),
            str(row["topic"]),
            str(row["content"]),
            str(row["mock_summary"]),
            str(row["mock_tags"]),
        ]
    )
    matched_terms = sorted(tokenize(query) & tokenize(haystack))
    matched_text = ", ".join(matched_terms[:5]) if matched_terms else str(row["topic"])
    return (
        f"Bai nay nen doc vi khop voi truy van qua cac y: {matched_text}. "
        f"No co diem match {float(row.get('match_score', 0)):.1f} va diem chat luong "
        f"{float(row['quality_score']):.1f}/100, phu hop de uu tien xem truoc."
    )


def fallback_answer(query: str, rows: list[pd.Series]) -> str:
    if not rows:
        return "Mình chưa tìm thấy bài phù hợp với câu hỏi này trong kho dữ liệu."
    topics = ", ".join(dict.fromkeys(str(row["topic"]) for row in rows[:3]))
    return (
        f"Minh tim thay {len(rows)} bai lien quan nhat cho cau hoi '{query}'. "
        f"Cac bai noi bat tap trung vao: {topics}. Hay doc theo thu tu ben duoi vi danh sach da duoc sap xep theo diem match giam dan. "
        f"{QUALITY_DISCLAIMER}"
    )


def generate_rag_response(query: str, rows: list[pd.Series]) -> dict[str, Any]:
    if not rows:
        return {"answer": fallback_answer(query, rows), "reasons": {}}

    fallback = {
        "answer": fallback_answer(query, rows),
        "reasons": {str(row["post_id"]): fallback_reason(query, row) for row in rows},
    }
    if not get_bool_config("RAG_ENABLED", DEFAULT_RAG_ENABLED):
        return fallback

    includes_discord_data = any(str(row.get("source", "mock")).lower() == "discord" for row in rows)
    if includes_discord_data and not get_bool_config(
        "RAG_INCLUDE_DISCORD_DATA",
        DEFAULT_RAG_INCLUDE_DISCORD_DATA,
    ):
        print("[RAG] Skipped external LLM because Discord data sharing is disabled")
        return fallback

    provider_name = str(get_config_value("RAG_PROVIDER", DEFAULT_RAG_PROVIDER) or DEFAULT_RAG_PROVIDER).lower()
    providers = {
        "gemini": call_gemini_rag,
        "openai": call_openai_rag,
    }
    provider = providers.get(provider_name)
    if provider is None:
        print(f"[RAG] Unsupported provider: {provider_name}")
        return fallback

    context_posts = build_context_posts(rows)
    try:
        response = provider(query, context_posts)
        answer = str(response.get("answer", "")).strip()
        reasons = response.get("reasons", {})
        if answer and isinstance(reasons, dict):
            return {"answer": answer, "reasons": {str(key): str(value) for key, value in reasons.items()}}
    except Exception as exc:
        print(f"[RAG] {provider_name} failed: {exc}")

    return fallback


def topic_key(value: str) -> str:
    return normalize_rule_text(str(value).strip())


def topic_display_name(value: str) -> str:
    clean_value = str(value).strip()
    key = topic_key(clean_value)
    known_labels = {
        "ai": "AI",
        "ai safety": "AI Safety",
        "api": "API",
        "css": "CSS",
        "hax": "HAX",
        "llm": "LLM",
        "nlp": "NLP",
        "rag": "RAG",
        "ui": "UI",
        "ux": "UX",
    }
    return known_labels.get(key, clean_value.title())


def row_topic_keys(row: pd.Series) -> set[str]:
    raw_topics = [str(row.get("topic", ""))]
    raw_topics.extend(str(row.get("mock_tags", "")).split(";"))
    return {topic_key(value) for value in raw_topics if topic_key(value)}


def filter_posts_by_topic(df: pd.DataFrame, topic: str) -> pd.DataFrame:
    expected_key = topic_key(topic)
    if not expected_key or df.empty:
        return df.iloc[0:0].copy()
    matches = df.apply(lambda row: expected_key in row_topic_keys(row), axis=1)
    return df[matches].copy()


def post_to_result(row: pd.Series, reason: str | None = None) -> dict[str, Any]:
    tags = [tag.strip() for tag in str(row["mock_tags"]).split(";") if tag.strip()]
    quality_reason = reason or fallback_reason("", row)
    return {
        "post_id": row["post_id"],
        "title": row["title"],
        "author": row["author"],
        "topic": row["topic"],
        "summary": row["mock_summary"],
        "reason": quality_reason,
        "quality_reason": quality_reason,
        "quality_score": float(row["quality_score"]),
        "match_score": float(row.get("match_score", 0)),
        "lexical_score": float(row.get("lexical_score", 0)),
        "semantic_score": float(row.get("semantic_score", 0)),
        "url": row["url"],
        "source": row.get("source", "mock"),
        "tags": tags,
        "score_detail": score_detail(row),
    }


def build_chat_response(
    query: str,
    df: pd.DataFrame,
    top_k: int | None = None,
    exact_topic: str | None = None,
) -> dict[str, Any]:
    ranking_intent = detect_quality_ranking_intent(query)
    if is_out_of_scope_query(query):
        return {
            "answer": (
                "Câu hỏi này nằm ngoài phạm vi tìm kiếm bài viết kỹ thuật của Quality Hub. "
                "Với thông tin như thời tiết hoặc logistics, hãy kiểm tra kênh hoặc "
                "thông báo chính thức để có dữ liệu chính xác."
            ),
            "results": [],
            "mode": "out_of_scope",
        }

    if not exact_topic and not ranking_intent and not query_has_domain_signal(query, df):
        return {"answer": fallback_answer(query, []), "results": [], "mode": "no_results"}

    if exact_topic:
        ranked = filter_posts_by_topic(df, exact_topic)
        ranked["match_score"] = ranked["quality_score"]
        ranked = ranked.sort_values(
            "quality_score",
            ascending=ranking_intent == "lowest",
        )
    elif ranking_intent:
        ranked = rank_posts_by_quality(df, query, ranking_intent)
    else:
        ranked = search_posts(df, query)

    if top_k is not None:
        requested_limit = top_k
    elif ranking_intent:
        requested_limit = requested_ranking_limit(query)
    else:
        requested_limit = get_top_k_results()
    result_limit = min(10, max(1, requested_limit))
    top_rows = [row for _, row in ranked.head(result_limit).iterrows()]
    if ranking_intent:
        rag_response = {
            "answer": quality_ranking_answer(ranking_intent, top_rows),
            "reasons": {
                str(row["post_id"]): fallback_reason(query, row)
                for row in top_rows
            },
        }
    else:
        rag_response = generate_rag_response(query, top_rows)
    reasons = rag_response.get("reasons", {})
    results = [
        post_to_result(row, str(reasons.get(str(row["post_id"])) or fallback_reason(query, row)))
        for row in top_rows
    ]
    answer = str(rag_response.get("answer") or fallback_answer(query, top_rows))
    if results and QUALITY_DISCLAIMER not in answer:
        answer = f"{answer} {QUALITY_DISCLAIMER}"
    mode = f"quality_{ranking_intent}" if ranking_intent else ("topic" if exact_topic else "search")
    return {"answer": answer, "results": results, "mode": mode}


def build_content_overview(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"top_posts": [], "hot_topics": []}

    recent_overview = df.copy()
    created_at = pd.to_datetime(
        recent_overview["created_at"],
        errors="coerce",
        utc=True,
        format="mixed",
    )
    if created_at.notna().any():
        recent_cutoff = created_at.max() - pd.Timedelta(days=6)
        recent_posts = recent_overview[created_at >= recent_cutoff]
        if not recent_posts.empty:
            recent_overview = recent_posts

    top_posts = [
        post_to_result(row)
        for _, row in recent_overview.sort_values("quality_score", ascending=False).head(5).iterrows()
    ]

    topic_post_ids: dict[str, set[str]] = {}
    topic_labels: dict[str, str] = {}
    for _, row in df.iterrows():
        post_id = str(row["post_id"])
        raw_topics = [str(row["topic"])]
        raw_topics.extend(str(row["mock_tags"]).split(";"))
        for raw_topic in raw_topics:
            key = topic_key(raw_topic)
            if not key:
                continue
            topic_labels.setdefault(key, topic_display_name(raw_topic))
            topic_post_ids.setdefault(key, set()).add(post_id)

    hot_topics = [
        {"name": topic_labels[key], "count": len(post_ids)}
        for key, post_ids in sorted(
            topic_post_ids.items(),
            key=lambda item: -len(item[1]),
        )[:15]
    ]
    return {"top_posts": top_posts, "hot_topics": hot_topics}


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    ensure_database_ready()
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/status")
def status() -> dict[str, Any]:
    df = load_posts()
    storage_stats = sqlite_storage.database_stats()
    return {
        "post_count": len(df),
        "discord_configured": has_discord_config(),
        "last_sync_at": last_sync_at,
        "last_sync_message": last_sync_message,
        "storage": "sqlite",
        "embedding_model": storage_stats["embedding_model"],
        "embedding_count": storage_stats["embedding_count"],
        "sources": storage_stats["sources"],
        "background_sync": True,
    }


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    return build_content_overview(load_posts())


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict[str, Any]:
    df = load_posts()
    return build_chat_response(
        payload.query,
        df,
        top_k=payload.top_k,
        exact_topic=payload.topic,
    )
