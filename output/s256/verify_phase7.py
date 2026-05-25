"""Phase 7 verification — /finance-ap training refresh."""
import os, sys, hashlib

def file_sha256(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()

def main():
    errors = []
    base = '.claude/skills/finance-ap/references/team-training-2026-05-14.md'
    mirrors = [
        '.claude/skills/finance-ap/references/team-training-2026-05-14.md',
        '.agent/skills/finance-ap/references/team-training-2026-05-14.md',
        '.agents/skills/finance-ap/references/team-training-2026-05-14.md',
    ]

    # Check training doc has required content
    content = open(base, encoding='utf-8').read()
    checks = [
        ('96 / 96', 'Lock count bumped to 96/96'),
        ('Joevic', 'Joevic added to per-role section'),
        ('S255', 'S255 deployed entry'),
        ('S256', 'S256 in-flight entry'),
        ('Bridge', 'Bridge access documented'),
    ]
    for keyword, desc in checks:
        if keyword not in content:
            errors.append(f"Missing in training doc: {desc} (keyword: '{keyword}')")

    # Check mirrors match
    hashes = [file_sha256(m) for m in mirrors]
    if len(set(hashes)) > 1:
        errors.append(f"Mirror mismatch: {hashes}")

    # Check SKILL.md updated
    skill = open('.claude/skills/finance-ap/SKILL.md', encoding='utf-8').read()
    if 'PII audit' not in skill:
        errors.append("SKILL.md missing PII audit outcome")

    if errors:
        print("PHASE 7 VERIFY FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"PHASE 7 VERIFY: ALL PASS (3 mirrors sha256={hashes[0][:16]}...)")
    return 0

if __name__ == '__main__':
    sys.exit(main())
