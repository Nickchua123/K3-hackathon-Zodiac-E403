from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
CODEBASE_DIR = ROOT_DIR / "codebase"
DEFAULT_GOLDEN_SET = Path(__file__).with_name("golden_set.csv")
DEFAULT_RESULTS = Path(__file__).with_name("results.csv")
DEFAULT_SUMMARY = Path(__file__).with_name("summary.json")
MOCK_DATA_PATH = CODEBASE_DIR / "mock_posts.csv"

# Eval phải lặp lại được và không gửi dữ liệu ra API ngoài.
os.environ["RAG_ENABLED"] = "false"
sys.path.insert(0, str(CODEBASE_DIR))

import main as app_main  # noqa: E402


REQUIRED_GOLDEN_COLUMNS = {
    "case_id",
    "category",
    "query",
    "expected_behavior",
    "relevant_post_ids",
    "min_relevant_in_top_k",
    "answer_must_contain_any",
    "notes",
}
RETRIEVAL_BEHAVIORS = {"retrieve", "retrieve_with_caveat"}
SUPPORTED_BEHAVIORS = RETRIEVAL_BEHAVIORS | {"reject_no_evidence", "refuse"}


def configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", str(value).lower())
    return "".join(character for character in decomposed if unicodedata.category(character) != "Mn")


def split_values(value: str, separator: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(separator) if item.strip()]


def load_golden_set(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_GOLDEN_COLUMNS - columns
        if missing:
            raise ValueError(f"Golden set thiếu cột: {', '.join(sorted(missing))}")
        cases = list(reader)

    if not cases:
        raise ValueError("Golden set đang rỗng.")

    seen_ids: set[str] = set()
    for case in cases:
        case_id = case["case_id"].strip()
        behavior = case["expected_behavior"].strip()
        if not case_id or case_id in seen_ids:
            raise ValueError(f"case_id rỗng hoặc trùng: {case_id!r}")
        if behavior not in SUPPORTED_BEHAVIORS:
            raise ValueError(f"{case_id}: expected_behavior không hợp lệ: {behavior!r}")
        try:
            int(case["min_relevant_in_top_k"])
        except ValueError as exc:
            raise ValueError(f"{case_id}: min_relevant_in_top_k phải là số nguyên.") from exc
        seen_ids.add(case_id)
    return cases


def load_fixed_eval_data() -> pd.DataFrame:
    frame = pd.read_csv(MOCK_DATA_PATH, encoding="utf-8-sig")
    missing = [column for column in app_main.REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"mock_posts.csv thiếu cột: {', '.join(missing)}")
    frame = frame[app_main.REQUIRED_COLUMNS].copy()
    frame["source"] = "mock"
    return app_main.add_scores(frame)


def run_pipeline(data: pd.DataFrame, query: str, top_k: int) -> tuple[str, list[dict[str, Any]]]:
    response = app_main.build_chat_response(query, data, top_k=top_k)
    return str(response["answer"]), list(response["results"])


def answer_contains_any(answer: str, raw_patterns: str) -> bool:
    patterns = split_values(raw_patterns, "|")
    if not patterns:
        return True
    normalized_answer = normalize_text(answer)
    return any(normalize_text(pattern) in normalized_answer for pattern in patterns)


def is_grounded(result: dict[str, Any], source_urls: dict[str, str]) -> bool:
    post_id = str(result.get("post_id", ""))
    url = str(result.get("url", "")).strip()
    return bool(post_id and url and source_urls.get(post_id) == url)


def is_transparent(result: dict[str, Any]) -> bool:
    quality_score = result.get("quality_score")
    details = result.get("score_detail")
    required_detail_keys = {
        "signal",
        "raw_value",
        "score",
        "weight",
        "contribution",
        "description",
    }
    return (
        isinstance(quality_score, (int, float))
        and isinstance(details, list)
        and len(details) == len(app_main.WEIGHTS)
        and all(required_detail_keys.issubset(detail) for detail in details)
    )


def evaluate_case(
    case: dict[str, str],
    data: pd.DataFrame,
    source_urls: dict[str, str],
    top_k: int,
) -> dict[str, Any]:
    answer, results = run_pipeline(data, case["query"], top_k)
    actual_ids = [str(result.get("post_id", "")) for result in results]
    expected_ids = set(split_values(case["relevant_post_ids"], ";"))
    relevant_count = len(expected_ids.intersection(actual_ids))
    minimum_relevant = int(case["min_relevant_in_top_k"])
    behavior = case["expected_behavior"]

    relevance_pass = True
    response_behavior_pass = True
    if behavior in RETRIEVAL_BEHAVIORS:
        relevance_pass = bool(results) and relevant_count >= minimum_relevant
    elif behavior == "reject_no_evidence":
        relevance_pass = not results
        response_behavior_pass = not results and answer_contains_any(
            answer,
            case["answer_must_contain_any"],
        )
    elif behavior == "refuse":
        relevance_pass = not results
        response_behavior_pass = not results and answer_contains_any(
            answer,
            case["answer_must_contain_any"],
        )

    if behavior == "retrieve_with_caveat":
        response_behavior_pass = answer_contains_any(answer, case["answer_must_contain_any"])

    groundedness_pass = all(is_grounded(result, source_urls) for result in results)
    transparency_pass = all(is_transparent(result) for result in results)
    case_pass = (
        relevance_pass
        and groundedness_pass
        and transparency_pass
        and response_behavior_pass
    )

    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "query": case["query"],
        "expected_behavior": behavior,
        "expected_post_ids": ";".join(sorted(expected_ids)),
        "actual_post_ids": ";".join(actual_ids),
        "relevant_in_top_k": relevant_count,
        "relevance_pass": relevance_pass,
        "groundedness_pass": groundedness_pass,
        "transparency_pass": transparency_pass,
        "response_behavior_pass": response_behavior_pass,
        "case_pass": case_pass,
        "answer": answer,
        "notes": case["notes"],
    }


def build_summary(rows: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    total = len(rows)
    passed = sum(bool(row["case_pass"]) for row in rows)
    retrieval_rows = [row for row in rows if row["expected_behavior"] in RETRIEVAL_BEHAVIORS]
    rows_with_results = [row for row in rows if row["actual_post_ids"]]

    relevance_passed = sum(bool(row["relevance_pass"]) for row in retrieval_rows)
    groundedness_passed = sum(bool(row["groundedness_pass"]) for row in rows_with_results)
    transparency_passed = sum(bool(row["transparency_pass"]) for row in rows_with_results)
    behavior_passed = sum(bool(row["response_behavior_pass"]) for row in rows)

    relevance_rate = relevance_passed / len(retrieval_rows) if retrieval_rows else 1.0
    groundedness_rate = groundedness_passed / len(rows_with_results) if rows_with_results else 1.0
    transparency_rate = transparency_passed / len(rows_with_results) if rows_with_results else 1.0
    behavior_rate = behavior_passed / total if total else 1.0

    quality_bar = {
        "relevance_at_least_80_percent": relevance_rate >= 0.80,
        "groundedness_100_percent": groundedness_rate == 1.0,
        "transparency_100_percent": transparency_rate == 1.0,
        "no_hallucinated_post_ids": groundedness_rate == 1.0,
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_source": str(MOCK_DATA_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
        "top_k": top_k,
        "total_cases": total,
        "passed_cases": passed,
        "failed_cases": total - passed,
        "case_pass_rate": round(passed / total, 4) if total else 1.0,
        "metrics": {
            "retrieval_relevance_pass_rate": round(relevance_rate, 4),
            "groundedness_pass_rate": round(groundedness_rate, 4),
            "transparency_pass_rate": round(transparency_rate, 4),
            "response_behavior_pass_rate": round(behavior_rate, 4),
        },
        "quality_bar": quality_bar,
        "quality_bar_pass": all(quality_bar.values()),
        "failed_case_ids": [row["case_id"] for row in rows if not row["case_pass"]],
    }


def write_results(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chạy golden set cho Discord Quality Digest.")
    parser.add_argument("--golden-set", type=Path, default=DEFAULT_GOLDEN_SET)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Trả exit code 1 nếu có case fail hoặc không đạt quality bar.",
    )
    return parser.parse_args()


def main() -> int:
    configure_console_encoding()
    args = parse_args()
    if not 1 <= args.top_k <= 10:
        raise ValueError("--top-k phải nằm trong khoảng 1-10.")

    cases = load_golden_set(args.golden_set)
    data = load_fixed_eval_data()
    source_urls = {
        str(row["post_id"]): str(row["url"])
        for _, row in data.iterrows()
    }
    rows = [
        evaluate_case(case, data, source_urls, args.top_k)
        for case in cases
    ]
    summary = build_summary(rows, args.top_k)

    write_results(args.results, rows)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Eval: {summary['passed_cases']}/{summary['total_cases']} case pass "
        f"({summary['case_pass_rate'] * 100:.1f}%)."
    )
    print(
        "Relevance={:.1f}% | Groundedness={:.1f}% | "
        "Transparency={:.1f}% | Behavior={:.1f}%".format(
            summary["metrics"]["retrieval_relevance_pass_rate"] * 100,
            summary["metrics"]["groundedness_pass_rate"] * 100,
            summary["metrics"]["transparency_pass_rate"] * 100,
            summary["metrics"]["response_behavior_pass_rate"] * 100,
        )
    )
    if summary["failed_case_ids"]:
        print(f"Case fail: {', '.join(summary['failed_case_ids'])}")
    print(f"Kết quả chi tiết: {args.results}")
    print(f"Tóm tắt: {args.summary}")

    strict_failure = bool(summary["failed_cases"]) or not summary["quality_bar_pass"]
    return 1 if args.strict and strict_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
