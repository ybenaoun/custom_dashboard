from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = APP_ROOT / ".env"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"').strip("'")
    return values


def post_json(base_url: str, api_key: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-RAG-API-Key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{path} failed with HTTP {exc.code}: {body}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the RAG FastAPI pipeline end to end.")
    parser.add_argument("--base-url", default="http://127.0.0.1:9001")
    parser.add_argument("--keep", action="store_true", help="Keep the validation document indexed.")
    args = parser.parse_args()

    env = load_env(ENV_FILE)
    api_key = env.get("RAG_INTERNAL_API_KEY")
    if not api_key:
        print("RAG_INTERNAL_API_KEY is missing from .env", file=sys.stderr)
        return 2

    doctype = "RAG Validation"
    docname = "RAG-E2E-001"
    index_payload = {
        "document": {
            "doctype": doctype,
            "docname": docname,
            "owner": "Administrator",
            "company": "Validation SARL",
            "metadata": {
                "owner": "Administrator",
                "company": "Validation SARL",
                "allowed_users": ["Administrator"],
                "permitted_roles": ["System Manager"],
                "source": "validate_rag_e2e.py",
            },
            "data": {
                "title": "Validation RAG chiffre d'affaires",
                "content": (
                    "Le chiffre d'affaires cumule de l'exercice 2026 pour Validation SARL "
                    "est de 424242 MAD. Cette valeur sert uniquement au test RAG bout-en-bout."
                ),
            },
        }
    }
    ask_payload = {
        "question": "Quel est le chiffre d'affaires cumule 2026 de Validation SARL ?",
        "company": "Validation SARL",
        "user": "Administrator",
        "roles": ["System Manager"],
        "doctypes": [doctype],
    }

    index_result = post_json(args.base_url, api_key, "/rag/index", index_payload)
    ask_result = post_json(args.base_url, api_key, "/rag/ask", ask_payload)

    if not ask_result.get("sources"):
        raise RuntimeError(f"/rag/ask returned no sources: {json.dumps(ask_result, ensure_ascii=False)}")

    output = {
        "index": index_result,
        "ask": {
            "answer": ask_result.get("answer"),
            "sources": ask_result.get("sources"),
            "confidence": ask_result.get("confidence"),
            "retrieved_chunks": len(ask_result.get("retrieved_chunks") or []),
        },
    }

    if not args.keep:
        output["delete"] = post_json(
            args.base_url,
            api_key,
            "/rag/delete",
            {"doctype": doctype, "docname": docname},
        )

    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
