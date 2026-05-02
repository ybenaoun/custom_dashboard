from __future__ import annotations

from custom_dashboard.services import access


def has_app_permission() -> bool:
	return access.has_builder_access()


def get_dashboard_widget_permission_query_conditions(user=None):
	return access.get_dashboard_widget_permission_query_condition(user=user)


def has_dashboard_widget_permission(doc=None, user=None, ptype=None):
	return access.has_dashboard_widget_permission(doc=doc, user=user, ptype=ptype)


def get_user_dashboard_permission_query_conditions(user=None):
	return access.get_user_dashboard_permission_query_condition(user=user)


def has_user_dashboard_permission(doc=None, user=None, ptype=None):
	return access.has_user_dashboard_permission(doc=doc, user=user, ptype=ptype)
