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

For enterprise scenarios, it is recommended to separate protocol metadata from the code using a `landmarks.yaml` file.

### YAML Schema Reference

#### Landmark (Namespace)
| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique identifier for the landmark. |
| `description` | `string` | High-level summary shown during discovery. |
| `priority` | `int` | Discovery priority (1 is highest). |
| `remedy` | `string` | Guidance shown to the agent on ANY tool error in this namespace. |
| `remedy_global` | `string` | Alias for `remedy`. |
| `instructions` | `string` | Mandatory behavioral rules for the agent when using this landmark. |

#### Tool (Action)
Defined within a landmark or as a standalone action in the registry.
| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique identifier for the action. |
| `description` | `string` | Detailed description of what the tool does. |
| `remedy` | `string` | Specific guidance for this tool (overrides landmark remedy). |
| `parameters` | `list` | List of parameter definitions (name, type, description, required). |
