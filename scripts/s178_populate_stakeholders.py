#!/usr/bin/env python3
"""S178: Populate the BEI Company Stakeholder child table from the team's register data.

Run AFTER bench migrate (which creates the tabBEI Company Stakeholder table).
Executes inside frappe_backend container via SSM.
"""
import json, os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

r = {"populated": 0, "companies": [], "errors": []}

# Partner data from the team's completed Company Register XLSX
# Each entry: Frappe company name -> list of (name, role)
# Role inferred from company type: BEI-owned JV corps = "JV Partner",
# external franchise corps = "Franchisee", holding = "Shareholder/Director"
stakeholder_data = {
    "Irresistible Infusions Inc.": [
        ("Samer Karazi", "Director", 20.0),
        ("Daymae Salumbides Karazi", "Director", 0),
        ("Hernando Diokno Hernandez", "Director", 0),
        ("Paolo Miguel Gatan Sunga", "Director", 0),
        ("Michaelvin Gabrielle Rosales Chiong", "Director", 0),
        ("Bebang Enterprise Inc.", "Shareholder", 79.97),
    ],
    "BEBANG FRANCHISE CORP.": [
        ("Bebang Enterprise Inc.", "Shareholder", 79.97),
        ("Samer Karazi", "Shareholder", 20.0),
        ("Daymae Salumbides Karazi", "Director", 0),
        ("Hernando Diokno Hernandez", "Director", 0),
        ("Paolo Miguel Gatan Sunga", "Director", 0),
        ("Michaelvin Gabrielle Rosales Chiong", "Director", 0),
    ],
    "DMD HOLDINGS INC.": [
        ("Andrew Rodel Manansala", "JV Partner", 0),
    ],
    "BEBANG ARANETA GATEWAY": [
        ("Wilford Wong", "Franchisee", 0),
        ("Winchell Wong", "Franchisee", 0),
        ("Wei Min Choy", "Franchisee", 0),
    ],
    "BEBANG AYALA SOLENAD": [
        ("Francis Patrick Jose Fontanilla Tanjangco", "Franchisee", 0),
        ("Francisco Suntay Tanjangco", "Franchisee", 0),
        ("Hernando Diokno Hernandez", "Franchisee", 0),
    ],
    "BEBANG BF HOMES INC.": [
        ("Edward Cheson Sy", "JV Partner", 0),
        ("Ralph Kenneth Ty", "JV Partner", 0),
    ],
    "BEBANG D'VERDE": [
        ("Alyssa Young", "Franchisee", 0),
        ("Timothy Patrick Uy", "Franchisee", 0),
        ("Pablo Hicban", "Franchisee", 0),
    ],
    "BEBANG EVER GOTESCO COMMONWEALTH": [
        ("Francis Lopez", "Franchisee", 0),
        ("Angela Mylene C. Sediaren", "Franchisee", 0),
        ("Michelle Defensor", "Franchisee", 0),
    ],
    "BEBANG FESTIVAL INC.": [
        ("Jose Paulo Legaspi", "JV Partner", 0),
    ],
    "BEBANG FT INC.": [
        ("Andrew Rodel Manansala", "JV Partner", 0),
    ],
    "BEBANG GRAND CENTRAL INC.": [
        ("Rommel Gabaldon", "JV Partner", 0),
        ("Veronica Gabaldon", "JV Partner", 0),
    ],
    "BEBANG LCT INC.": [
        ("Ian Umali", "JV Partner", 0),
    ],
    "BEBANG MARILAO INC.": [
        ("Hernando Diokno Hernandez", "JV Partner", 0),
    ],
    "BEBANG MARKET MARKET INC.": [
        ("Andrew Rodel Manansala", "JV Partner", 0),
    ],
    "BEBANG MEGA INC.": [
        ("Ian Umali", "Franchisee", 0),
    ],
    "BEBANG NORTH EDSA INC.": [
        ("Andrew Rodel Manansala", "JV Partner", 0),
    ],
    "BEBANG PASEO INC.": [
        ("Julian Anthony De Guzman", "JV Partner", 0),
        ("Lorenzo Santos Castillo", "JV Partner", 0),
    ],
    "BEBANG PITX INC.": [
        ("Jose Paulo Legaspi", "JV Partner", 0),
    ],
    "BEBANG ROBINSONS GALLERIA SOUTH": [
        ("Wilford Wong", "Franchisee", 0),
        ("Winchell Wong", "Franchisee", 0),
        ("Wei Min Choy", "Franchisee", 0),
    ],
    "BEBANG SM BICUTAN INC.": [
        ("Vishal Shaq Daswani", "JV Partner", 0),
    ],
    "BEBANG SM CALOOCAN": [
        ("Alyssa Young", "Franchisee", 0),
        ("Timothy Patrick Uy", "Franchisee", 0),
        ("Pablo Hicban", "Franchisee", 0),
    ],
    "BEBANG SM CLARK": [
        ("Maria Luisa Gonzales Manliclic", "Franchisee", 0),
        ("Abel Clarin Manliclic", "Franchisee", 0),
    ],
    "BEBANG SM MARIKINA INC.": [
        ("Imelda Soriano", "JV Partner", 0),
        ("Ana Soriano", "JV Partner", 0),
    ],
    "BEBANG SM SANGANDAAN": [
        ("Wilford Wong", "Franchisee", 0),
        ("Winchell Wong", "Franchisee", 0),
        ("Wei Min Choy", "Franchisee", 0),
    ],
    "BEBANG SM SJDM": [
        ("Jose Paulo Legaspi", "Franchisee", 0),
        ("Carla Joyce Garcia", "Franchisee", 0),
    ],
    "BEBANG SM TAYTAY": [
        ("Kiefer Isaac Crisologo Ravena", "Franchisee", 0),
        ("Jose Paolo Gabriel Darroca", "Franchisee", 0),
        ("Mickey Ingles", "Franchisee", 0),
    ],
    "BEBANG SMEO INC.": [
        ("Lorenzo Castillo", "JV Partner", 0),
        ("Julian Anthony De Guzman", "JV Partner", 0),
    ],
    "BEBANG SMM INC.": [
        ("Lewis Alfred V Tenorio", "Franchisee", 0),
        ("Kiefer Isaac Crisologo Ravena", "Franchisee", 0),
    ],
    "BEBANG SMOA INC.": [
        ("Ian Umali", "JV Partner", 0),
    ],
    "BEBANG SMV INC.": [
        ("Benjamin Christopher Sunga", "JV Partner", 0),
    ],
    "BEBANG STARMALL ALABANG INC.": [
        ("Jose Paulo Legaspi", "JV Partner", 0),
    ],
    "BEBANG THE GRID FOOD MARKET": [
        ("Howard Paw", "Franchisee", 0),
    ],
    "BEBANG TOMAS MORATO": [
        ("Cherry Go", "Franchisee", 0),
        ("Jason Go", "Franchisee", 0),
    ],
    "BEBANG UP TOWN CENTER INC.": [
        ("Imelda Soriano", "JV Partner", 0),
        ("Ana Soriano", "JV Partner", 0),
        ("Dennis Soriano", "JV Partner", 0),
    ],
    "BEBANG VENICE GRAND CANAL INC.": [
        ("Rommel Gabaldon", "JV Partner", 0),
        ("Veronica Gabaldon", "JV Partner", 0),
    ],
    "BEBANG VISTAMALL": [
        ("Martin Lim", "Franchisee", 0),
    ],
}

for company_name, stakeholders in stakeholder_data.items():
    if not frappe.db.exists("Company", company_name):
        r["errors"].append(f"Company not found: {company_name}")
        continue

    try:
        doc = frappe.get_doc("Company", company_name)

        # Clear existing stakeholders to avoid duplicates on re-run
        if hasattr(doc, "stakeholders"):
            doc.stakeholders = []

        for name, role, pct in stakeholders:
            doc.append("stakeholders", {
                "stakeholder_name": name,
                "role": role,
                "ownership_pct": pct if pct > 0 else 0,
                "portal_access": 0,
            })

        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory = True
        doc.save()
        r["companies"].append({"company": company_name, "stakeholders": len(stakeholders)})
        r["populated"] += len(stakeholders)

    except Exception as e:
        r["errors"].append(f"{company_name}: {e}")

frappe.db.commit()

# Summary
r["total_companies"] = len(r["companies"])
r["total_stakeholders"] = r["populated"]

# Unique partners across all companies
unique = set()
for company_name, stakeholders in stakeholder_data.items():
    for name, role, pct in stakeholders:
        if role in ("JV Partner", "Franchisee", "Managing Partner"):
            unique.add(name)
r["unique_partners"] = len(unique)

print("R_BEGIN")
print(json.dumps(r, default=str, indent=2))
print("R_END")
