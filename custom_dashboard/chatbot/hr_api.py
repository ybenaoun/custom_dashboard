# -*- coding: utf-8 -*-
# Module: HR API - Read-Only Endpoints pour Chatbot ERPNext
# Sécurité: LECTURE SEULE — Aucune opération d'écriture autorisée
# Format retour: uniformisé avec accounting_api (pas de wrapper "status")
# Pagination V3: ajout de query_params, limit_start, limit_page_length

import frappe
from frappe import _
from frappe.utils import flt, getdate, add_days, format_date

def _get_company():
    return frappe.defaults.get_global_default('company') or 'Tunisian United Solutions (Demo)'

def _get_currency():
    return frappe.db.get_value('Company', _get_company(), 'default_currency') or 'TND'

def get_current_employee():
    """Récupère l'employé lié à l'utilisateur connecté."""
    employee = frappe.db.get_value('Employee', {'user_id': frappe.session.user}, 'name')
    if not employee:
        employee = frappe.db.get_value('Employee', {'personal_email': frappe.session.user}, 'name')
    return employee


# ═══════════════════════════════════════════════════════════
# 1. CONGÉS (LEAVE)
# ═══════════════════════════════════════════════════════════

def get_leave_balance(leave_type=None):
    try:
        if not frappe.has_permission('Leave Application', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les demandes de congé.')}

        employee = get_current_employee()
        if not employee:
            return {'error': 'no_employee', 'message': _('Aucun profil employé lié à votre compte.')}

        from hrms.hr.doctype.leave_application.leave_application import get_leave_details
        leaves = get_leave_details(employee, getdate())
        allocation = leaves.get('leave_allocation', {})

        if leave_type:
            result = allocation.get(leave_type, {'remaining_leaves': 0})
            return {
                'data_type': 'leave_balance',
                'currency': _get_currency(),
                'company': _get_company(),
                'employee': employee,
                'leave_type': leave_type,
                'balance': result
            }

        return {
            'data_type': 'leave_balance',
            'currency': _get_currency(),
            'company': _get_company(),
            'employee': employee,
            'allocation': allocation
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_leave_balance')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_leave_balance')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_my_absences(year=None, limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Leave Application', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les demandes de congé.')}

        employee = get_current_employee()
        if not employee:
            return {'error': 'no_employee', 'message': _('Aucun profil employé lié à votre compte.')}

        filters = {'employee': employee}
        if year:
            try:
                year = int(year)
                filters['from_date'] = ['>=', f'{year}-01-01']
                filters['to_date'] = ['<=', f'{year}-12-31']
            except (ValueError, TypeError):
                return {'error': 'invalid_year', 'message': _('Année invalide.')}

        items = frappe.get_all('Leave Application',
            filters=filters,
            fields=['name', 'leave_type', 'from_date', 'to_date', 'status', 'total_leave_days'],
            order_by='from_date desc',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Leave Application', filters=filters)

        return {
            'data_type': 'my_absences',
            'currency': _get_currency(),
            'company': _get_company(),
            'employee': employee,
            'count': len(items),
            'items': items,
            'query_params': {
                'doctype': 'Leave Application',
                'filters': filters,
                'fields': ['name', 'leave_type', 'from_date', 'to_date', 'status', 'total_leave_days'],
                'order_by': 'from_date desc',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'my_absences',
                'currency': _get_currency(),
                'employee': employee
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_my_absences')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_my_absences')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 2. PAIE (PAYROLL)
# ═══════════════════════════════════════════════════════════

def get_last_salary_slip():
    try:
        if not frappe.has_permission('Salary Slip', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les fiches de paie.')}

        employee = get_current_employee()
        if not employee:
            return {'error': 'no_employee', 'message': _('Profil employé non trouvé.')}

        slips = frappe.get_all('Salary Slip',
            filters={'employee': employee, 'docstatus': 1},
            fields=['name', 'start_date', 'end_date', 'gross_pay', 'net_pay', 'total_deduction'],
            order_by='start_date desc', limit=1)

        if not slips:
            return {
                'data_type': 'last_salary_slip',
                'currency': _get_currency(),
                'company': _get_company(),
                'message': _('Aucune fiche de paie trouvée.')
            }

        doc = frappe.get_doc('Salary Slip', slips[0].name)

        return {
            'data_type': 'last_salary_slip',
            'currency': _get_currency(),
            'company': _get_company(),
            'summary': dict(slips[0]),
            'earnings': [{'component': d.salary_component, 'amount': flt(d.amount)} for d in doc.earnings],
            'deductions': [{'component': d.salary_component, 'amount': flt(d.amount)} for d in doc.deductions]
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_last_salary_slip')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_last_salary_slip')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 3. PRÉSENCE (ATTENDANCE)
# ═══════════════════════════════════════════════════════════

def get_attendance_status(date=None):
    try:
        if not frappe.has_permission('Attendance', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les présences.')}

        employee = get_current_employee()
        if not employee:
            return {'error': 'no_employee', 'message': _('Aucun profil employé lié à votre compte.')}

        check_date = date or getdate()

        status = frappe.db.get_value('Attendance',
            {'employee': employee, 'attendance_date': check_date},
            'status')

        check_in = frappe.get_all('Employee Checkin',
            filters={'employee': employee,
                     'time': ['between', [f'{check_date} 00:00:00', f'{check_date} 23:59:59']]},
            fields=['time', 'log_type'],
            order_by='time asc')

        return {
            'data_type': 'attendance_status',
            'currency': _get_currency(),
            'company': _get_company(),
            'employee': employee,
            'date': str(check_date),
            'status': status or 'Non enregistré',
            'logs': check_in
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_attendance_status')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_attendance_status')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_team_absent_today(limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Attendance', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les présences.')}

        employee = get_current_employee()

        if employee:
            # Mode manager : absents de mon équipe
            team = frappe.get_all('Employee',
                filters={'reports_to': employee},
                fields=['name', 'employee_name'])

            if not team:
                # Pas d'équipe directe → fallback : tous les absents de la company
                team_ids = None
            else:
                team_ids = [d.name for d in team]
        else:
            # Pas d'employé lié → afficher tous les absents de la company
            team_ids = None

        filters = {
            'attendance_date': getdate(),
            'status': ['in', ['Absent', 'On Leave', 'Half Day']],
            'company': _get_company(),
        }
        if team_ids:
            filters['employee'] = ['in', team_ids]

        items = frappe.get_all('Attendance',
            filters=filters,
            fields=['employee', 'employee_name', 'status'],
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Attendance', filters=filters)

        return {
            'data_type': 'team_absent_today',
            'currency': _get_currency(),
            'company': _get_company(),
            'count': len(items),
            'items': items,
            'query_params': {
                'doctype': 'Attendance',
                'filters': filters,
                'fields': ['employee', 'employee_name', 'status'],
                'order_by': 'employee_name',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'team_absent_today',
                'currency': _get_currency()
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_team_absent_today')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_team_absent_today')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 4. NOTES DE FRAIS
# ═══════════════════════════════════════════════════════════

def get_expense_claims_status(limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Expense Claim', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les notes de frais.')}

        employee = get_current_employee()
        if not employee:
            return {'error': 'no_employee', 'message': _('Aucun profil employé lié à votre compte.')}

        filters = {'employee': employee}
        items = frappe.get_all('Expense Claim',
            filters=filters,
            fields=['name', 'posting_date', 'total_claimed_amount', 'approval_status', 'status'],
            order_by='creation desc',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Expense Claim', filters=filters)

        return {
            'data_type': 'expense_claims',
            'currency': _get_currency(),
            'company': _get_company(),
            'employee': employee,
            'count': len(items),
            'items': items,
            'query_params': {
                'doctype': 'Expense Claim',
                'filters': filters,
                'fields': ['name', 'posting_date', 'total_claimed_amount', 'approval_status', 'status'],
                'order_by': 'creation desc',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'expense_claims',
                'currency': _get_currency(),
                'employee': employee
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_expense_claims_status')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_expense_claims_status')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 5. RECRUTEMENT
# ═══════════════════════════════════════════════════════════

def get_job_openings(limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Job Opening', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les offres d\'emploi.')}

        filters = {'status': 'Open'}
        items = frappe.get_all('Job Opening',
            filters=filters,
            fields=['job_title', 'department', 'designation', 'route'],
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Job Opening', filters=filters)

        return {
            'data_type': 'job_openings',
            'currency': _get_currency(),
            'company': _get_company(),
            'count': len(items),
            'items': items,
            'query_params': {
                'doctype': 'Job Opening',
                'filters': filters,
                'fields': ['job_title', 'department', 'designation', 'route'],
                'order_by': 'creation desc',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'job_openings',
                'currency': _get_currency()
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_job_openings')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_job_openings')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


# ═══════════════════════════════════════════════════════════
# 6. PROFIL ET CARRIÈRE
# ═══════════════════════════════════════════════════════════

def get_employee_profile_summary(entity=None):
    try:
        if not frappe.has_permission('Employee', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les profils employés.')}

        employee = None
        if entity:
            # Recherche par nom
            employee = frappe.db.get_value('Employee',
                {'employee_name': ['like', f'%{entity}%'], 'status': 'Active'},
                'name')
            if not employee:
                # Recherche par ID
                employee = frappe.db.get_value('Employee',
                    {'name': entity, 'status': 'Active'}, 'name')
        if not employee:
            employee = get_current_employee()
        if not employee:
            return {'error': 'no_employee', 'message': _('Profil employé introuvable.')}

        doc = frappe.get_doc('Employee', employee)

        data = {
            'employee_id': doc.name,
            'full_name': doc.employee_name,
            'designation': doc.designation,
            'department': doc.department,
            'date_of_joining': str(doc.date_of_joining) if doc.date_of_joining else None,
            'reports_to': doc.reports_to,
            'reports_to_name': frappe.db.get_value('Employee', doc.reports_to, 'employee_name') if doc.reports_to else None,
            'emergency_contact': getattr(doc, 'emergency_phone_number', None),
            'company': doc.company,
            'branch': doc.branch,
            'employment_type': doc.employment_type
        }

        return {
            'data_type': 'employee_profile',
            'currency': _get_currency(),
            'company': _get_company(),
            'profile': data
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_employee_profile_summary')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_employee_profile_summary')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_upcoming_holidays(limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Holiday List', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les listes de jours fériés.')}

        employee = get_current_employee()
        holiday_list = frappe.db.get_value('Employee', employee, 'holiday_list') if employee else None

        if not holiday_list:
            holiday_list = frappe.db.get_value(
                'Company',
                frappe.defaults.get_user_default('company'),
                'default_holiday_list'
            )

        if not holiday_list:
            return {
                'data_type': 'upcoming_holidays',
                'currency': _get_currency(),
                'company': _get_company(),
                'message': _('Aucune liste de jours fériés configurée.'),
                'items': []
            }

        filters = {'parent': holiday_list, 'holiday_date': ['>=', getdate()]}
        items = frappe.get_all('Holiday',
            filters=filters,
            fields=['holiday_date', 'description'],
            order_by='holiday_date asc',
            limit_start=limit_start,
            limit_page_length=limit_page_length)

        total_count = frappe.db.count('Holiday', filters=filters)

        return {
            'data_type': 'upcoming_holidays',
            'currency': _get_currency(),
            'company': _get_company(),
            'holiday_list': holiday_list,
            'count': len(items),
            'items': items,
            'query_params': {
                'doctype': 'Holiday',
                'filters': filters,
                'fields': ['holiday_date', 'description'],
                'order_by': 'holiday_date asc',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'upcoming_holidays',
                'currency': _get_currency(),
                'holiday_list': holiday_list
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_upcoming_holidays')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_upcoming_holidays')
        return {'error': 'internal_error', 'message': _('Erreur interne du serveur')}


def get_leave_application_status(leave_id=None):
    try:
        if not leave_id or not str(leave_id).strip():
            return {'error': 'missing_parameter', 'message': _("L'identifiant de la demande de congé est obligatoire.")}

        if not frappe.has_permission('Leave Application', 'read'):
            return {'error': 'permission_denied', 'message': _('Permission insuffisante sur les demandes de congé.')}

        leave_id = str(leave_id).strip()
        if not frappe.db.exists('Leave Application', leave_id):
            return {'error': 'not_found', 'message': _('Demande de congé introuvable : {0}').format(leave_id)}

        doc = frappe.get_doc('Leave Application', leave_id)

        return {
            'data_type': 'leave_application_status',
            'currency': _get_currency(),
            'company': _get_company(),
            'application': {
                'name': doc.name,
                'employee_name': doc.employee_name,
                'leave_type': doc.leave_type,
                'from_date': str(doc.from_date),
                'to_date': str(doc.to_date),
                'total_leave_days': flt(doc.total_leave_days),
                'status': doc.status,
                'leave_approver': doc.leave_approver,
                'leave_approver_name': doc.leave_approver_name,
                'posting_date': str(doc.posting_date),
                'description': doc.description or ''
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'get_leave_application_status')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'get_leave_application_status')
        return {'error': 'internal_error', 'message': _('Erreur interne')}


def search_employee_directory(employee_name=None, limit_start=0, limit_page_length=20):
    try:
        if not frappe.has_permission('Employee', 'read'):
            return {'error': 'permission_denied', 'message': _("Permission insuffisante sur l'annuaire employés.")}

        # Si pas de terme de recherche, lister tous les employés actifs
        if not employee_name or not str(employee_name).strip():
            employees = frappe.get_all('Employee',
                filters={'status': 'Active', 'company': _get_company()},
                fields=['name', 'employee_name', 'designation', 'department',
                        'company_email', 'cell_number', 'image', 'branch', 'company'],
                order_by='employee_name ASC',
                limit_start=limit_start,
                limit_page_length=limit_page_length)
            total_count = frappe.db.count('Employee',
                filters={'status': 'Active', 'company': _get_company()})
            return {
                'data_type': 'employee_directory',
                'currency': _get_currency(),
                'company': _get_company(),
                'count': len(employees),
                'employees': employees,
                'query_params': {
                    'doctype': 'Employee',
                    'fields': ['name', 'employee_name', 'designation', 'department'],
                    'order_by': 'employee_name ASC',
                    'page_size': limit_page_length,
                    'total_count': total_count,
                    'data_type': 'employee_directory',
                    'currency': _get_currency()
                }
            }

        search_term = str(employee_name).strip()
        if len(search_term) < 2:
            return {'error': 'search_too_short', 'message': _('Veuillez saisir au moins 2 caractères pour la recherche.')}

        search_term = search_term.replace('%', '').replace('_', '\\_')

        employees = frappe.db.sql("""
            SELECT
                name,
                employee_name,
                designation,
                department,
                company_email,
                cell_number,
                image,
                branch,
                company
            FROM `tabEmployee`
            WHERE
                status = 'Active'
                AND (
                    employee_name LIKE %(search)s
                    OR designation LIKE %(search)s
                    OR department LIKE %(search)s
                )
            ORDER BY employee_name ASC
            LIMIT %(limit_start)s, %(limit_page_length)s
        """, {
            'search': f'%{search_term}%',
            'limit_start': limit_start,
            'limit_page_length': limit_page_length
        }, as_dict=True)

        total_count = frappe.db.sql("""
            SELECT COUNT(*) as total
            FROM `tabEmployee`
            WHERE
                status = 'Active'
                AND (
                    employee_name LIKE %(search)s
                    OR designation LIKE %(search)s
                    OR department LIKE %(search)s
                )
        """, {'search': f'%{search_term}%'})[0][0]

        return {
            'data_type': 'employee_directory',
            'currency': _get_currency(),
            'company': _get_company(),
            'search_term': search_term,
            'count': len(employees),
            'employees': employees,
            'query_params': {
                'doctype': 'Employee',
                'search_term': search_term,
                'fields': ['name', 'employee_name', 'designation', 'department', 'company_email', 'cell_number', 'image', 'branch', 'company'],
                'order_by': 'employee_name ASC',
                'page_size': limit_page_length,
                'total_count': total_count,
                'data_type': 'employee_directory',
                'currency': _get_currency()
            }
        }

    except frappe.PermissionError:
        frappe.log_error('Permission refusée', 'search_employee_directory')
        return {'error': 'permission_denied', 'message': _('Permission insuffisante')}
    except Exception as e:
        frappe.log_error(str(e), 'search_employee_directory')
        return {'error': 'internal_error', 'message': _('Erreur interne')}


# ═══════════════════════════════════════════════════════════
# DISPATCHER (sans wrapper status)
# ═══════════════════════════════════════════════════════════

def fetch_hr_data(intent, entity=None, from_date=None, to_date=None, limit_start=0, limit_page_length=20, **kwargs):
    if intent == 'leave_balance':
        return get_leave_balance(entity)
    if intent == 'my_absences':
        return get_my_absences(entity, limit_start, limit_page_length)
    if intent == 'last_salary_slip':
        return get_last_salary_slip()
    if intent == 'attendance_status':
        return get_attendance_status()
    if intent == 'team_absent_today':
        return get_team_absent_today(limit_start, limit_page_length)
    if intent == 'expense_claims':
        return get_expense_claims_status(limit_start, limit_page_length)
    if intent == 'job_openings':
        return get_job_openings(limit_start, limit_page_length)
    if intent == 'employee_profile':
        return get_employee_profile_summary(entity)
    if intent == 'upcoming_holidays':
        return get_upcoming_holidays(limit_start, limit_page_length)
    if intent == 'leave_application_status':
        return get_leave_application_status(entity)
    if intent == 'employee_directory':
        return search_employee_directory(entity, limit_start, limit_page_length)
    return {'error': 'unknown_intent', 'message': _('Intent inconnu : {0}').format(intent)}