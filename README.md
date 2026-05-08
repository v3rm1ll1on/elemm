# Elemm: The Landmark Manifest Protocol

[![PyPI version](https://img.shields.io/pypi/v/elemm.svg)](https://pypi.org/project/elemm/)
[![License](https://img.shields.io/pypi/l/elemm.svg)](https://github.com/v3rm1ll1on/elemm/blob/main/LICENSE)
[![Python versions](https://img.shields.io/pypi/pyversions/elemm.svg)](https://pypi.org/project/elemm/)

**The high-performance communication framework for autonomous LLM agents.**

Elemm is the **Landmark Manifest Protocol**, a high-performance communication framework designed to bridge the gap between static tool definitions and autonomous complex reasoning. By utilizing **Semantic Landmarks** and **Manifest-Driven Discovery**, Elemm optimizes token consumption, reduces execution latency, and provides a robust self-healing framework for agentic workflows.

---

## Core Advantages

Standard protocols like MCP often struggle with large-scale toolsets. Elemm provides a structural solution:

- **Efficient Discovery**: Agents only see a high-level manifest, loading detailed tool schemas only when needed.
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
