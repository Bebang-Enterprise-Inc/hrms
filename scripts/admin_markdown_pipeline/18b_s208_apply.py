"""S208 — Apply arbitration.json to MDs in CEO/Valuation/admin_compliance_dd/.

Wraps 18b_apply_arbitration.py with paths pointed at the DD package location.
"""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "admin_markdown_pipeline"))

spec = importlib.util.spec_from_file_location(
    "_apply_arb",
    ROOT / "scripts" / "admin_markdown_pipeline" / "18b_apply_arbitration.py",
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules["_apply_arb"] = mod
spec.loader.exec_module(mod)

DD = ROOT / "CEO" / "Valuation" / "admin_compliance_dd"
mod.MD = DD
mod.STAGING = DD / "_staging"
mod.MANIFEST = DD / "_manifest.jsonl"
mod.ARBLOG = DD / "_arbitration_log.jsonl"

if __name__ == "__main__":
    mod.main()
