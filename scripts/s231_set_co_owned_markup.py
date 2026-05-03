#!/usr/bin/env python3
"""S231 D-1 D1-2: set bki_markup_company_owned_percent live in BEI Settings.

The field's JSON default is 2.75 but the existing Single doc was created
before the field was added (PR #707), so the default never applied.
Set it now.
"""
from __future__ import annotations
import json, pathlib, sys
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from s231_ssm_helper import PAYLOAD_PREAMBLE, decode_output, run_in_container

PROBE = (
	PAYLOAD_PREAMBLE
	+ """
result = {}
before = frappe.db.get_single_value("BEI Settings", "bki_markup_company_owned_percent")
result["before"] = before
frappe.db.set_single_value("BEI Settings", "bki_markup_company_owned_percent", 2.75)
frappe.db.commit()
after = frappe.db.get_single_value("BEI Settings", "bki_markup_company_owned_percent")
result["after"] = after
result["set_at"] = frappe.utils.now()

# Re-read all 4 markup rates to verify the set
result["markup_rates_after"] = {
    "Company Owned": frappe.db.get_single_value("BEI Settings", "bki_markup_company_owned_percent"),
    "JV": frappe.db.get_single_value("BEI Settings", "bki_markup_jv_percent"),
    "Managed Franchise": frappe.db.get_single_value("BEI Settings", "bki_markup_managed_franchise_percent"),
    "Full Franchise": frappe.db.get_single_value("BEI Settings", "bki_markup_full_franchise_percent"),
}

_s231_emit(result)
frappe.destroy()
"""
)


def main() -> int:
	stdout = run_in_container(PROBE, timeout=90)
	data = decode_output(stdout)
	out = pathlib.Path("output/s231/verification/co_owned_markup_set.json")
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps(data, indent=2, default=str))
	print(json.dumps(data, indent=2, default=str))
	return 0


if __name__ == "__main__":
	sys.exit(main())
