# Getting Started with Elemm

Welcome to Elemm! This guide will help you set up your first autonomous tool environment using the Landmark Manifest Protocol.

---

## 1. Installation

Install Elemm directly from PyPI:

```bash
pip install elemm
```

---

## 2. Option A: Use the Gateway (Fastest)

The **Elemm Gateway** is a universal MCP server that connects to any OpenAPI, GraphQL, or native Elemm API. No code required.

```bash
elemm-gateway
```

This starts a STDIO-based MCP server that any compatible client (Claude Desktop, Cursor, Anything LLM, etc.) can use immediately.

### Connecting to Claude Desktop

Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "elemm-gateway": {
      "command": "elemm-gateway"
    }
  }
}
```

Then tell your agent: *"Connect to https://petstore3.swagger.io/api/v3/openapi.json and list all available pets."*

> [!TIP]
> See the [Gateway Reference](GATEWAY.md) for the complete documentation on security policies, authentication vault, sequence engine, and more.

---

## 2. Option B: Build Your Own Landmark Server

If you want to expose your own Python functions as Elemm landmarks, use the decorator-based approach:

```python
from elemm import AIProtocolManager, MetadataRegistry

registry = MetadataRegistry("landmarks.yaml")
manager = AIProtocolManager(registry=registry)

@manager.landmark("lighting:set_brightness")
async def set_brightness(room: str, level: int):
    """Sets the brightness level (0-100) for a specific room."""
    return {"room": room, "brightness": level, "status": "adjusted"}
```

---

## 3. How Agents Interact with Elemm

When an agent connects to an Elemm service (via the Gateway or a native server), it follows a strict discovery protocol:

1.  **Connect**: The agent calls `connect_to_site(url)` to establish a connection.
2.  **Get Manifest**: The agent calls `get_manifest()` to receive the protocol rules and a topology of available landmarks. This step authorizes the session.
3.  **Discover**: The agent calls `get_landmarks()` to see high-level functional areas.
4.  **Inspect**: The agent calls `inspect_landmark(landmark_id)` to get the exact technical signatures (parameters, types, descriptions) for the tools it needs.
5.  **Execute**: Only after inspection, the agent uses `call_action()` for single calls or `execute_sequence()` for multi-step pipelines with data piping.

---

## 4. Next Steps

*   **[Gateway Reference](GATEWAY.md)**: Full documentation for the Elemm Gateway (OpenAPI, GraphQL, Security, Vault, Sequences).
*   **[Developer Guide](DEVELOPER_GUIDE.md)**: Learn about Pydantic integration and SmartRepair.
*   **[Architecture Overview](ARCHITECTURE.md)**: Understand the "Landmark" philosophy.
*   **[Benchmarking Results](BENCHMARKING.md)**: See performance comparisons.
