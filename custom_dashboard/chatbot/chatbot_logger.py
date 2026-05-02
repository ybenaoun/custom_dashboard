# chatbot_logger.py
# Logging structuré pour tracer chaque décision du pipeline chatbot
# Activé uniquement si frappe.conf.chatbot_debug = True
# Stockage dans le DocType "Chatbot Trace"

import json
import frappe
from frappe.utils import now_datetime, add_days, nowdate


class ChatbotLogger:
    """
    Trace chaque étape du pipeline chatbot.
    Activé via site_config.json : "chatbot_debug": true

    Usage :
        logger = ChatbotLogger(conv.name, message)
        logger.log_step("classify", intent="customer_info", entity="Grant Plastics")
        logger.save()
    """

    def __init__(self, conversation_id, message):
        self.enabled = frappe.conf.get("chatbot_debug", False)
        self.trace = {
            "conversation_id": conversation_id,
            "message": message[:100] if message else "",
            "user": frappe.session.user,
            "timestamp": str(now_datetime()),
            "steps": [],
        }

    def log_step(self, step_name, **kwargs):
        """Ajoute une étape à la trace."""
        if not self.enabled:
            return
        self.trace["steps"].append({
            "step": step_name,
            **{k: str(v)[:200] if v is not None else None for k, v in kwargs.items()},
        })

    def save(self):
        """Sauvegarde la trace dans le DocType 'Chatbot Trace'."""
        if not self.enabled or not self.trace["steps"]:
            return
        try:
            if not frappe.db.exists("DocType", "Chatbot Trace"):
                return

            trace_doc = frappe.get_doc({
                "doctype": "Chatbot Trace",
                "conversation_id": self.trace["conversation_id"],
                "user": self.trace["user"],
                "message": self.trace["message"],
                "timestamp": self.trace["timestamp"],
                "trace_json": json.dumps(self.trace, indent=2, default=str, ensure_ascii=False),
            })
            trace_doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception:
            pass  # Ne jamais casser le flux principal pour un log

    @staticmethod
    def purge_old_traces(days=7):
        """
        Supprime les traces plus vieilles que N jours.
        Appeler via bench console ou cron :
            from custom_dashboard.chatbot.chatbot_logger import ChatbotLogger
            ChatbotLogger.purge_old_traces(days=7)
        """
        try:
            if not frappe.db.exists("DocType", "Chatbot Trace"):
                return 0
            cutoff = str(add_days(nowdate(), -days))
            count = frappe.db.count("Chatbot Trace", {"timestamp": ["<", cutoff]})
            if count > 0:
                frappe.db.delete("Chatbot Trace", {"timestamp": ["<", cutoff]})
                frappe.db.commit()
            return count
        except Exception:
            return 0