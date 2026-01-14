from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DeviceInfo:
    row_num: str
    canonical_location_id: str
    canonical_location_name: str
    canonical_location_kind: str
    canonical_store_code: str
    device_model: str
    device_serial_number: str


@dataclass(frozen=True)
class DeviceMapping:
    sn_to_device_id: dict[str, str]
    sn_to_info: dict[str, DeviceInfo]

    def frappe_device_id(self, sn: str, *, device_id_format: str) -> str | None:
        info = self.sn_to_info.get(sn)
        if not info:
            return None

        fmt = (device_id_format or "").strip().lower() or "canonical_location_id"

        if fmt == "canonical_location_id":
            return info.canonical_location_id
        if fmt == "canonical_location_name":
            return info.canonical_location_name or info.canonical_location_id
        if fmt == "canonical_location_id_and_name":
            if info.canonical_location_name:
                return f"{info.canonical_location_id} ({info.canonical_location_name})"
            return info.canonical_location_id
        if fmt == "full":
            parts: list[str] = [info.canonical_location_id]
            if info.canonical_location_name:
                parts.append(info.canonical_location_name)
            if info.canonical_store_code:
                parts.append(f"store_code={info.canonical_store_code}")
            parts.append(f"sn={info.device_serial_number}")
            if info.device_model:
                parts.append(f"model={info.device_model}")
            return " | ".join(parts)

        # Unknown format: fall back safely.
        return info.canonical_location_id


def load_sn_mapping(csv_path: str) -> DeviceMapping:
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(f"SN mapping CSV not found: {csv_path}")

    sn_to_device_id: dict[str, str] = {}
    sn_to_info: dict[str, DeviceInfo] = {}

    with p.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sn = (row.get("device_serial_number") or "").strip()
            canonical_id = (row.get("canonical_location_id") or "").strip()

            if not sn or not canonical_id:
                continue

            info = DeviceInfo(
                row_num=(row.get("row_num") or "").strip(),
                canonical_location_id=canonical_id,
                canonical_location_name=(row.get("canonical_location_name") or "").strip(),
                canonical_location_kind=(row.get("canonical_location_kind") or "").strip(),
                canonical_store_code=(row.get("canonical_store_code") or "").strip(),
                device_model=(row.get("device_model") or "").strip(),
                device_serial_number=sn,
            )

            sn_to_device_id[sn] = canonical_id
            sn_to_info[sn] = info

    if not sn_to_device_id:
        raise RuntimeError(f"No SN mappings loaded from {csv_path}")

    return DeviceMapping(sn_to_device_id=sn_to_device_id, sn_to_info=sn_to_info)
