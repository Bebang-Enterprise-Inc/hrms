"""Build the full store_name -> canonical per-store Company mapping from S037 + Company."""
import base64, sys, time

SCRIPT = r'''
import frappe, json
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

from hrms.api.company_master import _load_s037_rows

# All canonical per-store Companies
canonical = sorted(frappe.db.sql(
    """SELECT name FROM `tabCompany`
       WHERE entity_category = 'Store'
         AND (operational_status IS NULL OR operational_status NOT IN ('Permanently Closed','Dormant'))""",
    as_list=True,
), key=lambda x: x[0])

print(f"Canonical Companies: {len(canonical)}")
canonical_names = [c[0] for c in canonical]

# S037 rows
s037 = _load_s037_rows()
print(f"S037 store rows: {len(s037)}")

# Match each S037 store_name to its canonical Company by substring
mapping = {}
unmatched = []
for row in s037:
    store_name = (row.get("store_name") or "").strip()
    if not store_name:
        continue
    # Extract the store label (everything before the " - <parent>" suffix)
    # in canonical Company names, compare with normalized store_name
    best = None
    best_score = 0
    # Try exact substring match (case-insensitive)
    store_upper = store_name.upper().replace("!", "").replace("  ", " ")
    for co in canonical_names:
        # The canonical is "<STORE LABEL> - <PARENT>". Split on first " - "
        label_part = co.split(" - ", 1)[0].strip().upper()
        # Also compare without any special chars
        label_simple = label_part.replace(".", "").replace(",", "").replace("!", "")
        store_simple = store_upper.replace(".", "").replace(",", "")
        if label_simple == store_simple:
            best = co
            best_score = 1000
            break
        # Fuzzy: store is substring of label or vice versa
        if store_simple and (store_simple in label_simple or label_simple in store_simple):
            score = min(len(store_simple), len(label_simple))
            if score > best_score:
                best = co
                best_score = score
    if best:
        mapping[store_name] = best
    else:
        unmatched.append((store_name, row.get("buyer_entity_name")))

print(f"\nMapped: {len(mapping)}/49")
print(f"Unmatched: {len(unmatched)}")
for u in unmatched:
    print(f"  {u[0]!r} (buyer: {u[1]!r})")

# Print as Python dict literal for pasting into company_master.py
print("\n\n# --- paste this into _STORE_TO_CHILD in company_master.py ---")
print("_STORE_TO_CHILD: dict[str, str] = {")
for store, company in sorted(mapping.items()):
    print(f"    {store!r}: {company!r},")
print("}")

frappe.destroy()
'''

enc = base64.b64encode(SCRIPT.encode()).decode()
cmds = [
    "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
    f"echo '{enc}' | base64 -d > /tmp/bm.py",
    "docker cp /tmp/bm.py $BACKEND:/tmp/bm.py",
    "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/bm.py",
]
import boto3
ssm = boto3.client("ssm", region_name="ap-southeast-1")
r = ssm.send_command(InstanceIds=["i-026b7477d27bd46d6"], DocumentName="AWS-RunShellScript",
    Parameters={"commands": cmds, "executionTimeout": ["120"]})
cid = r["Command"]["CommandId"]
for _ in range(40):
    time.sleep(3)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId="i-026b7477d27bd46d6")
    if inv["Status"] in ("Success", "Failed", "TimedOut"):
        print(inv["StandardOutputContent"])
        sys.exit(0 if inv["Status"] == "Success" else 1)
