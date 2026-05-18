# Elemm: The Landmark Manifest Protocol

[![PyPI version](https://img.shields.io/pypi/v/elemm?style=flat-square&color=blue)](https://pypi.org/project/elemm/)
[![Downloads](https://img.shields.io/pypi/dm/elemm?style=flat-square&color=darkgreen)](https://pypi.org/project/elemm/)
[![Build Status](https://img.shields.io/github/actions/workflow/status/v3rm1ll1on/elemm/tests.yml?branch=main&style=flat-square)](https://github.com/v3rm1ll1on/elemm/actions/workflows/tests.yml)
[![License](https://img.shields.io/github/license/v3rm1ll1on/elemm?style=flat-square&color=orange)](https://github.com/v3rm1ll1on/elemm/blob/main/LICENSE)
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?style=flat-square&logo=discord&logoColor=white)](https://discord.gg/EHSgYDScGj)
[![Python versions](https://img.shields.io/badge/python-3.10+-blue?style=flat-square)](https://pypi.org/project/elemm/)

**The Infrastructure for the Agentic Web.**

Elemm is the **Landmark Manifest Protocol**, a next-generation communication framework designed to transform how autonomous LLM agents interact with the digital world. Instead of static tool definitions, Elemm provides a **dynamic, manifest-driven architecture** that enables agents to discover, navigate, and execute complex workflows across distributed APIs with unprecedented efficiency.

---

## The Vision: Agentic Web
In the Agentic Web, every API is a "Landmark". Agents no longer need massive, hardcoded system prompts to understand a service. They discover capabilities on-the-fly via a standardized manifest, just like a human navigates a website.

- **Unified Discovery**: Every Elemm-compliant server exposes its structure at `/.well-known/elemm-manifest.md`.
- **Zero System Prompt**: By providing rich semantic landmarks and manifest-driven discovery, you can eliminate thousands of tokens from your system prompts. The protocol *is* the documentation.
- **One MCP Server, Infinite APIs**: The built-in **Elemm Gateway** connects to any OpenAPI, GraphQL, or native Elemm service. A single `pip install` gives you a universal MCP server that discovers and loads landmarks on-the-fly, allowing you to scale your agent's capabilities without ever restarting your infrastructure.

---

## The Philosophy: Decoupling Intelligence

Elemm is more than just a protocol; it's a shift toward **Decentralized Intelligence**. In the traditional SaaS model, providers often bundle their APIs with expensive, centralized LLM interfaces. Elemm decouples the "Body" (the API) from the "Brain" (the Agent).

### Bring Your Own Agent (BYOA)
With Elemm, API providers only define the **Landmarks** and **Manifests**. The user brings their own autonomous agent to the platform. This shifts the computational burden and cost of "reasoning" to the edge—the user's own system.

### Sustainability & Efficiency
By eliminating the need for massive, repetitive system prompts and context-heavy tool injections, Elemm significantly reduces the global token footprint of AI interactions.
- **Lower Latency**: No more waiting for centralized "gatekeeper" models to process 20k tokens of documentation.
- **Reduced CO2 & Energy**: Fewer tokens mean less GPU compute time, directly translating into a lower carbon footprint for every autonomous task.
- **Cost Sovereignty**: Providers save on LLM hosting and token costs, while users get the freedom to choose the model that best fits their task and budget.

---

## Core Advantages

Standard protocols like MCP often struggle with large-scale toolsets. Elemm provides a structural solution:

- **Efficient Discovery**: Agents only see a high-level manifest, loading detailed tool schemas only when needed (on-demand inspection).
- **Direct Search**: `search_landmarks(query)` enables regex-based tool discovery without traversing the full hierarchy — ideal for large API surfaces.
- **Atomic Sequencing**: Execute multiple tool calls in a single LLM turn with native variable piping (`$step0.id`).
- **Multi-Protocol Gateway**: Connect to any **OpenAPI**, **GraphQL**, or **native Elemm** service through a single MCP server.
- **Security Policy Engine**: Built-in Guardian mode with Zero-Trust whitelist, pattern blacklists, landmark restrictions, HTTP method filtering, and Data Loss Prevention.
- **SmartRepair Engine**: Built-in error handling that provides agents with actionable remedies instead of cryptic stack traces.
- **Token Economy**: Reduces input tokens by up to 90% in complex forensic and administrative scenarios.
- **Observability Dashboard**: Optional web UI for real-time monitoring, API exploration, and configuration management.

---

## Documentation

*   **[Getting Started](docs/GETTING_STARTED.md)**: Install and run your first Elemm setup.
*   **[Gateway Reference](docs/GATEWAY.md)**: Complete reference for the Elemm Gateway (OpenAPI, GraphQL, Security, Vault).
*   **[Developer Guide](docs/DEVELOPER_GUIDE.md)**: Build your own landmark servers with decorators and Pydantic.
*   **[Architecture Overview](docs/ARCHITECTURE.md)**: Deep dive into the Elemm philosophy and package structure.
*   **[Protocol Specification](docs/PROTOCOL_SPEC.md)**: Technical details for implementers.
*   **[Dashboard & Observability](docs/DASHBOARD.md)**: The Gateway UI — monitoring, config, and API explorer.
*   **[Benchmarking Results](docs/BENCHMARKING.md)**: Performance analysis vs. standard MCP.

---

## Quick Start

### 1. Install
```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install elemm
```

### 2. Option A: Connect your AI Agent (Local Setup)
The fastest way to use Elemm locally is via the built-in **Gateway**. It acts as a universal MCP server that turns any OpenAPI or GraphQL API into a tool server.

**Do not run this manually in your terminal.** Instead, configure your AI agent (like Claude Desktop or Cursor) to run the `elemm-gateway` command.

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "elemm-gateway": {
      "command": "/absolute/path/to/project/.venv/bin/python3",
      "args": ["-m", "elemm_gateway.cli"]
    }
  }
}
```

*(Note: Use the absolute path to `elemm-gateway` if it is not in your system PATH).*

### 2. Option B: Run via Docker (Recommended 2-Step Setup)
To run the entire gateway stack (Visual Dashboard on port `8090` + MCP Gateway on port `8000`) warning-free with persistent storage, run:

```bash
docker run -d \
  -p 8000:8000 \
  -p 8090:8090 \
  -v ~/.elemm:/root/.elemm \
  --name elemm-gateway \
  ghcr.io/v3rm1ll1on/elemm:latest
```

Then configure your Claude Desktop to connect via **Server-Sent Events (SSE)**:

```json
{
  "mcpServers": {
    "elemm-gateway": {
      "type": "sse",
      "url": "http://localhost:8000/sse"
    }
  }
}
```

See [Getting Started in Docker](docs/GETTING_STARTED.md#2-option-b-run-in-docker-2-step-setup-recommended-for-cloud--dev) for details.

### 3. Start Discovering

Once connected, tell your agent:
> *"Use Elemm to connect to https://petstore.swagger.io/v2/swagger.json and list all available pets."*

The Gateway provides **9 core tools** to the agent. All domain-specific actions are discovered on-the-fly via the Elemm protocol.

### 4. Build Your Own Landmark Server (Optional)
Elemm uses a decorator-based approach to turn standard Python functions into high-performance landmarks:

```python
from elemm import AIProtocolManager, MetadataRegistry

registry = MetadataRegistry("landmarks.yaml")
manager = AIProtocolManager(registry=registry)

@manager.landmark("security:quarantine_node")
async def quarantine_node(node_id: str, urgent: bool = False):
    """Quarantines a compromised server node."""
    return {"status": "success", "node": node_id}
```

### Advanced Usage

- **Pydantic Discovery**: Elemm automatically generates schemas from Pydantic models.
- **Response Hygiene**: Built-in `_select`, `_filter`, `_limit`, and `_offset` parameters prevent context overflow.
- **Session Isolation**: Use `session_id` to run parallel tasks without cross-contamination.
- **Self-Healing**: The SmartRepair engine provides agents with actionable remedies when errors occur.
- **Search**: Use `search_landmarks(query)` with Python REGEX to locate tools instantly without full hierarchy traversal.
- **Dashboard**: Start `python3 -m elemm_gateway.ui_backend.dashboard_server` for a real-time observability UI on port 8090.

---

## License
Copyright (C) 2026 Marc Stöcker.
GPLv3 License. See [LICENSE](LICENSE) for details.
