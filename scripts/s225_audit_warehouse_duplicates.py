"""S225 Phase 2 — Warehouse duplicate audit (read-only).

Identify EVERY warehouse duplicate across all warehouses (canonical 49 stores +
commissary + cold-storage hubs). Build a definitive audit report Sam reviews
before authorizing Phase 3 consolidation.

Detection rules (per plan + audit B-13):
  - Normalize: lowercase, NFKD-normalize, em/en-dash to hyphen, collapse spaces, strip.
  - Cluster by normalized name; clusters with >1 member = candidate duplicates.
  - Within each cluster:
      * canonical_winner: matches '<LABEL> - <ENTITY>' exactly with hyphens, no em-dash, no extra space
      * losers: the rest
  - INTERCOMPANY HARD-STOP (audit B-13): if winner.company != loser.company, flag
    cluster MANUAL_REVIEW_REQUIRED — INTERCOMPANY, exclude from APPROVED ALL.
  - Per-loser metrics: bin SKU count, total qty, list, in-flight transactions.
  - Cross-check Sentry for past 14d errors mentioning each loser by name.

Output:
  output/s225/verification/duplicate_warehouse_audit.json
  output/s225/verification/duplicate_warehouse_audit.md

Run from worktree:
    python scripts/s225_audit_warehouse_duplicates.py
"""
from __future__ import annotations
import base64
import json
import pathlib
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "output" / "s225" / "verification" / "duplicate_warehouse_audit.json"
OUT_MD = ROOT / "output" / "s225" / "verification" / "duplicate_warehouse_audit.md"
OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

INSTANCE_ID = "i-026b7477d27bd46d6"
SENTRY_ORG = "bebang-enterprise-inc"
SENTRY_PROJECT = "bei-hrms"
SENTRY_LOOKBACK_DAYS = 14

INNER_SCRIPT = r'''
import os, json
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files",
]:
    os.makedirs(d, exist_ok=True)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Pull every warehouse with bin metrics + in-flight transactions
all_wh = frappe.db.sql("""
    SELECT
      w.name,
      w.warehouse_name,
      w.company,
      w.disabled,
      w.is_group,
      w.parent_warehouse,
      (SELECT COALESCE(SUM(b.actual_qty), 0) FROM `tabBin` b WHERE b.warehouse = w.name) AS total_stock,
      (SELECT COUNT(*) FROM `tabBin` b WHERE b.warehouse = w.name AND b.actual_qty != 0) AS sku_nonzero,
      (SELECT COUNT(*) FROM `tabBin` b WHERE b.warehouse = w.name) AS sku_total
    FROM `tabWarehouse` w
""", as_dict=True)

# Per-warehouse list of items with non-zero stock (kept compact)
warehouse_items = {}
for row in all_wh:
    if row["sku_nonzero"] > 0:
        items = frappe.db.sql("""
            SELECT b.item_code, b.actual_qty, b.stock_uom
            FROM `tabBin` b
            WHERE b.warehouse = %s AND b.actual_qty != 0
            ORDER BY b.item_code
        """, (row["name"],), as_dict=True)
        warehouse_items[row["name"]] = items
    else:
        warehouse_items[row["name"]] = []

# In-flight transactions per warehouse (open MRs, draft SEs)
in_flight = {}
for row in all_wh:
    name = row["name"]
    open_mrs = frappe.db.sql("""
        SELECT mri.parent AS mr_name, mri.warehouse, mri.item_code, mri.qty, mri.stock_uom, mr.status
        FROM `tabMaterial Request Item` mri
        JOIN `tabMaterial Request` mr ON mr.name = mri.parent
        WHERE mri.warehouse = %s
          AND mr.docstatus = 1
          AND mr.status IN ('Pending', 'Partially Ordered', 'Submitted')
        LIMIT 25
    """, (name,), as_dict=True)
    open_ses = frappe.db.sql("""
        SELECT sed.parent AS se_name, sed.s_warehouse, sed.t_warehouse, sed.item_code, sed.qty
        FROM `tabStock Entry Detail` sed
        JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE (sed.s_warehouse = %s OR sed.t_warehouse = %s)
          AND se.docstatus = 0
        LIMIT 25
    """, (name, name), as_dict=True)
    in_flight[name] = {"open_mrs": open_mrs, "draft_ses": open_ses}

print(json.dumps({
    "all_wh": all_wh,
    "warehouse_items": warehouse_items,
    "in_flight": in_flight,
    "total": len(all_wh),
}, default=str))
'''


def normalize(s: str) -> str:
    """Lowercase, NFKD-normalize, em/en-dash to hyphen, collapse whitespace, strip."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = s.replace("–", "-").replace("—", "-")  # en/em dash
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def is_strict_canonical_form(name: str) -> bool:
    """Check if the warehouse name matches '<LABEL> - <ENTITY>' canonical pattern.

    - Plain ASCII hyphens (not em/en-dash)
    - No double spaces
    - No leading/trailing spaces
    - At least one ' - ' separator (label - entity)
    """
    if not name or name != name.strip():
        return False
    if "–" in name or "—" in name:
        return False
    if "  " in name:
        return False
    return " - " in name


def fetch_warehouses_via_ssm() -> dict:
    """Run the inner Frappe SQL via SSM and return the parsed JSON."""
    import boto3
    enc = base64.b64encode(INNER_SCRIPT.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s225_audit_wh.py",
        "docker cp /tmp/s225_audit_wh.py $BACKEND:/tmp/s225_audit_wh.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s225_audit_wh.py",
    ]
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["300"]},
    )
    cid = r["Command"]["CommandId"]
    print(f"audit-fetch CommandId: {cid}", flush=True)

    inv = None
    for _ in range(80):
        time.sleep(4)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            break

    if inv is None or inv["Status"] not in ("Success", "Failed"):
        raise RuntimeError(f"audit-fetch SSM did not complete: {inv['Status'] if inv else 'no-inv'}")

    stdout = inv.get("StandardOutputContent", "")
    # The last big JSON line is our payload
    for line in stdout.splitlines()[::-1]:
        s = line.strip()
        if s.startswith("{") and s.endswith("}"):
            return json.loads(s)
    raise RuntimeError(f"audit-fetch SSM returned no JSON. stderr: {inv.get('StandardErrorContent','')[:1000]}")


def fetch_sentry_errors_for_loser(loser_name: str, token: str) -> list[dict]:
    """Query Sentry past 14d for errors mentioning this warehouse name."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=SENTRY_LOOKBACK_DAYS)
    params = {
        "query": loser_name,
        "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 5,
    }
    url = f"https://sentry.io/api/0/projects/{SENTRY_ORG}/{SENTRY_PROJECT}/events/?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        if isinstance(data, list):
            return [{
                "id": ev.get("id"),
                "title": (ev.get("title") or "")[:200],
                "dateCreated": ev.get("dateCreated"),
                "level": ev.get("level"),
                "culprit": (ev.get("culprit") or "")[:200],
            } for ev in data[:5]]
    except Exception as e:
        return [{"error": f"sentry query failed: {e}"}]
    return []


def doppler_get(secret: str) -> str:
    return subprocess.check_output(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", secret, "--plain", "--project", "bei-erp", "--config", "dev"],
        text=True,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    ).strip()


def cluster_id_for(canonical_name: str) -> str:
    """Slugify canonical name into a stable cluster ID."""
    s = normalize(canonical_name)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return f"cluster-{s}"


def main() -> int:
    payload = fetch_warehouses_via_ssm()
    all_wh = payload["all_wh"]
    warehouse_items = payload["warehouse_items"]
    in_flight = payload["in_flight"]

    # Cluster by normalized docname AND by normalized warehouse_name (catch field-collisions too)
    docname_clusters: dict[str, list[dict]] = defaultdict(list)
    for w in all_wh:
        docname_clusters[normalize(w["name"])].append(w)

    # Also cluster by warehouse_name field separately
    whname_clusters: dict[str, list[dict]] = defaultdict(list)
    for w in all_wh:
        whname_key = normalize(w.get("warehouse_name") or "")
        if whname_key:
            whname_clusters[whname_key].append(w)

    # A cluster is suspicious if either the normalized docname or warehouse_name has >1 member.
    # Merge by docname-normalized for the primary report.
    suspicious_clusters: list[dict] = []

    for key, members in docname_clusters.items():
        if len(members) <= 1:
            continue

        # Pick canonical_winner: prefer strict-canonical-form, then highest stock, then alphabetical.
        scored = []
        for m in members:
            score = (
                int(is_strict_canonical_form(m["name"])),
                -int(m["disabled"]),  # active before disabled
                float(m["total_stock"] or 0),
                m["name"],
            )
            scored.append((score, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        winner = scored[0][1]
        losers = [m for m in members if m["name"] != winner["name"]]

        intercompany = any(loser["company"] != winner["company"] for loser in losers)

        cluster_entry = {
            "cluster_id": cluster_id_for(winner["name"]),
            "normalized_key": key,
            "winner": {
                "name": winner["name"],
                "warehouse_name": winner["warehouse_name"],
                "company": winner["company"],
                "disabled": int(winner["disabled"]),
                "is_group": int(winner["is_group"]),
                "total_stock": float(winner["total_stock"] or 0),
                "sku_nonzero": int(winner["sku_nonzero"]),
                "is_strict_canonical_form": is_strict_canonical_form(winner["name"]),
            },
            "losers": [],
            "intercompany": intercompany,
            "manual_review": False,
            "manual_review_reason": [],
            "members_count": len(members),
        }

        for loser in losers:
            loser_name = loser["name"]
            iflight = in_flight.get(loser_name, {"open_mrs": [], "draft_ses": []})
            cluster_entry["losers"].append({
                "name": loser_name,
                "warehouse_name": loser.get("warehouse_name"),
                "company": loser["company"],
                "disabled": int(loser["disabled"]),
                "is_group": int(loser["is_group"]),
                "total_stock": float(loser["total_stock"] or 0),
                "sku_nonzero": int(loser["sku_nonzero"]),
                "items": warehouse_items.get(loser_name, []),
                "open_mrs_count": len(iflight["open_mrs"]),
                "draft_ses_count": len(iflight["draft_ses"]),
                "open_mrs_sample": iflight["open_mrs"][:5],
                "draft_ses_sample": iflight["draft_ses"][:5],
                "is_strict_canonical_form": is_strict_canonical_form(loser_name),
            })

        # Manual review triggers (per plan task 5)
        if intercompany:
            cluster_entry["manual_review"] = True
            cluster_entry["manual_review_reason"].append("INTERCOMPANY (audit B-13: winner.company != loser.company)")

        if not is_strict_canonical_form(winner["name"]):
            cluster_entry["manual_review"] = True
            cluster_entry["manual_review_reason"].append("NO_STRICT_CANONICAL_WINNER (Sam picks)")

        if any(l["total_stock"] > winner["total_stock"] for l in cluster_entry["losers"]):
            cluster_entry["manual_review"] = True
            cluster_entry["manual_review_reason"].append("LOSER_HAS_MORE_STOCK (counterintuitive — Sam decides)")

        if any(l["is_group"] for l in cluster_entry["losers"]):
            cluster_entry["manual_review"] = True
            cluster_entry["manual_review_reason"].append("LOSER_IS_GROUP (groups have children — can't simply disable)")

        if any(l["open_mrs_count"] > 0 or l["draft_ses_count"] > 0 for l in cluster_entry["losers"]):
            cluster_entry["manual_review"] = True
            cluster_entry["manual_review_reason"].append("IN_FLIGHT_TRANSACTIONS_ON_LOSER")

        suspicious_clusters.append(cluster_entry)

    # Also surface warehouse_name field collisions where docname-normalized doesn't already cover it
    docname_clustered_names = {m["name"] for c in docname_clusters.values() for m in c if len(c) > 1}
    whname_only_clusters: list[dict] = []
    for key, members in whname_clusters.items():
        if len(members) <= 1:
            continue
        if all(m["name"] in docname_clustered_names for m in members):
            continue  # already in main clusters
        whname_only_clusters.append({
            "field": "warehouse_name",
            "normalized_key": key,
            "members": [{"name": m["name"], "warehouse_name": m["warehouse_name"], "company": m["company"]} for m in members],
        })

    # Sentry cross-check for each loser
    sentry_token = ""
    try:
        sentry_token = doppler_get("SENTRY_API_TOKEN")
    except Exception as e:
        print(f"WARN: could not load SENTRY_API_TOKEN from Doppler: {e}", flush=True)
    sentry_errors_per_loser: dict[str, list] = {}
    if sentry_token:
        for cluster in suspicious_clusters:
            for loser in cluster["losers"]:
                events = fetch_sentry_errors_for_loser(loser["name"], sentry_token)
                if events:
                    sentry_errors_per_loser[loser["name"]] = events

    # Aggregate stats
    total_stranded_skus = sum(
        loser["sku_nonzero"]
        for cluster in suspicious_clusters
        for loser in cluster["losers"]
    )
    total_stranded_stock = sum(
        loser["total_stock"]
        for cluster in suspicious_clusters
        for loser in cluster["losers"]
    )

    audit = {
        "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "total_warehouses_scanned": payload["total"],
        "total_clusters_with_duplicates": len(suspicious_clusters),
        "intercompany_clusters": sum(1 for c in suspicious_clusters if c["intercompany"]),
        "manual_review_required": sum(1 for c in suspicious_clusters if c["manual_review"]),
        "auto_apply_eligible": sum(1 for c in suspicious_clusters if not c["manual_review"]),
        "total_stranded_skus": int(total_stranded_skus),
        "total_stranded_stock_units": float(total_stranded_stock),
        "clusters": suspicious_clusters,
        "warehouse_name_field_collisions_extra": whname_only_clusters,
        "sentry_errors_per_loser": sentry_errors_per_loser,
    }
    OUT_JSON.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {OUT_JSON}", flush=True)

    # Build human-readable MD
    md_lines = []
    md_lines.append("# S225 Phase 2 — Warehouse Duplicate Audit Report")
    md_lines.append("")
    md_lines.append("**For Sam to review BEFORE authorizing Phase 3 consolidation.**")
    md_lines.append("")
    md_lines.append(f"- Total warehouses scanned: **{audit['total_warehouses_scanned']}**")
    md_lines.append(f"- Duplicate clusters found: **{audit['total_clusters_with_duplicates']}**")
    md_lines.append(f"- Intercompany clusters (audit B-13 — excluded from APPROVED ALL): **{audit['intercompany_clusters']}**")
    md_lines.append(f"- Manual-review-required clusters: **{audit['manual_review_required']}**")
    md_lines.append(f"- Auto-apply-eligible clusters (with `S225 Phase 3 APPROVED ALL`): **{audit['auto_apply_eligible']}**")
    md_lines.append(f"- Stranded SKUs across all duplicates: **{audit['total_stranded_skus']}**")
    md_lines.append(f"- Stranded stock units (sum of qty on losers): **{audit['total_stranded_stock_units']:.2f}**")
    md_lines.append("")
    md_lines.append("## Per-cluster decision required")
    md_lines.append("")
    md_lines.append("Sam, for each cluster below please confirm in a PR comment using one of these tokens:")
    md_lines.append("")
    md_lines.append("- `S225 Phase 3 APPROVED ALL` — apply all clusters in the audit (excluding INTERCOMPANY-flagged ones)")
    md_lines.append("- `S225 Phase 3 APPROVED: <cluster_id1>, <cluster_id2>` — apply only listed clusters")
    md_lines.append("- `S225 Phase 3 APPROVED INTERCOMPANY: <cluster_id>` — explicit intercompany authorization")
    md_lines.append("- `S225 Phase 3 SKIP: <cluster_id>` — skip listed clusters (with rationale)")
    md_lines.append("")
    md_lines.append("---")

    for cluster in suspicious_clusters:
        winner = cluster["winner"]
        md_lines.append(f"\n## `{cluster['cluster_id']}`")
        md_lines.append("")
        flags = []
        if cluster["intercompany"]:
            flags.append("**INTERCOMPANY**")
        if cluster["manual_review"]:
            flags.append("**MANUAL_REVIEW_REQUIRED**")
        if not flags:
            flags.append("auto-apply eligible")
        md_lines.append(f"Status: {' · '.join(flags)}")
        if cluster["manual_review_reason"]:
            md_lines.append("")
            md_lines.append("Manual-review reasons:")
            for r in cluster["manual_review_reason"]:
                md_lines.append(f"- {r}")
        md_lines.append("")
        md_lines.append("**Proposed Canonical Winner:**")
        md_lines.append("")
        md_lines.append(f"| Name | Company | Stock units | Non-zero SKUs | Disabled | Is group |")
        md_lines.append(f"|---|---|---|---|---|---|")
        md_lines.append(f"| `{winner['name']}` | `{winner['company']}` | {winner['total_stock']:.2f} | {winner['sku_nonzero']} | {winner['disabled']} | {winner['is_group']} |")
        md_lines.append("")
        md_lines.append("**Losers (to be DISABLED + stock migrated to winner):**")
        md_lines.append("")
        md_lines.append(f"| Name | Company | Stock units | Non-zero SKUs | Disabled | Is group | Open MRs | Draft SEs |")
        md_lines.append(f"|---|---|---|---|---|---|---|---|")
        for loser in cluster["losers"]:
            md_lines.append(f"| `{loser['name']}` | `{loser['company']}` | {loser['total_stock']:.2f} | {loser['sku_nonzero']} | {loser['disabled']} | {loser['is_group']} | {loser['open_mrs_count']} | {loser['draft_ses_count']} |")

        # Per-loser SKU breakdown if non-empty
        for loser in cluster["losers"]:
            if loser["items"]:
                md_lines.append(f"\n  Stock breakdown for loser `{loser['name']}`:")
                md_lines.append(f"\n  | Item code | Qty | UoM |")
                md_lines.append(f"  |---|---|---|")
                for item in loser["items"][:30]:
                    md_lines.append(f"  | {item['item_code']} | {item['actual_qty']} | {item.get('stock_uom', '')} |")
                if len(loser["items"]) > 30:
                    md_lines.append(f"  | ... +{len(loser['items']) - 30} more rows | | |")

            sentry_events = sentry_errors_per_loser.get(loser["name"], [])
            if sentry_events and not (len(sentry_events) == 1 and "error" in sentry_events[0]):
                md_lines.append(f"\n  Sentry errors past {SENTRY_LOOKBACK_DAYS}d mentioning `{loser['name']}`:")
                for ev in sentry_events:
                    md_lines.append(f"  - [{ev.get('dateCreated')}] {ev.get('title')}")

    if whname_only_clusters:
        md_lines.append("\n## Warehouse_name field collisions (separate detection)")
        md_lines.append("")
        md_lines.append("These warehouses have the same `warehouse_name` field but distinct docnames.")
        md_lines.append("Not necessarily duplicates — review each.")
        md_lines.append("")
        for c in whname_only_clusters:
            md_lines.append(f"- key={c['normalized_key']!r}: " + ", ".join(f"`{m['name']}`" for m in c["members"]))

    OUT_MD.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Wrote {OUT_MD}", flush=True)

    if audit["total_clusters_with_duplicates"] == 0:
        print("\nWARN: no duplicates found. The 3MD em-dash duplicate is documented in S223 Sentry — "
              "if it isn't here, the production data may already be cleaned. Verify before proceeding.", flush=True)
        return 2

    print(f"\nPASS: audit complete — {audit['total_clusters_with_duplicates']} clusters, "
          f"{audit['auto_apply_eligible']} auto-apply eligible, "
          f"{audit['manual_review_required']} need manual review.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
