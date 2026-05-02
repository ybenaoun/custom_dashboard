from __future__ import annotations

import frappe

from custom_dashboard.services import widget_executor, widget_registry


@frappe.whitelist()
def list_available_widgets():
	"""Return only the widgets that the current user can see and use."""
	return widget_registry.list_available_widgets()


@frappe.whitelist()
def get_widget_definition(widget_name: str):
	"""Return a safe widget definition for the current user."""
	return widget_registry.get_widget_definition(widget_name)


@frappe.whitelist()
def get_widget_data(widget_name: str, filters=None):
	"""Execute the widget and return normalized data."""
	return widget_executor.get_widget_data(widget_name, filters=filters)


@frappe.whitelist()
def list_admin_widgets():
	"""Return widget configurations for the admin access panel."""
	return widget_registry.list_admin_widgets()


@frappe.whitelist()
def get_widget_admin_definition(widget_name: str):
	"""Return widget access details for admins."""
	return widget_registry.get_widget_admin_definition(widget_name)


@frappe.whitelist()
def save_widget_access(doc):
	"""Persist widget access rules edited from the admin panel."""
	return widget_registry.save_widget_access(doc)
