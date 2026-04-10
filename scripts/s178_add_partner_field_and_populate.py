#!/usr/bin/env python3
"""Create partner_names Custom Field on Company + populate from team's register."""
import json, os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

r = {"steps": [], "errors": []}

# ============================================================
# Step 1: Create partner_names Custom Field
# ============================================================
try:
    if frappe.db.exists("Custom Field", "Company-partner_names"):
        r["steps"].append("partner_names Custom Field already exists")
    else:
        cf = frappe.new_doc("Custom Field")
        cf.dt = "Company"
        cf.fieldname = "partner_names"
        cf.label = "Franchisee / Partner Names"
        cf.fieldtype = "Small Text"
        cf.insert_after = "store_locations"
        cf.description = "Names of franchisees or JV partners who own or operate this entity. Searchable in dropdowns and filterable in reports."
        cf.in_list_view = 1
        cf.in_standard_filter = 0
        cf.search_index = 0
        cf.insert(ignore_permissions=True)
        frappe.db.commit()
        r["steps"].append("partner_names Custom Field created")

    # Materialize column if missing
    cols = frappe.db.sql("SHOW COLUMNS FROM `tabCompany` LIKE 'partner_names'")
    if not cols:
        frappe.db.sql("ALTER TABLE `tabCompany` ADD COLUMN `partner_names` TEXT")
        frappe.db.commit()
        r["steps"].append("partner_names column materialized via ALTER TABLE")
    else:
        r["steps"].append("partner_names column already exists")

except Exception as e:
    r["errors"].append(f"Step 1: {e}")

# ============================================================
# Step 2: Populate partner_names from team's register
# ============================================================
try:
    # Partner data from the team's completed XLSX (extracted to CSV)
    # Format: company_name -> partner names (newline-separated in source, we'll use comma-separated)
    partner_data = {
        "DMD HOLDINGS INC.": "Andrew Rodel Manansala",
        "BEBANG BF HOMES INC.": "Edward Cheson Sy, Ralph Kenneth Ty",
        "BEBANG FESTIVAL INC.": "Jose Paulo Legaspi",
        "BEBANG FT INC.": "Andrew Rodel Manansala",
        "BEBANG GRAND CENTRAL INC.": "Rommel Gabaldon, Veronica Gabaldon",
        "BEBANG LCT INC.": "Ian Umali",
        "BEBANG MARILAO INC.": "Hernando Diokno Hernandez",
        "BEBANG MARKET MARKET INC.": "Andrew Rodel Manansala",
        "BEBANG MEGA INC.": "Ian Umali",
        "BEBANG NORTH EDSA INC.": "Andrew Rodel Manansala",
        "BEBANG PASEO INC.": "Julian Anthony De Guzman, Lorenzo Santos Castillo",
        "BEBANG PITX INC.": "Jose Paulo Legaspi",
        "BEBANG SM BICUTAN INC.": "Vishal Shaq Daswani",
        "BEBANG SM MARIKINA INC.": "Imelda Soriano, Ana Soriano",
        "BEBANG SMEO INC.": "Lorenzo Castillo, Julian Anthony De Guzman",
        "BEBANG SMM INC.": "Lewis Alfred V Tenorio, Kiefer Isaac Crisologo Ravena",
        "BEBANG SMOA INC.": "Ian Umali",
        "BEBANG SMV INC.": "Benjamin Christopher Sunga",
        "BEBANG STARMALL ALABANG INC.": "Jose Paulo Legaspi",
        "BEBANG UP TOWN CENTER INC.": "Imelda Soriano, Ana Soriano, Dennis Soriano",
        "BEBANG VENICE GRAND CANAL INC.": "Rommel Gabaldon, Veronica Gabaldon",
    }

    # These companies have names that the team CHANGED in the XLSX
    # but Frappe still has the old names. We populate using the CURRENT Frappe names.
    # The rename will happen in Phase 2 of S178.
    partner_data_external = {
        # Current Frappe name -> partner names
        "BEBANG ARANETA GATEWAY": "Wilford Wong, Winchell Wong, Wei Min Choy",  # will become TUNGSTEN CAPITAL HOLDINGS OPC
        "BEBANG AYALA SOLENAD": "Francis Patrick Jose Fontanilla Tanjangco, Francisco Suntay Tanjangco, Hernando Diokno Hernandez",  # will become HFFM SOLENAD
        "BEBANG D'VERDE": "Alyssa Young, Timothy Patrick Uy, Pablo Hicban",  # will become TAJ FOOD CORP
        "BEBANG EVER GOTESCO COMMONWEALTH": "Francis Lopez, Angela 'Mai' Mylene C. Sediaren, Michelle Defensor",  # will become DLS Dessert Craft
        "BEBANG SM CALOOCAN": "Alyssa Young, Timothy Patrick Uy, Pablo Hicban",  # stays or becomes TAJ (SM Caloocan branch)
        "BEBANG SM CLARK": "Maria Luisa Gonzales Manliclic, Abel Clarin Manliclic",  # will become RED TALDAWA
        "BEBANG SM SJDM": "Jose Paulo Legaspi, Carla Joyce Garcia",  # will become JL TRADE OPC
        "BEBANG SM TAYTAY": "Kiefer Isaac Crisologo Ravena, Jose Paolo Gabriel Darroca, Mickey Ingles",  # will become DAY ONES
        "BEBANG THE GRID FOOD MARKET": "Howard Paw",  # will become TASTECARTEL CORP
        "BEBANG TOMAS MORATO": "Cherry Go, Jason Go",  # will become B CUBED VENTURES
        "BEBANG VISTAMALL": "Martin Lim",  # will become TRICERN FOOD CORP
        "BEBANG SM SANGANDAAN": "Wilford Wong, Winchell Wong, Wei Min Choy",  # Tungsten Capital (SM Sangandaan branch)
        "BEBANG ROBINSONS GALLERIA SOUTH": "Wilford Wong, Winchell Wong, Wei Min Choy",  # Tungsten Capital (Galleria South branch)
    }

    # BFC-related
    partner_data_special = {
        "BEBANG FRANCHISE CORP.": "(Franchisor entity - BEI 79.97%, Samer Karazi 20%)",
        "Irresistible Infusions Inc.": "(Holding company - BEI 79.97%, Samer Karazi 20%)",
        "Bebang Enterprise Inc.": "(Head Office - parent entity)",
        "Bebang Kitchen Inc.": "(Commissary - subsidiary of BEI)",
    }

    all_partners = {}
    all_partners.update(partner_data)
    all_partners.update(partner_data_external)
    all_partners.update(partner_data_special)

    updated = 0
    not_found = []
    for company_name, partners in all_partners.items():
        if frappe.db.exists("Company", company_name):
            frappe.db.sql(
                "UPDATE `tabCompany` SET partner_names = %s WHERE name = %s",
                (partners, company_name),
            )
            updated += 1
        else:
            not_found.append(company_name)

    frappe.db.commit()
    r["steps"].append(f"Populated partner_names on {updated} companies, {len(not_found)} not found")
    if not_found:
        r["not_found"] = not_found

except Exception as e:
    r["errors"].append(f"Step 2: {e}")

# ============================================================
# Verify
# ============================================================
try:
    with_partners = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabCompany` WHERE partner_names IS NOT NULL AND partner_names != ''"
    )[0][0]
    r["companies_with_partner_names"] = with_partners

    # Sample
    sample = frappe.db.sql("""
        SELECT name, partner_names FROM `tabCompany`
        WHERE partner_names IS NOT NULL AND partner_names != ''
        ORDER BY name LIMIT 5
    """, as_dict=True)
    r["sample"] = sample

    # Unique partner names (for future RBAC)
    all_text = frappe.db.sql(
        "SELECT GROUP_CONCAT(partner_names SEPARATOR ', ') FROM `tabCompany` WHERE partner_names IS NOT NULL AND partner_names != ''"
    )[0][0] or ""
    # Split and deduplicate
    names = set()
    for chunk in all_text.split(","):
        name = chunk.strip()
        if name and not name.startswith("("):
            names.add(name)
    r["unique_partner_count"] = len(names)
    r["unique_partners_sample"] = sorted(list(names))[:15]

    r["all_pass"] = with_partners >= 30
except Exception as e:
    r["errors"].append(f"Verify: {e}")

print("R_BEGIN")
print(json.dumps(r, default=str, indent=2))
print("R_END")
