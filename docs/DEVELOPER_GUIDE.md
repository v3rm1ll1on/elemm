# Elemm Developer Guide

This guide explains how to build robust toolsets using the Elemm protocol.

---

## 1. Defining Actions with Decorators

The `AIProtocolManager` (aliased as `ElemmGateway`) is your primary interface. It allows you to register Python functions as "Actions" within specific "Landmarks".

```python
from elemm import AIProtocolManager, MetadataRegistry

registry = MetadataRegistry("landmarks.yaml")
manager = AIProtocolManager(registry=registry)

@manager.landmark("compute:toggle_power")
async def toggle_power(instance_id: str, state: str):
    """Control the power state of a virtual machine."""
    return {"status": "success", "instance": instance_id, "new_state": state}
```

### 1.1 Exposing Your Landmark Server

Once you have defined your landmarks, you can expose them in two ways depending on your application model:

#### Option A: FastAPI (Web API via HTTP)
Perfect for microservices, cloud deployments, or multi-client networks. The protocol manifest is served dynamically via HTTP:

```python
import uvicorn
from fastapi import FastAPI
from elemm import AIProtocolManager
from elemm.gateways.fastapi import FastAPIGateway

app = FastAPI()
manager = AIProtocolManager()

@manager.landmark("compute:toggle_power")
async def toggle_power(instance_id: str, state: str):
    """Control the power state of a virtual machine."""
    return {"status": "success", "instance": instance_id, "new_state": state}

gateway = FastAPIGateway(manager)
gateway.bind_to_app(app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

#### Option B: Standalone MCP (Local via STDIO)
Perfect for direct native integration with local AI agents (e.g. Claude Desktop) without needing web servers or port bindings:

```python
from elemm import ElemmGateway

# Initialize the high-level gateway wrapper
gateway = ElemmGateway(name="ComputeServer")

@gateway.action("compute:toggle_power")
async def toggle_power(instance_id: str, state: str):
    """Control the power state of a virtual machine."""
    return {"status": "success", "instance": instance_id, "new_state": state}

if __name__ == "__main__":
    gateway.run_mcp()
```

---

## 2. Type Hints and Pydantic

Elemm automatically generates JSON schemas from your Python type hints. This ensures the AI knows exactly what data type to send.

### Using Pydantic for Complex Objects
For nested or complex inputs, use Pydantic models. Elemm will automatically "unbox" the model into individual tool parameters for the agent.

```python
from pydantic import BaseModel

class InstanceConfig(BaseModel):
    image: str = "ubuntu-24.04"
    cpu_cores: int = 2
    memory_gb: int = 4

@manager.landmark("compute:create_instance")
def create_instance(name: str, config: InstanceConfig):
    # 'config' is automatically instantiated from individual tool arguments
    return {"name": name, "specs": config.model_dump()}
```

---

## 3. SmartRepair: Guiding the Agent

When an agent calls a tool incorrectly, Elemm returns a structured error with actionable guidance:

- **Standard Error**: `Invalid Instance ID 'VM-99'`
- **Elemm SmartRepair**: `{"_PROTOCOL_ERROR": "NOT_FOUND", "message": "Invalid Instance ID 'VM-99'", "remedy": "Use 'inspect_landmark(compute)' to find valid action signatures."}`

The SmartRepair engine also handles:
- **Namespace execution prevention**: Calling `call_action(action="compute")` instead of a specific tool.
- **Fuzzy matching**: Suggesting the closest matching action ID for typos.
- **Remote error translation**: Mapping HTTP status codes to protocol error codes with remedies.

---

## 4. Manifest-Driven Discovery

Unlike standard MCP servers that send all tool definitions at once, Elemm uses a tiered discovery approach:

1.  **Connect**: Establish context with `connect_to_site`.
2.  **Manifest**: Retrieve protocol rules and authorize the session via `get_manifest`.
3.  **Landmarks**: See available functional areas via `get_landmarks`.
4.  **Inspection**: On-demand loading of specific tool schemas via `inspect_landmark`.
5.  **Execution**: Execute actions via `call_action` or `execute_sequence`.

This prevents the "Context Fatigue" that occurs when an LLM is overwhelmed by hundreds of tool definitions.

### Searching at Scale with Smart Pagination & Filtering

When dealing with large environments (like a city with 100,000+ tools), agents can use `search_landmarks(query="...")` to look up specific functional zones or actions.

To protect the agent's context window from accidental bloat during broad searches, the Elemm Gateway applies smart search filters:
- **Search Cap & Pagination**: Broad keyword queries (e.g. `power|failure`) are automatically capped to 10 results at a time.
- **Smart Remediation Hints**: When results are truncated, the Gateway dynamically injects a warning instructing the agent to narrow down the query.
- **Dynamic Recommendations**: The search response includes a custom recommendation showing the agent how to inspect or fetch the manifest for the exact namespace of the first matching landmark (e.g. `get_manifest(landmark_id="Zentrum:Sector_042:energy")`).

---

## 5. Performance Best Practices

### Use Sequences for Chained Tasks
Encourage agents to use `execute_sequence` for multi-step operations. This reduces LLM roundtrips and saves tokens.

### Response Hygiene
Use the built-in hygiene parameters in every call:
- `_select`: Return only specific fields (e.g., `"name, owner.login"`).
- `_filter`: Filter array responses (e.g., `"state=open"`).
- `_limit`: Cap the number of returned items.

### Explicit Variable Piping
Elemm supports native variable piping. Results from previous steps can be accessed via `$stepN` or custom aliases, avoiding the need for the agent to manually extract and re-insert data.

---

## 6. Declarative Configuration (YAML)

For enterprise scenarios, it is recommended to separate protocol metadata from the code using a `landmarks.yaml` file. This allows you to update behavioral rules, descriptions, and remedies without redeploying code.

### YAML Document Root Properties

| Field | Type | Description |
| :--- | :--- | :--- |
| `global_aliases` | `dict` | Mapping of parameter names to lists of global search synonyms (e.g. `user_id: [uid, customer_id, user]`). |
| `landmarks` | `list` / `dict` | List of landmark metadata objects (when using lists) or direct ID-to-metadata mapping. |

### Landmark & Action Metadata Schema

Both namespaces (landmarks) and executable leaf actions share the same schema:

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `id` | `string` | *Required* | Unique identifier. Use `namespace:action_name` to define hierarchy. |
| `description` | `string` | *Required* | Detailed description shown to the agent during discovery or inspection. |
| `type` | `string` | `"navigation"` | Either `"navigation"` (for namespaces/areas) or `"action"` (for executable tools). |
| `remedy` | `string` | `null` | Guidance/SmartRepair shown to the agent on failure (shadows exceptions). |
| `remedy_global` | `string` | `null` | Alias for `remedy`. |
| `instructions` | `string` | `null` | Behavioral guidelines dynamically injected when the agent connect/inspects this landmark. |
| `priority` | `int` | `null` | Discovery sort weight (1 is highest priority). |
| `returns` | `string` | `null` | Description of the returned value. |
| `response_schema` | `object` | `null` | Standard JSON Schema representing the return object. |
| `tags` | `list` | `[]` | Category tags for search indexing. |
| `groups` | `list` | `[]` | Access groups or operational grouping. |
| `meta` | `object` | `{}` | Custom dictionary for application-specific metadata. |
| `parameters` | `list` | `[]` | List of [Parameter definitions](#parameter-schema). |
| `tools` | `list` | `[]` | Nested list of child landmarks/actions (useful for hierarchical definitions). |

### Parameter Schema

Defined under the `parameters` list of an action:

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `name` | `string` | *Required* | The programmatic parameter name expected by the handler function. |
| `type` | `string` | `"string"` | The data type (e.g., `string`, `number`, `integer`, `boolean`, `array`, `object`). |
| `description` | `string` | *Required* | Detailed explanation of what the parameter represents. |
| `required` | `boolean` | `true` | Set to `false` if the parameter is optional. |
| `default` | `any` | `null` | The default value when not specified by the agent. |
| `options` | `list` / `dict` | `null` | Restricts values to a list of exact enum options, supporting fuzzy correction. |
| `aliases` | `list` | `[]` | Action-specific parameter synonyms (e.g. `node_id: [node, node_name]`). |
| `location` | `string` | `"query"` | Where the value resides in bridges (e.g., `"query"`, `"path"`, `"header"`, `"body"`). |
| `meta` | `object` | `{}` | Custom key-value pairs. |

---

## 7. Launching the Server (STDIO & SSE Mode)

Once you have defined your landmarks and actions, you can boot your server as a native MCP server using `MCPGateway`. It supports two transport modes: **STDIO** (perfect for local agents like Claude Desktop) and **SSE** (Server-Sent Events, for web, remote, or containerized deployments).

### STDIO Mode (Local Integration)
This is the standard mode for local integrations. The server communicates via standard input/output.

```python
from elemm.gateways.mcp_server import MCPGateway

# Initialize the gateway
server = MCPGateway(manager, server_name="My-Landmark-Server")

# Run in STDIO mode (blocks the execution thread)
server.run_stdio()
```

### SSE Mode (Web / Remote Integration)
This starts an asynchronous Starlette web server powered by Uvicorn, making the landmark server accessible over HTTP via Server-Sent Events.

```python
from elemm.gateways.mcp_server import MCPGateway

# Initialize the gateway
server = MCPGateway(manager, server_name="My-Landmark-Server")

# Run in SSE mode on a custom port (blocks the execution thread)
server.run_sse(host="0.0.0.0", port=8005)
```

The SSE server exposes two standard endpoints:
- `GET /sse`: The SSE subscription endpoint.
- `POST /messages`: The endpoint for sending client commands.
