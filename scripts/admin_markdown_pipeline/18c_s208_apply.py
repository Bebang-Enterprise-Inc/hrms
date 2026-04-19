"""S208 — Apply arbitration.json to DD-package MDs (agent-format variant).

Agents produced arbitration.json with this shape (top-level source_of_truth
and reasoning, flat field values):
  {
    "file_id": "...",
    "source_of_truth": "claude-opus-4-7",
    "reasoning": "...",
    "fields": {"document_type": "SEC_AOI", "psic_code": "56290", ...}
  }

This is a different shape than the original 18b_apply_arbitration.py expected
(per-field nested dicts). This script handles the agent format and writes
canonical_* fields into the MD frontmatter.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

ROOT = Path(__file__).resolve().parents[2]
DD = ROOT / "CEO" / "Valuation" / "admin_compliance_dd"
STAGING = DD / "_staging"
MANIFEST = DD / "_manifest.jsonl"
ARBLOG = DD / "_arbitration_log.jsonl"
PICKS = ROOT / ".scratch" / "s208_picks.json"

CMAP = {
    "document_type": "document_type",
    "business_name": "canonical_business_name",
    "trade_name": "canonical_trade_name",
    "permit_number": "canonical_permit_number",
    "tin": "canonical_tin",
    "ocn": "canonical_ocn",
    "psic_code": "canonical_psic_code",
    "issuing_authority": "canonical_issuing_authority",
    "issue_date": "canonical_issue_date",
    "expiry_date": "canonical_expiry_date",
    "location_address": "canonical_location_address",
    "registered_address": "canonical_registered_address",
    "signatories": "canonical_signatories",
}


def yesc(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return json.dumps(v)
    if isinstance(v, list):
        return "[]" if not v else json.dumps(v, ensure_ascii=False)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    s = str(v).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def load_s208_file_map() -> dict[str, Path]:
    """file_id → md_path from manifest, restricted to S208 picks."""
    picks = json.loads(PICKS.read_text(encoding="utf-8"))
    pick_ids = {p["file_id"] for p in picks}
    out: dict[str, Path] = {}
    if not MANIFEST.exists():
        return out
    with MANIFEST.open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            fid = r.get("file_id")
            if fid in pick_ids and r.get("status") == "ok" and r.get("md_path"):
                out[fid] = ROOT / r["md_path"]
    return out


def main() -> None:
    file_map = load_s208_file_map()
    print(f"S208 picks with md_path in manifest: {len(file_map)}")

    ok = skip = err = 0
    with ARBLOG.open("a", encoding="utf-8") as log_fh:
        for fid, md_path in sorted(file_map.items()):
            stage = STAGING / fid
            arb_f = stage / "arbitration.json"
            if not arb_f.exists():
                skip += 1
                continue
            try:
                arb = json.loads(arb_f.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"ERR parse {fid}: {e}")
                err += 1
                continue
            if not md_path.exists():
                print(f"ERR missing MD: {md_path}")
                err += 1
                continue

            text = md_path.read_text(encoding="utf-8")
            if not text.startswith("---"):
                err += 1
                continue
            parts = text.split("---", 2)
            if len(parts) < 3:
                err += 1
                continue
            _, fm, body = parts

            pairs: list[tuple[str, str]] = []
            for line in fm.splitlines():
                if not line.strip() or line.startswith("#"):
                    continue
                m = re.match(r"^([A-Za-z0-9_]+):\s?(.*)$", line)
                if m:
                    pairs.append((m.group(1), m.group(2)))

            fields = arb.get("fields") or {}
            source_of_truth = arb.get("source_of_truth", "claude-opus-4-7")
            reasoning = (arb.get("reasoning") or "").strip()

            updated: dict[str, str] = {}
            for f, val in fields.items():
                k = CMAP.get(f)
                if not k:
                    continue
                updated[k] = yesc(val)

            new_pairs: list[tuple[str, str]] = []
            for k, v in pairs:
                if k in updated:
                    new_pairs.append((k, updated[k]))
                elif k == "validation_method":
                    new_pairs.append((k, yesc("opus_arbitrated")))
                elif k == "opus_arbitration_reasoning":
                    new_pairs.append((k, yesc(reasoning)))
                elif k == "opus_source_of_truth":
                    new_pairs.append((k, yesc(source_of_truth)))
                elif k == "dd_ready":
                    new_pairs.append((k, yesc(True)))
                else:
                    new_pairs.append((k, v))

            md_path.write_text(
                "---\n" + "\n".join(f"{k}: {v}" for k, v in new_pairs) + "\n---\n\n" + body.lstrip(),
                encoding="utf-8",
            )
            # Log each field applied
            for f, val in fields.items():
                log_fh.write(
                    json.dumps(
                        {
                            "file_id": fid,
                            "field": f,
                            "value": val,
                            "source_of_truth": source_of_truth,
                            "sprint": "S208",
                            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            ok += 1

    print(f"applied: ok={ok} skip={skip} err={err}")


if __name__ == "__main__":
    main()
