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

1. **Connect**: The agent calls `connect_to_site(url)` to establish a connection to a remote API.
2. **Manifest Discovery**: The agent calls `get_manifest()` to receive the protocol rules and authorize the session. No tool signatures are provided at this stage.
3. **Landmark Discovery**: The agent calls `get_landmarks()` to see available functional areas.
4. **Landmark Inspection**: Based on the task, the agent selects relevant landmarks and calls `inspect_landmark(id)` to retrieve full technical signatures.
5. **Execution**: The agent proceeds with `call_action()` or `execute_sequence()` once it has the required signatures.

> [!TIP]
> Agents may also use `search_landmarks(query)` as an alternative to `get_landmarks` + `inspect_landmark`. This allows direct regex-based discovery of specific tools without traversing the full hierarchy.

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

### Tool Isolation (9 Core Tools)
The Gateway never exposes raw API endpoints to the MCP client. It provides exactly **9 generic core tools**:
`connect_to_site`, `get_manifest`, `get_landmarks`, `inspect_landmark`, `search_landmarks`, `call_action`, `execute_sequence`, `list_aliases`, `clear_session`.

All domain-specific actions are accessed through `call_action` and `execute_sequence`.

### Security Policy (Guardian)
A built-in policy engine enforces restrictions before any request reaches the target API:
- **Zero-Trust Mode**: Whitelist-only access — only explicitly allowed landmarks and actions can be used.
- **Pattern Blacklists**: Block actions matching destructive keywords or regex patterns (e.g., `re:.*secret.*`).
- **Landmark Restrictions**: Hide and block entire functional areas (e.g., `admin`, `billing`).
- **HTTP Method Filtering**: Whitelist allowed methods (e.g., `GET`, `POST` only).
- **Deep Argument Inspection**: Pattern matching is applied recursively to all argument values.
- **Data Loss Prevention (DLP)**: API keys from the vault are automatically scrubbed from all responses before reaching the agent.
- **Custom Remediation Messages**: Per-pattern custom error messages for blocked operations.
- **Discovery Filtering**: Blocked landmarks are invisible in `get_landmarks` and `search_landmarks` output.

See [Gateway Reference](GATEWAY.md) for complete details.

---

## Package Structure

```
src/
├── elemm/                       # Core Protocol Library
│   ├── __init__.py              # Public API: AIProtocolManager, ElemmGateway, MetadataRegistry
│   ├── core/
│   │   ├── manager.py           # AIProtocolManager — decorator registration, call_action, get_manifest
│   │   ├── mcp.py               # MCPToolFactory — standardized MCP tool definitions
│   │   ├── presenter.py         # ManifestPresenter — Markdown/JSON manifest rendering
│   │   ├── repair.py            # SmartRepairEngine — structured error responses + fuzzy matching
│   │   ├── sequencer.py         # SequenceEngine — piping, session memory, retry logic
│   │   ├── discovery.py         # ParameterDiscovery — auto-extraction from Python type hints
│   │   ├── hygiene.py           # ResponseSquisher — _select, _filter, _limit, _offset
│   │   ├── registry.py          # MetadataRegistry — YAML metadata loader
│   │   ├── models.py            # Landmark, Manifest, Parameter data models
│   │   ├── schema.py            # SignatureGenerator — TypeScript signature rendering
│   │   ├── context.py           # Execution context container
│   │   └── exceptions.py        # Protocol-specific exceptions
│   ├── gateways/
│   │   ├── fastapi.py           # FastAPIGateway — REST server for native Elemm servers
│   │   └── mcp_server.py        # MCPGateway — STDIO MCP server for native Elemm servers
│   └── protocol/
│       └── landmarks.yaml       # Default protocol landmark definitions
│
└── elemm_gateway/               # Gateway Package (MCP Broker for external APIs)
    ├── __init__.py              # Version detection (pyproject.toml / importlib.metadata)
    ├── server.py                # ElemmGateway — main MCP server, dispatcher, connection manager
    ├── cli.py                   # CLI entry point (stdio / sse transport)
    ├── components.py            # Re-exported components for backward compatibility
    ├── services/
    │   ├── config.py            # ConfigManager — ~/.elemm/config.json with hot-reload
    │   ├── vault.py             # VaultManager — ~/.elemm/vault.json, auth injection
    │   ├── security.py          # SecurityPolicy (Guardian) — full policy engine
    │   ├── manifest.py          # ManifestBuilder — protocol globals injection
    │   ├── manifest_service.py  # ManifestService — URL probing, bridge routing, landmark inspection
    │   ├── openapi_bridge.py    # OpenAPIBridge — parses OpenAPI/Swagger specs into landmarks
    │   ├── graphql_bridge.py    # GraphQLBridge — introspects GraphQL schemas into landmarks
    │   ├── executors.py         # OpenAPIExecutor, GraphQLExecutor — HTTP request construction
    │   ├── sequencer.py         # SequenceEngine (gateway) — piping, session isolation, retry
    │   ├── hygiene.py           # ResponseSquisher (gateway) — response truncation
    │   ├── tool_registry.py     # GatewayToolRegistry — 9 core tool definitions
    │   ├── monitor.py           # ActivityMonitor — telemetry publisher to dashboard
    │   └── telemetry.py         # MonitoredReadStream / MonitoredWriteStream
    └── ui_backend/
        └── dashboard_server.py  # FastAPI dashboard (REST + WebSocket)
```

---

## Autonomous Reliability (SmartRepair)

Elemm is built for autonomous systems where human intervention is minimized:

- **Remedy Injection**: Technical errors are supplemented with human-readable "remedies". If an agent fails, it receives clear instructions on how to correct its path.
- **Validation Hardening**: Strict validation ensures that agents follow the discovery protocol and use valid, real-world data instead of placeholders.
- **Namespace Protection**: Calling a landmark area directly (e.g., `call_action(action="repos")`) is intercepted and returns guidance to use `inspect_landmark` first.
- **Fuzzy Matching**: Typos in action IDs are caught and the closest matches are suggested.
- **Type Mapping**: Automatic translation of Python types (Pydantic, Literals) into high-fidelity schemas for the LLM.
- **Forensic Auditing**: Every action and piped variable resolution is logged for complete auditability.
