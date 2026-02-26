"""
BEI ERP Data Consolidation - Phase 1 & 2
Phase 1: Create directory structure
Phase 2: Copy & deduplicate questionnaires and source documents

Run from project root: python scripts/consolidate/consolidate_phase1_2.py
"""
import os
import shutil
from pathlib import Path

ROOT = Path("F:/Dropbox/Projects/BEI-ERP")
DEST = ROOT / "data" / "_CONSOLIDATED"

# 14 department folders
DEPARTMENTS = [
    "01_FINANCE",
    "02_HR",
    "03_OPERATIONS",
    "04_SUPPLY_CHAIN",
    "05_PROCUREMENT",
    "06_COMMISSARY_RND",
    "07_PROJECTS",
    "08_BUSINESS_DEV",
    "09_IT",
    "10_MARKETING",
    "11_INTERNAL_AUDIT",
    "12_CUSTOMER_SUPPORT",
    "13_ADMIN",
    "14_ANALYTICS",
]

# Subfolders per department
SUBFOLDERS = ["questionnaires", "source_documents", "pending"]

# File mapping: source (relative to ROOT) -> destination folder (relative to DEST)
FILE_MAP = {
    # === Primary Department Specs ===
    "data/Department_Specs/01_OPERATIONS_Herdie_Hernandez.md": "03_OPERATIONS/questionnaires/",
    "data/Department_Specs/02_SUPPLY_CHAIN_Aldrin_Reyes.md": "04_SUPPLY_CHAIN/questionnaires/",
    "data/Department_Specs/03_PROCUREMENT_Cayla_Cabagnot.md": "05_PROCUREMENT/questionnaires/",
    "data/Department_Specs/04_FINANCE_Butch_Formoso.md": "01_FINANCE/questionnaires/",
    "data/Department_Specs/05_PROJECTS_Dan_Marquez.md": "07_PROJECTS/questionnaires/",
    "data/Department_Specs/06_BUSINESS_DEV_Andrew_Manansala.md": "08_BUSINESS_DEV/questionnaires/",
    "data/Department_Specs/07_HR_Ronald_Caringal.md": "02_HR/questionnaires/",
    "data/Department_Specs/08_IT_Archie_Reyes.md": "09_IT/questionnaires/",
    "data/Department_Specs/09_MARKETING_Maui_Mauricio.md": "10_MARKETING/questionnaires/",
    "data/Department_Specs/10_INTERNAL_AUDIT_Arshier_Ching.md": "11_INTERNAL_AUDIT/questionnaires/",
    "data/Department_Specs/11_CUSTOMER_SUPPORT_Ruby_Bernal.md": "12_CUSTOMER_SUPPORT/questionnaires/",
    "data/Department_Specs/12_ADMIN_General_Administration.md": "13_ADMIN/questionnaires/",
    "data/Department_Specs/13_RND_Arnold_James.md": "06_COMMISSARY_RND/questionnaires/",

    # === Follow-up Answers ===
    "data/Department_Specs/FollowUp_Answers/FINANCE_Butch_Formoso_ERPNext_Policy_Decisions_Answered_2026-01-05.md": "01_FINANCE/questionnaires/",
    "data/Department_Specs/FollowUp_Answers/HR_Ronald_Caringal_Attendance_BioID_Policy_Answered_2026-01-05.md": "02_HR/questionnaires/",
    "data/Department_Specs/FollowUp_Answers/HR_Ronald_Caringal_FollowUp_Answered_2025-12-27.md": "02_HR/questionnaires/",
    "data/Department_Specs/FollowUp_Answers/IT_Archie_Reyes_Attendance_Logs_FollowUp_Answered_2025-12-29.md": "09_IT/questionnaires/",
    "data/Department_Specs/FollowUp_Answers/OPS_Herdie_Hernandez_FollowUp_Answered_2025-12-28.md": "03_OPERATIONS/questionnaires/",
    "data/Department_Specs/FollowUp_Answers/PROCUREMENT_Cayla_Cabagnot_FollowUp_Answered_2025-12-27.md": "05_PROCUREMENT/questionnaires/",
    "data/Department_Specs/FollowUp_Answers/RND_Arnold_James_FollowUp_Answered_2025-12-27.md": "06_COMMISSARY_RND/questionnaires/",
    "data/Department_Specs/FollowUp_Answers/SUPPLY_CHAIN_Aldrin_Reyes_FollowUp_Answered_2025-12-27.md": "04_SUPPLY_CHAIN/questionnaires/",
    "data/Department_Specs/FollowUp_Answers/ANALYTICS_Dave_Store_Sales_Data_Pipeline_Answered_2026-01-04.md": "14_ANALYTICS/questionnaires/",

    # === Sprint/Audit Questionnaires ===
    "questionnaires/responses/SHELF_LIFE_RESPONSES.md": "06_COMMISSARY_RND/questionnaires/",

    # === Source Documents ===
    "data/_FINAL/COA.csv": "01_FINANCE/source_documents/",
    "docs/erp/WAREHOUSE_TREE_2025-12-31.csv": "04_SUPPLY_CHAIN/source_documents/",

    # === Pending Follow-ups ===
    "data/Follow-Ups/HR_FINANCE_Payroll_Gaps_Questionnaire.md": "02_HR/pending/",
    "data/Follow-Ups/HR_HRMS_Module_Gap_Questionnaire_2026-02-08.md": "02_HR/pending/",
    "data/Follow-Ups/OPS_Attendance_Store_Sales_Workflow_FollowUp.md": "03_OPERATIONS/pending/",
    "data/Follow-Ups/SUPPLY_CHAIN_Aldrin_Reyes_Route_Management_FollowUp.md": "04_SUPPLY_CHAIN/pending/",
    "data/Follow-Ups/SALES_VISIBILITY_DEFINITIONS_ONE_PAGER_TO_FILL.md": "03_OPERATIONS/pending/",
    "data/Follow-Ups/IT_Archie_Reyes_Attendance_Logs_FollowUp.md": "09_IT/pending/",
    "data/Follow-Ups/IT_Rajat_Verma_API_Integration_FollowUp.md": "09_IT/pending/",
    "data/Follow-Ups/ANALYTICS_Dave_Store_Sales_Dashboard_FollowUp.md": "14_ANALYTICS/pending/",
    "data/Follow-Ups/HR_Ronald_Caringal_Attendance_Logs_FollowUp.md": "02_HR/pending/",
}

# Additional files that may exist in docs/questionnaires/
DOCS_QUESTIONNAIRES_MAP = {
    "docs/questionnaires/CFO_PROCUREMENT_SPRINT_2026-02-09.md": "01_FINANCE/questionnaires/",
    "docs/questionnaires/POS_DAILY_SYNC_AUDIT_2026-02-12.md": "01_FINANCE/questionnaires/",
    "docs/questionnaires/MARKET_MARKET_Q4_GAPS_2026-02-13.md": "01_FINANCE/questionnaires/",
    "docs/questionnaires/BEBANG_ACCOUNT_NOS_EXTRACT.md": "01_FINANCE/source_documents/",
    "docs/questionnaires/FRANCHISE_GL_ACCOUNTS_PROPOSED.csv": "01_FINANCE/source_documents/",
    "docs/questionnaires/FRANCHISE_STORES_DATA_NOV2025.csv": "08_BUSINESS_DEV/source_documents/",
    "docs/questionnaires/FRANCHISE_BILLING_SUMMARY.txt": "08_BUSINESS_DEV/source_documents/",
}

# Additional source documents that may exist
EXTRA_SOURCE_DOCS = {
    "docs/erp/PERMISSION_MATRIX_2026-01-15.md": "05_PROCUREMENT/source_documents/",
    "docs/erp/ATTENDANCE_FLEXI_TIME_POLICY_2026-01-21.md": "02_HR/source_documents/",
    "docs/commissary/COMMISSARY_COST_BASELINE_2026-02-16.md": "06_COMMISSARY_RND/source_documents/",
    "questionnaires/templates/accounting_questionnaire.txt": "01_FINANCE/questionnaires/",
}


def create_structure():
    """Phase 1: Create directory tree."""
    print("=" * 60)
    print("PHASE 1: Creating directory structure")
    print("=" * 60)

    DEST.mkdir(parents=True, exist_ok=True)
    created = 0

    for dept in DEPARTMENTS:
        dept_path = DEST / dept
        dept_path.mkdir(exist_ok=True)
        for sub in SUBFOLDERS:
            (dept_path / sub).mkdir(exist_ok=True)
            created += 1

        # Create template DECISIONS.md
        decisions_path = dept_path / "DECISIONS.md"
        if not decisions_path.exists():
            dept_name = dept.split("_", 1)[1].replace("_", " ").title()
            decisions_path.write_text(
                f"# {dept_name} — Confirmed Decisions\n\n"
                f"**Last Updated:** 2026-02-19\n"
                f"**Status:** PENDING EXTRACTION (Phase 3)\n\n"
                f"---\n\n"
                f"_Decisions will be extracted from plan/progress files in Phase 3._\n",
                encoding="utf-8",
            )

        # Create template GAPS.md
        gaps_path = dept_path / "GAPS.md"
        if not gaps_path.exists():
            dept_name = dept.split("_", 1)[1].replace("_", " ").title()
            gaps_path.write_text(
                f"# {dept_name} — Open Questions & Gaps\n\n"
                f"**Last Updated:** 2026-02-19\n"
                f"**Status:** PENDING EXTRACTION (Phase 3)\n\n"
                f"---\n\n"
                f"_Gaps will be compiled from questionnaires and follow-ups in Phase 3._\n",
                encoding="utf-8",
            )

    # Create root README
    readme_path = DEST / "README.md"
    readme_path.write_text(
        "# BEI ERP — Consolidated Department Data\n\n"
        "**Created:** 2026-02-19\n"
        "**Purpose:** Single source of truth for all department questionnaires, "
        "confirmed decisions, and open gaps for ERPNext setup.\n\n"
        "## How to Use\n\n"
        "1. **Find a department** — Each folder (01-14) contains one department's complete data\n"
        "2. **Check decisions** — `DECISIONS.md` has every confirmed ERPNext decision with source references\n"
        "3. **Check gaps** — `GAPS.md` lists unanswered questions that block implementation\n"
        "4. **Read questionnaires** — `questionnaires/` has the original answered questionnaires\n"
        "5. **Check pending** — `pending/` has questionnaires sent but not yet returned\n\n"
        "## Root Files\n\n"
        "| File | Purpose |\n"
        "|------|---------|\n"
        "| `DECISION_REGISTER.md` | Cross-department view of ALL confirmed decisions |\n"
        "| `GAP_REGISTER.md` | Cross-department view of ALL open questions |\n"
        "| `DEPARTMENT_READINESS_SCORECARD.md` | At-a-glance readiness per department |\n\n"
        "## Department Index\n\n"
        "| # | Department | Key Contact | Primary Questionnaire |\n"
        "|---|-----------|-------------|----------------------|\n"
        "| 01 | Finance | Butch Formoso (CFO) | 04_FINANCE_Butch_Formoso.md |\n"
        "| 02 | HR | Ronald Caringal | 07_HR_Ronald_Caringal.md |\n"
        "| 03 | Operations | ~~Herdie Hernandez~~ (terminated) → Edlice | 01_OPERATIONS_Herdie_Hernandez.md |\n"
        "| 04 | Supply Chain | Aldrin Reyes | 02_SUPPLY_CHAIN_Aldrin_Reyes.md |\n"
        "| 05 | Procurement | Cayla Cabagnot | 03_PROCUREMENT_Cayla_Cabagnot.md |\n"
        "| 06 | Commissary/R&D | Arnold James | 13_RND_Arnold_James.md |\n"
        "| 07 | Projects | Dan Marquez | 05_PROJECTS_Dan_Marquez.md |\n"
        "| 08 | Business Dev | Andrew Manansala | 06_BUSINESS_DEV_Andrew_Manansala.md |\n"
        "| 09 | IT | Archie Reyes | 08_IT_Archie_Reyes.md |\n"
        "| 10 | Marketing | ~~Maui Mauricio~~ (terminated) → TBD | 09_MARKETING_Maui_Mauricio.md |\n"
        "| 11 | Internal Audit | ~~Arshier Ching~~ (resigned) → TBD | 10_INTERNAL_AUDIT_Arshier_Ching.md |\n"
        "| 12 | Customer Support | Ruby Bernal | 11_CUSTOMER_SUPPORT_Ruby_Bernal.md |\n"
        "| 13 | Admin | General Administration | 12_ADMIN_General_Administration.md |\n"
        "| 14 | Analytics | Dave | Store_Sales_Data_Pipeline_2026-01-04.md |\n\n"
        "## Personnel Changes\n\n"
        "- **Herdie Hernandez** (Operations) — Terminated. Contact Edlice for Ops questions.\n"
        "- **Maui Mauricio** (Marketing) — Terminated. Replacement TBD.\n"
        "- **Arshier Ching** (Internal Audit) — Resigned. Replacement TBD.\n",
        encoding="utf-8",
    )

    # Create placeholder root files
    for fname in ["DECISION_REGISTER.md", "GAP_REGISTER.md", "DEPARTMENT_READINESS_SCORECARD.md"]:
        fpath = DEST / fname
        if not fpath.exists():
            fpath.write_text(
                f"# {fname.replace('.md', '').replace('_', ' ').title()}\n\n"
                f"**Status:** PENDING — Will be populated in Phase 3\n",
                encoding="utf-8",
            )

    print(f"  Created {len(DEPARTMENTS)} department folders with {created} subfolders")
    print(f"  Created README.md + 3 root register files")
    print(f"  Created template DECISIONS.md + GAPS.md for each department")
    print()


def copy_files(file_map, label):
    """Copy files from source to destination, preserving names."""
    copied = 0
    skipped = 0
    missing = 0

    for src_rel, dest_rel in file_map.items():
        src = ROOT / src_rel
        if not src.exists():
            print(f"  MISSING: {src_rel}")
            missing += 1
            continue

        dest_dir = DEST / dest_rel
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / src.name

        if dest_file.exists():
            # Check if content is same
            if dest_file.read_bytes() == src.read_bytes():
                skipped += 1
                continue

        shutil.copy2(str(src), str(dest_file))
        copied += 1

    print(f"  {label}: {copied} copied, {skipped} already exist, {missing} missing")
    return copied, skipped, missing


def run_phase2():
    """Phase 2: Copy & deduplicate questionnaires."""
    print("=" * 60)
    print("PHASE 2: Copying questionnaires & source documents")
    print("=" * 60)

    total_copied = 0
    total_skipped = 0
    total_missing = 0

    for label, fmap in [
        ("Primary specs + follow-ups + pending", FILE_MAP),
        ("Sprint/audit questionnaires", DOCS_QUESTIONNAIRES_MAP),
        ("Extra source documents", EXTRA_SOURCE_DOCS),
    ]:
        c, s, m = copy_files(fmap, label)
        total_copied += c
        total_skipped += s
        total_missing += m

    print()
    print(f"  TOTAL: {total_copied} files copied, {total_skipped} already existed, {total_missing} not found")
    print()


def verify():
    """Quick verification: count files per department."""
    print("=" * 60)
    print("VERIFICATION: Files per department")
    print("=" * 60)

    total = 0
    for dept in DEPARTMENTS:
        dept_path = DEST / dept
        files = []
        for sub in SUBFOLDERS:
            sub_path = dept_path / sub
            if sub_path.exists():
                files.extend([f.name for f in sub_path.iterdir() if f.is_file()])
        total += len(files)
        status = "OK" if files else "EMPTY (no questionnaires)"
        print(f"  {dept}: {len(files)} files — {status}")
        for f in sorted(files):
            print(f"    - {f}")

    print()
    print(f"  TOTAL: {total} files across {len(DEPARTMENTS)} departments")


if __name__ == "__main__":
    create_structure()
    run_phase2()
    verify()
    print()
    print("Phase 1 + 2 complete. Next: Phase 3 (extract decisions from plans)")
