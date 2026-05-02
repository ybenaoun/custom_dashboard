# chatbot_api.py
# v6 : Service IA unique FastAPI/Cohere, pagination persistante via DocType
# Flow : Message → Classifier FastAPI/Cohere → API Frappe → Réponse
# Pagination : > SMART_THRESHOLD → résumé + top 3 + stockage dans conv.pagination_data
#              "suite" → affiche 5 suivants depuis conv.pagination_data

import frappe
import json
from frappe.utils import now_datetime, flt
from custom_dashboard.services import ai_gateway

# Le vrai intent_classifier ne doit contenir que l'analyse NLU
from custom_dashboard.chatbot.intent_classifier import classify_intent, get_date_range

# Imports des API métiers (vérifiés et alignés)
from custom_dashboard.chatbot.accounting_api import fetch_accounting_data, get_user_info
from custom_dashboard.chatbot.vente_api import fetch_sales_data
from custom_dashboard.chatbot.purchase_api import fetch_purchase_data
from custom_dashboard.chatbot.stock_api import fetch_stock_data
from custom_dashboard.chatbot.hr_api import fetch_hr_data
from custom_dashboard.chatbot.project_api import fetch_project_data

N_CONTEXT_MESSAGES = 10
SMART_THRESHOLD = 8
PAGE_SIZE = 5

CONTINUE_WORDS = [
    "suite", "continue", "continuer", "proceder", "procéder",
    "plus", "encore", "oui", "ok", "d'accord", "daccord",
    "yes", "more", "next", "go", "allez", "vas-y",
    "affiche la suite", "montre la suite", "les autres",
    "le reste", "et les autres", "show more"
]

ACCOUNTING_ROLES = {"Accounts Manager", "Accounts User", "System Manager", "Administrator"}
SALES_ROLES = {"Sales User", "Sales Manager"}
PURCHASE_ROLES = {"Purchase User", "Purchase Manager"}
STOCK_ROLES = {'Stock Manager', 'Stock User'}
HR_ROLES = {'HR Manager', 'HR User', 'Employee Self Service'}

SALES_INTENTS = {"unpaid_sales_invoices", "overdue_sales_invoices", "total_invoiced_period", "invoice_details", "customer_invoices", "draft_invoices", "top_debtors", "recent_invoices", "customer_payments", "customer_list"}

PURCHASE_INTENTS = {"unpaid_purchase_invoices", "overdue_purchase_invoices", "supplier_invoices", "total_purchased_period", "top_creditors", "supplier_list"}

FINANCE_INTENTS = {"revenue_period", "expenses_period", "net_profit", "account_balance", "financial_summary", "tax_rates", "received_payments_period", "paid_payments_period", "recent_payments"}

SALES_MODULE_INTENTS = {
    'sales_order_status', 'sales_orders_customer', 'sales_invoice_status',
    'sales_invoices_customer', 'customer_info', 'sales_summary',
    'sales_payment_status', 'order_discount', 'cancelled_orders',
    'quotations_for_customer', 'delayed_sales_orders'
}

PURCHASE_MODULE_INTENTS = {
    'material_request_status', 'purchase_order_tracking', 'delayed_orders',
    'supplier_details', 'last_purchase_price', 'pending_receipts',
    'purchase_unpaid_invoices', 'purchase_stats_year', 'my_pending_material_requests'
}
STOCK_INTENTS = {
    'stock_availability', 'out_of_stock_items', 'stock_history',
    'last_delivery_note', 'stock_valuation', 'batch_info', 'serial_status',
    'stock_purchase_requests', 'items_to_reorder', 'warehouse_details',
    'slow_moving_items', 'top_moving_items'
}
HR_INTENTS = {
    'leave_balance', 'my_absences', 'last_salary_slip', 'attendance_status',
    'team_absent_today', 'expense_claims', 'job_openings',
    'employee_profile', 'upcoming_holidays', 'leave_application_status',
    'employee_directory'
}
PROJECT_INTENTS = {
    'project_status', 'project_progress', 'project_details', 'project_list',
    'late_projects', 'projects_by_customer', 'project_cost', 'project_revenue',
    'project_profitability', 'task_list', 'task_status', 'task_details',
    'overdue_tasks', 'hours_by_project', 'billable_hours_by_project',
    'timesheets_by_employee', 'timesheet_details'
}
PROJECT_ROLES = {'Projects Manager', 'Projects User'}


SYSTEM_PROMPT_GENERAL = """Tu es un assistant AI intégré dans Wizo ERP.
RÈGLES : Détecte la langue et réponds dans la MÊME langue. Sois concis. Ne fabrique JAMAIS d'informations."""

SYSTEM_PROMPT_ACCOUNTING_FR = "Assistant comptable Wizo ERP. Réponds en français. Utilise UNIQUEMENT les données fournies. Sois concis."
SYSTEM_PROMPT_ACCOUNTING_EN = "Wizo ERP accounting assistant. Respond in English. Use ONLY the provided data. Be concise."


# ═══════════════════════════════════════════════════════════
#  CONVERSATIONS
# ═══════════════════════════════════════════════════════════

@frappe.whitelist()
def get_conversations():
    return frappe.get_all("Chatbot Conversation", filters={"user": frappe.session.user}, fields=["name", "title", "last_message_at", "creation"], order_by="last_message_at DESC", limit_page_length=50)

@frappe.whitelist()
def create_conversation(title=None):
    doc = frappe.get_doc({"doctype": "Chatbot Conversation", "user": frappe.session.user, "title": title or "Nouvelle conversation", "last_message_at": now_datetime()})
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "title": doc.title, "last_message_at": str(doc.last_message_at)}

@frappe.whitelist()
def get_messages(conversation_id):
    conv = frappe.get_doc("Chatbot Conversation", conversation_id)
    if conv.user != frappe.session.user and "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw("Accès non autorisé", frappe.PermissionError)
    return [{"role": m.role, "content": m.content, "timestamp": str(m.timestamp)} for m in conv.messages]

@frappe.whitelist()
def delete_conversation(conversation_id):
    conv = frappe.get_doc("Chatbot Conversation", conversation_id)
    if conv.user != frappe.session.user and "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw("Accès non autorisé", frappe.PermissionError)
    frappe.delete_doc("Chatbot Conversation", conversation_id, ignore_permissions=True)
    frappe.db.commit()
    return {"status": "ok"}

@frappe.whitelist()
def rename_conversation(conversation_id, new_title):
    conv = frappe.get_doc("Chatbot Conversation", conversation_id)
    if conv.user != frappe.session.user and "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw("Accès non autorisé", frappe.PermissionError)
    conv.title = new_title
    conv.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "ok", "title": new_title}


# ═══════════════════════════════════════════════════════════
#  CONTRÔLE D'ACCÈS
# ═══════════════════════════════════════════════════════════

def _check_access(intent, user_roles, language):
    is_fr = language == "fr"
    if "Guest" in user_roles and len(user_roles) <= 2:
        return "🔒 Vous devez être connecté pour accéder aux données comptables." if is_fr else "🔒 You must be logged in to access accounting data."
    has_accounting = bool(user_roles & ACCOUNTING_ROLES)
    has_sales = bool(user_roles & SALES_ROLES)
    has_purchase = bool(user_roles & PURCHASE_ROLES)
    has_stock = bool(user_roles & STOCK_ROLES)
    has_hr = bool(user_roles & HR_ROLES)

    if has_accounting:
        return None

    if intent in SALES_INTENTS and has_sales:
        return None
    if intent in PURCHASE_INTENTS and has_purchase:
        return None

    if intent in STOCK_INTENTS:
        if has_accounting or has_stock:
            return None
        return '🔒 Rôle Stock User ou Stock Manager requis.' if is_fr else '🔒 Stock User or Stock Manager role required.'

    if intent in HR_INTENTS:
        # Les données RH sont personnelles — tout employé accède à SES données
        if has_accounting or has_hr:
            return None
        # Employee Self Service peut voir ses propres données
        if 'Employee Self Service' in user_roles or 'Employee' in user_roles:
            return None
        return '🔒 Accès RH non autorisé.' if is_fr else '🔒 HR access denied.'

    if intent in SALES_MODULE_INTENTS:
        if has_accounting or has_sales:
            return None
        return '🔒 Rôle Sales User requis.' if is_fr else '🔒 Sales User role required.'

    if intent in PURCHASE_MODULE_INTENTS:
        if has_accounting or has_purchase:
            return None
        return '🔒 Rôle Purchase User requis.' if is_fr else '🔒 Purchase User role required.'

    if intent in PROJECT_INTENTS:
        has_project = bool(user_roles & PROJECT_ROLES)
        if has_accounting or has_project:
            return None
        # Tout employé peut voir les projets auxquels il est assigné
        if 'Employee' in user_roles:
            return None
        return '🔒 Rôle Projects User requis.' if is_fr else '🔒 Projects User role required.'

    if intent in SALES_INTENTS and has_purchase and not has_sales:
        return "🔒 Votre rôle **Purchase User** ne permet pas d'accéder aux données de vente." if is_fr else "🔒 Your Purchase User role cannot access sales data."
    if intent in PURCHASE_INTENTS and has_sales and not has_purchase:
        return "🔒 Votre rôle **Sales User** ne permet pas d'accéder aux données d'achat." if is_fr else "🔒 Your Sales User role cannot access purchase data."
    if intent in FINANCE_INTENTS or intent in SALES_INTENTS or intent in PURCHASE_INTENTS:
        return "🔒 Vous n'avez pas les droits pour consulter ces données. Contactez votre administrateur." if is_fr else "🔒 You don't have permissions. Contact your administrator."
    return None


# ═══════════════════════════════════════════════════════════
#  PAGINATION PERSISTANTE (DocType)
# ═══════════════════════════════════════════════════════════

def _is_continue_request(message):
    msg = message.lower().strip().rstrip("?!.")
    for word in CONTINUE_WORDS:
        if msg == word or msg.startswith(word):
            return True
    return False

def _save_pagination(conv, items, data_type, language, currency, total_count):
    conv.pagination_data = json.dumps({"items": items, "data_type": data_type, "language": language, "currency": currency, "total_count": total_count, "displayed": 0}, default=str)
    conv.save(ignore_permissions=True)
    frappe.db.commit()

def _clear_pagination(conv):
    if conv.pagination_data:
        conv.pagination_data = None
        conv.save(ignore_permissions=True)
        frappe.db.commit()

def _get_pagination(conv):
    if not conv.pagination_data:
        return None
    try:
        return json.loads(conv.pagination_data)
    except (json.JSONDecodeError, TypeError):
        return None

def _handle_continue(conv):
    pagination = _get_pagination(conv)
    if not pagination:
        return None

    items = pagination["items"]
    displayed = pagination["displayed"]
    lang = pagination["language"]
    cur = pagination["currency"]
    dt = pagination["data_type"]
    total = pagination["total_count"]
    is_fr = lang == "fr"

    start = displayed
    end = min(displayed + PAGE_SIZE, len(items))
    batch = items[start:end]
    remaining = len(items) - end

    if not batch:
        _clear_pagination(conv)
        return "✅ Tous les résultats ont été affichés." if is_fr else "✅ All results have been displayed."

    lines = []
    page = (displayed // PAGE_SIZE) + 1
    lines.append(f"📄 **Page {page}** — Résultats {start+1} à {end} sur {total} :" if is_fr else f"📄 **Page {page}** — Results {start+1} to {end} of {total}:")
    lines.append("")
    lines.extend(_format_items_as_table(batch, dt, cur))

    if remaining > 0:
        lines.append("")
        lines.append(f"📋 Il reste **{remaining}** résultats. Dites **\"suite\"** pour continuer." if is_fr else f"📋 **{remaining}** remaining. Say **\"more\"** to continue.")
        pagination["displayed"] = end
        conv.pagination_data = json.dumps(pagination, default=str)
        conv.save(ignore_permissions=True)
        frappe.db.commit()
    else:
        _clear_pagination(conv)
        lines.append("")
        lines.append("✅ **Tous les résultats ont été affichés.**" if is_fr else "✅ **All results displayed.**")

    return "\n".join(lines)

def _format_item(item, dt, cur):
    """Retourne une ligne de tableau markdown (sans header)."""
    if dt in ["unpaid_sales_invoices", "overdue_sales_invoices"]:
        days = item.get("days_overdue", "")
        overdue = f"⚠️ {days}j" if days else ""
        return f"| {item.get('name','?')} | {item.get('customer_name','')} | {flt(item.get('outstanding_amount',0)):,.2f} {cur} | {item.get('due_date','?')} | {overdue} |"
    elif dt in ["unpaid_purchase_invoices", "overdue_purchase_invoices"]:
        days = item.get("days_overdue", "")
        overdue = f"⚠️ {days}j" if days else ""
        return f"| {item.get('name','?')} | {item.get('supplier_name','')} | {flt(item.get('outstanding_amount',0)):,.2f} {cur} | {item.get('due_date','?')} | {overdue} |"
    elif dt in ["customer_invoices", "supplier_invoices"]:
        return f"| {item.get('name','?')} | {item.get('posting_date','')} | {flt(item.get('grand_total',0)):,.2f} {cur} | {flt(item.get('outstanding_amount',0)):,.2f} {cur} | {item.get('status','?')} |"
    elif dt in ["recent_payments", "received_payments_period", "paid_payments_period"]:
        if dt == "received_payments_period":
            ptype = "🟢"
        elif dt == "paid_payments_period":
            ptype = "🔴"
        else:
            ptype = "🟢" if item.get("payment_type") == "Receive" else "🔴"
        return f"| {ptype} {item.get('name','?')} | {item.get('party_name','')} | {flt(item.get('paid_amount',0)):,.2f} {cur} | {item.get('posting_date','?')} |"
    elif dt == "recent_invoices":
        t = "Vente" if "SINV" in str(item.get("name","")) else "Achat"
        return f"| {item.get('name','?')} | {t} | {item.get('customer_name', item.get('supplier_name',''))} | {flt(item.get('grand_total',0)):,.2f} {cur} | {item.get('posting_date','?')} |"
    elif dt in ["total_invoiced_period", "total_purchased_period"]:
        return f"| {item.get('name','?')} | {item.get('customer_name', item.get('supplier_name',''))} | {flt(item.get('grand_total',0)):,.2f} {cur} | {item.get('posting_date','?')} |"
    elif dt in ["top_debtors"]:
        return f"| {item.get('customer','')} | {flt(item.get('total_outstanding',0)):,.2f} {cur} | {item.get('invoice_count',0)} |"
    elif dt in ["top_creditors"]:
        return f"| {item.get('supplier','')} | {flt(item.get('total_outstanding',0)):,.2f} {cur} | {item.get('invoice_count',0)} |"
    return f"| {str(item)[:80]} |"


def _table_header(dt):
    """Retourne le header + separator du tableau markdown selon le data_type."""
    headers = {
        "unpaid_sales_invoices":    ("| Facture | Client | Restant | Échéance | Retard |",
                                     "|---------|--------|---------|----------|--------|"),
        "overdue_sales_invoices":   ("| Facture | Client | Restant | Échéance | Retard |",
                                     "|---------|--------|---------|----------|--------|"),
        "unpaid_purchase_invoices": ("| Facture | Fournisseur | Restant | Échéance | Retard |",
                                     "|---------|-------------|---------|----------|--------|"),
        "overdue_purchase_invoices":("| Facture | Fournisseur | Restant | Échéance | Retard |",
                                     "|---------|-------------|---------|----------|--------|"),
        "customer_invoices":        ("| Facture | Date | Total | Restant | Statut |",
                                     "|---------|------|-------|---------|--------|"),
        "supplier_invoices":        ("| Facture | Date | Total | Restant | Statut |",
                                     "|---------|------|-------|---------|--------|"),
        "recent_payments":          ("| Paiement | Tiers | Montant | Date |",
                                     "|----------|-------|---------|------|"),
        "received_payments_period": ("| Paiement | Tiers | Montant | Date |",
                                     "|----------|-------|---------|------|"),
        "paid_payments_period":     ("| Paiement | Tiers | Montant | Date |",
                                     "|----------|-------|---------|------|"),
        "recent_invoices":          ("| Facture | Type | Tiers | Total | Date |",
                                     "|---------|------|-------|-------|------|"),
        "total_invoiced_period":    ("| Facture | Client | Total | Date |",
                                     "|---------|--------|-------|------|"),
        "total_purchased_period":   ("| Facture | Fournisseur | Total | Date |",
                                     "|---------|-------------|-------|------|"),
        "top_debtors":              ("| Client | Dû | Factures |",
                                     "|--------|-----|----------|"),
        "top_creditors":            ("| Fournisseur | Dû | Factures |",
                                     "|-------------|-----|----------|"),
    }
    h = headers.get(dt)
    if h:
        return [h[0], h[1]]
    return []


def _format_items_as_table(items, dt, cur):
    """Formate une liste d'items en tableau markdown complet."""
    lines = _table_header(dt)
    for item in items:
        lines.append(_format_item(item, dt, cur))
    return lines


# ═══════════════════════════════════════════════════════════
#  ENVOI DE MESSAGE — Flow principal
# ═══════════════════════════════════════════════════════════

@frappe.whitelist()
def send_message(message, conversation_id=None):
    if not message or not message.strip():
        return {"response": "Veuillez entrer un message."}
    user = frappe.session.user

    if conversation_id:
        try:
            conv = frappe.get_doc("Chatbot Conversation", conversation_id)
            if conv.user != user and "System Manager" not in frappe.get_roles(user):
                frappe.throw("Accès non autorisé", frappe.PermissionError)
        except frappe.DoesNotExistError:
            conv = _create_new_conversation(user, message)
    else:
        conv = _create_new_conversation(user, message)

    conv.append("messages", {"role": "user", "content": message.strip(), "timestamp": now_datetime()})
    conv.last_message_at = now_datetime()
    conv.save(ignore_permissions=True)
    frappe.db.commit()

    # ─── ÉTAPE 0 : Pagination — suite demandée ? ───
    if _is_continue_request(message):
        bot_response = _handle_continue(conv)
        if bot_response:
            _save_and_return(conv, bot_response)
            return {"response": bot_response, "conversation_id": conv.name, "conversation_title": conv.title}
        else:
            # P9 — Pas de pagination active → message clair
            is_fr = True  # Détection basique
            en_words = ["more", "next", "continue", "yes", "go", "show more"]
            if message.lower().strip() in en_words:
                is_fr = False
            no_data_msg = "Pas de données en attente. Posez une nouvelle question." if is_fr else "No pending data. Ask a new question."
            _save_and_return(conv, no_data_msg)
            return {"response": no_data_msg, "conversation_id": conv.name, "conversation_title": conv.title}

    # ─── Nouvelle question → effacer pagination ───
    _clear_pagination(conv)

    # ─── ÉTAPE 1 : Classifier ───
    classification = classify_intent(message)
    intent = classification["intent"]
    period = classification["period"]
    language = classification["language"]
    entity = classification.get("entity")

    # ─── P4 : Détection multi-intent ───
    second_hint = _detect_multi_intent(message, intent, language)

    # ─── ÉTAPE 1b : Contrôle d'accès ───
    if intent not in ("general_chat", "action_not_supported"):
        user_info = get_user_info()
        user_roles = set(user_info["roles"])
        access_denied = _check_access(intent, user_roles, language)
        if access_denied:
            _save_and_return(conv, access_denied)
            return {"response": access_denied, "conversation_id": conv.name, "conversation_title": conv.title}

    # ─── ÉTAPE 1c : Action non supportée → guide navigation ───
    if intent == "action_not_supported":
        bot_response = _handle_action_not_supported(entity, language)
        _save_and_return(conv, bot_response)
        return {"response": bot_response, "conversation_id": conv.name, "conversation_title": conv.title}

    # ─── ÉTAPE 2 : Fetch données ───
    data = None
    if intent != 'general_chat':
        from_date, to_date = get_date_range(period)
        if intent in STOCK_INTENTS:
            data = fetch_stock_data(intent=intent, entity=entity)
        elif intent in HR_INTENTS:
            data = fetch_hr_data(intent=intent, entity=entity)
        elif intent in SALES_MODULE_INTENTS:
            data = fetch_sales_data(intent=intent,
                                  from_date=from_date, to_date=to_date, entity=entity)
        elif intent in PURCHASE_MODULE_INTENTS:
            data = fetch_purchase_data(intent=intent,
                                  from_date=from_date, to_date=to_date, entity=entity)
        elif intent in PROJECT_INTENTS:
            data = fetch_project_data(intent=intent,
                                  from_date=from_date, to_date=to_date, entity=entity)
        else:
            # Fallback → comptabilité (accounting_api)
            data = fetch_accounting_data(intent=intent,
                                  from_date=from_date, to_date=to_date, entity=entity)

    # ─── ÉTAPE 2b : Volume de données ───
    data_count = _data_count(data) if data else 0

    if data and data_count > SMART_THRESHOLD:
        bot_response = _generate_smart_summary(conv, data, language)
    elif data:
        bot_response = _generate_accounting_response(message, data, language)
    else:
        bot_response = _generate_general_response(message, conv)

    # P4 — Ajouter suggestion multi-intent si détecté
    if second_hint:
        bot_response += f"\n\n{second_hint}"

    _save_and_return(conv, bot_response)
    return {"response": bot_response, "conversation_id": conv.name, "conversation_title": conv.title}


def _save_and_return(conv, bot_response):
    conv.append("messages", {"role": "bot", "content": bot_response, "timestamp": now_datetime()})
    conv.last_message_at = now_datetime()
    conv.save(ignore_permissions=True)
    frappe.db.commit()


# ═══════════════════════════════════════════════════════════
#  ACTION NON SUPPORTÉE — Guides de navigation ERP
# ═══════════════════════════════════════════════════════════

NAVIGATION_GUIDES = {
    "sales_invoice": {
        "fr": "Comptabilité → Facture de vente → + Nouveau",
        "en": "Accounting → Sales Invoice → + New",
        "label_fr": "une facture de vente",
        "label_en": "a sales invoice",
    },
    "purchase_invoice": {
        "fr": "Comptabilité → Facture d'achat → + Nouveau",
        "en": "Accounting → Purchase Invoice → + New",
        "label_fr": "une facture d'achat",
        "label_en": "a purchase invoice",
    },
    "customer": {
        "fr": "Vente → Client → + Nouveau",
        "en": "Selling → Customer → + New",
        "label_fr": "un client",
        "label_en": "a customer",
    },
    "supplier": {
        "fr": "Achat → Fournisseur → + Nouveau",
        "en": "Buying → Supplier → + New",
        "label_fr": "un fournisseur",
        "label_en": "a supplier",
    },
    "payment_entry": {
        "fr": "Comptabilité → Écriture de paiement → + Nouveau",
        "en": "Accounting → Payment Entry → + New",
        "label_fr": "un paiement",
        "label_en": "a payment",
    },
    "journal_entry": {
        "fr": "Comptabilité → Écriture de journal → + Nouveau",
        "en": "Accounting → Journal Entry → + New",
        "label_fr": "une écriture comptable",
        "label_en": "a journal entry",
    },
    "quotation": {
        "fr": "Vente → Devis → + Nouveau",
        "en": "Selling → Quotation → + New",
        "label_fr": "un devis",
        "label_en": "a quotation",
    },
    "sales_order": {
        "fr": "Vente → Commande client → + Nouveau",
        "en": "Selling → Sales Order → + New",
        "label_fr": "une commande client",
        "label_en": "a sales order",
    },
    "purchase_order": {
        "fr": "Achat → Commande fournisseur → + Nouveau",
        "en": "Buying → Purchase Order → + New",
        "label_fr": "une commande fournisseur",
        "label_en": "a purchase order",
    },
    "item": {
        "fr": "Stock → Article → + Nouveau",
        "en": "Stock → Item → + New",
        "label_fr": "un article",
        "label_en": "an item",
    },
    "delivery_note": {
        "fr": "Stock → Bon de livraison → + Nouveau",
        "en": "Stock → Delivery Note → + New",
        "label_fr": "un bon de livraison",
        "label_en": "a delivery note",
    },
    "purchase_receipt": {
        "fr": "Stock → Bon de réception → + Nouveau",
        "en": "Stock → Purchase Receipt → + New",
        "label_fr": "un bon de réception",
        "label_en": "a purchase receipt",
    },
    "report": {
        "fr": "Comptabilité → Rapports → Menu (⋯) → Exporter",
        "en": "Accounting → Reports → Menu (⋯) → Export",
        "label_fr": "un rapport/export",
        "label_en": "a report/export",
    },
}

def _handle_action_not_supported(entity, language):
    """Retourne un message de guide navigation pour les actions non supportées."""
    is_fr = language == "fr"
    guide = NAVIGATION_GUIDES.get(entity)

    if guide:
        path = guide["fr"] if is_fr else guide["en"]
        label = guide["label_fr"] if is_fr else guide["label_en"]
        if is_fr:
            return f"🔒 Je suis un assistant en **lecture seule** — je ne peux pas gérer {label}.\n\n👉 **{path}**\n\nJe peux consulter vos données si vous avez besoin d'informations."
        else:
            return f"🔒 I'm a **read-only** assistant — I cannot manage {label}.\n\n👉 **{path}**\n\nI can look up your data if you need information."
    else:
        if is_fr:
            return "🔒 Je suis un assistant en **lecture seule** — je peux consulter vos données comptables mais je ne peux pas créer, modifier ou supprimer des éléments.\n\nPour effectuer cette action, utilisez directement l'interface Wizo ERP."
        else:
            return "🔒 I'm a **read-only** assistant — I can look up your accounting data but I cannot create, modify or delete records.\n\nTo perform this action, please use the Wizo ERP interface directly."


# ═══════════════════════════════════════════════════════════
#  P4 — MULTI-INTENT DETECTION
# ═══════════════════════════════════════════════════════════

MULTI_INTENT_HINTS = {
    "fr": {
        "impayé": ("factures impayées", "factures impayées"),
        "retard": ("factures en retard", "factures en retard"),
        "résultat": ("résultat net", "résultat net"),
        "bénéfice": ("bénéfice net", "résultat net"),
        "profit": ("profit", "résultat net"),
        "revenu": ("revenus", "chiffre d'affaires"),
        "chiffre": ("chiffre d'affaires", "chiffre d'affaires"),
        "dépense": ("dépenses", "total des dépenses"),
        "encaissement": ("encaissements", "encaissements"),
        "décaissement": ("décaissements", "décaissements"),
        "paiement": ("paiements", "derniers paiements"),
        "solde": ("solde", "solde bancaire"),
        "résumé": ("résumé financier", "résumé financier"),
        "bilan": ("bilan", "résumé financier"),
        "brouillon": ("brouillons", "factures brouillons"),
        "fournisseur": ("fournisseurs", "factures fournisseur impayées"),
        "client": ("clients", "factures client impayées"),
    },
    "en": {
        "unpaid": ("unpaid invoices", "unpaid invoices"),
        "overdue": ("overdue invoices", "overdue invoices"),
        "profit": ("net profit", "net profit"),
        "revenue": ("revenue", "revenue"),
        "expense": ("expenses", "total expenses"),
        "payment": ("payments", "recent payments"),
        "balance": ("balance", "account balance"),
        "summary": ("financial summary", "financial summary"),
        "draft": ("drafts", "draft invoices"),
    }
}

def _detect_multi_intent(message, first_intent, language):
    """Détecte si le message contient un 2ème intent séparé par 'et/and/aussi'."""
    msg = message.lower()
    separators = [" et ", " and ", " aussi ", " également ", " plus ", " ainsi que "]
    sep_found = None
    sep_pos = -1
    for sep in separators:
        pos = msg.find(sep)
        if pos > 0:
            sep_found = sep
            sep_pos = pos
            break

    if not sep_found:
        return None

    second_part = msg[sep_pos + len(sep_found):].strip()
    if not second_part or len(second_part) < 3:
        return None

    lang = "fr" if language == "fr" else "en"
    hints = MULTI_INTENT_HINTS.get(lang, {})
    for keyword, (label, suggestion) in hints.items():
        if keyword in second_part:
            is_fr = language == "fr"
            return f"💡 {'Pour' if is_fr else 'For'} {label}, {'demandez' if is_fr else 'ask'} : \"{suggestion}\""

    return None


# ═══════════════════════════════════════════════════════════
#  RÉSUMÉ INTELLIGENT + PAGINATION
# ═══════════════════════════════════════════════════════════

def _generate_smart_summary(conv, data, language):
    dt = data.get("data_type", "")
    cur = data.get("currency", "TND")
    count = _data_count(data)
    is_fr = language == "fr"

    all_items = _extract_all_items(data)
    all_items = _sort_items(all_items, dt)

    lines = [_build_header(data, dt, cur, is_fr, count)]
    lines.append("")

    top3 = all_items[:3]
    if top3:
        lines.append("🏆 **Top 3 :**" if is_fr else "🏆 **Top 3:**")
        lines.extend(_format_items_as_table(top3, dt, cur))
        lines.append("")

    lines.append(_build_filter_suggestions(dt, data, is_fr))
    lines.append("")

    remaining = len(all_items) - 3
    if remaining > 0:
        lines.append(f"📋 Il reste **{remaining}** résultats. Dites **\"suite\"** pour afficher les 5 suivants." if is_fr else f"📋 **{remaining}** remaining. Say **\"more\"** to see the next 5.")

    _save_pagination(conv, all_items, dt, language, cur, len(all_items))
    pagination = _get_pagination(conv)
    if pagination:
        pagination["displayed"] = 3
        conv.pagination_data = json.dumps(pagination, default=str)
        conv.save(ignore_permissions=True)
        frappe.db.commit()

    return "\n".join(lines)


def _extract_all_items(data):
    dt = data.get("data_type", "")
    if dt in ["unpaid_sales_invoices", "overdue_sales_invoices", "unpaid_purchase_invoices", "overdue_purchase_invoices", "customer_invoices", "supplier_invoices"]:
        return list(data.get("invoices", []))
    elif dt == "recent_invoices":
        return list(data.get("sales_invoices", [])) + list(data.get("purchase_invoices", []))
    elif dt in ["recent_payments", "received_payments_period", "paid_payments_period"]:
        return list(data.get("payments", []))
    elif dt in ["total_invoiced_period", "total_purchased_period"]:
        return list(data.get("invoices", []))
    return []

def _sort_items(items, dt):
    if dt in ["unpaid_sales_invoices", "overdue_sales_invoices", "unpaid_purchase_invoices", "overdue_purchase_invoices"]:
        return sorted(items, key=lambda x: flt(x.get("outstanding_amount", 0)), reverse=True)
    elif dt in ["customer_invoices", "supplier_invoices", "total_invoiced_period", "total_purchased_period", "recent_invoices"]:
        return sorted(items, key=lambda x: flt(x.get("grand_total", 0)), reverse=True)
    elif dt in ["recent_payments", "received_payments_period", "paid_payments_period"]:
        return sorted(items, key=lambda x: flt(x.get("paid_amount", 0)), reverse=True)
    return items

def _build_header(data, dt, cur, is_fr, count):
    if dt == "unpaid_sales_invoices":
        t = data.get("total_outstanding", 0)
        return f"📋 **{count} factures impayées** — Total : **{t:,.2f} {cur}**" if is_fr else f"📋 **{count} unpaid invoices** — Total: **{t:,.2f} {cur}**"
    elif dt == "overdue_sales_invoices":
        t = data.get("total_overdue", 0)
        return f"⚠️ **{count} factures en retard** — Total : **{t:,.2f} {cur}**" if is_fr else f"⚠️ **{count} overdue invoices** — Total: **{t:,.2f} {cur}**"
    elif dt == "unpaid_purchase_invoices":
        t = data.get("total_outstanding", 0)
        return f"📋 **{count} factures fournisseur impayées** — Total : **{t:,.2f} {cur}**" if is_fr else f"📋 **{count} unpaid supplier invoices** — Total: **{t:,.2f} {cur}**"
    elif dt == "overdue_purchase_invoices":
        t = data.get("total_overdue", 0)
        return f"⚠️ **{count} factures fournisseur en retard** — Total : **{t:,.2f} {cur}**" if is_fr else f"⚠️ **{count} overdue supplier invoices** — Total: **{t:,.2f} {cur}**"
    elif dt in ["customer_invoices", "supplier_invoices"]:
        party = data.get("customer") or data.get("supplier", "?")
        t = data.get("total_invoiced", 0)
        o = data.get("total_outstanding", 0)
        return f"📋 **{party}** — {count} factures | Total : **{t:,.2f} {cur}** | Impayé : **{o:,.2f} {cur}**" if is_fr else f"📋 **{party}** — {count} invoices | Total: **{t:,.2f} {cur}** | Outstanding: **{o:,.2f} {cur}**"
    elif dt in ["recent_payments", "received_payments_period", "paid_payments_period"]:
        tr = data.get("total_received", 0)
        tp = data.get("total_paid", 0)
        if dt == "received_payments_period":
            return f"🟢 **{count} encaissements** — Total : **{tr:,.2f} {cur}**" if is_fr else f"🟢 **{count} received** — Total: **{tr:,.2f} {cur}**"
        elif dt == "paid_payments_period":
            return f"🔴 **{count} décaissements** — Total : **{tp:,.2f} {cur}**" if is_fr else f"🔴 **{count} payments** — Total: **{tp:,.2f} {cur}**"
        return f"📋 **{count} paiements** — Encaissé : **{tr:,.2f} {cur}** | Décaissé : **{tp:,.2f} {cur}**" if is_fr else f"📋 **{count} payments** — In: **{tr:,.2f} {cur}** | Out: **{tp:,.2f} {cur}**"
    elif dt == "recent_invoices":
        return f"📋 **{count} factures récentes** ({data.get('sales_count',0)} vente + {data.get('purchase_count',0)} achat)" if is_fr else f"📋 **{count} recent invoices**"
    elif dt in ["total_invoiced_period", "total_purchased_period"]:
        t = data.get("total_grand", 0)
        return f"📋 **{count} factures** — Total : **{t:,.2f} {cur}**" if is_fr else f"📋 **{count} invoices** — Total: **{t:,.2f} {cur}**"
    return f"📋 **{count} résultats**" if is_fr else f"📋 **{count} results**"

def _build_filter_suggestions(dt, data, is_fr):
    if not is_fr:
        return "To refine: filter by customer/supplier name or period (this month, this year)."
    if dt in ["unpaid_sales_invoices", "overdue_sales_invoices"]:
        return "Pour affiner :\n- \"factures impayées de **[nom du client]**\"\n- \"factures en retard **ce mois**\"\n- \"quels clients doivent le plus\""
    elif dt in ["unpaid_purchase_invoices", "overdue_purchase_invoices"]:
        return "Pour affiner :\n- \"factures de **[nom du fournisseur]**\"\n- \"quels fournisseurs on doit le plus\""
    elif dt in ["recent_payments", "received_payments_period", "paid_payments_period"]:
        return "Pour affiner :\n- \"paiements de **[nom]**\"\n- \"encaissements **ce mois**\"\n- \"décaissements **ce mois**\""
    elif dt in ["customer_invoices", "supplier_invoices"]:
        party = data.get("customer") or data.get("supplier", "...")
        return f"Pour affiner :\n- \"factures impayées de {party}\"\n- \"factures de {party} **ce mois**\""
    elif dt in ["total_invoiced_period", "total_purchased_period"]:
        return "Pour affiner :\n- \"factures de **[nom du client]**\"\n- \"combien on a facturé **ce mois**\""
    elif dt == "recent_invoices":
        return "Pour affiner :\n- \"factures de **[nom du client]**\"\n- \"factures impayées\""
    return "Précisez par client, fournisseur ou période."


# ═══════════════════════════════════════════════════════════
#  COMPTEUR
# ═══════════════════════════════════════════════════════════

def _data_count(data):
    if not data:
        return 0
    dt = data.get("data_type", "")
    if dt in ["unpaid_sales_invoices", "overdue_sales_invoices", "unpaid_purchase_invoices", "overdue_purchase_invoices"]:
        return data.get("count", 0)
    if dt == "recent_invoices":
        return data.get("sales_count", 0) + data.get("purchase_count", 0)
    if dt in ["recent_payments", "received_payments_period", "paid_payments_period", "total_invoiced_period", "total_purchased_period", "customer_invoices", "supplier_invoices"]:
        return data.get("count", 0)
    return 0


# ═══════════════════════════════════════════════════════════
#  RÉPONSES VIA SERVICE IA UNIQUE FASTAPI/COHERE
# ═══════════════════════════════════════════════════════════

def _chat_endpoint():
    return (frappe.conf or {}).get("chatbot_fastapi_chat_endpoint") or "/chat"


def _call_fastapi_chat(messages, language="fr", timeout=120):
    if not messages:
        return ""

    user_message = messages[-1].get("content") or ""
    history = [
        {"role": row.get("role") or "user", "content": row.get("content") or ""}
        for row in messages[:-1]
        if row.get("content")
    ]
    payload = {
        "message": user_message,
        "language": language if language in {"fr", "en"} else "fr",
        "history": history,
    }
    result = ai_gateway.post_json(_chat_endpoint(), payload, timeout=timeout)
    response = result.get("response") or result.get("content") or result.get("message") or ""
    if isinstance(response, dict):
        return json.dumps(response, ensure_ascii=False)
    return str(response or "")

def _generate_accounting_response(question, data, language):
    data_text = _format_data_for_prompt(data)
    system_prompt = SYSTEM_PROMPT_ACCOUNTING_EN if language == "en" else SYSTEM_PROMPT_ACCOUNTING_FR
    user_content = f"{question}\n\nDonnées:\n{data_text}"
    try:
        bot = _call_fastapi_chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            language=language,
        )
        return bot if bot else "Désolé, je n'ai pas pu analyser les données."
    except ai_gateway.AIServiceError:
        return "Le service AI n'est pas disponible."
    except Exception as e:
        frappe.log_error(f"Chatbot Error: {str(e)}", "Chatbot Error")
        return "Une erreur inattendue s'est produite."

def _generate_general_response(question, conv):
    messages = [{"role": "system", "content": SYSTEM_PROMPT_GENERAL}]
    start_idx = max(0, len(conv.messages) - N_CONTEXT_MESSAGES)
    for msg in conv.messages[start_idx:]:
        messages.append({"role": "user" if msg.role == "user" else "assistant", "content": msg.content})
    try:
        bot = _call_fastapi_chat(messages, language="fr")
        return bot if bot else "Désolé, je n'ai pas pu générer de réponse."
    except ai_gateway.AIServiceError:
        return "Le service AI n'est pas disponible."
    except Exception as e:
        frappe.log_error(f"Chatbot Error: {str(e)}", "Chatbot Error")
        return "Une erreur inattendue s'est produite."


# ═══════════════════════════════════════════════════════════
#  FORMATAGE DONNÉES POUR LLM (≤8 items)
# ═══════════════════════════════════════════════════════════

def _format_data_for_prompt(data):
    dt = data.get("data_type", "")
    cur = data.get("currency", "TND")
    lines = []
    MAX = 8

    def ps():
        if data.get("from_date") and data.get("to_date"):
            return f" (du {data['from_date']} au {data['to_date']})"
        return ""

    if dt == "unpaid_sales_invoices":
        lines.append(f"Factures impayées : {data['count']} | Total : {data['total_outstanding']:.2f} {cur}")
        lines.extend(_table_header(dt))
        for i in data.get("invoices", [])[:MAX]:
            lines.append(f"| {i['name']} | {i.get('customer_name','')} | {flt(i['outstanding_amount']):.2f} {cur} | {i['due_date']} | |")
    elif dt == "overdue_sales_invoices":
        lines.append(f"Factures en retard : {data['count']} | Total : {data['total_overdue']:.2f} {cur}")
        lines.extend(_table_header(dt))
        for i in data.get("invoices", [])[:MAX]:
            lines.append(f"| {i['name']} | {i.get('customer_name','')} | {flt(i['outstanding_amount']):.2f} {cur} | {i['due_date']} | {i.get('days_overdue','?')}j |")
    elif dt == "total_invoiced_period":
        lines.append(f"Total facturé{ps()} : {data['total_grand']:.2f} {cur}")
        lines.append(f"HT: {data['total_net']:.2f} | Taxes: {data['total_taxes']:.2f} | Payé: {data['total_paid']:.2f} | Restant: {data['total_outstanding']:.2f} {cur}")
        lines.extend(_table_header(dt))
        for i in data.get("invoices", [])[:MAX]:
            lines.append(f"| {i['name']} | {i.get('customer_name','')} | {flt(i['grand_total']):.2f} {cur} | {i['posting_date']} |")
    elif dt == "invoice_details":
        if data.get("error"):
            lines.append(data.get("message", "Erreur"))
        else:
            party = data.get("customer") or data.get("supplier", "N/A")
            lines.append(f"Type: {data.get('invoice_type','')} | N°: {data['name']} | {'Client' if 'customer' in data else 'Fournisseur'}: {party}")
            lines.append(f"Date: {data['posting_date']} | Échéance: {data['due_date']} | Statut: {data['status']}")
            lines.append(f"HT: {data['net_total']:.2f} | Taxes: {data['total_taxes']:.2f} | TTC: {data['grand_total']:.2f} {cur}")
            lines.append(f"Payé: {data['paid_amount']:.2f} | Restant: {data['outstanding_amount']:.2f} {cur}")
            if data.get("items"):
                lines.append("")
                lines.append("| Article | Qté | Prix | Total |")
                lines.append("|---------|-----|------|-------|")
                for it in data["items"]:
                    lines.append(f"| {it['item_name']} | {it['qty']} | {it['rate']:.2f} | {it['amount']:.2f} {cur} |")
    elif dt == "customer_invoices":
        if data.get("error"):
            lines.append(data.get("message", "Erreur"))
        else:
            lines.append(f"Client: {data['customer']} | {data['count']} factures | Total: {data['total_invoiced']:.2f} | Impayé: {data['total_outstanding']:.2f} {cur}")
            lines.extend(_table_header(dt))
            for i in data.get("invoices", [])[:MAX]:
                lines.append(f"| {i['name']} | {i['posting_date']} | {flt(i['grand_total']):.2f} {cur} | {flt(i['outstanding_amount']):.2f} {cur} | {i['status']} |")
    elif dt == "draft_invoices":
        lines.append(f"Brouillons vente: {data['sales_count']} ({data['total_sales_draft']:.2f} {cur})")
        if data.get("sales_drafts"):
            lines.append("| Facture | Client | Total |")
            lines.append("|---------|--------|-------|")
            for i in data.get("sales_drafts", []):
                lines.append(f"| {i['name']} | {i.get('customer_name','')} | {flt(i['grand_total']):.2f} {cur} |")
        lines.append(f"Brouillons achat: {data['purchase_count']} ({data['total_purchase_draft']:.2f} {cur})")
        if data.get("purchase_drafts"):
            lines.append("| Facture | Fournisseur | Total |")
            lines.append("|---------|-------------|-------|")
            for i in data.get("purchase_drafts", []):
                lines.append(f"| {i['name']} | {i.get('supplier_name','')} | {flt(i['grand_total']):.2f} {cur} |")
    elif dt == "top_debtors":
        lines.append(f"Top clients endettés ({data['count']}, total: {data['total_debt']:.2f} {cur}):")
        lines.extend(_table_header(dt))
        for d in data.get("debtors", []):
            lines.append(f"| {d['customer']} | {d['total_outstanding']:.2f} {cur} | {d['invoice_count']} |")
    elif dt == "recent_invoices":
        lines.append(f"Dernières factures ({data['sales_count']} vente + {data['purchase_count']} achat):")
        lines.extend(_table_header(dt))
        for i in data.get("sales_invoices", [])[:MAX]:
            lines.append(f"| {i['name']} | Vente | {i.get('customer_name','')} | {flt(i['grand_total']):.2f} {cur} | {i['posting_date']} |")
        for i in data.get("purchase_invoices", [])[:MAX]:
            lines.append(f"| {i['name']} | Achat | {i.get('supplier_name','')} | {flt(i['grand_total']):.2f} {cur} | {i['posting_date']} |")
    elif dt == "unpaid_purchase_invoices":
        lines.append(f"Factures fournisseur impayées: {data['count']} | Total: {data['total_outstanding']:.2f} {cur}")
        lines.extend(_table_header(dt))
        for i in data.get("invoices", [])[:MAX]:
            lines.append(f"| {i['name']} | {i.get('supplier_name','')} | {flt(i['outstanding_amount']):.2f} {cur} | {i['due_date']} | |")
    elif dt == "overdue_purchase_invoices":
        lines.append(f"Factures fournisseur en retard: {data['count']} | Total: {data['total_overdue']:.2f} {cur}")
        lines.extend(_table_header(dt))
        for i in data.get("invoices", [])[:MAX]:
            lines.append(f"| {i['name']} | {i.get('supplier_name','')} | {flt(i['outstanding_amount']):.2f} {cur} | {i['due_date']} | {i.get('days_overdue','?')}j |")
    elif dt == "supplier_invoices":
        if data.get("error"):
            lines.append(data.get("message", "Erreur"))
        else:
            lines.append(f"Fournisseur: {data['supplier']} | {data['count']} factures | Total: {data['total_invoiced']:.2f} | Impayé: {data['total_outstanding']:.2f} {cur}")
            lines.extend(_table_header(dt))
            for i in data.get("invoices", [])[:MAX]:
                lines.append(f"| {i['name']} | {i['posting_date']} | {flt(i['grand_total']):.2f} {cur} | {flt(i['outstanding_amount']):.2f} {cur} | |")
    elif dt == "total_purchased_period":
        lines.append(f"Total achats{ps()}: {data['total_grand']:.2f} {cur}")
        lines.append(f"HT: {data['total_net']:.2f} | Taxes: {data['total_taxes']:.2f} | Payé: {data['total_paid']:.2f} | Restant: {data['total_outstanding']:.2f} {cur}")
    elif dt == "top_creditors":
        lines.append(f"Top fournisseurs à payer ({data['count']}, total: {data['total_debt']:.2f} {cur}):")
        lines.extend(_table_header(dt))
        for c in data.get("creditors", [])[:MAX]:
            lines.append(f"| {c['supplier']} | {c['total_outstanding']:.2f} {cur} | {c['invoice_count']} |")
    elif dt == "recent_payments":
        lines.append(f"Paiements{ps()}: Encaissé: {data['total_received']:.2f} | Décaissé: {data['total_paid']:.2f} {cur} | Total: {data['count']}")
        lines.extend(_table_header(dt))
        for p in data.get("payments", [])[:MAX]:
            t = "🟢" if p["payment_type"] == "Receive" else "🔴"
            lines.append(f"| {t} {p['name']} | {p.get('party_name','')} | {flt(p['paid_amount']):.2f} {cur} | {p['posting_date']} |")
    elif dt == "received_payments_period":
        lines.append(f"Encaissements{ps()}: {data['count']} paiements | Total: {data['total_received']:.2f} {cur}")
        lines.extend(_table_header(dt))
        for p in data.get("payments", [])[:MAX]:
            lines.append(f"| 🟢 {p['name']} | {p.get('party_name','')} | {flt(p['paid_amount']):.2f} {cur} | {p['posting_date']} |")
    elif dt == "paid_payments_period":
        lines.append(f"Décaissements{ps()}: {data['count']} paiements | Total: {data['total_paid']:.2f} {cur}")
        lines.extend(_table_header(dt))
        for p in data.get("payments", [])[:MAX]:
            lines.append(f"| 🔴 {p['name']} | {p.get('party_name','')} | {flt(p['paid_amount']):.2f} {cur} | {p['posting_date']} |")
    elif dt == "customer_payments":
        if data.get("error"):
            lines.append(data.get("message", "Erreur"))
        else:
            lines.append(f"Paiements de {data['party_name']}{ps()}: {data['count']} paiements")
            lines.append(f"Total reçu: {data['total_received']:.2f} | Total payé: {data['total_paid']:.2f} {cur}")
            lines.extend(_table_header(dt))
            for p in data.get("payments", [])[:MAX]:
                t = "🟢" if p["payment_type"] == "Receive" else "🔴"
                lines.append(f"| {t} {p['name']} | {p.get('party_name','')} | {flt(p['paid_amount']):.2f} {cur} | {p['posting_date']} |")
    elif dt == "revenue_period":
        lines.append(f"CA{ps()}: {data['total_revenue']:.2f} {cur}")
        lines.append(f"Dépenses: {data['total_expenses']:.2f} | Résultat net: {data['net_profit']:.2f} {cur}")
        if data.get("details"):
            lines.append("")
            lines.append("| Compte | Montant |")
            lines.append("|--------|---------|")
            for d in data["details"][:8]:
                lines.append(f"| {d['account']} | {d['amount']:.2f} {cur} |")
    elif dt == "expenses_period":
        lines.append(f"Total dépenses{ps()}: {data['total_expenses']:.2f} {cur}")
        if data.get("details"):
            lines.append("")
            lines.append("| Compte | Montant |")
            lines.append("|--------|---------|")
            for d in data["details"][:8]:
                lines.append(f"| {d['account']} | {d['amount']:.2f} {cur} |")
    elif dt == "net_profit":
        lines.append(f"Résultat financier{ps()}:")
        lines.append(f"Revenus: {data['total_revenue']:.2f} {cur}")
        lines.append(f"Dépenses: {data['total_expenses']:.2f} {cur}")
        profit = data['net_profit']
        lines.append(f"{'Bénéfice' if profit >= 0 else 'Perte'}: {abs(profit):.2f} {cur}")
    elif dt == "account_balance":
        if data.get("error"):
            lines.append(data.get("message", "Erreur"))
        elif data.get("multiple"):
            lines.append(f"Comptes ({data['count']}):")
            lines.append("| Compte | Solde |")
            lines.append("|--------|-------|")
            for a in data.get("accounts", []):
                lines.append(f"| {a['account']} | {a['balance']:.2f} {cur} |")
        else:
            lines.append(f"Compte: {data['account']} ({data['root_type']})")
            lines.append(f"Débit: {data['total_debit']:.2f} | Crédit: {data['total_credit']:.2f} {cur}")
            lines.append(f"Solde: {data['balance']:.2f} {cur}")
            if data.get("recent_entries"):
                lines.append("")
                lines.append("| Date | Type | Réf | Débit | Crédit |")
                lines.append("|------|------|-----|-------|--------|")
                for e in data["recent_entries"][:5]:
                    lines.append(f"| {e['posting_date']} | {e['voucher_type']} | {e['voucher_no']} | {flt(e['debit']):.2f} | {flt(e['credit']):.2f} {cur} |")
    elif dt == "financial_summary":
        if data.get("from_date") and data.get("to_date"):
            period_str = f" (du {data['from_date']} au {data['to_date']})"
        else:
            period_str = " (depuis le début)"
        lines.append(f"RÉSUMÉ FINANCIER{period_str}")
        lines.append("")
        lines.append("| Catégorie | Montant |")
        lines.append("|-----------|---------|")
        lines.append(f"| Actifs | {data['assets']:,.2f} {cur} |")
        lines.append(f"| Passifs | {data['liabilities']:,.2f} {cur} |")
        lines.append(f"| Capitaux | {data['equity']:,.2f} {cur} |")
        lines.append(f"| Revenus | {data['income']:,.2f} {cur} |")
        lines.append(f"| Dépenses | {data['expenses']:,.2f} {cur} |")
        profit = data['net_profit']
        lines.append(f"| {'Bénéfice' if profit >= 0 else 'Perte'} | {abs(profit):,.2f} {cur} |")
    elif dt == "tax_rates":
        lines.append(f"Taxes ({data['sales_count']}):")
        for t in data.get("sales_taxes", []):
            default = " [DÉFAUT]" if t.get("is_default") else ""
            lines.append(f"**{t['name']}{default}**")
            lines.append("| Description | Taux |")
            lines.append("|-------------|------|")
            for r in t.get("rates", []):
                lines.append(f"| {r['description']} | {r['rate']}% |")
    elif dt == "customer_list":
        lines.append(f"Clients ({data['count']}):")
        lines.append("| Client |")
        lines.append("|--------|")
        for c in data.get("customers", []):
            lines.append(f"| {c['customer_name']} |")
    elif dt == "supplier_list":
        lines.append(f"Fournisseurs ({data['count']}):")
        lines.append("| Fournisseur |")
        lines.append("|-------------|")
        for s in data.get("suppliers", []):
            lines.append(f"| {s['supplier_name']} |")

    # ── MODULE VENTE ──
    elif dt in ['sales_order_status', 'sales_orders_customer']:
        party = data.get('customer', '')
        lines.append(f"Commandes vente {('- ' + party) if party else ''}: {data['count']}")
        lines.append('| Commande | Client | Date | Statut | Total |')
        lines.append('|----------|--------|------|--------|-------|')
        for i in data.get('items', [])[:MAX]:
            lines.append(f"| {i['name']} | {i.get('customer','')} | {i.get('transaction_date','')} | {i.get('status','')} | {flt(i.get('grand_total',0)):,.2f} {cur} |")


    elif dt in ['sales_invoice_status', 'sales_invoices_customer']:
        party = data.get('customer', '')
        total = data.get('total_invoiced', 0)
        outstanding = data.get('total_outstanding', 0)
        lines.append(f"Factures vente {('- ' + party) if party else ''}: {data['count']} | Total: {total:,.2f} {cur} | Impayé: {outstanding:,.2f} {cur}")
        lines.append('| Facture | Date | Total | Impayé | Statut |')
        lines.append('|---------|------|-------|--------|--------|')
        for i in data.get('items', [])[:MAX]:
            lines.append(f"| {i['name']} | {i.get('posting_date','')} | {flt(i.get('grand_total',0)):,.2f} | {flt(i.get('outstanding_amount',0)):,.2f} {cur} | {i.get('status','')} |")


    elif dt == 'sales_summary':
        lines.append(f"Résumé ventes: Total {data.get('total_sales',0):,.2f} {cur} | Impayé: {data.get('total_outstanding',0):,.2f} {cur}")


    elif dt == 'customer_info':
        lines.append(f"Client: {data.get('customer_name','')} | Groupe: {data.get('customer_group','')}")
        lines.append(f"Email: {data.get('email','')} | Tél: {data.get('phone','')}")
        lines.append(f"Actif: {'Oui' if data.get('is_active') else 'Non'} | TVA: {data.get('tax_id','')}")


    elif dt == 'sales_payment_status':
        lines.append(f"Paiements pour {data.get('invoice_id','')}: {data['count']} | Total payé: {data.get('total_paid',0):,.2f} {cur}")
        for p in data.get('payments', [])[:MAX]:
            lines.append(f"| {p['name']} | {p.get('paid_amount',0):,.2f} {cur} | {p.get('posting_date','')} |")


    # ── MODULE ACHATS ──
    elif dt == 'delayed_orders':
        lines.append(f"Commandes en retard: {data['count']} | Total: {data.get('total_amount',0):,.2f} {cur}")
        lines.append('| Commande | Fournisseur | Date prévue | Total |')
        lines.append('|----------|-------------|-------------|-------|')
        for i in data.get('items', [])[:MAX]:
            lines.append(f"| {i['name']} | {i.get('supplier','')} | {i.get('schedule_date','')} | {flt(i.get('grand_total',0)):,.2f} {cur} |")


    elif dt == 'purchase_order_tracking':
        lines.append(f"BC: {data.get('purchase_order','')} | Fournisseur: {data.get('supplier','')}")
        lines.append(f"Statut: {data.get('status','')} | Total: {data.get('grand_total',0):,.2f} {cur}")
        lines.append(f"Reçu: {data.get('is_received','')} | Facturé: {data.get('is_billed','')}")


    elif dt == 'pending_receipts':
        lines.append(f"Commandes reçues non facturées: {data['count']}")
        lines.append('| Commande | Fournisseur | % Reçu | % Facturé |')
        lines.append('|----------|-------------|--------|-----------|')
        for i in data.get('items', [])[:MAX]:
            lines.append(f"| {i['name']} | {i.get('supplier','')} | {i.get('per_received',0):.0f}% | {i.get('per_billed',0):.0f}% |")


    elif dt == 'purchase_stats_year':
        lines.append('Achats par mois (année courante):')
        lines.append('| Mois | Total |')
        lines.append('|------|-------|')
        months_fr = ['Jan','Fév','Mar','Avr','Mai','Juin','Juil','Aoû','Sep','Oct','Nov','Déc']
        for row in data.get('monthly_stats', []):
            m = int(row.get('month', 1)) - 1
            lines.append(f"| {months_fr[m]} | {flt(row.get('total',0)):,.2f} {cur} |")


    # ── MODULE STOCK ──
    elif dt == 'stock_availability':
        lines.append(f"Stock de {data.get('item_code','')}: Réel={data.get('total_actual',0):.2f} | Réservé={data.get('total_reserved',0):.2f} | Projeté={data.get('total_projected',0):.2f}")
        if data.get('warehouses'):
            lines.append('| Entrepôt | Réel | Réservé | Projeté |')
            lines.append('|----------|------|---------|---------|')
            for w in data['warehouses'][:MAX]:
                lines.append(f"| {w.get('warehouse','')} | {flt(w.get('actual_qty',0)):.2f} | {flt(w.get('reserved_qty',0)):.2f} | {flt(w.get('projected_qty',0)):.2f} |")


    elif dt == 'out_of_stock_items':
        lines.append(f"Articles en rupture: {data['count']}")
        lines.append('| Article | Entrepôt | Qté Réelle |')
        lines.append('|---------|----------|------------|')
        for i in data.get('items', [])[:MAX]:
            lines.append(f"| {i.get('item_code','')} | {i.get('warehouse','')} | {flt(i.get('actual_qty',0)):.2f} |")


    elif dt == 'stock_valuation':
        lines.append(f"Valeur totale du stock: {data.get('total_value',0):,.2f} {cur}")
        lines.append(f"Nombre d'articles: {data.get('item_count',0)}")


    elif dt == 'items_to_reorder':
        lines.append(f"Articles à réapprovisionner: {data['count']}")
        lines.append('| Article | Entrepôt | Seuil | Qté actuelle |')
        lines.append('|---------|----------|-------|--------------|')
        for i in data.get('items', [])[:MAX]:
            lines.append(f"| {i.get('item_code','')} | {i.get('warehouse','')} | {flt(i.get('threshold',0)):.2f} | {flt(i.get('current_qty',0)):.2f} |")


    elif dt == 'slow_moving_items':
        lines.append(f"Articles dormants (180j+): {data['count']}")
        lines.append('| Article | Dernier mouvement |')
        lines.append('|---------|------------------|')
        for i in data.get('items', [])[:MAX]:
            lines.append(f"| {i.get('item_code','')} | {i.get('last_move','')} |")


    elif dt == 'top_moving_items':
        lines.append('Top articles sortis ce mois:')
        lines.append('| Article | Qté sortie |')
        lines.append('|---------|-----------|')
        for i in data.get('items', [])[:MAX]:
            lines.append(f"| {i.get('item_code','')} | {flt(i.get('total_out',0)):.2f} |")


    # ── MODULE RH ──
    elif dt == 'leave_balance':
        if data.get('leave_type'):
            b = data.get('balance', {})
            lines.append(f"Solde {data['leave_type']}: {b.get('remaining_leaves', 0)} jours restants")
        else:
            lines.append('Solde de congés:')
            lines.append('| Type | Alloué | Pris | Restant |')
            lines.append('|------|--------|------|---------|')
            for lt, info in (data.get('allocation') or {}).items():
                lines.append(f"| {lt} | {info.get('total_leaves',0)} | {info.get('leaves_taken',0)} | {info.get('remaining_leaves',0)} |")


    elif dt == 'last_salary_slip':
        s = data.get('summary', {})
        lines.append(f"Fiche de paie: {s.get('start_date','')} — {s.get('end_date','')}")
        lines.append(f"Brut: {flt(s.get('gross_pay',0)):,.2f} {cur} | Déductions: {flt(s.get('total_deduction',0)):,.2f} | Net: {flt(s.get('net_pay',0)):,.2f} {cur}")
        if data.get('earnings'):
            lines.append('| Composant | Montant |')
            lines.append('|-----------|---------|')
            for e in data['earnings'][:MAX]:
                lines.append(f"| {e['component']} | {flt(e['amount']):,.2f} {cur} |")


    elif dt == 'attendance_status':
        lines.append(f"Pointage {data.get('date','')}: {data.get('status','')}")
        if data.get('logs'):
            for log in data['logs']:
                lines.append(f"  {log.get('log_type','')}: {log.get('time','')}")


    elif dt == 'team_absent_today':
        lines.append(f"Absents aujourd'hui: {data['count']}")
        lines.append('| Employé | Statut |')
        lines.append('|---------|--------|')
        for a in data.get('items', [])[:MAX]:
            lines.append(f"| {a.get('employee_name','')} | {a.get('status','')} |")


    elif dt == 'employee_profile':
        lines.append(f"Employé: {data.get('full_name','')} | Poste: {data.get('designation','')}")
        lines.append(f"Département: {data.get('department','')} | Depuis: {data.get('date_of_joining','')}")
        lines.append(f"Responsable: {data.get('reports_to','')}")


    elif dt == 'upcoming_holidays':
        lines.append(f"Prochains jours fériés: {data['count']}")
        lines.append('| Date | Description |')
        lines.append('|------|-------------|')
        for h in data.get('items', [])[:10]:
            lines.append(f"| {h.get('holiday_date','')} | {h.get('description','')} |")


    elif dt in ['expense_claims']:
        lines.append(f"Notes de frais: {data['count']}")
        lines.append('| Référence | Date | Montant | Statut |')
        lines.append('|-----------|------|---------|--------|')
        for e in data.get('items', [])[:MAX]:
            lines.append(f"| {e.get('name','')} | {e.get('posting_date','')} | {flt(e.get('total_claimed_amount',0)):,.2f} {cur} | {e.get('approval_status','')} |")


    elif dt == 'job_openings':
        lines.append(f"Postes ouverts: {data['count']}")
        lines.append('| Poste | Département |')
        lines.append('|-------|-------------|')
        for j in data.get('items', [])[:MAX]:
            lines.append(f"| {j.get('job_title','')} | {j.get('department','')} |")

    elif dt == 'my_absences':
        lines.append(f"Congés de {data.get('employee','')}: {data['count']}")
        lines.append('| Référence | Type | Du | Au | Statut | Jours |')
        lines.append('|-----------|------|----|----|--------|-------|')
        for a in data.get('items', [])[:MAX]:
            lines.append(f"| {a.get('name','')} | {a.get('leave_type','')} | {a.get('from_date','')} | {a.get('to_date','')} | {a.get('status','')} | {a.get('total_leave_days',0)} |")

    elif dt == 'stock_history':
        lines.append(f"Mouvements de {data.get('item_code','')}: {data['count']}")
        lines.append('| Date | Qté | Entrepôt | Type | Référence |')
        lines.append('|------|-----|----------|------|-----------|')
        for m in data.get('items', [])[:MAX]:
            lines.append(f"| {m.get('posting_date','')} | {flt(m.get('actual_qty',0)):+.2f} | {m.get('warehouse','')} | {m.get('voucher_type','')} | {m.get('voucher_no','')} |")

    elif dt == 'stock_purchase_requests':
        lines.append(f"Demandes d'achat en cours: {data['count']}")
        lines.append('| Demande | Article | Qté | Commandé |')
        lines.append('|---------|---------|-----|----------|')
        for r in data.get('items', [])[:MAX]:
            lines.append(f"| {r.get('parent','')} | {r.get('item_code','')} | {flt(r.get('qty',0)):.2f} | {flt(r.get('ordered_qty',0)):.2f} |")

    elif dt == 'batch_info':
        lines.append(f"Lot: {data.get('batch_id','')} | Article: {data.get('item_code','')}")
        lines.append(f"Fabrication: {data.get('manufacturing_date','')} | Expiration: {data.get('expiry_date','')} | {'⚠️ EXPIRÉ' if data.get('is_expired') else '✅ Valide'}")
        lines.append(f"Quantité actuelle: {flt(data.get('current_qty',0)):.2f}")

    elif dt == 'serial_status':
        lines.append(f"N° Série: {data.get('serial_no','')} | Statut: {data.get('status','')}")
        lines.append(f"Entrepôt: {data.get('warehouse','')} | BL: {data.get('delivery_note','')}")
        lines.append(f"Garantie jusqu'au: {data.get('warranty_expiry','N/A')}")

    elif dt == 'last_delivery_note':
        if data.get('message'):
            lines.append(data['message'])
        else:
            lines.append(f"Dernier BL pour {data.get('item_code','')}: {data.get('delivery_note','')}")
            lines.append(f"Date: {data.get('date','')}")

    elif dt == 'warehouse_details':
        lines.append(f"Entrepôt: {data.get('warehouse','')} | Type: {data.get('type','')}")
        lines.append(f"Parent: {data.get('parent','')} | Société: {data.get('company','')}")

    elif dt == 'material_request_status':
        lines.append(f"Demande: {data.get('request_id','')} | Statut: {data.get('status','')}")
        lines.append(f"Commandé: {data.get('per_ordered',0):.0f}% | Reçu: {data.get('per_received',0):.0f}%")
        if data.get('items'):
            lines.append('| Article | Qté |')
            lines.append('|---------|-----|')
            for i in data['items'][:MAX]:
                lines.append(f"| {i.get('item_code','')} | {i.get('qty',0)} |")

    elif dt == 'supplier_details':
        lines.append(f"Fournisseur: {data.get('supplier','')} | Statut: {data.get('status','')}")
        lines.append(f"Groupe: {data.get('category','')} | Conditions paiement: {data.get('payment_terms','')}")
        lines.append(f"TVA: {data.get('tax_id','')} | Site: {data.get('website','')}")

    elif dt == 'last_purchase_price':
        lines.append(f"Dernier prix pour {data.get('item_code','')}: {flt(data.get('last_price',0)):,.2f} {cur}")
        lines.append(f"Commande: {data.get('order_ref','')} | Date: {data.get('date','')}")

    elif dt == 'purchase_unpaid_invoices':
        lines.append(f"Factures fournisseur impayées: {data['count']} | Total restant: {flt(data.get('total_outstanding',0)):,.2f} {cur}")
        lines.append('| Facture | Fournisseur | Échéance | Restant |')
        lines.append('|---------|-------------|----------|---------|')
        for i in data.get('items', [])[:MAX]:
            lines.append(f"| {i.get('name','')} | {i.get('supplier','')} | {i.get('due_date','')} | {flt(i.get('outstanding_amount',0)):,.2f} {cur} |")

    elif dt == 'pending_receipts':
        lines.append(f"Commandes reçues non facturées: {data['count']}")
        lines.append('| Commande | Fournisseur | % Reçu | % Facturé |')
        lines.append('|----------|-------------|--------|-----------|')
        for i in data.get('items', [])[:MAX]:
            lines.append(f"| {i['name']} | {i.get('supplier','')} | {i.get('per_received',0):.0f}% | {i.get('per_billed',0):.0f}% |")

    elif dt == 'order_discount':
        lines.append(f"Commande: {data.get('order_id','')} | Client: {data.get('customer','')}")
        lines.append(f"Total: {flt(data.get('grand_total',0)):,.2f} {cur} | Remise montant: {flt(data.get('discount_amount',0)):,.2f} {cur} | Remise %: {data.get('discount_percentage',0)}%")

    elif dt == 'cancelled_orders':
        lines.append(f"Commandes annulées: {data['count']}")
        lines.append('| Commande | Client | Date | Total |')
        lines.append('|----------|--------|------|-------|')
        for i in data.get('items', [])[:MAX]:
            lines.append(f"| {i['name']} | {i.get('customer','')} | {i.get('transaction_date','')} | {flt(i.get('grand_total',0)):,.2f} {cur} |")

    else:
        lines.append("Aucune donnée disponible.")
    return "\n".join(lines)

def _create_new_conversation(user, first_message):
    title = first_message.strip()[:50] + ("..." if len(first_message.strip()) > 50 else "")
    doc = frappe.get_doc({"doctype": "Chatbot Conversation", "user": user, "title": title, "last_message_at": now_datetime()})
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc
