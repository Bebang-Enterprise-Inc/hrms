"""Worker script: takes a reclassification JSON (from agent stdout) and applies it to MD YAML.

Expected JSON format:
[
  {
    "md_rel": "CORP_BEI/UNKNOWN/...md",
    "ai_label": "BIR 2303 Certificate of Registration — SM Megamall 2024",
    "ai_category": "BIR",
    "document_type": "BIR_2303",
    "permit_code_new": "BIR_2303",
    "short_description": "One-sentence description",
    "rename_to": "FORM_2303_SM_MEGAMALL_20241011_v1.md"
  },
  ...
]
"""
from __future__ import annotations
import argparse, json, re, shutil, sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
DD = ROOT / "CEO" / "Valuation" / "admin_compliance_dd"

YAML_UPDATE_KEYS = ["ai_label", "ai_category", "short_description", "document_type"]


def quote(v):
    if v is None:
        return "null"
    s = str(v)
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def update_md(md_path: Path, updates: dict) -> bool:
    text = md_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False
    parts = text.split("---", 2)
    if len(parts) < 3:
        return False
    fm_text, body = parts[1], parts[2]
    pairs = []
    seen = set()
    for line in fm_text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_]+):\s?(.*)$", line)
        if not m:
            continue
        k, v = m.group(1), m.group(2)
        if k in updates:
            v = quote(updates[k])
        seen.add(k)
        pairs.append((k, v))
    for k in YAML_UPDATE_KEYS:
        if k in updates and k not in seen:
            pairs.append((k, quote(updates[k])))
    new_text = "---\n" + "\n".join(f"{k}: {v}" for k, v in pairs) + "\n---\n" + body.lstrip("\n")
    md_path.write_text(new_text, encoding="utf-8")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("json_file", help="Path to JSON array of reclass updates")
    args = ap.parse_args()

    data = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    ok = err = renamed = 0
    for item in data:
        md_rel = item.get("md_rel")
        if not md_rel:
            err += 1
            continue
        md_path = DD / md_rel
        if not md_path.exists():
            print(f"MISS: {md_rel}")
            err += 1
            continue
        updates = {
            k: item.get(k)
            for k in YAML_UPDATE_KEYS
            if k in item and item.get(k) is not None
        }
        if update_md(md_path, updates):
            ok += 1
        # Optional rename
        rename_to = item.get("rename_to")
        if rename_to and rename_to != md_path.name:
            new_path = md_path.parent / rename_to
            if not new_path.exists():
                shutil.move(str(md_path), str(new_path))
                renamed += 1
    print(f"applied: ok={ok} renamed={renamed} err={err}")


if __name__ == "__main__":
    main()
