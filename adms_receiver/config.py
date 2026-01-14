from __future__ import annotations

import os
from dataclasses import dataclass


def _clean(s: str | None) -> str:
    return "" if s is None else str(s).strip()


def _as_int(env_name: str, default: int) -> int:
    raw = _clean(os.getenv(env_name, str(default)))
    try:
        return int(raw)
    except Exception:
        return default


@dataclass(frozen=True)
class Settings:
    database_url: str
    frappe_base_url: str
    frappe_token: str
    sn_mapping_csv: str
    sn_allowlist: set[str]

    # Frappe behavior
    skip_auto_attendance: int
    max_attempts: int

    # Unknown Bio ID catcher
    unknown_employee_field_value: str
    unknown_comment_enabled: int

    # Device metadata / identifiers
    device_id_format: str

    # Admin endpoints (server-side automation / commands)
    admin_token: str

    # Device command queue behavior (best-effort; format TBD)
    cmd_max_attempts: int


def load_settings() -> Settings:
    database_url = _clean(os.getenv("ADMS_DATABASE_URL"))
    frappe_base_url = _clean(os.getenv("FRAPPE_BASE_URL"))
    frappe_token = _clean(os.getenv("FRAPPE_TOKEN"))
    sn_mapping_csv = _clean(os.getenv("SN_MAPPING_CSV"))

    if not database_url:
        raise RuntimeError("Missing ADMS_DATABASE_URL")
    if not frappe_base_url:
        raise RuntimeError("Missing FRAPPE_BASE_URL")
    if not frappe_token:
        raise RuntimeError("Missing FRAPPE_TOKEN")
    if not sn_mapping_csv:
        raise RuntimeError("Missing SN_MAPPING_CSV")

    if not frappe_token.lower().startswith("token "):
        frappe_token = f"token {frappe_token}"

    sn_allowlist_raw = _clean(os.getenv("SN_ALLOWLIST"))
    sn_allowlist = {s.strip() for s in sn_allowlist_raw.split(",") if s.strip()} if sn_allowlist_raw else set()

    # Unknown Bio ID catcher (optional): route unmatched punches to a dedicated Employee in Frappe.
    # Set UNKNOWN_EMPLOYEE_FIELD_VALUE to enable (recommended value: 'UNKNOWN').
    unknown_employee_field_value = _clean(os.getenv("UNKNOWN_EMPLOYEE_FIELD_VALUE", ""))
    unknown_comment_enabled = _as_int("UNKNOWN_COMMENT_ENABLED", 1)

    skip_auto_attendance = _as_int("SKIP_AUTO_ATTENDANCE", 1)
    max_attempts = _as_int("MAX_ATTEMPTS", 20)

    # How we populate Employee Checkin.device_id in Frappe.
    # Options:
    # - canonical_location_id (default)
    # - canonical_location_name
    # - canonical_location_id_and_name
    # - full (includes store code + SN + model)
    device_id_format = _clean(os.getenv("DEVICE_ID_FORMAT", "canonical_location_id")) or "canonical_location_id"

    # Admin token for protected endpoints (command queue). If empty, admin endpoints are disabled.
    admin_token = _clean(os.getenv("ADMIN_TOKEN", ""))

    cmd_max_attempts = _as_int("CMD_MAX_ATTEMPTS", 3)

    return Settings(
        database_url=database_url,
        frappe_base_url=frappe_base_url,
        frappe_token=frappe_token,
        sn_mapping_csv=sn_mapping_csv,
        sn_allowlist=sn_allowlist,
        skip_auto_attendance=skip_auto_attendance,
        max_attempts=max_attempts,
        unknown_employee_field_value=unknown_employee_field_value,
        unknown_comment_enabled=unknown_comment_enabled,
        device_id_format=device_id_format,
        admin_token=admin_token,
        cmd_max_attempts=cmd_max_attempts,
    )
