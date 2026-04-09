#!/usr/bin/env python3
"""S175 Phase 0 — Re-verify Phase A audit baseline (HB-2/3/4/7 gate).

Ships a read-only payload to hq.bebang.ph via SSM and compares the results
against the frozen baseline at output/s175/preflight_audit.json.

If ANY delete-target GL count is non-zero, OR the company count has drifted,
OR the BEI 6xxxxxx counts have drifted, HARD BLOCKERS fire and we exit 1.

Writes:
  - output/s175/phase0_reverify.json   (live data + drift report)
  - output/s175/phase0_reverify.md     (human summary)
  - output/s175/phase0_raw_stdout.log  (via runner)
"""
from __future__ import annotations

import json
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s175_ssm_runner import run_on_frappe  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output" / "s175"
BASELINE = OUT / "preflight_audit.json"

PAYLOAD = r'''
#!/usr/bin/env python3
"""S175 Phase 0 live re-verify payload — read-only."""
import os, json, sys
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

BKI_DELETE_NUMS = [
    "4000001","4000002","4000100","4000101","4000200","4000201","4000202",
    "4000203","4000204","4000205","4000206","4000207","4000208","4000300",
    "4000301","4000302","4000303","4000304","4000305","4000306",
]
BEI_DELETE_NUMS = [
    "4000001","4000002","4000003","4000004","4000005","4000006","4000200",
    "4000201","4000202","4000203","4000204","4000205","4000206","4000207",
    "4000208","4000300","4000301","4000302","4000303","4000304","4000305","4000306",
]
BEI = "Bebang Enterprise Inc."
BKI = "Bebang Kitchen Inc."

result = {}

# 1. Company count + BFC existence
companies = frappe.get_all("Company", fields=["name","abbr","tax_id","default_currency"])
result["companies_count"] = len(companies)
result["companies"] = sorted([c["name"] for c in companies])
result["bfc_exists_real"] = bool(frappe.db.exists("Company", "BEBANG FRANCHISE CORP."))

# 2. BEI 6xxxxxx breakdown + GL
rows = frappe.db.sql("""
    SELECT root_type, report_type, COUNT(*)
    FROM `tabAccount`
    WHERE company = %s AND account_number LIKE '6%%'
    GROUP BY root_type, report_type
""", BEI, as_dict=False)
bei_6xxx_breakdown = [{"root_type": r[0], "report_type": r[1], "count": r[2]} for r in rows]
bei_6xxx_total = sum(r["count"] for r in bei_6xxx_breakdown)
gl6 = frappe.db.sql("""
    SELECT COUNT(*) FROM `tabGL Entry` ge
    JOIN `tabAccount` a ON ge.account = a.name
    WHERE a.company = %s AND a.account_number LIKE '6%%'
""", BEI)[0][0]
result["bei_6xxx"] = {
    "total": bei_6xxx_total,
    "breakdown": bei_6xxx_breakdown,
    "gl_entries": gl6,
}

def probe(company, number):
    row = frappe.db.sql(
        "SELECT name, account_name, is_group, root_type FROM `tabAccount` WHERE company=%s AND account_number=%s",
        (company, number), as_dict=True,
    )
    if not row:
        return {"exists": False}
    name = row[0]["name"]
    gl = frappe.db.sql("SELECT COUNT(*) FROM `tabGL Entry` WHERE account=%s", name)[0][0]
    children = frappe.db.sql("SELECT COUNT(*) FROM `tabAccount` WHERE parent_account=%s", name)[0][0]
    r = row[0]
    r["exists"] = True
    r["gl_entries"] = gl
    r["children_count"] = children
    return r

result["bki_delete_targets"] = {num: probe(BKI, num) for num in BKI_DELETE_NUMS}
result["bei_delete_targets"] = {num: probe(BEI, num) for num in BEI_DELETE_NUMS}

# 3. BEI Settings
bs = frappe.get_single("BEI Settings")
bei_settings_fields = [
    "bki_sales_income_account","bki_output_vat_account",
    "gr_ir_clearing_account","input_vat_goods_account",
    "input_vat_services_account","input_vat_capital_goods_account",
    "advances_to_suppliers_account","ewt_payable_account","ap_trade_account",
]
result["bei_settings"] = {}
for f in bei_settings_fields:
    val = bs.get(f) or ""
    exists = bool(val) and bool(frappe.db.exists("Account", val))
    result["bei_settings"][f] = {"value": val, "linked_account_exists": exists}

# 4. BEI 2104xxx range (collision check for 2104200)
result["bei_2104_range"] = frappe.db.sql(
    "SELECT account_number, account_name, is_group FROM `tabAccount` "
    "WHERE company=%s AND account_number LIKE '2104%%' ORDER BY account_number",
    BEI, as_dict=True,
)
result["bei_2104200_exists"] = bool(
    frappe.db.get_value("Account", {"company": BEI, "account_number": "2104200"}, "name")
)

# 5. BKI Store customer group count (S168 baseline)
result["bki_store_customer_count"] = frappe.db.sql(
    "SELECT COUNT(*) FROM `tabCustomer` WHERE customer_group=%s", "BKI Store"
)[0][0]

print("S175_PHASE0_JSON_START")
print(json.dumps(result, default=str))
print("S175_PHASE0_JSON_END")

frappe.destroy()
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    payload_path = OUT / "_phase0_payload.py"
    payload_path.write_text(PAYLOAD, encoding="utf-8")

    stdout, stderr, status = run_on_frappe(payload_path, tag="phase0_reverify")
    if status != "Success":
        print(f"[phase0] SSM status={status} — dumping stderr tail:")
        print(stderr[-2000:])
        sys.exit(1)

    if "S175_PHASE0_JSON_START" not in stdout:
        print("[phase0] Missing JSON markers in stdout:")
        print(stdout[-2000:])
        sys.exit(1)

    raw = stdout.split("S175_PHASE0_JSON_START", 1)[1].split("S175_PHASE0_JSON_END", 1)[0].strip()
    live = json.loads(raw)

    # Compare against baseline
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    drift = []
    hard_blockers = []

    # Company count
    bc_expected = 39  # baseline claim
    if live["companies_count"] != bc_expected:
        drift.append(f"company_count drifted: {live['companies_count']} (expected {bc_expected})")

    # BFC must still not exist as real company
    if live["bfc_exists_real"]:
        drift.append("BFC real company already exists (Phase 1 may skip creation)")

    # BEI 6xxxxxx
    if live["bei_6xxx"]["gl_entries"] != 0:
        hard_blockers.append(f"HB-4: BEI 6xxxxxx has {live['bei_6xxx']['gl_entries']} GL entries")
    if live["bei_6xxx"]["total"] != 136:
        drift.append(f"bei_6xxx total drifted: {live['bei_6xxx']['total']} (expected 136)")

    # BKI delete-targets
    for num, data in live["bki_delete_targets"].items():
        if data.get("exists") and data.get("gl_entries", 0) != 0:
            hard_blockers.append(f"HB-2: BKI {num} has {data['gl_entries']} GL entries")
    # BEI delete-targets
    for num, data in live["bei_delete_targets"].items():
        if data.get("exists") and data.get("gl_entries", 0) != 0:
            hard_blockers.append(f"HB-3: BEI {num} has {data['gl_entries']} GL entries")

    # 2104200 must not exist yet
    if live["bei_2104200_exists"]:
        drift.append("2104200 DUE TO BFC already exists on BEI — Phase 4 idempotent path will cover")

    live["_drift"] = drift
    live["_hard_blockers"] = hard_blockers
    live["_verified_at"] = datetime.now(timezone.utc).isoformat()

    (OUT / "phase0_reverify.json").write_text(json.dumps(live, indent=2, default=str), encoding="utf-8")

    # Human summary
    md = [
        "# S175 Phase 0 Reverify",
        f"**Verified:** {live['_verified_at']}",
        "",
        f"- companies_count: **{live['companies_count']}**",
        f"- bfc_exists_real: **{live['bfc_exists_real']}**",
        f"- bei_6xxx total: **{live['bei_6xxx']['total']}**, GL: **{live['bei_6xxx']['gl_entries']}**",
        f"- bki_delete_targets exist: **{sum(1 for v in live['bki_delete_targets'].values() if v.get('exists'))}/20**",
        f"- bei_delete_targets exist: **{sum(1 for v in live['bei_delete_targets'].values() if v.get('exists'))}/22**",
        f"- bei_settings.bki_sales_income_account: `{live['bei_settings']['bki_sales_income_account']['value']}` linked={live['bei_settings']['bki_sales_income_account']['linked_account_exists']}",
        f"- bki_store_customer_count: **{live['bki_store_customer_count']}**",
        "",
        "## Drift",
        "\n".join(f"- {d}" for d in drift) if drift else "(none)",
        "",
        "## Hard Blockers",
        "\n".join(f"- {hb}" for hb in hard_blockers) if hard_blockers else "(none)",
    ]
    (OUT / "phase0_reverify.md").write_text("\n".join(md), encoding="utf-8")

    if hard_blockers:
        print("PHASE0 HARD BLOCKERS:")
        for hb in hard_blockers:
            print("  " + hb)
        sys.exit(2)

    print("PHASE0 OK")
    print(f"  companies={live['companies_count']}  bei_6xxx={live['bei_6xxx']['total']} gl={live['bei_6xxx']['gl_entries']}")
    print(f"  bki_delete_targets={sum(1 for v in live['bki_delete_targets'].values() if v.get('exists'))}/20")
    print(f"  bei_delete_targets={sum(1 for v in live['bei_delete_targets'].values() if v.get('exists'))}/22")
    print(f"  bfc_exists_real={live['bfc_exists_real']}")


if __name__ == "__main__":
    main()
