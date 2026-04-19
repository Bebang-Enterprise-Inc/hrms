"""Build _INDEX.md + _MASTER_MANIFEST.csv from every MD file in data/admin_markdown/."""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[2]
MD_ROOT = REPO_ROOT / "data" / "admin_markdown"
INDEX_MD = MD_ROOT / "_INDEX.md"
MASTER_CSV = MD_ROOT / "_MASTER_MANIFEST.csv"


def _parse_yaml_value(raw: str) -> Any:
    raw = raw.strip()
    if raw in {"", "null", "~"}:
        return None
    if raw in {"true", "True"}:
        return True
    if raw in {"false", "False"}:
        return False
    if raw.startswith(('"', "[", "{")):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw.strip('"')
    try:
        return float(raw) if "." in raw else int(raw)
    except ValueError:
        return raw


def _parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    out: dict = {}
    for line in parts[1].splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_]+):\s?(.*)$", line)
        if m:
            out[m.group(1)] = _parse_yaml_value(m.group(2))
    return out


def main():
    rows: list[dict] = []
    for p in sorted(MD_ROOT.rglob("*.md")):
        if p.name.startswith("_") or "_staging" in p.parts or "_validation" in p.parts or "_pages" in p.parts:
            continue
        try:
            fm = _parse_frontmatter(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not fm:
            continue
        fm["_md_relative"] = str(p.relative_to(MD_ROOT)).replace("\\", "/")
        rows.append(fm)

    preferred = [
        "_md_relative", "entity_code", "entity_legal_name", "entity_store_mapping",
        "permit_code", "document_type",
        "canonical_business_name", "canonical_trade_name", "canonical_permit_number",
        "canonical_tin", "canonical_ocn", "canonical_psic_code",
        "canonical_issuing_authority", "canonical_issue_date", "canonical_expiry_date",
        "canonical_location_address", "canonical_registered_address", "canonical_signatories",
        "validation_method", "disagreements", "dd_ready",
        "mistral_document_type", "mistral_tin", "mistral_ocn", "mistral_signatories",
        "gemini_pro_document_type", "gemini_pro_tin", "gemini_pro_ocn", "gemini_pro_signatories",
        "opus_arbitration_reasoning", "opus_source_of_truth",
        "source_drive_id", "source_drive_url", "source_path", "source_md5",
        "source_modified", "size_bytes",
        "extraction_date", "extraction_models", "extraction_cost_usd",
    ]
    all_keys: list[str] = []
    seen: set[str] = set()
    for k in preferred:
        all_keys.append(k); seen.add(k)
    for r in rows:
        for k in r.keys():
            if k not in seen:
                all_keys.append(k); seen.add(k)

    def _csv_val(v):
        if v is None:
            return ""
        if isinstance(v, (list, dict)):
            return json.dumps(v, ensure_ascii=False)
        return v

    with MASTER_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=all_keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: _csv_val(r.get(k)) for k in all_keys})
    print(f"wrote {MASTER_CSV.relative_to(REPO_ROOT)} ({len(rows)} rows)")

    rows.sort(key=lambda r: (str(r.get("entity_code") or ""), str(r.get("permit_code") or ""), str(r.get("_md_relative") or "")))
    lines = [
        "# BEI Admin Compliance – Master Index",
        "",
        f"Total files indexed: **{len(rows)}**.",
        "",
    ]
    dd_count = sum(1 for r in rows if r.get("dd_ready") is True)
    arb_pending = sum(1 for r in rows if r.get("validation_method") == "opus_arbitrated_pending")
    arb_done = sum(1 for r in rows if r.get("validation_method") == "opus_arbitrated")
    dual = sum(1 for r in rows if r.get("validation_method") == "dual_match")
    lines.append(f"- DD ready: **{dd_count}** / {len(rows)}")
    lines.append(f"- Validation: {dual} dual_match, {arb_done} opus_arbitrated, {arb_pending} pending arbitration")
    lines.append("")

    by_entity = defaultdict(list)
    for r in rows:
        by_entity[str(r.get("entity_code") or "UNKNOWN")].append(r)
    for entity in sorted(by_entity.keys()):
        ent_rows = by_entity[entity]
        legal = ent_rows[0].get("entity_legal_name", "")
        store = ent_rows[0].get("entity_store_mapping", "")
        lines.append(f"## {entity} — {legal}" + (f"  *(store: {store})*" if store else ""))
        lines.append("")
        lines.append("| Permit | Document | Issue | Expiry | DD | Validation | Drive |")
        lines.append("|---|---|---|---|---|---|---|")
        ent_rows.sort(key=lambda r: (str(r.get("permit_code") or ""), str(r.get("canonical_expiry_date") or "")))
        for r in ent_rows:
            permit = r.get("permit_code") or ""
            dtype = r.get("document_type") or ""
            issue = r.get("canonical_issue_date") or ""
            expiry = r.get("canonical_expiry_date") or ""
            dd = "✅" if r.get("dd_ready") is True else "⚠️"
            val = r.get("validation_method") or ""
            url = r.get("source_drive_url") or ""
            md_rel = r.get("_md_relative") or ""
            drive_md = f"[Drive]({url})" if url else ""
            file_md = f"[{Path(md_rel).name}]({md_rel})" if md_rel else ""
            lines.append(f"| {permit} | {file_md} – {dtype} | {issue} | {expiry} | {dd} | {val} | {drive_md} |")
        lines.append("")

    INDEX_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {INDEX_MD.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
