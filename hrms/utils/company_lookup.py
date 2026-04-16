"""Branch -> Company resolver (S201).

Maps `Employee.branch` values to the Frappe Company that should own the
employee's payroll. Drives `Employee.validate()` auto-population and the
Transfer API's `new_company` field.

Single source of truth: `hrms/data_seed/branch_company_map.csv`.
Backing Company names come from live Frappe (post-S196 ALL CAPS store-first).

Usage:
    from hrms.utils.company_lookup import resolve_branch_to_company
    company = resolve_branch_to_company("SM MEGAMALL")
    # -> "SM MEGAMALL - BEBANG ENTERPRISE INC."
"""

from __future__ import annotations

import csv
import os
import threading
import time
from typing import Any

import frappe


BEI_PARENT_COMPANY = "BEBANG ENTERPRISE INC."
BKI_COMMISSARY_COMPANY = "BEBANG KITCHEN INC."

CATEGORY_HO = "HO"
CATEGORY_STORE = "Store"
CATEGORY_COMMISSARY = "Commissary"

MAP_RELPATH = ("data_seed", "branch_company_map.csv")

_CACHE_TTL = 60  # seconds
_cache_lock = threading.Lock()
_branch_map_cache: dict[str, dict] = {}
_store_company_index: dict[str, str] = {}
_cache_ts: float = 0.0


class UnknownBranch(Exception):
    """Raised when a branch value cannot be resolved to any Company."""


def _normalize(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()


def _resolve_map_path() -> str:
    """Resolve branch_company_map.csv path. Prefer Frappe app path; fall back
    to the file's own location for standalone use (tests, scripts).
    """
    try:
        return os.path.normpath(os.path.join(frappe.get_app_path("hrms"), *MAP_RELPATH))
    except Exception:
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(here, "..", *MAP_RELPATH))


def _load_branch_map() -> dict[str, dict]:
    """Load branch_company_map.csv keyed by uppercased old_branch."""
    path = _resolve_map_path()
    if not os.path.exists(path):
        try:
            frappe.log_error(
                title="S201 company_lookup: branch_company_map.csv missing",
                message=f"Expected at {path}",
            )
        except Exception:
            pass
        return {}
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return {_normalize(r.get("old_branch")): r for r in rows if r.get("old_branch")}


def _load_store_company_index() -> dict[str, str]:
    """Build {store_prefix_upper: full_company_name} for all entity_category='Store' Companies.

    Post-S196, Company names are `<STORE PREFIX> - <CORP>` (ALL CAPS).
    Index by the store prefix so resolver can find the exact docname.
    """
    try:
        companies = frappe.get_all(
            "Company",
            filters={"entity_category": "Store"},
            fields=["name"],
        )
    except Exception:
        # Not in Frappe context (tests) — caller should mock.
        return {}
    index: dict[str, str] = {}
    for row in companies:
        name = row.get("name") or ""
        if " - " in name:
            prefix = name.split(" - ", 1)[0].strip().upper()
            # First-wins; if two companies share a prefix (shouldn't), keep first.
            index.setdefault(prefix, name)
    return index


def _refresh_cache() -> None:
    """Rebuild both caches under lock."""
    global _branch_map_cache, _store_company_index, _cache_ts
    with _cache_lock:
        _branch_map_cache = _load_branch_map()
        _store_company_index = _load_store_company_index()
        _cache_ts = time.time()


def _ensure_fresh() -> None:
    """Reload caches if stale."""
    if not _branch_map_cache or (time.time() - _cache_ts) > _CACHE_TTL:
        _refresh_cache()


def clear_cache(*_args: Any, **_kwargs: Any) -> None:
    """Invalidate both caches. Wired to on_update hooks on Branch and Company."""
    global _branch_map_cache, _store_company_index, _cache_ts
    with _cache_lock:
        _branch_map_cache = {}
        _store_company_index = {}
        _cache_ts = 0.0


def get_non_store_parent() -> str:
    """Return the BEI parent Company name (BEBANG ENTERPRISE INC.)."""
    return BEI_PARENT_COMPANY


def get_commissary_company() -> str:
    """Return the Commissary Company name (BEBANG KITCHEN INC.)."""
    return BKI_COMMISSARY_COMPANY


def get_branch_category(branch: str) -> str | None:
    """Return the target_category ('HO' | 'Store' | 'Commissary') for a branch,
    or None if the branch is not mapped. Caller decides what to do on miss.
    """
    _ensure_fresh()
    row = _branch_map_cache.get(_normalize(branch))
    return (row or {}).get("target_category") or None


def get_branch_company_hint(branch: str) -> str | None:
    """Return the target_company_hint for a branch (store prefix OR full
    non-store Company name), or None if not mapped.
    """
    _ensure_fresh()
    row = _branch_map_cache.get(_normalize(branch))
    return (row or {}).get("target_company_hint") or None


def resolve_branch_to_company(
    branch: str,
    department: str | None = None,
) -> str:
    """Return the Frappe Company docname an employee with this branch should
    post to.

    Commissary disambiguation: bare `SHAW COMMISSARY` / `COMMISSARY SHAW`
    branches route by department — Commissary dept -> BKI, else -> BEI parent.
    Suffix-tagged commissary branches (Production / Logistics / RD QC) are
    resolved deterministically via the map.

    Args:
        branch: Employee.branch value (case-insensitive lookup).
        department: Employee.department (optional; used only for bare
                    commissary disambiguation).

    Returns:
        Frappe Company docname (e.g. "SM MEGAMALL - BEBANG ENTERPRISE INC.").

    Raises:
        UnknownBranch: if the branch is not in the mapping CSV.
    """
    _ensure_fresh()
    key = _normalize(branch)
    if not key:
        raise UnknownBranch("Empty branch value")
    row = _branch_map_cache.get(key)
    if not row:
        raise UnknownBranch(f"Branch {branch!r} not found in branch_company_map.csv")

    category = (row.get("target_category") or "").strip()
    hint = (row.get("target_company_hint") or "").strip()

    if category == CATEGORY_HO:
        return BEI_PARENT_COMPANY

    if category == CATEGORY_COMMISSARY:
        # Deterministic rows (e.g. SHAW COMMISSARY - Production) carry a
        # concrete Company name as hint -> always route there.
        # Ambiguous rows (bare SHAW COMMISSARY / COMMISSARY SHAW) carry
        # hint=DEPT_DRIVEN -> check department: Commissary -> BKI, else BEI.
        if hint == "DEPT_DRIVEN":
            if _normalize(department) == "COMMISSARY":
                return BKI_COMMISSARY_COMPANY
            return BEI_PARENT_COMPANY
        if hint:
            return hint
        return BKI_COMMISSARY_COMPANY

    if category == CATEGORY_STORE:
        # Hint is the store prefix (e.g. "SM MEGAMALL"). Look up the live
        # Frappe Company whose name starts with that prefix.
        if not hint or hint == "NEEDS_MANUAL_REVIEW":
            raise UnknownBranch(
                f"Branch {branch!r} flagged NEEDS_MANUAL_REVIEW — resolve manually"
            )
        full_name = _store_company_index.get(_normalize(hint))
        if not full_name:
            # Rebuild index once in case of fresh provisioning
            _refresh_cache()
            full_name = _store_company_index.get(_normalize(hint))
        if not full_name:
            raise UnknownBranch(
                f"Branch {branch!r} maps to store prefix {hint!r} but no "
                f"Company with entity_category='Store' starts with that prefix"
            )
        return full_name

    raise UnknownBranch(
        f"Branch {branch!r} has unknown target_category {category!r}"
    )


def resolve_branch_rename(branch: str) -> str | None:
    """Return the canonical new_branch name per the rename map.

    Returns None if the branch is not in the map. Returns the same branch if
    no rename needed (old == new).
    """
    _ensure_fresh()
    row = _branch_map_cache.get(_normalize(branch))
    if not row:
        return None
    return (row.get("new_branch") or "").strip() or None


def iter_branch_map() -> list[dict]:
    """Return a list copy of the full branch map (for reporting / patches)."""
    _ensure_fresh()
    return list(_branch_map_cache.values())
