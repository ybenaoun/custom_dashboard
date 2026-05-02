import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import cint

from custom_dashboard import setup
from custom_dashboard.services import access, dashboard_service, widget_executor, widget_registry


def ensure_user(email, *roles):
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = email.split("@", 1)[0]
		user.enabled = 1

	if roles:
		user.add_roles(*roles)

	return user


class TestDashboardV2(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		setup.sync_records()
		setup.ensure_demo_setup()
		cls.owner = ensure_user("dashboard_owner@example.com", "Dashboard Manager")
		cls.editor = ensure_user("dashboard_editor@example.com", "Dashboard Consumer")
		cls.viewer = ensure_user("dashboard_viewer@example.com", "Dashboard Consumer")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_widget_definition_contains_structured_filters(self):
		definition = widget_registry.get_widget_definition("SALES_THIS_MONTH", user=self.owner.name)

		self.assertEqual(definition["data_source_type"], "python_method")
		self.assertEqual(definition["module_name"], "Selling")
		self.assertTrue(definition["allow_filters"])
		self.assertTrue(any(field["fieldname"] == "period" for field in definition["filters_schema"]))
		self.assertEqual(definition["default_filters"]["period"], "this_month")

		stock_definition = widget_registry.get_widget_definition("STOCK_AGE_PROFILE", user=self.owner.name)
		self.assertEqual(stock_definition["module_name"], "Stock")
		self.assertTrue(any(field["fieldname"] == "warehouse" for field in stock_definition["filters_schema"]))

		selling_ai = widget_registry.get_widget_definition("AI_SELLING_INSIGHTS", user=self.owner.name)
		self.assertEqual(selling_ai["module_name"], "Selling")
		self.assertEqual(selling_ai["widget_type"], "ai_insight")
		self.assertTrue(any(field["fieldname"] == "customer_group" for field in selling_ai["filters_schema"]))

		buying_ai = widget_registry.get_widget_definition("AI_BUYING_INSIGHTS", user=self.owner.name)
		self.assertEqual(buying_ai["module_name"], "Buying")
		self.assertEqual(buying_ai["widget_type"], "ai_insight")
		self.assertTrue(any(field["fieldname"] == "supplier_group" for field in buying_ai["filters_schema"]))

	def test_consumer_catalog_excludes_manager_only_widgets(self):
		widgets = widget_registry.list_available_widgets(user=self.viewer.name)
		widget_names = {widget["name"] for widget in widgets}

		self.assertIn("SALES_THIS_MONTH", widget_names)
		self.assertNotIn("PIPELINE_HEALTH", widget_names)

	def test_widget_catalog_is_deduplicated_by_module(self):
		widgets = widget_registry.list_available_widgets(user="Administrator")
		keys = [(widget["module_name"], widget["canonical_name"]) for widget in widgets]
		widget_names = {widget["name"] for widget in widgets}

		self.assertEqual(len(keys), len(set(keys)))
		self.assertIn("SALES_THIS_MONTH", widget_names)
		self.assertNotIn("SELLING_REVENUE_SNAPSHOT", widget_names)

	def test_shared_dashboard_supports_role_and_user_shares(self):
		frappe.set_user(self.owner.name)
		payload = {
			"title": f"Dashboard test partage {frappe.generate_hash(length=6)}",
			"is_default": 0,
			"is_shared": 0,
			"shares": [
				{
					"share_type": "User",
					"user": self.editor.name,
					"can_edit": 1,
				},
				{
					"share_type": "Role",
					"role": "Dashboard Consumer",
					"can_edit": 0,
				},
			],
			"items": [
				{
					"widget": "SALES_THIS_MONTH",
					"x": 0,
					"y": 0,
					"w": 3,
					"h": 3,
				}
			],
		}
		dashboard = dashboard_service.save_user_dashboard(payload, user=self.owner.name)

		self.assertTrue(access.can_read_dashboard(dashboard["name"], user=self.editor.name))
		self.assertTrue(access.can_write_dashboard(dashboard["name"], user=self.editor.name))
		self.assertTrue(access.can_read_dashboard(dashboard["name"], user=self.viewer.name))
		self.assertFalse(access.can_write_dashboard(dashboard["name"], user=self.viewer.name))

	def test_database_widgets_return_normalized_payloads(self):
		card = widget_executor.get_widget_data("SALES_THIS_MONTH", user=self.owner.name)
		self.assertEqual(card["widget"], "SALES_THIS_MONTH")
		self.assertEqual(card["type"], "number_card")
		self.assertIn("value", card["data"])

		chart = widget_executor.get_widget_data("MONTHLY_REVENUE_CHART", user=self.owner.name)
		self.assertEqual(chart["widget"], "MONTHLY_REVENUE_CHART")
		self.assertEqual(chart["type"], "chart")
		self.assertIn("labels", chart["data"])
		self.assertIn("datasets", chart["data"])

		stock_chart = widget_executor.get_widget_data("STOCK_AGE_PROFILE", user=self.owner.name)
		self.assertEqual(stock_chart["widget"], "STOCK_AGE_PROFILE")
		self.assertEqual(stock_chart["type"], "chart")

	def test_inactive_widgets_are_hidden_from_catalog(self):
		widget = frappe.get_doc("Custom Dashboard Widget", "STOCK_AGE_PROFILE")
		original_state = widget.is_active
		widget.is_active = 0
		widget.save(ignore_permissions=True)
		frappe.clear_document_cache("Custom Dashboard Widget", widget.name)

		try:
			widgets = widget_registry.list_available_widgets(user=self.owner.name)
			widget_names = {entry["name"] for entry in widgets}
			self.assertNotIn("STOCK_AGE_PROFILE", widget_names)

			admin_widgets = widget_registry.list_admin_widgets(user="Administrator")
			admin_names = {entry["name"] for entry in admin_widgets}
			self.assertIn("STOCK_AGE_PROFILE", admin_names)
		finally:
			widget = frappe.get_doc("Custom Dashboard Widget", "STOCK_AGE_PROFILE")
			widget.is_active = original_state
			widget.save(ignore_permissions=True)
			frappe.clear_document_cache("Custom Dashboard Widget", widget.name)

	def test_save_stock_module_dashboard_reuses_published_record(self):
		frappe.set_user("Administrator")
		first = dashboard_service.save_user_dashboard(
			{
				"title": f"Stock publie {frappe.generate_hash(length=6)}",
				"module_name": "Stock",
				"is_default": 1,
				"is_shared": 0,
				"items": [
					{
						"widget": "STOCK_TURNOVER",
						"x": 0,
						"y": 0,
						"w": 3,
						"h": 3,
					}
				],
			},
			user="Administrator",
		)

		second = dashboard_service.save_user_dashboard(
			{
				"title": f"Stock publie maj {frappe.generate_hash(length=6)}",
				"module_name": "Stock",
				"items": [
					{
						"widget": "STOCK_AGE_PROFILE",
						"x": 0,
						"y": 0,
						"w": 5,
						"h": 4,
					}
				],
			},
			user="Administrator",
		)

		self.assertEqual(first["name"], second["name"])
		self.assertEqual(second["module_name"], "Stock")
		self.assertEqual(second["is_shared"], 1)
		self.assertEqual(second["is_default"], 1)
		self.assertEqual(second["items"][0]["widget"], "STOCK_AGE_PROFILE")

	def test_stock_module_default_does_not_clear_personal_default(self):
		frappe.set_user("Administrator")
		personal = dashboard_service.save_user_dashboard(
			{
				"title": f"Perso defaut {frappe.generate_hash(length=6)}",
				"is_default": 1,
				"is_shared": 0,
				"items": [
					{
						"widget": "SALES_THIS_MONTH",
						"x": 0,
						"y": 0,
						"w": 3,
						"h": 3,
					}
				],
			},
			user="Administrator",
		)

		module_dashboard = dashboard_service.save_user_dashboard(
			{
				"title": f"Stock defaut module {frappe.generate_hash(length=6)}",
				"module_name": "Stock",
				"items": [
					{
						"widget": "STOCK_TURNOVER",
						"x": 0,
						"y": 0,
						"w": 3,
						"h": 3,
					}
				],
			},
			user="Administrator",
		)

		personal_doc = frappe.get_doc("User Dashboard", personal["name"])
		module_doc = frappe.get_doc("User Dashboard", module_dashboard["name"])

		self.assertEqual(cint(personal_doc.is_default), 1)
		self.assertEqual(cint(module_doc.is_default), 1)
		self.assertEqual(module_doc.module_name, "Stock")

	def test_stock_module_rejects_non_stock_widgets(self):
		frappe.set_user("Administrator")
		with self.assertRaises(frappe.ValidationError):
			dashboard_service.save_user_dashboard(
				{
					"title": f"Stock invalide {frappe.generate_hash(length=6)}",
					"module_name": "Stock",
					"items": [
						{
							"widget": "SALES_THIS_MONTH",
							"x": 0,
							"y": 0,
							"w": 3,
							"h": 3,
						}
					],
				},
				user="Administrator",
			)

	def test_selling_and_buying_module_dashboards_accept_module_widgets(self):
		frappe.set_user("Administrator")

		selling = dashboard_service.save_user_dashboard(
			{
				"title": f"Ventes module {frappe.generate_hash(length=6)}",
				"module_name": "Selling",
				"items": [
					{
					"widget": "SALES_THIS_MONTH",
						"x": 0,
						"y": 0,
						"w": 3,
						"h": 3,
					}
				],
			},
			user="Administrator",
		)

		buying = dashboard_service.save_user_dashboard(
			{
				"title": f"Achats module {frappe.generate_hash(length=6)}",
				"module_name": "Buying",
				"items": [
					{
						"widget": "BUYING_SPEND_THIS_MONTH",
						"x": 0,
						"y": 0,
						"w": 3,
						"h": 3,
					}
				],
			},
			user="Administrator",
		)

		self.assertEqual(selling["module_name"], "Selling")
		self.assertEqual(selling["is_default"], 1)
		self.assertEqual(selling["items"][0]["widget"], "SALES_THIS_MONTH")

		self.assertEqual(buying["module_name"], "Buying")
		self.assertEqual(buying["is_default"], 1)
		self.assertEqual(buying["items"][0]["widget"], "BUYING_SPEND_THIS_MONTH")

	def test_selling_module_rejects_buying_widgets(self):
		frappe.set_user("Administrator")
		with self.assertRaises(frappe.ValidationError):
			dashboard_service.save_user_dashboard(
				{
					"title": f"Ventes invalide {frappe.generate_hash(length=6)}",
					"module_name": "Selling",
					"items": [
						{
							"widget": "BUYING_SPEND_THIS_MONTH",
							"x": 0,
							"y": 0,
							"w": 3,
							"h": 3,
						}
					],
				},
				user="Administrator",
			)
