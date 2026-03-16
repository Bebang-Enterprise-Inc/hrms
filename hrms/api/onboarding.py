# Copyright (c) 2025, Bebang Enterprise Inc.
# For license information, please see license.txt

"""
BEI Onboarding API

Server-side methods used by tasks.bebang.ph to support:
- QR-based self onboarding
- Kiosk onboarding (supervisor device)
- New hire onboarding (no Employee ID yet)

Important:
- These endpoints are intended to be called server-to-server (Next.js -> Frappe)
- Do NOT expose API tokens to the browser
"""

from __future__ import annotations

import json
import secrets
from typing import Any

import frappe
from frappe.utils import now_datetime, today
from frappe.utils.data import add_to_date

from hrms.api.contact_validation import validate_email_address, validate_ph_mobile_number
from hrms.api.profile_policy import classify_employee_policy

SESSION_DOCTYPE = "BEI Onboarding Session"
REQUEST_DOCTYPE = "BEI Onboarding Request"


def _new_token() -> str:
	# 24 chars URL-safe token (short enough for QR, long enough for security)
	return secrets.token_urlsafe(18)


def _as_dict(obj: Any) -> dict[str, Any]:
	if obj is None:
		return {}
	if isinstance(obj, dict):
		return obj
	if isinstance(obj, str):
		try:
			parsed = json.loads(obj)
			return parsed if isinstance(parsed, dict) else {}
		except Exception:
			return {}
	return {}


HR_APPROVER_FALLBACK = "nad@bebang.ph,ana@bebang.ph"
ELEVATED_ONBOARDING_REVIEWER_ROLES = {
	"System Manager",
	"Administrator",
	"HR Manager",
	"HR User",
}
IDENTITY_FIELDS = {
	"first_name",
	"middle_name",
	"last_name",
	"date_of_birth",
	"gender",
	"marital_status",
}
GOVERNMENT_ID_FIELDS = {"tin_number", "sss_number", "philhealth_number", "pagibig_number"}
BANK_FIELDS = {"bank_name", "bank_ac_no"}
WORK_IDENTITY_FIELDS = {"company_email", "custom_work_phone"}
EMAIL_FIELDS = {"company_email", "personal_email"}
PHONE_FIELDS = {"cell_number", "custom_work_phone", "emergency_phone_number"}
PROOF_ATTACHMENTS = {
	"tin_proof_url": ("tin_number", "custom_tin_verified"),
	"sss_proof_url": ("sss_number", "custom_sss_verified"),
	"philhealth_proof_url": ("philhealth_number", "custom_philhealth_verified"),
	"pagibig_proof_url": ("pagibig_number", "custom_pagibig_verified"),
}
OPEN_REVIEW_STATUSES = {"Pending", "Escalated", "Revision Requested"}
ENRICHMENT_FIELD_ALIASES = {
	"emergency_contact_name": "person_to_be_contacted",
	"emergency_contact_person": "person_to_be_contacted",
	"emergency_phone": "emergency_phone_number",
	"emergency_contact_number": "emergency_phone_number",
	"emergency_relationship": "relation",
	"custom_tin": "tin_number",
	"custom_sss": "sss_number",
	"custom_philhealth": "philhealth_number",
	"custom_pagibig": "pagibig_number",
	"bank_account_number": "bank_ac_no",
	"work_phone": "custom_work_phone",
}
INPUT_TO_EMPLOYEE_FIELD_MAP = {
	"custom_nickname": "custom_nickname",
	"first_name": "first_name",
	"middle_name": "middle_name",
	"last_name": "last_name",
	"date_of_birth": "date_of_birth",
	"gender": "gender",
	"marital_status": "marital_status",
	"company_email": "company_email",
	"custom_work_phone": "custom_work_phone",
	"cell_number": "cell_number",
	"personal_email": "personal_email",
	"current_address": "current_address",
	"permanent_address": "permanent_address",
	"person_to_be_contacted": "person_to_be_contacted",
	"emergency_phone_number": "emergency_phone_number",
	"relation": "relation",
	"bank_name": "bank_name",
	"bank_ac_no": "bank_ac_no",
	"tin_number": "tin_number",
	"sss_number": "sss_number",
	"philhealth_number": "philhealth_number",
	"pagibig_number": "pagibig_number",
	"custom_uniform_size": "custom_uniform_size",
	"attachments": None,
	"selfie_file_url": None,
}


def _json_dumps(value: Any) -> str:
	return json.dumps(value, ensure_ascii=False)


def _norm_text(value: Any) -> str:
	if value is None:
		return ""
	if isinstance(value, bool):
		return "1" if value else "0"
	if isinstance(value, int | float):
		return str(value)
	return str(value).strip()


def _norm_email(value: Any) -> str:
	return _norm_text(value).lower()


def _is_elevated_onboarding_reviewer(user_id: str) -> bool:
	if not user_id:
		return False
	return bool(set(frappe.get_roles(user_id) or []).intersection(ELEVATED_ONBOARDING_REVIEWER_ROLES))


def _can_access_assigned_request(approver_email: Any, reviewer_email: str) -> bool:
	if _is_elevated_onboarding_reviewer(reviewer_email):
		return True

	allowed_reviewers = [
		_norm_email(value)
		for value in _norm_text(approver_email).replace("\n", ",").split(",")
		if _norm_email(value)
	]
	if not allowed_reviewers:
		return False

	return _norm_email(reviewer_email) in allowed_reviewers


def _normalize_field_name(field_name: str) -> str:
	return ENRICHMENT_FIELD_ALIASES.get(field_name, field_name)


def _normalize_requested_changes(changes: dict[str, Any]) -> dict[str, Any]:
	normalized: dict[str, Any] = {}

	for section_key, section_value in changes.items():
		if isinstance(section_value, dict):
			normalized_section: dict[str, Any] = {}
			for field_key, field_value in section_value.items():
				normalized_key = _normalize_field_name(str(field_key))
				normalized_section[normalized_key] = field_value
			normalized[section_key] = normalized_section
		else:
			normalized_key = _normalize_field_name(str(section_key))
			normalized[normalized_key] = section_value

	return normalized


def _extract_requested_field_keys(changes: dict[str, Any]) -> list[str]:
	flat_changes = _flatten_requested_changes(changes)
	keys = []

	for field_key, field_value in flat_changes.items():
		if field_key == "attachments":
			continue
		if _norm_text(field_value):
			keys.append(field_key)

	return sorted(set(keys))


def _validate_contact_fields(changes: dict[str, Any]) -> dict[str, Any]:
	validated = _normalize_requested_changes(changes)

	for section_value in validated.values():
		if not isinstance(section_value, dict):
			continue

		for field_key, field_value in list(section_value.items()):
			if field_key in EMAIL_FIELDS:
				result = validate_email_address(_norm_text(field_value))
				if not result["valid"]:
					frappe.throw(result["error"])
				section_value[field_key] = result["normalized"]
			elif field_key in PHONE_FIELDS:
				result = validate_ph_mobile_number(_norm_text(field_value))
				if not result["valid"]:
					frappe.throw(result["error"])
				section_value[field_key] = result["normalized"]

	return validated


def _determine_review_lane(requested_field_keys: list[str]) -> str:
	keys = set(requested_field_keys)
	if keys & IDENTITY_FIELDS:
		return "identity_demographic"
	if keys & GOVERNMENT_ID_FIELDS:
		return "government_ids"
	if keys & BANK_FIELDS:
		return "payroll_bank"
	if keys & WORK_IDENTITY_FIELDS:
		return "work_identity"
	return "non_sensitive_follow_up"


def _determine_risk_level(requested_field_keys: list[str]) -> str:
	keys = set(requested_field_keys)
	if keys & (IDENTITY_FIELDS | GOVERNMENT_ID_FIELDS | BANK_FIELDS):
		return "high"
	if keys & WORK_IDENTITY_FIELDS:
		return "medium"
	return "low"


def _requires_hr_review(requested_field_keys: list[str]) -> bool:
	keys = set(requested_field_keys)
	return bool(keys & (IDENTITY_FIELDS | GOVERNMENT_ID_FIELDS | BANK_FIELDS | WORK_IDENTITY_FIELDS))


def _determine_proof_status(changes: dict[str, Any]) -> str:
	attachments = _flatten_requested_changes(changes).get("attachments")
	if isinstance(attachments, dict) and any(_norm_text(value) for value in attachments.values()):
		return "documents_attached"
	return "not_required"


def _get_employee_snapshot(employee_row: dict[str, Any], requested_field_keys: list[str]) -> dict[str, Any]:
	snapshot: dict[str, Any] = {}
	for field_key in requested_field_keys:
		employee_field = INPUT_TO_EMPLOYEE_FIELD_MAP.get(field_key, field_key)
		if employee_field:
			snapshot[field_key] = employee_row.get(employee_field)
	return snapshot


def _get_request_meta(doc_or_row: Any) -> dict[str, Any]:
	return _as_dict(getattr(doc_or_row, "submitted_by_meta", None) or doc_or_row.get("submitted_by_meta"))


def _set_request_meta(doc: Any, meta: dict[str, Any]) -> None:
	doc.submitted_by_meta = _json_dumps(meta)


def _set_workflow_state(doc: Any, review_state: str, **extra: Any) -> dict[str, Any]:
	meta = _get_request_meta(doc)
	workflow = meta.get("workflow")
	if not isinstance(workflow, dict):
		workflow = {}
	workflow["review_state"] = review_state
	for key, value in extra.items():
		workflow[key] = value
	meta["workflow"] = workflow
	_set_request_meta(doc, meta)
	return meta


@frappe.whitelist()
def create_session(
	branch: str,
	mode: str = "self",
	verifier_email: str | None = None,
	expires_in_minutes: int = 30,
) -> dict[str, Any]:
	"""
	Create an onboarding session.

	Intended to be called by an authenticated supervisor/manager flow.
	"""
	if not branch:
		return {"success": False, "error": "Branch is required", "code": "MISSING_BRANCH"}

	mode = (mode or "self").strip().lower()
	if mode not in ("self", "kiosk", "new_hire"):
		return {"success": False, "error": "Invalid mode", "code": "INVALID_MODE"}

	token = _new_token()
	expires_at = add_to_date(now_datetime(), minutes=int(expires_in_minutes))

	doc = frappe.get_doc(
		{
			"doctype": SESSION_DOCTYPE,
			"token": token,
			"branch": branch,
			"mode": mode,
			"verifier_email": verifier_email or "",
			"created_by_user": frappe.session.user,
			"expires_at": expires_at,
			"status": "Active",
		}
	)

	try:
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return {
			"success": True,
			"data": {
				"token": token,
				"expires_at": str(expires_at),
				"branch": branch,
				"mode": mode,
			},
		}
	except Exception as e:
		frappe.log_error(title="BEI Onboarding create_session failed", message=str(e))
		return {"success": False, "error": "Failed to create session", "code": "CREATE_FAILED"}


@frappe.whitelist()
def get_session(token: str) -> dict[str, Any]:
	"""Return minimal session metadata (no PII)."""
	if not token:
		return {"success": False, "error": "Token is required", "code": "MISSING_TOKEN"}

	name = frappe.db.get_value(SESSION_DOCTYPE, {"token": token}, "name")
	if not name:
		return {"success": False, "error": "Session not found", "code": "NOT_FOUND"}

	doc = frappe.get_doc(SESSION_DOCTYPE, name)
	if doc.status != "Active":
		return {"success": False, "error": "Session not active", "code": "NOT_ACTIVE"}

	if doc.expires_at and now_datetime() > doc.expires_at:
		# best-effort mark expired
		try:
			frappe.db.set_value(SESSION_DOCTYPE, name, "status", "Expired")
			frappe.db.commit()
		except Exception:
			pass
		return {"success": False, "error": "Session expired", "code": "EXPIRED"}

	return {
		"success": True,
		"data": {
			"token": token,
			"branch": doc.branch,
			"mode": doc.mode,
			"expires_at": str(doc.expires_at) if doc.expires_at else None,
			"verifier_email": doc.verifier_email or "",
		},
	}


@frappe.whitelist()
def lookup_employee(
	token: str, biometric_id: str | None = None, employee: str | None = None
) -> dict[str, Any]:
	"""
	Lookup employee within a session context.
	Returns minimal confirmation fields only (no sensitive data).
	"""
	session = get_session(token)
	if not session.get("success"):
		return session

	if not biometric_id and not employee:
		return {"success": False, "error": "Employee identifier required", "code": "MISSING_IDENTIFIER"}

	filters = {}
	if employee:
		filters["name"] = employee
	if biometric_id:
		filters["attendance_device_id"] = biometric_id

	# NOTE: Request all fields needed for prefilling the onboarding form
	fields = [
		"name",
		"employee_name",
		"first_name",
		"middle_name",
		"last_name",
		"gender",
		"date_of_birth",
		"branch",
		"department",
		"designation",
		"reports_to",
		"cell_number",
		"personal_email",
		"current_address",
		"permanent_address",
		"person_to_be_contacted",  # Emergency contact name
		"emergency_phone_number",  # Emergency phone
		"relation",  # Emergency relationship
		"sss_number",  # Custom field
		"philhealth_number",  # Custom field
		"pagibig_number",  # Custom field
		"tin_number",  # Custom field
		"bank_name",  # If exists
		"bank_ac_no",  # Bank account number
		"image",  # Profile photo
		"attendance_device_id",  # Biometric ID
	]
	rows = frappe.get_all("Employee", filters=filters, fields=fields, limit=2)

	if not rows:
		return {"success": False, "error": "Employee not found", "code": "EMP_NOT_FOUND"}
	if len(rows) > 1:
		return {"success": False, "error": "Multiple matches found", "code": "MULTIPLE_MATCHES"}

	row = rows[0]

	# Branch scoping: by default, only allow onboarding employees for session branch
	sess_branch = session["data"].get("branch")
	if sess_branch and row.get("branch") and row["branch"] != sess_branch:
		return {"success": False, "error": "Employee not in this branch", "code": "BRANCH_MISMATCH"}

	return {
		"success": True,
		"data": {
			"name": row.get("name"),
			"employee_name": row.get("employee_name"),
			"first_name": row.get("first_name"),
			"middle_name": row.get("middle_name"),
			"last_name": row.get("last_name"),
			"gender": row.get("gender"),
			"date_of_birth": row.get("date_of_birth"),
			"branch": row.get("branch"),
			"department": row.get("department"),
			"designation": row.get("designation"),
			"reports_to": row.get("reports_to"),
			"cell_number": row.get("cell_number"),
			"personal_email": row.get("personal_email"),
			"current_address": row.get("current_address"),
			"permanent_address": row.get("permanent_address"),
			"emergency_contact_name": row.get("person_to_be_contacted"),
			"emergency_phone": row.get("emergency_phone_number"),
			"emergency_relationship": row.get("relation"),
			"sss_number": row.get("sss_number"),
			"philhealth_number": row.get("philhealth_number"),
			"pagibig_number": row.get("pagibig_number"),
			"tin_number": row.get("tin_number"),
			"bank_name": row.get("bank_name"),
			"bank_ac_no": row.get("bank_ac_no"),
			"image": row.get("image"),
			"biometric_id": row.get("attendance_device_id"),
		},
	}


@frappe.whitelist()
def submit_request(
	token: str,
	employee: str | None = None,
	request_type: str = "update_existing",
	requested_changes: str | None = None,
	submitted_by_meta: str | None = None,
	selfie_file_url: str | None = None,
	verifier_email: str | None = None,
) -> dict[str, Any]:
	"""
	Create an onboarding request.

	- For updates, pass `employee`
	- For new hires, pass request_type='new_hire' and leave employee empty
	"""
	session = get_session(token)
	if not session.get("success"):
		return session

	request_type = (request_type or "update_existing").strip().lower()
	if request_type not in ("update_existing", "new_hire"):
		return {"success": False, "error": "Invalid request_type", "code": "INVALID_REQUEST_TYPE"}

	if request_type == "update_existing" and not employee:
		return {"success": False, "error": "Employee is required", "code": "MISSING_EMPLOYEE"}

	changes = _as_dict(requested_changes)
	meta = _as_dict(submitted_by_meta)

	doc = frappe.get_doc(
		{
			"doctype": REQUEST_DOCTYPE,
			"session_token": token,
			"employee": employee or "",
			"request_type": request_type,
			"status": "Pending",
			"submitted_at": now_datetime(),
			"submitted_via": meta.get("submitted_via") or "",
			"submitted_by_meta": json.dumps(meta, ensure_ascii=False),
			"requested_changes": json.dumps(changes, ensure_ascii=False),
			"selfie_file_url": selfie_file_url or "",
			"approver_email": verifier_email or "",
		}
	)

	try:
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return {"success": True, "data": {"request": doc.name, "status": doc.status}}
	except Exception as e:
		frappe.log_error(title="BEI Onboarding submit_request failed", message=str(e))
		return {"success": False, "error": "Failed to submit request", "code": "SUBMIT_FAILED"}


def _flatten_requested_changes(changes: dict[str, Any]) -> dict[str, Any]:
	"""Flatten nested request payloads into canonical Employee field keys."""
	flat: dict[str, Any] = {}
	normalized = _normalize_requested_changes(changes)

	for key, value in normalized.items():
		normalized_key = _normalize_field_name(str(key))
		if normalized_key == "attachments" and isinstance(value, dict):
			flat["attachments"] = value
			continue
		if isinstance(value, dict):
			for nested_key, nested_value in value.items():
				flat[_normalize_field_name(str(nested_key))] = nested_value
		else:
			flat[normalized_key] = value
	return flat


def _build_enrichment_submission_meta(
	employee_row: dict[str, Any],
	requested_changes: dict[str, Any],
	submitted_via: str | None = None,
	submission_reason: str | None = None,
) -> dict[str, Any]:
	requested_field_keys = _extract_requested_field_keys(requested_changes)
	policy = classify_employee_policy(employee_row)
	snapshot = _get_employee_snapshot(employee_row, requested_field_keys)

	return {
		"submission_kind": "profile_enrichment",
		"employee_name": employee_row.get("employee_name") or "",
		"branch": employee_row.get("branch") or "",
		"designation": employee_row.get("designation") or "",
		"submitted_via": submitted_via or "BEI Tasks - Profile Update",
		"submission_reason": submission_reason or "",
		"policy": policy,
		"workflow": {
			"review_state": "Pending Review",
			"requested_field_keys": requested_field_keys,
			"current_snapshot": snapshot,
			"lane": _determine_review_lane(requested_field_keys),
			"risk_level": _determine_risk_level(requested_field_keys),
			"proof_status": _determine_proof_status(requested_changes),
			"requires_hr_review": _requires_hr_review(requested_field_keys),
			"claimed_by": "",
			"claimed_at": "",
			"supersedes_requests": [],
		},
	}


def _get_enrichment_employee_row(employee: str, requested_field_keys: list[str]) -> dict[str, Any]:
	base_fields = ["name", "employee_name", "branch", "department", "designation"]
	snapshot_fields = [
		employee_field
		for employee_field in {
			INPUT_TO_EMPLOYEE_FIELD_MAP.get(field_key, field_key) for field_key in requested_field_keys
		}
		if employee_field
	]
	employee_fields = list(dict.fromkeys([*base_fields, *snapshot_fields]))
	return (
		frappe.db.get_value(
			"Employee",
			employee,
			employee_fields,
			as_dict=True,
		)
		or {}
	)


def _get_requested_field_keys_from_request(doc_or_row: Any) -> list[str]:
	meta = _get_request_meta(doc_or_row)
	workflow = meta.get("workflow")
	if isinstance(workflow, dict) and isinstance(workflow.get("requested_field_keys"), list):
		return [str(key) for key in workflow.get("requested_field_keys", []) if str(key)]

	requested_changes = _as_dict(
		getattr(doc_or_row, "requested_changes", None) or doc_or_row.get("requested_changes")
	)
	return _extract_requested_field_keys(requested_changes)


def _get_request_claim_owner(doc_or_row: Any) -> str:
	meta = _get_request_meta(doc_or_row)
	workflow = meta.get("workflow")
	if isinstance(workflow, dict):
		return _norm_text(workflow.get("claimed_by"))
	return ""


def _check_request_stale(req: Any) -> tuple[bool, dict[str, Any]]:
	meta = _get_request_meta(req)
	workflow = meta.get("workflow")
	if not isinstance(workflow, dict):
		return False, {}

	snapshot = workflow.get("current_snapshot")
	if not isinstance(snapshot, dict):
		return False, {}

	requested_changes = _as_dict(req.requested_changes)
	flat_changes = _flatten_requested_changes(requested_changes)
	employee_doc = (
		frappe.db.get_value(
			"Employee",
			req.employee,
			list(
				{
					INPUT_TO_EMPLOYEE_FIELD_MAP.get(key, key)
					for key in snapshot.keys()
					if INPUT_TO_EMPLOYEE_FIELD_MAP.get(key, key)
				}
			),
			as_dict=True,
		)
		or {}
	)

	stale_fields = []
	for request_key, snapshot_value in snapshot.items():
		employee_field = INPUT_TO_EMPLOYEE_FIELD_MAP.get(request_key, request_key)
		current_value = employee_doc.get(employee_field)
		requested_value = flat_changes.get(request_key)
		if _norm_text(current_value) != _norm_text(snapshot_value) and _norm_text(
			current_value
		) != _norm_text(requested_value):
			stale_fields.append(
				{
					"field": request_key,
					"snapshot_value": snapshot_value,
					"current_value": current_value,
					"requested_value": requested_value,
				}
			)

	return bool(stale_fields), {"stale_fields": stale_fields}


@frappe.whitelist()
def submit_enrichment_update(
	employee: str,
	requested_changes: str | None = None,
	submitted_via: str | None = None,
	approver_email: str | None = None,
	submission_reason: str | None = None,
) -> dict[str, Any]:
	"""Create one grouped enrichment submission for profile updates."""
	if not employee:
		return {"success": False, "error": "Employee is required", "code": "MISSING_EMPLOYEE"}

	if not frappe.db.exists("Employee", employee):
		return {"success": False, "error": "Employee not found", "code": "EMP_NOT_FOUND"}

	changes = _validate_contact_fields(_as_dict(requested_changes))
	requested_field_keys = _extract_requested_field_keys(changes)
	attachments = _flatten_requested_changes(changes).get("attachments")

	if not requested_field_keys and not (isinstance(attachments, dict) and attachments):
		return {"success": False, "error": "No changes to submit", "code": "NO_CHANGES"}

	employee_row = _get_enrichment_employee_row(employee, requested_field_keys)
	meta = _build_enrichment_submission_meta(employee_row, changes, submitted_via, submission_reason)

	superseded_requests: list[str] = []
	open_requests = frappe.get_all(
		REQUEST_DOCTYPE,
		filters={"employee": employee, "status": ("in", list(OPEN_REVIEW_STATUSES))},
		fields=["name", "status", "submitted_by_meta", "requested_changes", "approver_notes"],
		order_by="creation asc",
	)

	for row in open_requests:
		existing_keys = set(_get_requested_field_keys_from_request(row))
		if not existing_keys.intersection(requested_field_keys):
			continue

		claim_owner = _get_request_claim_owner(row)
		if claim_owner:
			return {
				"success": False,
				"error": f"An overlapping submission is already under review ({row['name']}).",
				"code": "OVERLAPPING_REQUEST_UNDER_REVIEW",
			}

		existing_doc = frappe.get_doc(REQUEST_DOCTYPE, row["name"])
		existing_meta = _set_workflow_state(
			existing_doc,
			"Superseded",
			superseded_at=str(now_datetime()),
			superseded_reason="Replaced by a newer profile enrichment submission.",
		)
		workflow = existing_meta.get("workflow") if isinstance(existing_meta.get("workflow"), dict) else {}
		workflow["superseded_by"] = ""
		existing_meta["workflow"] = workflow
		existing_doc.status = "Rejected"
		existing_doc.approver_notes = "\n".join(
			part
			for part in [existing_doc.approver_notes or "", "Superseded by a newer enrichment submission."]
			if part
		)
		_set_request_meta(existing_doc, existing_meta)
		existing_doc.save(ignore_permissions=True)
		superseded_requests.append(existing_doc.name)

	if superseded_requests:
		workflow = meta.get("workflow") if isinstance(meta.get("workflow"), dict) else {}
		workflow["supersedes_requests"] = superseded_requests
		meta["workflow"] = workflow

	doc = frappe.get_doc(
		{
			"doctype": REQUEST_DOCTYPE,
			"session_token": _new_token(),
			"employee": employee,
			"request_type": "update_existing",
			"status": "Pending",
			"submitted_at": now_datetime(),
			"submitted_via": submitted_via or "BEI Tasks - Profile Update",
			"requested_changes": _json_dumps(changes),
			"submitted_by_meta": _json_dumps(meta),
			"approver_email": approver_email or HR_APPROVER_FALLBACK,
			"escalated_to_hr": 1 if meta["workflow"]["requires_hr_review"] else 0,
		}
	)

	try:
		doc.insert(ignore_permissions=True)
		if superseded_requests:
			for superseded_name in superseded_requests:
				superseded_doc = frappe.get_doc(REQUEST_DOCTYPE, superseded_name)
				superseded_meta = _get_request_meta(superseded_doc)
				superseded_workflow = superseded_meta.get("workflow")
				if not isinstance(superseded_workflow, dict):
					superseded_workflow = {}
				superseded_workflow["superseded_by"] = doc.name
				superseded_meta["workflow"] = superseded_workflow
				_set_request_meta(superseded_doc, superseded_meta)
				superseded_doc.save(ignore_permissions=True)

		frappe.db.set_value(
			"Employee",
			employee,
			{
				"custom_enrichment_status": "Submitted",
				"custom_enrichment_submitted_date": today(),
			},
			update_modified=True,
		)
		frappe.db.commit()
	except Exception as exc:
		frappe.log_error(title="BEI submit_enrichment_update failed", message=str(exc))
		frappe.db.rollback()
		return {"success": False, "error": "Failed to submit enrichment request", "code": "SUBMIT_FAILED"}

	return {
		"success": True,
		"data": {
			"request": doc.name,
			"status": doc.status,
			"review_state": meta["workflow"]["review_state"],
			"requested_field_keys": requested_field_keys,
			"superseded_requests": superseded_requests,
		},
	}


def _create_employee_from_new_hire_request(req) -> dict[str, Any]:
	"""
	Auto-creates an Employee record directly via SQL INSERT.
	Extracts all mapping from requested_changes
	"""
	import json
	import re

	changes = _as_dict(req.requested_changes)

	# Flatten nested structure from enrichment wizard (safe_map handling for new hires)
	flat_changes = _flatten_requested_changes(changes)

	# ── Required fields ──────────────────────────────────────────────────────────
	required = [
		"first_name",
		"last_name",
		"branch",
		"department",
		"designation",
		"date_of_joining",
		"new_attendance_device_id",
	]
	missing = [f for f in required if not flat_changes.get(f)]
	if missing:
		frappe.throw(f"Cannot create Employee — missing required fields: {', '.join(missing)}")

	# ── Bio ID validation ────────────────────────────────────────────────────────
	bio_id = flat_changes["new_attendance_device_id"]
	if not re.match(r"^9\d{6}$", str(bio_id)):
		frappe.throw(
			f"Invalid Bio ID format: '{bio_id}'. Must match ^9\\d{{6}}$ (e.g., 9001812). "
			f"Last assigned: 9001811."
		)

	# Check uniqueness
	existing = frappe.db.get_value("Employee", {"attendance_device_id": bio_id}, "name")
	if existing:
		frappe.throw(f"Bio ID {bio_id} is already assigned to Employee {existing}")

	# ── Generate Employee ID ─────────────────────────────────────────────────────
	# BEI naming series: BEI-EMP-YYYY-NNNNN (e.g., BEI-EMP-2026-00637)
	year = frappe.utils.nowdate()[:4]
	last_emp = frappe.db.sql(
		"""
        SELECT name FROM tabEmployee
        WHERE name LIKE %s
        ORDER BY name DESC LIMIT 1 FOR UPDATE
    """,
		(f"BEI-EMP-{year}-%",),
		as_dict=True,
	)

	if last_emp:
		last_num = int(last_emp[0]["name"].split("-")[-1])
		new_num = last_num + 1
	else:
		new_num = 1

	employee_id = f"BEI-EMP-{year}-{new_num:05d}"

	# ── Build full name ──────────────────────────────────────────────────────────
	first = (flat_changes.get("first_name", "") or "").strip()
	middle = (flat_changes.get("middle_name", "") or "").strip()
	last = (flat_changes.get("last_name", "") or "").strip()
	employee_name = f"{first} {middle} {last}".replace("  ", " ").strip()

	# ── Safe Creation via ORM ────────────────────────────────────────────────────────
	company = frappe.db.get_single_value("Global Defaults", "default_company") or "Bebang Enterprise Inc."

	employee_doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"employee": employee_id,
			"employee_name": employee_name,
			"first_name": first,
			"middle_name": middle or "",
			"last_name": last,
			"gender": flat_changes.get("gender", "Male"),
			"date_of_birth": flat_changes.get("date_of_birth") or None,
			"date_of_joining": flat_changes["date_of_joining"],
			"branch": flat_changes["branch"],
			"department": flat_changes["department"],
			"designation": flat_changes["designation"],
			"company": company,
			"status": "Active",
			"attendance_device_id": bio_id,
			"new_attendance_device_id": bio_id,
			"personal_email": flat_changes.get("personal_email", ""),
			"cell_number": flat_changes.get("cell_number", ""),
			"current_address": flat_changes.get("current_address", ""),
			"permanent_address": flat_changes.get("permanent_address", ""),
			"person_to_be_contacted": flat_changes.get("person_to_be_contacted", ""),
			"emergency_phone_number": flat_changes.get("emergency_phone_number", ""),
			"relation": flat_changes.get("relation", ""),
			"tin_number": flat_changes.get("tin_number", ""),
			"sss_number": flat_changes.get("sss_number", ""),
			"philhealth_number": flat_changes.get("philhealth_number", ""),
			"pagibig_number": flat_changes.get("pagibig_number", ""),
			"bank_name": flat_changes.get("bank_name", ""),
			"bank_ac_no": flat_changes.get("bank_ac_no", ""),
			"reports_to": flat_changes.get("reports_to", ""),
			"image": req.selfie_file_url or "",
		}
	)

	# Bypass user permission to save properly during system approval action
	employee_doc.flags.ignore_permissions = True
	employee_doc.insert()
	return {"employee_id": employee_id, "employee_name": employee_name}


def _notify_new_employee_created(employee_id: str, employee_name: str, req) -> None:
	"""Notify HR team when a new employee record is created via onboarding approval."""
	try:
		from hrms.api.google_chat import send_message_to_space
		from hrms.utils.bei_config import SPACE_NOTIFICATIONS, get_chat_space

		space = get_chat_space(SPACE_NOTIFICATIONS)
		changes = _as_dict(req.requested_changes)

		flat_changes = _flatten_requested_changes(changes)

		branch = flat_changes.get("branch", "Unknown Branch")
		designation = flat_changes.get("designation", "Unknown Designation")
		bio_id = flat_changes.get("new_attendance_device_id", "TBD")
		message = (
			f"*New Employee Created*\n"
			f"Name: {employee_name}\n"
			f"Employee ID: {employee_id}\n"
			f"Bio ID: {bio_id}\n"
			f"Branch: {branch}\n"
			f"Designation: {designation}\n"
			f"Approved by: {req.approver_email}\n"
			f"Onboarding Request: {req.name}"
		)
		send_message_to_space(space, message)
	except Exception:
		pass  # Notification failure must NEVER block employee creation


@frappe.whitelist()
def approve_and_apply(
	request_name: str,
	approver_email: str,
	decision: str = "approve",
	approver_notes: str | None = None,
	is_hr_approver: bool | int | None = None,
	approved_fields: str | None = None,
) -> dict[str, Any]:
	"""
	Approve (or reject) and optionally apply an onboarding request.

	Notes:
	- Access control is enforced in tasks.bebang.ph (verifier routing + auth)
	- This method applies changes using the current session user (typically integration user)
	"""
	if not request_name:
		return {"success": False, "error": "Request is required", "code": "MISSING_REQUEST"}

	decision = (decision or "approve").strip().lower()
	if decision not in ("approve", "reject", "escalate"):
		return {"success": False, "error": "Invalid decision", "code": "INVALID_DECISION"}

	if not frappe.db.exists(REQUEST_DOCTYPE, request_name):
		return {"success": False, "error": "Request not found", "code": "NOT_FOUND"}

	req = frappe.get_doc(REQUEST_DOCTYPE, request_name)

	if req.status not in ("Pending", "Escalated"):
		return {"success": False, "error": "Request not pending", "code": "NOT_PENDING"}

	if not _can_access_assigned_request(req.approver_email, approver_email):
		return {"success": False, "error": "Not permitted to act on this request", "code": "FORBIDDEN"}

	req.approver_email = approver_email or ""
	req.approver_notes = approver_notes or ""
	req.approved_at = now_datetime()

	meta = _get_request_meta(req)
	workflow = meta.get("workflow")
	if not isinstance(workflow, dict):
		workflow = {}
	claim_owner = _norm_text(workflow.get("claimed_by"))
	if claim_owner and claim_owner != _norm_text(approver_email):
		return {
			"success": False,
			"error": f"Request is currently claimed by {claim_owner}",
			"code": "CLAIM_CONFLICT",
		}
	if not claim_owner:
		workflow["claimed_by"] = approver_email
		workflow["claimed_at"] = str(now_datetime())
	meta["workflow"] = workflow
	_set_request_meta(req, meta)

	if decision == "reject":
		req.status = "Rejected"
		_set_workflow_state(req, "Rejected", decided_by=approver_email, decided_at=str(now_datetime()))
		req.save(ignore_permissions=True)
		frappe.db.commit()
		return {"success": True, "data": {"status": req.status, "review_state": "Rejected"}}

	if decision == "escalate":
		req.status = "Escalated"
		req.escalated_to_hr = 1
		_set_workflow_state(
			req, "Pending Review", escalated_by=approver_email, escalated_at=str(now_datetime())
		)
		req.save(ignore_permissions=True)
		frappe.db.commit()
		return {"success": True, "data": {"status": req.status, "review_state": "Pending Review"}}

	# approve
	req.status = "Approved"
	requested_changes = _as_dict(req.requested_changes)
	flat_changes = _flatten_requested_changes(requested_changes)
	requested_field_keys = _get_requested_field_keys_from_request(req)

	# Optional partial approval path. If no subset is provided, default to the full field set.
	approved_field_set = set(requested_field_keys)
	if approved_fields:
		try:
			parsed_fields = (
				json.loads(approved_fields) if isinstance(approved_fields, str) else approved_fields
			)
			if isinstance(parsed_fields, list) and parsed_fields:
				approved_field_set = {
					str(field) for field in parsed_fields if str(field) in requested_field_keys
				}
		except Exception:
			approved_field_set = set(requested_field_keys)

	if req.request_type == "update_existing" and req.employee:
		is_stale, stale_details = _check_request_stale(req)
		if is_stale:
			req.status = "Escalated"
			_set_workflow_state(
				req,
				"Stale",
				stale_details=stale_details,
				stale_detected_at=str(now_datetime()),
			)
			req.save(ignore_permissions=True)
			frappe.db.commit()
			return {
				"success": False,
				"error": "Request snapshot is stale. Review and resubmit.",
				"code": "STALE_REQUEST",
				"data": stale_details,
			}

	# Apply changes (only for update_existing)
	if req.request_type == "update_existing" and req.employee:
		try:
			employee_before = (
				frappe.db.get_value(
					"Employee",
					req.employee,
					[
						"first_name",
						"middle_name",
						"last_name",
						"employee_name",
					],
					as_dict=True,
				)
				or {}
			)

			updates = {}
			for request_key in approved_field_set:
				employee_field = INPUT_TO_EMPLOYEE_FIELD_MAP.get(request_key, request_key)
				if not employee_field or request_key not in flat_changes:
					continue
				updates[employee_field] = flat_changes[request_key]

			if updates:
				name_parts = {
					"first_name": updates.get("first_name", employee_before.get("first_name")),
					"middle_name": updates.get("middle_name", employee_before.get("middle_name")),
					"last_name": updates.get("last_name", employee_before.get("last_name")),
				}
				if any(key in updates for key in ("first_name", "middle_name", "last_name")):
					updates["employee_name"] = " ".join(
						part
						for part in [
							name_parts["first_name"],
							name_parts["middle_name"],
							name_parts["last_name"],
						]
						if _norm_text(part)
					).strip()

				for field, value in updates.items():
					frappe.db.set_value("Employee", req.employee, field, value, update_modified=True)

			attachments = flat_changes.get("attachments")
			if isinstance(attachments, dict):
				for attachment_key, (request_field, verified_field) in PROOF_ATTACHMENTS.items():
					if attachment_key in attachments and request_field in approved_field_set:
						frappe.db.set_value("Employee", req.employee, verified_field, 1, update_modified=True)

			remaining_fields = sorted(set(requested_field_keys) - set(approved_field_set))
			req.status = "Approved" if remaining_fields else "Applied"
			req.applied_at = now_datetime()
			req.applied_by = frappe.session.user
			review_state = "Partially Approved" if remaining_fields else "Applied"
			_set_workflow_state(
				req,
				review_state,
				approved_fields=sorted(approved_field_set),
				remaining_fields=remaining_fields,
				decided_by=approver_email,
				decided_at=str(now_datetime()),
			)
			req.save(ignore_permissions=True)
			frappe.db.commit()
		except Exception as e:
			frappe.log_error(title="BEI Onboarding apply failed", message=str(e))
			return {"success": False, "error": "Approved but failed to apply changes", "code": "APPLY_FAILED"}

	elif req.request_type == "new_hire":
		try:
			result = _create_employee_from_new_hire_request(req)
			req.status = "Applied"
			req.applied_at = now_datetime()
			req.applied_by = frappe.session.user
			req.approver_notes = (req.approver_notes or "") + f"\nEmployee created: {result['employee_id']}"
			_set_workflow_state(req, "Applied", decided_by=approver_email, decided_at=str(now_datetime()))
			req.save(ignore_permissions=True)
			frappe.db.commit()

			_notify_new_employee_created(result["employee_id"], result["employee_name"], req)

		except frappe.ValidationError as e:
			frappe.db.rollback()
			frappe.log_error(title="BEI New Hire Employee Creation Failed", message=str(e))
			return {"success": False, "error": str(e), "code": "EMPLOYEE_CREATE_FAILED"}
		except Exception as e:
			frappe.db.rollback()
			frappe.log_error(title="BEI New Hire Employee Creation Failed", message=str(e))
			return {
				"success": False,
				"error": "Failed to create employee record",
				"code": "EMPLOYEE_CREATE_FAILED",
			}

	frappe.db.commit()
	final_meta = _get_request_meta(req)
	final_workflow = final_meta.get("workflow") if isinstance(final_meta.get("workflow"), dict) else {}
	return {
		"success": True,
		"data": {
			"status": req.status,
			"review_state": final_workflow.get("review_state")
			or ("Applied" if req.status == "Applied" else "Pending Review"),
		},
	}


@frappe.whitelist()
def request_revision(
	request_name: str,
	reviewer_email: str,
	fields_to_revise: str,  # JSON array of field keys
	revision_notes: str | None = None,
) -> dict[str, Any]:
	"""
	Request revision for specific fields in an onboarding request.

	Instead of rejecting the whole request, HR can ask the employee
	to correct specific fields and resubmit.
	"""
	if not request_name:
		return {"success": False, "error": "Request is required", "code": "MISSING_REQUEST"}

	if not frappe.db.exists(REQUEST_DOCTYPE, request_name):
		return {"success": False, "error": "Request not found", "code": "NOT_FOUND"}

	req = frappe.get_doc(REQUEST_DOCTYPE, request_name)

	if req.status not in ("Pending", "Escalated"):
		return {"success": False, "error": "Request not pending", "code": "NOT_PENDING"}

	if not _can_access_assigned_request(req.approver_email, reviewer_email):
		return {
			"success": False,
			"error": "Not permitted to request revision for this request",
			"code": "FORBIDDEN",
		}

	# Parse fields to revise
	try:
		fields = json.loads(fields_to_revise) if isinstance(fields_to_revise, str) else fields_to_revise
		if not isinstance(fields, list) or len(fields) == 0:
			return {"success": False, "error": "Fields to revise required", "code": "MISSING_FIELDS"}
	except Exception:
		return {"success": False, "error": "Invalid fields format", "code": "INVALID_FIELDS"}

	# Update request with revision info
	req.status = "Revision Requested"
	req.approver_email = reviewer_email or ""
	req.approver_notes = revision_notes or ""

	# Store revision details in a custom field or in approver_notes
	revision_info = {
		"fields": fields,
		"requested_by": reviewer_email,
		"requested_at": str(now_datetime()),
		"notes": revision_notes or "",
	}

	# Append revision info to approver_notes for now
	# (Could be stored in a separate field if needed)
	req.approver_notes = json.dumps(revision_info, ensure_ascii=False)
	_set_workflow_state(
		req,
		"More Info Needed",
		revision_fields=fields,
		revision_requested_by=reviewer_email,
		revision_requested_at=str(now_datetime()),
	)

	try:
		req.save(ignore_permissions=True)
		frappe.db.commit()
		return {
			"success": True,
			"data": {
				"status": req.status,
				"fields_to_revise": fields,
			},
		}
	except Exception as e:
		frappe.log_error(title="BEI Onboarding request_revision failed", message=str(e))
		return {"success": False, "error": "Failed to request revision", "code": "REVISION_FAILED"}


@frappe.whitelist()
def claim_request(request_name: str, reviewer_email: str, release: bool = False) -> dict[str, Any]:
	"""Claim or release a grouped enrichment submission for review."""
	if not request_name:
		return {"success": False, "error": "Request is required", "code": "MISSING_REQUEST"}

	if not reviewer_email:
		return {"success": False, "error": "Reviewer is required", "code": "MISSING_REVIEWER"}

	if not frappe.db.exists(REQUEST_DOCTYPE, request_name):
		return {"success": False, "error": "Request not found", "code": "NOT_FOUND"}

	req = frappe.get_doc(REQUEST_DOCTYPE, request_name)
	if req.status not in OPEN_REVIEW_STATUSES and req.status != "Approved":
		return {"success": False, "error": "Request is not open for review", "code": "NOT_OPEN"}

	if not _can_access_assigned_request(req.approver_email, reviewer_email):
		return {"success": False, "error": "Not permitted to claim this request", "code": "FORBIDDEN"}

	meta = _get_request_meta(req)
	workflow = meta.get("workflow")
	if not isinstance(workflow, dict):
		workflow = {}

	existing_owner = _norm_text(workflow.get("claimed_by"))
	reviewer_email = _norm_text(reviewer_email)

	if release:
		if existing_owner and existing_owner != reviewer_email:
			return {
				"success": False,
				"error": f"Request is claimed by {existing_owner}",
				"code": "CLAIM_CONFLICT",
			}
		workflow["claimed_by"] = ""
		workflow["claimed_at"] = ""
	else:
		if existing_owner and existing_owner != reviewer_email:
			return {
				"success": False,
				"error": f"Request is already claimed by {existing_owner}",
				"code": "CLAIM_CONFLICT",
			}
		workflow["claimed_by"] = reviewer_email
		workflow["claimed_at"] = str(now_datetime())

	meta["workflow"] = workflow
	_set_request_meta(req, meta)

	try:
		req.save(ignore_permissions=True)
		frappe.db.commit()
	except Exception as exc:
		frappe.log_error(title="BEI Onboarding claim_request failed", message=str(exc))
		frappe.db.rollback()
		return {"success": False, "error": "Failed to update claim", "code": "CLAIM_FAILED"}

	return {
		"success": True,
		"data": {
			"claimed_by": workflow.get("claimed_by") or "",
			"claimed_at": workflow.get("claimed_at") or "",
		},
	}
