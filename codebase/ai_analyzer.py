"""
ai_analyzer.py - Module AI phân tích, tóm tắt và đánh giá bài đăng Discord.
Hỗ trợ tự động đọc API Key từ file .env hoặc biến môi trường.
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
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


def read_config_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def get_config_value(key: str, default: str | None = None) -> str | None:
    environment_value = os.environ.get(key)
    if environment_value:
        return environment_value

    config_paths = [
        APP_DIR / ".env",
        ROOT_DIR / ".env",
    ]
    for path in config_paths:
        value = read_config_values(path).get(key)
        if value:
            return value
    return default


def get_api_key(provider: str) -> str | None:
    """Đọc đúng API key của provider, không dùng chéo key giữa Gemini và OpenAI."""
    if provider == "gemini":
        return get_config_value("GEMINI_API_KEY") or get_config_value("GOOGLE_API_KEY")
    if provider == "openai":
        return get_config_value("OPENAI_API_KEY")
    raise ValueError(f"Unsupported AI provider: {provider}")


def is_configured_key(key: str | None) -> bool:
    return bool(key and key not in {"your_gemini_api_key_here", "your_openai_api_key_here"})


def _call_gemini_api(api_key: str, prompt: str, model_name: str) -> str:
    """Gọi Google Gemini API bằng HTTP REST."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
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


def _call_openai_api(api_key: str, prompt: str, model_name: str) -> str:
    """Gọi OpenAI API bằng HTTP REST."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model_name,
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


def analyze_post_content(
    title: str,
    content: str,
    api_key: str | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """
    Phân tích bài viết bằng AI thật (Gemini/OpenAI) hoặc Fallback nếu không có Key.
    """
    selected_provider = str(provider or get_config_value("AI_PROVIDER", "auto") or "auto").strip().lower()
    if selected_provider not in {"auto", "gemini", "openai"}:
        fallback = _heuristic_fallback(title, content)
        fallback["provider"] = f"Rule Fallback (AI_PROVIDER không hợp lệ: {selected_provider})"
        return fallback

    gemini_key = api_key if api_key and selected_provider in {"auto", "gemini"} else get_api_key("gemini")
    openai_key = api_key if api_key and selected_provider == "openai" else get_api_key("openai")
    has_gemini = selected_provider in {"auto", "gemini"} and is_configured_key(gemini_key)
    has_openai = selected_provider in {"auto", "openai"} and is_configured_key(openai_key)
    if not (has_gemini or has_openai):
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

    failures: list[str] = []
    gemini_model = str(get_config_value("GEMINI_MODEL", DEFAULT_GEMINI_MODEL) or DEFAULT_GEMINI_MODEL)
    openai_model = str(get_config_value("OPENAI_MODEL", DEFAULT_OPENAI_MODEL) or DEFAULT_OPENAI_MODEL)

    if has_gemini:
        try:
            raw_response = _call_gemini_api(str(gemini_key), prompt, gemini_model)
            data = json.loads(raw_response)
            data["is_real_ai"] = True
            data["provider"] = f"Google {gemini_model} 🤖"
            return data
        except Exception as exc:
            failures.append(f"Gemini: {type(exc).__name__}")

    if has_openai:
        try:
            raw_response = _call_openai_api(str(openai_key), prompt, openai_model)
            data = json.loads(raw_response)
            data["is_real_ai"] = True
            data["provider"] = f"OpenAI {openai_model} 🤖"
            return data
        except Exception as exc:
            failures.append(f"OpenAI: {type(exc).__name__}")

    fallback_res = _heuristic_fallback(title, content)
    failure_summary = ", ".join(failures) if failures else "không có provider khả dụng"
    fallback_res["provider"] = f"Rule Fallback ({failure_summary})"
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
