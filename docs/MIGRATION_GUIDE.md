# Migration Guide: Moving to Elemm v1.0.1

This guide helps you transition your existing landmark implementations to the stabilized v1.0.1 protocol.

---

## 1. High-Level API: Use `ElemmGateway`

In previous versions, you might have used `AIProtocolManager` directly. For v1.0.1, we introduced the `ElemmGateway` facade to simplify server setup and tool registration.

**Old (v1.0.0):**
```python
from elemm.core.manager import AIProtocolManager
manager = AIProtocolManager()

@manager.action(namespace="Compute", name="start")
async def start_instance(id: str):
    ...
```

**New (v1.0.1):**
```python
from elemm import ElemmGateway
gateway = ElemmGateway(name="CloudControl")

@gateway.action(landmark="Compute")
async def start_instance(id: str):
    ...
```
*Note: The `landmark` parameter replaces `namespace`. The tool name is automatically derived from the function name.*

---

## 2. Automated Prefixing

Elemm v1.0.1 automatically prefixes tool IDs with their landmark name (e.g., `Compute:start_instance`). You no longer need to manually manage unique strings across different landmarks.

---

## 3. Declarative Metadata (YAML)

If you were using custom dictionary-based metadata loading, switch to the standardized `load_metadata` method. We've also added support for global remedies.

**Old YAML:**
```yaml
namespaces:
  - id: "Compute"
    remedy: "Global fix..."
```

**New YAML (v1.0.1):**
```yaml
landmarks:
  - id: "Compute"
    remedy_global: "Global fix..." # New alias for better readability
```

---

## 4. Discovery Endpoints

The protocol now strictly follows the well-known URI pattern for discovery. Ensure your agentic wrappers point to:

- **Manifest**: `GET /.well-known/elemm-manifest.md`
- **Inspection**: `GET /.well-known/elemm-inspect.md?landmark_id=...`
- **Execution**: `POST /.well-known/elemm/execute`

---

## 5. Pydantic Unboxing

v1.0.1 introduces "Smart Unboxing". If your function takes a single Pydantic model, it will now appear as individual parameters to the agent. This requires **no code changes** on your part, but you will notice cleaner tool schemas in the manifest.
