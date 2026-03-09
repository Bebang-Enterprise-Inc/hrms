"""Google Chat tools for BEI Analytics Agent.

Contains:
- send_gchat: MCP tool for the agent to send messages to the notification space.
- send_failure_alert: Standalone function for agent.py to call on crash (no agent needed).

Uses service account with Chat Bot scope (NOT DWD).
"""

import os
from typing import Any

from claude_agent_sdk import tool
from google.oauth2 import service_account
from googleapiclient.discovery import build

CREDENTIALS_PATH = os.environ.get(
    "GOOGLE_CREDENTIALS_PATH", "credentials/task-manager-service.json"
)
BOT_SCOPES = ["https://www.googleapis.com/auth/chat.bot"]
NOTIFICATION_SPACE = "spaces/AAQABiNmpBg"


def _get_chat_service():
    """Build an authenticated Chat v1 service using bot credentials."""
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=BOT_SCOPES
    )
    return build("chat", "v1", credentials=creds)


@tool(
    "send_gchat",
    "Send message to Sam's Google Chat notification space",
    {
        "message": str,
    },
)
async def send_gchat(args: dict[str, Any]) -> dict[str, Any]:
    """Send a message to the BEI notification space in Google Chat."""
    message = args["message"]

    try:
        service = _get_chat_service()

        response = (
            service.spaces()
            .messages()
            .create(
                parent=NOTIFICATION_SPACE,
                body={"text": message},
            )
            .execute()
        )

        message_id = response.get("name", "")
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Message sent to Google Chat (ID: {message_id})",
                }
            ]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error sending message: {e}"}],
            "is_error": True,
        }


async def send_gchat_impl(args: dict[str, Any]) -> dict[str, Any]:
    """Plain async function for the direct Anthropic API agentic loop."""
    return await send_gchat(args)


def send_failure_alert(error_message: str) -> bool:
    """Send crash notification to Google Chat. Works outside agent context.

    This is a standalone function (NOT a @tool) meant to be called directly
    by agent.py when the agent crashes. It must work without the agent being alive.
    """
    try:
        service = _get_chat_service()
        text = (
            "\u26a0\ufe0f *BEI Analytics Agent FAILED*\n\n"
            f"{error_message}\n\n"
            "Check logs at: analytics-agent/runs/"
        )
        service.spaces().messages().create(
            parent=NOTIFICATION_SPACE,
            body={"text": text},
        ).execute()
        return True
    except Exception as e:
        print(f"CRITICAL: Failed to send failure alert: {e}")
        return False
