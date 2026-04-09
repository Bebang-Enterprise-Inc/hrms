"""S172 Defect #9: ensure HR User and HR Manager have Employee read/write.

The S166 L3 audit confirmed test.hr@bebang.ph received 403 on
`/api/resource/Employee`. The my.bebang.ph proxy has no allowlist and is a
pure passthrough, so the 403 must come from Frappe's built-in
`has_permission("Employee", "read")` check. Standard ERPNext installs grant
HR User and HR Manager read+write on Employee, but the production site
may have had its DocPerm rows drift (partial migration, manual admin edit,
stale fixture).

This patch is idempotent: it checks for existing DocPerm rows first, only
inserts the missing ones, and never downgrades existing permissions.
"""

from __future__ import annotations

import frappe


REQUIRED_ROLES = [
	{"role": "HR User", "read": 1, "write": 1, "create": 1, "delete": 0},
	{"role": "HR Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
]


def execute() -> None:
	doctype = "Employee"

	if not frappe.db.exists("DocType", doctype):
		frappe.logger().info(f"[S172] DocType {doctype} not found; skipping.")
		return

	for perm in REQUIRED_ROLES:
		role = perm["role"]

		if not frappe.db.exists("Role", role):
			frappe.logger().info(f"[S172] Role {role} not found; skipping.")
			continue

		# Check for an existing DocPerm row at permlevel 0 for this role.
		existing = frappe.db.get_value(
			"DocPerm",
			{"parent": doctype, "role": role, "permlevel": 0},
			["name", "read", "write", "create", "delete"],
			as_dict=True,
		)

		if existing:
			# Upgrade only — never downgrade existing grants.
			needs_update = False
			update_fields = {}
			for key in ("read", "write", "create", "delete"):
				desired = int(perm[key])
				current = int(existing.get(key) or 0)
				if desired and not current:
					update_fields[key] = 1
					needs_update = True

			if needs_update:
				frappe.db.set_value("DocPerm", existing["name"], update_fields)
				frappe.logger().info(
					f"[S172] Upgraded DocPerm {doctype}/{role}: {update_fields}"
				)
			else:
				frappe.logger().info(
					f"[S172] DocPerm {doctype}/{role} already sufficient."
				)
		else:
			# No row exists — insert a new DocPerm via the parent DocType doc
			# so the permission is attached properly (not via raw SQL).
			doctype_doc = frappe.get_doc("DocType", doctype)
			doctype_doc.append(
				"permissions",
				{
					"role": role,
					"permlevel": 0,
					"read": perm["read"],
					"write": perm["write"],
					"create": perm["create"],
					"delete": perm["delete"],
					"submit": 0,
					"cancel": 0,
					"amend": 0,
				},
			)
			doctype_doc.save(ignore_permissions=True)
			frappe.logger().info(
				f"[S172] Inserted DocPerm {doctype}/{role} (r/w/c/d=1/1/1/{perm['delete']})"
			)

	frappe.db.commit()
	frappe.clear_cache(doctype=doctype)
