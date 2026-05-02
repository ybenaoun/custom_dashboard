from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import cint


class CustomDashboardWidget(Document):
	def autoname(self):
		if self.name and not self.name.lower().startswith("new-dashboard-widget"):
			self.name = self.name.strip().upper()
			return

		base_name = (frappe.scrub(self.title or "") or "widget").upper()
		if not frappe.db.exists(self.doctype, base_name):
			self.name = base_name
			return

		self.name = make_autoname(f"{base_name}-.###")

	def validate(self):
		self.title = (self.title or "").strip()
		self.python_method = (self.python_method or "").strip()
		self.static_data_json = (self.static_data_json or "").strip()
		self.category = (self.category or "").strip()
		self.icon = (self.icon or "").strip()

		if not self.title:
			frappe.throw(_("Title is required."))

		self._validate_data_source()
		self._validate_role_rows()

	def _validate_data_source(self):
		if self.data_source_type == "python_method":
			if not self.python_method:
				frappe.throw(_("Python method is required when data source type is python_method."))

			try:
				method = frappe.get_attr(self.python_method)
			except Exception as exc:
				frappe.throw(
					_("Python method was not found: {0}").format(self.python_method),
					exc=exc.__class__,
				)

			if not callable(method):
				frappe.throw(_("Python method must be callable."))

		elif self.data_source_type == "static_json":
			if not self.static_data_json:
				frappe.throw(_("Static data JSON is required when data source type is static_json."))

			try:
				json.loads(self.static_data_json)
			except json.JSONDecodeError as exc:
				frappe.throw(
					_("Static data JSON is invalid: {0}").format(exc),
					exc=frappe.ValidationError,
				)

	def _validate_role_rows(self):
		seen_roles = set()
		for row in self.get("roles") or []:
			if not row.role:
				frappe.throw(_("Each widget role row must define a role."))

			if row.role in seen_roles:
				frappe.throw(_("Role {0} is duplicated in widget access rows.").format(row.role))

			if cint(row.can_use) and not cint(row.can_view):
				row.can_view = 1

			seen_roles.add(row.role)
