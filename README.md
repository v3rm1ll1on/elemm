# Elemm (Landmark Protocol)

**The Universal AI-Native Backend Bridge. Turn any API into resilient, autonomous AI tools in seconds.**

`Elemm` is a high-performance framework centered around the **Model Context Protocol (MCP)**. It transforms standard REST endpoints into "AI Landmarks", enabling autonomous agents (like Claude or GPT) to discover and interact with your backend with zero-shot precision and self-healing resilience.

---

## Why Elemm? (The Problem with Flat APIs)

Traditional APIs (OpenAPI/Swagger) are built for humans. When you feed a 200-endpoint Swagger file to an LLM:
1.  **Context Overload**: The agent drowns in noise (HTTP codes, headers, internal types).
2.  **Token Waste**: Every turn costs thousands of tokens just for tool descriptions.
3.  **Fragility**: If the AI makes one typo in a parameter, it gets a raw 400 error and gives up.

**Elemm solves this with the Landmark-Architecture.**

| Feature | Standard OpenAPI | Native MCP (Flat) | **Elemm (Landmarks)** |
| :--- | :--- | :--- | :--- |
| **Noise Level** | High (HTTP Metadata) | Medium (Flat-List) | **Low (Context Isolated)** |
| **Discovery** | Static (Manual) | Static (Full Load) | **Hierarchical (Drill-Down)** |
| **Error Handling** | Generic 4xx/5xx | RAW Error | **Agent-Repair-Kit (Self-Healing)** |
| **Security** | Manual Header Logic | Manual | **Zero-Config (Auto-Shield)** |
| **Max Scale** | Limited by Context | ~50 Tools | **Unlimited (Scale out)** |
| **Token Cost** | factor 5x | factor 1x | **factor < 0.1x (Hygiene)** |

---

## 📚 Documentation Index

For deep dives into the protocol's power, see our specialized guides:
- [**Architecture & Navigation**](docs/ARCHITECTURE.md) - How to scale to 1000+ tools with Token-Hygiene.
- [**Agent-Repair-Kit**](docs/REPAIR_KIT.md) - How Self-Healing and Remedies break error loops.
- [**Security & Shielding**](docs/SECURITY.md) - Auto-Auth detection and Read-Only protection.
- [**MCP Integration**](docs/MCP_INTEGRATION.md) - Native Model Context Protocol support (SSE & Stdio).
- [**Decorator Reference**](docs/DECORATORS.md) - Full API reference for @ai.tool and @ai.action.

---

## Key Features

### 1. Agent-Repair-Kit (Self-Healing)
Elemm is the first protocol that actively talks back to the AI when things go wrong. 
- **Automated Remedies**: If a validation fails (422), Elemm injects your custom `remedy` instructions into the error response.
- **Noise Detection**: It explicitly warns the agent if it's hallucinating parameters that don't exist in the manifest.
- **Instructional Loops**: The AI receives a "behebbar" (fixable) JSON that guides it back to the successful call.

### 2. Hierarchical Navigation (Context Hygiene)
Stop loading the full API at once. Elemm uses a "Drill-Down" flow:
- **Signposts**: The agent only sees the "Main Entries" (e.g., `explore_logistics`, `explore_billing`).
- **Module Loading**: Only when the agent enters a module are the specific tools revealed.
- **Token Efficiency**: This reduces the active context size by up to 90%.

### 3. Managed Security (Auto-Shield)
Elemm auto-detects `HTTPBearer`, `APIKey`, and `OAuth2` dependencies. 
- Technical credentials are **hidden** from the agent.
- The protocol marks them as `managed_by: protocol`.
- **Read-Only Mode**: Protect your production with a single flag (`LANDMARK_READ_ONLY=True`) which strips all state-changing actions from the manifest.

---

## Quick Start

### 1. Installation
```bash
pip install elemm
```

### 2. Implementation
```python
from elemm import Elemm
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()
ai = Elemm(agent_welcome="Welcome to Solaris-OS.")

class Order(BaseModel):
    item_id: str
    amount: int = Field(..., ge=1, le=100)

@ai.tool(id="get_categories", type="navigation")
@app.get("/categories")
async def list_cats():
    """Discover available product modules."""
    return ["Electronics", "Books"]

@ai.action(
    id="place_order", 
    remedy="Always provide an amount between 1 and 100."
)
@app.post("/order")
async def order(data: Order):
    return {"status": "success"}

# Bind everything
ai.bind_to_app(app)
```

---

## Decorator Reference

Use the decorators that fit your naming convention – they are all functionally identical aliases of `@ai.landmark`:

*   **`@ai.tool(id=...)`**: Best for OpenAI / LangChain style.
*   **`@ai.action(id=...)`**: Standard for API-centric logic.
*   **`@ai.landmark(id=...)`**: The precise term for semantic navigation.

### Key Options:
- `id` (Required): The unique name of the tool for the AI.
- `type` (Default: "read"/"write"): "read", "write", or "navigation".
- `remedy`: The instruction given to the AI if it fails the validation.
- `instructions`: Specific rules for this tool (e.g., "Ask for approval first").
- `global_access`: If True, this tool stays visible even deep inside other modules.

---

## Native MCP Support (Model Context Protocol)

Elemm isn't just a manifest; it's a bridge. Connect your entire API directly to agents using the built-in MCP Server.

### 1. Web-Native (SSE)
Expose your API as an MCP server via HTTP/SSE. This allows agents to connect to your production environment over the web.

```python
app = FastAPI()
ai.bind_mcp_sse(app, route_prefix="/mcp")
```

The agent connects to: `http://localhost:8000/mcp/sse`

### 2. Dual-Boot (Stdio)
For local development or command-line usage (pipes), use the Stdio launcher. This starts both the HTTP server and the MCP bridge in a single process.

```python
if __name__ == "__main__":
    import sys
    if "--mcp" in sys.argv:
        ai.run_mcp_stdio("your_api_module:app")
    else:
        uvicorn.run(app)
```

Usage with Claude Desktop:
```json
{
  "mcpServers": {
    "my-backend": {
      "command": "python3",
      "args": ["/path/to/app.py", "--mcp"]
    }
  }
}
```

---

## Architecture & Resilience

Elemm is built for scale. 
- **Reverse Proxy Support**: Automatically respects `root_path` (Nginx/Traefik).
- **Circular Ref Safety**: Handles complex Pydantic models (self-referencing models).
- **ID Sanitization**: Safely handles special characters in tags and module names.

---

## 📄 License
GNU General Public License v3.0. Created by Marc Stöcker.
