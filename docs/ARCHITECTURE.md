# Elemm Architecture: Hierarchical Navigation 🗺️

This document explains the core philosophy of Elemm: **Hierarchical Navigation (Landmarks)** and why it is superior to traditional flat-list tool exports.

---

## The Problem: The "Flat-List" Context Explosion 💥

In most LLM tool-calling implementations (like standard MCP or OpenAI Function Calling), all available tools are loaded into the agent's context at the start of the session.

- **With 5 tools**: Everything is fine.
- **With 50 tools**: The agent starts getting confused (Tool Hallucinations).
- **With 200 tools**: The context window is wasted on descriptions, and inference latency skyrockets.

## The Solution: The "Drill-Down" Discovery 🌪️

Elemm treats an API like a **world with landmarks**, not a flat list of items. It uses a three-phase discovery process:

### Phase 1: Signposting (Root Level)
When the agent first connects, it only sees "Entry Point" landmarks. These are tools marked as `type="navigation"`.
- *Agent sees:* `explore_logistics`, `explore_billing`, `global_search`.
- *Context Usage:* **Minimal.**

### Phase 2: Drilling Down (Module Level)
The agent decides to perform a logistical task. It calls `explore_logistics`. Elemm then provides a specialized manifest for that group.
- *Agent sees:* `get_shipment`, `update_delivery`, `list_carriers`.
- *Context Usage:* **Focused.** The billing tools are not in the context anymore.

### Phase 3: Global Access (Cross-Cutting)
Some tools are needed everywhere (e.g., a "Help" tool or a "Global Status" check). These are marked with `global_access=True`.
- They appear in the Root level AND in every submodule.

---

## Implementation Details

### Grouping via FastAPI Tags
Elemm automatically maps FastAPI `tags` to navigation groups.

```python
# This tag defines the group in FastAPI
tags_metadata = [{"name": "Warehouse", "description": "Operations for inventory"}]

# 1. Navigation Signpost (Root level)
@ai.tool(id="explore_warehouse", type="navigation")
@app.get("/inventory/overview", tags=["Warehouse"])
async def overview():
    return {"info": "Welcome to the warehouse."}

# 2. Specialized Tool (Only visible inside 'Warehouse')
@ai.tool(id="check_stock")
@app.get("/inventory/stock", tags=["Warehouse"])
async def check_item(id: str):
    return {"count": 42}
```

### URL Mapping & Discovery
Each group has its own manifest URL:
- **Root**: `/.well-known/llm-landmarks.json`
- **Sub-group**: `/.well-known/llm-landmarks.json?group=Warehouse`

**Note:** Elemm automatically handles ID sanitization. A tag named `Market & Sales` becomes `explore_market_and_sales` as an ID.

---

## Token Hygiene Facts
| API Size | Flat-List Context | Elemm Context |
| :--- | :--- | :--- |
| 10 Tools | ~1k Tokens | ~1k Tokens |
| 100 Tools | ~15k Tokens | **~1.5k Tokens** |
| 500 Tools | Impossible | **~2k Tokens** |

By using Elemm, you can scale your AI-Tooling to enterprise levels without worrying about context limits or inference costs.
