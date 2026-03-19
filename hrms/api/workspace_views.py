from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import frappe
from frappe import _

ALLOWED_ROLES = {"System Manager", "HR Manager", "HR User", "Area Supervisor", "Store Supervisor"}
USER_DEFAULT_KEY = "bei_portal_workspace_views"
MAX_VIEWS_PER_SCOPE = 12
MAX_SCOPE_LENGTH = 80
MAX_NAME_LENGTH = 80


def _check_permission() -> None:
	roles = set(frappe.get_roles(frappe.session.user))
	if not roles.intersection(ALLOWED_ROLES):
		frappe.throw(_("You do not have permission to manage workspace views."), frappe.PermissionError)


def _sanitize_scope(scope: str | None) -> str:
	value = (scope or "").strip()
	if not value:
		frappe.throw(_("Workspace scope is required."))
	if len(value) > MAX_SCOPE_LENGTH:
		frappe.throw(_("Workspace scope is too long."))
	return value


def _sanitize_name(name: str | None) -> str:
	value = (name or "").strip()
	if not value:
		frappe.throw(_("View name is required."))
	if len(value) > MAX_NAME_LENGTH:
		frappe.throw(_("View name is too long."))
	return value


def _coerce_filters(filters: dict[str, Any] | str | None) -> dict[str, str]:
	if filters is None:
		return {}
	if isinstance(filters, str):
		try:
			filters = json.loads(filters)
		except Exception:
			frappe.throw(_("Could not parse workspace view filters."))
	if not isinstance(filters, dict):
		frappe.throw(_("Workspace view filters must be an object."))

	normalized: dict[str, str] = {}
	for key, value in filters.items():
		if value is None:
			continue
		key_text = str(key).strip()
		if not key_text:
			continue
		value_text = str(value).strip()
		if not value_text:
			continue
		normalized[key_text] = value_text
	return normalized


def _load_store() -> dict[str, list[dict[str, Any]]]:
	raw = frappe.defaults.get_user_default(USER_DEFAULT_KEY)
	if not raw:
		return {}
	if isinstance(raw, dict):
		return raw
	if isinstance(raw, str):
		try:
			parsed = json.loads(raw)
		except Exception:
			return {}
		return parsed if isinstance(parsed, dict) else {}
	return {}


def _persist_store(store: dict[str, list[dict[str, Any]]]) -> None:
	frappe.defaults.set_user_default(USER_DEFAULT_KEY, json.dumps(store))


@frappe.whitelist()
def get_workspace_views(scope: str) -> dict[str, Any]:
	_check_permission()
	scope_key = _sanitize_scope(scope)
	store = _load_store()
	views = store.get(scope_key, [])
	return {"views": views}


@frappe.whitelist()
def save_workspace_view(scope: str, name: str, filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	_check_permission()
	scope_key = _sanitize_scope(scope)
	view_name = _sanitize_name(name)
	view_filters = _coerce_filters(filters)
	store = _load_store()
	scope_views = [view for view in store.get(scope_key, []) if view.get("name") != view_name]
	scope_views.insert(
		0,
		{
			"name": view_name,
			"filters": view_filters,
			"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
		},
	)
	store[scope_key] = scope_views[:MAX_VIEWS_PER_SCOPE]
	_persist_store(store)
	return {"success": True, "views": store[scope_key]}


@frappe.whitelist()
def delete_workspace_view(scope: str, name: str) -> dict[str, Any]:
	_check_permission()
	scope_key = _sanitize_scope(scope)
	view_name = _sanitize_name(name)
	store = _load_store()
	scope_views = [view for view in store.get(scope_key, []) if view.get("name") != view_name]
	store[scope_key] = scope_views
	_persist_store(store)
	return {"success": True, "views": scope_views}
