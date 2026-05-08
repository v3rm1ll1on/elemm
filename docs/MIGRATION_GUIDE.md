# Quick Migration: Shifting your API to Elemm

This guide provides a 3-step action plan to migrate your existing tools, scripts, or APIs to the Elemm Landmark Protocol.

---

## Step 1: Categorize your Tools (Landmarks)

Instead of a flat list of tools, group your functions into logical domains. 

**Example:**
- `get_user`, `list_users` -> Landmark: **HR**
- `restart_server`, `get_load` -> Landmark: **Ops**

---

## Step 2: Wrap your Functions

Replace your existing tool decorators (or manual registries) with the `@gateway.action` decorator.

```python
from elemm import ElemmGateway

gateway = ElemmGateway(name="MyService")

# Just add the decorator and specify a landmark
@gateway.action(landmark="Ops")
async def get_system_load():
    # Your existing code stays exactly the same
    return {"load": 0.42}
```

**Key Difference:** You don't need to rename your functions or change your business logic. The protocol handles the namespacing (e.g., `Ops:get_system_load`) automatically.

---

## Step 3: Enrich with Metadata (3a or 3b)

You need to tell the agent what your tools do. You have two ways to do this:

### 3a: The Inline Way (Fastest)
Add descriptions and "SmartRepair" remedies directly to your decorators. This is great for quick migrations and small toolsets.

```python
@gateway.action(
    landmark="Ops",
    description="Restarts a specific server node.",
    remedy="Use 'Ops:list_servers' to find a valid server name."
)
async def restart_server(name: str):
    ...
```

### 3b: The Declarative Way (Scalable)
Move all metadata (descriptions, global remedies, instructions) into a `landmarks.yaml`. This keeps your Python code "pure" and allows you to update the agent's behavior without redeploying code.

```yaml
# landmarks.yaml
landmarks:
  - id: "Ops"
    description: "System administration and monitoring tools."
    remedy_global: "Always verify the target node status before executing write actions."
```

In your Python code, simply load it:
```python
gateway.load_metadata("landmarks.yaml")
```

---

## Summary: What changed?

1.  **No more massive System Prompts**: The protocol handles discovery and guidance.
2.  **Less Token Waste**: Agents only load the tools they actually need for the current landmark.
3.  **Automatic Error Recovery**: The `remedy` loop fixes agent mistakes on-the-fly.
