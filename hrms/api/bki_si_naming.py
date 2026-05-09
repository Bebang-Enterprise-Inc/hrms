"""S238 v2.2 — Autoname hook for BKI Sales Invoices.

Embeds the originating BEI Store Order # into the SI name so a Frappe list
view shows SI <-> Order linkage at a glance. Only acts when company is BKI;
non-BKI SIs fall back to whatever naming_series their doc carries.

BIR context: Frappe ERP is not BIR-accredited (no PTU CAS / PTU LL / EIS).
The Frappe-issued BKI->Store SI is a supplementary document in BIR terms;
the buyer's Input-VAT-eligible invoice comes from a separate BIR-registered
channel. See tmp/s238/BIR_SERIES_RESEARCH.md (CEO-approved 2026-05-08).
"""

from __future__ import annotations

import re

import frappe
from frappe.model.naming import make_autoname

_BKI_COMPANY = "BEBANG KITCHEN INC."
_ORDER_PATTERN = re.compile(r"^BEI-ORD-(\d{4})-(\d+)$")


def set_bki_si_name(doc, method=None):
	"""Frappe doc_event handler for Sales Invoice autoname.

	Algorithm:
	1. If company != BKI, return (Frappe falls back to naming_series).
	2. If custom_bei_store_order is empty/missing, name = MISC fallback.
	3. If custom_bei_store_order parses BEI-ORD-{YYYY}-{NNNNN}, count
	   existing SIs already linked to that order, set
	   doc.name = f"BKI-SI-{year}-{tail}-{count+1}".
	4. If parse fails, name = MISC fallback (defensive).
	"""
	if (doc.company or "").strip().upper() != _BKI_COMPANY:
		return  # non-BKI SIs unaffected

	order = (getattr(doc, "custom_bei_store_order", "") or "").strip()
	if not order:
		doc.name = make_autoname("BKI-SI-MISC-.YYYY.-.####")
		return

	m = _ORDER_PATTERN.match(order)
	if not m:
		doc.name = make_autoname("BKI-SI-MISC-.YYYY.-.####")
		return

	year, tail = m.group(1), m.group(2)

	# Count BKI SIs already linked to this same order.
	# Exclude doc itself in case Frappe re-runs autoname during validation.
	existing = frappe.db.count(
		"Sales Invoice",
		{
			"custom_bei_store_order": order,
			"company": _BKI_COMPANY,
			"name": ["!=", doc.name or ""],
		},
	)
	doc.name = f"BKI-SI-{year}-{tail}-{existing + 1}"
