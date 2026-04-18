"""S204 Phase 0 preflight verification.

Checks (all via Frappe REST API on hq.bebang.ph):
1. hrms PR #610 deployed to production (merge commit landed, code live)
2. BEI Settings.commissary_company == "BEBANG KITCHEN INC."
3. Each target customer has BEBANG KITCHEN INC. in its `companies` allowlist
4. Pinnacle Cold Storage stock >= 5000 per key SKU

Writes output/l3/s204/PHASE0_READINESS.json with full verdict.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import urllib.error
import urllib.parse
import urllib.request

HQ = "https://hq.bebang.ph"
KEY_SKUS = ["FG001", "FG002", "FG010", "FG023", "PM002", "PM003", "PM007"]
PINNACLE_WH = "PINNACLE COLD STORAGE SOLUTIONS - BKI"
MIN_STOCK = 5000
TARGET_CUSTOMERS = [
    "BEBANG MEGA INC.",         # S1 SM Tanza + S4 Ayala Evo (internal)
    "BEBANG ENTERPRISE INC.",   # S2 SM Megamall (internal)
    "TASTECARTEL CORP.",        # S3 The Grid - Rockwell (non-internal; negative-path, billing-hold expected)
]
REQUIRED_COMPANY = "BEBANG KITCHEN INC."


def _auth_header() -> dict[str, str]:
    key = os.environ.get("FRAPPE_API_KEY")
    secret = os.environ.get("FRAPPE_API_SECRET")
    if not (key and secret):
        sys.exit(
            "FRAPPE_API_KEY / FRAPPE_API_SECRET not in env. "
            "Re-run with: FRAPPE_API_KEY=$(doppler ...) FRAPPE_API_SECRET=$(doppler ...) python ..."
        )
    return {
        "Authorization": f"token {key}:{secret}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) S204-Preflight",
        "Accept": "application/json",
    }


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{HQ}{path}"
    if params:
        url += "?" + urllib.parse.urlencode({k: (json.dumps(v) if not isinstance(v, str) else v) for k, v in params.items()})
    req = urllib.request.Request(url, headers=_auth_header())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"_http_error": e.code, "_body": body}
    except Exception as e:
        return {"_error": str(e)}


def check_deploy_marker() -> dict[str, Any]:
    """Confirm S203 followup is in production HEAD (via git log on local repo)."""
    try:
        result = subprocess.run(
            ["git", "log", "origin/production", "--oneline", "-30"],
            capture_output=True, text=True, check=True,
            cwd=Path(__file__).resolve().parent.parent,
        )
        has_s203_followup = "S203 followup" in result.stdout and "bei_legal_entity" in result.stdout
        return {
            "pr_610_in_production_log": has_s203_followup,
            "matches": [line for line in result.stdout.splitlines() if "S203 followup" in line or "bei_legal_entity" in line],
        }
    except Exception as e:
        return {"error": str(e)}


def check_commissary_setting() -> dict[str, Any]:
    r = _get(
        "/api/method/frappe.client.get_single_value",
        {"doctype": "BEI Settings", "field": "commissary_company"},
    )
    value = r.get("message") if isinstance(r, dict) else None
    return {
        "commissary_company": value,
        "expected": REQUIRED_COMPANY,
        "match": value == REQUIRED_COMPANY,
        "raw": r,
    }


def check_markup_setting() -> dict[str, Any]:
    r = _get(
        "/api/method/frappe.client.get_single_value",
        {"doctype": "BEI Settings", "field": "bki_markup_jv_percent"},
    )
    return {"bki_markup_jv_percent": r.get("message") if isinstance(r, dict) else None, "raw": r}


def check_customer_allowlist(customer_name: str) -> dict[str, Any]:
    r = _get(
        "/api/method/frappe.client.get",
        {"doctype": "Customer", "name": customer_name},
    )
    msg = r.get("message") if isinstance(r, dict) else None
    if not msg:
        return {"customer": customer_name, "found": False, "raw": r}
    companies = [row.get("company") for row in (msg.get("companies") or [])]
    return {
        "customer": customer_name,
        "found": True,
        "is_internal_customer": msg.get("is_internal_customer"),
        "companies": companies,
        "has_bki": REQUIRED_COMPANY in companies,
    }


def check_pinnacle_stock() -> dict[str, Any]:
    bins = {}
    for sku in KEY_SKUS:
        r = _get(
            "/api/method/frappe.client.get_list",
            {
                "doctype": "Bin",
                "filters": {"item_code": sku, "warehouse": PINNACLE_WH},
                "fields": ["item_code", "warehouse", "actual_qty", "reserved_qty", "projected_qty"],
                "limit_page_length": 5,
            },
        )
        rows = r.get("message") or []
        qty = float(rows[0].get("actual_qty", 0)) if rows else 0.0
        bins[sku] = {"actual_qty": qty, "sufficient": qty >= MIN_STOCK, "raw_rows": rows}
    return bins


def main() -> int:
    out_dir = Path(__file__).resolve().parent.parent / "output" / "l3" / "s204"
    out_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "generated_at_utc": subprocess.run(
            ["python", "-c", "from datetime import datetime,timezone;print(datetime.now(timezone.utc).isoformat())"],
            capture_output=True, text=True, check=True,
        ).stdout.strip(),
        "deploy_marker": check_deploy_marker(),
        "commissary_company": check_commissary_setting(),
        "bki_markup_jv_percent": check_markup_setting(),
        "customers": [check_customer_allowlist(name) for name in TARGET_CUSTOMERS],
        "pinnacle_stock": check_pinnacle_stock(),
    }

    # Roll up
    # Internal customers must have BKI in allowlist; non-internal customers don't hit validate_inter_company_party
    def _customer_ok(c: dict[str, Any]) -> bool:
        if not c.get("found"):
            return False
        if c.get("is_internal_customer"):
            return bool(c.get("has_bki"))
        return True  # non-internal: allowlist irrelevant

    verdicts = {
        "deploy_ok": report["deploy_marker"].get("pr_610_in_production_log", False),
        "commissary_setting_ok": report["commissary_company"].get("match", False),
        "customers_ok": all(_customer_ok(c) for c in report["customers"]),
        "stock_ok": all(b["sufficient"] for b in report["pinnacle_stock"].values()),
    }
    report["verdicts"] = verdicts
    report["all_green"] = all(verdicts.values())

    (out_dir / "PHASE0_READINESS.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps({"verdicts": verdicts, "all_green": report["all_green"]}, indent=2))
    return 0 if report["all_green"] else 1


if __name__ == "__main__":
    sys.exit(main())
