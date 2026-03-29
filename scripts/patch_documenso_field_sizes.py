#!/usr/bin/env python3
"""
Patch Documenso client bundle for custom field sizes.

Updates per-field-type sizing:
- Signature: 2.4x width, 2.4x height (216x72px)
- Email: 3.1x width, 0.8x height (279x24px)
- Name: 2.4x width, 0.8x height (216x24px)
- Date: 1.5x width, 0.8x height (135x24px)
- TEXT: 4.4x width, 3.2x height (396x96px — 4 lines)
- Number: 1.3x width, 0.8x height (117x24px)
- RADIO: 2.0x width, 4.0x height (180x120px — 4 options)
- CHECKBOX: 2.0x width, 4.0x height (180x120px — 4 options)

Usage:
  python3 patch_documenso_field_sizes.py /path/to/envelope-editor-*.js
"""

import sys
import os

def patch_client_bundle(filename):
    """Apply field size patch to Documenso client bundle."""

    if not os.path.exists(filename):
        print(f"ERROR: File not found: {filename}")
        sys.exit(1)

    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Safety check: MutationObserver must be unchanged
    if 'D.current={height:Math.max(al),width:Math.max(ll)}' not in content:
        print("ERROR: MutationObserver signature not found. Aborting.")
        sys.exit(1)

    # Safety check: no broken patches from previous iterations
    if 'ee==="SIGNATURE"' in content:
        print("ERROR: Broken patch detected (ee==='SIGNATURE'). Aborting.")
        sys.exit(1)

    # Original click handler line
    old_line = 'const E=D.current.width/me*100,I=D.current.height/ce*100;'

    if old_line not in content:
        print("ERROR: Click handler signature not found. Aborting.")
        sys.exit(1)

    # New click handler with per-field-type sizing
    new_line = (
        'const _fw={"SIGNATURE":2.4,"FREE_SIGNATURE":2.4,"EMAIL":3.1,"NAME":2.4,"DATE":1.5,'
        '"TEXT":4.4,"NUMBER":1.3,"RADIO":2.0,"CHECKBOX":2.0},'
        '_fh={"SIGNATURE":2.4,"FREE_SIGNATURE":2.4,"EMAIL":0.8,"NAME":0.8,"DATE":0.8,'
        '"TEXT":3.2,"NUMBER":0.8,"RADIO":4.0,"CHECKBOX":4.0},'
        'E=(_fw[p]||1)*D.current.width/me*100,I=(_fh[p]||1)*D.current.height/ce*100;'
    )

    # Apply patch
    count = content.count(old_line)
    if count != 1:
        print(f"ERROR: Found {count} occurrences of click handler (expected 1). Aborting.")
        sys.exit(1)

    content = content.replace(old_line, new_line)

    # Safety check: patch must be applied
    if '_fw[p]' not in content:
        print("ERROR: Patch application failed. Aborting.")
        sys.exit(1)

    # Write patched file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"SUCCESS: Patched {os.path.basename(filename)}")
    print(f"  TEXT: width 4.4x (396px), height 3.2x (96px)")
    print(f"  RADIO: width 2.0x (180px), height 4.0x (120px)")
    print(f"  CHECKBOX: width 2.0x (180px), height 4.0x (120px)")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    patch_client_bundle(sys.argv[1])
