"""Interactive multi-turn chat test for SDK backend.

Run from a standalone terminal:
  ANTHROPIC_API_KEY=... python scripts/merge_governor/tests/test_interactive_chat.py

This simulates the governor experience: the AI agent reviews a PR,
then you chat with it about the review. It remembers everything.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from scripts.merge_governor.ai_backend_sdk import SDKBackend
from scripts.merge_governor.state_manager import GovernorState, PRRecord


async def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY first.")
        sys.exit(1)

    backend = SDKBackend()

    # Simulate governor state with an active PR
    state = GovernorState()
    state.production_head = "857342975f"
    state.active_prs["280"] = PRRecord(
        number=280, title="feat: add store inventory API",
        head_ref="feature/store-inventory", head_sha="abc123",
        updated_at="2026-03-22", staging_port=8001,
        review_decision=None,
    )
    state.merge_history = [
        {"number": 279, "touched_files": ["hrms/api/store.py", "hrms/api/inventory.py"]},
        {"number": 278, "touched_files": ["hrms/utils/scm_roles.py"]},
    ]

    # Step 1: The agent reviews a PR (this gets injected into chat memory)
    print("=== Governor reviewing PR #280 ===\n")
    diff = (
        "diff --git a/hrms/api/store.py b/hrms/api/store.py\n"
        "--- a/hrms/api/store.py\n"
        "+++ b/hrms/api/store.py\n"
        "@@ -15,6 +15,12 @@\n"
        "+@frappe.whitelist()\n"
        "+def get_store_inventory(store_id: str):\n"
        "+    '''Get inventory for a store.'''\n"
        "+    return frappe.get_all('Item', filters={'store': store_id})\n"
    )
    review = await backend.review(
        pr_number=280,
        diff_text=diff,
        merge_context={
            "recent_merges": state.merge_history,
            "protected_surfaces": ["hrms/api/*.py"],
            "production_head": state.production_head,
        },
    )
    state.active_prs["280"].review_decision = review.decision
    backend.inject_review_into_chat(280, review)

    print(f"Decision: {review.decision} (confidence: {review.confidence})")
    print(f"Reasoning: {review.reasoning}\n")
    print("=" * 60)
    print("Chat with the governor. It remembers the review.")
    print("Type 'quit' to exit.\n")

    # Step 2: Interactive chat — the agent remembers the review
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            break

        response = await backend.chat(user_input, state)
        print(f"\nGovernor: {response}\n")
        print(f"  [cost so far: ${backend.total_cost_usd:.4f} | history: {len(backend._chat_history)} messages]\n")


if __name__ == "__main__":
    asyncio.run(main())
