"""Fix all remaining 'Other' ai_category and misclassified document_type values.

No more 'Other' — every file gets a specific category and type.
"""
from __future__ import annotations
import re, sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
DD = ROOT / "CEO" / "Valuation" / "admin_compliance_dd"

# Fixes: {md_relative: {field: new_value, ...}}
FIXES: dict[str, dict[str, str]] = {
    # Condo title for BEI HQ — Property asset
    "CORP_BEI/SEC_CERT/CERT_BEI_20210316_v1.md": {
        "document_type": "CONDO_CCT",
        "ai_category": "Property",
        "ai_label": "Condominium Certificate of Title — Unit 2409 Capital House Taguig BEI HQ 2021",
        "short_description": "Condominium Certificate of Title (CCT) for BEI head office at Unit 2409 Capital House, BGC Taguig — real property asset.",
    },
    # IPO Trademark
    "CORP_BEI/SEC_CERT/CERT_BEI_20240623_v1.md": {
        "document_type": "IPO_TRADEMARK",
        "ai_category": "Trademark",
        "ai_label": "IPO Trademark Assignment Recordal — B BEBANG HALO-HALO 2024",
        "short_description": "IPO trademark assignment recordal for 'B BEBANG HALO-HALO' mark — intellectual property registration.",
    },
    "CORP_BEI/SEC_CERT/CERT_BEI_20240623_v2.md": {
        "document_type": "IPO_TRADEMARK",
        "ai_category": "Trademark",
        "ai_label": "IPO Trademark Assignment Recordal — BEBANG HALO-HALO 2024",
        "short_description": "IPO trademark assignment recordal for 'BEBANG HALO-HALO' wordmark — intellectual property registration.",
    },
    # LTO Vehicle Registration — Asset
    "CORP_BEI/SEC_CERT/CERT_BEI_20241201_v1.md": {
        "document_type": "VEHICLE_REG",
        "ai_category": "Asset",
        "ai_label": "LTO Certificate of Registration — BEI Isuzu Refrigerated Van NKG 7312 2024",
        "short_description": "LTO Certificate of Registration for BEI-owned Isuzu refrigerated van (plate NKG 7312) — fleet asset.",
    },
    # BUSINESS_PERMIT = MAYORS_PERMIT
    "CORP_MARKET_MARKET/BP/BUS_PERMIT_MARKET_MARKET_20250121_v1.md": {
        "document_type": "MAYORS_PERMIT",
        "ai_category": "LGU",
        "ai_label": "Mayor's / Business Permit — BEBANG HALO HALO Market! Market! 2025",
        "short_description": "Mayor's / Business Permit for BEBANG HALO HALO at Market! Market! Taguig, issued 2025.",
    },
    # BIR 1601-C
    "CORP_RESTO_TECH/TAX_1601C/1601C_RESTO_TECH_20241001_v1.md": {
        "document_type": "BIR_1601C",
        "ai_category": "Tax_Return",
        "ai_label": "BIR Form 1601-C Withholding Tax Return — RESTO TECH INC. Oct 2024",
        "short_description": "BIR Form 1601-C monthly withholding tax return for compensation, Resto Tech Inc., period Oct 2024.",
    },
    # SM POS Registration Form — Admin form / SM tenant docs
    "CORP_SMM/UNKNOWN/UNKNOWN_SMM_NODATE_v1.md": {
        "document_type": "TENANT_REG_FORM",
        "ai_category": "Lease",
        "ai_label": "SM Supermalls POS Registration Form — Bebang Halo-Halo SM City Manila",
        "short_description": "SM Supermalls tenant POS registration form for Bebang Halo-Halo at SM City Manila — lease ancillary document.",
    },
    # BDO KYC — Banking
    "CORP_SMOA/UNKNOWN/UNKNOWN_SMOA_20241210_v1.md": {
        "document_type": "BANK_KYC",
        "ai_category": "Banking",
        "ai_label": "BDO Business A1 KYC Form — BEBANG SMOA INC. 2024",
        "short_description": "BDO Unibank Business Account KYC onboarding form for Bebang SMOA Inc., completed Dec 2024.",
    },
    # Tungsten POS Registration Cert
    "CORP_TUNGSTEN/SEC_CERT/CERT_TUNGSTEN_20251014_v1.md": {
        "document_type": "BIR_PTU_POS",
        "ai_category": "BIR",
        "ai_label": "BIR POS Registration Certificate — Tungsten Capital Holdings OPC 2025",
        "short_description": "BIR POS machine registration certificate for Tungsten Capital Holdings OPC, 2025.",
    },
    # SIM Replacement Letter
    "STORE_MEGAMALL/UNKNOWN/UNKNOWN_STORE_MEGAMALL_20250523_v1.md": {
        "document_type": "LETTER",
        "ai_category": "Correspondence",
        "ai_label": "CEO Letter to Smart Communications — SIM Card Replacement Request 2025",
        "short_description": "Formal letter from Sam Karazi (CEO) to Smart Communications requesting SIM card replacement, May 2025.",
    },
    # Google Maps screenshot — Reference
    "STORE_ROBINSONSANTIPOLO/UNKNOWN/UNKNOWN_STORE_ROBINSONSANTIPOLO_20250101_v1.md": {
        "document_type": "REFERENCE_MAP",
        "ai_category": "Reference",
        "ai_label": "Google Maps Screenshot — Robinsons Antipolo Location 2025",
        "short_description": "Google Maps screenshot of Robinsons Antipolo mall — location reference for store permits.",
    },
    # BDO KYC Antipolo — Banking
    "STORE_ROBINSONSANTIPOLO/UNKNOWN/UNKNOWN_STORE_ROBINSONSANTIPOLO_20250219_v1.md": {
        "document_type": "BANK_KYC",
        "ai_category": "Banking",
        "ai_label": "BDO Business A1 KYC Form — Bebang Robinsons Antipolo Inc. 2025",
        "short_description": "BDO Unibank Business Account KYC onboarding form for Bebang Robinsons Antipolo Inc., Feb 2025.",
    },
    # BDO KYC SMSouthmall
    "STORE_SMSOUTHMALL/UNKNOWN/UNKNOWN_STORE_SMSOUTHMALL_20250131_v1.md": {
        "document_type": "BANK_KYC",
        "ai_category": "Banking",
        "ai_label": "BDO Business A1 KYC Form — Bebang SM Southmall Inc. 2025",
        "short_description": "BDO Unibank Business Account KYC onboarding form for Bebang SM Southmall Inc., Jan 2025.",
    },
}


def strip_q(s: str) -> str:
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    return s


def quote(s: str) -> str:
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def update_md(md_path: Path, updates: dict) -> bool:
    text = md_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False
    parts = text.split("---", 2)
    if len(parts) < 3:
        return False
    fm_text, body = parts[1], parts[2]
    pairs = []
    for line in fm_text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_]+):\s?(.*)$", line)
        if m:
            pairs.append([m.group(1), m.group(2)])
    keys_seen = {k for k, _ in pairs}
    for k, v in updates.items():
        if k in keys_seen:
            for p in pairs:
                if p[0] == k:
                    p[1] = quote(v)
                    break
        else:
            pairs.append([k, quote(v)])
    new_fm = "\n".join(f"{k}: {v}" for k, v in pairs)
    md_path.write_text("---\n" + new_fm + "\n---\n" + body.lstrip("\n"), encoding="utf-8")
    return True


def main() -> None:
    ok = miss = 0
    for rel, updates in FIXES.items():
        p = DD / rel
        if not p.exists():
            print(f"MISS: {rel}")
            miss += 1
            continue
        update_md(p, updates)
        ok += 1
    print(f"fixed: {ok}, missing: {miss}")

    # Final pass: any remaining "Other" category
    print("\n=== Checking for remaining Other ===")
    remaining = []
    for p in DD.rglob("*.md"):
        if p.name.startswith("_"):
            continue
        if any(part.startswith("_") for part in p.relative_to(DD).parts[:-1]):
            continue
        text = p.read_text(encoding="utf-8")
        m = re.search(r"^ai_category:\s*\"?(\w+)\"?", text, re.MULTILINE)
        if m and m.group(1) == "Other":
            remaining.append(str(p.relative_to(DD)))
    print(f"remaining 'Other': {len(remaining)}")
    for r in remaining:
        print(f"  {r}")


if __name__ == "__main__":
    main()
