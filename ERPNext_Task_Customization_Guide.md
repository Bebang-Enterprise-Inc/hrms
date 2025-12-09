# ERPNext Task Customization & Google Chat Integration Guide

## 📋 **Current Situation**

You mentioned you couldn't:
1. Add **labels** to tasks
2. **Assign tasks** to someone

## ✅ **Solutions**

### **1. Assigning Tasks to Users**

ERPNext uses the **Assignment** feature for task assignment. Here's how to enable it:

#### **Method 1: Using the Assignment Button (Recommended)**
1. Open any Task document
2. Look for the **"Assign"** button in the toolbar (top right)
3. Click it and select the user(s) to assign the task to
4. The assignment will appear in the user's ToDo list

#### **Method 2: Add Custom Field for Direct Assignment**
If the Assignment button isn't visible, you can add a custom field:

1. Go to **Customize Form** (gear icon → Customize)
2. Select **Task** doctype
3. Add a new field:
   - **Field Type**: Link
   - **Field Name**: `assigned_to`
   - **Options**: User
   - **Label**: Assigned To
4. Save and reload

#### **Method 3: Enable Assignment Feature**
If Assignment button is missing, check:
- Go to **System Settings** → **Enable Assignment Rule**
- Ensure **Assignment** doctype is enabled in your workspace

---

### **2. Adding Labels/Tags to Tasks**

ERPNext doesn't have a built-in "Labels" field, but you can use:

#### **Option A: Use Tags (Built-in Feature)**
1. Open a Task
2. Look for the **"Tags"** field (usually at the bottom)
3. Add tags like: `urgent`, `bug`, `feature`, `review`, etc.
4. Tags can be used for filtering and searching

#### **Option B: Add Custom "Labels" Field**
1. Go to **Customize Form** → **Task**
2. Add a new field:
   - **Field Type**: Multi-select (or Select with multiple options)
   - **Field Name**: `labels`
   - **Label**: Labels
   - **Options**: 
     ```
     Urgent
     High Priority
     Bug
     Feature
     Review
     In Progress
     Blocked
     ```
3. Save and reload

#### **Option C: Use Priority + Color Fields**
- **Priority**: Low, Medium, High (built-in)
- **Color**: Assign colors to tasks for visual categorization

---

### **3. Google Chat Integration**

ERPNext doesn't have native Google Chat integration, but you can achieve it through:

#### **Method 1: Using Webhooks (Recommended)**

**Step 1: Create a Webhook in ERPNext**
1. Go to **Integrations** → **Webhooks**
2. Create a new Webhook:
   - **Webhook Type**: Outgoing
   - **Request URL**: Your Google Chat Webhook URL
   - **Request Method**: POST
   - **Enable**: Yes

**Step 2: Get Google Chat Webhook URL**
1. In Google Chat, go to your space
2. Click **Configure Webhooks** → **Add Webhook**
3. Copy the webhook URL

**Step 3: Create Custom Script for Task Events**
1. Go to **Customize Form** → **Task**
2. Add a **Client Script** or **Server Script**:

```python
# Server Script (Python)
# Hook: Task.on_update

import frappe
import requests
import json

def send_to_google_chat(doc, method):
    # Get webhook URL from System Settings or custom field
    webhook_url = frappe.db.get_value("System Settings", None, "google_chat_webhook_url")
    
    if not webhook_url:
        return
    
    # Prepare message
    message = {
        "text": f"Task Updated: {doc.subject}\nStatus: {doc.status}\nAssigned To: {doc.assigned_to or 'Unassigned'}\nLink: {frappe.utils.get_url_to_form('Task', doc.name)}"
    }
    
    # Send to Google Chat
    try:
        response = requests.post(webhook_url, json=message)
        response.raise_for_status()
    except Exception as e:
        frappe.log_error(f"Google Chat webhook failed: {str(e)}")
```

**Step 4: Create Webhook for Different Events**
Create separate webhooks for:
- Task Created (`on_insert`)
- Task Updated (`on_update`)
- Task Closed (`on_update` with status check)

---

#### **Method 2: Using Pipedream (No-Code Solution)**

1. Sign up for [Pipedream](https://pipedream.com)
2. Create a new workflow:
   - **Trigger**: ERPNext (when Task is created/updated)
   - **Action**: Google Chat (send message)
3. Configure the workflow to send notifications

**Advantages:**
- No coding required
- Visual workflow builder
- Handles authentication automatically

---

#### **Method 3: Using n8n (Self-Hosted Alternative)**

1. Install n8n (self-hosted or cloud)
2. Create workflow:
   - **Trigger**: ERPNext Webhook or API
   - **Action**: Google Chat API
3. Configure authentication and message format

---

### **4. Complete Customization Example**

Here's a complete setup to add both assignment and labels:

#### **Step 1: Customize Task Form**

1. Go to **Customize** → **Customize Form**
2. Select **Task** doctype
3. Add these custom fields:

**Field 1: Assigned To (if not visible)**
```
Field Type: Link
Field Name: assigned_to
Options: User
Label: Assigned To
Insert After: [choose appropriate field]
```

**Field 2: Labels**
```
Field Type: Multi-select
Field Name: task_labels
Label: Labels
Options:
  Urgent
  High Priority
  Bug
  Feature
  Review
  In Progress
  Blocked
  Customer Request
Insert After: priority
```

**Field 3: Google Chat Notifications**
```
Field Type: Check
Field Name: notify_google_chat
Label: Notify in Google Chat
Default: 1
Insert After: task_labels
```

#### **Step 2: Add Server Script for Google Chat**

1. Go to **Customize** → **Custom Script**
2. Create new script:

```python
# DocType: Task
# Script Type: Server Script
# Event: on_update

import frappe
import requests
import json

def send_google_chat_notification(doc, method):
    # Check if notification is enabled
    if not doc.get("notify_google_chat"):
        return
    
    # Get webhook URL (store in System Settings or Custom Field)
    webhook_url = frappe.conf.get("google_chat_webhook_url") or frappe.db.get_value(
        "System Settings", None, "google_chat_webhook_url"
    )
    
    if not webhook_url:
        frappe.log_error("Google Chat webhook URL not configured")
        return
    
    # Determine event type
    old_doc = doc.get_doc_before_save()
    if old_doc:
        if old_doc.status != doc.status:
            if doc.status == "Closed":
                event = "Task Closed"
            else:
                event = "Task Status Changed"
        else:
            event = "Task Updated"
    else:
        event = "Task Created"
    
    # Build message
    labels = ", ".join(doc.get("task_labels", [])) if doc.get("task_labels") else "None"
    assigned_to = doc.get("assigned_to") or "Unassigned"
    
    message = {
        "cards": [{
            "header": {
                "title": f"{event}: {doc.subject}",
                "subtitle": f"Task #{doc.name}"
            },
            "sections": [{
                "widgets": [{
                    "textParagraph": {
                        "text": f"""
<b>Status:</b> {doc.status}<br>
<b>Assigned To:</b> {assigned_to}<br>
<b>Labels:</b> {labels}<br>
<b>Priority:</b> {doc.get('priority', 'Medium')}<br>
<b>Description:</b> {doc.get('description', 'N/A')[:100]}...
                        """
                    }
                }, {
                    "buttons": [{
                        "textButton": {
                            "text": "Open Task",
                            "onClick": {
                                "openLink": {
                                    "url": frappe.utils.get_url_to_form("Task", doc.name)
                                }
                            }
                        }
                    }]
                }]
            }]
        }]
    }
    
    # Send to Google Chat
    try:
        response = requests.post(
            webhook_url,
            json=message,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        response.raise_for_status()
    except Exception as e:
        frappe.log_error(f"Google Chat notification failed: {str(e)}", "Task Notification Error")
```

#### **Step 3: Configure Webhook URL**

**Option A: System Settings**
1. Go to **System Settings**
2. Add custom field for `google_chat_webhook_url`
3. Enter your Google Chat webhook URL

**Option B: Site Config**
Add to `site_config.json`:
```json
{
    "google_chat_webhook_url": "https://chat.googleapis.com/v1/spaces/..."
}
```

---

## 🔧 **Quick Fixes**

### **If Assignment Button is Missing:**

1. Check user permissions:
   - Go to **Role Permissions**
   - Ensure "Assignment" doctype has read/write permissions

2. Enable Assignment in Workspace:
   - Go to **Workspace** settings
   - Add "Assignment" to visible modules

3. Use ToDo instead:
   - Create a ToDo and link it to the Task
   - ToDos have built-in assignment

### **If Tags Field is Missing:**

1. Go to **Customize Form** → **Task**
2. Check if "Tags" field exists but is hidden
3. If missing, add it as a custom field (type: "Tags")

---

## 📝 **Testing the Setup**

1. **Test Assignment:**
   - Create a new Task
   - Click "Assign" button or use custom field
   - Check assignee's ToDo list

2. **Test Labels:**
   - Add labels to a task
   - Filter tasks by label

3. **Test Google Chat:**
   - Create/update a task
   - Check Google Chat for notification
   - Verify message format and link

---

## 🚀 **Advanced: Custom Task Form**

If you want a completely customized task form:

1. Go to **Customize Form** → **Task**
2. Rearrange fields as needed
3. Add custom sections
4. Create custom views

---

## 📚 **Resources**

- [ERPNext Assignment Documentation](https://docs.frappe.io/erpnext/user/manual/en/assignment)
- [ERPNext Customization Guide](https://docs.frappe.io/frappe/user/en/guides/customization)
- [Google Chat Webhooks](https://developers.google.com/chat/api/guides/webhooks)
- [Pipedream ERPNext Integration](https://pipedream.com/apps/erpnext)

---

## ⚠️ **Important Notes**

1. **Permissions**: Ensure users have proper permissions to assign tasks
2. **Webhook Security**: Keep Google Chat webhook URLs secure (use environment variables)
3. **Rate Limits**: Google Chat has rate limits; batch notifications if needed
4. **Testing**: Test in a development environment first

---

**Need Help?** Check ERPNext documentation or Frappe community forums for specific customization needs.


