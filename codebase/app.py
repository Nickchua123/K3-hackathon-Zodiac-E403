from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DATA_PATH = APP_DIR / "mock_posts.csv"
DISCORD_DATA_PATH = APP_DIR / "discord_posts.csv"
ENV_PATH = APP_DIR / ".env"
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"
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

st.set_page_config(
    page_title="Discord Quality Digest",
    page_icon="DQ",
    layout="wide",
)


def ai_cache_key(post_id: str) -> str:
    return f"ai_metadata_{post_id}"


@st.cache_data
def load_posts() -> pd.DataFrame:
    frames = []
    errors = []
    for path, source in [(DATA_PATH, "mock"), (DISCORD_DATA_PATH, "discord")]:
        if not path.exists():
            continue
        try:
            frame = pd.read_csv(path, encoding="utf-8-sig")
        except Exception as exc:
            errors.append(f"{path.name}: không đọc được CSV ({exc})")
            continue

        missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
        if missing:
            errors.append(f"{path.name}: thiếu cột {', '.join(missing)}")
            continue

        frame = frame[REQUIRED_COLUMNS].copy()
        frame["source"] = source
        frames.append(frame)

    if errors:
        st.error("Lỗi dữ liệu: " + " | ".join(errors))

    if not frames:
        return pd.DataFrame(columns=REQUIRED_COLUMNS + ["source"])

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["post_id"], keep="last")
    return add_scores(df)


@st.cache_data
def load_local_env() -> dict[str, str]:
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
    try:
        secret_value = st.secrets.get(key)
    except Exception:
        secret_value = None
    return secret_value or os.getenv(key) or load_local_env().get(key) or default


def has_discord_config() -> bool:
    token = get_config_value("DISCORD_BOT_TOKEN")
    channel_id = get_config_value("DISCORD_CHANNEL_ID")
    channel_ids = get_config_value("DISCORD_CHANNEL_IDS")
    return bool(token and token != "your_discord_bot_token_here" and (channel_id or channel_ids))


def get_int_config(key: str, default: str) -> int:
    try:
        return int(get_config_value(key, default) or default)
    except ValueError:
        return int(default)


def auto_sync_discord() -> None:
    if not has_discord_config():
        return

    sync_interval = max(
        30,
        get_int_config("DISCORD_SYNC_INTERVAL_SECONDS", DEFAULT_DISCORD_SYNC_INTERVAL_SECONDS),
    )
    last_sync_at = float(st.session_state.get("discord_last_sync_at", 0))
    now = time.time()
    if now - last_sync_at < sync_interval:
        return

    st.session_state.discord_last_sync_at = now
    sync_limit = get_int_config("DISCORD_SYNC_LIMIT", DEFAULT_DISCORD_SYNC_LIMIT)

    try:
        from discord_bot import sync_discord_posts_to_csv

        with st.spinner("Đang đồng bộ dữ liệu Discord..."):
            synced_posts = sync_discord_posts_to_csv(limit=sync_limit)
        load_posts.clear()
        if synced_posts:
            st.toast(f"Đã đồng bộ {len(synced_posts)} bài từ Discord.")
    except Exception as exc:
        st.warning(f"Không đồng bộ được Discord: {exc}")


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
    scored["quality_tier"] = pd.cut(
        scored["quality_score"],
        bins=[-1, 50, 70, 85, 101],
        labels=["Can xem lai", "Kha", "Tot", "Noi bat"],
    )
    return scored.sort_values("quality_score", ascending=False).reset_index(drop=True)


def tokenize(text: str) -> set[str]:
    normalized = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
    stopwords = {
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
    return {token for token in normalized if token and token not in stopwords}


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


def parse_json_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


def generate_ai_metadata(title: str, content: str) -> dict:
    api_key = get_config_value("GEMINI_API_KEY")
    model_name = get_config_value("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in .env or .streamlit/secrets.toml")

    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise RuntimeError("Missing dependency: run `pip install -r requirements.txt`") from exc

    prompt = f"""
You are analyzing a Vietnamese Discord learning post for a hackathon prototype.
Return only valid JSON with these keys:
- summary: one concise Vietnamese sentence.
- topic: one topic label, 1-4 words.
- tags: 3-5 short tags.
- quality_reason: one concise Vietnamese sentence explaining why this post is useful or not.

Title: {title}
Content: {content}
"""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    text = getattr(response, "text", "") or ""
    data = parse_json_response(text)

    tags = data.get("tags", [])
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

    return {
        "summary": str(data.get("summary", "")).strip(),
        "topic": str(data.get("topic", "")).strip(),
        "tags": tags[:5],
        "quality_reason": str(data.get("quality_reason", "")).strip(),
    }


def get_ai_metadata(post_id: str) -> dict | None:
    return st.session_state.get(ai_cache_key(post_id))


def get_display_metadata(row: pd.Series) -> dict:
    metadata = get_ai_metadata(str(row["post_id"]))
    if metadata:
        return metadata

    return {
        "summary": str(row["mock_summary"]),
        "topic": str(row["topic"]),
        "tags": [tag.strip() for tag in str(row["mock_tags"]).split(";") if tag.strip()],
        "quality_reason": "Đây là bản tóm tắt mẫu; có thể bật AI thật để tạo lý do chất lượng theo nội dung.",
    }


def get_ranked_posts_for_query(df: pd.DataFrame, query: str, limit: int = 3) -> pd.DataFrame:
    if not query.strip():
        return df.sort_values("quality_score", ascending=False).head(limit)
    candidates = search_posts(df, query)
    if candidates.empty:
        return candidates
    return candidates.sort_values(["quality_score", "match_score"], ascending=False).head(limit)


def render_score_detail(row: pd.Series) -> None:
    rows = []
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
        rows.append(
            {
                "Tín hiệu": label,
                "Dữ liệu gốc": raw_display,
                "Điểm 0-100": round(score, 1),
                "Trọng số": f"{int(weight * 100)}%",
                "Đóng góp": round(score * weight, 1),
                "Ý nghĩa": description,
            }
        )

    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption(
        "Công thức: Click 20% + Like 15% + Tim 20% + Thời lượng xem 25% + "
        "Tỷ lệ xem hết 10% + Lưu/Chia sẻ 10%."
    )


def render_post_result(row: pd.Series, rank: int) -> None:
    metadata = get_display_metadata(row)
    tags = " ".join(f"`{tag}`" for tag in metadata["tags"])
    st.markdown(f"**{rank}. {row['title']}**")
    st.caption(f"{row['post_id']} | {metadata['topic']} | Điểm chất lượng: {row['quality_score']:.1f}/100")
    st.write(metadata["summary"])
    st.write(f"Lý do nên đọc: {metadata['quality_reason']}")
    if tags:
        st.markdown(tags)
    st.markdown(f"[Mở bài gốc]({row['url']})")
    with st.expander("Xem chi tiết chấm điểm"):
        render_score_detail(row)


def render_chatbot_tab(df: pd.DataFrame) -> None:
    st.subheader("Chatbot tìm bài đăng chất lượng")
    st.caption("Hỏi một chủ đề, bot sẽ trả top 3 bài liên quan có điểm chất lượng cao nhất.")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [
            {
                "role": "assistant",
                "content": "Bạn muốn tìm bài đăng chất lượng về chủ đề gì?",
                "results": None,
            }
        ]

    prompt_col_1, prompt_col_2, prompt_col_3 = st.columns(3)
    example_query = None
    if prompt_col_1.button("RAG và prompt", use_container_width=True):
        example_query = "tìm bài hay về RAG và prompt"
    if prompt_col_2.button("eval chatbot", use_container_width=True):
        example_query = "bài viết về golden set và đánh giá chatbot"
    if prompt_col_3.button("UX khi AI không chắc", use_container_width=True):
        example_query = "thiết kế UX khi AI không chắc"

    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("results") is not None:
                if message["results"].empty:
                    st.info("Chưa tìm thấy bài phù hợp. Thử hỏi bằng từ khóa khác.")
                else:
                    for rank, (_, row) in enumerate(message["results"].iterrows(), start=1):
                        render_post_result(row, rank)
                        if rank < len(message["results"]):
                            st.divider()

    user_query = st.chat_input("Nhập chủ đề bạn muốn tìm...")
    if example_query and not user_query:
        user_query = example_query

    if user_query:
        st.session_state.chat_messages.append(
            {
                "role": "user",
                "content": user_query,
                "results": None,
            }
        )
        results = get_ranked_posts_for_query(df, user_query, limit=3)
        answer = "Mình tìm thấy top 3 bài phù hợp nhất, sắp xếp ưu tiên theo điểm chất lượng."
        if results.empty:
            answer = "Mình chưa tìm thấy bài phù hợp với câu hỏi này."
        st.session_state.chat_messages.append(
            {
                "role": "assistant",
                "content": answer,
                "results": results,
            }
        )
        st.rerun()


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.4rem; padding-bottom: 2rem; }
        [data-testid="stMetricValue"] { font-size: 1.45rem; }
        div[data-testid="stDataFrame"] { border: 1px solid #d8dee4; border-radius: 8px; }
        .post-title { font-size: 1.15rem; font-weight: 700; margin-bottom: .25rem; }
        .muted { color: #667085; font-size: .92rem; }
        .pill {
            display: inline-block;
            border: 1px solid #d0d5dd;
            border-radius: 999px;
            padding: .15rem .5rem;
            margin: .1rem .2rem .1rem 0;
            background: #f8fafc;
            font-size: .82rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    inject_css()
    auto_sync_discord()
    df = load_posts()

    st.title("Trợ lý tổng hợp bài đăng chất lượng")

    render_chatbot_tab(df)


if __name__ == "__main__":
    main()
