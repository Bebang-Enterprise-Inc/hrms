# Agentic Blip Implementation Plan

## Research Summary

Based on research of Anthropic's Claude Tool Use API and Agent SDK documentation, here's how to transform Blip from a simple intent-router into an agentic assistant like Claude Code.

## Key Concepts from Research

### 1. Tool Use API (Core Pattern)

Claude's tool use follows this pattern:

```python
# 1. Define tools with JSON schema
tools = [
    {
        "name": "get_sales",
        "description": "Get sales data for a store or area",
        "input_schema": {
            "type": "object",
            "properties": {
                "store": {"type": "string", "description": "Store name"},
                "period": {"type": "string", "enum": ["today", "yesterday", "this_week"]}
            },
            "required": ["period"]
        }
    }
]

# 2. Send message with tools
response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    messages=[{"role": "user", "content": user_message}],
    tools=tools
)

# 3. Handle tool_use blocks in response
for block in response.content:
    if block.type == "tool_use":
        tool_name = block.name
        tool_input = block.input
        tool_id = block.id

        # Execute the tool
        result = execute_tool(tool_name, tool_input)

        # Send result back to Claude
        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": json.dumps(result)
            }]
        })

        # Continue conversation
        response = client.messages.create(...)
```

### 2. Agentic Loop Pattern

The key to making Blip "intelligent" like Claude Code is the **agentic loop**:

```
while not done:
    1. Claude analyzes situation
    2. Claude decides which tool(s) to call (or respond directly)
    3. Execute tool(s) and return results
    4. Claude processes results and decides next action
    5. Repeat until task is complete
```

### 3. stop_reason Values

- `"end_turn"` - Claude is done, no more tools needed
- `"tool_use"` - Claude wants to use a tool
- `"max_tokens"` - Response was cut off

## Current Architecture vs Agentic Architecture

### Current (Rigid)
```
User Message → Parse Intent → Route to Handler → Format Response
```

**Problems:**
- One-shot, no follow-up capability
- Claude can only pick from predefined intents
- No reasoning or multi-step tasks
- No tool composition

### Agentic (Flexible)
```
User Message → Claude + Tools → [Loop: Reason → Act → Observe] → Response
```

**Benefits:**
- Multi-step task execution
- Claude decides what tools to use
- Can compose multiple tools
- Can ask clarifying questions
- Autonomous decision-making

## Implementation Plan

### Phase 1: Define Frappe API Tools

Create tool definitions for each Frappe API capability:

```python
# hrms/services/blip/ai/tools.py

BLIP_TOOLS = [
    {
        "name": "get_sales_data",
        "description": "Get sales data for a specific store, area, or company-wide. Use this when the user asks about revenue, sales performance, or store metrics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "store": {
                    "type": "string",
                    "description": "Store name (e.g., 'Megamall', 'Market Market'). Omit for area-wide or company-wide."
                },
                "area": {
                    "type": "string",
                    "description": "Area name (e.g., 'BGC', 'Makati'). Omit for store-specific or company-wide."
                },
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "this_week", "last_week", "this_month"],
                    "description": "Time period for sales data"
                }
            },
            "required": ["period"]
        }
    },
    {
        "name": "get_inventory",
        "description": "Check inventory levels at a store. Use when user asks about stock, items, or product availability.",
        "input_schema": {
            "type": "object",
            "properties": {
                "store": {"type": "string", "description": "Store name"},
                "item": {"type": "string", "description": "Specific item to check (optional)"}
            },
            "required": ["store"]
        }
    },
    {
        "name": "get_leave_balance",
        "description": "Get an employee's remaining leave balance. Use when user asks about their own or someone's leave credits.",
        "input_schema": {
            "type": "object",
            "properties": {
                "employee": {"type": "string", "description": "Employee name or email. Omit for the asking user."}
            }
        }
    },
    {
        "name": "get_employees_on_leave",
        "description": "Get list of employees on leave for a specific date. Use when user asks 'who is on leave' or about attendance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "store": {"type": "string", "description": "Filter by store (optional)"}
            },
            "required": ["date"]
        }
    },
    {
        "name": "get_weather_forecast",
        "description": "Get weather forecast for a location with sales impact prediction. Use when user asks about weather.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "Location name (default: Metro Manila)"}
            }
        }
    },
    {
        "name": "get_commissary_production",
        "description": "Get commissary (Bebang Kitchen) production data. Use when user asks about leche flan, frozen milk, or production.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product": {"type": "string", "description": "Product name (e.g., 'Leche Flan', 'Frozen Milk')"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"}
            }
        }
    },
    {
        "name": "search_employees",
        "description": "Search for employees by name, store, or position. Use when user asks about team members or org structure.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (name, position, or store)"},
                "store": {"type": "string", "description": "Filter by store (optional)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "submit_leave_request",
        "description": "Submit a leave request on behalf of the user. ONLY use after confirming details with user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "leave_type": {"type": "string", "enum": ["Vacation", "Sick", "Emergency"]},
                "from_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "to_date": {"type": "string", "description": "End date YYYY-MM-DD"},
                "reason": {"type": "string", "description": "Reason for leave"}
            },
            "required": ["leave_type", "from_date", "to_date"]
        }
    }
]
```

### Phase 2: Implement Tool Executor

```python
# hrms/services/blip/ai/tool_executor.py

async def execute_tool(
    tool_name: str,
    tool_input: dict,
    user_context: dict,
    frappe_client: Any
) -> dict:
    """Execute a tool and return results."""

    if tool_name == "get_sales_data":
        return await frappe_client.get_sales_data(
            store=tool_input.get("store"),
            area=tool_input.get("area"),
            period=tool_input.get("period"),
            user_context=user_context
        )

    elif tool_name == "get_inventory":
        return await frappe_client.get_inventory(
            store=tool_input.get("store"),
            item=tool_input.get("item"),
            user_context=user_context
        )

    elif tool_name == "get_leave_balance":
        employee = tool_input.get("employee") or user_context.get("employee")
        return await frappe_client.get_leave_balance(
            employee=employee,
            user_context=user_context
        )

    # ... etc for each tool

    else:
        return {"error": f"Unknown tool: {tool_name}"}
```

### Phase 3: Implement Agentic Loop

```python
# hrms/services/blip/ai/agent.py

import anthropic
from typing import Any, List
from .tools import BLIP_TOOLS
from .tool_executor import execute_tool

class BlipAgent:
    """Agentic Blip that can reason and use tools autonomously."""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_iterations = 10  # Prevent infinite loops

    async def run(
        self,
        user_message: str,
        user_context: dict,
        frappe_client: Any,
        conversation_history: List[dict] = None
    ) -> str:
        """
        Run the agentic loop until Claude produces a final response.
        """
        # Build initial messages
        messages = conversation_history or []
        messages.append({"role": "user", "content": user_message})

        system_prompt = self._build_system_prompt(user_context)

        for iteration in range(self.max_iterations):
            # Call Claude with tools
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=system_prompt,
                tools=BLIP_TOOLS,
                messages=messages
            )

            # Check if Claude is done (no tool calls)
            if response.stop_reason == "end_turn":
                # Extract text response
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return "I'm not sure how to help with that."

            # Process tool calls
            if response.stop_reason == "tool_use":
                # Add assistant's response to history
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Execute each tool call
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = await execute_tool(
                            tool_name=block.name,
                            tool_input=block.input,
                            user_context=user_context,
                            frappe_client=frappe_client
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, default=str)
                        })

                # Add tool results to messages
                messages.append({
                    "role": "user",
                    "content": tool_results
                })

        return "I got stuck in a loop. Please try rephrasing your question."

    def _build_system_prompt(self, user_context: dict) -> str:
        """Build system prompt with user context."""
        name = user_context.get("employee_name", "there")
        is_admin = user_context.get("is_admin", False)
        store = user_context.get("store", "")

        return f"""You are Blip, BEBANG's AI assistant. You help employees with business questions using the available tools.

ABOUT BEBANG:
- Philippine halo-halo chain with ~50 stores in Metro Manila
- Products: Presidential Halo-Halo, Mango Graham, Classic Halo-Halo
- Commissary: Bebang Kitchen (Frozen Milk, Leche Flan, Ube)

USER CONTEXT:
- Name: {name}
- Admin: {is_admin}
- Store: {store or 'Not assigned'}

YOUR APPROACH:
1. Understand what the user needs
2. Use tools to get the information (don't guess data!)
3. If you need multiple pieces of data, call multiple tools
4. Synthesize the results into a helpful, natural response
5. If something is unclear, ask for clarification

IMPORTANT:
- Be conversational and friendly
- Don't be robotic - you're a helpful colleague
- Use ₱ for Philippine Peso amounts
- If data shows issues (low sales, high inventory), proactively mention it
- For actions (like submitting leave), ALWAYS confirm with the user first

Current date: {datetime.now().strftime('%Y-%m-%d')} ({datetime.now().strftime('%A')})
"""
```

### Phase 4: Update Google Chat Handler

```python
# hrms/services/blip/handlers/gchat.py (updated)

from ai.agent import BlipAgent

async def handle_message(
    event: dict,
    frappe_client: Any,
    agent: BlipAgent
) -> dict:
    """Handle message with agentic Blip."""

    user = event.get("user", {})
    user_email = user.get("email", "")
    space_name = event.get("space", {}).get("name", "")
    message_text = event.get("message", {}).get("text", "").strip()
    message_text = message_text.replace("@Blip", "").strip()

    if not message_text:
        return {"text": "I didn't catch that. What would you like to know?"}

    # Get user context
    user_context = await get_user_context(user_email, frappe_client)

    # Get conversation history
    conversation_history = conversation_manager.get_messages(space_name, user_email)

    # Store user message
    conversation_manager.add_user_message(space_name, user_email, message_text)

    try:
        # Run the agent
        response_text = await agent.run(
            user_message=message_text,
            user_context=user_context,
            frappe_client=frappe_client,
            conversation_history=conversation_history
        )

        # Store response
        conversation_manager.add_assistant_message(space_name, user_email, response_text)

        return {"text": response_text}

    except Exception as e:
        logger.exception(f"Agent error: {e}")
        return {"text": "Oops, something went wrong. Please try again."}
```

### Phase 5: Add Memory/Context Management

For persistent memory across conversations, implement a simple key-value store:

```python
# hrms/services/blip/memory.py

import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class BlipMemory:
    """Long-term memory for Blip."""

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.local_cache = {}  # Fallback if no Redis

    async def remember(self, user_email: str, key: str, value: Any, ttl_days: int = 30):
        """Store a fact about a user."""
        memory_key = f"blip:memory:{user_email}:{key}"
        data = {
            "value": value,
            "stored_at": datetime.now().isoformat()
        }

        if self.redis:
            await self.redis.setex(
                memory_key,
                timedelta(days=ttl_days),
                json.dumps(data)
            )
        else:
            self.local_cache[memory_key] = data

    async def recall(self, user_email: str, key: str) -> Optional[Any]:
        """Recall a fact about a user."""
        memory_key = f"blip:memory:{user_email}:{key}"

        if self.redis:
            data = await self.redis.get(memory_key)
            if data:
                return json.loads(data).get("value")
        else:
            return self.local_cache.get(memory_key, {}).get("value")

        return None

    async def get_all_memories(self, user_email: str) -> Dict[str, Any]:
        """Get all memories for a user."""
        prefix = f"blip:memory:{user_email}:"
        memories = {}

        if self.redis:
            keys = await self.redis.keys(f"{prefix}*")
            for key in keys:
                short_key = key.replace(prefix, "")
                value = await self.recall(user_email, short_key)
                if value:
                    memories[short_key] = value
        else:
            for key, data in self.local_cache.items():
                if key.startswith(prefix):
                    short_key = key.replace(prefix, "")
                    memories[short_key] = data.get("value")

        return memories
```

Add a "remember" tool:

```python
{
    "name": "remember_fact",
    "description": "Store a fact about the user for future reference. Use when user says 'remember that...' or shares preferences.",
    "input_schema": {
        "type": "object",
        "properties": {
            "fact_type": {
                "type": "string",
                "description": "Category of fact (preference, schedule, contact, etc.)"
            },
            "fact": {
                "type": "string",
                "description": "The fact to remember"
            }
        },
        "required": ["fact_type", "fact"]
    }
},
{
    "name": "recall_facts",
    "description": "Recall stored facts about the user. Use to personalize responses.",
    "input_schema": {
        "type": "object",
        "properties": {
            "fact_type": {
                "type": "string",
                "description": "Category of fact to recall (optional, omit for all)"
            }
        }
    }
}
```

## Architecture Comparison

| Feature | Current Blip | Agentic Blip |
|---------|-------------|--------------|
| Intent Routing | Hardcoded list | Claude decides |
| Multi-step Tasks | No | Yes |
| Tool Composition | No | Yes |
| Clarifying Questions | No | Yes |
| Autonomous Decisions | No | Yes |
| Memory | Short-term only | Short + Long-term |
| Response Quality | Template-based | Natural language |

## Token/Cost Considerations

Using Haiku 4.5 for the agentic loop is cost-effective:
- Input: $0.80/M tokens
- Output: $4.00/M tokens

Typical conversation:
- System prompt: ~500 tokens
- User message: ~50 tokens
- Tool calls: ~100 tokens each
- Final response: ~200 tokens

Estimated cost per interaction: $0.001 - $0.01

## Security Considerations

1. **Tool Permissions**: Some tools should require confirmation (submit_leave_request)
2. **User Context**: Always pass user_context to tools for permission checking
3. **Rate Limiting**: Implement rate limits per user
4. **Audit Logging**: Log all tool executions for compliance

## Testing Plan

1. **Unit Tests**: Test each tool executor independently
2. **Integration Tests**: Test agentic loop with mock Frappe responses
3. **E2E Tests**: Test via actual Google Chat webhook

## Migration Strategy

1. Deploy new agentic system alongside current (feature flag)
2. Test with admin users first
3. Gradually roll out to all users
4. Monitor for issues and gather feedback
5. Remove old intent-based system once stable

## Next Steps

1. [ ] Create `hrms/services/blip/ai/tools.py` with tool definitions
2. [ ] Create `hrms/services/blip/ai/tool_executor.py`
3. [ ] Create `hrms/services/blip/ai/agent.py` with agentic loop
4. [ ] Update `hrms/services/blip/handlers/gchat.py`
5. [ ] Add memory system
6. [ ] Add unit tests
7. [ ] Deploy and test
