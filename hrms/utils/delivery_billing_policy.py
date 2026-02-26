# Copyright (c) 2026, Bebang Enterprise Inc.
# For license information, please see license.txt

from collections.abc import Mapping
from datetime import datetime

CPO_APPROVER_EMAIL = "mae@bebang.ph"
CFO_APPROVER_EMAIL = "butch@bebang.ph"
DUAL_APPROVAL_TIER = "CPO+CFO"


class DeliveryBillingPolicyError(ValueError):
	"""Raised when a pre-delivery billing request violates policy."""


def should_auto_create_billing_on_delivery(setting_value):
	"""Treat missing setting as enabled; explicit falsey values disable automation."""
	if setting_value is None:
		return True

	if isinstance(setting_value, bool):
		return setting_value

	if isinstance(setting_value, int | float):
		return int(setting_value) == 1

	text = str(setting_value).strip().lower()
	if text in {"1", "true", "yes", "y", "on"}:
		return True
	if text in {"0", "false", "no", "n", "off", ""}:
		return False

	return bool(setting_value)


def append_approval_audit_log(existing_log, action, approver, approved_at, comment=None):
	"""Append one structured approval line to the audit log text field."""
	if isinstance(approved_at, datetime):
		timestamp = approved_at.isoformat(sep=" ", timespec="seconds")
	else:
		timestamp = str(approved_at)

	entry = f"[{timestamp}] {action} by {approver}"
	cleaned_comment = (comment or "").strip()
	if cleaned_comment:
		entry = f"{entry} | Comment: {cleaned_comment}"

	if not existing_log:
		return entry
	return f"{existing_log}\n{entry}"


def _value(doc_or_dict, key, default=None):
	if isinstance(doc_or_dict, Mapping):
		return doc_or_dict.get(key, default)
	return getattr(doc_or_dict, key, default)


def get_pre_delivery_exception_trace(exception_doc, trip_reference, trip_stop_idx):
	"""Validate exception against delivery policy and return normalized audit trace."""
	approval_tier = _value(exception_doc, "approval_tier")
	if approval_tier != DUAL_APPROVAL_TIER:
		raise DeliveryBillingPolicyError(
			"Pre-delivery billing requires an exception approved under CPO+CFO dual approval."
		)

	status = _value(exception_doc, "status")
	if status != "Approved":
		raise DeliveryBillingPolicyError("Pre-delivery billing exception is not fully approved yet.")

	exception_trip = _value(exception_doc, "delivery_trip_reference")
	if exception_trip != trip_reference:
		raise DeliveryBillingPolicyError(
			f"Exception trip reference mismatch: expected {trip_reference}, got {exception_trip or 'empty'}."
		)

	try:
		exception_stop_idx = int(_value(exception_doc, "delivery_stop_idx") or 0)
		target_stop_idx = int(trip_stop_idx or 0)
	except (TypeError, ValueError):
		raise DeliveryBillingPolicyError("Invalid delivery stop index on exception or billing.")

	if exception_stop_idx != target_stop_idx:
		raise DeliveryBillingPolicyError(
			f"Exception stop mismatch: expected stop {target_stop_idx}, got {exception_stop_idx}."
		)

	cpo_approved_by = _value(exception_doc, "cpo_approved_by")
	cpo_approved_at = _value(exception_doc, "cpo_approved_at")
	cfo_approved_by = _value(exception_doc, "cfo_approved_by")
	cfo_approved_at = _value(exception_doc, "cfo_approved_at")

	if cpo_approved_by != CPO_APPROVER_EMAIL or not cpo_approved_at:
		raise DeliveryBillingPolicyError("Pre-delivery billing requires explicit Daymae/CPO approval trace.")

	if cfo_approved_by != CFO_APPROVER_EMAIL or not cfo_approved_at:
		raise DeliveryBillingPolicyError("Pre-delivery billing requires explicit Butch/CFO approval trace.")

	return {
		"exception_name": _value(exception_doc, "name"),
		"cpo_approved_by": cpo_approved_by,
		"cpo_approved_at": cpo_approved_at,
		"cfo_approved_by": cfo_approved_by,
		"cfo_approved_at": cfo_approved_at,
		"approval_audit_log": _value(exception_doc, "approval_audit_log"),
	}
