"""
Bridge Frappe -> FastAPI (Cohere).

Pattern :
- Lit l'utilisateur courant + ses roles via frappe.session
- Signe un JWT court (60s) avec une cle partagee (frappe.conf.chatbot_jwt_secret)
- Forward le message vers le service FastAPI
- Renvoie la reponse au frontend

Configuration requise dans site_config.json :
    bench --site <site> set-config chatbot_jwt_secret "<meme valeur que JWT_SECRET cote FastAPI>"
    bench --site <site> set-config chatbot_fastapi_url "http://127.0.0.1:9001"

Note: 9001 par defaut car bench ecoute deja sur 9000 (socketio.js).
"""
from __future__ import annotations

import json
from typing import Any, Callable

import frappe
import jwt
import requests
from frappe import _
from frappe.utils import now_datetime
from custom_dashboard.services import ai_gateway

from custom_dashboard.chatbot.accounting_api import fetch_accounting_data
from custom_dashboard.chatbot.chatbot_api import (
    FINANCE_INTENTS,
    HR_INTENTS,
    PROJECT_INTENTS,
    PURCHASE_INTENTS,
    PURCHASE_MODULE_INTENTS,
    SALES_INTENTS,
    SALES_MODULE_INTENTS,
    STOCK_INTENTS,
    _check_access,
)
from custom_dashboard.chatbot.hr_api import fetch_hr_data
from custom_dashboard.chatbot.intent_classifier import get_date_range
from custom_dashboard.chatbot.project_api import fetch_project_data
from custom_dashboard.chatbot.purchase_api import fetch_purchase_data
from custom_dashboard.chatbot.stock_api import fetch_stock_data
from custom_dashboard.chatbot.vente_api import fetch_sales_data


DEFAULT_HTTP_TIMEOUT = 60  # secondes
DEFAULT_LANGUAGE = "fr"
SUPPORTED_LANGUAGES = {"fr", "en"}
MAX_HISTORY_TURNS = 20
MAX_TOOL_PAGE_LENGTH = 100


TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "fetch_accounting_data": {
        "handler": fetch_accounting_data,
        "intents": FINANCE_INTENTS | SALES_INTENTS | PURCHASE_INTENTS,
        "supports_dates": True,
    },
    "fetch_sales_data": {
        "handler": fetch_sales_data,
        "intents": SALES_MODULE_INTENTS,
        "supports_dates": True,
    },
    "fetch_purchase_data": {
        "handler": fetch_purchase_data,
        "intents": PURCHASE_MODULE_INTENTS,
        "supports_dates": True,
    },
    "fetch_stock_data": {
        "handler": fetch_stock_data,
        "intents": STOCK_INTENTS,
        "supports_dates": False,
    },
    "fetch_hr_data": {
        "handler": fetch_hr_data,
        "intents": HR_INTENTS,
        "supports_dates": True,
    },
    "fetch_project_data": {
        "handler": fetch_project_data,
        "intents": PROJECT_INTENTS,
        "supports_dates": True,
    },
}


def _get_config() -> dict[str, Any]:
    cfg = ai_gateway.get_config()
    cfg["http_timeout"] = float((frappe.conf or {}).get("chatbot_http_timeout") or cfg["http_timeout"] or DEFAULT_HTTP_TIMEOUT)
    return cfg


def _sign_jwt(cfg: dict[str, Any]) -> str:
    return ai_gateway.sign_jwt(cfg)


def _normalize_history(history: Any) -> list[dict[str, str]]:
    if isinstance(history, str):
        try:
            history = frappe.parse_json(history) or []
        except Exception:
            history = []
    if not isinstance(history, list):
        return []

    normalized: list[dict[str, str]] = []
    for entry in history[-MAX_HISTORY_TURNS:]:
        if not isinstance(entry, dict):
            continue
        role = str(entry.get("role") or "").strip()
        content = str(entry.get("content") or "").strip()
        if role not in {"user", "assistant", "system"} or not content:
            continue
        normalized.append({"role": role, "content": content})
    return normalized


def _get_or_create_conversation(conversation_id: str | None, message: str):
    user = frappe.session.user
    if conversation_id:
        try:
            conv = frappe.get_doc("Chatbot Conversation", conversation_id)
            if conv.user != user and "System Manager" not in frappe.get_roles(user):
                frappe.throw(_("Accès non autorisé"), frappe.PermissionError)
            return conv
        except frappe.DoesNotExistError:
            pass

    title = message.strip()[:50] + ("..." if len(message.strip()) > 50 else "")
    conv = frappe.get_doc({
        "doctype": "Chatbot Conversation",
        "user": user,
        "title": title or _("Nouvelle conversation"),
        "last_message_at": now_datetime(),
    })
    conv.insert(ignore_permissions=True)
    frappe.db.commit()
    return conv


def _history_from_conversation(conv) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for row in list(conv.messages or [])[-MAX_HISTORY_TURNS:]:
        role = "assistant" if row.role == "bot" else row.role
        if role not in {"user", "assistant", "system"}:
            continue
        content = str(row.content or "").strip()
        if content:
            history.append({"role": role, "content": content})
    return history


def _append_conversation_message(conv, role: str, content: str) -> None:
    conv.append("messages", {
        "role": role,
        "content": content,
        "timestamp": now_datetime(),
    })
    conv.last_message_at = now_datetime()
    conv.save(ignore_permissions=True)
    frappe.db.commit()


def _json_string(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, str):
        try:
            parsed = frappe.parse_json(value)
            return json.dumps(parsed, ensure_ascii=False, default=str)
        except Exception:
            return value
    return json.dumps(value, ensure_ascii=False, default=str)


@frappe.whitelist()
def send_message_v2(
    message: str,
    language: str = DEFAULT_LANGUAGE,
    history: Any = None,
    conversation_id: str | None = None,
) -> dict:
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentification requise"), frappe.PermissionError)

    if not message or not str(message).strip():
        frappe.throw(_("Message vide"))

    cfg = _get_config()
    if not cfg["jwt_secret"]:
        frappe.throw(_(
            "chatbot_jwt_secret manquant dans site_config.json. "
            "Lance: bench --site <site> set-config chatbot_jwt_secret <secret>"
        ))

    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE

    clean_message = str(message).strip()
    conv = _get_or_create_conversation(conversation_id, clean_message)
    payload_history = (
        _normalize_history(history)
        if history is not None
        else _history_from_conversation(conv)
    )

    _append_conversation_message(conv, "user", clean_message)

    payload = {
        "message": clean_message,
        "language": language,
        "history": payload_history,
    }

    try:
        result = ai_gateway.post_json("/chat", payload, timeout=cfg["http_timeout"])
    except ai_gateway.AIServiceError as exc:
        frappe.throw(_(str(exc)))

    bot_response = str(result.get("response") or "").strip()
    if bot_response:
        _append_conversation_message(conv, "bot", bot_response)

    result["conversation_id"] = conv.name
    result["conversation_title"] = conv.title
    return result


@frappe.whitelist()
def prepare_stream_v2(
    message: str,
    language: str = DEFAULT_LANGUAGE,
    history: Any = None,
    conversation_id: str | None = None,
) -> dict:
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentification requise"), frappe.PermissionError)

    if not message or not str(message).strip():
        frappe.throw(_("Message vide"))

    cfg = _get_config()
    if not cfg["jwt_secret"]:
        frappe.throw(_(
            "chatbot_jwt_secret manquant dans site_config.json. "
            "Lance: bench --site <site> set-config chatbot_jwt_secret <secret>"
        ))

    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE

    clean_message = str(message).strip()
    conv = _get_or_create_conversation(conversation_id, clean_message)
    payload_history = (
        _normalize_history(history)
        if history is not None
        else _history_from_conversation(conv)
    )
    _append_conversation_message(conv, "user", clean_message)

    return {
        "fastapi_url": cfg["fastapi_public_url"],
        "endpoint": "/chat/stream",
        "token": _sign_jwt(cfg),
        "expires_in": cfg["jwt_ttl"],
        "payload": {
            "message": clean_message,
            "language": language,
            "history": payload_history,
        },
        "conversation_id": conv.name,
        "conversation_title": conv.title,
    }


@frappe.whitelist()
def finish_stream_v2(conversation_id: str, response: str) -> dict:
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentification requise"), frappe.PermissionError)

    if not conversation_id:
        frappe.throw(_("Conversation requise"))

    conv = frappe.get_doc("Chatbot Conversation", conversation_id)
    if conv.user != frappe.session.user and "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw(_("Accès non autorisé"), frappe.PermissionError)

    bot_response = str(response or "").strip()
    if bot_response:
        _append_conversation_message(conv, "bot", bot_response)

    return {
        "status": "ok",
        "conversation_id": conv.name,
        "conversation_title": conv.title,
    }


@frappe.whitelist()
def submit_feedback(
    conversation_id: str | None = None,
    question: str | None = None,
    response: str | None = None,
    rating: str | None = None,
    comment: str | None = None,
    expected_answer: str | None = None,
    rag_sources: Any = None,
    used_tools: Any = None,
    metadata: Any = None,
) -> dict:
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentification requise"), frappe.PermissionError)

    normalized_rating = str(rating or "").strip().lower()
    if normalized_rating in {"positive", "like", "good", "1", "yes"}:
        normalized_rating = "up"
    if normalized_rating in {"negative", "dislike", "bad", "-1", "no"}:
        normalized_rating = "down"
    if normalized_rating not in {"up", "down"}:
        frappe.throw(_("Feedback invalide"))

    conv = None
    if conversation_id:
        conv = frappe.get_doc("Chatbot Conversation", conversation_id)
        if conv.user != frappe.session.user and "System Manager" not in frappe.get_roles(frappe.session.user):
            frappe.throw(_("Acces non autorise"), frappe.PermissionError)

    doc = frappe.get_doc(
        {
            "doctype": "Chatbot Feedback",
            "user": frappe.session.user,
            "conversation_id": conv.name if conv else None,
            "rating": normalized_rating,
            "score": 1 if normalized_rating == "up" else -1,
            "question": str(question or "")[:10000],
            "answer": str(response or "")[:20000],
            "comment": str(comment or "")[:1000],
            "expected_answer": str(expected_answer or "")[:20000],
            "rag_sources_json": _json_string(rag_sources)[:20000],
            "used_tools_json": _json_string(used_tools)[:5000],
            "metadata_json": _json_string(metadata)[:10000],
        }
    )
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "ok", "feedback_id": doc.name}


def _decode_tool_jwt() -> dict[str, Any]:
    cfg = _get_config()
    if not cfg["jwt_secret"]:
        frappe.throw(_("chatbot_jwt_secret manquant"), frappe.PermissionError)

    token = (frappe.get_request_header("X-Chatbot-JWT") or "").strip()
    if not token:
        authorization = frappe.get_request_header("Authorization") or ""
        if authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()
    if not token:
        frappe.throw(_("JWT chatbot requis"), frappe.PermissionError)
    try:
        payload = jwt.decode(
            token,
            cfg["jwt_secret"],
            algorithms=[cfg["jwt_algorithm"]],
        )
    except jwt.ExpiredSignatureError:
        frappe.throw(_("JWT expire"), frappe.PermissionError)
    except jwt.InvalidTokenError:
        frappe.throw(_("JWT invalide"), frappe.PermissionError)

    if not payload.get("user") or payload.get("user") == "Guest":
        frappe.throw(_("Authentification requise"), frappe.PermissionError)
    return payload


def _parse_tool_arguments(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError:
            frappe.throw(_("Arguments tool JSON invalides"))

    if arguments is None:
        return {}
    if not isinstance(arguments, dict):
        frappe.throw(_("Arguments tool invalides"))
    return arguments


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(number, maximum))


def _execute_registered_tool(tool_name: str, args: dict[str, Any], language: str) -> Any:
    args = dict(args)
    intent = str(args.get("intent") or "").strip()
    if tool_name == "fetch_accounting_data" and intent == "sales_summary":
        intent = "revenue_period"
        args["intent"] = intent

    spec = TOOL_REGISTRY.get(tool_name)
    if not spec:
        frappe.throw(_("Tool non autorisé: {0}").format(tool_name), frappe.PermissionError)

    if not intent:
        frappe.throw(_("Intent requis pour le tool"))
    if intent not in spec["intents"]:
        for candidate_name, candidate_spec in TOOL_REGISTRY.items():
            if intent in candidate_spec["intents"]:
                tool_name = candidate_name
                spec = candidate_spec
                break
        else:
            frappe.throw(
                _("Intent {0} non autorisé pour {1}").format(intent, tool_name),
                frappe.PermissionError,
            )

    roles = set(frappe.get_roles(frappe.session.user))
    access_denied = _check_access(intent, roles, language)
    if access_denied:
        frappe.throw(access_denied, frappe.PermissionError)

    period = str(args.get("period") or "").strip()
    from_date = args.get("from_date")
    to_date = args.get("to_date")
    if spec["supports_dates"] and (not from_date or not to_date):
        from_date, to_date = get_date_range(period or "this_month")

    kwargs = {
        "intent": intent,
        "entity": args.get("entity"),
        "limit_start": _bounded_int(args.get("limit_start"), 0, 0, 10000),
        "limit_page_length": _bounded_int(
            args.get("limit_page_length"),
            20,
            1,
            MAX_TOOL_PAGE_LENGTH,
        ),
    }
    if spec["supports_dates"]:
        kwargs["from_date"] = from_date
        kwargs["to_date"] = to_date

    handler: Callable[..., Any] = spec["handler"]
    return handler(**kwargs)


@frappe.whitelist(allow_guest=True)
def execute_tool_v2(tool_name: str, arguments: Any = None, language: str = DEFAULT_LANGUAGE) -> dict:
    payload = _decode_tool_jwt()
    user = payload["user"]
    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE

    previous_user = frappe.session.user
    frappe.set_user(user)
    try:
        args = _parse_tool_arguments(arguments)
        data = _execute_registered_tool(str(tool_name or "").strip(), args, language)
        return {"ok": True, "tool": tool_name, "data": data}
    finally:
        frappe.set_user(previous_user)


@frappe.whitelist()
def voice_session() -> dict:
    """Renvoie l'URL FastAPI publique + un JWT court pour appeler /voice/tts et /voice/stt."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentification requise"), frappe.PermissionError)

    cfg = _get_config()
    if not cfg["jwt_secret"]:
        frappe.throw(_(
            "chatbot_jwt_secret manquant dans site_config.json. "
            "Lance: bench --site <site> set-config chatbot_jwt_secret <secret>"
        ))

    return {
        "fastapi_url": cfg["fastapi_public_url"],
        "tts_endpoint": "/voice/tts",
        "stt_endpoint": "/voice/stt",
        "token": _sign_jwt(cfg),
        "expires_in": cfg["jwt_ttl"],
    }


@frappe.whitelist()
def health_v2() -> dict:
    """Sonde la sante de la stack chatbot (utile pour debug)."""
    cfg = _get_config()

    if not cfg["jwt_secret"]:
        return {"status": "ko", "reason": "chatbot_jwt_secret manquant"}

    try:
        response = requests.get(f"{cfg['fastapi_url']}/health", timeout=5)
    except requests.exceptions.RequestException as exc:
        return {"status": "ko", "reason": f"FastAPI inaccessible: {exc}"}

    if response.status_code != 200:
        return {"status": "ko", "reason": f"HTTP {response.status_code}"}

    payload = response.json()
    return {
        "status": "ok",
        "fastapi_url": cfg["fastapi_url"],
        "fastapi_health": payload,
        "jwt_ttl_s": cfg["jwt_ttl"],
    }
