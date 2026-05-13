from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from custom_dashboard.services import access, widget_registry


DEFAULT_WIDGET_W = 6
DEFAULT_WIDGET_H = 4
SUPPORTED_MODULE_DASHBOARDS = {"Stock", "Selling", "Buying"}


def _parse_payload(doc) -> dict[str, Any]:
	payload = frappe.parse_json(doc) if isinstance(doc, str) else doc
	as_dict = getattr(payload, "as_dict", None)
	if callable(as_dict):
		payload = as_dict()

	if not isinstance(payload, dict):
		frappe.throw(_("Le payload du dashboard doit etre un objet JSON."))

	return payload


def _serialize_filters_json(filters_payload) -> str:
	if filters_payload in (None, "", {}):
		return ""

	try:
		payload = (
			frappe.parse_json(filters_payload) if isinstance(filters_payload, str) else filters_payload
		)
	except Exception as exc:
		frappe.throw(_("Les filtres doivent etre un JSON valide."), exc=exc.__class__)

	if payload in (None, "", {}):
		return ""

	return frappe.as_json(payload, indent=2)


def _normalize_module_name(value: str | None) -> str:
	module_name = (value or "").strip()
	if not module_name:
		return ""

	if module_name not in SUPPORTED_MODULE_DASHBOARDS:
		frappe.throw(
			_("Les modules supportes sont: {0}.").format(
				", ".join(sorted(SUPPORTED_MODULE_DASHBOARDS))
			)
		)

	return module_name


def _assert_module_widget_compatibility(widget_doc, module_name: str) -> None:
	if not module_name:
		return

	widget_module_name = (getattr(widget_doc, "module_name", "") or "").strip()
	if widget_module_name == module_name:
		return

	frappe.throw(
		_("Le widget {0} n'est pas disponible pour le module {1}.").format(
			frappe.bold(widget_doc.title or widget_doc.name), frappe.bold(module_name)
		)
	)


def _get_module_dashboard_target(
	module_name: str, current_user: str, current_name: str | None = None
):
	module_name = _normalize_module_name(module_name)
	access.require_dashboard_admin(current_user)

	if current_name:
		current_doc = access.assert_dashboard_write_access(current_name, user=current_user)
		if (current_doc.module_name or "").strip() == module_name:
			return current_doc

	existing_dashboards = frappe.get_all(
		"User Dashboard",
		filters={"module_name": module_name},
		pluck="name",
		order_by="is_default desc, modified desc",
		limit_page_length=1,
	)
	if existing_dashboards:
		return access.assert_dashboard_write_access(existing_dashboards[0], user=current_user)

	return frappe.new_doc("User Dashboard")


def _default_layout(widget_name: str, widget_type: str | None = None) -> dict[str, int]:
	layout = widget_registry.get_widget_default_layout(widget_name)
	return {
		"w": max(cint(layout.get("w") or DEFAULT_WIDGET_W), 1),
		"h": max(cint(layout.get("h") or (5 if widget_type == "table" else DEFAULT_WIDGET_H)), 1),
	}


def _serialize_share_row(row) -> dict[str, Any]:
	return {
		"name": getattr(row, "name", None),
		"share_type": row.share_type,
		"user": getattr(row, "user", "") or "",
		"role": getattr(row, "role", "") or "",
		"can_edit": cint(row.can_edit),
	}


def _serialize_dashboard_item(item, user: str | None = None) -> dict[str, Any] | None:
	if not access.can_access_widget(item.widget, user=user, action="view", require_active=True):
		return None

	widget_doc = access.get_widget_doc(item.widget)
	return {
		"name": item.name,
		"widget": item.widget,
		"x": cint(item.x),
		"y": cint(item.y),
		"w": cint(item.w),
		"h": cint(item.h),
		"display_title": item.display_title or widget_doc.title,
		"filters_json": item.filters_json or "",
		"widget_definition": widget_registry.serialize_widget_definition(widget_doc, user=user),
	}


def serialize_dashboard(doc, user: str | None = None) -> dict[str, Any]:
	current_user = access.get_current_user(user)
	items = []
	for item in doc.get("items") or []:
		serialized = _serialize_dashboard_item(item, user=current_user)
		if serialized:
			items.append(serialized)

	share_flags = access.get_dashboard_share_flags(doc, user=current_user)
	can_manage_sharing = access.can_manage_dashboard_sharing(doc, user=current_user)

	return {
		"name": doc.name,
		"title": doc.title,
		"user": doc.user,
		"module_name": getattr(doc, "module_name", "") or "",
		"is_active": 1 if access.is_dashboard_active(doc) else 0,
		"is_default": cint(doc.is_default),
		"is_shared": cint(doc.is_shared),
		"can_write": share_flags["can_edit"],
		"can_manage_sharing": can_manage_sharing,
		"is_owner": share_flags["is_owner"],
		"items": items,
		"shares": [_serialize_share_row(row) for row in doc.get("shares") or []] if can_manage_sharing else [],
	}


def list_user_dashboards(user: str | None = None) -> list[dict[str, Any]]:
	current_user = access.get_current_user(user)
	access.require_builder_access(current_user)

	dashboards = frappe.get_all(
		"User Dashboard",
		fields=[
			"name",
			"title",
			"user",
			"module_name",
			"is_active",
			"is_default",
			"is_shared",
			"modified",
		],
		order_by="is_default desc, modified desc",
	)

	result = []
	for dashboard in dashboards:
		if not access.can_read_dashboard(dashboard, user=current_user):
			continue

		share_flags = access.get_dashboard_share_flags(dashboard, user=current_user)
		result.append(
			{
				"name": dashboard.name,
				"title": dashboard.title,
				"user": dashboard.user,
				"module_name": dashboard.module_name or "",
				"is_active": cint(dashboard.is_active if dashboard.is_active is not None else 1),
				"is_default": cint(dashboard.is_default),
				"is_shared": cint(dashboard.is_shared),
				"can_write": share_flags["can_edit"],
				"is_owner": share_flags["is_owner"],
				"modified": dashboard.modified,
			}
		)

	return result


def get_dashboard(name: str, user: str | None = None) -> dict[str, Any]:
	dashboard_doc = access.assert_dashboard_read_access(name, user=user)
	return serialize_dashboard(dashboard_doc, user=user)


def get_module_dashboard(module_name: str, user: str | None = None) -> dict[str, Any] | None:
	module_name = _normalize_module_name(module_name)
	current_user = access.get_current_user(user)
	if not access.has_builder_access(current_user):
		return None

	existing = frappe.get_all(
		"User Dashboard",
		filters={"module_name": module_name},
		pluck="name",
		order_by="is_default desc, modified desc",
		limit_page_length=1,
	)
	if not existing:
		return None

	dashboard_doc = frappe.get_doc("User Dashboard", existing[0])
	is_active = access.is_dashboard_active(dashboard_doc)
	is_admin = access.is_dashboard_admin(current_user)

	if not is_active and not is_admin:
		return {
			"name": dashboard_doc.name,
			"title": dashboard_doc.title,
			"module_name": module_name,
			"is_active": 0,
			"disabled": True,
			"items": [],
			"shares": [],
			"can_write": False,
			"can_manage_sharing": False,
			"is_owner": False,
			"is_default": cint(dashboard_doc.is_default),
			"is_shared": cint(dashboard_doc.is_shared),
			"disabled_message": _(
				"Ce tableau de bord est actuellement désactivé par l'administrateur."
			),
		}

	if not access.can_read_dashboard(dashboard_doc, user=current_user):
		return None

	payload = serialize_dashboard(dashboard_doc, user=current_user)
	payload["disabled"] = not is_active
	if not is_active:
		payload["disabled_message"] = _(
			"Ce tableau de bord est actuellement désactivé par l'administrateur."
		)
	return payload


def can_view_module_dashboard(module_name: str, user: str | None = None) -> bool:
	"""Light check used by the frontend redirect to decide if /app/<module> should swap."""
	try:
		module_name = _normalize_module_name(module_name)
	except Exception:
		return False

	current_user = access.get_current_user(user)
	if not access.has_builder_access(current_user):
		return False

	existing = frappe.get_all(
		"User Dashboard",
		filters={"module_name": module_name},
		pluck="name",
		order_by="is_default desc, modified desc",
		limit_page_length=1,
	)
	if not existing:
		return False

	return access.can_read_dashboard(existing[0], user=current_user)


def get_sharing_options(user: str | None = None) -> dict[str, list[dict[str, str]]]:
	current_user = access.get_current_user(user)
	access.require_builder_access(current_user)

	users = frappe.get_all(
		"User",
		filters={"enabled": 1, "user_type": ["!=", "Website User"]},
		fields=["name", "full_name"],
		order_by="full_name asc, name asc",
	)
	return {
		"users": [
			{
				"value": row.name,
				"label": row.full_name or row.name,
			}
			for row in users
		],
		"roles": [{"value": role, "label": role} for role in access.get_assignable_roles()],
	}


def _apply_dashboard_shares(target, payload: dict[str, Any], user: str | None = None) -> None:
	if not access.can_manage_dashboard_sharing(target, user=user):
		return

	target.set("shares", [])
	seen = set()
	for row in payload.get("shares") or []:
		share_type = (row.get("share_type") or "").strip()
		role = (row.get("role") or "").strip()
		shared_user = (row.get("user") or "").strip()
		if share_type not in {"User", "Role"}:
			continue
		if share_type == "User" and not shared_user:
			continue
		if share_type == "Role" and not role:
			continue

		key = (share_type, shared_user or role)
		if key in seen:
			continue
		seen.add(key)

		target.append(
			"shares",
			{
				"share_type": share_type,
				"user": shared_user if share_type == "User" else None,
				"role": role if share_type == "Role" else None,
				"can_edit": cint(row.get("can_edit")),
			},
		)


def _apply_dashboard_payload(target, payload: dict[str, Any], user: str | None = None) -> None:
	current_user = access.get_current_user(user)
	is_admin = access.is_dashboard_admin(current_user)
	can_manage_sharing = target.is_new() or access.can_manage_dashboard_sharing(target, user=current_user)
	module_name = _normalize_module_name(payload.get("module_name"))

	target.title = (payload.get("title") or "").strip()
	if not target.title:
		frappe.throw(_("Le titre du tableau de bord est obligatoire."))

	if target.is_new():
		target.user = (
			payload.get("user") if is_admin and payload.get("user") and not module_name else current_user
		)
	elif can_manage_sharing and is_admin and payload.get("user") and not module_name:
		target.user = payload.get("user")

	target.module_name = module_name
	if is_admin and "is_active" in payload:
		target.is_active = 1 if cint(payload.get("is_active")) else 0
	elif target.is_active is None:
		target.is_active = 1
	if can_manage_sharing:
		if module_name:
			target.is_default = 1
			target.is_shared = 1
			target.set("shares", [])
		else:
			target.is_default = cint(payload.get("is_default"))
			target.is_shared = cint(payload.get("is_shared"))
			_apply_dashboard_shares(target, payload, user=current_user)

	target.set("items", [])
	for index, item in enumerate(payload.get("items") or [], start=1):
		widget_doc = access.assert_widget_access(
			item.get("widget"),
			user=current_user,
			action="use",
			require_active=True,
		)
		_assert_module_widget_compatibility(widget_doc, module_name)
		layout = _default_layout(widget_doc.name, widget_doc.widget_type)
		target.append(
			"items",
			{
				"widget": widget_doc.name,
				"x": max(cint(item.get("x")), 0),
				"y": cint(item.get("y")) if item.get("y") is not None else (index - 1) * 4,
				"w": max(cint(item.get("w")) or layout["w"], 1),
				"h": max(cint(item.get("h")) or layout["h"], 1),
				"display_title": (item.get("display_title") or widget_doc.title).strip(),
				"filters_json": _serialize_filters_json(item.get("filters_json")),
			},
		)


def _clear_other_defaults(doc) -> None:
	if not cint(doc.is_default):
		return

	frappe.db.sql(
		"""
			update `tabUser Dashboard`
			set is_default = 0
			where user = %s and name != %s
		""",
		(doc.user, doc.name),
	)


def _clear_other_module_defaults(doc) -> None:
	if not cint(doc.is_default):
		return

	module_name = (getattr(doc, "module_name", "") or "").strip()
	if not module_name:
		return

	frappe.db.sql(
		"""
			update `tabUser Dashboard`
			set is_default = 0
			where module_name = %s and name != %s
		""",
		(module_name, doc.name),
	)


def save_user_dashboard(doc, user: str | None = None) -> dict[str, Any]:
	current_user = access.get_current_user(user)
	access.require_builder_access(current_user)

	payload = _parse_payload(doc)
	name = payload.get("name")
	module_name = _normalize_module_name(payload.get("module_name"))

	if module_name:
		target = _get_module_dashboard_target(module_name, current_user, current_name=name)
	elif name:
		target = access.assert_dashboard_write_access(name, user=current_user)
	else:
		target = frappe.new_doc("User Dashboard")

	_apply_dashboard_payload(target, payload, user=current_user)
	target.save(ignore_permissions=True)
	if access.can_manage_dashboard_sharing(target, user=current_user):
		if (target.module_name or "").strip():
			_clear_other_module_defaults(target)
		else:
			_clear_other_defaults(target)

	return serialize_dashboard(target, user=current_user)


CATEGORY_MODULE_MAPPING = {
	"Stock": "Stock",
	"Vente": "Selling",
	"Achat": "Buying",
}

MODULE_CATEGORY_LABELS = {
	"Stock": "Stock",
	"Selling": "Vente",
	"Buying": "Achat",
}


def _category_to_module(category: str | None) -> str | None:
	if not category:
		return None
	cleaned = category.strip()
	if cleaned in CATEGORY_MODULE_MAPPING:
		return CATEGORY_MODULE_MAPPING[cleaned]
	if cleaned in CATEGORY_MODULE_MAPPING.values():
		return cleaned
	return None


def _module_to_category(module_name: str | None) -> str:
	module = (module_name or "").strip()
	return MODULE_CATEGORY_LABELS.get(module, "")


def _serialize_admin_share(row) -> dict[str, Any]:
	share_type = (row.get("share_type") if hasattr(row, "get") else getattr(row, "share_type", "")) or ""
	return {
		"share_type": share_type,
		"user": (row.get("user") if hasattr(row, "get") else getattr(row, "user", "")) or "",
		"role": (row.get("role") if hasattr(row, "get") else getattr(row, "role", "")) or "",
		"can_edit": cint(row.get("can_edit") if hasattr(row, "get") else getattr(row, "can_edit", 0)),
	}


def list_admin_dashboards(
	category: str | None = None,
	user: str | None = None,
) -> list[dict[str, Any]]:
	access.require_dashboard_admin(user)
	filters: dict[str, Any] = {}
	module_filter = _category_to_module(category)
	if category and not module_filter:
		return []
	if module_filter:
		filters["module_name"] = module_filter

	rows = frappe.get_all(
		"User Dashboard",
		filters=filters,
		fields=[
			"name",
			"title",
			"user",
			"module_name",
			"is_active",
			"is_default",
			"is_shared",
			"modified",
		],
		order_by="modified desc",
	)

	dashboards = []
	for row in rows:
		shares = frappe.get_all(
			"User Dashboard Share",
			filters={"parent": row.name, "parenttype": "User Dashboard"},
			fields=["share_type", "user", "role", "can_edit"],
		)
		access_label = "private"
		if any(s.share_type == "User" for s in shares):
			access_label = "user"
		elif any(s.share_type == "Role" for s in shares):
			access_label = "role"
		if cint(row.is_shared):
			access_label = "global"

		dashboards.append(
			{
				"name": row.name,
				"title": row.title,
				"user": row.user,
				"module_name": row.module_name or "",
				"category": _module_to_category(row.module_name),
				"is_active": cint(row.is_active if row.is_active is not None else 1),
				"is_default": cint(row.is_default),
				"is_shared": cint(row.is_shared),
				"access_label": access_label,
				"share_count": len(shares),
				"modified": row.modified,
			}
		)
	return dashboards


def get_admin_dashboard(name: str, user: str | None = None) -> dict[str, Any]:
	access.require_dashboard_admin(user)
	doc = frappe.get_doc("User Dashboard", name)
	return {
		"name": doc.name,
		"title": doc.title,
		"user": doc.user,
		"module_name": (doc.module_name or "").strip(),
		"category": _module_to_category(doc.module_name),
		"is_active": cint(doc.is_active if doc.is_active is not None else 1),
		"is_default": cint(doc.is_default),
		"is_shared": cint(doc.is_shared),
		"shares": [_serialize_admin_share(row) for row in doc.get("shares") or []],
	}


def admin_save_dashboard(doc, user: str | None = None) -> dict[str, Any]:
	access.require_dashboard_admin(user)
	payload = _parse_payload(doc)
	category = (payload.get("category") or "").strip()
	module_name = _category_to_module(category) if category else _normalize_module_name(payload.get("module_name"))
	payload["module_name"] = module_name or ""

	name = payload.get("name")
	if name:
		target = frappe.get_doc("User Dashboard", name)
	else:
		target = frappe.new_doc("User Dashboard")

	current_user = access.get_current_user(user)
	target.title = (payload.get("title") or "").strip()
	if not target.title:
		frappe.throw(_("Le titre du tableau de bord est obligatoire."))
	target.user = payload.get("user") or target.user or current_user
	target.module_name = module_name or ""
	target.is_active = 1 if cint(payload.get("is_active", 1)) else 0
	target.is_default = cint(payload.get("is_default"))
	target.is_shared = cint(payload.get("is_shared"))

	target.set("shares", [])
	if not module_name:
		_apply_dashboard_shares(target, payload, user=current_user)

	target.save(ignore_permissions=True)
	if module_name:
		_clear_other_module_defaults(target)
	else:
		_clear_other_defaults(target)
	frappe.clear_document_cache("User Dashboard", target.name)
	return get_admin_dashboard(target.name, user=user)


def admin_toggle_dashboard_active(
	name: str, is_active: int | bool, user: str | None = None
) -> dict[str, Any]:
	access.require_dashboard_admin(user)
	doc = frappe.get_doc("User Dashboard", name)
	doc.is_active = 1 if cint(is_active) else 0
	doc.save(ignore_permissions=True)
	frappe.clear_document_cache("User Dashboard", name)
	return get_admin_dashboard(name, user=user)


def admin_delete_dashboard(name: str, user: str | None = None) -> dict[str, Any]:
	access.require_dashboard_admin(user)
	if not frappe.db.exists("User Dashboard", name):
		frappe.throw(_("Tableau de bord introuvable: {0}").format(name))
	frappe.delete_doc("User Dashboard", name, ignore_permissions=True, force=True)
	frappe.clear_document_cache("User Dashboard", name)
	return {"name": name, "deleted": True}


def admin_duplicate_dashboard(name: str, user: str | None = None) -> dict[str, Any]:
	access.require_dashboard_admin(user)
	source = frappe.get_doc("User Dashboard", name)
	clone = frappe.new_doc("User Dashboard")
	clone.title = f"{source.title} - copie"
	clone.user = source.user
	clone.module_name = ""
	clone.is_active = cint(source.is_active if source.is_active is not None else 1)
	clone.is_default = 0
	clone.is_shared = cint(source.is_shared)
	clone.set("shares", [])
	for row in source.get("shares") or []:
		clone.append(
			"shares",
			{
				"share_type": row.share_type,
				"user": row.user,
				"role": row.role,
				"can_edit": cint(row.can_edit),
			},
		)
	clone.set("items", [])
	for item in source.get("items") or []:
		clone.append(
			"items",
			{
				"widget": item.widget,
				"x": cint(item.x),
				"y": cint(item.y),
				"w": cint(item.w),
				"h": cint(item.h),
				"display_title": item.display_title,
				"filters_json": item.filters_json,
			},
		)
	clone.save(ignore_permissions=True)
	frappe.clear_document_cache("User Dashboard", clone.name)
	return get_admin_dashboard(clone.name, user=user)
