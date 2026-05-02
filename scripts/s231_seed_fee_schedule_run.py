#!/usr/bin/env python3
"""S231 D-3-4: invoke the seed scripts for BEI Fee Schedule + BEI Fee Carveout."""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

PROBE = (
	PAYLOAD_PREAMBLE
	+ """
result = {}
import traceback

for fn_name in [
    "hrms.on_demand.s231_seed_fee_schedule",
    "hrms.on_demand.s231_seed_fee_carveouts",
]:
    try:
        mod = __import__(fn_name, fromlist=["run"])
        out = mod.run()
        result[fn_name] = out
    except Exception as e:
        result[fn_name] = {
            "error": str(e)[:500],
            "tb": traceback.format_exc()[:3000],
        }

# Verify rows
result["fee_schedule_count"] = frappe.db.count("BEI Fee Schedule")
result["fee_schedule_sample"] = frappe.db.sql(
    "SELECT name, ownership_type, fee_type, rate, base_field, recipient_company FROM `tabBEI Fee Schedule` ORDER BY name",
    as_dict=True,
)
result["fee_carveout_count"] = frappe.db.count("BEI Fee Carveout")
result["fee_carveout_sample"] = frappe.db.sql(
    "SELECT name, store, fee_type, rate_override FROM `tabBEI Fee Carveout` ORDER BY name",
    as_dict=True,
)

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	stdout = run_in_container(PROBE, timeout=240)
	data = decode_output(stdout)
	out = pathlib.Path("output/s231/verification/fee_schedule_seed_log.json")
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps(data, indent=2, default=str))
	print(f"Wrote {out}")
	for fn in ["hrms.on_demand.s231_seed_fee_schedule", "hrms.on_demand.s231_seed_fee_carveouts"]:
		r = data.get(fn, {})
		if "error" in r:
			print(f"\n{fn}: ERROR — {r['error']}")
		else:
			print(f"\n{fn}: created={r.get('created')} updated={r.get('updated')} skipped_no_store={r.get('skipped_no_store')}")
			if r.get("errors"):
				print(f"  errors: {r['errors']}")
	print(f"\nFinal counts: schedule={data['fee_schedule_count']} carveout={data['fee_carveout_count']}")
	if data.get("fee_schedule_sample"):
		print("\nFee Schedule rows:")
		for s in data["fee_schedule_sample"]:
			print(f"  {s['name']}: rate={s['rate']} base={s['base_field']} -> {s['recipient_company']}")
	if data.get("fee_carveout_sample"):
		print("\nCarveout rows:")
		for c in data["fee_carveout_sample"]:
			print(f"  {c['name']}: rate={c['rate_override']}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
