"""Compare blind audit extraction vs canonical values. Score accuracy."""
from __future__ import annotations
import csv, json, re, sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
MD_ROOT = ROOT / "data" / "admin_markdown"
STAGING = MD_ROOT / "_staging"
SAMPLE = ROOT / ".scratch" / "audit_sample.json"
REPORT_CSV = MD_ROOT / "_AUDIT_REPORT.csv"
REPORT_MD = MD_ROOT / "_AUDIT_REPORT.md"

CMP_FIELDS = [
    ("document_type", "document_type"),
    ("permit_number", "canonical_permit_number"),
    ("tin", "canonical_tin"),
    ("issue_date", "canonical_issue_date"),
    ("expiry_date", "canonical_expiry_date"),
    ("issuing_authority", "canonical_issuing_authority"),
    ("signatories", "canonical_signatories"),
]


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
        if v in {"null", "~", ""}:
            v = None
        elif v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        elif v.startswith("[") or v.startswith("{"):
            try:
                v = json.loads(v)
            except Exception:
                pass
        out[k] = v
    return out


def norm_str(s) -> str:
    if s is None:
        return ""
    s = str(s).strip().upper()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^A-Z0-9 /.-]", "", s)
    return s


def norm_date(s) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    return m.group(0) if m else s[:10]


def norm_sig_names(v) -> set[str]:
    if v is None:
        return set()
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            return {norm_str(v)}
    if isinstance(v, list):
        names = set()
        for item in v:
            if isinstance(item, dict):
                n = item.get("name", "")
            else:
                n = str(item)
            n = norm_str(n)
            if n:
                names.add(n)
        return names
    return {norm_str(v)}


def compare(field: str, blind, canonical) -> tuple[str, str]:
    """Return (verdict, note). verdict = MATCH | PARTIAL | MISMATCH | BOTH_NULL | NULL_DIFF"""
    if field in {"issue_date", "expiry_date"}:
        b, c = norm_date(blind), norm_date(canonical)
        if not b and not c:
            return "BOTH_NULL", ""
        if b == c:
            return "MATCH", ""
        if not b or not c:
            return "NULL_DIFF", f"blind={b!r} canonical={c!r}"
        return "MISMATCH", f"blind={b!r} canonical={c!r}"
    if field == "signatories":
        b, c = norm_sig_names(blind), norm_sig_names(canonical)
        if not b and not c:
            return "BOTH_NULL", ""
        if b == c:
            return "MATCH", f"n={len(c)}"
        if b.issubset(c) or c.issubset(b):
            overlap = b & c
            extra_c = c - b
            extra_b = b - c
            extras = []
            if extra_c:
                extras.append(f"canonical_extra={sorted(extra_c)[:3]}")
            if extra_b:
                extras.append(f"blind_extra={sorted(extra_b)[:3]}")
            return "PARTIAL", f"overlap={len(overlap)}/{max(len(b), len(c))} {'; '.join(extras)}"
        inter = b & c
        return "MISMATCH", f"overlap={len(inter)} blind={len(b)} canonical={len(c)}"
    # String fields
    b, c = norm_str(blind), norm_str(canonical)
    if not b and not c:
        return "BOTH_NULL", ""
    if b == c:
        return "MATCH", ""
    if b and c and (b in c or c in b):
        return "PARTIAL", f"blind={b[:40]!r} canonical={c[:40]!r}"
    if not b or not c:
        return "NULL_DIFF", f"blind={b[:40]!r} canonical={c[:40]!r}"
    return "MISMATCH", f"blind={b[:40]!r} canonical={c[:40]!r}"


def main() -> None:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    rows: list[dict] = []
    covered = 0
    for entry in sample:
        fid = entry["file_id"]
        blind_path = STAGING / fid / "audit_blind.json"
        md_path = ROOT / entry["md_path"]
        if not blind_path.exists():
            rows.append({"file_id": fid, "name": entry.get("name"), "status": "NO_BLIND"})
            continue
        if not md_path.exists():
            rows.append({"file_id": fid, "name": entry.get("name"), "status": "NO_MD"})
            continue
        try:
            blind = json.loads(blind_path.read_text(encoding="utf-8"))
        except Exception as e:
            rows.append({"file_id": fid, "name": entry.get("name"), "status": f"BAD_BLIND:{e}"})
            continue
        fm = parse_frontmatter(md_path.read_text(encoding="utf-8"))
        bf = blind.get("fields") or blind
        covered += 1
        for blind_field, canon_field in CMP_FIELDS:
            verdict, note = compare(blind_field, bf.get(blind_field), fm.get(canon_field))
            rows.append({
                "file_id": fid,
                "name": entry.get("name"),
                "document_type": entry.get("document_type"),
                "field": blind_field,
                "blind": bf.get(blind_field) if not isinstance(bf.get(blind_field), (list, dict)) else json.dumps(bf.get(blind_field), ensure_ascii=False),
                "canonical": fm.get(canon_field) if not isinstance(fm.get(canon_field), (list, dict)) else json.dumps(fm.get(canon_field), ensure_ascii=False),
                "verdict": verdict,
                "note": note,
            })

    with REPORT_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["file_id", "name", "document_type", "field", "blind", "canonical", "verdict", "note", "status"], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {REPORT_CSV}")

    # Aggregate
    verdict_count: dict[str, int] = {}
    per_field: dict[str, dict[str, int]] = {}
    for r in rows:
        v = r.get("verdict")
        if not v:
            continue
        verdict_count[v] = verdict_count.get(v, 0) + 1
        f = r.get("field") or "?"
        per_field.setdefault(f, {})
        per_field[f][v] = per_field[f].get(v, 0) + 1

    total_checks = sum(verdict_count.values())
    matches = verdict_count.get("MATCH", 0) + verdict_count.get("BOTH_NULL", 0)
    partials = verdict_count.get("PARTIAL", 0)
    mismatches = verdict_count.get("MISMATCH", 0)
    null_diffs = verdict_count.get("NULL_DIFF", 0)

    lines = [
        "# Forensic DD Spot-Check Audit Report",
        "",
        f"Sample: {covered} files × {len(CMP_FIELDS)} fields = **{total_checks} field-level checks**",
        "",
        "## Overall accuracy",
        "",
        f"- **MATCH** (exact): {matches} ({100*matches/max(total_checks,1):.1f}%)",
        f"- **PARTIAL** (subset / substring): {partials} ({100*partials/max(total_checks,1):.1f}%)",
        f"- **NULL_DIFF** (one side null, other populated): {null_diffs} ({100*null_diffs/max(total_checks,1):.1f}%)",
        f"- **MISMATCH** (clear conflict): {mismatches} ({100*mismatches/max(total_checks,1):.1f}%)",
        "",
        f"**DD-defensible accuracy (MATCH+PARTIAL): {100*(matches+partials)/max(total_checks,1):.1f}%**",
        "",
        "## Per-field breakdown",
        "",
        "| Field | MATCH | PARTIAL | NULL_DIFF | MISMATCH |",
        "|---|---:|---:|---:|---:|",
    ]
    for f in [x[0] for x in CMP_FIELDS]:
        d = per_field.get(f, {})
        m = d.get("MATCH", 0) + d.get("BOTH_NULL", 0)
        p = d.get("PARTIAL", 0)
        n = d.get("NULL_DIFF", 0)
        mm = d.get("MISMATCH", 0)
        lines.append(f"| {f} | {m} | {p} | {n} | {mm} |")

    lines += ["", "## Files with MISMATCH (require human review)", ""]
    for r in rows:
        if r.get("verdict") == "MISMATCH":
            lines.append(f"- `{r['file_id']}` **{r['field']}** · {r['name']}")
            lines.append(f"  - blind: `{str(r.get('blind'))[:120]}`")
            lines.append(f"  - canonical: `{str(r.get('canonical'))[:120]}`")
            lines.append(f"  - note: {r.get('note', '')}")

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT_MD}")
    print()
    print(f"MATCH: {matches} | PARTIAL: {partials} | NULL_DIFF: {null_diffs} | MISMATCH: {mismatches} | total: {total_checks}")
    print(f"DD-defensible (MATCH+PARTIAL): {100*(matches+partials)/max(total_checks,1):.1f}%")


if __name__ == "__main__":
    main()
