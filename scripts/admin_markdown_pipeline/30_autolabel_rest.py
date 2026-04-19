"""Auto-derive ai_label, ai_category, short_description for MDs that don't have them yet.

For files with clear document_type + entity_code + business_name, we don't need agents —
we can construct high-quality labels from existing fields.
"""
from __future__ import annotations
import re, sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
DD = ROOT / "CEO" / "Valuation" / "admin_compliance_dd"


def parse_fm(text: str) -> list[tuple[str, str]]:
    if not text.startswith("---"):
        return []
    parts = text.split("---", 2)
    if len(parts) < 3:
        return []
    pairs = []
    for line in parts[1].splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_]+):\s?(.*)$", line)
        if m:
            pairs.append((m.group(1), m.group(2)))
    return pairs


def strip_quotes(s: str) -> str:
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    return s


DT_TO_CATEGORY = {
    "BIR_2303": "BIR", "BIR_PTU_POS": "BIR", "BIR_ATP": "BIR", "BIR_BOOKS": "BIR",
    "BIR_1601C": "Tax_Return", "BIR_OTHER": "BIR",
    "SEC_AOI": "SEC", "SEC_BYLAWS": "SEC", "SEC_COI": "SEC", "SEC_CERT": "SEC",
    "SEC_GIS": "SEC", "SEC_BOARD_RES": "SEC", "SEC_COVER": "SEC", "SEC_FORM_SUMMARY": "SEC",
    "MAYORS_PERMIT": "LGU", "BARANGAY_CLEARANCE": "LGU", "BUILDING_PERMIT": "LGU",
    "FSIC": "LGU", "SANITARY": "LGU", "DOLE": "LGU", "CERT_OCCUPANCY": "LGU",
    "LEASE": "Lease", "CONTRACT": "Contract",
    "FRANCHISE_AGREEMENT": "Contract", "JV_AGREEMENT": "Contract",
    "INSURANCE": "Insurance", "RECEIPT": "Receipt", "SALES_INVOICE": "Receipt",
    "ID": "ID", "LETTER": "Other", "SWORN_STATEMENT": "Other", "OTHER": "Other",
}

DT_LABEL = {
    "BIR_2303": "BIR 2303 Certificate of Registration",
    "BIR_PTU_POS": "BIR Permit to Use POS",
    "BIR_ATP": "BIR Authority to Print",
    "BIR_BOOKS": "BIR Books of Accounts",
    "BIR_1601C": "BIR Form 1601-C (Withholding Tax)",
    "BIR_OTHER": "BIR Notice/Other",
    "SEC_AOI": "Articles of Incorporation",
    "SEC_BYLAWS": "By-Laws",
    "SEC_COI": "Certificate of Incorporation",
    "SEC_CERT": "SEC Certificate",
    "SEC_GIS": "General Information Sheet",
    "SEC_BOARD_RES": "Board Resolution",
    "SEC_COVER": "SEC Cover Sheet",
    "SEC_FORM_SUMMARY": "SEC Form Summary",
    "MAYORS_PERMIT": "Mayor's / Business Permit",
    "BARANGAY_CLEARANCE": "Barangay Clearance",
    "BUILDING_PERMIT": "Building Permit",
    "FSIC": "Fire Safety Inspection Certificate",
    "SANITARY": "Sanitary Permit",
    "DOLE": "DOLE Clearance",
    "CERT_OCCUPANCY": "Certificate of Occupancy",
    "LEASE": "Lease Contract",
    "CONTRACT": "Contract",
    "FRANCHISE_AGREEMENT": "Franchise Agreement",
    "JV_AGREEMENT": "Joint Venture Agreement",
    "INSURANCE": "Insurance Policy / Receipt",
    "RECEIPT": "Receipt",
    "SALES_INVOICE": "Sales Invoice",
    "ID": "Identification Document",
    "LETTER": "Letter",
    "SWORN_STATEMENT": "Sworn Statement / Affidavit",
    "OTHER": "Other Document",
}


def year_from_date(d: str) -> str:
    if not d:
        return ""
    m = re.match(r"^(\d{4})", d)
    return m.group(1) if m else ""


def build_labels(fm: dict, entity_code: str) -> tuple[str, str, str]:
    dt = strip_quotes(fm.get("document_type", "") or "").upper()
    biz = strip_quotes(fm.get("canonical_business_name", "") or "").strip()
    trade = strip_quotes(fm.get("canonical_trade_name", "") or "").strip()
    entity_map = strip_quotes(fm.get("entity_store_mapping", "") or "").strip()
    issue = strip_quotes(fm.get("canonical_issue_date", "") or "").strip()
    expiry = strip_quotes(fm.get("canonical_expiry_date", "") or "").strip()

    cat = DT_TO_CATEGORY.get(dt, "Other")
    label_type = DT_LABEL.get(dt, dt.replace("_", " ").title())

    # Pick best entity label
    entity_label = ""
    if entity_map and entity_map.lower() != "null":
        entity_label = entity_map
    elif trade and trade.lower() not in {"null", ""}:
        entity_label = trade
    elif biz and biz.lower() not in {"null", ""}:
        entity_label = biz
    else:
        entity_label = entity_code.replace("CORP_", "").replace("STORE_", "").replace("_", " ")

    yr = year_from_date(issue)
    ai_label = f"{label_type} — {entity_label}" + (f" {yr}" if yr else "")

    # Short description
    parts = [label_type]
    if entity_label:
        parts.append(f"for {entity_label}")
    if issue:
        parts.append(f"issued {issue}")
    if expiry:
        parts.append(f"expiring {expiry}")
    short_desc = ", ".join(parts) + "."

    return ai_label, cat, short_desc


def update_md(md_path: Path) -> bool:
    text = md_path.read_text(encoding="utf-8")
    pairs = parse_fm(text)
    if not pairs:
        return False
    fm_dict = {k: v for k, v in pairs}
    if fm_dict.get("ai_label"):  # already labeled
        return False
    ec = strip_quotes(fm_dict.get("entity_code", "") or "")
    ai_label, ai_cat, short_desc = build_labels(fm_dict, ec)

    q = lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
    new_fields = [("ai_label", q(ai_label)), ("ai_category", q(ai_cat)), ("short_description", q(short_desc))]

    # Insert ai_* fields right after document_type (or at start if not found)
    insert_idx = 0
    for i, (k, _) in enumerate(pairs):
        if k == "document_type":
            insert_idx = i + 1
            break
    # Remove any existing ai_* to avoid duplicates
    pairs = [(k, v) for (k, v) in pairs if k not in {"ai_label", "ai_category", "short_description"}]
    pairs = pairs[:insert_idx] + new_fields + pairs[insert_idx:]

    parts = text.split("---", 2)
    new_fm = "\n".join(f"{k}: {v}" for k, v in pairs)
    new_text = "---\n" + new_fm + "\n---\n" + parts[2].lstrip("\n")
    md_path.write_text(new_text, encoding="utf-8")
    return True


def main() -> None:
    updated = skipped = 0
    for p in sorted(DD.rglob("*.md")):
        if p.name.startswith("_"):
            continue
        rel = p.relative_to(DD)
        if any(part.startswith("_") for part in rel.parts[:-1]):
            continue
        if update_md(p):
            updated += 1
        else:
            skipped += 1
    print(f"auto-labeled: {updated} | skipped (already labeled): {skipped}")


if __name__ == "__main__":
    main()
