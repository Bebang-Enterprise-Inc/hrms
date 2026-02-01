"""
Blip Agentic Loop

Implements an agentic assistant that can reason and use tools autonomously,
similar to Claude Code. Uses Anthropic's tool use API with an agentic loop.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import anthropic

from .tools import BLIP_TOOLS, CONFIRMATION_REQUIRED
from .tool_executor import execute_tool

logger = logging.getLogger(__name__)


class BlipAgent:
    """
    Agentic Blip assistant that can reason and use tools autonomously.

    The agent runs in a loop:
    1. Analyze user message and context
    2. Decide what action to take (use tool or respond)
    3. Execute tools and observe results
    4. Repeat until task is complete

    This is similar to how Claude Code operates - the model decides
    what tools to use rather than following a rigid intent router.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5-20251001",
        max_iterations: int = 10
    ):
        """
        Initialize the Blip agent.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
            max_iterations: Maximum tool call iterations to prevent infinite loops
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_iterations = max_iterations

    async def run(
        self,
        user_message: str,
        user_context: Dict[str, Any],
        frappe_client: Any,
        memory_store: Any = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """
        Run the agentic loop until Claude produces a final response.

        Args:
            user_message: The user's message
            user_context: User permissions and context (employee, store, roles)
            frappe_client: Frappe API client for tool execution
            memory_store: Optional memory storage for personalization
            conversation_history: Previous messages for context

        Returns:
            Final response text from the agent
        """
        # Build messages list
        messages = self._prepare_messages(conversation_history, user_message)

        # Build system prompt with user context
        system_prompt = self._build_system_prompt(user_context)

        logger.info(f"Starting agentic loop for: {user_message[:100]}...")

        for iteration in range(self.max_iterations):
            logger.debug(f"Iteration {iteration + 1}/{self.max_iterations}")

            try:
                # Call Claude with tools
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    system=system_prompt,
                    tools=BLIP_TOOLS,
                    messages=messages
                )

                logger.debug(f"Response stop_reason: {response.stop_reason}")

                # Check if Claude is done (no tool calls)
                if response.stop_reason == "end_turn":
                    return self._extract_text_response(response)

                # Process tool calls
                if response.stop_reason == "tool_use":
                    # Add assistant's response to message history
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })

                    # Execute each tool and collect results
                    tool_results = await self._execute_tools(
                        response.content,
                        user_context,
                        frappe_client,
                        memory_store
                    )

                    # Add tool results to messages
                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })

                    # Continue loop

                elif response.stop_reason == "max_tokens":
                    logger.warning("Response truncated due to max_tokens")
                    return self._extract_text_response(response) + "..."

            except anthropic.APIError as e:
                logger.exception(f"Anthropic API error: {e}")
                return "I'm having trouble connecting to my brain right now. Please try again."

        # Max iterations reached
        logger.warning(f"Max iterations ({self.max_iterations}) reached")
        return "I got a bit stuck thinking about that. Could you try rephrasing your question?"

    def _prepare_messages(
        self,
        conversation_history: Optional[List[Dict]],
        user_message: str
    ) -> List[Dict]:
        """Prepare the messages list for the API call."""
        messages = []

        # Add conversation history if available
        if conversation_history:
            # Format: [{"role": "user/assistant", "content": "..."}]
            for msg in conversation_history[-10:]:  # Last 10 messages
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })

        return messages

    def _build_system_prompt(self, user_context: Dict[str, Any]) -> str:
        """Build the system prompt with user context and instructions."""
        name = user_context.get("employee_name", "")
        if name:
            name = name.split()[0]  # First name only
        else:
            name = user_context.get("email", "").split("@")[0]

        is_admin = user_context.get("is_admin", False)
        store = user_context.get("store", "")
        area = user_context.get("area", "")
        roles = user_context.get("roles", [])

        now = datetime.now()

        return f"""You are Blip, BEBANG's AI assistant. You're helpful, friendly, and knowledgeable about the company.

ABOUT BEBANG (BEI - Bebang Enterprise Inc.):
- Philippine halo-halo chain with ~50 stores across Metro Manila
- Products: Presidential Halo-Halo (premium), Mango Graham, Classic Halo-Halo
- Add-ons: Leche Flan, Ube, Ice Cream
- Commissary (Bebang Kitchen): Produces Frozen Milk, Leche Flan, Ube Halaya, Toppings

STORE AREAS:
- BGC: Market Market, Uptown Mall, High Street
- Ortigas: Megamall, Podium, Shangri-La
- Makati: Greenbelt, Glorietta, Landmark
- North: Trinoma, SM North, Fairview

USER CONTEXT:
- Name: {name or 'Employee'}
- Email: {user_context.get('email', 'Unknown')}
- Store: {store or 'Not assigned'}
- Area: {area or 'Not assigned'}
- Admin: {'Yes' if is_admin else 'No'}
- Roles: {', '.join(roles) if roles else 'Standard employee'}

CURRENT TIME:
- Date: {now.strftime('%Y-%m-%d')} ({now.strftime('%A')})
- Time: {now.strftime('%I:%M %p')} (Philippine Time)

YOUR APPROACH:
1. Understand what the user needs - don't just match keywords
2. Use tools to get real data - NEVER make up numbers or facts
3. If you need multiple pieces of information, call multiple tools
4. Synthesize results into a helpful, natural response
5. If something is unclear, ask for clarification
6. Be proactive - if you notice issues (low inventory, anomalies), mention them

TOOL USAGE:
- You have access to various tools for sales, inventory, HR, attendance, etc.
- ALWAYS use tools for factual data - don't guess or hallucinate
- You can call multiple tools if needed to answer a question
- For actions (like submitting leave), ALWAYS confirm with the user first

COMMUNICATION STYLE:
- Be conversational and friendly, not robotic
- Use ₱ for Philippine Peso amounts (e.g., ₱45,230)
- Keep responses concise but complete
- Don't start every response with "Based on the data..." - be natural
- You can use light humor when appropriate
- If you don't know something, say so honestly

MEMORY:
- You can remember facts about users using the remember_fact tool
- Use recall_facts to personalize your responses when relevant
- Remember preferences, schedules, and important context

PERMISSIONS:
- Only show data the user is authorized to see
- Admins can see all company data
- Regular employees can see their own data and their store's data
- Respect privacy - don't share personal info about other employees"""

    async def _execute_tools(
        self,
        content_blocks: List,
        user_context: Dict[str, Any],
        frappe_client: Any,
        memory_store: Any
    ) -> List[Dict]:
        """Execute tool calls and return results."""
        tool_results = []

        for block in content_blocks:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input
                tool_id = block.id

                logger.info(f"Executing tool: {tool_name}")
                logger.debug(f"Tool input: {tool_input}")

                # Check if tool requires confirmation
                if tool_name in CONFIRMATION_REQUIRED:
                    # For now, just execute - in production, you'd want to
                    # interrupt the loop and ask for user confirmation
                    logger.warning(f"Tool {tool_name} requires confirmation - executing anyway")

                # Execute the tool
                result = await execute_tool(
                    tool_name=tool_name,
                    tool_input=tool_input,
                    user_context=user_context,
                    frappe_client=frappe_client,
                    memory_store=memory_store
                )

                logger.debug(f"Tool result: {json.dumps(result, default=str)[:500]}...")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": json.dumps(result, default=str)
                })

        return tool_results

    def _extract_text_response(self, response) -> str:
        """Extract text content from Claude's response."""
        for block in response.content:
            if hasattr(block, "text"):
                return block.text

        return "I processed your request but didn't generate a response. Please try again."


class BlipAgentWithFallback(BlipAgent):
    """
    Blip agent with fallback to simple responses for common patterns.

    This extends the base agent to handle simple greetings and help requests
    without making API calls, reducing latency and cost.
    """

    SIMPLE_RESPONSES = {
        "hi": "Hey! I'm Blip, BEBANG's AI assistant. What can I help you with today?",
        "hello": "Hello! I'm Blip. How can I help you?",
        "hey": "Hey there! What can I do for you?",
        "thanks": "You're welcome! Let me know if you need anything else.",
        "thank you": "Happy to help! Anything else you need?",
        "bye": "See you later! Have a great day!",
        "goodbye": "Goodbye! Don't hesitate to reach out if you need anything.",
    }

    async def run(
        self,
        user_message: str,
        user_context: Dict[str, Any],
        frappe_client: Any,
        memory_store: Any = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """Run with simple pattern matching fallback."""
        # Check for simple patterns first
        message_lower = user_message.lower().strip()

        for pattern, response in self.SIMPLE_RESPONSES.items():
            if message_lower == pattern or message_lower == f"{pattern}!":
                name = user_context.get("employee_name", "").split()[0]
                if name and "{name}" in response:
                    response = response.replace("{name}", name)
                return response

        # Fall back to full agentic loop
        return await super().run(
            user_message=user_message,
            user_context=user_context,
            frappe_client=frappe_client,
            memory_store=memory_store,
            conversation_history=conversation_history
        )
