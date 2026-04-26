#!/usr/bin/env python3
"""S224 - query Frappe Error Log directly via SSM for events during S223 L3 sweep window.

Sweep window: 2026-04-26T05:19:52Z -> 2026-04-26T06:05:07Z UTC
                (= 2026-04-26 13:19 -> 14:05 PHT)

Filters by method/title patterns matching our known failure layers:
- create_stock_transfer (Pattern A)
- approve_material_request (Pattern B)
- get_pending_material_requests (Pattern B)
- _create_mr_for_store_order / submit_order / approve_order (Pattern C)

Outputs: output/s223/verification/error_log_during_sweep.json
"""
from __future__ import annotations
import base64
import gzip
import json
import pathlib
import sys
import time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"
OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "s223" / "verification" / "error_log_during_sweep.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

SCRIPT = '''
import json
import frappe

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()

# Sweep window UTC -> PHT: 13:19:52 to 14:05:07 PHT (UTC+8)
WINDOW_START = "2026-04-26 13:00:00"  # 30 min buffer before sweep
WINDOW_END   = "2026-04-26 14:30:00"  # 30 min buffer after sweep

# Pull all Error Log entries in window
errors = frappe.db.sql("""
    SELECT name, creation, method, error
    FROM `tabError Log`
    WHERE creation BETWEEN %s AND %s
    ORDER BY creation DESC
    LIMIT 500
""", (WINDOW_START, WINDOW_END), as_dict=True)

# Bucket errors by inferred pattern
result = {
    "window_start_pht": WINDOW_START,
    "window_end_pht": WINDOW_END,
    "total_errors_in_window": len(errors),
    "by_pattern": {},
    "raw_errors": [],
}

PATTERN_KEYWORDS = {
    "Pattern_A_Dispatch": ["create_stock_transfer", "Stock Entry", "Material Issue", "dispatch"],
    "Pattern_B_WhApproval": ["approve_material_request", "get_pending_material_requests", "Approve Warehouse", "Material Request"],
    "Pattern_C_MRCreation": ["_create_mr_for_store_order", "submit_order", "MR Creation Error", "create_mr_for_store_order"],
    "ORTIGAS_GREENHILLS": ["ORTIGAS GREENHILLS", "BEIFRANCHISE FOOD OPC"],
    "NAIA_T3": ["NAIA T3", "HALO-HALO TERMINAL"],
    "ORTIGAS_ESTANCIA": ["ORTIGAS ESTANCIA", "BB ESTANCIA"],
    "AYALA_SOLENAD": ["AYALA SOLENAD", "HFFM SOLENAD"],
    "approve_order": ["approve_order", "BEI Store Order"],
}

for pat, keywords in PATTERN_KEYWORDS.items():
    matched = []
    for err in errors:
        haystack = (err.get("method", "") or "") + " " + (err.get("error", "") or "")[:2000]
        if any(kw.lower() in haystack.lower() for kw in keywords):
            matched.append({
                "name": err["name"],
                "creation_pht": str(err["creation"]),
                "method": err.get("method", "")[:200],
                "error_head": (err.get("error", "") or "")[:1500],
            })
    result["by_pattern"][pat] = {"count": len(matched), "samples": matched[:5]}

# Top distinct method strings (first 100 chars) - useful for spotting unexpected patterns
from collections import Counter
method_counts = Counter()
for err in errors:
    m = (err.get("method", "") or "")[:80]
    method_counts[m] += 1
result["top_methods"] = method_counts.most_common(15)

# Always include the 25 most recent errors verbatim for human review
for err in errors[:25]:
    result["raw_errors"].append({
        "name": err["name"],
        "creation_pht": str(err["creation"]),
        "method": (err.get("method", "") or "")[:200],
        "error_head": (err.get("error", "") or "")[:2500],
    })

import gzip as _gz, base64 as _b64
compressed = _gz.compress(json.dumps(result, default=str).encode())
print("__B64_START__")
print(_b64.b64encode(compressed).decode())
print("__B64_END__")
frappe.destroy()
'''


def run(timeout: int = 180) -> str:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s224err.py",
        "docker cp /tmp/s224err.py $BACKEND:/tmp/s224err.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s224err.py",
    ]
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                         Parameters={"commands": cmds, "executionTimeout": [str(timeout)]})
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}", flush=True)
    deadline = time.time() + timeout + 30
    while time.time() < deadline:
        time.sleep(8)
        try:
            inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            out = inv.get("StandardOutputContent", "")
            if inv["Status"] != "Success":
                sys.stderr.write(inv.get("StandardErrorContent", "") + "\n")
            return out
    raise TimeoutError()


def main() -> int:
    out = run()
    s = out.find("__B64_START__")
    e = out.find("__B64_END__")
    if s < 0 or e < 0:
        sys.stderr.write(out[:5000] + "\n")
        return 1
    b64 = out[s + len("__B64_START__"):e].strip()
    data = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
    OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"Wrote: {OUT}\n")
    print(f"Total errors in window: {data['total_errors_in_window']}\n")
    print("By pattern:")
    for pat, info in data["by_pattern"].items():
        print(f"  {pat}: {info['count']}")
    print()
    print("Top methods (first 80 chars):")
    for m, c in data["top_methods"]:
        print(f"  {c:3d}  {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
