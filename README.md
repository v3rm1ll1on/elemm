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
    agent_welcome="Welcome to the SmartHome OS. You are an indoor climate specialist.",
    version="2.0-stable"
)

class LightOrder(BaseModel):
    brightness: int # Ranges from 0 to 100
    color_temp: str = "warm"

# 2. Mark your routes as Landmarks
@app.post("/lights/{room_id}")
@ai.landmark(
    id="set_room_lighting",
    type="write",
    instructions="Always report the new brightness level to the user."
)
def set_lights(room_id: str, order: LightOrder):
    return {"status": "dimmed", "room": room_id}

# 3. Mount the Discovery Manifest (at /.well-known/llm-landmarks.json)
app.include_router(ai.get_router())

# 4. Bind to scan your routes (CRITICAL!)
ai.bind_to_app(app)
```

---

## Core Concepts

### The @landmark Decorator
This is where you tell the agent *how* to use the tool.
*   `id`: A unique, snake_case identifier for the tool.
*   `type`: Categorize the action (e.g., `read`, `write`, `navigation`).
*   `instructions`: Specific behavioral guidelines for the LLM when using *this* tool.
*   `description`: If omitted, `elemm` uses the function's docstring.

### Automatic Argument Detection
You don't need to define parameters manually. `elemm` inspects your function signature:
*   **Path/Query Params**: Automatically identified and typed.
*   **Payloads**: If you use a Pydantic `BaseModel`, its entire schema is extracted recursively.
*   **Optionality**: Correctly identifies optional fields and default values.

---

## Advanced Usage

### Manual Parameter Overrides
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

### Model Context Protocol (MCP) Export
`elemm` is the perfect source for MCP Tools. You can generate a full tool-box with one line:

```python
# Returns a list of dicts compatible with MCP tool definitions
mcp_tool_box = ai.get_mcp_tools()

# These can be served via an MCP Server to any LLM client.
```

### Response Schema Prediction
`elemm` looks at your `response_model` to tell the agent what the JSON output will look like. This drastically reduces "parsing hallucinations" by the LLM.

---

## The Manifest Format
Your application will serve a standardized JSON at `/.well-known/llm-landmarks.json`:

```json
{
  "version": "v1-lmlmm",
  "agent_welcome": "...",
  "actions": [
    {
      "id": "set_room_lighting",
      "method": "POST",
      "url": "/lights/{room_id}",
      "parameters": [...],
      "payload": [...],
      "instructions": "..."
    }
  ]
}
```

---

## License
MIT License. Created by the AI Evolution Team.
