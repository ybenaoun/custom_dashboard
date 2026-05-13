from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import cint


class UserDashboard(Document):
	def autoname(self):
		if self.name and not self.name.lower().startswith("new-user-dashboard"):
			return

		base_user = _safe_slug(self.user or frappe.session.user or "user")
		base_title = _safe_slug(self.title or "dashboard") or "dashboard"
		self.name = make_autoname(f"{base_user}-{base_title}-.###")

	def validate(self):
		self.title = (self.title or "").strip()
		self.set("module_name", (self.get("module_name") or "").strip())
		if self.is_active is None:
			self.is_active = 1
		else:
			self.is_active = 1 if cint(self.is_active) else 0
		if not self.title:
			frappe.throw(_("Title is required."))

		if not self.user:
			frappe.throw(_("User is required."))

		for index, item in enumerate(self.get("items") or [], start=1):
			item.x = cint(item.x)
			item.y = cint(item.y) if item.y is not None else (index - 1) * 4
			item.w = max(cint(item.w) or 6, 1)
			item.h = max(cint(item.h) or 4, 1)
			item.display_title = (item.display_title or "").strip()


def _safe_slug(value: str) -> str:
	value = frappe.scrub(value or "") or "dashboard"
	return re.sub(r"[^a-z0-9_-]+", "_", value.lower()).strip("_") or "dashboard"
