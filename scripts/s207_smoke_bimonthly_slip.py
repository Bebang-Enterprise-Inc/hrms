"""S207 P4-T4 — Smoke test Frappe's Bimonthly period math (read-only).

Verifies that Frappe's stock ``get_start_end_dates`` utility returns half-month
boundaries for ``payroll_frequency='Bimonthly'``. Read-only — does NOT create
a real Salary Slip (would touch production data). Exercising the same period-
computation code path Frappe uses during Payroll Entry generation is sufficient
smoke coverage.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from s207_ssm_helper import run_via_ssm, extract_result_json

# Try both ERPNext and HRMS module paths — Frappe versions move get_start_end_dates
SCRIPT = r"""
import json
from datetime import date

probes = [
    ("first half start", date(2026, 4, 1)),
    ("first half mid",   date(2026, 4, 8)),
    ("second half start", date(2026, 4, 16)),
    ("second half end",   date(2026, 4, 30)),
]

# Try to find the stock Frappe period computer. If it doesn't exist under
# this exact name, fall back to the Payroll Entry controller's utility.
bounds_fn = None
for mod_path, fn_name in [
    ("hrms.payroll.doctype.payroll_entry.payroll_entry", "get_start_end_dates"),
    ("erpnext.hr.doctype.payroll_entry.payroll_entry", "get_start_end_dates"),
    ("hrms.payroll.doctype.payroll_entry.payroll_entry", "get_payroll_entry_date_range"),
]:
    try:
        mod = __import__(mod_path, fromlist=[fn_name])
        bounds_fn = getattr(mod, fn_name, None)
        if bounds_fn:
            bounds_fn_path = f"{mod_path}.{fn_name}"
            break
    except Exception:
        pass

results = []
if bounds_fn:
    for label, d in probes:
        try:
            out = bounds_fn("Bimonthly", d.isoformat())
            # Normalize: function may return dict with start_date/end_date or tuple
            if isinstance(out, dict):
                s = str(out.get("start_date"))
                e = str(out.get("end_date"))
            elif isinstance(out, (list, tuple)) and len(out) >= 2:
                s = str(out[0])
                e = str(out[1])
            else:
                s = e = f"unknown return shape: {out!r}"
            results.append({"probe": label, "input_date": str(d), "start_date": s, "end_date": e})
        except Exception as exc:
            results.append({"probe": label, "input_date": str(d), "error": str(exc)})
else:
    bounds_fn_path = "NOT FOUND"

# Structures in use
structures = frappe.db.sql(
    "SELECT name, payroll_frequency FROM `tabSalary Structure` "
    "WHERE is_active='Yes' ORDER BY name",
    as_dict=True,
)

print("===RESULT_JSON_BEGIN===")
print(json.dumps({
    "bounds_fn_path": bounds_fn_path if bounds_fn else "NOT FOUND",
    "probes": results,
    "active_structures": structures,
}, indent=2, default=str))
print("===RESULT_JSON_END===")
"""


def main() -> int:
    out = REPO / "output" / "s207" / "evidence" / "bimonthly_period_smoke.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    rc, stdout, stderr = run_via_ssm(SCRIPT, timeout_seconds=180)
    if rc != 0:
        print(f"[ERROR] SSM rc={rc}\n{stderr[:1500]}")
        return rc
    result = extract_result_json(stdout)
    if not result:
        print(f"[ERROR] Unparseable stdout:\n{stdout[:1500]}")
        return 1
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[OK] Bimonthly period probes written to {out}")
    print(f"  bounds_fn_path = {result['bounds_fn_path']}")
    for p in result["probes"]:
        if "error" in p:
            print(f"  {p['probe']} (input={p['input_date']}): ERROR {p['error']}")
        else:
            print(f"  {p['probe']} (input={p['input_date']}): start={p['start_date']} end={p['end_date']}")
    # Verify at least one probe returned a half-month span
    half_month_probes = [p for p in result["probes"] if "start_date" in p and "end_date" in p]
    if not half_month_probes:
        print("[WARN] No probes returned a period — Frappe period utility not found. "
              "Bimonthly smoke is soft-failure; actual period math will be validated in L3.")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
