# accounting_api.py
# APIs comptables — v3 : Pagination V3 ajoutée (limit_start, limit_page_length, query_params)
# 24 intents : Factures vente + achat, paiements, rapports financiers

import frappe
from frappe.utils import nowdate, getdate, flt

def _get_company():
    return frappe.defaults.get_global_default('company') or 'Tunisian United Solutions (Demo)'

def _get_currency():
    return frappe.db.get_value('Company', _get_company(), 'default_currency') or 'TND'


def get_user_info():
    user = frappe.session.user
    full_name = frappe.db.get_value("User", user, "full_name") or user
    roles = frappe.get_roles(user)
    return {"user": user, "full_name": full_name, "roles": roles}


def _apply_date_filter(filters, from_date, to_date, field="posting_date"):
    if from_date and to_date:
        filters[field] = ["between", [from_date, to_date]]
    elif from_date:
        filters[field] = [">=", from_date]
    elif to_date:
        filters[field] = ["<=", to_date]


# ═══════════════════════════════════════════════════════════
#  FACTURES DE VENTE (Sales Invoice)
# ═══════════════════════════════════════════════════════════

def get_unpaid_sales_invoices(from_date=None, to_date=None, limit_start=0, limit_page_length=20, **kwargs):
    filters = {"company": _get_company(), "docstatus": 1, "outstanding_amount": [">", 0]}
    _apply_date_filter(filters, from_date, to_date)

    invoices = frappe.get_all("Sales Invoice", filters=filters,
        fields=["name", "customer", "customer_name", "posting_date",
                "due_date", "grand_total", "outstanding_amount", "status"],
        order_by="outstanding_amount DESC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total = sum(flt(i.outstanding_amount) for i in invoices)
    total_count = frappe.db.count("Sales Invoice", filters=filters)

    return {
        "data_type": "unpaid_sales_invoices",
        "invoices": invoices,
        "count": len(invoices),
        "total_outstanding": total,
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Sales Invoice",
            "filters": filters,
            "fields": ["name", "customer", "customer_name", "posting_date",
                       "due_date", "grand_total", "outstanding_amount", "status"],
            "order_by": "outstanding_amount DESC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "unpaid_sales_invoices",
            "currency": _get_currency(),
            "from_date": from_date,
            "to_date": to_date
        }
    }


def get_overdue_sales_invoices(from_date=None, to_date=None, limit_start=0, limit_page_length=20, **kwargs):
    today = nowdate()
    filters = {"company": _get_company(), "docstatus": 1,
               "outstanding_amount": [">", 0], "due_date": ["<", today]}
    _apply_date_filter(filters, from_date, to_date)

    invoices = frappe.get_all("Sales Invoice", filters=filters,
        fields=["name", "customer", "customer_name", "posting_date",
                "due_date", "grand_total", "outstanding_amount", "status"],
        order_by="due_date ASC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    today_date = getdate(today)
    for inv in invoices:
        inv["days_overdue"] = (today_date - getdate(inv.due_date)).days

    total = sum(flt(i.outstanding_amount) for i in invoices)
    total_count = frappe.db.count("Sales Invoice", filters=filters)

    return {
        "data_type": "overdue_sales_invoices",
        "invoices": invoices,
        "count": len(invoices),
        "total_overdue": total,
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Sales Invoice",
            "filters": filters,
            "fields": ["name", "customer", "customer_name", "posting_date",
                       "due_date", "grand_total", "outstanding_amount", "status"],
            "order_by": "due_date ASC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "overdue_sales_invoices",
            "currency": _get_currency(),
            "from_date": from_date,
            "to_date": to_date
        }
    }


def get_total_invoiced(from_date=None, to_date=None, limit_start=0, limit_page_length=20, **kwargs):
    filters = {"company": _get_company(), "docstatus": 1, "is_return": 0}
    _apply_date_filter(filters, from_date, to_date)

    invoices = frappe.get_all("Sales Invoice", filters=filters,
        fields=["name", "customer", "customer_name", "posting_date",
                "grand_total", "net_total", "total_taxes_and_charges",
                "outstanding_amount"],
        order_by="posting_date DESC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total_grand = sum(flt(i.grand_total) for i in invoices)
    total_net = sum(flt(i.net_total) for i in invoices)
    total_taxes = sum(flt(i.total_taxes_and_charges) for i in invoices)
    total_outstanding = sum(flt(i.outstanding_amount) for i in invoices)
    total_count = frappe.db.count("Sales Invoice", filters=filters)

    return {
        "data_type": "total_invoiced_period",
        "invoices": invoices,
        "count": len(invoices),
        "total_grand": total_grand,
        "total_net": total_net,
        "total_taxes": total_taxes,
        "total_outstanding": total_outstanding,
        "total_paid": total_grand - total_outstanding,
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Sales Invoice",
            "filters": filters,
            "fields": ["name", "customer", "customer_name", "posting_date",
                       "grand_total", "net_total", "total_taxes_and_charges", "outstanding_amount"],
            "order_by": "posting_date DESC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "total_invoiced_period",
            "currency": _get_currency(),
            "from_date": from_date,
            "to_date": to_date
        }
    }


def get_invoice_details(from_date=None, to_date=None, entity=None, **kwargs):
    if not entity:
        return {"data_type": "invoice_details", "error": "no_invoice_number",
                "message": "Aucun numéro de facture spécifié.",
                "currency": _get_currency(), "company": _get_company()}
    try:
        doc = frappe.get_doc("Sales Invoice", entity)
        items = []
        for item in doc.items:
            items.append({
                "item_name": item.item_name,
                "qty": item.qty,
                "rate": flt(item.rate),
                "amount": flt(item.amount)
            })
        return {"data_type": "invoice_details", "invoice_type": "Sales Invoice",
                "name": doc.name, "customer": doc.customer_name or doc.customer,
                "posting_date": str(doc.posting_date),
                "due_date": str(doc.due_date) if doc.due_date else "N/A",
                "grand_total": flt(doc.grand_total),
                "net_total": flt(doc.net_total),
                "total_taxes": flt(doc.total_taxes_and_charges),
                "outstanding_amount": flt(doc.outstanding_amount),
                "paid_amount": flt(doc.grand_total) - flt(doc.outstanding_amount),
                "status": doc.status, "items": items,
                "currency": _get_currency(), "company": _get_company()}
    except frappe.DoesNotExistError:
        try:
            doc = frappe.get_doc("Purchase Invoice", entity)
            items = []
            for item in doc.items:
                items.append({
                    "item_name": item.item_name,
                    "qty": item.qty,
                    "rate": flt(item.rate),
                    "amount": flt(item.amount)
                })
            return {"data_type": "invoice_details",
                    "invoice_type": "Purchase Invoice",
                    "name": doc.name,
                    "supplier": doc.supplier_name or doc.supplier,
                    "posting_date": str(doc.posting_date),
                    "due_date": str(doc.due_date) if doc.due_date else "N/A",
                    "grand_total": flt(doc.grand_total),
                    "net_total": flt(doc.net_total),
                    "total_taxes": flt(doc.total_taxes_and_charges),
                    "outstanding_amount": flt(doc.outstanding_amount),
                    "paid_amount": flt(doc.grand_total) - flt(doc.outstanding_amount),
                    "status": doc.status, "items": items,
                    "currency": _get_currency(), "company": _get_company()}
        except frappe.DoesNotExistError:
            return {"data_type": "invoice_details", "error": "not_found",
                    "message": f"Facture '{entity}' introuvable.",
                    "currency": _get_currency(), "company": _get_company()}


def get_customer_invoices(from_date=None, to_date=None, entity=None,
                          limit_start=0, limit_page_length=20, **kwargs):
    if not entity:
        return {"data_type": "customer_invoices", "error": "no_customer",
                "message": "Aucun nom de client spécifié.",
                "currency": _get_currency(), "company": _get_company()}

    customers = frappe.get_all("Customer",
        filters={"customer_name": ["like", f"%{entity}%"]},
        fields=["name", "customer_name"], limit_page_length=5)

    if not customers:
        suppliers = frappe.get_all("Supplier",
            filters={"supplier_name": ["like", f"%{entity}%"]},
            fields=["name", "supplier_name"], limit_page_length=5)
        if suppliers:
            return get_supplier_invoices(from_date=from_date, to_date=to_date, entity=entity,
                                         limit_start=limit_start, limit_page_length=limit_page_length)
        return {"data_type": "customer_invoices", "error": "customer_not_found",
                "message": f"'{entity}' introuvable dans les clients ni les fournisseurs.",
                "currency": _get_currency(), "company": _get_company()}

    customer_name = customers[0].name
    filters = {"company": _get_company(), "docstatus": 1, "customer": customer_name}
    _apply_date_filter(filters, from_date, to_date)

    invoices = frappe.get_all("Sales Invoice", filters=filters,
        fields=["name", "customer_name", "posting_date", "due_date",
                "grand_total", "outstanding_amount", "status"],
        order_by="posting_date DESC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total = sum(flt(i.grand_total) for i in invoices)
    outstanding = sum(flt(i.outstanding_amount) for i in invoices)
    total_count = frappe.db.count("Sales Invoice", filters=filters)

    return {
        "data_type": "customer_invoices",
        "customer": customers[0].customer_name,
        "invoices": invoices,
        "count": len(invoices),
        "total_invoiced": total,
        "total_outstanding": outstanding,
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Sales Invoice",
            "filters": filters,
            "fields": ["name", "customer_name", "posting_date", "due_date",
                       "grand_total", "outstanding_amount", "status"],
            "order_by": "posting_date DESC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "customer_invoices",
            "currency": _get_currency(),
            "customer": customers[0].customer_name,
            "from_date": from_date,
            "to_date": to_date
        }
    }


def get_draft_invoices(from_date=None, to_date=None, limit_start=0, limit_page_length=20, **kwargs):
    filters = {"company": _get_company(), "docstatus": 0}
    _apply_date_filter(filters, from_date, to_date)

    sales = frappe.get_all("Sales Invoice", filters=filters,
        fields=["name", "customer", "customer_name", "posting_date",
                "grand_total", "status"],
        order_by="posting_date DESC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    purchases = frappe.get_all("Purchase Invoice",
        filters={"company": _get_company(), "docstatus": 0},
        fields=["name", "supplier", "supplier_name", "posting_date",
                "grand_total", "status"],
        order_by="posting_date DESC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total_sales_count = frappe.db.count("Sales Invoice", filters=filters)
    total_purchase_count = frappe.db.count("Purchase Invoice", filters={"company": _get_company(), "docstatus": 0})

    return {
        "data_type": "draft_invoices",
        "sales_drafts": sales,
        "sales_count": len(sales),
        "purchase_drafts": purchases,
        "purchase_count": len(purchases),
        "total_sales_draft": sum(flt(i.grand_total) for i in sales),
        "total_purchase_draft": sum(flt(i.grand_total) for i in purchases),
        "currency": _get_currency(),
        "company": _get_company(),
        "query_params_sales": {
            "doctype": "Sales Invoice",
            "filters": filters,
            "fields": ["name", "customer", "customer_name", "posting_date", "grand_total", "status"],
            "order_by": "posting_date DESC",
            "page_size": limit_page_length,
            "total_count": total_sales_count,
            "data_type": "draft_invoices_sales"
        },
        "query_params_purchase": {
            "doctype": "Purchase Invoice",
            "filters": {"company": _get_company(), "docstatus": 0},
            "fields": ["name", "supplier", "supplier_name", "posting_date", "grand_total", "status"],
            "order_by": "posting_date DESC",
            "page_size": limit_page_length,
            "total_count": total_purchase_count,
            "data_type": "draft_invoices_purchase"
        }
    }


def get_top_debtors(from_date=None, to_date=None, limit_start=0, limit_page_length=20, **kwargs):
    invoices = frappe.get_all("Sales Invoice",
        filters={"company": _get_company(), "docstatus": 1,
                 "outstanding_amount": [">", 0]},
        fields=["customer", "customer_name", "outstanding_amount"],
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    customer_debt = {}
    for inv in invoices:
        cust = inv.customer_name or inv.customer
        if cust not in customer_debt:
            customer_debt[cust] = {"customer": cust, "total_outstanding": 0,
                                    "invoice_count": 0}
        customer_debt[cust]["total_outstanding"] += flt(inv.outstanding_amount)
        customer_debt[cust]["invoice_count"] += 1

    debtors = sorted(customer_debt.values(),
                     key=lambda x: x["total_outstanding"], reverse=True)
    total = sum(d["total_outstanding"] for d in debtors)
    total_count = len(customer_debt)

    return {
        "data_type": "top_debtors",
        "debtors": debtors[:limit_page_length],
        "count": len(debtors),
        "total_debt": total,
        "currency": _get_currency(),
        "company": _get_company(),
        "query_params": {
            "doctype": "Sales Invoice",
            "filters": {"company": _get_company(), "docstatus": 1, "outstanding_amount": [">", 0]},
            "fields": ["customer", "customer_name", "outstanding_amount"],
            "group_by": "customer",
            "order_by": "total_outstanding DESC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "top_debtors",
            "currency": _get_currency()
        }
    }


def get_recent_invoices(from_date=None, to_date=None, limit_start=0, limit_page_length=20, **kwargs):
    sales = frappe.get_all("Sales Invoice",
        filters={"company": _get_company(), "docstatus": 1},
        fields=["name", "customer", "customer_name", "posting_date",
                "grand_total", "outstanding_amount", "status"],
        order_by="creation DESC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    purchases = frappe.get_all("Purchase Invoice",
        filters={"company": _get_company(), "docstatus": 1},
        fields=["name", "supplier", "supplier_name", "posting_date",
                "grand_total", "outstanding_amount", "status"],
        order_by="creation DESC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total_sales_count = frappe.db.count("Sales Invoice", filters={"company": _get_company(), "docstatus": 1})
    total_purchase_count = frappe.db.count("Purchase Invoice", filters={"company": _get_company(), "docstatus": 1})

    return {
        "data_type": "recent_invoices",
        "sales_invoices": sales,
        "sales_count": len(sales),
        "purchase_invoices": purchases,
        "purchase_count": len(purchases),
        "currency": _get_currency(),
        "company": _get_company(),
        "query_params_sales": {
            "doctype": "Sales Invoice",
            "filters": {"company": _get_company(), "docstatus": 1},
            "fields": ["name", "customer", "customer_name", "posting_date", "grand_total", "outstanding_amount", "status"],
            "order_by": "creation DESC",
            "page_size": limit_page_length,
            "total_count": total_sales_count,
            "data_type": "recent_invoices_sales"
        },
        "query_params_purchase": {
            "doctype": "Purchase Invoice",
            "filters": {"company": _get_company(), "docstatus": 1},
            "fields": ["name", "supplier", "supplier_name", "posting_date", "grand_total", "outstanding_amount", "status"],
            "order_by": "creation DESC",
            "page_size": limit_page_length,
            "total_count": total_purchase_count,
            "data_type": "recent_invoices_purchase"
        }
    }


# ═══════════════════════════════════════════════════════════
#  FACTURES D'ACHAT (Purchase Invoice)
# ═══════════════════════════════════════════════════════════

def get_unpaid_purchase_invoices(from_date=None, to_date=None, limit_start=0, limit_page_length=20, **kwargs):
    filters = {"company": _get_company(), "docstatus": 1, "outstanding_amount": [">", 0]}
    _apply_date_filter(filters, from_date, to_date)

    invoices = frappe.get_all("Purchase Invoice", filters=filters,
        fields=["name", "supplier", "supplier_name", "posting_date",
                "due_date", "grand_total", "outstanding_amount", "status"],
        order_by="outstanding_amount DESC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total = sum(flt(i.outstanding_amount) for i in invoices)
    total_count = frappe.db.count("Purchase Invoice", filters=filters)

    return {
        "data_type": "unpaid_purchase_invoices",
        "invoices": invoices,
        "count": len(invoices),
        "total_outstanding": total,
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Purchase Invoice",
            "filters": filters,
            "fields": ["name", "supplier", "supplier_name", "posting_date",
                       "due_date", "grand_total", "outstanding_amount", "status"],
            "order_by": "outstanding_amount DESC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "unpaid_purchase_invoices",
            "currency": _get_currency(),
            "from_date": from_date,
            "to_date": to_date
        }
    }


def get_overdue_purchase_invoices(from_date=None, to_date=None, limit_start=0, limit_page_length=20, **kwargs):
    today = nowdate()
    filters = {"company": _get_company(), "docstatus": 1,
               "outstanding_amount": [">", 0], "due_date": ["<", today]}
    _apply_date_filter(filters, from_date, to_date)

    invoices = frappe.get_all("Purchase Invoice", filters=filters,
        fields=["name", "supplier", "supplier_name", "posting_date",
                "due_date", "grand_total", "outstanding_amount", "status"],
        order_by="due_date ASC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    today_date = getdate(today)
    for inv in invoices:
        inv["days_overdue"] = (today_date - getdate(inv.due_date)).days

    total = sum(flt(i.outstanding_amount) for i in invoices)
    total_count = frappe.db.count("Purchase Invoice", filters=filters)

    return {
        "data_type": "overdue_purchase_invoices",
        "invoices": invoices,
        "count": len(invoices),
        "total_overdue": total,
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Purchase Invoice",
            "filters": filters,
            "fields": ["name", "supplier", "supplier_name", "posting_date",
                       "due_date", "grand_total", "outstanding_amount", "status"],
            "order_by": "due_date ASC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "overdue_purchase_invoices",
            "currency": _get_currency(),
            "from_date": from_date,
            "to_date": to_date
        }
    }


def get_supplier_invoices(from_date=None, to_date=None, entity=None,
                          limit_start=0, limit_page_length=20, **kwargs):
    if not entity:
        return {"data_type": "supplier_invoices", "error": "no_supplier",
                "message": "Aucun nom de fournisseur spécifié.",
                "currency": _get_currency(), "company": _get_company()}

    suppliers = frappe.get_all("Supplier",
        filters={"supplier_name": ["like", f"%{entity}%"]},
        fields=["name", "supplier_name"], limit_page_length=5)

    if not suppliers:
        customers = frappe.get_all("Customer",
            filters={"customer_name": ["like", f"%{entity}%"]},
            fields=["name", "customer_name"], limit_page_length=5)
        if customers:
            return get_customer_invoices(from_date=from_date, to_date=to_date, entity=entity,
                                         limit_start=limit_start, limit_page_length=limit_page_length)
        return {"data_type": "supplier_invoices", "error": "supplier_not_found",
                "message": f"'{entity}' introuvable dans les fournisseurs ni les clients.",
                "currency": _get_currency(), "company": _get_company()}

    supplier_name = suppliers[0].name
    filters = {"company": _get_company(), "docstatus": 1, "supplier": supplier_name}
    _apply_date_filter(filters, from_date, to_date)

    invoices = frappe.get_all("Purchase Invoice", filters=filters,
        fields=["name", "supplier_name", "posting_date", "due_date",
                "grand_total", "outstanding_amount", "status"],
        order_by="posting_date DESC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total = sum(flt(i.grand_total) for i in invoices)
    outstanding = sum(flt(i.outstanding_amount) for i in invoices)
    total_count = frappe.db.count("Purchase Invoice", filters=filters)

    return {
        "data_type": "supplier_invoices",
        "supplier": suppliers[0].supplier_name,
        "invoices": invoices,
        "count": len(invoices),
        "total_invoiced": total,
        "total_outstanding": outstanding,
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Purchase Invoice",
            "filters": filters,
            "fields": ["name", "supplier_name", "posting_date", "due_date",
                       "grand_total", "outstanding_amount", "status"],
            "order_by": "posting_date DESC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "supplier_invoices",
            "currency": _get_currency(),
            "supplier": suppliers[0].supplier_name,
            "from_date": from_date,
            "to_date": to_date
        }
    }


def get_total_purchased(from_date=None, to_date=None, limit_start=0, limit_page_length=20, **kwargs):
    filters = {"company": _get_company(), "docstatus": 1, "is_return": 0}
    _apply_date_filter(filters, from_date, to_date)

    invoices = frappe.get_all("Purchase Invoice", filters=filters,
        fields=["name", "supplier", "supplier_name", "posting_date",
                "grand_total", "net_total", "total_taxes_and_charges",
                "outstanding_amount"],
        order_by="posting_date DESC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total_grand = sum(flt(i.grand_total) for i in invoices)
    total_net = sum(flt(i.net_total) for i in invoices)
    total_taxes = sum(flt(i.total_taxes_and_charges) for i in invoices)
    total_outstanding = sum(flt(i.outstanding_amount) for i in invoices)
    total_count = frappe.db.count("Purchase Invoice", filters=filters)

    return {
        "data_type": "total_purchased_period",
        "invoices": invoices,
        "count": len(invoices),
        "total_grand": total_grand,
        "total_net": total_net,
        "total_taxes": total_taxes,
        "total_outstanding": total_outstanding,
        "total_paid": total_grand - total_outstanding,
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Purchase Invoice",
            "filters": filters,
            "fields": ["name", "supplier", "supplier_name", "posting_date",
                       "grand_total", "net_total", "total_taxes_and_charges", "outstanding_amount"],
            "order_by": "posting_date DESC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "total_purchased_period",
            "currency": _get_currency(),
            "from_date": from_date,
            "to_date": to_date
        }
    }


def get_top_creditors(from_date=None, to_date=None, limit_start=0, limit_page_length=20, **kwargs):
    invoices = frappe.get_all("Purchase Invoice",
        filters={"company": _get_company(), "docstatus": 1,
                 "outstanding_amount": [">", 0]},
        fields=["supplier", "supplier_name", "outstanding_amount"],
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    supplier_debt = {}
    for inv in invoices:
        sup = inv.supplier_name or inv.supplier
        if sup not in supplier_debt:
            supplier_debt[sup] = {"supplier": sup, "total_outstanding": 0,
                                   "invoice_count": 0}
        supplier_debt[sup]["total_outstanding"] += flt(inv.outstanding_amount)
        supplier_debt[sup]["invoice_count"] += 1

    creditors = sorted(supplier_debt.values(),
                       key=lambda x: x["total_outstanding"], reverse=True)
    total = sum(c["total_outstanding"] for c in creditors)
    total_count = len(supplier_debt)

    return {
        "data_type": "top_creditors",
        "creditors": creditors[:limit_page_length],
        "count": len(creditors),
        "total_debt": total,
        "currency": _get_currency(),
        "company": _get_company(),
        "query_params": {
            "doctype": "Purchase Invoice",
            "filters": {"company": _get_company(), "docstatus": 1, "outstanding_amount": [">", 0]},
            "fields": ["supplier", "supplier_name", "outstanding_amount"],
            "group_by": "supplier",
            "order_by": "total_outstanding DESC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "top_creditors",
            "currency": _get_currency()
        }
    }


# ═══════════════════════════════════════════════════════════
#  PAIEMENTS (Payment Entry)
# ═══════════════════════════════════════════════════════════

def get_recent_payments(from_date=None, to_date=None, limit_start=0, limit_page_length=20, **kwargs):
    filters = {"company": _get_company(), "docstatus": 1}
    _apply_date_filter(filters, from_date, to_date)

    payments = frappe.get_all("Payment Entry", filters=filters,
        fields=["name", "payment_type", "posting_date", "party_type",
                "party", "party_name", "paid_amount", "mode_of_payment",
                "reference_no", "status"],
        order_by="posting_date DESC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total_received = sum(flt(p.paid_amount) for p in payments
                         if p.payment_type == "Receive")
    total_paid = sum(flt(p.paid_amount) for p in payments
                     if p.payment_type == "Pay")
    total_count = frappe.db.count("Payment Entry", filters=filters)

    return {
        "data_type": "recent_payments",
        "payments": payments,
        "count": len(payments),
        "total_received": total_received,
        "total_paid": total_paid,
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Payment Entry",
            "filters": filters,
            "fields": ["name", "payment_type", "posting_date", "party_type",
                       "party", "party_name", "paid_amount", "mode_of_payment",
                       "reference_no", "status"],
            "order_by": "posting_date DESC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "recent_payments",
            "currency": _get_currency(),
            "from_date": from_date,
            "to_date": to_date
        }
    }


def get_received_payments(from_date=None, to_date=None, limit_start=0, limit_page_length=20, **kwargs):
    filters = {"company": _get_company(), "docstatus": 1, "payment_type": "Receive"}
    _apply_date_filter(filters, from_date, to_date)

    payments = frappe.get_all("Payment Entry", filters=filters,
        fields=["name", "posting_date", "party_type", "party", "party_name",
                "paid_amount", "mode_of_payment", "reference_no"],
        order_by="posting_date DESC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total = sum(flt(p.paid_amount) for p in payments)
    total_count = frappe.db.count("Payment Entry", filters=filters)

    return {
        "data_type": "received_payments_period",
        "payments": payments,
        "count": len(payments),
        "total_received": total,
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Payment Entry",
            "filters": filters,
            "fields": ["name", "posting_date", "party_type", "party", "party_name",
                       "paid_amount", "mode_of_payment", "reference_no"],
            "order_by": "posting_date DESC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "received_payments_period",
            "currency": _get_currency(),
            "from_date": from_date,
            "to_date": to_date
        }
    }


def get_paid_payments(from_date=None, to_date=None, limit_start=0, limit_page_length=20, **kwargs):
    filters = {"company": _get_company(), "docstatus": 1, "payment_type": "Pay"}
    _apply_date_filter(filters, from_date, to_date)

    payments = frappe.get_all("Payment Entry", filters=filters,
        fields=["name", "posting_date", "party_type", "party", "party_name",
                "paid_amount", "mode_of_payment", "reference_no"],
        order_by="posting_date DESC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total = sum(flt(p.paid_amount) for p in payments)
    total_count = frappe.db.count("Payment Entry", filters=filters)

    return {
        "data_type": "paid_payments_period",
        "payments": payments,
        "count": len(payments),
        "total_paid": total,
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Payment Entry",
            "filters": filters,
            "fields": ["name", "posting_date", "party_type", "party", "party_name",
                       "paid_amount", "mode_of_payment", "reference_no"],
            "order_by": "posting_date DESC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "paid_payments_period",
            "currency": _get_currency(),
            "from_date": from_date,
            "to_date": to_date
        }
    }


def get_customer_payments(from_date=None, to_date=None, entity=None,
                          limit_start=0, limit_page_length=20, **kwargs):
    if not entity:
        return {"data_type": "customer_payments", "error": "no_party",
                "message": "Aucun nom de client ou fournisseur spécifié.",
                "currency": _get_currency(), "company": _get_company()}

    customers = frappe.get_all("Customer",
        filters={"customer_name": ["like", f"%{entity}%"]},
        fields=["name", "customer_name"], limit_page_length=3)
    suppliers = frappe.get_all("Supplier",
        filters={"supplier_name": ["like", f"%{entity}%"]},
        fields=["name", "supplier_name"], limit_page_length=3)

    filters = {"company": _get_company(), "docstatus": 1}
    party_name_display = entity

    if customers:
        filters["party_type"] = "Customer"
        filters["party"] = customers[0].name
        party_name_display = customers[0].customer_name
    elif suppliers:
        filters["party_type"] = "Supplier"
        filters["party"] = suppliers[0].name
        party_name_display = suppliers[0].supplier_name
    else:
        return {"data_type": "customer_payments", "error": "party_not_found",
                "message": f"'{entity}' introuvable dans les clients ou fournisseurs.",
                "currency": _get_currency(), "company": _get_company()}

    _apply_date_filter(filters, from_date, to_date)

    payments = frappe.get_all("Payment Entry", filters=filters,
        fields=["name", "payment_type", "posting_date", "party_name",
                "paid_amount", "mode_of_payment", "reference_no"],
        order_by="posting_date DESC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total_received = sum(flt(p.paid_amount) for p in payments
                         if p.payment_type == "Receive")
    total_paid = sum(flt(p.paid_amount) for p in payments
                     if p.payment_type == "Pay")
    total_count = frappe.db.count("Payment Entry", filters=filters)

    return {
        "data_type": "customer_payments",
        "party_name": party_name_display,
        "payments": payments,
        "count": len(payments),
        "total_received": total_received,
        "total_paid": total_paid,
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Payment Entry",
            "filters": filters,
            "fields": ["name", "payment_type", "posting_date", "party_name",
                       "paid_amount", "mode_of_payment", "reference_no"],
            "order_by": "posting_date DESC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "customer_payments",
            "currency": _get_currency(),
            "party_name": party_name_display,
            "from_date": from_date,
            "to_date": to_date
        }
    }


# ═══════════════════════════════════════════════════════════
#  RAPPORTS FINANCIERS
# ═══════════════════════════════════════════════════════════

def get_revenue(from_date=None, to_date=None, **kwargs):
    income_accounts = frappe.get_all("Account",
        filters={"company": _get_company(), "root_type": "Income", "is_group": 0},
        fields=["name"], limit_page_length=0)
    account_names = [a.name for a in income_accounts]

    if not account_names:
        return {"data_type": "revenue_period", "total_revenue": 0,
                "total_expenses": 0, "net_profit": 0, "details": [],
                "currency": _get_currency(), "company": _get_company(),
                "from_date": from_date, "to_date": to_date}

    gl_filters = {"company": _get_company(), "account": ["in", account_names],
                  "is_cancelled": 0}
    _apply_date_filter(gl_filters, from_date, to_date)

    gl_entries = frappe.get_all("GL Entry", filters=gl_filters,
        fields=["account", "debit", "credit", "posting_date"],
        order_by="posting_date DESC", limit_page_length=0)

    total_revenue = sum(flt(gl.credit) - flt(gl.debit) for gl in gl_entries)

    account_summary = {}
    for gl in gl_entries:
        acc = gl.account
        if acc not in account_summary:
            account_summary[acc] = 0
        account_summary[acc] += flt(gl.credit) - flt(gl.debit)

    details = [{"account": a, "amount": v} for a, v in account_summary.items() if v != 0]
    details.sort(key=lambda x: x["amount"], reverse=True)

    expense_accounts = frappe.get_all("Account",
        filters={"company": _get_company(), "root_type": "Expense", "is_group": 0},
        fields=["name"], limit_page_length=0)

    total_expenses = 0
    if expense_accounts:
        exp_filters = {"company": _get_company(),
                       "account": ["in", [a.name for a in expense_accounts]],
                       "is_cancelled": 0}
        _apply_date_filter(exp_filters, from_date, to_date)
        exp_entries = frappe.get_all("GL Entry", filters=exp_filters,
            fields=["debit", "credit"], limit_page_length=0)
        total_expenses = sum(flt(e.debit) - flt(e.credit) for e in exp_entries)

    return {
        "data_type": "revenue_period",
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_profit": total_revenue - total_expenses,
        "details": details,
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date
    }


def get_expenses(from_date=None, to_date=None, **kwargs):
    expense_accounts = frappe.get_all("Account",
        filters={"company": _get_company(), "root_type": "Expense", "is_group": 0},
        fields=["name"], limit_page_length=0)

    if not expense_accounts:
        return {"data_type": "expenses_period", "total_expenses": 0,
                "details": [], "count": 0,
                "currency": _get_currency(), "company": _get_company(),
                "from_date": from_date, "to_date": to_date}

    gl_filters = {"company": _get_company(),
                  "account": ["in", [a.name for a in expense_accounts]],
                  "is_cancelled": 0}
    _apply_date_filter(gl_filters, from_date, to_date)

    gl_entries = frappe.get_all("GL Entry", filters=gl_filters,
        fields=["account", "debit", "credit"],
        limit_page_length=0)

    account_summary = {}
    for gl in gl_entries:
        acc = gl.account
        if acc not in account_summary:
            account_summary[acc] = 0
        account_summary[acc] += flt(gl.debit) - flt(gl.credit)

    details = [{"account": a, "amount": v}
               for a, v in account_summary.items() if v != 0]
    details.sort(key=lambda x: x["amount"], reverse=True)

    total = sum(d["amount"] for d in details)

    return {
        "data_type": "expenses_period",
        "total_expenses": total,
        "details": details,
        "count": len(details),
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date
    }


def get_net_profit(from_date=None, to_date=None, **kwargs):
    revenue_data = get_revenue(from_date=from_date, to_date=to_date)
    return {
        "data_type": "net_profit",
        "total_revenue": revenue_data["total_revenue"],
        "total_expenses": revenue_data["total_expenses"],
        "net_profit": revenue_data["net_profit"],
        "revenue_details": revenue_data.get("details", []),
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date
    }


def get_account_balance(from_date=None, to_date=None, entity=None, **kwargs):
    if not entity:
        accounts = frappe.get_all("Account",
            filters={"company": _get_company(), "account_type": ["in", ["Bank", "Cash"]], "is_group": 0},
            fields=["name", "root_type", "account_type"],
            limit_page_length=10)
        if accounts:
            results = []
            for acc in accounts:
                gl_filters = {"company": _get_company(), "account": acc.name, "is_cancelled": 0}
                _apply_date_filter(gl_filters, from_date, to_date)
                entries = frappe.get_all("GL Entry", filters=gl_filters,
                    fields=["debit", "credit"], limit_page_length=0)
                bal = sum(flt(e.debit) - flt(e.credit) for e in entries)
                results.append({"account": acc.name, "account_type": acc.account_type,
                               "root_type": acc.root_type, "balance": bal})
            return {
                "data_type": "account_balance",
                "multiple": True,
                "accounts": results,
                "count": len(results),
                "currency": _get_currency(),
                "company": _get_company(),
                "from_date": from_date,
                "to_date": to_date
            }
        entity = "banque"

    type_mapping = {
        "banque": "Bank", "bank": "Bank", "bancaire": "Bank",
        "caisse": "Cash", "cash": "Cash", "espèce": "Cash", "espece": "Cash",
        "client": "Receivable", "receivable": "Receivable", "débiteur": "Receivable",
        "fournisseur": "Payable", "payable": "Payable", "créditeur": "Payable",
        "stock": "Stock", "inventaire": "Stock", "inventory": "Stock",
        "revenu": "Income Account", "income": "Income Account",
        "dépense": "Expense Account", "expense": "Expense Account",
        "capitaux": "Equity", "equity": "Equity",
    }

    entity_lower = entity.lower().strip()
    accounts = []

    for keyword, acc_type in type_mapping.items():
        if keyword in entity_lower:
            accounts = frappe.get_all("Account",
                filters={"company": _get_company(), "account_type": acc_type, "is_group": 0},
                fields=["name", "root_type", "account_type"],
                limit_page_length=5)
            if accounts:
                break

    if not accounts:
        accounts = frappe.get_all("Account",
            filters={"company": _get_company(), "name": ["like", f"%{entity}%"], "is_group": 0},
            fields=["name", "root_type", "account_type"],
            limit_page_length=5)

    if not accounts:
        accounts = frappe.get_all("Account",
            filters={"company": _get_company(), "account_name": ["like", f"%{entity}%"], "is_group": 0},
            fields=["name", "root_type", "account_type"],
            limit_page_length=5)

    if len(accounts) > 1:
        results = []
        for acc in accounts:
            gl_filters = {"company": _get_company(), "account": acc.name, "is_cancelled": 0}
            _apply_date_filter(gl_filters, from_date, to_date)
            entries = frappe.get_all("GL Entry", filters=gl_filters,
                fields=["debit", "credit"], limit_page_length=0)
            bal = sum(flt(e.debit) - flt(e.credit) for e in entries)
            results.append({"account": acc.name, "account_type": acc.account_type,
                           "root_type": acc.root_type, "balance": bal})
        return {
            "data_type": "account_balance",
            "multiple": True,
            "accounts": results,
            "count": len(results),
            "currency": _get_currency(),
            "company": _get_company(),
            "from_date": from_date,
            "to_date": to_date
        }

    if not accounts:
        return {"data_type": "account_balance", "error": "account_not_found",
                "message": f"Compte '{entity}' introuvable.",
                "currency": _get_currency(), "company": _get_company()}

    account_name = accounts[0].name
    gl_filters = {"company": _get_company(), "account": account_name, "is_cancelled": 0}
    _apply_date_filter(gl_filters, from_date, to_date)

    gl_entries = frappe.get_all("GL Entry", filters=gl_filters,
        fields=["debit", "credit", "posting_date", "voucher_type", "voucher_no"],
        order_by="posting_date DESC", limit_page_length=50)

    total_debit = sum(flt(gl.debit) for gl in gl_entries)
    total_credit = sum(flt(gl.credit) for gl in gl_entries)
    balance = total_debit - total_credit

    return {
        "data_type": "account_balance",
        "account": account_name,
        "root_type": accounts[0].root_type,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "balance": balance,
        "entry_count": len(gl_entries),
        "recent_entries": gl_entries[:10],
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date
    }


def get_financial_summary(from_date=None, to_date=None, **kwargs):
    root_types = ["Asset", "Liability", "Equity", "Income", "Expense"]
    summary = {}

    for rt in root_types:
        accounts = frappe.get_all("Account",
            filters={"company": _get_company(), "root_type": rt, "is_group": 0},
            fields=["name"], limit_page_length=0)
        if not accounts:
            summary[rt] = 0
            continue
        gl_filters = {"company": _get_company(),
                      "account": ["in", [a.name for a in accounts]],
                      "is_cancelled": 0}
        _apply_date_filter(gl_filters, from_date, to_date)
        entries = frappe.get_all("GL Entry", filters=gl_filters,
            fields=["debit", "credit"], limit_page_length=0)
        total_debit = sum(flt(e.debit) for e in entries)
        total_credit = sum(flt(e.credit) for e in entries)
        if rt in ["Asset", "Expense"]:
            summary[rt] = total_debit - total_credit
        else:
            summary[rt] = total_credit - total_debit

    net_profit = summary.get("Income", 0) - summary.get("Expense", 0)

    return {
        "data_type": "financial_summary",
        "assets": summary.get("Asset", 0),
        "liabilities": summary.get("Liability", 0),
        "equity": summary.get("Equity", 0),
        "income": summary.get("Income", 0),
        "expenses": summary.get("Expense", 0),
        "net_profit": net_profit,
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date
    }


# ═══════════════════════════════════════════════════════════
#  DIVERS
# ═══════════════════════════════════════════════════════════

def get_tax_rates(from_date=None, to_date=None, **kwargs):
    sales_taxes = frappe.get_all("Sales Taxes and Charges Template",
        filters={"company": _get_company(), "disabled": 0},
        fields=["name", "title", "is_default"],
        limit_page_length=20)

    purchase_taxes = frappe.get_all("Purchase Taxes and Charges Template",
        filters={"company": _get_company(), "disabled": 0},
        fields=["name", "title", "is_default"],
        limit_page_length=20)

    sales_details = []
    for t in sales_taxes:
        doc = frappe.get_doc("Sales Taxes and Charges Template", t.name)
        rates = []
        for row in doc.taxes:
            rates.append({
                "description": row.description,
                "rate": flt(row.rate),
                "charge_type": row.charge_type
            })
        sales_details.append({
            "name": t.title or t.name,
            "is_default": t.is_default,
            "rates": rates
        })

    return {
        "data_type": "tax_rates",
        "sales_taxes": sales_details,
        "sales_count": len(sales_taxes),
        "purchase_count": len(purchase_taxes),
        "currency": _get_currency(),
        "company": _get_company()
    }


def get_customer_list(from_date=None, to_date=None, limit_start=0, limit_page_length=50, **kwargs):
    customers = frappe.get_all("Customer",
        filters={"disabled": 0},
        fields=["name", "customer_name", "customer_group",
                "territory", "customer_type"],
        order_by="customer_name",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total_count = frappe.db.count("Customer", filters={"disabled": 0})

    return {
        "data_type": "customer_list",
        "customers": customers,
        "count": len(customers),
        "currency": _get_currency(),
        "company": _get_company(),
        "query_params": {
            "doctype": "Customer",
            "filters": {"disabled": 0},
            "fields": ["name", "customer_name", "customer_group", "territory", "customer_type"],
            "order_by": "customer_name",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "customer_list",
            "currency": _get_currency()
        }
    }


def get_supplier_list(from_date=None, to_date=None, limit_start=0, limit_page_length=50, **kwargs):
    suppliers = frappe.get_all("Supplier",
        filters={"disabled": 0},
        fields=["name", "supplier_name", "supplier_group",
                "supplier_type", "country"],
        order_by="supplier_name",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total_count = frappe.db.count("Supplier", filters={"disabled": 0})

    return {
        "data_type": "supplier_list",
        "suppliers": suppliers,
        "count": len(suppliers),
        "currency": _get_currency(),
        "company": _get_company(),
        "query_params": {
            "doctype": "Supplier",
            "filters": {"disabled": 0},
            "fields": ["name", "supplier_name", "supplier_group", "supplier_type", "country"],
            "order_by": "supplier_name",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "supplier_list",
            "currency": _get_currency()
        }
    }


# ═══════════════════════════════════════════════════════════
#  DISPATCHER
# ═══════════════════════════════════════════════════════════

def fetch_accounting_data(intent, from_date=None, to_date=None, entity=None,
                          limit_start=0, limit_page_length=20):
    handlers = {
        "unpaid_sales_invoices": get_unpaid_sales_invoices,
        "overdue_sales_invoices": get_overdue_sales_invoices,
        "total_invoiced_period": get_total_invoiced,
        "invoice_details": get_invoice_details,
        "customer_invoices": get_customer_invoices,
        "draft_invoices": get_draft_invoices,
        "top_debtors": get_top_debtors,
        "recent_invoices": get_recent_invoices,
        "unpaid_purchase_invoices": get_unpaid_purchase_invoices,
        "overdue_purchase_invoices": get_overdue_purchase_invoices,
        "supplier_invoices": get_supplier_invoices,
        "total_purchased_period": get_total_purchased,
        "top_creditors": get_top_creditors,
        "recent_payments": get_recent_payments,
        "received_payments_period": get_received_payments,
        "paid_payments_period": get_paid_payments,
        "customer_payments": get_customer_payments,
        "revenue_period": get_revenue,
        "expenses_period": get_expenses,
        "net_profit": get_net_profit,
        "account_balance": get_account_balance,
        "financial_summary": get_financial_summary,
        "tax_rates": get_tax_rates,
        "customer_list": get_customer_list,
        "supplier_list": get_supplier_list,
    }

    handler = handlers.get(intent)
    if handler:
        return handler(from_date=from_date, to_date=to_date, entity=entity,
                       limit_start=limit_start, limit_page_length=limit_page_length)
    return None