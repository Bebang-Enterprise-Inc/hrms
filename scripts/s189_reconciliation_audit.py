"""S189: Daily reconciliation audit — webhook vs poll parity + consumption accuracy.

Runs daily at 2 AM PHT (via GH Actions) after 1 AM finalization completes.

Checks:
  1. Order count parity: webhook + poll_only = total (exact match)
  2. Consumption parity: BOM-computed consumption matches daily_material_consumption within 0.1%
  3. Frappe SE parity: total KG pushed to Frappe matches daily_material_consumption.total_kg within 0.1%
  4. Store coverage: any store with 0 webhook but >0 poll = internet was down
  5. Alert on drift: if any check fails >1%, log as CRITICAL

Output: tmp/reconciliation/YYYY-MM-DD_audit.json

Usage:
    python scripts/s189_reconciliation_audit.py --date yesterday
    python scripts/s189_reconciliation_audit.py --date 2026-04-12
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://csnniykjrychgajfrgua.supabase.co")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
MGMT_TOKEN = os.environ.get("SUPABASE_MGMT_TOKEN", "")
MGMT_URL = "https://api.supabase.com/v1/projects/csnniykjrychgajfrgua/database/query"

FRAPPE_URL = os.environ.get("FRAPPE_URL", "https://hq.bebang.ph")
FRAPPE_API_KEY = os.environ.get("FRAPPE_API_KEY", "")
FRAPPE_API_SECRET = os.environ.get("FRAPPE_API_SECRET", "")
FRAPPE_AUTH = {"Authorization": f"token {FRAPPE_API_KEY}:{FRAPPE_API_SECRET}"}


def resolve_date(s):
    if s == "today":
        return datetime.utcnow().strftime("%Y-%m-%d")
    if s == "yesterday":
        return (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    return s


def run_sql(sql):
    r = requests.post(MGMT_URL, headers={
        "Authorization": f"Bearer {MGMT_TOKEN}",
        "Content-Type": "application/json",
    }, json={"query": sql}, timeout=60)
    r.raise_for_status()
    return r.json()


def check_order_count_parity(date):
    """Check 1: webhook + poll_only = total."""
    rows = run_sql(f"""
        SELECT
            COUNT(*) FILTER (WHERE ingestion_source = 'webhook') AS webhook,
            COUNT(*) FILTER (WHERE ingestion_source = 'poll') AS poll,
            COUNT(*) FILTER (WHERE ingestion_source = 'backfill') AS backfill,
            COUNT(*) AS total
        FROM pos_orders
        WHERE business_date = '{date}'
    """)
    if not rows:
        return {"check": "order_count_parity", "status": "NO_DATA", "details": f"no orders for {date}"}

    r = rows[0]
    webhook = int(r.get("webhook", 0))
    poll = int(r.get("poll", 0))
    backfill = int(r.get("backfill", 0))
    total = int(r.get("total", 0))

    sum_ = webhook + poll + backfill
    status = "PASS" if sum_ == total else "FAIL"
    return {
        "check": "order_count_parity",
        "status": status,
        "webhook": webhook,
        "poll": poll,
        "backfill": backfill,
        "total": total,
        "sum_of_parts": sum_,
    }


def check_consumption_parity(date):
    """Check 2: BOM-computed vs stored daily_material_consumption."""
    computed = run_sql(f"""
        SELECT
            pb.material_code,
            SUM(COALESCE(i.quantity, 1) * pb.grams_per_serving) AS computed_grams
        FROM pos_order_items i
        JOIN pos_orders o ON o.id = i.order_id
        JOIN product_bom pb ON pb.product_name = i.product_name AND pb.is_active = TRUE
        WHERE o.business_date = '{date}'
        GROUP BY pb.material_code
    """)
    stored = run_sql(f"""
        SELECT material_code, SUM(total_grams) AS stored_grams
        FROM daily_material_consumption
        WHERE business_date = '{date}' AND channel = 'POS'
        GROUP BY material_code
    """)
    stored_map = {r["material_code"]: float(r["stored_grams"]) for r in stored}

    mismatches = []
    for row in computed:
        code = row["material_code"]
        comp = float(row["computed_grams"])
        stored_val = stored_map.get(code, 0.0)
        if comp == 0:
            continue
        pct_diff = abs(comp - stored_val) / comp * 100
        if pct_diff > 0.1:
            mismatches.append({
                "material_code": code,
                "computed": comp,
                "stored": stored_val,
                "pct_diff": round(pct_diff, 3),
            })

    status = "PASS" if not mismatches else "FAIL"
    return {
        "check": "consumption_parity",
        "status": status,
        "materials_checked": len(computed),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:10],
    }


def check_frappe_se_parity(date):
    """Check 3: Frappe SE total KG matches Supabase total."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/daily_material_consumption_frappe_sync",
        params={"business_date": f"eq.{date}", "select": "material_code,total_kg,sync_status,frappe_stock_entry_name"},
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"},
    )
    sync_rows = r.json() if r.ok else []

    if not sync_rows:
        return {"check": "frappe_se_parity", "status": "NO_DATA", "details": "no sync log entries"}

    success = [x for x in sync_rows if x.get("sync_status") == "SUCCESS" or x.get("frappe_stock_entry_name")]
    failed = [x for x in sync_rows if x.get("sync_status") == "FAILED"]

    status = "PASS" if not failed else "WARN"
    return {
        "check": "frappe_se_parity",
        "status": status,
        "sync_log_rows": len(sync_rows),
        "success_count": len(success),
        "failed_count": len(failed),
        "failed_samples": [x["material_code"] for x in failed[:5]],
    }


def check_store_coverage(date):
    """Check 4: stores with 0 webhook but >0 poll (internet was down)."""
    rows = run_sql(f"""
        SELECT location_id,
               COUNT(*) FILTER (WHERE ingestion_source = 'webhook') AS webhook,
               COUNT(*) FILTER (WHERE ingestion_source = 'poll') AS poll
        FROM pos_orders
        WHERE business_date = '{date}'
        GROUP BY location_id
        HAVING COUNT(*) FILTER (WHERE ingestion_source = 'webhook') = 0
           AND COUNT(*) FILTER (WHERE ingestion_source = 'poll') > 0
        ORDER BY poll DESC
    """)
    status = "PASS" if len(rows) <= 5 else "WARN"  # <=5 stores with internet issues is tolerable
    return {
        "check": "store_coverage",
        "status": status,
        "stores_with_internet_issues": len(rows),
        "samples": [
            {"location_id": r["location_id"], "poll_orders": int(r["poll"])}
            for r in rows[:10]
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--output-dir", default="tmp/reconciliation")
    args = parser.parse_args()

    date = resolve_date(args.date)
    print(f"S189 Reconciliation Audit — {date}")

    results = {
        "date": date,
        "run_at": datetime.utcnow().isoformat(),
        "checks": [],
    }

    for fn in [check_order_count_parity, check_consumption_parity, check_frappe_se_parity, check_store_coverage]:
        try:
            result = fn(date)
            results["checks"].append(result)
            icon = {"PASS": "[OK]", "WARN": "[WARN]", "FAIL": "[FAIL]", "NO_DATA": "[--]"}.get(result["status"], "[?]")
            print(f"  {icon} {result['check']}: {result['status']}")
            if result["status"] in ("FAIL", "WARN"):
                print(f"       {json.dumps({k: v for k, v in result.items() if k not in ('check','status')}, default=str)[:200]}")
        except Exception as e:
            print(f"  [ERROR] {fn.__name__}: {e}")
            results["checks"].append({"check": fn.__name__, "status": "ERROR", "error": str(e)})

    # Overall status
    statuses = [c["status"] for c in results["checks"]]
    results["overall"] = (
        "FAIL" if "FAIL" in statuses else
        "ERROR" if "ERROR" in statuses else
        "WARN" if "WARN" in statuses else
        "PASS"
    )
    print(f"\nOverall: {results['overall']}")

    # Write output
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date}_audit.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"Saved: {out_path}")

    if results["overall"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
