"""
ai_analyzer.py - Module AI phân tích, tóm tắt và đánh giá bài đăng Discord.
Hỗ trợ tự động đọc API Key từ file .env / .streamlit/secrets.toml / Biến môi trường.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent


def get_api_key() -> str | None:
    """Tự động đọc Gemini/OpenAI API Key từ nhiều nguồn (Environment, .env, secrets.toml)."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if key:
        return key

    for env_file in [APP_DIR / ".env", ROOT_DIR / ".env"]:
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY=") or line.startswith("GOOGLE_API_KEY="):
                        return line.split("=", 1)[1].strip(" '\"")
                    if line.startswith("OPENAI_API_KEY="):
                        return line.split("=", 1)[1].strip(" '\"")

    secrets_path = APP_DIR / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        with open(secrets_path, "r", encoding="utf-8") as f:
            for line in f:
                if "GEMINI_API_KEY" in line or "GOOGLE_API_KEY" in line or "OPENAI_API_KEY" in line:
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        return parts[1].strip(" '\"\n")

    return None


def _call_gemini_api(api_key: str, prompt: str) -> str:
    """Gọi Google Gemini 1.5 Flash API bằng HTTP REST."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")

    with urllib.request.urlopen(req, timeout=12) as response:
        res_data = json.loads(response.read().decode("utf-8"))
        candidates = res_data.get("candidates", [])
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            if parts and "text" in parts[0]:
                return parts[0]["text"]
    raise RuntimeError("Khong nhan duoc phan hoi hop le tu Gemini API")


def _call_openai_api(api_key: str, prompt: str) -> str:
    """Gọi OpenAI GPT-4o-mini API bằng HTTP REST."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are an expert AI assistant that responds in valid JSON format."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")

    with urllib.request.urlopen(req, timeout=12) as response:
        res_data = json.loads(response.read().decode("utf-8"))
        choices = res_data.get("choices", [])
        if choices and "message" in choices[0]:
            return choices[0]["message"].get("content", "")
    raise RuntimeError("Khong nhan duoc phan hoi hop le tu OpenAI API")


def _heuristic_fallback(title: str, content: str) -> dict[str, Any]:
    """Fallback an toàn khi chưa cấu hình API Key hoặc lỗi mạng."""
    clean_text = content.strip()
    sentences = [s.strip() for s in re.split(r"[.!?\n]", clean_text) if s.strip()]

    summary = " ".join(sentences[:2]) if sentences else "Bài đăng ngắn chia sẻ thông tin học tập."
    if len(summary) > 250:
        summary = summary[:247] + "..."

    content_lower = (title + " " + content).lower()
    tag_candidates = {
        "RAG": ["rag", "retrieval", "vector", "embed"],
        "Prompting": ["prompt", "system prompt", "instruction"],
        "Agent": ["agent", "tool", "function call", "autogen", "crewai"],
        "Fine-tuning": ["fine-tune", "lora", "train", "huan luyen"],
        "LLM": ["llm", "gemini", "gpt", "claude", "ollama"],
        "Kinh nghiệm": ["chiase", "trai nghiem", "kinh nghiem", "luu y", "huong dan"],
        "Python": ["python", "code", "streamlit", "fastapi"],
    }

    extracted_tags = [tag for tag, keywords in tag_candidates.items() if any(kw in content_lower for kw in keywords)]
    if not extracted_tags:
        extracted_tags = ["Chia sẻ", "Kiến thức AI"]

    word_count = len(clean_text.split())
    ai_score = min(95.0, max(50.0, round(50 + (word_count / 15) + (len(extracted_tags) * 5), 1)))

    return {
        "summary": f"[Rule-Fallback] {summary}",
        "tags": extracted_tags,
        "topic": extracted_tags[0] if extracted_tags else "Chung",
        "ai_quality_score": ai_score,
        "key_takeaways": [
            f"Nội dung gồm khoảng {word_count} từ.",
            f"Chủ đề liên quan: {', '.join(extracted_tags)}.",
            "Khuyến nghị đọc trực tiếp bài viết gốc trên Discord để nắm chi tiết.",
        ],
        "is_real_ai": False,
        "provider": "Rule-based Engine (Fallback)",
    }


def analyze_post_content(title: str, content: str, api_key: str | None = None) -> dict[str, Any]:
    """
    Phân tích bài viết bằng AI thật (Gemini/OpenAI) hoặc Fallback nếu không có Key.
    """
    key = api_key or get_api_key()

    if not key or key in ["your_gemini_api_key_here", "your_openai_api_key_here"]:
        return _heuristic_fallback(title, content)

    prompt = f"""
Bạn là Trợ lý AI chuyên môn đánh giá và tổng hợp kiến thức cho học viên khóa học AI Thực Chiến.
Hãy phân tích bài đăng sau đây và trả về định dạng JSON đúng chuẩn:

Tiêu đề: {title}
Nội dung:
{content}

Hãy phản hồi DUY NHẤT một chuỗi JSON có cấu trúc như sau:
{{
  "summary": "Tóm tắt ngắn gọn 2-3 câu làm nổi bật giá trị cốt lõi của bài viết.",
  "tags": ["Tag1", "Tag2", "Tag3"],
  "topic": "Một trong các chủ đề: RAG, Prompt Engineering, AI Agent, Fine-tuning, Backend AI, Kinh nghiệm học tập",
  "ai_quality_score": 85.0,
  "key_takeaways": [
    "Ý chính 1",
    "Ý chính 2",
    "Ý chính 3"
  ]
}}
"""

    try:
        raw_response = _call_gemini_api(key, prompt)
        data = json.loads(raw_response)
        data["is_real_ai"] = True
        data["provider"] = "Google Gemini 1.5 Flash 🤖"
        return data
    except Exception:
        pass

    try:
        raw_response = _call_openai_api(key, prompt)
        data = json.loads(raw_response)
        data["is_real_ai"] = True
        data["provider"] = "OpenAI GPT-4o-mini 🤖"
        return data
    except Exception:
        pass

    fallback_res = _heuristic_fallback(title, content)
    fallback_res["provider"] = "Rule Fallback (Mạng/Key yếu)"
    return fallback_res


def semantic_search_score(query: str, title: str, content: str, summary: str, tags: list[str]) -> float:
    """Tính điểm khớp ngữ nghĩa giữa câu hỏi người dùng và bài đăng."""
    if not query.strip():
        return 0.0

    query_words = set(re.findall(r"\w+", query.lower()))
    text_corpus = f"{title} {content} {summary} {' '.join(tags)}".lower()
    text_words = set(re.findall(r"\w+", text_corpus))

    if not query_words:
        return 0.0

    overlap = len(query_words & text_words)
    ratio = overlap / len(query_words)
    return round(ratio * 100.0, 1)
