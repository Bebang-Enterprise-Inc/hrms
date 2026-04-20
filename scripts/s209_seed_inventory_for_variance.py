#!/usr/bin/env python3
"""S209 P4-T1: seed source warehouse inventory for the V1/V2 variance specs.

V1 (SM TANZA short-receive): needs >=10 of the picked DRY item at source
warehouse so the spec can order qty=10. We seed to a minimum of 20 to give
headroom against concurrent demand.

V2 (AYALA VERMOSA short-dispatch): needs EXACTLY 8 available at source so
that dispatch is forced to short. We reduce source inventory to 8 (issue any
excess) and store the pre-seed quantity in the snapshot for revert.

All mutations go through Stock Entry (Material Receipt / Material Issue)
to stay on the submit / cancel lifecycle. No ad-hoc SQL on tabBin or
tabStock Ledger Entry.

Usage:
    python scripts/s209_seed_inventory_for_variance.py --scenario V1
    python scripts/s209_seed_inventory_for_variance.py --scenario V2
    python scripts/s209_seed_inventory_for_variance.py --revert     # both

The variance-item picks live in `bei-tasks/tests/e2e/fixtures/s209_variance_items.json`
produced by `scripts/s209_generate_fixture.py`.
"""
from __future__ import annotations
import argparse
import base64
import gzip
import json
import pathlib
import sys
import time


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BEI_TASKS = pathlib.Path("F:/Dropbox/Projects/bei-tasks")
VARIANCE_FIXTURE = BEI_TASKS / "tests/e2e/fixtures/s209_variance_items.json"
SNAPSHOT_PATH = REPO_ROOT / "output/l3/s209/inventory_snapshot.json"

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"


def _build_seed_script(actions: list[dict]) -> str:
    """actions: [{"type":"receipt|issue", "warehouse":..., "item_code":..., "qty":..., "label":...}]"""
    actions_json = json.dumps(actions)
    return f'''
import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass

import json, base64, gzip
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

actions = {actions_json}

out = []
errors = []
for a in actions:
    try:
        co = frappe.db.get_value("Warehouse", a["warehouse"], "company")
        if not co:
            raise Exception(f"Warehouse {{a['warehouse']}} has no company")
        se = frappe.new_doc("Stock Entry")
        se.stock_entry_type = "Material Receipt" if a["type"] == "receipt" else "Material Issue"
        se.purpose = se.stock_entry_type
        se.company = co
        se.posting_date = frappe.utils.nowdate()
        se.posting_time = frappe.utils.nowtime()
        item_row = {{
            "item_code": a["item_code"],
            "qty": float(a["qty"]),
        }}
        if a["type"] == "receipt":
            item_row["t_warehouse"] = a["warehouse"]
            # Provide a nominal rate so the Material Receipt valuation is non-zero
            rate_row = frappe.db.get_value(
                "Item Price",
                {{"item_code": a["item_code"], "price_list": frappe.db.get_single_value("Buying Settings", "buying_price_list")}},
                "price_list_rate"
            )
            if not rate_row:
                rate_row = frappe.db.get_value("Item", a["item_code"], "standard_rate")
            item_row["basic_rate"] = float(rate_row or 1)
        else:
            item_row["s_warehouse"] = a["warehouse"]
        se.append("items", item_row)
        se.flags.ignore_permissions = True
        se.insert()
        se.submit()
        out.append({{
            "label": a.get("label"),
            "stock_entry": se.name,
            "warehouse": a["warehouse"],
            "item_code": a["item_code"],
            "type": a["type"],
            "qty": float(a["qty"]),
        }})
    except Exception as e:
        errors.append({{"label": a.get("label"), "error": str(e), "action": a}})

frappe.db.commit()

payload = {{"created": out, "errors": errors}}
blob = gzip.compress(json.dumps(payload).encode())
print("__S209_SEED_START__")
print(base64.b64encode(blob).decode())
print("__S209_SEED_END__")

frappe.destroy()
'''


def _build_stock_probe_script(pairs: list[tuple[str, str, str]]) -> str:
    """Probe current stock for (label, warehouse, item_code) tuples."""
    pairs_json = json.dumps(pairs)
    return f'''
import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass

import json, base64, gzip
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()

pairs = {pairs_json}
out = []
for lbl, wh, ic in pairs:
    qty = frappe.db.get_value("Bin", {{"warehouse": wh, "item_code": ic}}, "actual_qty") or 0
    out.append({{"label": lbl, "warehouse": wh, "item_code": ic, "actual_qty": float(qty)}})

payload = {{"stock": out}}
blob = gzip.compress(json.dumps(payload).encode())
print("__S209_PROBE_START__")
print(base64.b64encode(blob).decode())
print("__S209_PROBE_END__")

frappe.destroy()
'''


def run_in_container(python_script: str, timeout: int = 180) -> str:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(python_script.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s209_seed.py",
        "docker cp /tmp/s209_seed.py $BACKEND:/tmp/s209_seed.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s209_seed.py",
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


def _extract(stdout: str, start: str, end: str) -> dict:
    s = stdout.find(start)
    e = stdout.find(end)
    if s < 0 or e < 0:
        raise RuntimeError(f"Could not find markers {start} / {end}")
    return json.loads(
        gzip.decompress(base64.b64decode(stdout[s + len(start):e].strip())).decode()
    )


def load_variance_picks() -> dict:
    if not VARIANCE_FIXTURE.exists():
        raise FileNotFoundError(f"{VARIANCE_FIXTURE} missing — run s209_generate_fixture.py")
    return json.loads(VARIANCE_FIXTURE.read_text(encoding="utf-8"))


def scenario_v1_seed(picks: dict) -> list[dict]:
    """V1 needs >=10 at source (SM TANZA). Seed 20 to have headroom."""
    v1 = picks.get("V1_SM_TANZA")
    if not v1 or not v1.get("item_code"):
        raise RuntimeError("V1_SM_TANZA pick missing from variance fixture")
    return [{
        "type": "receipt",
        "warehouse": "SM TANZA - BEBANG MEGA INC.",
        "item_code": v1["item_code"],
        "qty": 20,
        "label": "V1_SEED",
    }]


def scenario_v2_seed(picks: dict, current_qty: float) -> list[dict]:
    """V2 target stock: qty=8 at AYALA VERMOSA source warehouse (V1 target: qty=10
    dispatched, accepted qty=8). If current > 8, issue the excess; if current
    < 8, receipt to top-up; if == 8, no-op."""
    v2 = picks.get("V2_AYALA_VERMOSA")
    if not v2 or not v2.get("item_code"):
        raise RuntimeError("V2_AYALA_VERMOSA pick missing from variance fixture")
    warehouse = "AYALA VERMOSA - BEBANG MEGA INC."
    ic = v2["item_code"]
    delta = 8.0 - current_qty
    if abs(delta) < 0.001:
        return []
    if delta > 0:
        return [{"type": "receipt", "warehouse": warehouse, "item_code": ic, "qty": delta, "label": "V2_TOPUP"}]
    return [{"type": "issue", "warehouse": warehouse, "item_code": ic, "qty": -delta, "label": "V2_SHRINK"}]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=["V1", "V2", "BOTH"], default="BOTH")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    picks = load_variance_picks()

    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if args.revert:
        if not SNAPSHOT_PATH.exists():
            print("[S209] snapshot not found, nothing to revert")
            return 0
        snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        # Reverse each seed by opposing Stock Entry (receipt<->issue)
        revert_actions = []
        for entry in snap:
            opposite = "issue" if entry["type"] == "receipt" else "receipt"
            revert_actions.append({
                "type": opposite,
                "warehouse": entry["warehouse"],
                "item_code": entry["item_code"],
                "qty": entry["qty"],
                "label": f"REVERT_{entry['label']}",
            })
        if not revert_actions:
            print("[S209] snapshot empty, no revert needed")
            return 0
        print(f"[S209] Reverting {len(revert_actions)} seed actions...")
        out = run_in_container(_build_seed_script(revert_actions))
        payload = _extract(out, "__S209_SEED_START__", "__S209_SEED_END__")
        if payload["errors"]:
            for e in payload["errors"]:
                sys.stderr.write(f"  [revert-error] {e}\n")
            return 2
        SNAPSHOT_PATH.unlink()
        print(f"[S209] reverted {len(payload['created'])} seed actions; snapshot cleared")
        return 0

    actions: list[dict] = []
    if args.scenario in ("V1", "BOTH"):
        actions.extend(scenario_v1_seed(picks))
    if args.scenario in ("V2", "BOTH"):
        # V2 needs current stock probe to compute delta
        v2_pick = picks.get("V2_AYALA_VERMOSA", {})
        if v2_pick and v2_pick.get("item_code"):
            out = run_in_container(_build_stock_probe_script([
                ("V2_CURRENT", "AYALA VERMOSA - BEBANG MEGA INC.", v2_pick["item_code"]),
            ]))
            probe = _extract(out, "__S209_PROBE_START__", "__S209_PROBE_END__")
            current = probe["stock"][0]["actual_qty"]
            print(f"[S209] V2 current qty at AYALA VERMOSA for {v2_pick['item_code']}: {current}")
            actions.extend(scenario_v2_seed(picks, current))

    if not actions:
        print("[S209] no seed actions needed")
        return 0

    print(f"[S209] Seeding {len(actions)} stock entries...")
    out = run_in_container(_build_seed_script(actions))
    payload = _extract(out, "__S209_SEED_START__", "__S209_SEED_END__")
    if payload["errors"]:
        for e in payload["errors"]:
            sys.stderr.write(f"  [seed-error] {e}\n")
        return 2

    # Record snapshot for revert — append to existing if revert-pending
    existing = []
    if SNAPSHOT_PATH.exists():
        try:
            existing = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    existing.extend(payload["created"])
    SNAPSHOT_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    print(f"[S209] seeded {len(payload['created'])} entries; snapshot @ {SNAPSHOT_PATH}")
    for row in payload["created"]:
        print(f"  {row['label']}: {row['type']} {row['qty']} of {row['item_code']} @ {row['warehouse']} (SE {row['stock_entry']})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
