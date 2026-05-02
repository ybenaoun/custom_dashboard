from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings


TOOL_PARAMETER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "description": "Intent ERPNext exact à exécuter, par exemple stock_availability ou sales_summary.",
        },
        "period": {
            "type": "string",
            "description": "Période relative optionnelle: today, this_week, this_month, last_month, this_year, all, YYYY-MM ou YYYY-MM-DD:YYYY-MM-DD.",
        },
        "from_date": {
            "type": "string",
            "description": "Date de début ISO YYYY-MM-DD si la période est connue.",
        },
        "to_date": {
            "type": "string",
            "description": "Date de fin ISO YYYY-MM-DD si la période est connue.",
        },
        "entity": {
            "type": "string",
            "description": "Client, fournisseur, article, entrepôt, projet ou employé ciblé si demandé.",
        },
        "limit_start": {
            "type": "integer",
            "minimum": 0,
            "description": "Offset de pagination.",
        },
        "limit_page_length": {
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
            "description": "Nombre maximum de lignes à retourner.",
        },
    },
    "required": ["intent"],
    "additionalProperties": False,
}


COHERE_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "fetch_accounting_data",
            "description": "Récupère les données comptables et factures. Pour chiffre d'affaires, revenu, revenue, CA cumulé ou montant total facturé, utiliser intent revenue_period. Autres intents utiles: expenses_period, net_profit, financial_summary, account_balance, received_payments_period, paid_payments_period, recent_payments, unpaid_sales_invoices, overdue_sales_invoices, total_invoiced_period, top_debtors, unpaid_purchase_invoices, overdue_purchase_invoices, total_purchased_period, top_creditors.",
            "parameters": TOOL_PARAMETER_SCHEMA,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_sales_data",
            "description": "Récupère les données opérationnelles du module Vente: commandes, devis, clients, statuts, remises et retards. Intents: sales_order_status, sales_orders_customer, sales_invoice_status, sales_invoices_customer, customer_info, sales_summary, sales_payment_status, order_discount, cancelled_orders, quotations_for_customer, delayed_sales_orders. Ne pas utiliser sales_summary pour le chiffre d'affaires cumulé: utiliser fetch_accounting_data avec intent revenue_period.",
            "parameters": TOOL_PARAMETER_SCHEMA,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_purchase_data",
            "description": "Récupère les données du module Achat: demandes de matériel, commandes, fournisseurs, réceptions et prix d'achat.",
            "parameters": TOOL_PARAMETER_SCHEMA,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_stock_data",
            "description": "Récupère les données de stock: disponibilité, ruptures, valorisation, lots, numéros de série, mouvements et entrepôts.",
            "parameters": TOOL_PARAMETER_SCHEMA,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_hr_data",
            "description": "Récupère les données RH autorisées: congés, absences, présence, notes de frais, profil employé et annuaire.",
            "parameters": TOOL_PARAMETER_SCHEMA,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_project_data",
            "description": "Récupère les données projets et tâches: statut, avancement, coûts, revenus, retards, temps saisis et rentabilité.",
            "parameters": TOOL_PARAMETER_SCHEMA,
        },
    },
]


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _get_call_attr(tool_call: Any, key: str) -> Any:
    if isinstance(tool_call, dict):
        return tool_call.get(key)
    return getattr(tool_call, key, None)


def _function_from_call(tool_call: Any) -> Any:
    return _get_call_attr(tool_call, "function") or {}


def _function_attr(function: Any, key: str) -> Any:
    if isinstance(function, dict):
        return function.get(key)
    return getattr(function, key, None)


def _parse_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if not raw_arguments:
        return {}
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError:
        return {"_invalid_json": str(raw_arguments)}
    return parsed if isinstance(parsed, dict) else {}


def _extract_error_detail(response: httpx.Response) -> Any:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:1000]
    return (
        payload.get("exception")
        or payload.get("_server_messages")
        or payload.get("message")
        or payload
    )


async def call_frappe_tool(
    tool_name: str,
    arguments: dict[str, Any],
    token: str | None,
    language: str,
) -> dict[str, Any]:
    if not token:
        return {"ok": False, "error": "missing_token", "message": "JWT utilisateur manquant"}

    url = (
        f"{settings.frappe_url.rstrip('/')}"
        "/api/method/custom_dashboard.chatbot.chatbot_proxy.execute_tool_v2"
    )
    headers = {"X-Chatbot-JWT": token}
    if settings.frappe_host_header:
        headers["Host"] = settings.frappe_host_header
    payload = {"tool_name": tool_name, "arguments": arguments, "language": language}

    try:
        async with httpx.AsyncClient(timeout=settings.frappe_tool_timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.RequestError as exc:
        return {"ok": False, "error": "frappe_unreachable", "message": str(exc)}

    if response.status_code >= 400:
        return {
            "ok": False,
            "error": "frappe_http_error",
            "status_code": response.status_code,
            "detail": _extract_error_detail(response),
        }

    try:
        payload = response.json()
    except ValueError:
        return {"ok": False, "error": "invalid_frappe_json", "message": response.text[:1000]}

    result = payload.get("message", payload)
    return result if isinstance(result, dict) else {"ok": True, "data": result}


async def execute_tool_calls(
    tool_calls: list[Any],
    user: dict[str, Any],
    language: str,
) -> list[dict[str, Any]]:
    token = user.get("_token")
    messages: list[dict[str, Any]] = []

    for tool_call in tool_calls:
        function = _function_from_call(tool_call)
        tool_name = str(_function_attr(function, "name") or "").strip()
        call_id = str(_get_call_attr(tool_call, "id") or tool_name)
        arguments = _parse_arguments(_function_attr(function, "arguments"))

        if arguments.get("_invalid_json"):
            result = {
                "ok": False,
                "error": "invalid_tool_arguments",
                "message": arguments["_invalid_json"],
            }
        else:
            result = await call_frappe_tool(tool_name, arguments, token, language)

        messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "content": _json_dumps(result),
        })

    return messages
