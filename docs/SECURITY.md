# Elemm Security: Context Validation and Session Isolation

The Elemm protocol acts as a shield by regulating the interaction between AI agents and APIs, limiting access, and hiding technical complexity.

## 1. Context-Aware Tool Validation

In Model Context Protocol (MCP) mode, the Elemm bridge acts as an intelligent firewall. A tool cannot be called simply by knowing its name. The bridge checks on every call:
- Is the tool visible in the agent's current navigation context (module)?
- Does the tool have the property `global_access=True`?

If neither of these conditions is met, the bridge blocks the call with a hint about the missing context. This prevents agents from accessing sensitive functions that are not relevant to their current task due to hallucinations or incorrect paths.

## 2. Session Isolation (Multi-Agent Operation)

When used via web interfaces (SSE), Elemm ensures that no data leakage occurs between different agents:
- **Isolated Instances**: Every SSE connection receives its own isolated instance of the landmark bridge.
- **State Separation**: The navigation state (which module is currently active) is strictly managed per session. An agent in the "finance" module does not affect the agent working in "IT support" at the same time.

## 3. Explicit Key Management

In version 0.6.0, Elemm has removed predefined internal keys (formerly `INTERNAL_KEY`). Administrative access to the full manifest (`_INTERNAL_ALL_`) now requires explicit configuration of the `internal_access_key` in the `FastAPIProtocolManager`. Without this configuration, no privileged access to hidden landmarks is possible.

## 4. Automated Sharding and Shielding

Elemm recognizes internal fields that should not pose a security risk for an AI or are simply noise, and automatically hides them:
- Authentication headers (if defined via dependency injection).
- Internal system objects such as `request`, `response`, or `background_tasks`.
- Database sessions.

These fields are marked in the manifest as `managed_by: protocol`. This signals to the agent that these parameters exist but it does not need to set them itself.

## 5. Read-Only Protection

The `read_only=True` mode serves as a physical filter. It removes all tools of the `write` type as well as all HTTP methods except `GET` and `HEAD`. This is an effective protection against prompt injection attacks aimed at manipulating or deleting data.
