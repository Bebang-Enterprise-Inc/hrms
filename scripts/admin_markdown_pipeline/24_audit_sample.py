"""Pick 30-file stratified sample for blind spot-check.

Stratifies by document_type to ensure coverage across:
- BIR_2303, SEC_AOI, SEC_BYLAWS, MAYORS_PERMIT, SEC_COI, FSIC, LEASE/CONTRACT, other
- Mix of opus_arbitrated and dual_match outcomes

Writes .scratch/audit_sample.json with 30 file entries.
"""
from __future__ import annotations
import json, random, re, sys
from collections import defaultdict
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
MD_ROOT = ROOT / "data" / "admin_markdown"
STAGING = MD_ROOT / "_staging"
MANIFEST = MD_ROOT / "_manifest.jsonl"
OUT = ROOT / ".scratch" / "audit_sample.json"

# Critical fields to blind-extract per file
AUDIT_FIELDS = [
    "document_type",
    "canonical_permit_number",
    "canonical_tin",
    "canonical_issue_date",
    "canonical_expiry_date",
    "canonical_issuing_authority",
    "canonical_signatories",
]

TARGET_TYPES = {
    "BIR_2303": 6,
    "SEC_AOI": 3,
    "SEC_BYLAWS": 3,
    "SEC_COI": 3,
    "MAYORS_PERMIT": 3,
    "FSIC": 2,
    "SANITARY": 2,
    "LEASE": 2,
    "CONTRACT": 2,
    "INSURANCE": 2,
    "OTHER": 2,
}


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    out = {}
    for line in parts[1].splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_]+):\s?(.*)$", line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        elif v in {"null", "~", ""}:
            v = None
        out[k] = v
    return out


def main() -> None:
    rng = random.Random(42)
    file_map: dict[str, dict] = {}
    with MANIFEST.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("status") != "ok":
                continue
            fid = r.get("file_id")
            if not fid or fid in file_map:
                continue
            md_rel = r.get("md_path")
            if not md_rel:
                continue
            md_path = ROOT / md_rel
            if not md_path.exists():
                continue
            fm = parse_frontmatter(md_path.read_text(encoding="utf-8"))
            if not fm:
                continue
            doc_type = fm.get("document_type") or "OTHER"
            file_map[fid] = {
                "file_id": fid,
                "name": r.get("name"),
                "md_path": md_rel,
                "staging": str(STAGING / fid),
                "document_type": doc_type,
                "validation_method": fm.get("validation_method"),
                "canonical": {k: fm.get(k) for k in AUDIT_FIELDS if k in fm or f"canonical_{k}" in fm},
            }

    by_type: dict[str, list[dict]] = defaultdict(list)
    for f in file_map.values():
        dt = f["document_type"] if f["document_type"] in TARGET_TYPES else "OTHER"
        by_type[dt].append(f)

    picked: list[dict] = []
    for dt, want in TARGET_TYPES.items():
        pool = by_type.get(dt, [])
        if not pool:
            continue
        rng.shuffle(pool)
        picked.extend(pool[:want])

    picked = picked[:30]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(picked, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({len(picked)} files)")
    print("type counts:")
    cnt: dict[str, int] = defaultdict(int)
    for f in picked:
        cnt[f["document_type"]] += 1
    for dt, n in sorted(cnt.items()):
        print(f"  {dt:20}  {n}")


if __name__ == "__main__":
    main()
