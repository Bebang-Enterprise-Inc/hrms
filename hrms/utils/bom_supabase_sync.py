"""Sync BOM changes to Supabase product_bom table (S189).

Fires on BOM on_update and after_insert via hooks.py doc_events.
Uses raw HTTP via hrms.utils.supabase (canonical BEI pattern).
No supabase-py SDK.
"""
import json

import frappe
import requests

from hrms.utils.supabase import get_service_key, SUPABASE_URL

# BOM FG Name -> POS product_name mapping (must match s189_seed_product_bom.py)
_VERIFIED_MAPPINGS = {
    "PRESIDENTIAL": "Presidential",
    "SPECIAL": "Special",
    "MELON": "Melon-ial",
    "MATCHARAP": "Matcharap",
    "HALOKAY UBE": "Halokay Ube",
    "BUKO PANDAN": "Buko Pandan",
    "MANGO GRAHAM CARAMEL": "Mango Graham",
    "BANANA CINNAMON": "Banana Cinnamon",
    "BUKO FRUIT SALAD": "Buko Fruit Salad",
    "STRAWBERRY PISTACHIO": "Berry Good (Strawberry)",
    "BLUEBERRY PISTACHIO": "Berry Good (Blueberry)",
    "COOKIE CRUMBLE": "Cookie Crumble",
    "SO CORNY": "So Corny",
    "MANGO CLASSIC": "Mango Classic",
    "CHOCO BROWNIE": "Brownie Overload",
    "POP LAMIG": "Pop Lamig",
    "ISKRAMBOL": "Iskrambol",
    "GINATAANG HALO-HALO": "Ginataang Halo Halo",
    "TIKIM PRESIDENTIAL": "Presidential (Tikim)",
    "TIKIM MANGO GRAHAM": "Mango Graham (Tikim)",
    "TIKIM CHOCO BROWNIE": "Choco Brownie (Tikim)",
}


def _map_frappe_to_pos_name(item_name):
    """Map Frappe BOM item_name to POS product_name."""
    return _VERIFIED_MAPPINGS.get((item_name or "").upper().strip())


def sync_bom_to_supabase(doc, method):
    """Push BOM changes to Supabase product_bom table.

    Called from hooks.py doc_events for BOM on_update and after_insert.
    Only syncs active default BOMs from BEI (not BKI manufacturing BOMs).
    """
    if not doc.is_active or not doc.is_default:
        return

    # Only sync BEI menu BOMs, not BKI manufacturing BOMs
    if doc.company == "Bebang Kitchen Inc.":
        return

    product_name = _map_frappe_to_pos_name(doc.item_name)
    if not product_name:
        frappe.log_error(
            f"BOM {doc.name}: cannot map '{doc.item_name}' to POS product_name",
            "S189 BOM Sync",
        )
        return

    sb_key = get_service_key()
    headers = {
        "apikey": sb_key,
        "Authorization": f"Bearer {sb_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    # Delete existing entries for this BOM source
    requests.delete(
        f"{SUPABASE_URL}/rest/v1/product_bom",
        params={"bom_source_name": f"eq.{doc.name}"},
        headers=headers,
        timeout=15,
    )

    bom_qty = float(doc.quantity or 1)
    rows = []
    for item in doc.items:
        rows.append({
            "product_name": product_name,
            "material_code": item.item_code,
            "material_name": item.item_name,
            "grams_per_serving": float(item.qty) / bom_qty,
            "bom_source": "frappe_bom",
            "bom_source_name": doc.name,
            "is_active": True,
        })

    if rows:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/product_bom",
            headers={**headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=rows,
            timeout=15,
        )
        if resp.ok:
            frappe.msgprint(
                f"Synced {len(rows)} ingredients to Supabase",
                indicator="green",
                alert=True,
            )
        else:
            frappe.log_error(
                f"Supabase sync failed for {doc.name}: {resp.status_code} {resp.text}",
                "S189 BOM Sync",
            )
