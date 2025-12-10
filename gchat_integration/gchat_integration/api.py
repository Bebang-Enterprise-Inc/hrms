"""
Google Chat Integration API
Provides whitelisted methods that Server Scripts can call to send messages to Google Chat.
"""
import frappe
import json


@frappe.whitelist()
def send_to_google_chat(space_name, message_text=None, card_json=None):
    """
    Send a message to Google Chat space.
    
    Args:
        space_name: Name of the Google Chat Space document
        message_text: Plain text message (optional)
        card_json: JSON string of card payload (optional)
    
    Returns:
        dict with success status and message_id or error
    """
    try:
        # Import here to avoid issues during app installation
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        
        # Get settings
        settings = frappe.get_single("Google Chat Settings")
        if not settings.enabled:
            return {"success": False, "error": "Google Chat integration is disabled"}
        
        # Get space details
        space = frappe.get_doc("Google Chat Space", space_name)
        if not space.enabled:
            return {"success": False, "error": f"Space '{space_name}' is disabled"}
        
        # Build credentials from stored settings
        creds_info = {
            "type": "service_account",
            "client_email": settings.client_email,
            "private_key": settings.private_key.replace("\\n", "\n"),
            "token_uri": settings.token_uri or "https://oauth2.googleapis.com/token",
        }
        
        credentials = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=["https://www.googleapis.com/auth/chat.bot"]
        )
        
        # Build Chat service
        service = build("chat", "v1", credentials=credentials)
        
        # Prepare message
        message = {}
        if message_text:
            message["text"] = message_text
        if card_json:
            cards = json.loads(card_json) if isinstance(card_json, str) else card_json
            message["cardsV2"] = cards if isinstance(cards, list) else [cards]
        
        if not message:
            return {"success": False, "error": "No message content provided"}
        
        # Send message
        result = service.spaces().messages().create(
            parent=space.space_id,
            body=message
        ).execute()
        
        frappe.log_error(
            title="Google Chat Message Sent",
            message=f"Sent to {space_name}: {result.get('name')}"
        )
        
        return {"success": True, "message_id": result.get("name")}
        
    except Exception as e:
        frappe.log_error(
            title="Google Chat Error",
            message=f"Failed to send to {space_name}: {str(e)}"
        )
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def send_task_notification(task_name, event_type="created"):
    """
    Send a rich card notification for a Task.
    
    Args:
        task_name: Name of the Task document
        event_type: "created" or "updated"
    
    Returns:
        dict with success status
    """
    try:
        task = frappe.get_doc("Task", task_name)
        
        if not task.google_chat_space:
            return {"success": False, "error": "No Google Chat space configured for this task"}
        
        # Build rich card
        status_emoji = {
            "Open": "🔵",
            "Working": "🟡", 
            "Pending Review": "🟠",
            "Overdue": "🔴",
            "Completed": "✅",
            "Cancelled": "⚫"
        }.get(task.status, "⚪")
        
        priority_emoji = {
            "Low": "🟢",
            "Medium": "🟡",
            "High": "🟠",
            "Urgent": "🔴"
        }.get(task.priority, "⚪")
        
        title = "📋 New Task Created" if event_type == "created" else "📋 Task Updated"
        
        card = {
            "cardId": f"task-{task.name}",
            "card": {
                "header": {
                    "title": title,
                    "subtitle": task.project or "No Project"
                },
                "sections": [
                    {
                        "widgets": [
                            {
                                "decoratedText": {
                                    "topLabel": "Task",
                                    "text": task.subject or task.name
                                }
                            },
                            {
                                "decoratedText": {
                                    "topLabel": "Status",
                                    "text": f"{status_emoji} {task.status}"
                                }
                            },
                            {
                                "decoratedText": {
                                    "topLabel": "Priority", 
                                    "text": f"{priority_emoji} {task.priority}"
                                }
                            }
                        ]
                    },
                    {
                        "widgets": [
                            {
                                "buttonList": {
                                    "buttons": [
                                        {
                                            "text": "👁️ View Task",
                                            "onClick": {
                                                "openLink": {
                                                    "url": f"https://lfg.bebang.ph/app/task/{task.name}"
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ]
            }
        }
        
        if task.assigned_to:
            # Add assignee info
            card["card"]["sections"][0]["widgets"].append({
                "decoratedText": {
                    "topLabel": "Assigned To",
                    "text": task.assigned_to
                }
            })
        
        return send_to_google_chat(
            space_name=task.google_chat_space,
            card_json=json.dumps([card])
        )
        
    except Exception as e:
        frappe.log_error(
            title="Task Notification Error",
            message=f"Failed to notify for task {task_name}: {str(e)}"
        )
        return {"success": False, "error": str(e)}

