#!/usr/bin/env python3
"""S231 Phase E-4: rename `Bebang FTE Inc.` references in production
Customer/Supplier/Address records to `BEBANG FT INC.` (canonical).

Operates on string fields only — does NOT rename docnames (no
frappe.rename_doc). For docname renames a separate step would be needed.
"""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

OLD = "Bebang FTE Inc."
NEW = "BEBANG FT INC."

PROBE = (
	PAYLOAD_PREAMBLE
	+ f"""
old = {OLD!r}
new = {NEW!r}

result = {{"old": old, "new": new}}

# Probe Customer
result["customer_matches"] = frappe.db.sql(
    "SELECT name, customer_name, tax_id FROM `tabCustomer` WHERE customer_name LIKE %s OR name LIKE %s LIMIT 50",
    (f"%{{old}}%", f"%{{old}}%"),
    as_dict=True,
)
result["supplier_matches"] = frappe.db.sql(
    "SELECT name, supplier_name FROM `tabSupplier` WHERE supplier_name LIKE %s OR name LIKE %s LIMIT 50",
    (f"%{{old}}%", f"%{{old}}%"),
    as_dict=True,
)
result["address_matches"] = frappe.db.sql(
    "SELECT name, address_title FROM `tabAddress` WHERE address_title LIKE %s OR name LIKE %s LIMIT 50",
    (f"%{{old}}%", f"%{{old}}%"),
    as_dict=True,
)

# Update Customer.customer_name (string field — safe SQL UPDATE)
cust_count = frappe.db.sql(
    "SELECT COUNT(*) FROM `tabCustomer` WHERE customer_name LIKE %s",
    (f"%{{old}}%",),
)[0][0]
if cust_count:
    frappe.db.sql(
        "UPDATE `tabCustomer` SET customer_name = REPLACE(customer_name, %s, %s) WHERE customer_name LIKE %s",
        (old, new, f"%{{old}}%"),
    )

# Update Supplier.supplier_name
sup_count = frappe.db.sql(
    "SELECT COUNT(*) FROM `tabSupplier` WHERE supplier_name LIKE %s",
    (f"%{{old}}%",),
)[0][0]
if sup_count:
    frappe.db.sql(
        "UPDATE `tabSupplier` SET supplier_name = REPLACE(supplier_name, %s, %s) WHERE supplier_name LIKE %s",
        (old, new, f"%{{old}}%"),
    )

# Update Address.address_title
addr_count = frappe.db.sql(
    "SELECT COUNT(*) FROM `tabAddress` WHERE address_title LIKE %s",
    (f"%{{old}}%",),
)[0][0]
if addr_count:
    frappe.db.sql(
        "UPDATE `tabAddress` SET address_title = REPLACE(address_title, %s, %s) WHERE address_title LIKE %s",
        (old, new, f"%{{old}}%"),
    )

frappe.db.commit()

result["counts_updated"] = {{
    "customer_name": cust_count,
    "supplier_name": sup_count,
    "address_title": addr_count,
}}

# Verify zero remaining
result["remaining_after"] = {{
    "customer_name": frappe.db.sql(
        "SELECT COUNT(*) FROM `tabCustomer` WHERE customer_name LIKE %s",
        (f"%{{old}}%",),
    )[0][0],
    "supplier_name": frappe.db.sql(
        "SELECT COUNT(*) FROM `tabSupplier` WHERE supplier_name LIKE %s",
        (f"%{{old}}%",),
    )[0][0],
    "address_title": frappe.db.sql(
        "SELECT COUNT(*) FROM `tabAddress` WHERE address_title LIKE %s",
        (f"%{{old}}%",),
    )[0][0],
}}

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	stdout = run_in_container(PROBE, timeout=120)
	data = decode_output(stdout)
	out = pathlib.Path("output/s231/verification/e4_fte_rename_log.json")
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps(data, indent=2, default=str))
	print(f"Wrote {out}")
	print(f"Customers matched: {len(data['customer_matches'])}")
	print(f"Suppliers matched: {len(data['supplier_matches'])}")
	print(f"Addresses matched: {len(data['address_matches'])}")
	print(f"Updates applied: {data['counts_updated']}")
	print(f"Remaining after: {data['remaining_after']}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
