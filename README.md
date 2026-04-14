# elemm -- AI Landmarks for Autonomous Agents

> **Turn your Web API into a self-describing playground for AI Agents.**

`elemm` (AI Landmarks) is a smart bridging protocol that exposes your backend functionality as a set of discoverable "Landmarks". It enables autonomous agents (GPT-4, Claude, local models) to understand, navigate, and control your system without manual API documentation or custom tool coding.

---

## Key Features

*   **Automatic Route Discovery**: Scans your FastAPI app and extracts all necessary metadata.
*   **Zero-Config Pydantic Support**: Automatically converts Pydantic models into AI-readable action payloads.
*   **Semantic Guiding**: Hard-code behavioral instructions (HIL, constraints, tone) directly into your endpoints.
*   **MCP Ready**: Export your landmarks as native Model Context Protocol (MCP) tools for instant compatibility with Claude Desktop, Cursor, and Aevo.
*   **Response Prediction**: Tells the agent what to expect in the JSON response before the call is made.

---

## Installation

```bash
pip install elemm
```

---

## Quickstart (FastAPI)

`elemm` integrates seamlessly with FastAPI to provide automatic discovery.

```python
from fastapi import FastAPI
from pydantic import BaseModel
from elemm import FastAPIProtocolManager

app = FastAPI()

# 1. Initialize the Manager
ai = FastAPIProtocolManager(
    agent_welcome="Welcome to the SmartHome OS.",
    version="2.0-stable"
)

class CartItem(BaseModel):
    product_id: int
    quantity: int

# 2. Mark your routes as Landmarks
@app.post("/cart/add")
@ai.landmark(id="add_to_cart", type="write")
def add(item: CartItem):
    # The agent automatically sees 'product_id' and 'quantity' in the manifest
    pass

# 3. Mount the Discovery Manifest (at /.well-known/llm-landmarks.json)
app.include_router(ai.get_router())

# 4. Bind to scan your routes (CRITICAL!)
ai.bind_to_app(app)
```

---

## Pro Features

### 1. Customizing Agent Behavior
Different models (GPT-4o, Claude 3.5, etc.) react differently to instructions. You can override the global protocol instructions to fine-tune your agent's reasoning:

```python
ai = FastAPIProtocolManager(
    agent_welcome="...",
    protocol_instructions="CRITICAL: Never ever send nested objects for flat parameters!"
)
```

### 2. Manual Parameter Overrides
If you need to provide more context to the AI than your code provides:

```python
@ai.landmark(
    id="search",
    type="read",
    params={
        "q": {"description": "Keywords only, no full sentences.", "required": True},
        "limit": {"default": 10, "description": "Max results to return"}
    }
)
def search_api(q: str, limit: int = 5):
    ...
```

### 3. Model Context Protocol (MCP) Export
`elemm` is the perfect source for MCP Tools. You can generate a full tool-box with one line:

```python
# Returns a list of dicts compatible with MCP tool definitions
mcp_tool_box = ai.get_mcp_tools()
```

---

## Core Concepts

### The @landmark Decorator
This is where you tell the agent *how* to use the tool.
*   `id`: A unique identifies.
*   `type`: e.g., `read`, `write`, `navigation`.
*   `instructions`: Specific behavioral guidelines.

### Automatic Argument Detection
You don't need to define parameters manually. `elemm` inspects your function signature and Pydantic models automatically.

---

## License
MIT License. Created by the AI Evolution Team.
