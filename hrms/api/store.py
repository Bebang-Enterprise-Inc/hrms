# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Store Operations API
Handles store ordering, receiving, and FQI reports for my.bebang.ph
"""

import base64
import hashlib
import json
import re

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, getdate, now_datetime, nowdate

from hrms.utils.bei_config import SPACE_OPS, get_chat_space, get_company
from hrms.utils.scm_roles import SCM_APPROVAL_ROLES, check_scm_permission
from hrms.utils.supply_chain_contracts import (
	FINANCE_TREATMENT_SAME_COMPANY,
	REQUEST_SOURCE_STORE_DISPOSAL,
	REQUEST_SOURCE_STORE_ORDER,
	REQUEST_SOURCE_STORE_RETURN,
	infer_finance_treatment,
	resolve_material_request_contract,
	resolve_route_source_warehouse,
	resolve_store_buyer_entity,
	resolve_warehouse_company,
	stamp_material_request_contract,
	stamp_stock_entry_contract,
)


def _manual_pos_upload_disabled_message() -> str:
	return _(
		"Manual POS uploads are disabled. Sales now sync automatically via API. "
		"Use Closing Report for X/Z-reading evidence, cash control, and POS-down exceptions."
	)


def _notify_store_ops(msg=None, *, event=None, requested_space=None):
	"""Send a non-blocking Store Ops notification.

	Legacy raw text is kept for non-migrated callers. Sprint 38 structured events
	should use the ``event`` path.
	"""
	try:
		from hrms.api.google_chat import send_message_to_space, send_notification_event

		if event:
			payload = dict(event)
			payload.setdefault("requested_space", requested_space or get_chat_space(SPACE_OPS))
			send_notification_event(payload)
			return
		if msg:
			send_message_to_space(get_chat_space(SPACE_OPS), msg)
	except Exception:
		pass


def _decode_base64_attachment(base64_data, default_ext="bin"):
	"""Decode a base64 attachment payload and infer a reasonable file extension."""
	if not base64_data:
		return None, None

	if "," in base64_data:
		header, content = base64_data.split(",", 1)
		header_lower = header.lower()
		if "sheet" in header_lower:
			ext = "xlsx"
		elif "csv" in header_lower:
			ext = "csv"
		elif "png" in header_lower:
			ext = "png"
		elif "gif" in header_lower:
			ext = "gif"
		elif "webp" in header_lower:
			ext = "webp"
		elif "jpeg" in header_lower or "jpg" in header_lower:
			ext = "jpg"
		else:
			ext = default_ext
	else:
		content = base64_data
		ext = default_ext

	try:
		return base64.b64decode(content), ext
	except Exception as e:
		frappe.log_error(f"Failed to decode base64 attachment: {e!s}", "Base64 Decode Error")
		frappe.throw(_("Invalid attachment data"))


def save_base64_image(base64_data, doctype, docname=None, fieldname="photo"):
	"""
	Save a base64-encoded image as a Frappe file attachment.
	Returns the file URL that can be stored in Attach Image fields.

	Args:
	    base64_data: Base64 string (with or without data:image/... prefix)
	    doctype: DocType to attach the file to
	    docname: Document name (optional, can attach later)
	    fieldname: Field name for the attachment

	Returns:
	    str: File URL (e.g., /files/maintenance_photo_abc123.jpg)
	"""
	if not base64_data:
		return None

	# Check if it's already a URL (not base64)
	if base64_data.startswith(("/files/", "/private/", "http://", "https://")):
		return base64_data

	file_content, ext = _decode_base64_attachment(base64_data, default_ext="jpg")

	# Generate unique filename using hash
	file_hash = hashlib.md5(file_content).hexdigest()[:12]
	filename = f"{doctype.lower().replace(' ', '_')}_{file_hash}.{ext}"

	# Save using Frappe's file handler
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": file_content,
			"attached_to_doctype": doctype if docname else None,
			"attached_to_name": docname,
			"attached_to_field": fieldname,
			"is_private": 0,
		}
	)
	file_doc.save(ignore_permissions=True)

	return file_doc.file_url


def save_base64_file(base64_data, doctype, docname=None, fieldname="attachment", default_ext="bin"):
	"""Save a base64-encoded non-image file as a Frappe attachment."""
	if not base64_data:
		return None

	if base64_data.startswith(("/files/", "/private/", "http://", "https://")):
		return base64_data

	file_content, ext = _decode_base64_attachment(base64_data, default_ext=default_ext)

	file_hash = hashlib.md5(file_content).hexdigest()[:12]
	filename = f"{doctype.lower().replace(' ', '_')}_{fieldname}_{file_hash}.{ext}"

	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": file_content,
			"attached_to_doctype": doctype if docname else None,
			"attached_to_name": docname,
			"attached_to_field": fieldname,
			"is_private": 0,
		}
	)
	file_doc.save(ignore_permissions=True)

	return file_doc.file_url


STORE_OPS_ALLOWED_ROLES = [
	"Store Staff",
	"Store OIC",
	"Store Supervisor",
	"Area Supervisor",
	"Regional Manager",
	"System Manager",
	"Administrator",
]
AREA_SUPERVISOR_ROLE = "Area Supervisor"
REGIONAL_MANAGER_ROLE = "Regional Manager"
REGIONAL_MANAGER_FALLBACK_EMAIL = "edlice@bebang.ph"
SYSTEM_APPROVER_ROLES = {"System Manager", "Administrator"}


def _has_column(doctype: str, fieldname: str) -> bool:
	"""Return True when the runtime table includes the requested column."""
	has_column = getattr(frappe.db, "has_column", None)
	if not callable(has_column):
		return False
	try:
		return bool(has_column(doctype, fieldname))
	except Exception:
		return False


def validate_store_ops_role():
	"""Validate that current user has a store operations role.
	Raises PermissionError if user lacks required role."""
	user_roles = frappe.get_roles(frappe.session.user)
	if not any(role in user_roles for role in STORE_OPS_ALLOWED_ROLES):
		frappe.throw(_("You do not have permission for store operations"), frappe.PermissionError)


def resolve_warehouse(store_or_branch):
	"""
	Resolve a branch name or partial warehouse name to the full warehouse name.
	Branch names like 'TEST-STORE-BGC' need to be converted to warehouse names 'TEST-STORE-BGC - BEI'.
	"""
	if not store_or_branch:
		return None

	# First check if the exact warehouse exists
	if frappe.db.exists("Warehouse", store_or_branch):
		return store_or_branch

	# Try appending company abbreviation (BEI is the default company)
	warehouse_with_company = f"{store_or_branch} - BEI"
	if frappe.db.exists("Warehouse", warehouse_with_company):
		return warehouse_with_company

	# Try to find warehouse by warehouse_name (without company suffix)
	warehouse = frappe.db.get_value("Warehouse", {"warehouse_name": store_or_branch}, "name")
	if warehouse:
		return warehouse

	frappe.throw(_("Could not find Store: {0}").format(store_or_branch))


def resolve_employee_store_context(employee):
	"""Resolve a warehouse for an employee, falling back to the reporting chain.

	This keeps store-scoped workflows usable when a store employee is linked to a
	reporting manager with a branch but the employee record itself is still missing
	its direct branch assignment.
	"""
	employee_row = dict(employee or {})
	visited = set()
	manager_name = str(employee_row.get("reports_to") or "").strip()
	branch = str(employee_row.get("branch") or "").strip()
	resolved_via = "employee_branch" if branch else None
	resolved_manager = None

	while not branch and manager_name and manager_name not in visited:
		visited.add(manager_name)
		manager = frappe.db.get_value(
			"Employee", manager_name, ["name", "branch", "reports_to"], as_dict=True
		)
		if not manager:
			break
		manager_branch = str(manager.get("branch") or "").strip()
		if manager_branch:
			branch = manager_branch
			resolved_via = "reports_to_branch"
			resolved_manager = manager.get("name")
			break
		manager_name = str(manager.get("reports_to") or "").strip()

	if not branch:
		return {
			"branch": None,
			"warehouse": None,
			"warehouse_name": None,
			"resolved_via": resolved_via or "unresolved",
			"resolved_manager": resolved_manager,
		}

	try:
		warehouse = resolve_warehouse(branch)
	except Exception:
		return {
			"branch": branch,
			"warehouse": None,
			"warehouse_name": None,
			"resolved_via": resolved_via or "employee_branch",
			"resolved_manager": resolved_manager,
		}

	return {
		"branch": branch,
		"warehouse": warehouse,
		"warehouse_name": frappe.db.get_value("Warehouse", warehouse, "warehouse_name") or warehouse,
		"resolved_via": resolved_via or "employee_branch",
		"resolved_manager": resolved_manager,
	}


def _normalize_store_key(value):
	return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _designation_is_store_lead(designation):
	label = str(designation or "").upper()
	return "STORE SUPERVISOR" in label or "STORE OIC" in label or " OIC" in label or label == "OIC"


def _is_test_user(user_id):
	local_part = str(user_id or "").strip().split("@", 1)[0].lower()
	return local_part.startswith(("test", "e2e", "qa"))


def _is_area_supervisor_user(user_id, role_cache=None):
	user = str(user_id or "").strip()
	if not user:
		return False
	cache = role_cache if role_cache is not None else {}
	if user in cache:
		return cache[user]
	try:
		roles = set(frappe.get_roles(user))
	except Exception:
		roles = set()
	cache[user] = AREA_SUPERVISOR_ROLE in roles
	return cache[user]


def _clean_warehouse_branch_candidates(*values):
	seen = set()
	candidates = []
	for raw in values:
		text = str(raw or "").strip()
		if not text:
			continue
		variants = [text]
		without_company = re.sub(r"\s*-\s*BEI$", "", text, flags=re.IGNORECASE).strip()
		if without_company:
			variants.append(without_company)
		if " - " in text:
			variants.append(text.split(" - ", 1)[0].strip())
		for variant in variants:
			key = _normalize_store_key(variant)
			if key and key not in seen:
				seen.add(key)
				candidates.append(variant)
	return candidates


def _warehouse_branch_candidates(warehouse):
	warehouse_doc = (
		frappe.db.get_value(
			"Warehouse",
			warehouse,
			["name", "warehouse_name", "parent_warehouse"],
			as_dict=True,
		)
		or {}
	)
	parent_name = None
	if warehouse_doc.get("parent_warehouse"):
		parent_name = frappe.db.get_value(
			"Warehouse", warehouse_doc.get("parent_warehouse"), "warehouse_name"
		)
	return _clean_warehouse_branch_candidates(
		warehouse_doc.get("warehouse_name"),
		warehouse_doc.get("name"),
		warehouse,
		parent_name,
	)


def _resolve_valid_area_supervisor(candidate, warehouse, source, role_cache=None):
	user = str(candidate or "").strip()
	if not user:
		return None
	if _is_area_supervisor_user(user, role_cache=role_cache):
		return user
	frappe.log_error(
		f"Warehouse {warehouse} has invalid {source} mapping '{user}' (missing Area Supervisor role).",
		"Store Area Supervisor Mapping",
	)
	return None


def _choose_preferred_area_supervisor(candidates, prefer_test=False):
	users = sorted({str(user or "").strip() for user in candidates if str(user or "").strip()})
	if not users:
		return None

	test_users = [user for user in users if _is_test_user(user)]
	non_test_users = [user for user in users if user not in test_users]

	if prefer_test and test_users:
		return test_users[0]

	if non_test_users:
		return non_test_users[0]

	return users[0]


def _get_default_area_supervisor(role_cache=None, branch_keys=None):
	try:
		role_rows = frappe.get_all(
			"Has Role",
			filters={"role": AREA_SUPERVISOR_ROLE},
			fields=["parent"],
			limit_page_length=500,
		)
	except Exception:
		return None

	candidates = sorted(
		{str(row.get("parent")).strip() for row in role_rows if row and str(row.get("parent") or "").strip()}
	)
	if not candidates:
		return None

	try:
		enabled_rows = frappe.get_all(
			"User",
			filters={"name": ["in", candidates], "enabled": 1},
			fields=["name"],
			limit_page_length=max(200, len(candidates)),
		)
		enabled_users = {str(row.get("name")).strip() for row in enabled_rows if row.get("name")}
	except Exception:
		enabled_users = set(candidates)

	valid_candidates = [
		user
		for user in candidates
		if user in enabled_users and _is_area_supervisor_user(user, role_cache=role_cache)
	]
	if not valid_candidates:
		return None

	prefer_test = any("TEST" in str(key or "").upper() for key in (branch_keys or set()))
	if prefer_test:
		return _choose_preferred_area_supervisor(valid_candidates, prefer_test=True)
	return None


def _is_enabled_user(user_id):
	user = str(user_id or "").strip()
	if not user:
		return False
	try:
		rows = frappe.get_all(
			"User",
			filters={"name": user, "enabled": 1},
			fields=["name"],
			limit_page_length=1,
		)
	except Exception:
		return False
	return bool(rows)


def _doctype_has_field(doctype, fieldname):
	try:
		meta = frappe.get_meta(doctype)
		return bool(meta and meta.has_field(fieldname))
	except Exception:
		return False


def _get_regional_manager_fallback_user():
	user = str(REGIONAL_MANAGER_FALLBACK_EMAIL or "").strip()
	if not user:
		return None
	if not _is_enabled_user(user):
		frappe.log_error(
			f"Regional manager fallback user {user} is missing or disabled.",
			"Store Order Approver Fallback",
		)
		return None
	try:
		roles = set(frappe.get_roles(user))
	except Exception:
		roles = set()
	if not roles.intersection({AREA_SUPERVISOR_ROLE, REGIONAL_MANAGER_ROLE, "System Manager"}):
		frappe.log_error(
			f"Regional manager fallback user {user} has no approval role.",
			"Store Order Approver Fallback",
		)
		return None
	return user


def _resolve_review_approver_for_store(warehouse):
	area_supervisor = _get_area_supervisor_for_store(warehouse)
	if area_supervisor:
		return area_supervisor, "area_supervisor"

	regional_manager = _get_regional_manager_fallback_user()
	if regional_manager:
		return regional_manager, "regional_manager_fallback"

	return None, "unmapped"


def _is_system_approver(user_id):
	try:
		roles = set(frappe.get_roles(user_id))
	except Exception:
		roles = set()
	return bool(roles.intersection(SYSTEM_APPROVER_ROLES))


def _is_regional_manager_user(user_id):
	user = str(user_id or "").strip()
	if not user:
		return False
	try:
		roles = set(frappe.get_roles(user))
	except Exception:
		roles = set()
	return bool(roles.intersection({REGIONAL_MANAGER_ROLE, "System Manager", "HR Manager"}))


def _create_order_notification_log(order_name, for_user, subject):
	if not for_user:
		return
	try:
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": for_user,
				"from_user": frappe.session.user,
				"type": "Alert",
				"document_type": "BEI Store Order",
				"document_name": order_name,
				"subject": subject or f"Store order {order_name} requires approval.",
				"email_content": subject or f"Store order {order_name} requires approval.",
			}
		).insert(ignore_permissions=True)
	except Exception:
		pass


def _assign_order_for_approval(order_name, assigned_to, description):
	if not assigned_to:
		return False
	try:
		from frappe.desk.form.assign_to import add as add_assignment

		add_assignment(
			{
				"assign_to": [assigned_to],
				"doctype": "BEI Store Order",
				"name": order_name,
				"description": description,
				"notify": 1,
				"assigned_by": frappe.session.user,
				"priority": "High",
			}
		)
		_create_order_notification_log(
			order_name=order_name,
			for_user=assigned_to,
			subject=description,
		)
		return True
	except Exception:
		try:
			todo = frappe.get_doc(
				{
					"doctype": "ToDo",
					"allocated_to": assigned_to,
					"reference_type": "BEI Store Order",
					"reference_name": order_name,
					"description": description,
					"priority": "High",
					"status": "Open",
				}
			)
			todo.insert(ignore_permissions=True)
			_create_order_notification_log(
				order_name=order_name,
				for_user=assigned_to,
				subject=description,
			)
			return True
		except Exception:
			frappe.log_error(
				f"Failed to assign BEI Store Order {order_name} to {assigned_to}",
				"Store Order Assignment Error",
			)
			return False


def _close_order_assignments(order_name, allocated_to=None):
	try:
		filters = {
			"reference_type": "BEI Store Order",
			"reference_name": order_name,
			"status": "Open",
		}
		if allocated_to:
			filters["allocated_to"] = allocated_to
		for row in frappe.get_all("ToDo", filters=filters, fields=["name"]):
			todo = frappe.get_doc("ToDo", row.name)
			todo.status = "Closed"
			todo.save(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			f"Failed to close ToDo assignments for BEI Store Order {order_name}",
			"Store Order Assignment Close Error",
		)


def _append_order_comment(order_name, content):
	try:
		frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Info",
				"reference_doctype": "BEI Store Order",
				"reference_name": order_name,
				"content": content,
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			f"Failed to add comment on BEI Store Order {order_name}: {content}",
			"Store Order Comment Error",
		)


def _create_approval_queue_entry(order, approver, priority="Normal"):
	if not approver:
		return None
	queue_entry = frappe.new_doc("BEI Approval Queue")
	queue_entry.reference_doctype = "BEI Store Order"
	queue_entry.reference_name = order.name
	queue_entry.assigned_approver = approver
	queue_entry.status = "Pending"
	queue_entry.priority = priority
	queue_entry.store = order.store
	queue_entry.submitted_by = order.submitted_by or frappe.session.user
	queue_entry.submitted_at = frappe.utils.now()
	queue_entry.insert(ignore_permissions=True)
	return queue_entry


def _get_pending_approval_entries(order_name):
	return frappe.get_all(
		"BEI Approval Queue",
		filters={
			"reference_doctype": "BEI Store Order",
			"reference_name": order_name,
			"status": "Pending",
		},
		fields=["name", "assigned_approver", "priority", "submitted_at", "creation"],
		order_by="creation asc",
	)


def _has_approved_stage_entry(order_name, approver):
	if not approver:
		return False
	return bool(
		frappe.db.exists(
			"BEI Approval Queue",
			{
				"reference_doctype": "BEI Store Order",
				"reference_name": order_name,
				"assigned_approver": approver,
				"status": "Approved",
			},
		)
	)


def _get_regional_manager_for_store(warehouse, area_supervisor=None):
	field_candidates = [
		"custom_regional_manager",
		"custom_regional_supervisor",
		"custom_regional_approver",
	]

	warehouse_chain = [warehouse]
	parent = frappe.db.get_value("Warehouse", warehouse, "parent_warehouse")
	if parent:
		warehouse_chain.append(parent)

	for wh in warehouse_chain:
		for fieldname in field_candidates:
			if not _doctype_has_field("Warehouse", fieldname):
				continue
			candidate = frappe.db.get_value("Warehouse", wh, fieldname)
			if candidate and _is_enabled_user(candidate) and _is_regional_manager_user(candidate):
				return candidate, f"warehouse.{fieldname}"

	if area_supervisor:
		area_employee = frappe.db.get_value(
			"Employee",
			{"user_id": area_supervisor, "status": "Active"},
			["name", "reports_to"],
			as_dict=True,
		)
		reports_to = area_employee.get("reports_to") if area_employee else None
		if reports_to:
			manager_user = frappe.db.get_value("Employee", reports_to, "user_id")
			if manager_user and _is_enabled_user(manager_user) and _is_regional_manager_user(manager_user):
				return manager_user, "employee.reports_to"

	regional_manager = _get_regional_manager_fallback_user()
	if regional_manager:
		return regional_manager, "regional_manager_fallback"

	return None, "unmapped"


def _get_regional_manager_fallback_excluding(exclude_user):
	candidate = _get_regional_manager_fallback_user()
	if candidate and candidate != exclude_user:
		return candidate, "regional_manager_fallback"
	return None, "unmapped"


def _resolve_order_approval_routing(warehouse, is_emergency, submitted_after_cutoff):
	area_approver = _get_area_supervisor_for_store(warehouse)
	regional_approver, regional_source = _get_regional_manager_for_store(
		warehouse, area_supervisor=area_approver
	)

	if area_approver and regional_approver and regional_approver == area_approver:
		fallback_regional, fallback_source = _get_regional_manager_fallback_excluding(
			exclude_user=area_approver
		)
		if fallback_regional:
			regional_approver = fallback_regional
			regional_source = fallback_source

	requires_regional_after_area = bool(
		cint(is_emergency)
		and submitted_after_cutoff
		and area_approver
		and regional_approver
		and regional_approver != area_approver
	)

	if area_approver:
		return {
			"first_approver": area_approver,
			"first_source": "area_supervisor",
			"requires_regional_after_area": requires_regional_after_area,
			"regional_approver": regional_approver,
			"regional_source": regional_source,
		}

	if regional_approver:
		return {
			"first_approver": regional_approver,
			"first_source": "regional_manager_fallback",
			"requires_regional_after_area": False,
			"regional_approver": regional_approver,
			"regional_source": regional_source,
		}

	return {
		"first_approver": None,
		"first_source": "unmapped",
		"requires_regional_after_area": False,
		"regional_approver": None,
		"regional_source": "unmapped",
	}


def _infer_area_supervisor_for_store(warehouse, role_cache=None):
	branch_candidates = _warehouse_branch_candidates(warehouse)
	branch_keys = {_normalize_store_key(candidate) for candidate in branch_candidates if candidate}
	if not branch_keys:
		return None

	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "user_id", "designation", "branch", "reports_to"],
		limit_page_length=5000,
	)
	if not employees:
		return _get_default_area_supervisor(role_cache=role_cache, branch_keys=branch_keys)

	branch_employees = [row for row in employees if _normalize_store_key(row.get("branch")) in branch_keys]

	direct_area_users = sorted(
		{
			str(row.get("user_id")).strip()
			for row in branch_employees
			if row.get("user_id") and _is_area_supervisor_user(row.get("user_id"), role_cache=role_cache)
		}
	)

	store_lead_reports_to = sorted(
		{
			str(row.get("reports_to")).strip()
			for row in branch_employees
			if row.get("reports_to") and _designation_is_store_lead(row.get("designation"))
		}
	)

	manager_area_users = []
	if store_lead_reports_to:
		reporting_managers = frappe.get_all(
			"Employee",
			filters={"name": ["in", store_lead_reports_to], "status": "Active"},
			fields=["name", "user_id", "designation", "branch"],
			limit_page_length=max(200, len(store_lead_reports_to)),
		)
		manager_area_users = sorted(
			{
				str(row.get("user_id")).strip()
				for row in reporting_managers
				if row.get("user_id") and _is_area_supervisor_user(row.get("user_id"), role_cache=role_cache)
			}
		)

	prefer_test_store = any("TEST" in key for key in branch_keys)
	if manager_area_users and direct_area_users:
		intersection = sorted(set(manager_area_users).intersection(set(direct_area_users)))
		if intersection:
			return _choose_preferred_area_supervisor(intersection, prefer_test=prefer_test_store)

	if manager_area_users:
		return _choose_preferred_area_supervisor(manager_area_users, prefer_test=prefer_test_store)

	if direct_area_users:
		return _choose_preferred_area_supervisor(direct_area_users, prefer_test=prefer_test_store)

	return _get_default_area_supervisor(role_cache=role_cache, branch_keys=branch_keys)


def _collect_store_area_supervisor_mapping(apply_fixes=False, include_disabled=False, max_rows=200):
	warehouses = frappe.get_all(
		"Warehouse",
		filters={"is_group": 0, "disabled": 0 if not include_disabled else ["in", [0, 1]]},
		fields=["name", "warehouse_name", "custom_area_supervisor", "disabled"],
		order_by="warehouse_name asc",
		limit_page_length=5000,
	)

	role_cache = {}
	rows = []
	updated = 0
	invalid = 0
	unmapped = 0

	for warehouse in warehouses:
		name = warehouse.get("name")
		current = str(warehouse.get("custom_area_supervisor") or "").strip()
		current_valid = _is_area_supervisor_user(current, role_cache=role_cache) if current else False
		resolved = current if current_valid else _infer_area_supervisor_for_store(name, role_cache=role_cache)
		updated_now = False

		if current and not current_valid:
			invalid += 1
		if not resolved:
			unmapped += 1

		if apply_fixes and resolved and current != resolved:
			frappe.db.set_value("Warehouse", name, "custom_area_supervisor", resolved, update_modified=False)
			updated += 1
			updated_now = True

		status = "mapped" if current_valid else "unmapped"
		if current and not current_valid:
			status = "mapped_invalid_role"
		if resolved and not current_valid:
			status = "resolved_by_inference"

		rows.append(
			{
				"warehouse": name,
				"warehouse_name": warehouse.get("warehouse_name"),
				"current_mapping": current or None,
				"resolved_mapping": resolved or None,
				"status": status,
				"updated": updated_now,
			}
		)

	if max_rows and max_rows > 0:
		rows = rows[:max_rows]

	return {
		"total_stores": len(warehouses),
		"updated_mappings": updated,
		"invalid_role_mappings": invalid,
		"unmapped_after_resolution": unmapped,
		"rows": rows,
	}


def _get_area_supervisor_for_store(warehouse, persist_inferred=True):
	"""Resolve area supervisor for a warehouse, validating role and inferring fallback mapping."""
	role_cache = {}

	supervisor = _resolve_valid_area_supervisor(
		frappe.db.get_value("Warehouse", warehouse, "custom_area_supervisor"),
		warehouse=warehouse,
		source="Warehouse.custom_area_supervisor",
		role_cache=role_cache,
	)
	if supervisor:
		return supervisor

	parent = frappe.db.get_value("Warehouse", warehouse, "parent_warehouse")
	if parent:
		parent_supervisor = _resolve_valid_area_supervisor(
			frappe.db.get_value("Warehouse", parent, "custom_area_supervisor"),
			warehouse=warehouse,
			source=f"Parent Warehouse.custom_area_supervisor ({parent})",
			role_cache=role_cache,
		)
		if parent_supervisor:
			return parent_supervisor

	inferred = _infer_area_supervisor_for_store(warehouse, role_cache=role_cache)
	if inferred and persist_inferred:
		try:
			frappe.db.set_value(
				"Warehouse", warehouse, "custom_area_supervisor", inferred, update_modified=False
			)
		except Exception:
			frappe.log_error(
				f"Failed to persist inferred area supervisor '{inferred}' for warehouse {warehouse}.",
				"Store Area Supervisor Mapping",
			)
	return inferred


FROZEN_TOKENS = {
	"frozen",
	"chilled",
	"cold",
	"ice",
	"icecream",
	"meat",
	"chicken",
	"pork",
	"beef",
	"fc",
}
FRESH_MARKET_TOKENS = {
	"fresh",
	"produce",
	"vegetable",
	"vegetables",
	"fruit",
	"fruits",
	"seafood",
	"fish",
	"eggs",
	"fm",
}
DRY_TOKENS = {
	"dry",
	"shelf",
	"stable",
	"canned",
	"rice",
	"flour",
	"sugar",
	"powder",
	"spice",
	"spices",
	"drygoods",
}


def _tokenize_metadata(*parts):
	text = " ".join(str(part or "") for part in parts).lower()
	return set(re.findall(r"[a-z0-9]+", text))


def _normalize_cargo_category(value):
	raw = str(value or "").strip().upper().replace("-", " ").replace("_", " ")
	raw = " ".join(raw.split())
	if raw in {"FC", "FROZEN", "FROZEN CHILLED", "CHILLED"}:
		return "FC"
	if raw in {"FM", "FRESH", "FRESH MARKET", "FRESHMARKET"}:
		return "FM"
	if raw in {"DRY", "DRY GOODS", "DRYGOODS"}:
		return "DRY"
	return ""


def _lane_to_cargo_category(lane):
	if lane == "Frozen":
		return "FC"
	if lane == "Fresh Market":
		return "FM"
	return "DRY"


def _resolve_store_order_source_warehouse(store_warehouse, cargo_category):
	"""Resolve the warehouse that should fulfill a store order lane."""
	return resolve_route_source_warehouse(store_warehouse, cargo_category)


def _resolve_delivery_lane(item_doc):
	"""Infer lane from explicit category first, then tokenized metadata."""
	explicit_category = _normalize_cargo_category(item_doc.get("cargo_category") or item_doc.get("lane"))
	if explicit_category == "FC":
		return "Frozen"
	if explicit_category == "FM":
		return "Fresh Market"

	tokens = _tokenize_metadata(
		item_doc.get("item_name"),
		item_doc.get("item_group"),
		item_doc.get("cargo_category"),
		item_doc.get("lane"),
	)

	if tokens.intersection(FROZEN_TOKENS):
		return "Frozen"
	if tokens.intersection(FRESH_MARKET_TOKENS):
		return "Fresh Market"
	if explicit_category == "DRY":
		return "Dry"
	if tokens.intersection(DRY_TOKENS):
		return "Dry"
	return "Dry"


def _compose_signal_modifiers(is_salary_week=False, is_holiday=False, is_weather_risk=False):
	"""Build deterministic signal multipliers for demand modulation."""
	salary_week_multiplier = 1.10 if is_salary_week else 1.0
	holiday_multiplier = 1.12 if is_holiday else 1.0
	overlap_multiplier = 1.08 if (is_salary_week and is_holiday) else 1.0
	weather_multiplier = 1.06 if is_weather_risk else 1.0
	composite_multiplier = (
		salary_week_multiplier * holiday_multiplier * overlap_multiplier * weather_multiplier
	)
	return {
		"salary_week_multiplier": flt(salary_week_multiplier, 4),
		"holiday_multiplier": flt(holiday_multiplier, 4),
		"overlap_multiplier": flt(overlap_multiplier, 4),
		"weather_multiplier": flt(weather_multiplier, 4),
		"composite_multiplier": flt(composite_multiplier, 4),
	}


def _is_salary_week(target_date):
	return target_date.day <= 7 or 13 <= target_date.day <= 16


def _is_holiday(target_date):
	try:
		return bool(frappe.db.exists("Holiday", {"holiday_date": str(target_date)}))
	except Exception:
		return False


def _is_weather_risk(warehouse):
	"""Graceful weather risk probe; no hard dependency on custom weather doctypes."""
	for doctype in ("BEI Weather Alert", "Weather Alert"):
		try:
			if frappe.db.exists(
				doctype,
				{
					"store": warehouse,
					"severity": ["in", ["Severe", "High", "Typhoon", "Heavy Rain"]],
					"status": ["not in", ["Resolved", "Closed"]],
				},
			):
				return True
		except Exception:
			continue
	return False


def _get_signal_flags(warehouse, for_date=None):
	date_obj = getdate(for_date or nowdate())
	return {
		"is_salary_week": _is_salary_week(date_obj),
		"is_holiday": _is_holiday(date_obj),
		"is_weather_risk": _is_weather_risk(warehouse),
	}


def _apply_adaptive_tuning(current_multiplier, delta, floor=0.70, ceiling=1.50):
	new_multiplier = flt(current_multiplier) + flt(delta)
	return flt(min(max(new_multiplier, floor), ceiling), 4)


def _risk_rank(order_count, recommended_qty, available_to_promise):
	"""Lower rank means higher urgency."""
	shortage_gap = max(0, flt(recommended_qty) - flt(available_to_promise))
	if shortage_gap >= 20:
		return 1
	if shortage_gap > 0:
		return 2
	if flt(order_count) >= 8:
		return 3
	return 4


def _build_recommendation_contract(
	last_order_qty,
	available_to_promise,
	lane,
	order_count=0,
	signal_multiplier=1.0,
	projected_sales=0.0,
	bom_consumption=0.0,
	coverage_window_days=1,
):
	baseline = flt(last_order_qty)
	if baseline <= 0:
		baseline = max(1.0, flt(order_count) * 0.5)
	projected_sales = flt(projected_sales or (baseline * 0.60), 2)
	bom_consumption = flt(bom_consumption or (baseline * 0.40), 2)
	coverage_window_days = max(1.0, flt(coverage_window_days))
	forecast_demand = flt(
		(projected_sales + bom_consumption) * flt(signal_multiplier) * coverage_window_days,
		2,
	)
	safety_buffer = flt(max(1.0, forecast_demand * 0.15), 2)
	recommended_qty = flt(
		max(0.0, forecast_demand + safety_buffer - flt(available_to_promise)),
		2,
	)
	return {
		"lane": lane,
		"available_to_promise": flt(available_to_promise, 2),
		"coverage_window_days": coverage_window_days,
		"projected_sales": projected_sales,
		"bom_consumption": bom_consumption,
		"forecast_demand": forecast_demand,
		"safety_buffer": safety_buffer,
		"recommended_qty": recommended_qty,
		# S019 compatibility: suggested_qty remains canonical persistence field.
		"suggested_qty": recommended_qty,
		"risk_rank": _risk_rank(order_count, recommended_qty, available_to_promise),
	}


def _coverage_window_days_for_lane(lane):
	if lane == "Frozen":
		return 2
	if lane == "Fresh Market":
		return 1
	return 3


def _parse_snapshot_source_reference(raw_value):
	if isinstance(raw_value, dict):
		return raw_value
	text = str(raw_value or "").strip()
	if not text:
		return {}
	try:
		parsed = json.loads(text)
	except Exception:
		return {}
	return parsed if isinstance(parsed, dict) else {}


def _load_store_item_demand_snapshots(warehouse, item_codes, target_date):
	"""Load latest snapshot rows per item on or before the target date."""
	if not warehouse or not item_codes:
		return {}

	try:
		rows = frappe.get_all(
			"BEI Inventory Risk Snapshot",
			filters={
				"warehouse": warehouse,
				"item_code": ["in", item_codes],
				"snapshot_date": ["<=", str(target_date)],
			},
			fields=[
				"item_code",
				"warehouse",
				"snapshot_date",
				"avg_daily_demand",
				"available_qty",
				"source_reference",
			],
			order_by="snapshot_date desc, modified desc",
			limit_page_length=max(200, len(item_codes) * 4),
		)
	except Exception:
		return {}

	snapshots = {}
	for row in rows or []:
		item_code = row.get("item_code")
		if not item_code or item_code in snapshots:
			continue
		source_reference = _parse_snapshot_source_reference(row.get("source_reference"))
		snapshots[item_code] = {
			"snapshot_date": row.get("snapshot_date"),
			"avg_daily_demand": flt(row.get("avg_daily_demand"), 4),
			"available_qty": flt(row.get("available_qty"), 2),
			"projected_sales": flt(source_reference.get("projected_sales"), 2),
			"bom_consumption": flt(source_reference.get("bom_consumption"), 2),
			"coverage_window_days": flt(source_reference.get("coverage_window_days"), 2),
			"lookback_days": cint(source_reference.get("lookback_days") or 0),
			"signal_source": source_reference.get("signal_source") or "sales_demand_snapshot",
			"source_reference": source_reference,
		}

	return snapshots


def _estimate_projected_sales_and_bom(last_order_qty, order_count, lane):
	baseline = max(1.0, flt(last_order_qty), flt(order_count) * 0.75)
	projected_sales = flt(baseline * 0.65, 2)
	bom_factor = 0.35 if lane in {"Frozen", "Fresh Market"} else 0.25
	bom_consumption = flt(max(0.5, baseline * bom_factor), 2)
	return projected_sales, bom_consumption


def _get_adaptive_delta(warehouse):
	"""Estimate adaptive tuning delta from recent ordering behavior."""
	try:
		since_date = add_days(nowdate(), -28)
		rows = frappe.db.sql(
			"""
            SELECT
                soi.qty_requested,
                COALESCE(NULLIF(soi.recommended_qty, 0), soi.suggested_qty, 0) AS baseline_qty
            FROM `tabBEI Store Order Item` soi
            INNER JOIN `tabBEI Store Order` so ON so.name = soi.parent
            WHERE so.store = %(warehouse)s
              AND so.status NOT IN ('Draft', 'Cancelled')
              AND so.order_date >= %(since_date)s
            ORDER BY so.order_date DESC
            LIMIT 400
        """,
			{"warehouse": warehouse, "since_date": since_date},
			as_dict=True,
		)
	except Exception:
		return 0.0

	ratios = []
	for row in rows or []:
		baseline_qty = flt(row.get("baseline_qty"))
		if baseline_qty <= 0:
			continue
		qty_requested = flt(row.get("qty_requested"))
		ratios.append((qty_requested - baseline_qty) / baseline_qty)

	if not ratios:
		return 0.0

	avg_ratio = sum(ratios) / len(ratios)
	# Keep adaptive effect conservative.
	return flt(min(max(avg_ratio * 0.10, -0.08), 0.08), 4)


def _normalize_order_line(item_data, lane="Dry"):
	recommended_qty = flt(item_data.get("recommended_qty", item_data.get("suggested_qty", 0)))
	qty_requested = flt(item_data.get("qty_requested", 0))
	is_edited = 1 if qty_requested != recommended_qty else 0
	deviation_reason = item_data.get("deviation_reason") or item_data.get("reason_for_edit") or ""
	return {
		"item_code": item_data.get("item_code"),
		"qty_requested": qty_requested,
		"suggested_qty": recommended_qty,
		"recommended_qty": recommended_qty,
		"lane": lane,
		"available_to_promise": flt(item_data.get("available_to_promise", 0)),
		"forecast_demand": flt(item_data.get("forecast_demand", 0)),
		"safety_buffer": flt(item_data.get("safety_buffer", 0)),
		"risk_rank": cint(item_data.get("risk_rank", 4)),
		"is_edited": is_edited,
		"deviation_reason": deviation_reason,
	}


def _sanitize_submitted_items(items):
	"""Keep only rows with valid item code and positive qty."""
	sanitized = []
	dropped = []
	for row in items or []:
		if not isinstance(row, dict):
			dropped.append({"item_code": "", "reason": "invalid_row_type"})
			continue

		item_code = str(row.get("item_code") or "").strip()
		qty_requested = flt(row.get("qty_requested", 0))

		if not item_code:
			dropped.append({"item_code": "", "reason": "missing_item_code"})
			continue
		if qty_requested <= 0:
			dropped.append({"item_code": item_code, "reason": "non_positive_qty"})
			continue

		normalized = dict(row)
		normalized["item_code"] = item_code
		normalized["qty_requested"] = qty_requested
		sanitized.append(normalized)

	return sanitized, dropped


@frappe.whitelist()
def get_user_store():
	"""
	Resolve the current user's store(s) based on their role.

	Store Staff / Store Supervisor: Returns store from Employee.branch
	Area Supervisor: Returns all stores where Warehouse.custom_area_supervisor = user

	Returns:
	    {
	        "stores": [{"name": "Store Name - BEI", "warehouse_name": "Store Name"}],
	        "default_store": "Store Name - BEI",
	        "is_multi_store": false,
	        "role": "Store Staff"
	    }
	"""
	user = frappe.session.user
	user_roles = frappe.get_roles(user)

	stores = []
	role = None

	if "Area Supervisor" in user_roles:
		# Area supervisors see all stores assigned to them
		role = "Area Supervisor"
		area_stores = frappe.get_all(
			"Warehouse",
			filters={"custom_area_supervisor": user, "is_group": 0},
			fields=["name", "warehouse_name"],
			order_by="warehouse_name",
		)
		stores = area_stores

	if not stores and (
		"Store Supervisor" in user_roles or "Store Staff" in user_roles or "Employee" in user_roles
	):
		# Store staff/supervisors get their branch from Employee record
		role = "Store Supervisor" if "Store Supervisor" in user_roles else "Store Staff"
		employee = frappe.db.get_value(
			"Employee",
			{"user_id": user, "status": "Active"},
			["name", "branch", "employee_name", "reports_to"],
			as_dict=True,
		)
		if employee:
			store_context = resolve_employee_store_context(employee)
			if store_context.get("warehouse"):
				stores = [
					{
						"name": store_context["warehouse"],
						"warehouse_name": store_context["warehouse_name"],
					}
				]

	# System / HR / Regional fallback - return all stores
	if not stores and (
		"System Manager" in user_roles
		or "HR User" in user_roles
		or "HR Manager" in user_roles
		or "Regional Manager" in user_roles
	):
		role = "Regional Manager" if "Regional Manager" in user_roles else "HR User"
		stores = frappe.get_all(
			"Warehouse",
			filters={"is_group": 0, "disabled": 0},
			fields=["name", "warehouse_name"],
			order_by="warehouse_name",
			limit=50,
		)

	default_store = stores[0]["name"] if stores else None

	return {"stores": stores, "default_store": default_store, "is_multi_store": len(stores) > 1, "role": role}


@frappe.whitelist()
def audit_store_area_supervisor_mapping(
	apply_fixes: int | str = 0, include_disabled: int | str = 0, max_rows: int | str = 200
):
	"""Audit and optionally fix store-to-area-supervisor mappings.

	Only System Manager / HR Manager / Administrator may execute this operation.
	"""
	user_roles = set(frappe.get_roles(frappe.session.user))
	if not user_roles.intersection({"System Manager", "HR Manager", "Administrator"}):
		frappe.throw(
			_("Only System Manager, HR Manager, or Administrator can audit supervisor mappings."),
			frappe.PermissionError,
		)

	return _collect_store_area_supervisor_mapping(
		apply_fixes=bool(cint(apply_fixes)),
		include_disabled=bool(cint(include_disabled)),
		max_rows=cint(max_rows) or 0,
	)


@frappe.whitelist()
def get_orderable_items(store: str, date: str | None = None) -> dict:
	"""
	Get items available for ordering by this store.
	Returns lane-aware recommendation fields while preserving `suggested_qty`
	as canonical persisted field for S019 compatibility.
	"""
	if not store:
		frappe.throw(_("Store is required"))

	# Resolve branch name to warehouse name
	warehouse = resolve_warehouse(store)

	# Get items with order frequency for this store, sorted by most ordered first
	items = frappe.db.sql(
		"""
        SELECT
            i.name, i.item_name, i.item_group, i.stock_uom, i.image,
            COALESCE(freq.order_count, 0) as order_count
        FROM `tabItem` i
        LEFT JOIN (
            SELECT soi.item_code, COUNT(DISTINCT soi.parent) as order_count
            FROM `tabBEI Store Order Item` soi
            JOIN `tabBEI Store Order` so ON so.name = soi.parent
            WHERE so.store = %s AND so.status != 'Draft'
            GROUP BY soi.item_code
        ) freq ON freq.item_code = i.name
        WHERE i.is_stock_item = 1 AND i.disabled = 0
        ORDER BY COALESCE(freq.order_count, 0) DESC, i.item_group, i.item_name
    """,
		warehouse,
		as_dict=True,
	)

	# V-14 fix: Batch query for last order quantities (was N+1: 2 queries per item).
	# Gets the most recent non-Draft order qty for each item in a single SQL query.
	last_qty_map = {}
	last_qty_rows = frappe.db.sql(
		"""
        SELECT oi.item_code, oi.qty_requested
        FROM `tabBEI Store Order Item` oi
        INNER JOIN `tabBEI Store Order` o ON o.name = oi.parent
        WHERE o.store = %(warehouse)s AND o.status != 'Draft'
            AND oi.creation = (
                SELECT MAX(oi2.creation)
                FROM `tabBEI Store Order Item` oi2
                INNER JOIN `tabBEI Store Order` o2 ON o2.name = oi2.parent
                WHERE o2.store = %(warehouse)s AND o2.status != 'Draft'
                    AND oi2.item_code = oi.item_code
            )
    """,
		{"warehouse": warehouse},
		as_dict=True,
	)
	for row in last_qty_rows:
		last_qty_map[row.item_code] = row.qty_requested

	# Batch stock quantities (available-to-promise approximation)
	stock_map = {}
	item_codes = [row.name for row in items]
	if item_codes:
		stock_rows = frappe.get_all(
			"Bin",
			filters={"warehouse": warehouse, "item_code": ["in", item_codes]},
			fields=["item_code", "actual_qty"],
			limit_page_length=max(200, len(item_codes) * 3),
		)
		for row in stock_rows:
			stock_map[row.item_code] = flt(stock_map.get(row.item_code, 0)) + flt(row.actual_qty)

	target_date = getdate(date or nowdate())
	signal_flags = _get_signal_flags(warehouse, for_date=target_date)
	signal_modifiers = _compose_signal_modifiers(**signal_flags)
	adaptive_delta = _get_adaptive_delta(warehouse)
	tuned_multiplier = _apply_adaptive_tuning(signal_modifiers["composite_multiplier"], adaptive_delta)
	demand_snapshots = _load_store_item_demand_snapshots(warehouse, item_codes, target_date)

	for item in items:
		item_code = item.name
		last_order_qty = flt(last_qty_map.get(item_code, 0))
		available_to_promise = flt(stock_map.get(item_code, 0), 2)
		lane = _resolve_delivery_lane(item)
		snapshot = demand_snapshots.get(item_code) or {}
		coverage_window_days = flt(snapshot.get("coverage_window_days") or 0)
		if coverage_window_days <= 0:
			coverage_window_days = _coverage_window_days_for_lane(lane)

		projected_sales = flt(snapshot.get("projected_sales"), 2)
		bom_consumption = flt(snapshot.get("bom_consumption"), 2)
		if projected_sales > 0 or bom_consumption > 0:
			recommendation_source = snapshot.get("signal_source") or "sales_demand_snapshot"
			avg_daily_demand = flt(
				snapshot.get("avg_daily_demand") or (projected_sales + bom_consumption),
				4,
			)
		else:
			projected_sales, bom_consumption = _estimate_projected_sales_and_bom(
				last_order_qty, flt(item.order_count), lane
			)
			recommendation_source = "heuristic"
			avg_daily_demand = flt(projected_sales + bom_consumption, 4)

		contract = _build_recommendation_contract(
			last_order_qty=last_order_qty,
			available_to_promise=available_to_promise,
			lane=lane,
			order_count=flt(item.order_count),
			signal_multiplier=tuned_multiplier,
			projected_sales=projected_sales,
			bom_consumption=bom_consumption,
			coverage_window_days=coverage_window_days,
		)
		item["item_code"] = item_code
		item["uom"] = item.get("stock_uom")
		item["last_order_qty"] = last_order_qty
		item["available_stock"] = available_to_promise
		item["is_oos"] = 1 if available_to_promise <= 0 else 0
		item["cargo_category"] = _lane_to_cargo_category(lane)
		item["packaging_description"] = item.get("stock_uom") or ""
		item["signal_multiplier"] = tuned_multiplier
		item["avg_daily_demand"] = avg_daily_demand
		item["recommendation_source"] = recommendation_source
		item["demand_snapshot_date"] = snapshot.get("snapshot_date")
		item["lookback_days"] = cint(snapshot.get("lookback_days") or 0)
		item.update(contract)

	items = sorted(
		items,
		key=lambda row: (
			cint(row.get("risk_rank", 4)),
			-flt(row.get("order_count", 0)),
			row.get("item_group") or "",
			row.get("item_name") or "",
		),
	)

	return {"items": items}


def _get_order_cutoff():
	"""Read order cutoff hour from BEI Settings.

	Returns (cutoff_hour, cutoff_time) where cutoff_hour is the integer hour
	(default 12) and cutoff_time is the display string (e.g. "11:59").
	"""
	cutoff_hour = 12
	try:
		meta = frappe.get_meta("BEI Settings")
		cutoff_field = None
		for candidate in ("order_cutoff_hour", "ordering_cutoff_hour"):
			if meta.has_field(candidate):
				cutoff_field = candidate
				break
		if cutoff_field:
			raw = frappe.db.get_single_value("BEI Settings", cutoff_field)
			cutoff_hour = int(raw) if raw else 12
	except Exception:
		# Missing/legacy settings fields should not block order submission.
		cutoff_hour = 12
	cutoff_hour = max(1, min(cutoff_hour, 23))
	cutoff_time = f"{cutoff_hour - 1:02d}:59"
	return cutoff_hour, cutoff_time


def _validate_order_cutoff(store, is_emergency=False):
	"""
	Validate that order submission is within the allowed cutoff time.
	Default cutoff: 11:59 AM (from Ian questionnaire 2026-02-17, same for all stores).
	Configurable via BEI Settings.order_cutoff_hour.
	Emergency orders bypass the cutoff but are logged.
	"""
	cutoff_hour, cutoff_time = _get_order_cutoff()

	if now_datetime().hour >= cutoff_hour:
		if is_emergency:
			frappe.log_error(
				f"Emergency order submitted after cutoff {cutoff_time} by {frappe.session.user} for store {store}",
				"Emergency Order After Cutoff",
			)
			return
		frappe.throw(
			_(
				"Order submission closed. Daily cutoff is {0}. "
				"Contact your Area Supervisor for emergency orders."
			).format(cutoff_time)
		)


@frappe.whitelist()
def validate_order_schedule(store: str, date: str | None = None) -> dict:
	"""
	Check if order submission is currently allowed for the given store.
	Frontend can call this before showing the order form.
	Returns {allowed: true/false, cutoff_time: "11:59", reason/message: "...", next_delivery_day: "..."}
	"""
	if not store:
		frappe.throw(_("Store is required"))

	cutoff_hour, cutoff_time = _get_order_cutoff()
	allowed = now_datetime().hour < cutoff_hour
	requested_date = getdate(date or nowdate())
	next_delivery_date = add_days(str(requested_date), 1)
	next_delivery_day = getdate(next_delivery_date).strftime("%A, %Y-%m-%d")
	reason = (
		f"Ordering is open until {cutoff_time}"
		if allowed
		else f"Ordering closed at {cutoff_time}. Contact your Area Supervisor for emergency orders."
	)

	return {
		"allowed": allowed,
		"cutoff_time": cutoff_time,
		"reason": reason,
		"message": reason,
		"next_delivery_day": next_delivery_day,
	}


@frappe.whitelist()
def submit_order(
	store: str,
	items: list | str,
	cargo_category: str | None = None,
	delivery_date: str | None = None,
	is_emergency: bool | int | str = False,
	notes: str = "",
) -> dict:
	"""
	Submit a new store order.

	Args:
	    store (str): Warehouse name or branch code for the store
	    items (list): [{item_code, qty_requested, deviation_reason?}]
	    cargo_category (str): FC | DRY | FM (required — BEI Store Order has reqd: 1)
	    delivery_date (str, optional): Requested delivery date (defaults to tomorrow)
	    is_emergency (bool/int): If True, bypasses cutoff gate (logs but allows)
	    notes (str): Optional order notes
	"""
	if not store:
		frappe.throw(_("Store is required"))

	normalized_cargo_category = _normalize_cargo_category(cargo_category)
	if not normalized_cargo_category:
		frappe.throw(_("Cargo category is required (FC, DRY, or FM)"))

	is_emergency_flag = frappe.utils.cint(is_emergency)
	cutoff_hour, cutoff_time = _get_order_cutoff()
	submitted_after_cutoff = now_datetime().hour >= cutoff_hour

	# Validate ordering schedule cutoff
	_validate_order_cutoff(store, is_emergency=is_emergency_flag)

	# Resolve branch name to warehouse name
	warehouse = resolve_warehouse(store)

	if isinstance(items, str):
		items = json.loads(items)

	sanitized_items, dropped_items = _sanitize_submitted_items(items)
	if not sanitized_items:
		frappe.throw(_("At least one item with quantity greater than zero is required"))
	if dropped_items:
		frappe.log_error(
			json.dumps(dropped_items),
			f"Store order payload had dropped lines ({warehouse})",
		)
	items = sanitized_items

	order_date = nowdate()

	# Duplicate check: no existing non-cancelled order for same store + date + category
	if not is_emergency_flag:
		existing = frappe.db.exists(
			"BEI Store Order",
			{
				"store": warehouse,
				"order_date": order_date,
				"cargo_category": normalized_cargo_category,
				"status": ["not in", ["Cancelled"]],
			},
		)
		if existing:
			frappe.throw(
				_("An order already exists for {0} on {1} for category {2}: {3}").format(
					warehouse, order_date, normalized_cargo_category, existing
				)
			)

	# Validate quantities - prevent unreasonable orders
	MAX_ORDER_QTY = 10000
	for item_data in items:
		qty = flt(item_data.get("qty_requested", 0))
		if qty > MAX_ORDER_QTY:
			frappe.throw(
				_("Order quantity {0} exceeds maximum allowed ({1}) for item {2}").format(
					qty, MAX_ORDER_QTY, item_data.get("item_code")
				)
			)

	item_codes = [row.get("item_code") for row in items if row.get("item_code")]
	item_meta = {}
	if item_codes:
		item_fields = ["name", "item_group", "item_name"]
		try:
			if frappe.get_meta("Item").has_field("cargo_category"):
				item_fields.append("cargo_category")
		except Exception:
			pass

		for row in frappe.get_all(
			"Item",
			filters={"name": ["in", item_codes]},
			fields=item_fields,
			limit_page_length=max(200, len(item_codes)),
		):
			item_meta[row.name] = row

	# Determine is_bulk_order: bulk if more than 10 line items
	is_bulk_order = 1 if len(items) > 10 else 0

	order = frappe.new_doc("BEI Store Order")
	order.store = warehouse
	order.order_date = order_date
	order.delivery_date = delivery_date or add_days(nowdate(), 1)
	order.cargo_category = normalized_cargo_category
	order.is_emergency = is_emergency_flag
	order.is_bulk_order = is_bulk_order
	order.notes = notes
	order.status = "Pending Approval"
	order.submitted_by = frappe.session.user

	edited_lines_count = 0
	for item_data in items:
		item_code = item_data.get("item_code")
		meta = dict(item_meta.get(item_code, {}) or {})
		meta["lane"] = item_data.get("lane")
		if item_data.get("cargo_category"):
			meta["cargo_category"] = item_data.get("cargo_category")
		lane = _resolve_delivery_lane(meta)
		expected_category = _lane_to_cargo_category(lane)
		if expected_category != normalized_cargo_category:
			frappe.throw(
				_(
					"Item {0} resolves to lane {1} ({2}) but order category is {3}. "
					"Submit each lane separately."
				).format(item_code, lane, expected_category, normalized_cargo_category)
			)
		normalized = _normalize_order_line(item_data, lane=lane)
		if normalized["is_edited"]:
			edited_lines_count += 1
		order.append("items", normalized)

	routing = _resolve_order_approval_routing(
		warehouse=warehouse,
		is_emergency=is_emergency_flag,
		submitted_after_cutoff=submitted_after_cutoff,
	)
	first_approver = routing["first_approver"]
	first_source = routing["first_source"]
	requires_regional_after_area = bool(routing["requires_regional_after_area"])
	regional_approver = routing["regional_approver"]
	regional_source = routing["regional_source"]

	requires_manual_approval = bool(
		is_bulk_order
		or edited_lines_count > 0
		or requires_regional_after_area
		or (is_emergency_flag and submitted_after_cutoff)
	)
	if requires_manual_approval and not first_approver:
		frappe.throw(
			_(
				"Order requires Area Supervisor approval but no valid Area Supervisor mapping was found for {0}, "
				"and Regional Manager fallback {1} is unavailable. Please update Warehouse.custom_area_supervisor "
				"or provision fallback approver access before submitting."
			).format(warehouse, REGIONAL_MANAGER_FALLBACK_EMAIL)
		)

	order.insert(ignore_permissions=True)

	warning = None
	queue_status = "not_required"
	queue_name = None
	if order.status == "Pending Approval" and requires_manual_approval:
		queue_status = "pending"
		try:
			if first_approver:
				queue_priority = "Urgent" if is_emergency_flag and submitted_after_cutoff else "Normal"
				queue_entry = _create_approval_queue_entry(
					order=order,
					approver=first_approver,
					priority=queue_priority,
				)
				queue_name = queue_entry.name if queue_entry else None
				assigned = _assign_order_for_approval(
					order_name=order.name,
					assigned_to=first_approver,
					description=(
						f"Store order {order.name} requires your approval."
						if not requires_regional_after_area
						else f"Store order {order.name} requires your Stage 1 approval before regional sign-off."
					),
				)
				queue_status = "created" if assigned else "failed"
				if not assigned:
					warning = (
						f"Order {order.name} created, but approver assignment to {first_approver} failed."
					)
			else:
				queue_status = "unmapped"
				warning = "Order created but no approver mapping was found for this store."
		except Exception:
			frappe.log_error(
				f"Failed to create approval queue for order {order.name}", "Approval Queue Error"
			)
			warning = "Order created but approval routing failed. Please notify your approver manually."
			queue_status = "failed"

	if requires_regional_after_area and regional_approver:
		_append_order_comment(
			order.name,
			_(
				"Emergency order submitted after cutoff {0}. Approval chain: Area Supervisor -> Regional Manager ({1})."
			).format(cutoff_time, regional_approver),
		)
	elif first_source == "regional_manager_fallback" and first_approver:
		_append_order_comment(
			order.name,
			_("Area Supervisor mapping missing; routed directly to Regional Manager ({0}).").format(
				first_approver
			),
		)

	result = {
		"success": True,
		"name": order.name,
		"status": order.status,
		"requires_area_supervisor_review": bool(
			requires_manual_approval and first_source == "area_supervisor"
		),
		"requires_regional_manager_review": bool(requires_regional_after_area),
		"edited_lines_count": edited_lines_count,
		"message": f"Order {order.name} submitted successfully",
		"approval_queue_status": queue_status,
		"approval_queue_name": queue_name,
		"approval_approver_source": first_source if requires_manual_approval else "not_required",
		"approval_assigned_approver": first_approver if requires_manual_approval else None,
		"regional_approver": regional_approver,
		"regional_approver_source": regional_source,
		"submitted_after_cutoff": bool(submitted_after_cutoff),
		"is_emergency": bool(is_emergency_flag),
		"cargo_category": normalized_cargo_category,
		"dropped_invalid_lines": len(dropped_items),
	}
	if warning:
		result["warning"] = warning
	_notify_store_ops(
		event={
			"family": "store_order_new",
			"source_system": "frappe",
			"source_ref": order.name,
			"severity": "critical" if is_emergency_flag else "medium",
			"owner": "Store Ops / Warehouse",
			"facts": {
				"order_name": order.name,
				"warehouse": warehouse,
				"item_count": len(items),
				"is_emergency": bool(is_emergency_flag),
				"queue_status": queue_status,
				"approval_queue_name": queue_name,
				"approval_assigned_approver": first_approver if requires_manual_approval else None,
				"dashboard_url": "https://my.bebang.ph/dashboard/store-ops/order-approvals",
			},
		},
		requested_space=get_chat_space(SPACE_OPS),
	)
	return result


@frappe.whitelist()
def get_order_history(store: str | None = None, limit: int | str = 20) -> dict:
	"""Get past orders for a store."""
	if not store:
		return {"orders": []}

	# Resolve branch name to warehouse name
	warehouse = resolve_warehouse(store)

	orders = frappe.get_all(
		"BEI Store Order",
		filters={"store": warehouse},
		fields=["name", "order_date", "delivery_date", "status", "submitted_by", "approved_by"],
		order_by="creation desc",
		limit=int(limit),
	)

	# Get item counts for each order
	for order in orders:
		order["item_count"] = frappe.db.count("BEI Store Order Item", {"parent": order.name})

	return {"orders": orders}


@frappe.whitelist()
def get_order_review_queue(date: str | None = None, status: str | None = None) -> dict:
	"""Canonical store namespace wrapper for order review queue."""
	from hrms.api.ordering import get_order_review_queue as ordering_queue

	return ordering_queue(date=date, status=status)


@frappe.whitelist()
def approve_order(order_name: str, approved_quantities: list | str | None = None) -> dict:
	"""
	Approve a store order with staged routing support.
	- Regular/manual orders: single-step approval
	- Emergency orders submitted after cutoff: Area Supervisor -> Regional Manager
	"""
	user = frappe.session.user
	order = frappe.get_doc("BEI Store Order", order_name)

	if order.status != "Pending Approval":
		frappe.throw(_("Order is not pending approval"))

	pending_entries = _get_pending_approval_entries(order_name)
	active_entry = pending_entries[0] if pending_entries else None
	assigned_approver = active_entry.get("assigned_approver") if active_entry else None

	is_system_user = _is_system_approver(user)
	if assigned_approver:
		if assigned_approver != user and not is_system_user:
			frappe.throw(
				_("Order {0} is currently assigned to {1}.").format(order_name, assigned_approver),
				frappe.PermissionError,
			)
	else:
		user_roles = set(frappe.get_roles(user))
		allowed_roles = {AREA_SUPERVISOR_ROLE, REGIONAL_MANAGER_ROLE}.union(SYSTEM_APPROVER_ROLES)
		if not user_roles.intersection(allowed_roles):
			frappe.throw(
				_(
					"Only assigned approvers, Area Supervisors, Regional Managers, or System Managers can approve."
				),
				frappe.PermissionError,
			)

	approved_qty_map = {}
	if approved_quantities:
		parsed = approved_quantities
		if isinstance(parsed, str):
			parsed = json.loads(parsed)
		if isinstance(parsed, list):
			for row in parsed:
				item_code = (row or {}).get("item_code")
				if not item_code:
					continue
				approved_qty_map[item_code] = flt((row or {}).get("qty_approved", 0))
		elif isinstance(parsed, dict):
			for item_code, qty in parsed.items():
				approved_qty_map[item_code] = flt(qty)

	for item in order.items:
		if item.item_code in approved_qty_map:
			item.qty_approved = approved_qty_map[item.item_code]
		elif not flt(getattr(item, "qty_approved", 0)):
			item.qty_approved = item.qty_requested

	cutoff_hour, _cutoff_time = _get_order_cutoff()
	order_created_dt = get_datetime(order.creation) if getattr(order, "creation", None) else now_datetime()
	submitted_after_cutoff = order_created_dt.hour >= cutoff_hour
	routing = _resolve_order_approval_routing(
		warehouse=order.store,
		is_emergency=order.is_emergency,
		submitted_after_cutoff=submitted_after_cutoff,
	)
	area_approver = _get_area_supervisor_for_store(order.store)
	regional_approver = routing.get("regional_approver")
	requires_dual_stage = bool(routing.get("requires_regional_after_area"))

	current_stage = "single_step"
	if assigned_approver and assigned_approver == area_approver:
		current_stage = "area_supervisor"
	elif assigned_approver and assigned_approver == regional_approver:
		current_stage = "regional_manager"
	elif requires_dual_stage:
		if user == area_approver:
			current_stage = "area_supervisor"
		elif user == regional_approver:
			current_stage = "regional_manager"

	if requires_dual_stage and current_stage == "regional_manager":
		if not _has_approved_stage_entry(order_name, area_approver):
			frappe.throw(
				_("Area Supervisor approval is required before Regional Manager final approval."),
				frappe.PermissionError,
			)

	if requires_dual_stage and current_stage == "single_step" and not is_system_user:
		frappe.throw(
			_("Dual-stage approval is configured, but current approval stage could not be resolved."),
			frappe.PermissionError,
		)

	if active_entry:
		queue_doc = frappe.get_doc("BEI Approval Queue", active_entry["name"])
		queue_doc.status = "Approved"
		queue_doc.approved_by = user
		queue_doc.approved_at = now_datetime()
		queue_doc.save(ignore_permissions=True)
		_close_order_assignments(order_name, allocated_to=assigned_approver)

	is_area_stage_approval = current_stage == "area_supervisor"
	should_forward_to_regional = bool(
		requires_dual_stage and is_area_stage_approval and regional_approver and regional_approver != user
	)

	if should_forward_to_regional:
		order.status = "Pending Approval"
		order.save(ignore_permissions=True)

		queue_entry = None
		try:
			queue_entry = _create_approval_queue_entry(
				order=order,
				approver=regional_approver,
				priority="Urgent",
			)
		except Exception:
			frappe.log_error(
				f"Failed to create regional approval queue for order {order_name}",
				"Store Order Regional Queue Error",
			)
		assigned_ok = False
		if queue_entry:
			assigned_ok = _assign_order_for_approval(
				order_name=order_name,
				assigned_to=regional_approver,
				description=(
					f"Store order {order_name} completed Area Supervisor approval. "
					"Regional Manager final approval required."
				),
			)
			_append_order_comment(
				order_name,
				_(
					"Area Supervisor approval completed by {0}. Routed to Regional Manager ({1}) for final sign-off."
				).format(user, regional_approver),
			)

		_notify_store_ops(
			event={
				"family": "store_order_approved",
				"source_system": "frappe",
				"source_ref": order_name,
				"severity": "high",
				"owner": regional_approver or "Regional Manager",
				"facts": {
					"order_name": order_name,
					"stage": "area_supervisor_forwarded",
					"store": order.store,
					"approved_by": user,
					"regional_approver": regional_approver,
					"dashboard_url": "https://my.bebang.ph/dashboard/store-ops/order-approvals",
				},
			},
			requested_space=get_chat_space(SPACE_OPS),
		)
		return {
			"success": True,
			"status": order.status,
			"stage": "area_supervisor",
			"message": f"Area Supervisor approval captured. Routed to Regional Manager ({regional_approver}).",
			"requires_regional_manager_review": True,
			"approval_approver_source": "regional_manager",
			"approval_assigned_approver": regional_approver,
			"approval_queue_status": "created" if queue_entry and assigned_ok else "failed",
			"material_request": None,
			"dr_number": "",
		}

	order.status = "Approved"
	order.approved_by = user
	order.approved_at = now_datetime()
	order.save(ignore_permissions=True)
	_close_order_assignments(order_name)

	# Create the warehouse dispatch request inside the same transaction so the
	# order cannot report success while the downstream fulfillment contract is broken.
	mr_name = _create_mr_for_store_order(order)
	if not mr_name:
		frappe.throw(
			_(
				"Failed to create the warehouse dispatch request for order {0}. "
				"Check route/source warehouse configuration and retry."
			).format(order_name)
		)

	store_space = None
	try:
		store_space = frappe.db.get_value("Warehouse", order.store, "custom_gchat_space")
	except Exception:
		store_space = None

	_notify_store_ops(
		event={
			"family": "store_order_approved",
			"source_system": "frappe",
			"source_ref": order_name,
			"severity": "medium",
			"owner": "Warehouse / Store Ops",
			"facts": {
				"order_name": order_name,
				"stage": "approved",
				"store": order.store,
				"approved_by": user,
				"material_request": mr_name,
				"dashboard_url": "https://my.bebang.ph/dashboard/store-ops/order-approvals",
			},
		},
		requested_space=store_space or get_chat_space(SPACE_OPS),
	)
	final_stage = "regional_manager" if requires_dual_stage else current_stage

	return {
		"success": True,
		"message": f"Order {order_name} approved",
		"status": order.status,
		"stage": final_stage,
		"approval_queue_status": "completed",
		"requires_regional_manager_review": False,
		"approval_approver_source": final_stage,
		"material_request": mr_name,
		"dr_number": mr_name or "",
	}


@frappe.whitelist()
def reject_order(order_name: str, reason: str) -> dict:
	"""Canonical store namespace wrapper for rejecting pending orders."""
	from hrms.api.ordering import reject_order as ordering_reject

	return ordering_reject(order_name=order_name, reason=reason)


def _create_mr_for_store_order(order):
	"""
	Create a Material Request (Material Transfer) for an approved BEI Store Order.
	Sets custom_store_order so warehouse dispatch can trace MR -> originating store order.

	Returns the MR name, or None if creation fails so the caller can abort approval.
	"""
	try:
		required_by = add_days(nowdate(), 1)

		mr = frappe.new_doc("Material Request")
		mr.material_request_type = "Material Transfer"
		mr.transaction_date = nowdate()
		mr.schedule_date = required_by
		mr.custom_store_order = order.name

		# Destination warehouse is the store's warehouse (field name is "store" on BEI Store Order)
		store_warehouse = order.store
		if not store_warehouse:
			frappe.log_error(f"No store warehouse found on order {order.name}", "Store Ordering")
			return None
		cargo_category = getattr(order, "cargo_category", None) or "DRY"
		source_warehouse = _resolve_store_order_source_warehouse(store_warehouse, cargo_category)
		buyer_entity_row = resolve_store_buyer_entity(warehouse_docname=store_warehouse)
		source_company = resolve_warehouse_company(source_warehouse) or get_company()
		target_company = (
			str(buyer_entity_row.get("buyer_entity_name") or "").strip()
			or resolve_warehouse_company(store_warehouse)
			or source_company
		)
		finance_treatment = infer_finance_treatment(source_company, target_company)
		operational_target_warehouse = store_warehouse
		if finance_treatment != FINANCE_TREATMENT_SAME_COMPANY and source_warehouse:
			# Intercompany store lanes cannot use the buyer-store warehouse in the
			# stock movement doc. Keep the real destination in contract metadata and
			# use a source-company-valid operational target so the MR remains valid.
			operational_target_warehouse = source_warehouse

		mr.set_warehouse = operational_target_warehouse
		mr.company = source_company
		stamp_material_request_contract(
			mr,
			request_source=REQUEST_SOURCE_STORE_ORDER,
			cargo_lane=cargo_category,
			source_warehouse=source_warehouse,
			destination_warehouse=store_warehouse,
			source_company=source_company,
			target_company=target_company,
			finance_treatment=finance_treatment,
		)
		mr.remarks = f"Warehouse dispatch request for store order {order.name} " f"({cargo_category})"

		for item in order.items:
			qty = flt(getattr(item, "qty_approved", None) or getattr(item, "qty_requested", 0))
			if qty <= 0:
				continue
			row = {
				"item_code": item.item_code,
				"item_name": item.item_name,
				"qty": qty,
				"uom": getattr(item, "uom", None) or "Nos",
				"stock_uom": getattr(item, "uom", None) or "Nos",
				"conversion_factor": 1,
				"warehouse": operational_target_warehouse,
				"schedule_date": required_by,
			}
			if source_warehouse:
				row["from_warehouse"] = source_warehouse
			mr.append("items", row)

		if not mr.items:
			return None

		mr.insert(ignore_permissions=True)
		mr.submit()
		return mr.name

	except Exception as e:
		frappe.log_error(
			title=f"MR Creation Error for Store Order {order.name}",
			message=str(e),
		)
		return None


@frappe.whitelist()
def get_expected_deliveries(store: str | None = None) -> dict:
	"""
	Get trips expected to deliver to this store today.
	Returns distribution trips with this store as a stop.
	"""
	if not store:
		return {"deliveries": []}

	today = nowdate()

	# Find trips with this store as a stop
	trips = frappe.db.sql(
		"""
        SELECT DISTINCT
            t.name, t.trip_date, t.route_name, t.driver, t.vehicle,
            t.status, t.departure_time,
            s.stop_order, s.items_count, s.status as stop_status
        FROM `tabBEI Distribution Trip` t
        JOIN `tabBEI Trip Stop` s ON s.parent = t.name
        WHERE s.store = %s
        AND t.trip_date = %s
        AND t.status IN ('Preparing', 'In Transit')
        ORDER BY t.trip_date, s.stop_order
    """,
		(store, today),
		as_dict=True,
	)

	return {"deliveries": trips}


@frappe.whitelist()
def complete_receiving(
	store: str,
	trip: str,
	items: list | str,
	receiver_1_signature: str | None = None,
	receiver_2_signature: str | None = None,
	driver_signature: str | None = None,
) -> dict:
	"""
	Complete receiving for a delivery.
	Items: list of {item_code, expected_qty, received_qty, checks, has_issue}
	"""
	if not store:
		frappe.throw(_("Store is required"))

	if isinstance(items, str):
		items = json.loads(items)

	warehouse = resolve_warehouse(store)

	receiving = frappe.new_doc("BEI Store Receiving")
	receiving.store = warehouse
	receiving.trip = trip
	receiving.receiving_date = now_datetime()
	receiving.receiver_1 = frappe.session.user
	receiving.receiver_1_signature = receiver_1_signature
	receiving.receiver_2_signature = receiver_2_signature
	receiving.driver_signature = driver_signature

	has_issues = False
	for item_data in items:
		row = receiving.append(
			"items",
			{
				"item_code": item_data.get("item_code"),
				"expected_qty": item_data.get("expected_qty"),
				"received_qty": item_data.get("received_qty"),
				"check_condition": item_data.get("check_condition", 0),
				"check_packaging": item_data.get("check_packaging", 0),
				"check_expiry": item_data.get("check_expiry", 0),
				"check_temperature": item_data.get("check_temperature", 0),
				"check_food_quality": item_data.get("check_food_quality", 0),
				"expiry_date": item_data.get("expiry_date"),
				"temperature_reading": item_data.get("temperature_reading"),
				"has_issue": item_data.get("has_issue", 0),
			},
		)
		if row.has_issue:
			has_issues = True

	receiving.status = "With Issues" if has_issues else "Completed"
	receiving.insert(ignore_permissions=True)

	contract = _resolve_store_receiving_contract(warehouse, trip)
	stock_entry_name = _create_store_receiving_stock_entry(receiving, contract)
	if stock_entry_name and _has_column("BEI Store Receiving", "stock_entry"):
		receiving.stock_entry = stock_entry_name
		receiving.save(ignore_permissions=True)

	result = {
		"success": True,
		"receiving": receiving.name,
		"message": f"Receiving {receiving.name} completed",
	}
	if stock_entry_name:
		result["stock_entry"] = stock_entry_name
	return result


def _resolve_store_receiving_contract(store_warehouse: str, trip_name: str | None) -> dict:
	"""Resolve the original delivery contract so receiving can post stock correctly."""
	source_warehouse = None
	store_order_name = None
	cargo_lane = None

	if trip_name and frappe.db.exists("BEI Distribution Trip", trip_name):
		source_warehouse = _resolve_store_return_destination_warehouse(
			type("_TripRef", (), {"trip": trip_name})()
		)
		if frappe.db.exists("DocType", "BEI Trip Stop"):
			store_order_name = frappe.db.get_value(
				"BEI Trip Stop",
				{"parent": trip_name, "store": store_warehouse},
				"store_order",
				order_by="idx asc",
			)

	if store_order_name:
		cargo_lane = frappe.db.get_value("BEI Store Order", store_order_name, "cargo_category")
		if _has_column("Material Request", "custom_store_order"):
			mr_name = frappe.db.get_value(
				"Material Request",
				{"custom_store_order": store_order_name, "docstatus": 1},
				"name",
				order_by="creation desc",
			)
			if mr_name:
				contract = resolve_material_request_contract(frappe.get_doc("Material Request", mr_name))
				contract["source_warehouse"] = contract.get("source_warehouse") or source_warehouse
				contract["destination_warehouse"] = contract.get("destination_warehouse") or store_warehouse
				contract["cargo_lane"] = contract.get("cargo_lane") or cargo_lane
				contract["source_company"] = contract.get("source_company") or resolve_warehouse_company(
					contract["source_warehouse"]
				)
				contract["target_company"] = contract.get("target_company") or resolve_warehouse_company(
					store_warehouse
				)
				contract["finance_treatment"] = contract.get("finance_treatment") or infer_finance_treatment(
					contract["source_company"], contract["target_company"]
				)
				return contract

	source_company = resolve_warehouse_company(source_warehouse)
	target_company = resolve_warehouse_company(store_warehouse)
	return {
		"request_source": REQUEST_SOURCE_STORE_ORDER,
		"cargo_lane": cargo_lane,
		"source_warehouse": source_warehouse,
		"destination_warehouse": store_warehouse,
		"source_company": source_company,
		"target_company": target_company,
		"finance_treatment": infer_finance_treatment(source_company, target_company),
	}


def _create_store_receiving_stock_entry(receiving, contract: dict) -> str | None:
	"""Post intercompany store receipts into store inventory after delivery confirmation."""
	finance_treatment = contract.get("finance_treatment") or FINANCE_TREATMENT_SAME_COMPANY
	if finance_treatment == FINANCE_TREATMENT_SAME_COMPANY:
		return None

	receipt_rows = []
	for item in receiving.items:
		received_qty = flt(getattr(item, "received_qty", 0))
		if received_qty <= 0:
			continue
		receipt_rows.append((item, received_qty))

	if not receipt_rows:
		return None

	stock_entry = frappe.new_doc("Stock Entry")
	stock_entry.stock_entry_type = "Material Receipt"
	stock_entry.company = (
		contract.get("target_company") or resolve_warehouse_company(receiving.store) or get_company()
	)
	stock_entry.posting_date = frappe.utils.today()
	stock_entry.posting_time = _current_time_string()
	stock_entry.to_warehouse = receiving.store
	stock_entry.remarks = (
		f"Store receiving {receiving.name}"
		f" | Trip: {receiving.trip or ''}"
		f" | Source: {contract.get('source_warehouse') or 'Unclassified'}"
	)
	stamp_stock_entry_contract(
		stock_entry,
		request_source=contract.get("request_source") or REQUEST_SOURCE_STORE_ORDER,
		cargo_lane=contract.get("cargo_lane"),
		destination_warehouse=receiving.store,
		source_company=contract.get("source_company"),
		target_company=stock_entry.company,
		finance_treatment=finance_treatment,
	)

	for item, received_qty in receipt_rows:
		item_doc = frappe.get_doc("Item", item.item_code)
		row = {
			"item_code": item.item_code,
			"item_name": item_doc.item_name,
			"description": item_doc.description,
			"qty": received_qty,
			"uom": getattr(item, "uom", None) or item_doc.stock_uom,
			"stock_uom": item_doc.stock_uom,
			"conversion_factor": 1,
			"t_warehouse": receiving.store,
		}
		if getattr(item, "batch_no", None):
			row["batch_no"] = item.batch_no
		stock_entry.append("items", row)

	stock_entry.insert(ignore_permissions=True)
	stock_entry.submit()
	return stock_entry.name


@frappe.whitelist()
def create_fqi_report(
	store: str,
	receiving: str | None = None,
	item_code: str | None = None,
	issue_type: str | None = None,
	description: str | None = None,
	photo: str | None = None,
	expected_qty: int | float | str | None = None,
	actual_qty: int | float | str | None = None,
) -> dict:
	"""
	Create a Food Quality Incident report.
	"""
	if not store:
		frappe.throw(_("Store is required"))

	if not issue_type:
		frappe.throw(_("Issue type is required"))

	# Resolve store name to valid warehouse (handles branch codes like TEST-STORE-BGC)
	try:
		warehouse = resolve_warehouse(store)
	except Exception:
		# Provide helpful suggestions for common typos
		similar_stores = frappe.db.sql(
			"""
            SELECT name FROM tabWarehouse
            WHERE name LIKE %s OR warehouse_name LIKE %s
            LIMIT 5
        """,
			(f"%{store[:10]}%", f"%{store[:10]}%"),
			as_dict=True,
		)

		suggestions = [s.name for s in similar_stores] if similar_stores else []
		msg = _("Store '{0}' not found.").format(store)
		if suggestions:
			msg += " " + _("Did you mean: {0}?").format(", ".join(suggestions))
		frappe.throw(msg)

	# Convert base64 photo to file URL to avoid DataError (1406) on Attach Image column (C10 fix)
	photo_url = save_base64_image(photo, "BEI FQI Report", fieldname="photo") if photo else None

	fqi = frappe.new_doc("BEI FQI Report")
	fqi.store = warehouse
	fqi.receiving = receiving
	fqi.item_code = item_code
	fqi.issue_type = issue_type
	fqi.description = description
	fqi.photo = photo_url
	fqi.expected_qty = expected_qty
	fqi.actual_qty = actual_qty
	fqi.reported_by = frappe.session.user
	fqi.reported_at = now_datetime()
	fqi.status = "Open"
	fqi.insert(ignore_permissions=True)

	return {"success": True, "fqi": fqi.name, "message": f"FQI Report {fqi.name} created"}


@frappe.whitelist()
def get_fqi_reports(
	store: str | None = None,
	status: str | None = None,
	limit: int | str = 20,
) -> dict:
	"""Get FQI reports optionally filtered by store and status."""
	filters = {}
	if store:
		filters["store"] = store
	if status:
		filters["status"] = status

	reports = frappe.get_all(
		"BEI FQI Report",
		filters=filters,
		fields=[
			"name",
			"store",
			"item_code",
			"issue_type",
			"status",
			"reported_by",
			"reported_at",
			"resolved_at",
		],
		order_by="creation desc",
		limit=int(limit),
		ignore_permissions=True,
	)

	return {"reports": reports}


# ==============================================================================
# STORE RETURNS
# ==============================================================================


@frappe.whitelist()
def get_returns_pending(store: str | None = None) -> dict:
	"""
	Get store receiving items where has_issue=1 and no linked return Stock Entry.
	Returns items that need operator resolution back to warehouse or disposal.
	"""
	filters = {"has_issue": 1}

	if store:
		# Get all receivings for this store
		receiving_names = frappe.get_all("BEI Store Receiving", filters={"store": store}, pluck="name")
		if not receiving_names:
			return {"items": []}
		filters["parent"] = ["in", receiving_names]

	query = """
        SELECT
            ri.name,
            ri.parent AS receiving,
            ri.item_code,
            ri.item_name,
            ri.received_qty,
            ri.has_issue,
            ri.fqi_reference,
            r.store,
            r.receiving_date,
            r.trip
        FROM `tabBEI Store Receiving Item` ri
        JOIN `tabBEI Store Receiving` r ON r.name = ri.parent
        WHERE ri.has_issue = 1
            AND NOT EXISTS (
                SELECT 1 FROM `tabStock Entry`
                WHERE stock_entry_type = 'Material Transfer'
                    AND purpose = 'Material Transfer'
                    AND remarks LIKE CONCAT('%%Store Return%%', ri.parent, '%%')
                    AND docstatus = 1
            )
    """
	params = {}
	if store:
		query += "\n        AND r.store = %(store)s"
		params["store"] = store
	query += "\n        ORDER BY r.receiving_date DESC\n        LIMIT 100"

	items = frappe.db.sql(query, params, as_dict=True)

	return {"items": items}


def _resolve_store_return_destination_warehouse(receiving_doc):
	"""Resolve the warehouse that originally dispatched the received trip."""
	trip_name = getattr(receiving_doc, "trip", None)
	if not trip_name or not frappe.db.exists("BEI Distribution Trip", trip_name):
		return None

	trip = frappe.get_doc("BEI Distribution Trip", trip_name)
	route_ref = getattr(trip, "route", None) or getattr(trip, "route_name", None)
	if not route_ref:
		return None

	if frappe.db.exists("BEI Route", route_ref):
		return frappe.db.get_value("BEI Route", route_ref, "source_warehouse")

	return frappe.db.get_value("BEI Route", {"route_name": route_ref}, "source_warehouse")


def _attach_store_issue_photo(stock_entry, photo: str | None):
	"""Persist optional proof photo on the Stock Entry when the custom field exists."""
	if not photo:
		return
	photo_url = save_base64_image(photo, "Stock Entry", fieldname="custom_return_photo")
	if photo_url and _has_column("Stock Entry", "custom_return_photo"):
		stock_entry.custom_return_photo = photo_url


def _current_time_string() -> str:
	"""Return HH:MM:SS even when now_datetime() is stubbed to a plain string in tests."""
	current = now_datetime()
	if hasattr(current, "strftime"):
		return current.strftime("%H:%M:%S")
	return str(current)


def _extract_store_issue_context(stock_entry):
	receiving_name = None
	store = stock_entry.from_warehouse
	reason = ""
	if stock_entry.remarks:
		for part in stock_entry.remarks.split("|"):
			part = part.strip()
			if part.startswith("Receiving:"):
				receiving_name = part.replace("Receiving:", "").strip()
			elif part.startswith("Reason:"):
				reason = part.replace("Reason:", "").strip()
	return receiving_name, store, reason


def _create_store_issue_credit_note(stock_entry, store, reason):
	"""Create the finance reversal record for a store issue movement when applicable."""
	credit_note_name = None
	journal_entry_name = None
	original_billing = _find_original_billing(store)
	if not original_billing:
		return credit_note_name, journal_entry_name

	frappe.db.savepoint("store_issue_credit")
	try:
		return_value = flt(stock_entry.total_outgoing_value or 0)
		billed_value = flt(original_billing.get("total_billed_value")) or 1
		ratio = min(return_value / billed_value, 1.0) if billed_value > 0 else 0

		royalty_rev = round(flt(original_billing.get("royalty_fee", 0)) * ratio, 2)
		mgmt_rev = round(flt(original_billing.get("management_fee", 0)) * ratio, 2)
		marketing_rev = round(flt(original_billing.get("marketing_fee", 0)) * ratio, 2)
		ecomm_rev = round(flt(original_billing.get("ecommerce_fee", 0)) * ratio, 2)
		total_credit = royalty_rev + mgmt_rev + marketing_rev + ecomm_rev

		if total_credit > 0:
			cn = frappe.new_doc("BEI Billing Schedule")
			cn.billing_type = "Credit Note"
			cn.naming_series = "BILL-CN-.YYYY.-.#####"
			cn.store = original_billing.get("store")
			cn.billing_period_start = nowdate()
			cn.billing_period_end = nowdate()
			cn.status = "Unpaid"
			cn.royalty_fee = -royalty_rev
			cn.management_fee = -mgmt_rev
			cn.marketing_fee = -marketing_rev
			cn.ecommerce_fee = -ecomm_rev
			cn.subtotal = -total_credit
			cn.vat_amount = 0
			cn.total_amount = -total_credit
			cn.remarks = f"Credit Note for Store Issue {stock_entry.name} | {store} | {reason}"
			cn.flags.ignore_mandatory = True
			cn.insert(ignore_permissions=True)
			credit_note_name = cn.name

			store_cost_center = _get_store_cost_center(store)
			store_customer = _get_store_customer(store)

			jv_accounts = []
			if royalty_rev > 0:
				jv_accounts.append(
					{
						"account": "4000301 - ROYALTY FEE INCOME - BEI",
						"debit_in_account_currency": royalty_rev,
						"cost_center": store_cost_center,
					}
				)
			if mgmt_rev > 0:
				jv_accounts.append(
					{
						"account": "4000302 - MANAGEMENT FEE INCOME - BEI",
						"debit_in_account_currency": mgmt_rev,
						"cost_center": store_cost_center,
					}
				)
			if marketing_rev > 0:
				jv_accounts.append(
					{
						"account": "4000303 - MARKETING FEE INCOME - BEI",
						"debit_in_account_currency": marketing_rev,
						"cost_center": store_cost_center,
					}
				)
			if ecomm_rev > 0:
				jv_accounts.append(
					{
						"account": "4000304 - ECOMMERCE FEE INCOME - BEI",
						"debit_in_account_currency": ecomm_rev,
						"cost_center": store_cost_center,
					}
				)

			jv_accounts.append(
				{
					"account": "1103101 - ACCOUNTS RECEIVABLE - TRADE - BEI",
					"credit_in_account_currency": total_credit,
					"party_type": "Customer",
					"party": store_customer,
					"cost_center": store_cost_center,
				}
			)

			journal_entry = frappe.get_doc(
				{
					"doctype": "Journal Entry",
					"voucher_type": "Credit Note",
					"posting_date": nowdate(),
					"company": get_company(),
					"user_remark": f"Credit Note for Store Issue {stock_entry.name} | {store} | {reason}",
					"cheque_no": stock_entry.name,
					"cheque_date": frappe.utils.today(),
					"accounts": jv_accounts,
				}
			)
			journal_entry.insert(ignore_permissions=True)
			journal_entry.submit()
			journal_entry_name = journal_entry.name

		frappe.db.release_savepoint("store_issue_credit")
	except Exception:
		frappe.db.rollback(save_point="store_issue_credit")
		frappe.log_error(
			f"Credit note creation failed for store issue {stock_entry.name}",
			"Store Issue Credit Note Error",
		)
		frappe.throw(_("Failed to create credit note for the store issue. Please try again."))

	return credit_note_name, journal_entry_name


@frappe.whitelist()
def create_store_return(
	receiving: str,
	items: list | str,
	reason: str,
	photo: str | None = None,
) -> dict:
	"""
	Create a store return for items with issues from a receiving doc.
	Tracks the return intent and creates a Stock Entry to transfer items back to warehouse.

	Args:
	    receiving: BEI Store Receiving document name
	    items: JSON list of {item_code, qty, reason}
	    reason: Overall reason for return
	    photo: Optional base64 photo of returned items
	"""
	if isinstance(items, str):
		items = json.loads(items)

	if not items:
		frappe.throw(_("No items to return"))

	receiving_doc = frappe.get_doc("BEI Store Receiving", receiving)
	store = receiving_doc.store

	# G-100: Idempotency — check if a return Stock Entry already exists for this receiving
	existing_return = frappe.db.exists(
		"Stock Entry",
		{
			"stock_entry_type": "Material Transfer",
			"remarks": ["like", f"%Receiving: {receiving}%"],
			"docstatus": ["<", 2],
		},
	)
	if existing_return:
		frappe.throw(_("A return already exists for receiving {0}: {1}").format(receiving, existing_return))

	return_warehouse = _resolve_store_return_destination_warehouse(receiving_doc)
	if not return_warehouse:
		frappe.throw(_("Unable to resolve the originating warehouse for this return"))

	# Create Stock Entry (Material Transfer back to warehouse)
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Transfer"
	se.posting_date = nowdate()
	se.posting_time = _current_time_string()
	se.from_warehouse = store
	se.to_warehouse = return_warehouse
	se.remarks = f"Store Return from {store} | Receiving: {receiving} | Reason: {reason}"
	source_company = resolve_warehouse_company(store) or get_company()
	target_company = resolve_warehouse_company(return_warehouse) or source_company
	se.company = source_company
	stamp_stock_entry_contract(
		se,
		request_source=REQUEST_SOURCE_STORE_RETURN,
		source_company=source_company,
		target_company=target_company,
	)

	for item_data in items:
		qty = flt(item_data.get("qty") or item_data.get("return_qty"))
		if qty <= 0:
			continue

		item_code = item_data.get("item_code")
		item = frappe.get_doc("Item", item_code)

		se.append(
			"items",
			{
				"item_code": item_code,
				"item_name": item.item_name,
				"description": item.description or item.item_name,
				"qty": qty,
				"uom": item_data.get("uom") or item.stock_uom,
				"stock_uom": item.stock_uom,
				"conversion_factor": 1,
				"s_warehouse": store,
				"t_warehouse": return_warehouse,
			},
		)

	if not se.items:
		frappe.throw(_("No valid items with quantity to return"))

	_attach_store_issue_photo(se, photo)

	frappe.db.savepoint("create_store_return")
	try:
		se.insert(ignore_permissions=True)
		se.submit()
		frappe.db.release_savepoint("create_store_return")
	except Exception:
		frappe.db.rollback(save_point="create_store_return")
		frappe.log_error(f"Store return Stock Entry failed for {receiving}", "Store Return Error")
		frappe.throw(_("Failed to create store return. Please try again."))

	# G-002 Task 2D: Notify warehouse-facing operations of the return request
	try:
		from hrms.api.google_chat import SPACE_NOTIFICATIONS, get_chat_space, send_message_to_space

		store_name = store.replace(" - BEI", "") if store else "Unknown"
		msg = f"New Store Return Request: {se.name}\n"
		msg += f"Store: {store_name} | Items: {len(se.items)}\n"
		msg += f"Return To: {return_warehouse}\n"
		msg += f"Reason: {reason}"
		space = get_chat_space(SPACE_NOTIFICATIONS)
		send_message_to_space(space, msg)
	except Exception:
		frappe.log_error(f"Return notification failed for {se.name}", "Store Return Notification Error")

	return {
		"success": True,
		"stock_entry": se.name,
		"message": f"Store return {se.name} created — {len(se.items)} item(s) returned to warehouse",
	}


@frappe.whitelist()
def create_store_disposal(
	receiving: str,
	items: list | str,
	reason: str,
	photo: str | None = None,
) -> dict:
	"""
	Create a store disposal/write-off entry for receiving issues that cannot be returned.
	Requires supervisor-level authority and proof photo when available.
	"""
	allowed_roles = {"Store Supervisor", "Area Supervisor", "Warehouse User", "System Manager"}
	if not set(frappe.get_roles(frappe.session.user)).intersection(allowed_roles):
		frappe.throw(_("You do not have permission to dispose store receiving items"), frappe.PermissionError)

	if isinstance(items, str):
		items = json.loads(items)

	if not items:
		frappe.throw(_("No items to dispose"))

	receiving_doc = frappe.get_doc("BEI Store Receiving", receiving)
	store = receiving_doc.store

	existing_disposal = frappe.db.exists(
		"Stock Entry",
		{
			"stock_entry_type": "Material Issue",
			"remarks": ["like", f"%Store Disposal%Receiving: {receiving}%"],
			"docstatus": ["<", 2],
		},
	)
	if existing_disposal:
		frappe.throw(
			_("A disposal already exists for receiving {0}: {1}").format(receiving, existing_disposal)
		)

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Issue"
	se.company = resolve_warehouse_company(store) or get_company()
	se.posting_date = nowdate()
	se.posting_time = _current_time_string()
	se.from_warehouse = store
	se.remarks = f"Store Disposal from {store} | Receiving: {receiving} | Reason: {reason}"
	stamp_stock_entry_contract(
		se,
		request_source=REQUEST_SOURCE_STORE_DISPOSAL,
		source_company=se.company,
		target_company=se.company,
		finance_treatment=FINANCE_TREATMENT_SAME_COMPANY,
	)

	for item_data in items:
		qty = flt(item_data.get("qty") or item_data.get("disposal_qty") or item_data.get("return_qty"))
		if qty <= 0:
			continue

		item_code = item_data.get("item_code")
		item = frappe.get_doc("Item", item_code)

		se.append(
			"items",
			{
				"item_code": item_code,
				"item_name": item.item_name,
				"description": item.description or item.item_name,
				"qty": qty,
				"uom": item_data.get("uom") or item.stock_uom,
				"stock_uom": item.stock_uom,
				"conversion_factor": 1,
				"s_warehouse": store,
			},
		)

	if not se.items:
		frappe.throw(_("No valid items with quantity to dispose"))

	_attach_store_issue_photo(se, photo)

	frappe.db.savepoint("create_store_disposal")
	try:
		se.insert(ignore_permissions=True)
		se.submit()
		frappe.db.release_savepoint("create_store_disposal")
	except Exception:
		frappe.db.rollback(save_point="create_store_disposal")
		frappe.log_error(f"Store disposal Stock Entry failed for {receiving}", "Store Disposal Error")
		frappe.throw(_("Failed to create store disposal. Please try again."))

	return {
		"success": True,
		"stock_entry": se.name,
		"receiving": receiving,
		"message": f"Store disposal {se.name} created — {len(se.items)} item(s) written off",
	}


@frappe.whitelist()
def process_store_return(stock_entry_name: str) -> dict:
	"""
	Process a submitted store return Stock Entry.
	G-002: Creates credit note (BEI Billing Schedule) + GL Journal Entry
	to reverse pro-rata franchise fees on returned items.

	Args:
	    stock_entry_name: Submitted Stock Entry for the return
	"""
	check_scm_permission(SCM_APPROVAL_ROLES, "process store returns")

	se = frappe.get_doc("Stock Entry", stock_entry_name)

	if se.docstatus != 1:
		frappe.throw(_("Stock Entry must be submitted before processing"))

	if se.stock_entry_type != "Material Transfer":
		frappe.throw(_("Not a valid store return entry"))

	receiving_name, store, reason = _extract_store_issue_context(se)
	credit_note_name, jv_name = _create_store_issue_credit_note(se, store, reason)

	# G-002 Task 2D: Notification OUTSIDE savepoint — failure must NOT roll back
	try:
		_notify_store_issue_processed(se, store, reason, credit_note_name, issue_label="Store Return")
	except Exception:
		frappe.log_error(f"Return notification failed for {se.name}", "Store Return Notification Error")

	result = {
		"success": True,
		"stock_entry": se.name,
		"receiving": receiving_name,
		"items_returned": len(se.items),
		"credit_note": credit_note_name,
		"journal_entry": jv_name,
		"message": f"Return {se.name} processed — {len(se.items)} item(s) returned, credit note: {credit_note_name or 'N/A'}",
	}

	return result


@frappe.whitelist()
def process_store_disposal(stock_entry_name: str) -> dict:
	"""Process a submitted store disposal entry and create the related billing reversal."""
	check_scm_permission(SCM_APPROVAL_ROLES, "process store disposals")

	se = frappe.get_doc("Stock Entry", stock_entry_name)

	if se.docstatus != 1:
		frappe.throw(_("Stock Entry must be submitted before processing"))

	if se.stock_entry_type != "Material Issue":
		frappe.throw(_("Not a valid store disposal entry"))

	if REQUEST_SOURCE_STORE_DISPOSAL != getattr(se, "custom_request_source", REQUEST_SOURCE_STORE_DISPOSAL):
		if "Store Disposal" not in str(se.remarks or ""):
			frappe.throw(_("Not a valid store disposal entry"))

	receiving_name, store, reason = _extract_store_issue_context(se)
	credit_note_name, journal_entry_name = _create_store_issue_credit_note(se, store, reason)

	try:
		_notify_store_issue_processed(se, store, reason, credit_note_name, issue_label="Store Disposal")
	except Exception:
		frappe.log_error(f"Disposal notification failed for {se.name}", "Store Disposal Notification Error")

	return {
		"success": True,
		"stock_entry": se.name,
		"receiving": receiving_name,
		"items_disposed": len(se.items),
		"credit_note": credit_note_name,
		"journal_entry": journal_entry_name,
		"message": (
			f"Disposal {se.name} processed — {len(se.items)} item(s) written off, "
			f"credit note: {credit_note_name or 'N/A'}"
		),
	}


def _find_original_billing(store):
	"""Find the most recent billing for a store to calculate pro-rata fee reversal."""
	billing = frappe.db.sql(
		"""
        SELECT name, store, royalty_fee, management_fee, marketing_fee,
               ecommerce_fee, subtotal, total_amount
        FROM `tabBEI Billing Schedule`
        WHERE store = %s
        AND billing_type IN ('Monthly Fees', 'Delivery')
        AND docstatus < 2
        ORDER BY billing_period_end DESC
        LIMIT 1
    """,
		store,
		as_dict=True,
	)

	if not billing:
		return None

	result = billing[0]
	# total_billed_value is the PHP value used for pro-rata ratio (value / value = dimensionless)
	result["total_billed_value"] = flt(result.get("total_amount", 0)) or 1
	return result


def _get_store_cost_center(store):
	"""Get cost center for a store warehouse."""
	cost_center = frappe.db.get_value("Warehouse", store, "custom_cost_center")
	if not cost_center:
		cost_center = frappe.db.get_value("Company", get_company(), "cost_center")
	return cost_center


def _get_store_customer(store):
	"""Get the Customer linked to a store for AR party field (DM-1)."""
	# Try to find a Customer with the same name as the warehouse
	store_name = store.replace(" - BEI", "") if store else ""
	customer = frappe.db.get_value("Customer", {"customer_name": ["like", f"%{store_name}%"]}, "name")
	if not customer:
		frappe.throw(_(f"No Customer record found for store '{store_name}'. Create a Customer first."))
	return customer


def _notify_store_issue_processed(se, store, reason, credit_note_name, issue_label="Store Return"):
	"""Send a non-blocking Google Chat notification for a processed store issue."""
	try:
		from hrms.api.google_chat import SPACE_NOTIFICATIONS, get_chat_space, send_message_to_space

		store_name = store.replace(" - BEI", "") if store else "Unknown"
		items_count = len(se.items)
		msg = f"{issue_label} Processed: {se.name}\n"
		msg += f"Store: {store_name} | Items: {items_count}\n"
		if reason:
			msg += f"Reason: {reason}\n"
		if credit_note_name:
			msg += f"Credit Note: {credit_note_name}"

		# Notify commissary space
		space = get_chat_space(SPACE_NOTIFICATIONS)
		send_message_to_space(space, msg)
	except ImportError:
		pass


# ==============================================================================
# STORE OPENING/CLOSING REPORTS
# ==============================================================================


@frappe.whitelist()
def submit_opening_report(
	store: str,
	checklist_items: list | str | None = None,
	report_time: str | None = None,
	notes: str | None = None,
	photo_backup_area: str | None = None,
	photo_frozen_milk: str | None = None,
	photo_toppings_area: str | None = None,
	photo_dispatch_area: str | None = None,
	photo_cold_storage_temp: str | None = None,
) -> dict:
	"""Submit daily opening report with 5 required photos.

	Bug fixes (C1):
	- report_time made optional (defaults to current time) since frontend may not send it
	- Photos saved via save_base64_image to avoid DataError on Attach Image fields
	- checklist_items can be empty list (allows incomplete submission per REQ-007)
	- Wrapped in try/except returning user-friendly error instead of raw traceback
	"""
	try:
		validate_store_ops_role()
		if not store:
			frappe.throw(_("Store is required"))

		# Resolve store name to valid warehouse
		warehouse = resolve_warehouse(store)

		if isinstance(checklist_items, str):
			checklist_items = json.loads(checklist_items)

		doc = frappe.new_doc("BEI Store Opening Report")
		doc.store = warehouse
		doc.report_date = nowdate()
		doc.report_time = report_time or now_datetime().strftime("%H:%M:%S")
		doc.submitted_by = frappe.session.user
		doc.notes = notes

		# Handle photos - convert base64 to file URLs if needed
		# This MUST happen before insert to avoid DataError (1406) on Attach Image columns
		doc.photo_backup_area = save_base64_image(
			photo_backup_area, "BEI Store Opening Report", fieldname="photo_backup_area"
		)
		doc.photo_frozen_milk = save_base64_image(
			photo_frozen_milk, "BEI Store Opening Report", fieldname="photo_frozen_milk"
		)
		doc.photo_toppings_area = save_base64_image(
			photo_toppings_area, "BEI Store Opening Report", fieldname="photo_toppings_area"
		)
		doc.photo_dispatch_area = save_base64_image(
			photo_dispatch_area, "BEI Store Opening Report", fieldname="photo_dispatch_area"
		)
		doc.photo_cold_storage_temp = save_base64_image(
			photo_cold_storage_temp, "BEI Store Opening Report", fieldname="photo_cold_storage_temp"
		)

		# Allow empty checklist (incomplete submission per REQ-007)
		if checklist_items:
			for item in checklist_items:
				doc.append("checklist_items", item)

		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		return {"success": True, "name": doc.name}

	except frappe.exceptions.LinkValidationError as e:
		frappe.log_error(f"Opening Report LinkValidation: {e!s}", "Opening Report Submission Error")
		return {"success": False, "error": str(e)}
	except Exception as e:
		frappe.log_error(
			f"Opening Report Error for store {store}: {e!s}\n\n{frappe.get_traceback()}",
			"Opening Report Submission Error",
		)
		return {
			"success": False,
			"error": _("Failed to submit opening report. Please try again or contact support."),
		}


@frappe.whitelist()
def get_opening_reports(
	store: str | None = None,
	date_from: str | None = None,
	date_to: str | None = None,
	limit: int | str = 20,
) -> dict:
	"""Get opening report history."""
	filters = {}
	if store:
		filters["store"] = store
	if date_from:
		filters["report_date"] = [">=", date_from]
	if date_to:
		if "report_date" in filters:
			filters["report_date"] = ["between", [date_from, date_to]]
		else:
			filters["report_date"] = ["<=", date_to]

	reports = frappe.get_all(
		"BEI Store Opening Report",
		filters=filters,
		fields=["name", "store", "report_date", "report_time", "status", "submitted_by"],
		order_by="report_date desc",
		limit=int(limit),
	)
	return {"reports": reports}


@frappe.whitelist()
def get_closing_reports(
	store: str | None = None,
	date_from: str | None = None,
	date_to: str | None = None,
	limit: int | str = 20,
) -> dict:
	"""Get closing report history."""
	filters = {}
	if store:
		filters["store"] = store
	if date_from:
		filters["report_date"] = [">=", date_from]
	if date_to:
		if "report_date" in filters:
			filters["report_date"] = ["between", [date_from, date_to]]
		else:
			filters["report_date"] = ["<=", date_to]

	reports = frappe.get_all(
		"BEI Store Closing Report",
		filters=filters,
		fields=["name", "store", "report_date", "status", "cash_variance"],
		order_by="report_date desc",
		limit=int(limit),
	)
	return {"reports": reports}


@frappe.whitelist()
def submit_midshift_check(
	store: str,
	shift: str | None = None,
	temperature_readings: list | str | None = None,
	cleanliness_status: str | None = None,
	checklist_items: list | str | None = None,
	issues_found: str | None = None,
	corrective_action: str | None = None,
	photo_evidence: str | list | None = None,
	late_reason: str | None = None,
	equipment: str | list | None = None,
	notes: str | None = None,
) -> dict:
	"""Submit mid-shift temperature and cleanliness check with time window validation.

	Bug fixes (C3):
	- shift defaults to auto-detected based on current time
	- temperature_readings and checklist_items both accepted (frontend may send either)
	- cleanliness_status made optional (defaults to 'Good')
	- photo_evidence saved via save_base64_image to avoid DataError
	- Time window validation relaxed: logs warning but allows submission with auto-populated late_reason
	- insert with ignore_permissions=True for Employee Self Service role
	"""
	try:
		validate_store_ops_role()
		if not store:
			frappe.throw(_("Store is required"))

		# Resolve branch name to warehouse name
		warehouse = resolve_warehouse(store)

		if isinstance(temperature_readings, str):
			temperature_readings = json.loads(temperature_readings)
		if isinstance(checklist_items, str):
			checklist_items = json.loads(checklist_items)

		# Auto-detect shift based on current time if not provided
		current_time = now_datetime()
		current_time_str = current_time.strftime("%H:%M:%S")
		if not shift:
			hour = current_time.hour
			if hour < 12:
				shift = "Morning"
			elif hour < 17:
				shift = "Afternoon"
			else:
				shift = "Evening"

		# Normalize shift and cleanliness values to title case (Frappe Select field expects exact match)
		shift_map = {"morning": "Morning", "afternoon": "Afternoon", "evening": "Evening"}
		normalized_shift = shift_map.get(shift.lower(), shift.title()) if shift else "Afternoon"

		cleanliness_map = {
			"excellent": "Excellent",
			"good": "Good",
			"needs attention": "Needs Attention",
			"critical": "Critical",
		}
		normalized_cleanliness = (
			cleanliness_map.get(
				(cleanliness_status or "good").lower(), (cleanliness_status or "Good").title()
			)
			if cleanliness_status
			else "Good"
		)

		# Define time windows per shift (can be moved to BEI Shift Template later)
		shift_windows = {
			"Morning": ("10:00:00", "11:00:00"),
			"Afternoon": ("14:00:00", "15:00:00"),
			"Evening": ("18:00:00", "19:00:00"),
		}

		# Get time window for this shift
		window_start, window_end = shift_windows.get(normalized_shift, ("00:00:00", "23:59:59"))

		# Check if submission is on time
		is_on_time = window_start <= current_time_str <= window_end

		# Handle photo evidence - convert base64 to file URL
		photo_url = (
			save_base64_image(photo_evidence, "BEI Midshift Checklist", fieldname="photo_evidence")
			if photo_evidence
			else None
		)

		doc = frappe.new_doc("BEI Midshift Checklist")
		doc.store = warehouse
		doc.check_datetime = current_time
		doc.submitted_by = frappe.session.user
		doc.shift = normalized_shift
		doc.cleanliness_status = normalized_cleanliness
		doc.issues_found = issues_found
		doc.corrective_action = corrective_action
		doc.photo_evidence = photo_url
		doc.equipment = equipment or "General"

		# Time window fields
		doc.window_start = window_start
		doc.window_end = window_end
		doc.is_on_time = 1 if is_on_time else 0
		# Auto-populate late_reason instead of blocking submission
		if not is_on_time:
			doc.late_reason = (
				late_reason or f"Submitted at {current_time_str} (outside {window_start}-{window_end} window)"
			)

		if temperature_readings:
			for reading in temperature_readings:
				doc.append("temperature_readings", reading)

		# Also accept checklist_items (frontend may send this instead of temperature_readings)
		if checklist_items and hasattr(doc, "checklist_items"):
			for item in checklist_items:
				doc.append("checklist_items", item)

		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		return {
			"success": True,
			"name": doc.name,
			"is_on_time": is_on_time,
			"window_start": window_start,
			"window_end": window_end,
		}

	except Exception as e:
		frappe.log_error(
			f"Midshift Check Error for store {store}: {e!s}\n\n{frappe.get_traceback()}",
			"Midshift Check Submission Error",
		)
		return {
			"success": False,
			"error": _("Failed to submit midshift report. Please try again or contact support."),
		}


@frappe.whitelist()
def get_midshift_checks(
	store: str | None = None,
	date: str | None = None,
	limit: int | str = 20,
) -> dict:
	"""Get mid-shift check history."""
	filters = {}
	if store:
		filters["store"] = store
	if date:
		filters["check_datetime"] = ["like", f"{date}%"]

	checks = frappe.get_all(
		"BEI Midshift Checklist",
		filters=filters,
		fields=["name", "store", "check_datetime", "shift", "cleanliness_status"],
		order_by="check_datetime desc",
		limit=int(limit),
	)
	return {"checks": checks}


@frappe.whitelist()
def upload_pos_data(
	store: str | None = None,
	pos_date: str | None = None,
	pos_system: str | None = None,
	discount_report: str | None = None,
	transaction_report: str | None = None,
	product_mix: str | None = None,
	daily_sales_revenue: str | None = None,
	sales_summary: str | None = None,
	notes: str | None = None,
	skip_date_validation: bool | int | str = False,
) -> dict:
	"""
	Upload daily POS data with 5 required report files.

	Args:
	    store: Store/branch name
	    pos_date: Date of POS data
	    pos_system: POS system used (MOSAIC)
	    discount_report: Discount Report file (base64)
	    transaction_report: Transaction Report file (base64)
	    product_mix: Product Mix file (base64)
	    daily_sales_revenue: Daily Sales Revenue - Summary file (base64)
	    sales_summary: Sales Summary file (base64)
	    notes: Optional notes
	    skip_date_validation: Skip date validation (for back-dated uploads with supervisor approval)
	"""
	frappe.throw(_manual_pos_upload_disabled_message())
	validate_store_ops_role()

	if not store:
		frappe.throw(_("Store is required"))

	if not all([discount_report, transaction_report, product_mix, daily_sales_revenue, sales_summary]):
		frappe.throw(_("All 5 POS report files are required"))

	# Date validation: Extract date from sales_summary and validate it matches pos_date
	date_mismatch_warning = None
	if not skip_date_validation:
		try:
			from hrms.utils.pos_parser import parse_sales_summary

			# Decode sales_summary if it's base64/data-url
			if isinstance(sales_summary, str) and not sales_summary.startswith("/files/"):
				try:
					content, _decoded_ext = _decode_base64_attachment(sales_summary, default_ext="xlsx")
				except Exception:
					content = sales_summary.encode() if isinstance(sales_summary, str) else sales_summary
			else:
				content = None

			if content:
				summary_data = parse_sales_summary(content)
				file_date = summary_data.get("metadata", {}).get("from_date")

				if file_date and str(file_date) != str(pos_date):
					date_mismatch_warning = _(
						"Warning: POS file date ({0}) does not match claimed date ({1}). "
						"Please verify the correct date before submitting."
					).format(file_date, pos_date)
					# Log the mismatch but allow upload (with warning returned)
					frappe.log_error(
						f"POS date mismatch - Store: {store}, File date: {file_date}, Claimed date: {pos_date}",
						"POS Upload Date Mismatch",
					)
		except Exception as e:
			# Don't block upload if date validation fails, just log it
			frappe.log_error(f"POS date validation error: {e!s}", "POS Upload Date Validation Error")

	# Resolve branch name to warehouse name (C6 fix)
	warehouse = resolve_warehouse(store)

	# Case-insensitive POS system matching (e.g., "Mosaic" -> "MOSAIC")
	if pos_system:
		pos_system = pos_system.strip().upper()

	# Save report files as Frappe File records BEFORE insert (fields are mandatory)
	doctype_name = "BEI POS Upload"
	doc = frappe.new_doc("BEI POS Upload")
	doc.store = warehouse
	doc.pos_date = pos_date
	doc.uploaded_by = frappe.session.user
	doc.pos_system = pos_system
	doc.notes = notes
	doc.discount_report = save_base64_file(
		discount_report, doctype_name, fieldname="discount_report", default_ext="xlsx"
	)
	doc.transaction_report = save_base64_file(
		transaction_report, doctype_name, fieldname="transaction_report", default_ext="xlsx"
	)
	doc.product_mix = save_base64_file(product_mix, doctype_name, fieldname="product_mix", default_ext="xlsx")
	doc.daily_sales_revenue = save_base64_file(
		daily_sales_revenue, doctype_name, fieldname="daily_sales_revenue", default_ext="xlsx"
	)
	doc.sales_summary = save_base64_file(
		sales_summary, doctype_name, fieldname="sales_summary", default_ext="xlsx"
	)
	doc.insert()

	result = {"success": True, "name": doc.name}
	if date_mismatch_warning:
		result["warning"] = date_mismatch_warning
		result["date_mismatch"] = True
		# Tag the document so Finance can filter mismatched uploads in reconciliation view
		frappe.db.set_value("BEI POS Upload", doc.name, "has_date_mismatch", 1)
	return result


@frappe.whitelist()
def get_pos_uploads(
	store: str | None = None,
	date_from: str | None = None,
	date_to: str | None = None,
	limit: int | str = 20,
) -> dict:
	"""Get POS upload history."""
	filters = {}
	if store:
		filters["store"] = store
	if date_from:
		filters["pos_date"] = [">=", date_from]
	if date_to:
		if "pos_date" in filters:
			filters["pos_date"] = ["between", [date_from, date_to]]
		else:
			filters["pos_date"] = ["<=", date_to]

	uploads = frappe.get_all(
		"BEI POS Upload",
		filters=filters,
		fields=["name", "store", "pos_date", "gross_sales", "net_sales", "status"],
		order_by="pos_date desc",
		limit=int(limit),
	)
	return {"uploads": uploads}


# ==============================================================================
# BANK DEPOSIT REPORTS
# ==============================================================================


@frappe.whitelist()
def submit_bank_deposit(
	store: str | None = None,
	deposit_date: str | None = None,
	bank: str | None = None,
	deposits: list | str | None = None,
	total_amount: int | float | str = 0,
	photos: list | str | None = None,
	notes: str | None = None,
	deposit_type: str | None = None,
) -> dict:
	"""
	Submit bank deposit record with deposit slip photos.

	Bug fixes (C5):
	- Resolve store to warehouse (frontend sends branch code)
	- deposit_date defaults to today
	- bank defaults to empty string (frontend may not send it for Pickup type)
	- Photos converted from base64 via save_base64_image
	- deposit_type accepted (Bank Deposit or Pickup per DocType)
	- insert with ignore_permissions=True for Employee Self Service role
	- Returns user-friendly error instead of raw traceback

	Args:
	    store: Store/branch name
	    deposit_date: Date of deposit (defaults to today)
	    bank: Bank name (BDO, BPI, etc.)
	    deposits: List of {dates_covered, amount} for each deposit entry
	    total_amount: Total deposit amount
	    photos: List of deposit slip photo URLs/base64
	    notes: Optional notes
	    deposit_type: Bank Deposit or Pickup
	"""
	try:
		validate_store_ops_role()

		if not store:
			frappe.throw(_("Store is required"))

		# Resolve branch name to warehouse name
		warehouse = resolve_warehouse(store)

		if isinstance(deposits, str):
			try:
				deposits = json.loads(deposits)
			except (json.JSONDecodeError, ValueError):
				frappe.throw(_("Invalid deposits format. Please submit the form again."))

		if isinstance(photos, str):
			try:
				photos = json.loads(photos)
			except (json.JSONDecodeError, ValueError):
				photos = [photos]

		if not deposits:
			deposits = []

		if not photos:
			photos = []

		doc = frappe.new_doc("BEI Bank Deposit")
		doc.store = warehouse
		doc.deposit_date = deposit_date or nowdate()
		doc.bank = bank or ""
		doc.total_amount = float(total_amount or 0)
		doc.submitted_by = frappe.session.user
		doc.notes = notes
		if deposit_type:
			doc.deposit_type = deposit_type

		# Add deposit entries
		for entry in deposits:
			doc.append(
				"deposit_entries",
				{
					"dates_covered": entry.get("dates_covered") or entry.get("date") or nowdate(),
					"amount": float(entry.get("amount", 0)),
				},
			)

		# Add photos - convert base64 to file URLs
		for i, photo in enumerate(photos):
			photo_data = photo
			if isinstance(photo, dict):
				photo_data = photo.get("photo") or photo.get("url") or photo.get("data")

			photo_url = (
				save_base64_image(photo_data, "BEI Bank Deposit", fieldname="photo") if photo_data else None
			)
			if photo_url:
				doc.append("deposit_photos", {"photo": photo_url, "photo_number": i + 1})

		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		return {"success": True, "name": doc.name}

	except Exception as e:
		frappe.log_error(
			f"Bank Deposit Error for store {store}: {e!s}\n\n{frappe.get_traceback()}",
			"Bank Deposit Submission Error",
		)
		return {
			"success": False,
			"error": _("Failed to submit bank deposit. Please try again or contact support."),
		}


@frappe.whitelist()
def get_bank_deposits(
	store: str | None = None,
	date_from: str | None = None,
	date_to: str | None = None,
	limit: int | str = 20,
) -> dict:
	"""Get bank deposit history."""
	filters = {}
	if store:
		filters["store"] = store
	if date_from:
		filters["deposit_date"] = [">=", date_from]
	if date_to:
		if "deposit_date" in filters:
			filters["deposit_date"] = ["between", [date_from, date_to]]
		else:
			filters["deposit_date"] = ["<=", date_to]

	deposits = frappe.get_all(
		"BEI Bank Deposit",
		filters=filters,
		fields=["name", "store", "deposit_date", "bank", "total_amount", "submitted_by"],
		order_by="deposit_date desc",
		limit=int(limit),
	)
	return {"deposits": deposits}


# ==============================================================================
# POS DATA EXTRACTION
# ==============================================================================


@frappe.whitelist()
def extract_pos_data(
	sales_summary: str | None = None,
	transaction_report: str | None = None,
	discount_report: str | None = None,
	daily_sales_revenue: str | None = None,
	product_mix: str | None = None,
) -> dict:
	"""
	Extract and parse data from MOSAIC POS export files.

	Accepts file content in multiple formats:
	- File URL (stored in Frappe File)
	- Base64 encoded string
	- Direct file content

	Args:
	    sales_summary: Sales Summary file
	    transaction_report: Transaction Report file
	    discount_report: Discount Report file
	    daily_sales_revenue: Daily Sales Revenue file
	    product_mix: Product Mix file

	Returns:
	    Consolidated extracted data for frontend display:
	    {
	        "success": True,
	        "data": {
	            "date": "2026-01-30",
	            "gross_sales": 65474.00,
	            "net_sales": 55587.24,
	            "vat": 5575.73,
	            "beginning_si": 16526,
	            "ending_si": 16735,
	            "transaction_count": 209,
	            "eod_counter": 76,
	            "discount_pwd": 1056.85,
	            "discount_senior": 1223.28,
	            "by_payment_type": {
	                "Cash": 38970.00,
	                "MosaicPay QRPH": 26504.00
	            },
	            "total_items_sold": 357,
	            ...
	        }
	    }
	"""
	import base64

	from hrms.utils.pos_parser import extract_all_pos_data

	def get_file_content(file_input):
		"""Get file content from various input formats."""
		if not file_input:
			return None

		# If it's a Frappe file URL
		if isinstance(file_input, str) and file_input.startswith("/files/"):
			file_doc = frappe.get_doc("File", {"file_url": file_input})
			return file_doc.get_content()

		# If it's base64 encoded
		if isinstance(file_input, str):
			try:
				# Try to decode base64
				return base64.b64decode(file_input)
			except Exception:
				pass

		# If it's already bytes
		if isinstance(file_input, bytes):
			return file_input

		return None

	try:
		result = extract_all_pos_data(
			sales_summary_content=get_file_content(sales_summary),
			transaction_report_content=get_file_content(transaction_report),
			discount_report_content=get_file_content(discount_report),
			daily_sales_revenue_content=get_file_content(daily_sales_revenue),
			product_mix_content=get_file_content(product_mix),
		)

		return {
			"success": result.get("success", False),
			"data": result.get("consolidated", {}),
			"sales_summary": result.get("sales_summary"),
			"transaction_report": result.get("transaction_report"),
			"discount_report": result.get("discount_report"),
			"daily_sales_revenue": result.get("daily_sales_revenue"),
			"product_mix": result.get("product_mix"),
			"errors": result.get("errors", []),
		}

	except Exception as e:
		frappe.log_error(f"POS extraction error: {e!s}", "POS Extraction")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_extracted_pos_data(pos_upload_name: str) -> dict:
	"""
	Get extracted data for a POS Upload document.

	If extraction hasn't been done yet, perform it now.
	Stores extracted data in the document for caching.

	Args:
	    pos_upload_name: Name of BEI POS Upload document

	Returns:
	    Extracted POS data
	"""
	doc = frappe.get_doc("BEI POS Upload", pos_upload_name)

	# Check if already extracted
	if doc.extracted_data:
		try:
			return {"success": True, "data": json.loads(doc.extracted_data), "cached": True}
		except Exception:
			pass

	# Extract data from uploaded files
	result = extract_pos_data(
		sales_summary=doc.sales_summary,
		transaction_report=doc.transaction_report,
		discount_report=doc.discount_report,
		daily_sales_revenue=doc.daily_sales_revenue,
		product_mix=doc.product_mix,
	)

	# Cache the result if successful
	if result.get("success") and result.get("data"):
		doc.db_set("extracted_data", json.dumps(result["data"]))
		doc.db_set("gross_sales", result["data"].get("gross_sales", 0))
		doc.db_set("net_sales", result["data"].get("net_sales", 0))
		doc.db_set("status", "Extracted")

	return result


# ==============================================================================
# CLOSING REPORT 3-STAGE FLOW (Enhanced 2026-01-31)
# ==============================================================================


@frappe.whitelist()
def get_or_create_closing_report(store: str) -> dict:
	"""
	Get existing closing report for today or create a new one.
	Returns the report document with current stage status.
	"""
	validate_store_ops_role()
	if not store:
		frappe.throw(_("Store is required"))

	# Resolve store to warehouse (C2 fix for get_or_create_closing_report)
	store = resolve_warehouse(store)

	today = nowdate()

	# Check for existing report
	existing = frappe.db.get_value(
		"BEI Store Closing Report",
		{"store": store, "report_date": today},
		["name", "stage_completed", "status"],
		as_dict=True,
	)

	if existing:
		doc = frappe.get_doc("BEI Store Closing Report", existing.name)
		return {
			"success": True,
			"name": doc.name,
			"is_new": False,
			"stage_completed": doc.stage_completed,
			"status": doc.status,
			"data": doc.as_dict(),
		}

	# Create new report
	doc = frappe.new_doc("BEI Store Closing Report")
	doc.store = store
	doc.report_date = today
	doc.submitted_by = frappe.session.user
	# stage_completed is auto-computed by DocType's update_stage_completed() during insert
	doc.insert()

	return {
		"success": True,
		"name": doc.name,
		"is_new": True,
		"stage_completed": "cash",
		"status": "Draft",
		"data": doc.as_dict(),
	}


@frappe.whitelist()
def submit_closing_stage1_cash(
	report_name: str,
	petty_cash_fund: int | float | str = 0,
	delivery_fund: int | float | str = 0,
	change_fund: int | float | str = 0,
	cash_notes: str | None = None,
	pos_down: bool | int | str = False,
	pos_down_estimated_sales: int | float | str | None = None,
	pos_down_transaction_count: int | str | None = None,
	pos_down_notes: str | None = None,
	variance_explanation: str | None = None,
	actual_cash_count: int | float | str = 0,
	**kwargs: object,
) -> dict:
	"""
	Submit Stage 1: Cash Count & Reconciliation

	Note: Cash Sales Fund stays in POS only - not entered here.
	Only Petty Cash, Delivery Fund, and Change Fund are entered in this stage.
	Denomination breakdown and voucher amounts are passed via kwargs.
	actual_cash_count: Physical cash count by crew.
	variance_explanation: Required when cash_variance > ±50 (explain while you see the number).
	"""
	validate_store_ops_role()
	doc = frappe.get_doc("BEI Store Closing Report", report_name)

	doc.petty_cash_fund = float(petty_cash_fund or 0)
	doc.delivery_fund = float(delivery_fund or 0)
	doc.change_fund = float(change_fund or 0)
	doc.cash_notes = cash_notes
	doc.actual_cash_count = float(actual_cash_count or 0)
	doc.variance_explanation = variance_explanation

	# POS Down mode
	doc.pos_down = 1 if pos_down else 0
	if pos_down:
		doc.pos_down_estimated_sales = float(pos_down_estimated_sales or 0)
		doc.pos_down_transaction_count = int(pos_down_transaction_count or 0)
		doc.pos_down_notes = pos_down_notes

	# Save denomination breakdown and voucher amounts
	denom_prefixes = ("pcf_denom_", "del_denom_", "chg_denom_")
	voucher_fields = ("pcf_voucher_amount", "delivery_voucher_amount")
	for key, value in kwargs.items():
		if key.startswith(denom_prefixes) or key in voucher_fields:
			if doc.meta.has_field(key):
				doc.set(key, float(value or 0))

	# stage_completed is auto-computed by DocType's update_stage_completed() during save
	doc.save()

	return {
		"success": True,
		"name": doc.name,
		"stage_completed": doc.stage_completed,
		"total_funds": doc.total_funds,
		"cash_variance": doc.cash_variance,
	}


@frappe.whitelist()
def submit_closing_stage2_checklist(
	report_name: str,
	inventory_items: list | str,
	checklist_items: list | str | None = None,
	cashier_signoff: bool | int | str = False,
	production_signoff: bool | int | str = False,
	supervisor_signoff: bool | int | str = False,
) -> dict:
	"""
	Submit Stage 2: Checklist & Inventory Spot Check

	inventory_items: List of {item_name, expected_count, actual_count}
	- 12 specific items categorized by: Highest Cost, Single Count Variances,
	  Shortest Shelf Life, Most Used Items
	- Accepts both item_name and item_description keys (frontend compatibility)

	checklist_items: General end-of-day tasks

	Note: equipment_status moved to Stage 3 (entered alongside equipment photos).
	"""
	validate_store_ops_role()
	doc = frappe.get_doc("BEI Store Closing Report", report_name)

	if isinstance(inventory_items, str):
		inventory_items = json.loads(inventory_items)

	if isinstance(checklist_items, str):
		checklist_items = json.loads(checklist_items)

	# Clear existing inventory items
	doc.inventory_spot_check = []

	# Add inventory spot check items (12 items)
	for item in inventory_items:
		doc.append(
			"inventory_spot_check",
			{
				"item_name": item.get("item_name") or item.get("item_description") or item.get("name", ""),
				"category": item.get("category"),
				"expected_count": float(item.get("expected_count", 0)),
				"actual_count": float(item.get("actual_count", 0)),
			},
		)

	# Add checklist items if provided
	if checklist_items:
		doc.checklist_items = []
		for item in checklist_items:
			doc.append("checklist_items", item)

	# Staff signoffs
	doc.cashier_signoff = 1 if cashier_signoff else 0
	doc.production_signoff = 1 if production_signoff else 0
	doc.supervisor_signoff = 1 if supervisor_signoff else 0

	# stage_completed is auto-computed by DocType's update_stage_completed() during save
	doc.save()

	return {
		"success": True,
		"name": doc.name,
		"stage_completed": doc.stage_completed,
		"inventory_variance_total": doc.inventory_variance_total,
		"inventory_variance_count": doc.inventory_variance_count,
	}


@frappe.whitelist()
def submit_closing_stage3_photos(
	report_name: str,
	x_reading_opening_photo: str,
	x_reading_closing_photo: str,
	z_reading_photo: str,
	store_photos: list | str | None = None,
	equipment_status: str | None = None,
	notes: str | None = None,
) -> dict:
	"""
	Submit Stage 3: Photos & Equipment

	Document Scanner Photos (with edge detection):
	- x_reading_opening_photo: X-Reading from opening shift
	- x_reading_closing_photo: X-Reading from closing shift
	- z_reading_photo: Z-Reading (end of day)

	store_photos: Dict of store area photos (accepts both photo_* and short key formats)
	equipment_status: Dict with freezer_temp, chiller_temp, pos_closed_properly
	                  (moved from Stage 2 — entered alongside equipment photos)

	Removed: pos_files (handled by separate BEI POS Upload endpoint),
	         variance_explanation (moved to Stage 1 — explain when you see the number)
	"""
	validate_store_ops_role()
	doc = frappe.get_doc("BEI Store Closing Report", report_name)
	doctype_name = "BEI Store Closing Report"

	# Document scanner photos (required) — save as files, not raw base64
	if not x_reading_opening_photo or not str(x_reading_opening_photo).strip():
		frappe.throw(_("X-Reading Opening photo is required"), title=_("Missing Photo"))
	if not x_reading_closing_photo or not str(x_reading_closing_photo).strip():
		frappe.throw(_("X-Reading Closing photo is required"), title=_("Missing Photo"))
	if not z_reading_photo or not str(z_reading_photo).strip():
		frappe.throw(_("Z-Reading photo is required"), title=_("Missing Photo"))

	doc.photo_xread_opening = save_base64_image(
		str(x_reading_opening_photo).strip(), doctype_name, docname=doc.name, fieldname="photo_xread_opening"
	)
	doc.photo_xread_closing = save_base64_image(
		str(x_reading_closing_photo).strip(), doctype_name, docname=doc.name, fieldname="photo_xread_closing"
	)
	doc.photo_zread = save_base64_image(
		str(z_reading_photo).strip(), doctype_name, docname=doc.name, fieldname="photo_zread"
	)

	# Store area photos — normalize keys (accept both photo_* and short format)
	if store_photos:
		if isinstance(store_photos, str):
			store_photos = json.loads(store_photos)
		if isinstance(store_photos, list):
			store_photos = {
				p.get("field", ""): p.get("data", p.get("url", ""))
				for p in store_photos
				if isinstance(p, dict)
			}

		photo_map = {
			"photo_logo_signage": ["photo_logo_signage", "logo_signage"],
			"photo_hygrometer": ["photo_hygrometer", "hygrometer"],
			"photo_water_meter": ["photo_water_meter", "water_meter"],
			"photo_backup_area_clean": ["photo_backup_area_clean", "backup_area"],
			"photo_frozen_milk_clean": ["photo_frozen_milk_clean", "frozen_milk"],
			"photo_toppings_clean": ["photo_toppings_clean", "toppings"],
			"photo_dispatch_clean": ["photo_dispatch_clean", "dispatch"],
			"photo_cold_storage_close": ["photo_cold_storage_close", "cold_storage"],
			"photo_cashier_clean": ["photo_cashier_clean", "cashier"],
			"photo_rollup_closed": ["photo_rollup_closed", "rollup_door"],
		}
		for doc_field, accepted_keys in photo_map.items():
			for key in accepted_keys:
				value = store_photos.get(key)
				if value:
					saved_url = save_base64_image(value, doctype_name, docname=doc.name, fieldname=doc_field)
					if saved_url:
						doc.set(doc_field, saved_url)
					break

	# Equipment readings (moved from Stage 2 — entered alongside equipment photos)
	if equipment_status:
		if isinstance(equipment_status, str):
			equipment_status = json.loads(equipment_status)
		doc.freezer_temp = equipment_status.get("freezer_temp")
		doc.chiller_temp = equipment_status.get("chiller_temp")
		doc.pos_closed_properly = equipment_status.get("pos_closed_properly", 0)

	doc.notes = notes
	doc.report_time = now_datetime().strftime("%H:%M:%S")

	# Auto-link today's POS upload if not already linked (D-1)
	if not doc.pos_upload:
		today_upload = frappe.db.get_value(
			"BEI POS Upload", {"store": doc.store, "pos_date": doc.report_date}, "name"
		)
		if today_upload:
			doc.pos_upload = today_upload

	# stage_completed is auto-computed by DocType's update_stage_completed() during save
	doc.save(ignore_permissions=True)

	return {
		"success": True,
		"name": doc.name,
		"stage_completed": doc.stage_completed,
		"status": doc.status,
		"cash_variance": doc.cash_variance,
	}


@frappe.whitelist()
def get_closing_report_status(store: str | None = None, date: str | None = None) -> dict:
	"""
	Get closing report status for a store on a specific date.
	Returns stage progress and completion status.
	"""
	if not store:
		frappe.throw(_("Store is required"))
	if not date:
		date = nowdate()
	required_fields = ["name", "stage_completed", "status", "pos_down", "cash_variance"]
	optional_fields = [
		fieldname
		for fieldname in ("inventory_variance_total", "cashier_signoff", "production_signoff")
		if _has_column("BEI Store Closing Report", fieldname)
	]

	report = frappe.db.get_value(
		"BEI Store Closing Report",
		{"store": store, "report_date": date},
		required_fields + optional_fields,
		as_dict=True,
	)

	if not report:
		return {"exists": False, "stage_completed": None, "status": None}

	return {
		"exists": True,
		"name": report.get("name"),
		"stage_completed": report.get("stage_completed"),
		"status": report.get("status"),
		"pos_down": report.get("pos_down"),
		"cash_variance": report.get("cash_variance"),
		"inventory_variance_total": flt(report.get("inventory_variance_total") or 0),
		"cashier_signoff": cint(report.get("cashier_signoff") or 0),
		"production_signoff": cint(report.get("production_signoff") or 0),
	}


# ==============================================================================
# MID-SHIFT HANDOVER
# ==============================================================================


@frappe.whitelist()
def submit_mid_shift_handover(
	store: str,
	outgoing_cashier: str | None = None,
	incoming_cashier: str | None = None,
	x_reading_photo: str | None = None,
	cash_count: int | float | str = 0,
	expected_cash: int | float | str = 0,
	variance_explanation: str | None = None,
	x_reading_cash: int | float | str | None = None,
	sales_cash_deposit: int | float | str | None = None,
) -> dict:
	"""
	Submit mid-shift handover when cashiers switch shifts.
	Identifies shortage/overage per cashier shift.

	Bug fixes (C4):
	- Resolve employee IDs from names/emails (frontend may send either)
	- x_reading_photo converted via save_base64_image
	- cash_count/expected_cash default to 0 to avoid float(None) errors
	- Accept renamed frontend field aliases (x_reading_cash, sales_cash_deposit)
	- Auto-populate outgoing/incoming cashier from session user if not provided
	- insert with ignore_permissions=True for Store Staff role
	"""
	try:
		validate_store_ops_role()
		if not store:
			frappe.throw(_("Store is required"))

		# Resolve store
		warehouse = resolve_warehouse(store)

		# Resolve employee references - frontend may send email, name, or employee ID
		def resolve_employee_ref(ref):
			if not ref:
				return None
			# Check if it's already an Employee ID
			if frappe.db.exists("Employee", ref):
				return ref
			# Check by user_id (email)
			emp = frappe.db.get_value("Employee", {"user_id": ref, "status": "Active"}, "name")
			if emp:
				return emp
			# Check by employee_name
			emp = frappe.db.get_value("Employee", {"employee_name": ref, "status": "Active"}, "name")
			if emp:
				return emp
			return ref  # Return as-is, let Frappe validation handle it

		resolved_outgoing = resolve_employee_ref(outgoing_cashier)
		resolved_incoming = resolve_employee_ref(incoming_cashier)

		# Auto-populate from session user if not provided
		if not resolved_outgoing:
			resolved_outgoing = frappe.db.get_value(
				"Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
			)
		if not resolved_incoming:
			resolved_incoming = resolved_outgoing  # Same person if not specified

		# Handle x_reading_photo base64
		photo_url = (
			save_base64_image(x_reading_photo, "BEI Mid-Shift Handover", fieldname="x_reading_photo")
			if x_reading_photo
			else None
		)

		# Support renamed fields from frontend
		final_cash_count = float(sales_cash_deposit or cash_count or 0)
		final_expected_cash = float(x_reading_cash or expected_cash or 0)

		doc = frappe.new_doc("BEI Mid-Shift Handover")
		doc.store = warehouse
		doc.report_date = nowdate()
		doc.handover_time = now_datetime().strftime("%H:%M:%S")
		doc.outgoing_cashier = resolved_outgoing
		doc.incoming_cashier = resolved_incoming
		doc.x_reading_photo = photo_url
		doc.cash_count = final_cash_count
		doc.expected_cash = final_expected_cash
		doc.variance_explanation = variance_explanation
		doc.submitted_by = frappe.session.user

		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)

		# Link to closing report if exists
		closing_report = frappe.db.get_value(
			"BEI Store Closing Report", {"store": warehouse, "report_date": nowdate()}, "name"
		)
		if closing_report:
			doc.db_set("closing_report", closing_report)

		return {
			"success": True,
			"name": doc.name,
			"variance": getattr(doc, "variance", 0),
			"status": getattr(doc, "status", "Submitted"),
		}

	except Exception as e:
		frappe.log_error(
			f"Handover Error for store {store}: {e!s}\n\n{frappe.get_traceback()}",
			"Handover Submission Error",
		)
		return {
			"success": False,
			"error": _("Failed to submit handover report. Please try again or contact support."),
		}


@frappe.whitelist()
def get_mid_shift_handovers(
	store: str,
	date: str | None = None,
	limit: int | str = 10,
) -> dict:
	"""Get mid-shift handovers for a store on a specific date."""
	validate_store_ops_role()

	if not date:
		date = nowdate()

	handovers = frappe.get_all(
		"BEI Mid-Shift Handover",
		filters={"store": store, "report_date": date},
		fields=[
			"name",
			"handover_time",
			"outgoing_cashier",
			"incoming_cashier",
			"cash_count",
			"expected_cash",
			"variance",
			"status",
		],
		order_by="handover_time desc",
		limit=int(limit),
	)

	# Get employee names
	for h in handovers:
		h["outgoing_cashier_name"] = (
			frappe.db.get_value("Employee", h["outgoing_cashier"], "employee_name") or h["outgoing_cashier"]
		)
		h["incoming_cashier_name"] = (
			frappe.db.get_value("Employee", h["incoming_cashier"], "employee_name") or h["incoming_cashier"]
		)

	return {"handovers": handovers}


# ==============================================================================
# MAINTENANCE REQUESTS
# ==============================================================================


@frappe.whitelist()
def submit_maintenance_request(
	store: str | None = None,
	priority: str | None = None,
	description: str | None = None,
	issue_category: str | None = None,
	category: str | None = None,
	equipment_area: str | None = None,
	impact_on_operations: str | None = None,
	title: str | None = None,
	before_photos: list | str | None = None,
	photos: list | str | None = None,
) -> dict:
	"""
	Submit a maintenance request from store staff.
	Notifies Projects team (Daniel) for assessment and assignment.

	Args:
	    store: Store/branch name
	    priority: Urgent, High, Normal
	    description: Issue description
	    issue_category: Category (Equipment, Plumbing, etc.) - backend param name
	    category: Category - frontend param name (alias for issue_category)
	    equipment_area: Specific equipment/area affected (optional)
	    impact_on_operations: Can Operate, Limited Operations, Cannot Operate (optional)
	    title: Issue title (optional, prepended to description)
	    before_photos: Single photo (deprecated, for backward compatibility)
	    photos: JSON array of photo objects [{photo: url, caption: text}, ...]
	"""
	validate_store_ops_role()

	import json

	if not store:
		frappe.throw(_("Store is required"))

	if not priority or not description:
		frappe.throw(_("Priority and description are required"))

	# Support both parameter names (frontend sends 'category', backend expects 'issue_category')
	final_category = issue_category or category
	if not final_category:
		frappe.throw(_("Issue category is required"))

	# Resolve branch name to warehouse name
	warehouse = resolve_warehouse(store)

	# Build full description from title + description
	full_description = description
	if title:
		full_description = f"{title}\n\n{description}"

	doc = frappe.new_doc("BEI Maintenance Request")
	doc.store = warehouse
	doc.request_date = nowdate()
	doc.issue_category = final_category
	doc.equipment_area = equipment_area or "Other"
	doc.priority = priority
	doc.description = full_description
	# Normalize impact_on_operations (frontend may send "Partial Impact" for "Limited Operations")
	impact_map = {"Partial Impact": "Limited Operations"}
	normalized_impact = impact_map.get(impact_on_operations, impact_on_operations) or "Can Operate"
	doc.impact_on_operations = normalized_impact
	doc.reported_by = frappe.session.user
	doc.status = "Open"

	# Handle photos - support both old single photo and new array format
	# Also handles base64 data by saving to file system first
	if photos:
		# Parse JSON if string
		if isinstance(photos, str):
			try:
				photos = json.loads(photos)
			except (json.JSONDecodeError, ValueError):
				# Not valid JSON — treat as a single photo URL/base64 string
				photos = [photos]

		# Ensure iterable (single dict becomes a list)
		if isinstance(photos, dict):
			photos = [photos]

		# Add each photo to the child table
		for photo_data in photos:
			photo_url = None
			caption = ""

			if isinstance(photo_data, str):
				# Simple string - could be URL or base64
				photo_url = save_base64_image(photo_data, "BEI Maintenance Request", fieldname="photo")
			elif isinstance(photo_data, dict):
				# Object with photo and optional caption
				raw_photo = photo_data.get("photo") or photo_data.get("url")
				photo_url = save_base64_image(raw_photo, "BEI Maintenance Request", fieldname="photo")
				caption = photo_data.get("caption", "")

			if photo_url:
				doc.append("photos", {"photo": photo_url, "caption": caption})
	elif before_photos:
		# Backward compatibility: convert single photo to child table entry
		photo_url = save_base64_image(before_photos, "BEI Maintenance Request", fieldname="photo")
		if photo_url:
			doc.append("photos", {"photo": photo_url})

	doc.insert(ignore_permissions=True)

	return {
		"success": True,
		"name": doc.name,
		"message": _("Maintenance request {0} submitted. Projects team will be notified.").format(doc.name),
	}


@frappe.whitelist()
def get_maintenance_requests(
	store: str | None = None,
	status: str | None = None,
	limit: int | str = 20,
	my_requests: bool | int | str = False,
) -> dict:
	"""Get maintenance requests optionally filtered by store and status.

	Bug fix (C14): Added my_requests parameter to filter by current user's reported_by.
	This is the fix for "request not visible after submit" - the frontend was calling
	get_maintenance_requests without filtering by user, so it showed requests from
	all stores (or none if store filter didn't match).
	"""
	filters = {}

	# C14 fix: When my_requests=True, filter by current user
	if my_requests or (not store and not status):
		filters["reported_by"] = frappe.session.user
	else:
		if store:
			# Resolve store name for consistent matching
			try:
				warehouse = resolve_warehouse(store)
				filters["store"] = warehouse
			except Exception:
				filters["store"] = store
		if status:
			if isinstance(status, str):
				filters["status"] = status
			else:
				filters["status"] = ["in", status]

	requests = frappe.get_all(
		"BEI Maintenance Request",
		filters=filters,
		fields=[
			"name",
			"store",
			"store_code",
			"issue_category",
			"equipment_area",
			"priority",
			"status",
			"scheduled_date",
			"request_date",
			"reported_by",
			"description",
		],
		order_by="request_date desc, creation desc",
		limit=int(limit),
	)

	return {"requests": requests}


@frappe.whitelist()
def get_my_maintenance_requests(status: str | None = None, limit: int | str = 20) -> dict:
	"""Get maintenance requests submitted by current user.

	Bug fix (C14): Dedicated endpoint for "View My Requests" functionality.
	Filters by reported_by = current user so submitted requests always appear.
	"""
	filters = {"reported_by": frappe.session.user}
	if status:
		if isinstance(status, str):
			filters["status"] = status
		else:
			filters["status"] = ["in", status]

	requests = frappe.get_all(
		"BEI Maintenance Request",
		filters=filters,
		fields=[
			"name",
			"store",
			"store_code",
			"issue_category",
			"equipment_area",
			"priority",
			"status",
			"scheduled_date",
			"request_date",
			"description",
		],
		order_by="request_date desc, creation desc",
		limit=int(limit),
	)

	return {"requests": requests}


@frappe.whitelist()
def check_maintenance_for_closing(store: str, date: str | None = None) -> dict:
	"""
	Check if there's maintenance scheduled or completed today that needs verification.
	Used to show dynamic maintenance section in closing report.
	"""
	if not date:
		date = nowdate()

	# Get completed maintenance that needs verification
	from hrms.hr.doctype.bei_maintenance_completion.bei_maintenance_completion import (
		check_maintenance_for_closing_report,
	)

	return check_maintenance_for_closing_report(store, date)


@frappe.whitelist()
def verify_maintenance_from_closing(
	maintenance_completion: str,
	verified: bool | int | str = True,
	verification_notes: str | None = None,
) -> dict:
	"""
	Verify or reject maintenance completion from closing report.
	"""
	doc = frappe.get_doc("BEI Maintenance Completion", maintenance_completion)

	if verified:
		return doc.verify_completion(notes=verification_notes)
	else:
		if not verification_notes:
			frappe.throw(_("Rejection reason is required"))
		return doc.reject_completion(notes=verification_notes)
