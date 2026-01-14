from __future__ import annotations

import json
from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class FrappeClient:
    base_url: str
    auth_header: str

    def _headers(self) -> dict:
        return {
            "Authorization": self.auth_header,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def add_checkin_by_attendance_device_id(
        self,
        *,
        attendance_device_id: str,
        timestamp: str,
        device_id: str | None,
        log_type: str | None,
        skip_auto_attendance: int = 1,
    ) -> dict:
        url = (
            self.base_url.rstrip("/")
            + "/api/method/hrms.hr.doctype.employee_checkin.employee_checkin.add_log_based_on_employee_field"
        )
        payload = {
            "employee_field_value": attendance_device_id,
            "timestamp": timestamp,
            "device_id": device_id,
            "log_type": log_type,
            "skip_auto_attendance": int(skip_auto_attendance),
        }
        r = requests.post(url, headers=self._headers(), data=json.dumps(payload), timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Frappe add_log_based_on_employee_field failed: {r.status_code} {r.text[:300]}")
        return (r.json() or {}).get("message") or {}

    def add_comment(self, *, reference_doctype: str, reference_name: str, content: str) -> dict:
        """Create a Frappe Comment row linked to a document."""
        url = self.base_url.rstrip("/") + "/api/resource/Comment"
        payload = {
            "comment_type": "Comment",
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "content": content,
        }
        r = requests.post(url, headers=self._headers(), data=json.dumps(payload), timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Frappe create Comment failed: {r.status_code} {r.text[:300]}")
        return (r.json() or {}).get("data") or {}
