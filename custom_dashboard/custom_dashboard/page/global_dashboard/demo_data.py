# -*- coding: utf-8 -*-
"""
Script de génération de données démo pour le tableau de bord global.

Usage :
    bench --site erpnext.localhost execute custom_dashboard.custom_dashboard.page.global_dashboard.demo_data.create_demo_data

Pour supprimer :
    bench --site erpnext.localhost execute custom_dashboard.custom_dashboard.page.global_dashboard.demo_data.delete_demo_data
"""

import random
import math
import frappe
from frappe.utils import nowdate, add_days, add_months, getdate, today
from datetime import timedelta, date as _date


COMPANY = "Tunisan United Solutions"
ABBR = "TUS"
CURRENCY = "TND"
WAREHOUSE = "Magasins - TUS"
COST_CENTER = "Principal - TUS"
INCOME_ACCOUNT = "Ventes - TUS"
EXPENSE_ACCOUNT = "Coût des marchandises vendues - TUS"
RECEIVABLE_ACCOUNT = "Débiteurs - TUS"
PAYABLE_ACCOUNT = "Créditeurs - TUS"
CASH_ACCOUNT = "Espèces - TUS"
STOCK_ACCOUNT = "Stock Existant - TUS"

PREFIX = "DEMO"

# Facteur de croissance mensuel simulé (index 0 = il y a 11 mois, 11 = mois courant)
GROWTH_CURVE = [0.55, 0.60, 0.62, 0.68, 0.72, 0.78, 0.82, 0.88, 0.93, 0.97, 1.02, 1.10]


# ===========================================================================
# Helpers
# ===========================================================================

def _spread_dates(date_from, date_to, n):
    """Retourne n dates réparties uniformément entre date_from et date_to (inclus)."""
    f = getdate(date_from)
    t = getdate(date_to)
    delta = (t - f).days
    if delta <= 0:
        return [str(f)] * n
    step = delta / max(n - 1, 1)
    dates = []
    for i in range(n):
        d = f + timedelta(days=round(step * i))
        if d > t:
            d = t
        dates.append(str(d))
    return dates


def _weekly_dates(date_from, date_to, per_week=2):
    """Retourne des dates couvrant chaque semaine ISO de la période, per_week dates/semaine."""
    f = getdate(date_from)
    t = getdate(date_to)
    result = []
    monday = f - timedelta(days=f.weekday())
    while monday <= t:
        week_start = max(f, monday)
        week_end = min(t, monday + timedelta(days=6))
        if week_start <= week_end:
            span = (week_end - week_start).days
            for _ in range(per_week):
                offset = random.randint(0, span)
                d = week_start + timedelta(days=offset)
                result.append(str(d))
        monday += timedelta(weeks=1)
    return result


_FY_CACHE = None

def _in_active_fy(dt):
    """Returns True if dt falls within an active Fiscal Year (cached)."""
    global _FY_CACHE
    if _FY_CACHE is None:
        _FY_CACHE = frappe.db.sql(
            "SELECT year_start_date, year_end_date FROM `tabFiscal Year` WHERE disabled=0 ORDER BY year_start_date",
            as_dict=True,
        )
    d = getdate(dt)
    return any(getdate(r.year_start_date) <= d <= getdate(r.year_end_date) for r in _FY_CACHE)


def _growth_factor(month_offset_from_now):
    """Facteur multiplicatif selon le mois (0 = mois courant, 11 = il y a 11 mois)."""
    idx = max(0, min(11, 11 - month_offset_from_now))
    base = GROWTH_CURVE[idx]
    return base * random.uniform(0.88, 1.12)


# ===========================================================================
# Master data
# ===========================================================================

def _ensure_warehouse():
    if not frappe.db.exists("Warehouse", WAREHOUSE):
        frappe.get_doc({
            "doctype": "Warehouse",
            "warehouse_name": "Magasins",
            "company": COMPANY,
            "parent_warehouse": f"Tous les entrepôts - {ABBR}",
        }).insert()
        print(f"  Entrepôt '{WAREHOUSE}' créé")


def _create_items():
    print("\n[1/10] Création des articles...")
    items_data = [
        ("DEMO-ITEM-001", "Écran LED 24 pouces",        "Products",      450, 15),
        ("DEMO-ITEM-002", "Clavier mécanique RGB",       "Products",      120, 30),
        ("DEMO-ITEM-003", "Souris sans fil Pro",         "Products",       65, 50),
        ("DEMO-ITEM-004", "Câble HDMI 2m",               "Consumable",     18, 100),
        ("DEMO-ITEM-005", "Hub USB-C 7 ports",           "Products",       85, 25),
        ("DEMO-ITEM-006", "SSD NVMe 1TB",                "Products",      280, 20),
        ("DEMO-ITEM-007", "RAM DDR5 16GB",               "Raw Material",  190, 40),
        ("DEMO-ITEM-008", "Ventilateur PC 120mm",        "Sub Assemblies", 25, 60),
        ("DEMO-ITEM-009", "Boîtier ATX Gaming",          "Products",      210, 10),
        ("DEMO-ITEM-010", "Alimentation 750W",           "Products",      145, 18),
        ("DEMO-ITEM-011", "Webcam HD 1080p",             "Products",       95, 35),
        ("DEMO-ITEM-012", "Casque audio Bluetooth",      "Products",      175, 22),
        ("DEMO-ITEM-013", "Tapis de souris XL",          "Consumable",     35, 80),
        ("DEMO-ITEM-014", "Support écran réglable",      "Products",      110, 12),
        ("DEMO-ITEM-015", "Station d'accueil USB-C",     "Products",      320,  8),
        ("DEMO-ITEM-016", "Imprimante laser A4",         "Products",      590, 10),
        ("DEMO-ITEM-017", "Scanner portable",            "Products",      230, 14),
        ("DEMO-ITEM-018", "Routeur WiFi 6",              "Products",      310, 16),
        ("DEMO-ITEM-019", "Onduleur 1000VA",             "Products",      420, 12),
        ("DEMO-ITEM-020", "Tablette graphique A5",       "Products",      260, 20),
        ("DEMO-ITEM-021", "Câble réseau Cat6 5m",        "Consumable",     22, 200),
        ("DEMO-ITEM-022", "Disque dur externe 2TB",      "Products",      195, 30),
        ("DEMO-ITEM-023", "Lecteur de cartes USB",       "Consumable",     28, 75),
        ("DEMO-ITEM-024", "Projecteur HD 3000 lm",       "Products",     1200,  5),
        ("DEMO-ITEM-025", "Enceinte Bluetooth portable", "Products",      145, 20),
    ]

    items = []
    for code, name, group, rate, safety_stock in items_data:
        if frappe.db.exists("Item", code):
            items.append(code)
            continue
        doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": code,
            "item_name": name,
            "item_group": group,
            "stock_uom": "Nos",
            "is_stock_item": 1,
            "valuation_rate": rate * 0.6,
            "standard_rate": rate,
            "safety_stock": safety_stock,
            "opening_stock": 0,
            "item_defaults": [{
                "company": COMPANY,
                "default_warehouse": WAREHOUSE,
                "income_account": INCOME_ACCOUNT,
                "expense_account": EXPENSE_ACCOUNT,
                "buying_cost_center": COST_CENTER,
                "selling_cost_center": COST_CENTER,
            }],
        })
        doc.insert()
        items.append(code)

    print(f"  {len(items)} articles prêts")
    return items


CUSTOMER_NAMES = [
    "TechnoPlus SARL", "Méditerranée Digital", "Atlas Informatique",
    "Sahara Connect", "Carthage Systems", "Bardo Electronics",
    "Sousse IT Solutions", "Djerba NetWorks", "Tunis DataCenter",
    "Nabeul Tech", "Sfax Informatique Pro", "Bizerte Office Systems",
]

SUPPLIER_NAMES = [
    "Global Tech Supplies", "MicroChip Distribution", "EuroComponents SARL",
    "Asia Parts Import", "Maghreb Hardware", "TechImport Pro",
    "Delta Electronics", "Méditerranée Composants",
]


def _create_customers():
    print("\n[2/10] Création des clients...")
    customers = []
    for name in CUSTOMER_NAMES:
        existing = frappe.db.exists("Customer", {"customer_name": name})
        if existing:
            customers.append(existing)
            continue
        doc = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": name,
            "customer_type": "Company",
            "customer_group": frappe.db.get_single_value("Selling Settings", "customer_group") or "All Customer Groups",
            "territory": frappe.db.get_single_value("Selling Settings", "territory") or "All Territories",
            "default_currency": CURRENCY,
        })
        doc.insert()
        customers.append(doc.name)

    print(f"  {len(customers)} clients prêts")
    return customers


def _create_suppliers():
    print("\n[3/10] Création des fournisseurs...")
    suppliers = []
    for name in SUPPLIER_NAMES:
        existing = frappe.db.exists("Supplier", {"supplier_name": name})
        if existing:
            suppliers.append(existing)
            continue
        doc = frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": name,
            "supplier_type": "Company",
            "supplier_group": frappe.db.get_single_value("Buying Settings", "supplier_group") or "All Supplier Groups",
            "default_currency": CURRENCY,
        })
        doc.insert()
        suppliers.append(doc.name)

    print(f"  {len(suppliers)} fournisseurs prêts")
    return suppliers


def _create_employees():
    print("\n[4/10] Création des employés...")
    employees_data = [
        ("Ahmed",    "Ben Ali",    "1990-05-15", "Sales"),
        ("Fatma",    "Trabelsi",   "1988-09-22", "Accounts"),
        ("Mohamed",  "Bouazizi",   "1992-03-10", "Engineering"),
        ("Leila",    "Mansouri",   "1995-11-03", "Human Resources"),
        ("Karim",    "Jebali",     "1987-07-28", "Sales"),
        ("Sonia",    "Belhadj",    "1991-02-14", "Accounts"),
        ("Yassine",  "Hamdi",      "1993-08-05", "Engineering"),
        ("Nadia",    "Gharbi",     "1989-12-20", "Human Resources"),
    ]

    employees = []
    for first, last, dob, dept in employees_data:
        existing = frappe.db.exists("Employee", {"employee_name": f"{first} {last}", "company": COMPANY})
        if existing:
            employees.append(existing)
            continue

        if not frappe.db.exists("Department", f"{dept} - {ABBR}"):
            if not frappe.db.exists("Department", dept):
                frappe.get_doc({
                    "doctype": "Department",
                    "department_name": dept,
                    "company": COMPANY,
                }).insert()

        doc = frappe.get_doc({
            "doctype": "Employee",
            "first_name": first,
            "last_name": last,
            "employee_name": f"{first} {last}",
            "date_of_birth": dob,
            "date_of_joining": "2024-01-15",
            "gender": "Male" if first in ("Ahmed", "Mohamed", "Karim", "Yassine") else "Female",
            "company": COMPANY,
            "status": "Active",
        })
        doc.insert()
        employees.append(doc.name)

    print(f"  {len(employees)} employés prêts")
    return employees


# ===========================================================================
# Transactions — helpers partagés
# ===========================================================================

def _item_rate(item_code):
    return frappe.db.get_value("Item", item_code, "standard_rate") or 100


def _item_cost(item_code):
    return (frappe.db.get_value("Item", item_code, "valuation_rate") or 60) * random.uniform(0.9, 1.1)


def _selling_price_list():
    return frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"


def _buying_price_list():
    return frappe.db.get_single_value("Buying Settings", "buying_price_list") or "Standard Buying"


# ===========================================================================
# Stock entries — 1 réception par semaine sur 12 mois
# ===========================================================================

def _create_stock_entries(items):
    print("\n[5/10] Création des mouvements de stock...")
    count = 0
    t = getdate(today())

    for month_offset in range(11, -1, -1):
        ms = add_months(t.replace(day=1), -month_offset)
        me_raw = add_days(add_months(ms, 1), -1)
        me = min(getdate(me_raw), t)
        gf = _growth_factor(month_offset)

        # Réceptions hebdomadaires : 1-2 par semaine
        dates = _weekly_dates(str(ms), str(me), per_week=random.randint(1, 2))
        for dt in dates:
            selected = random.sample(items, min(random.randint(4, 8), len(items)))
            se = frappe.get_doc({
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "posting_date": dt,
                "company": COMPANY,
                "items": [
                    {
                        "item_code": item,
                        "qty": max(1, int(random.randint(10, 60) * gf)),
                        "t_warehouse": WAREHOUSE,
                        "basic_rate": _item_cost(item),
                        "cost_center": COST_CENTER,
                    }
                    for item in selected
                ],
            })
            try:
                se.insert()
                se.submit()
                count += 1
            except Exception as e:
                print(f"  ⚠ Stock Entry skip: {str(e)[:80]}")

    print(f"  {count} entrées de stock créées")


# ===========================================================================
# Devis — 2-3 par semaine sur 6 mois
# ===========================================================================

def _create_quotations(items, customers):
    print("\n[6/10] Création des devis...")
    count = 0
    t = getdate(today())

    for month_offset in range(5, -1, -1):
        ms = add_months(t.replace(day=1), -month_offset)
        me = min(getdate(add_days(add_months(ms, 1), -1)), t)
        gf = _growth_factor(month_offset)

        dates = _weekly_dates(str(ms), str(me), per_week=random.randint(2, 3))
        for dt in dates:
            customer = random.choice(customers)
            selected = random.sample(items, random.randint(1, 5))
            qt = frappe.get_doc({
                "doctype": "Quotation",
                "quotation_to": "Customer",
                "party_name": customer,
                "transaction_date": dt,
                "valid_till": str(add_days(dt, 30)),
                "company": COMPANY,
                "order_type": "Sales",
                "selling_price_list": _selling_price_list(),
                "items": [
                    {
                        "item_code": item,
                        "qty": max(1, int(random.randint(1, 12) * gf)),
                        "rate": _item_rate(item),
                        "warehouse": WAREHOUSE,
                    }
                    for item in selected
                ],
            })
            try:
                qt.insert()
                qt.submit()
                count += 1
            except Exception as e:
                print(f"  ⚠ Quotation skip: {str(e)[:80]}")

    print(f"  {count} devis créés")


# ===========================================================================
# Commandes client — 2-3 par semaine sur 6 mois
# ===========================================================================

def _create_sales_orders(items, customers):
    print("\n[7/10] Création des commandes client...")
    count = 0
    t = getdate(today())

    for month_offset in range(5, -1, -1):
        ms = add_months(t.replace(day=1), -month_offset)
        me = min(getdate(add_days(add_months(ms, 1), -1)), t)
        gf = _growth_factor(month_offset)

        dates = _weekly_dates(str(ms), str(me), per_week=random.randint(2, 3))
        for dt in dates:
            customer = random.choice(customers)
            selected = random.sample(items, random.randint(1, 5))
            so = frappe.get_doc({
                "doctype": "Sales Order",
                "customer": customer,
                "transaction_date": dt,
                "delivery_date": str(add_days(dt, random.randint(7, 30))),
                "company": COMPANY,
                "order_type": "Sales",
                "selling_price_list": _selling_price_list(),
                "items": [
                    {
                        "item_code": item,
                        "qty": max(1, int(random.randint(1, 8) * gf)),
                        "rate": _item_rate(item),
                        "warehouse": WAREHOUSE,
                        "delivery_date": str(add_days(dt, random.randint(7, 30))),
                    }
                    for item in selected
                ],
            })
            try:
                so.insert()
                so.submit()
                count += 1
            except Exception as e:
                print(f"  ⚠ Sales Order skip: {str(e)[:80]}")

    print(f"  {count} commandes client créées")


# ===========================================================================
# Factures de vente — 3-5 par semaine sur 12 mois (volume élevé pour graphiques)
# ===========================================================================

def _create_sales_invoices(items, customers):
    print("\n[8/10] Création des factures de vente...")
    count = 0
    t = getdate(today())

    for month_offset in range(11, -1, -1):
        ms = add_months(t.replace(day=1), -month_offset)
        me = min(getdate(add_days(add_months(ms, 1), -1)), t)
        gf = _growth_factor(month_offset)

        # Densité variable selon la saison simulée
        seasonal = 1.0 + 0.25 * math.sin(math.pi * (11 - month_offset) / 6)
        per_week = max(2, int(round(random.randint(3, 5) * seasonal)))

        dates = _weekly_dates(str(ms), str(me), per_week=per_week)
        for dt in dates:
            if not _in_active_fy(dt):
                continue
            customer = random.choice(customers)
            selected = random.sample(items, random.randint(1, 6))
            si = frappe.get_doc({
                "doctype": "Sales Invoice",
                "customer": customer,
                "posting_date": dt,
                "set_posting_time": 1,
                "due_date": dt,
                "payment_terms_template": "",
                "company": COMPANY,
                "debit_to": RECEIVABLE_ACCOUNT,
                "selling_price_list": _selling_price_list(),
                "update_stock": 0,
                "items": [
                    {
                        "item_code": item,
                        "qty": max(1, int(random.randint(1, 10) * gf)),
                        "rate": _item_rate(item) * random.uniform(0.95, 1.08),
                        "income_account": INCOME_ACCOUNT,
                        "expense_account": EXPENSE_ACCOUNT,
                        "cost_center": COST_CENTER,
                    }
                    for item in selected
                ],
            })
            try:
                si.insert()
                si.submit()
                count += 1

                # 75 % des factures sont payées
                if random.random() < 0.75:
                    try:
                        from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
                        pe = get_payment_entry("Sales Invoice", si.name)
                        pe.reference_no = f"PAY-{si.name}"
                        pe.reference_date = str(add_days(dt, random.randint(3, 25)))
                        pe.paid_to = CASH_ACCOUNT
                        pe.insert()
                        pe.submit()
                    except Exception:
                        pass

            except Exception as e:
                print(f"  ⚠ Sales Invoice skip: {str(e)[:80]}")

    print(f"  {count} factures de vente créées")


# ===========================================================================
# Commandes & factures fournisseur — 2-4 par semaine sur 12 mois
# ===========================================================================

def _create_purchase_orders(items, suppliers):
    print("\n[9/10] Création des commandes fournisseur et réceptions...")
    po_count = 0
    pr_count = 0
    t = getdate(today())

    for month_offset in range(11, -1, -1):
        ms = add_months(t.replace(day=1), -month_offset)
        me = min(getdate(add_days(add_months(ms, 1), -1)), t)
        gf = _growth_factor(month_offset)

        dates = _weekly_dates(str(ms), str(me), per_week=random.randint(2, 3))
        for dt in dates:
            supplier = random.choice(suppliers)
            selected = random.sample(items, random.randint(2, 6))
            po = frappe.get_doc({
                "doctype": "Purchase Order",
                "supplier": supplier,
                "transaction_date": dt,
                "schedule_date": str(add_days(dt, random.randint(7, 21))),
                "company": COMPANY,
                "buying_price_list": _buying_price_list(),
                "items": [
                    {
                        "item_code": item,
                        "qty": max(1, int(random.randint(5, 35) * gf)),
                        "rate": _item_cost(item),
                        "warehouse": WAREHOUSE,
                        "schedule_date": str(add_days(dt, random.randint(7, 21))),
                        "cost_center": COST_CENTER,
                        "expense_account": EXPENSE_ACCOUNT,
                    }
                    for item in selected
                ],
            })
            try:
                po.insert()
                po.submit()
                po_count += 1

                # Réception pour 65 % des PO
                if random.random() < 0.65:
                    pr_date = str(min(getdate(add_days(dt, random.randint(5, 20))), t))
                    pr = frappe.get_doc({
                        "doctype": "Purchase Receipt",
                        "supplier": supplier,
                        "posting_date": pr_date,
                        "company": COMPANY,
                        "buying_price_list": _buying_price_list(),
                        "items": [
                            {
                                "item_code": row.item_code,
                                "qty": row.qty,
                                "rate": row.rate,
                                "warehouse": WAREHOUSE,
                                "purchase_order": po.name,
                                "purchase_order_item": row.name,
                                "cost_center": COST_CENTER,
                                "expense_account": EXPENSE_ACCOUNT,
                            }
                            for row in po.items
                        ],
                    })
                    try:
                        pr.insert()
                        pr.submit()
                        pr_count += 1
                    except Exception:
                        pass

            except Exception as e:
                print(f"  ⚠ Purchase Order skip: {str(e)[:80]}")

    print(f"  {po_count} commandes fournisseur, {pr_count} réceptions créées")


def _create_purchase_receipts(items, suppliers):
    """Incluses dans _create_purchase_orders."""
    pass


def _create_purchase_invoices(items, suppliers):
    print("\n[10/10] Création des factures d'achat...")
    count = 0
    t = getdate(today())

    for month_offset in range(11, -1, -1):
        ms = add_months(t.replace(day=1), -month_offset)
        me = min(getdate(add_days(add_months(ms, 1), -1)), t)
        gf = _growth_factor(month_offset)

        dates = _weekly_dates(str(ms), str(me), per_week=random.randint(2, 4))
        for dt in dates:
            if not _in_active_fy(dt):
                continue
            supplier = random.choice(suppliers)
            selected = random.sample(items, random.randint(1, 5))
            pi = frappe.get_doc({
                "doctype": "Purchase Invoice",
                "supplier": supplier,
                "posting_date": dt,
                "set_posting_time": 1,
                "bill_date": dt,
                "bill_no": f"DEMO-{dt}-{random.randint(1000,9999)}",
                "due_date": dt,
                "payment_terms_template": "",
                "company": COMPANY,
                "credit_to": PAYABLE_ACCOUNT,
                "buying_price_list": _buying_price_list(),
                "update_stock": 1,
                "set_warehouse": WAREHOUSE,
                "items": [
                    {
                        "item_code": item,
                        "qty": max(1, int(random.randint(3, 25) * gf)),
                        "rate": _item_cost(item),
                        "warehouse": WAREHOUSE,
                        "expense_account": EXPENSE_ACCOUNT,
                        "cost_center": COST_CENTER,
                    }
                    for item in selected
                ],
            })
            try:
                pi.insert()
                pi.submit()
                count += 1

                # 55 % des factures achat sont payées
                if random.random() < 0.55:
                    try:
                        from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
                        pe = get_payment_entry("Purchase Invoice", pi.name)
                        pe.reference_no = f"PAY-{pi.name}"
                        pe.reference_date = str(add_days(dt, random.randint(10, 40)))
                        pe.paid_from = CASH_ACCOUNT
                        pe.insert()
                        pe.submit()
                    except Exception:
                        pass

            except Exception as e:
                print(f"  ⚠ Purchase Invoice skip: {str(e)[:80]}")

    print(f"  {count} factures d'achat créées")


# ===========================================================================
# Congés
# ===========================================================================

def _create_leave_applications(employees):
    if not employees or not frappe.db.exists("DocType", "Leave Application"):
        return

    print("\n[Bonus] Création des demandes de congé...")
    leave_types = frappe.get_all("Leave Type", fields=["name"], limit=1)
    if not leave_types:
        return

    leave_type = leave_types[0].name
    t = getdate(today())
    count = 0

    for emp in employees[:5]:
        try:
            from_d = add_days(t, random.randint(3, 20))
            la = frappe.get_doc({
                "doctype": "Leave Application",
                "employee": emp,
                "leave_type": leave_type,
                "from_date": str(from_d),
                "to_date": str(add_days(from_d, random.randint(2, 10))),
                "status": "Open",
                "company": COMPANY,
            })
            la.insert()
            count += 1
        except Exception as e:
            print(f"  ⚠ Leave Application skip: {str(e)[:80]}")

    print(f"  {count} demandes de congé créées")


# ===========================================================================
# Point d'entrée
# ===========================================================================

def create_demo_data():
    """Crée toutes les données démo."""
    frappe.flags.ignore_permissions = True
    frappe.flags.mute_emails = True

    print("=" * 60)
    print("Création des données démo pour le dashboard global")
    print("=" * 60)

    _ensure_warehouse()
    items     = _create_items()
    customers = _create_customers()
    suppliers = _create_suppliers()
    employees = _create_employees()

    _create_stock_entries(items)
    _create_quotations(items, customers)
    _create_sales_orders(items, customers)
    _create_sales_invoices(items, customers)
    _create_purchase_orders(items, suppliers)
    _create_purchase_receipts(items, suppliers)
    _create_purchase_invoices(items, suppliers)
    _create_leave_applications(employees)

    frappe.db.commit()
    print("\n" + "=" * 60)
    print("Données démo créées avec succès !")
    print("Accédez à /app/global-dashboard pour voir le résultat.")
    print("=" * 60)


# ===========================================================================
# Suppression
# ===========================================================================

def delete_demo_data():
    """Supprime toutes les données démo."""
    frappe.flags.ignore_permissions = True
    print("Suppression des données démo...")

    for dt in [
        "Payment Entry",
        "Purchase Invoice",
        "Purchase Receipt",
        "Purchase Order",
        "Sales Invoice",
        "Sales Order",
        "Quotation",
        "Stock Entry",
        "Leave Application",
    ]:
        if not frappe.db.exists("DocType", dt):
            continue
        docs = frappe.get_all(
            dt,
            filters={"company": COMPANY, "docstatus": ["in", [0, 1]]},
            fields=["name", "docstatus"],
            order_by="creation desc",
        )
        for doc in docs:
            try:
                d = frappe.get_doc(dt, doc.name)
                is_demo = False

                if hasattr(d, "items"):
                    for row in d.items:
                        if hasattr(row, "item_code") and row.item_code and "DEMO" in row.item_code:
                            is_demo = True
                            break
                if hasattr(d, "customer") and d.customer and d.customer in CUSTOMER_NAMES:
                    is_demo = True
                if hasattr(d, "supplier") and d.supplier and d.supplier in SUPPLIER_NAMES:
                    is_demo = True
                if hasattr(d, "employee") and d.employee:
                    emp_name = frappe.db.get_value("Employee", d.employee, "employee_name") or ""
                    if emp_name in (
                        "Ahmed Ben Ali", "Fatma Trabelsi", "Mohamed Bouazizi",
                        "Leila Mansouri", "Karim Jebali", "Sonia Belhadj",
                        "Yassine Hamdi", "Nadia Gharbi",
                    ):
                        is_demo = True

                if not is_demo:
                    continue

                if d.docstatus == 1:
                    d.cancel()
                d.delete()
            except Exception:
                pass

        if docs:
            print(f"  {dt}: traité")

    DEMO_EMP_NAMES = [
        "Ahmed Ben Ali", "Fatma Trabelsi", "Mohamed Bouazizi",
        "Leila Mansouri", "Karim Jebali", "Sonia Belhadj",
        "Yassine Hamdi", "Nadia Gharbi",
    ]

    for dt, flt in [
        ("Item",     {"name": ["like", "DEMO-ITEM%"]}),
        ("Customer", {"customer_name": ["in", CUSTOMER_NAMES]}),
        ("Supplier", {"supplier_name": ["in", SUPPLIER_NAMES]}),
        ("Employee", {"employee_name": ["in", DEMO_EMP_NAMES]}),
    ]:
        docs = frappe.get_all(dt, filters=flt)
        for doc in docs:
            try:
                frappe.delete_doc(dt, doc.name, force=True)
            except Exception:
                pass
        if docs:
            print(f"  {dt}: {len(docs)} supprimés")

    frappe.db.commit()
    print("Données démo supprimées.")
