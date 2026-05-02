"""
Couche d'execution des widgets IA via le service IA unique FastAPI/Cohere.

Pattern :
- Le widget collecte un *contexte* (KPIs deja calcules par les autres widgets)
- Construit un prompt structure (sortie JSON imposee)
- Appelle le backend FastAPI centralise, qui porte l'integration Cohere
- Cache la reponse dans Redis (TTL 30 min) keye par (widget_name, filters_hash)
- Renvoie {summary, anomalies[], recommendations[], generated_at, model, parse_failed}
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from custom_dashboard.services import ai_gateway, widget_executor


DEFAULT_AI_SERVICE_KEY = "fastapi-cohere"
DEFAULT_AI_INSIGHT_ENDPOINT = "/chat"
DEFAULT_CACHE_TTL = 30 * 60  # 30 minutes
CACHE_PREFIX = "custom_dashboard:ai_insight"
DEFAULT_TIMEOUT = 60  # secondes


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _get_config() -> dict[str, Any]:
	conf = frappe.conf or {}
	return {
		"endpoint": conf.get("ai_insight_fastapi_endpoint") or DEFAULT_AI_INSIGHT_ENDPOINT,
		"service_key": (
			conf.get("cohere_model")
			or conf.get("chatbot_model")
			or conf.get("ai_service_key")
			or DEFAULT_AI_SERVICE_KEY
		),
		"cache_ttl": int(conf.get("ai_insight_cache_ttl") or DEFAULT_CACHE_TTL),
		"timeout": int(conf.get("ai_insight_timeout") or DEFAULT_TIMEOUT),
	}


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def _cache_key(widget_name: str, filters: dict[str, Any], model: str) -> str:
	payload = json.dumps({"f": filters, "m": model}, sort_keys=True, default=str)
	digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
	return f"{CACHE_PREFIX}:{widget_name}:{digest}"


def _cache_get(key: str) -> dict[str, Any] | None:
	try:
		raw = frappe.cache().get_value(key)
	except Exception:
		return None
	if not raw:
		return None
	if isinstance(raw, (bytes, bytearray)):
		try:
			raw = raw.decode("utf-8")
		except Exception:
			return None
	if isinstance(raw, str):
		try:
			return json.loads(raw)
		except Exception:
			return None
	if isinstance(raw, dict):
		return raw
	return None


def _cache_set(key: str, value: dict[str, Any], ttl: int) -> None:
	try:
		frappe.cache().set_value(key, json.dumps(value, default=str), expires_in_sec=ttl)
	except Exception:
		# Le cache est best-effort : un echec ne doit pas casser le widget.
		pass


# ---------------------------------------------------------------------------
# Sanitisation pour le prompt
# ---------------------------------------------------------------------------


_SANITIZE_RE = re.compile(r"[`\r\n\t]+")


def _clip(value: Any, max_len: int = 200) -> str:
	if value is None:
		return ""
	text = _SANITIZE_RE.sub(" ", str(value)).strip()
	return text[:max_len]


def _safe_number(value: Any) -> float:
	try:
		return round(float(flt(value)), 2)
	except Exception:
		return 0.0


# ---------------------------------------------------------------------------
# Construction des contextes metiers
# ---------------------------------------------------------------------------


def _safe_widget_call(widget_name: str, filters: dict[str, Any]) -> dict[str, Any] | None:
	"""Execute un widget existant en isolant les erreurs."""
	try:
		method = getattr(widget_executor, _WIDGET_METHODS[widget_name])
	except Exception:
		return None
	try:
		return method(filters=filters, widget=None) or {}
	except Exception as exc:
		frappe.log_error(
			title=f"AI insights: widget {widget_name} a echoue",
			message=str(exc),
		)
	return None


_WIDGET_METHODS = {
	"STOCK_TURNOVER": "stock_turnover_widget",
	"DORMANT_STOCK": "dormant_stock_widget",
	"STOCK_AGE_PROFILE": "stock_age_profile_widget",
	"WAREHOUSE_STOCKOUT_RISK": "warehouse_stockout_risk_widget",
	"MONTHLY_STOCK_FLOW": "monthly_stock_flow_widget",
	"RESERVATION_PRESSURE": "reservation_pressure_widget",
	"INVENTORY_CONCENTRATION": "inventory_concentration_widget",
	"SALES_THIS_MONTH": "sales_this_month_widget",
	"MONTHLY_REVENUE_CHART": "monthly_revenue_chart_widget",
	"TOP_CUSTOMERS": "top_customers_widget",
	"PIPELINE_HEALTH": "pipeline_health_widget",
	"OVERDUE_INVOICES": "overdue_invoices_widget",
	"REVENUE_BY_CATEGORY": "revenue_by_category_widget",
	"PAYMENT_DELAY": "payment_delay_widget",
	"AT_RISK_CUSTOMERS": "at_risk_customers_widget",
	"PROFITABLE_PRODUCTS": "profitable_products_widget",
	"BUYING_SPEND_THIS_MONTH": "buying_spend_this_month_widget",
	"BUYING_MONTHLY_SPEND": "buying_monthly_spend_widget",
	"BUYING_TOP_SUPPLIERS": "buying_top_suppliers_widget",
	"BUYING_OPEN_PURCHASE_ORDERS": "buying_open_purchase_orders_widget",
}


def build_stock_context(filters: dict[str, Any]) -> dict[str, Any]:
	"""Reagrege les KPIs Stock deja calcules par les widgets existants."""
	turnover = _safe_widget_call("STOCK_TURNOVER", filters) or {}
	dormant = _safe_widget_call("DORMANT_STOCK", filters) or {}
	age_profile = _safe_widget_call("STOCK_AGE_PROFILE", filters) or {}
	stockout = _safe_widget_call("WAREHOUSE_STOCKOUT_RISK", filters) or {}
	monthly_flow = _safe_widget_call("MONTHLY_STOCK_FLOW", filters) or {}
	reservation = _safe_widget_call("RESERVATION_PRESSURE", filters) or {}
	concentration = _safe_widget_call("INVENTORY_CONCENTRATION", filters) or {}

	# top entrepots a risque (label + ratio)
	stockout_top = []
	for label, value in zip(stockout.get("labels") or [], (stockout.get("datasets") or [{}])[0].get("values") or []):
		stockout_top.append({"warehouse": _clip(label, 80), "risk_score": _safe_number(value)})
	stockout_top = stockout_top[:5]

	# repartition ABC
	abc_buckets = []
	conc_labels = concentration.get("labels") or []
	conc_values = (concentration.get("datasets") or [{}])[0].get("values") or []
	for label, value in zip(conc_labels, conc_values):
		abc_buckets.append({"bucket": _clip(label, 40), "value": _safe_number(value)})

	# tendance mensuelle (in / out)
	monthly_trend = []
	flow_labels = monthly_flow.get("labels") or []
	flow_datasets = monthly_flow.get("datasets") or []
	in_values = next((d.get("values") for d in flow_datasets if "entr" in (d.get("name") or "").lower()), [])
	out_values = next((d.get("values") for d in flow_datasets if "sort" in (d.get("name") or "").lower()), [])
	for idx, label in enumerate(flow_labels[-6:]):
		monthly_trend.append(
			{
				"month": _clip(label, 20),
				"in_value": _safe_number(in_values[idx]) if idx < len(in_values) else 0.0,
				"out_value": _safe_number(out_values[idx]) if idx < len(out_values) else 0.0,
			}
		)

	# top reservation pressure
	reservation_top = []
	res_labels = reservation.get("labels") or []
	res_values = (reservation.get("datasets") or [{}])[0].get("values") or []
	for label, value in zip(res_labels[:5], res_values[:5]):
		reservation_top.append({"warehouse": _clip(label, 80), "ratio": _safe_number(value)})

	currency = (
		concentration.get("currency")
		or (concentration.get("summary") or {}).get("currency")
		or ""
	)

	return {
		"period": _clip(turnover.get("context") or dormant.get("context") or "", 80),
		"currency": _clip(currency, 16),
		"filters": {
			"company": _clip(filters.get("company"), 80),
			"warehouse": _clip(filters.get("warehouse"), 80),
			"item_group": _clip(filters.get("item_group"), 80),
			"period": _clip(filters.get("period"), 40),
		},
		"kpis": {
			"stock_turnover_ratio": _safe_number(turnover.get("value")),
			"outflow_value": _safe_number(turnover.get("secondary_value")),
			"dormant_value": _safe_number(dormant.get("value")),
			"dormant_items_count": _safe_number(dormant.get("secondary_value")),
			"total_stock_value": _safe_number((concentration.get("summary") or {}).get("value")),
			"abc_buckets": abc_buckets,
			"age_profile": [
				{"bucket": _clip(label, 40), "value": _safe_number(value)}
				for label, value in zip(
					age_profile.get("labels") or [],
					(age_profile.get("datasets") or [{}])[0].get("values") or [],
				)
			],
			"warehouses_at_risk": stockout_top,
			"top_reservation_pressure": reservation_top,
			"monthly_flow_last_6": monthly_trend,
		},
		}


def _dataset_values(payload: dict[str, Any], name_contains: str = "") -> list[Any]:
	datasets = payload.get("datasets") or []
	if not datasets:
		return []
	if not name_contains:
		return datasets[0].get("values") or []
	needle = name_contains.lower()
	for dataset in datasets:
		if needle in (dataset.get("name") or "").lower():
			return dataset.get("values") or []
	return []


def _chart_points(payload: dict[str, Any], value_name: str = "", count_name: str = "", limit: int = 6) -> list[dict[str, Any]]:
	labels = payload.get("labels") or []
	values = _dataset_values(payload, value_name)
	counts = _dataset_values(payload, count_name) if count_name else []
	start_index = max(len(labels) - limit, 0)
	points = []
	for index in range(start_index, len(labels)):
		point = {
			"period": _clip(labels[index], 40),
			"value": _safe_number(values[index]) if index < len(values) else 0.0,
		}
		if count_name:
			point["count"] = _safe_number(counts[index]) if index < len(counts) else 0.0
		points.append(point)
	return points


def _chart_breakdown(payload: dict[str, Any], value_name: str = "", limit: int = 6) -> list[dict[str, Any]]:
	labels = payload.get("labels") or []
	values = _dataset_values(payload, value_name)
	breakdown = []
	for label, value in zip(labels[:limit], values[:limit]):
		breakdown.append({"label": _clip(label, 80), "value": _safe_number(value)})
	return breakdown


def build_selling_context(filters: dict[str, Any]) -> dict[str, Any]:
	"""Reagrege les KPIs Ventes deja calcules par les widgets existants."""
	revenue = _safe_widget_call("SALES_THIS_MONTH", filters) or {}
	revenue_trend = _safe_widget_call("MONTHLY_REVENUE_CHART", filters) or {}
	top_customers = _safe_widget_call("TOP_CUSTOMERS", filters) or {}
	pipeline = _safe_widget_call("PIPELINE_HEALTH", filters) or {}
	overdue = _safe_widget_call("OVERDUE_INVOICES", filters) or {}
	revenue_by_category = _safe_widget_call("REVENUE_BY_CATEGORY", filters) or {}
	payment_delay = _safe_widget_call("PAYMENT_DELAY", filters) or {}
	at_risk = _safe_widget_call("AT_RISK_CUSTOMERS", filters) or {}
	profitable_products = _safe_widget_call("PROFITABLE_PRODUCTS", filters) or {}

	return {
		"period": _clip(revenue.get("context") or revenue_trend.get("context") or "", 80),
		"currency": _clip(revenue.get("currency") or (revenue_trend.get("summary") or {}).get("currency") or "", 16),
		"filters": {
			"company": _clip(filters.get("company"), 80),
			"customer_group": _clip(filters.get("customer_group"), 80),
			"territory": _clip(filters.get("territory"), 80),
			"period": _clip(filters.get("period"), 40),
		},
		"kpis": {
			"revenue": _safe_number(revenue.get("value")),
			"invoice_count": _safe_number(revenue.get("secondary_value")),
			"overdue_amount": _safe_number(overdue.get("value")),
			"overdue_invoice_count": _safe_number(overdue.get("secondary_value")),
			"payment_delay_days": _safe_number(payment_delay.get("value")),
			"paid_invoice_count": _safe_number(payment_delay.get("secondary_value")),
			"at_risk_customer_count": _safe_number(at_risk.get("value")),
			"at_risk_outstanding": _safe_number(at_risk.get("secondary_value")),
			"pipeline_potential": _safe_number((pipeline.get("summary") or {}).get("value")),
			"monthly_revenue_last_6": _chart_points(revenue_trend, "ca", "factures"),
			"pipeline_by_status": _chart_breakdown(pipeline, "opportunites", limit=8),
			"revenue_by_customer_group": _chart_breakdown(revenue_by_category, "ca", limit=6),
			"top_customers": [
				{
					"customer": _clip(row.get("customer"), 120),
					"invoice_count": _safe_number(row.get("invoice_count")),
					"amount": _safe_number(row.get("amount")),
				}
				for row in (top_customers.get("rows") or [])[:5]
			],
			"profitable_products": [
				{
					"product": _clip(row.get("item_name"), 120),
					"revenue": _safe_number(row.get("revenue")),
					"margin": _safe_number(row.get("margin")),
					"margin_pct": _safe_number(row.get("margin_pct")),
				}
				for row in (profitable_products.get("rows") or [])[:5]
			],
		},
	}


def build_buying_context(filters: dict[str, Any]) -> dict[str, Any]:
	"""Reagrege les KPIs Achats deja calcules par les widgets existants."""
	spend = _safe_widget_call("BUYING_SPEND_THIS_MONTH", filters) or {}
	monthly_spend = _safe_widget_call("BUYING_MONTHLY_SPEND", filters) or {}
	top_suppliers = _safe_widget_call("BUYING_TOP_SUPPLIERS", filters) or {}
	open_orders = _safe_widget_call("BUYING_OPEN_PURCHASE_ORDERS", filters) or {}

	return {
		"period": _clip(spend.get("context") or open_orders.get("context") or "", 80),
		"currency": _clip(spend.get("currency") or (monthly_spend.get("summary") or {}).get("currency") or "", 16),
		"filters": {
			"company": _clip(filters.get("company"), 80),
			"supplier": _clip(filters.get("supplier"), 120),
			"supplier_group": _clip(filters.get("supplier_group"), 80),
			"period": _clip(filters.get("period"), 40),
		},
		"kpis": {
			"purchase_spend": _safe_number(spend.get("value")),
			"purchase_invoice_count": _safe_number(spend.get("secondary_value")),
			"open_purchase_order_amount": _safe_number(open_orders.get("value")),
			"open_purchase_order_count": _safe_number(open_orders.get("secondary_value")),
			"monthly_spend_last_6": _chart_points(monthly_spend, "achats", "factures"),
			"top_suppliers": [
				{
					"supplier": _clip(row.get("supplier"), 120),
					"invoice_count": _safe_number(row.get("invoice_count")),
					"amount": _safe_number(row.get("amount")),
				}
				for row in (top_suppliers.get("rows") or [])[:5]
			],
		},
	}


# ---------------------------------------------------------------------------
# Prompt + appel LLM
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = (
	"Tu es un analyste ERP francophone experimente en ventes, achats et stock. "
	"Tu recois des KPIs deja agreges et tu produis EXCLUSIVEMENT un objet JSON valide "
	"correspondant au schema fourni, sans bloc Markdown ni texte hors JSON. "
	"Utilise un francais clair et concret, evite le jargon."
)


JSON_SCHEMA_HINT = {
	"summary": "Phrase synthetique en francais (<= 220 caracteres).",
	"anomalies": [
		{
			"label": "Titre court de l'anomalie",
			"severity": "low|medium|high",
			"evidence": "Chiffre ou observation tiree du contexte (<= 200 caracteres)",
		}
	],
	"recommendations": [
		{
			"action": "Action concrete et faisable (<= 200 caracteres)",
			"rationale": "Justification basee sur les KPIs (<= 200 caracteres)",
			"priority": "low|medium|high",
		}
	],
}


def _build_stock_prompt(context: dict[str, Any]) -> list[dict[str, str]]:
	user_payload = {
		"task": (
			"Analyse les KPIs de stock ci-dessous, identifie les anomalies (rotation faible, "
			"dormants eleves, entrepots a risque, sur-reservation, concentration ABC anormale) "
			"et propose 2 a 4 recommandations operationnelles classees par priorite. "
			"Reponds STRICTEMENT en JSON conforme au schema."
		),
		"json_schema": JSON_SCHEMA_HINT,
		"context": context,
		"constraints": [
			"3 anomalies maximum, classees par severite decroissante.",
			"Chaque anomalie doit citer un chiffre du contexte dans 'evidence'.",
			"Pas de hallucination : si une donnee manque, n'invente pas.",
			"Repond en francais.",
		],
	}
	return [
		{"role": "system", "content": SYSTEM_PROMPT},
		{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
	]


def _build_selling_prompt(context: dict[str, Any]) -> list[dict[str, str]]:
	user_payload = {
		"task": (
			"Analyse les KPIs de ventes ci-dessous, identifie les anomalies commerciales "
			"(chiffre d'affaires faible ou concentre, factures en retard, delai de paiement eleve, "
			"pipeline desequilibre, marge produit fragile) et propose 2 a 4 recommandations "
			"commerciales/recouvrement classees par priorite. Reponds STRICTEMENT en JSON conforme au schema."
		),
		"json_schema": JSON_SCHEMA_HINT,
		"context": context,
		"constraints": [
			"3 anomalies maximum, classees par severite decroissante.",
			"Chaque anomalie doit citer un chiffre du contexte dans 'evidence'.",
			"Pas de hallucination : si une donnee manque, n'invente pas.",
			"Repond en francais.",
		],
	}
	return [
		{"role": "system", "content": SYSTEM_PROMPT},
		{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
	]


def _build_buying_prompt(context: dict[str, Any]) -> list[dict[str, str]]:
	user_payload = {
		"task": (
			"Analyse les KPIs d'achats ci-dessous, identifie les anomalies "
			"(depenses concentrees, hausse de tendance, commandes ouvertes elevees, dependance fournisseur) "
			"et propose 2 a 4 recommandations d'approvisionnement ou de controle des couts classees par priorite. "
			"Reponds STRICTEMENT en JSON conforme au schema."
		),
		"json_schema": JSON_SCHEMA_HINT,
		"context": context,
		"constraints": [
			"3 anomalies maximum, classees par severite decroissante.",
			"Chaque anomalie doit citer un chiffre du contexte dans 'evidence'.",
			"Pas de hallucination : si une donnee manque, n'invente pas.",
			"Repond en francais.",
		],
	}
	return [
		{"role": "system", "content": SYSTEM_PROMPT},
		{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
	]


def _message_payload(messages: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
	if not messages:
		return "", []
	user_message = messages[-1].get("content") or ""
	history = [
		{"role": row.get("role") or "user", "content": row.get("content") or ""}
		for row in messages[:-1]
		if row.get("content")
	]
	return user_message, history


def _build_fastapi_payload(
	*,
	endpoint: str,
	widget_name: str,
	filters: dict[str, Any],
	context: dict[str, Any],
	messages: list[dict[str, str]],
) -> dict[str, Any]:
	user_message, history = _message_payload(messages)
	metadata = {
		"task": "dashboard_widget_insight",
		"source": "dashboard_ai_widget",
		"widget_name": widget_name,
		"filters": filters,
		"context": context,
		"original_message": user_message,
		"original_messages": messages,
		"json_schema": JSON_SCHEMA_HINT,
		"response_format": "json",
	}

	if endpoint.rstrip("/") == "/chat":
		system_history = [row for row in history if row.get("role") == "system"][:1]
		return {
			"message": f"Générer une analyse structurée pour le widget IA {widget_name}.",
			"language": "fr",
			"history": system_history,
			"use_rag": False,
			"use_tools": False,
			"metadata": metadata,
		}

	return {
		"widget_name": widget_name,
		"language": "fr",
		"filters": filters,
		"context": context,
		"messages": messages,
		"json_schema": JSON_SCHEMA_HINT,
		"response_format": "json",
	}


def _extract_fastapi_text(payload: dict[str, Any]) -> str:
	if {"summary", "anomalies", "recommendations"}.intersection(payload):
		return json.dumps(payload, ensure_ascii=False)

	for key in ("data", "insight", "result"):
		value = payload.get(key)
		if isinstance(value, dict):
			return json.dumps(value, ensure_ascii=False)

	for key in ("response", "content", "message", "text"):
		value = payload.get(key)
		if isinstance(value, dict):
			return json.dumps(value, ensure_ascii=False)
		if value:
			return str(value)

	return json.dumps(payload, ensure_ascii=False)


def _call_fastapi_insight(
	*,
	widget_name: str,
	filters: dict[str, Any],
	context: dict[str, Any],
	messages: list[dict[str, str]],
	cfg: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
	payload = _build_fastapi_payload(
		endpoint=cfg["endpoint"],
		widget_name=widget_name,
		filters=filters,
		context=context,
		messages=messages,
	)
	result = ai_gateway.post_json(cfg["endpoint"], payload, timeout=cfg["timeout"])
	return _extract_fastapi_text(result), result


# ---------------------------------------------------------------------------
# Parsing reponse
# ---------------------------------------------------------------------------


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _normalize_severity(value: Any) -> str:
	v = (str(value or "")).strip().lower()
	if v in {"high", "haute", "elevee", "critical", "critique"}:
		return "high"
	if v in {"low", "faible", "basse"}:
		return "low"
	return "medium"


def _parse_response(text: str) -> tuple[dict[str, Any], bool]:
	"""Retourne (payload_normalise, parse_failed)."""
	if not text:
		return {"summary": "", "anomalies": [], "recommendations": []}, True

	candidate = text.strip()
	if not candidate.startswith("{"):
		match = _JSON_BLOCK_RE.search(candidate)
		if match:
			candidate = match.group(0)

	try:
		raw = json.loads(candidate)
	except Exception:
		return (
			{
				"summary": text.strip()[:500],
				"anomalies": [],
				"recommendations": [],
			},
			True,
		)

	if not isinstance(raw, dict):
		return ({"summary": text.strip()[:500], "anomalies": [], "recommendations": []}, True)

	anomalies = []
	for entry in raw.get("anomalies") or []:
		if not isinstance(entry, dict):
			continue
		anomalies.append(
			{
				"label": _clip(entry.get("label"), 200),
				"severity": _normalize_severity(entry.get("severity")),
				"evidence": _clip(entry.get("evidence"), 240),
			}
		)

	recommendations = []
	for entry in raw.get("recommendations") or []:
		if not isinstance(entry, dict):
			continue
		recommendations.append(
			{
				"action": _clip(entry.get("action"), 240),
				"rationale": _clip(entry.get("rationale"), 240),
				"priority": _normalize_severity(entry.get("priority")),
			}
		)

	return (
		{
			"summary": _clip(raw.get("summary"), 500),
			"anomalies": anomalies,
			"recommendations": recommendations,
		},
		False,
	)


# ---------------------------------------------------------------------------
# Entry points utilises par les widgets
# ---------------------------------------------------------------------------


def _build_payload(
	*,
	widget_name: str,
	filters: dict[str, Any],
	context: dict[str, Any],
	build_messages,
	force_refresh: bool = False,
) -> dict[str, Any]:
	cfg = _get_config()
	cache_key = _cache_key(widget_name, filters, f"{cfg['service_key']}:{cfg['endpoint']}")

	if not force_refresh:
		cached = _cache_get(cache_key)
		if cached:
			cached["from_cache"] = True
			return cached

	try:
		raw_text, service_payload = _call_fastapi_insight(
			widget_name=widget_name,
			filters=filters,
			context=context,
			messages=build_messages(context),
			cfg=cfg,
		)
	except Exception as exc:
		message = str(exc) or exc.__class__.__name__
		return {
			"summary": "",
			"anomalies": [],
			"recommendations": [],
			"context_snapshot": context,
			"model": cfg["service_key"],
			"generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
			"from_cache": False,
			"parse_failed": False,
			"error": _clip(message, 500),
		}

	parsed, parse_failed = _parse_response(raw_text)
	payload = {
		**parsed,
		"context_snapshot": context,
		"model": service_payload.get("model") or cfg["service_key"],
		"generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
		"from_cache": False,
		"parse_failed": parse_failed,
	}
	if parse_failed:
		payload["raw_response"] = _clip(raw_text, 1000)

	_cache_set(cache_key, payload, cfg["cache_ttl"])
	return payload


def _extract_force_refresh(filters: Any) -> bool:
	"""normalize_filters drope tout champ hors schema, donc on lit le flag avant."""
	raw: Any = filters
	if isinstance(raw, str):
		try:
			raw = frappe.parse_json(raw) or {}
		except Exception:
			raw = {}
	elif raw is None:
		raw = {}
	elif not isinstance(raw, dict):
		raw = {}
	return bool(raw.get("force_refresh"))


def ai_stock_insights_widget(filters=None, widget=None) -> dict[str, Any]:
	"""Widget IA Stock : synthese, anomalies, recommandations."""
	force_refresh = _extract_force_refresh(filters)
	resolved_filters = widget_executor.normalize_filters(filters, widget_name="AI_STOCK_INSIGHTS")

	context = build_stock_context(resolved_filters)
	return _build_payload(
		widget_name="AI_STOCK_INSIGHTS",
		filters=resolved_filters,
		context=context,
			build_messages=_build_stock_prompt,
			force_refresh=force_refresh,
		)


def ai_selling_insights_widget(filters=None, widget=None) -> dict[str, Any]:
	"""Widget IA Ventes : synthese, anomalies, recommandations."""
	force_refresh = _extract_force_refresh(filters)
	resolved_filters = widget_executor.normalize_filters(filters, widget_name="AI_SELLING_INSIGHTS")

	context = build_selling_context(resolved_filters)
	return _build_payload(
		widget_name="AI_SELLING_INSIGHTS",
		filters=resolved_filters,
		context=context,
		build_messages=_build_selling_prompt,
		force_refresh=force_refresh,
	)


def ai_buying_insights_widget(filters=None, widget=None) -> dict[str, Any]:
	"""Widget IA Achats : synthese, anomalies, recommandations."""
	force_refresh = _extract_force_refresh(filters)
	resolved_filters = widget_executor.normalize_filters(filters, widget_name="AI_BUYING_INSIGHTS")

	context = build_buying_context(resolved_filters)
	return _build_payload(
		widget_name="AI_BUYING_INSIGHTS",
		filters=resolved_filters,
		context=context,
		build_messages=_build_buying_prompt,
		force_refresh=force_refresh,
	)
