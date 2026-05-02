from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import jwt


APP_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = APP_ROOT / ".env"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"').strip("'")
    return values


def make_chat_jwt(env: dict[str, str]) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "user": "Administrator",
            "roles": ["System Manager"],
            "company": "Validation SARL",
            "iat": now,
            "exp": now + 300,
        },
        env["JWT_SECRET"],
        algorithm=env.get("JWT_ALGORITHM") or "HS256",
    )


def post_json(
    base_url: str,
    path: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str],
) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{path} failed with HTTP {exc.code}: {body}") from exc


def post_sse(
    base_url: str,
    path: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str],
) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    events: list[dict[str, Any]] = []
    with urllib.request.urlopen(request, timeout=180) as response:
        raw = response.read().decode("utf-8")
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        event = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())
        if data_lines:
            events.append({"event": event, "data": json.loads("\n".join(data_lines))})
    done = next((item["data"] for item in events if item["event"] == "done"), {})
    return {"events": events, "done": done}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RAG enrichment through /chat and /chat/stream.")
    parser.add_argument("--base-url", default="http://127.0.0.1:9001")
    args = parser.parse_args()

    env = load_env(ENV_FILE)
    rag_headers = {"X-RAG-API-Key": env["RAG_INTERNAL_API_KEY"]}
    chat_headers = {"Authorization": f"Bearer {make_chat_jwt(env)}"}
    doctype = "RAG Validation"
    docname = "CHAT-RAG-E2E-001"
    question = "Quel est le chiffre d'affaires cumule 2026 de Validation SARL selon le contexte indexe ?"

    document_payload = {
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
                "source": "validate_chat_rag.py",
            },
            "data": {
                "title": "Validation branchement chat RAG",
                "content": (
                    "Le chiffre d'affaires cumule de l'exercice 2026 pour Validation SARL "
                    "est de 919191 MAD. Cette valeur valide le branchement RAG dans /chat."
                ),
            },
        }
    }
    chat_payload = {
        "message": question,
        "language": "fr",
        "company": "Validation SARL",
        "doctypes": [doctype],
    }

    try:
        index_result = post_json(args.base_url, "/rag/index", document_payload, headers=rag_headers)
        chat_result = post_json(args.base_url, "/chat", chat_payload, headers=chat_headers)
        if not chat_result.get("rag_sources"):
            raise RuntimeError(f"/chat returned no rag_sources: {json.dumps(chat_result, ensure_ascii=False)}")

        stream_result = post_sse(args.base_url, "/chat/stream", chat_payload, headers=chat_headers)
        if not stream_result["done"].get("rag_sources"):
            raise RuntimeError(f"/chat/stream returned no rag_sources in done: {stream_result}")

        print(
            json.dumps(
                {
                    "index": index_result,
                    "chat": {
                        "response": chat_result.get("response"),
                        "rag_sources": chat_result.get("rag_sources"),
                        "rag_confidence": chat_result.get("rag_confidence"),
                    },
                    "stream": {
                        "response": stream_result["done"].get("response"),
                        "rag_sources": stream_result["done"].get("rag_sources"),
                        "rag_confidence": stream_result["done"].get("rag_confidence"),
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        post_json(args.base_url, "/rag/delete", {"doctype": doctype, "docname": docname}, headers=rag_headers)


if __name__ == "__main__":
    raise SystemExit(main())
