from __future__ import annotations

import json
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
BENCH_ROOT = APP_ROOT.parents[2]
SITES_PATH = BENCH_ROOT / "sites"

for app_name in ("frappe", "erpnext", "custom_dashboard"):
    app_path = BENCH_ROOT / "apps" / app_name
    if app_path.exists():
        sys.path.insert(0, str(app_path))


def main() -> int:
    import frappe
    from custom_dashboard.chatbot.chatbot_proxy import submit_feedback

    frappe.init(site="erpnext.localhost", sites_path=str(SITES_PATH))
    frappe.connect()
    frappe.set_user("Administrator")
    feedback_id = None
    try:
        result = submit_feedback(
            question="Question de validation feedback",
            response="Reponse de validation feedback",
            rating="down",
            comment="Validation automatique",
            expected_answer="Reponse attendue de validation",
            rag_sources=[],
            used_tools=[],
            metadata={"source": "validate_feedback.py"},
        )
        feedback_id = result.get("feedback_id")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    finally:
        if feedback_id:
            frappe.delete_doc("Chatbot Feedback", feedback_id, ignore_permissions=True, force=True)
            frappe.db.commit()
        frappe.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
