#!/usr/bin/env python3
"""S167 handoff snapshot — verifiable ground truth for the handoff document."""
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

snap = {}

# Dept PCF funds
snap["dept_funds"] = frappe.db.sql("""
    SELECT name, fund_type, department, store, custodian, fund_amount,
           threshold_percentage, is_enabled
    FROM `tabBEI Petty Cash Fund`
    WHERE fund_type = 'Department'
    ORDER BY name
""", as_dict=True)

# Store PCF fund (TEST-STORE-BGC)
snap["test_store_fund"] = frappe.db.get_value(
    "BEI Petty Cash Fund", "PCF-TEST-STORE-BGC - BEI",
    ["name", "fund_type", "store", "custodian", "fund_amount", "threshold_percentage", "is_enabled"],
    as_dict=True,
)

# TEST-STORE-BGC - BEI warehouse
snap["test_warehouse"] = frappe.db.get_value(
    "Warehouse", "TEST-STORE-BGC - BEI",
    ["name", "company", "is_group", "disabled"],
    as_dict=True,
)

# Test employees (current state)
for emp in ["TEST-HR-001", "TEST-STAFF-001", "TEST-SUPERVISOR-001",
            "TEST-COMMISSARY-001", "TEST-WAREHOUSE-001", "TEST-FINANCE-001"]:
    snap.setdefault("test_employees", {})[emp] = frappe.db.get_value(
        "Employee", emp,
        ["name", "status", "user_id", "department", "branch", "company"],
        as_dict=True,
    )

# Recent PCF activity (last 24h)
snap["recent_expenses"] = frappe.db.sql("""
    SELECT name, employee_name, manual_vendor, manual_amount, pcf_fund, status, pcf_batch
    FROM `tabBEI Expense Request`
    WHERE pcf_fund IN ('PCF-HR and Admin','PCF-Supply Chain','PCF-Commissary','PCF-TEST-STORE-BGC - BEI')
      AND creation > DATE_SUB(NOW(), INTERVAL 24 HOUR)
    ORDER BY creation DESC
""", as_dict=True)

snap["recent_batches"] = frappe.db.sql("""
    SELECT name, pcf_fund, status, total_amount, expense_count
    FROM `tabBEI PCF Batch`
    WHERE pcf_fund IN ('PCF-HR and Admin','PCF-Supply Chain','PCF-Commissary','PCF-TEST-STORE-BGC - BEI')
      AND creation > DATE_SUB(NOW(), INTERVAL 24 HOUR)
    ORDER BY creation DESC
""", as_dict=True)

print("=== HANDOFF SNAPSHOT ===")
print(json.dumps(snap, indent=2, default=str))
frappe.destroy()
