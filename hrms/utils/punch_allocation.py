"""Shift-share allocation from Employee Checkin (S206 Phase 1).

Computes what fraction of an employee's shifts in a given date range fell at
each store Company. Source: `tabEmployee Checkin` via ADMS push sync. Uses
`device_store_bridge.resolve_device_company` to map device -> Company.

Shift-share basis (per LD-8): a "shift" is a paired IN+OUT punch at the same
device on the same day. Orphan INs (no matching OUT in the period) count as
half shifts. Orphan OUTs are dropped.

Returns a dict `{company_name: share_0_to_1}` that sums to 1.0 (or empty if
zero shifts). Callers use this to split `Salary Slip.gross_pay` across
covered Companies for paired-JE cost-sharing (see labor_allocation.py).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

import frappe

from hrms.utils.device_store_bridge import (
	UnknownDeviceCompany,
	resolve_device_company,
)

# Frappe Employee Checkin log_type values
LOG_TYPE_IN = "IN"
LOG_TYPE_OUT = "OUT"


def compute_shift_share(
	employee: str,
	start_date: date | str,
	end_date: date | str,
	department: str | None = None,
) -> dict[str, float]:
	"""Return `{company_name: share}` for an employee's shifts in the period.

	Shares are normalized to sum to 1.0. Empty dict if no valid shifts.

	Args:
	    employee: Frappe Employee docname.
	    start_date, end_date: date range inclusive (ISO strings or date objects).
	    department: Employee.department — used only to disambiguate bare
	        SHAW COMMISSARY branches (Commissary dept -> BKI, else -> BEI parent).

	Returns:
	    dict[company_name, share]. Shares are floats 0.0-1.0 summing to 1.0.
	"""
	shifts_by_company = compute_shifts_by_store(employee, start_date, end_date, department=department)
	total = sum(shifts_by_company.values())
	if total <= 0:
		return {}
	return {c: cnt / total for c, cnt in shifts_by_company.items()}


def compute_shifts_by_store(
	employee: str,
	start_date: date | str,
	end_date: date | str,
	department: str | None = None,
) -> dict[str, float]:
	"""Return raw shift counts per store Company (not normalized).

	Half-shift counts (orphan INs) are included.
	"""
	checkins = _fetch_checkins(employee, start_date, end_date)
	paired = _pair_punches(checkins)

	shifts: dict[str, float] = {}
	for shift in paired:
		device_sn = shift["device_id"]
		try:
			company = resolve_device_company(device_sn, department=department)
		except UnknownDeviceCompany as exc:
			# Log but don't fail the whole allocation — one bad punch shouldn't
			# poison the month. Operator fixes the device mapping and re-runs.
			_log_warn(f"S206 punch_allocation: skipping unresolvable device for employee {employee!r}: {exc}")
			continue
		shifts[company] = shifts.get(company, 0.0) + shift["weight"]
	return shifts


def _fetch_checkins(employee: str, start_date, end_date) -> list[dict]:
	"""Query tabEmployee Checkin for `employee` in the date range.

	Uses correct Frappe field names: `time` (not `event_time`), `device_id`
	(not `device_sn`), `log_type`. See S206 audit B8 for the mismatch.
	"""
	rows = frappe.db.sql(
		"""
        SELECT
            name,
            time,
            device_id,
            log_type
        FROM `tabEmployee Checkin`
        WHERE employee = %(employee)s
          AND time >= %(start)s
          AND time < DATE_ADD(%(end)s, INTERVAL 1 DAY)
        ORDER BY time ASC
        """,
		{"employee": employee, "start": start_date, "end": end_date},
		as_dict=True,
	)
	return rows


def _pair_punches(checkins: list[dict]) -> list[dict]:
	"""Pair IN punches with the next OUT on the same device/day.

	Returns shifts: list of dicts with `device_id` + `weight` (1.0 for paired,
	0.5 for orphan IN, 0 dropped for orphan OUT).
	"""
	shifts: list[dict] = []
	# Group by (device_id, date)
	by_device_day: dict[tuple[str, date], list[dict]] = {}
	for row in checkins:
		t = row["time"]
		# Frappe returns datetime; normalize
		if isinstance(t, str):
			t = datetime.fromisoformat(t)
		day = t.date() if isinstance(t, datetime) else t
		key = (row["device_id"] or "", day)
		by_device_day.setdefault(key, []).append({**row, "time": t})

	for (device_id, _day), day_rows in by_device_day.items():
		if not device_id:
			# Orphan punches with no device id — skip
			continue
		# Sort within the day (already sorted by outer SQL but be defensive)
		day_rows.sort(key=lambda r: r["time"])
		# Walk and pair: IN then next OUT = 1 full shift; orphan IN = 0.5.
		pending_in = None
		for row in day_rows:
			log_type = (row.get("log_type") or "").upper()
			if log_type == LOG_TYPE_IN:
				if pending_in is not None:
					# Two INs in a row — treat the first as a half shift
					shifts.append({"device_id": device_id, "weight": 0.5})
				pending_in = row
			elif log_type == LOG_TYPE_OUT:
				if pending_in is not None:
					shifts.append({"device_id": device_id, "weight": 1.0})
					pending_in = None
				# Orphan OUT — dropped
		if pending_in is not None:
			# Day ended with IN but no OUT — half shift
			shifts.append({"device_id": device_id, "weight": 0.5})

	return shifts


def _log_warn(message: str) -> None:
	try:
		frappe.logger().warning(message)
	except Exception:
		pass
