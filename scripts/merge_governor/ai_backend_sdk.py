"""Backend B: Claude Agent SDK (ANTHROPIC_API_KEY, pay-per-token).

Always works but costs money. Requires explicit --ai-backend sdk flag.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from .ai_backend_base import ReviewBackend, ReviewResult

if TYPE_CHECKING:
	from .state_manager import GovernorState

logger = structlog.get_logger("governor.ai.sdk")

REVIEW_SYSTEM_PROMPT = """\
You are a code review agent for BEI-ERP (Frappe/ERPNext).
You review PR diffs for conflicts, anti-rewind violations, and protected surface modifications.
Always respond with a JSON object containing: decision, reasoning, confidence, conflicting_files, suggested_fix.
"""


CHAT_SYSTEM_PROMPT = """\
You are governor-erp, an AI merge governor for BEI-ERP (Frappe/ERPNext).

You manage production merges for a team of 5-8 parallel Claude Code builder sessions.
You review PR diffs, detect file conflicts, prevent anti-rewind regressions, and serialize merges.

You have persistent memory of this conversation. The operator (Sam, CEO) chats with you
naturally about PRs, merges, staging, and code conflicts. Be direct, concise, and opinionated.
When you reviewed a PR, remember your reasoning so you can explain it when asked.

When the operator mentions a PR number in any format (274, #274, PR 274, PR-274, etc.),
PR details are automatically fetched from GitHub and appended to the message.
Use those details to give informed, specific answers. Never say "I don't have details" —
the details are fetched for you.

Current governor state is injected as context at the start of each message.

## BEI Deployment Knowledge

BEI has TWO repositories with different deployment pipelines:

### BEI-ERP (hq.bebang.ph) — Frappe Backend
- Repo: Bebang-Enterprise-Inc/hrms, release branch: `production`
- Deploy: PR merge to production -> GHA build-and-deploy.yml -> Docker build -> AWS EC2 SSM
- EC2: i-026b7477d27bd46d6 (ap-southeast-1), Docker Swarm with 9 services
- Image: samkarazi/bebang-erpnext-hrms:v15, build time 5-12 min
- Rollback: `docker service rollback frappe_backend` (fastest)

### BEI-Tasks (my.bebang.ph) — React Frontend
- Separate bei-tasks repo, release branch: `main`
- Deploy: push to main -> Vercel auto-deploys
- Governor auto-triggers `vercel --prod --force` (cache-bust) after every successful backend merge
- Rollback: Vercel dashboard or CLI
- CORS errors from my.bebang.ph = backend API not deployed yet

### Docker Build Flags
- `no_cache=true`: ALWAYS for Python .py or DocType JSON changes (skipping = deploys old code!)
- `skip_build=true`: Config-only changes, data imports (reuses existing image)
- `run_migrate=true`: DocType schema changes (adds/removes fields)
- Build time ~2 min = CACHED (old code!), ~5-10 min = FRESH (correct)

### Post-Deploy Checklist
1. frappe.ping -> pong
2. Login page -> HTTP 200
3. Redis flush (if CSS 404 or after migrate)
4. Image cleanup (keep 4 newest)

### NEVER DO
- docker commit (corrupts Python), edit files in container (lost on restart)
- docker compose down -v (deletes all data volumes)
- skip bench migrate after DocType changes
- deploy without no_cache=true for Python/DocType changes
- push directly to production branch
- claim SHIPPED without L1-L4 green

### L1-L4 Testing
- L1: API health (ping, login page)
- L2: Page rendering, CSS/JS assets load
- L3: Full workflow E2E for affected module
- L4: Automated assertion runner
- All 4 must be green before SHIPPED status

### Ship Status
- SHIPPED = merged + deployed + live + L1-L4 green
- MERGED_NOT_LIVE = PR merged but deploy not proven
- DEPLOYED_NOT_VERIFIED = production updated but L1-L4 still red
"""


class SDKBackend(ReviewBackend):
	"""AI backend using Anthropic API with persistent multi-turn chat."""

	def __init__(self):
		self._api_key = os.environ.get("ANTHROPIC_API_KEY", "")
		self._client = None
		self._total_cost_usd = 0.0
		self._cost_log_file = Path(__file__).parent / "logs" / "cost_log.jsonl"
		self._cost_log_file.parent.mkdir(exist_ok=True)
		# Persistent chat history for multi-turn conversation
		self._chat_history: list[dict[str, str]] = []
		self._max_chat_history = 40  # Keep last 40 messages (20 turns)

	def _get_client(self):
		if self._client is None:
			try:
				import anthropic

				self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
			except ImportError:
				raise ImportError("anthropic package not installed. Run: pip install anthropic")
		return self._client

	async def review(
		self,
		pr_number: int,
		diff_text: str,
		merge_context: dict[str, Any],
		timeout_s: float = 120,
	) -> ReviewResult:
		client = self._get_client()

		recent_merges = merge_context.get("recent_merges", [])
		recent_files = []
		for m in recent_merges:
			for f in m.get("touched_files", []):
				if f not in recent_files:
					recent_files.append(f)

		user_prompt = (
			f"Review PR #{pr_number}.\n\n"
			f"Files touched by last {len(recent_merges)} merged PRs:\n"
			+ "\n".join(f"  - {f}" for f in recent_files[:50])
			+ "\n\nProtected surfaces:\n"
			+ "\n".join(f"  - {p}" for p in merge_context.get("protected_surfaces", []))
			+ f"\n\nDiff:\n```\n{diff_text[:50000]}\n```\n\n"
			f'Respond with JSON: {{"decision": "APPROVE|REJECT|NEEDS_FIX", '
			f'"reasoning": "...", "confidence": 0.0-1.0, '
			f'"conflicting_files": [], "suggested_fix": null}}'
		)

		try:
			import asyncio

			response = await asyncio.wait_for(
				client.messages.create(
					model="claude-sonnet-4-20250514",
					max_tokens=1024,
					system=REVIEW_SYSTEM_PROMPT,
					messages=[{"role": "user", "content": user_prompt}],
				),
				timeout=timeout_s,
			)

			raw_text = response.content[0].text if response.content else ""

			# Track cost
			input_tokens = getattr(response.usage, "input_tokens", 0)
			output_tokens = getattr(response.usage, "output_tokens", 0)
			# Approximate cost (Sonnet pricing)
			cost = (input_tokens * 3 / 1_000_000) + (output_tokens * 15 / 1_000_000)
			self._total_cost_usd += cost
			self._log_cost(cost, f"review_pr_{pr_number}")

			return self._parse_response(raw_text, pr_number)

		except Exception as e:
			logger.error("sdk_review_error", pr=pr_number, error=str(e))
			return ReviewResult(
				decision="REJECT",
				reasoning=f"SDK backend error: {e}",
				confidence=0.0,
				raw_response=str(e),
			)

	async def chat(self, message: str, state: GovernorState) -> str:
		"""Multi-turn chat with persistent conversation history."""
		client = self._get_client()

		# Build state context
		pr_details = []
		for _k, pr in state.active_prs.items():
			port_str = f" staging:{pr.staging_port}" if pr.staging_port else ""
			review_str = f" review={pr.review_decision}" if pr.review_decision else ""
			pr_details.append(f"  PR #{pr.number} [{pr.head_ref}]{port_str}{review_str}")

		context_lines = [
			"[Governor State]",
			f"Status: {'PAUSED' if state.paused else 'RUNNING'}",
			f"Active PRs: {len(state.active_prs)}",
			f"Merge queue: {len(state.merge_queue)} — {state.merge_queue}",
			f"Production HEAD: {state.production_head[:12] if state.production_head else 'unknown'}",
		]
		if pr_details:
			context_lines.append("PRs:")
			context_lines.extend(pr_details)
		if state.merge_history:
			recent = state.merge_history[-3:]
			context_lines.append(f"Recent merges: {[m.get('number') for m in recent]}")

		context_block = "\n".join(context_lines)

		# Add user message to history (with state context)
		user_msg = f"{context_block}\n\nOperator: {message}"
		self._chat_history.append({"role": "user", "content": user_msg})

		# Trim history to max size
		if len(self._chat_history) > self._max_chat_history:
			self._chat_history = self._chat_history[-self._max_chat_history :]

		try:
			response = await client.messages.create(
				model="claude-sonnet-4-20250514",
				max_tokens=1024,
				system=CHAT_SYSTEM_PROMPT,
				messages=self._chat_history,
			)

			reply = response.content[0].text if response.content else "No response"

			# Track cost
			input_tokens = getattr(response.usage, "input_tokens", 0)
			output_tokens = getattr(response.usage, "output_tokens", 0)
			cost = (input_tokens * 3 / 1_000_000) + (output_tokens * 15 / 1_000_000)
			self._total_cost_usd += cost
			self._log_cost(cost, "chat")
			logger.info(
				"sdk_chat_cost",
				input_tokens=input_tokens,
				output_tokens=output_tokens,
				cost_usd=round(cost, 4),
				history_len=len(self._chat_history),
			)

			# Add assistant reply to history
			self._chat_history.append({"role": "assistant", "content": reply})

			return reply

		except Exception as e:
			logger.error("sdk_chat_error", error=str(e))
			# Remove the failed user message from history
			self._chat_history.pop()
			raise

	def inject_review_into_chat(self, pr_number: int, result: ReviewResult) -> None:
		"""Inject a review result into chat history so the agent remembers it."""
		summary = (
			f"[I just reviewed PR #{pr_number}]\n"
			f"Decision: {result.decision}\n"
			f"Confidence: {result.confidence}\n"
			f"Reasoning: {result.reasoning}\n"
		)
		if result.conflicting_files:
			summary += f"Conflicting files: {', '.join(result.conflicting_files)}\n"
		if result.suggested_fix:
			summary += f"Suggested fix: {result.suggested_fix}\n"

		self._chat_history.append({"role": "assistant", "content": summary})

	async def health_check(self) -> bool:
		if not self._api_key:
			logger.warning("sdk_no_api_key")
			return False
		try:
			client = self._get_client()
			response = await client.messages.create(
				model="claude-sonnet-4-20250514",
				max_tokens=10,
				messages=[{"role": "user", "content": "Reply OK"}],
			)
			return bool(response.content)
		except Exception as e:
			logger.warning("sdk_health_failed", error=str(e))
			return False

	def _parse_response(self, raw: str, pr_number: int) -> ReviewResult:
		"""Parse SDK response into ReviewResult."""
		# Try to find JSON in the response — handle nested braces
		data = None

		# Strategy 1: Find the outermost JSON object by brace matching
		start = raw.find("{")
		if start >= 0:
			depth = 0
			for i in range(start, len(raw)):
				if raw[i] == "{":
					depth += 1
				elif raw[i] == "}":
					depth -= 1
					if depth == 0:
						try:
							data = json.loads(raw[start : i + 1])
						except json.JSONDecodeError:
							pass
						break

		# Strategy 2: Try parsing the entire response as JSON
		if data is None:
			try:
				data = json.loads(raw)
			except (json.JSONDecodeError, ValueError):
				pass

		if data is None:
			# Fail-safe: extract what we can from the raw text
			import re

			decision = "REJECT"
			for d in ("APPROVE", "REJECT", "NEEDS_FIX"):
				if d in raw.upper():
					decision = d
					break
			return ReviewResult(
				decision=decision,
				reasoning=raw[:300] if raw else f"Unparseable response for PR #{pr_number}",
				confidence=0.5,
				raw_response=raw,
			)

		decision = data.get("decision", "REJECT").upper()
		if decision not in ("APPROVE", "REJECT", "NEEDS_FIX"):
			decision = "REJECT"

		return ReviewResult(
			decision=decision,
			reasoning=data.get("reasoning", "No reasoning"),
			confidence=float(data.get("confidence", 0.5)),
			raw_response=raw,
			conflicting_files=data.get("conflicting_files", []),
			suggested_fix=data.get("suggested_fix"),
		)

	@property
	def total_cost_usd(self) -> float:
		return self._total_cost_usd

	def _log_cost(self, cost: float, action: str) -> None:
		"""Append a cost entry to the cost log file."""
		try:
			with open(self._cost_log_file, "a", encoding="utf-8") as f:
				f.write(
					json.dumps(
						{
							"ts": time.time(),
							"cost": cost,
							"action": action,
							"session_total": self._total_cost_usd,
						}
					)
					+ "\n"
				)
		except Exception:
			pass

	def get_cost_last_24h(self) -> tuple[float, int]:
		"""Read cost log and sum last 24 hours. Returns (total_cost, num_calls)."""
		cutoff = time.time() - 86400
		total = 0.0
		count = 0
		try:
			with open(self._cost_log_file, encoding="utf-8") as f:
				for line in f:
					line = line.strip()
					if not line:
						continue
					entry = json.loads(line)
					if entry.get("ts", 0) >= cutoff:
						total += entry.get("cost", 0)
						count += 1
		except FileNotFoundError:
			pass
		except Exception:
			pass
		return total, count
