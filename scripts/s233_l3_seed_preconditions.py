#!/usr/bin/env python3
"""S233 v3 L3 pre-flight seeder.

Idempotent. Ensures L3 spec preconditions are met BEFORE Playwright opens
the browser:
  1. BFI2 has is_group=1 AND entity_category in {Head Office, Holding Company,
     Franchisor, Commissary} (delegates to s233_backfill_bfi2_entity_category.py)
  2. test.bd@bebang.ph User exists with role "BD Manager"
  3. test.crew@bebang.ph User exists with role "Crew" (no BD Manager — for
     S7 negative-case button-hidden test)

Output: output/l3/s233/seed_complete.json with the resolved state.

Per CEO browser-only directive: this script runs BEFORE the browser opens
(not from inside the spec body).
"""
from __future__ import annotations
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import run_in_container

PREAMBLE = """\
import os, sys, json, traceback
for d in (
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
):
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

def _emit(payload):
    print("---S233-SEED-START---")
    print(json.dumps(payload, indent=2, default=str))
    print("---S233-SEED-END---")
"""

SEED = PREAMBLE + """
result = {"steps": []}
try:
    # Step 1: BFI2 is_group + entity_category
    bfi2 = frappe.db.get_value(
        "Company", "BEBANG FT INC.",
        ["is_group", "entity_category", "abbr"], as_dict=True,
    )
    result["steps"].append({"step": 1, "name": "bfi2_state", "value": bfi2})
    ALLOWED = {"Head Office", "Holding Company", "Franchisor", "Commissary"}
    if not bfi2:
        result["error"] = "BFI2 not found — cannot seed L3"
        _emit(result); frappe.destroy(); raise SystemExit(0)
    if bfi2.get("is_group") != 1 or bfi2.get("entity_category") not in ALLOWED:
        result["error"] = (
            f"BFI2 not canonical: is_group={bfi2.get('is_group')}, "
            f"entity_category={bfi2.get('entity_category')!r}. "
            f"Run s233_backfill_bfi2_entity_category.py first."
        )
        _emit(result); frappe.destroy(); raise SystemExit(0)

    # Step 2: test.bd@bebang.ph User with BD Manager role
    BD_USER = "test.bd@bebang.ph"
    bd_step = {"step": 2, "name": "test_bd_user"}
    if not frappe.db.exists("User", BD_USER):
        u = frappe.new_doc("User")
        u.email = BD_USER
        u.first_name = "Test"
        u.last_name = "BD"
        u.username = BD_USER.split("@")[0]
        u.send_welcome_email = 0
        u.enabled = 1
        u.user_type = "System User"
        u.flags.ignore_permissions = True
        u.insert()
        bd_step["created"] = True
    else:
        bd_step["created"] = False
    # Ensure BD Manager role assigned (idempotent)
    if not frappe.db.exists("Has Role", {"parent": BD_USER, "role": "BD Manager"}):
        u = frappe.get_doc("User", BD_USER)
        u.append("roles", {"role": "BD Manager"})
        u.flags.ignore_permissions = True
        u.save()
        bd_step["bd_manager_role_added"] = True
    else:
        bd_step["bd_manager_role_added"] = False
    # Set test password
    from frappe.utils.password import update_password
    update_password(BD_USER, "BeiTest2026!")
    bd_step["password_set"] = True
    result["steps"].append(bd_step)

    # Step 3: test.crew@bebang.ph User with Crew role only (no BD Manager)
    CREW_USER = "test.crew@bebang.ph"
    crew_step = {"step": 3, "name": "test_crew_user"}
    if not frappe.db.exists("User", CREW_USER):
        u = frappe.new_doc("User")
        u.email = CREW_USER
        u.first_name = "Test"
        u.last_name = "Crew"
        u.username = CREW_USER.split("@")[0]
        u.send_welcome_email = 0
        u.enabled = 1
        u.user_type = "System User"
        u.flags.ignore_permissions = True
        u.insert()
        crew_step["created"] = True
    else:
        crew_step["created"] = False
    # Ensure Crew role assigned (only Crew, no BD Manager — for negative test)
    if frappe.db.exists("Has Role", {"parent": CREW_USER, "role": "Crew"}):
        crew_step["crew_role_present"] = True
    else:
        u = frappe.get_doc("User", CREW_USER)
        u.append("roles", {"role": "Crew"})
        u.flags.ignore_permissions = True
        u.save()
        crew_step["crew_role_added"] = True
    # Confirm Crew user does NOT have BD Manager (would invalidate S7 negative case)
    has_bd = frappe.db.exists("Has Role", {"parent": CREW_USER, "role": "BD Manager"})
    if has_bd:
        # Strip it
        frappe.db.delete("Has Role", {"parent": CREW_USER, "role": "BD Manager"})
        crew_step["stripped_bd_manager_role"] = True
    update_password(CREW_USER, "BeiTest2026!")
    crew_step["password_set"] = True
    result["steps"].append(crew_step)

    frappe.db.commit()
    result["status"] = "OK"
except Exception as e:
    result["error"] = str(e)
    result["traceback"] = traceback.format_exc()
    result["status"] = "ERROR"

_emit(result)
frappe.destroy()
"""


def main() -> int:
	stdout = run_in_container(SEED, timeout=180)
	if "---S233-SEED-START---" not in stdout:
		print("ERROR: seed output missing markers:\n" + stdout[-2000:], file=sys.stderr)
		return 2
	s = stdout.split("---S233-SEED-START---", 1)[1].split("---S233-SEED-END---", 1)[0].strip()
	data = json.loads(s)
	out_path = REPO_ROOT / "output" / "l3" / "s233" / "seed_complete.json"
	out_path.parent.mkdir(parents=True, exist_ok=True)
	out_path.write_text(json.dumps(data, indent=2, default=str))
	print(json.dumps(data, indent=2, default=str))
	return 0 if data.get("status") == "OK" else 1


if __name__ == "__main__":
	sys.exit(main())
