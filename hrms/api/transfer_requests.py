"""BEI Transfer Request API.

Implements staged transfer approvals, future-dated HR submit bridge,
and ADMS sync orchestration with per-device audit rows.
"""

from __future__ import annotations

import os
import re
from typing import Any

import requests

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_to_date, cint, get_datetime, getdate, now_datetime, nowdate

from hrms.utils.adms_validation import (
	preflight_check_enrollment,
	validate_device_batch,
	validate_employee_bio_id,
)
from hrms.utils.device_mapping import DEVICE_TO_STORE
from hrms.utils.roving_employees import is_roving


DOCTYPE_TRANSFER_REQUEST = "BEI Transfer Request"
DOCTYPE_TRANSFER_DEVICE_COMMAND = "BEI Transfer Device Command"
BEI_COMPANY_NAME = "Bebang Enterprise Inc."

STAGE_PENDING_AREA = "Pending Area Approval"
STAGE_PENDING_HR = "Pending HR Approval"
STAGE_WAITING_EFFECTIVE = "HR Approved - Waiting Effective Date"
STAGE_PENDING_IT = "Pending IT Approval"
STAGE_READY_SYNC = "Ready for Sync"
STAGE_SYNC_IN_PROGRESS = "Sync In Progress"
STAGE_SYNCED = "Synced"
STAGE_SYNC_FAILED = "Sync Failed"
STAGE_REJECTED = "Rejected"
STAGE_CANCELLED = "Cancelled"

IMMUTABLE_STAGES = {STAGE_REJECTED, STAGE_CANCELLED, STAGE_SYNCED}
NON_APPROVABLE_STAGES = {
	STAGE_READY_SYNC,
	STAGE_SYNC_IN_PROGRESS,
	STAGE_SYNC_FAILED,
	STAGE_SYNCED,
	STAGE_REJECTED,
	STAGE_CANCELLED,
}

ADMS_STATUS_PENDING = "PENDING"
ADMS_STATUS_SENT = "SENT"
ADMS_STATUS_ACKED = "ACKED"
ADMS_STATUS_FAILED = "FAILED"

REQUESTER_ROLES = {"Store Supervisor", "Area Supervisor", "HR User", "HR Manager", "System Manager"}
AREA_APPROVER_ROLES = {"Area Supervisor", "System Manager"}
HR_APPROVER_ROLES = {"HR User", "HR Manager", "System Manager"}
IT_APPROVER_ROLES = {"System Manager", "IT User"}
HR_ORG_CHANGE_ROLES = {"HR User", "HR Manager"}
READ_ALL_ROLES = AREA_APPROVER_ROLES.union(HR_APPROVER_ROLES).union(IT_APPROVER_ROLES)
TRANSFER_READ_ROLES = REQUESTER_ROLES.union(READ_ALL_ROLES)

BLOCKED_WAREHOUSE_TERMS = (
	"3PL",
	"3RD PARTY",
	"THIRD PARTY",
	"3MD",
)

RELIEVER_CLEANUP_COMMAND_TYPE = "RELIEVER_DELETE_USERINFO"


def _has_any_role(roles: set[str], user: str | None = None) -> bool:
	active_user = user or frappe.session.user
	return bool(set(frappe.get_roles(active_user)).intersection(roles))


def _require_any_role(roles: set[str], message: str):
	if not _has_any_role(roles):
		frappe.throw(_(message), frappe.PermissionError)


def _can_manage_org_changes(user: str | None = None) -> bool:
	active_user = user or frappe.session.user
	if active_user == "Administrator":
		return True
	return bool(set(frappe.get_roles(active_user)).intersection(HR_ORG_CHANGE_ROLES))


def _normalize_optional_value(value: Any) -> str | None:
	if value is None:
		return None
	text = str(value).strip()
	return text or None


def _coerce_bool(value: Any) -> int:
	return 1 if cint(value) else 0


def _coerce_positive_int(value: Any, *, field_label: str) -> int | None:
	if value is None or str(value).strip() == "":
		return None
	parsed = cint(value)
	if parsed <= 0:
		frappe.throw(_("{0} must be greater than zero").format(field_label))
	return parsed


def _enforce_org_change_field_guard(*, to_department: str | None, to_designation: str | None):
	if _can_manage_org_changes():
		return
	if to_department or to_designation:
		frappe.throw(
			_("Only HR users can set Department or Designation in transfer requests"),
			frappe.PermissionError,
		)


def _compute_reliever_window(effective_date: Any, reliever_days: int | None) -> tuple[Any | None, Any | None]:
	if not reliever_days:
		return None, None
	start_date = getdate(effective_date)
	end_date = getdate(add_to_date(start_date, days=reliever_days))
	return start_date, end_date


def _build_branch_reports_to_defaults(options: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
	branches = sorted({(option.get("branch") or "").strip() for option in options if option.get("branch")})
	if not branches:
		return {}

	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active", "branch": ["in", branches]},
		fields=["name", "employee_name", "designation", "branch"],
		order_by="branch asc, designation asc, employee_name asc",
		limit_page_length=2000,
	)

	by_branch: dict[str, dict[str, Any]] = {}
	for row in employees:
		branch_name = (row.get("branch") or "").strip()
		if not branch_name:
			continue

		bucket = by_branch.setdefault(
			branch_name,
			{
				"area_manager": None,
				"store_oic": None,
				"default_reports_to": None,
			},
		)
		designation = (row.get("designation") or "").upper()
		candidate = {
			"employee": row.get("name"),
			"employee_name": row.get("employee_name"),
			"designation": row.get("designation"),
		}

		if not bucket["area_manager"] and ("AREA MANAGER" in designation or "AREA SUPERVISOR" in designation):
			bucket["area_manager"] = candidate
		if not bucket["store_oic"] and ("OIC" in designation or "STORE SUPERVISOR" in designation):
			bucket["store_oic"] = candidate

	for branch_name, leadership in by_branch.items():
		default_candidate = leadership.get("area_manager") or leadership.get("store_oic")
		if default_candidate:
			leadership["default_reports_to"] = default_candidate.get("employee")

	return by_branch


def _require_stage_approver(stage: str):
	stage_map = {
		STAGE_PENDING_AREA: AREA_APPROVER_ROLES,
		STAGE_PENDING_HR: HR_APPROVER_ROLES,
		STAGE_WAITING_EFFECTIVE: HR_APPROVER_ROLES,
		STAGE_PENDING_IT: IT_APPROVER_ROLES,
	}
	roles = stage_map.get(stage)
	if not roles:
		frappe.throw(_("This request is not in an approvable stage"))
	_require_any_role(roles, "You do not have permission to approve this stage")


def _set_stage(doc, stage: str, status: str = "Pending"):
	doc.current_stage = stage
	doc.stage_status = status
	doc.last_action_by = frappe.session.user
	doc.last_action_at = now_datetime()


def _append_timeline_comment(doc, text: str):
	doc.add_comment("Comment", text=text)


def _notify_transfer_event(doc, event_title: str, details: str | None = None):
	"""Best-effort Chat notification for transfer workflow milestones.

	Notification failures must never block transfer execution.
	"""
	try:
		from hrms.api.google_chat import send_message_to_space
		from hrms.utils.bei_config import SPACE_ADMIN_IT, SPACE_NOTIFICATIONS, get_chat_space

		technical_stages = {STAGE_PENDING_IT, STAGE_READY_SYNC, STAGE_SYNC_IN_PROGRESS, STAGE_SYNC_FAILED, STAGE_SYNCED}
		target_space = get_chat_space(SPACE_ADMIN_IT if doc.current_stage in technical_stages else SPACE_NOTIFICATIONS)
		message_lines = [
			f"*{event_title}*",
			f"Request: {doc.name}",
			f"Employee: {doc.employee_name or doc.employee}",
			f"Stage: {doc.current_stage}",
			f"Effective: {doc.effective_date}",
		]
		if details:
			message_lines.append(f"Details: {details}")
		send_message_to_space(target_space, "\n".join(message_lines))
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Transfer Notification Error")


def _require_store_warehouse_mapping(doc):
	if not doc.store_warehouse:
		frappe.throw(_("Missing Warehouse Mapping for target store"))
	resolved = _validate_store_warehouse_for_transfer(
		doc.store_warehouse,
		expected_branch=getattr(doc, "to_branch", None),
	)
	if not getattr(doc, "to_branch", None):
		doc.to_branch = resolved["branch"]


def _split_roles(raw_roles: str | None) -> list[str]:
	if not raw_roles:
		return []
	parts = re.split(r"[\n,]+", raw_roles)
	return [part.strip() for part in parts if part and part.strip()]


def _sync_designation_roles(employee_id: str, designation_hint: str | None = None) -> dict | None:
	"""Apply role changes from BEI Designation Role Map."""
	if not frappe.db.exists("DocType", "BEI Designation Role Map"):
		return None

	employee = frappe.get_doc("Employee", employee_id)
	if not employee.user_id:
		return None

	designation = designation_hint or employee.designation
	if not designation:
		return None

	map_name = frappe.db.get_value(
		"BEI Designation Role Map",
		{"designation": designation, "is_active": 1},
		"name",
	)
	if not map_name:
		return None

	role_map = frappe.get_doc("BEI Designation Role Map", map_name)
	roles_to_add = _split_roles(role_map.roles_to_add)
	roles_to_remove = _split_roles(role_map.roles_to_remove)

	current_roles = set(frappe.get_roles(employee.user_id))
	final_add = [role for role in roles_to_add if role not in current_roles]
	final_remove = [role for role in roles_to_remove if role in current_roles]

	if not final_add and not final_remove:
		return {"designation": designation, "added": [], "removed": []}

	user_doc = frappe.get_doc("User", employee.user_id)
	user_doc.flags.ignore_permissions = True
	if final_add:
		user_doc.add_roles(*final_add)
	if final_remove:
		user_doc.remove_roles(*final_remove)

	return {
		"designation": designation,
		"user_id": employee.user_id,
		"added": final_add,
		"removed": final_remove,
	}


def _serialize_request(doc, include_comments: bool = False):
	payload = doc.as_dict()

	if include_comments:
		payload["timeline"] = frappe.get_all(
			"Comment",
			filters={
				"reference_doctype": DOCTYPE_TRANSFER_REQUEST,
				"reference_name": doc.name,
			},
			fields=["comment_type", "content", "creation", "comment_by"],
			order_by="creation asc",
		)

	if frappe.db.exists("DocType", DOCTYPE_TRANSFER_DEVICE_COMMAND):
		payload["device_commands"] = frappe.get_all(
			DOCTYPE_TRANSFER_DEVICE_COMMAND,
			filters={"transfer_request": doc.name},
			fields=[
				"name",
				"device_sn",
				"command_type",
				"adms_command_id",
				"status",
				"attempts",
				"last_error",
				"sent_at",
				"acked_at",
			],
			order_by="creation asc",
		)

	return payload


def _build_transfer_details(doc) -> list[dict]:
	if cint(getattr(doc, "is_reliever", 0)):
		return []

	details = []
	candidate_rows = [
		("Branch", "branch", doc.from_branch, doc.to_branch),
		("Reports To", "reports_to", doc.from_reports_to, doc.to_reports_to),
	]
	for property_name, fieldname, current_value, new_value in candidate_rows:
		if new_value and new_value != current_value:
			details.append(
				{
					"property": property_name,
					"fieldname": fieldname,
					"current": current_value or "",
					"new": new_value,
				}
			)
	return details


def _ensure_employee_transfer(doc, submit_now: bool):
	"""Create (or submit) Employee Transfer linked to a transfer request."""
	if cint(getattr(doc, "is_reliever", 0)):
		# Reliever routing is temporary device enrollment and must not mutate Employee Master.
		return None

	employee = frappe.get_doc("Employee", doc.employee)

	if doc.employee_transfer_ref and frappe.db.exists("Employee Transfer", doc.employee_transfer_ref):
		transfer = frappe.get_doc("Employee Transfer", doc.employee_transfer_ref)
	else:
		transfer_details = _build_transfer_details(doc)
		if not transfer_details:
			frappe.throw(_("No employee master changes were detected for this transfer request"))

		transfer = frappe.get_doc(
			{
				"doctype": "Employee Transfer",
				"employee": doc.employee,
				"company": employee.company,
				"new_company": employee.company,
				"transfer_date": getdate(doc.effective_date),
				"transfer_details": transfer_details,
			}
		).insert(ignore_permissions=True)
		doc.employee_transfer_ref = transfer.name

	if submit_now and transfer.docstatus == 0:
		transfer.submit()

	return transfer


def _enforce_effective_date_dispatch_guard(
	doc,
	allow_emergency_override: int = 0,
	emergency_override_reason: str | None = None,
	hr_override_user: str | None = None,
):
	"""AUDIT-1 invariant: never dispatch before effective_date without evidence."""
	if getdate(nowdate()) >= getdate(doc.effective_date):
		return

	# Override already approved in a previous step.
	if doc.emergency_override_requested and doc.emergency_override_approved_at:
		return

	if not cint(allow_emergency_override):
		frappe.throw(
			_(
				"Cannot mark transfer as Ready for Sync before effective date. "
				"Use emergency override with dual approval evidence."
			)
		)

	if not emergency_override_reason:
		frappe.throw(_("Emergency override reason is required"))

	if not _has_any_role({"System Manager"}):
		frappe.throw(_("Emergency override requires a System Manager approver"), frappe.PermissionError)

	if not hr_override_user:
		frappe.throw(_("HR override approver is required"))
	if not frappe.db.exists("User", hr_override_user):
		frappe.throw(_("HR override approver does not exist"))
	if not _has_any_role(HR_APPROVER_ROLES, user=hr_override_user):
		frappe.throw(_("HR override approver must have HR approval permissions"))

	doc.emergency_override_requested = 1
	doc.emergency_override_reason = emergency_override_reason
	doc.emergency_override_hr_approved_by = hr_override_user
	doc.emergency_override_system_approved_by = frappe.session.user
	doc.emergency_override_approved_at = now_datetime()


def _normalize_store_key(value: str | None) -> str:
	if not value:
		return ""
	v = value.strip().upper()
	v = re.sub(r"\s*-\s*BEI$", "", v)
	v = re.sub(r"\s*-\s*BEBANG\s+ENTERPRISE(?:\s+INC\.?)?$", "", v)
	# Warehouse labels often follow "<store> - <company>".
	if " - " in v:
		v = v.split(" - ", 1)[0].strip()
	v = v.replace("&", "AND")
	v = re.sub(r"[^A-Z0-9]+", "", v)
	return v


def _contains_blocked_warehouse_term(value: str | None) -> bool:
	if not value:
		return False
	upper_value = str(value).upper()
	return any(term in upper_value for term in BLOCKED_WAREHOUSE_TERMS)


def _get_branch_index() -> dict[str, str]:
	rows = frappe.get_all("Branch", fields=["name"], limit_page_length=0)
	index: dict[str, str] = {}
	for row in rows:
		branch_name = (row.get("name") or "").strip()
		if not branch_name:
			continue
		index[_normalize_store_key(branch_name)] = branch_name
	return index


def _resolve_branch_from_store_warehouse(store_warehouse: str | None, branch_index: dict[str, str] | None = None) -> str | None:
	if not store_warehouse:
		return None

	candidates = [str(store_warehouse).strip()]
	if " - " in candidates[0]:
		candidates.append(candidates[0].split(" - ", 1)[0].strip())

	for candidate in candidates:
		if candidate and frappe.db.exists("Branch", candidate):
			return candidate

	normalized_index = branch_index or _get_branch_index()
	for candidate in candidates:
		norm = _normalize_store_key(candidate)
		if norm and norm in normalized_index:
			return normalized_index[norm]

	return None


def _validate_store_warehouse_for_transfer(store_warehouse: str | None, expected_branch: str | None = None) -> dict[str, Any]:
	warehouse_name = (store_warehouse or "").strip()
	if not warehouse_name:
		frappe.throw(_("Missing Warehouse Mapping for target store"))
	if not frappe.db.exists("Warehouse", warehouse_name):
		frappe.throw(_("Invalid warehouse mapping: {0}").format(warehouse_name))

	if _contains_blocked_warehouse_term(warehouse_name):
		frappe.throw(_("Warehouse is blocked for employee transfer routing: {0}").format(warehouse_name))

	warehouse_doc = frappe.get_doc("Warehouse", warehouse_name)
	warehouse_company = (getattr(warehouse_doc, "company", None) or "").strip()
	if warehouse_company and warehouse_company != BEI_COMPANY_NAME:
		frappe.throw(
			_("Warehouse company mismatch. Expected {0}, got {1}").format(BEI_COMPANY_NAME, warehouse_company)
		)

	if cint(getattr(warehouse_doc, "is_group", 0)):
		frappe.throw(_("Warehouse cannot be a group node for transfer routing: {0}").format(warehouse_name))

	warehouse_label = (getattr(warehouse_doc, "warehouse_name", None) or warehouse_name).strip()
	if _contains_blocked_warehouse_term(warehouse_label):
		frappe.throw(_("Warehouse is blocked for employee transfer routing: {0}").format(warehouse_name))

	branch_index = _get_branch_index()
	branch_name = (getattr(warehouse_doc, "branch", None) or "").strip()
	if branch_name and not frappe.db.exists("Branch", branch_name):
		branch_name = ""

	if not branch_name:
		branch_name = _resolve_branch_from_store_warehouse(warehouse_name, branch_index=branch_index) or ""

	if not branch_name:
		frappe.throw(_("Unable to derive target branch from warehouse {0}").format(warehouse_name))

	if expected_branch:
		expected_key = _normalize_store_key(expected_branch)
		branch_key = _normalize_store_key(branch_name)
		if expected_key and branch_key and expected_key != branch_key:
			frappe.throw(
				_(
					"Target branch {0} does not match warehouse {1} (derived branch: {2})"
				).format(expected_branch, warehouse_name, branch_name)
			)

	return {
		"warehouse": warehouse_name,
		"branch": branch_name,
		"company": warehouse_company or BEI_COMPANY_NAME,
		"warehouse_label": warehouse_label,
	}


def _list_transfer_store_warehouse_options(search_text: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
	branch_index = _get_branch_index()
	search_lower = (search_text or "").strip().lower()
	limit = max(1, min(500, cint(limit) or 100))

	filters: dict[str, Any] = {}
	warehouse_meta = frappe.get_meta("Warehouse")
	fields = ["name"]
	for field in ("warehouse_name", "company", "is_group", "disabled", "branch"):
		if warehouse_meta.has_field(field):
			fields.append(field)

	if warehouse_meta.has_field("is_group"):
		filters["is_group"] = 0
	if warehouse_meta.has_field("disabled"):
		filters["disabled"] = 0
	if warehouse_meta.has_field("company"):
		filters["company"] = BEI_COMPANY_NAME

	rows = frappe.get_all(
		"Warehouse",
		filters=filters,
		fields=fields,
		order_by="name asc",
		limit_page_length=max(limit * 5, 200),
	)

	options: list[dict[str, str]] = []
	for row in rows:
		warehouse_name = (row.get("name") or "").strip()
		warehouse_label = (row.get("warehouse_name") or warehouse_name).strip()
		if not warehouse_name:
			continue
		if _contains_blocked_warehouse_term(warehouse_name) or _contains_blocked_warehouse_term(warehouse_label):
			continue

		branch_name = (row.get("branch") or "").strip()
		if branch_name and not frappe.db.exists("Branch", branch_name):
			branch_name = ""
		if not branch_name:
			branch_name = _resolve_branch_from_store_warehouse(warehouse_name, branch_index=branch_index) or ""
		if not branch_name:
			continue

		if search_lower:
			haystack = f"{warehouse_name} {warehouse_label} {branch_name}".lower()
			if search_lower not in haystack:
				continue

		options.append(
			{
				"warehouse": warehouse_name,
				"warehouse_label": warehouse_label,
				"branch": branch_name,
				"company": (row.get("company") or BEI_COMPANY_NAME).strip(),
			}
		)

	options = options[:limit]
	leadership_defaults = _build_branch_reports_to_defaults(options)

	for option in options:
		leadership = leadership_defaults.get(option.get("branch") or "", {})
		area_manager = leadership.get("area_manager")
		store_oic = leadership.get("store_oic")
		default_reports_to = leadership.get("default_reports_to")

		option["default_reports_to"] = default_reports_to
		option["default_reports_to_name"] = (
			(area_manager or store_oic or {}).get("employee_name") if default_reports_to else None
		)
		option["default_reports_to_designation"] = (
			(area_manager or store_oic or {}).get("designation") if default_reports_to else None
		)
		option["area_manager"] = area_manager
		option["store_oic"] = store_oic

	return options


def _get_employee_bio_id(employee_id: str) -> str:
	employee = frappe.get_doc("Employee", employee_id)
	bio_id = (
		(getattr(employee, "attendance_device_id", None) or "").strip()
		or (getattr(employee, "new_attendance_device_id", None) or "").strip()
	)
	if not bio_id:
		frappe.throw(_("Employee {0} has no biometric ID assigned").format(employee_id))
	return bio_id


def _compute_transfer_device_plan(doc, bio_id: str) -> dict[str, Any]:
	"""Resolve target/remove devices for transfer routing."""
	store_key = _normalize_store_key(doc.store_warehouse or doc.to_branch)
	if not store_key:
		frappe.throw(_("Unable to resolve target store mapping for transfer sync"))

	device_pairs = list(DEVICE_TO_STORE.items())
	is_reliever = bool(cint(getattr(doc, "is_reliever", 0)))
	if is_roving(bio_id):
		target_devices = sorted({sn for sn, _ in device_pairs})
		return {
			"target_devices": target_devices,
			"remove_devices": [],
			"is_roving": True,
			"is_reliever": is_reliever,
			"target_store_key": store_key,
			"source_store_key": _normalize_store_key(doc.from_branch),
		}

	target_devices = [sn for sn, store_name in device_pairs if _normalize_store_key(store_name) == store_key]
	if not target_devices:
		frappe.throw(
			_("No biometric devices mapped for target store warehouse {0}").format(doc.store_warehouse or doc.to_branch)
		)

	if is_reliever:
		return {
			"target_devices": sorted(set(target_devices)),
			"remove_devices": [],
			"is_roving": False,
			"is_reliever": True,
			"target_store_key": store_key,
			"source_store_key": _normalize_store_key(doc.from_branch),
		}

	source_key = _normalize_store_key(doc.from_branch)
	remove_devices = []
	if source_key and source_key != store_key:
		remove_devices = [
			sn
			for sn, store_name in device_pairs
			if _normalize_store_key(store_name) == source_key and sn not in target_devices
		]

	return {
		"target_devices": sorted(set(target_devices)),
		"remove_devices": sorted(set(remove_devices)),
		"is_roving": False,
		"is_reliever": False,
		"target_store_key": store_key,
		"source_store_key": source_key,
	}


def _get_adms_config() -> dict[str, Any]:
	base_url = (
		(frappe.conf.get("adms_base_url") if getattr(frappe, "conf", None) else None)
		or os.environ.get("ADMS_BASE_URL")
		or "http://localhost:8080"
	)
	token = (
		(frappe.conf.get("adms_admin_token") if getattr(frappe, "conf", None) else None)
		or os.environ.get("ADMS_ADMIN_TOKEN")
	)
	timeout_seconds = cint(
		(frappe.conf.get("adms_request_timeout_seconds") if getattr(frappe, "conf", None) else None)
		or os.environ.get("ADMS_REQUEST_TIMEOUT_SECONDS")
		or 15
	)
	stale_timeout_minutes = cint(
		(frappe.conf.get("adms_sync_stale_timeout_minutes") if getattr(frappe, "conf", None) else None)
		or os.environ.get("ADMS_SYNC_STALE_TIMEOUT_MINUTES")
		or 30
	)

	return {
		"base_url": (base_url or "").rstrip("/"),
		"token": token,
		"timeout_seconds": max(5, timeout_seconds),
		"stale_timeout_minutes": max(5, stale_timeout_minutes),
	}


def _require_adms_config(config: dict[str, Any]):
	if not config.get("base_url"):
		frappe.throw(_("ADMS base URL is not configured"))
	if not config.get("token"):
		frappe.throw(_("ADMS admin token is not configured"))


def _queue_adms_command(device_sn: str, command_text: str, config: dict[str, Any]) -> dict[str, Any]:
	url = f"{config['base_url']}/admin/device/{device_sn}/commands"
	try:
		response = requests.post(
			url,
			headers={"X-Admin-Token": config["token"], "Content-Type": "application/json"},
			json={"command_text": command_text},
			timeout=config["timeout_seconds"],
		)
		if response.status_code >= 400:
			return {
				"success": False,
				"error": f"HTTP {response.status_code}: {(response.text or '')[:240]}",
			}
		payload = response.json() if response.text else {}
		return {
			"success": True,
			"command_id": payload.get("id"),
			"status": payload.get("status") or ADMS_STATUS_PENDING,
		}
	except Exception as exc:
		return {"success": False, "error": str(exc)}


def _fetch_adms_commands(device_sn: str, config: dict[str, Any], limit: int = 200) -> dict[str, Any]:
	url = f"{config['base_url']}/admin/device/{device_sn}/commands?limit={int(limit)}"
	try:
		response = requests.get(
			url,
			headers={"X-Admin-Token": config["token"]},
			timeout=config["timeout_seconds"],
		)
		if response.status_code >= 400:
			return {"success": False, "error": f"HTTP {response.status_code}: {(response.text or '')[:240]}"}
		payload = response.json() if response.text else {}
		return {"success": True, "rows": payload.get("rows") or []}
	except Exception as exc:
		return {"success": False, "error": str(exc)}


def _coerce_datetime(value: Any):
	if not value:
		return None
	try:
		return get_datetime(value)
	except Exception:
		return None


def _build_update_command(bio_id: str, employee_name: str) -> str:
	return f"DATA UPDATE USERINFO PIN={bio_id}\tName={employee_name}\tPri=0"


def _build_delete_command(bio_id: str) -> str:
	return f"DATA DELETE USERINFO PIN={bio_id}"


def _upsert_command_row(
	doc,
	device_sn: str,
	command_type: str,
	command_text: str,
	*,
	status: str,
	is_required: int,
	adms_command_id: int | None = None,
	last_error: str | None = None,
	increment_attempt: bool = False,
):
	if not frappe.db.exists("DocType", DOCTYPE_TRANSFER_DEVICE_COMMAND):
		frappe.throw(_("DocType BEI Transfer Device Command is not installed"))

	existing_name = frappe.db.get_value(
		DOCTYPE_TRANSFER_DEVICE_COMMAND,
		{"transfer_request": doc.name, "device_sn": device_sn, "command_type": command_type},
		"name",
		order_by="creation desc",
	)

	if existing_name:
		cmd = frappe.get_doc(DOCTYPE_TRANSFER_DEVICE_COMMAND, existing_name)
	else:
		cmd = frappe.new_doc(DOCTYPE_TRANSFER_DEVICE_COMMAND)
		cmd.transfer_request = doc.name
		cmd.device_sn = device_sn
		cmd.command_type = command_type

	cmd.command_text = command_text
	cmd.is_required = cint(is_required)
	cmd.status = status
	cmd.last_error = last_error
	if adms_command_id is not None:
		cmd.adms_command_id = adms_command_id

	if increment_attempt:
		cmd.attempts = cint(cmd.attempts) + 1

	if status in (ADMS_STATUS_SENT, ADMS_STATUS_ACKED):
		if not cmd.sent_at:
			cmd.sent_at = now_datetime()
	if status == ADMS_STATUS_ACKED:
		cmd.acked_at = now_datetime()
	if status == ADMS_STATUS_FAILED and not cmd.acked_at:
		cmd.acked_at = now_datetime()

	cmd.last_polled_at = now_datetime()

	if cmd.is_new():
		cmd.insert(ignore_permissions=True)
	else:
		cmd.save(ignore_permissions=True)

	return cmd


def _get_command_rows(transfer_request_name: str, statuses: list[str] | None = None) -> list[dict]:
	filters = {"transfer_request": transfer_request_name}
	if statuses:
		filters["status"] = ["in", statuses]

	return frappe.get_all(
		DOCTYPE_TRANSFER_DEVICE_COMMAND,
		filters=filters,
		fields=[
			"name",
			"device_sn",
			"command_type",
			"adms_command_id",
			"status",
			"attempts",
			"last_error",
			"sent_at",
			"acked_at",
			"is_required",
			"creation",
		],
		order_by="creation asc",
	)


def _summarize_command_statuses(transfer_request_name: str) -> dict[str, int]:
	rows = _get_command_rows(transfer_request_name)
	summary = {
		ADMS_STATUS_PENDING: 0,
		ADMS_STATUS_SENT: 0,
		ADMS_STATUS_ACKED: 0,
		ADMS_STATUS_FAILED: 0,
		"total": len(rows),
	}
	for row in rows:
		status = (row.get("status") or "").upper()
		if status in summary:
			summary[status] += 1
	return summary


def _refresh_reliever_cleanup_status(doc) -> bool:
	if not cint(getattr(doc, "is_reliever", 0)):
		return False

	rows = _get_command_rows(doc.name)
	cleanup_rows = [row for row in rows if row.get("command_type") == RELIEVER_CLEANUP_COMMAND_TYPE]
	if not cleanup_rows:
		return False

	statuses = {(row.get("status") or "").upper() for row in cleanup_rows}
	current_status = (getattr(doc, "reliever_cleanup_status", None) or "").strip()
	if statuses == {ADMS_STATUS_ACKED}:
		next_status = "Completed"
	elif ADMS_STATUS_PENDING in statuses or ADMS_STATUS_SENT in statuses:
		next_status = "Queued"
	elif ADMS_STATUS_FAILED in statuses:
		next_status = "Failed"
	else:
		next_status = current_status or "Pending"

	if next_status != current_status:
		doc.reliever_cleanup_status = next_status
		doc.save(ignore_permissions=True)
		return True
	return False


def _refresh_transfer_stage_from_commands(doc):
	reliever_cleanup_changed = _refresh_reliever_cleanup_status(doc)
	rows = _get_command_rows(doc.name)
	if not rows:
		return reliever_cleanup_changed

	required_rows = [r for r in rows if cint(r.get("is_required"))]
	if not required_rows:
		required_rows = rows

	statuses = {r.get("status") for r in required_rows}
	has_pending = ADMS_STATUS_PENDING in statuses or ADMS_STATUS_SENT in statuses
	has_failed = ADMS_STATUS_FAILED in statuses
	all_acked = statuses == {ADMS_STATUS_ACKED}

	stage_before = doc.current_stage
	if all_acked:
		_set_stage(doc, STAGE_SYNCED, status="Approved")
	elif has_pending:
		_set_stage(doc, STAGE_SYNC_IN_PROGRESS, status="Pending")
	elif has_failed:
		_set_stage(doc, STAGE_SYNC_FAILED, status="Rejected")
	else:
		return reliever_cleanup_changed

	if doc.current_stage != stage_before:
		doc.save(ignore_permissions=True)
		_append_timeline_comment(
			doc,
			_("Transfer sync stage updated: {0} -> {1}").format(stage_before, doc.current_stage),
		)
		_notify_transfer_event(doc, "Transfer Sync Stage Updated", details=f"{stage_before} -> {doc.current_stage}")
		return True
	return reliever_cleanup_changed


def _sync_command_statuses_from_adms(doc, config: dict[str, Any]) -> dict[str, Any]:
	poll_rows = _get_command_rows(doc.name, [ADMS_STATUS_PENDING, ADMS_STATUS_SENT, ADMS_STATUS_FAILED])
	if not poll_rows:
		return {"updated": 0, "errors": []}

	updated = 0
	errors: list[dict[str, str]] = []
	stale_cutoff = add_to_date(now_datetime(), minutes=-cint(config["stale_timeout_minutes"]))

	rows_by_device: dict[str, list[dict]] = {}
	for row in poll_rows:
		rows_by_device.setdefault(row.get("device_sn"), []).append(row)

	for device_sn, rows in rows_by_device.items():
		adms_result = _fetch_adms_commands(device_sn, config=config, limit=200)
		if not adms_result.get("success"):
			errors.append({"device_sn": device_sn, "error": adms_result.get("error") or "Unknown ADMS error"})
			continue

		remote_by_id = {
			cint(remote.get("id")): remote
			for remote in (adms_result.get("rows") or [])
			if remote.get("id") is not None
		}

		for row in rows:
			cmd_doc = frappe.get_doc(DOCTYPE_TRANSFER_DEVICE_COMMAND, row["name"])
			remote = remote_by_id.get(cint(cmd_doc.adms_command_id))
			if remote:
				remote_status = (remote.get("status") or "").upper()
				if remote_status in {ADMS_STATUS_PENDING, ADMS_STATUS_SENT, ADMS_STATUS_ACKED, ADMS_STATUS_FAILED}:
					cmd_doc.status = remote_status
				cmd_doc.last_error = remote.get("last_error")
				cmd_doc.sent_at = _coerce_datetime(remote.get("sent_at")) or cmd_doc.sent_at
				cmd_doc.acked_at = _coerce_datetime(remote.get("acked_at")) or cmd_doc.acked_at

			if cmd_doc.status in {ADMS_STATUS_PENDING, ADMS_STATUS_SENT}:
				sent_dt = _coerce_datetime(cmd_doc.sent_at) or _coerce_datetime(cmd_doc.creation)
				if sent_dt and sent_dt <= stale_cutoff:
					cmd_doc.status = ADMS_STATUS_FAILED
					cmd_doc.last_error = cmd_doc.last_error or "timeout_waiting_for_device_callback"
					cmd_doc.acked_at = now_datetime()

			cmd_doc.last_polled_at = now_datetime()
			cmd_doc.save(ignore_permissions=True)
			updated += 1

	return {"updated": updated, "errors": errors}


def _dispatch_transfer_sync(doc, *, force_retry_failed: bool = False, remarks: str | None = None) -> dict[str, Any]:
	_require_store_warehouse_mapping(doc)
	_enforce_effective_date_dispatch_guard(doc)

	config = _get_adms_config()
	_require_adms_config(config)

	bio_id = _get_employee_bio_id(doc.employee)
	employee_name = doc.employee_name or doc.employee
	validate_employee_bio_id(bio_id)

	plan = _compute_transfer_device_plan(doc, bio_id=bio_id)
	target_devices = plan["target_devices"]
	remove_devices = plan["remove_devices"]
	all_devices = sorted(set(target_devices + remove_devices))

	_, invalid_devices = validate_device_batch(all_devices)
	if invalid_devices:
		frappe.throw(_("Invalid device mapping: {0}").format(", ".join(invalid_devices)))

	preflight = preflight_check_enrollment(
		[(sn, bio_id, employee_name) for sn in target_devices],
		check_store_match=False,
	)
	if not preflight.get("can_proceed"):
		frappe.throw(
			_("ADMS preflight failed: {0}").format(preflight.get("error_message") or "Unknown validation error")
		)

	dispatch_plan = []
	for sn in target_devices:
		dispatch_plan.append(
			{
				"device_sn": sn,
				"command_type": "UPDATE_USERINFO",
				"command_text": _build_update_command(bio_id, employee_name),
				"is_required": 1,
			}
		)
	for sn in remove_devices:
		dispatch_plan.append(
			{
				"device_sn": sn,
				"command_type": "DELETE_USERINFO",
				"command_text": _build_delete_command(bio_id),
				"is_required": 0,
			}
		)

	queued = 0
	failed = 0
	skipped = 0
	already_active = 0
	errors: list[dict[str, str]] = []

	for cmd in dispatch_plan:
		existing_name = frappe.db.get_value(
			DOCTYPE_TRANSFER_DEVICE_COMMAND,
			{
				"transfer_request": doc.name,
				"device_sn": cmd["device_sn"],
				"command_type": cmd["command_type"],
			},
			"name",
			order_by="creation desc",
		)
		if existing_name:
			existing = frappe.get_doc(DOCTYPE_TRANSFER_DEVICE_COMMAND, existing_name)
			if existing.status == ADMS_STATUS_ACKED:
				skipped += 1
				continue
			if existing.status in {ADMS_STATUS_PENDING, ADMS_STATUS_SENT}:
				already_active += 1
				continue
			if existing.status == ADMS_STATUS_FAILED and not force_retry_failed:
				skipped += 1
				continue

		result = _queue_adms_command(cmd["device_sn"], cmd["command_text"], config=config)
		if result.get("success"):
			_upsert_command_row(
				doc,
				cmd["device_sn"],
				cmd["command_type"],
				cmd["command_text"],
				status=(result.get("status") or ADMS_STATUS_PENDING),
				is_required=cmd["is_required"],
				adms_command_id=cint(result.get("command_id")) if result.get("command_id") else None,
				increment_attempt=True,
				last_error=None,
			)
			queued += 1
		else:
			error_text = result.get("error") or "Failed to queue ADMS command"
			_upsert_command_row(
				doc,
				cmd["device_sn"],
				cmd["command_type"],
				cmd["command_text"],
				status=ADMS_STATUS_FAILED,
				is_required=cmd["is_required"],
				increment_attempt=True,
				last_error=error_text,
			)
			failed += 1
			errors.append({"device_sn": cmd["device_sn"], "error": error_text})

	stage_before = doc.current_stage
	if queued > 0 or already_active > 0:
		_set_stage(doc, STAGE_SYNC_IN_PROGRESS, status="Pending")
	elif failed > 0:
		_set_stage(doc, STAGE_SYNC_FAILED, status="Rejected")
	else:
		_refresh_transfer_stage_from_commands(doc)

	doc.sync_batch_id = f"tr-sync-{now_datetime().strftime('%Y%m%d%H%M%S')}"
	doc.save(ignore_permissions=True)

	log_text = _(
		"Transfer sync dispatch executed. queued={0}, failed={1}, skipped={2}, active={3}"
	).format(queued, failed, skipped, already_active)
	if remarks:
		log_text += _(". Notes: {0}").format(remarks)
	_append_timeline_comment(doc, log_text)
	_notify_transfer_event(doc, "Transfer Sync Dispatch", details=log_text)

	return {
		"success": True,
		"name": doc.name,
		"from_stage": stage_before,
		"to_stage": doc.current_stage,
		"queued": queued,
		"failed": failed,
		"skipped": skipped,
		"already_active": already_active,
		"errors": errors,
		"device_plan": {
			"target_devices": target_devices,
			"remove_devices": remove_devices,
			"is_roving": plan["is_roving"],
			"is_reliever": plan.get("is_reliever"),
		},
	}


@frappe.whitelist()
def get_transfer_sync_config_status():
	"""AUDIT-5 runtime check: confirms ADMS config is present."""
	_require_any_role(READ_ALL_ROLES, "You do not have permission to view transfer sync configuration")
	config = _get_adms_config()
	return {
		"base_url": config.get("base_url"),
		"has_base_url": bool(config.get("base_url")),
		"has_admin_token": bool(config.get("token")),
		"request_timeout_seconds": config.get("timeout_seconds"),
		"stale_timeout_minutes": config.get("stale_timeout_minutes"),
	}


@frappe.whitelist()
def audit_transfer_store_mappings(pilot_warehouses=None):
	"""AUDIT-2 utility: verify warehouse/device mapping coverage for pilot stores."""
	_require_any_role(READ_ALL_ROLES, "You do not have permission to audit transfer mappings")

	targets: list[str] = []
	if pilot_warehouses:
		if isinstance(pilot_warehouses, str):
			for part in re.split(r"[\n,]+", pilot_warehouses):
				if part and part.strip():
					targets.append(part.strip())
		elif isinstance(pilot_warehouses, (list, tuple)):
			targets = [str(v).strip() for v in pilot_warehouses if str(v).strip()]

	if not targets:
		targets = sorted(
			{
				store_name
				for store_name in DEVICE_TO_STORE.values()
				if store_name and str(store_name).strip()
			}
		)

	rows = []
	missing_warehouse = []
	missing_device_mapping = []
	for target in targets:
		store_key = _normalize_store_key(target)
		warehouse_exists = bool(frappe.db.exists("Warehouse", target))
		devices = [
			sn
			for sn, store_name in DEVICE_TO_STORE.items()
			if _normalize_store_key(store_name) == store_key
		]
		has_devices = len(devices) > 0

		if not warehouse_exists:
			missing_warehouse.append(target)
		if not has_devices:
			missing_device_mapping.append(target)

		rows.append(
			{
				"store_warehouse": target,
				"normalized_key": store_key,
				"warehouse_exists": warehouse_exists,
				"device_count": len(devices),
				"device_sn_list": devices,
				"status": "ok" if warehouse_exists and has_devices else "blocked",
			}
		)

	return {
		"total": len(rows),
		"ok": len([row for row in rows if row["status"] == "ok"]),
		"blocked": len([row for row in rows if row["status"] == "blocked"]),
		"missing_warehouse": sorted(set(missing_warehouse)),
		"missing_device_mapping": sorted(set(missing_device_mapping)),
		"rows": rows,
	}

@frappe.whitelist()
@rate_limit(limit=20, seconds=60)
def create_transfer_request(
	employee,
	effective_date,
	reason,
	to_branch=None,
	to_department=None,
	to_designation=None,
	to_reports_to=None,
	store_warehouse=None,
	is_reliever=0,
	reliever_days=None,
):
	_require_any_role(REQUESTER_ROLES, "You do not have permission to create transfer requests")

	if not all([employee, effective_date, reason, store_warehouse]):
		frappe.throw(_("Required fields: employee, effective_date, reason, store_warehouse"))
	if not frappe.db.exists("Employee", employee):
		frappe.throw(_("Employee not found"), frappe.DoesNotExistError)
	to_department = _normalize_optional_value(to_department)
	to_designation = _normalize_optional_value(to_designation)
	to_reports_to = _normalize_optional_value(to_reports_to)
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Reason is required"))
	reliever_flag = _coerce_bool(is_reliever)
	reliever_days_value = _coerce_positive_int(reliever_days, field_label="Reliever days")
	_enforce_org_change_field_guard(to_department=to_department, to_designation=to_designation)

	if reliever_flag and not reliever_days_value:
		frappe.throw(_("Reliever days is required when reliever mode is enabled"))
	if not reliever_flag:
		reliever_days_value = None

	reliever_start_date, reliever_end_date = _compute_reliever_window(effective_date, reliever_days_value)

	warehouse_meta = _validate_store_warehouse_for_transfer(
		store_warehouse,
		expected_branch=to_branch,
	)
	to_branch = to_branch or warehouse_meta["branch"]

	employee_doc = frappe.get_doc("Employee", employee)
	doc = frappe.get_doc(
		{
			"doctype": DOCTYPE_TRANSFER_REQUEST,
			"employee": employee,
			"requested_by": frappe.session.user,
			"requested_on": now_datetime(),
			"effective_date": getdate(effective_date),
			"reason": reason,
			"from_branch": employee_doc.branch,
			"to_branch": to_branch,
			"from_department": employee_doc.department,
			"to_department": to_department,
			"from_designation": employee_doc.designation,
			"to_designation": to_designation,
			"from_reports_to": employee_doc.reports_to,
			"to_reports_to": to_reports_to,
			"store_warehouse": store_warehouse,
			"is_reliever": reliever_flag,
			"reliever_days": reliever_days_value,
			"reliever_start_date": reliever_start_date,
			"reliever_end_date": reliever_end_date,
			"reliever_cleanup_status": "Pending" if reliever_flag else None,
			"current_stage": STAGE_PENDING_AREA,
			"stage_status": "Pending",
		}
	).insert(ignore_permissions=True)

	_append_timeline_comment(doc, _("Transfer request submitted by {0}").format(frappe.session.user))
	_notify_transfer_event(doc, "Transfer Request Submitted")

	return {
		"success": True,
		"name": doc.name,
		"current_stage": doc.current_stage,
	}


@frappe.whitelist()
def get_transfer_form_options(search_text=None, limit=100):
	"""Return filtered BEI store-warehouse options + branch leadership defaults for transfer forms."""
	_require_any_role(TRANSFER_READ_ROLES, "You do not have permission to view transfer form options")
	options = _list_transfer_store_warehouse_options(search_text=search_text, limit=limit)
	return {
		"warehouses": options,
		"total": len(options),
	}


def _pending_stages_for_user() -> list[str]:
	stages = []
	if _has_any_role(AREA_APPROVER_ROLES):
		stages.append(STAGE_PENDING_AREA)
	if _has_any_role(HR_APPROVER_ROLES):
		stages.extend([STAGE_PENDING_HR, STAGE_WAITING_EFFECTIVE])
	if _has_any_role(IT_APPROVER_ROLES):
		stages.append(STAGE_PENDING_IT)
	return stages


@frappe.whitelist()
def list_transfer_requests(current_stage=None, employee=None, my_requests=0, pending_for_me=0, page=1, page_size=20):
	_require_any_role(
		REQUESTER_ROLES.union(AREA_APPROVER_ROLES).union(HR_APPROVER_ROLES).union(IT_APPROVER_ROLES),
		"You do not have permission to view transfer requests",
	)

	page = max(1, cint(page) or 1)
	page_size = min(100, max(1, cint(page_size) or 20))
	filters = {}

	if current_stage:
		filters["current_stage"] = current_stage
	if employee:
		filters["employee"] = employee
	if cint(my_requests):
		filters["requested_by"] = frappe.session.user

	if cint(pending_for_me):
		pending_stages = _pending_stages_for_user()
		if not pending_stages:
			return {"data": [], "total": 0, "page": page, "page_size": page_size}
		filters["current_stage"] = ["in", pending_stages]
	elif not _has_any_role(READ_ALL_ROLES):
		filters["requested_by"] = frappe.session.user

	total = frappe.db.count(DOCTYPE_TRANSFER_REQUEST, filters=filters)
	data = frappe.get_all(
		DOCTYPE_TRANSFER_REQUEST,
		filters=filters,
		fields=[
			"name",
			"employee",
			"employee_name",
			"requested_by",
			"requested_on",
			"effective_date",
			"from_branch",
			"to_branch",
			"store_warehouse",
			"is_reliever",
			"reliever_days",
			"reliever_end_date",
			"reliever_cleanup_status",
			"current_stage",
			"stage_status",
			"employee_transfer_ref",
			"last_action_by",
			"last_action_at",
		],
		order_by="creation desc",
		start=(page - 1) * page_size,
		page_length=page_size,
	)

	return {"data": data, "total": total, "page": page, "page_size": page_size}


@frappe.whitelist()
def get_transfer_request_detail(transfer_request_name):
	if not frappe.db.exists(DOCTYPE_TRANSFER_REQUEST, transfer_request_name):
		frappe.throw(_("Transfer request not found"), frappe.DoesNotExistError)

	doc = frappe.get_doc(DOCTYPE_TRANSFER_REQUEST, transfer_request_name)
	can_view = doc.requested_by == frappe.session.user or _has_any_role(READ_ALL_ROLES)
	if not can_view:
		frappe.throw(_("You do not have permission to view this transfer request"), frappe.PermissionError)

	return _serialize_request(doc, include_comments=True)


@frappe.whitelist()
@rate_limit(limit=30, seconds=60)
def approve_transfer_stage(
	transfer_request_name,
	remarks=None,
	allow_emergency_override=0,
	emergency_override_reason=None,
	hr_override_user=None,
):
	if not frappe.db.exists(DOCTYPE_TRANSFER_REQUEST, transfer_request_name):
		frappe.throw(_("Transfer request not found"), frappe.DoesNotExistError)

	doc = frappe.get_doc(DOCTYPE_TRANSFER_REQUEST, transfer_request_name)
	if doc.current_stage in IMMUTABLE_STAGES:
		frappe.throw(_("Transfer request is already in an immutable stage"))
	if doc.current_stage in NON_APPROVABLE_STAGES:
		frappe.throw(_("Current stage does not support approval transitions"))

	stage_before = doc.current_stage
	_require_stage_approver(stage_before)
	_require_store_warehouse_mapping(doc)

	if stage_before == STAGE_PENDING_AREA:
		_set_stage(doc, STAGE_PENDING_HR, status="Pending")
	elif stage_before == STAGE_PENDING_HR:
		is_due_now = getdate(doc.effective_date) <= getdate(nowdate())
		_ensure_employee_transfer(doc, submit_now=is_due_now)
		_set_stage(doc, STAGE_PENDING_IT if is_due_now else STAGE_WAITING_EFFECTIVE, status="Pending")
	elif stage_before == STAGE_WAITING_EFFECTIVE:
		if getdate(doc.effective_date) > getdate(nowdate()):
			frappe.throw(_("Cannot advance before effective date"))
		_ensure_employee_transfer(doc, submit_now=True)
		_set_stage(doc, STAGE_PENDING_IT, status="Pending")
	elif stage_before == STAGE_PENDING_IT:
		_enforce_effective_date_dispatch_guard(
			doc,
			allow_emergency_override=allow_emergency_override,
			emergency_override_reason=emergency_override_reason,
			hr_override_user=hr_override_user,
		)
		_set_stage(doc, STAGE_READY_SYNC, status="Approved")
	else:
		frappe.throw(_("Unsupported stage transition from {0}").format(stage_before))

	doc.save(ignore_permissions=True)

	log_text = _("Approved stage transition: {0} -> {1}").format(stage_before, doc.current_stage)
	if remarks:
		log_text += _(". Notes: {0}").format(remarks)
	_append_timeline_comment(doc, log_text)
	_notify_transfer_event(doc, "Transfer Stage Approved", details=f"{stage_before} -> {doc.current_stage}")

	auto_dispatch_result = None
	if doc.current_stage == STAGE_READY_SYNC:
		try:
			auto_dispatch_result = _dispatch_transfer_sync(
				doc,
				force_retry_failed=False,
				remarks="Auto-dispatch after IT approval",
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Transfer Auto Dispatch Failure")

	return {
		"success": True,
		"name": doc.name,
		"from_stage": stage_before,
		"to_stage": doc.current_stage,
		"auto_dispatch": auto_dispatch_result,
	}


@frappe.whitelist()
@rate_limit(limit=30, seconds=60)
def reject_transfer_stage(transfer_request_name, reason):
	if not reason:
		frappe.throw(_("Rejection reason is required"))
	if not frappe.db.exists(DOCTYPE_TRANSFER_REQUEST, transfer_request_name):
		frappe.throw(_("Transfer request not found"), frappe.DoesNotExistError)

	doc = frappe.get_doc(DOCTYPE_TRANSFER_REQUEST, transfer_request_name)
	if doc.current_stage in IMMUTABLE_STAGES:
		frappe.throw(_("Transfer request is already in an immutable stage"))
	if doc.current_stage in {STAGE_SYNC_IN_PROGRESS, STAGE_SYNCED}:
		frappe.throw(_("Cannot reject transfer while sync is in progress or completed"))

	_require_stage_approver(doc.current_stage)
	stage_before = doc.current_stage

	_set_stage(doc, STAGE_REJECTED, status="Rejected")
	doc.rejection_reason = reason
	doc.save(ignore_permissions=True)
	_append_timeline_comment(
		doc,
		_("Rejected at stage {0}. Reason: {1}").format(stage_before, reason),
	)
	_notify_transfer_event(doc, "Transfer Stage Rejected", details=f"{stage_before}. Reason: {reason}")

	return {"success": True, "name": doc.name, "current_stage": doc.current_stage}


@frappe.whitelist()
@rate_limit(limit=20, seconds=60)
def cancel_transfer_request(transfer_request_name, reason=None):
	if not frappe.db.exists(DOCTYPE_TRANSFER_REQUEST, transfer_request_name):
		frappe.throw(_("Transfer request not found"), frappe.DoesNotExistError)

	doc = frappe.get_doc(DOCTYPE_TRANSFER_REQUEST, transfer_request_name)
	if doc.current_stage in IMMUTABLE_STAGES.union({STAGE_SYNC_IN_PROGRESS, STAGE_SYNCED}):
		frappe.throw(_("Transfer request cannot be cancelled in its current stage"))

	is_owner = doc.requested_by == frappe.session.user
	if not is_owner:
		_require_any_role(READ_ALL_ROLES, "You do not have permission to cancel this transfer request")
	elif doc.current_stage != STAGE_PENDING_AREA:
		frappe.throw(_("Requesters can only cancel while pending area approval"))

	stage_before = doc.current_stage
	_set_stage(doc, STAGE_CANCELLED, status="Rejected")
	doc.save(ignore_permissions=True)
	_append_timeline_comment(
		doc,
		_("Cancelled request from stage {0}. Reason: {1}").format(stage_before, reason or "-"),
	)
	_notify_transfer_event(doc, "Transfer Request Cancelled", details=f"{stage_before}. Reason: {reason or '-'}")

	return {"success": True, "name": doc.name, "current_stage": doc.current_stage}


@frappe.whitelist()
@rate_limit(limit=20, seconds=60)
def dispatch_transfer_sync(transfer_request_name, force_retry_failed=0, remarks=None):
	if not frappe.db.exists(DOCTYPE_TRANSFER_REQUEST, transfer_request_name):
		frappe.throw(_("Transfer request not found"), frappe.DoesNotExistError)

	if frappe.session.user != "Administrator":
		_require_any_role(IT_APPROVER_ROLES, "You do not have permission to dispatch transfer sync")

	doc = frappe.get_doc(DOCTYPE_TRANSFER_REQUEST, transfer_request_name)
	if doc.current_stage not in {STAGE_READY_SYNC, STAGE_SYNC_IN_PROGRESS, STAGE_SYNC_FAILED}:
		frappe.throw(_("Transfer is not ready for sync dispatch"))

	return _dispatch_transfer_sync(
		doc,
		force_retry_failed=bool(cint(force_retry_failed)),
		remarks=remarks,
	)


@frappe.whitelist()
@rate_limit(limit=20, seconds=60)
def retry_transfer_sync(transfer_request_name, remarks=None):
	if not frappe.db.exists(DOCTYPE_TRANSFER_REQUEST, transfer_request_name):
		frappe.throw(_("Transfer request not found"), frappe.DoesNotExistError)

	_require_any_role(IT_APPROVER_ROLES, "You do not have permission to retry transfer sync")

	doc = frappe.get_doc(DOCTYPE_TRANSFER_REQUEST, transfer_request_name)
	if doc.current_stage not in {STAGE_SYNC_FAILED, STAGE_SYNC_IN_PROGRESS, STAGE_READY_SYNC}:
		frappe.throw(_("Transfer is not in a retryable sync stage"))

	return _dispatch_transfer_sync(doc, force_retry_failed=True, remarks=remarks or "Manual retry")


@frappe.whitelist()
def reconcile_transfer_sync_status(transfer_request_name=None, limit=100):
	"""Poll ADMS command rows and reconcile transfer sync stages."""
	if frappe.session.user != "Administrator":
		_require_any_role(IT_APPROVER_ROLES, "You do not have permission to reconcile transfer sync status")

	config = _get_adms_config()
	_require_adms_config(config)

	if transfer_request_name:
		if not frappe.db.exists(DOCTYPE_TRANSFER_REQUEST, transfer_request_name):
			frappe.throw(_("Transfer request not found"), frappe.DoesNotExistError)
		targets = [frappe._dict({"name": transfer_request_name})]
	else:
		targets = frappe.get_all(
			DOCTYPE_TRANSFER_REQUEST,
			filters={"current_stage": ["in", [STAGE_READY_SYNC, STAGE_SYNC_IN_PROGRESS, STAGE_SYNC_FAILED, STAGE_SYNCED]]},
			fields=["name"],
			limit=min(max(cint(limit) or 100, 1), 500),
			order_by="modified asc",
		)

	processed = 0
	stage_updates = 0
	errors: list[dict[str, str]] = []
	for row in targets:
		try:
			doc = frappe.get_doc(DOCTYPE_TRANSFER_REQUEST, row.name)
			if doc.current_stage == STAGE_READY_SYNC:
				_dispatch_transfer_sync(doc, force_retry_failed=False, remarks="Scheduler dispatch")
				processed += 1
				continue

			result = _sync_command_statuses_from_adms(doc, config=config)
			processed += 1
			if _refresh_transfer_stage_from_commands(doc):
				stage_updates += 1
			for error in result.get("errors") or []:
				errors.append({"name": row.name, "error": f"{error.get('device_sn')}: {error.get('error')}"})
		except Exception as exc:
			errors.append({"name": row.name, "error": str(exc)})
			frappe.log_error(frappe.get_traceback(), "Transfer Sync Reconciliation Failure")

	return {"processed": processed, "stage_updates": stage_updates, "errors": errors}


@frappe.whitelist()
def get_transfer_sync_dashboard(status=None, page=1, page_size=50):
	_require_any_role(READ_ALL_ROLES, "You do not have permission to view transfer sync dashboard")

	page = max(1, cint(page) or 1)
	page_size = min(200, max(1, cint(page_size) or 50))

	stage_counts = {}
	for stage in [STAGE_PENDING_IT, STAGE_READY_SYNC, STAGE_SYNC_IN_PROGRESS, STAGE_SYNCED, STAGE_SYNC_FAILED]:
		stage_counts[stage] = frappe.db.count(DOCTYPE_TRANSFER_REQUEST, filters={"current_stage": stage})

	transfer_filters = {"current_stage": ["in", [STAGE_PENDING_IT, STAGE_READY_SYNC, STAGE_SYNC_IN_PROGRESS, STAGE_SYNCED, STAGE_SYNC_FAILED]]}
	if status:
		transfer_filters["current_stage"] = status

	total = frappe.db.count(DOCTYPE_TRANSFER_REQUEST, filters=transfer_filters)
	transfers = frappe.get_all(
		DOCTYPE_TRANSFER_REQUEST,
		filters=transfer_filters,
		fields=[
			"name",
			"employee",
			"employee_name",
			"effective_date",
			"to_branch",
			"store_warehouse",
			"is_reliever",
			"reliever_end_date",
			"reliever_cleanup_status",
			"current_stage",
			"stage_status",
			"sync_batch_id",
			"last_action_at",
			"last_action_by",
		],
		order_by="modified desc",
		start=(page - 1) * page_size,
		page_length=page_size,
	)

	command_summary = {}
	if frappe.db.exists("DocType", DOCTYPE_TRANSFER_DEVICE_COMMAND):
		for transfer in transfers:
			command_summary[transfer["name"]] = _summarize_command_statuses(transfer["name"])

	return {
		"summary": stage_counts,
		"total": total,
		"page": page,
		"page_size": page_size,
		"transfers": transfers,
		"command_summary": command_summary,
	}


@frappe.whitelist()
def run_due_transfer_submissions(limit=100):
	"""Scheduler-safe bridge for future-dated transfers.

	Moves HR-approved waiting transfers to Pending IT Approval when effective_date
	is reached and ensures linked Employee Transfer is submitted.
	"""
	if frappe.session.user != "Administrator":
		_require_any_role(HR_APPROVER_ROLES, "You do not have permission to run due transfer submissions")

	due_requests = frappe.get_all(
		DOCTYPE_TRANSFER_REQUEST,
		filters={
			"current_stage": STAGE_WAITING_EFFECTIVE,
			"effective_date": ["<=", getdate(nowdate())],
		},
		fields=["name"],
		limit=min(max(cint(limit) or 100, 1), 500),
		order_by="effective_date asc",
	)

	processed = 0
	errors = []
	for row in due_requests:
		try:
			doc = frappe.get_doc(DOCTYPE_TRANSFER_REQUEST, row.name)
			_require_store_warehouse_mapping(doc)
			_ensure_employee_transfer(doc, submit_now=True)
			_set_stage(doc, STAGE_PENDING_IT, status="Pending")
			doc.save(ignore_permissions=True)
			log_text = _("Effective date reached. Moved to Pending IT Approval")
			_append_timeline_comment(doc, log_text)
			_notify_transfer_event(doc, "Transfer Effective Date Reached", details=log_text)
			processed += 1
		except Exception as exc:
			errors.append({"name": row.name, "error": str(exc)})
			frappe.log_error(
				frappe.get_traceback(),
				"Transfer Request Due Submission Failure",
			)

	return {"processed": processed, "errors": errors}


def _dispatch_reliever_cleanup(doc) -> dict[str, Any]:
	config = _get_adms_config()
	_require_adms_config(config)

	bio_id = _get_employee_bio_id(doc.employee)
	validate_employee_bio_id(bio_id)
	plan = _compute_transfer_device_plan(doc, bio_id=bio_id)
	if plan.get("is_roving"):
		doc.reliever_cleanup_status = "Skipped (Roving)"
		doc.save(ignore_permissions=True)
		return {"queued": 0, "failed": 0, "skipped": len(plan.get("target_devices") or []), "errors": []}

	cleanup_devices = sorted(set(plan.get("target_devices") or []))
	queued = 0
	failed = 0
	skipped = 0
	errors: list[dict[str, str]] = []

	for device_sn in cleanup_devices:
		result = _queue_adms_command(device_sn, _build_delete_command(bio_id), config=config)
		if result.get("success"):
			_upsert_command_row(
				doc,
				device_sn,
				RELIEVER_CLEANUP_COMMAND_TYPE,
				_build_delete_command(bio_id),
				status=(result.get("status") or ADMS_STATUS_PENDING),
				is_required=0,
				adms_command_id=cint(result.get("command_id")) if result.get("command_id") else None,
				increment_attempt=True,
				last_error=None,
			)
			queued += 1
		else:
			error_text = result.get("error") or "Failed to queue reliever cleanup command"
			_upsert_command_row(
				doc,
				device_sn,
				RELIEVER_CLEANUP_COMMAND_TYPE,
				_build_delete_command(bio_id),
				status=ADMS_STATUS_FAILED,
				is_required=0,
				increment_attempt=True,
				last_error=error_text,
			)
			failed += 1
			errors.append({"device_sn": device_sn, "error": error_text})

	if not cleanup_devices:
		skipped = 1

	doc.reliever_cleanup_status = "Failed" if failed > 0 else ("Queued" if queued > 0 else "Skipped")
	doc.save(ignore_permissions=True)

	log_text = _("Reliever cleanup dispatch executed. queued={0}, failed={1}, skipped={2}").format(
		queued,
		failed,
		skipped,
	)
	_append_timeline_comment(doc, log_text)
	_notify_transfer_event(doc, "Reliever Cleanup Dispatch", details=log_text)

	return {
		"queued": queued,
		"failed": failed,
		"skipped": skipped,
		"errors": errors,
	}


@frappe.whitelist()
def run_due_reliever_cleanup(limit=100):
	"""Scheduler helper: remove reliever from temporary store devices after reliever window ends."""
	if frappe.session.user != "Administrator":
		_require_any_role(
			IT_APPROVER_ROLES.union(HR_APPROVER_ROLES),
			"You do not have permission to run reliever cleanup",
		)

	due = frappe.get_all(
		DOCTYPE_TRANSFER_REQUEST,
		filters={
			"is_reliever": 1,
			"reliever_end_date": ["<=", getdate(nowdate())],
			"current_stage": ["in", [STAGE_SYNC_IN_PROGRESS, STAGE_SYNCED, STAGE_SYNC_FAILED]],
		},
		fields=["name"],
		limit=min(max(cint(limit) or 100, 1), 500),
		order_by="reliever_end_date asc",
	)

	processed = 0
	errors: list[dict[str, str]] = []
	for row in due:
		try:
			doc = frappe.get_doc(DOCTYPE_TRANSFER_REQUEST, row.name)
			current_cleanup_status = (getattr(doc, "reliever_cleanup_status", None) or "").strip().lower()
			if current_cleanup_status == "completed":
				continue

			_dispatch_reliever_cleanup(doc)
			processed += 1
		except Exception as exc:
			errors.append({"name": row.name, "error": str(exc)})
			frappe.log_error(frappe.get_traceback(), "Reliever Cleanup Dispatch Failure")

	return {"processed": processed, "errors": errors}


@frappe.whitelist()
def run_ready_transfer_sync(limit=100):
	"""Scheduler helper: dispatch sync for IT-approved requests."""
	if frappe.session.user != "Administrator":
		_require_any_role(IT_APPROVER_ROLES, "You do not have permission to run transfer sync dispatch")

	ready = frappe.get_all(
		DOCTYPE_TRANSFER_REQUEST,
		filters={
			"current_stage": STAGE_READY_SYNC,
			"effective_date": ["<=", getdate(nowdate())],
		},
		fields=["name"],
		limit=min(max(cint(limit) or 100, 1), 500),
		order_by="modified asc",
	)

	processed = 0
	errors = []
	for row in ready:
		try:
			doc = frappe.get_doc(DOCTYPE_TRANSFER_REQUEST, row.name)
			_dispatch_transfer_sync(doc, force_retry_failed=False, remarks="Scheduler dispatch")
			processed += 1
		except Exception as exc:
			errors.append({"name": row.name, "error": str(exc)})
			frappe.log_error(frappe.get_traceback(), "Transfer Sync Dispatch Failure")

	return {"processed": processed, "errors": errors}
