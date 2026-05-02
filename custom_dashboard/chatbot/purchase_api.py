# -*- coding: utf-8 -*-
# Module: PURCHASE API - Read-Only Endpoints pour Chatbot ERPNext
# Sécurité: LECTURE SEULE — Aucune opération d'écriture autorisée
# Format retour: uniformisé avec accounting_api (pas de wrapper "status")
# Pagination V3: ajout de query_params, limit_start, limit_page_length

import frappe
from frappe import _
from frappe.utils import flt, getdate

def _get_company():
    return frappe.defaults.get_global_default('company') or 'Tunisian United Solutions (Demo)'

def _get_currency():
    return frappe.db.get_value('Company', _get_company(), 'default_currency') or 'TND'


# ═══════════════════════════════════════════════════════════
# 1. DEMANDES D'ACHAT (MATERIAL REQUESTS)
# ═══════════════════════════════════════════════════════════

def get_material_request_status(request_id=None):
    try:
        if not request_id or not str(request_id).strip():
            return {'error': 'missing_parameter', 'message': _('Référence de demande obligatoire.')}

        if not frappe.has_permission('Material Request', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les demandes d\'achat.')}

        request_id = str(request_id).strip()
        if not frappe.db.exists('Material Request', request_id):
            return {'error': 'not_found', 'message': _('Demande introuvable : {0}').format(request_id)}

        mr = frappe.get_doc('Material Request', request_id)

        data = {
            'name': mr.name,
            'material_request_type': mr.material_request_type,
            'transaction_date': str(mr.transaction_date),
            'status': mr.status,
            'per_ordered': flt(mr.per_ordered),
            'per_received': flt(mr.per_received),
            'workflow_state': mr.get('workflow_state') or 'Pas de workflow',
            'items': [
                {'item_code': d.item_code, 'qty': flt(d.qty), 'uom': d.uom}
                for d in mr.items
            ]
        }

        return {
            'data_type': 'material_request_status',
            'currency': _get_currency(),
            'company': _get_company(),
            'request': data
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_material_request_status')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_material_request_status')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_my_pending_material_requests(limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Material Request', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les demandes de matériel.')}

        session_user = frappe.session.user

        requests = frappe.db.sql("""
            SELECT name, material_request_type, transaction_date,
                   status, schedule_date, title, docstatus, owner
            FROM `tabMaterial Request`
            WHERE
                owner = %(user)s
                AND (
                    docstatus = 0
                    OR (docstatus = 1 AND status IN ('Pending', 'Partially Ordered'))
                )
            ORDER BY transaction_date DESC
            LIMIT %(limit_start)s, %(limit_page_length)s
        """, {
            'user': session_user,
            'limit_start': limit_start,
            'limit_page_length': limit_page_length
        }, as_dict=True)

        # Compter le total pour la pagination
        total_count = frappe.db.sql("""
            SELECT COUNT(*) as total
            FROM `tabMaterial Request`
            WHERE
                owner = %(user)s
                AND (
                    docstatus = 0
                    OR (docstatus = 1 AND status IN ('Pending', 'Partially Ordered'))
                )
        """, {'user': session_user})[0][0]

        # Enrichissement avec les items enfants
        result = []
        for mr in requests:
            items = frappe.get_all(
                'Material Request Item',
                filters={'parent': mr['name']},
                fields=['item_code', 'item_name', 'qty', 'uom', 'warehouse', 'description']
            )
            mr_dict = dict(mr)
            mr_dict['items'] = items
            result.append(mr_dict)

        return {
            'data_type': 'my_pending_material_requests',
            'currency': _get_currency(),
            'company': _get_company(),
            'user': session_user,
            'count': len(result),
            'requests': result,
            'query_params': {
                'doctype': 'Material Request',
                'filters': {
                    'owner': session_user,
                    'docstatus': ['in', [0, 1]],
                    'status': ['in', ['Pending', 'Partially Ordered']]
                },
                'fields': ['name', 'material_request_type', 'transaction_date', 'status', 'schedule_date', 'title', 'docstatus', 'owner'],
                'order_by': 'transaction_date DESC',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'my_pending_material_requests',
                'currency': _get_currency(),
                'user': session_user
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_my_pending_material_requests')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_my_pending_material_requests')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 2. BONS DE COMMANDE (PURCHASE ORDERS)
# ═══════════════════════════════════════════════════════════

def get_purchase_order_tracking(purchase_order=None):
    try:
        if not purchase_order or not str(purchase_order).strip():
            return {'error': 'missing_parameter', 'message': _('Référence du bon de commande obligatoire.')}

        if not frappe.has_permission('Purchase Order', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les bons de commande.')}

        purchase_order = str(purchase_order).strip()
        if not frappe.db.exists('Purchase Order', purchase_order):
            return {'error': 'not_found', 'message': _('Bon de commande introuvable : {0}').format(purchase_order)}

        po = frappe.get_doc('Purchase Order', purchase_order)

        data = {
            'name': po.name,
            'supplier': po.supplier,
            'status': po.status,
            'grand_total': flt(po.base_grand_total),
            'order_currency': po.currency,
            'delivery_date': str(po.schedule_date) if po.schedule_date else None,
            'per_received': flt(po.per_received),
            'is_received': 'Oui' if flt(po.per_received) == 100 else f'{flt(po.per_received):.1f}%',
            'per_billed': flt(po.per_billed),
            'is_billed': 'Oui' if flt(po.per_billed) == 100 else f'{flt(po.per_billed):.1f}%',
            'contact': po.contact_display
        }

        return {
            'data_type': 'purchase_order_tracking',
            'currency': _get_currency(),
            'company': _get_company(),
            'order': data
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_purchase_order_tracking')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_purchase_order_tracking')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_delayed_orders(limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Purchase Order', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les bons de commande.')}

        today = getdate()
        filters = {
            'docstatus': 1,
            'status': ['not in', ['Completed', 'Closed', 'Cancelled']],
            'schedule_date': ['<', today]
        }
        items = frappe.get_all('Purchase Order',
            filters=filters,
            fields=['name', 'supplier', 'schedule_date', 'grand_total', 'status'],
            order_by='schedule_date ASC',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Purchase Order', filters=filters)
        total_amount = sum(flt(i['grand_total']) for i in items)

        return {
            'data_type': 'delayed_orders',
            'currency': _get_currency(),
            'company': _get_company(),
            'count': len(items),
            'total_amount': total_amount,
            'orders': items,
            'query_params': {
                'doctype': 'Purchase Order',
                'filters': filters,
                'fields': ['name', 'supplier', 'schedule_date', 'grand_total', 'status'],
                'order_by': 'schedule_date ASC',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'delayed_orders',
                'currency': _get_currency()
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_delayed_orders')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_delayed_orders')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 3. FOURNISSEURS
# ═══════════════════════════════════════════════════════════

def get_supplier_details(supplier_name=None):
    try:
        if not supplier_name or not str(supplier_name).strip():
            return {'error': 'missing_parameter', 'message': _('Nom du fournisseur obligatoire.')}

        if not frappe.has_permission('Supplier', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les fournisseurs.')}

        supplier_name = str(supplier_name).strip()
        if not frappe.db.exists('Supplier', supplier_name):
            return {'error': 'not_found', 'message': _('Fournisseur inconnu : {0}').format(supplier_name)}

        sup = frappe.get_doc('Supplier', supplier_name)

        data = {
            'name': sup.name,
            'supplier_name': sup.supplier_name,
            'supplier_group': sup.supplier_group,
            'status': 'Bloqué' if sup.is_frozen else 'Actif',
            'payment_terms': sup.payment_terms,
            'tax_id': sup.tax_id,
            'website': sup.website
        }

        return {
            'data_type': 'supplier_details',
            'currency': _get_currency(),
            'company': _get_company(),
            'supplier': data
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_supplier_details')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_supplier_details')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 4. ANALYSE DES PRIX
# ═══════════════════════════════════════════════════════════

def get_last_purchase_price(item_code=None):
    try:
        if not item_code or not str(item_code).strip():
            return {'error': 'missing_parameter', 'message': _('Code article obligatoire.')}

        if not frappe.has_permission('Purchase Order', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les bons de commande.')}

        item_code = str(item_code).strip()

        last_price = frappe.get_all('Purchase Order Item',
            filters={'item_code': item_code, 'docstatus': 1},
            fields=['base_rate', 'parent', 'creation'],
            order_by='creation desc',
            limit=1)

        if not last_price:
            return {
                'data_type': 'last_purchase_price',
                'currency': _get_currency(),
                'company': _get_company(),
                'item_code': item_code,
                'message': _('Aucun historique d\'achat pour cet article.')
            }

        return {
            'data_type': 'last_purchase_price',
            'currency': _get_currency(),
            'company': _get_company(),
            'item_code': item_code,
            'last_price': flt(last_price[0].base_rate),
            'order_ref': last_price[0].parent,
            'date': str(last_price[0].creation)
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_last_purchase_price')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_last_purchase_price')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 5. RÉCEPTIONS ET FACTURES
# ═══════════════════════════════════════════════════════════

def get_pending_receipts(limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Purchase Order', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les bons de commande.')}

        filters = {'docstatus': 1, 'per_received': ['>', 0], 'per_billed': ['<', 100]}
        items = frappe.get_all('Purchase Order',
            filters=filters,
            fields=['name', 'supplier', 'per_received', 'per_billed'],
            order_by='name',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Purchase Order', filters=filters)

        return {
            'data_type': 'pending_receipts',
            'currency': _get_currency(),
            'company': _get_company(),
            'count': len(items),
            'orders': items,
            'query_params': {
                'doctype': 'Purchase Order',
                'filters': filters,
                'fields': ['name', 'supplier', 'per_received', 'per_billed'],
                'order_by': 'name',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'pending_receipts',
                'currency': _get_currency()
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_pending_receipts')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_pending_receipts')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_unpaid_invoices(supplier=None, limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Purchase Invoice', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les factures fournisseurs.')}

        filters = {'docstatus': 1, 'status': ['in', ['Unpaid', 'Partly Paid']]}
        if supplier:
            filters['supplier'] = str(supplier).strip()

        invoices = frappe.get_all('Purchase Invoice',
            filters=filters,
            fields=['name', 'supplier', 'due_date', 'outstanding_amount', 'grand_total'],
            order_by='due_date ASC',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Purchase Invoice', filters=filters)
        total_outstanding = sum(flt(i['outstanding_amount']) for i in invoices)

        return {
            'data_type': 'purchase_unpaid_invoices',
            'currency': _get_currency(),
            'company': _get_company(),
            'count': len(invoices),
            'total_outstanding': total_outstanding,
            'invoices': invoices,
            'query_params': {
                'doctype': 'Purchase Invoice',
                'filters': filters,
                'fields': ['name', 'supplier', 'due_date', 'outstanding_amount', 'grand_total'],
                'order_by': 'due_date ASC',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'purchase_unpaid_invoices',
                'currency': _get_currency()
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_unpaid_invoices')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_unpaid_invoices')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 6. STATISTIQUES D'ACHAT
# ═══════════════════════════════════════════════════════════

def get_purchase_stats_current_year(limit_start=0, limit_page_length=12):
    try:
        if not frappe.has_permission('Purchase Invoice', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les factures fournisseurs.')}

        user_roles = set(frappe.get_roles(frappe.session.user))
        if not (user_roles & {'Purchase Manager', 'Accounts Manager', 'System Manager', 'Administrator'}):
            return {'error': 'insufficient_roles', 'message': _('Droits insuffisants pour les statistiques globales.')}

        data = frappe.db.sql("""
            SELECT MONTH(posting_date) AS month, SUM(base_grand_total) AS total
            FROM `tabPurchase Invoice`
            WHERE docstatus = 1 AND YEAR(posting_date) = YEAR(CURDATE())
            GROUP BY MONTH(posting_date)
            ORDER BY month
            LIMIT %(limit_start)s, %(limit_page_length)s
        """, {
            'limit_start': limit_start,
            'limit_page_length': limit_page_length
        }, as_dict=True)

        total_count = len(frappe.db.sql("""
            SELECT DISTINCT MONTH(posting_date) as month
            FROM `tabPurchase Invoice`
            WHERE docstatus = 1 AND YEAR(posting_date) = YEAR(CURDATE())
        """, as_dict=True))

        return {
            'data_type': 'purchase_stats_year',
            'currency': _get_currency(),
            'company': _get_company(),
            'count': len(data),
            'monthly_stats': data,
            'query_params': {
                'doctype': 'Purchase Invoice',
                'filters': {'docstatus': 1, 'posting_date': ['like', f'{getdate().year}%']},
                'group_by': 'MONTH(posting_date)',
                'fields': ['MONTH(posting_date) as month', 'SUM(base_grand_total) as total'],
                'order_by': 'month',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'purchase_stats_year',
                'currency': _get_currency()
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_purchase_stats_current_year')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_purchase_stats_current_year')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# DISPATCHER (sans wrapper status)
# ═══════════════════════════════════════════════════════════

def fetch_purchase_data(intent, from_date=None, to_date=None, entity=None, limit_start=0, limit_page_length=20):
    if intent == 'material_request_status':
        return get_material_request_status(entity)
    if intent == 'my_pending_material_requests':
        return get_my_pending_material_requests(limit_start, limit_page_length)
    if intent == 'purchase_order_tracking':
        return get_purchase_order_tracking(entity)
    if intent == 'delayed_orders':
        return get_delayed_orders(limit_start, limit_page_length)
    if intent == 'supplier_details':
        return get_supplier_details(entity)
    if intent == 'last_purchase_price':
        return get_last_purchase_price(entity)
    if intent == 'pending_receipts':
        return get_pending_receipts(limit_start, limit_page_length)
    if intent == 'purchase_unpaid_invoices':
        return get_unpaid_invoices(entity, limit_start, limit_page_length)
    if intent == 'purchase_stats_year':
        return get_purchase_stats_current_year(limit_start, limit_page_length)
    return {'error': 'unknown_intent', 'message': _('Intent inconnu : {0}').format(intent)}