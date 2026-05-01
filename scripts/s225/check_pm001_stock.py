"""Quick PM001/FG001 stock probe — run via SSM/docker exec on production container."""
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

result = {}
for item in ["PM001", "FG001"]:
    rows = frappe.get_all("Bin",
        filters={"item_code": item, "actual_qty": [">", -1000]},
        fields=["warehouse", "actual_qty", "reserved_qty", "projected_qty"],
        order_by="actual_qty desc",
        limit=20)
    nonzero = [r for r in rows if r.get("actual_qty") > 0]
    zero = [r for r in rows if r.get("actual_qty") == 0]
    result[item] = {
        "total_bins": len(rows),
        "nonzero_count": len(nonzero),
        "zero_count": len(zero),
        "top_5_nonzero": nonzero[:5],
        "sample_zero": zero[:3],
    }

print(json.dumps(result, indent=2, default=str))
