"""Build one _ENTITY_SUMMARY.md per entity folder."""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[2]
MD_ROOT = REPO_ROOT / "data" / "admin_markdown"

REQUIRED_PERMIT_TYPES = ["BIR_2303", "SEC_AOI", "SEC_BYLAWS", "SEC_GIS", "BP", "BARANGAY_CLEARANCE", "FSIC", "SANITARY", "DOLE"]


def _parse_yaml_value(raw: str):
    raw = raw.strip()
    if raw in {"", "null", "~"}: return None
    if raw.startswith(('"', "[", "{")):
        try: return json.loads(raw)
        except json.JSONDecodeError: return raw.strip('"')
    try: return float(raw) if "." in raw else int(raw)
    except ValueError: return raw


def _parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"): return {}
    parts = text.split("---", 2)
    if len(parts) < 3: return {}
    out: dict = {}
    for line in parts[1].splitlines():
        if not line.strip() or line.startswith("#"): continue
        m = re.match(r"^([A-Za-z0-9_]+):\s?(.*)$", line)
        if m: out[m.group(1)] = _parse_yaml_value(m.group(2))
    return out


def _parse_date(s):
    if not s: return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"):
        try: return datetime.strptime(s, fmt).date()
        except ValueError: continue
    try: return date.fromisoformat(s[:10])
    except ValueError: return None


def build_summary_for_entity(entity_dir: Path) -> None:
    docs: list[dict] = []
    for p in entity_dir.rglob("*.md"):
        if p.name.startswith("_"): continue
        fm = _parse_frontmatter(p.read_text(encoding="utf-8"))
        if not fm: continue
        fm["_path"] = str(p.relative_to(MD_ROOT)).replace("\\", "/")
        docs.append(fm)
    if not docs: return

    entity_code = entity_dir.name
    legal = docs[0].get("entity_legal_name") or entity_code
    store = docs[0].get("entity_store_mapping") or ""

    bir = next((d for d in docs if d.get("permit_code") == "BIR_2303"), None)
    aoi = next((d for d in docs if d.get("permit_code") == "SEC_AOI"), None)

    lines: list[str] = [
        f"# {entity_code} — {legal}", "",
        f"*Store mapping:* **{store or '(none)'}**", "",
        "## Identity", "",
        f"- Business name: {bir.get('canonical_business_name') if bir else (aoi.get('canonical_business_name') if aoi else '')}",
        f"- TIN: {bir.get('canonical_tin') if bir else ''}",
        f"- OCN: {bir.get('canonical_ocn') if bir else ''}",
        f"- PSIC: {bir.get('canonical_psic_code') if bir else ''}",
        f"- Registered address: {bir.get('canonical_registered_address') if bir else (aoi.get('canonical_registered_address') if aoi else '')}",
        "",
    ]
    by_permit = defaultdict(list)
    for d in docs:
        by_permit[d.get("permit_code") or "UNKNOWN"].append(d)

    lines.extend(["## Permits On File", "", "| Permit | Count | Earliest Expiry | Latest Expiry | DD |", "|---|---|---|---|---|"])
    for permit in sorted(by_permit.keys()):
        entries = by_permit[permit]
        expiries = [e for e in (_parse_date(str(e.get("canonical_expiry_date") or "")) for e in entries) if e]
        earliest = min(expiries).isoformat() if expiries else "—"
        latest = max(expiries).isoformat() if expiries else "—"
        dd_ok = all(e.get("dd_ready") for e in entries)
        lines.append(f"| {permit} | {len(entries)} | {earliest} | {latest} | {'✅' if dd_ok else '⚠️'} |")
    lines.append("")

    missing = [p for p in REQUIRED_PERMIT_TYPES if p not in by_permit]
    if missing:
        lines.extend(["## Missing Required Permit Types", ""])
        for m in missing: lines.append(f"- **{m}**")
        lines.append("")

    sig_set: dict[str, str] = {}
    for d in docs:
        sigs = d.get("canonical_signatories") or []
        if isinstance(sigs, list):
            for s in sigs:
                if isinstance(s, dict) and s.get("name"):
                    sig_set.setdefault(s["name"].upper(), s.get("title", "") or "")
    if sig_set:
        lines.extend(["## Signatories", ""])
        for name, title in sorted(sig_set.items()):
            lines.append(f"- **{name}**" + (f" — {title}" if title else ""))
        lines.append("")

    lines.extend(["## Files", "", "| Permit | Document | Issue | Expiry | DD |", "|---|---|---|---|---|"])
    for d in sorted(docs, key=lambda x: (x.get("permit_code") or "", x.get("_path") or "")):
        expiry = d.get("canonical_expiry_date") or ""
        issue = d.get("canonical_issue_date") or ""
        dd = "✅" if d.get("dd_ready") is True else "⚠️"
        rel = d.get("_path") or ""
        rel_from_entity = str(Path(rel).relative_to(entity_code)).replace("\\", "/") if rel.startswith(entity_code) else rel
        lines.append(f"| {d.get('permit_code','')} | [{Path(rel).name}]({rel_from_entity}) — {d.get('document_type','')} | {issue} | {expiry} | {dd} |")

    out_path = entity_dir / "_ENTITY_SUMMARY.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  wrote {out_path.relative_to(MD_ROOT)}")


def main():
    for entity_dir in sorted(MD_ROOT.iterdir()):
        if not entity_dir.is_dir() or entity_dir.name.startswith("_"): continue
        print(f"==> {entity_dir.name}")
        build_summary_for_entity(entity_dir)


if __name__ == "__main__":
    main()
