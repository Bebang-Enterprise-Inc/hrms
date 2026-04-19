"""BEI Labor Allocation Log (S206 Phase 3 + S207 Phase 2).

Idempotency ledger for the reliever labor cost-sharing engine. Unique axis is
the Salary Slip (LD-14): one Log row per Slip. Ad-hoc full-month runs see
half-month runs' rows and skip them — no double-post.

See docs/plans/2026-04-19-sprint-207-semi-monthly-allocation-and-coa-completion.md.
"""

from __future__ import annotations

import frappe
from frappe.model.document import Document


class BEILaborAllocationLog(Document):
	def validate(self):
		self._validate_slip_unique()

	def _validate_slip_unique(self):
		"""S207 LD-14: one Log row per Salary Slip.

		The DB unique index (`idx_slip_employee`) is the ultimate guard, but the
		Python validate() runs first and gives a clearer error message than the
		raw MySQL duplicate-key error. Catches both new Slips and edits that
		would collide with an existing row.
		"""
		if not self.slip_name:
			frappe.throw("BEI Labor Allocation Log: slip_name is required (S207 LD-14).")
		existing = frappe.db.get_value(
			"BEI Labor Allocation Log",
			{
				"slip_name": self.slip_name,
				"name": ["!=", self.name or ""],
			},
			"name",
		)
		if existing:
			frappe.throw(
				f"BEI Labor Allocation Log: Salary Slip {self.slip_name} already has "
				f"an allocation log ({existing}). LD-14: one Log row per Salary Slip — "
				f"idempotency prevents full-month reruns from double-posting half-period slips."
			)
