from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parents[1]
BENCH_ROOT = APP_ROOT.parents[2]
SITES_PATH = BENCH_ROOT / "sites"

for app_name in ("frappe", "erpnext", "custom_dashboard"):
    app_path = BENCH_ROOT / "apps" / app_name
    if app_path.exists():
        sys.path.insert(0, str(app_path))


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


def first_existing_doc(frappe: Any, doctypes: list[str]) -> tuple[str, str]:
    for doctype in doctypes:
        if not frappe.db.table_exists(doctype):
            continue
        rows = frappe.get_all(
            doctype,
            fields=["name"],
            order_by="modified desc",
            limit_page_length=1,
        )
        if rows:
            return doctype, rows[0].name
    raise RuntimeError(f"No documents found for doctypes: {', '.join(doctypes)}")


def hook_contains(value: Any, dotted_path: str) -> bool:
    if isinstance(value, str):
        return value == dotted_path
    if isinstance(value, (list, tuple, set)):
        return dotted_path in value
    return False


def validate_hooks_loaded(frappe: Any) -> dict[str, bool]:
    doc_events = frappe.get_hooks("doc_events") or {}
    wildcard_events = doc_events.get("*") or {}
    checks = {
        "on_update": hook_contains(
            wildcard_events.get("on_update"),
            "custom_dashboard.rag.on_rag_doc_update",
        ),
        "on_trash": hook_contains(
            wildcard_events.get("on_trash"),
            "custom_dashboard.rag.on_rag_doc_trash",
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"RAG doc_events hooks are not fully loaded: {checks}")
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Frappe to FastAPI RAG integration.")
    parser.add_argument("--site", default="erpnext.localhost")
    parser.add_argument("--doctype", action="append", dest="doctypes")
    parser.add_argument("--user", default="Administrator")
    args = parser.parse_args()

    import frappe
    from custom_dashboard import rag
    from custom_dashboard.rag_config import get_rag_doctypes

    frappe.init(site=args.site, sites_path=str(SITES_PATH))
    frappe.connect()
    frappe.set_user(args.user)

    try:
        hook_checks = validate_hooks_loaded(frappe)
        enabled_doctypes = list((get_rag_doctypes() or {}).keys())
        doctypes = args.doctypes or [dt for dt in ("Item", "Customer", "Sales Invoice") if dt in enabled_doctypes]
        if not doctypes:
            doctypes = enabled_doctypes[:3]

        doctype, docname = first_existing_doc(frappe, doctypes)
        index_result = rag.index_document(doctype, docname)

        roles = rag._read_roles_for_doctype(doctype) or frappe.get_roles(args.user)
        doc = frappe.get_doc(doctype, docname)
        company = doc.get("company") if hasattr(doc, "company") else None
        ask_payload = {
            "question": f"Dans le contexte indexe, quel est le nom du document {doctype} {docname} ?",
            "doctypes": [doctype],
            "company": company,
            "user": args.user,
            "roles": roles,
        }
        ask_result = post_json(
            rag._get_fastapi_url(),
            rag._get_internal_api_key(),
            "/rag/ask",
            {key: value for key, value in ask_payload.items() if value not in (None, "", [])},
        )

        if not ask_result.get("sources"):
            raise RuntimeError(f"/rag/ask returned no sources: {json.dumps(ask_result, ensure_ascii=False)}")

        print(
            json.dumps(
                {
                    "doctype": doctype,
                    "docname": docname,
                    "hooks": hook_checks,
                    "index": index_result,
                    "ask": {
                        "answer": ask_result.get("answer"),
                        "sources": ask_result.get("sources"),
                        "confidence": ask_result.get("confidence"),
                        "retrieved_chunks": len(ask_result.get("retrieved_chunks") or []),
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        frappe.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
