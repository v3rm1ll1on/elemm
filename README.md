# Elemm: The Landmark Manifest Protocol

[![PyPI version](https://img.shields.io/pypi/v/elemm.svg)](https://pypi.org/project/elemm/)
[![License](https://img.shields.io/pypi/l/elemm.svg)](https://github.com/v3rm1ll1on/elemm/blob/main/LICENSE)
[![Python versions](https://img.shields.io/pypi/pyversions/elemm.svg)](https://pypi.org/project/elemm/)

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
- **Atomic Sequencing**: Execute multiple tool calls in a single LLM turn with native variable piping (`$step0.id`).
- **Multi-Protocol Gateway**: Connect to any **OpenAPI**, **GraphQL**, or **native Elemm** service through a single MCP server.
- **Security Policy Engine**: Built-in Guardian mode with pattern blacklists, landmark restrictions, and HTTP method filtering.
- **SmartRepair Engine**: Built-in error handling that provides agents with actionable remedies instead of cryptic stack traces.
- **Token Economy**: Reduces input tokens by up to 90% in complex forensic and administrative scenarios.

---

## Documentation

*   **[Getting Started](docs/GETTING_STARTED.md)**: Install and run your first Elemm setup.
*   **[Gateway Reference](docs/GATEWAY.md)**: Complete reference for the Elemm Gateway (OpenAPI, GraphQL, Security, Vault).
*   **[Developer Guide](docs/DEVELOPER_GUIDE.md)**: Build your own landmark servers with decorators and Pydantic.
*   **[Architecture Overview](docs/ARCHITECTURE.md)**: Deep dive into the Elemm philosophy.
*   **[Protocol Specification](docs/PROTOCOL_SPEC.md)**: Technical details for implementers.
*   **[Benchmarking Results](docs/BENCHMARKING.md)**: Performance analysis vs. standard MCP.

---

## Quick Start

### 1. Install
```bash
pip install elemm
```

### 2. Connect your AI Agent (MCP Client)
The fastest way to use Elemm is via the built-in **Gateway**. It acts as a universal MCP server that turns any OpenAPI or GraphQL API into a tool server.

**Do not run this manually in your terminal.** Instead, configure your AI agent (like Claude Desktop or Cursor) to run the `elemm-gateway` command.

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "elemm-gateway": {
      "command": "elemm-gateway"
    }
  }
}
```

*(Note: Use the absolute path to `elemm-gateway` if it is not in your system PATH).*

### 3. Start Discovering

Once connected, tell your agent:
> *"Use Elemm to connect to https://petstore.swagger.io/v2/swagger.json and list all available pets."*

The Gateway provides exactly **8 core tools** to the agent. All domain-specific actions are discovered on-the-fly via the Elemm protocol.

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
- **Response Hygiene**: Built-in `_select`, `_filter`, and `_limit` parameters prevent context overflow.
- **Session Isolation**: Use `session_id` to run parallel tasks without cross-contamination.
- **Self-Healing**: The SmartRepair engine provides agents with actionable remedies when errors occur.

---

## License
Copyright (C) 2026 Marc Stöcker.
GPLv3 License. See [LICENSE](LICENSE) for details.
