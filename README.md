# elemm (Landmark Protocol)

**The Universal AI-Native Backend Bridge. Turn any API into a navigable map for autonomous agents.**

`elemm` is a high-performance framework for FastAPI that transforms standard REST endpoints into "AI Landmarks". It optimizes your API for autonomous agents (like Claude or GPT via MCP), enabling them to discover, understand, and interact with your backend with zero-shot precision.

---

## Quick Start

### 1. Installation
```bash
pip install elemm
```

### 2. Implementation
```python
from elemm import FastAPIProtocolManager
from fastapi import FastAPI, Header

app = FastAPI()
ai = FastAPIProtocolManager(agent_welcome="Welcome to System-X.")

@ai.landmark(id="get_status", type="read", description="Check system health.")
@app.get("/status")
async def health(auth_token: str = Header(..., description="Your API Token")):
    return {"status": "nominal"}

# Register the protocol
app.include_router(ai.get_router())
ai.bind_to_app(app)
```

---

## The @landmark Decorator Reference

The decorator is the primary way to provide semantic context to an AI agent. Here is a detailed breakdown of all available options:

### `id` (string, required)
The unique identifier for the action. The AI uses this ID to call the tool.
*   *Example:* `id="process_payment"`

### `type` (string, required)
Defines the nature of the action. This helps the AI categorize its capabilities:
*   `read`: For fetching information (e.g., searching products, reading logs).
*   `write`: For actions that change state (e.g., creating a user, deleting a file).
*   `navigation`: For actions that explain the API's structure (e.g., listing categories, help endpoints).
*   *Example:* `type="write"`

### `description` (string, optional)
The semantic instruction for the AI. If omitted, the function's docstring is used. This is the most important field for AI reasoning.
*   *Example:* `description="Use this to find products by price range or keywords."`

### `instructions` (string, optional)
Specific "Rules of Engagement" for this action. Useful for enforcing business logic at the AI level.
*   *Example:* `instructions="Always ask for the user's shipping address BEFORE calling this."`

### `remedy` (string, optional)
**AI-Native Error Handling.** Instructions for the agent on how to proceed if the API call fails or returns an error.
*   *Example:* `remedy="If this returns a 402 (Payment Required), explain the premium subscription benefits to the user."`

### `hidden` (boolean, default: False)
If set to `True`, the landmark is registered in your code but **excluded from the AI manifest**. 
*   **Why use this?** For security (preventing AI from seeing sensitive endpoints) or during maintenance when an endpoint should be temporarily disabled for agents without changing the routing logic.

---

## Native MCP Support

`elemm` natively supports the **Model Context Protocol (MCP)**. This allows you to export your entire API as a tool-kit for high-end AI clients in seconds:

*   **Instant Integration**: Works with Claude Desktop, Cursor, and other MCP-compatible agents.
*   **Auto-Sync**: Your AI tools are always in sync with your latest API deployment.
*   **Bridge Logic**: See `examples/mcp_bridge.py` for a ready-to-use bridge implementation.

---

## Practical Applications

`elemm` is universal. It is designed for **any** API that needs to be controlled or queried by an AI Assistant:

*   **E-Commerce**: Automate shopping flows, support, and inventory tracking.
*   **Internal Dashboards & ERP**: Turn complex data silos into conversational interfaces for employees.
*   **IoT & Infrastructure**: Control hardware, manage servers, or query sensors via natural language.
*   **SaaS & Tooling**: Enable your users to interact with your platform via AI agents autonomously.

Essentially, if it has an API, `elemm` makes it AI-Native.

---

## Core Features and Hardening

Standard OpenAPI documentation is often too noisy for LLMs. `elemm` provides a hardened abstraction layer:

*   **Managed Parameters**: sensitive headers (e.g., `Authorization`) are automatically marked as `managed_by: protocol`, preventing AI hallucinations.
*   **Context Injection**: Technical fields (e.g., `Request`, `Session`) are automatically moved to a context scope, keeping the agent's input clean.
*   **Pydantic V2 Support**: Deep extraction of Enums, nested models, and field metadata.

---

## License
MIT License. Created by v3rm1ll1on.
