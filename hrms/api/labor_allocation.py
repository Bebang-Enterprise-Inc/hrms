"""Whitelisted API for BEI reliever labor cost-sharing (S206 + S207).

Two endpoints:

- ``preview_allocation(period_start, period_end)``
    Dry-run. Returns planned paired JEs for every in-scope Salary Slip whose
    period overlaps [period_start, period_end]. No DB writes. Safe to call any
    time. Accepts any date range — half-month for Bimonthly cadence, full
    month for ad-hoc Q2 reporting.

- ``post_allocation(period_start, period_end, confirm=False)``
    Apply path. Gated on ``S206_APPLY=1`` env var OR ``confirm=True`` kwarg.
    Per-slip savepoint (DM-2). Idempotency keyed on ``slip_name`` (one Log row
    per Salary Slip — LD-14): ad-hoc full-month runs see half-month runs'
    Logs and skip them; no double-post.

Phase ordering note: S207 Phase 1 replaces the S206 ``(year, month)`` API with
this ``(period_start, period_end)`` form. There is no shim — CEO directive
2026-04-19 ("I need long term solution that is sustainable"). The
``preview_scheduled`` cron wrapper is installed in S207 Phase 5.

Requires: S206 on-demand account seeder already ran on every in-scope Company
+ TP Policy v1.2 active (see docs/compliance/s206-transfer-pricing-policy.md).

Permission: Accounts Manager / CFO / System Manager for ``post_allocation``;
additionally Accounts User can call ``preview_allocation``.
"""

from __future__ import annotations

import json
import os

# Module-level datetime imports — function-local imports defeat unittest.mock
# and freezegun, which S207 Phase 7 needs to test the preview_scheduled day
# guard (LD-16). Keep these at the module top so tests can patch them.
from datetime import date, datetime, timedelta, timezone

import frappe
from frappe import _

from hrms.utils.labor_allocation import allocate_slip, posting_date_for_slip
from hrms.utils.sentry import set_backend_observability_context

APPLY_ENV_VAR = "S206_APPLY"
LOG_DOCTYPE = "BEI Labor Allocation Log"

POST_ROLES = {"Accounts Manager", "CFO", "System Manager"}
PREVIEW_ROLES = POST_ROLES | {"Accounts User"}

# Philippines Time offset — used by preview_scheduled day-guard.
PHT = timezone(timedelta(hours=8))


def _apply_mode(confirm: bool = False) -> bool:
	if confirm:
		return True
	return os.environ.get(APPLY_ENV_VAR, "").strip() == "1"


def _coerce_date(value) -> date:
	"""Accept date / datetime / ISO string; return a ``date``."""
	if isinstance(value, datetime):
		return value.date()
	if isinstance(value, date):
		return value
	if isinstance(value, str):
		return date.fromisoformat(value[:10])
	frappe.throw(_("S207 allocation: unparseable date value {0}").format(value))


def _require_any_role(roles: set[str]) -> None:
	user_roles = set(frappe.get_roles(frappe.session.user))
	if not (user_roles & roles):
		frappe.throw(
			_("S206 labor allocation: user {0} lacks any of {1}").format(frappe.session.user, sorted(roles)),
			frappe.PermissionError,
		)


def _in_scope_slip_names(period_start: date, period_end: date) -> list[str]:
	"""Submitted Salary Slips whose period overlaps [period_start, period_end].

	A slip is in-scope iff ``slip.start_date <= period_end`` AND
	``slip.end_date >= period_start``. Matches S206 semantics; the caller
	decides the period (half-month for Bimonthly cadence, full month for ad-hoc
	Q2 reporting).
	"""
	rows = frappe.db.sql(
		"""
		SELECT name
		FROM `tabSalary Slip`
		WHERE docstatus = 1
		  AND start_date <= %(end)s
		  AND end_date >= %(start)s
		ORDER BY employee, name
		""",
		{"start": period_start, "end": period_end},
		as_dict=True,
	)
	return [r["name"] for r in rows]


def _existing_log(slip_name: str) -> str | None:
	"""LD-14: idempotency keyed on ``slip_name``, not period.

	One Log row per Salary Slip — prevents double-posting when Sam runs ad-hoc
	full-month queries (e.g. ``preview_allocation(2026-04-01, 2026-04-30)``)
	after per-half-month runs (April 1-15, April 16-30). The full-month pass
	iterates over the same Slips; each Slip already has a Log row and is
	skipped as idempotent.
	"""
	return frappe.db.get_value(LOG_DOCTYPE, {"slip_name": slip_name}, "name")


@frappe.whitelist()
def preview_allocation(period_start, period_end) -> dict:
	"""Dry-run: return planned paired JEs for every in-scope slip in the period.

	Safe — no DB writes, no side effects.
	"""
	start = _coerce_date(period_start)
	end = _coerce_date(period_end)
	set_backend_observability_context(
		module="finance",
		action="preview_allocation",
		mutation_type="read",
		extras={"period_start": str(start), "period_end": str(end)},
	)
	_require_any_role(PREVIEW_ROLES)

	slip_names = _in_scope_slip_names(start, end)

	planned: list[dict] = []
	skipped: list[dict] = []
	errors: list[dict] = []

	for name in slip_names:
		try:
			result = allocate_slip(name, dry_run=True)
		except Exception as exc:
			errors.append({"slip": name, "error": str(exc)})
			continue
		if result["status"] == "skipped":
			skipped.append({"slip": name, "reason": result.get("reason")})
		else:
			planned.append(result)

	return {
		"period": {"start": str(start), "end": str(end)},
		"total_slips": len(slip_names),
		"planned_count": len(planned),
		"skipped_count": len(skipped),
		"errors_count": len(errors),
		"planned": planned,
		"skipped": skipped,
		"errors": errors,
		"dry_run": True,
	}


@frappe.whitelist()
def post_allocation(period_start, period_end, confirm: bool | int | str = False) -> dict:
	"""Apply paired-JE allocation for every in-scope slip in the period.

	Gated by ``S206_APPLY=1`` env var OR ``confirm=True`` kwarg.
	Per-slip savepoint; one bad slip does not kill the batch (DM-2).
	Idempotent: Slips with an existing Log row are skipped (LD-14).
	"""
	start = _coerce_date(period_start)
	end = _coerce_date(period_end)
	set_backend_observability_context(
		module="finance",
		action="post_allocation",
		mutation_type="create",
		extras={"period_start": str(start), "period_end": str(end)},
	)
	_require_any_role(POST_ROLES)

	if isinstance(confirm, str):
		confirm = confirm.strip().lower() in ("1", "true", "yes")
	if not _apply_mode(confirm=bool(confirm)):
		frappe.throw(
			_(
				"S207 post_allocation requires S206_APPLY=1 env var "
				"(or confirm=True kwarg). Use preview_allocation for dry-run."
			)
		)

	slip_names = _in_scope_slip_names(start, end)

	applied: list[dict] = []
	skipped_idempotent: list[dict] = []
	skipped_other: list[dict] = []
	errors: list[dict] = []

	for name in slip_names:
		slip_info = frappe.db.get_value(
			"Salary Slip",
			name,
			["employee", "start_date", "end_date"],
			as_dict=True,
		)
		if not slip_info:
			errors.append({"slip": name, "error": "Salary Slip not found"})
			continue
		if _existing_log(name):
			skipped_idempotent.append({"slip": name, "employee": slip_info["employee"]})
			continue

		sp = f"s207_slip_{name.replace('-', '_')}"
		try:
			frappe.db.savepoint(sp)
			result = allocate_slip(name, dry_run=False)
			if result["status"] == "skipped":
				_record_log(name, slip_info, result)
				skipped_other.append({"slip": name, "reason": result.get("reason")})
			elif result["status"] == "applied":
				_record_log(name, slip_info, result)
				applied.append(result)
			frappe.db.release_savepoint(sp)
		except Exception as exc:
			try:
				frappe.db.rollback(save_point=sp)
			except Exception:
				pass
			frappe.log_error(
				title=f"S207 post_allocation failed for slip {name}",
				message=f"period={start}..{end}, error={exc}",
			)
			errors.append({"slip": name, "error": str(exc)})

	# Batch commit — per-slip savepoints only give rollback isolation; without
	# this commit a later unrelated exception could roll back the whole batch.
	frappe.db.commit()  # nosemgrep: frappe-manual-commit -- intentional batch persist; see docstring

	return {
		"period": {"start": str(start), "end": str(end)},
		"applied": applied,
		"applied_count": len(applied),
		"skipped_idempotent": skipped_idempotent,
		"skipped_idempotent_count": len(skipped_idempotent),
		"skipped_other": skipped_other,
		"skipped_other_count": len(skipped_other),
		"errors": errors,
		"errors_count": len(errors),
	}


def _record_log(slip_name: str, slip_info: dict, result: dict) -> None:
	"""Insert a BEI Labor Allocation Log row for this Salary Slip.

	LD-14: ``slip_name`` is the unique axis. ``period_start`` / ``period_end``
	are informational — they match the slip's own period (not the API call's
	period) so full-month and half-month API calls for the same slip converge
	on identical Log row content.
	"""
	pairs = result.get("pairs", [])
	home_jes = [p["home_je"] for p in pairs if p.get("home_je")]
	covered_jes = [p["covered_je"] for p in pairs if p.get("covered_je")]
	covered_companies = list({p["covered_company"] for p in pairs})
	total = sum(p.get("amount", 0) for p in pairs)
	shares: dict[str, float] = {}
	for p in pairs:
		shares[p["covered_company"]] = p.get("share", 0)

	log = frappe.get_doc(
		{
			"doctype": LOG_DOCTYPE,
			"slip_name": slip_name,
			"employee": slip_info["employee"],
			"period_start": slip_info["start_date"],
			"period_end": slip_info["end_date"],
			"home_company": result.get("home_company"),
			"covered_companies": json.dumps(covered_companies),
			"home_jes_json": json.dumps(home_jes),
			"covered_jes_json": json.dumps(covered_jes),
			"total_allocated": total,
			"shift_shares_json": json.dumps(shares),
		}
	)
	log.insert(ignore_permissions=True)


# --- Scheduled wrapper -----------------------------------------------------
# Installed by S207 Phase 5 (see hrms/hooks.py scheduler_events.cron
# "0 22 * * *"). Phase 1 leaves the function undefined so nothing fires
# during the phase-1-to-phase-4 gap; Phase 5 adds it back with the
# Bimonthly day-guard and the new (period_start, period_end) signature.
