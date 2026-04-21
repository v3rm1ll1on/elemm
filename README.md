# Elemm: LLM Landmark Protocol

Elemm is a protocol standard for hierarchical structuring of API interfaces for AI agents. It enables agents to efficiently navigate complex toolsets with minimal token consumption and maximum precision.

## Core Concepts

### 1. Landmarks
Landmarks are marked entry points within an API. They function as signposts that guide agents through various functional modules (e.g., IT, HR, Finance).

### 2. Hierarchical Navigation
Instead of presenting a flat list of hundreds of tools, Elemm provides context-specific toolsets. The agent actively navigates between modules, which increases accuracy and minimizes the risk of hallucinations or incorrect tool selection.

### 3. Hybrid Mode (Auto-Flattening)
For small or flat APIs (less than 10 landmarks without a group structure), Elemm automatically switches to a hybrid mode. In this mode, all tools are made directly visible to eliminate navigation overhead for simple tasks.

### 4. Agent Repair Kit (Self-Healing)
Elemm utilizes dynamic correction hints (Remedies). In case of validation errors (HTTP 422), the protocol provides the agent with precise instructions for error resolution instead of having to keep these permanently in the context.

## Features

- **Token Optimization**: Static tool descriptions are stripped of redundant instructions. Contextual help is only delivered when needed.
- **Session Isolation**: Complete separation of navigation states in multi-agent operations through isolated bridge instances per connection.
- **Deep Type Discovery**: Automatic extraction of Enum and Literal types from Pydantic models for precise JSON schemas.
- **Native MCP Support**: Full compatibility with the Model Context Protocol (both Stdio and SSE).

## Quick Start

### Installation

```bash
pip install elemm
```

### Integration with FastAPI

```python
from fastapi import FastAPI
from elemm.fastapi import FastAPIProtocolManager as Elemm

app = FastAPI()
ai = Elemm(agent_welcome="Welcome to the Enterprise ERP System.")

# Define a landmark
@app.get("/finance/audit")
@ai.landmark(id="finance", type="navigation", opens_group="finance")
async def finance_module():
    return {"status": "Active"}

# Register a tool in a group
@app.post("/finance/transfer")
@ai.action(id="transfer", group="finance")
async def transfer_funds(amount: float):
    return {"result": "Success"}

ai.bind_to_app(app)
ai.bind_mcp_sse(app, route_prefix="/mcp")
```

## Architecture and Security

Elemm is designed for enterprise production use:
- **Context Firewall**: The MCP bridge validates tool calls against the agent's current navigation state.
- **Reverse Proxy Support**: Automatically respects `root_path` when behind Nginx or Traefik.
- **Circular Reference Safety**: Safely handles complex, recursive Pydantic models.

## License
GNU General Public License v3.0. Created by Marc Stöcker.
