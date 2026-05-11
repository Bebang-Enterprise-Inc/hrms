#!/usr/bin/env python3
"""Probe Company + Warehouse stock-related defaults to explain the sweep failures."""
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

# Buyer Companies from the sweep — 45 ready + 4 broken
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


def main() -> None:
    payload = {"timestamp_utc": datetime.utcnow().isoformat() + "Z", "stores": []}
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        for company in STORES_ALL:
            row = {"company": company}
            # Company-level stock defaults
            c = frappe.db.get_value(
                "Company",
                company,
                [
                    "abbr",
                    "cost_center",
                    "default_currency",
                    "stock_received_but_not_billed",
                    "default_inventory_account",
                    "default_expense_account",
                    "default_cash_account",
                    "default_bank_account",
                    "default_receivable_account",
                    "default_payable_account",
                ],
                as_dict=True,
            )
            row.update(c or {})

            # Warehouse defaults
            wh = frappe.db.get_value(
                "Warehouse",
                company,
                ["account", "is_group", "disabled", "warehouse_type", "default_in_transit_warehouse"],
                as_dict=True,
            )
            row["warehouse_attrs"] = wh or {}

            # 1104210 account name on this Company
            acct_1104210 = frappe.db.get_value(
                "Account",
                {"company": company, "account_number": "1104210"},
                "name",
            )
            row["account_1104210"] = acct_1104210

            # Does Warehouse.account == 1104210 account?
            row["warehouse_account_is_1104210"] = bool(
                acct_1104210 and (wh or {}).get("account") == acct_1104210
            )

            payload["stores"].append(row)

        payload["status"] = "OK"
    except Exception as e:
        import traceback
        payload["status"] = "ERROR"
        payload["fatal_error"] = str(e)
        payload["traceback"] = traceback.format_exc()

    out_path = "/tmp/s244_stock_defaults.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    sys.stdout.write(f"S244_STOCK_DEFAULTS_OK status={payload.get('status')}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
