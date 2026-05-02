# -*- coding: utf-8 -*-
"""
Patch : ajouter des factures de vente et d'achat supplémentaires.
Usage : bench --site erpnext.localhost execute custom_dashboard.custom_dashboard.page.global_dashboard.patch_invoices.run
"""

import random
import frappe
from frappe.utils import getdate, add_days, add_months, today, flt


def run():
    frappe.flags.ignore_permissions = True
    frappe.flags.mute_emails = True

    COMPANY = "Tunisan United Solutions"
    WAREHOUSE = "Magasins - TUS"
    COST_CENTER = "Principal - TUS"
    INCOME_ACCOUNT = "Ventes - TUS"
    EXPENSE_ACCOUNT = "Coût des marchandises vendues - TUS"
    RECEIVABLE_ACCOUNT = "Débiteurs - TUS"
    PAYABLE_ACCOUNT = "Créditeurs - TUS"
    CASH_ACCOUNT = "Espèces - TUS"

    items = frappe.get_all("Item", filters={"name": ["like", "DEMO-ITEM%"]}, pluck="name")
    customers = frappe.get_all("Customer", filters={"name": ["like", "DEMO-CUST%"]}, pluck="name")
    suppliers = frappe.get_all("Supplier", filters={"name": ["like", "DEMO-SUPP%"]}, pluck="name")

    if not items:
        # Fallback : prendre tous les items
        items = frappe.get_all("Item", filters={"disabled": 0, "is_stock_item": 1}, pluck="name", limit=15)
    if not customers:
        customers = frappe.get_all("Customer", pluck="name", limit=8)
    if not suppliers:
        suppliers = frappe.get_all("Supplier", pluck="name", limit=5)

    print(f"Items: {len(items)}, Customers: {len(customers)}, Suppliers: {len(suppliers)}")

    if not items or not customers or not suppliers:
        print("Pas assez de données master. Lancez d'abord create_demo_data.")
        return

    t = getdate(today())
    si_count = 0
    pi_count = 0

    # --- Factures de vente (jan 2026 -> aujourd'hui) ---
    print("Création des factures de vente...")
    for month_offset in range(3, -1, -1):
        base = add_months(t.replace(day=1), -month_offset)
        if base < getdate("2026-01-01"):
            base = getdate("2026-01-01")

        nb = random.randint(8, 14)
        for i in range(nb):
            day = random.randint(1, 28)
            dt = base.replace(day=day)
            if dt > t:
                dt = t
            if dt < getdate("2026-01-01"):
                dt = getdate("2026-01-01")

            customer = random.choice(customers)
            sel_items = random.sample(items, min(random.randint(1, 4), len(items)))
            due = add_days(dt, 45)

            try:
                si = frappe.get_doc({
                    "doctype": "Sales Invoice",
                    "customer": customer,
                    "posting_date": str(dt),
                    "due_date": str(due),
                    "company": COMPANY,
                    "debit_to": RECEIVABLE_ACCOUNT,
                    "update_stock": 1,
                    "set_warehouse": WAREHOUSE,
                    "items": [
                        {
                            "item_code": item,
                            "qty": random.randint(1, 8),
                            "rate": frappe.db.get_value("Item", item, "standard_rate") or 100,
                            "warehouse": WAREHOUSE,
                            "income_account": INCOME_ACCOUNT,
                            "expense_account": EXPENSE_ACCOUNT,
                            "cost_center": COST_CENTER,
                        }
                        for item in sel_items
                    ],
                })
                si.insert()
                si.submit()
                si_count += 1

                # Payer 60% des factures
                if random.random() < 0.6:
                    try:
                        from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
                        pe = get_payment_entry("Sales Invoice", si.name)
                        pe.reference_no = "PAY-" + si.name
                        pe.reference_date = str(add_days(dt, random.randint(5, 20)))
                        pe.paid_to = CASH_ACCOUNT
                        pe.insert()
                        pe.submit()
                    except Exception:
                        pass
            except Exception as e:
                err = str(e)[:60]
                if "Insufficient" not in err:
                    print(f"  SI skip: {err}")

    print(f"  {si_count} factures de vente créées")

    # --- Factures d'achat (jan 2026 -> aujourd'hui) ---
    print("Création des factures d'achat...")
    for month_offset in range(3, -1, -1):
        base = add_months(t.replace(day=1), -month_offset)
        if base < getdate("2026-01-01"):
            base = getdate("2026-01-01")

        nb = random.randint(5, 10)
        for i in range(nb):
            day = random.randint(1, 28)
            dt = base.replace(day=day)
            if dt > t:
                dt = t
            if dt < getdate("2026-01-01"):
                dt = getdate("2026-01-01")

            supplier = random.choice(suppliers)
            sel_items = random.sample(items, min(random.randint(1, 3), len(items)))
            due = add_days(dt, 60)

            try:
                pi = frappe.get_doc({
                    "doctype": "Purchase Invoice",
                    "supplier": supplier,
                    "posting_date": str(dt),
                    "due_date": str(due),
                    "company": COMPANY,
                    "credit_to": PAYABLE_ACCOUNT,
                    "update_stock": 1,
                    "set_warehouse": WAREHOUSE,
                    "items": [
                        {
                            "item_code": item,
                            "qty": random.randint(3, 15),
                            "rate": (frappe.db.get_value("Item", item, "valuation_rate") or 60) * random.uniform(0.9, 1.1),
                            "warehouse": WAREHOUSE,
                            "expense_account": EXPENSE_ACCOUNT,
                            "cost_center": COST_CENTER,
                        }
                        for item in sel_items
                    ],
                })
                pi.insert()
                pi.submit()
                pi_count += 1

                # Payer 40%
                if random.random() < 0.4:
                    try:
                        from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
                        pe = get_payment_entry("Purchase Invoice", pi.name)
                        pe.reference_no = "PAY-" + pi.name
                        pe.reference_date = str(add_days(dt, random.randint(10, 30)))
                        pe.paid_from = CASH_ACCOUNT
                        pe.insert()
                        pe.submit()
                    except Exception:
                        pass
            except Exception as e:
                err = str(e)[:60]
                print(f"  PI skip: {err}")

    print(f"  {pi_count} factures d'achat créées")

    frappe.db.commit()
    print(f"\nTotal: {si_count} SI + {pi_count} PI créés avec succès.")
