# 🛠️ Elemm v2 Developer Guide

This guide explains how to build and integrate tools into the Elemm v2 framework.

---

## 1. The Core Concept: Handlers & Metadata
In Elemm, a tool consists of two parts:
1.  **The Handler**: A Python function that performs the work.
2.  **The Metadata**: Declarative information (JSON/YAML) that tells the AI *how* and *why* to use the tool.

---

## 2. Creating your first Landmark
The easiest way to register a tool is using the `@manager.landmark` decorator.

```python
from elemm.core.manager import AIProtocolManager
from typing import Literal

manager = AIProtocolManager()

@manager.landmark(
    "security:lock_door",
    description="Lock or unlock a specific door.",
    remedy="Check the door_id in 'security:get_status' if this fails."
)
async def lock_door(door_id: str, action: Literal["lock", "unlock"]):
    # The logic goes here
    return {"status": "success", "door": door_id, "state": action}
```

### 🧠 Pro-Tip: Let Elemm do the heavy lifting
Instead of writing complex JSON schemas, just use Python type hints. Elemm's **Auto-Mapping engine** translates them for the AI:
- `Literal["red", "blue"]` -> The AI sees a choice between "red" and "blue".
- `int` / `float` -> The AI knows it needs a number.
- **Pydantic Models** -> The AI gets a full structural map of the data.

---

## 3. Using Pydantic for Complex Inputs
If your tool requires complex nested data, just use a Pydantic model. Elemm will handle the schema generation and validation for you.

```python
from pydantic import BaseModel

class Config(BaseModel):
    brightness: int
    color_temp: int = 2700

@manager.landmark("lighting:apply_config")
def set_lighting(zone: str, config: Config):
    # 'config' is automatically instantiated as a Pydantic model!
    return {"zone": zone, "applied": config.model_dump()}
```

---

## 4. Integrating YAML Metadata
While you can define everything in Python, we recommend keeping your descriptions and remedies in a `landmarks.yaml` file. This allows you to update the AI's "instructions" without redeploying code.

**`landmarks.yaml`**:
```yaml
landmarks:
  - id: "security:lock_door"
    remedy: "Access denied? Ensure the user has the 'admin' role."
    parameters:
      - name: "door_id"
        options: ["front_door", "back_door", "garage"]
```

**Python**:
```python
manager.load_metadata("landmarks.yaml")
```

---

## 5. SmartRepair: Helping the AI help itself
Think of `remedy` as a **safety net**. When the AI fails (e.g., using a wrong ID), it usually gets a cryptic technical error. With a remedy, you give it a "Hitchhiker's Guide" response.

- **❌ Bad (Technical)**: `ValueError: ID 'f_door' not in database.`
- **✅ Good (Human/AI)**: `Invalid door_id. Use 'security:get_status' to find the correct ID (e.g., 'front_door').`

> [!TIP]
> Always assume the AI is a smart intern who just needs a little hint to get back on track.

---

---

## 6. Guiding the AI (Prompt Engineering via Metadata)
While you don't call the tools yourself, you control how the AI uses them. The AI's "brain" is guided by your `description` and `instructions`.

### How to enforce Sequencing
If you want the AI to use `execute_sequence` for better performance (e.g., when arming the house and turning off lights), tell it so in the global or landmark-level instructions.

**Example `landmarks.yaml`**:
```yaml
instructions: |
  When the user says "Goodnight", ALWAYS use 'execute_sequence' to arm the security system and turn off all lights in a single turn.
```

### What the AI actually does (Under the hood)
When you provide good metadata, a complex task like "Lock the front door and if successful, arm the security system" results in a single efficient call:

**AI Call Example**:
```json
execute_sequence(actions=[
  {
    "action": "security:lock_door",
    "parameters": {"door_id": "front_door", "action": "lock"},
    "alias": "door_lock"
  },
  {
    "action": "lighting:set_state",
    "condition": "$door_lock.status == 'success'",
    "parameters": {"zone": "all", "state": "off"},
    "alias": "lights_off"
  },
  {
    "action": "security:arm",
    "condition": "$lights_off.status == 'success'",
    "parameters": {"mode": "night"}
  }
])
```

### Best Practices for Metadata
- **Tool Description**: Start with a strong verb. "Lock the door" is better than "Door locking mechanism".
- **Parameter Description**: Be specific about formats. "Target room ID (e.g. 'kitchen')" instead of "the room".
- **Remedies**: Treat these as "System Prompts" that only trigger on failure. They are your second chance to guide the AI.
