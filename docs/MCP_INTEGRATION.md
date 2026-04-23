# MCP Integration (Model Context Protocol)

Elemm provides native support for the Model Context Protocol (MCP). This allows AI agents to use landmark-enabled APIs directly as tools without the need for manual definitions or extensive system prompting.

## Features

- **Automatic Tool Export**: Landmarks are transparently translated into MCP tool definitions.
- **Registry-based Navigation**: The bridge provides dedicated tools (`get_manifest`, `navigate`) to control the active context.
- **Session Isolation**: Every agent (SSE connection) receives an isolated bridge instance with its own navigation state.
- **Token Efficiency**: Reduction of static tool descriptions through dynamic delivery of instructions in case of errors.

## Navigation Model

Unlike flat MCP servers, Elemm uses a hierarchical model:

1. **get_manifest**: Returns the Markdown manifest of available landmarks and global tools.
2. **navigate**: Allows switching to a specific module. After the switch, the bridge dynamically updates the list of available tools.

This process minimizes the number of simultaneously visible tools and significantly increases reliability for large tool catalogs.

## Configuration in FastAPI

### SSE (Server-Sent Events)

For web-based deployments, `bind_mcp_sse` is recommended. This allows multiple agents to access the API simultaneously via HTTP.

```python
from elemm.fastapi import Elemm

ai = Elemm(agent_welcome="You are a forensics specialist.")
# ... Define landmarks ...

app = FastAPI()
ai.bind_to_app(app)
ai.bind_mcp_sse(app, route_prefix="/mcp")
```

Agents connect to: `http://your-api/mcp/sse`.

### Stdio (Dual-Boot)

For local development or benchmarks via pipes, `run_mcp_stdio` is used.

```python
if __name__ == "__main__":
    import sys
    if "--mcp" in sys.argv:
        ai.run_mcp_stdio("your_module:app", port=8001)
    else:
        uvicorn.run(app, port=8001)
```

## Hybrid Mode (Auto-Flattening)

Elemm automatically optimizes access:
- If an API has fewer than 10 landmarks and no explicit group structure is defined, all tools are exported flat.
- This eliminates navigation overhead ("Navigation Tax") for simple use cases.
- As complexity increases (more landmarks or groups), the protocol automatically switches to structured navigation.

## Dynamic Correction (Agent Repair Kit)

Elemm avoids writing detailed instructions and remedies into every static tool description. Instead, the protocol utilizes the HTTP 422 handler:
- If a validation error occurs, the response is enriched with precise instructions and the stored correction hint (remedy).
- The agent receives the required help exactly when needed.
- This saves valuable tokens on every request and keeps the context window clean.

## Security and Validation

The MCP bridge acts as a gateway:
- Tools are only callable if they are visible in the agent's current context or have global access.
- Session data is managed via isolated instances in the FastAPI middleware or the SSE handler to prevent data leakage between different agent sessions.
