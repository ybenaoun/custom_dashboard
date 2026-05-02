# -*- coding: utf-8 -*-
"""
Backend du tableau de bord global.
Point d'entrée unique : get_dashboard_data(period, company)
Retourne la structure complète consommée par le JS frontend.
"""

import frappe
from frappe import _
from frappe.query_builder.functions import Sum, Count, IfNull
from datetime import timedelta as _td
from frappe.utils import (
    getdate,
    add_days,
    add_months,
    flt,
    cint,
    nowdate,
    now_datetime,
    formatdate,
    fmt_money,
)


# ===========================================================================
# Helpers : dates et cache
# ===========================================================================

def _resolve_period(period):
    """Convertit un libellé de période en (date_from, date_to, range_label)."""
    today = getdate(nowdate())

    if period == "Aujourd'hui":
        return str(today), str(today), _("Aujourd'hui ({0})").format(formatdate(str(today)))

    if period == "Cette semaine":
        start = add_days(today, -today.weekday())
        end = add_days(start, 6)
        return str(start), str(end), _("Semaine du {0} au {1}").format(
            formatdate(str(start)), formatdate(str(end))
        )

    if period == "Ce trimestre":
        q = (today.month - 1) // 3
        start = today.replace(month=q * 3 + 1, day=1)
        end_month = q * 3 + 3
        end = add_days(start.replace(month=end_month + 1, day=1) if end_month < 12
                       else start.replace(year=start.year + 1, month=1, day=1), -1)
        return str(start), str(end), _("T{0} {1}").format(q + 1, today.year)

    if period == "Cette année":  # noqa: RET503
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)
        return str(start), str(end), _("Année {0}").format(today.year)

    # Défaut : Ce mois
    start = today.replace(day=1)
    end = add_days(add_months(start, 1), -1)
    return str(start), str(end), _("{0}").format(formatdate(str(start), "MMMM YYYY"))


def _previous_period(date_from, date_to):
    """Période précédente de même durée."""
    f = getdate(date_from)
    t = getdate(date_to)
    delta = (t - f).days + 1
    prev_to = add_days(f, -1)
    prev_from = add_days(prev_to, -(delta - 1))
    return str(prev_from), str(prev_to)


def _pct_change(current, previous):
    current, previous = flt(current), flt(previous)
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / abs(previous)) * 100, 2)


def _trend_label(pct):
    if pct > 0:
        return "+{0}%".format(pct)
    if pct < 0:
        return "{0}%".format(pct)
    return "0%"


def _trend_fill(raw_rows, date_from, date_to, value_key="t"):
    """Zero-fills weekly trend data for all ISO weeks overlapping [date_from, date_to].
    Returns (labels, values) where labels are 'DD/MM' (Monday of each week).
    """
    f = getdate(date_from)
    t = getdate(date_to)

    lookup = {}
    for r in (raw_rows or []):
        yw = int(getattr(r, "yw", 0))
        v = flt(getattr(r, value_key, 0) or 0)
        lookup[yw] = lookup.get(yw, 0) + v

    weeks = []
    monday = f - _td(days=f.weekday())
    while monday <= t:
        iso = monday.isocalendar()
        yw = iso[0] * 100 + iso[1]
        week_end = monday + _td(days=6)
        if week_end >= f:
            weeks.append((yw, monday))
        monday += _td(weeks=1)

    if not weeks:
        return [], []

    labels = [w[1].strftime("%d/%m") for w in weeks]
    values = [lookup.get(w[0], 0) for w in weeks]
    return labels, values


def _weekly_series(label, sql, params, value_key="v", chart_type="line", date_from=None, date_to=None):
    """Exécute une requête hebdomadaire et retourne une série {label, labels, values, type}.
    La requête doit projeter `yw` (YEARWEEK ISO) et la colonne `value_key`.
    """
    try:
        rows = frappe.db.sql(sql, params or {}, as_dict=True)
    except Exception:
        rows = []
    labels, values = _trend_fill(rows, date_from, date_to, value_key=value_key)
    return {
        "label": label,
        "labels": labels,
        "values": values,
        "type": chart_type,
    }


def _money(value, company=None):
    """Formate un montant avec le symbole monétaire."""
    currency = None
    if company:
        currency = frappe.db.get_value("Company", company, "default_currency")
    if not currency:
        currency = frappe.defaults.get_global_default("currency") or "EUR"
    return fmt_money(flt(value), currency=currency)


def _cache_key(prefix, date_from, date_to, company):
    return "gd_{0}_{1}_{2}_{3}".format(prefix, date_from, date_to, company or "all")


def _cached(prefix, date_from, date_to, company, fn):
    key = _cache_key(prefix, date_from, date_to, company)
    val = frappe.cache().get_value(key)
    if val is not None:
        return val
    val = fn()
    frappe.cache().set_value(key, val, expires_in_sec=300)
    return val


# ===========================================================================
# Permissions
# ===========================================================================

def _has_dashboard_access(user=None):
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return True
    if not frappe.db.exists("DocType", "Dashboard Access Control"):
        return True
    try:
        cfg = frappe.get_single("Dashboard Access Control")
    except Exception:
        return True
    if not cfg.enabled:
        return True
    if cfg.access_type == "Par utilisateur":
        return any(r.user == user for r in (cfg.allowed_users or []))
    if cfg.access_type == "Par rôle":
        roles = set(frappe.get_roles(user))
        return any(r.role in roles for r in (cfg.allowed_roles or []))
    return True


def has_desk_icon_permission():
    return _has_dashboard_access()


def _get_config(user=None):
    user = user or frappe.session.user
    has_access = _has_dashboard_access(user)
    config = {
        "has_access": has_access,
        "can_export": False,
        "default_period": "Ce mois",
        "visible_modules": ["Stock", "Vente", "Achat", "Comptabilité", "RH"],
    }
    if not has_access:
        return config

    if not frappe.db.exists("DocType", "Dashboard Access Control"):
        config["can_export"] = True
        return config

    try:
        cfg = frappe.get_single("Dashboard Access Control")
    except Exception:
        config["can_export"] = True
        return config

    config["default_period"] = cfg.default_period or "Ce mois"
    if cfg.visible_modules:
        config["visible_modules"] = [r.module_name for r in cfg.visible_modules if r.enabled]

    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        config["can_export"] = True
    elif not cfg.enabled:
        config["can_export"] = True
    elif cfg.access_type == "Par utilisateur":
        for r in (cfg.allowed_users or []):
            if r.user == user:
                config["can_export"] = bool(r.can_export)
                break
    elif cfg.access_type == "Par rôle":
        user_roles = set(frappe.get_roles(user))
        for r in (cfg.allowed_roles or []):
            if r.role in user_roles and r.can_export:
                config["can_export"] = True
                break

    return config


# ===========================================================================
# Point d'entrée principal
# ===========================================================================

@frappe.whitelist()
def get_dashboard_data(period=None, company=None):
    """Retourne toutes les données du dashboard en un seul appel."""
    config = _get_config()
    if not config["has_access"]:
        frappe.throw(
            _("Vous n'avez pas accès à ce tableau de bord. Contactez votre administrateur."),
            frappe.PermissionError,
        )

    period = period or config["default_period"]
    date_from, date_to, range_label = _resolve_period(period)
    visible = set(config["visible_modules"])
    company = company or None

    modules = []
    summary_cards = []

    if "Stock" in visible:
        stock = _cached("stock", date_from, date_to, company,
                        lambda: _stock_module(date_from, date_to, company))
        modules.append(stock["module"])
        summary_cards.extend(stock["cards"])

    if "Vente" in visible:
        sales = _cached("sales", date_from, date_to, company,
                        lambda: _sales_module(date_from, date_to, company))
        modules.append(sales["module"])
        summary_cards.extend(sales["cards"])

    if "Achat" in visible:
        purchase = _cached("purchase", date_from, date_to, company,
                           lambda: _purchase_module(date_from, date_to, company))
        modules.append(purchase["module"])
        summary_cards.extend(purchase["cards"])

    if "Comptabilité" in visible:
        accounting = _cached("accounting", date_from, date_to, company,
                             lambda: _accounting_module(date_from, date_to, company))
        modules.append(accounting["module"])
        summary_cards.extend(accounting["cards"])

    if "RH" in visible:
        hr = _cached("hr", date_from, date_to, company,
                     lambda: _hr_module(date_from, date_to, company))
        modules.append(hr["module"])
        summary_cards.extend(hr["cards"])

    # Graphique global : évolution du CA sur 12 mois
    chart = _build_revenue_chart(company)

    return {
        "filters": {
            "period": period,
            "company": company or "",
            "date_from": date_from,
            "date_to": date_to,
            "range_label": range_label,
        },
        "config": config,
        "generated_at": frappe.utils.format_datetime(now_datetime(), "HH:mm:ss"),
        "summary_cards": summary_cards,
        "modules": modules,
        "chart": chart,
        "report_route": {
            "path": "query-report/KPI Global Report",
            "label": _("Rapport KPI"),
            "route_options": {
                "from_date": date_from,
                "to_date": date_to,
                "company": company or "",
            },
        },
    }


# ===========================================================================
# Analyse IA (Qwen via Ollama)
# ===========================================================================

@frappe.whitelist()
def analyze_with_ai(chart_title, chart_type, labels, datasets, filters=None, period=None):
    """Analyse un graphique via le modèle Qwen (Ollama) et retourne une interprétation en français."""
    import os
    import requests as _requests

    labels = frappe.parse_json(labels) if isinstance(labels, str) else (labels or [])
    datasets = frappe.parse_json(datasets) if isinstance(datasets, str) else (datasets or [])
    filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})

    base_url = os.environ.get("QWEN_BASE_URL") or frappe.conf.get("qwen_base_url", "http://localhost:11434/v1")
    api_key  = os.environ.get("QWEN_API_KEY")  or frappe.conf.get("qwen_api_key",  "ollama")
    model    = os.environ.get("QWEN_MODEL")    or frappe.conf.get("qwen_model",    "qwen2.5:3b")

    datasets_text = "\n".join(
        "- {name} : {values}".format(
            name=ds.get("name", "Série"),
            values=ds.get("values", ds.get("data", [])),
        )
        for ds in datasets
    )

    prompt = (
        "Analyste ERP. Analyse ce graphique en français.\n"
        "Titre: {title} | Type: {chart_type} | Période: {period} | Société: {company}\n"
        "X: {labels}\n{datasets_text}\n\n"
        "Réponds en JSON valide, exactement ces 4 clés, sois concis :\n"
        '{{"resume":"...","tendance":"...","anomalies":"...","recommandation":"..."}}'
    ).format(
        title=chart_title,
        chart_type=chart_type,
        period=period or filters.get("range_label", "Non spécifiée"),
        company=filters.get("company") or "Toutes sociétés",
        labels=labels,
        datasets_text=datasets_text,
    )

    try:
        response = _requests.post(
            "{0}/chat/completions".format(base_url.rstrip("/")),
            headers={
                "Authorization": "Bearer {0}".format(api_key),
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 400,
                "keep_alive": -1,
                "options": {
                    "num_ctx": 1024,
                    "num_predict": 400,
                    "num_thread": 4,
                    "num_gpu": 14,
                },
            },
            timeout=60,
        )
        response.raise_for_status()
    except _requests.exceptions.ConnectionError:
        frappe.throw(
            _("Impossible de contacter Ollama. Vérifiez qu'Ollama est en cours d'exécution ({0}).").format(base_url)
        )
    except _requests.exceptions.Timeout:
        frappe.throw(_("Ollama n'a pas répondu dans le délai imparti (60 s)."))
    except _requests.exceptions.HTTPError as exc:
        frappe.throw(_("Erreur HTTP Ollama : {0}").format(str(exc)))

    try:
        content = response.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as exc:
        frappe.throw(_("Réponse inattendue d'Ollama : {0}").format(str(exc)))

    # Nettoie les blocs markdown ```json ... ``` si présents
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1] if len(parts) > 1 else content
        if content.startswith("json"):
            content = content[4:]

    result = frappe.parse_json(content.strip())
    if not result or not isinstance(result, dict):
        frappe.throw(_("La réponse de Gemini n'est pas au format JSON attendu."))

    return {
        "resume": result.get("resume", ""),
        "tendance": result.get("tendance", ""),
        "anomalies": result.get("anomalies", ""),
        "recommandation": result.get("recommandation", ""),
    }


# ===========================================================================
# Module Stock
# ===========================================================================

def _stock_module(date_from, date_to, company):
    Bin = frappe.qb.DocType("Bin")
    Item = frappe.qb.DocType("Item")
    SLE = frappe.qb.DocType("Stock Ledger Entry")
    Warehouse = frappe.qb.DocType("Warehouse")

    # Valeur totale du stock
    q = frappe.qb.from_(Bin).select(IfNull(Sum(Bin.stock_value), 0).as_("v"))
    if company:
        q = q.join(Warehouse).on(
            (Bin.warehouse == Warehouse.name) & (Warehouse.company == company)
        )
    total_value = flt(q.run(as_dict=True)[0].v)

    # Rupture de stock
    q2 = (
        frappe.qb.from_(Bin)
        .join(Item).on(Bin.item_code == Item.name)
        .select(Count(Bin.item_code).distinct().as_("c"))
        .where(Bin.actual_qty <= 0)
        .where(Item.disabled == 0)
    )
    if company:
        q2 = q2.join(Warehouse).on(
            (Bin.warehouse == Warehouse.name) & (Warehouse.company == company)
        )
    out_of_stock = cint(q2.run(as_dict=True)[0].c)

    # Sous seuil de réapprovisionnement
    q3 = (
        frappe.qb.from_(Bin)
        .join(Item).on(Bin.item_code == Item.name)
        .select(Count(Bin.item_code).distinct().as_("c"))
        .where(Item.disabled == 0)
        .where(Bin.actual_qty < IfNull(Item.safety_stock, 0))
        .where(Item.safety_stock > 0)
    )
    if company:
        q3 = q3.join(Warehouse).on(
            (Bin.warehouse == Warehouse.name) & (Warehouse.company == company)
        )
    below_reorder = cint(q3.run(as_dict=True)[0].c)

    # Taux de rotation
    q4 = (
        frappe.qb.from_(SLE)
        .select(IfNull(Sum(SLE.stock_value_difference * -1), 0).as_("v"))
        .where(SLE.actual_qty < 0)
        .where(SLE.posting_date >= date_from)
        .where(SLE.posting_date <= date_to)
        .where(SLE.is_cancelled == 0)
    )
    if company:
        q4 = q4.where(SLE.company == company)
    outgoing = flt(q4.run(as_dict=True)[0].v)
    turnover = round(outgoing / total_value, 2) if total_value else 0

    # Stock dormant (> 90 jours)
    cutoff = str(add_days(getdate(date_to), -90))
    q5 = (
        frappe.qb.from_(Bin)
        .join(Item).on(Bin.item_code == Item.name)
        .select(Count(Bin.item_code).distinct().as_("c"))
        .where(Bin.actual_qty > 0)
        .where(Item.disabled == 0)
    )
    if company:
        q5 = q5.join(Warehouse).on(
            (Bin.warehouse == Warehouse.name) & (Warehouse.company == company)
        )
    total_with_stock = cint(q5.run(as_dict=True)[0].c)

    q6 = (
        frappe.qb.from_(SLE)
        .select(Count(SLE.item_code).distinct().as_("c"))
        .where(SLE.posting_date > cutoff)
        .where(SLE.is_cancelled == 0)
    )
    if company:
        q6 = q6.where(SLE.company == company)
    recently_moved = cint(q6.run(as_dict=True)[0].c)
    dormant_pct = 0
    if total_with_stock > 0:
        dormant_pct = round(max(0, total_with_stock - recently_moved) / total_with_stock * 100, 1)

    # Top 5 articles
    top_items = frappe.db.sql(
        """
        SELECT item_code, COUNT(*) AS cnt, SUM(ABS(actual_qty)) AS qty
        FROM `tabStock Ledger Entry`
        WHERE posting_date BETWEEN %(f)s AND %(t)s AND is_cancelled = 0
              {cf}
        GROUP BY item_code ORDER BY cnt DESC LIMIT 5
        """.format(cf="AND company = %(co)s" if company else ""),
        {"f": date_from, "t": date_to, "co": company},
        as_dict=True,
    )

    # Tendance : mouvements par semaine sur la période
    trend_data = frappe.db.sql(
        """
        SELECT YEARWEEK(posting_date, 1) AS yw, COUNT(*) AS cnt
        FROM `tabStock Ledger Entry`
        WHERE posting_date BETWEEN %(f)s AND %(t)s AND is_cancelled = 0
              {cf}
        GROUP BY yw ORDER BY yw LIMIT 12
        """.format(cf="AND company = %(co)s" if company else ""),
        {"f": date_from, "t": date_to, "co": company},
        as_dict=True,
    )

    # Tendances additionnelles (sorties / entrées valorisées par semaine)
    cf_co = "AND company = %(co)s" if company else ""
    params = {"f": date_from, "t": date_to, "co": company}
    trend_outgoing = _weekly_series(
        _("Sorties valorisées"),
        f"""
        SELECT YEARWEEK(posting_date, 1) AS yw,
               COALESCE(SUM(stock_value_difference * -1), 0) AS v
        FROM `tabStock Ledger Entry`
        WHERE posting_date BETWEEN %(f)s AND %(t)s
          AND is_cancelled = 0 AND actual_qty < 0 {cf_co}
        GROUP BY yw ORDER BY yw LIMIT 12
        """,
        params, chart_type="line", date_from=date_from, date_to=date_to,
    )
    trend_incoming = _weekly_series(
        _("Entrées valorisées"),
        f"""
        SELECT YEARWEEK(posting_date, 1) AS yw,
               COALESCE(SUM(stock_value_difference), 0) AS v
        FROM `tabStock Ledger Entry`
        WHERE posting_date BETWEEN %(f)s AND %(t)s
          AND is_cancelled = 0 AND actual_qty > 0 {cf_co}
        GROUP BY yw ORDER BY yw LIMIT 12
        """,
        params, chart_type="bar", date_from=date_from, date_to=date_to,
    )
    trend_movements_labels, trend_movements_values = _trend_fill(
        trend_data, date_from, date_to, "cnt"
    )

    return {
        "cards": [
            {
                "module_label": _("Stock"),
                "label": _("Valeur totale du stock"),
                "formatted_value": _money(total_value, company),
                "description": _("{0} articles en rupture").format(out_of_stock),
                "route": {"path": "List/Stock Ledger Entry", "label": _("Voir le stock")},
            },
        ],
        "module": {
            "label": _("Stock"),
            "color": "#0f766e",
            "is_customizable": True,
            "description": _("Rotation {0}x | Dormant {1}%").format(turnover, dormant_pct),
            "primary_metric": {
                "formatted_value": _money(total_value, company),
                "route": {"path": "List/Bin", "label": _("Détail stock")},
            },
            "stats": [
                {
                    "label": _("Articles en rupture"),
                    "formatted_value": str(out_of_stock),
                    "description": _("Quantité actuelle ≤ 0"),
                    "route": {"path": "List/Bin/actual_qty=%5B%22%3C%3D%22%2C0%5D", "label": _("Voir")},
                },
                {
                    "label": _("Sous seuil réappro."),
                    "formatted_value": str(below_reorder),
                    "description": _("En dessous du stock de sécurité"),
                    "route": None,
                },
                {
                    "label": _("Rotation du stock"),
                    "formatted_value": "{0}x".format(turnover),
                    "description": _("Sorties / Valeur stock sur la période"),
                    "route": None,
                },
                {
                    "label": _("Stock dormant"),
                    "formatted_value": "{0}%".format(dormant_pct),
                    "description": _("Aucun mouvement depuis 90 jours"),
                    "route": None,
                },
            ] + [
                {
                    "label": _("Top : {0}").format(item.item_code),
                    "formatted_value": "{0} mvts".format(cint(item.cnt)),
                    "description": _("{0} unités déplacées").format(flt(item.qty, 0)),
                    "route": {"path": "Form/Item/{0}".format(item.item_code), "label": _("Ouvrir")},
                }
                for item in (top_items or [])[:3]
            ],
            "trend": {"labels": trend_movements_labels, "values": trend_movements_values},
            "trends": {
                "movements": {
                    "label": _("Mouvements / sem."),
                    "labels": trend_movements_labels,
                    "values": trend_movements_values,
                    "type": "bar",
                },
                "outgoing": trend_outgoing,
                "incoming": trend_incoming,
            },
        },
    }


# ===========================================================================
# Module Vente
# ===========================================================================

def _sales_module(date_from, date_to, company):
    SI = frappe.qb.DocType("Sales Invoice")
    SO = frappe.qb.DocType("Sales Order")
    QT = frappe.qb.DocType("Quotation")

    # CA période courante
    q = (
        frappe.qb.from_(SI)
        .select(IfNull(Sum(SI.grand_total), 0).as_("t"), Count("*").as_("c"))
        .where(SI.posting_date >= date_from)
        .where(SI.posting_date <= date_to)
        .where(SI.docstatus == 1)
    )
    if company:
        q = q.where(SI.company == company)
    r = q.run(as_dict=True)[0]
    ca_current = flt(r.t)
    inv_count = cint(r.c)

    # CA période précédente
    pf, pt = _previous_period(date_from, date_to)
    q2 = (
        frappe.qb.from_(SI)
        .select(IfNull(Sum(SI.grand_total), 0).as_("t"))
        .where(SI.posting_date >= pf)
        .where(SI.posting_date <= pt)
        .where(SI.docstatus == 1)
    )
    if company:
        q2 = q2.where(SI.company == company)
    ca_prev = flt(q2.run(as_dict=True)[0].t)
    ca_pct = _pct_change(ca_current, ca_prev)

    # Commandes en cours
    q3 = (
        frappe.qb.from_(SO)
        .select(Count("*").as_("c"))
        .where(SO.docstatus == 1)
        .where(SO.status.notin(["Completed", "Closed", "Cancelled"]))
    )
    if company:
        q3 = q3.where(SO.company == company)
    pending_so = cint(q3.run(as_dict=True)[0].c)

    # Factures impayées
    q4 = (
        frappe.qb.from_(SI)
        .select(Count("*").as_("c"), IfNull(Sum(SI.outstanding_amount), 0).as_("t"))
        .where(SI.docstatus == 1)
        .where(SI.outstanding_amount > 0)
    )
    if company:
        q4 = q4.where(SI.company == company)
    unpaid = q4.run(as_dict=True)[0]
    unpaid_count = cint(unpaid.c)
    unpaid_amount = flt(unpaid.t)

    # Panier moyen
    avg_basket = round(ca_current / inv_count, 2) if inv_count else 0

    # Top 5 clients
    q5 = (
        frappe.qb.from_(SI)
        .select(SI.customer, SI.customer_name, IfNull(Sum(SI.grand_total), 0).as_("t"))
        .where(SI.posting_date >= date_from)
        .where(SI.posting_date <= date_to)
        .where(SI.docstatus == 1)
        .groupby(SI.customer)
        .orderby(Sum(SI.grand_total), order=frappe.qb.desc)
        .limit(5)
    )
    if company:
        q5 = q5.where(SI.company == company)
    top_customers = q5.run(as_dict=True)

    # Taux de conversion devis -> commande
    q6 = (
        frappe.qb.from_(QT)
        .select(Count("*").as_("c"))
        .where(QT.transaction_date >= date_from)
        .where(QT.transaction_date <= date_to)
        .where(QT.docstatus == 1)
    )
    if company:
        q6 = q6.where(QT.company == company)
    total_qt = cint(q6.run(as_dict=True)[0].c)

    q7 = (
        frappe.qb.from_(QT)
        .select(Count("*").as_("c"))
        .where(QT.transaction_date >= date_from)
        .where(QT.transaction_date <= date_to)
        .where(QT.docstatus == 1)
        .where(QT.status == "Ordered")
    )
    if company:
        q7 = q7.where(QT.company == company)
    conv_qt = cint(q7.run(as_dict=True)[0].c)
    conv_rate = round(conv_qt / total_qt * 100, 1) if total_qt else 0

    # Tendance CA par semaine
    trend_data = frappe.db.sql(
        """
        SELECT YEARWEEK(posting_date, 1) AS yw,
               COALESCE(SUM(grand_total), 0) AS t
        FROM `tabSales Invoice`
        WHERE posting_date BETWEEN %(f)s AND %(t)s AND docstatus = 1
              {cf}
        GROUP BY yw ORDER BY yw LIMIT 12
        """.format(cf="AND company = %(co)s" if company else ""),
        {"f": date_from, "t": date_to, "co": company},
        as_dict=True,
    )

    cf_co = "AND company = %(co)s" if company else ""
    params = {"f": date_from, "t": date_to, "co": company}
    trend_invoice_count = _weekly_series(
        _("Factures de vente"),
        f"""
        SELECT YEARWEEK(posting_date, 1) AS yw, COUNT(*) AS v
        FROM `tabSales Invoice`
        WHERE posting_date BETWEEN %(f)s AND %(t)s
          AND docstatus = 1 {cf_co}
        GROUP BY yw ORDER BY yw LIMIT 12
        """,
        params, chart_type="bar", date_from=date_from, date_to=date_to,
    )
    trend_orders = _weekly_series(
        _("Commandes clients"),
        f"""
        SELECT YEARWEEK(transaction_date, 1) AS yw, COUNT(*) AS v
        FROM `tabSales Order`
        WHERE transaction_date BETWEEN %(f)s AND %(t)s
          AND docstatus = 1 {cf_co}
        GROUP BY yw ORDER BY yw LIMIT 12
        """,
        params, chart_type="line", date_from=date_from, date_to=date_to,
    )
    trend_avg_basket = _weekly_series(
        _("Panier moyen"),
        f"""
        SELECT YEARWEEK(posting_date, 1) AS yw,
               COALESCE(AVG(grand_total), 0) AS v
        FROM `tabSales Invoice`
        WHERE posting_date BETWEEN %(f)s AND %(t)s
          AND docstatus = 1 {cf_co}
        GROUP BY yw ORDER BY yw LIMIT 12
        """,
        params, chart_type="line", date_from=date_from, date_to=date_to,
    )
    trend_revenue_labels, trend_revenue_values = _trend_fill(
        trend_data, date_from, date_to, "t"
    )

    return {
        "cards": [
            {
                "module_label": _("Vente"),
                "label": _("Chiffre d'affaires"),
                "formatted_value": _money(ca_current, company),
                "description": _("{0} vs période préc.").format(_trend_label(ca_pct)),
                "route": {"path": "List/Sales Invoice", "label": _("Factures")},
            },
        ],
        "module": {
            "label": _("Vente"),
            "color": "#2563eb",
            "is_customizable": True,
            "description": _("Panier moyen {0} | Conversion devis {1}%").format(
                _money(avg_basket, company), conv_rate
            ),
            "primary_metric": {
                "formatted_value": _money(ca_current, company),
                "route": {"path": "List/Sales Invoice", "label": _("Factures de vente")},
            },
            "stats": [
                {
                    "label": _("Évolution CA"),
                    "formatted_value": _trend_label(ca_pct),
                    "description": _("Précédent : {0}").format(_money(ca_prev, company)),
                    "route": None,
                },
                {
                    "label": _("Commandes en cours"),
                    "formatted_value": str(pending_so),
                    "description": _("Sales Orders soumis non terminés"),
                    "route": {"path": "List/Sales Order/status=%5B%22not+in%22%2C%5B%22Completed%22%2C%22Closed%22%2C%22Cancelled%22%5D%5D", "label": _("Voir")},
                },
                {
                    "label": _("Factures impayées"),
                    "formatted_value": "{0} ({1})".format(unpaid_count, _money(unpaid_amount, company)),
                    "description": _("Montant total impayé"),
                    "route": {"path": "List/Sales Invoice/outstanding_amount=%5B%22%3E%22%2C0%5D", "label": _("Voir")},
                },
                {
                    "label": _("Taux conversion devis"),
                    "formatted_value": "{0}%".format(conv_rate),
                    "description": _("{0} devis convertis sur {1}").format(conv_qt, total_qt),
                    "route": None,
                },
            ] + [
                {
                    "label": _("Top : {0}").format(c.customer_name or c.customer),
                    "formatted_value": _money(c.t, company),
                    "description": "",
                    "route": {"path": "Form/Customer/{0}".format(c.customer), "label": _("Ouvrir")},
                }
                for c in (top_customers or [])[:3]
            ],
            "trend": {"labels": trend_revenue_labels, "values": trend_revenue_values},
            "trends": {
                "revenue": {
                    "label": _("Chiffre d'affaires"),
                    "labels": trend_revenue_labels,
                    "values": trend_revenue_values,
                    "type": "line",
                },
                "invoices": trend_invoice_count,
                "orders": trend_orders,
                "avg_basket": trend_avg_basket,
            },
        },
    }


# ===========================================================================
# Module Achat
# ===========================================================================

def _purchase_module(date_from, date_to, company):
    PI = frappe.qb.DocType("Purchase Invoice")
    PO = frappe.qb.DocType("Purchase Order")

    # Total achats
    q = (
        frappe.qb.from_(PI)
        .select(IfNull(Sum(PI.grand_total), 0).as_("t"))
        .where(PI.posting_date >= date_from)
        .where(PI.posting_date <= date_to)
        .where(PI.docstatus == 1)
    )
    if company:
        q = q.where(PI.company == company)
    purch_current = flt(q.run(as_dict=True)[0].t)

    pf, pt = _previous_period(date_from, date_to)
    q2 = (
        frappe.qb.from_(PI)
        .select(IfNull(Sum(PI.grand_total), 0).as_("t"))
        .where(PI.posting_date >= pf)
        .where(PI.posting_date <= pt)
        .where(PI.docstatus == 1)
    )
    if company:
        q2 = q2.where(PI.company == company)
    purch_prev = flt(q2.run(as_dict=True)[0].t)
    purch_pct = _pct_change(purch_current, purch_prev)

    # PO en attente réception
    q3 = (
        frappe.qb.from_(PO)
        .select(Count("*").as_("c"))
        .where(PO.docstatus == 1)
        .where(PO.status.notin(["Completed", "Closed", "Cancelled", "Delivered"]))
        .where(PO.per_received < 100)
    )
    if company:
        q3 = q3.where(PO.company == company)
    pending_po = cint(q3.run(as_dict=True)[0].c)

    # Délai moyen livraison
    avg_days_r = frappe.db.sql(
        """
        SELECT AVG(DATEDIFF(pr.posting_date, po.transaction_date)) AS d
        FROM `tabPurchase Receipt` pr
        JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
        JOIN `tabPurchase Order` po ON po.name = pri.purchase_order
        WHERE pr.posting_date BETWEEN %(f)s AND %(t)s AND pr.docstatus = 1
              {cf}
        """.format(cf="AND pr.company = %(co)s" if company else ""),
        {"f": date_from, "t": date_to, "co": company},
        as_dict=True,
    )
    avg_days = round(flt(avg_days_r[0].d if avg_days_r else 0), 1)

    # Top 5 fournisseurs
    q5 = (
        frappe.qb.from_(PI)
        .select(PI.supplier, PI.supplier_name, IfNull(Sum(PI.grand_total), 0).as_("t"))
        .where(PI.posting_date >= date_from)
        .where(PI.posting_date <= date_to)
        .where(PI.docstatus == 1)
        .groupby(PI.supplier)
        .orderby(Sum(PI.grand_total), order=frappe.qb.desc)
        .limit(5)
    )
    if company:
        q5 = q5.where(PI.company == company)
    top_suppliers = q5.run(as_dict=True)

    # Factures fournisseur impayées
    q6 = (
        frappe.qb.from_(PI)
        .select(Count("*").as_("c"), IfNull(Sum(PI.outstanding_amount), 0).as_("t"))
        .where(PI.docstatus == 1)
        .where(PI.outstanding_amount > 0)
    )
    if company:
        q6 = q6.where(PI.company == company)
    up = q6.run(as_dict=True)[0]

    # Conformité réceptions
    conf_r = frappe.db.sql(
        """
        SELECT COALESCE(SUM(poi.qty), 0) AS oq, COALESCE(SUM(poi.received_qty), 0) AS rq
        FROM `tabPurchase Order Item` poi
        JOIN `tabPurchase Order` po ON po.name = poi.parent
        WHERE po.transaction_date BETWEEN %(f)s AND %(t)s AND po.docstatus = 1
              {cf}
        """.format(cf="AND po.company = %(co)s" if company else ""),
        {"f": date_from, "t": date_to, "co": company},
        as_dict=True,
    )
    conf_rate = 100.0
    if conf_r and flt(conf_r[0].oq) > 0:
        conf_rate = round(flt(conf_r[0].rq) / flt(conf_r[0].oq) * 100, 1)

    # Tendance
    trend_data = frappe.db.sql(
        """
        SELECT YEARWEEK(posting_date, 1) AS yw, COALESCE(SUM(grand_total), 0) AS t
        FROM `tabPurchase Invoice`
        WHERE posting_date BETWEEN %(f)s AND %(t)s AND docstatus = 1
              {cf}
        GROUP BY yw ORDER BY yw LIMIT 12
        """.format(cf="AND company = %(co)s" if company else ""),
        {"f": date_from, "t": date_to, "co": company},
        as_dict=True,
    )

    cf_co = "AND company = %(co)s" if company else ""
    params = {"f": date_from, "t": date_to, "co": company}
    trend_pi_count = _weekly_series(
        _("Factures fournisseur"),
        f"""
        SELECT YEARWEEK(posting_date, 1) AS yw, COUNT(*) AS v
        FROM `tabPurchase Invoice`
        WHERE posting_date BETWEEN %(f)s AND %(t)s
          AND docstatus = 1 {cf_co}
        GROUP BY yw ORDER BY yw LIMIT 12
        """,
        params, chart_type="bar", date_from=date_from, date_to=date_to,
    )
    trend_po_count = _weekly_series(
        _("Commandes d'achat"),
        f"""
        SELECT YEARWEEK(transaction_date, 1) AS yw, COUNT(*) AS v
        FROM `tabPurchase Order`
        WHERE transaction_date BETWEEN %(f)s AND %(t)s
          AND docstatus = 1 {cf_co}
        GROUP BY yw ORDER BY yw LIMIT 12
        """,
        params, chart_type="line", date_from=date_from, date_to=date_to,
    )
    trend_receipts = _weekly_series(
        _("Réceptions"),
        f"""
        SELECT YEARWEEK(posting_date, 1) AS yw, COUNT(*) AS v
        FROM `tabPurchase Receipt`
        WHERE posting_date BETWEEN %(f)s AND %(t)s
          AND docstatus = 1 {cf_co}
        GROUP BY yw ORDER BY yw LIMIT 12
        """,
        params, chart_type="line", date_from=date_from, date_to=date_to,
    )
    trend_amount_labels, trend_amount_values = _trend_fill(
        trend_data, date_from, date_to, "t"
    )

    return {
        "cards": [
            {
                "module_label": _("Achat"),
                "label": _("Total achats"),
                "formatted_value": _money(purch_current, company),
                "description": _("{0} vs période préc.").format(_trend_label(purch_pct)),
                "route": {"path": "List/Purchase Invoice", "label": _("Factures achat")},
            },
        ],
        "module": {
            "label": _("Achat"),
            "color": "#ea580c",
            "is_customizable": True,
            "description": _("Délai moyen {0}j | Conformité {1}%").format(avg_days, conf_rate),
            "primary_metric": {
                "formatted_value": _money(purch_current, company),
                "route": {"path": "List/Purchase Invoice", "label": _("Factures achat")},
            },
            "stats": [
                {
                    "label": _("Évolution achats"),
                    "formatted_value": _trend_label(purch_pct),
                    "description": _("Précédent : {0}").format(_money(purch_prev, company)),
                    "route": None,
                },
                {
                    "label": _("PO en attente réception"),
                    "formatted_value": str(pending_po),
                    "description": _("Commandes non entièrement reçues"),
                    "route": {"path": "List/Purchase Order/per_received=%5B%22%3C%22%2C100%5D", "label": _("Voir")},
                },
                {
                    "label": _("Factures fournisseur impayées"),
                    "formatted_value": "{0} ({1})".format(cint(up.c), _money(flt(up.t), company)),
                    "description": "",
                    "route": {"path": "List/Purchase Invoice/outstanding_amount=%5B%22%3E%22%2C0%5D", "label": _("Voir")},
                },
                {
                    "label": _("Délai moyen livraison"),
                    "formatted_value": "{0} jours".format(avg_days),
                    "description": _("De la commande à la réception"),
                    "route": None,
                },
            ] + [
                {
                    "label": _("Top : {0}").format(s.supplier_name or s.supplier),
                    "formatted_value": _money(s.t, company),
                    "description": "",
                    "route": {"path": "Form/Supplier/{0}".format(s.supplier), "label": _("Ouvrir")},
                }
                for s in (top_suppliers or [])[:3]
            ],
            "trend": {"labels": trend_amount_labels, "values": trend_amount_values},
            "trends": {
                "amount": {
                    "label": _("Montant achats"),
                    "labels": trend_amount_labels,
                    "values": trend_amount_values,
                    "type": "line",
                },
                "invoices": trend_pi_count,
                "orders": trend_po_count,
                "receipts": trend_receipts,
            },
        },
    }


# ===========================================================================
# Module Comptabilité
# ===========================================================================

def _accounting_module(date_from, date_to, company):
    GL = frappe.qb.DocType("GL Entry")
    Acc = frappe.qb.DocType("Account")

    # Trésorerie
    q = (
        frappe.qb.from_(GL)
        .join(Acc).on(GL.account == Acc.name)
        .select(IfNull(Sum(GL.debit - GL.credit), 0).as_("v"))
        .where(Acc.account_type.isin(["Bank", "Cash"]))
        .where(GL.is_cancelled == 0)
    )
    if company:
        q = q.where(GL.company == company)
    cash = flt(q.run(as_dict=True)[0].v)

    # Revenus
    q2 = (
        frappe.qb.from_(GL)
        .join(Acc).on(GL.account == Acc.name)
        .select(IfNull(Sum(GL.credit - GL.debit), 0).as_("v"))
        .where(Acc.root_type == "Income")
        .where(GL.posting_date >= date_from)
        .where(GL.posting_date <= date_to)
        .where(GL.is_cancelled == 0)
    )
    if company:
        q2 = q2.where(GL.company == company)
    income = flt(q2.run(as_dict=True)[0].v)

    # Dépenses
    q3 = (
        frappe.qb.from_(GL)
        .join(Acc).on(GL.account == Acc.name)
        .select(IfNull(Sum(GL.debit - GL.credit), 0).as_("v"))
        .where(Acc.root_type == "Expense")
        .where(GL.posting_date >= date_from)
        .where(GL.posting_date <= date_to)
        .where(GL.is_cancelled == 0)
    )
    if company:
        q3 = q3.where(GL.company == company)
    expense = flt(q3.run(as_dict=True)[0].v)
    net = income - expense

    # Aging AR
    ar = _compute_aging("Sales Invoice", company)
    ap = _compute_aging("Purchase Invoice", company)

    # Liquidité
    q4 = (
        frappe.qb.from_(GL)
        .join(Acc).on(GL.account == Acc.name)
        .select(IfNull(Sum(GL.debit - GL.credit), 0).as_("v"))
        .where(Acc.root_type == "Asset")
        .where(Acc.account_type.isin(["Bank", "Cash", "Receivable", "Stock"]))
        .where(GL.is_cancelled == 0)
    )
    if company:
        q4 = q4.where(GL.company == company)
    c_assets = flt(q4.run(as_dict=True)[0].v)

    q5 = (
        frappe.qb.from_(GL)
        .join(Acc).on(GL.account == Acc.name)
        .select(IfNull(Sum(GL.credit - GL.debit), 0).as_("v"))
        .where(Acc.root_type == "Liability")
        .where(GL.is_cancelled == 0)
    )
    if company:
        q5 = q5.where(GL.company == company)
    c_liab = flt(q5.run(as_dict=True)[0].v)
    liq = round(c_assets / c_liab, 2) if c_liab else 0

    # Tendance revenus par semaine
    trend_data = frappe.db.sql(
        """
        SELECT YEARWEEK(gl.posting_date, 1) AS yw,
               COALESCE(SUM(gl.credit - gl.debit), 0) AS t
        FROM `tabGL Entry` gl
        JOIN `tabAccount` a ON a.name = gl.account
        WHERE a.root_type = 'Income'
          AND gl.posting_date BETWEEN %(f)s AND %(t)s
          AND gl.is_cancelled = 0
              {cf}
        GROUP BY yw ORDER BY yw LIMIT 12
        """.format(cf="AND gl.company = %(co)s" if company else ""),
        {"f": date_from, "t": date_to, "co": company},
        as_dict=True,
    )

    cf_co = "AND gl.company = %(co)s" if company else ""
    params = {"f": date_from, "t": date_to, "co": company}
    trend_expense = _weekly_series(
        _("Charges"),
        f"""
        SELECT YEARWEEK(gl.posting_date, 1) AS yw,
               COALESCE(SUM(gl.debit - gl.credit), 0) AS v
        FROM `tabGL Entry` gl
        JOIN `tabAccount` a ON a.name = gl.account
        WHERE a.root_type = 'Expense'
          AND gl.posting_date BETWEEN %(f)s AND %(t)s
          AND gl.is_cancelled = 0 {cf_co}
        GROUP BY yw ORDER BY yw LIMIT 12
        """,
        params, chart_type="bar", date_from=date_from, date_to=date_to,
    )
    trend_cash = _weekly_series(
        _("Trésorerie"),
        f"""
        SELECT YEARWEEK(gl.posting_date, 1) AS yw,
               COALESCE(SUM(gl.debit - gl.credit), 0) AS v
        FROM `tabGL Entry` gl
        JOIN `tabAccount` a ON a.name = gl.account
        WHERE a.account_type IN ('Bank', 'Cash')
          AND gl.posting_date BETWEEN %(f)s AND %(t)s
          AND gl.is_cancelled = 0 {cf_co}
        GROUP BY yw ORDER BY yw LIMIT 12
        """,
        params, chart_type="line", date_from=date_from, date_to=date_to,
    )
    trend_income_labels, trend_income_values = _trend_fill(
        trend_data, date_from, date_to, "t"
    )
    # Résultat net par semaine = revenus - charges (alignés sur le même set de labels)
    expense_map = dict(zip(trend_expense["labels"], trend_expense["values"]))
    income_map = dict(zip(trend_income_labels, trend_income_values))
    all_labels = trend_income_labels or trend_expense["labels"]
    net_values = [
        flt(income_map.get(l, 0)) - flt(expense_map.get(l, 0)) for l in all_labels
    ]

    return {
        "cards": [
            {
                "module_label": _("Comptabilité"),
                "label": _("Trésorerie"),
                "formatted_value": _money(cash, company),
                "description": _("Résultat net : {0}").format(_money(net, company)),
                "route": {"path": "List/GL Entry", "label": _("Écritures")},
            },
        ],
        "module": {
            "label": _("Comptabilité"),
            "color": "#7c3aed",
            "is_customizable": False,
            "description": _("Liquidité {0} | AR {1} | AP {2}").format(
                liq, _money(ar["total"], company), _money(ap["total"], company)
            ),
            "primary_metric": {
                "formatted_value": _money(cash, company),
                "route": {"path": "List/GL Entry", "label": _("GL Entries")},
            },
            "stats": [
                {
                    "label": _("Résultat net"),
                    "formatted_value": _money(net, company),
                    "description": _("Revenus {0} - Dépenses {1}").format(
                        _money(income, company), _money(expense, company)
                    ),
                    "route": None,
                },
                {
                    "label": _("Créances clients (AR)"),
                    "formatted_value": _money(ar["total"], company),
                    "description": _("0-30j: {0} | 30-60j: {1} | 60-90j: {2} | >90j: {3}").format(
                        _money(ar["0_30"], company), _money(ar["30_60"], company),
                        _money(ar["60_90"], company), _money(ar["90_plus"], company),
                    ),
                    "route": {"path": "query-report/Accounts Receivable", "label": _("Détail")},
                },
                {
                    "label": _("Dettes fournisseurs (AP)"),
                    "formatted_value": _money(ap["total"], company),
                    "description": _("0-30j: {0} | 30-60j: {1} | 60-90j: {2} | >90j: {3}").format(
                        _money(ap["0_30"], company), _money(ap["30_60"], company),
                        _money(ap["60_90"], company), _money(ap["90_plus"], company),
                    ),
                    "route": {"path": "query-report/Accounts Payable", "label": _("Détail")},
                },
                {
                    "label": _("Ratio de liquidité"),
                    "formatted_value": str(liq),
                    "description": _("Actifs courants / Passifs courants"),
                    "route": None,
                },
            ],
            "trend": {"labels": trend_income_labels, "values": trend_income_values},
            "trends": {
                "income": {
                    "label": _("Revenus"),
                    "labels": trend_income_labels,
                    "values": trend_income_values,
                    "type": "line",
                },
                "expense": trend_expense,
                "net": {
                    "label": _("Résultat net"),
                    "labels": all_labels,
                    "values": net_values,
                    "type": "bar",
                },
                "cash": trend_cash,
            },
        },
    }


def _compute_aging(doctype_name, company):
    today = getdate(nowdate())
    buckets = {"total": 0, "0_30": 0, "30_60": 0, "60_90": 0, "90_plus": 0}
    filters = {"docstatus": 1, "outstanding_amount": [">", 0]}
    if company:
        filters["company"] = company
    invoices = frappe.get_all(
        doctype_name, filters=filters, fields=["posting_date", "outstanding_amount"]
    )
    for inv in invoices:
        days = (today - getdate(inv.posting_date)).days
        amt = flt(inv.outstanding_amount)
        buckets["total"] += amt
        if days <= 30:
            buckets["0_30"] += amt
        elif days <= 60:
            buckets["30_60"] += amt
        elif days <= 90:
            buckets["60_90"] += amt
        else:
            buckets["90_plus"] += amt
    for k in buckets:
        buckets[k] = round(buckets[k], 2)
    return buckets


# ===========================================================================
# Module RH / Utilisateurs
# ===========================================================================

def _hr_module(date_from, date_to, company):
    User = frappe.qb.DocType("User")

    # Utilisateurs actifs
    q = (
        frappe.qb.from_(User)
        .select(Count("*").as_("c"))
        .where(User.enabled == 1)
        .where(User.user_type == "System User")
    )
    active_users = cint(q.run(as_dict=True)[0].c)

    # Employés actifs
    emp_f = {"status": "Active"}
    if company:
        emp_f["company"] = company
    active_emp = frappe.db.count("Employee", emp_f)

    # Connectés aujourd'hui
    today = nowdate()
    q2 = (
        frappe.qb.from_(User)
        .select(User.name, User.full_name, User.last_active)
        .where(User.enabled == 1)
        .where(User.user_type == "System User")
        .where(User.last_active >= today)
        .orderby(User.last_active, order=frappe.qb.desc)
        .limit(20)
    )
    logged = q2.run(as_dict=True)

    # Répartition par rôle
    HasRole = frappe.qb.DocType("Has Role")
    q3 = (
        frappe.qb.from_(HasRole)
        .join(User).on(HasRole.parent == User.name)
        .select(HasRole.role, Count("*").as_("c"))
        .where(User.enabled == 1)
        .where(User.user_type == "System User")
        .groupby(HasRole.role)
        .orderby(Count("*"), order=frappe.qb.desc)
        .limit(10)
    )
    roles = q3.run(as_dict=True)

    # Congés en attente
    pending_leaves = 0
    if frappe.db.exists("DocType", "Leave Application"):
        lf = {"status": "Open", "docstatus": 0}
        if company:
            lf["company"] = company
        pending_leaves = frappe.db.count("Leave Application", lf)

    # Tendances RH (présences, absences, congés) si les doctypes existent
    cf_co = "AND company = %(co)s" if company else ""
    params = {"f": date_from, "t": date_to, "co": company}

    trend_attendance = {"label": _("Présences"), "labels": [], "values": [], "type": "line"}
    trend_absences = {"label": _("Absences"), "labels": [], "values": [], "type": "bar"}
    if frappe.db.exists("DocType", "Attendance"):
        trend_attendance = _weekly_series(
            _("Présences"),
            f"""
            SELECT YEARWEEK(attendance_date, 1) AS yw, COUNT(*) AS v
            FROM `tabAttendance`
            WHERE attendance_date BETWEEN %(f)s AND %(t)s
              AND status = 'Present' AND docstatus = 1 {cf_co}
            GROUP BY yw ORDER BY yw LIMIT 12
            """,
            params, chart_type="line", date_from=date_from, date_to=date_to,
        )
        trend_absences = _weekly_series(
            _("Absences"),
            f"""
            SELECT YEARWEEK(attendance_date, 1) AS yw, COUNT(*) AS v
            FROM `tabAttendance`
            WHERE attendance_date BETWEEN %(f)s AND %(t)s
              AND status = 'Absent' AND docstatus = 1 {cf_co}
            GROUP BY yw ORDER BY yw LIMIT 12
            """,
            params, chart_type="bar", date_from=date_from, date_to=date_to,
        )

    trend_leaves = {"label": _("Congés"), "labels": [], "values": [], "type": "line"}
    if frappe.db.exists("DocType", "Leave Application"):
        trend_leaves = _weekly_series(
            _("Congés"),
            f"""
            SELECT YEARWEEK(from_date, 1) AS yw, COUNT(*) AS v
            FROM `tabLeave Application`
            WHERE from_date BETWEEN %(f)s AND %(t)s
              AND docstatus = 1 {cf_co}
            GROUP BY yw ORDER BY yw LIMIT 12
            """,
            params, chart_type="line", date_from=date_from, date_to=date_to,
        )

    # Évolution effectif : nouvelles arrivées par semaine
    trend_headcount = {"label": _("Effectif (arrivées)"), "labels": [], "values": [], "type": "bar"}
    if frappe.db.exists("DocType", "Employee"):
        trend_headcount = _weekly_series(
            _("Arrivées"),
            f"""
            SELECT YEARWEEK(date_of_joining, 1) AS yw, COUNT(*) AS v
            FROM `tabEmployee`
            WHERE date_of_joining BETWEEN %(f)s AND %(t)s
              AND status = 'Active' {cf_co}
            GROUP BY yw ORDER BY yw LIMIT 12
            """,
            params, chart_type="bar", date_from=date_from, date_to=date_to,
        )

    return {
        "cards": [
            {
                "module_label": _("RH"),
                "label": _("Utilisateurs actifs"),
                "formatted_value": str(active_users),
                "description": _("{0} employés | {1} connectés aujourd'hui").format(
                    active_emp, len(logged)
                ),
                "route": {"path": "List/User", "label": _("Utilisateurs")},
            },
        ],
        "module": {
            "label": _("RH / Utilisateurs"),
            "color": "#be185d",
            "is_customizable": False,
            "description": _("{0} congés en attente").format(pending_leaves),
            "primary_metric": {
                "formatted_value": "{0} utilisateurs".format(active_users),
                "route": {"path": "List/User", "label": _("Utilisateurs")},
            },
            "stats": [
                {
                    "label": _("Employés actifs"),
                    "formatted_value": str(active_emp),
                    "description": "",
                    "route": {"path": "List/Employee/status=Active", "label": _("Voir")},
                },
                {
                    "label": _("Connectés aujourd'hui"),
                    "formatted_value": str(len(logged)),
                    "description": ", ".join(
                        [(u.full_name or u.name) for u in (logged or [])[:5]]
                    ) or _("Aucun"),
                    "route": None,
                },
                {
                    "label": _("Congés en attente"),
                    "formatted_value": str(pending_leaves),
                    "description": _("Demandes à approuver"),
                    "route": {"path": "List/Leave Application/status=Open", "label": _("Voir")} if pending_leaves else None,
                },
            ] + [
                {
                    "label": _("Rôle : {0}").format(r.role),
                    "formatted_value": str(cint(r.c)),
                    "description": "",
                    "route": None,
                }
                for r in (roles or [])[:4]
            ],
            "trend": {
                "labels": [(u.full_name or u.name)[:8] for u in (logged or [])[:8]],
                "values": [1 for _ in (logged or [])[:8]],
            },
            "trends": {
                "headcount": trend_headcount,
                "attendance": trend_attendance,
                "absences": trend_absences,
                "leaves": trend_leaves,
            },
        },
    }


# ===========================================================================
# Graphique global CA 12 mois
# ===========================================================================

def _build_revenue_chart(company):
    SI = frappe.qb.DocType("Sales Invoice")
    today = getdate(nowdate())
    labels = []
    values = []

    for i in range(11, -1, -1):
        ms = add_months(today.replace(day=1), -i)
        me = add_days(add_months(ms, 1), -1) if i > 0 else today
        q = (
            frappe.qb.from_(SI)
            .select(IfNull(Sum(SI.grand_total), 0).as_("t"))
            .where(SI.posting_date >= str(ms))
            .where(SI.posting_date <= str(me))
            .where(SI.docstatus == 1)
        )
        if company:
            q = q.where(SI.company == company)
        v = flt(q.run(as_dict=True)[0].t)
        labels.append(formatdate(str(ms), "MMM YY"))
        values.append(round(v, 2))

    if not any(values):
        return None

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": _("Chiffre d'affaires"), "values": values}],
        },
        "type": "bar",
        "height": 180,
        "colors": ["#2563eb"],
        "axisOptions": {"xIsSeries": True},
    }
