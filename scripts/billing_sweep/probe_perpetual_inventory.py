#!/usr/bin/env python3
"""Probe Company.enable_perpetual_inventory to confirm sweep-failure root cause."""
from __future__ import annotations

import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)

import json
import sys
from datetime import datetime

import frappe  # type: ignore


def main() -> None:
    payload = {"timestamp_utc": datetime.utcnow().isoformat() + "Z"}
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        # List the Company fields related to perpetual inventory / stock
        meta_fields = []
        for f in frappe.get_meta("Company").fields:
            if f.fieldname and any(k in (f.fieldname or "").lower() for k in
                                    ("perpetual", "stock", "inventory")):
                meta_fields.append({"fieldname": f.fieldname, "fieldtype": f.fieldtype,
                                    "label": f.label})
        payload["company_stock_fields"] = meta_fields

        # Pull a column list from tabCompany matching the pattern
        cols = frappe.db.sql(
            """SELECT COLUMN_NAME FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tabCompany'
                 AND (COLUMN_NAME LIKE '%perpetual%' OR COLUMN_NAME LIKE '%stock%')""",
            as_dict=True,
        )
        payload["company_columns"] = [c["COLUMN_NAME"] for c in cols]

        # Compare per-company values for the 49 stores
        STORES_ALL = [
            "ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC",
            "AYALA EVO CITY - BEBANG MEGA INC.",
            "AYALA FAIRVIEW TERRACES - BEBANG FT INC.",
            "AYALA MARKET MARKET - BEBANG MARKET MARKET INC.",
            "AYALA SOLENAD - HFFM SOLENAD FOOD SERVICES INC.",
            "AYALA UP TOWN CENTER - BEBANG UP TOWN CENTER INC.",
            "AYALA VERMOSA - BEBANG MEGA INC.",
            "BF HOMES - BEBANG BF HOMES INC.",
            "CTTM TOMAS MORATO - B CUBED VENTURES CORP.",
            "D'VERDE CALAMBA - TAJ FOOD CORP.",
            "EVER COMMONWEALTH - DLS DESSERT CRAFT INC.",
            "FESTIVAL MALL ALABANG - BEBANG FESTIVAL INC.",
            "LUCKY CHINATOWN - BEBANG LCT INC.",
            "MEGAWIDE PITX - BEBANG PITX INC.",
            "MEGAWORLD PASEO CENTER - BEBANG PASEO INC.",
            "MEGAWORLD VENICE GRAND CANAL - BEBANG VENICE GRAND CANAL INC.",
            "NAIA T3 - HALO-HALO TERMINAL FOOD CORP.",
            "ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP.",
            "ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC",
            "ROBINSONS GALLERIA SOUTH - TUNGSTEN CAPITAL HOLDINGS OPC",
            "ROBINSONS GENERAL TRIAS - BEBANG MEGA INC.",
            "ROBINSONS IMUS - BEBANG MEGA INC.",
            "ROBINSONS PLACE DASMARINAS - FREEZE DELIGHT INC.",
            "SM BICUTAN - BEBANG SM BICUTAN INC.",
            "SM CALOOCAN - TAJ FOOD CORP.",
            "SM CLARK - RED TALDAWA FOODS OPC",
            "SM EAST ORTIGAS - BEBANG SMEO INC.",
            "SM GRAND CENTRAL - BEBANG GRAND CENTRAL INC.",
            "SM MALL OF ASIA - BEBANG SMOA INC.",
            "SM MARIKINA - BEBANG SM MARIKINA INC.",
            "SM MARILAO - BEBANG MARILAO INC.",
            "SM NORTH EDSA - BEBANG NORTH EDSA INC.",
            "SM PULILAN - BEBANG SMM INC.",
            "SM SAN JOSE DEL MONTE - JL TRADE OPC",
            "SM SANGANDAAN - TUNGSTEN CAPITAL HOLDINGS OPC",
            "SM STA. ROSA - SWEET HARMONY FOOD CORP.",
            "SM TANZA - BEBANG MEGA INC.",
            "SM TAYTAY - DAY ONES FOOD AND DRINK ESTABLISHMENTS CORP.",
            "SM VALENZUELA - BEBANG SMV INC.",
            "STA. LUCIA EAST GRAND MALL - BEBANG SM MARIKINA INC.",
            "THE GRID ROCKWELL - TASTECARTEL CORP.",
            "THE TERMINAL - BEBANG STARMALL ALABANG INC.",
            "UP TOWN MALL BGC - DMD HOLDINGS INC.",
            "VISTA MALL TAGUIG - TRICERN FOOD CORP.",
            "XENTROMALL MONTALBAN - PERPETUAL FOOD CORP.",
            "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.",
            "SM MANILA - BEBANG ENTERPRISE INC.",
            "SM MEGAMALL - BEBANG ENTERPRISE INC.",
            "SM SOUTHMALL - BEBANG ENTERPRISE INC.",
        ]

        # Build SELECT with all stock-related cols
        all_cols = ["name"] + payload["company_columns"]
        col_clause = ", ".join(f"`{c}`" for c in all_cols)
        rows = frappe.db.sql(
            f"SELECT {col_clause} FROM `tabCompany` WHERE name IN %s",
            (tuple(STORES_ALL),),
            as_dict=True,
        )
        payload["per_company"] = [dict(r) for r in rows]

        # Also test the actual erpnext helper for one PASS and one FAIL store
        try:
            import erpnext
            payload["erpnext_perpetual_helper"] = {
                "ARANETA_PASS": bool(erpnext.is_perpetual_inventory_enabled(
                    "ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC")),
                "AFT_FAIL": bool(erpnext.is_perpetual_inventory_enabled(
                    "AYALA FAIRVIEW TERRACES - BEBANG FT INC.")),
                "GHO_FAIL": bool(erpnext.is_perpetual_inventory_enabled(
                    "ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC")),
            }
        except Exception as e:
            payload["erpnext_perpetual_helper"] = {"error": str(e)[:300]}

        payload["status"] = "OK"
    except Exception as e:
        import traceback
        payload["status"] = "ERROR"
        payload["fatal_error"] = str(e)
        payload["traceback"] = traceback.format_exc()

    out_path = "/tmp/s244_perp.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    sys.stdout.write(f"S244_PERP_OK status={payload.get('status')}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
