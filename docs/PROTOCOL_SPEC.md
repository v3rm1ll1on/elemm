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
            type: "string" # Supports auto-mapping from Pydantic, Literal, Enum
            description: "Description of the parameter."
            required: true
            options: ["val1", "val2"] # Optional: Strict list of allowed values (Enum)
        returns: "{ field: type }" # TypeScript-style return hint
        remedy: "Specific advice if this tool fails." # Tool-specific recovery instruction
```

---

## 2. Standard Protocol Tools
Every Elemm-compliant gateway MUST expose the following core tools:

### `get_manifest(full: boolean = false)`
- **Purpose**: High-level discovery.
- **Returns**: A list of Landmark IDs and descriptions. If `full=true`, it returns the entire technical registry (use with caution).

### `inspect_landmarks(landmark_ids: string[])`
- **Purpose**: Technical discovery for one or more specific landmarks.
- **Returns**: Full TypeScript signatures for all tools. 
- **Type Mapping**: If a parameter has `options`, it is rendered as a TypeScript Union (e.g., `mode: "home" | "away"`). This forces LLM precision.

### `call_action(action: string, parameters: object, alias?: string)`
- **Purpose**: Single action execution.
- **Validation**: Strict schema validation and landmark-existence check.
- **Alias**: If provided, the result is stored in the global session context, allowing for cross-turn data piping.

### `execute_sequence(actions: object[])`
- **Purpose**: High-performance pipeline execution.
- **Alias System**: Each step can have an `alias` (e.g., `step0`).
- **Piping**: Results can be accessed via `$alias.field`.
- **Conditions**: Each action can have a `condition` field (e.g., `"condition": "$step0.status == 'ok'"`). If the condition is not met, the step is skipped.
- **String Interpolation**: Variables can be used inside strings, e.g., `{"message": "Result for $city: $step0.data"}`.

### `list_aliases()`
- **Purpose**: Debugging and state inspection.
- **Returns**: A dictionary of all current aliases and their stored values in the session context.

---

## 3. Variable Piping Syntax
Elemm supports dynamic data flow between tools in a sequence.

- **Syntax**: `$alias.field_name`
- **Nested Fields**: `$alias.user.id` (supports deep objects).
- **Array Access**: `$alias[0].id` or `$alias.items[0].id`.
- **Ambiguity Detection**: If a field is accessed on a list of objects, the engine attempts to resolve it. If multiple items match, it returns an error requesting an explicit index.
- **Resolution**: The engine resolves these variables server-side before passing them to the next tool. It supports both direct references and interpolation within strings.

---

## 4. SmartRepair JSON Structure
When a protocol violation or tool error occurs, the system returns a `RepairResult`:

```json
{
  "status": "error",
  "message": "Human-readable description of what went wrong.",
  "remedy": "Specific instructions on how to fix the call.",
  "suggested_fix": "Optional: A ready-to-use tool call string.",
  "expected_schema": { "type": "object", "properties": { ... } },
  "valid_options": ["option1", "option2"]
}
```

### SmartRepair Features:
- **Fuzzy Matching**: Automated correction for case-sensitivity or typos in action IDs and enum values.
- **Placeholder Detection**: Prevents execution with unresolved variables (e.g. `$stepX`) or AI placeholders like `UNKNOWN`.
- **Direct Call Protection**: Blocks attempts to call underlying tools directly, forcing the use of the protocol handshake.
- **Remedy Shadowing**: Internal tool errors are replaced by high-level remedies to keep the LLM focused on recovery rather than technical stack traces.

---

## 5. Web Discovery (.well-known)
For HTTP-based gateways, Elemm standardizes discovery via the following endpoints:

- `GET /.well-known/elemm-manifest.md`: Returns the high-level summary manifest.
- `GET /.well-known/elemm-inspect.md?landmark_id=ID`: Returns technical signatures for a landmark.
- `POST /.well-known/elemm/execute`: Central execution endpoint for `call_action` and `execute_sequence`.

---

## 6. Protocol Constraints
1.  **Namespace Isolation**: Tools cannot be called without their namespace prefix (e.g., `noc:resolve`).
2.  **Manifest-First (Safety Lock)**: Gateways MUST enforce that `get_manifest` is called before any execution tools (`call_action`, `execute_sequence`) become active. Failure to do so results in a "CRITICAL PROTOCOL VIOLATION".
3.  **Strict Parameters**: Missing required parameters MUST trigger a SmartRepair response with a schema hint.
4.  **Handler Hardening**: The engine only passes arguments that are present in the underlying function's signature, filtering out AI noise.
