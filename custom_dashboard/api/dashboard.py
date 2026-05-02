from __future__ import annotations

import frappe

from custom_dashboard.services import dashboard_service


@frappe.whitelist()
def list_user_dashboards():
	"""Return the dashboards that the current user can access."""
	return dashboard_service.list_user_dashboards()


@frappe.whitelist()
def get_dashboard(name: str):
	"""Return a dashboard and its accessible items."""
	return dashboard_service.get_dashboard(name)


@frappe.whitelist()
def get_module_dashboard(module_name: str):
	"""Return the unique published dashboard for a given module (Stock, ...)."""
	return dashboard_service.get_module_dashboard(module_name)


@frappe.whitelist()
def can_view_module_dashboard(module_name: str):
	"""Boolean used by the frontend router redirect."""
	return dashboard_service.can_view_module_dashboard(module_name)


@frappe.whitelist()
def save_user_dashboard(doc):
	"""Create or update a user dashboard."""
	return dashboard_service.save_user_dashboard(doc)


@frappe.whitelist()
def get_sharing_options():
	"""Return user and role options for advanced dashboard sharing."""
	return dashboard_service.get_sharing_options()
