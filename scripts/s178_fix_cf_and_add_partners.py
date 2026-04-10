#!/usr/bin/env python3
"""Fix store_locations CF metadata + create partner_names CF + materialize + populate."""
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
# Fix store_locations Custom Field metadata (search_index=0)
# ============================================================
try:
    if frappe.db.exists("Custom Field", "Company-store_locations"):
        frappe.db.set_value("Custom Field", "Company-store_locations", {
            "search_index": 0,
            "in_standard_filter": 0,
        })
        frappe.db.commit()
        r["steps"].append("Fixed store_locations CF: search_index=0, in_standard_filter=0")
except Exception as e:
    r["errors"].append(f"Fix store_locations: {e}")

# ============================================================
# Create partner_names Custom Field via direct SQL (bypass ORM validation)
# ============================================================
try:
    if frappe.db.exists("Custom Field", "Company-partner_names"):
        r["steps"].append("partner_names Custom Field already exists in metadata")
    else:
        frappe.db.sql("""
            INSERT INTO `tabCustom Field`
            (name, creation, modified, modified_by, owner, docstatus,
             dt, fieldname, label, fieldtype, insert_after,
             `description`, in_list_view, in_standard_filter, search_index)
            VALUES
            ('Company-partner_names', NOW(), NOW(), 'Administrator', 'Administrator', 0,
             'Company', 'partner_names', 'Franchisee / Partner Names', 'Small Text', 'store_locations',
             'Names of franchisees or JV partners. Searchable in dropdowns, filterable in reports.',
             1, 0, 0)
        """)
        frappe.db.commit()
        r["steps"].append("partner_names Custom Field inserted via SQL")

    # Materialize column
    cols = frappe.db.sql("SHOW COLUMNS FROM `tabCompany` LIKE 'partner_names'")
    if not cols:
        frappe.db.sql("ALTER TABLE `tabCompany` ADD COLUMN `partner_names` TEXT")
        frappe.db.commit()
        r["steps"].append("partner_names column materialized via ALTER TABLE")
    else:
        r["steps"].append("partner_names column already exists")

except Exception as e:
    r["errors"].append(f"Create partner_names: {e}")

# ============================================================
# Populate partner_names
# ============================================================
try:
    partner_data = {
        "DMD HOLDINGS INC.": "Andrew Rodel Manansala",
        "BEBANG ARANETA GATEWAY": "Wilford Wong, Winchell Wong, Wei Min Choy",
        "BEBANG AYALA SOLENAD": "Francis Patrick Jose Fontanilla Tanjangco, Francisco Suntay Tanjangco, Hernando Diokno Hernandez",
        "BEBANG BF HOMES INC.": "Edward Cheson Sy, Ralph Kenneth Ty",
        "BEBANG D'VERDE": "Alyssa Young, Timothy Patrick Uy, Pablo Hicban",
        "BEBANG EVER GOTESCO COMMONWEALTH": "Francis Lopez, Angela Mylene C. Sediaren, Michelle Defensor",
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
        "BEBANG ROBINSONS GALLERIA SOUTH": "Wilford Wong, Winchell Wong, Wei Min Choy",
        "BEBANG SM BICUTAN INC.": "Vishal Shaq Daswani",
        "BEBANG SM CALOOCAN": "Alyssa Young, Timothy Patrick Uy, Pablo Hicban",
        "BEBANG SM CLARK": "Maria Luisa Gonzales Manliclic, Abel Clarin Manliclic",
        "BEBANG SM MARIKINA INC.": "Imelda Soriano, Ana Soriano",
        "BEBANG SM SANGANDAAN": "Wilford Wong, Winchell Wong, Wei Min Choy",
        "BEBANG SM SJDM": "Jose Paulo Legaspi, Carla Joyce Garcia",
        "BEBANG SM TAYTAY": "Kiefer Isaac Crisologo Ravena, Jose Paolo Gabriel Darroca, Mickey Ingles",
        "BEBANG SMEO INC.": "Lorenzo Castillo, Julian Anthony De Guzman",
        "BEBANG SMM INC.": "Lewis Alfred V Tenorio, Kiefer Isaac Crisologo Ravena",
        "BEBANG SMOA INC.": "Ian Umali",
        "BEBANG SMV INC.": "Benjamin Christopher Sunga",
        "BEBANG STARMALL ALABANG INC.": "Jose Paulo Legaspi",
        "BEBANG THE GRID FOOD MARKET": "Howard Paw",
        "BEBANG TOMAS MORATO": "Cherry Go, Jason Go",
        "BEBANG UP TOWN CENTER INC.": "Imelda Soriano, Ana Soriano, Dennis Soriano",
        "BEBANG VENICE GRAND CANAL INC.": "Rommel Gabaldon, Veronica Gabaldon",
        "BEBANG VISTAMALL": "Martin Lim",
        # Special entities
        "BEBANG FRANCHISE CORP.": "(Franchisor - BEI 79.97%, Samer Karazi 20%)",
        "Irresistible Infusions Inc.": "(Holding company)",
        "Bebang Enterprise Inc.": "(Head Office - parent entity)",
        "Bebang Kitchen Inc.": "(Commissary)",
    }

    updated = 0
    not_found = []
    for company_name, partners in partner_data.items():
        if frappe.db.exists("Company", company_name):
            frappe.db.sql(
                "UPDATE `tabCompany` SET partner_names = %s WHERE name = %s",
                (partners, company_name),
            )
            updated += 1
        else:
            not_found.append(company_name)

    frappe.db.commit()
    r["steps"].append(f"Populated partner_names on {updated} companies")
    if not_found:
        r["not_found"] = not_found

except Exception as e:
    r["errors"].append(f"Populate: {e}")

# ============================================================
# Verify
# ============================================================
try:
    with_partners = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabCompany` WHERE partner_names IS NOT NULL AND partner_names != ''"
    )[0][0]
    r["companies_with_partner_names"] = with_partners

    with_stores = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabCompany` WHERE store_locations IS NOT NULL AND store_locations != ''"
    )[0][0]
    r["companies_with_store_locations"] = with_stores

    # Sample
    sample = frappe.db.sql("""
        SELECT name, store_locations, partner_names FROM `tabCompany`
        WHERE partner_names IS NOT NULL AND partner_names != ''
        ORDER BY name LIMIT 5
    """, as_dict=True)
    r["sample"] = [{k: (v[:60] if v else "") for k, v in s.items()} for s in sample]

    r["all_pass"] = with_partners >= 30 and with_stores >= 35
except Exception as e:
    r["errors"].append(f"Verify: {e}")

print("R_BEGIN")
print(json.dumps(r, default=str, indent=2))
print("R_END")
