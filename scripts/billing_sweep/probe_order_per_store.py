#!/usr/bin/env python3
"""Probe — for each store, find a real existing BEI Store Order # we can link to.

Read-only. Looks up the latest existing BEI Store Order per store. Falls back
to the doctype's natural-keyed list if necessary.
"""
from __future__ import annotations

import os
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)

import json
import sys
from datetime import datetime

import frappe  # type: ignore

ALL_STORES = [
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


def main() -> None:
    payload = {
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "doctype_meta": {},
        "per_store_orders": {},
    }
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        # First: discover the BEI Store Order doctype shape (what's the company link field?)
        if frappe.db.exists("DocType", "BEI Store Order"):
            meta = frappe.get_meta("BEI Store Order")
            payload["doctype_meta"]["fields"] = [
                {"fieldname": f.fieldname, "fieldtype": f.fieldtype, "options": f.options}
                for f in meta.fields
                if f.fieldtype in ("Link", "Data", "Select") and f.fieldname in
                ("company", "buyer_company", "store_company", "store", "buyer", "store_warehouse",
                 "buyer_warehouse", "customer", "to_company", "source_warehouse")
            ]
            payload["doctype_meta"]["total_rows"] = frappe.db.count("BEI Store Order")

            # Get a sample row to see what fields are populated
            sample = frappe.db.sql(
                """SELECT * FROM `tabBEI Store Order` ORDER BY creation DESC LIMIT 1""",
                as_dict=True,
            )
            if sample:
                # Reduce to only fields that contain a store-like name
                row = sample[0]
                payload["doctype_meta"]["sample_keys"] = list(row.keys())[:50]
                payload["doctype_meta"]["sample_subset"] = {
                    k: row[k] for k in row.keys()
                    if k in ("name", "company", "buyer_company", "store", "store_company",
                             "warehouse", "source_warehouse", "buyer_warehouse",
                             "to_company", "from_company")
                }

        # For each store, try several candidate field names to find an order
        for store in ALL_STORES:
            found = None
            # Try multiple candidate fields
            for field_name in ("buyer_company", "store_company", "company", "buyer", "to_company"):
                try:
                    n = frappe.db.get_value(
                        "BEI Store Order",
                        {field_name: store},
                        "name",
                        order_by="creation desc",
                    )
                    if n:
                        found = {"order_no": n, "matched_field": field_name}
                        break
                except Exception:
                    continue
            # Last resort: search by store name in any text-like field
            if not found:
                try:
                    rows = frappe.db.sql(
                        """SELECT name FROM `tabBEI Store Order`
                           WHERE store_warehouse LIKE %s OR buyer_warehouse LIKE %s
                           ORDER BY creation DESC LIMIT 1""",
                        (f"%{store}%", f"%{store}%"),
                        as_dict=True,
                    )
                    if rows:
                        found = {"order_no": rows[0]["name"], "matched_field": "warehouse_like"}
                except Exception as e:
                    payload.setdefault("query_errors", []).append(
                        f"{store}: {str(e)[:200]}"
                    )
            payload["per_store_orders"][store] = found

        payload["status"] = "OK"

    except Exception as e:
        import traceback
        payload["status"] = "ERROR"
        payload["fatal_error"] = str(e)
        payload["traceback"] = traceback.format_exc()

    out_path = "/tmp/s244_order_probe.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    sys.stdout.write(f"S244_ORDER_PROBE_OK status={payload.get('status')}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
