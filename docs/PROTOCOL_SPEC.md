# Elemm Protocol Specification

This document defines the technical standards for the Landmark Manifest Protocol (Elemm), covering discovery mechanisms, execution logic, and the SmartRepair system.

---

## 1. Landmark Architecture

The protocol organizes capabilities into **Landmarks** (logical namespaces). Each landmark groups related actions and provides a clear domain-specific boundary for AI agents.

### Landmark Metadata
A landmark definition must provide:
- **ID**: A unique namespace identifier (e.g., `Security`, `IT_Ops`).
- **Description**: A high-level explanation of the landmark's purpose.
- **Actions**: A list of tools available within this namespace.

---

## 2. Standard Protocol Tools

Every Elemm-compliant gateway must expose the following core tools:

### `get_manifest(full: boolean = false)`
- **Purpose**: Initial discovery.
- **Returns**: A list of available Landmarks and their high-level descriptions.
- **Enforcement**: Gateways should enforce that this is the first tool called by the agent.

### `inspect_landmarks(landmark_id: string | string[])`
- **Purpose**: Technical discovery for specific landmarks.
- **Returns**: Full technical signatures (JSON/TypeScript) for all actions in the specified namespaces.
- **Implementation Note**: Accepts either a single string ID or an array of IDs.

### `call_action(action: string, parameters: object, alias?: string)`
- **Purpose**: Single action execution.
- **Validation**: Strict schema validation and landmark-existence checks.
- **State Persistence**: If an `alias` is provided, the result is stored in the session context for future reference.

### `execute_sequence(actions: object[])`
- **Purpose**: Batch execution with dependency management.
- **Piping**: Supports the `$alias.field` syntax for passing data between steps.
- **State Persistence**: Each step's result is stored under its `alias` (or default `stepN`) in the session context.
- **Conditions**: Actions can be conditionally executed based on previous results.
- **Resolution**: All variables are resolved server-side before execution.

---

## 3. Variable Piping Syntax

Elemm enables dynamic data flow via a standardized syntax:
- **Direct Access**: `$step0.id`
- **Nested Objects**: `$step0.user.profile.email`
- **Array Indexing**: `$step1.items[0].status`

The execution engine resolves these placeholders in real-time, ensuring that the agent does not need to manually manage intermediate state in its prompt.

---

## 4. SmartRepair Mechanism

When a protocol violation or execution error occurs, Elemm returns a structured `RepairResult` instead of a standard stack trace:

- **Message**: A clear explanation of the error.
- **Remedy**: Actionable instructions for the agent (e.g., "Use 'NOC:resolve_ip' first to get a valid hostname").
- **Expected Schema**: A hint of the correct parameter structure.

### Fuzzy Matching
The engine attempts to correct common AI errors, such as case-sensitivity issues in action IDs or minor typos in enum values, before returning a repair hint.

---

## 5. Protocol Constraints

1.  **Namespace Enforcement**: All actions must be prefixed with their landmark ID (e.g., `Security:quarantine`).
2.  **Handshake Requirement**: Agents must perform a manifest discovery before executing actions. Direct calls to underlying tools are blocked.
3.  **Parameter Filtering**: The engine strictly filters tool arguments, passing only those defined in the underlying function signature to prevent AI "hallucination noise".
