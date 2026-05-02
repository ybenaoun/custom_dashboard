from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


ADMIN_ROLES = {"System Manager", "Dashboard Admin"}
BUILDER_ROLES = ADMIN_ROLES | {"Dashboard Manager", "Dashboard Consumer"}
READ_TYPES = {"read", "report", "export", "print", "email", "share"}
WRITE_TYPES = {"write", "delete"}
IGNORED_ROLES = {"All", "Guest"}


def get_current_user(user: str | None = None) -> str:
	return user or frappe.session.user


def get_user_roles(user: str | None = None) -> set[str]:
	user = get_current_user(user)
	if user == "Administrator":
		return set(ADMIN_ROLES)
	return set(frappe.get_roles(user))


def get_assignable_roles() -> list[str]:
	roles = frappe.get_all(
		"Role",
		filters={"name": ["not in", sorted(IGNORED_ROLES)]},
		pluck="name",
		order_by="name asc",
	)
	return roles


def is_dashboard_admin(user: str | None = None) -> bool:
	user = get_current_user(user)
	if user == "Administrator":
		return True
	return bool(ADMIN_ROLES & get_user_roles(user))


def require_dashboard_admin(user: str | None = None) -> None:
	if not is_dashboard_admin(user):
		frappe.throw(
			_("Vous devez avoir un role administrateur du dashboard pour effectuer cette action."),
			frappe.PermissionError,
		)


def has_builder_access(user: str | None = None) -> bool:
	return is_dashboard_admin(user) or bool(get_user_roles(user) & BUILDER_ROLES)


def require_builder_access(user: str | None = None) -> None:
	if not has_builder_access(user):
		frappe.throw(
			_("Vous n'etes pas autorise a acceder au constructeur de tableaux de bord."),
			frappe.PermissionError,
		)


def get_widget_doc(widget: str | Document) -> Document:
	if isinstance(widget, Document):
		return widget
	if isinstance(widget, dict):
		return frappe._dict(widget)
	return frappe.get_cached_doc("Custom Dashboard Widget", widget)


def get_dashboard_doc(dashboard: str | Document) -> Document:
	if isinstance(dashboard, Document):
		return dashboard
	if isinstance(dashboard, dict):
		return frappe._dict(dashboard)
	return frappe.get_doc("User Dashboard", dashboard)


def is_widget_active(widget: str | Document) -> bool:
	return cint(get_widget_doc(widget).is_active) == 1


def _has_widget_role_permission(
	widget: str | Document,
	user: str | None = None,
	action: str = "view",
) -> bool:
	if is_dashboard_admin(user):
		return True

	roles = get_user_roles(user)
	fieldname = "can_use" if action == "use" else "can_view"

	for row in get_widget_doc(widget).get("roles") or []:
		if row.role in roles and cint(row.get(fieldname)):
			return True

	return False


def get_widget_permissions(widget: str | Document, user: str | None = None) -> dict[str, bool]:
	return {
		"can_view": can_access_widget(widget, user=user, action="view", require_active=True),
		"can_use": can_access_widget(widget, user=user, action="use", require_active=True),
	}


def can_access_widget(
	widget: str | Document,
	user: str | None = None,
	action: str = "view",
	require_active: bool = True,
) -> bool:
	if require_active and not is_widget_active(widget):
		return False
	return _has_widget_role_permission(widget, user=user, action=action)


def assert_widget_access(
	widget: str | Document,
	user: str | None = None,
	action: str = "view",
	require_active: bool = True,
) -> Document:
	require_builder_access(user)
	widget_doc = get_widget_doc(widget)

	if require_active and not is_widget_active(widget_doc):
		frappe.throw(_("Le widget {0} est inactif.").format(frappe.bold(widget_doc.name)))

	if not _has_widget_role_permission(widget_doc, user=user, action=action):
		frappe.throw(
			_("Vous n'etes pas autorise a acceder au widget {0}.").format(
				frappe.bold(widget_doc.name)
			),
			frappe.PermissionError,
		)

	return widget_doc


def list_accessible_widgets(user: str | None = None, action: str = "view") -> list[Document]:
	require_builder_access(user)
	widget_names = frappe.get_all(
		"Custom Dashboard Widget",
		fields=["name"],
		filters={"is_active": 1},
		order_by="category asc, title asc, modified desc",
	)

	widgets: list[Document] = []
	for row in widget_names:
		widget_doc = frappe.get_cached_doc("Custom Dashboard Widget", row.name)
		if _has_widget_role_permission(widget_doc, user=user, action=action):
			widgets.append(widget_doc)

	return widgets


def _dashboard_share_rows_from_doc(dashboard_doc) -> list[Any] | None:
	if not hasattr(dashboard_doc, "get"):
		return None
	shares = dashboard_doc.get("shares")
	if shares is None:
		return None
	return shares


def _dashboard_share_flags_from_rows(rows: list[Any], user: str | None = None) -> dict[str, bool]:
	current_user = get_current_user(user)
	roles = get_user_roles(current_user)
	can_read = False
	can_edit = False

	for row in rows or []:
		share_type = (row.get("share_type") if hasattr(row, "get") else getattr(row, "share_type", "")) or ""
		if share_type == "User" and (row.get("user") if hasattr(row, "get") else getattr(row, "user", None)) == current_user:
			can_read = True
			can_edit = can_edit or cint(row.get("can_edit") if hasattr(row, "get") else getattr(row, "can_edit", 0)) == 1
		elif share_type == "Role" and (row.get("role") if hasattr(row, "get") else getattr(row, "role", None)) in roles:
			can_read = True
			can_edit = can_edit or cint(row.get("can_edit") if hasattr(row, "get") else getattr(row, "can_edit", 0)) == 1

	return {"can_read": can_read or can_edit, "can_edit": can_edit}


def _dashboard_share_flags_from_db(dashboard_name: str, user: str | None = None) -> dict[str, bool]:
	if not dashboard_name or not frappe.db.exists("DocType", "User Dashboard Share"):
		return {"can_read": False, "can_edit": False}

	current_user = get_current_user(user)
	roles = [role for role in get_user_roles(current_user) if role not in IGNORED_ROLES]
	clauses = [f"(share_type = 'User' and user = {frappe.db.escape(current_user)})"]
	if roles:
		role_list = ", ".join(frappe.db.escape(role) for role in roles)
		clauses.append(f"(share_type = 'Role' and role in ({role_list}))")

	row = frappe.db.sql(
		f"""
			select
				count(*) as matches,
				max(ifnull(can_edit, 0)) as can_edit
			from `tabUser Dashboard Share`
			where parent = %s
				and parenttype = 'User Dashboard'
				and ({' or '.join(clauses)})
		""",
		(dashboard_name,),
		as_dict=True,
	)[0]

	return {
		"can_read": cint(row.matches) > 0,
		"can_edit": cint(row.can_edit) == 1,
	}


def get_dashboard_share_flags(dashboard: str | Document | Any, user: str | None = None) -> dict[str, bool]:
	dashboard_doc = get_dashboard_doc(dashboard)
	current_user = get_current_user(user)

	if is_dashboard_admin(current_user):
		return {"can_read": True, "can_edit": True, "is_owner": True}

	is_owner = dashboard_doc.user == current_user
	if is_owner:
		return {"can_read": True, "can_edit": True, "is_owner": True}

	can_read = cint(getattr(dashboard_doc, "is_shared", 0)) == 1
	can_edit = False

	rows = _dashboard_share_rows_from_doc(dashboard_doc)
	if rows is not None:
		flags = _dashboard_share_flags_from_rows(rows, user=current_user)
	else:
		flags = _dashboard_share_flags_from_db(getattr(dashboard_doc, "name", None), user=current_user)

	can_read = can_read or flags["can_read"] or flags["can_edit"]
	can_edit = can_edit or flags["can_edit"]
	return {"can_read": can_read, "can_edit": can_edit, "is_owner": False}


def can_read_dashboard(dashboard: str | Document | Any, user: str | None = None) -> bool:
	if not has_builder_access(user):
		return False

	return get_dashboard_share_flags(dashboard, user=user)["can_read"]


def can_write_dashboard(dashboard: str | Document | Any, user: str | None = None) -> bool:
	if not has_builder_access(user):
		return False

	return get_dashboard_share_flags(dashboard, user=user)["can_edit"]


def can_manage_dashboard_sharing(dashboard: str | Document | Any, user: str | None = None) -> bool:
	dashboard_doc = get_dashboard_doc(dashboard)
	current_user = get_current_user(user)
	return is_dashboard_admin(current_user) or dashboard_doc.user == current_user


def assert_dashboard_read_access(dashboard: str | Document, user: str | None = None) -> Document:
	require_builder_access(user)
	dashboard_doc = get_dashboard_doc(dashboard)
	if not can_read_dashboard(dashboard_doc, user=user):
		frappe.throw(
			_("Vous n'etes pas autorise a acceder au tableau de bord {0}.").format(
				frappe.bold(dashboard_doc.name)
			),
			frappe.PermissionError,
		)
	return dashboard_doc


def assert_dashboard_write_access(dashboard: str | Document, user: str | None = None) -> Document:
	require_builder_access(user)
	dashboard_doc = get_dashboard_doc(dashboard)
	if not can_write_dashboard(dashboard_doc, user=user):
		frappe.throw(
			_("Vous ne pouvez modifier que vos tableaux de bord ou ceux qui vous deleguent l'edition."),
			frappe.PermissionError,
		)
	return dashboard_doc


def get_dashboard_widget_permission_query_condition(user: str | None = None) -> str | None:
	user = get_current_user(user)
	if is_dashboard_admin(user):
		return None

	if not has_builder_access(user):
		return "1=0"

	roles = [role for role in get_user_roles(user) if role not in IGNORED_ROLES]
	if not roles:
		return "1=0"

	role_list = ", ".join(frappe.db.escape(role) for role in roles)
	return f"""
		`tabCustom Dashboard Widget`.`is_active` = 1
		and exists (
			select 1
			from `tabCustom Dashboard Widget Role`
			where `tabCustom Dashboard Widget Role`.`parent` = `tabCustom Dashboard Widget`.`name`
				and `tabCustom Dashboard Widget Role`.`parenttype` = 'Custom Dashboard Widget'
				and ifnull(`tabCustom Dashboard Widget Role`.`can_view`, 0) = 1
				and `tabCustom Dashboard Widget Role`.`role` in ({role_list})
		)
	"""


def has_dashboard_widget_permission(
	doc: str | Document | None = None,
	user: str | None = None,
	ptype: str | None = None,
) -> bool:
	ptype = ptype or "read"

	if is_dashboard_admin(user):
		return True

	if ptype in READ_TYPES:
		if not doc:
			return has_builder_access(user)
		return can_access_widget(doc, user=user, action="view", require_active=True)

	return False


def get_user_dashboard_permission_query_condition(user: str | None = None) -> str | None:
	user = get_current_user(user)
	if is_dashboard_admin(user):
		return None

	if not has_builder_access(user):
		return "1=0"

	roles = [role for role in get_user_roles(user) if role not in IGNORED_ROLES]
	role_condition = "1=0"
	if roles:
		role_list = ", ".join(frappe.db.escape(role) for role in roles)
		role_condition = f"(share_type = 'Role' and role in ({role_list}))"

	return (
		f"(`tabUser Dashboard`.`user` = {frappe.db.escape(user)} "
		"or ifnull(`tabUser Dashboard`.`is_shared`, 0) = 1 "
		"or exists ("
		"select 1 from `tabUser Dashboard Share` "
		"where `tabUser Dashboard Share`.`parent` = `tabUser Dashboard`.`name` "
		"and `tabUser Dashboard Share`.`parenttype` = 'User Dashboard' "
		f"and ((share_type = 'User' and user = {frappe.db.escape(user)}) or {role_condition})"
		"))"
	)


def has_user_dashboard_permission(
	doc: str | Document | None = None,
	user: str | None = None,
	ptype: str | None = None,
) -> bool:
	ptype = ptype or "read"

	if is_dashboard_admin(user):
		return True

	if ptype == "create":
		return has_builder_access(user)

	if not doc:
		return has_builder_access(user) if ptype in READ_TYPES else False

	if ptype in READ_TYPES:
		return can_read_dashboard(doc, user=user)

	if ptype in WRITE_TYPES:
		return can_write_dashboard(doc, user=user)

	return False
