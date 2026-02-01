"""
Pub/Sub Consumer for Blip

Consumes messages from Google Workspace Events API via Pub/Sub.
This enables Blip to receive ALL messages in a space without @mention.

The flow:
1. Google Chat space message → Workspace Events API → Pub/Sub topic
2. This consumer pulls from Pub/Sub subscription
3. Processes message and responds via Google Chat API
"""

import asyncio
import base64
import json
import logging
import os
import tempfile
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

import httpx
from google.oauth2 import service_account
from google.auth.transport.requests import Request

from config import settings

logger = logging.getLogger(__name__)


def get_service_account_credentials(scopes: list, subject: str = None):
    """
    Get Google service account credentials.

    Supports:
    1. GOOGLE_SERVICE_ACCOUNT_JSON env var (base64-encoded JSON)
    2. GOOGLE_SERVICE_ACCOUNT_FILE config (file path)
    3. Default: credentials/task-manager-service.json
    """
    creds = None

    # Option 1: Base64-encoded JSON in environment
    if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
        try:
            json_bytes = base64.b64decode(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
            info = json.loads(json_bytes.decode('utf-8'))
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=scopes
            )
            logger.debug("Using credentials from GOOGLE_SERVICE_ACCOUNT_JSON")
        except Exception as e:
            logger.warning(f"Failed to parse GOOGLE_SERVICE_ACCOUNT_JSON: {e}")

    # Option 2: File path
    if not creds and settings.GOOGLE_SERVICE_ACCOUNT_FILE:
        try:
            creds = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=scopes
            )
            logger.debug(f"Using credentials from {settings.GOOGLE_SERVICE_ACCOUNT_FILE}")
        except Exception as e:
            logger.warning(f"Failed to load {settings.GOOGLE_SERVICE_ACCOUNT_FILE}: {e}")

    # Option 3: Default path
    if not creds:
        default_path = "credentials/task-manager-service.json"
        try:
            creds = service_account.Credentials.from_service_account_file(
                default_path, scopes=scopes
            )
            logger.debug(f"Using credentials from {default_path}")
        except Exception as e:
            raise RuntimeError(
                f"No valid Google credentials found. "
                f"Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE. Error: {e}"
            )

    # Apply domain-wide delegation if subject specified
    if subject:
        creds = creds.with_subject(subject)

    creds.refresh(Request())
    return creds

# Pub/Sub configuration
PROJECT_ID = "quiet-walker-475722-s2"
SUBSCRIPTION_NAME = f"projects/{PROJECT_ID}/subscriptions/blip-chat-pull"
TOPIC_NAME = f"projects/{PROJECT_ID}/topics/blip-chat-events"
BLIP_SPACE_ID = "spaces/AAQABiNmpBg"  # ! Blip Notifications space

# Workspace Events subscription tracking
EVENTS_SUBSCRIPTION_NAME = None
EVENTS_SUBSCRIPTION_EXPIRY = None


class PubSubConsumer:
    """Consumes Workspace Events from Pub/Sub and processes them."""

    def __init__(
        self,
        message_handler: Callable,
        blip_agent: Any,
        frappe_client: Any,
        memory_store: Any,
        conversation_manager: Any
    ):
        self.message_handler = message_handler
        self.blip_agent = blip_agent
        self.frappe_client = frappe_client
        self.memory_store = memory_store
        self.conversation_manager = conversation_manager
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._renewal_task: Optional[asyncio.Task] = None

    def _get_cloud_credentials(self):
        """Get credentials for Pub/Sub API."""
        return get_service_account_credentials(
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )

    def _get_chat_credentials(self):
        """Get credentials for Chat API (with DWD)."""
        return get_service_account_credentials(
            scopes=[
                'https://www.googleapis.com/auth/chat.spaces',
                'https://www.googleapis.com/auth/chat.messages'
            ],
            subject='sam@bebang.ph'
        )

    async def start(self):
        """Start the Pub/Sub consumer in the background."""
        if self.running:
            logger.warning("PubSub consumer already running")
            return

        self.running = True
        logger.info("Starting Pub/Sub consumer for Blip Notifications space")

        # Start the main consumer task
        self._task = asyncio.create_task(self._consume_loop())

        # Start the subscription renewal task
        self._renewal_task = asyncio.create_task(self._renewal_loop())

        # Ensure Workspace Events subscription exists
        await self._ensure_events_subscription()

    async def stop(self):
        """Stop the Pub/Sub consumer."""
        self.running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._renewal_task:
            self._renewal_task.cancel()
            try:
                await self._renewal_task
            except asyncio.CancelledError:
                pass

        logger.info("Pub/Sub consumer stopped")

    async def _consume_loop(self):
        """Main loop that pulls and processes messages from Pub/Sub."""
        logger.info(f"Pub/Sub consumer loop started, subscription: {SUBSCRIPTION_NAME}")

        while self.running:
            try:
                await self._pull_and_process()
            except Exception as e:
                logger.exception(f"Error in Pub/Sub consumer loop: {e}")

            # Poll every 2 seconds
            await asyncio.sleep(2)

    async def _pull_and_process(self):
        """Pull messages from Pub/Sub and process them."""
        creds = self._get_cloud_credentials()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://pubsub.googleapis.com/v1/{SUBSCRIPTION_NAME}:pull",
                headers={
                    "Authorization": f"Bearer {creds.token}",
                    "Content-Type": "application/json"
                },
                json={"maxMessages": 10},
                timeout=30.0
            )

            if response.status_code != 200:
                logger.error(f"Pub/Sub pull error: {response.status_code} - {response.text}")
                return

            result = response.json()
            messages = result.get("receivedMessages", [])

            if not messages:
                return

            logger.info(f"Received {len(messages)} messages from Pub/Sub")

            ack_ids = []
            for msg in messages:
                try:
                    ack_id = msg["ackId"]
                    data = base64.b64decode(msg["message"]["data"]).decode("utf-8")
                    event_data = json.loads(data)

                    await self._process_event(event_data)
                    ack_ids.append(ack_id)

                except Exception as e:
                    logger.exception(f"Error processing Pub/Sub message: {e}")
                    # Still ack to prevent reprocessing
                    ack_ids.append(msg.get("ackId"))

            # Acknowledge processed messages
            if ack_ids:
                await client.post(
                    f"https://pubsub.googleapis.com/v1/{SUBSCRIPTION_NAME}:acknowledge",
                    headers={
                        "Authorization": f"Bearer {creds.token}",
                        "Content-Type": "application/json"
                    },
                    json={"ackIds": ack_ids}
                )

    async def _process_event(self, event_data: dict):
        """Process a Workspace Events event."""
        event_type = event_data.get("type", "")

        if "message.v1.created" not in event_type:
            logger.debug(f"Ignoring event type: {event_type}")
            return

        # Extract the Chat message from the event
        message_resource = event_data.get("message", {})
        if not message_resource:
            logger.warning("No message resource in event")
            return

        # Get sender info
        sender = message_resource.get("sender", {})
        sender_name = sender.get("name", "")

        # Skip bot messages (prevent loop)
        if sender.get("type") == "BOT":
            logger.debug("Skipping bot message")
            return

        # Extract user email from sender
        # The sender name format is "users/USER_ID" - we need to look up the email
        user_email = await self._get_user_email(sender_name)
        if not user_email:
            logger.warning(f"Could not determine user email for {sender_name}")
            return

        message_text = message_resource.get("text", "").strip()
        space_name = message_resource.get("space", {}).get("name", BLIP_SPACE_ID)

        if not message_text:
            return

        logger.info(f"Processing Pub/Sub message from {user_email}: {message_text[:50]}...")

        # Create event structure compatible with existing handler
        event = {
            "type": "MESSAGE",
            "user": {
                "email": user_email,
                "displayName": sender.get("displayName", "")
            },
            "message": {
                "text": message_text,
                "name": message_resource.get("name", "")
            },
            "space": {
                "type": "SPACE",
                "name": space_name
            }
        }

        # Process with existing handler
        response = await self.message_handler(
            event=event,
            blip_agent=self.blip_agent,
            frappe_client=self.frappe_client,
            memory_store=self.memory_store,
            conversation_manager=self.conversation_manager
        )

        # Send response via Chat API (since this is not a request-response flow)
        response_text = response.get("text", "")
        if response_text:
            await self._send_chat_response(space_name, response_text)

    async def _get_user_email(self, user_name: str) -> Optional[str]:
        """Get user email from user name (users/USER_ID format)."""
        if not user_name or not user_name.startswith("users/"):
            return None

        user_id = user_name.replace("users/", "")

        # Use Admin Directory API to look up user
        creds = get_service_account_credentials(
            scopes=['https://www.googleapis.com/auth/admin.directory.user.readonly'],
            subject='sam@bebang.ph'
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://admin.googleapis.com/admin/directory/v1/users",
                headers={"Authorization": f"Bearer {creds.token}"},
                params={"domain": "bebang.ph", "maxResults": 500}
            )

            if response.status_code != 200:
                logger.error(f"Admin API error: {response.status_code}")
                return None

            users = response.json().get("users", [])
            for user in users:
                if user.get("id") == user_id:
                    return user.get("primaryEmail")

        return None

    async def _send_chat_response(self, space_name: str, text: str):
        """Send a response message to the Chat space."""
        creds = self._get_chat_credentials()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://chat.googleapis.com/v1/{space_name}/messages",
                headers={
                    "Authorization": f"Bearer {creds.token}",
                    "Content-Type": "application/json"
                },
                json={"text": text}
            )

            if response.status_code == 200:
                logger.info(f"Sent response to {space_name}")
            else:
                logger.error(f"Failed to send response: {response.status_code} - {response.text}")

    async def _ensure_events_subscription(self):
        """Ensure the Workspace Events subscription exists and is active."""
        global EVENTS_SUBSCRIPTION_NAME, EVENTS_SUBSCRIPTION_EXPIRY

        creds = self._get_chat_credentials()

        async with httpx.AsyncClient() as client:
            # Check for existing subscription
            response = await client.get(
                "https://workspaceevents.googleapis.com/v1/subscriptions",
                headers={"Authorization": f"Bearer {creds.token}"},
                params={"filter": f'targetResource="//chat.googleapis.com/{BLIP_SPACE_ID}"'}
            )

            if response.status_code == 200:
                subs = response.json().get("subscriptions", [])
                for sub in subs:
                    if sub.get("state") == "ACTIVE":
                        EVENTS_SUBSCRIPTION_NAME = sub.get("name")
                        EVENTS_SUBSCRIPTION_EXPIRY = sub.get("expireTime")
                        logger.info(f"Found existing subscription: {EVENTS_SUBSCRIPTION_NAME}")
                        logger.info(f"Expires: {EVENTS_SUBSCRIPTION_EXPIRY}")
                        return

            # Create new subscription
            logger.info("Creating new Workspace Events subscription...")
            await self._create_events_subscription()

    async def _create_events_subscription(self):
        """Create a new Workspace Events subscription."""
        global EVENTS_SUBSCRIPTION_NAME, EVENTS_SUBSCRIPTION_EXPIRY

        creds = self._get_chat_credentials()

        subscription_body = {
            "targetResource": f"//chat.googleapis.com/{BLIP_SPACE_ID}",
            "eventTypes": ["google.workspace.chat.message.v1.created"],
            "notificationEndpoint": {"pubsubTopic": TOPIC_NAME},
            "payloadOptions": {"includeResource": True}
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://workspaceevents.googleapis.com/v1/subscriptions",
                headers={
                    "Authorization": f"Bearer {creds.token}",
                    "Content-Type": "application/json"
                },
                json=subscription_body
            )

            if response.status_code == 200:
                result = response.json()
                sub_response = result.get("response", result)
                EVENTS_SUBSCRIPTION_NAME = sub_response.get("name")
            elif response.status_code == 409:
                # Subscription already exists - extract name from error details
                result = response.json()
                details = result.get("error", {}).get("details", [])
                for detail in details:
                    if detail.get("@type", "").endswith("ErrorInfo"):
                        existing_sub = detail.get("metadata", {}).get("current_subscription")
                        if existing_sub:
                            EVENTS_SUBSCRIPTION_NAME = existing_sub
                            logger.info(f"Using existing subscription: {EVENTS_SUBSCRIPTION_NAME}")
                            return
                logger.info("Subscription exists but couldn't extract name")
                EVENTS_SUBSCRIPTION_EXPIRY = sub_response.get("expireTime")
                logger.info(f"Created subscription: {EVENTS_SUBSCRIPTION_NAME}")
                logger.info(f"Expires: {EVENTS_SUBSCRIPTION_EXPIRY}")
            else:
                logger.error(f"Failed to create subscription: {response.status_code} - {response.text}")

    async def _renewal_loop(self):
        """Background loop to renew the Workspace Events subscription before expiry."""
        while self.running:
            try:
                if EVENTS_SUBSCRIPTION_EXPIRY:
                    # Parse expiry time
                    expiry = datetime.fromisoformat(EVENTS_SUBSCRIPTION_EXPIRY.replace("Z", "+00:00"))
                    now = datetime.now(expiry.tzinfo)

                    # Renew 1 hour before expiry
                    if expiry - now < timedelta(hours=1):
                        logger.info("Subscription expiring soon, renewing...")
                        await self._renew_subscription()

            except Exception as e:
                logger.exception(f"Error in renewal loop: {e}")

            # Check every 30 minutes
            await asyncio.sleep(1800)

    async def _renew_subscription(self):
        """Renew the Workspace Events subscription."""
        global EVENTS_SUBSCRIPTION_NAME, EVENTS_SUBSCRIPTION_EXPIRY

        if not EVENTS_SUBSCRIPTION_NAME:
            await self._create_events_subscription()
            return

        creds = self._get_chat_credentials()

        async with httpx.AsyncClient() as client:
            # Get current subscription
            response = await client.get(
                f"https://workspaceevents.googleapis.com/v1/{EVENTS_SUBSCRIPTION_NAME}",
                headers={"Authorization": f"Bearer {creds.token}"}
            )

            if response.status_code != 200:
                # Subscription no longer exists, create new one
                await self._create_events_subscription()
                return

            # Reactivate/renew the subscription
            # The API uses PATCH to update, setting ttl extends expiry
            response = await client.patch(
                f"https://workspaceevents.googleapis.com/v1/{EVENTS_SUBSCRIPTION_NAME}",
                headers={
                    "Authorization": f"Bearer {creds.token}",
                    "Content-Type": "application/json"
                },
                params={"updateMask": "ttl"},
                json={"ttl": "604800s"}  # 7 days (max)
            )

            if response.status_code == 200:
                result = response.json()
                sub_response = result.get("response", result)
                EVENTS_SUBSCRIPTION_EXPIRY = sub_response.get("expireTime")
                logger.info(f"Renewed subscription, new expiry: {EVENTS_SUBSCRIPTION_EXPIRY}")
            else:
                logger.error(f"Failed to renew: {response.status_code} - {response.text}")
                # Try creating a new subscription
                await self._create_events_subscription()
