# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BEIFeeCarveout(Document):
	"""S231 D-3-3: per-store franchise fee rate override.

	When `BEIBillingSchedule.calculate_fees` looks up a fee rate for a given
	(ownership_type, fee_type), it consults BEI Fee Carveout FIRST keyed by
	(store, fee_type). If a carveout exists, its `rate_override` replaces the
	BEI Fee Schedule rate.

	Used for one-off rates negotiated outside the standard schedule.
	Example: Vista Mall Management Fee = 2.00% (vs MF schedule's 2.50%).

	Source of truth for the carveout list:
	`data/_CLEANROOM/2026-04-09_franchise_agreements/05_Per_Store_Fee_Carveouts.md`

	Plan: docs/plans/2026-05-02-sprint-231-pricing-coupling-and-defaults-defense.md
	"""

	def validate(self) -> None:
		"""Reject invalid rate_override values and require a notes value."""
		if self.rate_override is None:
			frappe.throw(_("S231 D-3-3: Rate Override is required (decimal, e.g. 0.02 for 2%)."))
		if self.rate_override < 0 or self.rate_override > 1:
			frappe.throw(
				_(
					"S231 D-3-3: Rate Override must be between 0 and 1 (decimal form). "
					"Got {0}. Use 0.02 for 2%, not 2."
				).format(self.rate_override)
			)
		if not self.notes or not self.notes.strip():
			frappe.throw(
				_(
					"S231 D-3-3: Notes are required for audit trail. Cite the contract "
					"amendment / CEO directive that authorised the carveout."
				)
			)
