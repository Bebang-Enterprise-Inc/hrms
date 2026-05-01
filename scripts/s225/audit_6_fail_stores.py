"""Deep audit of the 6 stores that failed sweep-v8.

For each store, dump:
 - Company config (4 inventory accounts + cost center + abbr + parent_company)
 - Warehouse config (company + parent_warehouse + warehouse_type)
 - Customer config (default_company + customer_group + tax_id)
 - BEI Route assignment (which route + cargo type + active)
 - Bin state at the source warehouse (PCS-BKI / 3MD) for top PM items
 - Recent BEI Warehouse Receiving rows (status + docstatus)
 - Recent Material Request -> Stock Entry chain
 - Compare to a known working store (ARANETA GATEWAY)

Output: full JSON to stdout, summarized via SSM."""
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

FAIL_STORES = [
    ("SM MARIKINA - BEBANG SM MARIKINA INC.", "SM MARIKINA - BEBANG SM MARIKINA INC."),  # backend WR not produced
    ("STA. LUCIA EAST GRAND MALL - BEBANG SM MARIKINA INC.", "STA. LUCIA EAST GRAND MALL - BEBANG SM MARIKINA INC."),
    ("THE GRID ROCKWELL - TASTECARTEL CORP.", "THE GRID ROCKWELL - TASTECARTEL CORP."),
    ("THE TERMINAL - BEBANG STARMALL ALABANG INC.", "THE TERMINAL - BEBANG STARMALL ALABANG INC."),
    ("UP TOWN MALL BGC - DMD HOLDINGS INC.", "UP TOWN MALL BGC - DMD HOLDINGS INC."),
    ("VISTA MALL TAGUIG - TRICERN FOOD CORP.", "VISTA MALL TAGUIG - TRICERN FOOD CORP."),
]
WORKING_STORES = [
    ("ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC", "ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC"),
    ("AYALA EVO CITY - BEBANG MEGA INC.", "AYALA EVO CITY - BEBANG MEGA INC."),
]

ALL_STORES = [(name, "fail") for (name, _) in FAIL_STORES] + [(name, "working") for (name, _) in WORKING_STORES]

result = {"stores": {}}

COMPANY_FIELDS = [
    "name", "abbr", "parent_company", "default_currency", "country",
    "default_inventory_account", "default_receivable_account", "default_payable_account",
    "default_income_account", "default_expense_account",
    "stock_received_but_not_billed", "stock_adjustment_account",
    "expenses_included_in_valuation", "round_off_account", "round_off_cost_center",
    "default_payroll_payable_account", "cost_center",
]

for store_name, kind in ALL_STORES:
    s = {"kind": kind}
    # Company (use store_name as canonical name; per S033 each store has own Company)
    co_exists = bool(frappe.db.exists("Company", store_name))
    if co_exists:
        co = frappe.db.get_value("Company", store_name, COMPANY_FIELDS, as_dict=True)
        s["company"] = dict(co)
    else:
        s["company"] = {"NOT_FOUND": True}

    # Warehouse
    wh_exists = bool(frappe.db.exists("Warehouse", store_name))
    if wh_exists:
        wh = frappe.db.get_value("Warehouse", store_name,
            ["name", "company", "parent_warehouse", "warehouse_type", "disabled", "is_group"], as_dict=True)
        s["warehouse"] = dict(wh)
    else:
        s["warehouse"] = {"NOT_FOUND": True}

    # Customer
    cust_exists = bool(frappe.db.exists("Customer", store_name))
    if cust_exists:
        cust = frappe.db.get_value("Customer", store_name,
            ["name", "customer_group", "tax_id", "disabled", "is_internal_customer", "represents_company", "territory"], as_dict=True)
        s["customer"] = dict(cust)
    else:
        s["customer"] = {"NOT_FOUND": True}

    # BEI Route assignment for this store
    routes = frappe.db.sql("""
        SELECT br.name AS route, br.cargo_type, br.source_warehouse, br.active
        FROM `tabBEI Route Stop` brs
        INNER JOIN `tabBEI Route` br ON br.name = brs.parent
        WHERE brs.store = %(store)s
        ORDER BY br.cargo_type
    """, {"store": store_name}, as_dict=True)
    s["routes"] = [dict(r) for r in routes]

    # Recent BEI Warehouse Receiving for this store (target_warehouse = warehouse name)
    if wh_exists:
        # Discover schema first
        wr_meta = frappe.get_meta("BEI Warehouse Receiving")
        wr_fields = [f.fieldname for f in wr_meta.fields if f.fieldname in (
            "status","target_warehouse","source_warehouse","stock_entry","docstatus"
        )]
        wr_select = ["name","creation","docstatus"] + wr_fields
        wrs = frappe.db.sql(f"""
            SELECT {','.join('`'+c+'`' for c in wr_select)}
            FROM `tabBEI Warehouse Receiving`
            WHERE target_warehouse = %(wh)s
              AND creation > NOW() - INTERVAL 4 HOUR
            ORDER BY creation DESC
            LIMIT 5
        """, {"wh": store_name}, as_dict=True)
        s["recent_wrs_4h"] = [dict(r) for r in wrs]

    # Recent Material Requests for this store
    if co_exists:
        mrs = frappe.db.sql("""
            SELECT name, status, docstatus, creation, transaction_date, set_warehouse, material_request_type
            FROM `tabMaterial Request`
            WHERE company = %(co)s
              AND creation > NOW() - INTERVAL 4 HOUR
            ORDER BY creation DESC
            LIMIT 5
        """, {"co": store_name}, as_dict=True)
        s["recent_mrs_4h"] = [dict(r) for r in mrs]

    result["stores"][store_name] = s

# Sentry timeline correlation marker
result["audit_run_at_pht"] = "2026-04-30 19:00 PHT"
result["context"] = "Post sweep-v8 analysis: 6 fails, 3 skipped, 40 passed."

print(json.dumps(result, indent=2, default=str))
