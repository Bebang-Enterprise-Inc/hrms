#!/usr/bin/env python3
"""S246 Phase 1B — 7 unanswered audit items in one SSM pass.

Audits items P1B.1 through P1B.7 + 30-day Error Log sweep.
Output: /tmp/s246_p1b_audit.json (single payload with all 7 sub-audits).
Read-only.
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
from collections import Counter

import frappe  # type: ignore

BKI_COMPANY = "BEBANG KITCHEN INC."

# 13 PASS stores from billing sweep 2026-05-11
PASS_STORES = [
    "ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC",
    "AYALA EVO CITY - BEBANG MEGA INC.",
    "AYALA VERMOSA - BEBANG MEGA INC.",
    "D'VERDE CALAMBA - TAJ FOOD CORP.",
    "NAIA T3 - HALO-HALO TERMINAL FOOD CORP.",
    "ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP.",
    "ROBINSONS GENERAL TRIAS - BEBANG MEGA INC.",
    "ROBINSONS IMUS - BEBANG MEGA INC.",
    "ROBINSONS PLACE DASMARINAS - FREEZE DELIGHT INC.",
    "SM STA. ROSA - SWEET HARMONY FOOD CORP.",
    "SM TANZA - BEBANG MEGA INC.",
    "STA. LUCIA EAST GRAND MALL - BEBANG SM MARIKINA INC.",
    "XENTROMALL MONTALBAN - PERPETUAL FOOD CORP.",
]


# --- P1B.1: BKI SI GL posting audit ---
def p1b_1_bki_si_gl_audit():
    """Sample 5 Submitted BKI SIs, trace GL Entries on BKI's books."""
    out = {"audit": "P1B.1 — BKI SI GL Posting"}
    samples = frappe.db.sql(
        """SELECT name, customer, custom_bei_store_order, grand_total, posting_date, modified
           FROM `tabSales Invoice`
           WHERE company = %s AND docstatus = 1
           ORDER BY RAND() LIMIT 5""",
        BKI_COMPANY, as_dict=True,
    )
    out["sample_count"] = len(samples)
    out["samples"] = []
    for s in samples:
        gl = frappe.db.sql(
            """SELECT account, debit, credit, against, voucher_type, voucher_no
               FROM `tabGL Entry`
               WHERE voucher_no = %s AND voucher_type = 'Sales Invoice'
                 AND is_cancelled = 0
               ORDER BY creation""",
            s["name"], as_dict=True,
        )
        out["samples"].append({
            "si_name": s["name"],
            "customer": s["customer"],
            "order": s["custom_bei_store_order"],
            "grand_total": float(s["grand_total"] or 0),
            "posting_date": str(s["posting_date"]),
            "gl_lines": [
                {"account": g["account"], "debit": float(g["debit"]), "credit": float(g["credit"])}
                for g in gl
            ],
            "gl_balanced": abs(sum(float(g["debit"]) - float(g["credit"]) for g in gl)) < 0.01,
        })
    out["all_balanced"] = all(s["gl_balanced"] for s in out["samples"])
    return out


# --- P1B.2: Tax flow Output VAT (BKI) → Input VAT (Store) ---
def p1b_2_tax_flow_audit():
    """For 5 SI-PI pairs, trace VAT entries on both sides."""
    out = {"audit": "P1B.2 — Output VAT → Input VAT Flow"}
    pairs = frappe.db.sql(
        """SELECT si.name AS si_name, si.customer, si.grand_total,
                  pi.name AS pi_name, pi.company AS buyer_company
           FROM `tabSales Invoice` si
           JOIN `tabPurchase Invoice` pi ON pi.bki_si_reference = si.name
           WHERE si.company = %s AND si.docstatus = 1 AND pi.docstatus = 1
           ORDER BY RAND() LIMIT 5""",
        BKI_COMPANY, as_dict=True,
    )
    out["pair_count"] = len(pairs)
    out["pairs"] = []
    for p in pairs:
        si_taxes = frappe.db.sql(
            """SELECT account_head, tax_amount FROM `tabSales Taxes and Charges`
               WHERE parent = %s ORDER BY idx""",
            p["si_name"], as_dict=True,
        )
        pi_taxes = frappe.db.sql(
            """SELECT account_head, tax_amount FROM `tabPurchase Taxes and Charges`
               WHERE parent = %s ORDER BY idx""",
            p["pi_name"], as_dict=True,
        )
        out["pairs"].append({
            "si_name": p["si_name"],
            "pi_name": p["pi_name"],
            "buyer_company": p["buyer_company"],
            "si_taxes": [{"acct": t["account_head"], "amt": float(t["tax_amount"])} for t in si_taxes],
            "pi_taxes": [{"acct": t["account_head"], "amt": float(t["tax_amount"])} for t in pi_taxes],
            "si_total_vat": sum(float(t["tax_amount"]) for t in si_taxes
                                if "vat" in (t["account_head"] or "").lower()),
            "pi_total_vat": sum(float(t["tax_amount"]) for t in pi_taxes
                                if "vat" in (t["account_head"] or "").lower()),
        })
    return out


# --- P1B.3: Cancel + return flow audit ---
def p1b_3_cancel_cascade_audit():
    """Sample 3 cancelled BKI SIs that had cascaded PIs."""
    out = {"audit": "P1B.3 — Cancel Cascade"}
    cancelled = frappe.db.sql(
        """SELECT name, customer, custom_bei_store_order, modified FROM `tabSales Invoice`
           WHERE company = %s AND docstatus = 2
           ORDER BY modified DESC LIMIT 10""",
        BKI_COMPANY, as_dict=True,
    )
    out["cancelled_si_count"] = len(cancelled)
    out["cases"] = []
    for c in cancelled[:3]:
        # Look for any PI that still references this cancelled SI
        pi_orphan = frappe.db.sql(
            """SELECT name, docstatus FROM `tabPurchase Invoice` WHERE bki_si_reference = %s""",
            c["name"], as_dict=True,
        )
        out["cases"].append({
            "si_name": c["name"],
            "si_cancelled_at": str(c["modified"]),
            "paired_pi_remaining": pi_orphan,
            "cascade_clean": len(pi_orphan) == 0,
        })
    return out


# --- P1B.4: 13 PASS stores inventory posting reality ---
def p1b_4_pass_stores_inventory():
    """For each of 13 PASS stores, check stock GL state."""
    out = {"audit": "P1B.4 — 13 PASS Stores Inventory Reality"}
    out["stores"] = []
    for company in PASS_STORES:
        # Get any stock-related GL entries for this Company
        stock_gl = frappe.db.sql(
            """SELECT COUNT(*) AS cnt, COALESCE(SUM(debit), 0) AS total_dr, COALESCE(SUM(credit), 0) AS total_cr
               FROM `tabGL Entry` ge
               JOIN `tabAccount` a ON a.name = ge.account
               WHERE ge.company = %s
                 AND a.account_type IN ('Stock', 'Stock Received But Not Billed')
                 AND ge.is_cancelled = 0""",
            company, as_dict=True,
        )
        # Total stock value in Warehouse from Bin (current actual_qty * valuation_rate)
        bin_total = frappe.db.sql(
            """SELECT COALESCE(SUM(actual_qty * valuation_rate), 0) AS total_value, COUNT(*) AS bin_count
               FROM `tabBin`
               WHERE warehouse = %s AND actual_qty > 0""",
            company, as_dict=True,
        )
        out["stores"].append({
            "company": company,
            "stock_gl_entry_count": stock_gl[0]["cnt"] if stock_gl else 0,
            "stock_gl_total_dr": float((stock_gl[0] or {}).get("total_dr") or 0),
            "stock_gl_total_cr": float((stock_gl[0] or {}).get("total_cr") or 0),
            "current_bin_inventory_value": float((bin_total[0] or {}).get("total_value") or 0),
            "bin_count_with_stock": (bin_total[0] or {}).get("bin_count") or 0,
        })
    out["zero_stock_gl_count"] = sum(1 for s in out["stores"] if s["stock_gl_entry_count"] == 0)
    out["nonzero_inventory_count"] = sum(1 for s in out["stores"] if s["current_bin_inventory_value"] > 0)
    return out


# --- P1B.5: 839 historical test BKI SI GL audit ---
def p1b_5_historical_si_gl():
    """Breakdown of historical BKI SIs by docstatus + paired PI/SE count + GL footprint."""
    out = {"audit": "P1B.5 — 839 Historical Test BKI SI GL Audit"}
    breakdown = frappe.db.sql(
        """SELECT docstatus, COUNT(*) AS cnt, SUM(grand_total) AS total
           FROM `tabSales Invoice` WHERE company = %s GROUP BY docstatus""",
        BKI_COMPANY, as_dict=True,
    )
    out["si_breakdown"] = [
        {"docstatus": b["docstatus"], "count": b["cnt"],
         "total_pesos": float(b["total"] or 0)} for b in breakdown
    ]
    out["si_total_count"] = sum(b["cnt"] for b in breakdown)

    # Count cascaded PIs (any PI with bki_si_reference set)
    paired_pi = frappe.db.sql(
        """SELECT docstatus, COUNT(*) AS cnt FROM `tabPurchase Invoice`
           WHERE bki_si_reference IS NOT NULL AND bki_si_reference != ''
           GROUP BY docstatus""",
        as_dict=True,
    )
    out["paired_pi_breakdown"] = [{"docstatus": b["docstatus"], "count": b["cnt"]} for b in paired_pi]

    # GL footprint of submitted BKI SIs
    bki_gl = frappe.db.sql(
        """SELECT COUNT(*) AS cnt, COALESCE(SUM(debit), 0) AS dr, COALESCE(SUM(credit), 0) AS cr
           FROM `tabGL Entry`
           WHERE company = %s AND voucher_type = 'Sales Invoice' AND is_cancelled = 0""",
        BKI_COMPANY, as_dict=True,
    )
    out["bki_si_active_gl_entries"] = bki_gl[0]["cnt"] if bki_gl else 0
    out["bki_si_total_dr"] = float((bki_gl[0] or {}).get("dr") or 0)
    out["bki_si_total_cr"] = float((bki_gl[0] or {}).get("cr") or 0)

    # GL footprint of cascaded PIs (on stores' books)
    pi_gl = frappe.db.sql(
        """SELECT COUNT(*) AS cnt, COALESCE(SUM(debit), 0) AS dr, COALESCE(SUM(credit), 0) AS cr
           FROM `tabGL Entry` ge
           JOIN `tabPurchase Invoice` pi ON pi.name = ge.voucher_no
           WHERE ge.voucher_type = 'Purchase Invoice'
             AND pi.bki_si_reference IS NOT NULL AND pi.bki_si_reference != ''
             AND ge.is_cancelled = 0""",
        as_dict=True,
    )
    out["paired_pi_active_gl_entries"] = pi_gl[0]["cnt"] if pi_gl else 0
    out["paired_pi_total_dr"] = float((pi_gl[0] or {}).get("dr") or 0)
    out["paired_pi_total_cr"] = float((pi_gl[0] or {}).get("cr") or 0)

    # Orphan PI check: PIs whose bki_si_reference points to a non-existent SI
    orphan_pi = frappe.db.sql(
        """SELECT COUNT(*) AS cnt FROM `tabPurchase Invoice` pi
           LEFT JOIN `tabSales Invoice` si ON si.name = pi.bki_si_reference
           WHERE pi.bki_si_reference IS NOT NULL AND pi.bki_si_reference != ''
             AND si.name IS NULL""",
        as_dict=True,
    )
    out["orphan_pi_count"] = orphan_pi[0]["cnt"] if orphan_pi else 0

    return out


# --- P1B.6: 30-day Error Log sweep ---
def p1b_6_error_log_sweep():
    """Group S238 errors by unique fingerprint in last 30 days."""
    out = {"audit": "P1B.6 — 30-Day Error Log Sweep"}
    total = frappe.db.sql(
        """SELECT COUNT(*) AS cnt FROM `tabError Log`
           WHERE creation >= NOW() - INTERVAL 30 DAY
             AND (method LIKE '%%S238%%' OR error LIKE 'S238%%' OR error LIKE '%%bki_store_pi%%')""",
        as_dict=True,
    )
    out["total_s238_errors_30d"] = total[0]["cnt"] if total else 0

    # Group by method (truncated title)
    by_method = frappe.db.sql(
        """SELECT method, COUNT(*) AS cnt
           FROM `tabError Log`
           WHERE creation >= NOW() - INTERVAL 30 DAY
             AND (method LIKE '%%S238%%' OR error LIKE 'S238%%' OR error LIKE '%%bki_store_pi%%')
           GROUP BY method ORDER BY cnt DESC LIMIT 10""",
        as_dict=True,
    )
    out["by_method"] = [{"method": b["method"], "count": b["cnt"]} for b in by_method]

    # Daily breakdown
    by_day = frappe.db.sql(
        """SELECT DATE(creation) AS day, COUNT(*) AS cnt
           FROM `tabError Log`
           WHERE creation >= NOW() - INTERVAL 30 DAY
             AND (method LIKE '%%S238%%' OR error LIKE 'S238%%' OR error LIKE '%%bki_store_pi%%')
           GROUP BY DATE(creation) ORDER BY day DESC""",
        as_dict=True,
    )
    out["by_day"] = [{"day": str(b["day"]), "count": b["cnt"]} for b in by_day]

    # Pick the longest error for representative sample
    longest = frappe.db.sql(
        """SELECT name, method, creation, LENGTH(error) AS err_len, error
           FROM `tabError Log`
           WHERE creation >= NOW() - INTERVAL 30 DAY
             AND (method LIKE '%%S238%%' OR error LIKE 'S238%%' OR error LIKE '%%bki_store_pi%%')
           ORDER BY LENGTH(error) DESC LIMIT 3""",
        as_dict=True,
    )
    out["longest_errors"] = [
        {"name": e["name"], "method": e["method"], "creation": str(e["creation"]),
         "err_len": e["err_len"], "preview": e["error"][:800] if e["error"] else None}
        for e in longest
    ]
    return out


# --- P1B.7: Cross-store transfer model audit ---
def p1b_7_cross_store_audit():
    """Check whether store-to-store stock movement is supported / happens."""
    out = {"audit": "P1B.7 — Cross-Store Transfer Model"}
    # Material Transfer Stock Entries between two different store Warehouses
    cross = frappe.db.sql(
        """SELECT se.name, se.stock_entry_type, se.company,
                  sei.s_warehouse, sei.t_warehouse
           FROM `tabStock Entry` se
           JOIN `tabStock Entry Detail` sei ON sei.parent = se.name
           WHERE se.stock_entry_type = 'Material Transfer'
             AND se.docstatus = 1
             AND sei.s_warehouse IS NOT NULL AND sei.t_warehouse IS NOT NULL
             AND sei.s_warehouse != sei.t_warehouse
           ORDER BY se.creation DESC LIMIT 20""",
        as_dict=True,
    )
    out["recent_material_transfer_count"] = len(cross)

    # Pattern: is the transfer between two different per-store Companies (cross-Company)?
    cross_company = 0
    for c in cross:
        s_co = frappe.db.get_value("Warehouse", c["s_warehouse"], "company")
        t_co = frappe.db.get_value("Warehouse", c["t_warehouse"], "company")
        if s_co != t_co:
            cross_company += 1
    out["cross_company_transfer_count"] = cross_company
    out["sample"] = [
        {"name": c["name"], "source": c["s_warehouse"], "target": c["t_warehouse"]}
        for c in cross[:5]
    ]

    # Are there any inter-company API endpoints?
    out["resolve_store_buyer_entity_referenced"] = bool(frappe.db.sql(
        """SELECT COUNT(*) FROM `tabFile` WHERE file_name LIKE '%%supply_chain_contracts%%'""",
        as_dict=True,
    ))
    return out


def main() -> None:
    payload = {
        "sprint": "S246",
        "phase": "1B",
        "purpose": "7-item audit + 30-day Error Log sweep",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "audits": {},
    }
    try:
        frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        frappe.set_user("Administrator")

        payload["audits"]["p1b_1_bki_si_gl"] = p1b_1_bki_si_gl_audit()
        payload["audits"]["p1b_2_tax_flow"] = p1b_2_tax_flow_audit()
        payload["audits"]["p1b_3_cancel_cascade"] = p1b_3_cancel_cascade_audit()
        payload["audits"]["p1b_4_pass_stores_inventory"] = p1b_4_pass_stores_inventory()
        payload["audits"]["p1b_5_historical_si_gl"] = p1b_5_historical_si_gl()
        payload["audits"]["p1b_6_error_log_sweep"] = p1b_6_error_log_sweep()
        payload["audits"]["p1b_7_cross_store"] = p1b_7_cross_store_audit()
        payload["status"] = "OK"

    except Exception as e:
        import traceback
        payload["status"] = "ERROR"
        payload["fatal_error"] = str(e)
        payload["traceback"] = traceback.format_exc()

    out_path = "/tmp/s246_p1b_audit.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    sys.stdout.write(f"S246_P1B_OK status={payload.get('status')}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
