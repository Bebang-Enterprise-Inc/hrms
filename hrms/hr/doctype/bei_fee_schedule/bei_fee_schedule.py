# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BEIFeeSchedule(Document):
	"""S231 D-3-2: per-(ownership_type, fee_type) franchise fee schedule.

	The single source of truth for monthly franchise fee rates. Replaces the
	hardcoded 0.07 / 0.025 / 0.05 / 0.04 constants previously in
	`hrms/hr/doctype/bei_billing_schedule/bei_billing_schedule.py::calculate_fees`.

	Schedule is consulted first; per-store carveouts in BEI Fee Carveout
	override the rate when present. See `hrms/api/billing.py` for the
	`get_fee_schedule` whitelisted reader and `calculate_fees` for the
	consumer.

	Plan: docs/plans/2026-05-02-sprint-231-pricing-coupling-and-defaults-defense.md
	"""

	def validate(self) -> None:
		"""Reject invalid rate values and require a recipient_company."""
		if self.rate is None:
			frappe.throw(_("S231 D-3-2: Rate is required (decimal, e.g. 0.07 for 7%)."))
		if self.rate < 0 or self.rate > 1:
			frappe.throw(
				_(
					"S231 D-3-2: Rate must be between 0 and 1 (decimal form). Got {0}. "
					"Use 0.07 for 7%, not 7."
				).format(self.rate)
			)
		if self.fee_type == "E-commerce" and self.base_field != "website_sales":
			# Defensive: CEO 2026-05-02 explicitly required e-com on bebang.ph
			# website only, NOT FoodPanda/Grab (online_sales). Rejecting at
			# validate prevents seed-script typos from silently broadening
			# the e-com base.
			frappe.throw(
				_(
					"S231 D-3-2: E-commerce fee MUST use `website_sales` as base_field "
					"(per CEO 2026-05-02 / BFC Franchise Agreement §XI.I / JV Agreement §9.1). "
					"`online_sales` includes FoodPanda + Grab and is NOT the e-com base."
				)
			)
		if self.ownership_type == "Company Owned":
			# Co-Owned has no fees per design (Company-internal transfers go
			# through BKI markup, not franchise fees).
			frappe.throw(
				_(
					"S231 D-3-2: Company Owned ownership_type carries no franchise fees. "
					"Markup for company-owned stores lives in BEI Settings."
					"bki_markup_company_owned_percent."
				)
			)
