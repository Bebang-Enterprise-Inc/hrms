"""Deterministic notification policy, rendering, and certification helpers.

This module stays pure-Python so both Frappe and standalone services can share
the same family definitions without importing the framework runtime.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from copy import deepcopy
from typing import Any

SPACE_NOTIFICATIONS = "spaces/AAQABiNmpBg"
SPACE_ERP_AUTOMATION = "spaces/AAQA3NVVR6c"
SPACE_ACCOUNTING = "spaces/AAAA9RN0JZQ"
SPACE_OPS = "spaces/AAAAvDZdY-o"

PORTAL_BASE_URL = "https://my.bebang.ph"

REQUIRED_EVENT_FIELDS = (
	"family",
	"source_system",
	"source_ref",
	"severity",
	"delivery_class",
	"owner",
	"dedup_key",
	"facts",
	"requested_space",
	"fallback_text",
)


def _portal_url(path: str) -> str:
	path_text = str(path or "").strip()
	if not path_text:
		return PORTAL_BASE_URL
	if path_text.startswith("http://") or path_text.startswith("https://"):
		return path_text
	if not path_text.startswith("/"):
		path_text = f"/{path_text}"
	return f"{PORTAL_BASE_URL}{path_text}"


FAMILY_POLICIES: dict[str, dict[str, Any]] = {
	"sheets_sync_critical": {
		"family_label": "Sheets Sync Critical",
		"delivery_class": "critical_immediate",
		"default_space": SPACE_NOTIFICATIONS,
		"allowed_spaces": (SPACE_NOTIFICATIONS, SPACE_ERP_AUTOMATION),
		"allow_requested_space": False,
		"default_severity": "critical",
		"owner": "Dave Martinez / Edlice Dela Cruz",
		"dedup_window_minutes": 90,
		"routing_reason": "High-signal sync blocker for finance and operations.",
	},
	"maintenance_sla_backlog": {
		"family_label": "Maintenance SLA Backlog",
		"delivery_class": "action_digest",
		"default_space": SPACE_NOTIFICATIONS,
		"allowed_spaces": (SPACE_NOTIFICATIONS, SPACE_ERP_AUTOMATION),
		"allow_requested_space": False,
		"default_severity": "high",
		"owner": "Projects Manager",
		"dedup_window_minutes": 120,
		"routing_reason": "Exec-facing backlog digest for overdue maintenance work.",
	},
	"maintenance_status_update": {
		"family_label": "Maintenance Status Update",
		"delivery_class": "action_digest",
		"default_space": SPACE_OPS,
		"allowed_spaces": (SPACE_OPS, SPACE_ERP_AUTOMATION),
		"allow_requested_space": True,
		"default_severity": "medium",
		"owner": "Projects Team / Store Manager",
		"dedup_window_minutes": 60,
		"routing_reason": "Store and ops lifecycle update; does not belong in Blip by default.",
	},
	"approval_queue_new": {
		"family_label": "Approval Queue New",
		"delivery_class": "action_digest",
		"default_space": SPACE_NOTIFICATIONS,
		"allowed_spaces": (SPACE_NOTIFICATIONS, SPACE_ERP_AUTOMATION),
		"allow_requested_space": False,
		"default_severity": "high",
		"owner": "Assigned Approver",
		"dedup_window_minutes": 45,
		"routing_reason": "Actionable approval brief for the approver / control cell.",
	},
	"store_order_new": {
		"family_label": "Store Order New",
		"delivery_class": "awareness_digest",
		"default_space": SPACE_OPS,
		"allowed_spaces": (SPACE_OPS, SPACE_ERP_AUTOMATION),
		"allow_requested_space": False,
		"default_severity": "medium",
		"owner": "Store Ops / Warehouse",
		"dedup_window_minutes": 45,
		"routing_reason": "Ops awareness only; approval queue owns the Blip action signal.",
	},
	"store_order_approved": {
		"family_label": "Store Order Approved",
		"delivery_class": "action_digest",
		"default_space": SPACE_OPS,
		"allowed_spaces": (SPACE_OPS, SPACE_ERP_AUTOMATION),
		"allow_requested_space": True,
		"default_severity": "medium",
		"owner": "Warehouse / Store Ops",
		"dedup_window_minutes": 45,
		"routing_reason": "Fulfilment and store follow-through update; not a Blip catch-all item.",
	},
	"discount_critical_digest": {
		"family_label": "Discount Critical Digest",
		"delivery_class": "critical_immediate",
		"default_space": SPACE_ACCOUNTING,
		"allowed_spaces": (SPACE_ACCOUNTING, SPACE_ERP_AUTOMATION),
		"allow_requested_space": False,
		"default_severity": "critical",
		"owner": "Accounting",
		"dedup_window_minutes": 180,
		"routing_reason": "Private accounting alert for discount-abuse review.",
	},
	"morning_readiness_digest": {
		"family_label": "Morning Readiness Digest",
		"delivery_class": "action_digest",
		"default_space": SPACE_NOTIFICATIONS,
		"allowed_spaces": (SPACE_NOTIFICATIONS, SPACE_ERP_AUTOMATION),
		"allow_requested_space": False,
		"default_severity": "medium",
		"owner": "ERP Automation / Ops",
		"dedup_window_minutes": 180,
		"routing_reason": "Daily readiness brief for store, warehouse, and finance syncs.",
	},
}

EXCLUDED_FAMILIES: dict[str, dict[str, str]] = {
	"meta_ads_digest": {
		"owner": "Marketing",
		"destination_policy": "Keep out of Blip; route to marketing-only reporting channels.",
	},
	"attendance_bridge_failure": {
		"owner": "HR / Biometrics",
		"destination_policy": "Route to biometric ops / HR support, not Blip catch-all.",
	},
	"biometric_daily_digest": {
		"owner": "HR / Biometrics",
		"destination_policy": "Route to biometric dashboard/digest destinations only.",
	},
	"unclassified_external_or_future_sender": {
		"owner": "Control Cell",
		"destination_policy": "Must be classified before using Blip policy routes.",
	},
}


def get_notification_policy(family: str) -> dict[str, Any]:
	try:
		return deepcopy(FAMILY_POLICIES[family])
	except KeyError as exc:
		raise ValueError(f"Unknown notification family: {family}") from exc


def get_family_allowed_spaces(family: str | None) -> set[str]:
	if not family or family not in FAMILY_POLICIES:
		return set()
	return set(FAMILY_POLICIES[family].get("allowed_spaces") or ())


def family_allows_requested_space(family: str | None) -> bool:
	if not family or family not in FAMILY_POLICIES:
		return False
	return bool(FAMILY_POLICIES[family].get("allow_requested_space"))


def list_certified_families() -> list[str]:
	return list(FAMILY_POLICIES.keys())


def build_certified_family_manifest_rows() -> list[dict[str, Any]]:
	rows: list[dict[str, Any]] = []
	for family, policy in FAMILY_POLICIES.items():
		rows.append(
			{
				"family": family,
				"family_label": policy["family_label"],
				"delivery_class": policy["delivery_class"],
				"default_space": policy["default_space"],
				"allowed_spaces": ",".join(policy["allowed_spaces"]),
				"allow_requested_space": "yes" if policy["allow_requested_space"] else "no",
				"default_severity": policy["default_severity"],
				"owner": policy["owner"],
				"dedup_window_minutes": policy["dedup_window_minutes"],
				"routing_reason": policy["routing_reason"],
			}
		)
	return rows


def build_exclusion_rows() -> list[dict[str, Any]]:
	return [
		{
			"family": family,
			"owner": meta["owner"],
			"destination_policy": meta["destination_policy"],
		}
		for family, meta in EXCLUDED_FAMILIES.items()
	]


def build_routing_matrix_rows() -> list[dict[str, Any]]:
	rows: list[dict[str, Any]] = []
	for family, policy in FAMILY_POLICIES.items():
		rows.append(
			{
				"family": family,
				"delivery_class": policy["delivery_class"],
				"default_space": policy["default_space"],
				"allowed_spaces": ",".join(policy["allowed_spaces"]),
				"allow_requested_space": "yes" if policy["allow_requested_space"] else "no",
				"routing_reason": policy["routing_reason"],
			}
		)
	return rows


def _clean_text(value: Any, fallback: str = "-") -> str:
	text = str(value or "").strip()
	return text or fallback


def _unique_texts(values: list[Any] | tuple[Any, ...], limit: int | None = None) -> list[str]:
	result: list[str] = []
	seen: set[str] = set()
	for value in values:
		text = str(value or "").strip()
		if not text or text in seen:
			continue
		seen.add(text)
		result.append(text)
		if limit is not None and len(result) >= limit:
			break
	return result


def _severity_label(value: str) -> str:
	text = str(value or "").strip().lower()
	if text == "critical":
		return "Critical"
	if text == "high":
		return "High"
	if text == "medium":
		return "Medium"
	if text == "low":
		return "Low"
	return text.title() or "Medium"


def _build_sheet_url(facts: dict[str, Any]) -> str:
	spreadsheet_id = _clean_text(facts.get("spreadsheet_id"), fallback="")
	if not spreadsheet_id:
		return ""
	return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"


# ---------------------------------------------------------------------------
# Error Diagnosis Map — translate raw error strings into actionable fixes
# ---------------------------------------------------------------------------

# Each entry: (compiled_regex, diagnosis, recommended_fix)
# Order matters: first match wins.
_ERROR_DIAGNOSES: list[tuple[re.Pattern[str], str, str]] = [
	(
		re.compile(r"set default Stock Received But Not Billed.*?Company\s+(\S+)", re.IGNORECASE),
		'Company "{match}" is missing the "Stock Received But Not Billed" default account. '
		"This is a one-time ERPNext setup issue, not a data problem.",
		'Go to ERPNext > Setup > Company > "{match}" > Default Accounts and set the '
		'"Stock Received But Not Billed" account (usually under Current Liabilities). '
		"Once configured, rerun the sync — all affected rows should clear.",
	),
	(
		re.compile(r"Could not find.*?Item Code:\s*(\S+)", re.IGNORECASE),
		'Item Code "{match}" does not exist in ERPNext. The source sheet references an item '
		"that has not been created or was deleted.",
		'Create Item "{match}" in ERPNext (Stock > Item > New) with the correct item group '
		"and UOM, or correct the item code in the source sheet, then rerun.",
	),
	(
		re.compile(r"Warehouse\s+(\S+.*?)\s+not found", re.IGNORECASE),
		'Warehouse "{match}" referenced in the sheet does not exist in ERPNext.',
		'Create the warehouse in ERPNext (Stock > Warehouse > New) under the correct '
		"company tree, or fix the warehouse name in the source sheet.",
	),
	(
		re.compile(r"duplicate entry.*?for key\s+'(\S+)'", re.IGNORECASE),
		"Duplicate record detected — the sync tried to create a record that already exists.",
		"Check if the source sheet has duplicate rows with the same key. "
		"Remove duplicates from the sheet or mark existing records for update instead of insert.",
	),
	(
		re.compile(r"Mandatory.*?Supplier\s", re.IGNORECASE),
		"Rows are missing the required Supplier field. Likely blank rows at the bottom of the sheet.",
		"Delete empty/blank rows at the bottom of the source sheet that have no supplier, "
		"then rerun the sync.",
	),
	(
		re.compile(r"Mandatory.*?Invoice", re.IGNORECASE),
		"Rows are missing required invoice numbers. These may be partial entries or blank tail rows.",
		"Fill in invoice numbers on real data rows or delete blank rows, then rerun.",
	),
	(
		re.compile(r"rate must be.*?positive|amount.*?cannot be (zero|negative)", re.IGNORECASE),
		"Some rows have zero or negative amounts that ERPNext rejects.",
		"Review the flagged rows for pricing errors or credit notes that need separate handling.",
	),
	(
		re.compile(r"Account.*?does not belong to.*?Company\s+(\S+)", re.IGNORECASE),
		'An account is assigned to the wrong company. The ledger account does not belong to "{match}".',
		'Check the Chart of Accounts for company "{match}" and ensure the correct '
		"account is mapped. This is usually a setup issue after adding a new company entity.",
	),
]


def _diagnose_errors(errors: list[str]) -> tuple[str, str] | None:
	"""Match error strings against known patterns. Returns (diagnosis, fix) or None."""
	error_text = " ".join(errors).strip()
	if not error_text:
		return None
	for pattern, diagnosis_template, fix_template in _ERROR_DIAGNOSES:
		m = pattern.search(error_text)
		if m:
			match_val = m.group(1) if m.lastindex and m.lastindex >= 1 else ""
			return (
				diagnosis_template.replace("{match}", match_val),
				fix_template.replace("{match}", match_val),
			)
	return None


# ---------------------------------------------------------------------------
# Pattern Recognition — detect clusters, aging, and anomalies
# ---------------------------------------------------------------------------

def _analyze_store_clusters(breaches: list[dict[str, Any]]) -> str:
	"""Identify store-level concentration in SLA breaches."""
	if not breaches:
		return ""
	store_counts: Counter[str] = Counter()
	for row in breaches:
		store = _clean_text((row or {}).get("store"), fallback="")
		if store:
			store_counts[store] += 1
	if not store_counts:
		return ""
	top_store, top_count = store_counts.most_common(1)[0]
	total = len(breaches)
	pct = round(top_count / total * 100) if total else 0
	if top_count >= 5 and pct >= 30:
		return (
			f"{top_store} accounts for {top_count} of {total} breaches ({pct}%). "
			f"This looks like a systemic maintenance gap at that location, "
			f"not individual ticket delays."
		)
	if len(store_counts) <= 3 and total >= 10:
		names = ", ".join(s for s, _ in store_counts.most_common(3))
		return f"Breaches are concentrated in {len(store_counts)} stores: {names}."
	return ""


def _analyze_aging_pattern(breaches: list[dict[str, Any]]) -> str:
	"""Identify tickets that have been stale for an unusually long time."""
	if not breaches:
		return ""
	ages = []
	for row in breaches:
		try:
			ages.append(float((row or {}).get("age_hours") or 0))
		except (ValueError, TypeError):
			pass
	if not ages:
		return ""
	max_age = max(ages)
	if max_age >= 168:  # 7+ days
		days = round(max_age / 24, 1)
		return f"Oldest breach is {days} days old — well past any SLA tier."
	if max_age >= 48:
		return f"Oldest breach is {round(max_age, 1)}h — multiple days without movement."
	return ""


def _diagnose_morning_lane(area: dict[str, Any]) -> str:
	"""Produce a lane-specific diagnosis for morning readiness failures."""
	label = _clean_text((area or {}).get("label"), fallback="").lower()
	status = _clean_text((area or {}).get("status"), fallback="").lower()
	error = _clean_text((area or {}).get("last_error"), fallback="")
	if status in ("green", "ready"):
		return ""
	# Try to diagnose from the error message
	if error:
		diagnosis = _diagnose_errors([error])
		if diagnosis:
			return f"{(area or {}).get('label', 'Lane')}: {diagnosis[0]}"
	# Fallback lane-specific guidance
	if "inventory" in label or "shadow" in label:
		return f"{(area or {}).get('label', 'Store Inventory')}: Sync did not complete before deadline. Check if the scheduled job ran and whether any stores timed out."
	if "warehouse" in label or "ian" in label:
		return f"{(area or {}).get('label', 'Warehouse Inventory')}: Warehouse baseline sync missed the window. Verify the cron trigger fired and the warehouse API responded."
	if "ap" in label or "procurement" in label or "finance" in label:
		return f"{(area or {}).get('label', 'AP/Procurement')}: Finance baseline sync failed. Check the Sheets Receiver logs for row-level errors or schema mismatches."
	return f"{(area or {}).get('label', 'Unknown lane')}: Sync did not reach ready state before the deadline."


# ---------------------------------------------------------------------------
# Delta Awareness — compare current state to previous notification
# ---------------------------------------------------------------------------

def _compute_delta_summary(family: str, current_facts: dict[str, Any], previous_snapshot: dict[str, Any] | None) -> str:
	"""Compare current facts to previous snapshot and describe what changed."""
	if not previous_snapshot:
		return ""
	if family == "maintenance_sla_backlog":
		prev_count = int(previous_snapshot.get("total_breaches") or 0)
		curr_breaches = list(current_facts.get("breaches") or [])
		curr_count = len(curr_breaches)
		if curr_count == prev_count:
			prev_names = set(previous_snapshot.get("breach_names") or [])
			curr_names = {_clean_text((r or {}).get("name"), "") for r in curr_breaches} - {""}
			new_tickets = curr_names - prev_names
			resolved = prev_names - curr_names
			if not new_tickets and not resolved:
				return "Backlog unchanged since last report — same tickets, same count."
			parts = []
			if new_tickets:
				parts.append(f"{len(new_tickets)} new breach(es)")
			if resolved:
				parts.append(f"{len(resolved)} resolved")
			return "Since last report: " + ", ".join(parts) + "."
		diff = curr_count - prev_count
		direction = "increased" if diff > 0 else "decreased"
		return f"Backlog {direction} from {prev_count} to {curr_count} ({'+' if diff > 0 else ''}{diff})."
	if family == "morning_readiness_digest":
		prev_status = _clean_text(previous_snapshot.get("status"), fallback="")
		curr_status = _clean_text(current_facts.get("status"), fallback="")
		if prev_status and curr_status and prev_status != curr_status:
			return f"Status changed from {prev_status} to {curr_status} since last report."
	return ""


def _build_snapshot_for_cache(family: str, facts: dict[str, Any]) -> dict[str, Any]:
	"""Build a compact snapshot of current facts for delta comparison next time."""
	if family == "maintenance_sla_backlog":
		breaches = list(facts.get("breaches") or [])
		return {
			"total_breaches": len(breaches),
			"breach_names": sorted(
				_clean_text((r or {}).get("name"), "")
				for r in breaches
				if _clean_text((r or {}).get("name"), "")
			),
			"counts_by_priority": facts.get("counts_by_priority") or {},
		}
	if family == "morning_readiness_digest":
		return {
			"status": facts.get("status"),
			"area_keys": [
				_clean_text((a or {}).get("key"), "")
				for a in (facts.get("areas") or [])
			],
		}
	if family == "sheets_sync_critical":
		return {
			"rows_failed": facts.get("rows_failed"),
			"rows_processed": facts.get("rows_processed"),
			"errors": _unique_texts(facts.get("errors") or [], limit=3),
		}
	return {}


def _build_default_source_ref(family: str, facts: dict[str, Any]) -> str:
	if family == "sheets_sync_critical":
		return f"{_clean_text(facts.get('spreadsheet_name'))} / {_clean_text(facts.get('sheet_name'))}"
	if family == "maintenance_sla_backlog":
		return f"maintenance_sla:{_clean_text(facts.get('report_date'), fallback='today')}"
	if family == "maintenance_status_update":
		return _clean_text(facts.get("request_name"), fallback="maintenance_request")
	if family == "approval_queue_new":
		return _clean_text(facts.get("queue_name"), fallback="approval_queue")
	if family in {"store_order_new", "store_order_approved"}:
		return _clean_text(facts.get("order_name"), fallback="store_order")
	if family == "discount_critical_digest":
		return f"discount_audit:{_clean_text(facts.get('business_date'), fallback='today')}"
	if family == "morning_readiness_digest":
		return f"morning_sync:{_clean_text(facts.get('report_date'), fallback='today')}"
	return family


def _build_default_dedup_key(family: str, facts: dict[str, Any], source_ref: str) -> str:
	if family == "sheets_sync_critical":
		payload = {
			"source_ref": source_ref,
			"trigger": facts.get("trigger"),
			"rows_failed": facts.get("rows_failed", 0),
			"reasons": sorted(_unique_texts(facts.get("reasons") or [])),
			"errors": _unique_texts(facts.get("errors") or [], limit=3),
			"alerts": _unique_texts(facts.get("alerts") or [], limit=3),
		}
	elif family == "maintenance_sla_backlog":
		payload = {
			"source_ref": source_ref,
			"request_names": sorted(
				_unique_texts(
					[(row or {}).get("name") for row in (facts.get("breaches") or [])],
				)
			),
		}
	elif family == "morning_readiness_digest":
		payload = {
			"source_ref": source_ref,
			"status": facts.get("status"),
			"area_statuses": [
				{
					"key": (area or {}).get("key"),
					"status": (area or {}).get("status"),
					"ready_before_deadline": (area or {}).get("ready_before_deadline"),
				}
				for area in (facts.get("areas") or [])
			],
		}
	else:
		payload = {"source_ref": source_ref, "facts": facts}

	digest = hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]
	return f"{family}:{digest}"


def _sheet_recommended_fix(facts: dict[str, Any]) -> tuple[str, str]:
	"""Returns (diagnosis, recommended_fix) for sheets sync errors."""
	error_list = _unique_texts(facts.get("errors") or [], limit=5)
	reasons = set(_unique_texts(facts.get("reasons") or []))
	# Try the diagnosis map first for specific actionable fixes
	diagnosis_result = _diagnose_errors(error_list)
	if diagnosis_result:
		return diagnosis_result
	# Fallback to legacy pattern matching
	errors_lower = " ".join(error_list).lower()
	if "invoice_no" in errors_lower:
		return (
			"Rows are missing required invoice numbers.",
			"Restore invoice numbers on non-blank rows or correct the AR/AP transform before rerunning the sync.",
		)
	if "supplier" in errors_lower:
		return (
			"Rows have missing supplier fields — likely blank tail rows in the sheet.",
			"Fill the missing supplier/invoice fields on real rows and delete blank tail rows before rerunning.",
		)
	if "suspicious_change_alert" in reasons and not int(facts.get("rows_failed") or 0):
		return (
			"An unusual edit or deletion pattern was detected in the source sheet.",
			"Confirm the mass edit/deletion was intentional before finance or ops rely on the updated sheet.",
		)
	return (
		"The sync encountered errors that need manual review.",
		"Fix the top sync errors or source-sheet schema mismatch, then rerun the sheet sync.",
	)


def _render_sheets_sync_critical(event: dict[str, Any]) -> dict[str, Any]:
	facts = event["facts"]
	rows_failed = int(facts.get("rows_failed") or 0)
	rows_processed = int(facts.get("rows_processed") or 0)
	reasons = _unique_texts(facts.get("reasons") or [])
	errors = _unique_texts(facts.get("errors") or [], limit=5)
	alerts = _unique_texts(facts.get("alerts") or [], limit=3)
	trigger = _clean_text(facts.get("trigger"), fallback="manual")
	if trigger == "scheduled":
		trigger = "scheduled (6-hour fallback)"
	sheet_ref = _build_default_source_ref("sheets_sync_critical", facts)
	diagnosis, recommended_fix = _sheet_recommended_fix(facts)
	if rows_failed:
		summary = f"{sheet_ref}: {rows_failed} of {rows_processed} rows failed during {trigger}."
		if diagnosis:
			summary += f" Root cause: {diagnosis}"
	else:
		summary = f"{sheet_ref} synced, but the change pattern looks unusual and needs review."
	delta = _compute_delta_summary("sheets_sync_critical", facts, event.get("_previous_snapshot"))
	if delta:
		summary += f" {delta}"
	if rows_failed:
		action = recommended_fix
	else:
		action = "Verify the reported edit/deletion pattern against the source sheet before the team relies on it."
	evidence_bits = [f"Sheet: {sheet_ref}", f"Trigger: {trigger}"]
	if reasons:
		evidence_bits.append("Reasons: " + ", ".join(reasons))
	if errors:
		evidence_bits.append("Top errors: " + "; ".join(errors))
	if alerts:
		evidence_bits.append("Change alerts: " + "; ".join(alerts))
	sheet_url = _build_sheet_url(facts)
	if sheet_url:
		evidence_bits.append(sheet_url)
	return {
		"summary": summary,
		"why_it_matters": "Finance and ops can end up working from stale or misleading sheet-backed data until this lane is verified.",
		"action_now": action,
		"owner": event["owner"],
		"recommended_fix": recommended_fix,
		"evidence": " | ".join(evidence_bits),
		"urgency": _severity_label(event["severity"]),
		"event_count": max(rows_failed, len(alerts), len(errors), 1),
	}


def _render_maintenance_sla_backlog(event: dict[str, Any]) -> dict[str, Any]:
	facts = event["facts"]
	breaches = list(facts.get("breaches") or [])
	counts = facts.get("counts_by_priority") or {}
	total = len(breaches)
	count_bits = [
		f"{priority}: {int(counts.get(priority) or 0)}"
		for priority in ("Urgent", "High", "Normal")
		if int(counts.get(priority) or 0)
	]
	top_rows = []
	for row in breaches[:5]:
		top_rows.append(
			"{name} ({store}, {priority}, age {age}h)".format(
				name=_clean_text((row or {}).get("name")),
				store=_clean_text((row or {}).get("store")),
				priority=_clean_text((row or {}).get("priority")),
				age=_clean_text((row or {}).get("age_hours")),
			)
		)
	delta = _compute_delta_summary("maintenance_sla_backlog", facts, event.get("_previous_snapshot"))
	cluster_insight = _analyze_store_clusters(breaches)
	aging_insight = _analyze_aging_pattern(breaches)
	summary = f"{total} maintenance requests are past SLA."
	if count_bits:
		summary += " " + ", ".join(count_bits) + "."
	if delta:
		summary += f" {delta}"
	why = "Stores are carrying unresolved maintenance issues beyond target response time, which can keep operations exposed or degraded."
	if cluster_insight:
		why = cluster_insight + " " + why
	action = "Review the Projects queue now, assign or escalate the oldest urgent items first, and update each ticket with the next ETA."
	recommended = "Clear urgent breaches first, then rebalance high/normal backlog and chase vendors with no confirmed schedule."
	if aging_insight:
		recommended = f"{aging_insight} {recommended}"
	return {
		"summary": summary,
		"why_it_matters": why,
		"action_now": action,
		"owner": event["owner"],
		"recommended_fix": recommended,
		"evidence": " | ".join(
			_unique_texts(
				[
					f"Overdue count: {total}",
					"Top tickets: " + "; ".join(top_rows) if top_rows else "",
					f"Dashboard: {_portal_url('/dashboard/projects')}",
				]
			)
		),
		"urgency": _severity_label(event["severity"]),
		"event_count": max(total, 1),
	}


def _render_maintenance_status_update(event: dict[str, Any]) -> dict[str, Any]:
	facts = event["facts"]
	request_name = _clean_text(facts.get("request_name"))
	store = _clean_text(facts.get("store"))
	status = _clean_text(facts.get("status"), fallback="Open")
	event_kind = _clean_text(facts.get("event_kind"), fallback="status_change")
	priority = _clean_text(facts.get("priority"))
	category = _clean_text(facts.get("issue_category"))
	description = _clean_text(facts.get("description"))
	if event_kind == "created":
		summary = f"New maintenance request {request_name} was filed for {store}."
		action = "Projects should triage the issue, assign an owner, and confirm the response plan."
		recommended = "Set the owner/SLA now and give the store a concrete next step."
		why = "A newly reported issue needs ownership before it becomes an SLA breach or store escalation."
	elif status == "Completed":
		summary = f"Maintenance request {request_name} is marked Completed for {store}."
		action = (
			"Store leadership should verify the work result and close the loop in the next maintenance check."
		)
		recommended = (
			"Confirm the work quality and capture verification so the ticket does not linger unresolved."
		)
		why = "Completed work still needs store confirmation before the issue is truly closed."
	elif status == "Verified":
		summary = f"Maintenance request {request_name} has been verified for {store}."
		action = "No action needed unless the issue reappears."
		recommended = "Keep the request closed and reopen only if the same issue returns."
		why = "The maintenance lifecycle is complete and no further operator intervention is expected."
	elif status == "Cancelled":
		summary = f"Maintenance request {request_name} was cancelled for {store}."
		action = "No action needed unless the underlying issue is still active."
		recommended = "Refile the request only if the issue still affects operations."
		why = "Cancelled requests should not keep creating follow-up chatter unless the problem remains unresolved."
	else:
		summary = f"Maintenance request {request_name} updated to {status} for {store}."
		action = "Review the latest owner, schedule, or vendor update if the store still needs clarification."
		recommended = "Keep the request moving and avoid silent status changes without a next step."
		why = "Lifecycle updates should clarify what changed and who owns the next step."
	return {
		"summary": summary,
		"why_it_matters": why,
		"action_now": action,
		"owner": event["owner"],
		"recommended_fix": recommended,
		"evidence": " | ".join(
			_unique_texts(
				[
					f"Request: {request_name}",
					f"Store: {store}",
					f"Priority: {priority}",
					f"Category: {category}",
					f"Issue: {description}",
					f"Projects queue: {_portal_url('/dashboard/projects')}",
				]
			)
		),
		"urgency": _severity_label(event["severity"]),
		"event_count": 1,
	}


def _render_approval_queue_new(event: dict[str, Any]) -> dict[str, Any]:
	facts = event["facts"]
	reference_doctype = _clean_text(facts.get("reference_doctype"), fallback="Approval")
	reference_name = _clean_text(facts.get("reference_name"), fallback=facts.get("subject"))
	store = _clean_text(facts.get("store"))
	queue_name = _clean_text(facts.get("queue_name"))
	dashboard_url = _clean_text(
		facts.get("dashboard_url"), fallback=_portal_url("/dashboard/store-ops/order-approvals")
	)
	return {
		"summary": f"{reference_doctype} {reference_name} is waiting for approval.",
		"why_it_matters": "The workflow will not move forward until the assigned approver reviews the queue item.",
		"action_now": "Open the approval queue now and approve or reject with a clear reason.",
		"owner": event["owner"],
		"recommended_fix": "Review quantities, routing, and urgency before approving so the workflow does not stall later.",
		"evidence": " | ".join(
			_unique_texts(
				[
					f"Queue: {queue_name}",
					f"Store: {store}",
					f"Priority: {_clean_text(facts.get('priority'))}",
					f"Dashboard: {dashboard_url}",
				]
			)
		),
		"urgency": _severity_label(event["severity"]),
		"event_count": 1,
	}


def _render_store_order_new(event: dict[str, Any]) -> dict[str, Any]:
	facts = event["facts"]
	order_name = _clean_text(facts.get("order_name"))
	store = _clean_text(facts.get("warehouse"), fallback=_clean_text(facts.get("store")))
	item_count = int(facts.get("item_count") or 0)
	is_emergency = bool(facts.get("is_emergency"))
	queue_status = _clean_text(facts.get("queue_status"), fallback="unknown")
	queue_name = _clean_text(facts.get("approval_queue_name"), fallback="")
	dashboard_url = _clean_text(
		facts.get("dashboard_url"), fallback=_portal_url("/dashboard/store-ops/order-approvals")
	)
	if queue_status in {"failed", "unmapped"}:
		action = "Fix the approval routing now so the order does not stall."
		recommended = "Repair the approver mapping or assignment failure before the cutoff window closes."
	else:
		action = "No action needed unless this is urgent or the approval queue stops moving."
		recommended = "Monitor the order approval queue and watch for routing gaps on emergency orders."
	return {
		"summary": f"New store order {order_name} was submitted from {store} for {item_count} items.",
		"why_it_matters": "Ops needs early visibility when emergency or approval-routing issues can delay dispatch.",
		"action_now": action,
		"owner": event["owner"],
		"recommended_fix": recommended,
		"evidence": " | ".join(
			_unique_texts(
				[
					f"Order: {order_name}",
					f"Store: {store}",
					f"Emergency: {'Yes' if is_emergency else 'No'}",
					f"Approval queue: {queue_name}" if queue_name and queue_name != "-" else "",
					f"Queue status: {queue_status}",
					f"Dashboard: {dashboard_url}",
				]
			)
		),
		"urgency": _severity_label(event["severity"]),
		"event_count": 1,
	}


def _render_store_order_approved(event: dict[str, Any]) -> dict[str, Any]:
	facts = event["facts"]
	order_name = _clean_text(facts.get("order_name"))
	stage = _clean_text(facts.get("stage"), fallback="approved")
	store = _clean_text(facts.get("store"), fallback=_clean_text(facts.get("warehouse")))
	if stage == "area_supervisor_forwarded":
		action = "Regional Manager should review and finalize the queued emergency order."
		recommended = "Approve or reject the forwarded emergency request so dispatch can proceed."
		why = "The order is still blocked until the second approval stage completes."
		summary = f"Store order {order_name} cleared Area Supervisor review and is waiting on Regional Manager sign-off."
		evidence = [
			f"Order: {order_name}",
			f"Store: {store}",
			f"Regional approver: {_clean_text(facts.get('regional_approver'))}",
			f"Dashboard: {_clean_text(facts.get('dashboard_url'), fallback=_portal_url('/dashboard/store-ops/order-approvals'))}",
		]
	else:
		action = "Warehouse should process the material request and the store can monitor dispatch."
		recommended = "Pick, stage, and dispatch the linked material request without waiting for another chat follow-up."
		why = "The order is approved and can now move into fulfilment."
		summary = (
			f"Store order {order_name} is approved and dispatch request {_clean_text(facts.get('material_request'))} is ready."
			if facts.get("material_request")
			else f"Store order {order_name} is approved."
		)
		evidence = [
			f"Order: {order_name}",
			f"Store: {store}",
			f"Approved by: {_clean_text(facts.get('approved_by'))}",
			f"Material Request: {_clean_text(facts.get('material_request'))}",
			f"Dashboard: {_clean_text(facts.get('dashboard_url'), fallback=_portal_url('/dashboard/store-ops/order-approvals'))}",
		]
	return {
		"summary": summary,
		"why_it_matters": why,
		"action_now": action,
		"owner": event["owner"],
		"recommended_fix": recommended,
		"evidence": " | ".join(_unique_texts(evidence)),
		"urgency": _severity_label(event["severity"]),
		"event_count": 1,
	}


def _render_discount_critical_digest(event: dict[str, Any]) -> dict[str, Any]:
	facts = event["facts"]
	rows = list(facts.get("rows") or [])
	business_date = _clean_text(facts.get("business_date"))
	store_names = _unique_texts(
		[(row or {}).get("store_name") for row in rows],
		limit=5,
	)
	top_clusters = []
	for row in rows[:5]:
		top_clusters.append(
			"{store} / {identity} / orders {orders}".format(
				store=_clean_text((row or {}).get("store_name")),
				identity=_clean_text((row or {}).get("identity_key")),
				orders=int((row or {}).get("order_count") or 0),
			)
		)
	return {
		"summary": f"Discount audit found {len(rows)} critical clusters for {business_date}.",
		"why_it_matters": "Potential SC/PWD abuse needs accounting review before the evidence trail gets colder and closeout confidence drops.",
		"action_now": "Open the discount-abuse queue now and validate the flagged receipts or identities.",
		"owner": event["owner"],
		"recommended_fix": "Clear false positives, escalate real abuse patterns, and mark reviewed rows so the same clusters do not linger unresolved.",
		"evidence": " | ".join(
			_unique_texts(
				[
					"Stores: " + ", ".join(store_names) if store_names else "",
					"Top clusters: " + "; ".join(top_clusters) if top_clusters else "",
					f"Review queue: {_clean_text(facts.get('review_url'), fallback=_portal_url('/dashboard/accounting/discount-abuse'))}",
				]
			)
		),
		"urgency": _severity_label(event["severity"]),
		"event_count": max(len(rows), 1),
	}


def _render_morning_readiness_digest(event: dict[str, Any]) -> dict[str, Any]:
	facts = event["facts"]
	status = _clean_text(facts.get("status"), fallback="yellow").lower()
	areas = list(facts.get("areas") or [])
	area_bits = []
	failed_lanes = []
	lane_diagnoses = []
	for area in areas:
		area_status = _clean_text((area or {}).get("status"), fallback="").lower()
		area_bits.append(
			"{label}: {status}".format(
				label=_clean_text((area or {}).get("label")),
				status=_clean_text((area or {}).get("status")),
			)
		)
		if area_status in ("red", "failed", "error"):
			failed_lanes.append(_clean_text((area or {}).get("label")))
			diagnosis = _diagnose_morning_lane(area)
			if diagnosis:
				lane_diagnoses.append(diagnosis)
	delta = _compute_delta_summary("morning_readiness_digest", facts, event.get("_previous_snapshot"))
	if status == "green":
		summary = f"Morning syncs are ready for operations for {_clean_text(facts.get('report_date'))}."
		action = "No action needed."
		recommended = "Keep monitoring the daily readiness report, but no manual recovery is needed."
		why = "Store ordering, warehouse inventory, and finance baselines all landed before the morning operating window."
	elif status == "red":
		summary = f"Morning syncs are not ready for {_clean_text(facts.get('report_date'))}."
		if failed_lanes:
			summary += f" Failing: {', '.join(failed_lanes)}."
		if delta:
			summary += f" {delta}"
		if lane_diagnoses:
			action = " ".join(lane_diagnoses)
		else:
			action = "Escalate the failing lane now and rerun the missed sync before teams rely on the data."
		recommended = "Open the morning sync report, recover the blocked lane, and clear the latest runtime error before 9:00 AM PHT."
		why = "At least one operational data lane missed the readiness target or failed outright."
	else:
		summary = f"Morning syncs landed with exceptions for {_clean_text(facts.get('report_date'))}."
		if delta:
			summary += f" {delta}"
		if lane_diagnoses:
			action = " ".join(lane_diagnoses)
		else:
			action = "Review the exception lane now and clear it before finance or ops uses the affected data."
		recommended = "Resolve the exception rows or rerun the incomplete lane so the day starts from a clean baseline."
		why = "The morning data is present, but at least one lane still needs operator attention."
	return {
		"summary": summary,
		"why_it_matters": why,
		"action_now": action,
		"owner": event["owner"],
		"recommended_fix": recommended,
		"evidence": " | ".join(
			_unique_texts(
				[
					"Areas: " + "; ".join(area_bits) if area_bits else "",
					f"Target: {_clean_text(facts.get('sync_target_pht_time'))}",
					f"Deadline: {_clean_text(facts.get('ready_deadline_pht_time'))}",
					f"Artifact: {_clean_text(facts.get('artifact_markdown_path'))}",
				]
			)
		),
		"urgency": _severity_label(event["severity"]),
		"event_count": max(len(areas), 1),
	}


RENDERERS = {
	"sheets_sync_critical": _render_sheets_sync_critical,
	"maintenance_sla_backlog": _render_maintenance_sla_backlog,
	"maintenance_status_update": _render_maintenance_status_update,
	"approval_queue_new": _render_approval_queue_new,
	"store_order_new": _render_store_order_new,
	"store_order_approved": _render_store_order_approved,
	"discount_critical_digest": _render_discount_critical_digest,
	"morning_readiness_digest": _render_morning_readiness_digest,
}


def build_notification_event(
	event: dict[str, Any],
	previous_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
	if not isinstance(event, dict):
		raise ValueError("Notification event must be a dict")
	family = _clean_text(event.get("family"), fallback="")
	if not family:
		raise ValueError("Notification event missing family")
	policy = get_notification_policy(family)
	facts = deepcopy(event.get("facts") or {})
	normalized = deepcopy(event)
	normalized["family"] = family
	normalized["facts"] = facts
	normalized.setdefault("source_system", "frappe")
	normalized.setdefault("requested_space", policy["default_space"])
	normalized.setdefault("delivery_class", policy["delivery_class"])
	normalized.setdefault("severity", policy["default_severity"])
	normalized.setdefault("owner", policy["owner"])
	normalized.setdefault("source_ref", _build_default_source_ref(family, facts))
	normalized.setdefault("dedup_key", _build_default_dedup_key(family, facts, normalized["source_ref"]))
	if previous_snapshot:
		normalized["_previous_snapshot"] = previous_snapshot
	brief = RENDERERS[family](normalized)
	normalized["brief"] = brief
	normalized["event_count"] = brief.get("event_count") or normalized.get("event_count") or 1
	normalized["fallback_text"] = normalized.get("fallback_text") or render_notification_text(normalized)
	normalized["_current_snapshot"] = _build_snapshot_for_cache(family, facts)
	normalized.pop("_previous_snapshot", None)
	return normalized


def validate_notification_event(event: dict[str, Any]) -> list[str]:
	errors: list[str] = []
	for field in REQUIRED_EVENT_FIELDS:
		value = event.get(field)
		if field == "facts" and isinstance(value, dict):
			continue
		if value in (None, "", []):
			errors.append(field)
	return errors


def render_notification_text(event: dict[str, Any]) -> str:
	brief = event.get("brief") or {}
	lines = [
		f"*{_clean_text(event.get('family')).replace('_', ' ').title()}*",
		"",
		"*Summary*",
		_clean_text(brief.get("summary")),
		"",
		"*Why this matters*",
		_clean_text(brief.get("why_it_matters")),
		"",
		"*Action now*",
		_clean_text(brief.get("action_now")),
		"",
		"*Owner*",
		_clean_text(brief.get("owner"), fallback=_clean_text(event.get("owner"))),
		"",
		"*Recommended fix*",
		_clean_text(brief.get("recommended_fix")),
		"",
		"*Evidence / source link*",
		_clean_text(brief.get("evidence"), fallback=_clean_text(event.get("source_ref"))),
		"",
		"*Urgency*",
		_clean_text(brief.get("urgency"), fallback=_severity_label(event.get("severity"))),
	]
	return "\n".join(lines).strip()
