import frappe
from frappe.utils import now_datetime, add_days, add_months, getdate, cint


def has_desk_icon_permission():
	return frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()


@frappe.whitelist()
def get_dashboard_data():
	frappe.only_for(["System Manager", "Administrator"])

	today = getdate(now_datetime())
	week_ago = add_days(today, -7)
	month_ago = add_months(today, -1)

	return {
		"users": get_user_stats(today, week_ago, month_ago),
		"errors": get_error_stats(today, week_ago),
		"emails": get_email_stats(today, week_ago),
		"website": get_website_stats(),
		"files": get_file_stats(),
		"activity": get_activity_stats(today, week_ago),
		"workflows": get_workflow_stats(),
		"automation": get_automation_stats(),
		"todos": get_todo_stats(),
		"background_jobs": get_background_job_stats(today, week_ago),
		"distributions": {
			"users": get_user_distribution(),
			"emails": get_email_breakdown(),
			"files": get_file_distribution(),
			"modules": get_module_health(),
		},
	}


def get_user_stats(today, week_ago, month_ago):
	total_system = frappe.db.count("User", {"user_type": "System User", "enabled": 1})
	total_website = frappe.db.count("User", {"user_type": "Website User", "enabled": 1})
	disabled = frappe.db.count("User", {"enabled": 0})
	new_this_week = frappe.db.count("User", {"creation": (">=", week_ago)})

	active_last_week = frappe.db.sql(
		"""SELECT COUNT(DISTINCT user) FROM `tabActivity Log`
		WHERE operation = 'Login' AND status = 'Success'
		AND communication_date >= %s""",
		week_ago,
	)[0][0] or 0

	return {
		"total_system": total_system,
		"total_website": total_website,
		"disabled": disabled,
		"new_this_week": new_this_week,
		"active_last_week": active_last_week,
	}


def get_error_stats(today, week_ago):
	total_today = frappe.db.count("Error Log", {"creation": (">=", today)})
	total_this_week = frappe.db.count("Error Log", {"creation": (">=", week_ago)})
	unseen = frappe.db.count("Error Log", {"seen": 0})

	top_errors = frappe.db.sql(
		"""SELECT method, COUNT(*) as count
		FROM `tabError Log`
		WHERE creation >= %s
		GROUP BY method
		ORDER BY count DESC
		LIMIT 5""",
		today,
		as_dict=True,
	)

	return {
		"total_today": total_today,
		"total_this_week": total_this_week,
		"unseen": unseen,
		"top_errors": top_errors,
	}


def get_email_stats(today, week_ago):
	queue_count = frappe.db.count("Email Queue", {"status": "Not Sent"})
	sent_today = frappe.db.count("Email Queue", {"status": "Sent", "creation": (">=", today)})
	sent_this_week = frappe.db.count("Email Queue", {"status": "Sent", "creation": (">=", week_ago)})
	errors = frappe.db.count("Email Queue", {"status": "Error"})

	return {
		"queue_count": queue_count,
		"sent_today": sent_today,
		"sent_this_week": sent_this_week,
		"errors": errors,
	}


def get_website_stats():
	published_pages = frappe.db.count("Web Page", {"published": 1})
	published_forms = frappe.db.count("Web Form", {"published": 1})
	total_views = frappe.db.count("Web Page View")

	return {
		"published_pages": published_pages,
		"published_forms": published_forms,
		"total_views": cint(total_views),
	}


def get_file_stats():
	total_files = frappe.db.count("File", {"is_folder": 0})
	total_private = frappe.db.count("File", {"is_folder": 0, "is_private": 1})
	total_public = frappe.db.count("File", {"is_folder": 0, "is_private": 0})

	total_size = frappe.db.sql(
		"SELECT SUM(file_size) FROM `tabFile` WHERE is_folder = 0"
	)[0][0] or 0
	total_size_mb = round(total_size / (1024 * 1024), 1)

	return {
		"total_files": total_files,
		"total_private": total_private,
		"total_public": total_public,
		"total_size_mb": total_size_mb,
	}


def get_activity_stats(today, week_ago):
	logins_today = frappe.db.count(
		"Activity Log",
		{"operation": "Login", "status": "Success", "communication_date": (">=", today)},
	)
	failed_logins_week = frappe.db.count(
		"Activity Log",
		{"operation": "Login", "status": "Failed", "communication_date": (">=", week_ago)},
	)

	login_trend = frappe.db.sql(
		"""SELECT DATE(communication_date) as date, COUNT(*) as count
		FROM `tabActivity Log`
		WHERE operation = 'Login' AND status = 'Success'
		AND communication_date >= %s
		GROUP BY DATE(communication_date)
		ORDER BY date""",
		week_ago,
		as_dict=True,
	)

	return {
		"logins_today": logins_today,
		"failed_logins_week": failed_logins_week,
		"login_trend": login_trend,
	}


def get_workflow_stats():
	total_workflows = frappe.db.count("Workflow", {"is_active": 1})
	pending_actions = frappe.db.count("Workflow Action", {"status": "Open"})

	return {
		"total_active": total_workflows,
		"pending_actions": pending_actions,
	}


def get_automation_stats():
	total_auto_repeat = frappe.db.count("Auto Repeat", {"disabled": 0})
	total_assignment_rules = frappe.db.count("Assignment Rule", {"disabled": 0})
	total_notifications = frappe.db.count("Notification", {"enabled": 1})

	return {
		"auto_repeat": total_auto_repeat,
		"assignment_rules": total_assignment_rules,
		"notifications": total_notifications,
	}


def get_todo_stats():
	open_todos = frappe.db.count("ToDo", {"status": "Open"})
	overdue = frappe.db.count("ToDo", {"status": "Open", "date": ("<", getdate(now_datetime()))})

	return {
		"open": open_todos,
		"overdue": overdue,
	}


def get_background_job_stats(today, week_ago):
	failed_jobs = frappe.db.count("Scheduled Job Log", {"status": "Failed", "creation": (">=", week_ago)})
	total_job_types = frappe.db.count("Scheduled Job Type")

	return {
		"failed_this_week": failed_jobs,
		"total_job_types": total_job_types,
	}


def get_user_distribution():
	"""Répartition utilisateurs pour graphique donut."""
	system = frappe.db.count("User", {"user_type": "System User", "enabled": 1})
	website = frappe.db.count("User", {"user_type": "Website User", "enabled": 1})
	disabled = frappe.db.count("User", {"enabled": 0})
	return [
		{"label": "Système", "value": system},
		{"label": "Site Web", "value": website},
		{"label": "Désactivés", "value": disabled},
	]


def get_email_breakdown():
	"""Répartition emails pour graphique bar."""
	today = getdate(now_datetime())
	week_ago = add_days(today, -7)
	return [
		{"label": "En attente", "value": frappe.db.count("Email Queue", {"status": "Not Sent"})},
		{"label": "Envoyés (jour)", "value": frappe.db.count("Email Queue", {"status": "Sent", "creation": (">=", today)})},
		{"label": "Envoyés (semaine)", "value": frappe.db.count("Email Queue", {"status": "Sent", "creation": (">=", week_ago)})},
		{"label": "Erreurs", "value": frappe.db.count("Email Queue", {"status": "Error"})},
	]


def get_file_distribution():
	"""Répartition fichiers privé/public pour donut."""
	private = frappe.db.count("File", {"is_folder": 0, "is_private": 1})
	public = frappe.db.count("File", {"is_folder": 0, "is_private": 0})
	return [
		{"label": "Privés", "value": private},
		{"label": "Publics", "value": public},
	]


def get_module_health():
	"""Santé des modules pour graphique bar comparatif."""
	return [
		{"label": "Workflows", "value": frappe.db.count("Workflow", {"is_active": 1})},
		{"label": "Notifications", "value": frappe.db.count("Notification", {"enabled": 1})},
		{"label": "Auto Repeat", "value": frappe.db.count("Auto Repeat", {"disabled": 0})},
		{"label": "Assignment", "value": frappe.db.count("Assignment Rule", {"disabled": 0})},
		{"label": "Web Pages", "value": frappe.db.count("Web Page", {"published": 1})},
		{"label": "Web Forms", "value": frappe.db.count("Web Form", {"published": 1})},
	]


@frappe.whitelist()
def get_error_trend():
	frappe.only_for(["System Manager", "Administrator"])
	fourteen_days_ago = add_days(getdate(now_datetime()), -14)

	return frappe.db.sql(
		"""SELECT DATE(creation) as date, COUNT(*) as count
		FROM `tabError Log`
		WHERE creation >= %s
		GROUP BY DATE(creation)
		ORDER BY date""",
		fourteen_days_ago,
		as_dict=True,
	)


@frappe.whitelist()
def get_email_trend():
	frappe.only_for(["System Manager", "Administrator"])
	fourteen_days_ago = add_days(getdate(now_datetime()), -14)

	return frappe.db.sql(
		"""SELECT DATE(creation) as date, COUNT(*) as count
		FROM `tabEmail Queue`
		WHERE status = 'Sent' AND creation >= %s
		GROUP BY DATE(creation)
		ORDER BY date""",
		fourteen_days_ago,
		as_dict=True,
	)
