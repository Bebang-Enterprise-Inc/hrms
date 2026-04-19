"""Build reclassification batches — files with UNKNOWN permit_code or OTHER doc_type.

Writes .scratch/reclass_batches.jsonl with one line per batch (10 files each).
Each file entry includes MD path + body snippet (for agent to classify without re-reading PDF).
"""
from __future__ import annotations
import csv, json, re, sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
DD = ROOT / "CEO" / "Valuation" / "admin_compliance_dd"
MANIFEST = DD / "_MASTER_MANIFEST.csv"
OUT = ROOT / ".scratch" / "reclass_batches.jsonl"
BATCH = 10


def load_md(p: Path) -> tuple[dict, str]:
    text = p.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_text, body = parts[1], parts[2]
    fm = {}
    for line in fm_text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_]+):\s?(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm, body


def main() -> None:
    targets = []
    with MANIFEST.open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            pc = (r.get("permit_code") or "").upper()
            dt = (r.get("document_type") or "").upper()
            needs = pc in {"UNKNOWN", ""} or dt in {"OTHER", "UNKNOWN", "", "CERT"}
            if not needs:
                continue
            md_rel = r.get("_md_relative")
            if not md_rel:
                continue
            md_path = DD / md_rel
            if not md_path.exists():
                continue
            _, body = load_md(md_path)
            snippet = re.sub(r"\s+", " ", body).strip()[:1200]
            targets.append({
                "md_rel": md_rel,
                "entity_code": r.get("entity_code", ""),
                "current_doc_type": r.get("document_type", ""),
                "current_permit_code": r.get("permit_code", ""),
                "canonical_business_name": r.get("canonical_business_name", "") or "",
                "canonical_trade_name": r.get("canonical_trade_name", "") or "",
                "canonical_issue_date": r.get("canonical_issue_date", "") or "",
                "canonical_expiry_date": r.get("canonical_expiry_date", "") or "",
                "body_snippet": snippet,
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Write each batch as one line (pre-chunked)
    with OUT.open("w", encoding="utf-8") as fh:
        for i in range(0, len(targets), BATCH):
            fh.write(json.dumps({"batch_num": i // BATCH + 1, "files": targets[i:i + BATCH]}, ensure_ascii=False) + "\n")
    print(f"wrote {OUT} ({len(targets)} files in {(len(targets) + BATCH - 1) // BATCH} batches of {BATCH})")


if __name__ == "__main__":
    main()
