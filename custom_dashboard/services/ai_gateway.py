from __future__ import annotations

import time
from typing import Any

import frappe
import jwt
import requests
from frappe import _


DEFAULT_FASTAPI_URL = "http://127.0.0.1:9001"
DEFAULT_HTTP_TIMEOUT = 60
DEFAULT_JWT_TTL = 60


class AIServiceError(RuntimeError):
	"""Raised when the shared FastAPI/Cohere service cannot complete a request."""


def get_config() -> dict[str, Any]:
	conf = frappe.conf or {}
	fastapi_url = (
		conf.get("chatbot_fastapi_url")
		or conf.get("ai_fastapi_url")
		or DEFAULT_FASTAPI_URL
	)
	return {
		"fastapi_url": fastapi_url.rstrip("/"),
		"fastapi_public_url": (
			conf.get("chatbot_fastapi_public_url")
			or conf.get("ai_fastapi_public_url")
			or fastapi_url
		).rstrip("/"),
		"jwt_secret": conf.get("chatbot_jwt_secret") or conf.get("ai_jwt_secret"),
		"jwt_algorithm": conf.get("chatbot_jwt_algorithm") or conf.get("ai_jwt_algorithm") or "HS256",
		"jwt_ttl": int(conf.get("chatbot_jwt_ttl") or conf.get("ai_jwt_ttl") or DEFAULT_JWT_TTL),
		"http_timeout": float(
			conf.get("chatbot_http_timeout")
			or conf.get("ai_http_timeout")
			or DEFAULT_HTTP_TIMEOUT
		),
	}


def _get_user_company() -> str | None:
	try:
		return (
			frappe.defaults.get_user_default("Company")
			or frappe.defaults.get_global_default("company")
			or None
		)
	except Exception:
		return None


def sign_jwt(cfg: dict[str, Any] | None = None) -> str:
	cfg = cfg or get_config()
	if not cfg["jwt_secret"]:
		raise AIServiceError(
			"chatbot_jwt_secret manquant dans site_config.json. "
			"Configure le meme secret que le service FastAPI/Cohere."
		)

	now = int(time.time())
	payload = {
		"user": frappe.session.user,
		"roles": frappe.get_roles(),
		"company": _get_user_company(),
		"iat": now,
		"exp": now + cfg["jwt_ttl"],
	}
	return jwt.encode(payload, cfg["jwt_secret"], algorithm=cfg["jwt_algorithm"])


def post_json(
	endpoint: str,
	payload: dict[str, Any],
	*,
	timeout: float | None = None,
	allow_guest: bool = False,
) -> dict[str, Any]:
	if frappe.session.user == "Guest" and not allow_guest:
		frappe.throw(_("Authentification requise"), frappe.PermissionError)

	cfg = get_config()
	endpoint = "/" + (endpoint or "").lstrip("/")
	headers = {
		"Authorization": f"Bearer {sign_jwt(cfg)}",
		"Content-Type": "application/json",
	}

	try:
		response = requests.post(
			f"{cfg['fastapi_url']}{endpoint}",
			json=payload,
			headers=headers,
			timeout=timeout or cfg["http_timeout"],
		)
	except requests.exceptions.ConnectionError as exc:
		raise AIServiceError("Service IA FastAPI indisponible.") from exc
	except requests.exceptions.Timeout as exc:
		raise AIServiceError("Le service IA FastAPI n'a pas repondu dans les delais.") from exc

	if response.status_code == 401:
		raise AIServiceError("JWT rejete par le service IA FastAPI.")
	if response.status_code == 429:
		raise AIServiceError("Limite du service IA atteinte, reessayez dans une minute.")
	if response.status_code >= 400:
		raise AIServiceError(f"Service IA FastAPI HTTP {response.status_code}: {response.text[:300]}")

	try:
		data = response.json()
	except Exception as exc:
		raise AIServiceError("Reponse FastAPI invalide (non JSON).") from exc

	if not isinstance(data, dict):
		raise AIServiceError("Reponse FastAPI invalide.")
	return data
