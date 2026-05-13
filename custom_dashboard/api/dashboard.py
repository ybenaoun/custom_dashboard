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


@frappe.whitelist()
def list_admin_dashboards(category: str | None = None):
	"""Admin-only: list every dashboard with metadata for the management page."""
	return dashboard_service.list_admin_dashboards(category=category)


@frappe.whitelist()
def get_admin_dashboard(name: str):
	"""Admin-only: detailed dashboard for the access form."""
	return dashboard_service.get_admin_dashboard(name)


@frappe.whitelist()
def admin_save_dashboard(doc):
	"""Admin-only: create/edit a dashboard with category, activation and shares."""
	return dashboard_service.admin_save_dashboard(doc)


@frappe.whitelist()
def admin_toggle_dashboard_active(name: str, is_active):
	"""Admin-only: enable or disable a dashboard."""
	return dashboard_service.admin_toggle_dashboard_active(name, is_active)


@frappe.whitelist()
def admin_delete_dashboard(name: str):
	"""Admin-only: hard-delete a dashboard."""
	return dashboard_service.admin_delete_dashboard(name)


@frappe.whitelist()
def admin_duplicate_dashboard(name: str):
	"""Admin-only: duplicate a dashboard."""
	return dashboard_service.admin_duplicate_dashboard(name)
