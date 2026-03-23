"""Live demo — simulates governor activity while chat is open.

Shows what the governor terminal looks like with real-time PR events
appearing alongside the interactive chat.

Run: python scripts/merge_governor/tests/test_live_demo.py
(Set ANTHROPIC_API_KEY first for AI chat, or it falls back to keyword-only)
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from scripts.merge_governor.state_manager import GovernorState, PRRecord

# ANSI colors
DIM = "\033[90m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ts():
    return time.strftime("%H:%M:%S")


def activity(msg, color=DIM):
    print(f"{color}[{ts()}] {msg}{RESET}", flush=True)


async def simulate_activity(state, stop_event):
    """Simulate PR events happening in the background."""
    await asyncio.sleep(3)
    activity("PR watcher polling...", DIM)

    await asyncio.sleep(2)
    activity(f"{GREEN}New PR #283 detected:{RESET} feat: add reports API [{CYAN}feature/reports{RESET}]")
    state.active_prs["283"] = PRRecord(
        number=283, title="feat: add reports API",
        head_ref="feature/reports", head_sha="def456",
        updated_at="2026-03-22", staging_port=8002,
    )

    await asyncio.sleep(4)
    activity(f"Port :{CYAN}8002{RESET} assigned to PR #283")
    activity(f"Deploying PR #283 to staging :8002...")

    await asyncio.sleep(5)
    activity(f"{GREEN}PR #283 deployed to staging{RESET}")
    activity(f"Reviewing PR #283...")

    await asyncio.sleep(4)
    activity(f"{GREEN}PR #283 -> APPROVE{RESET} (confidence: 0.94, cost: $0.004)")
    state.active_prs["283"].review_decision = "APPROVE"
    state.merge_queue.append(283)

    await asyncio.sleep(6)
    activity(f"{GREEN}New PR #284 detected:{RESET} fix: correct overtime calc [{CYAN}fix/overtime-calc{RESET}]")
    state.active_prs["284"] = PRRecord(
        number=284, title="fix: correct overtime calc",
        head_ref="fix/overtime-calc", head_sha="ghi789",
        updated_at="2026-03-22",
    )

    await asyncio.sleep(4)
    activity(f"Port :{CYAN}8003{RESET} assigned to PR #284")
    activity(f"Reviewing PR #284...")

    await asyncio.sleep(4)
    activity(f"{RED}PR #284 -> REJECT{RESET} (confidence: 0.88) - modifies hrms/api/overtime.py, conflicts with PR #279")
    state.active_prs["284"].review_decision = "REJECT"

    await asyncio.sleep(5)
    activity(f"Merging PR #283 to production...")

    await asyncio.sleep(3)
    activity(f"{GREEN}PR #283 merged!{RESET} Triggering production deploy...")

    await asyncio.sleep(4)
    activity(f"L1 smoke test: ping OK, CSS OK, JS OK")
    activity(f"{GREEN}Merge cycle complete for PR #283{RESET}")

    # Keep running until stopped
    while not stop_event.is_set():
        await asyncio.sleep(30)
        if not stop_event.is_set():
            activity("PR watcher polling... no new PRs", DIM)


async def chat_loop(state, stop_event):
    """Interactive chat alongside live activity."""
    loop = asyncio.get_event_loop()

    # Optional: set up SDK backend for AI chat
    ai_backend = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from scripts.merge_governor.ai_backend_sdk import SDKBackend
            ai_backend = SDKBackend()
            if await ai_backend.health_check():
                activity(f"{GREEN}AI chat ready{RESET} (SDK backend)")
            else:
                ai_backend = None
        except Exception:
            pass

    from scripts.merge_governor.chat_handler import ChatHandler
    handler = ChatHandler(ai_backend=ai_backend)

    while not stop_event.is_set():
        try:
            line = await loop.run_in_executor(None, lambda: input(f"\n{BOLD}You:{RESET} "))
            if not line.strip():
                continue
            if line.strip().lower() in ("quit", "exit", "q"):
                stop_event.set()
                break

            response = await handler.handle(line.strip(), state)

            if response.source == "llm" and ai_backend:
                cost = ai_backend.total_cost_usd
                history = len(ai_backend._chat_history)
                activity(f"Chat cost: ${cost:.4f} ({history} messages)", DIM)

            print(f"\n{BOLD}Governor:{RESET} {response.text}")

            if response.source == "llm" and ai_backend:
                print(f"{DIM}  [cost: ${ai_backend.total_cost_usd:.4f} | history: {len(ai_backend._chat_history)} msgs]{RESET}")

        except (EOFError, KeyboardInterrupt):
            stop_event.set()
            break
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")


async def main():
    state = GovernorState()
    state.started_at = time.time()
    state.production_head = "857342975f"
    state.merge_history = [
        {"number": 279, "touched_files": ["hrms/api/overtime.py", "hrms/utils/scm_roles.py"]},
    ]

    print(f"""
{BOLD}{'='*60}
  governor-erp [LIVE DEMO]
  PRs: 0 active | Queue: 0 | Ports: 0/10
  AI: {'sdk' if os.environ.get('ANTHROPIC_API_KEY') else 'none'} | Production: 85734297
{'='*60}{RESET}
  Type commands or chat naturally. 'help' for commands.
  Activity will appear in real-time above your prompt.
""")

    stop_event = asyncio.Event()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(simulate_activity(state, stop_event))
        tg.create_task(chat_loop(state, stop_event))

    print(f"\n{DIM}Governor stopped.{RESET}")


if __name__ == "__main__":
    asyncio.run(main())
