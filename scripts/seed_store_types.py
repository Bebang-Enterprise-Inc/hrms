"""
Seed BEI Store Type records in production.

Run via bench console:
    bench --site hq.bebang.ph console < scripts/seed_store_types.py

Or pipe via SSM/Docker:
    cat scripts/seed_store_types.py | docker exec -i <container> bench --site hq.bebang.ph console

Source: Google Sheet - Store Type Classification
https://docs.google.com/spreadsheets/d/1gJojjZ3CeYxGoA2Aw0EqPuWejmmwTI6qmN8LDQFVxCs

52 stores: 24 JV, 26 Managed Franchise, 2 Full Franchise
"""
import frappe

STORE_TYPES = [
    {"store": "SM MEGAMALL", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "AYALA MARKET MARKET", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "SM MANILA", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "SM SOUTHMALL", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "AYALA FAIRVIEW TERRACES", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "SM NORTH EDSA", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "SM VALENZUELA", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "LUCKY CHINATOWN", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "ROBINSONS ANTIPOLO", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "THE TERMINAL", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "GRAND CENTRAL", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "SM MARIKINA", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "MEGAWORLD PASEO CENTER", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "PITX", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "SM EAST ORTIGAS", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "VENICE GRAND CANAL", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "FESTIVAL MALL ALABANG", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "BGC", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "SM MOA", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "EVER GOTESCO COMMONWEALTH", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "BF HOMES", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "SM SJDM", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "SM TANZA", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "SM SANGANDAAN", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "SM MARILAO", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "SM BICUTAN", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "SM CALOOCAN", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "ROBINSONS IMUS", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "AYALA UPTC", "store_type": "Full Franchise", "royalty_rate": 7, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "AYALA EVO", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "AYALA VERMOSA", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "ROBINSONS GENERAL TRIAS", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "SM PULILAN", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "AYALA SOLENAD", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "STA LUCIA EAST GRAND MALL", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "ROBINSONS GALLERIA SOUTH", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "NAIA TERMINAL 3", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "UPTOWN BGC", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "AYALA ALABANG TOWN CENTER", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "SM CLARK", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "CTTM TOMAS MORATO", "store_type": "Full Franchise", "royalty_rate": 7, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "VISTA MALL TAGUIG", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "ARANETA GATEWAY", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "ROBINSONS DASMARINAS", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "SM TAYTAY", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "D VERDE CALAMBA", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "ORTIGAS GREENHILLS", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "ORTIGAS ESTANCIA", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "SM STA ROSA", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
    {"store": "SM SAN PABLO", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "SM BATANGAS", "store_type": "JV", "royalty_rate": 0, "management_fee_rate": 0, "marketing_fee_rate": 5, "price_list_multiplier": 0},
    {"store": "XENTRO MONTALBAN", "store_type": "Managed Franchise", "royalty_rate": 7, "management_fee_rate": 2.5, "marketing_fee_rate": 5, "price_list_multiplier": 8},
]

created = 0
updated = 0
skipped = 0
errors = []

print(f"Seeding {len(STORE_TYPES)} BEI Store Type records...")

for rec in STORE_TYPES:
    store = rec["store"]
    try:
        # Check if department exists first
        if not frappe.db.exists("Department", store):
            # Try with " - BEI" suffix (Frappe department naming convention)
            dept_with_suffix = f"{store} - BEI"
            if not frappe.db.exists("Department", dept_with_suffix):
                errors.append(f"SKIP {store}: Department not found (tried '{store}' and '{dept_with_suffix}')")
                skipped += 1
                continue
            else:
                rec["store"] = dept_with_suffix
                store = dept_with_suffix

        if frappe.db.exists("BEI Store Type", store):
            doc = frappe.get_doc("BEI Store Type", store)
            doc.store_type = rec["store_type"]
            doc.royalty_rate = rec["royalty_rate"]
            doc.management_fee_rate = rec["management_fee_rate"]
            doc.marketing_fee_rate = rec["marketing_fee_rate"]
            doc.price_list_multiplier = rec["price_list_multiplier"]
            doc.save(ignore_permissions=True)
            updated += 1
            print(f"  Updated: {store} ({rec['store_type']})")
        else:
            frappe.get_doc({
                "doctype": "BEI Store Type",
                "store": store,
                "store_type": rec["store_type"],
                "royalty_rate": rec["royalty_rate"],
                "management_fee_rate": rec["management_fee_rate"],
                "marketing_fee_rate": rec["marketing_fee_rate"],
                "price_list_multiplier": rec["price_list_multiplier"],
            }).insert(ignore_permissions=True)
            created += 1
            print(f"  Created: {store} ({rec['store_type']})")
    except Exception as e:
        errors.append(f"ERROR {store}: {str(e)}")

frappe.db.commit()

print(f"\nDone! Created: {created}, Updated: {updated}, Skipped: {skipped}")
if errors:
    print(f"\nErrors/Warnings ({len(errors)}):")
    for e in errors:
        print(f"  {e}")
