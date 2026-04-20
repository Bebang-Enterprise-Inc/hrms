"""S208 fallback — Mistral-only extraction for the 38MB Grid Franchise PDF.

The full pipeline hung on this file (likely Gemini upload timeout on 38MB).
This script runs ONLY Mistral OCR and writes a minimal MD so the file lands
in the DD package. Opus arbitration (P3) can be run against mistral.md alone
with dd_ready=false in frontmatter until Sam re-reviews.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "admin_markdown_pipeline"))

# Load the main pipeline module for its helpers.
_pipeline_spec = importlib.util.spec_from_file_location(
    "_forensic_dd_pipeline",
    ROOT / "scripts" / "admin_markdown_pipeline" / "18_forensic_dd_pipeline.py",
)
assert _pipeline_spec and _pipeline_spec.loader
pipeline = importlib.util.module_from_spec(_pipeline_spec)
sys.modules["_forensic_dd_pipeline"] = pipeline
_pipeline_spec.loader.exec_module(pipeline)

DD_ROOT = ROOT / "CEO" / "Valuation" / "admin_compliance_dd"
pipeline.MD_ROOT = DD_ROOT
pipeline.STAGING = DD_ROOT / "_staging"
pipeline.MANIFEST = DD_ROOT / "_manifest.jsonl"
pipeline.ERRORS = DD_ROOT / "_errors.jsonl"

PICKS_JSON = ROOT / ".scratch" / "s208_picks.json"
TARGET_ID = "1W4-jGiRIgTGuki-iHQtqXeijXAwNJ33P"


def main() -> None:
    picks = json.loads(PICKS_JSON.read_text(encoding="utf-8"))
    match = [p for p in picks if p["file_id"] == TARGET_ID]
    if not match:
        print(f"ERROR: pick not found for {TARGET_ID}")
        sys.exit(1)
    p = match[0]

    row = {
        "file_id": p["file_id"],
        "name": p["name"],
        "dest_name": p["name"],
        "dest_path": f"{p['entity_code']}/{p['permit_code']}/{p['name']}",
        "entity_code": p["entity_code"],
        "permit_code": p["permit_code"],
        "full_path": p.get("path") or "",
        "md5": p.get("md5") or "",
        "modifiedTime": p.get("modifiedTime") or "",
        "size": p.get("size") or 0,
        "mime": "application/pdf",
    }

    stage_dir = pipeline.STAGING / p["file_id"]
    stage_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = stage_dir / "source.pdf"

    drive = pipeline._drive_client()
    pipeline._download_pdf(drive, p["file_id"], pdf_path)
    print(f"downloaded {pdf_path.stat().st_size/1e6:.1f}MB")

    from mistralai import Mistral

    mistral = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

    print("running Mistral OCR (may take 2-3 min on 38MB)...")
    t0 = time.perf_counter()
    mistral_out = pipeline.run_mistral_sync(pdf_path, mistral)
    print(f"Mistral done in {time.perf_counter()-t0:.1f}s")

    # Gemini skipped — empty dict
    gemini_out = {"structured": {}, "body_md": "", "meta": {"model": "SKIPPED_OVERSIZE"}}

    (stage_dir / "mistral.json").write_text(
        json.dumps(mistral_out.get("structured") or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (stage_dir / "mistral.md").write_text(mistral_out.get("body_md") or "", encoding="utf-8")
    (stage_dir / "gemini.json").write_text("{}", encoding="utf-8")
    (stage_dir / "gemini.md").write_text("", encoding="utf-8")

    # Synthesize disagreements: since gemini is empty, every non-empty mistral field is a "disagreement"
    m_struct = mistral_out.get("structured") or {}
    disagreements = [
        {"field": f, "mistral": m_struct.get(f), "gemini": None}
        for f in pipeline.CRITICAL_FIELDS
        if m_struct.get(f)
    ]

    summary = {
        "file_id": p["file_id"],
        "name": p["name"],
        "dest_path": row["dest_path"],
        "permit_code": p["permit_code"],
        "entity_code": p["entity_code"],
        "drive_url": f"https://drive.google.com/file/d/{p['file_id']}/view",
        "pdf_bytes": pdf_path.stat().st_size,
        "mistral_meta": mistral_out.get("meta"),
        "gemini_meta": {"model": "SKIPPED_OVERSIZE"},
        "disagreements": disagreements,
        "needs_arbitration": True,
        "oversize_fallback": True,
        "ts": pipeline._now_iso(),
    }
    (stage_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    registry = pipeline._load_registry()
    md_path = pipeline.write_final_md(row, mistral_out, gemini_out, disagreements, registry)
    print(f"wrote {md_path}")

    pipeline._append_jsonl(pipeline.MANIFEST, {
        "file_id": p["file_id"],
        "name": p["name"],
        "status": "ok",
        "md_path": str(md_path.relative_to(ROOT)),
        "staging": str(stage_dir.relative_to(ROOT)),
        "needs_arbitration": True,
        "disagreement_fields": [d["field"] for d in disagreements],
        "oversize_fallback": True,
        "ts": pipeline._now_iso(),
    })
    print("manifest appended")


if __name__ == "__main__":
    main()
