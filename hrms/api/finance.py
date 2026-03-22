"""Finance API compatibility surface used by my.bebang.ph."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

ALLOWED_ROLES = ["HR Manager", "System Manager", "HR User", "Area Supervisor", "Accounts User"]


def _require_access() -> None:
	"""Enforce role-based access for finance dashboard endpoints."""
	frappe.only_for(ALLOWED_ROLES)


def _coerce_month_year(month: Any = None, year: Any = None) -> tuple[int, int]:
	"""Normalize optional month/year inputs with sane bounds."""
	today = getdate(nowdate())
	normalized_month = cint(month) if month is not None else cint(today.month)
	normalized_year = cint(year) if year is not None else cint(today.year)

	if normalized_month < 1 or normalized_month > 12:
		frappe.throw(_("Month must be between 1 and 12."), exc=frappe.ValidationError)
	if normalized_year < 2000 or normalized_year > 2100:
		frappe.throw(_("Year must be between 2000 and 2100."), exc=frappe.ValidationError)

	return normalized_month, normalized_year


def _build_empty_store_row(store: str = "ALL") -> dict[str, Any]:
	return {
		"store": store,
		"store_name": store,
		"revenue": 0.0,
		"cogs": 0.0,
		"gross_profit": 0.0,
		"opex": 0.0,
		"payroll": 0.0,
		"other_expenses": 0.0,
		"net_income": 0.0,
		"net_margin": 0.0,
	}


@frappe.whitelist(allow_guest=False)
def get_consolidated_summary(
	month: int | str | None = None, year: int | str | None = None, store: str | None = None
) -> dict[str, Any]:
	"""Return consolidated finance summary aligned with portal contract."""
	_require_access()
	normalized_month, normalized_year = _coerce_month_year(month, year)
	period_label = f"{normalized_year}-{normalized_month:02d}"

	summary: dict[str, Any] = {
		"period_label": period_label,
		"total_revenue": 0.0,
		"total_cogs": 0.0,
		"gross_profit": 0.0,
		"total_opex": 0.0,
		"total_payroll": 0.0,
		"total_other": 0.0,
		"net_income": 0.0,
		"store_count": 1 if store else 0,
		"stores": [_build_empty_store_row(store)] if store else [],
	}

	# Best-effort enrichment using existing procurement analytics.
	try:
		from hrms.api import procurement

		kpis = procurement.get_dashboard_kpis() or {}
		summary["total_opex"] = flt(kpis.get("mtd_po_value", 0), 2)
		summary["total_other"] = flt(kpis.get("total_outstanding", 0), 2)
		summary["net_income"] = round(
			summary["total_revenue"]
			- summary["total_cogs"]
			- summary["total_opex"]
			- summary["total_payroll"]
			- summary["total_other"],
			2,
		)
	except Exception:
		# Keep API contract stable even when optional analytics fail.
		pass

	return summary


@frappe.whitelist(allow_guest=False)
def get_finance_kpis(
	period: str | None = None, month: int | str | None = None, year: int | str | None = None
) -> dict[str, Any]:
	"""Return KPI cards aligned with portal hooks."""
	_require_access()
	summary = get_consolidated_summary(month=month, year=year)
	total_expenses = flt(
		summary.get("total_cogs", 0)
		+ summary.get("total_opex", 0)
		+ summary.get("total_payroll", 0)
		+ summary.get("total_other", 0),
		2,
	)

	return {
		"total_revenue": flt(summary.get("total_revenue", 0), 2),
		"total_expenses": total_expenses,
		"net_income": flt(summary.get("net_income", 0), 2),
		"cash_position": 0.0,
		"period_label": period or summary.get("period_label"),
	}


@frappe.whitelist(allow_guest=False)
def get_store_pnl_summary(month: int | str, year: int | str) -> list[dict[str, Any]]:
	"""Return store-level P&L rows."""
	_require_access()
	summary = get_consolidated_summary(month=month, year=year)
	rows = summary.get("stores") or []
	if rows:
		return rows
	return [_build_empty_store_row()]


@frappe.whitelist(allow_guest=False)
def generate_monthly_report(
	month: int | str, year: int | str, store: str | None = None
) -> dict[str, Any]:
	"""Return monthly report payload scaffold compatible with portal expectations."""
	_require_access()
	normalized_month, normalized_year = _coerce_month_year(month, year)
	summary = get_consolidated_summary(month=normalized_month, year=normalized_year, store=store)

	return {
		"month": normalized_month,
		"year": normalized_year,
		"period_label": summary.get("period_label"),
		"revenue_by_store": [],
		"revenue_by_channel": [],
		"cogs_by_category": [],
		"opex_by_category": [],
		"summary": summary,
		"generated_at_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
	}
