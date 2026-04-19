"""S208 — Run the forensic DD OCR pipeline on the 86 BD-drive picks.

Reuses functions from `18_forensic_dd_pipeline.py` (Mistral + Gemini + download)
but writes output under `CEO/Valuation/admin_compliance_dd/` instead of
`data/admin_markdown/`, and sources rows from `.scratch/s208_picks.json`
(file_ids live in the Business Development drive, not the Admin drive dedupe).

Usage:
    doppler run --project bei-erp --config dev -- \
        python -u scripts/admin_markdown_pipeline/34_s208_run_pipeline.py \
        --concurrency 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "admin_markdown_pipeline"))

# Import original pipeline module and re-point its constants.
import importlib.util

_pipeline_spec = importlib.util.spec_from_file_location(
    "_forensic_dd_pipeline",
    ROOT / "scripts" / "admin_markdown_pipeline" / "18_forensic_dd_pipeline.py",
)
assert _pipeline_spec and _pipeline_spec.loader
pipeline = importlib.util.module_from_spec(_pipeline_spec)
sys.modules["_forensic_dd_pipeline"] = pipeline  # dataclass decorator needs this
_pipeline_spec.loader.exec_module(pipeline)

# Redirect output paths to CEO/Valuation/admin_compliance_dd/
DD_ROOT = ROOT / "CEO" / "Valuation" / "admin_compliance_dd"
pipeline.MD_ROOT = DD_ROOT
pipeline.STAGING = DD_ROOT / "_staging"
pipeline.MANIFEST = DD_ROOT / "_manifest.jsonl"
pipeline.ERRORS = DD_ROOT / "_errors.jsonl"
pipeline.ARB_LOG = DD_ROOT / "_arbitration_log.jsonl"

PICKS_JSON = ROOT / ".scratch" / "s208_picks.json"


def _build_rows_from_picks(picks: list[dict]) -> list[dict]:
    """Convert S208 pick entries → pipeline row dicts."""
    rows: list[dict] = []
    for p in picks:
        entity = p["entity_code"]
        permit = p["permit_code"]
        fid = p["file_id"]
        name = p["name"]
        # Destination filename — the pipeline uses Path(dest_name).stem.
        # Keep original PDF name so dest_name.stem matches the source filename.
        rows.append({
            "file_id": fid,
            "name": name,
            "dest_name": name,
            "dest_path": f"{entity}/{permit}/{name}",
            "entity_code": entity,
            "permit_code": permit,
            "full_path": p.get("path") or "",
            "md5": p.get("md5") or "",
            "modifiedTime": p.get("modifiedTime") or "",
            "size": p.get("size") or 0,
            "mime": "application/pdf",
            "is_winner": "1",
        })
    return rows


async def main_async(args) -> None:
    if not PICKS_JSON.exists():
        print(f"ERROR: missing {PICKS_JSON}. Run 33_s208_prep_picks.py first.")
        sys.exit(1)

    picks = json.loads(PICKS_JSON.read_text(encoding="utf-8"))
    rows = _build_rows_from_picks(picks)
    if args.limit:
        rows = rows[: args.limit]
    if args.skip:
        rows = rows[args.skip:]
    print(f"loaded {len(rows)} picks from {PICKS_JSON}")

    # Resume — read existing manifest, skip file_ids already processed OK.
    done: set[str] = set()
    if not args.force and pipeline.MANIFEST.exists():
        with pipeline.MANIFEST.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("status") == "ok" and rec.get("file_id"):
                    done.add(rec["file_id"])
    if done:
        before = len(rows)
        rows = [r for r in rows if r["file_id"] not in done]
        print(f"skip {before - len(rows)} already-processed (use --force to redo)")

    if not rows:
        print("nothing to do after resume filter")
        return

    print(f"processing {len(rows)} files @ {args.concurrency}x concurrency")
    print(f"output root: {DD_ROOT}")

    drive = pipeline._drive_client()
    from mistralai import Mistral

    mistral = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
    gemini = pipeline._genai_client()
    registry = pipeline._load_registry()

    ctx = pipeline.PipelineCtx(
        drive=drive,
        mistral=mistral,
        gemini=gemini,
        registry=registry,
        force=args.force,
    )

    sem = asyncio.Semaphore(args.concurrency)
    t0 = time.perf_counter()
    results = await asyncio.gather(*(pipeline.process_row(ctx, r, sem) for r in rows))
    elapsed = time.perf_counter() - t0

    ok = [r for r in results if r.get("status") == "ok"]
    err = [r for r in results if r.get("status") != "ok"]
    arb = [r for r in ok if r.get("needs_arbitration")]
    print(f"\n===== S208 DONE {elapsed:.1f}s =====")
    print(f"ok                : {len(ok)}")
    print(f"errors            : {len(err)}")
    print(f"needs arbitration : {len(arb)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
