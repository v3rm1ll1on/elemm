# MCP Integration (Model Context Protocol)

Elemm provides native support for the Model Context Protocol (MCP), allowing any landmark-enabled API to be used directly by AI agents (like Claude or Gemini) without manual tool definition or extensive system prompting.

## Features

- **Native Tool Export**: Landmarks are automatically converted to MCP tool definitions.
- **Mission Vaccination**: The agent persona (`agent_welcome`) and protocol rules are injected into every tool description.
- **Web-Native MCP (SSE)**: Expose MCP endpoints directly over HTTP/SSE.
- **Dual-Boot Stdio**: Run your API and an MCP Stdio bridge in a single process.

## Native Export Endpoint

The protocol automatically provides an MCP-compliant tool list at:
`GET /.well-known/mcp-tools.json`

This endpoint returns an array of MCP Tool objects, including parameters mapped from Pydantic models.

## Usage in FastAPI

### SSE (Server-Sent Events)

Use `bind_mcp_sse` to allow agents to connect to your API via HTTP. This is the recommended way for web-based deployments.

```python
from elemm.fastapi import Elemm

ai = Elemm(agent_welcome="You are a Logistics Manager.")
# ... define landmarks ...

app = FastAPI()
ai.bind_to_app(app)
ai.bind_mcp_sse(app, route_prefix="/mcp")
```

The agent can now connect to `http://your-api/mcp/sse`.

### Stdio (Dual-Boot)

For local development or benchmarking (e.g., using pipes), use `run_mcp_stdio`. This starts the web server in a background thread and the MCP Stdio bridge in the main thread.

```python
if __name__ == "__main__":
    import sys
    if "--mcp" in sys.argv:
        ai.run_mcp_stdio("your_module:app", port=8001)
    else:
        uvicorn.run(app, port=8001)
```

## Mission Vaccination

One of the core strengths of the Elemm-MCP integration is 'Vaccination'. Every tool description exported via MCP is prepended with the global `agent_welcome` and `protocol_instructions`. 

This ensures that:
1. The agent always knows its persona, even with a blank system prompt.
2. Context hygiene is maintained by isolating instructions to the active tool set.
3. Safety and alignment are enforced at the protocol level.

## Navigation & Context Groups

When an agent calls a landmark of type `navigation` that specifies an `opens_group`, the Elemm bridge automatically updates the active context group. The client is notified via the MCP `notifications/tool_list_changed` mechanism, forcing a refresh of the available tools.
