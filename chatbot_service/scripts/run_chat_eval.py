from __future__ import annotations

import argparse
import json
import re
import statistics
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt


APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = APP_ROOT / "eval" / "datasets" / "chatbot_eval.jsonl"
REPORT_DIR = APP_ROOT / "eval" / "reports"
ENV_FILE = APP_ROOT / ".env"

MODES: dict[str, dict[str, bool]] = {
    "baseline": {"use_rag": False, "use_tools": False},
    "tools": {"use_rag": False, "use_tools": True},
    "rag": {"use_rag": True, "use_tools": False},
    "hybrid": {"use_rag": True, "use_tools": True},
}


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"').strip("'")
    return values


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no} JSON invalid: {exc}") from exc
        if case.get("enabled", True):
            cases.append(case)
    return cases


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.lower()).strip()


def compact_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_text(value))


def make_jwt(env: dict[str, str], case: dict[str, Any]) -> str:
    now = int(time.time())
    payload = {
        "user": case.get("user") or "Administrator",
        "roles": case.get("roles") or ["System Manager"],
        "company": case.get("company"),
        "iat": now,
        "exp": now + 900,
    }
    return jwt.encode(
        payload,
        env["JWT_SECRET"],
        algorithm=env.get("JWT_ALGORITHM") or "HS256",
    )


def post_json(
    base_url: str,
    path: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: int = 180,
    attempts: int = 3,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        request = urllib.request.Request(
            base_url.rstrip("/") + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"{path} failed with HTTP {exc.code}: {body}")
            if exc.code < 500 or attempt >= attempts:
                raise last_error from exc
        except urllib.error.URLError as exc:
            last_error = RuntimeError(f"{path} failed: {exc}")
            if attempt >= attempts:
                raise last_error from exc
        time.sleep(1.5 * attempt)
    raise last_error or RuntimeError(f"{path} failed")


def setup_case_documents(base_url: str, env: dict[str, str], case: dict[str, Any]) -> list[tuple[str, str]]:
    api_key = env.get("RAG_INTERNAL_API_KEY")
    documents = case.get("setup_rag_documents") or []
    if not api_key or not documents:
        return []
    indexed: list[tuple[str, str]] = []
    for document in documents:
        post_json(base_url, "/rag/index", {"document": document}, {"X-RAG-API-Key": api_key})
        indexed.append((document["doctype"], document["docname"]))
    return indexed


def cleanup_documents(base_url: str, env: dict[str, str], docs: list[tuple[str, str]]) -> None:
    api_key = env.get("RAG_INTERNAL_API_KEY")
    if not api_key:
        return
    for doctype, docname in docs:
        try:
            post_json(
                base_url,
                "/rag/delete",
                {"doctype": doctype, "docname": docname},
                {"X-RAG-API-Key": api_key},
                timeout=60,
            )
        except Exception:
            pass


def source_matches(actual: list[dict[str, Any]], expected: list[dict[str, Any]]) -> bool:
    if not expected:
        return True
    for wanted in expected:
        found = False
        for source in actual:
            if wanted.get("doctype") and source.get("doctype") != wanted["doctype"]:
                continue
            if wanted.get("docname") and source.get("docname") != wanted["docname"]:
                continue
            found = True
            break
        if not found:
            return False
    return True


def grade_response(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    response = result.get("response") or ""
    normalized = normalize_text(response)
    checks: dict[str, Any] = {}

    expected_keywords = case.get("expected_keywords") or []
    if expected_keywords:
        compact_response = compact_text(response)
        missing = [
            kw
            for kw in expected_keywords
            if normalize_text(kw) not in normalized and compact_text(kw) not in compact_response
        ]
        checks["keywords"] = {"passed": not missing, "missing": missing}

    expected_regex = case.get("expected_regex")
    if expected_regex:
        checks["regex"] = {
            "passed": bool(re.search(expected_regex, response, flags=re.I | re.S))
            or bool(re.search(expected_regex, normalized, flags=re.I | re.S))
        }

    expected_sources = case.get("expected_sources") or []
    if expected_sources:
        checks["sources"] = {
            "passed": source_matches(result.get("rag_sources") or [], expected_sources),
            "expected": expected_sources,
        }

    expected_tools = case.get("expected_tools") or []
    if expected_tools:
        used_tools = result.get("used_tools") or []
        missing_tools = [tool for tool in expected_tools if tool not in used_tools]
        checks["tools"] = {"passed": not missing_tools, "missing": missing_tools}

    if not checks:
        return {"passed": False, "score": 0.0, "checks": {"configured": {"passed": False}}}

    passed = all(item["passed"] for item in checks.values())
    score = sum(1 for item in checks.values() if item["passed"]) / len(checks)
    return {"passed": passed, "score": score, "checks": checks}


def run_case_mode(base_url: str, env: dict[str, str], case: dict[str, Any], mode: str) -> dict[str, Any]:
    payload = {
        "message": case["question"],
        "language": case.get("language") or "fr",
        "company": case.get("company"),
        "doctypes": case.get("doctypes") or [],
        **MODES[mode],
    }
    payload = {key: value for key, value in payload.items() if value not in (None, "", [])}
    started = time.perf_counter()
    result = post_json(
        base_url,
        "/chat",
        payload,
        {"Authorization": f"Bearer {make_jwt(env, case)}"},
    )
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    grade = grade_response(case, result)
    return {
        "case_id": case["id"],
        "mode": mode,
        "latency_ms": latency_ms,
        "passed": grade["passed"],
        "score": grade["score"],
        "checks": grade["checks"],
        "response": result.get("response"),
        "rag_confidence": result.get("rag_confidence"),
        "rag_sources": result.get("rag_sources") or [],
        "used_tools": result.get("used_tools") or [],
        "input_tokens": result.get("input_tokens") or 0,
        "output_tokens": result.get("output_tokens") or 0,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for mode in MODES:
        rows = [row for row in results if row["mode"] == mode]
        if not rows:
            continue
        summary[mode] = {
            "total": len(rows),
            "passed": sum(1 for row in rows if row["passed"]),
            "accuracy": round(sum(1 for row in rows if row["passed"]) / len(rows), 4),
            "avg_score": round(statistics.mean(row["score"] for row in rows), 4),
            "avg_latency_ms": round(statistics.mean(row["latency_ms"] for row in rows), 2),
            "avg_rag_confidence": round(
                statistics.mean(row["rag_confidence"] or 0 for row in rows),
                4,
            ),
        }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate chatbot accuracy across baseline/tools/rag/hybrid modes.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--base-url", default="http://127.0.0.1:9001")
    parser.add_argument("--modes", default="baseline,tools,rag,hybrid")
    parser.add_argument("--keep-fixtures", action="store_true")
    args = parser.parse_args()

    env = load_env(ENV_FILE)
    cases = load_cases(args.dataset)
    requested_modes = [mode.strip() for mode in args.modes.split(",") if mode.strip()]
    invalid_modes = [mode for mode in requested_modes if mode not in MODES]
    if invalid_modes:
        raise ValueError(f"Modes invalides: {', '.join(invalid_modes)}")

    indexed_docs: list[tuple[str, str]] = []
    results: list[dict[str, Any]] = []
    try:
        for case in cases:
            indexed_docs.extend(setup_case_documents(args.base_url, env, case))
            case_modes = case.get("modes") or requested_modes
            for mode in requested_modes:
                if mode not in case_modes:
                    continue
                results.append(run_case_mode(args.base_url, env, case, mode))
    finally:
        if not args.keep_fixtures:
            cleanup_documents(args.base_url, env, indexed_docs)

    report = {
        "dataset": str(args.dataset),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": summarize(results),
        "results": results,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"chat_eval_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    print(json.dumps({"summary": report["summary"], "report": str(report_path)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
