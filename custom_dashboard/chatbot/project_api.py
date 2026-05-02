# project_api.py
# APIs Project Management — v2 : Pagination V3 ajoutée (limit_start, limit_page_length, query_params)
# Pattern identique à accounting_api.py

import frappe
from frappe.utils import nowdate, getdate, flt

def _get_company():
    return frappe.defaults.get_global_default('company') or 'Tunisian United Solutions (Demo)'

def _get_currency():
    return frappe.db.get_value('Company', _get_company(), 'default_currency') or 'TND'


# ═══════════════════════════════════════════════════════════
#  UTILITAIRES
# ═══════════════════════════════════════════════════════════

def get_user_info():
    user = frappe.session.user
    full_name = frappe.db.get_value("User", user, "full_name") or user
    roles = frappe.get_roles(user)
    return {"user": user, "full_name": full_name, "roles": roles}


def _apply_date_filter(filters, from_date, to_date, field="expected_start_date"):
    if from_date and to_date:
        filters[field] = ["between", [from_date, to_date]]
    elif from_date:
        filters[field] = [">=", from_date]
    elif to_date:
        filters[field] = ["<=", to_date]


def _resolve_project(entity):
    if not entity:
        return None, {
            "error": "no_project_specified",
            "message": "Aucun projet spécifié. Veuillez fournir un ID ou nom de projet.",
            "company": _get_company()
        }
    if frappe.db.exists("Project", entity):
        return entity, None
    projects = frappe.get_all("Project",
        filters={"project_name": ["like", f"%{entity}%"], "company": _get_company()},
        fields=["name", "project_name"],
        limit_page_length=5)
    if not projects:
        return None, {
            "error": "project_not_found",
            "message": f"Projet '{entity}' introuvable.",
            "company": _get_company()
        }
    return projects[0].name, None


def _resolve_task(entity):
    if not entity:
        return None, {
            "error": "no_task_specified",
            "message": "Aucune tâche spécifiée. Veuillez fournir un ID ou sujet de tâche.",
            "company": _get_company()
        }
    if frappe.db.exists("Task", entity):
        return entity, None
    tasks = frappe.get_all("Task",
        filters={"subject": ["like", f"%{entity}%"]},
        fields=["name", "subject"],
        limit_page_length=5)
    if not tasks:
        return None, {
            "error": "task_not_found",
            "message": f"Tâche '{entity}' introuvable.",
            "company": _get_company()
        }
    return tasks[0].name, None


# ═══════════════════════════════════════════════════════════
#  GROUPE 1 — PROJECT LEVEL (5 intents + 1 customer filter)
# ═══════════════════════════════════════════════════════════

def get_project_status(entity=None, from_date=None, to_date=None, **kwargs):
    project_name, err = _resolve_project(entity)
    if err:
        return {"data_type": "project_status", **err}
    doc = frappe.get_doc("Project", project_name)
    return {
        "data_type": "project_status",
        "project": doc.name,
        "project_name": doc.project_name,
        "status": doc.status,
        "customer": doc.customer or "N/A",
        "company": _get_company()
    }


def get_project_progress(entity=None, from_date=None, to_date=None, **kwargs):
    project_name, err = _resolve_project(entity)
    if err:
        return {"data_type": "project_progress", **err}
    doc = frappe.get_doc("Project", project_name)
    today = getdate(nowdate())
    expected_end = getdate(doc.expected_end_date) if doc.expected_end_date else None
    days_late = None
    is_late = False
    if expected_end and doc.status == "Open":
        if today > expected_end:
            days_late = (today - expected_end).days
            is_late = True
    return {
        "data_type": "project_progress",
        "project": doc.name,
        "project_name": doc.project_name,
        "status": doc.status,
        "percent_complete": flt(doc.percent_complete),
        "expected_start_date": str(doc.expected_start_date) if doc.expected_start_date else "N/A",
        "expected_end_date": str(doc.expected_end_date) if doc.expected_end_date else "N/A",
        "actual_start_date": str(doc.actual_start_date) if doc.actual_start_date else "N/A",
        "actual_end_date": str(doc.actual_end_date) if doc.actual_end_date else "N/A",
        "is_late": is_late,
        "days_late": days_late,
        "company": _get_company()
    }


def get_project_details(entity=None, from_date=None, to_date=None, **kwargs):
    project_name, err = _resolve_project(entity)
    if err:
        return {"data_type": "project_details", **err}
    doc = frappe.get_doc("Project", project_name)
    today = getdate(nowdate())
    expected_end = getdate(doc.expected_end_date) if doc.expected_end_date else None
    days_late = None
    is_late = False
    if expected_end and doc.status == "Open" and today > expected_end:
        days_late = (today - expected_end).days
        is_late = True
    gross_margin = flt(doc.gross_margin) if hasattr(doc, "gross_margin") else (
        flt(doc.total_billable_amount) - flt(doc.total_costing_amount)
    )
    return {
        "data_type": "project_details",
        "project": doc.name,
        "project_name": doc.project_name,
        "status": doc.status,
        "percent_complete": flt(doc.percent_complete),
        "customer": doc.customer or "N/A",
        "sales_order": doc.sales_order or "N/A",
        "expected_start_date": str(doc.expected_start_date) if doc.expected_start_date else "N/A",
        "expected_end_date": str(doc.expected_end_date) if doc.expected_end_date else "N/A",
        "actual_start_date": str(doc.actual_start_date) if doc.actual_start_date else "N/A",
        "actual_end_date": str(doc.actual_end_date) if doc.actual_end_date else "N/A",
        "is_late": is_late,
        "days_late": days_late,
        "estimated_costing": flt(doc.estimated_costing),
        "total_costing_amount": flt(doc.total_costing_amount),
        "total_billable_amount": flt(doc.total_billable_amount),
        "total_sales_amount": flt(doc.total_sales_amount),
        "gross_margin": gross_margin,
        "currency": _get_currency(),
        "company": _get_company()
    }


def list_projects(from_date=None, to_date=None, entity=None, status=None,
                  limit_start=0, limit_page_length=20, **kwargs):
    filters = {"company": _get_company()}
    if status:
        filters["status"] = status
    _apply_date_filter(filters, from_date, to_date, field="expected_start_date")

    projects = frappe.get_all("Project", filters=filters,
        fields=["name", "project_name", "status", "percent_complete",
                "customer", "expected_end_date", "total_costing_amount",
                "total_billable_amount"],
        order_by="expected_end_date ASC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total_count = frappe.db.count("Project", filters=filters)

    return {
        "data_type": "project_list",
        "projects": projects,
        "count": len(projects),
        "filter_status": status or "all",
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Project",
            "filters": filters,
            "fields": ["name", "project_name", "status", "percent_complete",
                       "customer", "expected_end_date", "total_costing_amount",
                       "total_billable_amount"],
            "order_by": "expected_end_date ASC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "project_list",
            "currency": _get_currency(),
            "from_date": from_date,
            "to_date": to_date,
            "filter_status": status or "all"
        }
    }


def get_late_projects(from_date=None, to_date=None, limit_start=0, limit_page_length=20, **kwargs):
    today = nowdate()
    filters = {
        "company": _get_company(),
        "status": "Open",
        "expected_end_date": ["<", today]
    }
    projects = frappe.get_all("Project", filters=filters,
        fields=["name", "project_name", "status", "percent_complete",
                "customer", "expected_end_date", "actual_end_date"],
        order_by="expected_end_date ASC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    today_date = getdate(today)
    for proj in projects:
        if proj.expected_end_date:
            proj["days_late"] = (today_date - getdate(proj.expected_end_date)).days
        else:
            proj["days_late"] = None

    total_count = frappe.db.count("Project", filters=filters)

    return {
        "data_type": "late_projects",
        "projects": projects,
        "count": len(projects),
        "company": _get_company(),
        "query_params": {
            "doctype": "Project",
            "filters": filters,
            "fields": ["name", "project_name", "status", "percent_complete",
                       "customer", "expected_end_date", "actual_end_date"],
            "order_by": "expected_end_date ASC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "late_projects",
            "currency": _get_currency()
        }
    }


def get_projects_by_customer(entity=None, from_date=None, to_date=None,
                              status=None, limit_start=0, limit_page_length=20, **kwargs):
    if not entity:
        return {
            "data_type": "projects_by_customer",
            "error": "no_customer_specified",
            "message": "Aucun client spécifié. Veuillez fournir un nom de client.",
            "company": _get_company()
        }
    customers = frappe.get_all("Customer",
        filters={"customer_name": ["like", f"%{entity}%"]},
        fields=["name", "customer_name"],
        limit_page_length=5)
    if not customers:
        return {
            "data_type": "projects_by_customer",
            "error": "customer_not_found",
            "message": f"Client '{entity}' introuvable.",
            "company": _get_company()
        }
    customer_name = customers[0].name
    filters = {"company": _get_company(), "customer": customer_name}
    if status:
        filters["status"] = status
    _apply_date_filter(filters, from_date, to_date, field="expected_start_date")

    projects = frappe.get_all("Project", filters=filters,
        fields=["name", "project_name", "status", "percent_complete",
                "expected_end_date", "total_costing_amount",
                "total_billable_amount", "gross_margin"],
        order_by="expected_end_date ASC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total_count = frappe.db.count("Project", filters=filters)
    total_billable = sum(flt(p.total_billable_amount) for p in projects)
    total_cost = sum(flt(p.total_costing_amount) for p in projects)

    return {
        "data_type": "projects_by_customer",
        "customer": customers[0].customer_name,
        "customer_id": customer_name,
        "projects": projects,
        "count": len(projects),
        "total_billable_amount": total_billable,
        "total_costing_amount": total_cost,
        "filter_status": status or "all",
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Project",
            "filters": filters,
            "fields": ["name", "project_name", "status", "percent_complete",
                       "expected_end_date", "total_costing_amount",
                       "total_billable_amount", "gross_margin"],
            "order_by": "expected_end_date ASC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "projects_by_customer",
            "currency": _get_currency(),
            "customer": customers[0].customer_name,
            "customer_id": customer_name,
            "from_date": from_date,
            "to_date": to_date
        }
    }


# ═══════════════════════════════════════════════════════════
#  GROUPE 2 — PROJECT FINANCIAL (3 intents)
# ═══════════════════════════════════════════════════════════

def get_project_cost(entity=None, from_date=None, to_date=None, **kwargs):
    project_name, err = _resolve_project(entity)
    if err:
        return {"data_type": "project_cost", **err}
    doc = frappe.get_doc("Project", project_name)
    over_budget = False
    budget_variance = None
    if doc.estimated_costing:
        budget_variance = flt(doc.total_costing_amount) - flt(doc.estimated_costing)
        over_budget = budget_variance > 0
    return {
        "data_type": "project_cost",
        "project": doc.name,
        "project_name": doc.project_name,
        "status": doc.status,
        "estimated_costing": flt(doc.estimated_costing),
        "total_costing_amount": flt(doc.total_costing_amount),
        "over_budget": over_budget,
        "budget_variance": budget_variance,
        "currency": _get_currency(),
        "company": _get_company()
    }


def get_project_revenue(entity=None, from_date=None, to_date=None, **kwargs):
    project_name, err = _resolve_project(entity)
    if err:
        return {"data_type": "project_revenue", **err}
    doc = frappe.get_doc("Project", project_name)
    return {
        "data_type": "project_revenue",
        "project": doc.name,
        "project_name": doc.project_name,
        "status": doc.status,
        "total_billable_amount": flt(doc.total_billable_amount),
        "total_sales_amount": flt(doc.total_sales_amount),
        "sales_order": doc.sales_order or "N/A",
        "currency": _get_currency(),
        "company": _get_company()
    }


def get_project_profitability(entity=None, from_date=None, to_date=None, **kwargs):
    project_name, err = _resolve_project(entity)
    if err:
        return {"data_type": "project_profitability", **err}
    doc = frappe.get_doc("Project", project_name)
    revenue = flt(doc.total_billable_amount)
    cost = flt(doc.total_costing_amount)
    gross_margin = flt(doc.gross_margin) if hasattr(doc, "gross_margin") and doc.gross_margin else (revenue - cost)
    margin_pct = None
    if revenue > 0:
        margin_pct = round((gross_margin / revenue) * 100, 2)
    is_profitable = gross_margin > 0
    return {
        "data_type": "project_profitability",
        "project": doc.name,
        "project_name": doc.project_name,
        "status": doc.status,
        "total_costing_amount": cost,
        "total_billable_amount": revenue,
        "gross_margin": gross_margin,
        "margin_percentage": margin_pct,
        "is_profitable": is_profitable,
        "currency": _get_currency(),
        "company": _get_company()
    }


# ═══════════════════════════════════════════════════════════
#  GROUPE 3 — TASK LEVEL (4 intents)
# ═══════════════════════════════════════════════════════════

def list_tasks_by_project(entity=None, from_date=None, to_date=None,
                           status=None, limit_start=0, limit_page_length=20, **kwargs):
    project_name, err = _resolve_project(entity)
    if err:
        return {"data_type": "task_list", **err}
    filters = {"project": project_name}
    if status:
        filters["status"] = status
    _apply_date_filter(filters, from_date, to_date, field="exp_end_date")

    tasks = frappe.get_all("Task", filters=filters,
        fields=["name", "subject", "status", "priority", "progress",
                "exp_start_date", "exp_end_date", "is_milestone",
                "total_costing_amount", "total_billing_amount"],
        order_by="exp_end_date ASC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total_count = frappe.db.count("Task", filters=filters)

    return {
        "data_type": "task_list",
        "project": project_name,
        "tasks": tasks,
        "count": len(tasks),
        "filter_status": status or "all",
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Task",
            "filters": filters,
            "fields": ["name", "subject", "status", "priority", "progress",
                       "exp_start_date", "exp_end_date", "is_milestone",
                       "total_costing_amount", "total_billing_amount"],
            "order_by": "exp_end_date ASC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "task_list",
            "currency": _get_currency(),
            "project": project_name,
            "from_date": from_date,
            "to_date": to_date
        }
    }


def get_task_status(entity=None, from_date=None, to_date=None, **kwargs):
    task_name, err = _resolve_task(entity)
    if err:
        return {"data_type": "task_status", **err}
    doc = frappe.get_doc("Task", task_name)
    return {
        "data_type": "task_status",
        "task": doc.name,
        "subject": doc.subject,
        "project": doc.project or "N/A",
        "status": doc.status,
        "priority": doc.priority or "N/A",
        "company": _get_company()
    }


def get_task_details(entity=None, from_date=None, to_date=None, **kwargs):
    task_name, err = _resolve_task(entity)
    if err:
        return {"data_type": "task_details", **err}
    doc = frappe.get_doc("Task", task_name)
    today = getdate(nowdate())
    exp_end = getdate(doc.exp_end_date) if doc.exp_end_date else None
    days_overdue = None
    is_overdue = False
    if exp_end and doc.status not in ["Completed", "Cancelled"]:
        if today > exp_end:
            days_overdue = (today - exp_end).days
            is_overdue = True
    return {
        "data_type": "task_details",
        "task": doc.name,
        "subject": doc.subject,
        "project": doc.project or "N/A",
        "status": doc.status,
        "priority": doc.priority or "N/A",
        "progress": flt(doc.progress),
        "is_milestone": doc.is_milestone,
        "exp_start_date": str(doc.exp_start_date) if doc.exp_start_date else "N/A",
        "exp_end_date": str(doc.exp_end_date) if doc.exp_end_date else "N/A",
        "act_start_date": str(doc.act_start_date) if doc.act_start_date else "N/A",
        "act_end_date": str(doc.act_end_date) if doc.act_end_date else "N/A",
        "is_overdue": is_overdue,
        "days_overdue": days_overdue,
        "total_costing_amount": flt(doc.total_costing_amount),
        "total_billing_amount": flt(doc.total_billing_amount),
        "currency": _get_currency(),
        "company": _get_company()
    }


def get_overdue_tasks(entity=None, from_date=None, to_date=None,
                      limit_start=0, limit_page_length=20, **kwargs):
    today = nowdate()
    filters = {
        "exp_end_date": ["<", today],
        "status": ["not in", ["Completed", "Cancelled"]]
    }
    if entity:
        project_name, err = _resolve_project(entity)
        if not err:
            filters["project"] = project_name

    tasks = frappe.get_all("Task", filters=filters,
        fields=["name", "subject", "project", "status", "priority",
                "exp_end_date", "progress"],
        order_by="exp_end_date ASC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    today_date = getdate(today)
    for task in tasks:
        if task.exp_end_date:
            task["days_overdue"] = (today_date - getdate(task.exp_end_date)).days
        else:
            task["days_overdue"] = None

    total_count = frappe.db.count("Task", filters=filters)

    return {
        "data_type": "overdue_tasks",
        "tasks": tasks,
        "count": len(tasks),
        "filter_project": entity or "all",
        "company": _get_company(),
        "query_params": {
            "doctype": "Task",
            "filters": filters,
            "fields": ["name", "subject", "project", "status", "priority",
                       "exp_end_date", "progress"],
            "order_by": "exp_end_date ASC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "overdue_tasks",
            "currency": _get_currency(),
            "filter_project": entity or "all"
        }
    }


# ═══════════════════════════════════════════════════════════
#  GROUPE 4 — TIMESHEET LEVEL (4 intents)
# ═══════════════════════════════════════════════════════════

def get_hours_by_project(entity=None, from_date=None, to_date=None,
                         limit_start=0, limit_page_length=20, **kwargs):
    project_name, err = _resolve_project(entity)
    if err:
        return {"data_type": "hours_by_project", **err}
    td_filters = {"project": project_name}
    _apply_date_filter(td_filters, from_date, to_date, field="from_time")

    timesheet_details = frappe.get_all("Timesheet Detail",
        filters=td_filters,
        fields=["hours", "billable_hours", "project", "task",
                "from_time", "to_time"],
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    total_hours = sum(flt(td.hours) for td in timesheet_details)
    total_billable = sum(flt(td.billable_hours) for td in timesheet_details)

    task_summary = {}
    for td in timesheet_details:
        key = td.task or "Sans tâche"
        if key not in task_summary:
            task_summary[key] = {"hours": 0, "billable_hours": 0}
        task_summary[key]["hours"] += flt(td.hours)
        task_summary[key]["billable_hours"] += flt(td.billable_hours)

    total_count = frappe.db.count("Timesheet Detail", filters=td_filters)

    return {
        "data_type": "hours_by_project",
        "project": project_name,
        "total_hours": round(total_hours, 2),
        "total_billable_hours": round(total_billable, 2),
        "non_billable_hours": round(total_hours - total_billable, 2),
        "task_breakdown": task_summary,
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Timesheet Detail",
            "filters": td_filters,
            "fields": ["hours", "billable_hours", "project", "task", "from_time", "to_time"],
            "order_by": "from_time",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "hours_by_project",
            "currency": _get_currency(),
            "project": project_name,
            "from_date": from_date,
            "to_date": to_date
        }
    }


def get_billable_hours_by_project(entity=None, from_date=None, to_date=None,
                                  limit_start=0, limit_page_length=20, **kwargs):
    project_name, err = _resolve_project(entity)
    if err:
        return {"data_type": "billable_hours_by_project", **err}
    ts_filters = {"docstatus": 1}
    _apply_date_filter(ts_filters, from_date, to_date, field="start_date")

    timesheets = frappe.get_all("Timesheet", filters=ts_filters,
        fields=["name", "employee", "start_date", "end_date",
                "total_billable_hours", "total_billable_amount", "status"],
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    relevant_ts = []
    total_billable_hours = 0
    total_billable_amount = 0

    for ts in timesheets:
        details = frappe.get_all("Timesheet Detail",
            filters={"parent": ts.name, "project": project_name, "is_billable": 1},
            fields=["hours", "billing_amount"],
            limit_page_length=0)
        if details:
            ts_hours = sum(flt(d.hours) for d in details)
            ts_amount = sum(flt(d.billing_amount) for d in details)
            total_billable_hours += ts_hours
            total_billable_amount += ts_amount
            relevant_ts.append({
                "timesheet": ts.name,
                "employee": ts.employee,
                "billable_hours": round(ts_hours, 2),
                "billable_amount": round(ts_amount, 2)
            })

    total_count = frappe.db.count("Timesheet", filters=ts_filters)

    return {
        "data_type": "billable_hours_by_project",
        "project": project_name,
        "total_billable_hours": round(total_billable_hours, 2),
        "total_billable_amount": round(total_billable_amount, 2),
        "timesheet_count": len(relevant_ts),
        "timesheets": relevant_ts,
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Timesheet",
            "filters": ts_filters,
            "fields": ["name", "employee", "start_date", "end_date",
                       "total_billable_hours", "total_billable_amount", "status"],
            "order_by": "start_date DESC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "billable_hours_by_project",
            "currency": _get_currency(),
            "project": project_name,
            "from_date": from_date,
            "to_date": to_date
        }
    }


def get_timesheets_by_employee(entity=None, from_date=None, to_date=None,
                               limit_start=0, limit_page_length=20, **kwargs):
    if not entity:
        return {
            "data_type": "timesheets_by_employee",
            "error": "no_employee_specified",
            "message": "Aucun employé spécifié. Veuillez fournir un nom ou ID d'employé.",
            "company": _get_company()
        }
    employee_id = None
    entity_display = entity
    if frappe.db.exists("Employee", entity):
        employee_id = entity
    else:
        employees = frappe.get_all("Employee",
            filters={"employee_name": ["like", f"%{entity}%"], "status": "Active"},
            fields=["name", "employee_name"],
            limit_page_length=5)
        if not employees:
            return {
                "data_type": "timesheets_by_employee",
                "error": "employee_not_found",
                "message": f"Employé '{entity}' introuvable.",
                "company": _get_company()
            }
        employee_id = employees[0].name
        entity_display = employees[0].employee_name

    filters = {"employee": employee_id}
    _apply_date_filter(filters, from_date, to_date, field="start_date")

    timesheets = frappe.get_all("Timesheet", filters=filters,
        fields=["name", "employee", "start_date", "end_date",
                "total_hours", "total_billable_hours",
                "total_billable_amount", "total_costing_amount", "status"],
        order_by="start_date DESC",
        limit_start=limit_start,
        limit_page_length=limit_page_length)

    for ts in timesheets:
        projects_in_ts = frappe.get_all("Timesheet Detail",
            filters={"parent": ts.name},
            fields=["project"],
            limit_page_length=0)
        ts["projects"] = list({p.project for p in projects_in_ts if p.project})

    total_count = frappe.db.count("Timesheet", filters=filters)
    total_hours = sum(flt(ts.total_hours) for ts in timesheets)
    total_billable = sum(flt(ts.total_billable_hours) for ts in timesheets)

    return {
        "data_type": "timesheets_by_employee",
        "employee": employee_id,
        "employee_name": entity_display,
        "timesheets": timesheets,
        "count": len(timesheets),
        "total_hours": round(total_hours, 2),
        "total_billable_hours": round(total_billable, 2),
        "currency": _get_currency(),
        "company": _get_company(),
        "from_date": from_date,
        "to_date": to_date,
        "query_params": {
            "doctype": "Timesheet",
            "filters": filters,
            "fields": ["name", "employee", "start_date", "end_date",
                       "total_hours", "total_billable_hours",
                       "total_billable_amount", "total_costing_amount", "status"],
            "order_by": "start_date DESC",
            "page_size": limit_page_length,
            "total_count": total_count,
            "data_type": "timesheets_by_employee",
            "currency": _get_currency(),
            "employee": employee_id,
            "employee_name": entity_display,
            "from_date": from_date,
            "to_date": to_date
        }
    }


def get_timesheet_details(entity=None, from_date=None, to_date=None, **kwargs):
    if not entity:
        return {
            "data_type": "timesheet_details",
            "error": "no_timesheet_specified",
            "message": "Aucun ID de timesheet spécifié. Exemple : TS-2024-005",
            "company": _get_company()
        }
    if not frappe.db.exists("Timesheet", entity):
        return {
            "data_type": "timesheet_details",
            "error": "timesheet_not_found",
            "message": f"Timesheet '{entity}' introuvable.",
            "company": _get_company()
        }
    doc = frappe.get_doc("Timesheet", entity)
    detail_lines = []
    for row in doc.time_logs:
        detail_lines.append({
            "activity_type": row.activity_type or "N/A",
            "task": row.task or "N/A",
            "project": row.project or "N/A",
            "from_time": str(row.from_time) if row.from_time else "N/A",
            "to_time": str(row.to_time) if row.to_time else "N/A",
            "hours": flt(row.hours),
            "is_billable": row.is_billable,
            "billable_hours": flt(row.billing_hours) if hasattr(row, "billing_hours") else flt(row.hours),
            "billing_amount": flt(row.billing_amount),
            "description": row.description or ""
        })
    return {
        "data_type": "timesheet_details",
        "timesheet": doc.name,
        "employee": doc.employee,
        "employee_name": doc.employee_name or doc.employee,
        "status": doc.status,
        "start_date": str(doc.start_date) if doc.start_date else "N/A",
        "end_date": str(doc.end_date) if doc.end_date else "N/A",
        "total_hours": flt(doc.total_hours),
        "total_billable_hours": flt(doc.total_billable_hours),
        "total_billable_amount": flt(doc.total_billable_amount),
        "total_costing_amount": flt(doc.total_costing_amount),
        "detail_count": len(detail_lines),
        "details": detail_lines,
        "currency": _get_currency(),
        "company": _get_company()
    }


# ═══════════════════════════════════════════════════════════
#  DISPATCHER
# ═══════════════════════════════════════════════════════════

def fetch_project_data(intent, from_date=None, to_date=None, entity=None,
                       limit_start=0, limit_page_length=20):
    handlers = {
        "project_status": get_project_status,
        "project_progress": get_project_progress,
        "project_details": get_project_details,
        "project_list": list_projects,
        "late_projects": get_late_projects,
        "projects_by_customer": get_projects_by_customer,
        "project_cost": get_project_cost,
        "project_revenue": get_project_revenue,
        "project_profitability": get_project_profitability,
        "task_list": list_tasks_by_project,
        "task_status": get_task_status,
        "task_details": get_task_details,
        "overdue_tasks": get_overdue_tasks,
        "hours_by_project": get_hours_by_project,
        "billable_hours_by_project": get_billable_hours_by_project,
        "timesheets_by_employee": get_timesheets_by_employee,
        "timesheet_details": get_timesheet_details,
    }
    handler = handlers.get(intent)
    if handler:
        return handler(entity=entity, from_date=from_date, to_date=to_date,
                       limit_start=limit_start, limit_page_length=limit_page_length)
    return None