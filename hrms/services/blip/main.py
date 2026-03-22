"""
Blip: AI-Powered Company Assistant

Main FastAPI application that handles webhooks from Google Chat,
Telegram, and WhatsApp, and uses Claude AI with agentic tool use
to answer questions and perform tasks for BEI employees.

Architecture:
- Claude Haiku 4.5 with tool use for agentic reasoning
- Frappe API tools for business data access
- Long-term memory for personalization
- Short-term conversation history for context
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from config import settings
from handlers.gchat import handle_gchat_event
from ai.agent import BlipAgentWithFallback
from frappe_client import FrappeClient
from memory import BlipMemory, conversation_manager
from pubsub_consumer import PubSubConsumer

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global instances
blip_agent: BlipAgentWithFallback = None
frappe_client: FrappeClient = None
memory_store: BlipMemory = None
pubsub_consumer: PubSubConsumer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources."""
    global blip_agent, frappe_client, memory_store, pubsub_consumer

    logger.info("Starting Blip AI Assistant (Agentic Mode)...")

    # Initialize the agentic Blip agent
    blip_agent = BlipAgentWithFallback(
        api_key=settings.ANTHROPIC_API_KEY,
        model=settings.CLAUDE_MODEL,
        max_iterations=10  # Prevent infinite loops
    )
    logger.info(f"Blip Agent initialized with model: {settings.CLAUDE_MODEL}")

    # Initialize Frappe client
    frappe_client = FrappeClient()
    logger.info(f"Frappe client initialized: {settings.FRAPPE_URL}")

    # Initialize memory store (in-memory for now, Redis in production)
    # TODO: Add Redis support with settings.REDIS_URL
    memory_store = BlipMemory()
    logger.info("Memory store initialized (in-memory mode)")

    # Initialize Pub/Sub consumer for receiving all messages in dedicated space
    # This allows Blip to respond without @mention in the "! Blip Notifications" space
    try:
        pubsub_consumer = PubSubConsumer(
            message_handler=handle_gchat_event,
            blip_agent=blip_agent,
            frappe_client=frappe_client,
            memory_store=memory_store,
            conversation_manager=conversation_manager
        )
        await pubsub_consumer.start()
        logger.info("Pub/Sub consumer started - Blip will receive all messages in dedicated space")
    except Exception as e:
        logger.warning(f"Pub/Sub consumer failed to start: {e}")
        logger.warning("Blip will only respond to @mentions (webhook mode only)")

    yield

    logger.info("Shutting down Blip AI Assistant...")

    # Stop Pub/Sub consumer
    if pubsub_consumer:
        await pubsub_consumer.stop()


app = FastAPI(
    title="Blip AI Assistant",
    description="AI-powered agentic assistant for BEI with tool use capabilities",
    version="2.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "mode": "agentic",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/status")
async def status():
    """Detailed status endpoint."""
    return {
        "status": "running",
        "service": settings.SERVICE_NAME,
        "version": "2.0.0",
        "mode": "agentic",
        "frappe_url": settings.FRAPPE_URL,
        "claude_model": settings.CLAUDE_MODEL,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/webhook/gchat")
async def gchat_webhook(request: Request):
    """
    Google Chat webhook endpoint.

    Receives events when users message Blip in Google Chat.
    Supports both HTTP endpoint format and Google Workspace Add-ons format.
    """
    try:
        event = await request.json()
        is_addons_format = "chat" in event
        logger.info(f"Received Google Chat event: {event.get('type', 'unknown')} (Add-ons: {is_addons_format})")
        logger.info(f"Event keys: {list(event.keys())}")
        logger.debug(f"Full event: {event}")

        response = await handle_gchat_event(
            event=event,
            blip_agent=blip_agent,
            frappe_client=frappe_client,
            memory_store=memory_store,
            conversation_manager=conversation_manager
        )

        # For Add-ons format, wrap response in required structure
        if is_addons_format:
            text = response.get("text", "")
            addons_response = {
                "hostAppDataAction": {
                    "chatDataAction": {
                        "createMessageAction": {
                            "message": {
                                "text": text
                            }
                        }
                    }
                }
            }
            logger.info(f"Returning Add-ons response: {text[:100]}...")
            return JSONResponse(content=addons_response)

        return JSONResponse(content=response)

    except Exception as e:
        logger.exception(f"Error handling Google Chat event: {e}")
        error_text = "Sorry, I encountered an error. Please try again."
        # Return appropriate format based on request
        if "chat" in (await request.body()).decode():
            return JSONResponse(content={
                "hostAppDataAction": {
                    "chatDataAction": {
                        "createMessageAction": {
                            "message": {"text": error_text}
                        }
                    }
                }
            })
        return JSONResponse(content={"text": error_text})


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """
    Telegram webhook endpoint.

    Receives updates when users message the Blip Telegram bot.
    """
    # TODO: Implement in Phase 5
    return {"status": "not_implemented"}


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    WhatsApp webhook endpoint.

    Receives messages from WhatsApp Business API.
    """
    # TODO: Implement in Phase 5
    return {"status": "not_implemented"}


@app.post("/api/chat")
async def web_chat(request: Request):
    """
    Web chat API endpoint.

    For the chat widget in my.bebang.ph.
    """
    try:
        data = await request.json()
        user_email = data.get("user_email")
        message = data.get("message")

        if not user_email or not message:
            raise HTTPException(status_code=400, detail="user_email and message required")

        # Create a mock Google Chat event structure
        event = {
            "type": "MESSAGE",
            "user": {"email": user_email},
            "message": {"text": message},
            "space": {"type": "WEB", "name": "web_chat"}
        }

        response = await handle_gchat_event(
            event=event,
            blip_agent=blip_agent,
            frappe_client=frappe_client,
            memory_store=memory_store,
            conversation_manager=conversation_manager
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error handling web chat: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.SERVICE_PORT,
        reload=True
    )
