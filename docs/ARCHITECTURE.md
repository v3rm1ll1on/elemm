# Elemm Architecture Overview

The Landmark Manifest Protocol is designed to solve the inherent scalability issues of standard tool-calling protocols.

---

## The Problem: The Swiss Army Knife Paradox

Standard AI toolsets (like basic MCP) often provide an agent with all available tools at once. 
As the toolset grows (e.g., 50+ tools), the following issues emerge:
- **Context Bloating**: The system prompt becomes massive, consuming tokens and increasing costs.
- **Latency**: Large prompts increase time-to-first-token.
- **Hallucinations**: The model loses focus and starts confusing similar tools or ignoring constraints.

---

## The Solution: Semantic Landmarks

Elemm solves this through a tiered discovery system called **Landmarks**:
- **Landmarks** function as an interactive table of contents.
- The agent initially only sees the high-level namespaces (e.g., `Security`, `IT`, `HR`).
- Detailed tool signatures are only loaded when the agent proactively "steps into" a specific landmark.
- This keeps the agent's context clean and focuses its reasoning power on the relevant subset of tools.

---

## The Discovery Cycle

The protocol follows a five-stage handshake:

1.  **Connect**: The agent calls `connect_to_site(url)` to establish a connection to a remote API.
2.  **Manifest Discovery**: The agent calls `get_manifest()` to receive the protocol rules and authorize the session. No tool signatures are provided at this stage.
3.  **Landmark Discovery**: The agent calls `get_landmarks()` to see available functional areas.
4.  **Landmark Inspection**: Based on the task, the agent selects relevant landmarks and calls `inspect_landmark(id)` to retrieve full technical signatures.
5.  **Execution**: The agent proceeds with `call_action()` or `execute_sequence()` once it has the required signatures.

---

## High-Performance Execution Engine

Elemm supports advanced execution patterns to minimize turn-around time:

### Atomic Actions
Standard request-response cycles for independent tasks via `call_action`.

### High-Performance Sequences
The `execute_sequence` command allows chaining multiple actions into a single LLM turn:
- **Native Piping**: Use results from previous steps (e.g., `$step0.id`) directly in subsequent commands.
- **Server-Side Execution**: The entire chain is resolved on the server, eliminating the need for multiple roundtrips to the LLM.
- **Error Handling**: `on_error: stop|continue` controls whether a failed step halts the pipeline or is skipped.
- **Smart Retry**: Steps can be configured to retry on specific error types (e.g., `RATE_LIMIT_EXCEEDED`).

---

## The Gateway: Broker Architecture

The **Elemm Gateway** is a universal MCP server that acts as a protocol-aware broker between AI agents and remote APIs.

### Multi-Protocol Support
The Gateway seamlessly bridges three API paradigms:
- **OpenAPI / Swagger**: REST APIs are automatically parsed into Elemm landmarks.
- **GraphQL**: Endpoints are introspected and mapped to landmarks.
- **Native Elemm**: Servers exposing `/.well-known/elemm-manifest.md` are natively supported.

### Tool Isolation (8 Core Tools)
The Gateway never exposes raw API endpoints to the MCP client. It provides exactly **8 generic core tools** (`connect_to_site`, `get_manifest`, `get_landmarks`, `inspect_landmark`, `call_action`, `execute_sequence`, `list_aliases`, `clear_session`). All domain-specific actions are accessed through `call_action` and `execute_sequence`.

### Security Policy (Guardian)
A built-in policy engine enforces restrictions before any request reaches the target API:
- **Pattern Blacklists**: Block actions containing destructive keywords (e.g., `delete`, `remove`).
- **Landmark Restrictions**: Hide and block entire functional areas (e.g., `admin`, `billing`).
- **HTTP Method Filtering**: Whitelist allowed methods (e.g., `GET`, `POST` only).
- **Discovery Filtering**: Blocked landmarks are invisible in `get_landmarks` output.

See [Gateway Reference](GATEWAY.md) for complete details.

---

## Autonomous Reliability (SmartRepair)

Elemm is built for autonomous systems where human intervention is minimized:

- **Remedy Injection**: Technical errors are supplemented with human-readable "remedies". If an agent fails, it receives clear instructions on how to correct its path.
- **Validation Hardening**: Strict validation ensures that agents follow the discovery protocol and use valid, real-world data instead of placeholders.
- **Type Mapping**: Automatic translation of Python types (Pydantic, Literals) into high-fidelity schemas for the LLM.
- **Forensic Auditing**: Every action and piped variable resolution is logged for complete auditability.
