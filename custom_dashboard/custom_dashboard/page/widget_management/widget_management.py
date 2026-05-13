from __future__ import annotations

import frappe

from custom_dashboard.services import access


def has_desk_icon_permission() -> bool:
	return access.is_dashboard_admin()


def get_context(context):
	if not access.is_dashboard_admin():
		raise frappe.PermissionError(
			"Accès réservé à l'administrateur ou au rôle System Manager."
		)
	return context
