from __future__ import annotations

import re
import os
import time
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


APP_DIR = Path(__file__).resolve().parent
DATA_PATH = APP_DIR / "mock_posts.csv"
GOLDEN_SET_PATH = APP_DIR / "golden_set.csv"

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
    page_title="Trợ lý Tổng hợp bài đăng chất lượng",
    page_icon="🧭",
    layout="wide",
)


@st.cache_data
def load_posts() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    return add_scores(df)


@st.cache_data
def load_golden_set() -> pd.DataFrame:
    return pd.read_csv(GOLDEN_SET_PATH)


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


def choose_ai_budget(question: str) -> tuple[int, int]:
    """Return (number of source posts, max output tokens) for the request."""
    text = question.lower()
    if any(word in text for word in ["tổng hợp", "tong hop", "bản tin", "ban tin", "toàn bộ", "toan bo"]):
        return 10, 700
    if any(word in text for word in ["so sánh", "so sanh", "phân tích", "phan tich", "vì sao", "vi sao"]):
        return 7, 550
    if any(word in text for word in ["liệt kê", "liet ke", "danh sách", "danh sach", "bài nào", "bai nao"]):
        return 8, 450
    return 5, 350


def build_ai_context(df: pd.DataFrame, limit: int = 10, max_chars: int = 1400) -> str:
    """Create a compact, source-grounded context and avoid sending whole documents."""
    columns = ["post_id", "title", "topic", "content", "mock_summary", "mock_tags", "quality_score"]
    available = [column for column in columns if column in df.columns]
    context_df = df.head(limit)[available].copy()
    for column in ["content", "mock_summary"]:
        if column in context_df:
            context_df[column] = context_df[column].fillna("").astype(str).str.slice(0, max_chars)
    return context_df.to_json(orient="records", force_ascii=False)


def ask_quality_assistant(
    question: str,
    df: pd.DataFrame,
    history: list[dict[str, str]] | None = None,
) -> str:
    if OpenAI is None:
        return "Chua cai thu vien OpenAI. Hay chay: python -m pip install -r requirements.txt"

    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        base_url = "https://api.groq.com/openai/v1"
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = None
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key:
        variable = "GROQ_API_KEY" if provider == "groq" else "OPENAI_API_KEY"
        return f"Chưa có {variable}. Hãy nạp API key bằng biến môi trường rồi tải lại ứng dụng."

    context_limit, max_output_tokens = choose_ai_budget(question)
    context = build_ai_context(df, limit=context_limit)
    instructions = """
Bạn là Trợ lý Tổng hợp bài đăng chất lượng cho một cộng đồng học tập.
Trả lời bằng tiếng Việt có dấu, rõ ràng và ngắn gọn.
Chỉ sử dụng thông tin trong danh sách bài đăng được cung cấp. Nếu thiếu dữ liệu,
hãy nói rõ là chưa có dữ liệu thay vì bịa. Khi nhắc đến bài đăng, luôn ghi post_id và tiêu đề.
Nếu được yêu cầu tổng hợp, hãy trả về: (1) tổng quan, (2) các ý chính,
(3) bài đăng đáng chú ý, (4) việc nên làm tiếp theo.
Khi đánh giá chất lượng, giải thích dựa trên quality_score và nội dung bài.
Ưu tiên các bài có tags announcement, deadline, important, bug-report, workshop,
resource hoặc evidence khi tạo bản tin. Không ưu tiên bài chỉ có tính xã giao nếu người dùng
không hỏi. Không suy diễn người đăng, thời gian hoặc thông tin ngoài dữ liệu.
"""
    recent_history = history[-6:] if history else []
    conversation = "\n".join(f"{item['role']}: {item['content']}" for item in recent_history)
    prompt = f"""Dữ liệu các bài đăng đã được lọc (JSON):\n{context}\n\nLịch sử trò chuyện gần đây:\n{conversation}\n\nCâu hỏi mới của người dùng:\n{question}"""

    try:
        client_args = {"api_key": api_key}
        if base_url:
            client_args["base_url"] = base_url
        client = OpenAI(**client_args)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_output_tokens,
            temperature=0.2,
        )
        return response.choices[0].message.content or "Trợ lý chưa tạo được câu trả lời."
    except Exception as exc:
        return f"Không gọi được AI ({type(exc).__name__}). Kiểm tra API key, model và hạn mức."


def run_golden_set(golden_set: pd.DataFrame, posts: pd.DataFrame) -> pd.DataFrame:
    """Run the CP3 test set and provide a transparent keyword-based smoke check."""
    results = []
    for _, test in golden_set.iterrows():
        answer = ask_quality_assistant(str(test["question"]), posts)
        answer_lower = answer.lower()
        keywords = [word.strip().lower() for word in str(test["expected_keywords"]).split(";")]
        matched = [word for word in keywords if word in answer_lower]
        results.append(
            {
                "Mã test": test["test_id"],
                "Câu hỏi": test["question"],
                "Loại": test["expected_type"],
                "Kết quả AI": answer[:1200],
                "Từ khóa khớp": ", ".join(matched) or "Không có",
                "Đạt sơ bộ": "Đạt" if matched else "Cần xem lại",
            }
        )
        time.sleep(0.25)
    return pd.DataFrame(results)


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
    st.markdown(f"<div class='post-title'>{row['title']}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='muted'>{row['post_id']} | {row['author']} | {row['topic']} | {row['created_at']}</div>",
        unsafe_allow_html=True,
    )
    tags_html = "".join(f"<span class='pill'>{tag.strip()}</span>" for tag in str(row["mock_tags"]).split(";"))
    st.markdown(tags_html, unsafe_allow_html=True)

    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("Nội dung bài viết")
        st.write(row["content"])
        st.subheader("Tóm tắt AI")
        st.write(row["mock_summary"])
        st.link_button("Mở bài gốc", row["url"])
    with right:
        st.subheader("Điểm chất lượng")
        score_col, tier_col = st.columns(2)
        score_col.metric("Điểm chất lượng", f"{row['quality_score']:.1f}/100")
        tier_col.metric("Xếp hạng", str(row["quality_tier"]))
        render_score_breakdown(row)


def main() -> None:
    inject_css()
    df = load_posts()

    st.title("🧭 Trợ lý Tổng hợp bài đăng chất lượng")
    st.caption("Biến nhiều bài đăng thành bản tin ngắn, dễ đọc và có thứ tự ưu tiên.")

    # Compact chat launcher: the user can ask without leaving the digest screen.
    with st.popover("💬", help="Mở Trợ lý Tổng hợp bài đăng chất lượng"):
        st.markdown("### 💬 Hỏi Trợ lý Kute")
        st.caption("Hỏi về các bài đăng đang được lọc ở màn hình này.")
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = [
                {
                    "role": "assistant",
                    "content": "Xin chào! Tôi có thể tổng hợp bài đăng, tìm bài nổi bật và giải thích điểm chất lượng. Bạn muốn biết điều gì?",
                }
            ]
        for message in st.session_state.chat_history[-6:]:
            with st.chat_message(message["role"], avatar="🤖" if message["role"] == "assistant" else "👤"):
                st.markdown(message["content"])
        bubble_question = st.text_area(
            "Câu hỏi của bạn",
            placeholder="Ví dụ: Các deadline quan trọng hiện nay là gì?",
            key="bubble_question",
        )
        if st.button("Gửi câu hỏi", type="primary", key="bubble_send") and bubble_question.strip():
            st.session_state.chat_history.append({"role": "user", "content": bubble_question.strip()})
            with st.spinner("Trợ lý đang tổng hợp dữ liệu..."):
                answer = ask_quality_assistant(
                    bubble_question.strip(),
                    df,
                    st.session_state.chat_history,
                )
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
            st.rerun()
        if st.button("Xóa lịch sử", key="bubble_clear"):
            st.session_state.chat_history = []
            st.rerun()

    st.markdown(
        """
        <div class="score-note">
        <b>Mục tiêu:</b> phát hiện bài đăng hữu ích, giải thích vì sao bài được ưu tiên,
        rồi dùng AI để tổng hợp thành câu trả lời có dẫn nguồn bài đăng.
        <br><br><b>Công thức chất lượng:</b> Click 20% + Like 15% + Tim 20% + Thời lượng xem 25%
        + Tỷ lệ xem hết 10% + Lưu/Chia sẻ 10%.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.header("🔎 Khám phá bài đăng")
    query = st.sidebar.text_input("Tìm kiếm", placeholder="Ví dụ: RAG và prompt")
    topics = ["Tất cả"] + sorted(df["topic"].unique().tolist())
    selected_topic = st.sidebar.selectbox("Chủ đề", topics)
    min_score = st.sidebar.slider("Điểm chất lượng tối thiểu", 0, 100, 0, step=5)
    sort_by = st.sidebar.selectbox("Sắp xếp", ["Điểm chất lượng", "Mới nhất", "Nhiều lưu/chia sẻ"])

    st.sidebar.divider()
    st.sidebar.subheader("🔗 Kênh Discord nguồn")
    discord_links = {
        "📚 Tài nguyên": "https://discord.com/channels/1526532830627102781/1527920166397018164",
        "💬 Chung": "https://discord.com/channels/1526532830627102781/1527920177390293164",
        "📣 Thông báo": "https://discord.com/channels/1526532830627102781/1527920171963125953",
        "🧠 Lý thuyết": "https://discord.com/channels/1526532830627102781/1529103552297963630",
        "🏫 Thông báo khóa 3": "https://discord.com/channels/1526532830627102781/1529105265369157732",
    }
    for label, url in discord_links.items():
        st.sidebar.markdown(f"[{label}]({url})")

    golden_set = load_golden_set()
    with st.sidebar.expander("🧪 CP3 - Golden set"):
        st.write(f"{len(golden_set)} câu kiểm thử, gồm câu đúng và câu ngoài phạm vi.")
        st.caption("Chạy thủ công để tạo bảng bằng chứng AI chạy thật.")
        if st.button("Chạy toàn bộ golden set", key="run_golden_set"):
            with st.spinner(f"Đang chạy {len(golden_set)} câu kiểm thử..."):
                st.session_state.golden_results = run_golden_set(golden_set, df)
            st.rerun()

    filtered = search_posts(df, query)
    if selected_topic != "Tất cả":
        filtered = filtered[filtered["topic"] == selected_topic]
    filtered = filtered[filtered["quality_score"] >= min_score]

    sort_map = {
        "Điểm chất lượng": "quality_score",
        "Mới nhất": "created_at",
        "Nhiều lưu/chia sẻ": "save_shares",
    }
    filtered = filtered.sort_values(sort_map[sort_by], ascending=False)

    top_col, avg_col, count_col, topic_col = st.columns(4)
    top_col.metric("Bài nổi bật nhất", f"{df['quality_score'].max():.1f}/100")
    avg_col.metric("Điểm trung bình", f"{df['quality_score'].mean():.1f}/100")
    count_col.metric("Bài đang xem", len(filtered))
    topic_col.metric("Chủ đề", selected_topic)

    table_cols = [
        "post_id",
        "title",
        "topic",
        "quality_score",
        "quality_tier",
        "clicks",
        "likes",
        "hearts",
        "watch_time_sec",
        "completion_percent",
        "save_shares",
    ]
    st.subheader("📌 Danh sách bài đăng được ưu tiên")
    st.dataframe(
        filtered[table_cols],
        hide_index=True,
        use_container_width=True,
        column_config={
            "quality_score": st.column_config.ProgressColumn("Điểm", min_value=0, max_value=100),
            "completion_percent": st.column_config.NumberColumn("Tỷ lệ xem hết", format="%.0f%%"),
            "watch_time_sec": st.column_config.NumberColumn("Thời lượng xem (s)"),
        },
    )

    if filtered.empty:
        st.info("Không có bài đăng phù hợp với bộ lọc hiện tại.")
        return

    selected_post = st.selectbox(
        "Chọn bài để xem chi tiết",
        filtered["post_id"].tolist(),
        format_func=lambda post_id: f"{post_id} - {filtered.loc[filtered['post_id'] == post_id, 'title'].iloc[0]}",
    )
    row = filtered[filtered["post_id"] == selected_post].iloc[0]
    render_detail(row)

    if "golden_results" in st.session_state:
        st.divider()
        st.header("🧪 Kết quả kiểm thử CP3")
        results = st.session_state.golden_results
        passed = int((results["Đạt sơ bộ"] == "Đạt").sum())
        m1, m2, m3 = st.columns(3)
        m1.metric("Tổng số câu", len(results))
        m2.metric("Đạt sơ bộ", passed)
        m3.metric("Cần xem lại", len(results) - passed)
        st.caption("Đạt sơ bộ = câu trả lời có ít nhất một từ khóa kỳ vọng; người dùng vẫn cần xem nội dung thực tế.")
        st.dataframe(results, hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
