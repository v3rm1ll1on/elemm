  <h1>Elemm: LLM Landmark Protocol</h1>
  <p><strong>Hierarchical API Discovery for Enterprise AI Agents</strong></p>

  [![PyPI version](https://badge.fury.io/py/elemm.svg)](https://badge.fury.io/py/elemm)
  [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
  [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
</div>

---

**Elemm** is a protocol standard for the Model Context Protocol (MCP) and FastAPI. It replaces overwhelming flat API tool lists with a **hierarchical, navigable structure** (Landmarks). This allows AI agents to efficiently explore and interact with massive enterprise APIs without context window overflows, reducing token consumption by up to 80% while significantly increasing reliability.

## Why Elemm?

Modern AI agents struggle when presented with hundreds of tools simultaneously. The context window fills up, cognitive latency spikes, and hallucinations become frequent. 

Elemm solves this by introducing **Landmarks**:
- **Semantic Signposts**: Group your tools into logical domains (e.g., IT, HR, Finance).
- **Just-in-Time Context**: The agent uses the `navigate` tool to switch modules. Elemm dynamically injects only the tools relevant to the current module into the agent's toolbelt.
- **Zero-Prompt Vision**: Stop writing massive system prompts. The protocol acts as its own documentation, guiding the agent automatically.

---

## Core Features

- **Hierarchical Navigation**: Transforms flat APIs into a navigable tree structure.
- **Extreme Token Efficiency**: Cuts token usage per step by up to 80%, enabling complex operations even on smaller local models (e.g., Gemma 4).
- **Agent Repair Kit**: Real-time self-healing. When the AI makes an error (e.g., HTTP 422), Elemm injects a dynamic `remedy` and `noise_warning` to guide self-correction without permanently polluting the context.
- **Hybrid Auto-Scaling**: Automatically flattens small toolsets (<10 tools) to eliminate navigation overhead for simple tasks.
- **Enterprise Security**: Context-aware tool validation, read-only modes, and strict session isolation for multi-agent environments.
- **Native MCP Bridge**: Full integration with the Model Context Protocol via Stdio and SSE.

---

## Quick Start

### Installation

```bash
# Core package (Native Python, Framework-Agnostic)
pip install elemm

# With FastAPI integration
pip install elemm[fastapi]
```

### Option A: Native Python (Framework-Agnostic)

Turn any Python module into a hierarchical MCP server without needing a web framework.

```python
import asyncio
from elemm.core.manager import BaseAIProtocolManager
from elemm.mcp.bridge import LandmarkBridge
import my_tools_module # Your file containing @manager.tool decorated functions

manager = BaseAIProtocolManager(agent_instructions="You are an AI assistant.")

# Auto-discover and register native python functions
manager.bind_module(my_tools_module)

# Create the MCP bridge and expose via Stdio
bridge = LandmarkBridge(manager=manager)
# You can now connect this to any MCP client!
```

### Option B: FastAPI Integration

Turn any FastAPI application into a hierarchical MCP server with just a few decorators.

```python
from fastapi import FastAPI
from elemm.integrations.fastapi.manager import FastAPIProtocolManager as Elemm

app = FastAPI()
ai = Elemm(agent_instructions="You are an IT Support Agent. Navigate landmarks to find tools.")

# 1. Define a Landmark (Entry Point)
@app.get("/it/ops")
@ai.landmark(id="it_ops", type="navigation")
async def it_portal():
    return {"status": "IT Operations Active"}

# 2. Register a Tool within that module
@app.post("/it/restart")
@ai.action(id="restart_node", groups=["it_ops"], remedy="Ensure node_id format is SRV-XXXX.")
async def restart(node_id: str):
    return {"result": f"Node {node_id} restarted."}

# 3. Bind everything to the app
ai.bind_to_app(app)

# 4. Expose via Stdio (CLI) or SSE (Web)
# Stdio: Run directly via `python app.py` (if script uses `run_mcp_stdio`)
# SSE: Connect your agent via HTTP
ai.bind_mcp_sse(app, route_prefix="/mcp")
```

### Agent-Side Connection

Connect Claude Desktop, LangChain, or any MCP-compatible agent!

**Local (Stdio):**
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

**Remote (SSE):** Simply point your agent to `http://your-api.com/mcp/sse`.

---

## Deep Dive Documentation

Explore our comprehensive guides to master Elemm:

- [Architecture & Zero-Prompt Vision](docs/ARCHITECTURE.md)
- [Elemm Gateway (Universal Broker)](docs/GATEWAY.md)
- [Agent Repair Kit (Self-Healing)](docs/REPAIR_KIT.md)
- [Security & Session Isolation](docs/SECURITY.md)
- [Case Study: Solaris ERP Benchmark](docs/CASE_STUDY.md) *(DEPRECATED - NEW TEST WILL COME SOON)*
- [Deployment Guide](docs/DEPLOYMENT.md)
- [MCP Integration Details](docs/MCP_INTEGRATION.md)
- [Decorators API Reference](docs/DECORATORS.md)

---

## Included Examples

Check out the [`examples/`](./examples) directory to see Elemm in action:

1. [Enterprise Hub](./examples/enterprise_hub): The flagship benchmark. A complex forensic audit simulation with 100+ tools.
2. [Basic Navigation](./examples/basic_navigation): The "Hello World" showing automatic FastAPI tag discovery.
3. [Synth-Shop](./examples/synth_shop): E-commerce with JWT authentication flows and image rendering.
4. [Office Management](./examples/office_management): Booking automation with location-based navigation.

---

## Contributing & License

Elemm is open-source and built for the community.
Licensed under the **GNU General Public License v3.0**. Created by Marc Stöcker.
