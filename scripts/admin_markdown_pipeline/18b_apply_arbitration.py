"""Apply Opus arbitration.json files to staged MD files."""
from __future__ import annotations
import json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

ROOT = Path(__file__).resolve().parents[2]
MD = ROOT / "data" / "admin_markdown"
STAGING = MD / "_staging"
MANIFEST = MD / "_manifest.jsonl"
ARBLOG = MD / "_arbitration_log.jsonl"

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

BACKSLASH = "\\"
ESC_BACKSLASH = "\\\\"
DQUOTE = '"'
ESC_DQUOTE = '\\"'


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
    s = str(v).replace(BACKSLASH, ESC_BACKSLASH).replace(DQUOTE, ESC_DQUOTE)
    return f'"{s}"'


def main():
    file_map = {}
    if MANIFEST.exists():
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("file_id") and r.get("md_path"):
                file_map[r["file_id"]] = ROOT / r["md_path"]

    ok = skip = err = 0
    for stage in sorted(STAGING.iterdir()):
        arb_f = stage / "arbitration.json"
        if not arb_f.exists():
            skip += 1
            continue
        try:
            arb = json.loads(arb_f.read_text(encoding="utf-8"))
        except Exception:
            err += 1
            continue
        md_path = file_map.get(stage.name)
        if not md_path or not md_path.exists():
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
        pairs = []
        for line in fm.splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            m = re.match(r"^([A-Za-z0-9_]+):\s?(.*)$", line)
            if m:
                pairs.append((m.group(1), m.group(2)))
        fields = arb.get("fields") or {}
        updated = {}
        reasons = []
        sources = []
        for f, p in fields.items():
            k = CMAP.get(f)
            if not k:
                continue
            updated[k] = yesc(p.get("value"))
            reasons.append(f"- {f}: [{p.get('source_of_truth', 'opus')}] {(p.get('reasoning') or '').strip()}")
            sources.append((f, p.get("source_of_truth", "opus")))
        new_pairs = []
        for k, v in pairs:
            if k in updated:
                new_pairs.append((k, updated[k]))
            elif k == "validation_method":
                new_pairs.append((k, yesc("opus_arbitrated")))
            elif k == "opus_arbitration_reasoning":
                new_pairs.append((k, yesc("\n".join(reasons)) if reasons else yesc("")))
            elif k == "opus_source_of_truth":
                new_pairs.append((k, yesc(json.dumps(dict(sources), ensure_ascii=False))))
            elif k == "dd_ready":
                new_pairs.append((k, yesc(True)))
            else:
                new_pairs.append((k, v))
        md_path.write_text(
            "---\n" + "\n".join(f"{k}: {v}" for k, v in new_pairs) + "\n---\n\n" + body.lstrip(),
            encoding="utf-8",
        )
        with ARBLOG.open("a", encoding="utf-8") as fh:
            for f, p in fields.items():
                fh.write(
                    json.dumps(
                        {
                            "file_id": stage.name,
                            "field": f,
                            "value": p.get("value"),
                            "source_of_truth": p.get("source_of_truth"),
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
