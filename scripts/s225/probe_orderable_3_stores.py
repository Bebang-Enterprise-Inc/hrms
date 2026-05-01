"""Probe get_orderable_items for the 3 PRECONDITION_BLOCKED stores.
Find out what's filtering items down to 0 (or what makes the API empty)."""
import sys, io
# Suppress any chatty stdout from frappe initialization
_buf = io.StringIO()
_old_stdout = sys.stdout
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
sys.stdout = _buf  # capture frappe's own prints so they don't muddy JSON
import frappe, json
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
sys.stdout = _old_stdout  # restore for our final json.dumps

STORES = [
    "AYALA EVO CITY - BEBANG MEGA INC.",
    "ROBINSONS PLACE DASMARINAS - FREEZE DELIGHT INC.",
    "XENTROMALL MONTALBAN - PERPETUAL FOOD CORP.",
]
# Known-good for comparison
WORKING = ["ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC"]

result = {}
for store in STORES + WORKING:
    s = {}
    # Call the API directly
    try:
        from hrms.api.store import get_orderable_items
        api_result = get_orderable_items(store)
        items = api_result.get("data", {}).get("items") or []
        s["api_items_count"] = len(items)
        s["api_first_3_codes"] = [it.get("item_code") for it in items[:3]]
        s["api_first_3_suggested"] = [(it.get("item_code"), it.get("suggested_qty"), it.get("delivery_lane")) for it in items[:3]]
        s["api_total_with_suggested_gt_0"] = sum(1 for it in items if (it.get("suggested_qty") or 0) > 0)
        s["api_total_dry_lane"] = sum(1 for it in items if it.get("delivery_lane") == "Dry")
        s["api_total_dry_with_suggested"] = sum(1 for it in items if (it.get("suggested_qty") or 0) > 0 and it.get("delivery_lane") == "Dry")
    except Exception as e:
        import traceback
        s["api_error"] = str(e)[:300]
        s["api_traceback"] = traceback.format_exc()[:1500]

    # BEI Routes for this store warehouse
    routes = frappe.db.sql("""
        SELECT br.name, br.cargo_type, br.source_warehouse, br.active
        FROM `tabBEI Route Stop` brs
        INNER JOIN `tabBEI Route` br ON br.name = brs.parent
        WHERE brs.store = %(s)s
        ORDER BY br.cargo_type
    """, {"s": store}, as_dict=True)
    s["routes_count"] = len(routes)
    s["routes"] = [dict(r) for r in routes]

    # Past order count
    cnt = frappe.db.sql("""
        SELECT COUNT(*) AS c FROM `tabBEI Store Order` WHERE store = %s AND status != 'Draft'
    """, (store,), as_dict=True)
    s["past_orders_count"] = cnt[0]["c"] if cnt else 0

    result[store] = s

print(json.dumps(result, indent=2, default=str))
