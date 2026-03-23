"""Governor self-evolution memory — Reflexion lessons + Procedural playbooks.

Lessons: "Don't do X, do Y instead" (learned from failures)
Playbooks: "When situation S, follow steps 1-2-3" (learned from successes)

Both are plain markdown files in ~/.governor/memory/.
Both are injected into AI prompts on startup.
The governor gets smarter with every failure and every successful recovery.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import structlog

logger = structlog.get_logger("governor.lessons")

MEMORY_DIR = Path.home() / ".governor" / "memory"
MAX_ITEMS = 100
MAX_TOKENS = 10000  # ~200 words per item, 50 items = 10K tokens


@dataclass
class Lesson:
    id: str
    category: str  # review | build | deploy | gate | merge | builder
    trigger: str
    wrong_action: str
    correct_action: str
    source_incident: str
    created_at: str = ""
    applied_count: int = 0
    last_applied: str = ""


@dataclass
class Playbook:
    id: str
    category: str  # build | deploy | gate | merge
    trigger: str
    steps: list[str] = field(default_factory=list)
    source_incident: str = ""
    created_at: str = ""
    success_count: int = 0


def _ensure_dir():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _timestamp() -> str:
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


# --- WRITE ---

def record_lesson(
    category: str,
    trigger: str,
    wrong_action: str,
    correct_action: str,
    source_incident: str,
) -> str | None:
    """Write a lesson after a failure. Returns lesson ID or None if deduped."""
    _ensure_dir()

    # Dedup: check if similar lesson exists
    existing = _find_similar(trigger, "lesson")
    if existing:
        _increment_applied(existing)
        logger.info("lesson_deduped", existing=existing.name, trigger=trigger[:50])
        return None

    ts = _timestamp()
    slug = re.sub(r"[^a-z0-9]+", "-", trigger[:40].lower()).strip("-")
    lesson_id = f"{time.strftime('%Y-%m-%d')}-{slug}"
    filename = f"lesson-{lesson_id}.md"

    content = f"""---
id: {lesson_id}
type: lesson
category: {category}
trigger: "{trigger}"
wrong_action: "{wrong_action}"
correct_action: "{correct_action}"
source_incident: "{source_incident}"
created_at: {ts}
applied_count: 0
last_applied: ""
---
"""
    (MEMORY_DIR / filename).write_text(content, encoding="utf-8")
    logger.info("lesson_recorded", id=lesson_id, category=category)
    _enforce_cap()
    return lesson_id


def record_playbook(
    category: str,
    trigger: str,
    steps: list[str],
    source_incident: str,
) -> str | None:
    """Write a playbook after a successful recovery. Returns ID or None if deduped."""
    _ensure_dir()

    existing = _find_similar(trigger, "playbook")
    if existing:
        _increment_applied(existing)
        logger.info("playbook_deduped", existing=existing.name, trigger=trigger[:50])
        return None

    ts = _timestamp()
    slug = re.sub(r"[^a-z0-9]+", "-", trigger[:40].lower()).strip("-")
    playbook_id = f"{time.strftime('%Y-%m-%d')}-{slug}"
    filename = f"playbook-{playbook_id}.md"

    steps_yaml = "\n".join(f'  - "{s}"' for s in steps)
    content = f"""---
id: {playbook_id}
type: playbook
category: {category}
trigger: "{trigger}"
steps:
{steps_yaml}
source_incident: "{source_incident}"
created_at: {ts}
success_count: 0
---
"""
    (MEMORY_DIR / filename).write_text(content, encoding="utf-8")
    logger.info("playbook_recorded", id=playbook_id, category=category)
    _enforce_cap()
    return playbook_id


# --- READ ---

def load_memory() -> str:
    """Read all lessons + playbooks, format as prompt context block."""
    _ensure_dir()

    lessons = []
    playbooks = []

    for f in sorted(MEMORY_DIR.glob("*.md")):
        try:
            text = f.read_text(encoding="utf-8")
            meta = _parse_frontmatter(text)
            if not meta:
                continue

            if meta.get("type") == "lesson":
                cat = meta.get("category", "?").upper()
                trigger = meta.get("trigger", "?")
                correct = meta.get("correct_action", "?")
                source = meta.get("source_incident", "")
                count = meta.get("applied_count", 0)
                lessons.append(f"- {cat}: {trigger} → {correct} (Source: {source}, applied {count}x)")

            elif meta.get("type") == "playbook":
                cat = meta.get("category", "?").upper()
                trigger = meta.get("trigger", "?")
                steps = meta.get("steps", [])
                source = meta.get("source_incident", "")
                steps_text = " → ".join(steps[:5])
                playbooks.append(f"- {cat}: When: {trigger} → {steps_text} (Source: {source})")

        except Exception:
            continue

    if not lessons and not playbooks:
        return ""

    lines = ["\n## Governor Memory (auto-evolved from past incidents)\n"]

    if lessons:
        lines.append("### Lessons (avoid these mistakes)")
        lines.extend(lessons[:50])
        lines.append("")

    if playbooks:
        lines.append("### Playbooks (follow these procedures)")
        lines.extend(playbooks[:50])
        lines.append("")

    result = "\n".join(lines)

    # Token budget check (~4 chars per token)
    if len(result) > MAX_TOKENS * 4:
        result = result[: MAX_TOKENS * 4] + "\n... (truncated to token budget)"

    return result


def get_memory_stats() -> dict:
    """Return stats about the memory system."""
    _ensure_dir()
    lessons = list(MEMORY_DIR.glob("lesson-*.md"))
    playbooks = list(MEMORY_DIR.glob("playbook-*.md"))
    return {
        "lesson_count": len(lessons),
        "playbook_count": len(playbooks),
        "total": len(lessons) + len(playbooks),
        "dir": str(MEMORY_DIR),
    }


# --- MANAGE ---

def check_repeat_failure(trigger: str) -> bool:
    """Check if a lesson exists for this trigger. If yes, it recurred — escalate."""
    existing = _find_similar(trigger, "lesson")
    if existing:
        meta = _parse_frontmatter(existing.read_text(encoding="utf-8"))
        if meta:
            logger.warning(
                "repeat_failure_despite_lesson",
                lesson=existing.name,
                applied_count=meta.get("applied_count", 0),
                trigger=trigger[:80],
            )
            _increment_applied(existing)
            return True
    return False


def _find_similar(trigger: str, mem_type: str) -> Path | None:
    """Find an existing memory item with >80% word overlap on trigger."""
    _ensure_dir()
    trigger_words = set(trigger.lower().split())
    if not trigger_words:
        return None

    prefix = "lesson-" if mem_type == "lesson" else "playbook-"
    for f in MEMORY_DIR.glob(f"{prefix}*.md"):
        try:
            meta = _parse_frontmatter(f.read_text(encoding="utf-8"))
            if not meta:
                continue
            existing_words = set(meta.get("trigger", "").lower().split())
            if not existing_words:
                continue
            overlap = len(trigger_words & existing_words) / max(len(trigger_words), len(existing_words))
            if overlap > 0.8:
                return f
        except Exception:
            continue
    return None


def _increment_applied(filepath: Path) -> None:
    """Increment applied_count in a memory file."""
    try:
        text = filepath.read_text(encoding="utf-8")
        # Simple regex replacement for applied_count or success_count
        for field_name in ("applied_count", "success_count"):
            match = re.search(rf"{field_name}: (\d+)", text)
            if match:
                old_count = int(match.group(1))
                text = text.replace(f"{field_name}: {old_count}", f"{field_name}: {old_count + 1}")
                break

        # Update last_applied
        ts = _timestamp()
        text = re.sub(r'last_applied: ".*"', f'last_applied: "{ts}"', text)

        filepath.write_text(text, encoding="utf-8")
    except Exception:
        pass


def _enforce_cap() -> None:
    """Enforce MAX_ITEMS cap. Prune oldest zero-applied items first."""
    _ensure_dir()
    all_files = sorted(MEMORY_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime)

    if len(all_files) <= MAX_ITEMS:
        return

    # Sort by priority: frequently applied items survive
    def _priority(f):
        try:
            meta = _parse_frontmatter(f.read_text(encoding="utf-8"))
            count = meta.get("applied_count", 0) or meta.get("success_count", 0)
            return count
        except Exception:
            return 0

    # Remove lowest-priority items until under cap
    by_priority = sorted(all_files, key=_priority)
    to_remove = len(all_files) - MAX_ITEMS
    for f in by_priority[:to_remove]:
        f.unlink()
        logger.info("lesson_pruned", file=f.name)


def _parse_frontmatter(text: str) -> dict | None:
    """Parse YAML frontmatter from markdown file."""
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end == -1:
        return None

    frontmatter = text[3:end].strip()
    result = {}
    current_key = None
    current_list = None

    for line in frontmatter.split("\n"):
        line = line.rstrip()
        if line.startswith("  - "):
            # List item
            if current_list is not None:
                val = line.strip("- ").strip().strip('"')
                current_list.append(val)
            continue

        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"')

            if current_list is not None and current_key:
                result[current_key] = current_list
                current_list = None

            if not val:
                # Might be a list
                current_key = key
                current_list = []
            else:
                # Try to parse as int
                try:
                    result[key] = int(val)
                except ValueError:
                    result[key] = val
                current_key = None

    if current_list is not None and current_key:
        result[current_key] = current_list

    return result if result else None
