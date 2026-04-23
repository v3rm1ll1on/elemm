# Elemm Reference: Decorators and Options

Elemm provides an intuitive API to mark FastAPI routes as AI landmarks. The framework handles the extraction of schemas, types, and validation rules directly from the Python code.

## 1. Decorator Aliases

Elemm provides three specialized decorators. The main difference lies in the preconfigured default type:

| Decorator | Default Type | Recommended Usage |
| :--- | :--- | :--- |
| **`@ai.tool(id=...)`** | `"read"` | For pure information queries (search, read, list). |
| **`@ai.action(id=...)`** | `"write"` | For state-changing actions (create, update, delete). |
| **`@ai.landmark(id=...)`** | *None* | Generic. Requires manual specification of `type`. |

```python
# Example for automatic typing:
@ai.tool(id="get_user")      # Automatically sets type="read"
@ai.action(id="delete_user") # Automatically sets type="write"
```

### `id` (String, Required)
The unique identifier of the tool. Elemm automatically sanitizes the ID from special characters.

### `instructions` (String, Optional)
**Highest Priority Metadata.** If provided, this string is used as the primary description for the AI agent. Use this to give specific, mission-oriented instructions to the LLM that should differ from the technical docstring.

### `description` (String, Optional)
**Medium Priority Metadata.** Used if `instructions` is not provided. If both are missing, Elemm automatically extracts the description from the function's **Docstring**.

### `type` (String)
Defines the nature of the action:
- `read`: Information gathering (Default for `@ai.tool`).
- `write`: Data modification (Default for `@ai.action`).
- `navigation`: Signposts for context switching.

### `remedy` (String, Optional)
Specific correction instruction transmitted to the agent in case of validation errors (HTTP 422). This is a core part of the "Agent Repair Kit". See [REPAIR_KIT.md](REPAIR_KIT.md).

### `global_access` (Boolean)
If set to `True`, the landmark is visible at the root level and in every sub-manifest (module). Use for cross-cutting tools like `search`.

### `hidden` (Boolean)
The landmark is registered in the code but invisible to the agent (except when accessed via the internal group `_INTERNAL_ALL_`).

## 3. Automated Extraction (Deep Type Discovery)

Elemm uses reflection to generate precise metadata for AI models:

### Enum and Literal Support
When Python `Enum` or `typing.Literal` types are used, Elemm automatically recognizes them and maps them to `options` in the manifest. The agent receives an exact list of allowed values.

### Response Schema
Elemm inspects the `response_model` of the FastAPI route. The agent receives structured information about what data structure the tool will return.

### Constraints and Validation
Pydantic constraints such as `ge` (greater than or equal to), `le` (less than or equal to), or `pattern` (Regex) are translated directly into the JSON schema for the agent.
