# Elemm Developer Guide

This guide explains how to build robust toolsets using the Elemm protocol.

---

## 1. Defining Actions with decorators

The `ElemmGateway` is your primary interface. It allows you to register Python functions as "Actions" within specific "Landmarks".

```python
from elemm import ElemmGateway
from typing import Literal

gateway = ElemmGateway(name="CloudGuardian")

@gateway.action(
    landmark="Compute",
    description="Control the power state of a virtual machine.",
    remedy="If the instance_id is unknown, use 'Compute:list_instances'."
)
async def toggle_power(instance_id: str, state: Literal["start", "stop"]):
    # Business logic here
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

@gateway.action(landmark="Compute")
def create_instance(name: str, config: InstanceConfig):
    # 'config' is automatically instantiated from individual tool arguments
    return {"name": name, "specs": config.model_dump()}
```

---

## 3. SmartRepair: Guiding the Agent

The `remedy` parameter in the `@gateway.action` decorator acts as a safety net. If an agent calls a tool incorrectly, Elemm will return the error along with the remedy.

- **Standard Error**: `Invalid Instance ID 'VM-99'`
- **Elemm SmartRepair**: `Invalid Instance ID 'VM-99'. Use 'Compute:list_instances' to find the correct ID.`

This mechanism dramatically reduces "stuck" agents and improves autonomous task completion rates.

---

## 4. Manifest-Driven Discovery

Unlike standard MCP servers that send all tool definitions at once, Elemm uses a tiered discovery approach:

1.  **Landmarks**: Grouping tools by domain (e.g. `Compute`, `Security`, `Networking`).
2.  **Manifest**: A compact overview of all namespaces.
3.  **Landmark Inspection**: On-demand loading of specific tool schemas.

This prevents the "Context Fatigue" that occurs when an LLM is overwhelmed by hundreds of tool definitions.

---

## 5. Performance Best Practices

### Use Sequences for Chained Tasks
Encourage agents to use `execute_sequence` for multi-step operations. You can guide this behavior in the landmark descriptions.

### Explicit Variable Piping
Elemm supports native variable piping. Results from previous steps can be accessed via `$stepN` aliases, avoiding the need for the agent to manually extract and re-insert data into the prompt.

---

## 6. Declarative Configuration (YAML)

For enterprise scenarios, it is recommended to separate protocol metadata from the code using a `landmarks.yaml` file. You can load this via `gateway.load_metadata("landmarks.yaml")`.

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
