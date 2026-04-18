"""BEI Labor Allocation Log (S206 Phase 3).

Idempotency ledger for the S206 reliever labor cost-sharing engine. One row
per (year, month, employee) pairing. Unique index enforced in validate().

See docs/plans/2026-04-17-sprint-206-reliever-allocation-engine.md.
"""

from __future__ import annotations

import frappe
from frappe.model.document import Document


class BEILaborAllocationLog(Document):
	def validate(self):
		self._validate_period_unique_per_employee()

	def _validate_period_unique_per_employee(self):
		existing = frappe.db.get_value(
			"BEI Labor Allocation Log",
			{
				"year": self.year,
				"month": self.month,
				"employee": self.employee,
				"name": ["!=", self.name or ""],
			},
			"name",
		)
		if existing:
			frappe.throw(
				f"S206 Labor Allocation Log: entry for employee {self.employee} "
				f"period {int(self.year):04d}-{int(self.month):02d} already exists ({existing}). "
				f"Duplicate allocation blocked."
			)
