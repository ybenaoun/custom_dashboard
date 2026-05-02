# intent_classifier.py
# V4 : Classification via service IA FastAPI/Cohere + support contexte conversationnel
# Le contexte est injecté dans le message user, PAS dans le system prompt

import re
import json
import frappe
from datetime import timedelta
from frappe.utils import nowdate, getdate, get_first_day, get_last_day, add_months
from custom_dashboard.services import ai_gateway

# System prompt — IDENTIQUE au dataset d'entraînement (ne JAMAIS modifier)
CLASSIF_SYSTEM_PROMPT = "Tu es le classificateur de l'assistant Wizio ERP. Retourne UNIQUEMENT un JSON avec les clés : intent, period, language, entity."


# ═══════════════════════════════════════════════════════════
#  CLASSIFICATION — avec ou sans contexte
# ═══════════════════════════════════════════════════════════

def classify_with_context(message, context_string=""):
    """
    Classification avec contexte conversationnel.
    Le contexte est prépendé au message user (le system prompt reste identique).
    
    Args:
        message: str — le message brut de l'utilisateur
        context_string: str — chaîne "[Contexte: ...]" ou "" si pas de contexte
    
    Returns:
        dict avec {intent, period, language, entity}
    """
    if context_string:
        enriched = f"{context_string}\n{message}"
    else:
        enriched = message

    return classify_intent(enriched)


def classify_intent(message):
    """
    Classification via le service IA unique FastAPI/Cohere.
    Fallback 1 : keyword matching si le service échoue ou retourne general_chat
    Fallback 2 : general_chat
    """
    llm_result = _classify_with_fastapi(message)
    if llm_result and llm_result["intent"] != "general_chat":
        return llm_result

    # Fallback keyword — attrape les requêtes EN que le modèle rate
    msg = message.lower().strip()
    keyword_result = _keyword_fallback(msg)
    if keyword_result:
        return keyword_result

    # Si LLM avait retourné general_chat, le garder
    if llm_result:
        return llm_result

    language = _detect_language(msg)
    return {
        "intent": "general_chat",
        "period": "all",
        "language": language,
        "entity": None,
    }


# ═══════════════════════════════════════════════════════════
#  KEYWORD FALLBACK — filet de sécurité pour les cas EN
# ═══════════════════════════════════════════════════════════

_KEYWORD_MAP = [
    # EN — intents que le modèle rate parfois
    (["unpaid invoices", "invoices not paid", "outstanding invoices"], "unpaid_sales_invoices", "en"),
    (["overdue invoices", "late invoices"], "overdue_sales_invoices", "en"),
    (["customer list", "list of customers", "all customers"], "customer_list", "en"),
    (["supplier list", "list of suppliers", "all suppliers"], "supplier_list", "en"),
    (["stock availability", "stock level", "check stock"], "stock_availability", "en"),
    (["out of stock", "no stock"], "out_of_stock_items", "en"),
    (["employee directory", "list of employees", "employee list"], "employee_directory", "en"),
    (["project list", "list of projects", "all projects"], "project_list", "en"),
    (["overdue tasks", "late tasks"], "overdue_tasks", "en"),
    (["leave balance", "my leaves", "remaining leaves"], "leave_balance", "en"),
    (["absent today", "who is absent"], "team_absent_today", "en"),
    (["job openings", "open positions", "hiring"], "job_openings", "en"),
]


def _keyword_fallback(msg):
    """Matching par mots-clés — filet de sécurité quand le LLM échoue."""
    for keywords, intent, lang in _KEYWORD_MAP:
        for kw in keywords:
            if kw in msg:
                return {
                    "intent": intent,
                    "period": "all",
                    "language": lang,
                    "entity": None,
                }
    return None


def _classification_endpoint():
    return (frappe.conf or {}).get("chatbot_fastapi_classify_endpoint") or "/chat"


def _extract_classification_result(payload):
    raw = payload
    for key in ("classification", "data", "result"):
        if isinstance(raw, dict) and isinstance(raw.get(key), dict):
            raw = raw.get(key)
            break

    if isinstance(raw, dict) and not raw.get("intent"):
        text = raw.get("response") or raw.get("content") or raw.get("message") or raw.get("text")
        if isinstance(text, str):
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    raw = json.loads(match.group())
                except json.JSONDecodeError:
                    return None

    if not isinstance(raw, dict):
        return None

    intent = raw.get("intent", "general_chat")
    if intent not in VALID_INTENTS:
        return None

    return {
        "intent": intent,
        "period": raw.get("period", "all"),
        "language": raw.get("language", "fr"),
        "entity": raw.get("entity"),
    }


def _classify_with_fastapi(message):
    """Utilise le service FastAPI/Cohere pour classifier."""
    try:
        endpoint = _classification_endpoint()
        if endpoint.rstrip("/") == "/chat":
            payload = {
                "message": message,
                "language": _detect_language(message),
                "history": [{"role": "system", "content": CLASSIF_SYSTEM_PROMPT}],
                "use_rag": False,
                "use_tools": False,
                "metadata": {
                    "task": "intent_classification",
                    "valid_intents": sorted(VALID_INTENTS),
                    "response_format": "json",
                },
            }
        else:
            payload = {
                "message": message,
                "system_prompt": CLASSIF_SYSTEM_PROMPT,
                "valid_intents": sorted(VALID_INTENTS),
                "response_format": "json",
            }
        return _extract_classification_result(
            ai_gateway.post_json(endpoint, payload, timeout=15)
        )
    except ai_gateway.AIServiceError as exc:
        frappe.log_error(f"Classification FastAPI indisponible: {str(exc)}", "Chatbot")
    except Exception as e:
        frappe.log_error(f"Erreur classification: {str(e)}", "Chatbot")
    return None


# ═══════════════════════════════════════════════════════════
#  INTENTS VALIDES (84 intents)
# ═══════════════════════════════════════════════════════════

VALID_INTENTS = {
    # Finance & Comptabilité (25)
    'unpaid_sales_invoices', 'overdue_sales_invoices', 'total_invoiced_period',
    'invoice_details', 'customer_invoices', 'draft_invoices', 'top_debtors',
    'recent_invoices', 'unpaid_purchase_invoices', 'overdue_purchase_invoices',
    'supplier_invoices', 'total_purchased_period', 'top_creditors',
    'recent_payments', 'received_payments_period', 'paid_payments_period',
    'customer_payments', 'revenue_period', 'expenses_period', 'net_profit',
    'account_balance', 'financial_summary', 'tax_rates', 'customer_list',
    'supplier_list',

    # Ventes (10)
    'sales_order_status', 'sales_orders_customer', 'sales_invoice_status',
    'customer_info', 'sales_summary',
    'sales_payment_status', 'order_discount', 'cancelled_orders',
    'quotations_for_customer', 'delayed_sales_orders',

    # Achats (7)
    'material_request_status', 'purchase_order_tracking',
    'supplier_details', 'last_purchase_price', 'pending_receipts',
    'purchase_stats_year', 'my_pending_material_requests',

    # Stock (13)
    'stock_availability', 'out_of_stock_items', 'stock_history',
    'last_delivery_note', 'stock_valuation', 'stock_entry_details',
    'batch_info', 'serial_status', 'stock_purchase_requests',
    'items_to_reorder', 'warehouse_details', 'slow_moving_items', 'top_moving_items',

    # RH (11)
    'leave_balance', 'my_absences', 'last_salary_slip', 'attendance_status',
    'team_absent_today', 'expense_claims', 'job_openings',
    'employee_profile', 'upcoming_holidays', 'leave_application_status',
    'employee_directory',

    # Projets (16)
    'project_status', 'project_progress', 'project_details', 'project_list',
    'late_projects', 'projects_by_customer', 'project_cost', 'project_revenue',
    'project_profitability', 'task_list', 'task_status', 'task_details',
    'overdue_tasks', 'billable_hours_by_project',
    'timesheets_by_employee', 'timesheet_details',

    # Système (2)
    'general_chat', 'action_not_supported',
}


# ═══════════════════════════════════════════════════════════
#  FALLBACK — Détection de langue
# ═══════════════════════════════════════════════════════════

def _detect_language(msg):
    en_words = ["invoice", "payment", "unpaid", "overdue", "customer", "supplier",
                "revenue", "expense", "profit", "balance", "draft", "how much",
                "show me", "give me", "what", "which", "list", "hello", "please",
                "create", "delete", "modify", "export", "print", "stock", "leave",
                "project", "task", "timesheet", "employee", "salary", "order"]
    fr_words = ["facture", "paiement", "impayé", "retard", "client", "fournisseur",
                "revenu", "dépense", "bénéfice", "solde", "brouillon", "combien",
                "montre", "donne", "quel", "liste", "bonjour", "svp", "merci",
                "créer", "supprimer", "modifier", "exporter", "imprimer", "stock",
                "congé", "projet", "tâche", "employé", "salaire", "commande"]

    en = sum(1 for w in en_words if w in msg)
    fr = sum(1 for w in fr_words if w in msg)
    return "en" if en > fr else "fr"


# ═══════════════════════════════════════════════════════════
#  DATE RANGE — Conversion période → dates SQL
# ═══════════════════════════════════════════════════════════

def get_date_range(period):
    if not period:
        return None, None

    today = getdate(nowdate())

    if period == "all":
        return None, None

    # ── Plage ISO : YYYY-MM-DD:YYYY-MM-DD ou YYYY-MM:YYYY-MM ─────
    range_match = re.match(r'^(\d{4}-\d{2}(?:-\d{2})?):(\d{4}-\d{2}(?:-\d{2})?)$', str(period))
    if range_match:
        start_raw, end_raw = range_match.group(1), range_match.group(2)
        def parse_partial(s):
            if re.match(r'^\d{4}-\d{2}$', s):
                d = getdate(s + "-01")
                return str(get_first_day(d)), str(get_last_day(d))
            return s, s
        s1, _ = parse_partial(start_raw)
        _, e2 = parse_partial(end_raw)
        return s1, e2

    # ── ISO YYYY-MM ───────────────────────────────────────
    iso_month = re.match(r'^(\d{4})-(\d{2})$', str(period))
    if iso_month:
        d = getdate(period + "-01")
        return str(get_first_day(d)), str(get_last_day(d))

    # ── Périodes relatives ────────────────────────────────
    if period == "today":
        return str(today), str(today)
    elif period == "yesterday":
        yesterday = today - timedelta(days=1)
        return str(yesterday), str(yesterday)
    elif period == "this_week":
        return str(today - timedelta(days=today.weekday())), str(today)
    elif period == "last_week":
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return str(start), str(end)
    elif period == "this_month":
        return str(get_first_day(today)), str(get_last_day(today))
    elif period == "last_month":
        lm = add_months(today, -1)
        return str(get_first_day(lm)), str(get_last_day(lm))
    elif period == "this_quarter":
        q_start_month = ((today.month - 1) // 3) * 3 + 1
        q_start = today.replace(month=q_start_month, day=1)
        return str(q_start), str(today)
    elif period == "last_quarter":
        q_start_month = ((today.month - 1) // 3) * 3 + 1
        lq_end_month = q_start_month - 1 if q_start_month > 1 else 12
        lq_end_year = today.year if q_start_month > 1 else today.year - 1
        lq_start_month = lq_end_month - 2 if lq_end_month > 2 else lq_end_month + 10
        lq_start_year = lq_end_year if lq_end_month > 2 else lq_end_year - 1
        lq_start = today.replace(year=lq_start_year, month=lq_start_month, day=1)
        lq_end = today.replace(year=lq_end_year, month=lq_end_month, day=1)
        return str(lq_start), str(get_last_day(lq_end))
    elif period == "this_year":
        return str(today.replace(month=1, day=1)), str(today)
    elif period == "last_year":
        ly = today.replace(year=today.year - 1)
        return str(ly.replace(month=1, day=1)), str(ly.replace(month=12, day=31))

    # ── Mois nommés ──────────────────────────────────────
    month_names = {
        "january": 1, "janvier": 1, "february": 2, "février": 2, "fevrier": 2,
        "march": 3, "mars": 3, "april": 4, "avril": 4,
        "may": 5, "mai": 5, "june": 6, "juin": 6,
        "july": 7, "juillet": 7, "august": 8, "août": 8, "aout": 8,
        "september": 9, "septembre": 9, "october": 10, "octobre": 10,
        "november": 11, "novembre": 11, "december": 12, "décembre": 12, "decembre": 12,
    }
    month_num = month_names.get(period.lower().strip() if period else "")
    if month_num:
        year = today.year
        if month_num > today.month:
            year -= 1
        d = today.replace(year=year, month=month_num, day=1)
        return str(get_first_day(d)), str(get_last_day(d))

    return None, None
