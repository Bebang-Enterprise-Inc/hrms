"""List files needing Opus arbitration.

Reads _manifest.jsonl + staging/*/summary.json. Prints per-file arbitration
specs (file_id, name, disagreement fields) so they can be dispatched to Agent
subagents for Opus to read the source PDF and return canonical values.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[2]
MD_ROOT = REPO_ROOT / "data" / "admin_markdown"
STAGING = MD_ROOT / "_staging"
MANIFEST = MD_ROOT / "_manifest.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=None, help="Only show files whose manifest ordinal is >= this*100 and < (this+1)*100")
    ap.add_argument("--since", type=str, default=None, help="Only show files with manifest ts >= this ISO timestamp")
    ap.add_argument("--missing-only", action="store_true", help="Only show files that still need arbitration (no arbitration.json yet)")
    args = ap.parse_args()

    manifest_recs: list[dict] = []
    if MANIFEST.exists():
        with MANIFEST.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    manifest_recs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    needing = []
    for i, rec in enumerate(manifest_recs):
        if rec.get("status") != "ok":
            continue
        if not rec.get("needs_arbitration"):
            continue
        if args.batch is not None:
            if not (args.batch * 100 <= i < (args.batch + 1) * 100):
                continue
        if args.since and (rec.get("ts") or "") < args.since:
            continue
        stage = STAGING / rec["file_id"]
        arb_file = stage / "arbitration.json"
        if args.missing_only and arb_file.exists():
            continue
        summary_file = stage / "summary.json"
        fields = rec.get("disagreement_fields") or []
        if summary_file.exists():
            try:
                s = json.loads(summary_file.read_text(encoding="utf-8"))
                fields = [d["field"] for d in (s.get("disagreements") or [])]
            except Exception:
                pass
        needing.append(
            {
                "file_id": rec["file_id"],
                "name": rec.get("name"),
                "stage_dir": str(stage),
                "fields": fields,
                "arb_exists": arb_file.exists(),
            }
        )

    for n in needing:
        print(json.dumps(n, ensure_ascii=False))
    print(f"\n# total_needing_arbitration: {len(needing)}", file=sys.stderr)


if __name__ == "__main__":
    main()
