from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DATA_PATH = APP_DIR / "mock_posts.csv"
ENV_PATH = APP_DIR / ".env"
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"

WEIGHTS = {
    "click_score": 0.20,
    "like_score": 0.15,
    "heart_score": 0.20,
    "watch_time_score": 0.25,
    "completion_score": 0.10,
    "save_share_score": 0.10,
}

METRIC_LABELS = {
    "click_score": "Click",
    "like_score": "Like",
    "heart_score": "Tim",
    "watch_time_score": "Thoi luong xem",
    "completion_score": "Ty le xem het",
    "save_share_score": "Luu/Chia se",
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
    df = pd.read_csv(DATA_PATH)
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


def normalize(series: pd.Series) -> pd.Series:
    min_value = series.min()
    max_value = series.max()
    if min_value == max_value:
        return pd.Series([100.0] * len(series), index=series.index)
    return ((series - min_value) / (max_value - min_value) * 100).round(1)


def add_scores(df: pd.DataFrame) -> pd.DataFrame:
    scored = df.copy()
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
    normalized = re.sub(r"[^a-zA-Z0-9_]+", " ", text.lower())
    stopwords = {
        "tim",
        "bai",
        "hay",
        "ve",
        "va",
        "cho",
        "cach",
        "cac",
        "nhung",
        "mot",
        "co",
        "la",
    }
    return {token for token in normalized.split() if token and token not in stopwords}


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
        "quality_reason": "Mock output: can goi AI that de tao ly do chat luong theo noi dung.",
    }


def add_ai_status_columns(df: pd.DataFrame) -> pd.DataFrame:
    view = df.copy()
    view["ai_status"] = view["post_id"].apply(lambda post_id: "AI ready" if get_ai_metadata(str(post_id)) else "Mock")
    view["ai_topic"] = view.apply(lambda row: get_display_metadata(row)["topic"], axis=1)
    view["ai_summary"] = view.apply(lambda row: get_display_metadata(row)["summary"], axis=1)
    return view


def build_ai_export(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        metadata = get_ai_metadata(str(row["post_id"]))
        if not metadata:
            continue
        rows.append(
            {
                "post_id": row["post_id"],
                "title": row["title"],
                "quality_score": row["quality_score"],
                "ai_topic": metadata["topic"],
                "ai_tags": ";".join(metadata["tags"]),
                "ai_summary": metadata["summary"],
                "ai_quality_reason": metadata["quality_reason"],
                "url": row["url"],
            }
        )
    return pd.DataFrame(rows)


def render_batch_ai_controls(df: pd.DataFrame, has_gemini_key: bool, title: bool = True) -> None:
    analyzed_count = sum(1 for post_id in df["post_id"] if get_ai_metadata(str(post_id)))
    if title:
        st.subheader("Batch AI processing")
        st.caption("Goi Gemini lan luot de tao summary, topic, tags va quality reason cho cac bai dang dang hien thi.")

    metric_col, button_col, clear_col = st.columns([0.28, 0.42, 0.30])
    metric_col.metric("Da co AI output", f"{analyzed_count}/{len(df)}")

    analyze_clicked = button_col.button(
        "Analyze visible posts",
        disabled=not has_gemini_key or df.empty,
        use_container_width=True,
    )
    clear_clicked = clear_col.button(
        "Clear AI outputs",
        disabled=analyzed_count == 0,
        use_container_width=True,
    )

    if clear_clicked:
        for post_id in df["post_id"]:
            st.session_state.pop(ai_cache_key(str(post_id)), None)
        st.rerun()

    if analyze_clicked:
        progress = st.progress(0)
        status = st.empty()
        errors = []
        rows = list(df.iterrows())

        for index, (_, row) in enumerate(rows, start=1):
            post_id = str(row["post_id"])
            if get_ai_metadata(post_id):
                progress.progress(index / len(rows))
                continue

            status.write(f"Dang phan tich {post_id}: {row['title']}")
            try:
                st.session_state[ai_cache_key(post_id)] = generate_ai_metadata(str(row["title"]), str(row["content"]))
            except Exception as exc:
                errors.append(f"{post_id}: {exc}")
                break
            progress.progress(index / len(rows))

        if errors:
            st.error("Dung batch vi co loi: " + errors[0])
        else:
            st.success("Da phan tich xong cac bai dang dang hien thi.")
        status.empty()
        st.rerun()


def get_ranked_posts_for_query(df: pd.DataFrame, query: str, limit: int = 3) -> pd.DataFrame:
    if not query.strip():
        return df.sort_values("quality_score", ascending=False).head(limit)
    candidates = search_posts(df, query)
    if candidates.empty:
        return candidates
    return candidates.sort_values(["quality_score", "match_score"], ascending=False).head(limit)


def render_post_result(row: pd.Series, rank: int) -> None:
    metadata = get_display_metadata(row)
    tags = " ".join(f"`{tag}`" for tag in metadata["tags"])
    st.markdown(f"**{rank}. {row['title']}**")
    st.caption(f"{row['post_id']} | {metadata['topic']} | Diem chat luong: {row['quality_score']:.1f}/100")
    st.write(metadata["summary"])
    st.write(f"Ly do nen doc: {metadata['quality_reason']}")
    if tags:
        st.markdown(tags)
    st.markdown(f"[Mo bai goc]({row['url']})")


def render_chatbot_tab(df: pd.DataFrame) -> None:
    st.subheader("Chatbot tim bai dang chat luong")
    st.caption("Hoi mot chu de, bot se tra top 3 bai lien quan co diem chat luong cao nhat.")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [
            {
                "role": "assistant",
                "content": "Ban muon tim bai dang chat luong ve chu de gi?",
                "results": None,
            }
        ]

    prompt_col_1, prompt_col_2, prompt_col_3 = st.columns(3)
    example_query = None
    if prompt_col_1.button("RAG va prompt", use_container_width=True):
        example_query = "tim bai hay ve RAG va prompt"
    if prompt_col_2.button("eval chatbot", use_container_width=True):
        example_query = "bai viet ve golden set va danh gia chatbot"
    if prompt_col_3.button("UX khi AI khong chac", use_container_width=True):
        example_query = "thiet ke UX khi AI khong chac"

    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("results") is not None:
                if message["results"].empty:
                    st.info("Chua tim thay bai phu hop. Thu hoi bang tu khoa khac.")
                else:
                    for rank, (_, row) in enumerate(message["results"].iterrows(), start=1):
                        render_post_result(row, rank)
                        if rank < len(message["results"]):
                            st.divider()

    user_query = st.chat_input("Nhap chu de ban muon tim...")
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
        answer = "Minh tim thay top 3 bai phu hop nhat, sap xep uu tien theo diem chat luong."
        if results.empty:
            answer = "Minh chua tim thay bai phu hop voi cau hoi nay."
        st.session_state.chat_messages.append(
            {
                "role": "assistant",
                "content": answer,
                "results": results,
            }
        )
        st.rerun()


def render_knowledge_base_tab(df: pd.DataFrame) -> pd.DataFrame:
    st.subheader("Knowledge base")
    query = st.text_input("Tim kiem trong bang", placeholder="tim bai hay ve RAG va prompt")
    topics = ["Tat ca"] + sorted(df["topic"].unique().tolist())
    selected_topic = st.selectbox("Chu de", topics)
    min_score = st.slider("Diem toi thieu", 0, 100, 0, step=5)
    sort_by = st.selectbox("Sap xep", ["Diem chat luong", "Moi nhat", "Nhieu luu/chia se"])

    filtered = search_posts(df, query)
    if selected_topic != "Tat ca":
        filtered = filtered[filtered["topic"] == selected_topic]
    filtered = filtered[filtered["quality_score"] >= min_score]

    sort_map = {
        "Diem chat luong": "quality_score",
        "Moi nhat": "created_at",
        "Nhieu luu/chia se": "save_shares",
    }
    filtered = filtered.sort_values(sort_map[sort_by], ascending=False)
    filtered = add_ai_status_columns(filtered)

    top_col, avg_col, count_col, topic_col = st.columns(4)
    top_col.metric("Bai noi bat", f"{df['quality_score'].max():.1f}")
    avg_col.metric("Diem trung binh", f"{df['quality_score'].mean():.1f}")
    count_col.metric("Bai dang", len(filtered))
    topic_col.metric("Chu de", selected_topic)

    table_cols = [
        "post_id",
        "title",
        "ai_status",
        "ai_topic",
        "quality_score",
        "quality_tier",
        "clicks",
        "likes",
        "hearts",
        "watch_time_sec",
        "completion_percent",
        "save_shares",
    ]
    st.dataframe(
        filtered[table_cols],
        hide_index=True,
        use_container_width=True,
        column_config={
            "quality_score": st.column_config.ProgressColumn("Diem", min_value=0, max_value=100),
            "completion_percent": st.column_config.NumberColumn("Ty le xem het", format="%.0f%%"),
            "watch_time_sec": st.column_config.NumberColumn("Thoi luong xem (s)"),
        },
    )

    if filtered.empty:
        st.info("Khong co bai phu hop bo loc hien tai.")
        return filtered

    selected_post = st.selectbox(
        "Chon bai de xem chi tiet",
        filtered["post_id"].tolist(),
        format_func=lambda post_id: f"{post_id} - {filtered.loc[filtered['post_id'] == post_id, 'title'].iloc[0]}",
    )
    row = filtered[filtered["post_id"] == selected_post].iloc[0]
    render_detail(row)
    return filtered


def render_admin_tab(df: pd.DataFrame, has_gemini_key: bool) -> None:
    st.subheader("Admin / AI processing")
    st.caption("Phan nay dung de chuan bi tri thuc cho chatbot, khong phai flow chinh cua nguoi dung.")

    render_batch_ai_controls(add_ai_status_columns(df), has_gemini_key, title=False)

    ai_export = build_ai_export(df)
    if not ai_export.empty:
        st.download_button(
            "Download AI results CSV",
            ai_export.to_csv(index=False).encode("utf-8"),
            file_name="ai_post_analysis.csv",
            mime="text/csv",
        )
    else:
        st.info("Chua co output AI that de tai xuong. Hay bam Analyze visible posts truoc.")

    st.subheader("Scoring formula")
    st.code(
        "Click 20% + Like 15% + Tim 20% + Thoi luong xem 25% + Ty le xem het 10% + Luu/Chia se 10%",
        language="text",
    )
    st.write("Moi tin hieu duoc chuan hoa ve thang 0-100 truoc khi tinh diem tong.")


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
        .score-note {
            border-left: 4px solid #2563eb;
            background: #eff6ff;
            padding: .75rem 1rem;
            border-radius: 6px;
            color: #1e3a8a;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_score_breakdown(row: pd.Series) -> None:
    breakdown = pd.DataFrame(
        {
            "Tin hieu": [METRIC_LABELS[column] for column in WEIGHTS],
            "Diem 0-100": [float(row[column]) for column in WEIGHTS],
            "Trong so": [f"{int(weight * 100)}%" for weight in WEIGHTS.values()],
            "Dong gop": [round(float(row[column]) * weight, 1) for column, weight in WEIGHTS.items()],
        }
    )
    st.dataframe(breakdown, hide_index=True, use_container_width=True)


def render_detail(row: pd.Series) -> None:
    cache_key = ai_cache_key(str(row["post_id"]))
    ai_metadata = st.session_state.get(cache_key)
    display_metadata = get_display_metadata(row)

    st.markdown(f"<div class='post-title'>{row['title']}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='muted'>{row['post_id']} | {row['author']} | {display_metadata['topic']} | {row['created_at']}</div>",
        unsafe_allow_html=True,
    )
    tags_html = "".join(f"<span class='pill'>{tag}</span>" for tag in display_metadata["tags"])
    st.markdown(tags_html, unsafe_allow_html=True)

    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("Noi dung bai viet")
        st.write(row["content"])

        button_col, status_col = st.columns([0.45, 0.55])
        with button_col:
            generate_clicked = st.button("Generate AI summary/tag", key=f"generate_{row['post_id']}")
        with status_col:
            if ai_metadata:
                st.success("AI output da tao")
            else:
                st.caption("Chua goi AI that, dang hien mock output.")

        if generate_clicked:
            try:
                with st.spinner("Dang goi Gemini..."):
                    ai_metadata = generate_ai_metadata(str(row["title"]), str(row["content"]))
                    st.session_state[cache_key] = ai_metadata
            except Exception as exc:
                st.error(f"Khong goi duoc Gemini: {exc}")

        if ai_metadata:
            st.subheader("AI summary")
            st.write(display_metadata["summary"])
            st.subheader("AI quality reason")
            st.write(display_metadata["quality_reason"])
        else:
            st.subheader("Mock AI summary")
            st.write(display_metadata["summary"])

        st.link_button("Mo bai goc", row["url"])
    with right:
        st.subheader("Diem chat luong")
        score_col, tier_col = st.columns(2)
        score_col.metric("Quality score", f"{row['quality_score']:.1f}/100")
        tier_col.metric("Xep hang", str(row["quality_tier"]))
        render_score_breakdown(row)


def main() -> None:
    inject_css()
    df = load_posts()

    st.title("Tro ly tong hop bai dang chat luong")
    st.caption("Chatbot tim top 3 bai dang lien quan co diem chat luong cao nhat.")

    st.markdown(
        """
        <div class="score-note">
        Cong thuc: Click 20% + Like 15% + Tim 20% + Thoi luong xem 25% + Ty le xem het 10% + Luu/Chia se 10%.
        Moi tin hieu duoc chuan hoa ve thang 0-100 truoc khi tinh diem.
        </div>
        """,
        unsafe_allow_html=True,
    )

    has_gemini_key = bool(get_config_value("GEMINI_API_KEY"))
    st.sidebar.caption(f"Gemini API: {'ready' if has_gemini_key else 'missing key'}")

    chat_tab, kb_tab, admin_tab = st.tabs(["Chatbot", "Knowledge base", "Admin"])
    with chat_tab:
        render_chatbot_tab(df)
    with kb_tab:
        render_knowledge_base_tab(df)
    with admin_tab:
        render_admin_tab(df, has_gemini_key)


if __name__ == "__main__":
    main()
