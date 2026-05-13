from __future__ import annotations

import frappe


def execute() -> None:
	if not frappe.db.has_column("User Dashboard", "is_active"):
		return

	frappe.db.sql(
		"""
		update `tabUser Dashboard`
		set is_active = 1
		where is_active is null or is_active = 0 and modified is null
		"""
	)
	frappe.db.sql(
		"""
		update `tabUser Dashboard`
		set is_active = 1
		where is_active is null
		"""
	)
