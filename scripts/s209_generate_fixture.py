#!/usr/bin/env python3
"""S209 fixture generator — produces the 49-store fixture for the S209 sweep.

Runs inside the Frappe container via SSM. Joins:
  - tabCompany (entity_category='Store', not disabled, not closed/dormant)
  - tabWarehouse (canonical per-store, is_group=0, disabled=0)
  - tabCustomer (canonical billing Customer: same name as Company, is_internal_customer=0)
  - resolver output from resolve_store_buyer_entity()

Emits:
  - tmp/s209_fixture.json (local)
  - tmp/s209_fixture_count.txt (integer count)
  - tmp/s209_variance_items.json (V1/V2 item picks for Phase 4)
  - Copies fixture to F:/Dropbox/Projects/bei-tasks/tests/e2e/fixtures/s204_all_stores.json

The fixture shape matches S209StoreConfig (see plan Appendix §E):
  {
    store: str,
    warehouse_docname: str,
    company: str,
    customer: str,             # customer_name = company post-PR #638
    tin: str,                  # empty ONLY for ORTIGAS GREENHILLS
    expectBillingHold: bool,   # false for all 49 canonical stores
    buyer_entity_status: "confirmed_legal_entity",
    parent_company: str | None,
    store_ownership_type: str,
    current_area_supervisor: str,
    allowEmptyTin: bool,       # true ONLY for ORTIGAS GREENHILLS
  }

Usage:
    python scripts/s209_generate_fixture.py
    python scripts/s209_generate_fixture.py --skip-variance   # skip variance-item selection
"""
from __future__ import annotations
import argparse
import base64
import json
import pathlib
import sys
import time


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BEI_TASKS = pathlib.Path("F:/Dropbox/Projects/bei-tasks")
TMP_DIR = REPO_ROOT / "tmp"
TMP_DIR.mkdir(exist_ok=True)


AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"


def _build_fixture_script() -> str:
    return '''
import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass

import json
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

from hrms.utils.supply_chain_contracts import resolve_store_buyer_entity

# All active per-store Companies
stores = frappe.db.sql(
    """SELECT name, parent_company, store_ownership_type, tax_id AS company_tax_id, operational_status
       FROM `tabCompany`
       WHERE entity_category = \\'Store\\'
         AND (operational_status IS NULL OR operational_status NOT IN (\\'Permanently Closed\\', \\'Dormant\\'))
       ORDER BY name""",
    as_dict=True,
)

# Canonical warehouses (exact-name match to Company)
warehouses = frappe.db.sql(
    """SELECT name, company, custom_area_supervisor, is_group, disabled
       FROM `tabWarehouse`
       WHERE disabled = 0 AND is_group = 0
         AND company IN (SELECT name FROM `tabCompany`
                         WHERE entity_category = \\'Store\\'
                           AND (operational_status IS NULL OR operational_status NOT IN (\\'Permanently Closed\\', \\'Dormant\\')))
         AND warehouse_name NOT IN (\\'FINISHED GOODS\\', \\'GOODS IN TRANSIT\\', \\'STORES\\', \\'WORK IN PROGRESS\\')""",
    as_dict=True,
)
wh_by_company = {}
for w in warehouses:
    wh_by_company.setdefault(w["company"], []).append(w)

# Canonical billing Customers (exact-name match, is_internal_customer=0)
billing_customers = frappe.db.sql(
    """SELECT name, customer_name, tax_id, is_internal_customer
       FROM `tabCustomer`
       WHERE is_internal_customer = 0
         AND disabled = 0
         AND name IN (SELECT name FROM `tabCompany`
                      WHERE entity_category = \\'Store\\'
                        AND (operational_status IS NULL OR operational_status NOT IN (\\'Permanently Closed\\', \\'Dormant\\')))""",
    as_dict=True,
)
bc_by_name = {c["name"]: c for c in billing_customers}

rows = []
for s in stores:
    co_name = s["name"]
    # Match canonical warehouse (exact-name)
    candidate_whs = wh_by_company.get(co_name, [])
    # Pick the one whose name equals the company string
    canonical_wh = None
    for w in candidate_whs:
        if w["name"] == co_name:
            canonical_wh = w
            break
    if not canonical_wh and candidate_whs:
        canonical_wh = candidate_whs[0]
    if not canonical_wh:
        # No warehouse -> skip
        continue

    # Match canonical billing Customer (exact-name)
    bc = bc_by_name.get(co_name)
    if not bc:
        # No billing Customer -> skip
        continue

    # Run resolver to capture buyer_entity_status (keyword-only args — plan App C)
    try:
        resolver_out = resolve_store_buyer_entity(warehouse_docname=canonical_wh["name"])
        buyer_status = resolver_out.get("buyer_entity_status", "unresolved") or "unresolved"
    except Exception as _e:
        buyer_status = "unresolved"

    rows.append({
        "store": co_name,
        "warehouse_docname": canonical_wh["name"],
        "company": co_name,
        "customer": bc["name"],
        "tin": bc.get("tax_id") or "",
        "expectBillingHold": False,
        "buyer_entity_status": buyer_status,
        "parent_company": s.get("parent_company"),
        "store_ownership_type": s.get("store_ownership_type") or "Company Owned",
        "current_area_supervisor": canonical_wh.get("custom_area_supervisor") or "",
        "allowEmptyTin": co_name == "ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC",
    })

import base64, gzip
blob = gzip.compress(json.dumps(rows).encode())
print("__FIXTURE_B64_START__")
print(base64.b64encode(blob).decode())
print("__FIXTURE_B64_END__")

frappe.destroy()
'''


def _build_variance_script(warehouses: list[tuple[str, str]]) -> str:
    """Pick the highest-suggested-qty DRY item per warehouse for V1/V2 variance tests."""
    wh_json = json.dumps(warehouses)
    return f'''
import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass

import json
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

from hrms.api.store import get_orderable_items

whs = {wh_json}
out = {{}}
for key, wh in whs:
    try:
        items = get_orderable_items(wh, None, 0)
        picks = [i for i in items.get("items", [])
                 if i.get("cargo_category") == "DRY" and (i.get("suggested_qty") or 0) >= 10]
        picks.sort(key=lambda x: -(x.get("suggested_qty") or 0))
        out[key] = picks[0] if picks else None
    except Exception as e:
        out[key] = {{"error": str(e)}}

print("__VARIANCE_START__")
print(json.dumps(out, indent=2, default=str))
print("__VARIANCE_END__")

frappe.destroy()
'''


def run_in_container(python_script: str, timeout: int = 180) -> str:
    """Execute python_script inside the frappe container via SSM. Returns stdout."""
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(python_script.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s209_script.py",
        "docker cp /tmp/s209_script.py $BACKEND:/tmp/s209_script.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s209_script.py",
    ]
    r = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": [str(timeout)]},
    )
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}")
    deadline = time.time() + timeout + 30
    while time.time() < deadline:
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            out = inv.get("StandardOutputContent", "")
            err = inv.get("StandardErrorContent", "")
            if inv["Status"] != "Success":
                sys.stderr.write(f"[SSM {inv['Status']}]\n{err}\n")
                raise RuntimeError(f"SSM command failed: {inv['Status']}")
            return out
    raise TimeoutError(f"SSM command {cid} did not complete")


def extract_between(haystack: str, start: str, end: str) -> str:
    s = haystack.find(start)
    e = haystack.find(end)
    if s < 0 or e < 0:
        raise RuntimeError(f"Could not find markers {start} / {end}")
    return haystack[s + len(start):e].strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-variance", action="store_true")
    args = ap.parse_args()

    # 1. Pull fixture
    print("[S209] Generating 49-store fixture from live Frappe...")
    fixture_out = run_in_container(_build_fixture_script(), timeout=180)
    fixture_b64 = extract_between(fixture_out, "__FIXTURE_B64_START__", "__FIXTURE_B64_END__")
    import base64, gzip
    fixture_json_bytes = gzip.decompress(base64.b64decode(fixture_b64))
    fixture = json.loads(fixture_json_bytes.decode("utf-8"))

    # 2. Expected 49
    if len(fixture) != 49:
        sys.stderr.write(f"[ERROR] expected 49 fixture entries, got {len(fixture)}\n")
        sys.stderr.write(f"Stores present: {[r['store'] for r in fixture]}\n")
        # still write partial for debugging
    else:
        print(f"[S209] Got {len(fixture)} entries (expected 49)")

    # 3. TIN integrity: only ORTIGAS GREENHILLS allowed empty
    for row in fixture:
        if not row["tin"] and "ORTIGAS GREENHILLS" not in row["store"]:
            sys.stderr.write(
                f"[BLOCKER] {row['store']} has empty TIN — fix master data before proceeding\n"
            )
            return 1

    # 4. expected_buyer sanity string (for verify_phase grep)
    for row in fixture:
        row["expected_buyer"] = row["customer"]

    # 5. Write local + bei-tasks copy
    local_path = TMP_DIR / "s209_fixture.json"
    local_path.write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    (TMP_DIR / "s209_fixture_count.txt").write_text(str(len(fixture)), encoding="utf-8")

    bei_path = BEI_TASKS / "tests/e2e/fixtures/s204_all_stores.json"
    bei_path.parent.mkdir(parents=True, exist_ok=True)
    bei_path.write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    print(f"[S209] Wrote fixture to {local_path} and {bei_path}")

    # 6. Variance-item picks (Phase 4 prereq)
    if args.skip_variance:
        print("[S209] Skipping variance-item selection")
        return 0

    print("[S209] Picking variance items for V1 (SM TANZA) + V2 (AYALA VERMOSA)...")
    variance_whs = []
    for row in fixture:
        if "SM TANZA" in row["store"]:
            variance_whs.append(("V1_SM_TANZA", row["warehouse_docname"]))
        elif "AYALA VERMOSA" in row["store"]:
            variance_whs.append(("V2_AYALA_VERMOSA", row["warehouse_docname"]))

    if len(variance_whs) < 2:
        sys.stderr.write(
            f"[WARN] expected SM TANZA + AYALA VERMOSA in fixture; got {variance_whs}\n"
        )
    else:
        try:
            var_out = run_in_container(_build_variance_script(variance_whs), timeout=90)
            var_json = extract_between(var_out, "__VARIANCE_START__", "__VARIANCE_END__")
            variance = json.loads(var_json)
        except Exception as e:
            sys.stderr.write(f"[WARN] variance pick failed: {e}\n")
            variance = {k: None for k, _ in variance_whs}

        var_path_bei = BEI_TASKS / "tests/e2e/fixtures/s209_variance_items.json"
        var_path_local = TMP_DIR / "s209_variance_items.json"
        var_path_bei.write_text(json.dumps(variance, indent=2), encoding="utf-8")
        var_path_local.write_text(json.dumps(variance, indent=2), encoding="utf-8")
        print(f"[S209] Wrote variance items to {var_path_bei}")
        for k, v in variance.items():
            if v and "item_code" in v:
                print(f"  {k}: {v['item_code']} (suggested_qty={v.get('suggested_qty')})")
            else:
                print(f"  {k}: NO VIABLE ITEM — Phase 4 will seed inventory before picking")

    return 0


if __name__ == "__main__":
    sys.exit(main())
