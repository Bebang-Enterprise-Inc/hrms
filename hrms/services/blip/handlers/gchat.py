"""
Google Chat Webhook Handler

Handles incoming events from Google Chat and routes them
to the Blip agent for processing.

Supports both:
- Standard HTTP endpoint format (type at top level)
- Google Workspace Add-ons format (chat/commonEventObject structure)
"""

import logging
from typing import Any, Tuple

from config import settings

logger = logging.getLogger(__name__)


def normalize_event(raw_event: dict) -> Tuple[dict, str]:
    """
    Normalize event from either HTTP endpoint or Add-ons format.

    Add-ons format has: chat, commonEventObject, authorizationEventObject
    HTTP endpoint format has: type, user, message, space at top level

    Returns:
        Tuple of (normalized_event, event_type)
    """
    # Check if this is Add-ons format (has 'chat' key)
    if "chat" in raw_event:
        logger.info("Detected Google Workspace Add-ons event format")
        chat = raw_event.get("chat", {})
        common = raw_event.get("commonEventObject", {})

        # Extract message payload
        message_payload = chat.get("messagePayload", {})
        message = message_payload.get("message", {})
        space = message_payload.get("space", {})

        # Get user from common event object
        user_info = common.get("userLocale", "")
        # Try to get email from various places
        user_email = ""
        if "invokedFunction" in common:
            # Sometimes in invokedFunction context
            pass

        # Check for user in the message sender
        sender = message.get("sender", {})
        user_email = sender.get("email", "")
        user_name = sender.get("displayName", "")

        # Determine event type from Add-ons format
        if message_payload:
            event_type = "MESSAGE"
        elif chat.get("addedToSpacePayload"):
            event_type = "ADDED_TO_SPACE"
            space = chat.get("addedToSpacePayload", {}).get("space", {})
        elif chat.get("removedFromSpacePayload"):
            event_type = "REMOVED_FROM_SPACE"
        else:
            event_type = "UNKNOWN"

        # Build normalized event matching HTTP endpoint format
        normalized = {
            "type": event_type,
            "user": {
                "email": user_email,
                "displayName": user_name,
            },
            "message": {
                "text": message.get("text", ""),
                "argumentText": message.get("argumentText", ""),
            },
            "space": {
                "type": space.get("type", ""),
                "name": space.get("name", ""),
                "displayName": space.get("displayName", ""),
            }
        }

        logger.info(f"Normalized Add-ons event: type={event_type}, user={user_email}")
        return normalized, event_type

    else:
        # Standard HTTP endpoint format
        event_type = raw_event.get("type", "")
        logger.info(f"Standard HTTP endpoint format: type={event_type}")
        return raw_event, event_type


async def handle_gchat_event(
    event: dict,
    blip_agent: Any,
    frappe_client: Any,
    memory_store: Any = None,
    conversation_manager: Any = None
) -> dict:
    """
    Handle a Google Chat event.

    Args:
        event: The Google Chat event payload (raw from webhook)
        blip_agent: Blip agentic assistant instance
        frappe_client: Frappe API client instance
        memory_store: Long-term memory storage
        conversation_manager: Short-term conversation history manager

    Returns:
        Response dict with 'text' key for Google Chat
    """
    # Normalize event format
    normalized_event, event_type = normalize_event(event)

    if event_type == "ADDED_TO_SPACE":
        return handle_added_to_space(normalized_event)

    elif event_type == "REMOVED_FROM_SPACE":
        return {"text": ""}  # No response needed

    elif event_type == "MESSAGE":
        return await handle_message(
            normalized_event,
            blip_agent,
            frappe_client,
            memory_store,
            conversation_manager
        )

    else:
        logger.warning(f"Unknown event type: {event_type}")
        logger.warning(f"Raw event keys: {list(event.keys())}")
        return {"text": "I received an unknown event type."}


def handle_added_to_space(event: dict) -> dict:
    """Handle when Blip is added to a space or DM."""
    space_type = event.get("space", {}).get("type", "")
    user_name = event.get("user", {}).get("displayName", "there")

    if space_type == "DM":
        return {
            "text": (
                f"Hi {user_name}! I'm Blip, BEI's AI assistant.\n\n"
                "I can help you with:\n"
                "- Sales data (by store, area, or company-wide)\n"
                "- Food cost analysis\n"
                "- Commissary production\n"
                "- Inventory levels\n"
                "- HR info (leave, attendance)\n"
                "- Weather forecasts\n\n"
                "Just ask me anything! For example:\n"
                '- "What are sales at Market Market today?"\n'
                '- "Who is on leave tomorrow?"\n'
                '- "What is the weather forecast?"\n\n'
                "I can also remember things about you and have natural conversations!"
            )
        }
    else:
        return {
            "text": (
                "Hi everyone! I'm Blip, BEI's AI assistant. "
                "Mention me with your question and I'll help.\n\n"
                "Example: @Blip What are today's sales?"
            )
        }


async def handle_message(
    event: dict,
    blip_agent: Any,
    frappe_client: Any,
    memory_store: Any,
    conversation_manager: Any
) -> dict:
    """
    Handle an incoming message using the agentic Blip.

    Flow:
    1. Extract user info and get conversation history
    2. Build user context (permissions, store, roles)
    3. Run the agentic loop (Claude decides what tools to use)
    4. Store messages in history
    5. Return response
    """
    user = event.get("user", {})
    user_email = user.get("email", "")
    space = event.get("space", {})
    space_name = space.get("name", "")
    message = event.get("message", {})
    message_text = message.get("text", "").strip()

    # Remove @Blip mention if present
    message_text = message_text.replace("@Blip", "").strip()

    if not message_text:
        return {"text": "I didn't catch that. What would you like to know?"}

    logger.info(f"Processing message from {user_email}: {message_text[:100]}...")

    # Get conversation history for context
    conversation_history = []
    if conversation_manager:
        conversation_history = conversation_manager.get_messages(space_name, user_email)
        msg_count = conversation_manager.get_message_count(space_name, user_email)
        logger.info(f"Conversation context: {msg_count} previous messages")

        # Store user message in history BEFORE processing
        conversation_manager.add_user_message(space_name, user_email, message_text)

    try:
        # Build user context for permissions
        user_context = await get_user_context(user_email, frappe_client)

        # Run the agentic loop
        response_text = await blip_agent.run(
            user_message=message_text,
            user_context=user_context,
            frappe_client=frappe_client,
            memory_store=memory_store,
            conversation_history=conversation_history
        )

        # Store assistant response in history
        if conversation_manager:
            conversation_manager.add_assistant_message(space_name, user_email, response_text)

        return {"text": response_text}

    except Exception as e:
        logger.exception(f"Error processing message: {e}")
        error_msg = (
            "Oops, something went wrong on my end. "
            "Could you try rephrasing that?"
        )
        # Store error response too for context
        if conversation_manager:
            conversation_manager.add_assistant_message(space_name, user_email, error_msg)
        return {"text": error_msg}


async def get_user_context(user_email: str, frappe_client: Any) -> dict:
    """
    Get user context including permissions.

    Args:
        user_email: The user's email address
        frappe_client: Frappe API client

    Returns:
        User context dict with permissions
    """
    is_admin = user_email in settings.admin_email_list

    context = {
        "email": user_email,
        "is_admin": is_admin,
        "roles": [],
        "employee": None,
        "employee_name": None,
        "store": None,
        "area": None
    }

    if is_admin:
        # Admin has full access
        context["roles"] = ["System Manager", "Administrator"]
        return context

    try:
        # Get user info from Frappe
        user_info = await frappe_client.get_user_context(user_email)
        context.update(user_info)
    except Exception as e:
        logger.warning(f"Could not get user context for {user_email}: {e}")

    return context
