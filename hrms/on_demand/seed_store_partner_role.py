"""Seed the Store Partner Frappe Role for S227.

Creates the `Store Partner` Role idempotently. The role is used by ~12
non-employee equity partners to access read-only Sales + Product analytics
on my.bebang.ph, scoped to their stores via the existing
`BEI Sales Dashboard Store Access` DocType.

Role properties:
- role_name: "Store Partner"
- desk_access: 0 (external users do not access the Frappe Desk)
- disabled: 0

Run on production via:

    docker exec $BACKEND bench --site hq.bebang.ph execute \
        hrms.on_demand.seed_store_partner_role.execute

Idempotent: if the role already exists, the script logs `existed` and
returns without modification.

Pattern reference: hrms/on_demand/s206_seed_intercompany_accounts.py.
"""

from __future__ import annotations

import frappe

ROLE_NAME = "Store Partner"


def execute() -> dict[str, str]:
	"""Create the `Store Partner` Role if missing. Returns a status dict."""
	if frappe.db.exists("Role", ROLE_NAME):
		frappe.logger().info(f"[S227] Role {ROLE_NAME!r} already exists; no-op.")
		return {"role": ROLE_NAME, "status": "existed"}

	role = frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": ROLE_NAME,
			"desk_access": 0,
			"disabled": 0,
		}
	)
	role.insert(ignore_permissions=True)
	frappe.db.commit()
	frappe.logger().info(f"[S227] Created Role {ROLE_NAME!r}.")
	return {"role": ROLE_NAME, "status": "created"}
