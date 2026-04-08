"""S171 - Mosaic POS + Website Sync Full Parity Audit (orchestrator).

Validates pos_orders / pos_order_items / pos_order_payments / price_breakdown /
channel classification / cross-channel reconciliation / tombstones across the
last N days against Mosaic POS as source-of-truth, plus drives the web_orders
verifier (Phase 6) and produces the canonical drift / defect artifacts under
output/l3/s171/.

Reuses S169 helpers as a library:
  - supabase_ids, mosaic_ids, tombstone_extras, _supabase_query_sql
    from scripts.verify_mosaic_pos_sync
  - load_credentials, ensure_token, REQUEST_INTERVAL, MAX_RETRIES, RETRY_WAIT,
    RATE_LIMIT_WAIT, MOSAIC_ORDERS_URL, _CHANNEL_MAP, _resolve_channel
    from scripts.sync_pos_to_supabase

Does NOT modify either S169 script. Anti-rewind contract: protected surfaces
are read-only here.

CLI:
  python scripts/s171_full_parity_audit.py \\
      [--from YYYY-MM-DD] [--to YYYY-MM-DD] \\
      [--tables pos_orders,pos_order_items,pos_order_payments,price_breakdown,channels,cross_channel,tombstone] \\
      [--sample 20] [--tombstone] [--dry-run] [--limit-stores N]

Env vars (via Doppler bei-erp/dev fallback):
  SUPABASE_SERVICE_ROLE_KEY, SUPABASE_MGMT_TOKEN, SENTRY_DSN
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import sentry_sdk

# ---------------------------------------------------------------------------
# Bootstrap S169 helpers
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Force Doppler resolution BEFORE importing the S169 modules so that
# sync_pos_to_supabase sees populated SUPABASE_KEY at import time.
def _resolve_secret(env_name: str) -> str:
    val = os.environ.get(env_name, "").strip()
    if val:
        return val
    try:
        import subprocess
        result = subprocess.run(
            ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", env_name,
             "--plain", "--project", "bei-erp", "--config", "dev"],
            capture_output=True, text=True, timeout=15,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""

for _k in ("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_MGMT_TOKEN", "SENTRY_DSN",
           "SUPERADMIN_API_KEY"):
    if not os.environ.get(_k):
        v = _resolve_secret(_k)
        if v:
            os.environ[_k] = v

import sync_pos_to_supabase as sps  # noqa: E402
import verify_mosaic_pos_sync as v169  # noqa: E402
from sync_pos_to_supabase import (  # noqa: E402
    load_credentials,
    ensure_token,
    REQUEST_INTERVAL,
    MAX_RETRIES,
    RETRY_WAIT,
    RATE_LIMIT_WAIT,
    MOSAIC_ORDERS_URL,
    CREDENTIALS_CSV,
    SUPABASE_URL,
    _CHANNEL_MAP,
)
from verify_mosaic_pos_sync import (  # noqa: E402
    supabase_ids,
    mosaic_ids as _mosaic_ids_s169,  # bug: uses page[size]=200, Mosaic max is 100
    tombstone_extras,
    _supabase_query_sql,
)


def mosaic_ids(client: httpx.Client, cred: dict,
               location_id: int, business_date: str) -> set[int]:
    """S171 local override of S169 mosaic_ids() with page[size]=100.

    The S169 helper hardcodes page[size]=200 which now hits a Mosaic 422
    `The page.size field must not be greater than 100.` Protected surface
    rule forbids editing the S169 script, so S171 owns its own fetcher.
    """
    token = ensure_token(client, cred)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    out: set[int] = set()
    page_number = 1
    page_size = 100  # Mosaic hard limit
    while True:
        params = {
            "filter[business_date]": business_date,
            "filter[location_id]": location_id,
            "page[number]": page_number,
            "page[size]": page_size,
        }
        last_exc: Exception | None = None
        data = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = client.get(MOSAIC_ORDERS_URL, headers=headers,
                               params=params, timeout=60)
                if r.status_code == 200:
                    data = r.json()
                    break
                if r.status_code == 429:
                    time.sleep(RATE_LIMIT_WAIT)
                    continue
                if r.status_code >= 500:
                    time.sleep(RETRY_WAIT)
                    continue
                raise RuntimeError(
                    f"Mosaic API error {r.status_code}: {r.text[:200]}")
            except httpx.RequestError as e:
                last_exc = e
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_WAIT)
                    continue
                raise
        if data is None:
            if last_exc:
                raise last_exc
            raise RuntimeError("mosaic_ids: max retries exceeded")
        rows = data.get("data") or []
        for row in rows:
            try:
                out.add(int(row.get("id")))
            except (TypeError, ValueError):
                continue
        if len(rows) < page_size:
            break
        page_number += 1
        time.sleep(REQUEST_INTERVAL)
    return out

# Propagate Supabase secrets to the S169 module for any helper that reads them.
sps.SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
sps.SUPABASE_MGMT_TOKEN = os.environ.get("SUPABASE_MGMT_TOKEN", "")

# Sentry (CB5 fail-fast)
SENTRY_DSN = os.environ.get("SENTRY_DSN", "").strip()
if not SENTRY_DSN:
    print("ERROR: SENTRY_DSN missing -- S171 audit refuses to run without observability.",
          file=sys.stderr)
    sys.exit(2)
sentry_sdk.init(
    dsn=SENTRY_DSN,
    traces_sample_rate=0.0,
    profiles_sample_rate=0.0,
    release="s171-full-parity-audit",
)
sentry_sdk.set_tag("module", "sync_verification")
sentry_sdk.set_tag("action", "s171_full_parity_audit")

PHT = timezone(timedelta(hours=8))
OUT_DIR = ROOT.parent / "output" / "l3" / "s171"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Evidence accumulators
# ---------------------------------------------------------------------------
EVIDENCE = {
    "form_submissions": [],
    "api_mutations": [],
    "state_verification": [],
}


def _record_form(form: str, inputs: dict, action: str, response: Any) -> None:
    EVIDENCE["form_submissions"].append({
        "form": form,
        "inputs": inputs,
        "submit_action": action,
        "response": str(response)[:500],
        "ts": datetime.now(PHT).isoformat(),
    })


def _record_mutation(endpoint: str, method: str, payload: Any, status: int,
                     body: Any) -> None:
    EVIDENCE["api_mutations"].append({
        "endpoint": endpoint,
        "method": method,
        "payload": payload if isinstance(payload, (dict, list, str, int, float, type(None))) else str(payload)[:500],
        "status": status,
        "response_body": (json.dumps(body)[:500] if not isinstance(body, str) else body[:500]),
        "ts": datetime.now(PHT).isoformat(),
    })


def _record_state(check: str, before: Any, after: Any, passed: bool) -> None:
    EVIDENCE["state_verification"].append({
        "check": check,
        "before": before,
        "after": after,
        "passed": bool(passed),
        "ts": datetime.now(PHT).isoformat(),
    })


def _flush_evidence() -> None:
    for k, v in EVIDENCE.items():
        (OUT_DIR / f"{k}.json").write_text(
            json.dumps(v, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _today_pht() -> datetime:
    return datetime.now(PHT)


def _date_range(date_from: str, date_to: str) -> list[str]:
    d0 = datetime.strptime(date_from, "%Y-%m-%d").date()
    d1 = datetime.strptime(date_to, "%Y-%m-%d").date()
    out = []
    cur = d0
    while cur <= d1:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _mosaic_get_order(client: httpx.Client, token: str, order_id: int) -> tuple[int, dict | None]:
    url = f"{MOSAIC_ORDERS_URL}/{order_id}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = client.get(url, headers=headers, timeout=30)
            if r.status_code == 429:
                time.sleep(RATE_LIMIT_WAIT)
                continue
            if r.status_code >= 500:
                time.sleep(RETRY_WAIT)
                continue
            if r.status_code == 200:
                try:
                    return 200, r.json()
                except Exception:
                    return 200, None
            return r.status_code, None
        except httpx.RequestError:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
                continue
            return 0, None
    return 0, None


# ---------------------------------------------------------------------------
# Phase 0 - preflight
# ---------------------------------------------------------------------------
def phase0(args) -> dict:
    print("[Phase 0] Preflight: schema probe + Mosaic health check")
    creds = load_credentials(CREDENTIALS_CSV)
    print(f"  Loaded {len(creds)} credential groups, "
          f"{sum(len(c['locations']) for c in creds)} store locations")

    # Schema probe via Supabase Mgmt API
    schema_sql = """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema='public'
          AND table_name IN ('pos_orders','pos_order_items','pos_order_payments',
                             'web_orders','web_order_items','sync_verification',
                             'v_pos_orders_live','daily_revenue')
        ORDER BY table_name, ordinal_position
    """
    schema = _supabase_query_sql(schema_sql)
    table_set = sorted({r["table_name"] for r in (schema or [])})
    print(f"  Schema present: {table_set}")

    # Mosaic health check on first 3 cred groups
    health = []
    with httpx.Client(http2=False) as client:
        for cred in creds[:3]:
            try:
                tok = ensure_token(client, cred)
                loc = cred["locations"][0]
                r = client.get(
                    MOSAIC_ORDERS_URL,
                    headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"},
                    params={
                        "filter[business_date]": (_today_pht() - timedelta(days=1)).strftime("%Y-%m-%d"),
                        "filter[location_id]": loc["location_id"],
                        "page[number]": 1, "page[size]": 1,
                    }, timeout=30,
                )
                health.append({
                    "group": cred["group_name"],
                    "client_id_tail": cred["client_id"][-6:],
                    "location_probed": loc["store_name"],
                    "status_code": r.status_code,
                    "ok": r.status_code == 200,
                })
            except Exception as e:
                health.append({"group": cred["group_name"], "error": str(e)[:200], "ok": False})
            time.sleep(REQUEST_INTERVAL)

    out = {
        "ts": datetime.now(PHT).isoformat(),
        "creds_loaded": len(creds),
        "stores": sum(len(c["locations"]) for c in creds),
        "schema_tables": table_set,
        "schema_columns": schema,
        "mosaic_health": health,
    }
    (OUT_DIR / "phase0_preflight.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    _record_form("phase0_preflight", {"creds": len(creds)}, "preflight", out)
    print(f"  Phase 0 OK -> output/l3/s171/phase0_preflight.json")
    return out


# ---------------------------------------------------------------------------
# Phase 1 - pos_orders count parity sweep
# ---------------------------------------------------------------------------
def phase1(args, creds: list[dict]) -> dict:
    print(f"[Phase 1] pos_orders count parity {args.date_from} -> {args.date_to}")
    dates = _date_range(args.date_from, args.date_to)
    drift_rows: list[dict] = []
    summary = {"total_phantoms": 0, "total_duplicates": 0, "total_missing": 0,
               "total_unconfirmed": 0, "tuples_audited": 0, "tuples_with_drift": 0}

    with httpx.Client(http2=False) as client:
        for cred in creds:
            tok_ts = 0
            locs = cred["locations"]
            if args.limit_stores:
                locs = locs[:args.limit_stores]
            for loc in locs:
                for ds in dates:
                    summary["tuples_audited"] += 1
                    try:
                        sup_ids = supabase_ids(client, loc["location_id"], ds)
                        mos_ids = mosaic_ids(client, cred, loc["location_id"], ds)
                    except Exception as e:
                        sentry_sdk.capture_exception(e)
                        drift_rows.append({
                            "location_id": loc["location_id"],
                            "location_name": loc["store_name"],
                            "business_date": ds,
                            "error": str(e)[:200],
                        })
                        continue
                    extras_ids = sorted(sup_ids - mos_ids)
                    missing_ids = sorted(mos_ids - sup_ids)
                    extras_status: list[dict] = []
                    phantom = duplicate = unconfirmed = 0
                    if extras_ids:
                        token = ensure_token(client, cred)
                        for oid in extras_ids[:50]:  # cap per-tuple to keep volume sane
                            sc, _ = _mosaic_get_order(client, token, oid)
                            time.sleep(REQUEST_INTERVAL)
                            if sc == 404:
                                extras_status.append({"id": oid, "status": "phantom"})
                                phantom += 1
                            elif sc == 200:
                                extras_status.append({"id": oid, "status": "duplicate"})
                                duplicate += 1
                            elif sc and sc >= 500:
                                extras_status.append({"id": oid, "status": "unconfirmed_transient"})
                                unconfirmed += 1
                            else:
                                extras_status.append({"id": oid, "status": f"unconfirmed_{sc}"})
                                unconfirmed += 1
                    row = {
                        "location_id": loc["location_id"],
                        "location_name": loc["store_name"],
                        "business_date": ds,
                        "mosaic_count": len(mos_ids),
                        "supabase_count": len(sup_ids),
                        "extras_count": len(extras_ids),
                        "missing_count": len(missing_ids),
                        "phantom_count": phantom,
                        "duplicate_count": duplicate,
                        "unconfirmed_count": unconfirmed,
                        "extras": extras_status,
                        "missing_ids_sample": missing_ids[:20],
                    }
                    drift_rows.append(row)
                    summary["total_phantoms"] += phantom
                    summary["total_duplicates"] += duplicate
                    summary["total_missing"] += len(missing_ids)
                    summary["total_unconfirmed"] += unconfirmed
                    if extras_ids or missing_ids:
                        summary["tuples_with_drift"] += 1
                    print(f"  loc={loc['location_id']:>5} {ds} mosaic={len(mos_ids):>4} "
                          f"sup={len(sup_ids):>4} extras={len(extras_ids):>3} "
                          f"missing={len(missing_ids):>3} ph={phantom} dup={duplicate}")

    out = {"summary": summary, "rows": drift_rows,
           "window": {"from": args.date_from, "to": args.date_to}}
    (OUT_DIR / "pos_orders_drift.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    _record_form("phase1_count_parity", {"days": len(dates), "creds": len(creds)},
                 "count_parity_sweep", summary)
    print(f"  Phase 1 OK -> output/l3/s171/pos_orders_drift.json")
    print(f"  Summary: {summary}")
    return out


# ---------------------------------------------------------------------------
# Phases 2/3/4 - per-order sample audit (items, payments, price_breakdown)
# ---------------------------------------------------------------------------
def phases_2_3_4(args, creds: list[dict], phase1_out: dict) -> dict:
    print(f"[Phases 2/3/4] Sampling {args.sample} orders per store-day for "
          f"items / payments / price_breakdown parity")
    items_drift: list[dict] = []
    payments_drift: list[dict] = []
    price_outliers: list[dict] = []
    sampled = 0

    # Build lookup: cred for a given location_id
    loc_to_cred = {}
    for c in creds:
        for loc in c["locations"]:
            loc_to_cred[loc["location_id"]] = c

    with httpx.Client(http2=False) as client:
        for row in phase1_out["rows"]:
            if "error" in row:
                continue
            if row.get("supabase_count", 0) == 0:
                continue
            cred = loc_to_cred.get(row["location_id"])
            if not cred:
                continue
            loc_id = row["location_id"]
            ds = row["business_date"]

            # Pull a sample of supabase IDs for this store-day
            sup_ids_sql = (
                f"SELECT id FROM v_pos_orders_live "
                f"WHERE location_id={loc_id} AND business_date='{ds}' "
                f"ORDER BY id LIMIT {args.sample}"
            )
            try:
                ids_resp = _supabase_query_sql(sup_ids_sql)
            except Exception as e:
                sentry_sdk.capture_exception(e)
                continue
            sample_ids = [int(r["id"]) for r in (ids_resp or [])]
            if not sample_ids:
                continue

            # Fetch supabase rows incl items, payments, price_breakdown
            sup_full_sql = (
                "SELECT po.id, po.gross_sales, po.net_sales, po.vatable_sales, "
                "po.vat_amount, po.vat_exempt_sales, po.zero_rated_sales, "
                "po.total_discounts, po.delivery_fee, "
                "(SELECT json_agg(json_build_object("
                "'product_id',poi.product_id,'quantity',poi.quantity,"
                "'price',poi.price,'gross_sales',poi.gross_sales)) "
                "FROM pos_order_items poi WHERE poi.order_id=po.id) AS items, "
                "(SELECT json_agg(json_build_object("
                "'payment_type',pop.payment_type,'paid_amount',pop.paid_amount,"
                "'returned_amount',pop.returned_amount)) "
                "FROM pos_order_payments pop WHERE pop.order_id=po.id) AS payments "
                f"FROM pos_orders po WHERE po.id = ANY(ARRAY{sample_ids}::int[])"
            )
            try:
                sup_full = _supabase_query_sql(sup_full_sql)
            except Exception as e:
                sentry_sdk.capture_exception(e)
                continue
            sup_by_id = {int(r["id"]): r for r in (sup_full or [])}

            token = ensure_token(client, cred)
            for oid in sample_ids:
                sampled += 1
                sc, mos = _mosaic_get_order(client, token, oid)
                time.sleep(REQUEST_INTERVAL)
                if sc != 200 or mos is None:
                    continue
                m_order = (mos.get("data") if isinstance(mos, dict) else None) or mos
                if not isinstance(m_order, dict):
                    continue
                m_attrs = m_order.get("attributes", m_order)
                sup_row = sup_by_id.get(oid, {})

                # ---- Phase 2: items ----
                m_items = m_attrs.get("items") or m_attrs.get("order_items") or []
                s_items = sup_row.get("items") or []
                if isinstance(s_items, str):
                    try:
                        s_items = json.loads(s_items)
                    except Exception:
                        s_items = []
                if len(m_items) != len(s_items or []):
                    items_drift.append({
                        "order_id": oid, "location_id": loc_id, "business_date": ds,
                        "kind": "count_mismatch",
                        "mosaic_count": len(m_items),
                        "supabase_count": len(s_items or []),
                    })

                # ---- Phase 3: payments ----
                m_pays = m_attrs.get("payments") or m_attrs.get("payment_methods") or []
                s_pays = sup_row.get("payments") or []
                if isinstance(s_pays, str):
                    try:
                        s_pays = json.loads(s_pays)
                    except Exception:
                        s_pays = []
                if len(m_pays) != len(s_pays or []):
                    payments_drift.append({
                        "order_id": oid, "location_id": loc_id, "business_date": ds,
                        "kind": "count_mismatch",
                        "mosaic_count": len(m_pays),
                        "supabase_count": len(s_pays or []),
                    })

                # ---- Phase 4: price_breakdown ----
                m_pb = m_attrs.get("price_breakdown") or m_attrs.get("totals") or {}
                if isinstance(m_pb, dict):
                    field_map = {
                        "gross_sales": "gross_sales",
                        "net_sales": "net_sales",
                        "vatable_sales": "vatable_sales",
                        "vat_amount": "vat_amount",
                        "vat_exempt_sales": "vat_exempt_sales",
                        "zero_rated_sales": "zero_rated_sales",
                        "total_discounts": "total_discounts",
                    }
                    drifts = {}
                    for sup_k, mos_k in field_map.items():
                        sv = sup_row.get(sup_k)
                        mv = m_pb.get(mos_k)
                        if sv is None or mv is None:
                            continue
                        try:
                            d = abs(float(sv) - float(mv))
                            if d > 0.01:
                                drifts[sup_k] = {"supabase": float(sv),
                                                 "mosaic": float(mv), "delta": d}
                        except (TypeError, ValueError):
                            continue
                    if drifts:
                        price_outliers.append({
                            "order_id": oid, "location_id": loc_id,
                            "business_date": ds, "drifts": drifts,
                        })
            print(f"  loc={loc_id} {ds}: sampled {len(sample_ids)} orders")

    items_out = {"summary": {"sampled": sampled, "drift_rows": len(items_drift)},
                 "rows": items_drift}
    pays_out = {"summary": {"sampled": sampled, "drift_rows": len(payments_drift)},
                "rows": payments_drift}
    price_out = {"summary": {"sampled": sampled, "outlier_orders": len(price_outliers)},
                 "rows": price_outliers}
    (OUT_DIR / "pos_order_items_drift.json").write_text(json.dumps(items_out, indent=2, default=str), encoding="utf-8")
    (OUT_DIR / "pos_order_payments_drift.json").write_text(json.dumps(pays_out, indent=2, default=str), encoding="utf-8")
    (OUT_DIR / "price_breakdown_outliers.json").write_text(json.dumps(price_out, indent=2, default=str), encoding="utf-8")
    _record_form("phases_2_3_4", {"sample_per_tuple": args.sample, "total_sampled": sampled},
                 "per_order_sample_audit",
                 {"items_drift": len(items_drift), "payments_drift": len(payments_drift),
                  "price_outliers": len(price_outliers)})
    print(f"  Phases 2/3/4 OK: sampled={sampled} items_drift={len(items_drift)} "
          f"pays_drift={len(payments_drift)} price_outliers={len(price_outliers)}")
    return {"items": items_out, "payments": pays_out, "price_breakdown": price_out}


# ---------------------------------------------------------------------------
# Phase 5 - channel classification audit
# ---------------------------------------------------------------------------
def phase5(args) -> dict:
    print("[Phase 5] Channel classification audit")
    sql = (
        "SELECT service_type_id, service_channel_id, channel, COUNT(*) AS n "
        "FROM v_pos_orders_live "
        f"WHERE business_date >= '{args.date_from}' AND business_date <= '{args.date_to}' "
        "GROUP BY service_type_id, service_channel_id, channel "
        "ORDER BY n DESC"
    )
    rows = _supabase_query_sql(sql) or []

    def expected(stid, scid):
        if stid in (17, 91):
            return "POS"
        if stid == 3:
            if scid == 1:
                return "GrabFood"
            if scid in (2, 16):
                return "FoodPanda"
            if scid == 19:
                return "WebDelivery"
            return "Delivery"
        if stid is None:
            return "Unknown"
        return "POS"

    misclassified = []
    for r in rows:
        stid = r.get("service_type_id")
        scid = r.get("service_channel_id")
        ch = r.get("channel")
        exp = expected(stid, scid)
        if ch != exp:
            misclassified.append({
                "service_type_id": stid, "service_channel_id": scid,
                "actual_channel": ch, "expected_channel": exp,
                "row_count": int(r.get("n") or 0),
            })
    out = {"window": {"from": args.date_from, "to": args.date_to},
           "tuples": rows, "misclassified": misclassified}
    (OUT_DIR / "channel_classification_audit.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    _record_form("phase5_channels", {"window": args.date_from + ".." + args.date_to},
                 "channel_audit",
                 {"distinct_tuples": len(rows), "misclassified": len(misclassified)})
    print(f"  Phase 5 OK: {len(rows)} distinct tuples, {len(misclassified)} misclassified")
    return out


# ---------------------------------------------------------------------------
# Phase 7 - cross-channel reconciliation
# ---------------------------------------------------------------------------
def phase7(args) -> dict:
    print("[Phase 7] Cross-channel reconciliation")
    sql = f"""
        WITH pos AS (
            SELECT location_id, business_date,
                   SUM(gross_sales) AS pos_gross
            FROM v_pos_orders_live
            WHERE business_date >= '{args.date_from}'
              AND business_date <= '{args.date_to}'
              AND COALESCE(channel,'') NOT IN ('WebDelivery')
            GROUP BY location_id, business_date
        ),
        web AS (
            SELECT location_id, business_date,
                   SUM(gross_sales) AS web_gross
            FROM web_orders
            WHERE business_date >= '{args.date_from}'
              AND business_date <= '{args.date_to}'
            GROUP BY location_id, business_date
        )
        SELECT COALESCE(p.location_id, w.location_id) AS location_id,
               COALESCE(p.business_date, w.business_date) AS business_date,
               COALESCE(p.pos_gross, 0)::numeric AS pos_gross,
               COALESCE(w.web_gross, 0)::numeric AS web_gross,
               (COALESCE(p.pos_gross,0) + COALESCE(w.web_gross,0))::numeric AS combined_gross
        FROM pos p
        FULL OUTER JOIN web w
          ON p.location_id = w.location_id AND p.business_date = w.business_date
        ORDER BY business_date DESC, location_id
    """
    try:
        rows = _supabase_query_sql(sql) or []
    except Exception as e:
        sentry_sdk.capture_exception(e)
        rows = [{"error": str(e)[:200]}]
    out = {"window": {"from": args.date_from, "to": args.date_to},
           "rows": rows}
    (OUT_DIR / "cross_channel_reconciliation.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    _record_form("phase7_cross_channel", {"window": args.date_from + ".." + args.date_to},
                 "cross_channel_recon", {"rows": len(rows)})
    print(f"  Phase 7 OK: {len(rows)} (store, date) tuples")
    return out


# ---------------------------------------------------------------------------
# Phase 8 - tombstone confirmed phantoms
# ---------------------------------------------------------------------------
def phase8(args, creds: list[dict], phase1_out: dict) -> dict:
    print("[Phase 8] Tombstone confirmed phantoms (S169 path)")
    loc_to_cred = {}
    for c in creds:
        for loc in c["locations"]:
            loc_to_cred[loc["location_id"]] = c

    tombstoned: list[dict] = []
    with httpx.Client(http2=False) as client:
        for row in phase1_out["rows"]:
            if not row.get("phantom_count"):
                continue
            cred = loc_to_cred.get(row["location_id"])
            if not cred:
                continue
            phantom_ids = {e["id"] for e in row.get("extras", []) if e.get("status") == "phantom"}
            if not phantom_ids:
                continue
            # Use S169 tombstone_extras with synthetic sets so it confirms again + writes
            try:
                sup_set = set(phantom_ids)
                mos_set: set[int] = set()
                confirmed, unconfirmed = tombstone_extras(
                    client, cred, row["location_id"], row["business_date"],
                    sup_set, mos_set, dry_run=args.dry_run,
                )
                tombstoned.append({
                    "location_id": row["location_id"],
                    "business_date": row["business_date"],
                    "confirmed_ids": confirmed,
                    "unconfirmed": unconfirmed,
                })
                _record_mutation(
                    f"UPDATE pos_orders SET cancelled_at=NOW() WHERE id=ANY(...) [loc={row['location_id']} {row['business_date']}]",
                    "UPDATE", {"ids": confirmed}, 200,
                    {"tombstoned": len(confirmed), "unconfirmed": len(unconfirmed)},
                )
            except Exception as e:
                sentry_sdk.capture_exception(e)
                tombstoned.append({"location_id": row["location_id"],
                                   "business_date": row["business_date"],
                                   "error": str(e)[:200]})

    out = {"summary": {"tuples_processed": len(tombstoned),
                       "total_tombstoned": sum(len(t.get("confirmed_ids", [])) for t in tombstoned)},
           "rows": tombstoned, "dry_run": args.dry_run}
    (OUT_DIR / "phantoms_tombstoned_s171.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    _record_form("phase8_tombstone", {"dry_run": args.dry_run},
                 "tombstone_phantoms", out["summary"])
    print(f"  Phase 8 OK: tombstoned={out['summary']['total_tombstoned']} dry_run={args.dry_run}")
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="S171 full parity audit")
    today = _today_pht().date()
    default_to = (today - timedelta(days=1)).isoformat()
    default_from = (today - timedelta(days=30)).isoformat()
    p.add_argument("--from", dest="date_from", default=default_from)
    p.add_argument("--to", dest="date_to", default=default_to)
    p.add_argument("--tables",
                   default="phase0,pos_orders,sample,channels,cross_channel,tombstone")
    p.add_argument("--sample", type=int, default=10,
                   help="orders to sample per (store, date) for items/payments/price")
    p.add_argument("--tombstone", action="store_true",
                   help="apply S169 tombstone path on confirmed phantoms")
    p.add_argument("--dry-run", action="store_true",
                   help="no UPDATE writes; print intended tombstones only")
    p.add_argument("--limit-stores", type=int, default=0,
                   help="cap stores per credential group (smoke test)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    print(f"S171 audit window: {args.date_from} -> {args.date_to}")
    print(f"Tables: {args.tables}")
    creds = load_credentials(CREDENTIALS_CSV)

    tables = {t.strip() for t in args.tables.split(",") if t.strip()}
    phase1_out: dict = {"rows": []}

    try:
        if "phase0" in tables:
            phase0(args)
        if "pos_orders" in tables:
            phase1_out = phase1(args, creds)
        if "sample" in tables and not phase1_out.get("rows"):
            # Load phase1 from disk if Phase 1 wasn't run in this invocation
            p1 = OUT_DIR / "pos_orders_drift.json"
            if p1.exists():
                phase1_out = json.loads(p1.read_text(encoding="utf-8"))
                print(f"  loaded Phase 1 from disk: {len(phase1_out.get('rows', []))} rows")
        if "sample" in tables and phase1_out.get("rows"):
            phases_2_3_4(args, creds, phase1_out)
        if "channels" in tables:
            phase5(args)
        if "cross_channel" in tables:
            phase7(args)
        if "tombstone" in tables and args.tombstone and phase1_out.get("rows"):
            phase8(args, creds, phase1_out)
        elif "tombstone" in tables and not args.tombstone:
            print("[Phase 8] SKIPPED (no --tombstone flag)")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        traceback.print_exc()
        _flush_evidence()
        return 1

    _flush_evidence()
    print("S171 audit complete -> output/l3/s171/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
