import os, sys
from datetime import date, timedelta

for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)

import frappe

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Delivery schedule based on Q1 2026 actual frequency
# warehouse_name -> {delivery_type: [day_of_week]}
SCHEDULE = {
    "Araneta Gateway":              {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Tue", "Thu"]},
    "Ayala Evo":                    {"COLD": ["Tue", "Thu"],        "DRY": ["Wed", "Fri"]},
    "Ayala Malls Fairview Terraces":{"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Mon", "Wed", "Fri"]},
    "Ayala Market Market":          {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Mon", "Wed", "Fri"]},
    "Ayala Solenad":                {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Tue", "Thu"]},
    "Ayala UPTC":                   {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Mon", "Wed", "Fri"]},
    "Ayala Vermosa":                {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Tue", "Thu"]},
    "BF Homes":                     {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Mon", "Wed", "Fri"]},
    "CTTM Tomas Morato":            {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Mon", "Wed", "Fri"]},
    "D'verde Laguna":               {"COLD": ["Tue", "Thu"],        "DRY": ["Wed", "Fri"]},
    "Ever Commonwealth":            {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Mon", "Wed", "Fri"]},
    "Festival Mall Alabang":        {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Tue", "Thu"]},
    "Greenhills Ortigas":           {"COLD": ["Wed", "Fri"],        "DRY": ["Wed"]},
    "Lucky Chinatown":              {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Tue", "Thu"]},
    "Megawide PITX":                {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Tue", "Thu"]},
    "Megaworld Paseo Center":       {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Mon", "Wed", "Fri"]},
    "Megaworld Venice Grand Canal": {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Mon", "Wed", "Fri"]},
    "NAIA T3":                      {"COLD": ["Tue", "Thu"],        "DRY": ["Wed", "Fri"]},
    "Robinson General Trias":       {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Tue", "Thu"]},
    "Robinson Imus":                {"COLD": ["Tue", "Thu"],        "DRY": ["Tue", "Thu"]},
    "Robinsons Antipolo":           {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Tue", "Thu"]},
    "Robisons Galleria South":      {"COLD": ["Tue", "Thu"],        "DRY": ["Wed", "Fri"]},
    "SJDM":                         {"COLD": ["Tue", "Thu"],        "DRY": ["Tue", "Thu"]},
    "SM Bicutan":                    {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Mon", "Wed", "Fri"]},
    "SM Caloocan":                   {"COLD": ["Tue", "Thu"],        "DRY": ["Wed", "Fri"]},
    "SM Clark":                      {"COLD": ["Tue", "Thu"],        "DRY": ["Wed", "Fri"]},
    "SM East Ortigas":               {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Mon", "Wed", "Fri"]},
    "SM Grand Central":              {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Wed", "Fri"]},
    "SM Mall Of Asia":               {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Mon", "Wed", "Fri"]},
    "SM  Manila":                    {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Tue", "Thu"]},
    "SM Marikina":                   {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Mon", "Wed", "Fri"]},
    "SM Marilao":                    {"COLD": ["Tue", "Thu"],        "DRY": ["Tue", "Thu"]},
    "SM Megamall":                   {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Tue", "Thu"]},
    "SM North EDSA":                 {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Mon", "Wed", "Fri"]},
    "SM Pulilan":                    {"COLD": ["Tue", "Thu"],        "DRY": ["Tue", "Thu"]},
    "SM San Pablo":                  {"COLD": ["Tue", "Thu"],        "DRY": ["Wed"]},
    "SM Sangandaan":                 {"COLD": ["Tue", "Thu"],        "DRY": ["Wed", "Fri"]},
    "SM Southmall":                  {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Tue", "Thu"]},
    "SM Sta. Rosa":                  {"COLD": ["Tue", "Thu"],        "DRY": ["Tue", "Thu"]},
    "SM Tanza":                      {"COLD": ["Tue", "Thu"],        "DRY": ["Tue", "Thu"]},
    "SM Taytay":                     {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Tue", "Thu"]},
    "SM Valenzuela":                 {"COLD": ["Tue", "Thu"],        "DRY": ["Tue", "Thu"]},
    "Sta. Lucia East Grand Mall":    {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Tue", "Thu"]},
    "The Grid - Rockwell":           {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Mon", "Wed", "Fri"]},
    "The Terminal":                  {"COLD": ["Tue", "Thu"],        "DRY": ["Tue", "Thu"]},
    "Up Town Mall BGC":              {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Mon", "Wed", "Fri"]},
    "Vista Mall Taguig":             {"COLD": ["Mon", "Wed", "Fri"], "DRY": ["Mon", "Wed", "Fri"]},
}

# Find this week's Monday
today = date.today()
monday = today - timedelta(days=today.weekday())
week_start = str(monday)

print("Creating delivery schedule for week of %s" % week_start)
print("Stores: %d" % len(SCHEDULE))

# Build warehouse_name -> DocName map from Frappe
wh_map = {}
warehouses = frappe.get_all("Warehouse", filters={"is_group": 0}, fields=["name", "warehouse_name"], limit_page_length=200)
for wh in warehouses:
    if wh.warehouse_name:
        wh_map[wh.warehouse_name] = wh.name

# Check if schedule already exists for this week
existing = frappe.db.get_value("BEI Delivery Schedule Week", {"week_start": week_start}, "name")
if existing:
    print("Schedule already exists: %s — deleting and recreating" % existing)
    frappe.delete_doc("BEI Delivery Schedule Week", existing, force=True, ignore_permissions=True)
    frappe.db.commit()

# Create the schedule
doc = frappe.new_doc("BEI Delivery Schedule Week")
doc.week_start = week_start
doc.published = 1

entries_added = 0
skipped = []

for wh_name, schedule in sorted(SCHEDULE.items()):
    docname = wh_map.get(wh_name)
    if not docname:
        skipped.append(wh_name)
        print("  SKIP: no warehouse for '%s'" % wh_name)
        continue

    for delivery_type, days in schedule.items():
        for day in days:
            doc.append("entries", {
                "store": docname,
                "day_of_week": day,
                "delivery_type": delivery_type,
            })
            entries_added += 1

print("Entries added: %d" % entries_added)
if skipped:
    print("Skipped: %s" % skipped)

try:
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    print("Created: %s (published=%s)" % (doc.name, doc.published))
except Exception as e:
    print("ERROR: %s" % str(e)[:200])
    import traceback
    traceback.print_exc()

# Verify
count = frappe.db.count("BEI Delivery Schedule Entry", {"parent": doc.name})
print("Entries in DB: %d" % count)

# Also check Estancia warehouse
estancia = frappe.db.exists("Warehouse", "Estancia - BEI")
print("Estancia warehouse exists: %s" % bool(estancia))

print("DELIVERY-SCHEDULE-DONE")
frappe.destroy()
