"""Whitelisted API for S206 reliever labor cost-sharing (Phase 3).

Two endpoints:

- ``preview_monthly_allocation(year, month)``
    Dry-run. Returns planned paired JEs for every in-scope Salary Slip in the
    period. No DB writes. Safe to call any time.

- ``post_monthly_allocation(year, month)``
    Apply path. Gated on ``S206_APPLY=1`` env var OR ``confirm=True`` kwarg.
    For each in-scope slip: checks BEI Labor Allocation Log for duplicate
    prevention (idempotency); creates paired JEs via
    :func:`hrms.utils.labor_allocation.allocate_slip`; records Log row.
    Per-slip savepoint — one bad slip does not kill the batch (DM-2).

Requires: S206 on-demand account seeder already ran
(hrms.on_demand.s206_seed_intercompany_accounts) + TP Policy signed by Finance.

Permission: Accounts Manager / CFO / System Manager for ``post_monthly_allocation``;
additionally Accounts User can call ``preview_monthly_allocation``.
"""

from __future__ import annotations

import calendar
import json
import os
from datetime import date

import frappe
from frappe import _

from hrms.utils.labor_allocation import allocate_slip
from hrms.utils.sentry import set_backend_observability_context

APPLY_ENV_VAR = "S206_APPLY"
LOG_DOCTYPE = "BEI Labor Allocation Log"

POST_ROLES = {"Accounts Manager", "CFO", "System Manager"}
PREVIEW_ROLES = POST_ROLES | {"Accounts User"}


def _apply_mode(confirm: bool = False) -> bool:
	if confirm:
		return True
	return os.environ.get(APPLY_ENV_VAR, "").strip() == "1"


def _period_bounds(year: int, month: int) -> tuple[date, date]:
	start = date(year, month, 1)
	last_day = calendar.monthrange(year, month)[1]
	end = date(year, month, last_day)
	return start, end


def _require_any_role(roles: set[str]) -> None:
	user_roles = set(frappe.get_roles(frappe.session.user))
	if not (user_roles & roles):
		frappe.throw(
			_("S206 labor allocation: user {0} lacks any of {1}").format(frappe.session.user, sorted(roles)),
			frappe.PermissionError,
		)


def _in_scope_slip_names(start: date, end: date) -> list[str]:
	"""Submitted Salary Slips whose period overlaps the month.

	A slip is in-scope if its start_date <= period_end AND end_date >= period_start.
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
		{"start": start, "end": end},
		as_dict=True,
	)
	return [r["name"] for r in rows]


def _existing_log(year: int, month: int, employee: str) -> str | None:
	return frappe.db.get_value(
		LOG_DOCTYPE,
		{"year": year, "month": month, "employee": employee},
		"name",
	)


@frappe.whitelist()
def preview_monthly_allocation(year: int | str, month: int | str) -> dict:
	"""Dry-run: return planned paired JEs for every in-scope slip in the month.

	Safe — no DB writes, no side effects.
	"""
	set_backend_observability_context(
		module="finance",
		action="preview_monthly_allocation",
		mutation_type="read",
		extras={"year": int(year), "month": int(month)},
	)
	_require_any_role(PREVIEW_ROLES)

	year_i, month_i = int(year), int(month)
	start, end = _period_bounds(year_i, month_i)
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
		"period": {"year": year_i, "month": month_i, "start": str(start), "end": str(end)},
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
def post_monthly_allocation(
	year: int | str,
	month: int | str,
	confirm: bool | int | str = False,
) -> dict:
	"""Apply paired-JE allocation for every in-scope slip in the month.

	Gated by ``S206_APPLY=1`` env var OR ``confirm=True`` kwarg.
	Per-slip savepoint; one bad slip does not kill the batch (DM-2).
	"""
	set_backend_observability_context(
		module="finance",
		action="post_monthly_allocation",
		mutation_type="create",
		extras={"year": int(year), "month": int(month)},
	)
	_require_any_role(POST_ROLES)

	if isinstance(confirm, str):
		confirm = confirm.strip().lower() in ("1", "true", "yes")
	if not _apply_mode(confirm=bool(confirm)):
		frappe.throw(
			_(
				"S206 post_monthly_allocation requires S206_APPLY=1 env var "
				"(or confirm=True kwarg). Use preview_monthly_allocation for dry-run."
			)
		)

	year_i, month_i = int(year), int(month)
	start, end = _period_bounds(year_i, month_i)
	slip_names = _in_scope_slip_names(start, end)

	applied: list[dict] = []
	skipped_idempotent: list[dict] = []
	skipped_other: list[dict] = []
	errors: list[dict] = []

	# Process each slip inside its own savepoint so one failure does not
	# roll back already-applied slips.
	for name in slip_names:
		# Idempotency: peek at Log before doing anything
		slip = frappe.db.get_value(
			"Salary Slip",
			name,
			["employee"],
			as_dict=True,
		)
		if not slip:
			errors.append({"slip": name, "error": "Salary Slip not found"})
			continue
		if _existing_log(year_i, month_i, slip["employee"]):
			skipped_idempotent.append({"slip": name, "employee": slip["employee"]})
			continue

		sp = f"s206_slip_{name.replace('-', '_')}"
		try:
			frappe.db.savepoint(sp)
			result = allocate_slip(name, dry_run=False)
			if result["status"] == "skipped":
				# Still write a no-op Log row so re-runs don't re-evaluate
				_record_log(year_i, month_i, slip["employee"], result)
				skipped_other.append(
					{
						"slip": name,
						"reason": result.get("reason"),
					}
				)
			elif result["status"] == "applied":
				_record_log(year_i, month_i, slip["employee"], result)
				applied.append(result)
			frappe.db.release_savepoint(sp)
		except Exception as exc:
			try:
				frappe.db.rollback(save_point=sp)
			except Exception:
				pass
			frappe.log_error(
				title=f"S206 post_monthly_allocation failed for slip {name}",
				message=f"year={year_i}, month={month_i}, error={exc}",
			)
			errors.append({"slip": name, "error": str(exc)})

	frappe.db.commit()

	return {
		"period": {"year": year_i, "month": month_i, "start": str(start), "end": str(end)},
		"applied": applied,
		"applied_count": len(applied),
		"skipped_idempotent": skipped_idempotent,
		"skipped_idempotent_count": len(skipped_idempotent),
		"skipped_other": skipped_other,
		"skipped_other_count": len(skipped_other),
		"errors": errors,
		"errors_count": len(errors),
	}


def _record_log(year: int, month: int, employee: str, result: dict) -> None:
	"""Insert a BEI Labor Allocation Log row for this (year, month, employee).

	Stores ALL home JEs (one per covered Company) in home_jes_json. Earlier
	version only stored the first pair's home_je, silently losing the rest
	and breaking forensic traceability for multi-cover relievers.
	"""
	pairs = result.get("pairs", [])
	home_jes = [p["home_je"] for p in pairs if p.get("home_je")]
	covered_jes = [p["covered_je"] for p in pairs if p.get("covered_je")]
	covered_companies = list({p["covered_company"] for p in pairs})
	total = sum(p.get("amount", 0) for p in pairs)
	shares: dict[str, float] = {}
	for p in pairs:
		shares[p["covered_company"]] = p.get("share", 0)

	start_date, end_date = _period_bounds(year, month)

	log = frappe.get_doc(
		{
			"doctype": LOG_DOCTYPE,
			"year": year,
			"month": month,
			"employee": employee,
			"period_start": start_date,
			"period_end": end_date,
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


def preview_monthly_allocation_scheduled() -> None:
	"""Cron wrapper: preview prior-month allocation and email the report.

	Registered in hooks.py scheduler_events.cron ``0 22 1 * *`` (first of month
	at 06:00 PHT). See S206 plan Phase 5.
	"""
	from datetime import datetime

	now = datetime.now()
	# Prior month
	year = now.year
	month = now.month - 1
	if month == 0:
		month = 12
		year -= 1

	set_backend_observability_context(
		module="finance",
		action="preview_monthly_allocation_scheduled",
		mutation_type="read",
		extras={"year": year, "month": month, "trigger": "cron"},
	)

	try:
		report = preview_monthly_allocation(year, month)
	except Exception as exc:
		frappe.log_error(
			title="S206 monthly preview cron failed",
			message=str(exc),
		)
		return

	# Email to Sam + Denise (configurable via BEI Settings in future)
	recipients = ["sam@bebang.ph"]
	subject = f"S206 monthly allocation preview — {year:04d}-{month:02d}"
	summary = (
		f"Period: {report['period']['start']} to {report['period']['end']}\n"
		f"Total Slips: {report['total_slips']}\n"
		f"Planned allocations: {report['planned_count']}\n"
		f"Skipped: {report['skipped_count']}\n"
		f"Errors: {report['errors_count']}\n\n"
		f"To apply:\n"
		f"  docker exec -e S206_APPLY=1 $BACKEND bench --site hq.bebang.ph execute "
		f"hrms.api.labor_allocation.post_monthly_allocation --kwargs "
		f'\'{{"year": {year}, "month": {month}}}\''
	)
	try:
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=f"<pre>{summary}</pre>",
			now=True,
		)
	except Exception as exc:
		frappe.log_error(
			title="S206 preview cron email failed",
			message=str(exc),
		)
