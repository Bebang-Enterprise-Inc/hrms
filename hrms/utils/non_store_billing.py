"""Non-store billing classifier (S201).

Decides whether an Employee should bill to `BEBANG ENTERPRISE INC.` (BEI
parent) regardless of which store they punch at.

Rule hierarchy (first match wins):
    1. bio_id in ROVING_EMPLOYEES -> True
    2. designation matches a non-store role (Area Supervisor, Regional Manager,
       Operations Manager, Area Coordinator, Projects Manager, etc.) -> True
    3. department in HO_DEPARTMENTS -> True
    4. branch resolves to category='HO' per branch_company_map -> True
    5. Else -> False (store or commissary biller; company_lookup decides which)

Per Sam 2026-04-17:
- SCM team at commissary (branch SHAW COMMISSARY - LOGISTICS) -> BEI parent
- R&D at commissary (SHAW COMMISSARY - RD QC) -> BEI parent (R&D dept rule)
- AS, Regional Manager, Projects, IT, Marketing, Finance, HR, Legal, Admin,
  Executive, Audit, R&D, BD -> BEI parent
"""

from __future__ import annotations

from typing import Any

from hrms.utils.company_lookup import (
    CATEGORY_HO,
    get_branch_category,
)
from hrms.utils.roving_employees import is_roving


# Department names that ALWAYS route to BEI parent. Keep uppercased for
# case-insensitive matching — live data has "Operations" vs "OPERATIONS" drift.
HO_DEPARTMENTS = frozenset(
    {
        "FINANCE AND ACCOUNTING",
        "FINANCE",
        "ACCOUNTING",
        "MARKETING",
        "HR AND ADMIN",
        "HR",
        "HUMAN RESOURCES",
        "PROJECTS",
        "ADMIN",
        "EXECUTIVE",
        "AUDIT",
        "INTERNAL AUDIT",
        "R&D",
        "RESEARCH AND DEVELOPMENT",
        "IT",
        "INFORMATION TECHNOLOGY",
        "BUSINESS DEVELOPMENT",
        "LEGAL",
        "SCM",
        "SUPPLY CHAIN",
        "SUPPLY CHAIN MANAGEMENT",
    }
)

# Designation keywords that ALWAYS route to BEI parent regardless of branch.
# Substring match, case-insensitive.
NON_STORE_DESIGNATIONS_KEYWORDS = (
    "AREA SUPERVISOR",
    "AREA COORDINATOR",
    "REGIONAL MANAGER",
    "OPERATIONS MANAGER",
    "PROJECTS MANAGER",
    "PROJECT MANAGER",
    "OPERATIONS DIRECTOR",
    "HEAD OF OPERATIONS",
    "CHIEF",  # CEO, CFO, COO, etc.
    "PRESIDENT",
    "VICE PRESIDENT",
    "DIRECTOR",
)


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()


def is_non_store_billing(
    *,
    bio_id: str | None = None,
    department: str | None = None,
    designation: str | None = None,
    branch: str | None = None,
) -> bool:
    """Return True if this employee should bill to BEI parent (not a store).

    Accepts individual fields rather than a doc object to keep the function
    testable without a Frappe context.
    """
    # Rule 1 — explicit roving authorization list (27 employees: AS, Projects,
    # Opening Team, Duty MyTown, Roving).
    if bio_id and is_roving(str(bio_id)):
        return True

    # Rule 2 — designation keywords.
    desig = _norm(designation)
    if desig:
        for kw in NON_STORE_DESIGNATIONS_KEYWORDS:
            if kw in desig:
                return True

    # Rule 3 — HO department.
    dept = _norm(department)
    if dept and dept in HO_DEPARTMENTS:
        return True

    # Rule 4 — branch_company_map says this branch is HO (e.g. BRITTANY OFFICE,
    # CAPITAL HOUSE, MYTOWN, SHAW COMMISSARY - LOGISTICS).
    if branch:
        try:
            category = get_branch_category(branch)
            if category == CATEGORY_HO:
                return True
        except Exception:
            # Missing map file or Frappe context — fail open (return False).
            pass

    return False


def is_non_store_billing_doc(employee_doc: Any) -> bool:
    """Convenience wrapper for a Frappe Employee doc."""
    return is_non_store_billing(
        bio_id=getattr(employee_doc, "attendance_device_id", None)
        or getattr(employee_doc, "new_attendance_device_id", None),
        department=getattr(employee_doc, "department", None),
        designation=getattr(employee_doc, "designation", None),
        branch=getattr(employee_doc, "branch", None),
    )
