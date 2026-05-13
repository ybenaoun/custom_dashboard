from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from custom_dashboard.services import access


PERIOD_OPTIONS = [
	{"label": _("Ce mois"), "value": "this_month"},
	{"label": _("Mois dernier"), "value": "last_month"},
	{"label": _("30 derniers jours"), "value": "last_30_days"},
	{"label": _("90 derniers jours"), "value": "last_90_days"},
	{"label": _("180 derniers jours"), "value": "last_180_days"},
	{"label": _("Depuis le debut de l'annee"), "value": "year_to_date"},
	{"label": _("Personnalisee"), "value": "custom"},
]

MODULE_LABELS = {
	"": _("General"),
	"Stock": _("Stock"),
	"Selling": _("Ventes"),
	"Buying": _("Achats"),
}

DEPRECATED_WIDGET_ALIASES = {
	"SELLING_REVENUE_SNAPSHOT": "SALES_THIS_MONTH",
	"SELLING_REVENUE_TREND": "MONTHLY_REVENUE_CHART",
	"SELLING_TOP_CUSTOMERS": "TOP_CUSTOMERS",
	"SELLING_OVERDUE_INVOICES": "OVERDUE_INVOICES",
}


def _safe_link_options(doctype: str) -> list[dict[str, str]]:
	if not frappe.db.exists("DocType", doctype):
		return []

	values = frappe.get_all(doctype, pluck="name", order_by="name asc")
	return [{"label": value, "value": value} for value in values]


def _sales_filters(default_period: str = "this_month", include_limit: bool = False) -> list[dict[str, Any]]:
	filters = [
		{
			"fieldname": "company",
			"label": _("Societe"),
			"fieldtype": "Select",
			"options": [{"label": _("Toutes"), "value": ""}] + _safe_link_options("Company"),
			"default": "",
		},
		{
			"fieldname": "period",
			"label": _("Periode"),
			"fieldtype": "Select",
			"options": PERIOD_OPTIONS,
			"default": default_period,
		},
		{
			"fieldname": "from_date",
			"label": _("Du"),
			"fieldtype": "Date",
			"visible_when": {"period": "custom"},
		},
		{
			"fieldname": "to_date",
			"label": _("Au"),
			"fieldtype": "Date",
			"visible_when": {"period": "custom"},
		},
		{
			"fieldname": "customer_group",
			"label": _("Groupe client"),
			"fieldtype": "Select",
			"options": [{"label": _("Tous"), "value": ""}] + _safe_link_options("Customer Group"),
			"default": "",
		},
		{
			"fieldname": "territory",
			"label": _("Territoire"),
			"fieldtype": "Select",
			"options": [{"label": _("Tous"), "value": ""}] + _safe_link_options("Territory"),
			"default": "",
		},
	]

	if include_limit:
		filters.append(
			{
				"fieldname": "limit",
				"label": _("Nombre de lignes"),
				"fieldtype": "Int",
				"default": 5,
				"min": 1,
				"max": 20,
			}
		)

	return filters


def _pipeline_filters() -> list[dict[str, Any]]:
	return [
		{
			"fieldname": "company",
			"label": _("Societe"),
			"fieldtype": "Select",
			"options": [{"label": _("Toutes"), "value": ""}] + _safe_link_options("Company"),
			"default": "",
		},
		{
			"fieldname": "period",
			"label": _("Periode"),
			"fieldtype": "Select",
			"options": PERIOD_OPTIONS,
			"default": "last_90_days",
		},
		{
			"fieldname": "from_date",
			"label": _("Du"),
			"fieldtype": "Date",
			"visible_when": {"period": "custom"},
		},
		{
			"fieldname": "to_date",
			"label": _("Au"),
			"fieldtype": "Date",
			"visible_when": {"period": "custom"},
		},
		{
			"fieldname": "status_scope",
			"label": _("Portee"),
			"fieldtype": "Select",
			"options": [
				{"label": _("Tout le pipeline"), "value": "all"},
				{"label": _("Opportunites ouvertes"), "value": "open"},
			],
			"default": "all",
		},
	]


def _overdue_invoice_filters() -> list[dict[str, Any]]:
	return [
		{
			"fieldname": "company",
			"label": _("Societe"),
			"fieldtype": "Select",
			"options": [{"label": _("Toutes"), "value": ""}] + _safe_link_options("Company"),
			"default": "",
		},
		{
			"fieldname": "customer_group",
			"label": _("Groupe client"),
			"fieldtype": "Select",
			"options": [{"label": _("Tous"), "value": ""}] + _safe_link_options("Customer Group"),
			"default": "",
		},
		{
			"fieldname": "territory",
			"label": _("Territoire"),
			"fieldtype": "Select",
			"options": [{"label": _("Tous"), "value": ""}] + _safe_link_options("Territory"),
			"default": "",
		},
	]


def _purchase_filters(
	default_period: str = "this_month", include_limit: bool = False
) -> list[dict[str, Any]]:
	filters = [
		{
			"fieldname": "company",
			"label": _("Societe"),
			"fieldtype": "Select",
			"options": [{"label": _("Toutes"), "value": ""}] + _safe_link_options("Company"),
			"default": "",
		},
		{
			"fieldname": "period",
			"label": _("Periode"),
			"fieldtype": "Select",
			"options": PERIOD_OPTIONS,
			"default": default_period,
		},
		{
			"fieldname": "from_date",
			"label": _("Du"),
			"fieldtype": "Date",
			"visible_when": {"period": "custom"},
		},
		{
			"fieldname": "to_date",
			"label": _("Au"),
			"fieldtype": "Date",
			"visible_when": {"period": "custom"},
		},
		{
			"fieldname": "supplier",
			"label": _("Fournisseur"),
			"fieldtype": "Select",
			"options": [{"label": _("Tous"), "value": ""}] + _safe_link_options("Supplier"),
			"default": "",
		},
		{
			"fieldname": "supplier_group",
			"label": _("Groupe fournisseur"),
			"fieldtype": "Select",
			"options": [{"label": _("Tous"), "value": ""}] + _safe_link_options("Supplier Group"),
			"default": "",
		},
	]

	if include_limit:
		filters.append(
			{
				"fieldname": "limit",
				"label": _("Nombre de lignes"),
				"fieldtype": "Int",
				"default": 5,
				"min": 1,
				"max": 20,
			}
		)

	return filters


def _stock_snapshot_filters(include_limit: bool = False) -> list[dict[str, Any]]:
	filters = [
		{
			"fieldname": "company",
			"label": _("Societe"),
			"fieldtype": "Select",
			"options": [{"label": _("Toutes"), "value": ""}] + _safe_link_options("Company"),
			"default": "",
		},
		{
			"fieldname": "warehouse",
			"label": _("Entrepot"),
			"fieldtype": "Select",
			"options": [{"label": _("Tous"), "value": ""}] + _safe_link_options("Warehouse"),
			"default": "",
		},
		{
			"fieldname": "item_group",
			"label": _("Groupe d'articles"),
			"fieldtype": "Select",
			"options": [{"label": _("Tous"), "value": ""}] + _safe_link_options("Item Group"),
			"default": "",
		},
	]

	if include_limit:
		filters.append(
			{
				"fieldname": "limit",
				"label": _("Nombre de lignes"),
				"fieldtype": "Int",
				"default": 6,
				"min": 3,
				"max": 12,
			}
		)

	return filters


def _stock_movement_filters(
	default_period: str = "last_90_days", include_limit: bool = False
) -> list[dict[str, Any]]:
	filters = _stock_snapshot_filters(include_limit=include_limit)
	filters[1:1] = [
		{
			"fieldname": "period",
			"label": _("Periode"),
			"fieldtype": "Select",
			"options": PERIOD_OPTIONS,
			"default": default_period,
		},
		{
			"fieldname": "from_date",
			"label": _("Du"),
			"fieldtype": "Date",
			"visible_when": {"period": "custom"},
		},
		{
			"fieldname": "to_date",
			"label": _("Au"),
			"fieldtype": "Date",
			"visible_when": {"period": "custom"},
		},
	]
	return filters


WIDGET_BLUEPRINTS = {
	"SELLING_REVENUE_SNAPSHOT": {
		"description": _("Chiffre d'affaires facture sur la periode des ventes."),
		"default_w": 3,
		"default_h": 3,
		"filters_schema_builder": lambda: _sales_filters("this_month"),
		"default_filters": {"period": "this_month", "company": "", "customer_group": "", "territory": ""},
		"chart_options": {},
	},
	"SELLING_REVENUE_TREND": {
		"description": _("Evolution mensuelle du chiffre d'affaires facture pour les ventes."),
		"default_w": 8,
		"default_h": 5,
		"filters_schema_builder": lambda: _sales_filters("last_180_days"),
		"default_filters": {"period": "last_180_days", "company": "", "customer_group": "", "territory": ""},
		"chart_options": {
			"chart_type": "line",
			"colors": ["#0f766e", "#1d4ed8"],
			"height": 260,
		},
	},
	"SELLING_TOP_CUSTOMERS": {
		"description": _("Top clients du module ventes, classes par chiffre d'affaires."),
		"default_w": 6,
		"default_h": 5,
		"filters_schema_builder": lambda: _sales_filters("last_90_days", include_limit=True),
		"default_filters": {
			"period": "last_90_days",
			"company": "",
			"customer_group": "",
			"territory": "",
			"limit": 5,
		},
		"chart_options": {},
	},
	"SELLING_OVERDUE_INVOICES": {
		"description": _("Montant et volume des factures ventes en retard."),
		"default_w": 3,
		"default_h": 3,
		"filters_schema_builder": _overdue_invoice_filters,
		"default_filters": {"company": "", "customer_group": "", "territory": ""},
		"chart_options": {},
	},
	"BUYING_SPEND_THIS_MONTH": {
		"description": _("Montant des achats factures sur la periode selectionnee."),
		"default_w": 3,
		"default_h": 3,
		"filters_schema_builder": lambda: _purchase_filters("this_month"),
		"default_filters": {
			"period": "this_month",
			"company": "",
			"supplier": "",
			"supplier_group": "",
		},
		"chart_options": {},
	},
	"BUYING_MONTHLY_SPEND": {
		"description": _("Evolution mensuelle des achats factures."),
		"default_w": 8,
		"default_h": 5,
		"filters_schema_builder": lambda: _purchase_filters("last_180_days"),
		"default_filters": {
			"period": "last_180_days",
			"company": "",
			"supplier": "",
			"supplier_group": "",
		},
		"chart_options": {
			"chart_type": "line",
			"colors": ["#7c2d12", "#0f766e"],
			"height": 260,
		},
	},
	"BUYING_TOP_SUPPLIERS": {
		"description": _("Top fournisseurs par montant d'achats factures."),
		"default_w": 6,
		"default_h": 5,
		"filters_schema_builder": lambda: _purchase_filters("last_90_days", include_limit=True),
		"default_filters": {
			"period": "last_90_days",
			"company": "",
			"supplier": "",
			"supplier_group": "",
			"limit": 5,
		},
		"chart_options": {},
	},
		"BUYING_OPEN_PURCHASE_ORDERS": {
			"description": _("Commandes d'achat ouvertes sur la periode choisie."),
			"default_w": 3,
			"default_h": 3,
			"filters_schema_builder": lambda: _purchase_filters("last_90_days"),
		"default_filters": {
			"period": "last_90_days",
			"company": "",
			"supplier": "",
			"supplier_group": "",
			},
			"chart_options": {},
		},
		"AI_BUYING_INSIGHTS": {
			"description": _(
				"Analyse IA des achats : synthese, anomalies fournisseurs et recommandations d'approvisionnement."
			),
			"default_w": 8,
			"default_h": 7,
			"filters_schema_builder": lambda: _purchase_filters("last_90_days", include_limit=True),
			"default_filters": {
				"period": "last_90_days",
				"company": "",
				"supplier": "",
				"supplier_group": "",
				"limit": 5,
			},
			"chart_options": {},
		},
		"SALES_THIS_MONTH": {
			"description": _("Montant facture et nombre de factures clients soumises sur la periode choisie."),
			"default_w": 3,
			"default_h": 3,
		"filters_schema_builder": lambda: _sales_filters("this_month"),
		"default_filters": {"period": "this_month", "company": "", "customer_group": "", "territory": ""},
		"chart_options": {},
	},
	"MONTHLY_REVENUE_CHART": {
		"description": _("Evolution mensuelle du chiffre d'affaires facture sur les six derniers mois."),
		"default_w": 8,
		"default_h": 5,
		"filters_schema_builder": lambda: _sales_filters("last_180_days"),
		"default_filters": {"period": "last_180_days", "company": "", "customer_group": "", "territory": ""},
		"chart_options": {
			"chart_type": "line",
			"colors": ["#0f766e", "#c084fc"],
			"height": 260,
		},
	},
	"TOP_CUSTOMERS": {
		"description": _("Classement des meilleurs clients par chiffre d'affaires facture."),
		"default_w": 6,
		"default_h": 5,
		"filters_schema_builder": lambda: _sales_filters("last_90_days", include_limit=True),
		"default_filters": {
			"period": "last_90_days",
			"company": "",
			"customer_group": "",
			"territory": "",
			"limit": 5,
		},
		"chart_options": {},
	},
	"PIPELINE_HEALTH": {
		"description": _("Repartition des opportunites commerciales par statut sur la periode choisie."),
		"default_w": 4,
		"default_h": 5,
		"filters_schema_builder": _pipeline_filters,
		"default_filters": {"period": "last_90_days", "company": "", "status_scope": "all"},
		"chart_options": {
			"chart_type": "donut",
			"colors": ["#0f766e", "#f59e0b", "#2563eb", "#ef4444"],
			"height": 260,
		},
	},
	"OVERDUE_INVOICES": {
		"description": _("Montant et volume des factures clientes en retard de paiement."),
		"default_w": 3,
		"default_h": 3,
		"filters_schema_builder": _overdue_invoice_filters,
		"default_filters": {"company": "", "customer_group": "", "territory": ""},
		"chart_options": {},
	},
		"REVENUE_BY_CATEGORY": {
			"description": _("Chiffre d'affaires reparti par groupe client sur la periode choisie."),
			"default_w": 5,
			"default_h": 4,
			"filters_schema_builder": lambda: _sales_filters("last_90_days", include_limit=True),
		"default_filters": {
			"period": "last_90_days",
			"company": "",
			"customer_group": "",
			"territory": "",
			"limit": 6,
		},
		"chart_options": {
			"chart_type": "bar",
			"colors": ["#0f766e", "#c084fc", "#2563eb", "#f97316", "#ef4444", "#eab308"],
			"height": 220,
			},
		},
		"AI_SELLING_INSIGHTS": {
			"description": _(
				"Analyse IA des ventes : synthese, anomalies commerciales et recommandations d'action."
			),
			"default_w": 8,
			"default_h": 7,
			"filters_schema_builder": lambda: _sales_filters("last_90_days", include_limit=True),
			"default_filters": {
				"period": "last_90_days",
				"company": "",
				"customer_group": "",
				"territory": "",
				"limit": 5,
			},
			"chart_options": {},
		},
		"STOCK_TURNOVER": {
			"description": _("Rotation du stock estimee sur la periode (valeur sortie / stock courant)."),
			"default_w": 3,
			"default_h": 3,
		"filters_schema_builder": lambda: _stock_movement_filters("last_90_days"),
		"default_filters": {
			"period": "last_90_days",
			"company": "",
			"warehouse": "",
			"item_group": "",
		},
		"chart_options": {},
	},
	"DORMANT_STOCK": {
		"description": _("Valeur et nombre d'articles en stock sans mouvement sur la periode."),
		"default_w": 3,
		"default_h": 3,
		"filters_schema_builder": lambda: _stock_movement_filters("last_90_days"),
		"default_filters": {
			"period": "last_90_days",
			"company": "",
			"warehouse": "",
			"item_group": "",
		},
		"chart_options": {},
	},
	"STOCK_AGE_PROFILE": {
		"description": _("Repartition de la valeur de stock selon l'anciennete du dernier mouvement."),
		"default_w": 5,
		"default_h": 4,
		"filters_schema_builder": _stock_snapshot_filters,
		"default_filters": {"company": "", "warehouse": "", "item_group": ""},
		"chart_options": {
			"chart_type": "donut",
			"colors": ["#0f766e", "#f59e0b", "#f97316", "#ef4444"],
			"height": 240,
		},
	},
	"WAREHOUSE_STOCKOUT_RISK": {
		"description": _("Entrepots les plus exposes aux ruptures projetees selon les bins."),
		"default_w": 6,
		"default_h": 5,
		"filters_schema_builder": lambda: _stock_snapshot_filters(include_limit=True),
		"default_filters": {
			"company": "",
			"warehouse": "",
			"item_group": "",
			"limit": 6,
		},
		"chart_options": {
			"chart_type": "bar",
			"colors": ["#ef4444", "#0f766e"],
			"height": 250,
		},
	},
	"MONTHLY_STOCK_FLOW": {
		"description": _("Flux mensuel d'entree et de sortie du stock a partir du grand livre."),
		"default_w": 8,
		"default_h": 5,
		"filters_schema_builder": lambda: _stock_movement_filters("last_180_days"),
		"default_filters": {
			"period": "last_180_days",
			"company": "",
			"warehouse": "",
			"item_group": "",
		},
		"chart_options": {
			"chart_type": "line",
			"colors": ["#0f766e", "#f97316"],
			"height": 260,
		},
	},
	"RESERVATION_PRESSURE": {
		"description": _("Tension de reservation par entrepot pour identifier les stocks deja promis."),
		"default_w": 6,
		"default_h": 5,
		"filters_schema_builder": lambda: _stock_snapshot_filters(include_limit=True),
		"default_filters": {
			"company": "",
			"warehouse": "",
			"item_group": "",
			"limit": 6,
		},
		"chart_options": {
			"chart_type": "bar",
			"colors": ["#2563eb"],
			"height": 250,
		},
	},
	"INVENTORY_CONCENTRATION": {
		"description": _("Concentration ABC du capital immobilise dans le stock courant."),
		"default_w": 5,
		"default_h": 4,
		"filters_schema_builder": _stock_snapshot_filters,
		"default_filters": {"company": "", "warehouse": "", "item_group": ""},
		"chart_options": {
			"chart_type": "donut",
			"colors": ["#0f766e", "#f59e0b", "#94a3b8"],
			"height": 240,
		},
	},
	"AI_STOCK_INSIGHTS": {
		"description": _(
			"Analyse IA du stock : synthese, anomalies detectees et recommandations operationnelles."
		),
		"default_w": 8,
		"default_h": 7,
		"filters_schema_builder": lambda: _stock_movement_filters("last_90_days"),
		"default_filters": {
			"period": "last_90_days",
			"company": "",
			"warehouse": "",
			"item_group": "",
		},
		"chart_options": {},
	},
	"PAYMENT_DELAY": {
		"description": _("Delai moyen de paiement clients sur la periode."),
		"default_w": 3,
		"default_h": 3,
		"filters_schema_builder": lambda: _sales_filters("last_90_days"),
		"default_filters": {
			"period": "last_90_days",
			"company": "",
			"customer_group": "",
			"territory": "",
		},
		"chart_options": {},
	},
	"AT_RISK_CUSTOMERS": {
		"description": _("Clients avec factures en retard de paiement."),
		"default_w": 3,
		"default_h": 3,
		"filters_schema_builder": _overdue_invoice_filters,
		"default_filters": {"company": "", "customer_group": "", "territory": ""},
		"chart_options": {},
	},
	"PROFITABLE_PRODUCTS": {
		"description": _("Top produits classes par marge sur la periode."),
		"default_w": 6,
		"default_h": 5,
		"filters_schema_builder": lambda: _sales_filters("last_90_days", include_limit=True),
		"default_filters": {
			"period": "last_90_days",
			"company": "",
			"customer_group": "",
			"territory": "",
			"limit": 5,
		},
		"chart_options": {},
	},
}


def get_widget_blueprint(widget_name: str) -> dict[str, Any]:
	return WIDGET_BLUEPRINTS.get(widget_name, {})


def get_widget_filters_schema(widget_name: str) -> list[dict[str, Any]]:
	blueprint = get_widget_blueprint(widget_name)
	builder = blueprint.get("filters_schema_builder")
	if callable(builder):
		return builder()
	return blueprint.get("filters_schema", [])


def get_widget_default_filters(widget_name: str) -> dict[str, Any]:
	blueprint = get_widget_blueprint(widget_name)
	return blueprint.get("default_filters", {})


def get_widget_default_layout(widget_name: str) -> dict[str, int]:
	blueprint = get_widget_blueprint(widget_name)
	return {
		"w": cint(blueprint.get("default_w") or 6),
		"h": cint(blueprint.get("default_h") or 4),
	}


def _serialize_base_definition(widget, user: str | None = None) -> dict[str, Any]:
	blueprint = get_widget_blueprint(widget.name)
	permissions = access.get_widget_permissions(widget, user=user)
	default_layout = get_widget_default_layout(widget.name)
	module_name = getattr(widget, "module_name", "") or ""

	return {
		"name": widget.name,
		"canonical_name": DEPRECATED_WIDGET_ALIASES.get(widget.name, widget.name),
		"title": widget.title,
		"description": widget.description or blueprint.get("description") or "",
		"widget_type": widget.widget_type,
		"data_source_type": widget.data_source_type,
		"module_name": module_name,
		"module_label": MODULE_LABELS.get(module_name, module_name or _("General")),
		"category": widget.category,
		"icon": widget.icon,
		"is_active": cint(widget.is_active),
		"allow_filters": cint(widget.allow_filters),
		"default_w": default_layout["w"],
		"default_h": default_layout["h"],
		"default_filters": get_widget_default_filters(widget.name),
		"filters_schema": get_widget_filters_schema(widget.name) if cint(widget.allow_filters) else [],
		"chart_options": blueprint.get("chart_options", {}),
		"can_view": permissions["can_view"],
		"can_use": permissions["can_use"],
	}


def serialize_widget_definition(widget, user: str | None = None) -> dict[str, Any]:
	return _serialize_base_definition(widget, user=user)


def list_available_widgets(user: str | None = None) -> list[dict[str, Any]]:
	widgets = access.list_accessible_widgets(user=user, action="view")
	available_names = {widget.name for widget in widgets}
	result = []
	seen_keys: set[tuple[str, str]] = set()

	for widget in widgets:
		canonical_name = DEPRECATED_WIDGET_ALIASES.get(widget.name, widget.name)
		if widget.name != canonical_name and canonical_name in available_names:
			continue

		module_name = getattr(widget, "module_name", "") or ""
		unique_key = (module_name, canonical_name)
		if unique_key in seen_keys:
			continue

		seen_keys.add(unique_key)
		result.append(serialize_widget_definition(widget, user=user))

	return result


def get_widget_definition(widget_name: str, user: str | None = None) -> dict[str, Any]:
	widget = access.assert_widget_access(widget_name, user=user, action="view", require_active=True)
	return serialize_widget_definition(widget, user=user)


CATEGORY_TO_MODULE = {
	"Stock": "Stock",
	"Vente": "Selling",
	"Achat": "Buying",
}

MODULE_TO_CATEGORY = {
	"Stock": "Stock",
	"Selling": "Vente",
	"Buying": "Achat",
}


def list_admin_widgets(category: str | None = None, user: str | None = None) -> list[dict[str, Any]]:
	access.require_dashboard_admin(user)
	filters: dict[str, Any] = {}
	if category:
		mapped = CATEGORY_TO_MODULE.get(category.strip()) if isinstance(category, str) else None
		if mapped:
			filters["module_name"] = mapped
		else:
			return []

	widgets = frappe.get_all(
		"Custom Dashboard Widget",
		fields=["name"],
		filters=filters,
		order_by="category asc, title asc",
	)
	result = []
	for row in widgets:
		doc = frappe.get_cached_doc("Custom Dashboard Widget", row.name)
		definition = serialize_widget_definition(doc, user=user)
		definition["category_label"] = MODULE_TO_CATEGORY.get(definition.get("module_name") or "", "")
		definition["role_count"] = len(doc.get("roles") or [])
		result.append(definition)
	return result


def admin_toggle_widget_active(
	widget_name: str, is_active: int | bool, user: str | None = None
) -> dict[str, Any]:
	access.require_dashboard_admin(user)
	if not frappe.db.exists("Custom Dashboard Widget", widget_name):
		frappe.throw(_("Widget introuvable: {0}").format(widget_name))
	doc = frappe.get_doc("Custom Dashboard Widget", widget_name)
	doc.is_active = 1 if cint(is_active) else 0
	doc.save(ignore_permissions=True)
	frappe.clear_document_cache("Custom Dashboard Widget", widget_name)
	return get_widget_admin_definition(widget_name, user=user)


def _serialize_widget_role_matrix(widget) -> list[dict[str, Any]]:
	role_map = {
		row.role: {"role": row.role, "can_view": cint(row.can_view), "can_use": cint(row.can_use)}
		for row in widget.get("roles") or []
		if row.role
	}
	rows = []
	for role in access.get_assignable_roles():
		current = role_map.get(role, {"role": role, "can_view": 0, "can_use": 0})
		rows.append(current)
	return rows


def get_widget_admin_definition(widget_name: str, user: str | None = None) -> dict[str, Any]:
	access.require_dashboard_admin(user)
	widget = frappe.get_doc("Custom Dashboard Widget", widget_name)
	payload = serialize_widget_definition(widget, user=user)
	payload["roles"] = _serialize_widget_role_matrix(widget)
	return payload


def _parse_payload(doc) -> dict[str, Any]:
	payload = frappe.parse_json(doc) if isinstance(doc, str) else doc
	as_dict = getattr(payload, "as_dict", None)
	if callable(as_dict):
		payload = as_dict()
	if not isinstance(payload, dict):
		frappe.throw(_("La configuration du widget doit etre un objet JSON."))
	return payload


def save_widget_access(doc, user: str | None = None) -> dict[str, Any]:
	access.require_dashboard_admin(user)
	payload = _parse_payload(doc)
	widget_name = payload.get("name")
	if not widget_name:
		frappe.throw(_("Le nom du widget est obligatoire."))

	widget = frappe.get_doc("Custom Dashboard Widget", widget_name)
	widget.is_active = cint(payload.get("is_active"))
	if payload.get("description") is not None:
		widget.description = payload.get("description")

	widget.set("roles", [])
	for row in payload.get("roles") or []:
		role = row.get("role")
		if not role:
			continue
		can_view = cint(row.get("can_view"))
		can_use = cint(row.get("can_use"))
		if not can_view and not can_use:
			continue
		widget.append(
			"roles",
			{
				"role": role,
				"can_view": 1 if can_view or can_use else 0,
				"can_use": 1 if can_use else 0,
			},
		)

	widget.save(ignore_permissions=True)
	frappe.clear_document_cache("Custom Dashboard Widget", widget.name)
	return get_widget_admin_definition(widget.name, user=user)
