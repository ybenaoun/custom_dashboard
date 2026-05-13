app_name = "custom_dashboard"
app_title = "Custom Dashboard"
app_publisher = "youssef"
app_description = "custom dashboard"
app_email = "youssef@youssef.com"
app_license = "mit"
app_logo_url = "/assets/custom_dashboard/images/custom_dashboard-logo.svg"
app_home = "/desk/custom-dashboard"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": app_name,
		"logo": app_logo_url,
		"title": app_title,
		"route": app_home,
		"has_permission": "custom_dashboard.permissions.has_app_permission",
	},
	{
		"name": "global-dashboard",
		"logo": "/assets/custom_dashboard/images/global-dashboard-logo.svg",
		"title": "Tableau de bord global",
		"route": "/app/global-dashboard",
		"has_permission": "custom_dashboard.custom_dashboard.page.global_dashboard.global_dashboard.has_desk_icon_permission",
	},
	{
		"name": "admin-dashboard",
		"logo": "/assets/custom_dashboard/images/admin-dashboard-logo.svg",
		"title": "Admin Dashboard",
		"route": "/app/admin-dashboard",
		"has_permission": "custom_dashboard.custom_dashboard.page.admin_dashboard.admin_dashboard.has_desk_icon_permission",
	},
	{
		"name": "dashboard-management",
		"logo": app_logo_url,
		"title": "Gestion des tableaux",
		"route": "/app/dashboard-management",
		"has_permission": "custom_dashboard.custom_dashboard.page.dashboard_management.dashboard_management.has_desk_icon_permission",
	},
	{
		"name": "widget-management",
		"logo": app_logo_url,
		"title": "Gestion des widgets",
		"route": "/app/widget-management",
		"has_permission": "custom_dashboard.custom_dashboard.page.widget_management.widget_management.has_desk_icon_permission",
	},
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/custom_dashboard/css/custom_dashboard.css"
app_include_js = ["/assets/custom_dashboard/js/chatbot.js"]

# include js, css files in header of web template
# web_include_css = "/assets/custom_dashboard/css/custom_dashboard.css"
# web_include_js = "/assets/custom_dashboard/js/custom_dashboard.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "custom_dashboard/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "custom_dashboard/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "custom_dashboard.utils.jinja_methods",
# 	"filters": "custom_dashboard.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "custom_dashboard.install.before_install"
after_install = "custom_dashboard.setup.after_install"

# Uninstallation
# ------------

# before_uninstall = "custom_dashboard.uninstall.before_uninstall"
# after_uninstall = "custom_dashboard.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "custom_dashboard.utils.before_app_install"
# after_app_install = "custom_dashboard.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "custom_dashboard.utils.before_app_uninstall"
# after_app_uninstall = "custom_dashboard.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "custom_dashboard.notifications.get_notification_config"

# Session Boot
# ------------
boot_session = "custom_dashboard.boot.boot_session"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Custom Dashboard Widget": "custom_dashboard.permissions.get_dashboard_widget_permission_query_conditions",
	"User Dashboard": "custom_dashboard.permissions.get_user_dashboard_permission_query_conditions",
}

has_permission = {
	"Custom Dashboard Widget": "custom_dashboard.permissions.has_dashboard_widget_permission",
	"User Dashboard": "custom_dashboard.permissions.has_user_dashboard_permission",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"*": {
		"on_update": "custom_dashboard.rag.on_rag_doc_update",
		"on_trash": "custom_dashboard.rag.on_rag_doc_trash",
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"custom_dashboard.tasks.all"
# 	],
# 	"daily": [
# 		"custom_dashboard.tasks.daily"
# 	],
# 	"hourly": [
# 		"custom_dashboard.tasks.hourly"
# 	],
# 	"weekly": [
# 		"custom_dashboard.tasks.weekly"
# 	],
# 	"monthly": [
# 		"custom_dashboard.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "custom_dashboard.install.before_tests"

after_migrate = "custom_dashboard.setup.after_migrate"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "custom_dashboard.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "custom_dashboard.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "custom_dashboard.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["custom_dashboard.utils.before_request"]
# after_request = ["custom_dashboard.utils.after_request"]

# Job Events
# ----------
# before_job = ["custom_dashboard.utils.before_job"]
# after_job = ["custom_dashboard.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"custom_dashboard.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

app_include_css = [
	"/assets/custom_dashboard/css/chatbot.css",
	"/assets/custom_dashboard/css/wizio-theme.css",
	"/assets/custom_dashboard/css/compact_dashboard.css",
	"/assets/custom_dashboard/css/final_dashboard.css",
]
