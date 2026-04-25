"""S223 Phase 1 verification gate."""
from __future__ import annotations

import pathlib
import re

register = pathlib.Path("output/s223/DEFECT_REGISTER.md").read_text(encoding="utf-8")

# Count store rows in the main table (rows that name a Pattern letter)
table_rows = [
    line
    for line in register.splitlines()
    if line.startswith("| ")
    and "Pattern" not in line
    and "---" not in line
    and "★" not in line.split("|")[0]  # don't double-count by ★ marker
]

# Each row has Pattern A / B / C / Allowed Skip — match by single-letter pattern column
pattern_rows = [
    line
    for line in table_rows
    if re.search(r"\|\s*(A|B|C|DEFECT-11|Allowed Skip|C / Allowed Skip)\s*\|", line)
]

assert len(pattern_rows) >= 13, (
    f"expected 13+ store rows in DEFECT_REGISTER table, got {len(pattern_rows)}"
)

# Each row must cite a fix file path (not "TBD")
for row in pattern_rows:
    cells = [c.strip() for c in row.split("|")]
    # cells: ['', '#', 'Store', 'Pattern', 'Layer', 'Element', 'Network call', 'Fix file', 'Cause', '']
    if len(cells) < 9:
        continue
    fix_cell = cells[7]
    assert fix_cell and "TBD" not in fix_cell, f"fix file path missing/TBD in row: {row[:100]}"

for pattern in ["Pattern A Investigation Summary", "Pattern B Investigation Summary", "Pattern C Investigation Summary"]:
    assert pattern in register, f"investigation summary missing for {pattern}"

print(f"PHASE 1 PASS — {len(pattern_rows)} store rows registered")
