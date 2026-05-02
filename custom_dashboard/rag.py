from __future__ import annotations

import json
from typing import Any

import frappe
import requests
from frappe import _

from custom_dashboard.rag_config import get_doctype_options, is_rag_doctype


DEFAULT_RAG_TIMEOUT = 30
INTERNAL_FIELDS = {
	"_assign",
	"_comments",
	"_liked_by",
	"_seen",
	"amended_from",
	"creation",
	"docstatus",
	"idx",
	"lft",
	"modified_by",
	"old_parent",
	"parent",
	"parentfield",
	"parenttype",
	"rgt",
}
SENSITIVE_FIELD_PARTS = ("password", "secret", "token", "api_key", "api_secret")


def _get_fastapi_url() -> str:
	conf = frappe.conf or {}
	return (conf.get("rag_fastapi_url") or conf.get("chatbot_fastapi_url") or "http://127.0.0.1:9001").rstrip("/")


def _get_internal_api_key() -> str | None:
	return (frappe.conf or {}).get("rag_internal_api_key")


def _request_headers() -> dict[str, str]:
	api_key = _get_internal_api_key()
	if not api_key:
		frappe.throw(_("rag_internal_api_key manquant dans site_config.json"))
	return {"X-RAG-API-Key": api_key, "Content-Type": "application/json"}


def _jsonable(value: Any) -> Any:
	return json.loads(frappe.as_json(value))


def _field_is_sensitive(fieldname: str) -> bool:
	lower = fieldname.lower()
	return any(part in lower for part in SENSITIVE_FIELD_PARTS)


def _clean_value(value: Any) -> Any:
	if isinstance(value, list):
		return [_clean_value(item) for item in value]
	if isinstance(value, dict):
		return {
			key: _clean_value(item)
			for key, item in value.items()
			if key not in INTERNAL_FIELDS and not _field_is_sensitive(str(key))
		}
	return _jsonable(value)


def _extract_configured_data(doc, options: dict[str, Any]) -> dict[str, Any]:
	fields = options.get("fields") or []
	if not fields:
		return _clean_value(doc.as_dict())

	data = {"doctype": doc.doctype, "name": doc.name}
	for fieldname in fields:
		if hasattr(doc, fieldname):
			data[fieldname] = _clean_value(doc.get(fieldname))
	return data


def _read_roles_for_doctype(doctype: str) -> list[str]:
	try:
		return sorted(
			{
				row.role
				for row in frappe.get_all(
					"DocPerm",
					filters={"parent": doctype, "read": 1},
					fields=["role"],
					limit_page_length=0,
				)
				if row.role
			}
		)
	except Exception:
		return []


def _shared_users(doctype: str, docname: str) -> list[str]:
	try:
		if not frappe.db.table_exists("DocShare"):
			return []
		return sorted(
			{
				row.user
				for row in frappe.get_all(
					"DocShare",
					filters={"share_doctype": doctype, "share_name": docname, "read": 1},
					fields=["user"],
					limit_page_length=0,
				)
				if row.user
			}
		)
	except Exception:
		return []


def _metadata_for_doc(doc, options: dict[str, Any]) -> dict[str, Any]:
	metadata_fields = set(options.get("metadata_fields") or [])
	if hasattr(doc, "company"):
		metadata_fields.add("company")

	metadata: dict[str, Any] = {
		"doctype": doc.doctype,
		"docname": doc.name,
		"owner": doc.owner,
		"modified": str(doc.modified) if doc.modified else None,
		"permitted_roles": options.get("permitted_roles") or _read_roles_for_doctype(doc.doctype),
		"allowed_users": _shared_users(doc.doctype, doc.name),
	}

	for fieldname in metadata_fields:
		if hasattr(doc, fieldname):
			metadata[fieldname] = _clean_value(doc.get(fieldname))

	return {key: value for key, value in metadata.items() if value not in (None, "", [])}


def build_rag_document(doc) -> dict[str, Any]:
	options = get_doctype_options(doc.doctype)
	return {
		"doctype": doc.doctype,
		"docname": doc.name,
		"data": _extract_configured_data(doc, options),
		"metadata": _metadata_for_doc(doc, options),
		"modified": str(doc.modified) if doc.modified else None,
	}


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
	response = requests.post(
		f"{_get_fastapi_url()}{path}",
		headers=_request_headers(),
		json=payload,
		timeout=int((frappe.conf or {}).get("rag_http_timeout") or DEFAULT_RAG_TIMEOUT),
	)
	if response.status_code >= 400:
		frappe.log_error(
			title=f"RAG FastAPI HTTP {response.status_code}",
			message=response.text[:4000],
		)
		response.raise_for_status()
	return response.json()


def on_rag_doc_update(doc, method=None) -> None:
	if not is_rag_doctype(doc.doctype):
		return
	if not _get_internal_api_key():
		return
	frappe.enqueue(
		"custom_dashboard.rag.index_document",
		doctype=doc.doctype,
		docname=doc.name,
		queue="short",
		timeout=120,
		enqueue_after_commit=True,
	)


def on_rag_doc_trash(doc, method=None) -> None:
	if not is_rag_doctype(doc.doctype):
		return
	if not _get_internal_api_key():
		return
	frappe.enqueue(
		"custom_dashboard.rag.delete_document",
		doctype=doc.doctype,
		docname=doc.name,
		queue="short",
		timeout=60,
		enqueue_after_commit=True,
	)


def index_document(doctype: str, docname: str) -> dict[str, Any]:
	if not is_rag_doctype(doctype):
		return {"status": "skipped", "reason": "doctype_not_enabled", "doctype": doctype}
	doc = frappe.get_doc(doctype, docname)
	payload = {"document": build_rag_document(doc)}
	return _post("/rag/index", payload)


def delete_document(doctype: str, docname: str) -> dict[str, Any]:
	return _post("/rag/delete", {"doctype": doctype, "docname": docname})


@frappe.whitelist()
def reindex_document(doctype: str, docname: str) -> dict[str, Any]:
	if not frappe.has_permission(doctype, "read", docname):
		frappe.throw(_("Acces non autorise"), frappe.PermissionError)
	return index_document(doctype, docname)


@frappe.whitelist()
def reindex_doctype(doctype: str, limit: int = 100, modified_after: str | None = None) -> dict[str, Any]:
	if not is_rag_doctype(doctype):
		frappe.throw(_("DocType non active pour le RAG: {0}").format(doctype))

	filters = {}
	if modified_after:
		filters["modified"] = [">=", modified_after]

	rows = frappe.get_all(
		doctype,
		filters=filters,
		fields=["name"],
		order_by="modified desc",
		limit_page_length=int(limit or 100),
	)
	for row in rows:
		frappe.enqueue(
			"custom_dashboard.rag.index_document",
			doctype=doctype,
			docname=row.name,
			queue="short",
			timeout=120,
			enqueue_after_commit=True,
		)
	return {"status": "queued", "doctype": doctype, "count": len(rows)}
