"""Patch (a) — per-field-type size multipliers in Documenso's envelope-editor bundle.

PROBLEM
-------
Documenso ships with one default field size (90×30 CSS px) for ALL field types.
BEI signers need bigger signature fields and wider email/name fields so the placed
field actually fits the content.

The sizing happens inside the click-handler in
`envelope-editor-renderer-provider-wrapper-<hash>.js`. The original line is:

    const X=REF.current.width/W*100,Y=REF.current.height/H*100;

Variable names are minified; the bundle filename hash changes per release. The
sizing line shape is stable.

FIX
---
Insert `_fw` (width multipliers) and `_fh` (height multipliers) lookup tables,
then apply them via the field-type variable:

    const _fw={"SIGNATURE":2.4,"FREE_SIGNATURE":2.4,"EMAIL":3.1,"NAME":2.4,
               "DATE":1.5,"TEXT":2.2,"NUMBER":1.3},
          _fh={"SIGNATURE":2.4,"FREE_SIGNATURE":2.4,"EMAIL":0.8,"NAME":0.8,
               "DATE":0.8,"TEXT":0.8,"NUMBER":0.8},
          X=(_fw[FIELDTYPE]||1)*REF.current.width/W*100,
          Y=(_fh[FIELDTYPE]||1)*REF.current.height/H*100;

The field-type variable is found by looking at the nearby `type:VAR` in the
form-data object the click-handler returns. Field types not in the maps get
multiplier 1 (default 90×30 px).

Multipliers were chosen to match DocuSign / Adobe Sign / Dropbox Sign defaults
for A4 documents.

USAGE
-----
    python patch_field_sizes.py --target /path/to/bundle.js
    python patch_field_sizes.py --target /path/to/bundle.js --verify-only
    python patch_field_sizes.py --search-root /app/apps/remix/build/client/assets
    python patch_field_sizes.py --search-root /app/apps/remix/build/client/assets --verify-only

In the Dockerfile this is invoked with --search-root so the bundle is auto-discovered
regardless of the filename hash.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

# Width multipliers (on base 90px = field default)
FW = {
    "SIGNATURE": 2.4,       # 216px — drawn signature needs horizontal room
    "FREE_SIGNATURE": 2.4,
    "EMAIL": 3.1,           # 279px — fits firstname.lastname@company.com
    "NAME": 2.4,            # 216px — fits Filipino names (25+ chars)
    "DATE": 1.5,            # 135px — fits "2026-03-27" or "March 27, 2026"
    "TEXT": 2.2,            # 198px — wider for notes/comments
    "NUMBER": 1.3,          # 117px — fits amounts with commas
}

# Height multipliers (on base 30px = field default)
FH = {
    "SIGNATURE": 2.4,       # 72px — room for handwriting
    "FREE_SIGNATURE": 2.4,
    "EMAIL": 0.8,           # 24px — single line
    "NAME": 0.8,
    "DATE": 0.8,
    "TEXT": 0.8,
    "NUMBER": 0.8,
}

# The sizing line we expect to find in the unpatched bundle.
# Matches: const VAR1=VAR2.current.width/VAR3*100,VAR4=VAR5.current.height/VAR6*100;
SIZING_RE = re.compile(
    r"const (\w+)=(\w+)\.current\.width/(\w+)\*100,(\w+)=(\w+)\.current\.height/(\w+)\*100;"
)

# Marker that the patch is already applied
PATCH_MARKER = "_fw["

# Bundle filename pattern (the hash suffix changes per release)
BUNDLE_GLOB = "envelope-editor-renderer-provider-wrapper-*.js"


def fw_literal() -> str:
    return "{" + ",".join(f'"{k}":{v}' for k, v in FW.items()) + "}"


def fh_literal() -> str:
    return "{" + ",".join(f'"{k}":{v}' for k, v in FH.items()) + "}"


def find_field_type_var(content: str, after_idx: int) -> str | None:
    """Find the variable that holds the field type string, scanning forward from after_idx."""
    # The click-handler returns a form-data object that includes `type:VAR`.
    # Look for the first `type:<identifier>` after the sizing line.
    m = re.search(r"type:(\w+)", content[after_idx:after_idx + 800])
    return m.group(1) if m else None


def detect_state(content: str) -> str:
    """Return 'patched' / 'unpatched' / 'unknown'."""
    if PATCH_MARKER in content:
        return "patched"
    if SIZING_RE.search(content):
        return "unpatched"
    return "unknown"


def apply_patch(content: str) -> tuple[str, str]:
    """Return (new_content, message). Raises ValueError if the patch can't be applied."""
    m = SIZING_RE.search(content)
    if not m:
        raise ValueError("Sizing pattern not found — bundle layout has changed upstream.")

    field_type_var = find_field_type_var(content, m.end())
    if not field_type_var:
        raise ValueError(
            "Could not locate the field-type variable (`type:VAR`) after the sizing line. "
            "Bundle layout has changed upstream."
        )

    old = m.group(0)
    V1, R1, W, V2, R2, H = m.groups()
    # R1 and R2 should be the same ref (e.g. both `D` or both `S`); we use R1 in the replacement.
    new = (
        f"const _fw={fw_literal()},"
        f"_fh={fh_literal()},"
        f"{V1}=(_fw[{field_type_var}]||1)*{R1}.current.width/{W}*100,"
        f"{V2}=(_fh[{field_type_var}]||1)*{R1}.current.height/{H}*100;"
    )
    new_content = content.replace(old, new, 1)
    if PATCH_MARKER not in new_content:
        raise ValueError("Replacement did not take effect — internal error.")
    return new_content, f"OK: patched (field-type variable = `{field_type_var}`)"


def resolve_target(target: str | None, search_root: str | None) -> pathlib.Path:
    """Locate the file to patch."""
    if target:
        p = pathlib.Path(target)
        if not p.is_file():
            raise FileNotFoundError(f"--target file not found: {target}")
        return p
    if not search_root:
        raise ValueError("Must give either --target FILE or --search-root DIR.")
    root = pathlib.Path(search_root)
    if not root.is_dir():
        raise FileNotFoundError(f"--search-root not a directory: {search_root}")
    matches = sorted(p for p in root.glob(BUNDLE_GLOB) if not p.name.endswith(".map"))
    if not matches:
        raise FileNotFoundError(
            f"No {BUNDLE_GLOB} under {search_root}. Build layout may have changed."
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple bundles match {BUNDLE_GLOB} under {search_root}: {[str(p) for p in matches]}. "
            "Pass --target explicitly."
        )
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--target", help="Path to the bundle file to patch.")
    parser.add_argument(
        "--search-root",
        help=(
            "Directory to glob for envelope-editor-renderer-provider-wrapper-*.js. "
            "Typically /app/apps/remix/build/client/assets inside the Documenso container."
        ),
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Report current patch state without modifying anything. Exits 0 if patched, 1 otherwise.",
    )
    args = parser.parse_args()

    try:
        target = resolve_target(args.target, args.search_root)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    content = target.read_text(encoding="utf-8")
    state = detect_state(content)
    print(f"target: {target}")
    print(f"state:  {state}")

    if args.verify_only:
        return 0 if state == "patched" else 1

    if state == "patched":
        print("Already patched. No changes made.")
        return 0
    if state == "unknown":
        print(
            "ERROR: Bundle does not match the expected unpatched OR patched shape. "
            "Documenso may have changed the click-handler layout upstream.",
            file=sys.stderr,
        )
        return 3

    try:
        new_content, msg = apply_patch(content)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3

    target.write_text(new_content, encoding="utf-8")
    print(msg)
    print(f"wrote: {target} ({len(new_content)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
