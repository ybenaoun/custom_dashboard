# -*- coding: utf-8 -*-
# Module: VENTE API - Read-Only Endpoints pour Chatbot ERPNext
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
# 1. COMMANDES DE VENTE
# ═══════════════════════════════════════════════════════════

def get_sales_order_status(order_id=None, limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Sales Order', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les commandes de vente.')}

        filters = {'docstatus': ['!=', 2]}
        if order_id:
            order_id = str(order_id).strip()
            if not frappe.db.exists('Sales Order', order_id):
                return {'error': 'not_found', 'message': _('Commande introuvable : {0}').format(order_id)}
            filters['name'] = order_id

        items = frappe.get_all('Sales Order',
            filters=filters,
            fields=['name', 'customer', 'transaction_date', 'status', 'grand_total'],
            order_by='transaction_date desc',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Sales Order', filters=filters)

        return {
            'data_type': 'sales_order_status',
            'currency': _get_currency(),
            'company': _get_company(),
            'count': len(items),
            'orders': items,
            'query_params': {
                'doctype': 'Sales Order',
                'filters': filters,
                'fields': ['name', 'customer', 'transaction_date', 'status', 'grand_total'],
                'order_by': 'transaction_date desc',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'sales_order_status',
                'currency': _get_currency()
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_sales_order_status')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_sales_order_status')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_sales_orders_for_customer(customer_id=None, limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Sales Order', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les commandes de vente.')}

        if not customer_id or not str(customer_id).strip():
            return {'error': 'missing_parameter', 'message': _('Identifiant client obligatoire.')}

        customer_id = str(customer_id).strip()
        if not frappe.db.exists('Customer', customer_id):
            return {'error': 'not_found', 'message': _('Client introuvable : {0}').format(customer_id)}

        filters = {'customer': customer_id}
        items = frappe.get_all('Sales Order',
            filters=filters,
            fields=['name', 'transaction_date', 'status', 'grand_total'],
            order_by='transaction_date desc',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Sales Order', filters=filters)

        return {
            'data_type': 'sales_orders_customer',
            'currency': _get_currency(),
            'company': _get_company(),
            'customer': customer_id,
            'count': len(items),
            'orders': items,
            'query_params': {
                'doctype': 'Sales Order',
                'filters': filters,
                'fields': ['name', 'transaction_date', 'status', 'grand_total'],
                'order_by': 'transaction_date desc',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'sales_orders_customer',
                'currency': _get_currency(),
                'customer': customer_id
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_sales_orders_for_customer')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_sales_orders_for_customer')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_sales_invoice_status(invoice_id=None, limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Sales Invoice', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les factures de vente.')}

        filters = {'docstatus': 1}
        if invoice_id:
            invoice_id = str(invoice_id).strip()
            if not frappe.db.exists('Sales Invoice', invoice_id):
                return {'error': 'not_found', 'message': _('Facture introuvable : {0}').format(invoice_id)}
            filters['name'] = invoice_id

        items = frappe.get_all('Sales Invoice',
            filters=filters,
            fields=['name', 'customer', 'posting_date', 'status', 'grand_total', 'outstanding_amount'],
            order_by='posting_date desc',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Sales Invoice', filters=filters)

        return {
            'data_type': 'sales_invoice_status',
            'currency': _get_currency(),
            'company': _get_company(),
            'count': len(items),
            'invoices': items,
            'query_params': {
                'doctype': 'Sales Invoice',
                'filters': filters,
                'fields': ['name', 'customer', 'posting_date', 'status', 'grand_total', 'outstanding_amount'],
                'order_by': 'posting_date desc',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'sales_invoice_status',
                'currency': _get_currency()
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_sales_invoice_status')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_sales_invoice_status')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_sales_invoices_for_customer(customer_id=None, limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Sales Invoice', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les factures de vente.')}

        if not customer_id or not str(customer_id).strip():
            return {'error': 'missing_parameter', 'message': _('Identifiant client obligatoire.')}

        customer_id = str(customer_id).strip()
        if not frappe.db.exists('Customer', customer_id):
            return {'error': 'not_found', 'message': _('Client introuvable : {0}').format(customer_id)}

        filters = {'customer': customer_id, 'docstatus': 1}
        items = frappe.get_all('Sales Invoice',
            filters=filters,
            fields=['name', 'posting_date', 'status', 'grand_total', 'outstanding_amount'],
            order_by='posting_date desc',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Sales Invoice', filters=filters)
        total_invoiced = sum(flt(i['grand_total']) for i in items)
        total_outstanding = sum(flt(i['outstanding_amount']) for i in items)

        return {
            'data_type': 'sales_invoices_customer',
            'currency': _get_currency(),
            'company': _get_company(),
            'customer': customer_id,
            'count': len(items),
            'total_invoiced': total_invoiced,
            'total_outstanding': total_outstanding,
            'invoices': items,
            'query_params': {
                'doctype': 'Sales Invoice',
                'filters': filters,
                'fields': ['name', 'posting_date', 'status', 'grand_total', 'outstanding_amount'],
                'order_by': 'posting_date desc',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'sales_invoices_customer',
                'currency': _get_currency(),
                'customer': customer_id
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_sales_invoices_for_customer')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_sales_invoices_for_customer')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_customer_info(customer_id=None):
    try:
        if not frappe.has_permission('Customer', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les clients.')}

        if not customer_id or not str(customer_id).strip():
            return {'error': 'missing_parameter', 'message': _('Identifiant client obligatoire.')}

        customer_id = str(customer_id).strip()
        if not frappe.db.exists('Customer', customer_id):
            return {'error': 'not_found', 'message': _('Client introuvable : {0}').format(customer_id)}

        doc = frappe.get_doc('Customer', customer_id)

        data = {
            'customer_id': doc.name,
            'customer_name': doc.customer_name,
            'email': doc.email_id,
            'phone': doc.mobile_no,
            'customer_group': doc.customer_group,
            'territory': doc.territory,
            'is_active': not doc.disabled,
            'tax_id': doc.tax_id
        }

        return {
            'data_type': 'customer_info',
            'currency': _get_currency(),
            'company': _get_company(),
            'customer': data
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_customer_info')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_customer_info')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_sales_summary(from_date=None, to_date=None, limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Sales Invoice', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les factures de vente.')}

        filters = {'docstatus': 1}
        if from_date and to_date:
            filters['posting_date'] = ['between', [from_date, to_date]]
        elif from_date:
            filters['posting_date'] = ['>=', from_date]
        elif to_date:
            filters['posting_date'] = ['<=', to_date]

        items = frappe.get_all('Sales Invoice',
            filters=filters,
            fields=['name', 'customer', 'posting_date', 'grand_total', 'outstanding_amount'],
            order_by='posting_date desc',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Sales Invoice', filters=filters)
        total_sales = sum(flt(i['grand_total']) for i in items)
        total_outstanding = sum(flt(i['outstanding_amount']) for i in items)

        return {
            'data_type': 'sales_summary',
            'currency': _get_currency(),
            'company': _get_company(),
            'count': len(items),
            'total_sales': total_sales,
            'total_outstanding': total_outstanding,
            'from_date': from_date,
            'to_date': to_date,
            'invoices': items,
            'query_params': {
                'doctype': 'Sales Invoice',
                'filters': filters,
                'fields': ['name', 'customer', 'posting_date', 'grand_total', 'outstanding_amount'],
                'order_by': 'posting_date desc',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'sales_summary',
                'currency': _get_currency(),
                'from_date': from_date,
                'to_date': to_date
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_sales_summary')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_sales_summary')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_payment_status(invoice_id=None, limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Payment Entry', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les paiements.')}

        if not invoice_id or not str(invoice_id).strip():
            return {'error': 'missing_parameter', 'message': _('Référence de facture obligatoire.')}

        invoice_id = str(invoice_id).strip()
        if not frappe.db.exists("Sales Invoice", invoice_id):
            return {"error": "not_found", "message": _("Facture introuvable")}

        refs = frappe.get_all('Payment Entry Reference',
            filters={'reference_name': invoice_id, 'reference_doctype': 'Sales Invoice'},
            fields=['parent'])

        if not refs:
            return {
                'data_type': 'sales_payment_status',
                'currency': _get_currency(),
                'company': _get_company(),
                'invoice_id': invoice_id,
                'count': 0,
                'total_paid': 0,
                'message': _('Aucun paiement trouvé pour cette facture.'),
                'payments': []
            }

        pe_names = [r['parent'] for r in refs]
        filters = {'name': ['in', pe_names], 'docstatus': 1}
        payments = frappe.get_all('Payment Entry',
            filters=filters,
            fields=['name', 'paid_amount', 'posting_date', 'payment_type', 'party'],
            order_by='posting_date desc',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Payment Entry', filters=filters)
        total_paid = sum(flt(p['paid_amount']) for p in payments)

        return {
            'data_type': 'sales_payment_status',
            'currency': _get_currency(),
            'company': _get_company(),
            'invoice_id': invoice_id,
            'count': len(payments),
            'total_paid': total_paid,
            'payments': payments,
            'query_params': {
                'doctype': 'Payment Entry',
                'filters': filters,
                'fields': ['name', 'paid_amount', 'posting_date', 'payment_type', 'party'],
                'order_by': 'posting_date desc',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'sales_payment_status',
                'currency': _get_currency(),
                'invoice_id': invoice_id
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_payment_status')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_payment_status')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_discount_for_order(order_id=None):
    try:
        if not frappe.has_permission('Sales Order', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les commandes de vente.')}

        if not order_id or not str(order_id).strip():
            return {'error': 'missing_parameter', 'message': _('Référence de commande obligatoire.')}

        order_id = str(order_id).strip()
        if not frappe.db.exists('Sales Order', order_id):
            return {'error': 'not_found', 'message': _('Commande introuvable : {0}').format(order_id)}

        doc = frappe.get_doc('Sales Order', order_id)

        data = {
            'order_id': doc.name,
            'customer': doc.customer,
            'grand_total': flt(doc.grand_total),
            'discount_amount': flt(doc.discount_amount),
            'discount_percentage': flt(doc.additional_discount_percentage)
        }

        return {
            'data_type': 'order_discount',
            'currency': _get_currency(),
            'company': _get_company(),
            'discount': data
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_discount_for_order')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_discount_for_order')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_cancelled_orders(from_date=None, to_date=None, limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Sales Order', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les commandes de vente.')}

        filters = {'status': 'Cancelled'}
        if from_date and to_date:
            filters['transaction_date'] = ['between', [from_date, to_date]]
        elif from_date:
            filters['transaction_date'] = ['>=', from_date]
        elif to_date:
            filters['transaction_date'] = ['<=', to_date]

        items = frappe.get_all('Sales Order',
            filters=filters,
            fields=['name', 'customer', 'transaction_date', 'status', 'grand_total'],
            order_by='transaction_date desc',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Sales Order', filters=filters)

        return {
            'data_type': 'cancelled_orders',
            'currency': _get_currency(),
            'company': _get_company(),
            'count': len(items),
            'from_date': from_date,
            'to_date': to_date,
            'orders': items,
            'query_params': {
                'doctype': 'Sales Order',
                'filters': filters,
                'fields': ['name', 'customer', 'transaction_date', 'status', 'grand_total'],
                'order_by': 'transaction_date desc',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'cancelled_orders',
                'currency': _get_currency(),
                'from_date': from_date,
                'to_date': to_date
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_cancelled_orders')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_cancelled_orders')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 2. DEVIS ET COMMANDES EN RETARD
# ═══════════════════════════════════════════════════════════

def get_quotations_for_customer(customer_id=None, limit_start=0, limit_page_length=20):
    try:
        if not customer_id or not str(customer_id).strip():
            return {'error': 'missing_parameter', 'message': _("L'identifiant client est obligatoire.")}

        if not frappe.has_permission('Quotation', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les devis.')}

        customer_id = str(customer_id).strip()
        if not frappe.db.exists('Customer', customer_id):
            return {'error': 'not_found', 'message': _('Client introuvable : {0}').format(customer_id)}

        filters = {'party_name': customer_id, 'quotation_to': 'Customer'}
        quotations = frappe.get_all('Quotation',
            filters=filters,
            fields=['name', 'transaction_date', 'grand_total', 'status', 'valid_till', 'currency'],
            order_by='transaction_date desc',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Quotation', filters=filters)

        return {
            'data_type': 'quotations_for_customer',
            'currency': _get_currency(),
            'company': _get_company(),
            'customer': customer_id,
            'count': len(quotations),
            'quotations': quotations,
            'query_params': {
                'doctype': 'Quotation',
                'filters': filters,
                'fields': ['name', 'transaction_date', 'grand_total', 'status', 'valid_till', 'currency'],
                'order_by': 'transaction_date desc',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'quotations_for_customer',
                'currency': _get_currency(),
                'customer': customer_id
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_quotations_for_customer')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_quotations_for_customer')
        return {'error': 'internal_error', 'message': _('Erreur interne')}


def get_delayed_sales_orders(limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Sales Order', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les commandes de vente.')}

        today = getdate()
        filters = {
            'docstatus': 1,
            'delivery_date': ['<', today],
            'status': ['not in', ['Completed', 'Cancelled', 'Closed']]
        }
        orders = frappe.get_all('Sales Order',
            filters=filters,
            fields=['name', 'customer', 'customer_name', 'delivery_date',
                    'grand_total', 'status', 'per_delivered'],
            order_by='delivery_date ASC',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        for order in orders:
            delivery = getdate(order['delivery_date'])
            order['days_delayed'] = (today - delivery).days

        total_count = frappe.db.count('Sales Order', filters=filters)

        return {
            'data_type': 'delayed_sales_orders',
            'currency': _get_currency(),
            'company': _get_company(),
            'reference_date': str(today),
            'count': len(orders),
            'orders': orders,
            'query_params': {
                'doctype': 'Sales Order',
                'filters': filters,
                'fields': ['name', 'customer', 'customer_name', 'delivery_date', 'grand_total', 'status', 'per_delivered'],
                'order_by': 'delivery_date ASC',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'delayed_sales_orders',
                'currency': _get_currency()
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_delayed_sales_orders')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_delayed_sales_orders')
        return {'error': 'internal_error', 'message': _('Erreur interne')}


# ═══════════════════════════════════════════════════════════
# DISPATCHER (sans wrapper status)
# ═══════════════════════════════════════════════════════════

def fetch_sales_data(intent, from_date=None, to_date=None, entity=None, limit_start=0, limit_page_length=20):
    if intent == 'sales_order_status':
        return get_sales_order_status(entity, limit_start, limit_page_length)
    if intent == 'sales_orders_customer':
        return get_sales_orders_for_customer(entity, limit_start, limit_page_length)
    if intent == 'quotations_for_customer':
        return get_quotations_for_customer(entity, limit_start, limit_page_length)
    if intent == 'delayed_sales_orders':
        return get_delayed_sales_orders(limit_start, limit_page_length)
    if intent == 'sales_invoice_status':
        return get_sales_invoice_status(entity, limit_start, limit_page_length)
    if intent == 'sales_invoices_customer':
        return get_sales_invoices_for_customer(entity, limit_start, limit_page_length)
    if intent == 'customer_info':
        return get_customer_info(entity)
    if intent == 'sales_summary':
        return get_sales_summary(from_date, to_date, limit_start, limit_page_length)
    if intent == 'sales_payment_status':
        return get_payment_status(entity, limit_start, limit_page_length)
    if intent == 'order_discount':
        return get_discount_for_order(entity)
    if intent == 'cancelled_orders':
        return get_cancelled_orders(from_date, to_date, limit_start, limit_page_length)
    return {'error': 'unknown_intent', 'message': _('Intent inconnu : {0}').format(intent)}