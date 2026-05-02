from __future__ import annotations

import frappe

from custom_dashboard.services import dashboard_service


def boot_session(bootinfo) -> None:
	"""Expose la liste des modules pour lesquels l'utilisateur a un dashboard custom.

	Permet au script de redirection (module_dashboard_redirect.js) d'eviter un
	xcall synchrone au premier chargement du desk.
	"""
	if frappe.session.user == "Guest":
		return

	accessible: dict[str, bool] = {}
	for module_name in sorted(dashboard_service.SUPPORTED_MODULE_DASHBOARDS):
		try:
			accessible[module_name] = bool(
				dashboard_service.can_view_module_dashboard(module_name)
			)
		except Exception:
			accessible[module_name] = False

	bootinfo.custom_dashboard_modules = accessible
