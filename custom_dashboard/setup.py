from __future__ import annotations

import json
from pathlib import Path

import frappe


DEMO_ROLES = (
	"Dashboard Admin",
	"Dashboard Manager",
	"Dashboard Consumer",
)

LEGACY_DEMO_DASHBOARD_TITLES = (
	"Shared Demo Dashboard",
	"Tableau de bord partage - demo",
)

MODULE_SIDEBAR_DASHBOARD_PAGES = {
	"Stock": "stock-dashboard",
	"Selling": "vente-dashboard",
	"Buying": "achat-dashboard",
}

DASHBOARD_SIDEBAR_LABELS = {"dashboard", "tableau de bord"}


def _module_sidebar_rows(module_name: str) -> list:
	if not frappe.db.exists("DocType", "Workspace Sidebar"):
		return []

	rows = frappe.get_all(
		"Workspace Sidebar",
		fields=["name", "title", "module", "for_user"],
		order_by="title asc",
		limit_page_length=0,
	)
	return [
		row
		for row in rows
		if (row.title or row.name) == module_name
		or (row.title or row.name).startswith(f"{module_name}-")
		or row.module == module_name
	]


DEMO_WIDGETS = (
	{
		"name": "SALES_THIS_MONTH",
		"title": "Chiffre d'affaires du mois",
		"description": "Montant facture et nombre de factures clients soumis sur la periode selectionnee.",
		"widget_type": "number_card",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.sales_this_month_widget",
		"category": "Ventes",
		"module_name": "Selling",
		"icon": "target",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Consumer", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "TOP_CUSTOMERS",
		"title": "Top clients",
		"description": "Classement des clients par chiffre d'affaires facture.",
		"widget_type": "table",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.top_customers_widget",
		"category": "Ventes",
		"module_name": "Selling",
		"icon": "users",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Consumer", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "MONTHLY_REVENUE_CHART",
		"title": "Evolution du chiffre d'affaires",
		"description": "Tendance mensuelle du chiffre d'affaires facture.",
		"widget_type": "chart",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.monthly_revenue_chart_widget",
		"category": "Finance",
		"module_name": "Selling",
		"icon": "trend-up",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Consumer", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "PIPELINE_HEALTH",
		"title": "Pipeline commercial",
		"description": "Repartition des opportunites par statut.",
		"widget_type": "chart",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.pipeline_health_widget",
		"category": "CRM",
		"module_name": "Selling",
		"icon": "activity",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "OVERDUE_INVOICES",
		"title": "Factures en retard",
		"description": "Encours client en retard de paiement.",
		"widget_type": "number_card",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.overdue_invoices_widget",
		"category": "Finance",
		"module_name": "Selling",
		"icon": "alert-circle",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Consumer", "can_view": 1, "can_use": 1},
		),
	},
		{
			"name": "REVENUE_BY_CATEGORY",
			"title": "CA par groupe client",
			"description": "Repartition du chiffre d'affaires par groupe client.",
			"widget_type": "chart",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.revenue_by_category_widget",
		"category": "Ventes",
		"module_name": "Selling",
		"icon": "bar-chart",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
				{"role": "Dashboard Consumer", "can_view": 1, "can_use": 1},
			),
		},
		{
			"name": "AI_SELLING_INSIGHTS",
			"title": "Analyse IA Ventes",
			"description": "Synthese, anomalies et recommandations IA generees a partir des KPIs Ventes.",
			"widget_type": "ai_insight",
			"data_source_type": "python_method",
			"python_method": "custom_dashboard.services.ai_executor.ai_selling_insights_widget",
			"category": "Ventes",
			"module_name": "Selling",
			"icon": "cpu",
			"is_active": 1,
			"allow_filters": 1,
			"roles": (
				{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
				{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
			),
		},
		{
			"name": "SELLING_REVENUE_SNAPSHOT",
			"title": "Ventes - CA periode",
			"description": "Montant facture et nombre de factures sur le module Ventes.",
		"widget_type": "number_card",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.sales_this_month_widget",
		"category": "Ventes",
		"module_name": "Selling",
		"icon": "target",
		"is_active": 0,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Consumer", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "SELLING_REVENUE_TREND",
		"title": "Ventes - Tendance CA",
		"description": "Evolution mensuelle du chiffre d'affaires ventes.",
		"widget_type": "chart",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.monthly_revenue_chart_widget",
		"category": "Ventes",
		"module_name": "Selling",
		"icon": "trend-up",
		"is_active": 0,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Consumer", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "SELLING_TOP_CUSTOMERS",
		"title": "Ventes - Top clients",
		"description": "Top clients du module Ventes classes par chiffre d'affaires.",
		"widget_type": "table",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.top_customers_widget",
		"category": "Ventes",
		"module_name": "Selling",
		"icon": "users",
		"is_active": 0,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Consumer", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "SELLING_OVERDUE_INVOICES",
		"title": "Ventes - Factures en retard",
		"description": "Montant et volume des factures ventes en retard.",
		"widget_type": "number_card",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.overdue_invoices_widget",
		"category": "Ventes",
		"module_name": "Selling",
		"icon": "alert-circle",
		"is_active": 0,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Consumer", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "BUYING_SPEND_THIS_MONTH",
		"title": "Achats - depenses periode",
		"description": "Montant des achats factures et nombre de factures achat.",
		"widget_type": "number_card",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.buying_spend_this_month_widget",
		"category": "Achats",
		"module_name": "Buying",
		"icon": "shopping-cart",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Consumer", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "BUYING_MONTHLY_SPEND",
		"title": "Achats - tendance depenses",
		"description": "Evolution mensuelle des depenses d'achats facturees.",
		"widget_type": "chart",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.buying_monthly_spend_widget",
		"category": "Achats",
		"module_name": "Buying",
		"icon": "trend-up",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Consumer", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "BUYING_TOP_SUPPLIERS",
		"title": "Achats - top fournisseurs",
		"description": "Top fournisseurs classes par montant d'achats factures.",
		"widget_type": "table",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.buying_top_suppliers_widget",
		"category": "Achats",
		"module_name": "Buying",
		"icon": "truck",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Consumer", "can_view": 1, "can_use": 1},
		),
	},
		{
			"name": "BUYING_OPEN_PURCHASE_ORDERS",
			"title": "Achats - commandes ouvertes",
			"description": "Montant et nombre de commandes d'achat ouvertes.",
			"widget_type": "number_card",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.buying_open_purchase_orders_widget",
		"category": "Achats",
		"module_name": "Buying",
		"icon": "clipboard-list",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
				{"role": "Dashboard Consumer", "can_view": 1, "can_use": 1},
			),
		},
		{
			"name": "AI_BUYING_INSIGHTS",
			"title": "Analyse IA Achats",
			"description": "Synthese, anomalies et recommandations IA generees a partir des KPIs Achats.",
			"widget_type": "ai_insight",
			"data_source_type": "python_method",
			"python_method": "custom_dashboard.services.ai_executor.ai_buying_insights_widget",
			"category": "Achats",
			"module_name": "Buying",
			"icon": "cpu",
			"is_active": 1,
			"allow_filters": 1,
			"roles": (
				{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
				{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
			),
		},
		{
			"name": "STOCK_TURNOVER",
			"title": "Rotation stock",
			"description": "Ratio rotation stock (valeur sortie / valeur stock) sur la periode.",
		"widget_type": "number_card",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.stock_turnover_widget",
		"category": "Stock",
		"module_name": "Stock",
		"icon": "refresh-cw",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "DORMANT_STOCK",
		"title": "Stock dormant",
		"description": "Articles en stock sans mouvement sur la periode choisie.",
		"widget_type": "number_card",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.dormant_stock_widget",
		"category": "Stock",
		"module_name": "Stock",
		"icon": "archive",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "STOCK_AGE_PROFILE",
		"title": "Age du stock",
		"description": "Valeur de stock repartie par anciennete du dernier mouvement.",
		"widget_type": "chart",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.stock_age_profile_widget",
		"category": "Stock",
		"module_name": "Stock",
		"icon": "pie-chart",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "WAREHOUSE_STOCKOUT_RISK",
		"title": "Risque rupture par entrepot",
		"description": "Entrepots les plus exposes aux ruptures projetees selon les bins.",
		"widget_type": "chart",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.warehouse_stockout_risk_widget",
		"category": "Stock",
		"module_name": "Stock",
		"icon": "alert-circle",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "MONTHLY_STOCK_FLOW",
		"title": "Flux mensuel du stock",
		"description": "Entrees et sorties mensuelles calculees depuis le grand livre de stock.",
		"widget_type": "chart",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.monthly_stock_flow_widget",
		"category": "Stock",
		"module_name": "Stock",
		"icon": "activity",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "RESERVATION_PRESSURE",
		"title": "Pression de reservation",
		"description": "Tension de reservation par entrepot pour detecter les stocks deja promis.",
		"widget_type": "chart",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.reservation_pressure_widget",
		"category": "Stock",
		"module_name": "Stock",
		"icon": "layers",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "INVENTORY_CONCENTRATION",
		"title": "Concentration ABC",
		"description": "Concentration ABC du capital immobilise dans le stock courant.",
		"widget_type": "chart",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.inventory_concentration_widget",
		"category": "Stock",
		"module_name": "Stock",
		"icon": "package",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "AI_STOCK_INSIGHTS",
		"title": "Analyse IA Stock",
		"description": "Synthese, anomalies et recommandations IA generees a partir des KPIs Stock.",
		"widget_type": "ai_insight",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.ai_executor.ai_stock_insights_widget",
		"category": "Stock",
		"module_name": "Stock",
		"icon": "cpu",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "PAYMENT_DELAY",
		"title": "Delai moyen paiement",
		"description": "Delai moyen de paiement clients.",
		"widget_type": "number_card",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.payment_delay_widget",
		"category": "Finance",
		"module_name": "Selling",
		"icon": "clock",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Consumer", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "AT_RISK_CUSTOMERS",
		"title": "Clients a risque",
		"description": "Clients avec factures en retard.",
		"widget_type": "number_card",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.at_risk_customers_widget",
		"category": "CRM",
		"module_name": "Selling",
		"icon": "alert-triangle",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
		),
	},
	{
		"name": "PROFITABLE_PRODUCTS",
		"title": "Produits rentables",
		"description": "Top produits classes par marge.",
		"widget_type": "table",
		"data_source_type": "python_method",
		"python_method": "custom_dashboard.services.widget_executor.profitable_products_widget",
		"category": "Ventes",
		"module_name": "Selling",
		"icon": "star",
		"is_active": 1,
		"allow_filters": 1,
		"roles": (
			{"role": "Dashboard Admin", "can_view": 1, "can_use": 1},
			{"role": "Dashboard Manager", "can_view": 1, "can_use": 1},
		),
	},
)


DEMO_DASHBOARD = {
	"name": "CUSTOM_DASHBOARD_SHARED_DEMO",
	"title": "Tableau de bord partage - demo",
	"user": "Administrator",
	"is_default": 0,
	"is_shared": 1,
	"items": (
		{"widget": "SALES_THIS_MONTH", "x": 0, "y": 0, "w": 3, "h": 3},
		{"widget": "OVERDUE_INVOICES", "x": 3, "y": 0, "w": 3, "h": 3},
		{"widget": "MONTHLY_REVENUE_CHART", "x": 0, "y": 3, "w": 8, "h": 5},
		{"widget": "PIPELINE_HEALTH", "x": 8, "y": 3, "w": 4, "h": 5},
		{"widget": "TOP_CUSTOMERS", "x": 0, "y": 8, "w": 8, "h": 5},
	),
}

MODULE_DEMO_DASHBOARDS = {
	"Selling": {
		"title": "Tableau de bord Ventes",
		"items": (
			{"widget": "SALES_THIS_MONTH", "x": 0, "y": 0, "w": 3, "h": 3},
			{"widget": "OVERDUE_INVOICES", "x": 3, "y": 0, "w": 3, "h": 3},
			{"widget": "MONTHLY_REVENUE_CHART", "x": 0, "y": 3, "w": 8, "h": 5},
			{"widget": "TOP_CUSTOMERS", "x": 0, "y": 8, "w": 8, "h": 5},
		),
	},
	"Buying": {
		"title": "Tableau de bord Achats",
		"items": (
			{"widget": "BUYING_SPEND_THIS_MONTH", "x": 0, "y": 0, "w": 3, "h": 3},
			{"widget": "BUYING_OPEN_PURCHASE_ORDERS", "x": 3, "y": 0, "w": 3, "h": 3},
			{"widget": "BUYING_MONTHLY_SPEND", "x": 0, "y": 3, "w": 8, "h": 5},
			{"widget": "BUYING_TOP_SUPPLIERS", "x": 0, "y": 8, "w": 8, "h": 5},
		),
	},
}


BROKEN_STANDARD_CHARTS = {
	# nom du Dashboard Chart -> noms possibles du Dashboard Chart Source
	# selon la version/export ERPNext (nom lisible ou dossier scrubbed).
	"Stock Value by Item Group": (
		"Stock Value by Item Group",
		"stock_value_by_item_group",
	),
}


def after_install():
	ensure_demo_setup()
	patch_broken_standard_charts()


def after_migrate():
	ensure_demo_setup()
	patch_broken_standard_charts()


def patch_broken_standard_charts() -> None:
	"""Repare les Dashboard Charts standards livres avec chart_type=Custom mais source vide.

	ERPNext expose certains charts (ex: 'Stock Value by Item Group') sans champ
	`source` dans le JSON, ce qui declenche un `get_config({name: ""})` cote
	frontend et un popup d'erreur serveur a chaque chargement du workspace.
	On retablit le lien vers le Dashboard Chart Source correspondant si celui-ci
	existe deja.
	"""
	if not frappe.db.exists("DocType", "Dashboard Chart"):
		return

	for chart_name, source_names in BROKEN_STANDARD_CHARTS.items():
		if not frappe.db.exists("Dashboard Chart", chart_name):
			continue

		if isinstance(source_names, str):
			source_candidates = (source_names, chart_name)
		else:
			source_candidates = tuple(source_names) + (chart_name,)

		source_name = next(
			(
				candidate
				for candidate in source_candidates
				if candidate and frappe.db.exists("Dashboard Chart Source", candidate)
			),
			None,
		)
		if not source_name:
			continue

		current = frappe.db.get_value(
			"Dashboard Chart",
			chart_name,
			["chart_type", "source"],
			as_dict=True,
		)
		if not current:
			continue
		if (current.chart_type or "") != "Custom":
			continue
		if (current.source or "").strip():
			continue

		frappe.db.set_value(
			"Dashboard Chart",
			chart_name,
			"source",
			source_name,
			update_modified=False,
		)
		frappe.clear_document_cache("Dashboard Chart", chart_name)


def sync_records():
	"""Sync only this app's standard records without running a full site migrate."""
	from frappe.model.sync import sync_for

	sync_for("custom_dashboard")
	ensure_dashboard_builder_page()
	ensure_transferred_pages_module()
	ensure_module_workspace_icon_links()
	ensure_dashboard_workspace_sidebar()
	ensure_dashboard_desktop_icon()
	ensure_dashboard_in_desktop_layouts()
	patch_broken_standard_charts()
	frappe.clear_cache()


def sync_and_seed():
	sync_records()
	ensure_demo_setup()


def inspect_dashboard_builder():
	"""Return source and database information for the dashboard builder page."""
	app_root = Path(__file__).resolve().parent
	page_json_path = app_root / "custom_dashboard" / "page" / "dashboard_builder" / "dashboard_builder.json"
	page_json = json.loads(page_json_path.read_text())

	return {
		"source_modules": (app_root / "modules.txt").read_text().strip().splitlines(),
		"source_page": {
			"name": page_json.get("name"),
			"page_name": page_json.get("page_name"),
			"module": page_json.get("module"),
			"title": page_json.get("title"),
			"standard": page_json.get("standard"),
		},
		"db_page": frappe.db.get_value(
			"Page",
			"dashboard-builder",
			["name", "module", "title", "page_name", "standard"],
			as_dict=True,
		),
		"db_modules": frappe.get_all(
			"Module Def",
			filters={"name": ["in", ["Dashboard", "Custom Dashboard"]]},
			fields=["name", "app_name"],
			order_by="name asc",
		),
	}


def inspect_recent_errors(limit: int = 5):
	"""Return recent error logs with truncated tracebacks for quick diagnosis."""
	rows = frappe.get_all(
		"Error Log",
		fields=["name", "method", "creation", "error"],
		order_by="creation desc",
		limit_page_length=limit,
	)
	return [
		{
			"name": row.name,
			"method": row.method,
			"creation": row.creation,
			"error": (row.error or "")[:4000],
		}
		for row in rows
	]


def inspect_module_dashboards():
	"""Return published dashboards for Stock/Selling/Buying with default flags."""
	return frappe.get_all(
		"User Dashboard",
		filters={"module_name": ["in", ["Stock", "Selling", "Buying"]]},
		fields=["name", "title", "module_name", "is_default", "is_shared", "modified"],
		order_by="module_name asc, modified desc",
	)


def inspect_module_widgets():
	"""Return module-scoped widgets for Stock/Selling/Buying."""
	return frappe.get_all(
		"Custom Dashboard Widget",
		filters={"module_name": ["in", ["Stock", "Selling", "Buying"]]},
		fields=["name", "title", "module_name", "widget_type", "is_active"],
		order_by="module_name asc, name asc",
	)


def inspect_dashboard_pages():
	"""Return availability of custom module pages."""
	return frappe.get_all(
		"Page",
		filters={"name": ["in", ["stock-dashboard", "vente-dashboard", "achat-dashboard"]]},
		fields=["name", "title", "module", "page_name", "modified"],
		order_by="name asc",
	)


def inspect_native_dashboards(limit: int = 100):
	"""Return native Frappe dashboards that can affect /dashboard-view routes."""
	if not frappe.db.exists("DocType", "Dashboard"):
		return []

	return frappe.get_all(
		"Dashboard",
		fields=["name", "dashboard_name", "module", "is_default", "is_standard"],
		order_by="is_default desc, module asc, name asc",
		limit_page_length=limit,
	)


def inspect_module_sidebar_dashboard_links():
	"""Return the active sidebar dashboard links for Stock/Selling/Buying."""
	rows = []
	if not frappe.db.exists("DocType", "Workspace Sidebar"):
		return rows

	for sidebar_title in MODULE_SIDEBAR_DASHBOARD_PAGES:
		sidebars = _module_sidebar_rows(sidebar_title)
		if not sidebars:
			rows.append({"sidebar": sidebar_title, "status": "missing"})
			continue

		for sidebar_row in sidebars:
			sidebar = frappe.get_doc("Workspace Sidebar", sidebar_row.name)
			for item in sidebar.get("items") or []:
				label = (item.label or "").strip()
				if (
					item.type == "Link"
					and (
						label.lower() in DASHBOARD_SIDEBAR_LABELS
						or item.link_type == "Dashboard"
						or item.link_to in MODULE_SIDEBAR_DASHBOARD_PAGES.values()
					)
				):
					rows.append(
						{
							"sidebar": sidebar_row.title or sidebar_row.name,
							"for_user": sidebar_row.for_user,
							"label": label,
							"link_type": item.link_type,
							"link_to": item.link_to,
							"idx": item.idx,
						}
				)
	return rows


def _is_module_dashboard_sidebar_item(item, module_name: str, page_name: str) -> bool:
	label = (item.label or "").strip().lower()
	return (
		item.type == "Link"
		and (
			label in DASHBOARD_SIDEBAR_LABELS
			or item.link_type == "Dashboard"
		)
		and (
			not item.link_to
			or item.link_to in {module_name, page_name}
			or item.link_type == "Dashboard"
		)
	)


def ensure_module_sidebar_dashboard_links():
	"""Point ERPNext module sidebar dashboard items to the custom dashboard pages.

	The native Dashboard link resolves to /desk/dashboard-view/<Dashboard>. On
	customized sites that can drift to another dashboard (for example Asset), so
	we use a direct Page link as the source of truth.
	"""
	if not frappe.db.exists("DocType", "Workspace Sidebar"):
		return []

	changes = []
	for sidebar_title, page_name in MODULE_SIDEBAR_DASHBOARD_PAGES.items():
		if not frappe.db.exists("Page", page_name):
			continue

		for sidebar_row in _module_sidebar_rows(sidebar_title):
			sidebar = frappe.get_doc("Workspace Sidebar", sidebar_row.name)
			for item in sidebar.get("items") or []:
				if not _is_module_dashboard_sidebar_item(item, sidebar_title, page_name):
					continue
				if item.link_type == "Page" and item.link_to == page_name:
					continue

				changes.append(
					{
						"sidebar": sidebar_row.title or sidebar_row.name,
						"for_user": sidebar_row.for_user,
						"label": item.label,
						"old_link_type": item.link_type,
						"old_link_to": item.link_to,
						"new_link_type": "Page",
						"new_link_to": page_name,
					}
				)
				frappe.db.set_value(
					"Workspace Sidebar Item",
					item.name,
					{
						"link_type": "Page",
						"link_to": page_name,
						"url": "",
						"route_options": "",
					},
					update_modified=False,
				)

			if any(change["sidebar"] == (sidebar_row.title or sidebar_row.name) for change in changes):
				frappe.clear_document_cache("Workspace Sidebar", sidebar_row.name)

	return changes


MODULE_WORKSPACE_ICON_FIXES = {
	# Workspace Sidebar title -> URL a poser sur le 1er item (label "Home").
	# ERPNext n'expose pas de Workspace doctype pour Selling/Buying, donc
	# get_route_for_icon() (frappe/public/js/frappe/utils/utils.js) renvoie
	# undefined et le clic sur l'icone affiche un popup
	# "Icon is not correctly configured". On bascule le link_type "Workspace"
	# en "URL" pour fournir une route explicite vers le workspace.
	"Selling": "/app/selling",
	"Buying": "/app/buying",
}


def ensure_module_workspace_icon_links():
	"""Pose une URL explicite sur le 1er item des sidebars Selling/Buying."""
	if not frappe.db.exists("DocType", "Workspace Sidebar"):
		return []

	changes = []
	for sidebar_title, target_url in MODULE_WORKSPACE_ICON_FIXES.items():
		for sidebar_row in _module_sidebar_rows(sidebar_title):
			sidebar = frappe.get_doc("Workspace Sidebar", sidebar_row.name)
			first_link = next(
				(item for item in sidebar.get("items") or [] if item.type == "Link"),
				None,
			)
			if not first_link:
				continue
			if first_link.link_type == "URL" and first_link.url == target_url:
				continue

			changes.append(
				{
					"sidebar": sidebar_row.title or sidebar_row.name,
					"label": first_link.label,
					"old_link_type": first_link.link_type,
					"old_link_to": first_link.link_to,
					"new_link_type": "URL",
					"new_url": target_url,
				}
			)
			frappe.db.set_value(
				"Workspace Sidebar Item",
				first_link.name,
				{
					"link_type": "URL",
					"url": target_url,
					"link_to": "",
					"route_options": "",
				},
				update_modified=False,
			)

			frappe.clear_document_cache("Workspace Sidebar", sidebar_row.name)

	return changes


def ensure_demo_setup():
	ensure_dashboard_builder_page()
	ensure_transferred_pages_module()
	ensure_module_sidebar_dashboard_links()
	ensure_module_workspace_icon_links()
	ensure_dashboard_workspace_sidebar()
	ensure_dashboard_desktop_icon()
	ensure_dashboard_in_desktop_layouts()

	if not frappe.db.exists("DocType", "Custom Dashboard Widget"):
		return

	ensure_roles()
	ensure_demo_widgets()
	cleanup_seeded_module_dashboards()
	ensure_demo_dashboard()


def ensure_roles():
	for role_name in DEMO_ROLES:
		if frappe.db.exists("Role", role_name):
			continue

		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role_name,
				"desk_access": 1,
			}
		).insert(ignore_permissions=True)


def ensure_demo_widgets():
	for widget in DEMO_WIDGETS:
		if frappe.db.exists("Custom Dashboard Widget", widget["name"]):
			doc = frappe.get_doc("Custom Dashboard Widget", widget["name"])
		else:
			doc = frappe.new_doc("Custom Dashboard Widget")
			doc.name = widget["name"]

		doc.title = widget["title"]
		doc.description = widget.get("description")
		doc.widget_type = widget["widget_type"]
		doc.data_source_type = widget["data_source_type"]
		doc.python_method = widget.get("python_method")
		doc.static_data_json = widget.get("static_data_json")
		doc.category = widget.get("category")
		doc.module_name = widget.get("module_name")
		doc.icon = widget.get("icon")
		doc.is_active = widget.get("is_active", 1)
		doc.allow_filters = widget.get("allow_filters", 0)
		doc.set("roles", [])
		for role in widget.get("roles", []):
			doc.append(
				"roles",
				{
					"doctype": "Custom Dashboard Widget Role",
					"role": role["role"],
					"can_view": role.get("can_view", 0),
					"can_use": role.get("can_use", 0),
				},
			)

		doc.save(ignore_permissions=True)
		frappe.clear_document_cache("Custom Dashboard Widget", doc.name)


def ensure_demo_dashboard():
	name = DEMO_DASHBOARD["name"]
	if frappe.db.exists("User Dashboard", name):
		dashboard = frappe.get_doc("User Dashboard", name)
	else:
		legacy_name = frappe.db.get_value(
			"User Dashboard",
			{"user": DEMO_DASHBOARD["user"], "title": ["in", list(LEGACY_DEMO_DASHBOARD_TITLES)]},
		)
		if legacy_name:
			dashboard = frappe.get_doc("User Dashboard", legacy_name)
		else:
			dashboard = frappe.new_doc("User Dashboard")
			dashboard.name = name

	dashboard.title = DEMO_DASHBOARD["title"]
	dashboard.user = DEMO_DASHBOARD["user"]
	dashboard.is_default = DEMO_DASHBOARD["is_default"]
	dashboard.is_shared = DEMO_DASHBOARD["is_shared"]
	dashboard.set("shares", [])
	dashboard.set("items", [])
	for item in DEMO_DASHBOARD["items"]:
		dashboard.append(
			"items",
			{
				"doctype": "User Dashboard Item",
				"widget": item["widget"],
				"x": item["x"],
				"y": item["y"],
				"w": item["w"],
				"h": item["h"],
				"display_title": frappe.db.get_value(
					"Custom Dashboard Widget", item["widget"], "title"
				)
				or item["widget"].replace("_", " ").title(),
			},
		)

	dashboard.save(ignore_permissions=True)


def ensure_module_dashboards():
	"""Deprecated: module dashboards are now created only from the builder."""
	return


def _seeded_module_dashboard_matches(dashboard, config: dict) -> bool:
	expected_widgets = [item["widget"] for item in config.get("items") or []]
	actual_widgets = [item.widget for item in dashboard.get("items") or []]
	return (
		dashboard.user == "Administrator"
		and dashboard.title == config.get("title")
		and actual_widgets == expected_widgets
	)


def cleanup_seeded_module_dashboards():
	"""Remove only dashboards that match the old automatic module seeds.

	Custom dashboards created from the builder are left untouched.
	"""
	for module_name, config in MODULE_DEMO_DASHBOARDS.items():
		existing_names = frappe.get_all(
			"User Dashboard",
			{"module_name": module_name},
			pluck="name",
		)
		for name in existing_names:
			dashboard = frappe.get_doc("User Dashboard", name)
			if not _seeded_module_dashboard_matches(dashboard, config):
				continue

			dashboard.delete(ignore_permissions=True)
			frappe.clear_document_cache("User Dashboard", name)


def build_seed_module_dashboard(module_name: str):
	"""Keep the previous seeding logic available for manual troubleshooting only."""
	config = MODULE_DEMO_DASHBOARDS.get(module_name)
	if not config:
		frappe.throw(f"Module non supporte: {module_name}")

	existing = frappe.db.get_value(
		"User Dashboard",
		{"module_name": module_name},
		"name",
	)
	if existing:
		return frappe.get_doc("User Dashboard", existing)

	dashboard = frappe.new_doc("User Dashboard")
	dashboard.title = config["title"]
	dashboard.user = "Administrator"
	dashboard.module_name = module_name
	dashboard.is_default = 1
	dashboard.is_shared = 1
	dashboard.set("shares", [])
	dashboard.set("items", [])

	for item in config.get("items") or []:
		widget_name = item.get("widget")
		if not widget_name or not frappe.db.exists("Custom Dashboard Widget", widget_name):
			continue

		dashboard.append(
			"items",
			{
				"doctype": "User Dashboard Item",
				"widget": widget_name,
				"x": item["x"],
				"y": item["y"],
				"w": item["w"],
				"h": item["h"],
				"display_title": frappe.db.get_value(
					"Custom Dashboard Widget",
					widget_name,
					"title",
				)
				or widget_name.replace("_", " ").title(),
			},
		)

	if dashboard.get("items"):
		dashboard.save(ignore_permissions=True)
	return dashboard


def ensure_dashboard_builder_page():
	"""Normalize the page metadata after earlier module-name experiments."""
	if not frappe.db.exists("Page", "dashboard-builder"):
		return

	frappe.db.set_value("Page", "dashboard-builder", "module", "Custom Dashboard", update_modified=False)
	frappe.db.set_value(
		"Page",
		"dashboard-builder",
		"title",
		"Constructeur de tableaux de bord",
		update_modified=False,
	)


def ensure_transferred_pages_module():
	"""Recâble les Pages déplacées depuis frappe vers custom_dashboard.

	Sans ça, Frappe résout le chemin disque vers `apps/frappe/frappe/desk/page/...`
	(ancien module en base) et lève FileNotFoundError.
	"""
	for page_name in (
		"admin-dashboard",
		"global-dashboard",
		"dashboard-management",
		"widget-management",
	):
		if not frappe.db.exists("Page", page_name):
			continue
		frappe.db.set_value(
			"Page", page_name, "module", "Custom Dashboard", update_modified=False
		)
		frappe.clear_document_cache("Page", page_name)


def ensure_dashboard_workspace_sidebar():
	"""Upsert the public workspace sidebar from the app's standard JSON definition."""
	if not frappe.db.exists("DocType", "Workspace Sidebar"):
		return

	app_root = Path(__file__).resolve().parent
	sidebar_json_path = app_root / "custom_dashboard" / "workspace_sidebar" / "custom_dashboard.json"
	if not sidebar_json_path.exists():
		return

	sidebar_json = json.loads(sidebar_json_path.read_text())
	title = sidebar_json.get("title")
	if not title:
		return

	if frappe.db.exists("Workspace Sidebar", title):
		sidebar = frappe.get_doc("Workspace Sidebar", title)
	else:
		sidebar = frappe.new_doc("Workspace Sidebar")
		sidebar.title = title

	sidebar.header_icon = sidebar_json.get("header_icon")
	sidebar.app = sidebar_json.get("app")
	sidebar.module = sidebar_json.get("module")
	sidebar.standard = sidebar_json.get("standard", 0)
	sidebar.for_user = sidebar_json.get("for_user")
	sidebar.set("items", [])
	for item in sidebar_json.get("items") or []:
		sidebar.append("items", item)

	sidebar.save(ignore_permissions=True)
	frappe.clear_document_cache("Workspace Sidebar", title)


def ensure_dashboard_desktop_icon():
	"""Upsert every Desktop Icon shipped under the app's desktop_icon/ folder."""
	if not frappe.db.exists("DocType", "Desktop Icon"):
		return

	app_root = Path(__file__).resolve().parent
	desktop_icon_dir = app_root / "desktop_icon"

	if desktop_icon_dir.exists():
		for icon_json_path in sorted(desktop_icon_dir.glob("*.json")):
			icon_json = json.loads(icon_json_path.read_text())
			label = icon_json.get("label") or icon_json.get("name")
			if not label:
				continue

			if frappe.db.exists("Desktop Icon", label):
				icon = frappe.get_doc("Desktop Icon", label)
			else:
				icon = frappe.new_doc("Desktop Icon")
				icon.name = label
				icon.label = label

			icon.app = icon_json.get("app")
			icon.hidden = icon_json.get("hidden", 0)
			icon.icon_type = icon_json.get("icon_type", "App")
			icon.idx = icon_json.get("idx", 0)
			icon.link = icon_json.get("link")
			icon.link_type = icon_json.get("link_type", "External")
			icon.logo_url = icon_json.get("logo_url")
			icon.standard = icon_json.get("standard", 1)
			icon.set("roles", icon_json.get("roles") or [])
			icon.save(ignore_permissions=True)

	from frappe.desk.doctype.desktop_icon.desktop_icon import clear_desktop_icons_cache

	clear_desktop_icons_cache()


def _icon_payload(icon):
	return {
		"label": icon.label,
		"bg_color": getattr(icon, "bg_color", None),
		"link": icon.link,
		"link_type": icon.link_type,
		"app": icon.app,
		"icon_type": icon.icon_type,
		"parent_icon": getattr(icon, "parent_icon", None),
		"icon": getattr(icon, "icon", None),
		"link_to": getattr(icon, "link_to", None),
		"idx": icon.idx,
		"standard": icon.standard,
		"logo_url": icon.logo_url,
		"hidden": icon.hidden,
		"name": icon.name,
		"restrict_removal": getattr(icon, "restrict_removal", 0),
		"icon_image": getattr(icon, "icon_image", None),
		"child_icons": [],
	}


def ensure_dashboard_in_desktop_layouts():
	"""Append every app-shipped icon to saved desktop layouts that predate it."""
	if not frappe.db.exists("DocType", "Desktop Layout"):
		return

	app_root = Path(__file__).resolve().parent
	desktop_icon_dir = app_root / "desktop_icon"
	if not desktop_icon_dir.exists():
		return

	icon_labels = []
	for icon_json_path in sorted(desktop_icon_dir.glob("*.json")):
		icon_json = json.loads(icon_json_path.read_text())
		label = icon_json.get("label") or icon_json.get("name")
		if label and frappe.db.exists("Desktop Icon", label):
			icon_labels.append(label)

	if not icon_labels:
		return

	icons = [frappe.get_doc("Desktop Icon", label) for label in icon_labels]

	for row in frappe.get_all("Desktop Layout", fields=["name", "layout"]):
		layout_raw = row.layout or "[]"
		try:
			layout = json.loads(layout_raw)
		except json.JSONDecodeError:
			continue

		if not isinstance(layout, list):
			continue

		layout_changed = False
		existing_labels = {
			item.get("label")
			for item in layout
			if isinstance(item, dict) and item.get("label")
		}
		existing_links = {
			item.get("link")
			for item in layout
			if isinstance(item, dict) and item.get("link")
		}

		for icon in icons:
			if icon.label in existing_labels or (icon.link and icon.link in existing_links):
				continue
			layout.append(_icon_payload(icon))
			existing_labels.add(icon.label)
			if icon.link:
				existing_links.add(icon.link)
			layout_changed = True

		if not layout_changed:
			continue

		desktop_layout = frappe.get_doc("Desktop Layout", row.name)
		desktop_layout.layout = json.dumps(layout)
		desktop_layout.save(ignore_permissions=True)
