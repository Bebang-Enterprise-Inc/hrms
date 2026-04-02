#!/usr/bin/env python3
"""
S154/D2: Load store-consumption BOMs into Frappe.

Creates BOM records for the 15 POS products with their ingredient components.
These are STORE CONSUMPTION BOMs (cups → ingredients), separate from
the 17 existing commissary production BOMs.

Usage:
  python scripts/s154_load_store_boms.py --dry-run
  python scripts/s154_load_store_boms.py
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
FRAPPE_URL = os.environ.get("FRAPPE_URL", "https://hq.bebang.ph")
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

BOM_CSV = ROOT / "data" / "_CLEANROOM" / "bom" / "store_consumption_bom.csv"

# The 15 primary POS products (from BD-2)
PRIMARY_PRODUCTS = {
    "PRESIDENTIAL", "HALUKAY UBE", "MANGO GRAHAM CARAMEL", "BANANA CINNAMON",
    "BUKO FRUIT", "MELON", "BUKO PANDAN", "STRAWBERRY PISTACHIO",
    "BLUEBERRY PISTACHIO", "MATCHARAP", "COOKIE CRUMBLE", "SO CORNY",
    "MANGO CLASSIC", "SPECIAL", "CHOCO BROWNIE",
}


def _get_secret(env_name: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    result = subprocess.run(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", env_name,
         "--plain", "--project", "bei-erp", "--config", "dev"],
        capture_output=True, text=True, timeout=15,
        creationflags=CREATE_NO_WINDOW,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    raise RuntimeError(f"{env_name} not found")


def load_bom_data() -> dict[str, list[dict]]:
    """Load BOM CSV grouped by product."""
    bom: dict[str, list[dict]] = defaultdict(list)
    with open(BOM_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            product = (row.get("pos_product") or "").strip().upper()
            if product not in PRIMARY_PRODUCTS:
                continue
            bom[product].append({
                "item_code": row.get("ingredient_item_code", "").strip(),
                "ingredient": row.get("ingredient_name", "").strip(),
                "grams_per_cup": float(row.get("grams_per_cup") or 0),
                "sku_conversion": float(row.get("sku_conversion") or 0),
            })
    return dict(bom)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="S154/D2: Load store consumption BOMs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    bom_data = load_bom_data()
    print(f"Loaded {len(bom_data)} primary products from BOM CSV")

    for product, components in sorted(bom_data.items()):
        print(f"  {product}: {len(components)} ingredients")
        if args.dry_run:
            for c in components[:5]:
                print(f"    {c['item_code']}: {c['ingredient']} ({c['grams_per_cup']}g/cup)")
            if len(components) > 5:
                print(f"    ... and {len(components) - 5} more")

    if args.dry_run:
        print(f"\n[DRY RUN] Would create {len(bom_data)} BOM records in Frappe")
        return

    api_key = _get_secret("FRAPPE_API_KEY")
    api_secret = _get_secret("FRAPPE_API_SECRET")
    headers = {
        "Authorization": f"token {api_key}:{api_secret}",
        "Content-Type": "application/json",
    }

    created = 0
    for product, components in bom_data.items():
        # Check if BOM already exists for this product
        # BOM naming: BOM-{item}-{version}
        # We need the Item record for the product
        # Store consumption BOMs use a naming convention: "STORE-{product}"
        bom_doc = {
            "doctype": "BOM",
            "item": product,  # This needs to be a valid Item code
            "is_active": 1,
            "is_default": 0,  # Don't override commissary BOMs
            "quantity": 1,
            "uom": "Cup",
            "custom_bom_type": "Store Consumption",
            "items": [],
        }

        for comp in components:
            bom_doc["items"].append({
                "item_code": comp["item_code"],
                "qty": comp["sku_conversion"] if comp["sku_conversion"] > 0 else comp["grams_per_cup"] / 1000,
                "uom": "Kg" if comp["sku_conversion"] > 0 and comp["sku_conversion"] < 1 else "Nos",
            })

        try:
            resp = requests.post(
                f"{FRAPPE_URL}/api/resource/BOM",
                headers=headers,
                json={"data": json.dumps(bom_doc)},
                timeout=30,
            )
            if resp.status_code in (200, 201):
                created += 1
                print(f"  Created BOM for {product}")
            else:
                print(f"  Warning: {product}: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            print(f"  Error: {product}: {e}")

    print(f"\nCreated {created}/{len(bom_data)} BOMs")


if __name__ == "__main__":
    main()
