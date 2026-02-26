#!/usr/bin/env python3
"""
Build an evidence-based skill usage dataset from Claude session logs.

Purpose:
- Aggregate observed /skill usage for this project from local Claude JSONL logs.
- Exclude sensitive command families (google/chat) from training outputs.
- Classify neutral context buckets (no sensitive prompt details).
- Produce machine-readable JSON for downstream DOCX training generation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


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


INTENT_KEYWORDS: Dict[str, List[str]] = {
    "planning_architecture": [
        "plan",
        "roadmap",
        "phase",
        "milestone",
        "architecture",
        "sad",
        "design",
        "scope",
        "gap",
        "handoff",
        "document",
        "docs",
        "workflow",
    ],
    "audit_verification": [
        "audit",
        "verify",
        "validation",
        "validate",
        "fact-check",
        "evidence",
        "accuracy",
        "cross-reference",
        "confirm",
        "proof",
        "truth",
    ],
    "testing_qa": [
        "test",
        "qa",
        "playwright",
        "e2e",
        "scenario",
        "regression",
        "pass",
        "fail",
        "smoke",
    ],
    "deployment_operations": [
        "deploy",
        "deployment",
        "production",
        "release",
        "rollback",
        "docker",
        "ssm",
        "migrate",
        "ci",
        "infra",
        "host",
        "hosted",
    ],
    "data_extraction_reporting": [
        "extract",
        "xlsx",
        "csv",
        "import",
        "export",
        "sync",
        "dataset",
        "schema",
        "etl",
        "report",
        "reconcile",
    ],
    "debugging_incident": [
        "error",
        "issue",
        "broken",
        "fix",
        "debug",
        "failure",
        "unblock",
        "not working",
        "wtf",
        "why",
    ],
    "automation_coordination": [
        "agent",
        "agents",
        "team",
        "teammates",
        "parallel",
        "orchestr",
        "owner",
        "assign",
        "spawn",
    ],
    "domain_ops_adms": [
        "adms",
        "biometric",
        "attendance",
        "device",
        "bio id",
        "machine",
        "enroll",
        "pin",
    ],
}


INTENT_LABEL = {
    "planning_architecture": "Planning / Architecture",
    "audit_verification": "Audit / Verification",
    "testing_qa": "Testing / QA",
    "deployment_operations": "Deployment / Operations",
    "data_extraction_reporting": "Data / Extraction / Reporting",
    "debugging_incident": "Debugging / Incident Response",
    "automation_coordination": "Automation / Team Coordination",
    "domain_ops_adms": "ADMS / Device Operations",
    "general_execution": "General Execution",
}


INTENT_TO_STAGE = {
    "planning_architecture": "Plan & Design",
    "audit_verification": "Quality Gate",
    "testing_qa": "Test & Validate",
    "deployment_operations": "Release & Operate",
    "data_extraction_reporting": "Data Workstream",
    "debugging_incident": "Incident & Debug",
    "automation_coordination": "Execution Coordination",
    "domain_ops_adms": "Operational Domain",
    "general_execution": "General Execution",
}


INTENT_BEST_TIME = {
    "planning_architecture": "Use during planning/design definition and before implementation starts.",
    "audit_verification": "Use when validating decisions, plans, or outputs before sign-off.",
    "testing_qa": "Use after implementation changes and before release acceptance.",
    "deployment_operations": "Use during release preparation, rollout, and post-release stabilization.",
    "data_extraction_reporting": "Use when collecting, transforming, or reconciling structured data.",
    "debugging_incident": "Use when something is failing and root-cause isolation is required.",
    "automation_coordination": "Use when work must be parallelized or coordinated across multiple agents.",
    "domain_ops_adms": "Use for biometric/ADMS operations and device workflow handling.",
    "general_execution": "Use for focused execution when no specialized pattern is required.",
}


SENSITIVE_PREFIXES = ("google", "chat")


SKILL_INTENT_HINTS: Dict[str, str] = {
    "plan-audit": "planning_architecture",
    "write-plan": "planning_architecture",
    "architect-reviewer": "planning_architecture",
    "design-review": "planning_architecture",
    "build": "planning_architecture",
    "fact-check": "audit_verification",
    "test-full-cycle": "testing_qa",
    "playwright": "testing_qa",
    "l1-api-check": "testing_qa",
    "l2-page-check": "testing_qa",
    "l3-submit-verify": "testing_qa",
    "qa-loop": "testing_qa",
    "deploy-frappe": "deployment_operations",
    "workflow": "deployment_operations",
    "cleanup-branches": "deployment_operations",
    "xlsx": "data_extraction_reporting",
    "extract-data-v2.1": "data_extraction_reporting",
    "accounting-extraction": "data_extraction_reporting",
    "sales": "data_extraction_reporting",
    "rlm": "data_extraction_reporting",
    "adms": "domain_ops_adms",
    "biometric-integration": "domain_ops_adms",
    "teammates": "automation_coordination",
    "team-planner": "automation_coordination",
    "tasks": "automation_coordination",
    "find-conversations": "automation_coordination",
    "save": "automation_coordination",
    "restore": "automation_coordination",
    "codex-session": "automation_coordination",
}


def parse_ts(ts_raw: str) -> Optional[datetime]:
    if not ts_raw:
        return None
    try:
        value = ts_raw.replace("Z", "+00:00") if ts_raw.endswith("Z") else ts_raw
        dt = datetime.fromisoformat(value)
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


def get_text_from_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def get_message_text(obj: dict) -> str:
    message = obj.get("message")
    if isinstance(message, dict):
        text = get_text_from_content(message.get("content"))
        if text:
            return text
    elif isinstance(message, str):
        return message

    return get_text_from_content(obj.get("content"))


def normalize_command(name: str) -> str:
    return name.strip().lstrip("/").lower()


def derive_skill_aliases(skill_dir_name: str) -> Tuple[str, Set[str]]:
    base = skill_dir_name.strip().lower()
    preferred = base
    if preferred.endswith("-bei-erp"):
        preferred = preferred[: -len("-bei-erp")]
    if preferred.startswith("gsd-"):
        preferred = f"gsd:{preferred[4:]}"

    aliases = {base}
    if base.endswith("-bei-erp"):
        short = base[: -len("-bei-erp")]
        aliases.add(short)
        if short.startswith("gsd-"):
            aliases.add(f"gsd:{short[4:]}")
    if base.startswith("gsd-"):
        aliases.add(f"gsd:{base[4:]}")

    return preferred, aliases


def load_skill_alias_map(skill_roots: List[Path]) -> Dict[str, str]:
    alias_to_preferred: Dict[str, str] = {}

    def put(alias: str, preferred: str) -> None:
        current = alias_to_preferred.get(alias)
        if current is None or len(preferred) < len(current):
            alias_to_preferred[alias] = preferred

    for root in skill_roots:
        if not root.exists() or not root.is_dir():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            preferred, aliases = derive_skill_aliases(child.name)
            put(preferred, preferred)
            for alias in aliases:
                put(alias, preferred)

    return alias_to_preferred


def extract_skill_name_from_path(raw_path: str) -> Optional[str]:
    cleaned = raw_path.strip().rstrip("\\/").replace("\\", "/")
    parts = cleaned.split("/")
    if not parts:
        return None
    return parts[-1].lower()


def is_sensitive_skill(skill: str) -> bool:
    value = skill.lower().lstrip("/")
    return any(
        value.startswith(prefix) or f"-{prefix}" in value or f":{prefix}" in value
        for prefix in SENSITIVE_PREFIXES
    )


def classify_intent(text: str) -> str:
    text_l = text.lower()
    scores: Dict[str, int] = {}
    for intent, kws in INTENT_KEYWORDS.items():
        scores[intent] = sum(1 for kw in kws if kw in text_l)

    best_intent = "general_execution"
    best_score = 0
    for intent, score in scores.items():
        if score > best_score:
            best_intent = intent
            best_score = score
    return best_intent


def infer_best_time(intent_counts: Dict[str, int]) -> str:
    ranked = sorted(intent_counts.items(), key=lambda x: (-x[1], x[0]))
    top = [k for k, v in ranked if v > 0][:2]
    if not top:
        return INTENT_BEST_TIME["general_execution"]
    if len(top) == 1:
        return INTENT_BEST_TIME.get(top[0], INTENT_BEST_TIME["general_execution"])

    pair = set(top)
    if pair == {"planning_architecture", "audit_verification"}:
        return "Use after drafting plans/designs and before execution approval."
    if pair == {"testing_qa", "debugging_incident"}:
        return "Use during bug triage and validation loops before closure."
    if pair == {"deployment_operations", "testing_qa"}:
        return "Use around release windows with immediate verification checkpoints."
    if pair == {"data_extraction_reporting", "audit_verification"}:
        return "Use when reconciling extracted data and validating final outputs."

    return (
        f"Use primarily for {INTENT_LABEL.get(top[0], top[0]).lower()}, "
        f"with secondary use in {INTENT_LABEL.get(top[1], top[1]).lower()}."
    )


def infer_skill_intent(skill: str, base_intent: str) -> str:
    if base_intent != "general_execution":
        return base_intent

    for prefix, hinted_intent in SKILL_INTENT_HINTS.items():
        if skill == prefix or skill.startswith(f"{prefix}:"):
            return hinted_intent
    return base_intent


@dataclass
class SkillUsage:
    command_count: int = 0
    base_marker_count: int = 0
    sessions: Set[str] = field(default_factory=set)
    command_sessions: Set[str] = field(default_factory=set)
    base_sessions: Set[str] = field(default_factory=set)
    source_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    intent_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None

    def touch_time(self, ts: datetime) -> None:
        iso = ts.isoformat()
        if self.first_seen is None or iso < self.first_seen:
            self.first_seen = iso
        if self.last_seen is None or iso > self.last_seen:
            self.last_seen = iso


def main() -> int:
    parser = argparse.ArgumentParser(description="Build skill training dataset from Claude logs.")
    parser.add_argument(
        "--claude-projects-root",
        default=str(Path.home() / ".claude" / "projects"),
        help="Root containing Claude JSONL session logs.",
    )
    parser.add_argument(
        "--project-filter",
        default=str(Path.cwd()),
        help="Case-insensitive cwd filter to scope logs to this project.",
    )
    parser.add_argument(
        "--after",
        default="",
        help="Optional lower timestamp bound (ISO-8601).",
    )
    parser.add_argument(
        "--before",
        default="",
        help="Optional upper timestamp bound (ISO-8601).",
    )
    parser.add_argument(
        "--output-json",
        default="scratchpad/reports/skill_training_dataset.json",
        help="Output dataset JSON path.",
    )
    args = parser.parse_args()

    projects_root = Path(args.claude_projects_root)
    if not projects_root.exists():
        raise SystemExit(f"Claude projects root not found: {projects_root}")

    lower_bound = parse_ts(args.after) if args.after else None
    upper_bound = parse_ts(args.before) if args.before else None
    if lower_bound and upper_bound and upper_bound < lower_bound:
        raise SystemExit("--before must be >= --after")

    project_filter = args.project_filter.strip().lower()

    skill_roots = [
        Path.home() / ".claude" / "skills",
        Path(args.project_filter) / ".claude" / "skills",
        Path.cwd() / ".claude" / "skills",
    ]
    alias_map = load_skill_alias_map(skill_roots)
    known_aliases = set(alias_map.keys())
    known_preferred = set(alias_map.values())

    stats: Dict[str, SkillUsage] = defaultdict(SkillUsage)
    session_events: Dict[str, List[Tuple[datetime, str]]] = defaultdict(list)

    meta = {
        "files_scanned": 0,
        "lines_scanned": 0,
        "json_parse_errors": 0,
        "events_in_scope": 0,
        "user_events_in_scope": 0,
        "command_events_counted": 0,
        "base_marker_events_counted": 0,
        "sensitive_events_excluded": 0,
    }

    def canonical_skill(name: str) -> Optional[str]:
        cmd = normalize_command(name)
        if cmd not in known_aliases:
            return None
        return alias_map.get(cmd, cmd)

    for file_path in iter_jsonl_files(projects_root):
        meta["files_scanned"] += 1
        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
                for raw in handle:
                    meta["lines_scanned"] += 1
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        meta["json_parse_errors"] += 1
                        continue

                    ts = parse_ts(obj.get("timestamp", ""))
                    if ts is None:
                        continue
                    if lower_bound and ts < lower_bound:
                        continue
                    if upper_bound and ts > upper_bound:
                        continue

                    cwd = str(obj.get("cwd") or "").lower()
                    if project_filter and project_filter not in cwd:
                        continue

                    text = get_message_text(obj)
                    if not text:
                        continue

                    meta["events_in_scope"] += 1
                    event_type = str(obj.get("type") or "").lower()
                    session_id = str(obj.get("sessionId") or "")

                    # Base skill markers: strong evidence skill was loaded.
                    for match in BASE_SKILL_RE.finditer(text):
                        raw_path = match.group(1).strip()
                        name_from_path = extract_skill_name_from_path(raw_path)
                        if not name_from_path:
                            continue
                        skill = canonical_skill(name_from_path)
                        if not skill:
                            continue
                        if is_sensitive_skill(skill):
                            meta["sensitive_events_excluded"] += 1
                            continue
                        usage = stats[skill]
                        usage.base_marker_count += 1
                        usage.base_sessions.add(session_id)
                        usage.sessions.add(session_id)
                        usage.source_counts["base_skill_marker"] += 1
                        usage.touch_time(ts)
                        meta["base_marker_events_counted"] += 1

                    if event_type != "user":
                        continue
                    meta["user_events_in_scope"] += 1

                    found_commands: List[Tuple[str, str]] = []
                    for match in COMMAND_NAME_RE.finditer(text):
                        found_commands.append((normalize_command(match.group(1)), "command_name_tag"))
                    for match in COMMAND_MESSAGE_RE.finditer(text):
                        found_commands.append((normalize_command(match.group(1)), "command_message_tag"))

                    # Inline slash command detection on short user prompts (noise controlled).
                    if (
                        not found_commands
                        and "<" not in text
                        and ">" not in text
                        and "Base directory for this skill:" not in text
                    ):
                        trimmed = text.strip()
                        non_empty_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                        if len(trimmed) <= 600 and len(non_empty_lines) <= 4 and non_empty_lines:
                            first_line = non_empty_lines[0]
                            for match in INLINE_SLASH_RE.finditer(first_line):
                                token = normalize_command(match.group(1))
                                if token in known_aliases:
                                    found_commands.append((token, "inline_slash_token"))

                    if not found_commands:
                        continue

                    base_intent = classify_intent(text)
                    for command_token, source in found_commands:
                        skill = canonical_skill(command_token)
                        if not skill:
                            continue
                        if is_sensitive_skill(skill):
                            meta["sensitive_events_excluded"] += 1
                            continue

                        usage = stats[skill]
                        usage.command_count += 1
                        usage.command_sessions.add(session_id)
                        usage.sessions.add(session_id)
                        usage.source_counts[source] += 1
                        intent = infer_skill_intent(skill, base_intent)
                        usage.intent_counts[intent] += 1
                        usage.touch_time(ts)
                        meta["command_events_counted"] += 1

                        if session_id:
                            session_events[session_id].append((ts, skill))
        except Exception:
            meta["json_parse_errors"] += 1

    # Build transition matrix from observed command ordering per session.
    transition_counts: Dict[Tuple[str, str], int] = defaultdict(int)
    for _, events in session_events.items():
        if len(events) < 2:
            continue
        ordered = sorted(events, key=lambda x: x[0])
        for idx in range(len(ordered) - 1):
            src = ordered[idx][1]
            dst = ordered[idx + 1][1]
            if src == dst:
                continue
            transition_counts[(src, dst)] += 1

    outgoing_map: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    incoming_map: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    for (src, dst), count in transition_counts.items():
        outgoing_map[src].append((dst, count))
        incoming_map[dst].append((src, count))

    rows: List[dict] = []
    for skill in sorted(stats.keys()):
        usage = stats[skill]
        intents_sorted = sorted(usage.intent_counts.items(), key=lambda x: (-x[1], x[0]))
        total_intents = sum(usage.intent_counts.values())
        dominant_intent = intents_sorted[0][0] if intents_sorted else "general_execution"

        intent_distribution = []
        for intent, count in intents_sorted:
            pct = (count / total_intents * 100.0) if total_intents else 0.0
            intent_distribution.append(
                {
                    "intent": intent,
                    "label": INTENT_LABEL.get(intent, intent),
                    "count": count,
                    "percent": round(pct, 1),
                }
            )

        outgoing = sorted(outgoing_map.get(skill, []), key=lambda x: (-x[1], x[0]))[:5]
        incoming = sorted(incoming_map.get(skill, []), key=lambda x: (-x[1], x[0]))[:5]

        rows.append(
            {
                "skill": f"/{skill}",
                "command_count": usage.command_count,
                "base_marker_count": usage.base_marker_count,
                "total_evidence_count": usage.command_count + usage.base_marker_count,
                "sessions": len([s for s in usage.sessions if s]),
                "first_seen_utc": usage.first_seen,
                "last_seen_utc": usage.last_seen,
                "source_counts": dict(sorted(usage.source_counts.items())),
                "dominant_intent": dominant_intent,
                "dominant_intent_label": INTENT_LABEL.get(dominant_intent, dominant_intent),
                "workflow_stage": INTENT_TO_STAGE.get(dominant_intent, "General Execution"),
                "best_time_to_use": infer_best_time(dict(usage.intent_counts)),
                "intent_distribution": intent_distribution,
                "recommended_pairings_outgoing": [
                    {"skill": f"/{dst}", "count": cnt} for dst, cnt in outgoing
                ],
                "recommended_pairings_incoming": [
                    {"skill": f"/{src}", "count": cnt} for src, cnt in incoming
                ],
            }
        )

    rows.sort(key=lambda x: (-x["command_count"], -x["base_marker_count"], x["skill"]))

    top_transitions = sorted(
        transition_counts.items(),
        key=lambda kv: (-kv[1], kv[0][0], kv[0][1]),
    )[:40]

    transition_rows = [
        {"from": f"/{src}", "to": f"/{dst}", "count": count}
        for (src, dst), count in top_transitions
    ]

    stage_counts: Dict[str, int] = defaultdict(int)
    for row in rows:
        stage_counts[row["workflow_stage"]] += row["command_count"]

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "filters": {
            "claude_projects_root": str(projects_root),
            "project_filter": args.project_filter,
            "after": args.after or None,
            "before": args.before or None,
        },
        "privacy_controls": {
            "sensitive_skill_prefixes_excluded": list(SENSITIVE_PREFIXES),
            "raw_message_text_exported": False,
            "context_mode": "aggregated_intent_only",
        },
        "meta": meta,
        "known_skill_roots": [str(root) for root in skill_roots if root.exists()],
        "known_skills_detected": len(known_preferred),
        "skills": rows,
        "workflow_summary": {
            "skills_with_usage": len(rows),
            "stage_counts": dict(sorted(stage_counts.items())),
            "top_transitions": transition_rows,
        },
    }

    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Dataset written: {out_path}")
    print(f"Skills with usage: {len(rows)}")
    print(f"Command events counted: {meta['command_events_counted']}")
    print(f"Base marker events counted: {meta['base_marker_events_counted']}")
    print(f"Sensitive events excluded: {meta['sensitive_events_excluded']}")

    print("\nTop non-sensitive skills by command count:")
    for row in rows[:20]:
        print(
            f"{row['command_count']:>4}  {row['skill']:<26} "
            f"stage={row['workflow_stage']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
