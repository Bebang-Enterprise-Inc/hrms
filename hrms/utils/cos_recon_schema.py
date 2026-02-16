# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
COS RECON Excel Export Schema (Versioned)
Defines column layouts for Cost of Sales Reconciliation exports.
"""

COS_RECON_V1 = {
    "version": "v1.0",
    "description": "Standard COS RECON format matching Google Sheets template (Oct-Dec 2025)",
    "columns": [
        {"col": "C", "field": "item_code", "header": "Item Code"},
        {"col": "D", "field": "item_name", "header": "Item Name"},
        {"col": "E", "field": "description", "header": "Description"},
        {"col": "F", "field": "grams", "header": "Grams"},
        {"col": "G", "field": "uom", "header": "UOM"},
        {"col": "H", "field": "counted_qty_whole", "header": "QTY Whole"},
        {"col": "I", "field": "counted_qty_loose", "header": "QTY Loose"},
        {"col": "J", "field": "unit_cost", "header": "Unit Cost"},
        {"col": "K", "field": "total_cost", "header": "Total Cost"},
    ]
}

# Future versions can be added here (e.g., COS_RECON_V2 with additional columns)
# Active version used by export_count_to_cos_recon() in hrms/api/inventory.py
ACTIVE_VERSION = COS_RECON_V1
