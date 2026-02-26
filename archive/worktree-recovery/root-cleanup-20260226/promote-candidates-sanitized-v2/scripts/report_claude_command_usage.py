#!/usr/bin/env python3
"""
Claude session command/skill usage analyzer.

Purpose:
- Find explicit slash commands from <command-name> / <command-message> tags.
- Find inline /command mentions in user text (first few lines).
- Find "Base directory for this skill" markers to detect loaded skills even
  when no explicit command tag was logged.

Outputs:
- JSON report with counts, time windows, and sample evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set


COMMAND_NAME_RE = re.compile(
    r"<command-name>\s*/?([a-zA-Z][a-zA-Z0-9:_-]*)\s*</command-name>",
    re.IGNORECASE,
)
COMMAND_MESSAGE_RE = re.compile(
    r"<command-message>\s*/?([a-zA-Z][a-zA-Z0-9:_-]*)\s*</command-message>",
    re.IGNORECASE,
)
INLINE_SLASH_RE = re.compile(r"(?<![A-Za-z0-9_])/([a-zA-Z][a-zA-Z0-9:_-]{1,64})")
BASE_SKILL_RE = re.compile(
    r"Base directory for this skill:\s*([^\r\n]+?skills[\\/][^\r\n\\/]+)",
    re.IGNORECASE,
)


def parse_ts(ts_raw: str) -> Optional[datetime]:
    if not ts_raw:
        return None
    try:
        if ts_raw.endswith("Z"):
            ts_raw = ts_raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def iter_jsonl_files(root: Path) -> Iterable[Path]:
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.endswith(".jsonl"):
                yield Path(dirpath) / fn


def get_user_text(message_content) -> str:
    if isinstance(message_content, str):
        return message_content

    if isinstance(message_content, list):
        parts: List[str] = []
        for item in message_content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)

    return ""


def normalize_command(cmd: str) -> str:
    return cmd.strip().lstrip("/").lower()


def shorten(text: str, limit: int = 180) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def yes_no(flag: bool) -> str:
    return "Yes" if flag else "No"


def md_escape(value: object) -> str:
    text = str(value)
    return text.replace("|", "\\|")


def build_markdown_report(
    report: dict,
    commands_rows: List[dict],
    loaded_rows: List[dict],
    skill_evidence: List[dict],
    top_n: int,
) -> str:
    lines: List[str] = []
    lines.append("# Skill Usage Last 30 Days")
    lines.append("")
    lines.append(f"- Generated (UTC): `{report['generated_at_utc']}`")
    lines.append(f"- Window: `{report['window_start_utc']}` to `{report['window_end_utc']}`")
    lines.append(
        f"- Project Filter: `{report['filters'].get('project_filter') or '(none - all projects)'}`"
    )
    lines.append(
        f"- Claude Projects Root: `{report['filters'].get('claude_projects_root')}`"
    )
    lines.append("")

    meta = report.get("meta", {})
    lines.append("## Scan Summary")
    lines.append("")
    lines.append(f"- Files scanned: `{meta.get('files_scanned', 0)}`")
    lines.append(f"- Lines scanned: `{meta.get('lines_scanned', 0)}`")
    lines.append(f"- User messages scanned: `{meta.get('messages_user_scanned', 0)}`")
    lines.append(
        f"- Non-user events scanned: `{meta.get('messages_non_user_scanned', 0)}`"
    )
    lines.append(f"- In-window messages/events: `{meta.get('messages_in_window', 0)}`")
    lines.append(f"- JSON parse errors: `{meta.get('json_parse_errors', 0)}`")
    lines.append("")

    lines.append("## Top Commands Detected")
    lines.append("")
    lines.append(
        "| Rank | Command | Count | Explicit Tags | Inline | Sessions | Known Skill |"
    )
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | --- |")
    for idx, row in enumerate(commands_rows[:top_n], start=1):
        source_counts = row.get("source_counts", {})
        explicit = int(source_counts.get("command_name_tag", 0)) + int(
            source_counts.get("command_message_tag", 0)
        )
        inline = int(source_counts.get("inline_slash_token", 0))
        lines.append(
            "| "
            + " | ".join(
                [
                    str(idx),
                    md_escape(row.get("name", "")),
                    str(row.get("count", 0)),
                    str(explicit),
                    str(inline),
                    str(row.get("sessions", 0)),
                    yes_no(bool(row.get("is_known_skill", False))),
                ]
            )
            + " |"
        )
    lines.append("")

    lines.append("## Top Skills Loaded (Base Markers)")
    lines.append("")
    lines.append("| Rank | Skill | Count | Sessions | Known Skill |")
    lines.append("| --- | --- | ---: | ---: | --- |")
    for idx, row in enumerate(loaded_rows[:top_n], start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(idx),
                    md_escape(row.get("name", "")),
                    str(row.get("count", 0)),
                    str(row.get("sessions", 0)),
                    yes_no(bool(row.get("is_known_skill", False))),
                ]
            )
            + " |"
        )
    lines.append("")

    known_evidence = [
        row
        for row in skill_evidence
        if row.get("is_known_skill")
        and (row.get("command_count", 0) > 0 or row.get("base_marker_count", 0) > 0)
    ]
    lines.append("## Known Skill Evidence")
    lines.append("")
    lines.append("| Rank | Skill | Command Count | Base Marker Count | Evidence Type |")
    lines.append("| --- | --- | ---: | ---: | --- |")
    for idx, row in enumerate(known_evidence[:top_n], start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(idx),
                    md_escape(row.get("skill", "")),
                    str(row.get("command_count", 0)),
                    str(row.get("base_marker_count", 0)),
                    md_escape(row.get("evidence_type", "")),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append(
        "- Command counts include explicit command tags and short inline `/command` usage."
    )
    lines.append(
        "- Base marker counts come from `Base directory for this skill:` entries."
    )
    lines.append(
        "- Alias naming matters (example: `/chat` vs `/chat-bei-erp`)."
    )
    lines.append("")

    return "\n".join(lines)


def load_known_skills(skill_roots: List[Path]) -> Set[str]:
    names: Set[str] = set()
    for root in skill_roots:
        if not root.exists() or not root.is_dir():
            continue
        for child in root.iterdir():
            if child.is_dir():
                names.add(child.name.lower())
    return names


def extract_skill_name_from_path(raw_path: str) -> Optional[str]:
    path = raw_path.strip().rstrip("\\/").replace("\\", "/")
    parts = path.split("/")
    if not parts:
        return None
    return parts[-1].lower()


@dataclass
class ItemStat:
    count: int = 0
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    sessions: Set[str] = field(default_factory=set)
    source_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    samples: List[Dict[str, str]] = field(default_factory=list)

    def add(self, ts: datetime, session_id: str, source: str, preview: str) -> None:
        iso = ts.isoformat()
        self.count += 1
        if self.first_seen is None or iso < self.first_seen:
            self.first_seen = iso
        if self.last_seen is None or iso > self.last_seen:
            self.last_seen = iso
        if session_id:
            self.sessions.add(session_id)
        self.source_counts[source] += 1
        if len(self.samples) < 3:
            self.samples.append(
                {
                    "timestamp": iso,
                    "session_id": session_id,
                    "source": source,
                    "preview": preview,
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Report Claude command/skill usage.")
    parser.add_argument(
        "--claude-projects-root",
        default=str(Path.home() / ".claude" / "projects"),
        help="Root directory containing Claude project session logs (.jsonl).",
    )
    parser.add_argument(
        "--project-filter",
        default="",
        help="Optional cwd substring filter (case-insensitive), e.g. F:\\Dropbox\\Projects\\BEI-ERP",
    )
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days.")
    parser.add_argument(
        "--after",
        default="",
        help="Override start timestamp (ISO-8601, UTC recommended).",
    )
    parser.add_argument(
        "--before",
        default="",
        help="Optional end timestamp (ISO-8601, UTC recommended).",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional output path for JSON report.",
    )
    parser.add_argument(
        "--output-md",
        default="",
        help="Optional output path for markdown summary report.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=25,
        help="Top N rows per markdown table (default: 25).",
    )
    parser.add_argument(
        "--inline-all",
        action="store_true",
        help="Count all inline /tokens (default: only known skills to avoid noisy XML-like fields).",
    )
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=max(args.days, 0))
    window_end = now

    if args.after:
        parsed_after = parse_ts(args.after)
        if parsed_after is None:
            raise SystemExit(f"Invalid --after value: {args.after}")
        window_start = parsed_after

    if args.before:
        parsed_before = parse_ts(args.before)
        if parsed_before is None:
            raise SystemExit(f"Invalid --before value: {args.before}")
        window_end = parsed_before

    if window_end < window_start:
        raise SystemExit("--before must be >= --after/window start")

    projects_root = Path(args.claude_projects_root)
    if not projects_root.exists():
        raise SystemExit(f"Claude projects root not found: {projects_root}")

    cwd_filter = args.project_filter.lower().strip()

    # Known skill roots: global + optional local project + current repo local.
    skill_roots: List[Path] = [Path.home() / ".claude" / "skills"]
    if args.project_filter:
        skill_roots.append(Path(args.project_filter) / ".claude" / "skills")
    skill_roots.append(Path.cwd() / ".claude" / "skills")
    known_skills = load_known_skills(skill_roots)

    command_stats: Dict[str, ItemStat] = defaultdict(ItemStat)
    skill_load_stats: Dict[str, ItemStat] = defaultdict(ItemStat)

    meta = {
        "files_scanned": 0,
        "lines_scanned": 0,
        "json_parse_errors": 0,
        "messages_user_scanned": 0,
        "messages_non_user_scanned": 0,
        "messages_in_window": 0,
    }

    for file_path in iter_jsonl_files(projects_root):
        meta["files_scanned"] += 1
        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                for raw_line in f:
                    meta["lines_scanned"] += 1
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        meta["json_parse_errors"] += 1
                        continue

                    event_type = str(obj.get("type") or "").lower()
                    if event_type == "user":
                        meta["messages_user_scanned"] += 1
                    else:
                        meta["messages_non_user_scanned"] += 1

                    ts = parse_ts(obj.get("timestamp", ""))
                    if ts is None or ts < window_start or ts > window_end:
                        continue

                    cwd = (obj.get("cwd") or "").lower()
                    if cwd_filter and cwd_filter not in cwd:
                        continue

                    msg = obj.get("message") or {}
                    text = ""
                    if isinstance(msg, dict):
                        text = get_user_text(msg.get("content"))
                    elif isinstance(msg, str):
                        text = msg

                    if not text:
                        text = get_user_text(obj.get("content"))
                    if not text:
                        continue

                    meta["messages_in_window"] += 1
                    session_id = obj.get("sessionId", "")
                    preview = shorten(text)

                    # 1) Explicit command tags.
                    tagged_cmds: Set[str] = set()
                    if event_type == "user":
                        for m in COMMAND_NAME_RE.finditer(text):
                            cmd = normalize_command(m.group(1))
                            tagged_cmds.add(cmd)
                            command_stats[cmd].add(ts, session_id, "command_name_tag", preview)
                        for m in COMMAND_MESSAGE_RE.finditer(text):
                            cmd = normalize_command(m.group(1))
                            tagged_cmds.add(cmd)
                            command_stats[cmd].add(ts, session_id, "command_message_tag", preview)

                    # 2) Skill base-directory markers (strong evidence of loaded skill).
                    for m in BASE_SKILL_RE.finditer(text):
                        raw_path = m.group(1).strip()
                        skill = extract_skill_name_from_path(raw_path)
                        if not skill:
                            continue
                        skill_load_stats[skill].add(
                            ts, session_id, "base_skill_marker", shorten(raw_path)
                        )

                    # 3) Inline slash tokens in the first lines when no explicit tag.
                    if (
                        event_type == "user"
                        and
                        not tagged_cmds
                        and "Base directory for this skill:" not in text
                        and "<" not in text
                        and ">" not in text
                    ):
                        # Only treat short conversational inputs as inline command candidates.
                        # Large pasted prompts/memory dumps create false positives.
                        stripped = text.strip()
                        line_count = len([ln for ln in text.splitlines() if ln.strip()])
                        if len(stripped) > 500 or line_count > 3:
                            continue

                        first_line = ""
                        for ln in text.splitlines():
                            if ln.strip():
                                first_line = ln.strip()
                                break
                        if not first_line:
                            continue

                        for m in INLINE_SLASH_RE.finditer(first_line):
                            cmd = normalize_command(m.group(1))
                            if not args.inline_all and cmd not in known_skills:
                                continue
                            command_stats[cmd].add(ts, session_id, "inline_slash_token", preview)

        except Exception:
            meta["json_parse_errors"] += 1

    def serialize_stats(stats_map: Dict[str, ItemStat], known_lookup: Set[str]) -> List[dict]:
        rows: List[dict] = []
        for name, stat in stats_map.items():
            rows.append(
                {
                    "name": f"/{name}",
                    "count": stat.count,
                    "first_seen": stat.first_seen,
                    "last_seen": stat.last_seen,
                    "sessions": len(stat.sessions),
                    "is_known_skill": name in known_lookup,
                    "source_counts": dict(sorted(stat.source_counts.items())),
                    "samples": stat.samples,
                }
            )
        rows.sort(key=lambda x: (-x["count"], x["name"]))
        return rows

    commands_rows = serialize_stats(command_stats, known_skills)
    loaded_rows = serialize_stats(skill_load_stats, known_skills)

    # Build evidence table: skills loaded but not explicitly tagged.
    command_count_by_skill = {r["name"].lstrip("/"): r["count"] for r in commands_rows}
    loaded_count_by_skill = {r["name"].lstrip("/"): r["count"] for r in loaded_rows}
    all_skill_names = sorted(set(command_count_by_skill) | set(loaded_count_by_skill))
    skill_evidence = []
    for skill in all_skill_names:
        command_count = command_count_by_skill.get(skill, 0)
        load_count = loaded_count_by_skill.get(skill, 0)
        if load_count > 0 and command_count == 0:
            reason = "loaded_without_explicit_command_tag"
        elif load_count == 0 and command_count > 0:
            reason = "explicit_command_without_base_marker"
        elif load_count > 0 and command_count > 0:
            reason = "both"
        else:
            reason = "none"
        skill_evidence.append(
            {
                "skill": f"/{skill}",
                "command_count": command_count,
                "base_marker_count": load_count,
                "evidence_type": reason,
                "is_known_skill": skill in known_skills,
            }
        )
    skill_evidence.sort(key=lambda x: (-(x["command_count"] + x["base_marker_count"]), x["skill"]))

    report = {
        "generated_at_utc": now.isoformat(),
        "window_start_utc": window_start.isoformat(),
        "window_end_utc": window_end.isoformat(),
        "filters": {
            "claude_projects_root": str(projects_root),
            "project_filter": args.project_filter,
        },
        "meta": meta,
        "known_skill_roots": [str(p) for p in skill_roots if p.exists()],
        "known_skills_count": len(known_skills),
        "commands_detected": commands_rows,
        "skills_loaded_via_base_marker": loaded_rows,
        "skill_evidence": skill_evidence,
    }

    output_json = args.output_json.strip()
    if output_json:
        out_json = Path(output_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Report written: {out_json}")
    else:
        print(json.dumps(report, indent=2))

    output_md = args.output_md.strip()
    if output_md:
        md = build_markdown_report(
            report=report,
            commands_rows=commands_rows,
            loaded_rows=loaded_rows,
            skill_evidence=skill_evidence,
            top_n=max(args.top, 1),
        )
        out_md = Path(output_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(md, encoding="utf-8")
        print(f"Markdown written: {out_md}")

    # Short terminal summary.
    print("\nTop commands:")
    for row in commands_rows[:15]:
        print(f"{row['count']:>4}  {row['name']}  {row['source_counts']}")

    print("\nTop loaded skills (base markers):")
    for row in loaded_rows[:15]:
        print(f"{row['count']:>4}  {row['name']}  {row['source_counts']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
