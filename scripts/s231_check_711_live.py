#!/usr/bin/env python3
"""S231 — verify PR #711 is live (get_fee_schedule callable) + current state."""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

PROBE = (
	PAYLOAD_PREAMBLE
	+ """
import traceback
result = {}
# Test get_fee_schedule
try:
    from hrms.api.billing import get_fee_schedule
    out = get_fee_schedule()
    result["get_fee_schedule"] = {
        "ok": True,
        "schedules_count": len(out.get("schedules", [])),
        "carveouts_count": len(out.get("carveouts", [])),
        "markup_rates": out.get("markup_rates", {}),
        "first_schedule": out.get("schedules", [None])[0] if out.get("schedules") else None,
    }
except Exception as e:
    result["get_fee_schedule"] = {"ok": False, "error": str(e)[:300], "tb": traceback.format_exc()[:1500]}

# Current ownership state of test targets
for c in ["AYALA FAIRVIEW TERRACES - BEBANG FT INC.", "SM SAN JOSE DEL MONTE - JL TRADE OPC"]:
    if frappe.db.exists("Company", c):
        result[c] = frappe.db.get_value("Company", c, ["store_ownership_type", "entity_category"], as_dict=True)
    else:
        result[c] = {"_missing": True}

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	stdout = run_in_container(PROBE, timeout=120)
	data = decode_output(stdout)
	out = pathlib.Path("output/s231/verification/check_711_live.json")
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps(data, indent=2, default=str))
	print(json.dumps(data, indent=2, default=str))
	return 0 if data.get("get_fee_schedule", {}).get("ok") else 1


if __name__ == "__main__":
	sys.exit(main())
