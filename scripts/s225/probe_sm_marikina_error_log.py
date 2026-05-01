"""Find any frappe.log_error entries connected to SM MARIKINA's SE/MR.
The auto-WR-creation in `_create_warehouse_receiving_for_se` swallows exceptions
via `frappe.log_error(...)` — that goes to the Error Log doctype.

We're hunting for entries logged in the last 90 minutes that mention either
the MR (MAT-MR-2026-00886), the SE (MAT-STE-2026-02189), or 'S198: Auto-create WR'."""
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

# 1. Errors mentioning the SE or MR or "S198"
errors = frappe.db.sql("""
    SELECT name, error, method, creation
    FROM `tabError Log`
    WHERE creation > NOW() - INTERVAL 90 MINUTE
      AND (error LIKE %(se)s OR error LIKE %(mr)s OR error LIKE '%%S198%%' OR method LIKE '%%warehouse%%')
    ORDER BY creation DESC
    LIMIT 15
""", {
    "se": "%MAT-STE-2026-02189%",
    "mr": "%MAT-MR-2026-00886%",
}, as_dict=True)
result["error_log_entries"] = []
for e in errors:
    result["error_log_entries"].append({
        "name": e["name"],
        "creation": str(e["creation"]),
        "method": e.get("method"),
        "error_first_500": (e["error"] or "")[:500],
    })

# 2. Try to call _create_warehouse_receiving_for_se directly with the SE doc to see what happens
try:
    se = frappe.get_doc("Stock Entry", "MAT-STE-2026-02189")

    # Replicate the resolve_material_request_contract call path
    from hrms.utils.supply_chain_contracts import resolve_material_request_contract
    from hrms.api.warehouse import _create_warehouse_receiving_for_se, resolve_warehouse_company, _get_commissary_company

    contract = resolve_material_request_contract(frappe.get_doc("Material Request", "MAT-MR-2026-00886"))
    result["resolved_contract"] = dict(contract)

    # Check the BKI scope guard manually
    source_company = resolve_warehouse_company(se.from_warehouse)
    bki = _get_commissary_company()
    result["bki_guard_check"] = {
        "se.from_warehouse": se.from_warehouse,
        "resolved_source_company": source_company,
        "commissary_company": bki,
        "guard_passes": source_company == bki,
    }

    # Now actually call _create_warehouse_receiving_for_se with same path the dispatch uses
    # (it must NOT raise, must return a name or None)
    wr_name = _create_warehouse_receiving_for_se(se, contract)
    result["replay_create_wr"] = {
        "wr_name_returned": wr_name,
    }
    # Check immediately if a WR exists for this SE now
    existing = frappe.db.get_value(
        "BEI Warehouse Receiving",
        {"stock_entry": se.name},
        "name",
    )
    result["wr_exists_after_replay"] = existing
except Exception as e:
    import traceback
    result["replay_error"] = {
        "msg": str(e)[:300],
        "trace_first_2000": traceback.format_exc()[:2000],
    }

print(json.dumps(result, indent=2, default=str))
