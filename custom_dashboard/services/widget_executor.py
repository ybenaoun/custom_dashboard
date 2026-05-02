from __future__ import annotations

import json
from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, add_to_date, cint, flt, get_first_day, get_last_day, getdate, nowdate

from custom_dashboard.services import access, widget_registry


FRENCH_MONTHS = {
	1: "Janv",
	2: "Fevr",
	3: "Mars",
	4: "Avr",
	5: "Mai",
	6: "Juin",
	7: "Juil",
	8: "Aout",
	9: "Sept",
	10: "Oct",
	11: "Nov",
	12: "Dec",
}


def normalize_filters(filters=None, widget_name: str | None = None) -> dict[str, Any]:
	if filters in (None, "", {}):
		payload = {}
	elif isinstance(filters, str):
		try:
			payload = frappe.parse_json(filters) or {}
		except Exception as exc:
			frappe.throw(_("Les filtres doivent etre un JSON valide."), exc=exc.__class__)
	else:
		payload = filters

	as_dict = getattr(payload, "as_dict", None)
	if callable(as_dict):
		payload = as_dict()

	if not isinstance(payload, dict):
		frappe.throw(_("Les filtres doivent etre un objet JSON."))

	if not widget_name:
		return payload

	schema = widget_registry.get_widget_filters_schema(widget_name)
	defaults = widget_registry.get_widget_default_filters(widget_name)
	if not schema:
		return payload

	normalized: dict[str, Any] = {}
	for field in schema:
		fieldname = field.get("fieldname")
		if not fieldname:
			continue
		value = payload.get(fieldname, defaults.get(fieldname))
		normalized[fieldname] = _coerce_filter_value(field, value)

	return normalized


def _coerce_filter_value(field: dict[str, Any], value: Any) -> Any:
	fieldtype = field.get("fieldtype")
	default = field.get("default")
	if value in (None, ""):
		value = default
	if value in (None, "") and fieldtype not in {"Check", "Int", "Float"}:
		return ""

	if fieldtype == "Int":
		return cint(value or 0)
	if fieldtype in {"Float", "Currency"}:
		return flt(value or 0)
	if fieldtype == "Check":
		return 1 if cint(value) else 0
	if fieldtype == "Date":
		return str(getdate(value)) if value else ""

	return str(value or "")


def _load_static_json(widget) -> Any:
	try:
		return json.loads(widget.static_data_json or "{}")
	except json.JSONDecodeError as exc:
		frappe.throw(
			_("Le JSON statique est invalide pour le widget {0}: {1}").format(widget.name, exc),
			exc=frappe.ValidationError,
		)


def _execute_python_method(widget, filters=None) -> Any:
	try:
		method = frappe.get_attr(widget.python_method)
	except Exception as exc:
		frappe.throw(
			_("La methode Python est introuvable pour le widget {0}.").format(widget.name),
			exc=exc.__class__,
		)

	if not callable(method):
		frappe.throw(_("La methode Python n'est pas callable pour le widget {0}.").format(widget.name))

	return method(filters=normalize_filters(filters, widget_name=widget.name), widget=widget.as_dict())


def execute_widget(widget, filters=None) -> dict[str, Any]:
	if widget.data_source_type == "static_json":
		payload = _load_static_json(widget)
	elif widget.data_source_type == "python_method":
		payload = _execute_python_method(widget, filters=filters)
	else:
		frappe.throw(_("Source de donnees non supportee pour le widget {0}.").format(widget.name))

	if isinstance(payload, dict) and {"widget", "title", "type", "data"}.issubset(payload):
		payload = payload.get("data")

	return {
		"widget": widget.name,
		"title": widget.title,
		"type": widget.widget_type,
		"data": payload,
	}


def get_widget_data(widget_name: str, filters=None, user: str | None = None) -> dict[str, Any]:
	widget = access.assert_widget_access(widget_name, user=user, action="use", require_active=True)
	return execute_widget(widget, filters=filters)


def _default_currency(company: str | None = None) -> str:
	if company and frappe.db.exists("Company", company):
		return frappe.db.get_value("Company", company, "default_currency") or ""
	return frappe.defaults.get_global_default("currency") or "USD"


def _resolve_date_range(filters: dict[str, Any], default_period: str = "this_month") -> tuple[date, date]:
	period = (filters.get("period") or default_period or "this_month").strip()
	today = getdate(nowdate())

	if period == "custom" and filters.get("from_date") and filters.get("to_date"):
		start = getdate(filters.get("from_date"))
		end = getdate(filters.get("to_date"))
	elif period == "last_month":
		last_month = getdate(add_to_date(today, months=-1))
		start = get_first_day(last_month)
		end = get_last_day(last_month)
	elif period == "last_30_days":
		start = add_days(today, -29)
		end = today
	elif period == "last_90_days":
		start = add_days(today, -89)
		end = today
	elif period == "last_180_days":
		start = add_days(today, -179)
		end = today
	elif period == "year_to_date":
		start = getdate(f"{today.year}-01-01")
		end = today
	else:
		start = get_first_day(today)
		end = get_last_day(today)

	if start > end:
		start, end = end, start

	return start, end


def _sales_invoice_conditions(
	filters: dict[str, Any],
	default_period: str = "this_month",
	include_overdue_only: bool = False,
) -> tuple[list[str], dict[str, Any], date | None, date | None]:
	conditions = ["docstatus = 1", "ifnull(is_return, 0) = 0"]
	params: dict[str, Any] = {}
	start: date | None = None
	end: date | None = None

	if include_overdue_only:
		conditions.extend(["outstanding_amount > 0", "due_date < %(today)s"])
		params["today"] = getdate(nowdate())
	else:
		start, end = _resolve_date_range(filters, default_period=default_period)
		conditions.append("posting_date between %(from_date)s and %(to_date)s")
		params.update({"from_date": start, "to_date": end})

	if filters.get("company"):
		conditions.append("company = %(company)s")
		params["company"] = filters.get("company")

	if filters.get("customer_group"):
		conditions.append("customer_group = %(customer_group)s")
		params["customer_group"] = filters.get("customer_group")

	if filters.get("territory"):
		conditions.append("territory = %(territory)s")
		params["territory"] = filters.get("territory")

	return conditions, params, start, end


def _opportunity_conditions(filters: dict[str, Any]) -> tuple[list[str], dict[str, Any], date, date]:
	start, end = _resolve_date_range(filters, default_period="last_90_days")
	conditions = ["transaction_date between %(from_date)s and %(to_date)s"]
	params: dict[str, Any] = {"from_date": start, "to_date": end}

	if filters.get("company"):
		conditions.append("company = %(company)s")
		params["company"] = filters.get("company")

	if filters.get("status_scope") == "open":
		conditions.append("status not in ('Lost', 'Won', 'Closed')")

	return conditions, params, start, end


def _purchase_invoice_conditions(
	filters: dict[str, Any], default_period: str = "this_month"
) -> tuple[list[str], dict[str, Any], date, date]:
	start, end = _resolve_date_range(filters, default_period=default_period)
	conditions = [
		"docstatus = 1",
		"ifnull(is_return, 0) = 0",
		"posting_date between %(from_date)s and %(to_date)s",
	]
	params: dict[str, Any] = {"from_date": start, "to_date": end}

	if filters.get("company"):
		conditions.append("company = %(company)s")
		params["company"] = filters.get("company")

	if filters.get("supplier"):
		conditions.append("supplier = %(supplier)s")
		params["supplier"] = filters.get("supplier")

	if filters.get("supplier_group"):
		conditions.append("ifnull(supplier_group, '') = %(supplier_group)s")
		params["supplier_group"] = filters.get("supplier_group")

	return conditions, params, start, end


def _purchase_order_conditions(
	filters: dict[str, Any], default_period: str = "last_90_days"
) -> tuple[list[str], dict[str, Any], date, date]:
	start, end = _resolve_date_range(filters, default_period=default_period)
	conditions = [
		"docstatus = 1",
		"transaction_date between %(from_date)s and %(to_date)s",
		"status not in ('Closed', 'Completed', 'Cancelled')",
	]
	params: dict[str, Any] = {"from_date": start, "to_date": end}

	if filters.get("company"):
		conditions.append("company = %(company)s")
		params["company"] = filters.get("company")

	if filters.get("supplier"):
		conditions.append("supplier = %(supplier)s")
		params["supplier"] = filters.get("supplier")

	if filters.get("supplier_group"):
		conditions.append("ifnull(supplier_group, '') = %(supplier_group)s")
		params["supplier_group"] = filters.get("supplier_group")

	return conditions, params, start, end


def _month_label(value: date) -> str:
	return f"{FRENCH_MONTHS.get(value.month, value.month)} {value.year}"


def _iter_month_starts(start: date, end: date) -> list[date]:
	cursor = getdate(f"{start.year}-{start.month:02d}-01")
	last = getdate(f"{end.year}-{end.month:02d}-01")
	months = []
	while cursor <= last:
		months.append(cursor)
		cursor = getdate(add_to_date(cursor, months=1))
	return months


def sales_this_month_widget(filters=None, widget=None) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return {"value": 0, "label": _("Chiffre d'affaires facture"), "secondary_value": 0}

	filters = normalize_filters(filters, widget_name="SALES_THIS_MONTH")
	conditions, params, start, end = _sales_invoice_conditions(filters, default_period="this_month")
	row = frappe.db.sql(
		f"""
			select
				ifnull(sum(base_grand_total), 0) as amount,
				count(*) as invoice_count
			from `tabSales Invoice`
			where {' and '.join(conditions)}
		""",
		params,
		as_dict=True,
	)[0]

	currency = _default_currency(filters.get("company"))
	return {
		"value": flt(row.amount),
		"currency": currency,
		"label": _("Chiffre d'affaires facture"),
		"secondary_value": cint(row.invoice_count),
		"secondary_label": _("Factures soumises"),
		"context": _("Du {0} au {1}").format(start, end),
	}


def monthly_revenue_chart_widget(filters=None, widget=None) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return {
			"chart_type": "line",
			"labels": [],
			"datasets": [],
			"summary": {"value": 0, "label": _("Aucune facture"), "currency": _default_currency()},
		}

	filters = normalize_filters(filters, widget_name="MONTHLY_REVENUE_CHART")
	start, end = _resolve_date_range(filters, default_period="last_180_days")
	conditions, params, _range_start, _range_end = _sales_invoice_conditions(
		filters, default_period="last_180_days"
	)
	months = _iter_month_starts(start, end)
	month_map = {
		month.strftime("%Y-%m"): {"label": _month_label(month), "amount": 0.0, "count": 0}
		for month in months
	}

	rows = frappe.db.sql(
		f"""
			select
				date_format(posting_date, '%%Y-%%m') as month_key,
				ifnull(sum(base_grand_total), 0) as amount,
				count(*) as invoice_count
			from `tabSales Invoice`
			where {' and '.join(conditions)}
			group by date_format(posting_date, '%%Y-%%m')
			order by month_key asc
		""",
		params,
		as_dict=True,
	)

	for row in rows:
		if row.month_key in month_map:
			month_map[row.month_key]["amount"] = flt(row.amount)
			month_map[row.month_key]["count"] = cint(row.invoice_count)

	currency = _default_currency(filters.get("company"))
	labels = [month_map[key]["label"] for key in month_map]
	amounts = [month_map[key]["amount"] for key in month_map]
	counts = [month_map[key]["count"] for key in month_map]
	return {
		"chart_type": "line",
		"labels": labels,
		"datasets": [
			{"name": _("CA facture"), "values": amounts},
			{"name": _("Nombre de factures"), "values": counts},
		],
		"currency": currency,
		"summary": {
			"value": sum(amounts),
			"currency": currency,
			"label": _("Cumul de la periode"),
		},
	}


def top_customers_widget(filters=None, widget=None) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return {"columns": [], "rows": []}

	filters = normalize_filters(filters, widget_name="TOP_CUSTOMERS")
	conditions, params, start, end = _sales_invoice_conditions(filters, default_period="last_90_days")
	limit = max(min(cint(filters.get("limit") or 5), 20), 1)
	rows = frappe.db.sql(
		f"""
			select
				customer,
				count(*) as invoice_count,
				ifnull(sum(base_grand_total), 0) as amount
			from `tabSales Invoice`
			where {' and '.join(conditions)}
			group by customer
			order by amount desc
			limit {limit}
		""",
		params,
		as_dict=True,
	)

	currency = _default_currency(filters.get("company"))
	return {
		"columns": [
			{"key": "customer", "label": _("Client"), "type": "Data"},
			{"key": "invoice_count", "label": _("Factures"), "type": "Int"},
			{"key": "amount", "label": _("CA"), "type": "Currency", "currency": currency},
		],
		"rows": [
			{
				"customer": row.customer,
				"invoice_count": cint(row.invoice_count),
				"amount": flt(row.amount),
			}
			for row in rows
		],
		"context": _("Du {0} au {1}").format(start, end),
	}


def pipeline_health_widget(filters=None, widget=None) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "Opportunity"):
		return {"chart_type": "donut", "labels": [], "datasets": [], "summary": {"value": 0}}

	filters = normalize_filters(filters, widget_name="PIPELINE_HEALTH")
	conditions, params, start, end = _opportunity_conditions(filters)
	rows = frappe.db.sql(
		f"""
			select
				coalesce(nullif(status, ''), 'Sans statut') as status,
				count(*) as opportunity_count,
				ifnull(sum(opportunity_amount), 0) as amount
			from `tabOpportunity`
			where {' and '.join(conditions)}
			group by status
			order by opportunity_count desc, status asc
		""",
		params,
		as_dict=True,
	)

	currency = _default_currency(filters.get("company"))
	labels = [row.status for row in rows]
	counts = [cint(row.opportunity_count) for row in rows]
	total_amount = sum(flt(row.amount) for row in rows)
	return {
		"chart_type": "donut",
		"labels": labels,
		"datasets": [{"name": _("Opportunites"), "values": counts}],
		"currency": currency,
		"summary": {
			"value": total_amount,
			"currency": currency,
			"label": _("Montant potentiel"),
		},
		"context": _("Du {0} au {1}").format(start, end),
	}


def revenue_by_category_widget(filters=None, widget=None) -> dict[str, Any]:
	"""Bar chart: revenue by customer_group over selected period."""
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return {
			"chart_type": "bar",
			"labels": [],
			"datasets": [],
			"summary": {"value": 0, "label": _("Aucune facture"), "currency": _default_currency()},
		}

	filters = normalize_filters(filters, widget_name="REVENUE_BY_CATEGORY")
	conditions, params, start, end = _sales_invoice_conditions(filters, default_period="last_90_days")
	limit = max(min(cint(filters.get("limit") or 6), 12), 3)

	rows = frappe.db.sql(
		f"""
			select
				coalesce(nullif(customer_group, ''), 'Non classifie') as category,
				ifnull(sum(base_grand_total), 0) as amount
			from `tabSales Invoice`
			where {' and '.join(conditions)}
			group by category
			order by amount desc
			limit {limit}
		""",
		params,
		as_dict=True,
	)

	currency = _default_currency(filters.get("company"))
	labels = [row.category for row in rows]
	amounts = [flt(row.amount) for row in rows]
	return {
		"chart_type": "bar",
		"labels": labels,
		"datasets": [{"name": _("CA par groupe client"), "values": amounts}],
		"currency": currency,
		"summary": {
			"value": sum(amounts),
			"currency": currency,
			"label": _("CA total sur la periode"),
		},
		"context": _("Du {0} au {1}").format(start, end),
	}


def buying_spend_this_month_widget(filters=None, widget=None) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "Purchase Invoice"):
		return {"value": 0, "label": _("Achats factures"), "secondary_value": 0}

	filters = normalize_filters(filters, widget_name="BUYING_SPEND_THIS_MONTH")
	conditions, params, start, end = _purchase_invoice_conditions(filters, default_period="this_month")
	row = frappe.db.sql(
		f"""
			select
				ifnull(sum(base_grand_total), 0) as amount,
				count(*) as invoice_count
			from `tabPurchase Invoice`
			where {' and '.join(conditions)}
		""",
		params,
		as_dict=True,
	)[0]

	currency = _default_currency(filters.get("company"))
	return {
		"value": flt(row.amount),
		"currency": currency,
		"label": _("Achats factures"),
		"secondary_value": cint(row.invoice_count),
		"secondary_label": _("Factures achat"),
		"context": _("Du {0} au {1}").format(start, end),
	}


def buying_monthly_spend_widget(filters=None, widget=None) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "Purchase Invoice"):
		return {
			"chart_type": "line",
			"labels": [],
			"datasets": [],
			"summary": {"value": 0, "label": _("Aucune facture achat"), "currency": _default_currency()},
		}

	filters = normalize_filters(filters, widget_name="BUYING_MONTHLY_SPEND")
	start, end = _resolve_date_range(filters, default_period="last_180_days")
	conditions, params, _range_start, _range_end = _purchase_invoice_conditions(
		filters, default_period="last_180_days"
	)
	months = _iter_month_starts(start, end)
	month_map = {
		month.strftime("%Y-%m"): {"label": _month_label(month), "amount": 0.0, "count": 0}
		for month in months
	}

	rows = frappe.db.sql(
		f"""
			select
				date_format(posting_date, '%%Y-%%m') as month_key,
				ifnull(sum(base_grand_total), 0) as amount,
				count(*) as invoice_count
			from `tabPurchase Invoice`
			where {' and '.join(conditions)}
			group by date_format(posting_date, '%%Y-%%m')
			order by month_key asc
		""",
		params,
		as_dict=True,
	)

	for row in rows:
		if row.month_key in month_map:
			month_map[row.month_key]["amount"] = flt(row.amount)
			month_map[row.month_key]["count"] = cint(row.invoice_count)

	currency = _default_currency(filters.get("company"))
	labels = [month_map[key]["label"] for key in month_map]
	amounts = [month_map[key]["amount"] for key in month_map]
	counts = [month_map[key]["count"] for key in month_map]
	return {
		"chart_type": "line",
		"labels": labels,
		"datasets": [
			{"name": _("Achats factures"), "values": amounts},
			{"name": _("Nombre de factures"), "values": counts},
		],
		"currency": currency,
		"summary": {
			"value": sum(amounts),
			"currency": currency,
			"label": _("Cumul de la periode"),
		},
	}


def buying_top_suppliers_widget(filters=None, widget=None) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "Purchase Invoice"):
		return {"columns": [], "rows": []}

	filters = normalize_filters(filters, widget_name="BUYING_TOP_SUPPLIERS")
	conditions, params, start, end = _purchase_invoice_conditions(filters, default_period="last_90_days")
	limit = max(min(cint(filters.get("limit") or 5), 20), 1)
	rows = frappe.db.sql(
		f"""
			select
				supplier,
				count(*) as invoice_count,
				ifnull(sum(base_grand_total), 0) as amount
			from `tabPurchase Invoice`
			where {' and '.join(conditions)}
			group by supplier
			order by amount desc
			limit {limit}
		""",
		params,
		as_dict=True,
	)

	currency = _default_currency(filters.get("company"))
	return {
		"columns": [
			{"key": "supplier", "label": _("Fournisseur"), "type": "Data"},
			{"key": "invoice_count", "label": _("Factures"), "type": "Int"},
			{"key": "amount", "label": _("Achats"), "type": "Currency", "currency": currency},
		],
		"rows": [
			{
				"supplier": row.supplier,
				"invoice_count": cint(row.invoice_count),
				"amount": flt(row.amount),
			}
			for row in rows
		],
		"context": _("Du {0} au {1}").format(start, end),
	}


def buying_open_purchase_orders_widget(filters=None, widget=None) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "Purchase Order"):
		return {"value": 0, "label": _("Commandes achat ouvertes"), "secondary_value": 0}

	filters = normalize_filters(filters, widget_name="BUYING_OPEN_PURCHASE_ORDERS")
	conditions, params, start, end = _purchase_order_conditions(filters, default_period="last_90_days")
	row = frappe.db.sql(
		f"""
			select
				count(*) as order_count,
				ifnull(sum(base_grand_total), 0) as open_amount
			from `tabPurchase Order`
			where {' and '.join(conditions)}
		""",
		params,
		as_dict=True,
	)[0]

	currency = _default_currency(filters.get("company"))
	return {
		"value": flt(row.open_amount),
		"currency": currency,
		"label": _("Montant commandes ouvertes"),
		"secondary_value": cint(row.order_count),
		"secondary_label": _("Commandes ouvertes"),
		"context": _("Du {0} au {1}").format(start, end),
	}


def _stock_scope_conditions(
	filters: dict[str, Any],
	stock_alias: str,
	item_alias: str = "item",
	warehouse_alias: str = "warehouse",
) -> tuple[list[str], dict[str, Any]]:
	conditions: list[str] = []
	params: dict[str, Any] = {}

	if filters.get("company"):
		conditions.append(f"ifnull({warehouse_alias}.company, '') = %(company)s")
		params["company"] = filters.get("company")

	if filters.get("warehouse"):
		conditions.append(f"{stock_alias}.warehouse = %(warehouse)s")
		params["warehouse"] = filters.get("warehouse")

	if filters.get("item_group"):
		conditions.append(f"ifnull({item_alias}.item_group, '') = %(item_group)s")
		params["item_group"] = filters.get("item_group")

	return conditions, params


def _stock_limit(
	filters: dict[str, Any], default_limit: int = 6, minimum: int = 3, maximum: int = 12
) -> int:
	return max(min(cint(filters.get("limit") or default_limit), maximum), minimum)


def stock_turnover_widget(filters=None, widget=None) -> dict[str, Any]:
	"""Rotation stock = valeur de sortie sur la periode / valeur actuelle du stock."""
	if not frappe.db.exists("DocType", "Stock Ledger Entry") or not frappe.db.exists("DocType", "Bin"):
		return {
			"value": 0,
			"label": _("Rotation stock"),
			"secondary_value": 0,
			"secondary_label": _("valeur sortie"),
		}

	filters = normalize_filters(filters, widget_name="STOCK_TURNOVER")
	start, end = _resolve_date_range(filters, default_period="last_90_days")
	movement_conditions, movement_params = _stock_scope_conditions(filters, stock_alias="sle")
	movement_params.update({"from_date": start, "to_date": end})

	outflow_row = frappe.db.sql(
		f"""
			select
				abs(
					ifnull(
						sum(case when sle.stock_value_difference < 0 then sle.stock_value_difference else 0 end),
						0
					)
				) as outflow_value
			from `tabStock Ledger Entry` sle
			left join `tabItem` item on item.name = sle.item_code
			left join `tabWarehouse` warehouse on warehouse.name = sle.warehouse
			where {' and '.join([
				"sle.is_cancelled = 0",
				"sle.posting_date between %(from_date)s and %(to_date)s",
				"sle.actual_qty < 0",
				"ifnull(item.disabled, 0) = 0",
				*movement_conditions,
			])}
		""",
		movement_params,
		as_dict=True,
	)[0]

	snapshot_conditions, snapshot_params = _stock_scope_conditions(filters, stock_alias="bin")
	stock_row = frappe.db.sql(
		f"""
			select ifnull(sum(bin.stock_value), 0) as stock_value
			from `tabBin` bin
			left join `tabItem` item on item.name = bin.item_code
			left join `tabWarehouse` warehouse on warehouse.name = bin.warehouse
			where {' and '.join([
				"bin.actual_qty > 0",
				"ifnull(item.disabled, 0) = 0",
				*snapshot_conditions,
			])}
		""",
		snapshot_params,
		as_dict=True,
	)[0]
	outflow_value = flt(outflow_row.outflow_value)
	stock_value = flt(stock_row.stock_value)

	ratio = (outflow_value / stock_value) if stock_value else 0
	return {
		"value": round(ratio, 2),
		"label": _("Rotation stock"),
		"secondary_value": round(outflow_value, 0),
		"secondary_label": _("valeur sortie"),
		"context": _("Du {0} au {1}").format(start, end),
	}


def dormant_stock_widget(filters=None, widget=None) -> dict[str, Any]:
	"""Articles en stock sans mouvement sur la periode selectionnee."""
	if not (
		frappe.db.exists("DocType", "Bin")
		and frappe.db.exists("DocType", "Item")
		and frappe.db.exists("DocType", "Stock Ledger Entry")
	):
		return {
			"value": 0,
			"label": _("Stock dormant"),
			"secondary_value": 0,
			"secondary_label": _("articles"),
		}

	filters = normalize_filters(filters, widget_name="DORMANT_STOCK")
	start, end = _resolve_date_range(filters, default_period="last_90_days")

	snapshot_conditions, snapshot_params = _stock_scope_conditions(filters, stock_alias="bin")
	snapshot_params.update({"from_date": start, "to_date": end})
	row = frappe.db.sql(
		f"""
			select
				ifnull(sum(bin.stock_value), 0) as dormant_value,
				count(distinct bin.item_code) as dormant_items
			from `tabBin` bin
			left join `tabItem` item on item.name = bin.item_code
			left join `tabWarehouse` warehouse on warehouse.name = bin.warehouse
			where {' and '.join([
				"bin.actual_qty > 0",
				"ifnull(item.disabled, 0) = 0",
				*snapshot_conditions,
				"""not exists (
					select 1
					from `tabStock Ledger Entry` sle
					where sle.item_code = bin.item_code
						and sle.warehouse = bin.warehouse
						and sle.is_cancelled = 0
						and sle.posting_date between %(from_date)s and %(to_date)s
						and abs(sle.actual_qty) > 0
				)""",
			])}
		""",
		snapshot_params,
		as_dict=True,
	)[0]

	return {
		"value": flt(row.dormant_value),
		"currency": _default_currency(filters.get("company")),
		"label": _("Stock dormant"),
		"secondary_value": cint(row.dormant_items),
		"secondary_label": _("articles sans mouvement"),
		"context": _("Du {0} au {1}").format(start, end),
	}


def stock_age_profile_widget(filters=None, widget=None) -> dict[str, Any]:
	if not (
		frappe.db.exists("DocType", "Bin")
		and frappe.db.exists("DocType", "Item")
		and frappe.db.exists("DocType", "Stock Ledger Entry")
	):
		return {
			"chart_type": "donut",
			"labels": [],
			"datasets": [],
			"summary": {"value": 0, "label": _("Aucun stock"), "currency": _default_currency()},
		}

	filters = normalize_filters(filters, widget_name="STOCK_AGE_PROFILE")
	snapshot_conditions, snapshot_params = _stock_scope_conditions(filters, stock_alias="bin")
	snapshot_params["as_of_date"] = getdate(nowdate())

	rows = frappe.db.sql(
		f"""
			select
				case
					when datediff(%(as_of_date)s, coalesce(last_move.last_posting_date, %(as_of_date)s)) <= 30 then '0-30 j'
					when datediff(%(as_of_date)s, coalesce(last_move.last_posting_date, %(as_of_date)s)) <= 90 then '31-90 j'
					when datediff(%(as_of_date)s, coalesce(last_move.last_posting_date, %(as_of_date)s)) <= 180 then '91-180 j'
					else '180+ j'
				end as age_bucket,
				ifnull(sum(bin.stock_value), 0) as stock_value
			from `tabBin` bin
			left join `tabItem` item on item.name = bin.item_code
			left join `tabWarehouse` warehouse on warehouse.name = bin.warehouse
			left join (
				select
					item_code,
					warehouse,
					max(posting_date) as last_posting_date
				from `tabStock Ledger Entry`
				where is_cancelled = 0
				group by item_code, warehouse
			) last_move
				on last_move.item_code = bin.item_code
				and last_move.warehouse = bin.warehouse
			where {' and '.join([
				"bin.actual_qty > 0",
				"ifnull(item.disabled, 0) = 0",
				*snapshot_conditions,
			])}
			group by age_bucket
		""",
		snapshot_params,
		as_dict=True,
	)

	bucket_order = ["0-30 j", "31-90 j", "91-180 j", "180+ j"]
	bucket_map = {row.age_bucket: flt(row.stock_value) for row in rows}
	values = [bucket_map.get(bucket, 0) for bucket in bucket_order]
	currency = _default_currency(filters.get("company"))
	return {
		"chart_type": "donut",
		"labels": bucket_order,
		"datasets": [{"name": _("Valeur de stock"), "values": values}],
		"currency": currency,
		"summary": {
			"value": sum(values),
			"currency": currency,
			"label": _("Valeur stock actuelle"),
		},
		"context": _("Photo au {0}").format(getdate(nowdate())),
	}


def warehouse_stockout_risk_widget(filters=None, widget=None) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "Bin"):
		return {
			"chart_type": "bar",
			"labels": [],
			"datasets": [],
			"summary": {"value": 0, "label": _("Aucun risque detecte")},
		}

	filters = normalize_filters(filters, widget_name="WAREHOUSE_STOCKOUT_RISK")
	limit = _stock_limit(filters)
	snapshot_conditions, snapshot_params = _stock_scope_conditions(filters, stock_alias="bin")
	rows = frappe.db.sql(
		f"""
			select
				bin.warehouse,
				count(*) as sku_count,
				ifnull(sum(abs(bin.projected_qty)), 0) as shortage_qty
			from `tabBin` bin
			left join `tabItem` item on item.name = bin.item_code
			left join `tabWarehouse` warehouse on warehouse.name = bin.warehouse
			where {' and '.join([
				"bin.projected_qty < 0",
				"ifnull(item.disabled, 0) = 0",
				*snapshot_conditions,
			])}
			group by bin.warehouse
			order by shortage_qty desc, sku_count desc, bin.warehouse asc
			limit {limit}
		""",
		snapshot_params,
		as_dict=True,
	)

	labels = [row.warehouse for row in rows]
	shortages = [flt(row.shortage_qty) for row in rows]
	sku_counts = [cint(row.sku_count) for row in rows]
	return {
		"chart_type": "bar",
		"labels": labels,
		"datasets": [
			{"name": _("Qte en deficit"), "values": shortages},
			{"name": _("Articles exposes"), "values": sku_counts},
		],
		"summary": {
			"value": sum(shortages),
			"label": _("Qte totale en deficit"),
		},
		"context": _("Photo instantanee des bins en projection negative."),
	}


def monthly_stock_flow_widget(filters=None, widget=None) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "Stock Ledger Entry"):
		return {
			"chart_type": "line",
			"labels": [],
			"datasets": [],
			"summary": {"value": 0, "label": _("Aucun mouvement")},
		}

	filters = normalize_filters(filters, widget_name="MONTHLY_STOCK_FLOW")
	start, end = _resolve_date_range(filters, default_period="last_180_days")
	conditions, params = _stock_scope_conditions(filters, stock_alias="sle")
	params.update({"from_date": start, "to_date": end})

	months = _iter_month_starts(start, end)
	month_map = {
		month.strftime("%Y-%m"): {"label": _month_label(month), "inbound": 0.0, "outbound": 0.0}
		for month in months
	}
	rows = frappe.db.sql(
		f"""
			select
				date_format(sle.posting_date, '%%Y-%%m') as month_key,
				ifnull(sum(case when sle.actual_qty > 0 then sle.actual_qty else 0 end), 0) as inbound_qty,
				abs(ifnull(sum(case when sle.actual_qty < 0 then sle.actual_qty else 0 end), 0)) as outbound_qty
			from `tabStock Ledger Entry` sle
			left join `tabItem` item on item.name = sle.item_code
			left join `tabWarehouse` warehouse on warehouse.name = sle.warehouse
			where {' and '.join([
				"sle.is_cancelled = 0",
				"sle.posting_date between %(from_date)s and %(to_date)s",
				"sle.actual_qty <> 0",
				"ifnull(item.disabled, 0) = 0",
				*conditions,
			])}
			group by month_key
			order by month_key asc
		""",
		params,
		as_dict=True,
	)

	for row in rows:
		if row.month_key in month_map:
			month_map[row.month_key]["inbound"] = flt(row.inbound_qty)
			month_map[row.month_key]["outbound"] = flt(row.outbound_qty)

	labels = [month_map[key]["label"] for key in month_map]
	inbound = [month_map[key]["inbound"] for key in month_map]
	outbound = [month_map[key]["outbound"] for key in month_map]
	return {
		"chart_type": "line",
		"labels": labels,
		"datasets": [
			{"name": _("Entrees"), "values": inbound},
			{"name": _("Sorties"), "values": outbound},
		],
		"summary": {
			"value": sum(outbound),
			"label": _("Sorties cumulees"),
		},
		"context": _("Du {0} au {1}").format(start, end),
	}


def reservation_pressure_widget(filters=None, widget=None) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "Bin"):
		return {
			"chart_type": "bar",
			"labels": [],
			"datasets": [],
			"summary": {"value": 0, "label": _("Aucune reservation")},
		}

	filters = normalize_filters(filters, widget_name="RESERVATION_PRESSURE")
	limit = _stock_limit(filters)
	snapshot_conditions, snapshot_params = _stock_scope_conditions(filters, stock_alias="bin")
	rows = frappe.db.sql(
		f"""
			select
				bin.warehouse,
				ifnull(sum(bin.actual_qty), 0) as actual_qty,
				ifnull(sum(bin.reserved_qty), 0) as reserved_qty
			from `tabBin` bin
			left join `tabItem` item on item.name = bin.item_code
			left join `tabWarehouse` warehouse on warehouse.name = bin.warehouse
			where {' and '.join([
				"bin.actual_qty > 0",
				"ifnull(item.disabled, 0) = 0",
				*snapshot_conditions,
			])}
			group by bin.warehouse
			having ifnull(sum(bin.reserved_qty), 0) > 0
			order by
				(ifnull(sum(bin.reserved_qty), 0) / nullif(ifnull(sum(bin.actual_qty), 0), 0)) desc,
				ifnull(sum(bin.reserved_qty), 0) desc,
				bin.warehouse asc
			limit {limit}
		""",
		snapshot_params,
		as_dict=True,
	)

	labels = []
	ratios = []
	for row in rows:
		labels.append(row.warehouse)
		actual_qty = flt(row.actual_qty)
		reserved_qty = flt(row.reserved_qty)
		ratio = (reserved_qty / actual_qty * 100) if actual_qty else 0
		ratios.append(round(ratio, 1))

	average_ratio = (sum(ratios) / len(ratios)) if ratios else 0
	return {
		"chart_type": "bar",
		"labels": labels,
		"datasets": [{"name": _("Taux de reservation %"), "values": ratios}],
		"summary": {
			"value": round(average_ratio, 1),
			"label": _("Taux moyen de reservation"),
		},
		"context": _("Photo instantanee des quantites deja reservees."),
	}


def inventory_concentration_widget(filters=None, widget=None) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "Bin"):
		return {
			"chart_type": "donut",
			"labels": [],
			"datasets": [],
			"summary": {"value": 0, "label": _("Aucun stock"), "currency": _default_currency()},
		}

	filters = normalize_filters(filters, widget_name="INVENTORY_CONCENTRATION")
	snapshot_conditions, snapshot_params = _stock_scope_conditions(filters, stock_alias="bin")
	rows = frappe.db.sql(
		f"""
			select
				bin.item_code,
				ifnull(sum(bin.stock_value), 0) as stock_value
			from `tabBin` bin
			left join `tabItem` item on item.name = bin.item_code
			left join `tabWarehouse` warehouse on warehouse.name = bin.warehouse
			where {' and '.join([
				"bin.actual_qty > 0",
				"ifnull(item.disabled, 0) = 0",
				*snapshot_conditions,
			])}
			group by bin.item_code
			having ifnull(sum(bin.stock_value), 0) > 0
			order by stock_value desc, bin.item_code asc
		""",
		snapshot_params,
		as_dict=True,
	)

	currency = _default_currency(filters.get("company"))
	total_value = sum(flt(row.stock_value) for row in rows)
	if not total_value:
		return {
			"chart_type": "donut",
			"labels": [],
			"datasets": [],
			"summary": {"value": 0, "label": _("Aucun stock"), "currency": currency},
		}

	bucket_labels = ["Classe A", "Classe B", "Classe C"]
	bucket_totals = {label: 0.0 for label in bucket_labels}
	bucket_counts = {label: 0 for label in bucket_labels}
	running_total = 0.0
	for row in rows:
		value = flt(row.stock_value)
		running_total += value
		share = (running_total / total_value) * 100 if total_value else 0
		if share <= 80:
			bucket = "Classe A"
		elif share <= 95:
			bucket = "Classe B"
		else:
			bucket = "Classe C"
		bucket_totals[bucket] += value
		bucket_counts[bucket] += 1

	values = [bucket_totals[label] for label in bucket_labels]
	share_a = (bucket_totals["Classe A"] / total_value * 100) if total_value else 0
	return {
		"chart_type": "donut",
		"labels": bucket_labels,
		"datasets": [{"name": _("Valeur immobilisee"), "values": values}],
		"currency": currency,
		"summary": {
			"value": total_value,
			"currency": currency,
			"label": _("Valeur totale de stock"),
		},
		"context": _("{0} articles portent {1}% de la valeur.").format(
			bucket_counts["Classe A"], round(share_a, 1)
		),
	}


def payment_delay_widget(filters=None, widget=None) -> dict[str, Any]:
	"""Delai moyen de paiement = posting_date -> payment reference."""
	if not (
		frappe.db.exists("DocType", "Sales Invoice")
		and frappe.db.exists("DocType", "Payment Entry")
		and frappe.db.exists("DocType", "Payment Entry Reference")
	):
		return {
			"value": 0,
			"label": _("Delai moyen paiement"),
			"secondary_value": 0,
			"secondary_label": _("jours"),
		}

	filters = normalize_filters(filters, widget_name="PAYMENT_DELAY")
	start, end = _resolve_date_range(filters, default_period="last_90_days")

	row = frappe.db.sql(
		"""
			select
				ifnull(avg(datediff(pe.posting_date, si.posting_date)), 0) as avg_days,
				count(distinct si.name) as invoice_count
			from `tabPayment Entry Reference` per
			inner join `tabPayment Entry` pe on pe.name = per.parent
			inner join `tabSales Invoice` si on si.name = per.reference_name
			where per.reference_doctype = 'Sales Invoice'
			  and pe.docstatus = 1
			  and si.docstatus = 1
			  and si.posting_date between %(from_date)s and %(to_date)s
		""",
		{"from_date": start, "to_date": end},
		as_dict=True,
	)[0]

	return {
		"value": round(flt(row.avg_days), 1),
		"label": _("Delai moyen paiement"),
		"secondary_value": cint(row.invoice_count),
		"secondary_label": _("factures reglees"),
		"context": _("Du {0} au {1}").format(start, end),
	}


def at_risk_customers_widget(filters=None, widget=None) -> dict[str, Any]:
	"""Clients avec factures en retard."""
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return {
			"value": 0,
			"label": _("Clients a risque"),
			"secondary_value": 0,
			"secondary_label": _("factures"),
		}

	filters = normalize_filters(filters, widget_name="AT_RISK_CUSTOMERS")
	conditions, params, _range_start, _range_end = _sales_invoice_conditions(
		filters, include_overdue_only=True
	)

	row = frappe.db.sql(
		f"""
			select
				count(distinct customer) as customer_count,
				count(*) as invoice_count,
				ifnull(sum(outstanding_amount), 0) as outstanding
			from `tabSales Invoice`
			where {' and '.join(conditions)}
		""",
		params,
		as_dict=True,
	)[0]

	return {
		"value": cint(row.customer_count),
		"label": _("Clients a risque"),
		"secondary_value": flt(row.outstanding),
		"secondary_label": _("encours en retard"),
		"context": _("Arrete au {0}").format(getdate(nowdate())),
	}


def profitable_products_widget(filters=None, widget=None) -> dict[str, Any]:
	"""Top produits par marge estimee (selling - valuation) sur la periode."""
	if not frappe.db.exists("DocType", "Sales Invoice Item"):
		return {"columns": [], "rows": []}

	filters = normalize_filters(filters, widget_name="PROFITABLE_PRODUCTS")
	conditions, params, start, end = _sales_invoice_conditions(filters, default_period="last_90_days")
	limit = max(min(cint(filters.get("limit") or 5), 20), 1)

	rows = frappe.db.sql(
		f"""
			select
				sii.item_code,
				sii.item_name,
				ifnull(sum(sii.qty), 0) as qty_sold,
				ifnull(sum(sii.base_net_amount), 0) as revenue,
				ifnull(sum(sii.qty * ifnull(sii.incoming_rate, 0)), 0) as cost
			from `tabSales Invoice Item` sii
			where sii.parent in (
				select name from `tabSales Invoice`
				where {' and '.join(conditions)}
			)
			group by sii.item_code, sii.item_name
			order by (ifnull(sum(sii.base_net_amount), 0) - ifnull(sum(sii.qty * ifnull(sii.incoming_rate, 0)), 0)) desc
			limit {limit}
		""",
		params,
		as_dict=True,
	)

	currency = _default_currency(filters.get("company"))
	result_rows = []
	for row in rows:
		margin = flt(row.revenue) - flt(row.cost)
		margin_pct = (margin / row.revenue * 100) if row.revenue else 0
		result_rows.append(
			{
				"item_name": row.item_name or row.item_code,
				"qty_sold": cint(row.qty_sold),
				"revenue": flt(row.revenue),
				"margin": margin,
				"margin_pct": round(margin_pct, 1),
			}
		)

	return {
		"columns": [
			{"key": "item_name", "label": _("Produit"), "type": "Data"},
			{"key": "qty_sold", "label": _("Qte"), "type": "Int"},
			{"key": "revenue", "label": _("CA"), "type": "Currency", "currency": currency},
			{"key": "margin", "label": _("Marge"), "type": "Currency", "currency": currency},
			{"key": "margin_pct", "label": _("Marge %"), "type": "Data"},
		],
		"rows": result_rows,
		"context": _("Du {0} au {1}").format(start, end),
	}


def overdue_invoices_widget(filters=None, widget=None) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return {"value": 0, "label": _("Factures en retard"), "secondary_value": 0}

	filters = normalize_filters(filters, widget_name="OVERDUE_INVOICES")
	conditions, params, _range_start, _range_end = _sales_invoice_conditions(
		filters, include_overdue_only=True
	)
	row = frappe.db.sql(
		f"""
			select
				ifnull(sum(outstanding_amount), 0) as amount_due,
				count(*) as invoice_count
			from `tabSales Invoice`
			where {' and '.join(conditions)}
		""",
		params,
		as_dict=True,
	)[0]

	currency = _default_currency(filters.get("company"))
	return {
		"value": flt(row.amount_due),
		"currency": currency,
		"label": _("Montant en retard"),
		"secondary_value": cint(row.invoice_count),
		"secondary_label": _("Factures en retard"),
		"context": _("Arrete au {0}").format(getdate(nowdate())),
	}
