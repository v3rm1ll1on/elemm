# elemm -- AI Landmarks for Autonomous Agents

> **Turn your Web API into a self-describing playground for AI Agents.**

`elemm` (AI Landmarks) is a smart bridging protocol that exposes your backend functionality as a set of discoverable "Landmarks". It enables autonomous agents (GPT-4, Claude, local models) to understand, navigate, and control your system without manual API documentation or custom tool coding.

---

## Key Features

*   **Automatic Route Discovery**: Scans your FastAPI app and extracts all necessary metadata.
*   **Automatic Header Detection**: Detects `fastapi.Header` parameters and exports them as landmarks, allowing agents to handle authentication (JWT, API-Keys) natively.
*   **Context Injection (Managed Context)**: Identifies internal dependencies (`Request`, `session_id`, `db`) and signals them as `context_dependencies` so the protocol bridge can handle them transparently without bothering the LLM.
*   **Zero-Config Pydantic Support**: Automatically converts Pydantic models (including nested lists and complex schemas) into AI-readable action payloads.
*   **Semantic Guiding**: Hard-code behavioral instructions (HIL, constraints, tone) directly into your endpoints.
*   **MCP Ready**: Export your landmarks as native Model Context Protocol (MCP) tools for instant compatibility with Claude Desktop, Cursor, and Aevo.
*   **Response Prediction**: Tells the agent what to expect in the JSON response before the call is made.

---

## Installation

```bash
# Since we are in development, use editable install:
pip install -e /home/siddy/ai_web_protocoll/ai_landmarks_pkg
```

---

## Quickstart (FastAPI)

`elemm` integrates seamlessly with FastAPI to provide automatic discovery.

```python
from fastapi import FastAPI, Header, Depends
from pydantic import BaseModel
from elemm import FastAPIProtocolManager

app = FastAPI()

# 1. Initialize the Manager
ai = FastAPIProtocolManager(
    agent_welcome="Welcome to the Synth-Genesis OS.",
    version="2.5-autonomous"
)

class CartItem(BaseModel):
    product_id: str
    quantity: int = 1

# 2. Mark your routes as Landmarks
# Note: Header and Depends are handled automatically!
@app.post("/cart")
@ai.landmark(id="add_to_cart", type="write", description="Add an item to your persistent cart.")
async def add_to_cart(
    item: CartItem, 
    authorization: str = Header(..., description="Bearer <token>")
):
    return {"status": "success"}

# 3. Use Context Injection
# Internal fields like session_id are recognized and moved to context_dependencies
@app.get("/profile")
@ai.landmark(id="get_profile", type="read")
async def profile(session_id: str): 
    # session_id stays invisible to the LLM but visible to the Bridge!
    return {"user": "Peter Meier"}

# 4. Mount and Bind
app.include_router(ai.get_router())
ai.bind_to_app(app)
```

---

## Advanced Architecture

### 1. Automatic Header & Auth Mapping
`elemm` detects when a parameter is a Header. The manifest then describes this parameter correctly, and compatible bridges (like `landmark_addon`) automatically map these parameters back to HTTP Headers during the request execution.

### 2. Context Dependency Management
Instead of exposing technical boilerplate to the LLM, `elemm` categorizes parameters:
*   **Landmark Parameters**: Active fields the LLM must decide on.
*   **Context Dependencies**: Fields the system needs but the protocol bridge handles (e.g., `session_id`, `request_id`).

### 3. Model Context Protocol (MCP) Export
`elemm` is the perfect source for MCP Tools. Generate a full tool-box with one line:

```python
# Returns a list of dicts compatible with MCP tool definitions
mcp_tool_box = ai.get_mcp_tools()
```

---

## Core Concepts

### The @landmark Decorator
This is where you tell the agent *how* to use the tool.
*   `id`: A unique identifies.
*   `type`: `read`, `write`, `navigation`, `discovery`.
*   `instructions`: Specific behavioral guidelines (e.g. "Always check stock before buying").

### Automatic Argument Detection
`elemm` inspects your function signature and Pydantic models automatically. It resolves `Annotated`, `Field`, and `Optional` types to create the most accurate JSON Schema for the Agent.

---

## License
MIT License. Created by the AI Evolution Team.
