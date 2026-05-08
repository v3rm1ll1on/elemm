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
- **One MCP Server, Infinite APIs**: Use a single MCP bridge to connect to dozens of Elemm-powered microservices. Each service manages its own tools, while the bridge provides a unified entry point for the agent.

---

## Core Advantages

Standard protocols like MCP often struggle with large-scale toolsets. Elemm provides a structural solution:

- **Efficient Discovery**: Agents only see a high-level manifest, loading detailed tool schemas only when needed (on-demand inspection).
- **Atomic Sequencing**: Execute multiple tool calls in a single LLM turn with native variable piping (`$step0.id`).
- **SmartRepair Engine**: Built-in error handling that provides agents with actionable remedies instead of cryptic stack traces.
- **Token Economy**: Reduces input tokens by up to 90% in complex forensic and administrative scenarios.

---

## Documentation

*   **[Getting Started](docs/GETTING_STARTED.md)**: Install and run your first landmark server.
*   **[Developer Guide](docs/DEVELOPER_GUIDE.md)**: Build your own tools with decorators and Pydantic.
*   **[Architecture Overview](docs/ARCHITECTURE.md)**: Deep dive into the Elemm philosophy.
*   **[Protocol Specification](docs/PROTOCOL_SPEC.md)**: Technical details for implementers.
*   **[Benchmarking Results](docs/BENCHMARKING.md)**: Performance analysis vs. standard MCP.

---

## Quick Start

### 1. Install
```bash
pip install elemm[fastapi]  # Includes web server support
```

### 2. Create a Landmark Server
Elemm uses a decorator-based approach to turn standard Python functions into high-performance landmarks.

```python
from elemm import ElemmGateway
from pydantic import BaseModel

gateway = ElemmGateway(name="SystemControl")

class SecurityRequest(BaseModel):
    node_id: str
    urgent: bool = False

@gateway.action(landmark="Security")
async def quarantine_node(request: SecurityRequest):
    """Quarantines a compromised server node."""
    return {"status": "success", "node": request.node_id}

if __name__ == "__main__":
    # Runs an Elemm-compliant API server
    gateway.run(port=8000)
```

### Advanced Usage

- **Pydantic Discovery**: Elemm automatically generates schemas from Pydantic models.
- **Raw Integration**: Access the manifest as a dictionary via `gateway.manager.get_manifest_dict()` for custom LLM wrappers.
- **Self-Healing**: The SmartRepair engine provides agents with actionable remedies (e.g., correct parameter names) when errors occur.

### 3. Connect to an Agent
Use the provided MCP bridge to connect your Elemm server to any MCP-compatible agent (e.g. Claude Desktop):

```json
"elemm": {
  "command": "python3",
  "args": ["-m", "elemm.integrations.mcp_bridge", "http://localhost:8000"]
}
```

---

## License
Copyright (C) 2026 Marc Stöcker.
GPLv3 License. See [LICENSE](LICENSE) for details.
