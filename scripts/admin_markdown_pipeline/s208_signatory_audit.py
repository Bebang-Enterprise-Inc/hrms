"""Check signatories on every FA/MA/JV/Contract in the DD package.

Goal: forensic verification that contracts are signed by both parties,
including BEI CEO (Sam Karazi).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
DD = ROOT / "CEO" / "Valuation" / "admin_compliance_dd"

CONTRACT_TYPES = {"FRANCHISE_AGREEMENT", "JV_AGREEMENT", "CONTRACT"}
BEI_CEO_TERMS = ["sam karazi", "samer karazi", "karazi"]
CONTRACT_KEYWORDS = ["franchise", "jv", "management agreement",
                     "joint venture", "memorandum", "agreement", "contract"]

_field_re = {
    "document_type": re.compile(r"^document_type:\s?(.*)$", re.MULTILINE),
    "ai_label": re.compile(r"^ai_label:\s?(.*)$", re.MULTILINE),
    "canonical_business_name": re.compile(r"^canonical_business_name:\s?(.*)$", re.MULTILINE),
    "entity_code": re.compile(r"^entity_code:\s?(.*)$", re.MULTILINE),
}
_sigs_re = re.compile(r"canonical_signatories:\s*(\[.*?\])(?=\n[a-z_]+:|\n---)", re.DOTALL)


def _unquote(s: str) -> str:
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    return s


def scan() -> list[dict]:
    out: list[dict] = []
    for md in DD.rglob("*.md"):
        rel = md.relative_to(DD)
        if rel.parts and rel.parts[0].startswith("_"):
            continue
        if md.name.startswith("_"):
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except Exception:
            continue
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        fm = parts[1]
        fields = {}
        for k, rx in _field_re.items():
            m = rx.search(fm)
            fields[k] = _unquote(m.group(1)) if m else ""
        dt = fields["document_type"]
        if dt not in CONTRACT_TYPES:
            continue
        name = md.name.lower()
        if not any(k in name for k in CONTRACT_KEYWORDS):
            continue

        sigs_m = _sigs_re.search(fm)
        sigs: list = []
        if sigs_m:
            raw = sigs_m.group(1)
            try:
                sigs = json.loads(raw)
            except Exception:
                sigs = []
        sig_names = [
            (s.get("name", "") if isinstance(s, dict) else str(s))
            for s in sigs
        ]
        sig_titles = [
            (s.get("title", "") if isinstance(s, dict) else "")
            for s in sigs
        ]
        out.append({
            "path": str(rel),
            "doc_type": dt,
            "entity_code": fields["entity_code"],
            "ai_label": fields["ai_label"],
            "sig_names": sig_names,
            "sig_titles": sig_titles,
        })
    return out


def main() -> None:
    agreements = scan()
    print(f"Total FA/MA/JV/Contract docs: {len(agreements)}")
    print()

    has_bei = 0
    missing_bei = []
    zero_sigs = []
    single_sig = []
    for a in agreements:
        sigs_lower = [s.lower() for s in a["sig_names"]]
        has_ceo = any(any(t in s for t in BEI_CEO_TERMS) for s in sigs_lower)
        if has_ceo:
            has_bei += 1
        else:
            missing_bei.append(a)
        if not a["sig_names"]:
            zero_sigs.append(a)
        elif len(a["sig_names"]) == 1:
            single_sig.append(a)

    print(f"Docs with Sam/Samer Karazi (BEI CEO) in signatories: {has_bei}/{len(agreements)}")
    print(f"Docs with ZERO signatories captured: {len(zero_sigs)}")
    print(f"Docs with only 1 signatory: {len(single_sig)}")
    print()

    print("=== Docs MISSING BEI CEO signature ===")
    for a in missing_bei:
        print(f"  [{a['doc_type']}] entity={a['entity_code']}")
        print(f"    path: {a['path']}")
        print(f"    label: {a['ai_label'][:80]}")
        print(f"    sigs({len(a['sig_names'])}): {list(zip(a['sig_names'], a['sig_titles']))[:6]}")
        print()

    print("=== Docs with ZERO signatories (OCR failed or blank template) ===")
    for a in zero_sigs:
        print(f"  [{a['doc_type']}] {a['path']}  label={a['ai_label'][:60]}")

    print()
    print("=== Docs with only 1 signatory (suspicious — likely not fully executed) ===")
    for a in single_sig:
        print(f"  [{a['doc_type']}] {a['path']}")
        print(f"    sig: {a['sig_names']}  title: {a['sig_titles']}")


if __name__ == "__main__":
    main()
