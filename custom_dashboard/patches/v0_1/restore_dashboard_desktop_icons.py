import frappe


def execute():
	"""Recâble les Pages et Desktop Icons admin/global dashboard transférés depuis frappe.

	1. Les Pages `admin-dashboard` et `global-dashboard` ont encore `module=Desk`
	   en base — Frappe résout alors le chemin disque vers `apps/frappe/frappe/desk/page/...`
	   qui n'existe plus → FileNotFoundError. On bascule le `module` vers
	   `Custom Dashboard` pour pointer vers l'app cible.
	2. Les Desktop Icons (app=frappe) deviennent orphelins. On les supprime puis
	   on resynchronise depuis les JSON livrés par custom_dashboard.
	"""
	_fix_page_module_references()
	_restore_desktop_icons()


def _fix_page_module_references():
	page_module_map = {
		"admin-dashboard": "Custom Dashboard",
		"global-dashboard": "Custom Dashboard",
	}
	for page_name, module in page_module_map.items():
		if not frappe.db.exists("Page", page_name):
			continue
		frappe.db.set_value("Page", page_name, "module", module, update_modified=False)
		frappe.clear_document_cache("Page", page_name)


def _restore_desktop_icons():
	if not frappe.db.exists("DocType", "Desktop Icon"):
		return

	for label in ("Admin Dashboard", "Tableau de bord global"):
		orphan = frappe.db.get_value(
			"Desktop Icon",
			{"label": label, "app": "frappe"},
			"name",
		)
		if orphan:
			frappe.delete_doc("Desktop Icon", orphan, ignore_permissions=True, force=True)

	from custom_dashboard.setup import (
		ensure_dashboard_desktop_icon,
		ensure_dashboard_in_desktop_layouts,
	)

	ensure_dashboard_desktop_icon()
	ensure_dashboard_in_desktop_layouts()
