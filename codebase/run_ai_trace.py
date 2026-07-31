from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ai_analyzer import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OPENAI_MODEL,
    analyze_post_content,
    get_config_value,
)


APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
MOCK_DATA_PATH = APP_DIR / "mock_posts.csv"
TRACE_DIR = ROOT_DIR / "traces"
TRACE_POST_ID = "P001"
LOCAL_TIMEZONE = ZoneInfo("Asia/Bangkok")


def load_mock_post(post_id: str) -> dict[str, str]:
    with MOCK_DATA_PATH.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("post_id") == post_id:
                return {key: str(value or "") for key, value in row.items()}
    raise RuntimeError(f"Không tìm thấy bài mock {post_id}")


def safe_output(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": str(result.get("summary", "")),
        "topic": str(result.get("topic", "")),
        "tags": [str(tag) for tag in result.get("tags", [])],
        "ai_quality_score": result.get("ai_quality_score"),
        "key_takeaways": [
            str(item) for item in result.get("key_takeaways", [])
        ],
    }


def provider_metadata(result: dict[str, Any]) -> tuple[str, str]:
    provider_label = str(result.get("provider", ""))
    if provider_label.startswith("Google "):
        return (
            "gemini",
            str(
                get_config_value("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
                or DEFAULT_GEMINI_MODEL
            ),
        )
    if provider_label.startswith("OpenAI "):
        return (
            "openai",
            str(
                get_config_value("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
                or DEFAULT_OPENAI_MODEL
            ),
        )
    raise RuntimeError(f"AI call đã fallback, không đủ điều kiện làm trace: {provider_label}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    post = load_mock_post(TRACE_POST_ID)
    selected_provider = str(
        get_config_value("AI_PROVIDER", "auto") or "auto"
    ).strip().lower()

    started_at = datetime.now(LOCAL_TIMEZONE)
    started = time.perf_counter()
    result = analyze_post_content(
        post["title"],
        post["content"],
        provider=selected_provider,
    )
    latency_ms = round((time.perf_counter() - started) * 1000)

    if not bool(result.get("is_real_ai")):
        raise RuntimeError(
            "Provider không trả kết quả AI thật; không tạo trace để tránh ghi sai evidence."
        )

    provider, model = provider_metadata(result)
    finished_at = datetime.now(LOCAL_TIMEZONE)
    input_fingerprint = hashlib.sha256(
        f"{post['title']}\n{post['content']}".encode("utf-8")
    ).hexdigest()

    trace = {
        "status": "success",
        "is_real_ai": True,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "latency_ms": latency_ms,
        "purpose": "Tóm tắt và gắn chủ đề/tag cho bài đăng trước khi lập chỉ mục",
        "decision_role": "AI enrichment trong background workflow",
        "provider": provider,
        "model": model,
        "input": {
            "source": "codebase/mock_posts.csv",
            "post_id": post["post_id"],
            "title": post["title"],
            "content_included_in_trace": False,
            "sha256": input_fingerprint,
        },
        "prompt_version": "codebase/ai_analyzer.py",
        "output": safe_output(result),
        "privacy": {
            "discord_content_sent": False,
            "api_key_recorded": False,
            "author_recorded": False,
            "url_recorded": False,
        },
    }

    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    trace_path = TRACE_DIR / f"ai-call-{started_at:%Y%m%d}.json"
    trace_path.write_text(
        json.dumps(trace, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "trace_path": str(trace_path),
                "provider": provider,
                "model": model,
                "is_real_ai": True,
                "latency_ms": latency_ms,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
