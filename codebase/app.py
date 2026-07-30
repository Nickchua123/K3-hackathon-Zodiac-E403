from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DATA_PATH = APP_DIR / "mock_posts.csv"

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


@st.cache_data
def load_posts() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    return add_scores(df)


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
        st.subheader("Noi dung bai viet")
        st.write(row["content"])
        st.subheader("Mock AI summary")
        st.write(row["mock_summary"])
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
    st.caption("Prototype mock: du lieu va output AI la gia lap de demo nhanh.")

    st.markdown(
        """
        <div class="score-note">
        Cong thuc: Click 20% + Like 15% + Tim 20% + Thoi luong xem 25% + Ty le xem het 10% + Luu/Chia se 10%.
        Moi tin hieu duoc chuan hoa ve thang 0-100 truoc khi tinh diem.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.header("Bo loc")
    query = st.sidebar.text_input("Tim kiem tu nhien", placeholder="tim bai hay ve RAG va prompt")
    topics = ["Tat ca"] + sorted(df["topic"].unique().tolist())
    selected_topic = st.sidebar.selectbox("Chu de", topics)
    min_score = st.sidebar.slider("Diem toi thieu", 0, 100, 0, step=5)
    sort_by = st.sidebar.selectbox("Sap xep", ["Diem chat luong", "Moi nhat", "Nhieu luu/chia se"])

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

    top_col, avg_col, count_col, topic_col = st.columns(4)
    top_col.metric("Bai noi bat", f"{df['quality_score'].max():.1f}")
    avg_col.metric("Diem trung binh", f"{df['quality_score'].mean():.1f}")
    count_col.metric("Bai dang", len(filtered))
    topic_col.metric("Chu de", selected_topic)

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
    st.subheader("Danh sach bai dang")
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
        return

    selected_post = st.selectbox(
        "Chon bai de xem chi tiet",
        filtered["post_id"].tolist(),
        format_func=lambda post_id: f"{post_id} - {filtered.loc[filtered['post_id'] == post_id, 'title'].iloc[0]}",
    )
    row = filtered[filtered["post_id"] == selected_post].iloc[0]
    render_detail(row)


if __name__ == "__main__":
    main()
