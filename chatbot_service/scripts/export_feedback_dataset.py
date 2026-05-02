from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parents[1]
BENCH_ROOT = APP_ROOT.parents[2]
SITES_PATH = BENCH_ROOT / "sites"

for app_name in ("frappe", "erpnext", "custom_dashboard"):
    app_path = BENCH_ROOT / "apps" / app_name
    if app_path.exists():
        sys.path.insert(0, str(app_path))


def parse_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def feedback_to_case(row: Any) -> dict[str, Any] | None:
    question = str(row.question or "").strip()
    if not question:
        return None

    expected = str(row.expected_answer or "").strip()
    answer = str(row.answer or "").strip()
    expected_keywords = []
    if expected:
        expected_keywords = [part.strip() for part in expected.splitlines() if part.strip()][:8]

    case = {
        "id": f"feedback_{row.name}",
        "enabled": bool(expected_keywords),
        "question": question,
        "language": "fr",
        "expected_keywords": expected_keywords,
        "modes": ["baseline", "tools", "rag", "hybrid"],
        "metadata": {
            "feedback_id": row.name,
            "conversation_id": row.conversation_id,
            "rating": row.rating,
            "original_answer": answer,
            "comment": row.comment,
            "rag_sources": parse_json(row.rag_sources_json, []),
            "used_tools": parse_json(row.used_tools_json, []),
        },
    }
    return case


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Chatbot Feedback rows to eval JSONL.")
    parser.add_argument("--site", default="erpnext.localhost")
    parser.add_argument(
        "--output",
        type=Path,
        default=APP_ROOT / "eval" / "datasets" / "feedback_eval.jsonl",
    )
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--rating", choices=["up", "down", "all"], default="down")
    args = parser.parse_args()

    import frappe

    frappe.init(site=args.site, sites_path=str(SITES_PATH))
    frappe.connect()
    try:
        filters = {}
        if args.rating != "all":
            filters["rating"] = args.rating
        rows = frappe.get_all(
            "Chatbot Feedback",
            filters=filters,
            fields=[
                "name",
                "conversation_id",
                "rating",
                "question",
                "answer",
                "comment",
                "expected_answer",
                "rag_sources_json",
                "used_tools_json",
            ],
            order_by="creation desc",
            limit_page_length=args.limit,
        )
        cases = [case for row in rows if (case := feedback_to_case(row))]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases)
        )
        print(json.dumps({"exported": len(cases), "output": str(args.output)}, indent=2, ensure_ascii=False))
        return 0
    finally:
        frappe.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
