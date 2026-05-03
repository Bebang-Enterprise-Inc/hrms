#!/usr/bin/env python3
"""S233 v3 A14: probe BEBANG FT INC. (BFI2) live entity_category + is_group state.

Run via SSM inside Frappe container. Captures snapshot to
output/s233/verification/bfi2_state_pre.json. Phase 0.4 step 1 of 2 —
backfill (set_value) only fires if probe shows entity_category not in
the canonical {Head Office, Holding Company, Franchisor, Commissary} set.
"""
from __future__ import annotations
import json, os, pathlib, sys

# SSM helper preamble — copied from scripts/s231_ssm_helper.py pattern
PREAMBLE = """\
import os, sys, json, traceback
for d in (
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
):
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

def _emit(payload):
    print("---S233-PROBE-START---")
    print(json.dumps(payload, indent=2, default=str))
    print("---S233-PROBE-END---")
"""

PROBE = PREAMBLE + """
result = {}
try:
    out = frappe.db.get_value(
        "Company", "BEBANG FT INC.",
        ["is_group", "entity_category", "abbr", "tax_id", "parent_company"],
        as_dict=True,
    )
    if not out:
        result["error"] = "BEBANG FT INC. does not exist"
    else:
        result["state"] = out
        ALLOWED = {"Head Office", "Holding Company", "Franchisor", "Commissary"}
        result["entity_category_in_allowed_set"] = (out.get("entity_category") in ALLOWED)
        result["is_group_correct"] = (out.get("is_group") == 1)
        result["needs_backfill"] = not result["entity_category_in_allowed_set"]
        result["recommended_value"] = "Holding Company"  # BFI2 is a holding entity per S231 design
except Exception as e:
    result["error"] = str(e)
    result["traceback"] = traceback.format_exc()

_emit(result)
frappe.destroy()
"""


def main() -> int:
    # Caller (this main) writes the script payload to /tmp on the SSM host
    # then docker execs into the backend container. We use the existing
    # s231_ssm_helper if available; otherwise emit the script for manual exec.
    REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        from s231_ssm_helper import decode_output, run_in_container
    except ImportError:
        print("ERROR: s231_ssm_helper not found; expected at scripts/s231_ssm_helper.py", file=sys.stderr)
        return 1

    stdout = run_in_container(PROBE, timeout=120)
    # decode_output expects START/END markers — ours are S231-PROBE-START/END.
    # Fall back to raw JSON between our markers.
    if "---S233-PROBE-START---" in stdout and "---S233-PROBE-END---" in stdout:
        s = stdout.split("---S233-PROBE-START---", 1)[1].split("---S233-PROBE-END---", 1)[0].strip()
        data = json.loads(s)
    else:
        try:
            data = decode_output(stdout)
        except Exception:
            print("ERROR: could not decode probe output:\n" + stdout[-2000:], file=sys.stderr)
            return 2

    out_path = pathlib.Path(__file__).resolve().parent.parent / "output" / "s233" / "verification" / "bfi2_state_pre.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, default=str))
    print(json.dumps(data, indent=2, default=str))
    return 0 if not data.get("error") else 1


if __name__ == "__main__":
    sys.exit(main())
