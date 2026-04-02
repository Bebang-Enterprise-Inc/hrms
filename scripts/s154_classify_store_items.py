#!/usr/bin/env python3
"""
S154/D1: Classify ~106 orderable items into 6 store_category values.

Sets custom_store_category on each Item in Frappe via REST API.
Categories: Toppings, Frozen, Sauces, Packaging, Supplies, Other

Classification logic:
1. BOM ingredient mapping (item_code prefix → known category)
2. Item group mapping (Packaging Materials → Packaging)
3. Keyword matching on item_name
4. Manual overrides for known items

Usage:
  python scripts/s154_classify_store_items.py --dry-run
  python scripts/s154_classify_store_items.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import requests

FRAPPE_URL = os.environ.get("FRAPPE_URL", "https://hq.bebang.ph")
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


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


# ---------------------------------------------------------------------------
# Classification rules
# ---------------------------------------------------------------------------

# Item code prefix → category
PREFIX_MAP = {
    "FG001": "Toppings",     # Leche Flan
    "FG002": "Toppings",     # Banana Cinnamon
    "FG003": "Toppings",     # Rice Crispies
    "FG004": "Toppings",     # Buko Pandan Jelly
    "FG005": "Toppings",     # Vanilla White Jelly
    "FG006": "Toppings",     # Coconut Jelly
    "FG007": "Sauces",       # Coconut Syrup
    "FG008": "Toppings",     # Ube Syrup
    "FG009": "Toppings",     # Sago
    "FG010": "Toppings",     # Strawberry Jelly
    "FG011": "Toppings",     # Matcha Jelly
    "FG012": "Toppings",     # Cookie Crumble
    "FG013": "Toppings",     # Langka
    "FG014": "Toppings",     # Pistachio/Cashew Mix
    "FG015": "Sauces",       # Buko Pandan Flavored Sauce
    "FG016": "Sauces",       # Mango Sauce
    "FG017": "Sauces",       # Melon Sauce
    "FG018": "Sauces",       # Strawberry Sauce
    "FG019": "Sauces",       # Blueberry Sauce
    "FG020": "Frozen",       # Frozen Ice Milk (all variants)
    "PM": "Packaging",       # All packaging items
    "OS": "Supplies",        # Office/cleaning supplies
    "CL": "Supplies",        # Cleaning items
}

# Keyword → category (checked against item_name, case-insensitive)
KEYWORD_MAP = {
    "jelly": "Toppings",
    "flan": "Toppings",
    "sago": "Toppings",
    "crispies": "Toppings",
    "langka": "Toppings",
    "pistachio": "Toppings",
    "cashew": "Toppings",
    "marshmallow": "Toppings",
    "nata": "Toppings",
    "macapuno": "Toppings",
    "ube halaya": "Toppings",
    "corn": "Toppings",
    "mais": "Toppings",
    "mango slice": "Toppings",
    "blueberry comstock": "Toppings",
    "strawberry fruit": "Toppings",
    "tapioca": "Toppings",
    "crushed oreo": "Toppings",
    "cheese": "Toppings",
    "fruit cocktail": "Toppings",

    "syrup": "Sauces",
    "sauce": "Sauces",
    "caramel": "Sauces",

    "frozen": "Frozen",
    "ice milk": "Frozen",

    "cup": "Packaging",
    "lid": "Packaging",
    "spoon": "Packaging",
    "plastic": "Packaging",
    "straw": "Packaging",
    "bag": "Packaging",
    "tissue": "Packaging",
    "napkin": "Packaging",

    "detergent": "Supplies",
    "bleach": "Supplies",
    "trash": "Supplies",
    "glove": "Supplies",
    "sanitizer": "Supplies",
    "soap": "Supplies",
    "mop": "Supplies",
    "broom": "Supplies",
    "sponge": "Supplies",
    "brush": "Supplies",
    "rag": "Supplies",
    "ballpen": "Supplies",
    "paper": "Supplies",
    "log book": "Supplies",
    "receipt": "Supplies",
}


def classify_item(item_code: str, item_name: str, item_group: str) -> str:
    """Classify an item into one of 6 store categories."""
    name_lower = (item_name or "").lower()
    code_upper = (item_code or "").upper()

    # 1. Exact prefix match
    for prefix, cat in PREFIX_MAP.items():
        if code_upper.startswith(prefix):
            return cat

    # 2. Item group mapping
    group_lower = (item_group or "").lower()
    if "packaging" in group_lower:
        return "Packaging"

    # 3. Keyword matching
    for kw, cat in KEYWORD_MAP.items():
        if kw in name_lower:
            return cat

    # 4. Item group fallbacks
    if "finished goods" in group_lower:
        return "Frozen"  # Most FG items are frozen products
    if "consumable" in group_lower:
        return "Supplies"

    return "Other"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="S154/D1: Classify store items")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = _get_secret("FRAPPE_API_KEY")
    api_secret = _get_secret("FRAPPE_API_SECRET")
    headers = {
        "Authorization": f"token {api_key}:{api_secret}",
        "Content-Type": "application/json",
    }

    # Fetch orderable items (same filter as get_orderable_items)
    print("Fetching orderable items from Frappe...")
    resp = requests.get(
        f"{FRAPPE_URL}/api/resource/Item",
        headers=headers,
        params={
            "filters": json.dumps([
                ["is_stock_item", "=", 1],
                ["disabled", "=", 0],
                ["item_group", "in", ["Finished Goods", "Consumables", "Packaging Materials", "Packaging", "Products"]],
                ["item_name", "not like", "%SAMPLE%"],
                ["item_name", "not like", "%R&D%"],
                ["item_name", "not like", "%TEST%"],
            ]),
            "fields": json.dumps(["name", "item_name", "item_group", "custom_store_category"]),
            "limit_page_length": 500,
        },
        timeout=30,
    )
    resp.raise_for_status()
    items = resp.json().get("data", [])
    print(f"  Found {len(items)} orderable items")

    # Classify each item
    categories: dict[str, int] = {}
    updates = []
    for item in items:
        code = item["name"]
        name = item.get("item_name", "")
        group = item.get("item_group", "")
        current = item.get("custom_store_category", "")

        new_cat = classify_item(code, name, group)
        categories[new_cat] = categories.get(new_cat, 0) + 1

        if current != new_cat:
            updates.append((code, name, current, new_cat))

    print(f"\n  Category distribution:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count}")
    print(f"\n  Items needing update: {len(updates)}")

    if args.dry_run:
        for code, name, old, new in updates[:20]:
            print(f"    {code} ({name}): {old or '(none)'} -> {new}")
        if len(updates) > 20:
            print(f"    ... and {len(updates) - 20} more")
        return

    # Apply updates
    updated = 0
    for code, name, old, new in updates:
        try:
            resp = requests.put(
                f"{FRAPPE_URL}/api/resource/Item/{code}",
                headers=headers,
                json={"custom_store_category": new},
                timeout=15,
            )
            if resp.status_code == 200:
                updated += 1
            else:
                print(f"    Warning: {code}: {resp.status_code}")
        except Exception as e:
            print(f"    Error: {code}: {e}")

    print(f"\n  Updated {updated}/{len(updates)} items")


if __name__ == "__main__":
    main()
