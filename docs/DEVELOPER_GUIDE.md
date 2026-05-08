# Elemm Developer Guide

This guide explains how to build robust toolsets using the Elemm protocol.

---

## 1. Defining Actions with decorators

The `ElemmGateway` is your primary interface. It allows you to register Python functions as "Actions" within specific "Landmarks".

```python
from elemm import ElemmGateway
from typing import Literal

gateway = ElemmGateway(name="SecurityHub")

@gateway.action(
    landmark="AccessControl",
    description="Control the locking mechanism of a specific door.",
    remedy="If 'Access Denied', verify the door_id via 'AccessControl:get_status'."
)
async def toggle_lock(door_id: str, state: Literal["lock", "unlock"]):
    # Business logic here
    return {"status": "success", "door": door_id, "new_state": state}
```

---

## 2. Type Hints and Pydantic

Elemm automatically generates JSON schemas from your Python type hints. This ensures the AI knows exactly what data type to send.

### Using Pydantic for Complex Objects
For nested or complex inputs, use Pydantic models:

```python
from pydantic import BaseModel

class NetworkConfig(BaseModel):
    ip: str
    vlan: int = 10
    dhcp: bool = True

@gateway.action(landmark="Network")
def apply_config(hostname: str, config: NetworkConfig):
    # 'config' is automatically validated and instantiated as a Pydantic model
    return {"host": hostname, "applied": config.model_dump()}
```

---

## 3. SmartRepair: Guiding the Agent

The `remedy` parameter in the `@gateway.action` decorator acts as a safety net. If an agent calls a tool incorrectly, Elemm will return the error along with the remedy.

- **Standard Error**: `Invalid ID 'SRV-1'`
- **Elemm SmartRepair**: `Invalid ID 'SRV-1'. Use 'NOC:list_nodes' to find the correct server ID.`

This mechanism dramatically reduces "stuck" agents and improves autonomous task completion rates.

---

## 4. Manifest-Driven Discovery

Unlike standard MCP servers that send all tool definitions at once, Elemm uses a tiered discovery approach:

1.  **Landmarks**: Grouping tools by domain (e.g. `Security`, `HR`, `IT`).
2.  **Manifest**: A compact overview of all namespaces.
3.  **Landmark Inspection**: On-demand loading of specific tool schemas.

This prevents the "Context Fatigue" that occurs when an LLM is overwhelmed by hundreds of tool definitions.

---

## 5. Performance Best Practices

### Use Sequences for Chained Tasks
Encourage agents to use `execute_sequence` for multi-step operations. You can guide this behavior in the landmark descriptions.

### Explicit Variable Piping
Elemm supports native variable piping. Results from previous steps can be accessed via `$stepN` aliases, avoiding the need for the agent to manually extract and re-insert data into the prompt.
