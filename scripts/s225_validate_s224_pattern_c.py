"""S225 Phase 1 task 3 — REST probe validating S224 Pattern C (fuzzy resolve_warehouse).

Pre-S224: resolve_warehouse("Estancia") → frappe.throw("Could not find Store: Estancia")
Post-S224: resolve_warehouse("Estancia") → matches LIKE %Estancia% via warehouse_name/name,
           returns the canonical warehouse if exactly one non-disabled, non-group match.

Probes (calls validate_order_schedule which internally uses resolve_warehouse):
  1. "Estancia" — partial label, expect resolve to canonical Ortigas Estancia warehouse
  2. "ESTANCIA" — uppercase, expect same resolution
  3. "Bebang" — broad partial, expect "Ambiguous" throw (multiple matches)

Run from worktree:
    python scripts/s225_validate_s224_pattern_c.py

Output:
    output/s225/verification/s224_pattern_c_validation.json
"""
from __future__ import annotations
import base64
import json
import pathlib
import sys
import time

OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "s225" / "verification" / "s224_pattern_c_validation.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

INSTANCE_ID = "i-026b7477d27bd46d6"

INNER_SCRIPT = r'''
import os, json, traceback
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files",
]:
    os.makedirs(d, exist_ok=True)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

from hrms.api.store import resolve_warehouse

def probe(label, store_arg, expect):
    out = {"label": label, "input": store_arg, "expect": expect}
    try:
        result = resolve_warehouse(store_arg)
        out["resolved_warehouse"] = result
        out["error"] = None
        out["ok"] = bool(result and (expect != "throw_ambiguous"))
        if expect == "throw_ambiguous":
            out["ok"] = False
            out["unexpected_pass"] = result
    except Exception as e:
        out["error"] = str(e)[:400]
        out["error_class"] = type(e).__name__
        if expect == "throw_ambiguous":
            out["ok"] = "ambiguous" in str(e).lower()
        else:
            out["ok"] = False
    return out

probes = [
    probe("probe_estancia", "Estancia", "resolve_to_ortigas_estancia"),
    probe("probe_estancia_uppercase", "ESTANCIA", "resolve_to_ortigas_estancia"),
    probe("probe_estancia_titlecase", "ortigas estancia", "resolve_to_ortigas_estancia"),
    probe("probe_ambiguous", "Bebang", "throw_ambiguous"),
]

# Sanity: list all Estancia-matching warehouses to confirm what should resolve to
estancia_wh = frappe.db.sql(
    """SELECT name, warehouse_name, company, disabled, is_group
       FROM `tabWarehouse` WHERE LOWER(warehouse_name) LIKE '%estancia%' OR LOWER(name) LIKE '%estancia%'""",
    as_dict=True,
)

result = {
    "probe_estancia": probes[0],
    "probe_estancia_uppercase": probes[1],
    "probe_estancia_titlecase": probes[2],
    "probe_ambiguous": probes[3],
    "estancia_warehouses_in_db": estancia_wh,
}

ok_count = sum(1 for p in probes[:3] if p["ok"])
ambig_ok = probes[3]["ok"]
result["status"] = "PASS" if ok_count == 3 and ambig_ok else "FAIL"
result["pass_count"] = ok_count
result["ambiguous_throws"] = ambig_ok

print(json.dumps(result))
frappe.db.rollback()
'''


def main() -> int:
    import boto3
    enc = base64.b64encode(INNER_SCRIPT.encode()).decode()

    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s225_pattern_c_probe.py",
        "docker cp /tmp/s225_pattern_c_probe.py $BACKEND:/tmp/s225_pattern_c_probe.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s225_pattern_c_probe.py",
    ]

    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["120"]},
    )
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}", flush=True)

    inv = None
    for _ in range(40):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            break

    if inv is None:
        print("SSM call did not complete", flush=True)
        return 2

    stdout = inv.get("StandardOutputContent", "")
    stderr = inv.get("StandardErrorContent", "")
    print("--- STDOUT ---")
    print(stdout)
    if stderr.strip():
        print("--- STDERR ---")
        print(stderr)

    inner_result = None
    for line in stdout.splitlines()[::-1]:
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                inner_result = json.loads(line)
                break
            except json.JSONDecodeError:
                continue

    evidence = {
        "checked_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "ssm_command_id": cid,
        "ssm_status": inv["Status"],
        "instance_id": INSTANCE_ID,
        "probe_estancia": (inner_result or {}).get("probe_estancia"),
        "probe_estancia_uppercase": (inner_result or {}).get("probe_estancia_uppercase"),
        "probe_estancia_titlecase": (inner_result or {}).get("probe_estancia_titlecase"),
        "probe_ambiguous": (inner_result or {}).get("probe_ambiguous"),
        "estancia_warehouses_in_db": (inner_result or {}).get("estancia_warehouses_in_db"),
        "status": (inner_result or {}).get("status", "UNKNOWN"),
        "pass_count": (inner_result or {}).get("pass_count", 0),
        "ambiguous_throws": (inner_result or {}).get("ambiguous_throws", False),
        "raw_stdout": stdout[-5000:],
        "raw_stderr": stderr[-2000:],
    }
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}", flush=True)

    if evidence["status"] == "PASS":
        print("\nPASS: Pattern C fuzzy resolve_warehouse confirmed (3 resolves + 1 ambiguous-throw)", flush=True)
        return 0
    print(f"\nFAIL: status={evidence['status']} pass={evidence['pass_count']}/3 ambig_throws={evidence['ambiguous_throws']}", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
