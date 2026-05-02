from __future__ import annotations

from typing import Any

import frappe


DEFAULT_RAG_DOCTYPES: dict[str, dict[str, Any]] = {
	"Item": {
		"fields": ["item_code", "item_name", "description", "item_group", "brand"],
		"metadata_fields": ["item_group", "brand", "disabled"],
	},
	"Customer": {
		"fields": ["customer_name", "customer_group", "territory", "customer_type"],
		"metadata_fields": ["customer_group", "territory"],
	},
	"Supplier": {
		"fields": ["supplier_name", "supplier_group", "supplier_type"],
		"metadata_fields": ["supplier_group"],
	},
	"Sales Invoice": {
		"fields": ["customer", "customer_name", "posting_date", "status", "grand_total", "remarks"],
		"metadata_fields": ["company", "customer", "status"],
	},
	"Purchase Invoice": {
		"fields": ["supplier", "supplier_name", "posting_date", "status", "grand_total", "remarks"],
		"metadata_fields": ["company", "supplier", "status"],
	},
	"Sales Order": {
		"fields": ["customer", "customer_name", "transaction_date", "delivery_date", "status", "grand_total"],
		"metadata_fields": ["company", "customer", "status"],
	},
	"Purchase Order": {
		"fields": ["supplier", "supplier_name", "transaction_date", "schedule_date", "status", "grand_total"],
		"metadata_fields": ["company", "supplier", "status"],
	},
	"Project": {
		"fields": ["project_name", "status", "customer", "expected_start_date", "expected_end_date", "notes"],
		"metadata_fields": ["company", "customer", "status"],
	},
	"Task": {
		"fields": ["subject", "status", "priority", "project", "description", "exp_start_date", "exp_end_date"],
		"metadata_fields": ["project", "status", "priority"],
	},
	"Issue": {
		"fields": ["subject", "status", "priority", "customer", "description", "resolution_details"],
		"metadata_fields": ["company", "customer", "status", "priority"],
	},
}


def _parse_configured_doctypes(raw: Any) -> dict[str, dict[str, Any]]:
	if not raw:
		return DEFAULT_RAG_DOCTYPES
	if isinstance(raw, str):
		try:
			raw = frappe.parse_json(raw)
		except Exception:
			frappe.log_error("Invalid rag_index_doctypes JSON", "RAG config")
			return DEFAULT_RAG_DOCTYPES
	if isinstance(raw, list):
		return {str(doctype): {} for doctype in raw if doctype}
	if isinstance(raw, dict):
		return {str(doctype): (opts or {}) for doctype, opts in raw.items() if doctype}
	return DEFAULT_RAG_DOCTYPES


def get_rag_doctypes() -> dict[str, dict[str, Any]]:
	"""Return the DocTypes enabled for automatic RAG indexing.

	Override with site_config.json:
	    "rag_index_doctypes": ["Item", "Customer"]
	or:
	    "rag_index_doctypes": {"Item": {"fields": ["item_name", "description"]}}
	"""
	return _parse_configured_doctypes((frappe.conf or {}).get("rag_index_doctypes"))


def is_rag_enabled() -> bool:
	return bool((frappe.conf or {}).get("rag_index_enabled", 1))


def is_rag_doctype(doctype: str) -> bool:
	return is_rag_enabled() and doctype in get_rag_doctypes()


def get_doctype_options(doctype: str) -> dict[str, Any]:
	return get_rag_doctypes().get(doctype, {})
