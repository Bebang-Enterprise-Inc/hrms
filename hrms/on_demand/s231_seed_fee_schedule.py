# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
"""S231 D-3-4: idempotent seed for `BEI Fee Schedule` rows.

Rates per CEO 2026-05-02 + cleanroom franchise contract documents:
  - JV Marketing: 5% of gross_sales → BEI
  - JV E-com: 5% of website_sales → BEI
  - Managed Franchise Royalty: 7% of net_sales_ex_vat → BFC
  - Managed Franchise Marketing: 5% of net_sales_ex_vat → BFC
  - Managed Franchise Management: 2.5% of gross_sales → BFC
  - Managed Franchise E-com: 5% of website_sales → BFC
  - Full Franchise Royalty: 7% of net_sales_ex_vat → BFC
  - Full Franchise Marketing: 5% of net_sales_ex_vat → BFC
  - Full Franchise E-com: 5% of website_sales → BFC

Co-Owned: NO franchise fees (BKI markup applies via bki_markup_company_owned_percent).

Run:
    bench --site hq.bebang.ph execute hrms.on_demand.s231_seed_fee_schedule.run

Sources:
  - data/_CLEANROOM/2026-04-09_franchise_agreements/01_JV_Agreement_Grand_Central_Gabaldon.md §9.1
  - data/_CLEANROOM/2026-04-09_franchise_agreements/02_Franchise_Management_Agreement_BFC.md
  - data/_CLEANROOM/2026-04-09_franchise_agreements/03_Franchise_Agreement_BFC.md §XI/XIII
  - data/_CLEANROOM/2026-04-09_franchise_agreements/06_CEO_Approvals_2026-05-02.md
"""

from __future__ import annotations

import frappe

# Single source of truth for all seeded rows. Edit here, re-run, idempotent.
# Format: (ownership_type, fee_type, rate, base_field, recipient_company, notes)
SCHEDULE_ROWS = [
	(
		"JV", "Marketing", 0.05, "gross_sales", "Bebang Enterprise Inc.",
		"JV Agreement §9.1: 5% of gross sales as Marketing Fee → BEI.",
	),
	(
		"JV", "E-commerce", 0.05, "website_sales", "Bebang Enterprise Inc.",
		"JV Agreement §9.1 + CEO 2026-05-02: 5% of bebang.ph website sales → BEI. "
		"NOT FoodPanda/Grab (online_sales).",
	),
	(
		"Managed Franchise", "Royalty", 0.07, "net_sales_ex_vat",
		"BEBANG FRANCHISE CORP.",
		"BFC Franchise Agreement §XIII.A: 7% royalty on net sales (ex-VAT) → BFC. "
		"Verified back-calculated against 18 stores Nov 2025.",
	),
	(
		"Managed Franchise", "Marketing", 0.05, "net_sales_ex_vat",
		"BEBANG FRANCHISE CORP.",
		"BFC Franchise Agreement §XI: 5% marketing on net sales (ex-VAT) → BFC.",
	),
	(
		"Managed Franchise", "Management", 0.025, "gross_sales",
		"BEBANG FRANCHISE CORP.",
		"BFC Franchise Management Agreement: 2.5% mgmt fee on gross sales → BFC. "
		"Per-store carveouts (e.g. Vista Mall 2.0%) live in BEI Fee Carveout.",
	),
	(
		"Managed Franchise", "E-commerce", 0.05, "website_sales",
		"BEBANG FRANCHISE CORP.",
		"BFC Franchise Agreement §XI.I + CEO 2026-05-02: 5% of bebang.ph website sales → BFC. "
		"NOT FoodPanda/Grab.",
	),
	(
		"Full Franchise", "Royalty", 0.07, "net_sales_ex_vat",
		"BEBANG FRANCHISE CORP.",
		"BFC Franchise Agreement §XIII.A: 7% royalty on net sales (ex-VAT) → BFC.",
	),
	(
		"Full Franchise", "Marketing", 0.05, "net_sales_ex_vat",
		"BEBANG FRANCHISE CORP.",
		"BFC Franchise Agreement §XI: 5% marketing on net sales (ex-VAT) → BFC.",
	),
	(
		"Full Franchise", "E-commerce", 0.05, "website_sales",
		"BEBANG FRANCHISE CORP.",
		"BFC Franchise Agreement §XI.I + CEO 2026-05-02: 5% of bebang.ph website sales → BFC. "
		"NOT FoodPanda/Grab.",
	),
]


def run() -> dict:
	"""Idempotent seed. Returns counts for closeout evidence capture."""
	created = 0
	updated = 0
	errors: list[dict] = []

	for ownership, fee_type, rate, base, recipient, notes in SCHEDULE_ROWS:
		docname = f"{ownership}-{fee_type}"
		try:
			if frappe.db.exists("BEI Fee Schedule", docname):
				doc = frappe.get_doc("BEI Fee Schedule", docname)
				dirty = False
				for field, value in (
					("rate", rate),
					("base_field", base),
					("recipient_company", recipient),
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
				doc = frappe.new_doc("BEI Fee Schedule")
				doc.ownership_type = ownership
				doc.fee_type = fee_type
				doc.rate = rate
				doc.base_field = base
				doc.recipient_company = recipient
				doc.notes = notes
				doc.flags.ignore_permissions = True
				doc.insert()
				created += 1
		except Exception as e:
			errors.append({"key": docname, "error": str(e)})

	frappe.db.commit()
	return {
		"created": created,
		"updated": updated,
		"total_rows": len(SCHEDULE_ROWS),
		"errors": errors,
	}
