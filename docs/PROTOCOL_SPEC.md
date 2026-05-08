# 📜 Elemm v2 Protocol Specification

This document defines the technical standards for the Elemm v2 protocol, covering landmark definitions, execution logic, and the SmartRepair system.

---

## 1. Landmark Definition (`landmarks.yaml`)
Landmarks are defined in a YAML manifest. Each landmark contains a group of related tools.

### Schema:
```yaml
landmarks:
  - id: "namespace_id"
    description: "High-level purpose of this namespace."
    tools:
      - id: "tool_name" # Fully qualified as namespace_id:tool_name
        description: "What the tool does."
        parameters:
          - name: "param_name"
            type: "string"
            description: "Description of the parameter."
            required: true
        returns: "{ field: type }" # TypeScript-style return hint
        remedy: "Specific advice if this tool fails."
```

---

## 2. Standard Protocol Tools
Every Elemm-compliant gateway MUST expose the following core tools:

### `get_manifest(full: boolean = false)`
- **Purpose**: High-level discovery.
- **Returns**: A list of Landmark IDs and descriptions. If `full=true`, it returns the entire technical registry (use with caution).

### `inspect_landmark(id: string)`
- **Purpose**: Technical discovery for a specific landmark.
- **Returns**: Full TypeScript signatures for all tools within the requested landmark.

### `call_action(action: string, parameters: object)`
- **Purpose**: Single action execution.
- **Validation**: Strict schema validation and landmark-existence check.

### `execute_sequence(actions: object[])`
- **Purpose**: High-performance pipeline execution.
- **Alias System**: Each step can have an `alias` (e.g., `step0`).
- **Piping**: Results can be accessed via `$alias.field`.

---

## 3. Variable Piping Syntax
Elemm supports dynamic data flow between tools in a sequence.

- **Syntax**: `$alias.field_name`
- **Nested Fields**: `$alias.user.id` (supports deep objects).
- **Array Access**: `$alias.items[0].id`.
- **Resolution**: The engine resolves these variables server-side before passing them to the next tool.

---

## 4. SmartRepair JSON Structure
When a protocol violation or tool error occurs, the system returns a `RepairResult`:

```json
{
  "status": "error",
  "message": "Human-readable description of what went wrong.",
  "remedy": "Specific instructions on how to fix the call.",
  "suggested_fix": "Optional: A ready-to-use tool call string.",
  "expected_schema": { "type": "object", "properties": { ... } }
}
```

---

## 5. Web Discovery (.well-known)
For HTTP-based gateways, Elemm standardizes discovery via the following endpoints:

- `GET /.well-known/elemm-manifest.md`: Returns the high-level summary manifest.
- `GET /.well-known/elemm-inspect.md?landmark_id=ID`: Returns technical signatures for a landmark.
- `POST /.well-known/elemm/execute`: Central execution endpoint for `call_action` and `execute_sequence`.

---

## 6. Protocol Constraints
1.  **Namespace Isolation**: Tools cannot be called without their namespace prefix (e.g., `noc:resolve`).
2.  **Manifest-First**: Gateways may enforce that `get_manifest` is called before any execution tools become active.
3.  **Strict Parameters**: Missing required parameters MUST trigger a SmartRepair response with a schema hint.
