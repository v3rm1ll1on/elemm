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

- **Hierarchical Navigation**: Replaces overwhelming flat tool lists with navigational signposts (Landmarks).
- **Extreme Token Efficiency**: Proven to reduce tokens-per-step by up to **80%** in enterprise environments.
- **Agent Repair Kit**: Real-time self-healing through dynamic `remedy` injection on validation errors.
- **Hybrid Auto-Scaling**: Automatically flattens small toolsets to eliminate navigation overhead where unnecessary.
- **Enterprise-Grade Security**: Strict session isolation for multi-agent environments and restricted administrative access (`_INTERNAL_ALL_`).
- **Deep Schema Discovery**: Automatic extraction of Enums, Literals, and complex nested types from Pydantic models.
- **Native MCP Bridge**: Full support for Model Context Protocol via Stdio and SSE (with Nginx-ready buffering logic).
- **Stateless-Ready**: Designed to function reliably even in extremely low-context environments (proven at 1k-4k context windows).

## Documentation

For deep dives into specific topics, see our technical documentation:

- [Architecture](docs/ARCHITECTURE.md): Core protocol design and Zero-Prompt Vision.
- [Gateway](docs/GATEWAY.md): Centralized hub for multi-host and cross-domain tool orchestration.
- [Case Study](docs/CASE_STUDY.md): Detailed results of the Solaris Benchmark (Classic vs. ELEMM).
- [Security](docs/SECURITY.md): Internal keys, God-mode protection, and administrative access.
- [Deployment](docs/DEPLOYMENT.md): Docker, Nginx (SSE tuning), and Cloud configuration.
- [MCP Integration](docs/MCP_INTEGRATION.md): Bridging FastAPI to Model Context Protocol.
- [Repair Kit](docs/REPAIR_KIT.md): Implementing self-healing via Remedies.
- [Decorators](docs/DECORATORS.md): API reference for `@ai.landmark`, `@ai.action`, and more.

## Quick Start

### Installation

```bash
pip install elemm
```

### Server-Side: FastAPI + MCP

Elemm turns your FastAPI application into a Model Context Protocol (MCP) server with hierarchical discovery.

```python
from fastapi import FastAPI
from elemm.fastapi import FastAPIProtocolManager as Elemm

app = FastAPI()
ai = Elemm(agent_instructions="You are a Solaris Forensic Auditor. Use landmarks to discover modules.")

# 1. Define a Landmark (A semantic entry point)
@app.get("/it/ops")
@ai.landmark(id="it_ops", type="navigation", opens_group="it_tools")
async def it_portal():
    return {"status": "IT Operations Active"}

# 2. Register a Tool within that module
@app.post("/it/restart")
@ai.action(id="restart_node", group="it_tools")
async def restart(node_id: str):
    return {"result": f"Node {node_id} restarted."}

# 3. Bind everything
ai.bind_to_app(app)

# 4. Expose via Stdio (CLI) or SSE (Web)
# For Stdio: No extra code needed, just run via 'python app.py'
# For SSE:
ai.bind_mcp_sse(app, route_prefix="/mcp")
```

### Agent-Side: Connecting to Elemm

You can connect any MCP-compatible agent (like Claude Desktop, LangChain, or custom agents) to your Elemm server.

#### Option A: Stdio (Local / CLI)
Run your agent and point it to the python script:
```json
{
  "mcpServers": {
    "my-enterprise-api": {
      "command": "python",
      "args": ["path/to/your/app.py"]
    }
  }
}
```

#### Option B: SSE (Remote / Production)
Connect via HTTP to the SSE endpoint:
```python
# The agent discovers tools at:
# http://your-api.com/mcp/sse
```

### Understanding Landmark URLs

Every Landmark defined with `@ai.landmark` is a standard FastAPI route. This means:
- **Humans** can visit `/it/ops` in their browser to see the status.
- **Agents** use the same endpoint as a "Signpost" to discover the `it_tools` group.
- **Documentation**: Your OpenAPI/Swagger UI remains fully functional and reflects the protocol structure.

## Migration Path: From Flat to Hierarchical in 3 Steps

If you have an existing flat FastAPI application, you can migrate to the landmark protocol without breaking your existing API:

### 1. Categorize your Routes
Organize your routes using standard FastAPI tags. These tags will become the basis for your navigational structure.

```python
app = FastAPI(openapi_tags=[
    {"name": "it_ops", "description": "Manage infrastructure and logs."}
])

@app.get("/logs", tags=["it_ops"])
async def get_logs(): ...
```

### 2. Initialize and Bind
Initialize the Elemm manager and bind it to your application. When you call `bind_to_app(app)`, Elemm scans all routes for their `tags`. For every unique tag found, it **automatically** creates a navigation tool (e.g., `explore_it_ops`) that allows the agent to switch into that context.

```python
from elemm.fastapi import FastAPIProtocolManager as Elemm
ai = Elemm(agent_instructions="You are an Ops Specialist.")

# This scans your FastAPI routes and creates 'explore_it_ops'
# because it found the tag on your routes.
ai.bind_to_app(app)
```

### 3. (Optional) Define High-Level Entry Points
While tags create automatic navigation, you can also mark specific status routes as high-level landmarks to provide better semantic guidance.

```python
@app.get("/it/portal")
@ai.landmark(id="it_portal", type="navigation", opens_group="it_ops")
async def it_portal():
    return {"status": "IT Portal Active"}
```

Once these steps are completed, an AI agent will no longer be overwhelmed by a flat list but will instead navigate through your defined modules.

## Architecture and Security

Elemm is designed for enterprise production use:
- **Context Firewall**: The MCP bridge validates tool calls against the agent's current navigation state.
- **Reverse Proxy Support**: Automatically respects `root_path` when behind Nginx or Traefik.
- **Circular Reference Safety**: Safely handles complex, recursive Pydantic models.

## License
GNU General Public License v3.0. Created by Marc Stöcker.
