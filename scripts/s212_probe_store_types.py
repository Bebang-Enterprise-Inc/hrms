#!/usr/bin/env python3
"""Probe store_type distribution and dispatch behavior for all 8 attempted stores."""
import base64, gzip, json, pathlib, sys, time

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"
OUT = pathlib.Path(__file__).resolve().parent.parent / "output" / "l3" / "s212" / "store_type_probe.json"

SCRIPT = '''
import base64, gzip, json
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

from hrms.utils.supply_chain_contracts import resolve_store_buyer_entity

stores = [
    "ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC",
    "AYALA FAIRVIEW TERRACES - BEBANG FT INC.",
    "AYALA MARKET MARKET - BEBANG MARKET MARKET INC.",
    "AYALA SOLENAD - HFFM SOLENAD FOOD SERVICES INC.",
    "AYALA UP TOWN CENTER - BEBANG UP TOWN CENTER INC.",
    "AYALA VERMOSA - BEBANG MEGA INC.",
    "BF HOMES - BEBANG BF HOMES INC.",
    "CTTM TOMAS MORATO - B CUBED VENTURES CORP.",
]

results = []
for wh in stores:
    entity = resolve_store_buyer_entity(warehouse_docname=wh) or {}
    results.append({
        "warehouse": wh,
        "buyer_entity_name": entity.get("buyer_entity_name"),
        "store_type": entity.get("store_type"),
        "store_ownership_type": entity.get("store_ownership_type"),
        "buyer_entity_status": entity.get("buyer_entity_status"),
    })

# Also pull all distinct store_types registered
distinct = frappe.db.sql(
    "SELECT DISTINCT store_ownership_type FROM `tabCompany` WHERE entity_category='Store' ORDER BY 1",
    as_dict=True,
)

# Also pull BEI Settings markup fields
settings = frappe.get_single("BEI Settings")
meta = settings.meta
markup_fields = [f.fieldname for f in meta.fields if "markup" in (f.fieldname or "").lower()]
markup_values = {k: getattr(settings, k, None) for k in markup_fields}

payload = {
    "attempted_stores": results,
    "distinct_ownership_types": [r["store_ownership_type"] for r in distinct],
    "markup_fields": markup_fields,
    "markup_values": markup_values,
}
compressed = gzip.compress(json.dumps(payload, default=str).encode())
print("__B64_START__")
print(base64.b64encode(compressed).decode())
print("__B64_END__")
frappe.destroy()
'''

def run(timeout=60):
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s212_st.py",
        "docker cp /tmp/s212_st.py $BACKEND:/tmp/s212_st.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s212_st.py",
    ]
    r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": [str(timeout)]})
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
                sys.stderr.write(err); raise RuntimeError(inv["Status"])
            return out
    raise TimeoutError()

out = run()
s = out.find("__B64_START__"); e = out.find("__B64_END__")
b64 = out[s+len("__B64_START__"):e].strip()
data = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
OUT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
print(f"Wrote {OUT}")
print()
print("=== ATTEMPTED STORES ===")
for r in data["attempted_stores"]:
    print(f"  {r['warehouse'][:40]:40s} | store_type={r['store_type']!r:30s} | ownership={r['store_ownership_type']!r}")
print()
print("=== DISTINCT OWNERSHIP TYPES (store Companies) ===")
for t in data["distinct_ownership_types"]:
    print(f"  {t!r}")
print()
print("=== BEI SETTINGS MARKUP FIELDS ===")
for k, v in data["markup_values"].items():
    print(f"  {k} = {v!r}")
