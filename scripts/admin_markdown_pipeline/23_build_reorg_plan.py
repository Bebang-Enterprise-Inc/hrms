"""Build _REORGANIZATION_PLAN.md + _DRIVE_RENAME_PROPOSALS.csv (DRY RUN only)."""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEDUPE_CSV = REPO_ROOT / "data" / "admin_drive_audit" / "03_dedupe_plan.csv"
MD_ROOT = REPO_ROOT / "data" / "admin_markdown"
OUT_MD = MD_ROOT / "_REORGANIZATION_PLAN.md"
OUT_CSV = MD_ROOT / "_DRIVE_RENAME_PROPOSALS.csv"


def main():
    rows = []
    with DEDUPE_CSV.open("r", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh): rows.append(row)
    winners = [r for r in rows if r.get("is_winner") == "1"]
    losers = [r for r in rows if r.get("is_winner") != "1"]
    reclaim_bytes = sum(int(r.get("size") or 0) for r in losers if (r.get("size") or "0").isdigit())
    actions = Counter(r.get("dedup_action") or "" for r in rows)
    by_entity = defaultdict(list)
    for r in winners: by_entity[r.get("entity_code") or "UNKNOWN"].append(r)

    cols = ["file_id", "name", "full_path", "entity_code", "permit_code", "dest_path", "dest_name", "dedup_action", "cluster_id", "cluster_tier", "size", "md5", "drive_url"]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({
                "file_id": r.get("file_id"), "name": r.get("name"), "full_path": r.get("full_path"),
                "entity_code": r.get("entity_code"), "permit_code": r.get("permit_code"),
                "dest_path": r.get("dest_path"), "dest_name": r.get("dest_name"),
                "dedup_action": r.get("dedup_action"), "cluster_id": r.get("cluster_id"),
                "cluster_tier": r.get("cluster_tier"), "size": r.get("size"), "md5": r.get("md5"),
                "drive_url": f"https://drive.google.com/file/d/{r.get('file_id')}/view",
            })
    print(f"wrote {OUT_CSV.relative_to(REPO_ROOT)} ({len(rows)} rows)")

    lines = [
        "# BEI Admin Drive Reorganization Plan (DRY RUN)", "",
        "**THIS IS A DRY-RUN ONLY. NO DRIVE CHANGES ARE MADE.** Requires Sam's explicit approval before execution.", "",
        "## Summary", "",
        f"- Total files enumerated: **{len(rows)}**",
        f"- Winners (to migrate / keep): **{len(winners)}**",
        f"- Losers (duplicates to archive): **{len(losers)}**",
        f"- Reclaimable duplicate bytes: **{reclaim_bytes:,} bytes (~{reclaim_bytes / (1024*1024):.1f} MB)**",
        "",
        "### Action breakdown", "", "| Action | Count |", "|---|---|",
    ]
    for action, n in actions.most_common(): lines.append(f"| {action or '(blank)'} | {n} |")
    lines.append("")

    lines.extend(["## Per-entity migrations", "", "| Entity | Files (winners) | Files (duplicates) |", "|---|---|---|"])
    loser_by_entity = defaultdict(int)
    for r in losers: loser_by_entity[r.get("entity_code") or "UNKNOWN"] += 1
    for entity in sorted(by_entity.keys()):
        lines.append(f"| {entity} | {len(by_entity[entity])} | {loser_by_entity.get(entity, 0)} |")
    lines.append("")

    lines.extend([
        "## What execution would do", "",
        "1. For every winner: move or copy to `dest_path` inside Admin - Canonical drive, renaming to `dest_name`.",
        "2. For every loser: move to an `_archive_dup/` folder in the source drive (NOT deleted — audit trail).",
        "3. Write a CSV audit log of every Drive operation.", "",
        "**Not included in this run**: the script that performs the Drive operations. That lives separately and will be built only after Sam reviews and approves this plan.", "",
    ])

    lines.extend(["## Sample renames (first 20)", "", "| Current path | → | New path |", "|---|---|---|"])
    for r in winners[:20]: lines.append(f"| {r.get('full_path') or ''} | → | {r.get('dest_path') or ''} |")
    lines.append("")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT_MD.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
