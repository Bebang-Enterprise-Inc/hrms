"""
Multi-Model AI Intent Parser

Uses Claude Haiku 4.5 for intent parsing AND conversational responses - LATEST
Uses Gemini 3 Flash for data formatting only - LATEST
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

import anthropic
from google import genai

from .prompts import INTENT_PARSER_SYSTEM, RESPONSE_FORMATTER_SYSTEM

logger = logging.getLogger(__name__)


class IntentParser:
    """
    Multi-model AI parser for Blip.

    - Claude Haiku 4.5: Intent parsing + conversational responses
    - Gemini 3 Flash Preview: Data formatting only (when there's actual data)
    """

    def __init__(
        self,
        api_key: str,
        gemini_api_key: str,
        model: str = "claude-haiku-4-5-20251001",
        gemini_model: str = "gemini-3-flash-preview"
    ):
        """
        Initialize the multi-model parser.

        Args:
            api_key: Anthropic API key
            gemini_api_key: Google Gemini API key
            model: Claude model for intent parsing
            gemini_model: Gemini model for response formatting
        """
        # Claude for intent parsing AND conversational responses
        self.claude = anthropic.Anthropic(api_key=api_key)
        self.claude_model = model

        # Gemini for data formatting only
        self.gemini = genai.Client(api_key=gemini_api_key)
        self.gemini_model = gemini_model

    async def parse(self, message: str, user_context: dict, conversation_history: str = "") -> dict:
        """
        Parse a user message into a structured intent using Claude.

        For conversational messages, Claude also generates the response directly.

        Args:
            message: The user's question
            user_context: Context about the user (permissions, store, etc.)
            conversation_history: Previous messages for context (last 10)

        Returns:
            Parsed intent with entities, and optionally direct_response
        """
        try:
            # Add context about the user to help with parsing
            context_info = self._build_context_string(user_context)

            # Build full context with conversation history
            full_context = context_info
            if conversation_history:
                full_context = f"{context_info}\n\n{conversation_history}"

            logger.info(f"Parsing with context length: {len(full_context)} chars")

            # Use Claude for intent parsing (and conversational responses)
            response = self.claude.messages.create(
                model=self.claude_model,
                max_tokens=1000,  # Increased for conversational responses
                system=INTENT_PARSER_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": f"{full_context}\n\nUser message: {message}"
                    }
                ]
            )

            # Extract JSON from response
            response_text = response.content[0].text.strip()
            logger.debug(f"Claude raw response: {response_text[:200]}...")

            # Handle markdown code blocks
            if response_text.startswith("```"):
                lines = response_text.split("```")
                if len(lines) >= 2:
                    response_text = lines[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]
                    response_text = response_text.strip()

            parsed = json.loads(response_text)
            parsed["original_message"] = message

            # Resolve relative dates
            if parsed.get("entities"):
                parsed["entities"] = self._resolve_dates(parsed.get("entities", {}))

            logger.info(f"Parsed: intent={parsed.get('intent')}, needs_data={parsed.get('needs_data')}")

            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.error(f"Raw response: {response_text[:500] if 'response_text' in dir() else 'N/A'}")
            return {
                "intent": "conversation",
                "entities": {},
                "needs_data": False,
                "direct_response": "I had trouble understanding that. Could you rephrase your question?",
                "confidence": 0.0,
                "original_message": message
            }
        except Exception as e:
            logger.exception(f"Error parsing intent: {e}")
            return {
                "intent": "conversation",
                "entities": {},
                "needs_data": False,
                "direct_response": f"Sorry, I encountered an issue. Please try again.",
                "confidence": 0.0,
                "original_message": message,
                "error": str(e)
            }

    async def format_response(
        self,
        intent: str,
        data: dict,
        user_context: dict,
        parsed: dict = None
    ) -> str:
        """
        Format query results into a human-readable response.

        If the intent doesn't need data (conversational), uses Claude's direct_response.
        Otherwise, formats data using Gemini.

        Args:
            intent: The intent type
            data: Query result data (or None for conversational)
            user_context: User context
            parsed: The parsed intent (contains direct_response for conversational)

        Returns:
            Formatted response string
        """
        # Check if Claude already provided a direct response
        if parsed and parsed.get("direct_response"):
            logger.info("Using Claude's direct response")
            return parsed["direct_response"]

        # Handle special response types (legacy support)
        if data.get("type") == "help":
            return self._get_help_response()

        if data.get("type") == "greeting":
            name = data.get("user_name", "").split()[0] if data.get("user_name") else ""
            greeting = f"Hey{' ' + name if name else ''}!"
            return f"{greeting} I'm Blip, BEBANG's AI assistant. What can I help you with?"

        if data.get("type") == "weather":
            return data.get("formatted_response", "Weather data unavailable.")

        if data.get("type") == "conversation":
            # Fallback for conversation type without direct_response
            return "I'm here to help! Ask me about sales, inventory, HR, or anything BEBANG-related."

        if data.get("type") == "unknown":
            return (
                "I'm not sure what you're asking. "
                "Try asking about sales, inventory, leave, attendance, or weather. "
                "Or just say hi!"
            )

        if data.get("error"):
            return f"Sorry, I couldn't get that info: {data['error']}"

        if not data or data.get("empty"):
            return "No data found for that query. Try a different date range or store?"

        try:
            # Use Gemini 3 Flash for data formatting only
            prompt = (
                f"{RESPONSE_FORMATTER_SYSTEM}\n\n"
                f"The user asked about {intent}. Format this data:\n\n"
                f"{json.dumps(data, indent=2, default=str)}"
            )

            response = self.gemini.models.generate_content(
                model=self.gemini_model,
                contents=prompt
            )

            return response.text.strip()

        except Exception as e:
            logger.exception(f"Error formatting response with Gemini: {e}")
            return self._simple_format(intent, data)

    def _build_context_string(self, user_context: dict) -> str:
        """Build context string for intent parsing."""
        parts = []

        # User identity
        if user_context.get("email"):
            name = user_context.get("employee_name") or user_context.get("email").split("@")[0]
            parts.append(f"User: {name}")

        if user_context.get("is_admin"):
            parts.append("Role: Admin (full data access)")
        else:
            if user_context.get("store"):
                parts.append(f"User's store: {user_context['store']}")
            if user_context.get("area"):
                parts.append(f"User's area: {user_context['area']}")

        # Current time context
        now = datetime.now()
        parts.append(f"Current date: {now.strftime('%Y-%m-%d')} ({now.strftime('%A')})")
        parts.append(f"Current time: {now.strftime('%I:%M %p')}")

        return "\n".join(parts) if parts else "User context: General employee"

    def _resolve_dates(self, entities: dict) -> dict:
        """Resolve relative date references to actual dates."""
        if not entities:
            return {}

        period = entities.get("period")
        today = datetime.now().date()

        if period == "today":
            entities["date"] = today.isoformat()
        elif period == "yesterday":
            entities["date"] = (today - timedelta(days=1)).isoformat()
        elif period == "tomorrow":
            entities["date"] = (today + timedelta(days=1)).isoformat()

        return entities

    def _get_help_response(self) -> str:
        """Return help text."""
        return """🥭 I'm Blip, BEBANG's AI assistant! Here's what I can help with:

**📊 Sales**
- "Sales at Megamall today"
- "How did Trinoma do this week?"

**📦 Inventory**
- "Stock levels at Market Market"
- "Ice inventory at BGC stores"

**🏭 Commissary**
- "Leche Flan production today"
- "Frozen Milk output this week"

**👥 HR**
- "Who's on leave tomorrow?"
- "My leave balance"
- "Team attendance today"

**🌤️ Weather**
- "Weather at Megamall" (with sales forecast!)

Just ask naturally - I understand nicknames like "megamall", "moa", "fairview"!"""

    def _simple_format(self, intent: str, data: dict) -> str:
        """Simple fallback formatting."""
        if isinstance(data, dict):
            lines = []
            for key, value in data.items():
                if key not in ["type", "empty", "error", "records"]:
                    if isinstance(value, (int, float)) and key.endswith("sales"):
                        lines.append(f"- {key.replace('_', ' ').title()}: ₱{value:,.2f}")
                    else:
                        lines.append(f"- {key.replace('_', ' ').title()}: {value}")
            return "\n".join(lines) if lines else "Data retrieved."
        return str(data)
