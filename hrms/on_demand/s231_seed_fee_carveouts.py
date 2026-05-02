# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
"""S231 D-3-4: idempotent seed for `BEI Fee Carveout` rows.

Per-store overrides to the standard BEI Fee Schedule rates. Each carveout
must cite the contract amendment / CEO directive that authorised it.

Source of truth:
    data/_CLEANROOM/2026-04-09_franchise_agreements/05_Per_Store_Fee_Carveouts.md

Run:
    bench --site hq.bebang.ph execute hrms.on_demand.s231_seed_fee_carveouts.run
"""

from __future__ import annotations

import frappe

# Format: (store, fee_type, rate_override, effective_from, notes)
CARVEOUT_ROWS = [
	(
		"Vista Mall",
		"Management",
		0.02,
		"2025-11-01",
		"Per CEO directive 2026-05-02; reason: Vista Mall handles own accounting + "
		"taxes. Verified against Nov 2025 actuals (back-calculated). Standard MF "
		"rate is 2.5% gross — this carveout reduces to 2.00% gross for Vista Mall.",
	),
]


def run() -> dict:
	"""Idempotent seed. Skips Carveout rows whose target Department doesn't exist."""
	created = 0
	updated = 0
	skipped_no_store = 0
	errors: list[dict] = []

	for store, fee_type, rate_override, effective_from, notes in CARVEOUT_ROWS:
		# Resolve store via Department lookup (may match by name OR by department_name)
		store_dept = frappe.db.get_value("Department", store, "name") or frappe.db.get_value(
			"Department", {"department_name": store}, "name"
		)
		if not store_dept:
			skipped_no_store += 1
			errors.append({"store": store, "error": "Department not found"})
			continue

		docname = f"{store_dept}-{fee_type}"
		try:
			if frappe.db.exists("BEI Fee Carveout", docname):
				doc = frappe.get_doc("BEI Fee Carveout", docname)
				dirty = False
				for field, value in (
					("rate_override", rate_override),
					("effective_from", effective_from),
					("notes", notes),
				):
					if doc.get(field) != value:
						doc.set(field, value)
						dirty = True
				if dirty:
					doc.flags.ignore_permissions = True
					doc.save()
					updated += 1
			else:
				doc = frappe.new_doc("BEI Fee Carveout")
				doc.store = store_dept
				doc.fee_type = fee_type
				doc.rate_override = rate_override
				doc.effective_from = effective_from
				doc.notes = notes
				doc.flags.ignore_permissions = True
				doc.insert()
				created += 1
		except Exception as e:
			errors.append({"store": store, "fee_type": fee_type, "error": str(e)})

	frappe.db.commit()
	return {
		"created": created,
		"updated": updated,
		"skipped_no_store": skipped_no_store,
		"total_rows": len(CARVEOUT_ROWS),
		"errors": errors,
	}
