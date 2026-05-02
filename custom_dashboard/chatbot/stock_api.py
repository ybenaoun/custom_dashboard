# -*- coding: utf-8 -*-
# Module: STOCK API - Read-Only Endpoints pour Chatbot ERPNext
# Sécurité: LECTURE SEULE — Aucune opération d'écriture autorisée
# Format retour: uniformisé avec accounting_api (pas de wrapper "status")
# Pagination V3: ajout de query_params, limit_start, limit_page_length

import frappe
from frappe import _
from frappe.utils import flt, getdate, add_days

def _get_company():
    return frappe.defaults.get_global_default('company') or 'Tunisian United Solutions (Demo)'

def _get_currency():
    return frappe.db.get_value('Company', _get_company(), 'default_currency') or 'TND'

STOCK_ROLES = {'Stock Manager', 'Stock User', 'System Manager', 'Administrator'}
STOCK_MANAGER_ROLES = {'Stock Manager', 'System Manager', 'Administrator'}


# ═══════════════════════════════════════════════════════════
# 1. DISPONIBILITÉ ET NIVEAUX DE STOCK
# ═══════════════════════════════════════════════════════════

def get_item_availability(item_code=None, warehouse=None):
    try:
        if not item_code or not str(item_code).strip():
            return {'error': 'missing_parameter', 'message': _('Code article obligatoire.')}

        if not frappe.has_permission('Item', 'read', item_code):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur cet article.')}

        item_code = str(item_code).strip()
        filters = {'item_code': item_code}
        if warehouse:
            filters['warehouse'] = str(warehouse).strip()

        bin_data = frappe.get_all('Bin',
            filters=filters,
            fields=['warehouse', 'actual_qty', 'reserved_qty', 'ordered_qty', 'projected_qty'])

        if not bin_data:
            return {
                'data_type': 'stock_availability',
                'currency': _get_currency(),
                'company': _get_company(),
                'item_code': item_code,
                'message': _('Aucune donnée de stock pour cet article.'),
                'warehouses': []
            }

        return {
            'data_type': 'stock_availability',
            'currency': _get_currency(),
            'company': _get_company(),
            'item_code': item_code,
            'total_actual': sum(flt(d.actual_qty) for d in bin_data),
            'total_reserved': sum(flt(d.reserved_qty) for d in bin_data),
            'total_projected': sum(flt(d.projected_qty) for d in bin_data),
            'count': len(bin_data),
            'warehouses': bin_data
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_item_availability')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_item_availability')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_out_of_stock_items(warehouse=None, limit_start=0, limit_page_length=20):
    try:
        user_roles = set(frappe.get_roles(frappe.session.user))
        if not (user_roles & STOCK_ROLES):
            return {'error': 'permission_denied', 'message': _('Accès refusé — rôle Stock requis.')}

        filters = {'projected_qty': ['<=', 0]}
        if warehouse:
            filters['warehouse'] = str(warehouse).strip()

        items = frappe.get_all('Bin',
            filters=filters,
            fields=['item_code', 'warehouse', 'actual_qty', 'projected_qty'],
            order_by='item_code',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Bin', filters=filters)

        return {
            'data_type': 'out_of_stock_items',
            'currency': _get_currency(),
            'company': _get_company(),
            'count': len(items),
            'items': items,
            'query_params': {
                'doctype': 'Bin',
                'filters': filters,
                'fields': ['item_code', 'warehouse', 'actual_qty', 'projected_qty'],
                'order_by': 'item_code',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'out_of_stock_items',
                'currency': _get_currency()
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_out_of_stock_items')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_out_of_stock_items')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 2. MOUVEMENTS ET HISTORIQUE
# ═══════════════════════════════════════════════════════════

def get_stock_history(item_code=None, limit_start=0, limit_page_length=20):
    try:
        if not item_code or not str(item_code).strip():
            return {'error': 'missing_parameter', 'message': _('Code article obligatoire.')}

        if not frappe.has_permission('Stock Ledger Entry', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur l\'historique des mouvements.')}

        item_code = str(item_code).strip()
        filters = {'item_code': item_code}
        movements = frappe.get_all('Stock Ledger Entry',
            filters=filters,
            fields=['posting_date', 'posting_time', 'actual_qty', 'warehouse',
                    'voucher_type', 'voucher_no', 'owner'],
            order_by='creation desc',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Stock Ledger Entry', filters=filters)

        return {
            'data_type': 'stock_history',
            'currency': _get_currency(),
            'company': _get_company(),
            'item_code': item_code,
            'count': len(movements),
            'movements': movements,
            'query_params': {
                'doctype': 'Stock Ledger Entry',
                'filters': filters,
                'fields': ['posting_date', 'posting_time', 'actual_qty', 'warehouse', 'voucher_type', 'voucher_no', 'owner'],
                'order_by': 'creation desc',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'stock_history',
                'currency': _get_currency(),
                'item_code': item_code
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_stock_history')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_stock_history')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_last_delivery_note(item_code=None):
    try:
        if not item_code or not str(item_code).strip():
            return {'error': 'missing_parameter', 'message': _('Code article obligatoire.')}

        if not frappe.has_permission('Delivery Note', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les bons de livraison.')}

        item_code = str(item_code).strip()

        last_dn = frappe.db.get_value('Delivery Note Item',
            {'item_code': item_code, 'docstatus': 1},
            ['parent', 'creation'],
            order_by='creation desc', as_dict=True)

        if not last_dn:
            return {
                'data_type': 'last_delivery_note',
                'currency': _get_currency(),
                'company': _get_company(),
                'item_code': item_code,
                'message': _('Aucun bon de livraison trouvé.')
            }

        return {
            'data_type': 'last_delivery_note',
            'currency': _get_currency(),
            'company': _get_company(),
            'item_code': item_code,
            'delivery_note': last_dn.parent,
            'date': str(last_dn.creation)
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_last_delivery_note')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_last_delivery_note')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 3. VALORISATION ET COÛTS
# ═══════════════════════════════════════════════════════════

def get_stock_valuation(warehouse=None):
    try:
        user_roles = set(frappe.get_roles(frappe.session.user))
        if not (user_roles & STOCK_MANAGER_ROLES):
            return {'error': 'permission_denied', 'message': _('Seul un Stock Manager peut voir la valorisation financière.')}

        # Requête SQL directe sur tabBin — plus fiable que le report stock_balance
        where_clauses = ["actual_qty > 0"]
        params = {}
        if warehouse:
            where_clauses.append("warehouse = %(warehouse)s")
            params['warehouse'] = str(warehouse).strip()
        where_sql = " AND ".join(where_clauses)

        total_row = frappe.db.sql(f"""
            SELECT
                COALESCE(SUM(stock_value), 0) AS total_value,
                COUNT(DISTINCT item_code) AS item_count,
                COUNT(*) AS bin_count
            FROM `tabBin`
            WHERE {where_sql}
        """, params, as_dict=True)[0]

        # Top articles par valeur
        top_items = frappe.db.sql(f"""
            SELECT item_code, warehouse, actual_qty, valuation_rate, stock_value
            FROM `tabBin`
            WHERE {where_sql}
            ORDER BY stock_value DESC
            LIMIT 10
        """, params, as_dict=True)

        return {
            'data_type': 'stock_valuation',
            'currency': _get_currency(),
            'company': _get_company(),
            'total_value': flt(total_row.total_value),
            'item_count': total_row.item_count,
            'bin_count': total_row.bin_count,
            'warehouse': warehouse,
            'top_items': top_items
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_stock_valuation')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_stock_valuation')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 4. LOTS ET NUMÉROS DE SÉRIE
# ═══════════════════════════════════════════════════════════

def get_batch_info(batch_id=None):
    try:
        if not batch_id or not str(batch_id).strip():
            return {'error': 'missing_parameter', 'message': _('Numéro de lot obligatoire.')}

        if not frappe.has_permission('Batch', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les lots.')}

        batch_id = str(batch_id).strip()
        if not frappe.db.exists('Batch', batch_id):
            return {'error': 'not_found', 'message': _('Numéro de lot introuvable : {0}').format(batch_id)}

        batch = frappe.get_doc('Batch', batch_id)

        data = {
            'batch_id': batch.name,
            'item_code': batch.item_code,
            'expiry_date': str(batch.expiry_date) if batch.expiry_date else None,
            'manufacturing_date': str(batch.manufacturing_date) if batch.manufacturing_date else None,
            'current_qty': flt(batch.batch_qty),
            'is_expired': getdate(batch.expiry_date) < getdate() if batch.expiry_date else False
        }

        return {
            'data_type': 'batch_info',
            'currency': _get_currency(),
            'company': _get_company(),
            'batch': data
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_batch_info')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_batch_info')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_serial_status(serial_no=None):
    try:
        if not serial_no or not str(serial_no).strip():
            return {'error': 'missing_parameter', 'message': _('Numéro de série obligatoire.')}

        if not frappe.has_permission('Serial No', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les numéros de série.')}

        serial_no = str(serial_no).strip()
        if not frappe.db.exists('Serial No', serial_no):
            return {'error': 'not_found', 'message': _('Numéro de série inconnu : {0}').format(serial_no)}

        sn = frappe.get_doc('Serial No', serial_no)

        data = {
            'serial_no': sn.name,
            'item_code': sn.item_code,
            'status': sn.status,
            'warehouse': sn.warehouse,
            'delivery_note': sn.delivery_document_no,
            'warranty_expiry': str(sn.warranty_expiry_date) if sn.warranty_expiry_date else None
        }

        return {
            'data_type': 'serial_status',
            'currency': _get_currency(),
            'company': _get_company(),
            'serial': data
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_serial_status')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_serial_status')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 5. RÉAPPROVISIONNEMENT ET ACHATS
# ═══════════════════════════════════════════════════════════

def get_purchase_requests_status(item_code=None, limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Material Request', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les demandes de matériel.')}

        # Le champ 'status' est sur Material Request (parent), pas sur Material Request Item
        # On fait donc un JOIN entre le parent et les items
        where_clauses = ["mr.docstatus = 1", "mr.status != 'Stopped'"]
        params = {'limit_start': limit_start, 'limit_page_length': limit_page_length}
        if item_code:
            where_clauses.append("mri.item_code = %(item_code)s")
            params['item_code'] = str(item_code).strip()

        where_sql = " AND ".join(where_clauses)

        requests = frappe.db.sql(f"""
            SELECT mri.parent, mri.item_code, mri.qty, mri.ordered_qty,
                   mr.status, mr.transaction_date
            FROM `tabMaterial Request Item` mri
            JOIN `tabMaterial Request` mr ON mri.parent = mr.name
            WHERE {where_sql}
            ORDER BY mr.creation DESC
            LIMIT %(limit_start)s, %(limit_page_length)s
        """, params, as_dict=True)

        total_count = frappe.db.sql(f"""
            SELECT COUNT(*) FROM `tabMaterial Request Item` mri
            JOIN `tabMaterial Request` mr ON mri.parent = mr.name
            WHERE {where_sql}
        """, params)[0][0]

        return {
            'data_type': 'stock_purchase_requests',
            'currency': _get_currency(),
            'company': _get_company(),
            'item_code': item_code,
            'count': len(requests),
            'items': requests,
            'query_params': {
                'doctype': 'Material Request Item',
                'item_code': item_code,
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'stock_purchase_requests',
                'currency': _get_currency(),
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_purchase_requests_status')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_purchase_requests_status')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_items_to_reorder(limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Item', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les articles.')}

        reorder_list = frappe.db.sql("""
            SELECT
                r.parent AS item_code,
                r.warehouse,
                r.warehouse_reorder_level AS threshold,
                b.projected_qty AS current_qty
            FROM `tabItem Reorder` r
            JOIN `tabBin` b ON r.parent = b.item_code AND r.warehouse = b.warehouse
            WHERE b.projected_qty <= r.warehouse_reorder_level
            ORDER BY r.parent
            LIMIT %(limit_start)s, %(limit_page_length)s
        """, {
            'limit_start': limit_start,
            'limit_page_length': limit_page_length
        }, as_dict=True)

        total_count = frappe.db.sql("""
            SELECT COUNT(*) as total
            FROM `tabItem Reorder` r
            JOIN `tabBin` b ON r.parent = b.item_code AND r.warehouse = b.warehouse
            WHERE b.projected_qty <= r.warehouse_reorder_level
        """)[0][0]

        return {
            'data_type': 'items_to_reorder',
            'currency': _get_currency(),
            'company': _get_company(),
            'count': len(reorder_list),
            'items': reorder_list,
            'query_params': {
                'doctype': 'Item Reorder Level',
                'join': 'Bin',
                'filters': {'projected_qty': ['<=', 'warehouse_reorder_level']},
                'fields': ['parent as item_code', 'warehouse', 'warehouse_reorder_level as threshold', 'projected_qty as current_qty'],
                'order_by': 'parent',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'items_to_reorder',
                'currency': _get_currency()
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_items_to_reorder')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_items_to_reorder')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 6. LOGISTIQUE ET ENTREPÔTS
# ═══════════════════════════════════════════════════════════

def get_warehouse_details(warehouse=None):
    try:
        if not warehouse or not str(warehouse).strip():
            return {'error': 'missing_parameter', 'message': _('Nom d\'entrepôt obligatoire.')}

        if not frappe.has_permission('Warehouse', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les entrepôts.')}

        warehouse = str(warehouse).strip()
        if not frappe.db.exists('Warehouse', warehouse):
            return {'error': 'not_found', 'message': _('Entrepôt introuvable : {0}').format(warehouse)}

        wh = frappe.get_doc('Warehouse', warehouse)

        data = {
            'warehouse': wh.name,
            'warehouse_name': wh.warehouse_name,
            'type': wh.warehouse_type,
            'parent': wh.parent_warehouse,
            'company': wh.company,
            'account': wh.account
        }

        return {
            'data_type': 'warehouse_details',
            'currency': _get_currency(),
            'company': _get_company(),
            'warehouse': data
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_warehouse_details')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_warehouse_details')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 7. ANALYSE ET KPI
# ═══════════════════════════════════════════════════════════

def get_slow_moving_items(days=180, limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Stock Ledger Entry', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur le grand livre des stocks.')}

        try:
            days = int(days)
        except (ValueError, TypeError):
            days = 180

        threshold_date = add_days(getdate(), -days)

        slow_items = frappe.db.sql("""
            SELECT item_code, MAX(posting_date) AS last_move
            FROM `tabStock Ledger Entry`
            GROUP BY item_code
            HAVING last_move < %(threshold)s
            ORDER BY last_move ASC
            LIMIT %(limit_start)s, %(limit_page_length)s
        """, {
            'threshold': threshold_date,
            'limit_start': limit_start,
            'limit_page_length': limit_page_length
        }, as_dict=True)

        total_count = frappe.db.sql("""
            SELECT COUNT(*) as total
            FROM (
                SELECT item_code
                FROM `tabStock Ledger Entry`
                GROUP BY item_code
                HAVING MAX(posting_date) < %(threshold)s
            ) AS t
        """, {'threshold': threshold_date})[0][0]

        return {
            'data_type': 'slow_moving_items',
            'currency': _get_currency(),
            'company': _get_company(),
            'days_threshold': days,
            'count': len(slow_items),
            'items': slow_items,
            'query_params': {
                'doctype': 'Stock Ledger Entry',
                'group_by': 'item_code',
                'having': f'MAX(posting_date) < "{threshold_date}"',
                'fields': ['item_code', 'MAX(posting_date) as last_move'],
                'order_by': 'last_move ASC',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'slow_moving_items',
                'currency': _get_currency(),
                'days_threshold': days
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_slow_moving_items')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_slow_moving_items')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_top_moving_items(limit=5, limit_start=0, limit_page_length=5):
    try:
        if not frappe.has_permission('Stock Ledger Entry', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur le grand livre des stocks.')}

        try:
            limit = int(limit)
        except (ValueError, TypeError):
            limit = 5

        top_items = frappe.db.sql("""
            SELECT item_code, SUM(ABS(actual_qty)) AS total_out
            FROM `tabStock Ledger Entry`
            WHERE actual_qty < 0
              AND company = %(company)s
              AND posting_date >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
            GROUP BY item_code
            ORDER BY total_out DESC
            LIMIT %(limit_start)s, %(limit_page_length)s
        """, {
            'company': _get_company(),
            'limit_start': limit_start,
            'limit_page_length': limit_page_length
        }, as_dict=True)

        total_count = frappe.db.sql("""
            SELECT COUNT(DISTINCT item_code) as total
            FROM `tabStock Ledger Entry`
            WHERE actual_qty < 0
              AND company = %(company)s
              AND posting_date >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
        """, {'company': _get_company()})[0][0]

        return {
            'data_type': 'top_moving_items',
            'currency': _get_currency(),
            'company': _get_company(),
            'count': len(top_items),
            'items': top_items,
            'query_params': {
                'doctype': 'Stock Ledger Entry',
                'filters': {'actual_qty': ['<', 0], 'posting_date': ['>=', 'DATE_SUB(CURDATE(), INTERVAL 1 MONTH)']},
                'group_by': 'item_code',
                'fields': ['item_code', 'SUM(ABS(actual_qty)) as total_out'],
                'order_by': 'total_out DESC',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'top_moving_items',
                'currency': _get_currency()
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_top_moving_items')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_top_moving_items')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 8. ÉCRITURE DE STOCK (Stock Entry)
# ═══════════════════════════════════════════════════════════

def get_stock_entry_details(stock_entry_id=None):
    try:
        if not stock_entry_id or not str(stock_entry_id).strip():
            return {'error': 'missing_parameter', 'message': _("L'identifiant de l'écriture de stock est obligatoire.")}

        if not frappe.has_permission('Stock Entry', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les écritures de stock.')}

        stock_entry_id = str(stock_entry_id).strip()
        if not frappe.db.exists('Stock Entry', stock_entry_id):
            return {'error': 'not_found', 'message': _('Écriture de stock introuvable : {0}').format(stock_entry_id)}

        doc = frappe.get_doc('Stock Entry', stock_entry_id)

        parent_data = {
            'name': doc.name,
            'stock_entry_type': doc.stock_entry_type,
            'posting_date': str(doc.posting_date),
            'from_warehouse': doc.from_warehouse,
            'to_warehouse': doc.to_warehouse,
            'docstatus': doc.docstatus,
            'total_amount': flt(doc.total_amount)
        }

        items_data = [
            {
                'item_code': item.item_code,
                'item_name': item.item_name,
                'qty': flt(item.qty),
                'uom': item.uom,
                's_warehouse': item.s_warehouse,
                't_warehouse': item.t_warehouse,
                'basic_rate': flt(item.basic_rate),
                'amount': flt(item.amount),
                'batch_no': item.batch_no or None,
                'serial_no': item.serial_no or None
            }
            for item in doc.items
        ]

        return {
            'data_type': 'stock_entry_details',
            'currency': _get_currency(),
            'company': _get_company(),
            'stock_entry': parent_data,
            'items_count': len(items_data),
            'items': items_data
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_stock_entry_details')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_stock_entry_details')
        return {'error': 'internal_error', 'message': _('Erreur interne')}


# ═══════════════════════════════════════════════════════════
# DISPATCHER (sans wrapper status)
# ═══════════════════════════════════════════════════════════

def fetch_stock_data(intent, entity=None, limit_start=0, limit_page_length=20, **kwargs):
    if intent == 'stock_availability':
        return get_item_availability(entity)
    if intent == 'out_of_stock_items':
        return get_out_of_stock_items(entity, limit_start, limit_page_length)
    if intent == 'stock_history':
        return get_stock_history(entity, limit_start, limit_page_length)
    if intent == 'last_delivery_note':
        return get_last_delivery_note(entity)
    if intent == 'stock_valuation':
        return get_stock_valuation()
    if intent == 'stock_entry_details':
        return get_stock_entry_details(entity)
    if intent == 'batch_info':
        return get_batch_info(entity)
    if intent == 'serial_status':
        return get_serial_status(entity)
    if intent == 'stock_purchase_requests':
        return get_purchase_requests_status(entity, limit_start, limit_page_length)
    if intent == 'items_to_reorder':
        return get_items_to_reorder(limit_start, limit_page_length)
    if intent == 'warehouse_details':
        return get_warehouse_details(entity)
    if intent == 'slow_moving_items':
        return get_slow_moving_items(limit_page_length=limit_page_length, limit_start=limit_start)
    if intent == 'top_moving_items':
        return get_top_moving_items(limit_page_length=limit_page_length, limit_start=limit_start)
    return {'error': 'unknown_intent', 'message': _('Intent inconnu : {0}').format(intent)}