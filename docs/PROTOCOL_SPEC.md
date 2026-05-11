# Elemm Protocol Specification

This document defines the technical standards for the Landmark Manifest Protocol (Elemm), covering discovery mechanisms, execution logic, and the SmartRepair system.

---

## 1. Landmark Architecture

The protocol organizes capabilities into **Landmarks** (logical namespaces). Each landmark groups related actions and provides a clear domain-specific boundary for AI agents.

### Landmark Metadata
A landmark definition must provide:
- **ID**: A unique namespace identifier (e.g., `security`, `repos`, `git`).
- **Description**: A high-level explanation of the landmark's purpose.
- **Actions**: A list of tools available within this namespace.

---

## 2. Standard Protocol Tools

Every Elemm-compliant gateway must expose the following 8 core tools:

### `connect_to_site(url: string)`
- **Purpose**: Establish a connection to a remote API.
- **Detection**: Auto-detects the interface type (OpenAPI, GraphQL, or native Elemm).
- **Side Effect**: Resets the session handshake state.

### `get_manifest()`
- **Purpose**: Initial discovery and session authorization.
- **Returns**: Protocol rules, landmark topology, and gateway globals.
- **Enforcement**: This call authorizes the session. Actions are blocked until it is called.

### `get_landmarks()`
- **Purpose**: High-level topology discovery.
- **Returns**: A summary of available functional areas and tool counts per landmark.
- **Security**: Landmarks restricted by the Security Policy are excluded from the response.

### `inspect_landmark(landmark_id: string | string[])`
- **Purpose**: Technical discovery for specific landmarks.
- **Returns**: Full TypeScript-style technical signatures for all actions in the specified namespaces.
- **Implementation Note**: Accepts either a single string ID or an array of IDs.

### `call_action(action: string, parameters: object)`
- **Purpose**: Single action execution.
- **Validation**: Security policy enforcement and schema validation.
- **Hygiene**: Supports `_select`, `_filter`, and `_limit` parameters.

### `execute_sequence(actions: object[], session_id?: string)`
- **Purpose**: Batch execution with dependency management.
- **Piping**: Supports the `$alias.field` syntax for passing data between steps.
- **State Persistence**: Each step's result is stored under its `alias` (or default `stepN`) in the session context.
- **Error Handling**: Per-step `on_error: "stop" | "continue"` controls pipeline behavior.
- **Smart Retry**: Steps can define `retry` count and `retryOn` error codes.
- **Resolution**: All variables are resolved server-side before execution.

### `list_aliases(session_id?: string)`
- **Purpose**: Inspect the current session memory bank.
- **Returns**: All stored aliases (results from previous sequence steps).

### `clear_session(session_id?: string)`
- **Purpose**: Privacy and memory hygiene.
- **Effect**: Clears all stored aliases for the specified session.

---

## 3. Variable Piping Syntax

Elemm enables dynamic data flow via a standardized syntax:
- **Direct Access**: `$step0`
- **Field Access**: `$step0.id`
- **Nested Objects**: `$step0.user.profile.email`
- **Array Indexing**: `$step1[0].status`
- **Combined**: `$step1[0].items[2].name`

The execution engine resolves these placeholders in real-time, ensuring that the agent does not need to manually manage intermediate state in its prompt.

---

## 4. Response Hygiene

Every action supports three universal parameters for context control:

| Parameter | Type | Description |
|---|---|---|
| `_select` | `string` | Comma-separated list of fields to return. Supports dot-notation. |
| `_filter` | `string` or `object` | Equality filter for array responses (e.g., `"state=open"`). |
| `_limit` | `integer` | Maximum number of items to return. |

Additionally, responses are automatically truncated to configurable limits to prevent context overflow.

---

## 5. SmartRepair Mechanism

When a protocol violation or execution error occurs, Elemm returns a structured error response instead of a standard stack trace:

- **`_PROTOCOL_ERROR`**: A machine-readable error code (e.g., `ACCESS_DENIED`, `PIPING_FAILED`).
- **`message`**: A clear explanation of the error.
- **`remedy`**: Actionable instructions for the agent (e.g., "Use 'inspect_landmark' to discover available actions.").
- **`_DEBUG_ECHO`**: A forensic payload showing the exact request that was sent.

### Fuzzy Matching
The engine attempts to correct common AI errors, such as calling a landmark namespace directly instead of a specific action, and returns the closest matching action IDs.

---

## 6. Security Policy

The gateway enforces a multi-layer security policy:

1. **HTTP Method Restriction**: Whitelist of allowed methods (empty list = all allowed).
2. **Action Blacklist**: Explicit action IDs to block.
3. **Landmark Blacklist**: Entire namespaces to hide and block.
4. **Pattern Matching**: Substrings in action names that trigger blocking (e.g., `delete`, `purge`).

Core tools are always exempt from security checks.

---

## 7. Protocol Constraints

1.  **Handshake Requirement**: Agents must call `get_manifest()` before any execution. Direct action calls are blocked with `PROTOCOL_VIOLATION`.
2.  **Broker Isolation**: The gateway only exposes 8 core tools to the MCP client. Domain-specific tools are never leaked.
3.  **Parameter Filtering**: The engine strictly filters tool arguments, passing only those defined in the underlying function signature to prevent AI "hallucination noise".
