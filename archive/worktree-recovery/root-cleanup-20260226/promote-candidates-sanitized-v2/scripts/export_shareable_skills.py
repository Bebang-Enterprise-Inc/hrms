#!/usr/bin/env python3
"""
Export sanitized, shareable skill files for external handoff.

Outputs:
- docs/skills-share/public-skills/<skill>/SKILL.md
- docs/skills-share/SHAREABLE_SKILLS_MANIFEST.md
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


DEFAULT_SKILLS = [
    "plan-audit",
    "fact-check",
    "write-plan",
    "architect-reviewer",
    "design-review",
    "team-planner",
    "teammates",
    "tasks",
    "find-conversations",
    "rlm",
    "adms",
    "playwright",
    "test-full-cycle",
    "deploy-frappe",
    "docx-designer",
    "xlsx",
    "save",
    "restore",
]


STATIC_REPLACEMENTS = [
    ("F:\\Dropbox\\Projects\\BEI-ERP", "<PROJECT_ROOT>"),
    ("C:\\Users\\Sam", "<USER_HOME>"),
    ("sam@bebang.ph", "<OWNER_EMAIL>"),
    ("my.bebang.ph", "<FRONTEND_HOST>"),
    ("hq.bebang.ph", "<BACKEND_HOST>"),
    ("bebang.ph", "<COMPANY_DOMAIN>"),
    ("Bebang Enterprise Inc.", "<COMPANY_NAME>"),
    ("BeiTest2026!", "<PASSWORD>"),
]


REGEX_REPLACEMENTS: List[Tuple[str, str]] = [
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "<EMAIL>"),
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<IP_ADDRESS>"),
    (r"\bi-[0-9a-f]{8,17}\b", "<AWS_INSTANCE_ID>"),
    (r"spaces/[A-Za-z0-9_-]+", "spaces/<SPACE_ID>"),
    (r"users/\d{6,}", "users/<USER_ID>"),
    (r"\bAKIA[0-9A-Z]{16}\b", "<AWS_ACCESS_KEY_ID>"),
    (r"\bAIza[0-9A-Za-z\-_]{35}\b", "<GOOGLE_API_KEY>"),
    (r"\bxox[baprs]-[A-Za-z0-9-]+\b", "<SLACK_TOKEN>"),
    (r"(?im)^(\s*(?:api[_ -]?key|secret|token|password)\s*[:=]\s*)(.+)$", r"\1<REDACTED>"),
    (r"(?i)\bbeitest\d{4}!\b", "<PASSWORD>"),
    (r"(?i)\bsamkarazi/[A-Za-z0-9._/-]+\b", "<DOCKER_IMAGE>"),
    (r"(?i)\bbebang[-_/][A-Za-z0-9._-]+\b", "<PROJECT_SLUG>"),
    (r"(?i)\bbebang\b", "<PROJECT_NAME>"),
    (r"[A-Z]:\\[^\s\"'`]+", "<ABS_PATH>"),
    (r"/(?:home|opt|etc|var|srv|usr|mnt|tmp)/[^\s\"'`]+", "<ABS_PATH>"),
]


@dataclass
class SkillResult:
    name: str
    source: str
    output: str
    replacements: int


def safe_display_path(path: Path, project_root: Path) -> str:
    try:
        rel = path.resolve().relative_to(project_root.resolve())
        return f"<PROJECT_ROOT>/{str(rel).replace('\\', '/')}"
    except Exception:
        return "<ABS_PATH>"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export sanitized shareable skills.")
    parser.add_argument(
        "--skills-file",
        default="docs/skills-share/SHAREABLE_SKILLS.txt",
        help="File containing skill names to export (one per line).",
    )
    parser.add_argument(
        "--output-root",
        default="docs/skills-share/public-skills",
        help="Output directory for sanitized skill folders.",
    )
    parser.add_argument(
        "--manifest",
        default="docs/skills-share/SHAREABLE_SKILLS_MANIFEST.md",
        help="Output manifest markdown path.",
    )
    return parser.parse_args()


def load_skill_names(path: Path) -> List[str]:
    if not path.exists():
        return list(DEFAULT_SKILLS)

    names: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        names.append(line)
    return names or list(DEFAULT_SKILLS)


def candidate_roots(project_root: Path) -> Iterable[Path]:
    yield project_root / ".claude" / "skills"
    yield project_root / ".agents" / "skills"
    yield project_root / ".agent" / "skills"
    yield Path.home() / ".claude" / "skills"
    yield Path.home() / ".agents" / "skills"


def resolve_skill_file(project_root: Path, skill_name: str) -> Path | None:
    for root in candidate_roots(project_root):
        candidate = root / skill_name / "SKILL.md"
        if candidate.exists():
            return candidate
    return None


def sanitize_text(text: str) -> Tuple[str, int]:
    total = 0
    out = text

    for before, after in STATIC_REPLACEMENTS:
        count = out.count(before)
        if count:
            out = out.replace(before, after)
            total += count

    for pattern, repl in REGEX_REPLACEMENTS:
        out, count = re.subn(pattern, repl, out)
        total += count

    return out, total


def write_manifest(
    path: Path,
    generated: str,
    results: List[SkillResult],
    missing: List[str],
) -> None:
    lines: List[str] = []
    lines.append("# Shareable Skills Manifest")
    lines.append("")
    lines.append(f"- Generated (UTC): `{generated}`")
    lines.append("- Output type: Sanitized `SKILL.md` only")
    lines.append("- Sensitive data policy: project/device/account identifiers replaced with placeholders")
    lines.append("")

    lines.append("## Exported Skills")
    lines.append("")
    lines.append("| Skill | Source | Output | Replacement Count |")
    lines.append("| --- | --- | --- | ---: |")
    for row in results:
        lines.append(
            f"| `{row.name}` | `{row.source}` | `{row.output}` | {row.replacements} |"
        )
    lines.append("")

    if missing:
        lines.append("## Missing Skills")
        lines.append("")
        for name in missing:
            lines.append(f"- `{name}`")
        lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- Review each sanitized output before external sharing.")
    lines.append("- If a placeholder missed sensitive context, add a new rule in `scripts/export_shareable_skills.py` and rerun.")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    project_root = Path.cwd()

    skills_file = Path(args.skills_file)
    skill_names = load_skill_names(skills_file)

    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    results: List[SkillResult] = []
    missing: List[str] = []

    for name in skill_names:
        src = resolve_skill_file(project_root, name)
        if src is None:
            missing.append(name)
            continue

        content = src.read_text(encoding="utf-8", errors="ignore")
        sanitized, replacements = sanitize_text(content)

        out_dir = output_root / name
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "SKILL.md"
        out_file.write_text(sanitized, encoding="utf-8")

        results.append(
            SkillResult(
                name=name,
                source=safe_display_path(src, project_root),
                output=safe_display_path(out_file, project_root),
                replacements=replacements,
            )
        )

    generated = datetime.now(timezone.utc).isoformat()
    manifest = Path(args.manifest)
    write_manifest(manifest, generated, results, missing)

    print(f"Exported: {len(results)} skills")
    print(f"Missing: {len(missing)} skills")
    print(f"Manifest: {manifest}")
    print(f"Output root: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
