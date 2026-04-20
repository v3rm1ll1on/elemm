# Elemm Reference: Decorators & Options 📜

Elemm provides a clean, intuitive API for marking your FastAPI routes as AI Landmarks.

---

## The Core Decorators

Elemm provides three identical aliases. Use whichever fits your project's naming convention:

- **`@ai.landmark(...)`**: The precise term for semantic navigation. Best for core architecture.
- **`@ai.tool(...)`**: Familiar for developers using OpenAI Tools or LangChain.
- **`@ai.action(...)`**: Standard terminology for API developers. Best for "Write" operations.

```python
# All of these are equivalent:
@ai.landmark(id="search")
@ai.tool(id="search")
@ai.action(id="search")
```

---

## Parameter Reference

### `id` (string, Required)
The unique identifier for the action. This is the "Function Name" the AI uses.
- *Tip:* Use snake_case. Elemm sanitizes these for you if they come from tags.

### `type` (string, Required)
Categorizes the action. This influences how navigation and filtering work.
- `read`: For fetching data (GET-style).
- `write`: For modifying data (POST/PUT/DELETE). Stripped in Read-Only mode.
- `navigation`: For signposts that open new modules.

### `description` (string, Optional)
The semantic instruction for the AI. 
- *Fallback:* If omitted, the function's **docstring** is automatically used.
- *Tip:* Be concise but descriptive. This is the agent's primary guide.

### `instructions` (string, Optional)
Specific "Rules of Engagement" for this action. 
- *Use Case:* Enforcing business logic like "Ask the user for confirmation BEFORE calling this." 

### `remedy` (string, Optional)
The self-healing instruction for error recovery.
- *Revealed:* Only shown during a 422 Validation Error. See [REPAIR_KIT.md](REPAIR_KIT.md).

### `global_access` (boolean, Default: `False`)
If `True`, this landmark is visible in the Root manifest AND every sub-group manifest.
- *Use Case:* Search tools, help desks, or system status checks.

### `hidden` (boolean, Default: `False`)
If `True`, the tool is registered in your code but excluded from the public AI manifest.
- *Use Case:* Sensitive internal endpoints that should not be discovered by agents.

---

## The Elemm Class Reference

### `Elemm(agent_welcome=..., version=..., protocol_instructions=...)`
The main manager class. (Alias for `FastAPIProtocolManager`).

- `agent_welcome`: The first message the agent sees.
- `protocol_instructions`: Global rules for the entire API (overrides defaults).
- `debug`: If `True`, prints discovery logs to the console.

### Methods
- `bind_to_app(app: FastAPI)`: Scans all routes and registers landmarks. Includes the Agent-Repair-Kit.
- `get_router()`: Returns the APIRouter for `/.well-known/llm-landmarks.json`.
- `get_manifest()`: Returns the raw manifest dictionary.
